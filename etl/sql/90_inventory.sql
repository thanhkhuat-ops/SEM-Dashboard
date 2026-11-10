-- Ảnh chụp tồn kho hiện tại + hàng đang về. Làm mới toàn bộ mỗi lần chạy (bảng nguồn nhỏ).

-- ---------- Nút tồn kho ----------
DELETE FROM {mart}.dim_inv_node;

-- kho nội bộ / 3PL có WMS (kho ảo Direct Import vẫn liệt kê nhưng không tính vào POOL)
INSERT INTO {mart}.dim_inv_node (node_id, node_type, country_code, title, warehouse_id, is_virtual, has_stock)
SELECT CONCAT('WH-', w.id), 'WH', IF(co.code = 'AUS', 'AU', co.code), w.title, w.id,
       IF(w.is_virtual = 1 OR COALESCE(co.code, '') NOT IN ('US', 'CA', 'AU', 'AUS'), 1, 0), 1
FROM {stg}.wh_warehouses w
LEFT JOIN {stg}.s_country co ON co.id = w.country_id
WHERE w.is_managed = 1
  AND (w.published = 1 OR EXISTS (SELECT 1 FROM {stg}.wh_product_inventory p WHERE p.warehouse_id = w.id AND p.quantity <> 0));

INSERT INTO {mart}.dim_inv_node (node_id, node_type, country_code, title, has_stock)
SELECT CONCAT('POOL-', country_code), 'POOL', country_code, CONCAT('Kho nội bộ ', country_code), 1
FROM {mart}.dim_inv_node WHERE node_type = 'WH' AND is_virtual = 0 GROUP BY country_code;

-- ---------- Kênh bán -> nút ----------
DELETE FROM {mart}.map_channel_node;

INSERT INTO {mart}.map_channel_node
  (sales_channel_id, code, title, country_code, fulfil_type, node_id, store_account_id, published)
SELECT x.id, x.code, x.title, x.cc, x.ft,
       CASE x.ft WHEN 'FBA' THEN CONCAT('FBA-', x.id) WHEN 'CG' THEN CONCAT('CG-', x.store_account_id)
                 WHEN 'MARKET' THEN NULL ELSE CONCAT('POOL-', x.cc) END,
       x.store_account_id, x.published
FROM (
  SELECT c.id, c.code, TRIM(REPLACE(c.title, CONVERT(UNHEX('C2A0') USING utf8mb4), ' ')) AS title, IF(co.code = 'AUS', 'AU', co.code) AS cc,
         c.store_account_id, c.published,
         CASE WHEN c.code LIKE 'WAYFAIR-%-CG' THEN 'CG'
              WHEN c.fulfill_method_id = 2 AND c.code LIKE 'AMZ-%' THEN 'FBA'
              WHEN c.fulfill_method_id = 2 THEN 'MARKET'
              WHEN c.fulfill_method_id = 3 THEN 'DROPSHIP'
              WHEN c.fulfill_method_id IN (4, 5) THEN 'AVC'
              WHEN c.fulfill_method_id = 8 THEN 'WHOLESALE'
              WHEN c.code LIKE 'SPF-%' THEN 'WEBSITE'
              ELSE 'FBM' END AS ft
  FROM {stg}.s_sales_channels c
  LEFT JOIN {stg}.s_sales_marketplaces m ON m.id = c.marketplace_id
  LEFT JOIN {stg}.s_country co ON co.id = m.country_id
) x;

INSERT INTO {mart}.dim_inv_node (node_id, node_type, country_code, title, store_account_id, has_stock)
SELECT CONCAT('CG-', store_account_id), 'CG', MAX(country_code),
       CONCAT('CastleGate ', REPLACE(REPLACE(MAX(title), 'Wayfair ', ''), ' CG', '')), store_account_id, 1
FROM {mart}.map_channel_node WHERE fulfil_type = 'CG' GROUP BY store_account_id;

INSERT INTO {mart}.dim_inv_node (node_id, node_type, country_code, title, store_account_id, sales_channel_id, has_stock)
SELECT node_id, 'FBA', country_code, title, store_account_id, sales_channel_id, 0
FROM {mart}.map_channel_node WHERE fulfil_type = 'FBA';

-- ---------- Tồn hiện tại ----------
DELETE FROM {mart}.fact_inv_stock;

-- kho nội bộ: tồn khả dụng của ngày mới nhất (on-hand - giữ cho đơn đang mở; nguồn ghi đè nhiều lần trong ngày theo
-- khóa sản phẩm_kho_ngày), bổ sung từ tồn on-hand nếu thiếu
INSERT INTO {mart}.fact_inv_stock (node_id, product_id, on_hand, reserved, available, unfulfillable, updated_at)
SELECT CONCAT('WH-', a.warehouse_id), a.product_id, a.quantity, a.reserved, a.inventory_available, 0, a.last_updated_dwh
FROM {stg}.wh_product_inventory_available a
JOIN (SELECT DATE(MAX(last_updated_dwh)) AS d FROM {stg}.wh_product_inventory_available) last
  ON a.last_updated_dwh >= last.d
