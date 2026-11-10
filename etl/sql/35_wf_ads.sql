-- Fact quảng cáo Wayfair Sponsored Products. Tham số :start, :end (DATE), :end_excl = :end + 1 ngày.
-- sales = doanh số giá sỉ (attr_wholesale_cost), retail_sales = doanh số giá bán lẻ (attr_rsales); view-through 14 ngày.
-- Tiền tệ theo store: wayfair.ca = CAD, còn lại USD. Chỉ giữ campaign có trong dim_wf_campaign.

-- ---------- Campaign ----------
DELETE FROM {mart}.fact_wf_campaign_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_wf_campaign_daily
  (report_date, campaign_id, country_code, account_id, targeting_type, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd, retail_sales, retail_sales_usd)
SELECT x.report_date, x.campaign_id, x.country_code, x.account_id, x.targeting_type, x.currency_code,
       x.impressions, x.clicks, x.cost, x.cost * fx.rate_usd, x.orders, x.units,
       x.sales, x.sales * fx.rate_usd, x.retail_sales, x.retail_sales * fx.rate_usd
FROM (
  SELECT s.campaign_date_run AS report_date, s.campaign_id,
         IF(s.store_url LIKE '%wayfair.ca%', 'CA', 'US') AS country_code,
         IF(s.store_url LIKE '%wayfair.ca%', 'CAD', 'USD') AS currency_code,
         c.account_id, s.targeting_type, s.impressions, s.clicks, s.spend AS cost,
         s.attr_orders_wview_through_Day_14 AS orders, s.attr_units_wview_through_Day_14 AS units,
         s.attr_wholesale_cost_wview_through_Day_14 AS sales, s.attr_rsales_wview_through_Day_14 AS retail_sales
  FROM {stg}.sem_wayfair__wsp_campaign s
  JOIN {mart}.dim_wf_campaign c ON c.campaign_id = s.campaign_id
  WHERE s.campaign_date_run >= :start AND s.campaign_date_run < :end_excl
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code;

-- ---------- Listing được quảng cáo ----------
DELETE FROM {mart}.fact_wf_product_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_wf_product_daily
  (report_date, campaign_id, listing_id, country_code, account_id, wayfair_sku, class_name, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd, retail_sales, retail_sales_usd)
SELECT x.report_date, x.campaign_id, x.listing_id, x.country_code, x.account_id, x.wayfair_sku, x.class_name,
       x.currency_code, x.impressions, x.clicks, x.cost, x.cost * fx.rate_usd, x.orders, x.units,
       x.sales, x.sales * fx.rate_usd, x.retail_sales, x.retail_sales * fx.rate_usd
FROM (
  SELECT s.campaign_date_run AS report_date, s.campaign_id, s.product_info_id AS listing_id,
         IF(s.store_url LIKE '%wayfair.ca%', 'CA', 'US') AS country_code,
         IF(s.store_url LIKE '%wayfair.ca%', 'CAD', 'USD') AS currency_code,
         c.account_id, SUBSTRING_INDEX(s.product_info_id, '_', 1) AS wayfair_sku, s.name_of_class AS class_name,
         s.impressions, s.clicks, s.spend AS cost,
         s.attr_orders_wview_through_Day_14 AS orders, s.attr_units_wview_through_Day_14 AS units,
         s.attr_wholesale_cost_wview_through_Day_14 AS sales, s.attr_rsales_wview_through_Day_14 AS retail_sales
  FROM {stg}.sem_wayfair__wsp_product s
  JOIN {mart}.dim_wf_campaign c ON c.campaign_id = s.campaign_id
  WHERE s.campaign_date_run >= :start AND s.campaign_date_run < :end_excl
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code;

-- ---------- Keyword x listing (report keyword targeting). Bid tra theo khóa chính keyword_info_id_YYYYMMDD ----------
DELETE FROM {mart}.fact_wf_keyword_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_wf_keyword_daily
  (report_date, campaign_id, keyword_info_id, listing_id, country_code, account_id, term_id, keyword, match_type,
   bid, currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   retail_sales, retail_sales_usd)
SELECT x.report_date, x.campaign_id, x.keyword_info_id, x.listing_id, x.country_code, x.account_id,
       LEFT(MD5(LOWER(TRIM(x.keyword))), 12), x.keyword, x.match_type, x.bid, x.currency_code,
       x.impressions, x.clicks, x.cost, x.cost * fx.rate_usd, x.orders, NULL,
       x.sales, x.sales * fx.rate_usd, x.retail_sales, x.retail_sales * fx.rate_usd
FROM (
  SELECT s.campaign_date_run AS report_date, s.campaign_id, s.keyword_info_id,
         COALESCE(s.product_info_id, '') AS listing_id,
         IF(s.store_url LIKE '%wayfair.ca%', 'CA', 'US') AS country_code,
         IF(s.store_url LIKE '%wayfair.ca%', 'CAD', 'USD') AS currency_code,
         c.account_id, k.keyword_value AS keyword, UPPER(mt.keyword_match_type) AS match_type,
         b.keyword_max_bid AS bid, s.impressions, s.clicks, s.spend AS cost,
         s.attr_orders_wview_through_Day_14 AS orders,
         s.attr_wholesale_cost_wview_through_Day_14 AS sales, s.attr_rsales_wview_through_Day_14 AS retail_sales
  FROM {stg}.sem_wayfair__wsp_keyword_targeting s
  JOIN {mart}.dim_wf_campaign c ON c.campaign_id = s.campaign_id
  LEFT JOIN {stg}.sem_wayfair__keyword_info k ON k.id = s.keyword_info_id
  LEFT JOIN {stg}.sem_wayfair__keyword_matchtype mt ON mt.id = k.keyword_match_type_id
  LEFT JOIN {stg}.sem_wayfair__keyword_info_daily b
         ON b.id = CONCAT(s.keyword_info_id, '_', DATE_FORMAT(s.campaign_date_run, '%Y%m%d'))
  WHERE s.campaign_date_run >= :start AND s.campaign_date_run < :end_excl
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code;

-- ---------- Keyword x search term (report keyword optimization, cộng gộp các tổ hợp thuộc tính lọc) ----------
DELETE FROM {mart}.fact_wf_search_term_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_wf_search_term_daily
  (report_date, campaign_id, keyword_info_id, term_id, country_code, account_id, target_term_id, keyword, match_type,
   currency_code, impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd, retail_sales, retail_sales_usd)
SELECT x.report_date, x.campaign_id, x.keyword_info_id, x.term_id, x.country_code, MAX(x.account_id),
       LEFT(MD5(LOWER(TRIM(MAX(k.keyword_value)))), 12), MAX(k.keyword_value), UPPER(MAX(mt.keyword_match_type)),
       x.currency_code, SUM(x.impressions), SUM(x.clicks), SUM(x.cost), SUM(x.cost) * MAX(fx.rate_usd),
       SUM(x.orders), SUM(x.units), SUM(x.sales), SUM(x.sales) * MAX(fx.rate_usd),
       SUM(x.retail_sales), SUM(x.retail_sales) * MAX(fx.rate_usd)
FROM (
  SELECT s.campaign_date_run AS report_date, s.campaign_id, s.keyword_info_id,
         IF(TRIM(COALESCE(s.customer_search_term, '')) = '', '',
            LEFT(MD5(LOWER(TRIM(s.customer_search_term))), 12)) AS term_id,
         IF(s.store_url LIKE '%wayfair.ca%', 'CA', 'US') AS country_code,
         IF(s.store_url LIKE '%wayfair.ca%', 'CAD', 'USD') AS currency_code,
         c.account_id, s.impressions, s.clicks, s.spend AS cost,
         s.attr_orders_wview_through_Day_14 AS orders, s.attr_units_wview_through_Day_14 AS units,
         s.attr_wholesale_cost_wview_through_Day_14 AS sales, s.attr_rsales_wview_through_Day_14 AS retail_sales
  FROM {stg}.sem_wayfair__wsp_keyword_optimization s
  JOIN {mart}.dim_wf_campaign c ON c.campaign_id = s.campaign_id
  WHERE s.campaign_date_run >= :start AND s.campaign_date_run < :end_excl
) x
LEFT JOIN {stg}.sem_wayfair__keyword_info k ON k.id = x.keyword_info_id
LEFT JOIN {stg}.sem_wayfair__keyword_matchtype mt ON mt.id = k.keyword_match_type_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code
GROUP BY x.report_date, x.campaign_id, x.keyword_info_id, x.term_id, x.country_code, x.currency_code;

-- ---------- Ngân sách / trạng thái theo ngày (tiền tệ theo store của campaign trong ngày đó) ----------
-- Nguồn đôi khi có 2 dòng cùng campaign x ngày (vd 2025-04-30): lấy daily cap lớn nhất.
DELETE FROM {mart}.fact_wf_budget_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_wf_budget_daily
  (report_date, campaign_id, account_id, state, daily_cap, daily_cap_usd, currency_code)
SELECT x.report_date, x.campaign_id, MAX(x.account_id), MAX(x.state), MAX(x.daily_cap), MAX(x.daily_cap * fx.rate_usd),
       MAX(x.currency_code)
FROM (
  SELECT d.campaign_date_run AS report_date, d.campaign_id, c.account_id, d.campaign_status AS state,
         CAST(NULLIF(REGEXP_REPLACE(d.campaign_daily_cap, '[^0-9.]', ''), '') AS DECIMAL(12, 2)) AS daily_cap,
         COALESCE(f.currency_code, IF(c.country_code = 'CA', 'CAD', 'USD')) AS currency_code
  FROM {stg}.sem_wayfair__campaign_info_daily d
  JOIN {mart}.dim_wf_campaign c ON c.campaign_id = d.campaign_id
  LEFT JOIN (SELECT report_date, campaign_id, MAX(currency_code) AS currency_code FROM {mart}.fact_wf_campaign_daily
             WHERE report_date BETWEEN :start AND :end GROUP BY report_date, campaign_id) f
         ON f.report_date = d.campaign_date_run AND f.campaign_id = d.campaign_id
  WHERE d.campaign_date_run >= :start AND d.campaign_date_run < :end_excl
) x
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = x.report_date AND fx.currency_code = x.currency_code
GROUP BY x.report_date, x.campaign_id;

-- ---------- Share of search (Search Term Research). Tỷ lệ ở nguồn tính theo %, lưu dạng phân số ----------
DELETE FROM {mart}.fact_wf_share_of_search WHERE report_date BETWEEN :start AND :end;

INSERT IGNORE INTO {mart}.fact_wf_share_of_search
  (report_date, account_id, catalog, term_id, term, class_name, impressions_30d, class_share,
   share_search, share_page1, share_top8)
SELECT s.report_date, s.account_id, s.brand_catalog, LEFT(MD5(LOWER(TRIM(t.customer_search_term))), 12),
       LEFT(t.customer_search_term, 255), s.name_of_class, s.total_search_term_impressions_in_the_last_30_days,
       s.search_term_share_of_impressions_for_given_class_percent / 100, s.supplier_share_of_search_percent / 100,
       s.supplier_share_of_page_1_percent / 100, s.supplier_share_of_top_8_percent / 100
FROM {stg}.sem_wayfair__wsp_search_term_research s
JOIN {stg}.sem_wayfair__search_term_info t ON t.id = s.customer_search_term_id
WHERE s.report_date >= :start AND s.report_date < :end_excl
  AND t.customer_search_term IS NOT NULL AND TRIM(t.customer_search_term) <> ''
