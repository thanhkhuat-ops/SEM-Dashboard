-- Doanh số theo kênh bán x sản phẩm x ngày, từ s_sales_report_data_by_orderdate (mọi kênh: Amazon FBA/FBM, Wayfair
-- dropship/CastleGate, website, eBay, Walmart...). Combo được tách ra sản phẩm con (tối đa 2 cấp) theo prd_productcombo,
-- vì tồn kho nằm ở sản phẩm con; doanh thu của combo chia cho các con theo tỷ lệ số lượng.
-- Tham số :start, :end (DATE).

DELETE FROM {mart}.fact_channel_sales_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_channel_sales_daily
  (report_date, sales_channel_id, product_id, units, revenue, revenue_usd, combo_units)
SELECT x.report_date, x.sales_channel_id, x.product_id, SUM(x.units), SUM(x.revenue), SUM(x.revenue * fx.rate_usd),
       SUM(x.combo_units)
FROM (
  -- sản phẩm thường
  SELECT s.report_date, s.sales_channel_id, s.product_id, s.total_quantity AS units, s.revenue,
         COALESCE(s.currency, 'USD') AS currency, 0 AS combo_units
  FROM {stg}.s_sales_report_data_by_orderdate s
  WHERE s.report_date BETWEEN :start AND :end AND s.product_id > 0
    AND NOT EXISTS (SELECT 1 FROM {stg}.prd_productcombo c WHERE c.product_id = s.product_id AND c.published = 1)
  UNION ALL
  -- combo cấp 1 (con không phải combo)
  SELECT s.report_date, s.sales_channel_id, c.child_id, s.total_quantity * c.quantity,
         s.revenue * c.quantity / t.total_qty, COALESCE(s.currency, 'USD'), s.total_quantity * c.quantity
  FROM {stg}.s_sales_report_data_by_orderdate s
  JOIN {stg}.prd_productcombo c ON c.product_id = s.product_id AND c.published = 1
  JOIN (SELECT product_id, SUM(quantity) AS total_qty FROM {stg}.prd_productcombo WHERE published = 1
        GROUP BY product_id) t ON t.product_id = s.product_id
  WHERE s.report_date BETWEEN :start AND :end
    AND NOT EXISTS (SELECT 1 FROM {stg}.prd_productcombo c2 WHERE c2.product_id = c.child_id AND c2.published = 1)
  UNION ALL
  -- combo cấp 2 (con của con)
  SELECT s.report_date, s.sales_channel_id, c2.child_id, s.total_quantity * c.quantity * c2.quantity,
         s.revenue * c.quantity / t.total_qty * c2.quantity / t2.total_qty, COALESCE(s.currency, 'USD'),
         s.total_quantity * c.quantity * c2.quantity
  FROM {stg}.s_sales_report_data_by_orderdate s
  JOIN {stg}.prd_productcombo c ON c.product_id = s.product_id AND c.published = 1
  JOIN {stg}.prd_productcombo c2 ON c2.product_id = c.child_id AND c2.published = 1
  JOIN (SELECT product_id, SUM(quantity) AS total_qty FROM {stg}.prd_productcombo WHERE published = 1
        GROUP BY product_id) t ON t.product_id = s.product_id
  JOIN (SELECT product_id, SUM(quantity) AS total_qty FROM {stg}.prd_productcombo WHERE published = 1
        GROUP BY product_id) t2 ON t2.product_id = c.child_id
  WHERE s.report_date BETWEEN :start AND :end
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency
GROUP BY x.report_date, x.sales_channel_id, x.product_id;

-- Lịch sử tồn on-hand theo ngày: POOL = các kho nội bộ thật của một nước (trace chỉ lưu dòng tồn > 0, nên ngày không có
-- dòng = hết hàng), CG = CastleGate của một tài khoản. Lịch sử FBA-<kênh> do etl/fba_sheet.py ghi, không xóa ở đây.
DELETE FROM {mart}.fact_inv_stock_daily WHERE stock_date BETWEEN :start AND :end
  AND (node_id LIKE 'POOL-%' OR node_id LIKE 'CG-%');

INSERT INTO {mart}.fact_inv_stock_daily (stock_date, node_id, product_id, on_hand)
SELECT t.the_date, CONCAT('POOL-', IF(co.code = 'AUS', 'AU', co.code)), t.product_id, SUM(t.quantity)
FROM {stg}.wh_product_inventory_trace t
JOIN {stg}.wh_warehouses w ON w.id = t.warehouse_id AND w.is_virtual = 0
JOIN {stg}.s_country co ON co.id = w.country_id
WHERE t.the_date BETWEEN :start AND :end AND t.product_id > 0 AND co.code IN ('US', 'CA', 'AUS', 'AU')
GROUP BY t.the_date, co.code, t.product_id;

INSERT INTO {mart}.fact_inv_stock_daily (stock_date, node_id, product_id, on_hand)
SELECT h.date, CONCAT('CG-', h.sales_store_account_id), h.product_id, SUM(h.on_hand_quantity)
FROM {stg}.wh_wayfair_castlegate_inventory_history h
WHERE h.date BETWEEN :start AND :end AND h.product_id > 0
GROUP BY h.date, h.sales_store_account_id, h.product_id
