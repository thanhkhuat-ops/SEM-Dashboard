-- Fact campaign + placement SB + ngân sách. Tham số :start, :end (DATE), :end_excl = :end + 1 ngày.
-- Chỉ giữ campaign có trong dim_campaign và profile có trong dim_account.

-- ---------- SB placement: nạp bảng _video trước, bảng thường ghi đè nếu trùng khóa ----------
DELETE FROM {mart}.fact_placement_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_placement_daily
  (report_date, ad_type, campaign_id, placement_id, profile_id, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT DATE(s.report_date), 'SB', s.campaign_id, s.placement_id, c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.total_orders_14d, NULL, s.total_sales_14d, s.total_sales_14d * fx.rate_usd,
       s.conversions_same_SKU_14d, s.sales_same_SKU_14d * fx.rate_usd,
       s.order_new2_brand_14d, s.sales_new2_brand_14d * fx.rate_usd,
       COALESCE(s.detail_pageview_clicks_14d, s.detail_pageview_14d),
       s.total_orders_14d, s.total_sales_14d * fx.rate_usd
FROM {stg}.sem__sb_campaigns_placement_video s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
WHERE s.report_date >= :start AND s.report_date < :end_excl;

INSERT INTO {mart}.fact_placement_daily
  (report_date, ad_type, campaign_id, placement_id, profile_id, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT * FROM (
  SELECT DATE(s.report_date) AS report_date, 'SB' AS ad_type, s.campaign_id, s.placement_id,
         c.profile_id, a.currency_code,
         s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd AS cost_usd,
         s.total_orders_14d AS orders, s.total_units_14d AS units,
         s.total_sales_14d AS sales, s.total_sales_14d * fx.rate_usd AS sales_usd,
         s.conversions_same_SKU_14d AS orders_same_sku, s.sales_same_SKU_14d * fx.rate_usd AS sales_same_sku_usd,
         s.order_new2_brand_14d AS ntb_orders, s.sales_new2_brand_14d * fx.rate_usd AS ntb_sales_usd,
         COALESCE(s.detail_pageview_clicks_14d, s.detail_pageview_14d) AS dpv,
         s.total_orders_14d AS orders_14d, s.total_sales_14d * fx.rate_usd AS sales_14d_usd
  FROM {stg}.sem__sb_campaigns_placement s
  JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
  JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
  LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
  WHERE s.report_date >= :start AND s.report_date < :end_excl
) n
ON DUPLICATE KEY UPDATE
  impressions = n.impressions, clicks = n.clicks, cost = n.cost, cost_usd = n.cost_usd,
  orders = n.orders, units = n.units, sales = n.sales, sales_usd = n.sales_usd,
  orders_same_sku = n.orders_same_sku, sales_same_sku_usd = n.sales_same_sku_usd,
  ntb_orders = n.ntb_orders, ntb_sales_usd = n.ntb_sales_usd, dpv = n.dpv,
  orders_14d = n.orders_14d, sales_14d_usd = n.sales_14d_usd;

-- ---------- Fact campaign ----------
DELETE FROM {mart}.fact_campaign_daily WHERE report_date BETWEEN :start AND :end;

-- SP: campaign x ad group, cửa sổ 7 ngày
INSERT INTO {mart}.fact_campaign_daily
  (report_date, ad_type, campaign_id, adgroup_id, profile_id, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, orders_14d, sales_14d_usd)
SELECT DATE(s.report_date), 'SP', s.campaign_id, s.adgroup_id, c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.purchases_7d, s.units_sold_clicks_7d, s.sales_7d, s.sales_7d * fx.rate_usd,
       s.purchases_same_sku_7d, s.attributed_sales_same_sku_7d * fx.rate_usd,
       s.purchases_14d, s.sales_14d * fx.rate_usd
FROM {stg}.sem__sp_campaigns s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SP'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
WHERE s.report_date >= :start AND s.report_date < :end_excl;

-- SB: cộng từ placement (cửa sổ 14 ngày)
INSERT INTO {mart}.fact_campaign_daily
  (report_date, ad_type, campaign_id, adgroup_id, profile_id, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT report_date, 'SB', campaign_id, '', MAX(profile_id), MAX(currency_code),
       SUM(impressions), SUM(clicks), SUM(cost), SUM(cost_usd), SUM(orders), SUM(units),
       SUM(sales), SUM(sales_usd), SUM(orders_same_sku), SUM(sales_same_sku_usd),
       SUM(ntb_orders), SUM(ntb_sales_usd), SUM(dpv), SUM(orders_14d), SUM(sales_14d_usd)
FROM {mart}.fact_placement_daily
WHERE report_date BETWEEN :start AND :end
GROUP BY report_date, campaign_id;

-- SD: campaign vCPM dùng quy đổi view + click (giống Ads Console), CPC dùng click.
-- Lưu ý lỗi mapping nguồn: attributed_orders_new_to_brand_14d chứa DOANH SỐ NTB,
-- attributed_sales_new_to_brand_14d chứa SỐ ĐƠN NTB -> đảo lại ở đây.
INSERT INTO {mart}.fact_campaign_daily
  (report_date, ad_type, campaign_id, adgroup_id, profile_id, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, ntb_orders, ntb_sales_usd, dpv, orders_14d, sales_14d_usd)
SELECT x.report_date, 'SD', x.campaign_id, '', x.profile_id, x.currency_code,
       x.impressions, x.clicks, x.cost, x.cost * x.rate,
       x.orders, x.units, x.sales, x.sales * x.rate,
       x.orders_same_sku, x.sales_same_sku * x.rate,
       x.ntb_orders, x.ntb_sales * x.rate, x.dpv, x.orders, x.sales * x.rate
FROM (
  SELECT DATE(s.report_date) AS report_date, s.campaign_id, c.profile_id, a.currency_code, fx.rate_usd AS rate,
         s.impressions, s.clicks, s.cost,
         IF(UPPER(s.cost_type) = 'VCPM', s.view_attributed_conversions_14d, s.attributed_conversions_14d) AS orders,
         IF(UPPER(s.cost_type) = 'VCPM', s.view_attributed_units_ordered_14d, s.attributed_units_ordered_14d) AS units,
         IF(UPPER(s.cost_type) = 'VCPM', s.view_attributed_sales_14d, s.attributed_sales_14d) AS sales,
         s.attributed_conversions_same_sku_14d AS orders_same_sku,
         s.attributed_sales_same_sku_14d AS sales_same_sku,
         IF(UPPER(s.cost_type) = 'VCPM', s.view_attributed_orders_new_to_brand_14d, s.attributed_sales_new_to_brand_14d) AS ntb_orders,
         IF(UPPER(s.cost_type) = 'VCPM', s.view_attributed_sales_new_to_brand_14d, s.attributed_orders_new_to_brand_14d) AS ntb_sales,
         IF(UPPER(s.cost_type) = 'VCPM', s.view_attributed_detail_pageview_14d, s.attributed_detail_pageview_14d) AS dpv
  FROM {stg}.sem__sdp_campaigns s
  JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SD'
  JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
  LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
  WHERE s.report_date >= :start AND s.report_date < :end_excl
) x;

-- ---------- Ngân sách / trạng thái theo ngày + Top-of-search IS (SP) ----------
DELETE FROM {mart}.fact_campaign_budget_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_campaign_budget_daily
  (report_date, ad_type, campaign_id, profile_id, budget, budget_usd, budget_type, state)
SELECT DATE(d.report_date), c.ad_type, d.campaign_id, c.profile_id,
       d.budget, d.budget * fx.rate_usd, UPPER(d.budget_type), UPPER(d.state)
FROM {stg}.sem__campaigns_base_daily d
JOIN {mart}.dim_campaign c ON c.campaign_id = d.campaign_id AND c.sponsored_type_id = d.sponsored_type_id
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(d.report_date) AND fx.currency_code = a.currency_code
WHERE d.report_date >= :start AND d.report_date < :end_excl;

UPDATE {mart}.fact_campaign_budget_daily b
JOIN {stg}.sem__sp_campaigns_topofsearch t
  ON t.campaign_id = b.campaign_id AND DATE(t.report_date) = b.report_date
SET b.top_of_search_is = t.top_ofsearch_impression_share
WHERE b.ad_type = 'SP' AND b.report_date BETWEEN :start AND :end
  AND t.report_date >= :start AND t.report_date < :end_excl;
