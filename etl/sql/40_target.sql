-- Fact keyword/target. term_id = 12 ký tự đầu MD5 của keyword đã viết thường (cùng quy tắc với customer_search_term_id).
-- Bid SP/SB tra theo khóa chính của sem__keywords_base_daily (keyword_id_type_YYYYMMDD) để tránh quét bảng 26GB.

DELETE FROM {mart}.fact_target_daily WHERE report_date BETWEEN :start AND :end;

-- ---------- SP ----------
INSERT INTO {mart}.fact_target_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, targeting, match_type, bid,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, orders_14d, sales_14d_usd, top_of_search_is)
SELECT DATE(s.report_date), 'SP', s.campaign_id, s.adgroup_id, s.keyword_id,
       LEFT(MD5(LOWER(TRIM(s.targeting))), 12), s.targeting, UPPER(s.match_type),
       CAST(NULLIF(k.keyword_bid, '') AS DECIMAL(12, 2)),
       c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.purchases_7d, s.units_sold_clicks_7d, s.sales_7d, s.sales_7d * fx.rate_usd,
       s.purchases_same_sku_7d, s.attributed_sales_same_sku_7d * fx.rate_usd,
       s.purchases_14d, s.sales_14d * fx.rate_usd, s.top_ofsearch_impression_share
FROM {stg}.sem__sp_targeting s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SP'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
LEFT JOIN {stg}.sem__keywords_base_daily k
       ON k.id = CONCAT(s.keyword_id, '_2_', DATE_FORMAT(s.report_date, '%Y%m%d'))
WHERE s.report_date >= :start AND s.report_date < :end_excl;

-- ---------- SB: bảng _video trước, bảng thường ghi đè nếu trùng khóa ----------
INSERT INTO {mart}.fact_target_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, targeting, match_type, bid,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT DATE(s.report_date), 'SB', s.campaign_id, s.adgroup_id, s.keyword_id,
       LEFT(MD5(LOWER(TRIM(s.targeting))), 12), s.targeting, UPPER(s.match_type),
       CAST(NULLIF(k.keyword_bid, '') AS DECIMAL(12, 2)),
       c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.total_orders_14d, NULL, s.total_sales_14d, s.total_sales_14d * fx.rate_usd,
       s.conversions_same_SKU_14d, s.sales_same_SKU_14d * fx.rate_usd,
       s.order_new2_brand_14d, s.sales_new2_brand_14d * fx.rate_usd,
       COALESCE(s.detail_pageview_14d, s.detail_pageview_clicks_14d),
       s.total_orders_14d, s.total_sales_14d * fx.rate_usd
FROM {stg}.sem__sb_keywords_video s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
LEFT JOIN {stg}.sem__keywords_base_daily k
       ON k.id = CONCAT(s.keyword_id, '_1_', DATE_FORMAT(s.report_date, '%Y%m%d'))
WHERE s.report_date >= :start AND s.report_date < :end_excl;

