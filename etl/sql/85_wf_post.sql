-- Bước sau cùng cho Wayfair, tính trên toàn bộ lịch sử trong mart:
-- loại targeting + store chính của campaign, và map campaign -> nhóm SP / brand theo tỷ trọng spend của listing.

-- (dùng ROW_NUMBER thay GROUP_CONCAT: campaign chạy lâu có hàng trăm ngày, vượt group_concat_max_len)
UPDATE {mart}.dim_wf_campaign c
JOIN (
  SELECT campaign_id, targeting_type FROM (
    SELECT campaign_id, targeting_type,
           ROW_NUMBER() OVER (PARTITION BY campaign_id ORDER BY report_date DESC, cost DESC) AS rn
    FROM {mart}.fact_wf_campaign_daily) x
  WHERE rn = 1
) t ON t.campaign_id = c.campaign_id
JOIN (
  SELECT campaign_id, country_code FROM (
    SELECT campaign_id, country_code, ROW_NUMBER() OVER (PARTITION BY campaign_id ORDER BY SUM(cost) DESC) AS rn
    FROM {mart}.fact_wf_campaign_daily GROUP BY campaign_id, country_code) y
  WHERE rn = 1
) k ON k.campaign_id = c.campaign_id
SET c.targeting_type = t.targeting_type, c.country_code = k.country_code;

TRUNCATE TABLE {mart}.map_wf_campaign_group;

INSERT INTO {mart}.map_wf_campaign_group (campaign_id, group_id, brand_id, weight_share, is_dominant)
SELECT t.campaign_id, t.group_id, t.brand_id,
       t.w / NULLIF(SUM(t.w) OVER (PARTITION BY t.campaign_id), 0),
       IF(ROW_NUMBER() OVER (PARTITION BY t.campaign_id ORDER BY t.w DESC, t.group_id) = 1, 1, 0)
FROM (
  SELECT f.campaign_id, l.group_id, MAX(l.brand_id) AS brand_id, SUM(COALESCE(f.cost_usd, 0)) + 0.0001 AS w
  FROM (SELECT campaign_id, listing_id, SUM(cost_usd) AS cost_usd FROM {mart}.fact_wf_product_daily
        GROUP BY campaign_id, listing_id
        UNION ALL
        SELECT campaign_id, listing_id, SUM(cost_usd) FROM {mart}.fact_wf_keyword_daily
        GROUP BY campaign_id, listing_id) f
  JOIN {mart}.dim_wf_listing l ON l.listing_id = f.listing_id
  WHERE l.group_id IS NOT NULL
  GROUP BY f.campaign_id, l.group_id
) t
