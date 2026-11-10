-- Bước sau cùng: map ad group -> sản phẩm và gắn Auto/Manual cho campaign SP. Tính trên toàn bộ lịch sử trong mart.

TRUNCATE TABLE {mart}.map_adgroup_product;

INSERT INTO {mart}.map_adgroup_product
  (ad_type, campaign_id, adgroup_id, product_id, group_id, brand_id, weight, weight_share, is_dominant)
SELECT t.ad_type, t.campaign_id, t.adgroup_id, t.product_id, t.group_id, t.brand_id, t.w,
       t.w / NULLIF(SUM(t.w) OVER (PARTITION BY t.ad_type, t.campaign_id, t.adgroup_id), 0),
       IF(ROW_NUMBER() OVER (PARTITION BY t.ad_type, t.campaign_id, t.adgroup_id ORDER BY t.w DESC, t.product_id) = 1, 1, 0)
FROM (
  -- SP: tỷ trọng chi phí của từng sản phẩm trong ad group
  SELECT f.ad_type, f.campaign_id, f.adgroup_id, f.product_id, p.group_id, p.brand_id,
         SUM(COALESCE(f.cost_usd, 0)) + 0.0001 AS w
  FROM {mart}.fact_product_daily f
  JOIN {mart}.dim_product p ON p.product_id = f.product_id
  GROUP BY f.ad_type, f.campaign_id, f.adgroup_id, f.product_id, p.group_id, p.brand_id
  UNION ALL
  -- SB: tỷ trọng doanh số Promoted của từng sản phẩm
  SELECT pp.ad_type, pp.campaign_id, pp.adgroup_id, m.product_id, p.group_id, p.brand_id,
         SUM(COALESCE(pp.sales_usd, 0)) + 0.0001 AS w
  FROM {mart}.fact_purchased_product_daily pp
  JOIN {mart}.map_asin_product m ON m.asin = pp.purchased_asin
  JOIN {mart}.dim_product p ON p.product_id = m.product_id
  WHERE pp.ad_type = 'SB' AND pp.attribution = 'PROMOTED'
  GROUP BY pp.ad_type, pp.campaign_id, pp.adgroup_id, m.product_id, p.group_id, p.brand_id
) t;

-- SP Auto: có target close-match / loose-match / substitutes / complements
UPDATE {mart}.dim_campaign c
LEFT JOIN (
  SELECT campaign_id,
         MAX(LOWER(targeting) IN ('close-match', 'loose-match', 'substitutes', 'complements')
             OR match_type = 'TARGETING_EXPRESSION_PREDEFINED') AS is_auto
  FROM {mart}.fact_target_daily
  WHERE ad_type = 'SP'
  GROUP BY campaign_id
) t ON t.campaign_id = c.campaign_id
SET c.targeting_mode = CASE WHEN t.campaign_id IS NULL THEN NULL WHEN t.is_auto = 1 THEN 'AUTO' ELSE 'MANUAL' END
WHERE c.ad_type = 'SP';
