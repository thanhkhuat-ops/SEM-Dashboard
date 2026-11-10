-- Fact customer search term (SP + SB). term_id = customer_search_term_id của staging.

DELETE FROM {mart}.fact_search_term_daily WHERE report_date BETWEEN :start AND :end;

-- ---------- SP ----------
INSERT INTO {mart}.fact_search_term_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, target_term_id, targeting, match_type,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, orders_14d, sales_14d_usd)
SELECT DATE(s.report_date), 'SP', s.campaign_id, s.adgroup_id, s.keyword_id, s.customer_search_term_id,
       LEFT(MD5(LOWER(TRIM(s.targeting))), 12), s.targeting, UPPER(s.match_type),
       c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.purchases_7d, s.units_sold_clicks_7d, s.sales_7d, s.sales_7d * fx.rate_usd,
       s.purchases_same_sku_7d, s.attributed_sales_same_sku_7d * fx.rate_usd,
       s.purchases_14d, s.sales_14d * fx.rate_usd
FROM {stg}.sem__sp_search_term s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SP'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
WHERE s.report_date >= :start AND s.report_date < :end_excl;

-- ---------- SB: bảng _video trước, bảng thường ghi đè nếu trùng khóa ----------
INSERT INTO {mart}.fact_search_term_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, target_term_id, targeting, match_type,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, sales, sales_usd,
   orders_14d, sales_14d_usd)
SELECT DATE(s.report_date), 'SB', s.campaign_id, s.adgroup_id, s.keyword_id, s.customer_search_term_id,
       LEFT(MD5(LOWER(TRIM(s.targeting))), 12), s.targeting, UPPER(s.match_type),
       c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.total_orders_14d, s.total_sales_14d, s.total_sales_14d * fx.rate_usd,
       s.total_orders_14d, s.total_sales_14d * fx.rate_usd
FROM {stg}.sem__sb_search_term_video s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
WHERE s.report_date >= :start AND s.report_date < :end_excl;

INSERT INTO {mart}.fact_search_term_daily
  (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id, target_term_id, targeting, match_type,
   profile_id, currency_code, impressions, clicks, cost, cost_usd, orders, sales, sales_usd,
   orders_14d, sales_14d_usd)
SELECT * FROM (
  SELECT DATE(s.report_date) AS report_date, 'SB' AS ad_type, s.campaign_id, s.adgroup_id,
         s.keyword_id AS target_id, s.customer_search_term_id AS term_id,
         LEFT(MD5(LOWER(TRIM(s.targeting))), 12) AS target_term_id, s.targeting,
         UPPER(s.match_type) AS match_type, c.profile_id, a.currency_code,
         s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd AS cost_usd,
         s.total_orders_14d AS orders, s.total_sales_14d AS sales, s.total_sales_14d * fx.rate_usd AS sales_usd,
         s.total_orders_14d AS orders_14d, s.total_sales_14d * fx.rate_usd AS sales_14d_usd
  FROM {stg}.sem__sb_search_term s
  JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
  JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
  LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
  WHERE s.report_date >= :start AND s.report_date < :end_excl
) n
ON DUPLICATE KEY UPDATE
  targeting = n.targeting, match_type = n.match_type,
  impressions = n.impressions, clicks = n.clicks, cost = n.cost, cost_usd = n.cost_usd,
  orders = n.orders, sales = n.sales, sales_usd = n.sales_usd,
  orders_14d = n.orders_14d, sales_14d_usd = n.sales_14d_usd;