INSERT INTO {mart}.fact_target_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, targeting, match_type, bid,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT * FROM (
  SELECT DATE(s.report_date) AS report_date, 'SB' AS ad_type, s.campaign_id, s.adgroup_id,
         s.keyword_id AS target_id, LEFT(MD5(LOWER(TRIM(s.targeting))), 12) AS term_id,
         s.targeting, UPPER(s.match_type) AS match_type,
         CAST(NULLIF(k.keyword_bid, '') AS DECIMAL(12, 2)) AS bid,
         c.profile_id, a.currency_code,
         s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd AS cost_usd,
         s.total_orders_14d AS orders, s.total_units_14d AS units,
         s.total_sales_14d AS sales, s.total_sales_14d * fx.rate_usd AS sales_usd,
         s.conversions_same_SKU_14d AS orders_same_sku, s.sales_same_SKU_14d * fx.rate_usd AS sales_same_sku_usd,
         s.order_new2_brand_14d AS ntb_orders, s.sales_new2_brand_14d * fx.rate_usd AS ntb_sales_usd,
         COALESCE(s.detail_pageview_14d, s.detail_pageview_clicks_14d) AS dpv,
         s.total_orders_14d AS orders_14d, s.total_sales_14d * fx.rate_usd AS sales_14d_usd
  FROM {stg}.sem__sb_keywords s
  JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
  JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
  LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
  LEFT JOIN {stg}.sem__keywords_base_daily k
         ON k.id = CONCAT(s.keyword_id, '_1_', DATE_FORMAT(s.report_date, '%Y%m%d'))
  WHERE s.report_date >= :start AND s.report_date < :end_excl
) n
ON DUPLICATE KEY UPDATE
  targeting = n.targeting, match_type = n.match_type, bid = n.bid,
  impressions = n.impressions, clicks = n.clicks, cost = n.cost, cost_usd = n.cost_usd,
  orders = n.orders, units = n.units, sales = n.sales, sales_usd = n.sales_usd,
  orders_same_sku = n.orders_same_sku, sales_same_sku_usd = n.sales_same_sku_usd,
  ntb_orders = n.ntb_orders, ntb_sales_usd = n.ntb_sales_usd, dpv = n.dpv,
  orders_14d = n.orders_14d, sales_14d_usd = n.sales_14d_usd;

-- ---------- SD: bid hiện tại lấy từ sem__targetings_base ----------
INSERT INTO {mart}.fact_target_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, targeting, match_type, bid,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT x.report_date, 'SD', x.campaign_id, x.adgroup_id, x.target_id,
       LEFT(MD5(LOWER(TRIM(x.targeting))), 12), x.targeting, 'SD_TARGET', x.bid,
       x.profile_id, x.currency_code, x.impressions, x.clicks, x.cost, x.cost * x.rate,
       x.orders, x.units, x.sales, x.sales * x.rate, x.orders_same_sku, x.sales_same_sku * x.rate,
       x.ntb_orders, x.ntb_sales * x.rate, x.dpv, x.orders, x.sales * x.rate
FROM (
  SELECT DATE(s.report_date) AS report_date, s.campaign_id, s.adgroup_id, s.target_id,
         COALESCE(NULLIF(s.targeting_expression, ''), s.targeting_text) AS targeting,
         tb.bid, c.profile_id, a.currency_code, fx.rate_usd AS rate,
         s.impressions, s.clicks, s.cost,
         IF(cb.cost_type = 'VCPM', s.view_attributed_conversions_14d, s.attributed_conversions_14d) AS orders,
         IF(cb.cost_type = 'VCPM', s.view_attributed_units_ordered_14d, s.attributed_units_ordered_14d) AS units,
         IF(cb.cost_type = 'VCPM', s.view_attributed_sales_14d, s.attributed_sales_14d) AS sales,
         s.attributed_conversions_same_sku_14d AS orders_same_sku,
         s.attributed_sales_same_sku_14d AS sales_same_sku,
         IF(cb.cost_type = 'VCPM', s.view_attributed_orders_new_to_brand_14d, s.attributed_orders_new_to_brand_14d) AS ntb_orders,
         IF(cb.cost_type = 'VCPM', s.view_attributed_sales_new_to_brand_14d, s.attributed_sales_new_to_brand_14d) AS ntb_sales,
         IF(cb.cost_type = 'VCPM', s.view_attributed_detail_pageview_14d, s.attributed_detail_pageview_14d) AS dpv
  FROM {stg}.sem__sdp_targetings s
  JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SD'
  JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
  LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
  LEFT JOIN {stg}.sem__targetings_base tb ON tb.id = CONCAT(s.target_id, '_', s.adgroup_id)
  LEFT JOIN (SELECT campaign_id, MAX(UPPER(cost_type)) AS cost_type
             FROM {stg}.sem__sdp_campaigns
             WHERE report_date >= :start AND report_date < :end_excl
             GROUP BY campaign_id) cb ON cb.campaign_id = s.campaign_id
  WHERE s.report_date >= :start AND s.report_date < :end_excl
) x;
