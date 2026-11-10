-- Fact sản phẩm được quảng cáo (SP) và ASIN được mua (halo SP, Promoted/Brand Halo SB).
-- product_id: ưu tiên map theo store account + seller SKU, sau đó theo ASIN.

DELETE FROM {mart}.fact_product_daily WHERE report_date BETWEEN :start AND :end;

INSERT INTO {mart}.fact_product_daily
  (report_date, ad_type, campaign_id, adgroup_id, ad_id, asin, sku, product_id, profile_id, currency_code,
   impressions, clicks, cost, cost_usd, orders, units, sales, sales_usd,
   orders_same_sku, sales_same_sku_usd, orders_14d, sales_14d_usd)
SELECT DATE(s.report_date), 'SP', s.campaign_id, s.adgroup_id, s.ad_id, s.advertised_asin, s.advertised_sku,
       COALESCE(ms.product_id, ma.product_id), c.profile_id, a.currency_code,
       s.impressions, s.clicks, s.cost, s.cost * fx.rate_usd,
       s.purchases_7d, s.units_sold_clicks_7d, s.sales_7d, s.sales_7d * fx.rate_usd,
       s.purchases_same_sku_7d, s.attributed_sales_same_sku_7d * fx.rate_usd,
       s.purchases_14d, s.sales_14d * fx.rate_usd
FROM {stg}.sem__sp_advertised_product s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SP'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
LEFT JOIN {mart}.map_sku_product ms ON ms.store_account_id = a.store_account_id AND ms.seller_sku = s.advertised_sku
LEFT JOIN {mart}.map_asin_product ma ON ma.asin = s.advertised_asin
WHERE s.report_date >= :start AND s.report_date < :end_excl;

DELETE FROM {mart}.fact_purchased_product_daily WHERE report_date BETWEEN :start AND :end;

-- SP: ASIN khách mua khác ASIN quảng cáo (cửa sổ 7 ngày), cộng qua các keyword
INSERT INTO {mart}.fact_purchased_product_daily
  (report_date, ad_type, campaign_id, adgroup_id, advertised_asin, purchased_asin, attribution,
   profile_id, currency_code, orders, units, sales, sales_usd)
SELECT DATE(s.report_date), 'SP', s.campaign_id, s.adgroup_id, COALESCE(s.advertised_asin, ''), s.purchased_asin,
       'SP_HALO', MAX(c.profile_id), MAX(a.currency_code),
       SUM(s.purchases_other_sku_7d), SUM(s.units_sold_other_sku_7d),
       SUM(s.sales_other_sku_7d), SUM(s.sales_other_sku_7d * fx.rate_usd)
FROM {stg}.sem__sp_purchased_product s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SP'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
WHERE s.report_date >= :start AND s.report_date < :end_excl AND s.purchased_asin IS NOT NULL
GROUP BY DATE(s.report_date), s.campaign_id, s.adgroup_id, COALESCE(s.advertised_asin, ''), s.purchased_asin;

-- SB: Promoted (mua đúng sản phẩm quảng cáo) / Brand Halo (sản phẩm khác cùng brand), cửa sổ 14 ngày
INSERT INTO {mart}.fact_purchased_product_daily
  (report_date, ad_type, campaign_id, adgroup_id, advertised_asin, purchased_asin, attribution,
   profile_id, currency_code, orders, units, sales, sales_usd, ntb_orders, ntb_sales_usd)
SELECT DATE(s.report_date), 'SB', s.campaign_id, COALESCE(s.adgroup_id, ''), '', s.purchased_asin,
       IF(LOWER(s.attribution_type) LIKE 'promoted%', 'PROMOTED', 'BRAND_HALO'),
       MAX(c.profile_id), MAX(a.currency_code),
       SUM(s.total_orders_14d), SUM(s.total_units_14d), SUM(s.total_sales_14d),
       SUM(s.total_sales_14d * fx.rate_usd), SUM(s.order_new2_brand_14d), SUM(s.sales_new2_brand_14d * fx.rate_usd)
FROM {stg}.sem__sb_purchased_product s
JOIN {mart}.dim_campaign c ON c.campaign_id = s.campaign_id AND c.ad_type = 'SB'
JOIN {mart}.dim_account a ON a.profile_id = c.profile_id
LEFT JOIN {mart}.fx_daily fx ON fx.date_key = DATE(s.report_date) AND fx.currency_code = a.currency_code
WHERE s.report_date >= :start AND s.report_date < :end_excl AND s.purchased_asin IS NOT NULL
GROUP BY DATE(s.report_date), s.campaign_id, COALESCE(s.adgroup_id, ''), s.purchased_asin,
         IF(LOWER(s.attribution_type) LIKE 'promoted%', 'PROMOTED', 'BRAND_HALO');
