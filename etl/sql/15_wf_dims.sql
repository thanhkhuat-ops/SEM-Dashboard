-- Dimension Wayfair: làm mới toàn bộ mỗi lần chạy (bảng nguồn nhỏ). Chạy sau 10_dims.sql (cần dim_product).

REPLACE INTO {mart}.dim_wf_account (account_id, account_name, short_name, currency_code, store_account_id)
SELECT w.id, w.account_name,
       CASE w.id WHEN '66301' THEN 'Infideals' WHEN '196216' THEN 'Hurav' WHEN '184614' THEN 'DHI'
                 ELSE TRIM(SUBSTRING_INDEX(w.account_name, ' ', 1)) END,
       w.currency_code, w.store_account_id
FROM {stg}.wayfair_accounts w;

-- Trạng thái / ngân sách lấy từ snapshot mới nhất của từng campaign trong bản sao campaign_info_daily.
-- targeting_type và country_code do 85_wf_post.sql ghi từ bảng fact nên không ghi đè ở đây.
INSERT INTO {mart}.dim_wf_campaign
  (campaign_id, account_id, campaign_name, state, daily_cap, lifetime_budget, start_date, end_date)
SELECT * FROM (
  SELECT ci.campaign_id, ci.account_id, ci.campaign_name, d.campaign_status AS state,
         CAST(NULLIF(REGEXP_REPLACE(d.campaign_daily_cap, '[^0-9.]', ''), '') AS DECIMAL(12, 2)) AS daily_cap,
         d.campaign_lifetime_budget AS lifetime_budget, d.campaign_init_date AS start_date,
         d.campaign_end_date AS end_date
  FROM {stg}.sem_wayfair__campaign_info ci
  LEFT JOIN (SELECT x.*, ROW_NUMBER() OVER (PARTITION BY x.campaign_id ORDER BY x.campaign_date_run DESC) AS rn
             FROM {stg}.sem_wayfair__campaign_info_daily x) d
         ON d.campaign_id = ci.campaign_id AND d.rn = 1
) n
ON DUPLICATE KEY UPDATE
  account_id = n.account_id, campaign_name = n.campaign_name,
  state = COALESCE(n.state, dim_wf_campaign.state), daily_cap = COALESCE(n.daily_cap, dim_wf_campaign.daily_cap),
  lifetime_budget = COALESCE(n.lifetime_budget, dim_wf_campaign.lifetime_budget),
  start_date = COALESCE(n.start_date, dim_wf_campaign.start_date),
  end_date = COALESCE(n.end_date, dim_wf_campaign.end_date);

-- Listing -> sản phẩm: (1) bảng map của team SEM, (2) map theo tháng upload bulk ads,
-- (3) part number của listing tra trong danh sách sản phẩm Wayfair (prd_wayfair_products)
DELETE FROM {mart}.map_wf_listing_product;

INSERT IGNORE INTO {mart}.map_wf_listing_product (listing_id, product_id)
SELECT sem_wayfair_id, product_id FROM {stg}.wayfair_map_sku_product_id
WHERE product_id > 0 AND sem_wayfair_id IS NOT NULL
UNION
SELECT sem_wayfair_id, product_id FROM {stg}.sem_wayfair_map_sku_product_id
WHERE product_id > 0 AND sem_wayfair_id IS NOT NULL;

INSERT IGNORE INTO {mart}.map_wf_listing_product (listing_id, product_id)
SELECT p.id, w.product_id
FROM {stg}.sem_wayfair__product_info p
JOIN JSON_TABLE(CONCAT('["', REPLACE(REPLACE(COALESCE(p.first_10_part_numbers, ''), ' ', ''), ',', '","'), '"]'),
                '$[*]' COLUMNS (part VARCHAR(100) PATH '$')) j
JOIN (SELECT supplier_part, MAX(product_id) AS product_id FROM {stg}.prd_wayfair_products
      WHERE product_id > 0 GROUP BY supplier_part) w ON w.supplier_part = j.part
WHERE j.part <> ''
  AND NOT EXISTS (SELECT 1 FROM {mart}.map_wf_listing_product m WHERE m.listing_id = p.id);

-- Sản phẩm đại diện của listing = sản phẩm bán nhiều unit nhất trên Wayfair (theo đơn đã nạp), rồi id nhỏ nhất
REPLACE INTO {mart}.dim_wf_listing
  (listing_id, wayfair_sku, account_id, product_name, part_numbers, product_id, group_id, brand_id, n_products)
SELECT p.id, p.wayfair_sku, p.account_id, p.product_name, p.first_10_part_numbers,
       r.product_id, dp.group_id, dp.brand_id, r.n_products
FROM {stg}.sem_wayfair__product_info p
LEFT JOIN (
  SELECT m.listing_id, m.product_id, COUNT(*) OVER (PARTITION BY m.listing_id) AS n_products,
         ROW_NUMBER() OVER (PARTITION BY m.listing_id ORDER BY COALESCE(s.units, 0) DESC, m.product_id) AS rn
  FROM {mart}.map_wf_listing_product m
  LEFT JOIN (SELECT product_id, SUM(units) AS units FROM {mart}.fact_wf_total_sales_daily GROUP BY product_id) s
         ON s.product_id = m.product_id
) r ON r.listing_id = p.id AND r.rn = 1
LEFT JOIN {mart}.dim_product dp ON dp.product_id = r.product_id
