-- Dimension: làm mới toàn bộ mỗi lần chạy (các bảng nguồn nhỏ).

REPLACE INTO {mart}.dim_account
  (profile_id, marketplace_id, merchant_id, store_account_id, store_account_name, company_name,
   country_code, currency_code, profile_name, account_label)
SELECT p.profile_id, p.marketplace_id, p.merchant_id, p.store_account_id, sa.title, co.title,
       p.country_code, p.currency_code, p.profile_name,
       CONCAT(COALESCE(sa.title, p.profile_name), ' - ', COALESCE(p.country_code, '?'))
FROM {stg}.amazon_profiles_base p
LEFT JOIN {stg}.s_sales_store_accounts sa ON sa.id = p.store_account_id
LEFT JOIN {stg}.s_sales_store_companies co ON co.id = sa.sales_store_company_id
WHERE p.profile_id IS NOT NULL AND p.profile_id <> '';

REPLACE INTO {mart}.dim_portfolio (portfolio_id, profile_id, portfolio_name, state)
SELECT portfolio_id, profile_id, portfolio_name, UPPER(state)
FROM {stg}.sem__portfolios_base;

-- Trạng thái và ngân sách lấy từ snapshot mới nhất của sem__campaigns_base_daily (tra theo khóa chính)
SET @snap := (SELECT MAX(report_date) FROM {stg}.sem__campaigns_base_daily);

REPLACE INTO {mart}.dim_campaign
  (campaign_id, ad_type, sponsored_type_id, profile_id, portfolio_id, campaign_name,
   state, budget, budget_type, start_date, targeting_mode)
SELECT c.campaign_id,
       CASE c.sponsored_type_id WHEN 1 THEN 'SB' WHEN 2 THEN 'SP' WHEN 3 THEN 'SD' END,
       c.sponsored_type_id, c.profile_id, NULLIF(c.portfolio_id, ''), c.campaign_name,
       UPPER(d.state), d.budget, UPPER(d.budget_type), DATE(d.start_date), NULL
FROM {stg}.sem__campaigns_base c
LEFT JOIN {stg}.sem__campaigns_base_daily d
       ON d.id = CONCAT(c.campaign_id, '_', c.sponsored_type_id, '_', DATE_FORMAT(@snap, '%Y%m%d'))
WHERE c.sponsored_type_id IN (1, 2, 3);

REPLACE INTO {mart}.dim_adgroup (adgroup_id, ad_type, campaign_id, adgroup_name)
SELECT adgroup_id,
       CASE sponsored_type_id WHEN 1 THEN 'SB' WHEN 2 THEN 'SP' WHEN 3 THEN 'SD' END,
       campaign_id, adgroup_name
FROM {stg}.sem__adgroups_base
WHERE sponsored_type_id IN (1, 2, 3);

REPLACE INTO {mart}.dim_placement (placement_id, placement_name)
SELECT placement_id, placement FROM {stg}.sem__sb_placement_mapping;

REPLACE INTO {mart}.dim_product
  (product_id, product_sku, title, short_name, brand_id, brand_name, group_id, group_name, volume)
SELECT p.id, p.product_sku, p.title, p.short_name, p.brand_id, b.brand_name, p.group_id, g.title, NULLIF(p.volume, 0)
FROM {stg}.prd_product p
LEFT JOIN {stg}.prd_brands b ON b.id = p.brand_id
LEFT JOIN {stg}.prd_groups g ON g.id = p.group_id;

REPLACE INTO {mart}.map_asin_product (asin, product_id)
SELECT asin, MAX(product_id)
FROM {stg}.prd_amazon_listings
WHERE product_id > 0 AND asin IS NOT NULL AND asin <> ''
GROUP BY asin;

-- prd_asin là nguồn master ASIN -> sản phẩm, ưu tiên hơn listing
REPLACE INTO {mart}.map_asin_product (asin, product_id)
SELECT asin, product_id
FROM {stg}.prd_asin
WHERE product_id > 0 AND asin IS NOT NULL AND asin <> '';

REPLACE INTO {mart}.map_sku_product (store_account_id, seller_sku, product_id)
SELECT store_account_id, seller_sku, MAX(product_id)
FROM {stg}.prd_amazon_listings
WHERE product_id > 0 AND store_account_id IS NOT NULL AND seller_sku IS NOT NULL
GROUP BY store_account_id, seller_sku;

-- Nạp sẵn brand của công ty vào từ điển (team bổ sung brand đối thủ sau)
INSERT IGNORE INTO {mart}.dict_brand (term, brand_type, source)
SELECT LOWER(TRIM(brand_name)), 'OWN', 'prd_brands'
FROM {stg}.prd_brands
WHERE brand_name IS NOT NULL AND TRIM(brand_name) <> '' AND LOWER(TRIM(brand_name)) <> 'no brand';

-- PIC: phiên bản phân công mới nhất của mỗi bản ghi phân công (it_id); nhóm SP lấy từ group_id và từ nhóm của
-- các sản phẩm được giao trực tiếp (product_id). Hai cột này là JSON array dạng ["532","433"].
DELETE FROM {mart}.map_group_pic;

INSERT IGNORE INTO {mart}.map_group_pic (group_id, user_id)
SELECT CAST(j.v AS UNSIGNED), a.user_id
FROM (SELECT x.*, ROW_NUMBER() OVER (PARTITION BY x.it_id ORDER BY x.last_update DESC, x.assign_date DESC, x.id DESC) AS rn
      FROM {stg}.prd_product_assigned x) a
JOIN JSON_TABLE(IF(JSON_VALID(a.group_id), a.group_id, '[]'), '$[*]' COLUMNS (v VARCHAR(20) PATH '$')) j
WHERE a.rn = 1 AND a.user_id IS NOT NULL AND j.v REGEXP '^[0-9]+$'
UNION
SELECT p.group_id, a.user_id
FROM (SELECT x.*, ROW_NUMBER() OVER (PARTITION BY x.it_id ORDER BY x.last_update DESC, x.assign_date DESC, x.id DESC) AS rn
      FROM {stg}.prd_product_assigned x) a
JOIN JSON_TABLE(IF(JSON_VALID(a.product_id), a.product_id, '[]'), '$[*]' COLUMNS (v VARCHAR(20) PATH '$')) j
JOIN {mart}.dim_product p ON p.product_id = CAST(j.v AS UNSIGNED)
WHERE a.rn = 1 AND a.user_id IS NOT NULL AND j.v REGEXP '^[0-9]+$' AND p.group_id IS NOT NULL;

REPLACE INTO {mart}.dim_pic (user_id, name, email, code, manager_id, active)
SELECT u.id, u.name, u.email, u.code, NULLIF(u.manager_id, 0), COALESCE(u.published, 1)
FROM {stg}.s_users u
WHERE u.type = 1 AND u.id IN (SELECT user_id FROM {mart}.map_group_pic);

