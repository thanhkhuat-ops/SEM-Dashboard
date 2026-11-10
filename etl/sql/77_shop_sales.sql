-- Doanh số Shopify (website) theo dòng hàng. Nguồn: s__shopify_orders_v2 + s__shopify_order_details_v2 +
-- s__shopify_order_refund_line_items. Dựng lại toàn bộ mỗi lần chạy (vài nghìn đơn).
-- Ngày = DATE(created_at) như nguồn lưu (khớp s_sales_report_data_by_orderdate của backend). Bỏ đơn voided.
-- gross = price x quantity; giảm giá = discount_allocations_amount (mã giảm giá cấp đơn đã chia về dòng);
-- net = gross - giảm giá (chưa trừ hoàn tiền, chưa gồm thuế / phí ship); refund = tiền hàng đã hoàn của dòng, tính
-- vào ngày đặt đơn. Nước = nước của kênh bán (store). Khách mới = đơn đầu tiên của customer_id trong store;
-- đơn không có customer_id (khách vãng lai, đơn từ app) = UNKNOWN. Đơn không có tỷ giá (trước ETL_BACKFILL_START) bị bỏ.

DELETE FROM {mart}.fact_shop_line;

INSERT INTO {mart}.fact_shop_line
  (line_item_id, order_id, report_date, sales_channel_id, country_code, currency_code, source_name, customer_type,
   financial_status, product_id, sku, units, gross_usd, discount_usd, net_usd, refund_units, refund_usd)
SELECT d.line_item_id, o.shopify_order_id, o.report_date, o.sales_channel_id, o.country_code, o.currency, o.source_name,
       o.customer_type, o.financial_status, COALESCE(NULLIF(d.product_id, 0), 0), d.sku, d.quantity,
       d.price * d.quantity * fx.rate_usd,
       COALESCE(d.discount_allocations_amount, d.total_discount, 0) * fx.rate_usd,
       (d.price * d.quantity - COALESCE(d.discount_allocations_amount, d.total_discount, 0)) * fx.rate_usd,
       COALESCE(r.qty, 0), COALESCE(r.subtotal, 0) * fx.rate_usd
FROM (
  SELECT o.shopify_order_id, DATE(o.created_at) AS report_date, o.sales_channel_id,
         COALESCE(IF(co.code = 'AUS', 'AU', co.code), 'US') AS country_code,
         UPPER(COALESCE(NULLIF(o.currency, ''), 'USD')) AS currency, o.source_name, o.financial_status,
         CASE WHEN COALESCE(o.customer_id, '') = '' THEN 'UNKNOWN'
              WHEN o.created_at = MIN(o.created_at) OVER (PARTITION BY o.sales_channel_id, o.customer_id) THEN 'NEW'
              ELSE 'RETURNING' END AS customer_type
  FROM {stg}.s__shopify_orders_v2 o
  LEFT JOIN {stg}.s_sales_channels ch ON ch.id = o.sales_channel_id
  LEFT JOIN {stg}.s_sales_marketplaces m ON m.id = ch.marketplace_id
  LEFT JOIN {stg}.s_country co ON co.id = m.country_id
  WHERE COALESCE(o.financial_status, '') <> 'voided' AND o.created_at IS NOT NULL
) o
JOIN {stg}.s__shopify_order_details_v2 d ON d.order_id = o.shopify_order_id
LEFT JOIN (SELECT line_item_id, SUM(quantity) AS qty, SUM(subtotal) AS subtotal
           FROM {stg}.s__shopify_order_refund_line_items GROUP BY line_item_id) r ON r.line_item_id = d.line_item_id
JOIN {mart}.fx_daily fx ON fx.date_key = o.report_date AND fx.currency_code = o.currency