JOIN {mart}.dim_inv_node n ON n.node_id = CONCAT('WH-', a.warehouse_id)
WHERE a.product_id > 0;

INSERT INTO {mart}.fact_inv_stock (node_id, product_id, on_hand, reserved, available, unfulfillable, updated_at)
SELECT CONCAT('WH-', p.warehouse_id), p.product_id, p.quantity, p.reserved, p.quantity - p.reserved, 0, p.lastupdated
FROM {stg}.wh_product_inventory p
JOIN {mart}.dim_inv_node n ON n.node_id = CONCAT('WH-', p.warehouse_id)
WHERE p.product_id > 0 AND p.quantity <> 0
  AND NOT EXISTS (SELECT 1 FROM {mart}.fact_inv_stock s WHERE s.node_id = CONCAT('WH-', p.warehouse_id)
                  AND s.product_id = p.product_id);

INSERT INTO {mart}.fact_inv_stock (node_id, product_id, on_hand, reserved, available, unfulfillable, updated_at)
SELECT CONCAT('POOL-', n.country_code), s.product_id, SUM(s.on_hand), SUM(s.reserved), SUM(s.available), 0, MAX(s.updated_at)
FROM {mart}.fact_inv_stock s
JOIN {mart}.dim_inv_node n ON n.node_id = s.node_id AND n.node_type = 'WH' AND n.is_virtual = 0
GROUP BY n.country_code, s.product_id;

INSERT INTO {mart}.fact_inv_stock (node_id, product_id, on_hand, reserved, available, unfulfillable, updated_at)
SELECT CONCAT('CG-', g.sales_store_account_id), g.product_id, SUM(g.qty_on_hand), SUM(g.qty_allocated),
       SUM(g.qty_fulfillable), SUM(g.qty_unfulfillable), MAX(g.update_at)
FROM {stg}.wh_wayfair_castlegate_inventory g
JOIN {mart}.dim_inv_node n ON n.node_id = CONCAT('CG-', g.sales_store_account_id)
WHERE g.product_id > 0
GROUP BY g.sales_store_account_id, g.product_id;

DELETE FROM {mart}.fact_inv_cg_detail;

INSERT INTO {mart}.fact_inv_cg_detail
  (store_account_id, cg_warehouse, product_id, on_hand, fulfillable, unfulfillable, on_order)
SELECT g.sales_store_account_id, COALESCE(cw.title, CONCAT('CG #', g.castlegate_warehouse_id)), g.product_id,
       SUM(g.qty_on_hand), SUM(g.qty_fulfillable), SUM(g.qty_unfulfillable), SUM(g.qty_on_order)
FROM {stg}.wh_wayfair_castlegate_inventory g
LEFT JOIN {stg}.wh_wayfair_castlegate_warehouses cw ON cw.id = g.castlegate_warehouse_id
WHERE g.product_id > 0
GROUP BY g.sales_store_account_id, COALESCE(cw.title, CONCAT('CG #', g.castlegate_warehouse_id)), g.product_id
HAVING SUM(g.qty_on_hand) <> 0 OR SUM(g.qty_on_order) <> 0;

-- ---------- Hàng đang về / pipeline ----------
DELETE FROM {mart}.fact_inv_incoming;

-- Container chưa nhập kho (1 Startup, 2 Pipeline, 6 đã cập cảng) -> kho nhận
INSERT INTO {mart}.fact_inv_incoming (source, ref, node_id, country_code, product_id, qty, eta, eta_estimated, stage)
SELECT 'CONTAINER', MAX(CONCAT(COALESCE(sh.shipment_number, ''), ' / ', c.container_number)),
       MAX(CONCAT('WH-', c.warehouse_id)), MAX(n.country_code), d.product_id,
       SUM(d.quantity - COALESCE(d.received_quantity, 0)),
       MAX(COALESCE(c.eta_warehouse, sh.estimated_time_import, sh.estimated_time_arrival + INTERVAL 7 DAY)),
       MAX(IF(c.eta_warehouse IS NULL, 1, 0)),
       MAX(CASE c.status WHEN 1 THEN 'Container: chuẩn bị' WHEN 2 THEN 'Container: đang trên biển'
                         WHEN 6 THEN 'Container: đã cập cảng' END)
FROM {stg}.pu_shipment_containers c
JOIN {stg}.pu_shipment_container_details d ON d.container_id = c.id
LEFT JOIN {stg}.pu_shipments sh ON sh.id = c.shipment_id
LEFT JOIN {mart}.dim_inv_node n ON n.node_id = CONCAT('WH-', c.warehouse_id)
WHERE c.status IN (1, 2, 6) AND d.product_id > 0
GROUP BY c.id, d.product_id
HAVING SUM(d.quantity - COALESCE(d.received_quantity, 0)) > 0;

