-- Tổng doanh số Wayfair theo giá sỉ (để tính TACoS). Nguồn: s__wayfair_orders + s__wayfair_order_details.
-- sales = wholesale_price x (quantity - cancelled_quantity), bỏ PO CANCELLED/REJECTED và đơn REPLACEMENT.
-- Tài khoản = kênh bán -> store account -> wayfair_accounts. Nước = nước của khách (wayfair.com / wayfair.ca),
-- tiền tệ = tiền tệ của kênh bán. Ngày = DATE(po_date).

DELETE FROM {mart}.fact_wf_total_sales_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_wf_total_sales_daily
  (report_date, account_id, country_code, order_type, wayfair_sku, product_id, currency_code,
   order_lines, units, sales, sales_usd)
SELECT x.report_date, x.account_id, x.country_code, x.order_type, x.wayfair_sku, x.product_id, x.currency_code,
       COUNT(*), SUM(x.qty), SUM(x.qty * x.price), SUM(x.qty * x.price * fx.rate_usd)
FROM (
  SELECT DATE(o.po_date) AS report_date, wa.id AS account_id,
         CASE WHEN UPPER(o.customer_country) IN ('CA', 'CAN') THEN 'CA'
              WHEN UPPER(o.customer_country) IN ('US', 'USA') THEN 'US'
              ELSE COALESCE(co.code, 'US') END AS country_code,
         o.order_type, COALESCE(d.wayfair_sku, '') AS wayfair_sku,
         COALESCE(NULLIF(d.product_id, 0), pw.product_id, 0) AS product_id,
         COALESCE(co.currency_code, wa.currency_code) AS currency_code,
         d.quantity - COALESCE(d.cancelled_quantity, 0) AS qty, d.wholesale_price AS price
  FROM {stg}.s__wayfair_orders o
  JOIN {stg}.s__wayfair_order_details d ON d.order_id = o.id
  JOIN {stg}.s_sales_channels ch ON ch.id = o.sales_channel_id
  JOIN {stg}.wayfair_accounts wa ON wa.store_account_id = ch.store_account_id
  LEFT JOIN {stg}.s_sales_marketplaces m ON m.id = ch.marketplace_id
  LEFT JOIN {stg}.s_country co ON co.id = m.country_id
  LEFT JOIN (SELECT supplier_part, MAX(NULLIF(product_id, 0)) AS product_id FROM {stg}.prd_wayfair_products
             GROUP BY supplier_part) pw ON pw.supplier_part = d.item_number
  WHERE o.po_date >= :start AND o.po_date < :end_excl
    AND UPPER(COALESCE(o.status, '')) NOT IN ('CANCELLED', 'REJECTED')
    AND o.order_type IN ('dropship', 'castle_gate')
    AND d.quantity - COALESCE(d.cancelled_quantity, 0) > 0 AND d.wholesale_price > 0
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code
GROUP BY x.report_date, x.account_id, x.country_code, x.order_type, x.wayfair_sku, x.product_id, x.currency_code
