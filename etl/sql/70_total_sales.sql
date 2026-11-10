-- Tổng doanh số theo ngày đặt hàng (để tính TACoS). Nguồn: s__amazon_orders + s__amazon_order_details.
-- sales = item_price (giá bán x số lượng, chưa thuế, chưa trừ khuyến mãi), bỏ đơn Canceled.
-- Ngày = DATE(purchased_date) theo giờ lưu ở nguồn; báo cáo quảng cáo dùng giờ marketplace nên có thể lệch vài giờ.
-- Đơn Pending thường chưa có giá nên doanh số những ngày gần nhất có thể thấp hơn thực tế.
-- fba_*: phần đơn giao bằng FBA (s__amazon_orders.fulfill_channel = 'AFN'); còn lại (MFN) là FBM.

DELETE FROM {mart}.fact_total_sales_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_total_sales_daily
  (report_date, store_account_id, country_code, asin, product_id, currency_code, order_items, units, sales, sales_usd,
   fba_order_items, fba_units, fba_sales_usd)
SELECT x.report_date, x.store_id, x.country_code, x.asin, MAX(x.product_id), x.currency_code,
       COUNT(*), SUM(x.qty), SUM(x.price), SUM(x.price * fx.rate_usd),
       SUM(x.fba), SUM(x.fba * x.qty), SUM(x.fba * x.price * fx.rate_usd)
FROM (
  SELECT DATE(o.purchased_date) AS report_date, o.store_id,
         CASE LOWER(o.sales_channel)
           WHEN 'amazon.com' THEN 'US' WHEN 'amazon.ca' THEN 'CA'
           WHEN 'amazon.com.au' THEN 'AU' WHEN 'amazon.com.mx' THEN 'MX' END AS country_code,
         CASE LOWER(o.sales_channel)
           WHEN 'amazon.com' THEN 'USD' WHEN 'amazon.ca' THEN 'CAD'
           WHEN 'amazon.com.au' THEN 'AUD' WHEN 'amazon.com.mx' THEN 'MXN' END AS currency_code,
         COALESCE(d.asin, '') AS asin, NULLIF(d.product_id, 0) AS product_id,
         d.quantity_ordered AS qty, d.item_price AS price, (o.fulfill_channel = 'AFN') AS fba
  FROM {stg}.s__amazon_orders o
  JOIN {stg}.s__amazon_order_details d ON d.amazon_order_id = o.id
  WHERE o.purchased_date >= :start AND o.purchased_date < :end_excl
    AND COALESCE(o.status, '') <> 'Canceled'
    AND o.store_id IN (SELECT store_account_id FROM {mart}.dim_account WHERE store_account_id IS NOT NULL)
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code
WHERE x.country_code IS NOT NULL
GROUP BY x.report_date, x.store_id, x.country_code, x.asin, x.currency_code;

-- Bổ sung product_id còn thiếu theo ASIN
UPDATE {mart}.fact_total_sales_daily t
JOIN {mart}.map_asin_product m ON m.asin = t.asin
SET t.product_id = m.product_id
WHERE t.product_id IS NULL AND t.report_date BETWEEN :start AND :end;