-- PO còn mở: phần chưa đóng vào container (chưa biết về kho / nước nào). Trạng thái 1-3 = chờ duyệt / đã duyệt /
-- đang sản xuất (suy từ nhật ký trạng thái). ETA = ngày giao dự kiến, thiếu thì ngày đặt + 90 ngày (ước tính).
INSERT INTO {mart}.fact_inv_incoming (source, ref, node_id, country_code, product_id, qty, eta, eta_estimated, stage)
SELECT 'PO', po.order_number, NULL, NULL, d.product_id, d.qty - COALESCE(rc.qty, 0),
       COALESCE(po.estimate_delivery_date, po.order_date + INTERVAL 90 DAY),
       IF(po.estimate_delivery_date IS NULL, 1, 0),
       CASE po.status WHEN 1 THEN 'PO: chờ duyệt' WHEN 2 THEN 'PO: đã duyệt' ELSE 'PO: đang sản xuất' END
FROM {stg}.pu_sc_purchase_orders po
JOIN (SELECT purchase_order_id, product_id, SUM(quantity) AS qty FROM {stg}.pu_sc_purchase_order_details
      GROUP BY purchase_order_id, product_id) d ON d.purchase_order_id = po.id
LEFT JOIN (SELECT r.purchase_order_id, rc.product_id, SUM(rc.quantity) AS qty
           FROM {stg}.sc_delivery_receipts r JOIN {stg}.sc_delivery_receipt_containers rc ON rc.receipt_id = r.id
           GROUP BY r.purchase_order_id, rc.product_id) rc
       ON rc.purchase_order_id = po.id AND rc.product_id = d.product_id
WHERE po.status IN (1, 2, 3) AND d.product_id > 0 AND d.qty - COALESCE(rc.qty, 0) > 0;

-- Shipment lên FBA chưa nhận xong (1 working, 2 đã gửi, 3 đang vận chuyển, 6 Amazon đang nhận), trong 120 ngày gần nhất
INSERT INTO {mart}.fact_inv_incoming (source, ref, node_id, country_code, product_id, qty, eta, eta_estimated, stage)
SELECT 'FBA_SHIPMENT', MAX(COALESCE(f.shipment_id, f.shipment_name)), MAX(CONCAT('FBA-', f.sales_channel_id)),
       MAX(m.country_code), d.product_id,
       SUM(IF(f.status = 1, d.quantityshipped, GREATEST(COALESCE(d.quantityactualshipped, 0) - COALESCE(d.quantityreceived, 0), 0))),
       MAX(COALESCE(f.delivered_date, f.shipped_date + INTERVAL 10 DAY, f.estimate_ship_date + INTERVAL 10 DAY,
                    f.working_date + INTERVAL 14 DAY)),
       MAX(IF(f.delivered_date IS NULL, 1, 0)),
       MAX(CASE f.status WHEN 1 THEN 'FBA: đang chuẩn bị' WHEN 2 THEN 'FBA: đã gửi' WHEN 3 THEN 'FBA: đang vận chuyển'
                         ELSE 'FBA: Amazon đang nhận' END)
FROM {stg}.shipment__fbashipments f
JOIN {stg}.shipment__fbashipment_details d ON d.fbashipment_id = f.id
JOIN {mart}.map_channel_node m ON m.sales_channel_id = f.sales_channel_id
WHERE f.status IN (1, 2, 3, 6) AND d.product_id > 0
  AND COALESCE(f.shipped_date, f.working_date, f.estimate_ship_date) >= CURDATE() - INTERVAL 120 DAY
GROUP BY f.id, d.product_id
HAVING SUM(IF(f.status = 1, d.quantityshipped, GREATEST(COALESCE(d.quantityactualshipped, 0) - COALESCE(d.quantityreceived, 0), 0))) > 0;

-- CastleGate: số đang gửi lên theo Wayfair (qty_on_order). Bảng inbound shipment của backend không cập nhật số đã
-- nhận nên không dùng để tính. Chưa có ETA: giả định 14 ngày.
INSERT INTO {mart}.fact_inv_incoming (source, ref, node_id, country_code, product_id, qty, eta, eta_estimated, stage)
SELECT 'CG_ON_ORDER', 'Wayfair on order', CONCAT('CG-', g.sales_store_account_id), n.country_code, g.product_id,
       SUM(g.qty_on_order), CURDATE() + INTERVAL 14 DAY, 1, 'CastleGate: đang gửi lên'
FROM {stg}.wh_wayfair_castlegate_inventory g
JOIN {mart}.dim_inv_node n ON n.node_id = CONCAT('CG-', g.sales_store_account_id)
WHERE g.product_id > 0
GROUP BY g.sales_store_account_id, g.product_id, n.country_code
HAVING SUM(g.qty_on_order) > 0
