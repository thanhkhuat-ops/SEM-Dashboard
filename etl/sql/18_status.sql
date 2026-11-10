-- Trạng thái (ENABLED / PAUSED / ARCHIVED…) cho cột Trạng thái của báo cáo campaign, ad group, keyword / target.
-- Chạy sau các bước theo ngày (cần fact_campaign_budget_daily) và sau khi đồng bộ snapshot trạng thái
-- (etl/sync_staging.py: sync_states). 10_dims / 15_wf_dims dùng REPLACE nên cột state được ghi lại mỗi lần chạy.

-- Campaign không có trong snapshot mới nhất (chủ yếu SD): lấy trạng thái gần nhất đã ghi theo ngày
UPDATE {mart}.dim_campaign c
JOIN (SELECT b.ad_type, b.campaign_id, b.state,
             ROW_NUMBER() OVER (PARTITION BY b.ad_type, b.campaign_id ORDER BY b.report_date DESC) AS rn
      FROM {mart}.fact_campaign_budget_daily b
      WHERE b.state IS NOT NULL AND b.state <> '') x
  ON x.campaign_id = c.campaign_id AND x.ad_type = c.ad_type AND x.rn = 1
SET c.state = x.state
WHERE c.state IS NULL OR c.state = '';

-- Ad group: snapshot mới nhất của từng ad group
UPDATE {mart}.dim_adgroup g
JOIN (SELECT d.adgroup_id,
             CASE d.sponsored_type_id WHEN 1 THEN 'SB' WHEN 2 THEN 'SP' WHEN 3 THEN 'SD' END AS ad_type, UPPER(d.state) AS state,
             ROW_NUMBER() OVER (PARTITION BY d.adgroup_id, d.sponsored_type_id ORDER BY d.report_date DESC) AS rn
      FROM {stg}.sem__adgroups_base_daily d
      WHERE d.state IS NOT NULL AND d.state <> '') x
  ON x.adgroup_id = g.adgroup_id AND x.ad_type = g.ad_type AND x.rn = 1
SET g.state = x.state;

-- Keyword SP / SB: dòng ngày mới nhất của mỗi keyword (tra lại theo khóa chính keyword_type_YYYYMMDD)
REPLACE INTO {mart}.dim_target_state (ad_type, target_id, state, as_of)
SELECT CASE k.sponsored_type_id WHEN 1 THEN 'SB' ELSE 'SP' END, k.keyword_id, UPPER(k.keyword_state), DATE(k.report_date)
FROM (SELECT keyword_id, sponsored_type_id, MAX(report_date) AS d
      FROM {stg}.sem__keywords_base_daily
      WHERE sponsored_type_id IN (1, 2) AND keyword_state IS NOT NULL AND keyword_state <> ''
      GROUP BY keyword_id, sponsored_type_id) m
JOIN {stg}.sem__keywords_base_daily k
  ON k.id = CONCAT(m.keyword_id, '_', m.sponsored_type_id, '_', DATE_FORMAT(m.d, '%Y%m%d'));

-- Target SD: danh mục target (bản hiện tại)
REPLACE INTO {mart}.dim_target_state (ad_type, target_id, state, as_of)
SELECT 'SD', target_id, UPPER(state), DATE(lastupdate)
FROM {stg}.sem__targetings_base
WHERE sponsored_type_id = 3 AND target_id IS NOT NULL AND state IS NOT NULL;

-- Listing Wayfair: trạng thái ngày mới nhất của mỗi listing (product_info_id)
UPDATE {mart}.dim_wf_listing l
JOIN (SELECT d.product_info_id, UPPER(d.product_status) AS state,
             ROW_NUMBER() OVER (PARTITION BY d.product_info_id ORDER BY d.campaign_date_run DESC) AS rn
      FROM {stg}.sem_wayfair__product_info_daily d
      WHERE d.product_status IS NOT NULL AND d.product_status <> '') x ON x.product_info_id = l.listing_id AND x.rn = 1
SET l.state = x.state
