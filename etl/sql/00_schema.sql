-- Schema báo cáo quảng cáo Amazon (ads_mart). Yêu cầu MySQL 8.0+.
-- {mart} và {stg} được thay bằng tên schema trong .env khi chạy.
-- Quy ước số liệu trong mọi bảng fact:
--   orders/units/sales = SP 7 ngày, SB/SD 14 ngày (giống Ads Console của seller)
--   orders_14d/sales_14d_usd = cửa sổ 14 ngày cho mọi loại (để so sánh)
--   *_usd = quy đổi USD theo tỷ giá ngày (fx_daily)

CREATE TABLE IF NOT EXISTS {mart}.dim_date (
  date_key DATE PRIMARY KEY,
  year SMALLINT NOT NULL,
  month TINYINT NOT NULL,
  month_start DATE NOT NULL,
  week_start DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS {mart}.fx_daily (
  date_key DATE NOT NULL,
  currency_code VARCHAR(5) NOT NULL,
  rate_usd DOUBLE,
  PRIMARY KEY (date_key, currency_code)
);

CREATE TABLE IF NOT EXISTS {mart}.dim_account (
  profile_id VARCHAR(25) PRIMARY KEY,
  marketplace_id VARCHAR(25),
  merchant_id VARCHAR(25),
  store_account_id INT,
  store_account_name VARCHAR(100),
  company_name VARCHAR(100),
  country_code VARCHAR(5),
  currency_code VARCHAR(5),
  profile_name VARCHAR(100),
  account_label VARCHAR(150),
  KEY idx_store (store_account_id, country_code)
);

CREATE TABLE IF NOT EXISTS {mart}.dim_portfolio (
  portfolio_id VARCHAR(25) PRIMARY KEY,
  profile_id VARCHAR(25),
  portfolio_name VARCHAR(150),
  state VARCHAR(15)
);

CREATE TABLE IF NOT EXISTS {mart}.dim_campaign (
  campaign_id VARCHAR(25) NOT NULL,
  ad_type CHAR(2) NOT NULL,
  sponsored_type_id TINYINT NOT NULL,
  profile_id VARCHAR(25),
  portfolio_id VARCHAR(25),
  campaign_name VARCHAR(500),
  state VARCHAR(15),
  budget DOUBLE,
  budget_type VARCHAR(25),
  start_date DATE,
  targeting_mode VARCHAR(10),
  PRIMARY KEY (campaign_id, ad_type),
  KEY idx_profile (profile_id),
  KEY idx_portfolio (portfolio_id)
);

CREATE TABLE IF NOT EXISTS {mart}.dim_adgroup (
  adgroup_id VARCHAR(25) NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_name VARCHAR(300),
  state VARCHAR(15),
  PRIMARY KEY (adgroup_id, ad_type),
  KEY idx_campaign (campaign_id)
);

CREATE TABLE IF NOT EXISTS {mart}.dim_placement (
  placement_id VARCHAR(12) PRIMARY KEY,
  placement_name VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS {mart}.dim_product (
  product_id INT PRIMARY KEY,
  product_sku VARCHAR(50),
  title VARCHAR(500),
  short_name VARCHAR(200),
  brand_id INT,
  brand_name VARCHAR(100),
  group_id INT,
  group_name VARCHAR(500),
  volume DOUBLE,  -- CBM / unit (prd_product.volume), để quy đổi tồn kho ra container
  KEY idx_group (group_id),
  KEY idx_brand (brand_id)
);

CREATE TABLE IF NOT EXISTS {mart}.map_asin_product (
  asin VARCHAR(20) PRIMARY KEY,
  product_id INT NOT NULL
);

CREATE TABLE IF NOT EXISTS {mart}.map_sku_product (
  store_account_id INT NOT NULL,
  seller_sku VARCHAR(100) NOT NULL,
  product_id INT NOT NULL,
  PRIMARY KEY (store_account_id, seller_sku)
);

-- Ad group -> sản phẩm. weight = chi phí (SP) hoặc doanh số Promoted (SB); is_dominant = sản phẩm chiếm tỷ trọng lớn nhất
CREATE TABLE IF NOT EXISTS {mart}.map_adgroup_product (
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_id VARCHAR(25) NOT NULL,
  product_id INT NOT NULL,
  group_id INT,
  brand_id INT,
  weight DOUBLE,
  weight_share DOUBLE,
  is_dominant TINYINT NOT NULL DEFAULT 0,
  PRIMARY KEY (ad_type, campaign_id, adgroup_id, product_id),
  KEY idx_group (group_id),
  KEY idx_brand (brand_id),
  KEY idx_campaign (campaign_id)
);

-- Từ khóa/search term đã chuẩn hóa và phân loại (do etl/terms.py ghi)
CREATE TABLE IF NOT EXISTS {mart}.dim_term (
  term_id VARCHAR(12) PRIMARY KEY,
  term VARCHAR(255) NOT NULL,
  normalized VARCHAR(255),
  word_count TINYINT,
  length_bucket VARCHAR(5),
  term_class VARCHAR(20),
  brand_hit VARCHAR(100),
  attribute_hits VARCHAR(255),
  product_term_hit VARCHAR(150),
  is_search_term TINYINT NOT NULL DEFAULT 0,
  is_keyword TINYINT NOT NULL DEFAULT 0,
  classified_at DATETIME,
  KEY idx_class (term_class),
  KEY idx_bucket (length_bucket)
);

CREATE TABLE IF NOT EXISTS {mart}.bridge_term_ngram (
  term_id VARCHAR(12) NOT NULL,
  n TINYINT NOT NULL,
  ngram VARCHAR(150) NOT NULL,
  PRIMARY KEY (term_id, n, ngram),
  KEY idx_ngram (n, ngram)
);

-- ===== Fact: campaign (SP: campaign x ad group; SB/SD: campaign, adgroup_id = '') =====
CREATE TABLE IF NOT EXISTS {mart}.fact_campaign_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_id VARCHAR(25) NOT NULL DEFAULT '',
  profile_id VARCHAR(25),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE,
  orders_same_sku INT, sales_same_sku_usd DOUBLE,
  ntb_orders INT, ntb_sales_usd DOUBLE, dpv INT,
  orders_14d INT, sales_14d_usd DOUBLE,
  PRIMARY KEY (report_date, ad_type, campaign_id, adgroup_id),
  KEY idx_campaign (campaign_id),
  KEY idx_profile_date (profile_id, report_date)
);

CREATE TABLE IF NOT EXISTS {mart}.fact_campaign_budget_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  profile_id VARCHAR(25),
  budget DOUBLE,
  budget_usd DOUBLE,
  budget_type VARCHAR(25),
  state VARCHAR(15),
  top_of_search_is DOUBLE,
  PRIMARY KEY (report_date, ad_type, campaign_id),
  KEY idx_campaign (campaign_id)
);

CREATE TABLE IF NOT EXISTS {mart}.fact_placement_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL DEFAULT 'SB',
  campaign_id VARCHAR(25) NOT NULL,
  placement_id VARCHAR(12) NOT NULL,
  profile_id VARCHAR(25),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE,
  orders_same_sku INT, sales_same_sku_usd DOUBLE,
  ntb_orders INT, ntb_sales_usd DOUBLE, dpv INT,
  orders_14d INT, sales_14d_usd DOUBLE,
  PRIMARY KEY (report_date, campaign_id, placement_id),
  KEY idx_campaign (campaign_id)
);

-- ===== Fact: keyword / target =====
CREATE TABLE IF NOT EXISTS {mart}.fact_target_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_id VARCHAR(25) NOT NULL,
  target_id VARCHAR(25) NOT NULL,
  term_id VARCHAR(12),
  targeting VARCHAR(255),
  match_type VARCHAR(40),
  bid DOUBLE,
  profile_id VARCHAR(25),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE,
  orders_same_sku INT, sales_same_sku_usd DOUBLE,
  ntb_orders INT, ntb_sales_usd DOUBLE, dpv INT,
  orders_14d INT, sales_14d_usd DOUBLE,
  top_of_search_is DOUBLE,
  PRIMARY KEY (report_date, ad_type, campaign_id, adgroup_id, target_id),
  KEY idx_campaign (campaign_id),
  KEY idx_term (term_id),
  KEY idx_type_campaign_match (ad_type, campaign_id, match_type)
);

-- ===== Fact: customer search term =====
CREATE TABLE IF NOT EXISTS {mart}.fact_search_term_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_id VARCHAR(25) NOT NULL,
  target_id VARCHAR(25) NOT NULL,
  term_id VARCHAR(12) NOT NULL,
  target_term_id VARCHAR(12),
  targeting VARCHAR(255),
  match_type VARCHAR(40),
  profile_id VARCHAR(25),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE,
  orders_same_sku INT, sales_same_sku_usd DOUBLE,
  ntb_orders INT, ntb_sales_usd DOUBLE, dpv INT,
  orders_14d INT, sales_14d_usd DOUBLE,
  PRIMARY KEY (report_date, ad_type, campaign_id, adgroup_id, target_id, term_id),
  KEY idx_term (term_id),
  KEY idx_campaign (campaign_id)
);

-- ===== Fact: sản phẩm được quảng cáo (SP) =====
CREATE TABLE IF NOT EXISTS {mart}.fact_product_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_id VARCHAR(25) NOT NULL,
  ad_id VARCHAR(25) NOT NULL,
  asin VARCHAR(20),
  sku VARCHAR(100),
  product_id INT,
  profile_id VARCHAR(25),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE,
  orders_same_sku INT, sales_same_sku_usd DOUBLE,
  ntb_orders INT, ntb_sales_usd DOUBLE, dpv INT,
  orders_14d INT, sales_14d_usd DOUBLE,
  PRIMARY KEY (report_date, ad_type, campaign_id, adgroup_id, ad_id),
  KEY idx_product (product_id),
  KEY idx_asin (asin),
  KEY idx_campaign (campaign_id)
);

-- ===== Fact: ASIN được mua (halo SP, Promoted/Brand Halo SB) =====
CREATE TABLE IF NOT EXISTS {mart}.fact_purchased_product_daily (
  report_date DATE NOT NULL,
  ad_type CHAR(2) NOT NULL,
  campaign_id VARCHAR(25) NOT NULL,
  adgroup_id VARCHAR(25) NOT NULL,
  advertised_asin VARCHAR(20) NOT NULL DEFAULT '',
  purchased_asin VARCHAR(20) NOT NULL,
  attribution VARCHAR(15) NOT NULL,
  profile_id VARCHAR(25),
  currency_code VARCHAR(5),
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE,
  ntb_orders INT, ntb_sales_usd DOUBLE,
  PRIMARY KEY (report_date, ad_type, campaign_id, adgroup_id, advertised_asin, purchased_asin, attribution),
  KEY idx_campaign (campaign_id),
  KEY idx_purchased (purchased_asin)
);

-- ===== Fact: tổng doanh số (từ đơn hàng) để tính TACoS =====
CREATE TABLE IF NOT EXISTS {mart}.fact_total_sales_daily (
  report_date DATE NOT NULL,
  store_account_id INT NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  asin VARCHAR(20) NOT NULL,
  product_id INT,
  currency_code VARCHAR(5),
  order_items INT,
  units INT,
  sales DOUBLE,
  sales_usd DOUBLE,
  fba_order_items INT, fba_units INT, fba_sales_usd DOUBLE,  -- phần FBA (AFN); FBM = tổng − FBA
  PRIMARY KEY (report_date, store_account_id, country_code, asin),
  KEY idx_product (product_id)
);

-- ===== Từ điển phân loại từ khóa (team tự bổ sung qua màn hình Từ điển) =====
CREATE TABLE IF NOT EXISTS {mart}.dict_brand (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term VARCHAR(100) NOT NULL,
  brand_type VARCHAR(12) NOT NULL,
  note VARCHAR(255),
  source VARCHAR(30) DEFAULT 'manual',
  UNIQUE KEY uq_term (term)
);

CREATE TABLE IF NOT EXISTS {mart}.dict_attribute (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term VARCHAR(100) NOT NULL,
  attr_group VARCHAR(50),
  note VARCHAR(255),
  UNIQUE KEY uq_term (term)
);

CREATE TABLE IF NOT EXISTS {mart}.dict_product_term (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term VARCHAR(100) NOT NULL,
  group_id INT,
  note VARCHAR(255),
  UNIQUE KEY uq_term (term)
);

CREATE TABLE IF NOT EXISTS {mart}.dict_stopword (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term VARCHAR(50) NOT NULL,
  UNIQUE KEY uq_term (term)
);

CREATE TABLE IF NOT EXISTS {mart}.dict_term_override (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term VARCHAR(255) NOT NULL,
  term_class VARCHAR(20) NOT NULL,
  note VARCHAR(255),
  UNIQUE KEY uq_term (term)
);

CREATE TABLE IF NOT EXISTS {mart}.cfg_kpi_target (
  id INT AUTO_INCREMENT PRIMARY KEY,
  scope_type VARCHAR(10) NOT NULL,
  scope_id VARCHAR(50),
  acos_target DOUBLE,
  tacos_target DOUBLE,
  note VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS {mart}.etl_run_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(20) NOT NULL,
  step VARCHAR(60) NOT NULL,
  date_start DATE,
  date_end DATE,
  started_at DATETIME NOT NULL,
  finished_at DATETIME,
  rows_affected BIGINT,
  status VARCHAR(10) NOT NULL,
  message TEXT,
  KEY idx_run (run_id)
);

-- ===== Người phụ trách (PIC) và gửi tin Google Chat =====
CREATE TABLE IF NOT EXISTS {mart}.dim_pic (
  user_id INT PRIMARY KEY,
  name VARCHAR(100),
  email VARCHAR(100),
  code VARCHAR(20),
  manager_id INT,
  active TINYINT NOT NULL DEFAULT 1
);

-- Nhóm sản phẩm đang được phân công cho PIC (phiên bản phân công mới nhất ở staging.prd_product_assigned)
CREATE TABLE IF NOT EXISTS {mart}.map_group_pic (
  group_id INT NOT NULL,
  user_id INT NOT NULL,
  PRIMARY KEY (group_id, user_id),
  KEY idx_user (user_id)
);

-- Cấu hình nhận tin của từng PIC (team tự nhập trên tab "Gửi tin PIC"; ETL không ghi đè)
CREATE TABLE IF NOT EXISTS {mart}.cfg_pic_notify (
  user_id INT PRIMARY KEY,
  webhook_url VARCHAR(1000),
  enabled TINYINT NOT NULL DEFAULT 0,
  acos_target DOUBLE,
  updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS {mart}.notify_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_date DATE NOT NULL,
  user_id INT NOT NULL,
  kind VARCHAR(20) NOT NULL,
  status VARCHAR(10) NOT NULL,
  http_status INT,
  message TEXT,
  error VARCHAR(1000),
  sent_at DATETIME NOT NULL,
  KEY idx_run (run_date, user_id, kind)
)
;

-- ===================================================================================================
-- Wayfair Sponsored Products. Quy ước:
--   sales = doanh số quy đổi theo GIÁ SỈ (wholesale cost, tiền Wayfair trả công ty) - dùng cho ACoS/ROAS
--   retail_sales = doanh số theo giá bán lẻ trên Wayfair (cột phụ)
--   orders/units/sales: view-through 14 ngày (mặc định của Wayfair)
--   country_code theo store hiển thị quảng cáo: wayfair.com = US (USD), wayfair.ca = CA (CAD)
-- ===================================================================================================
CREATE TABLE IF NOT EXISTS {mart}.dim_wf_account (
  account_id VARCHAR(10) PRIMARY KEY,
  account_name VARCHAR(100),
  short_name VARCHAR(50),
  currency_code VARCHAR(5),
  store_account_id INT
);

CREATE TABLE IF NOT EXISTS {mart}.dim_wf_campaign (
  campaign_id VARCHAR(30) PRIMARY KEY,
  account_id VARCHAR(10),
  campaign_name VARCHAR(150),
  targeting_type VARCHAR(50),
  country_code VARCHAR(5),
  state VARCHAR(30),
  daily_cap DOUBLE,
  lifetime_budget VARCHAR(50),
  start_date DATE,
  end_date VARCHAR(30),
  KEY idx_account (account_id)
);

-- Listing quảng cáo = Wayfair SKU x tài khoản (product_info_id ở nguồn, vd AAAI1009_66301)
CREATE TABLE IF NOT EXISTS {mart}.dim_wf_listing (
  listing_id VARCHAR(30) PRIMARY KEY,
  wayfair_sku VARCHAR(20),
  account_id VARCHAR(10),
  product_name VARCHAR(300),
  part_numbers VARCHAR(600),
  product_id INT,
  group_id INT,
  brand_id INT,
  n_products INT,
  state VARCHAR(15),
  KEY idx_group (group_id),
  KEY idx_brand (brand_id),
  KEY idx_sku (wayfair_sku)
);

-- Listing -> các sản phẩm nội bộ (mỗi listing gồm nhiều biến thể / part number)
CREATE TABLE IF NOT EXISTS {mart}.map_wf_listing_product (
  listing_id VARCHAR(30) NOT NULL,
  product_id INT NOT NULL,
  PRIMARY KEY (listing_id, product_id),
  KEY idx_product (product_id)
);

-- Campaign -> nhóm SP / brand, tỷ trọng theo spend của listing (để lọc theo Nhóm SP / Brand)
CREATE TABLE IF NOT EXISTS {mart}.map_wf_campaign_group (
  campaign_id VARCHAR(30) NOT NULL,
  group_id INT NOT NULL,
  brand_id INT,
  weight_share DOUBLE,
  is_dominant TINYINT NOT NULL DEFAULT 0,
  PRIMARY KEY (campaign_id, group_id),
  KEY idx_group (group_id),
  KEY idx_brand (brand_id)
);

CREATE TABLE IF NOT EXISTS {mart}.fact_wf_campaign_daily (
  report_date DATE NOT NULL,
  campaign_id VARCHAR(30) NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  account_id VARCHAR(10),
  targeting_type VARCHAR(50),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE, retail_sales DOUBLE, retail_sales_usd DOUBLE,
  PRIMARY KEY (report_date, campaign_id, country_code),
  KEY idx_campaign (campaign_id),
  KEY idx_account_date (account_id, report_date)
);

CREATE TABLE IF NOT EXISTS {mart}.fact_wf_product_daily (
  report_date DATE NOT NULL,
  campaign_id VARCHAR(30) NOT NULL,
  listing_id VARCHAR(30) NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  account_id VARCHAR(10),
  wayfair_sku VARCHAR(20),
  class_name VARCHAR(70),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE, retail_sales DOUBLE, retail_sales_usd DOUBLE,
  PRIMARY KEY (report_date, campaign_id, listing_id, country_code),
  KEY idx_listing (listing_id),
  KEY idx_campaign (campaign_id)
);

-- Keyword x listing (report keyword targeting; nguồn không có units)
CREATE TABLE IF NOT EXISTS {mart}.fact_wf_keyword_daily (
  report_date DATE NOT NULL,
  campaign_id VARCHAR(30) NOT NULL,
  keyword_info_id VARCHAR(70) NOT NULL,
  listing_id VARCHAR(30) NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  account_id VARCHAR(10),
  term_id VARCHAR(12),
  keyword VARCHAR(255),
  match_type VARCHAR(30),
  bid DOUBLE,
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE, retail_sales DOUBLE, retail_sales_usd DOUBLE,
  PRIMARY KEY (report_date, campaign_id, keyword_info_id, listing_id, country_code),
  KEY idx_campaign (campaign_id),
  KEY idx_term (term_id),
  KEY idx_listing (listing_id)
);

-- Keyword x search term khách gõ (report keyword optimization, đã cộng gộp các tổ hợp thuộc tính lọc).
-- term_id = '' khi Wayfair không trả search term.
CREATE TABLE IF NOT EXISTS {mart}.fact_wf_search_term_daily (
  report_date DATE NOT NULL,
  campaign_id VARCHAR(30) NOT NULL,
  keyword_info_id VARCHAR(150) NOT NULL,
  term_id VARCHAR(12) NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  account_id VARCHAR(10),
  target_term_id VARCHAR(12),
  keyword VARCHAR(255),
  match_type VARCHAR(30),
  currency_code VARCHAR(5),
  impressions BIGINT, clicks BIGINT, cost DOUBLE, cost_usd DOUBLE,
  orders INT, units INT, sales DOUBLE, sales_usd DOUBLE, retail_sales DOUBLE, retail_sales_usd DOUBLE,
  PRIMARY KEY (report_date, campaign_id, keyword_info_id, term_id, country_code),
  KEY idx_term (term_id),
  KEY idx_campaign (campaign_id)
);

CREATE TABLE IF NOT EXISTS {mart}.fact_wf_budget_daily (
  report_date DATE NOT NULL,
  campaign_id VARCHAR(30) NOT NULL,
  account_id VARCHAR(10),
  state VARCHAR(30),
  daily_cap DOUBLE,
  daily_cap_usd DOUBLE,
  currency_code VARCHAR(5),
  PRIMARY KEY (report_date, campaign_id)
);

-- Search Term Research: thị phần hiển thị của công ty trên kết quả tìm kiếm (impressions 30 ngày gần nhất)
CREATE TABLE IF NOT EXISTS {mart}.fact_wf_share_of_search (
  report_date DATE NOT NULL,
  account_id VARCHAR(10) NOT NULL,
  catalog VARCHAR(70) NOT NULL,
  term_id VARCHAR(12) NOT NULL,
  term VARCHAR(255),
  class_name VARCHAR(70),
  impressions_30d INT,
  class_share DOUBLE,
  share_search DOUBLE,
  share_page1 DOUBLE,
  share_top8 DOUBLE,
  PRIMARY KEY (report_date, account_id, catalog, term_id),
  KEY idx_term (term_id)
);

-- Tổng doanh số Wayfair theo giá sỉ (dropship + CastleGate) để tính TACoS. country_code theo nước của khách.
CREATE TABLE IF NOT EXISTS {mart}.fact_wf_total_sales_daily (
  report_date DATE NOT NULL,
  account_id VARCHAR(10) NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  order_type VARCHAR(20) NOT NULL,
  wayfair_sku VARCHAR(20) NOT NULL,
  product_id INT NOT NULL DEFAULT 0,
  currency_code VARCHAR(5) NOT NULL,
  order_lines INT,
  units INT,
  sales DOUBLE,
  sales_usd DOUBLE,
  PRIMARY KEY (report_date, account_id, country_code, order_type, wayfair_sku, product_id, currency_code),
  KEY idx_product (product_id),
  KEY idx_sku (wayfair_sku)
);

-- ===================================================================================================
-- Tồn kho & ngày dự kiến hết hàng. Nút tồn kho (node):
--   POOL-<nước>   gộp các kho nội bộ / 3PL thật của một nước (bỏ kho ảo): phục vụ FBM, dropship, website, eBay...
--   WH-<id>       từng kho nội bộ / 3PL (chi tiết của POOL, kể cả kho ảo Direct Import - không tính vào POOL)
--   CG-<store>    Wayfair CastleGate của một tài khoản (gộp các kho CG)
--   FBA-<kênh>    Amazon FBA của một kênh (tài khoản x nước) - CHƯA có số tồn vì nguồn MYI ở DWH đã dừng
-- ===================================================================================================
CREATE TABLE IF NOT EXISTS {mart}.dim_inv_node (
  node_id VARCHAR(30) PRIMARY KEY,
  node_type VARCHAR(10) NOT NULL,
  country_code VARCHAR(5),
  title VARCHAR(150),
  warehouse_id INT,
  store_account_id INT,
  sales_channel_id INT,
  is_virtual TINYINT NOT NULL DEFAULT 0,
  has_stock TINYINT NOT NULL DEFAULT 1,
  KEY idx_country (country_code)
);

-- Kênh bán -> nước, hình thức giao hàng, nút trừ tồn
CREATE TABLE IF NOT EXISTS {mart}.map_channel_node (
  sales_channel_id INT PRIMARY KEY,
  code VARCHAR(50),
  title VARCHAR(150),
  country_code VARCHAR(5),
  fulfil_type VARCHAR(12),
  node_id VARCHAR(30),
  store_account_id INT,
  published TINYINT
);

-- Doanh số theo kênh x sản phẩm x ngày (s_sales_report_data_by_orderdate); combo được tách ra sản phẩm con
CREATE TABLE IF NOT EXISTS {mart}.fact_channel_sales_daily (
  report_date DATE NOT NULL,
  sales_channel_id INT NOT NULL,
  product_id INT NOT NULL,
  units DOUBLE,
  revenue DOUBLE,
  revenue_usd DOUBLE,
  combo_units DOUBLE,
  PRIMARY KEY (report_date, sales_channel_id, product_id),
  KEY idx_product (product_id)
);

-- Shopify (website): một dòng = một dòng hàng của đơn, kèm thuộc tính của đơn (nguồn, khách mới / cũ). Dựng lại toàn bộ
-- mỗi lần ETL (vài nghìn đơn). Tiền USD theo tỷ giá ngày đặt; net = gross - giảm giá; refund = tiền hàng đã hoàn.
CREATE TABLE IF NOT EXISTS {mart}.fact_shop_line (
  line_item_id VARCHAR(30) PRIMARY KEY,
  order_id VARCHAR(30) NOT NULL,
  report_date DATE NOT NULL,
  sales_channel_id INT NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  currency_code VARCHAR(5),
  source_name VARCHAR(100),
  customer_type VARCHAR(10) NOT NULL,
  financial_status VARCHAR(30),
  product_id INT NOT NULL DEFAULT 0,
  sku VARCHAR(50),
  units INT,
  gross_usd DOUBLE,
  discount_usd DOUBLE,
  net_usd DOUBLE,
  refund_units INT,
  refund_usd DOUBLE,
  KEY idx_date (report_date),
  KEY idx_product (product_id),
  KEY idx_order (order_id)
);

-- Lịch sử tồn on-hand theo ngày của POOL / CG (để biết ngày nào đang hết hàng)
CREATE TABLE IF NOT EXISTS {mart}.fact_inv_stock_daily (
  stock_date DATE NOT NULL,
  node_id VARCHAR(30) NOT NULL,
  product_id INT NOT NULL,
  on_hand INT,
  PRIMARY KEY (stock_date, node_id, product_id),
  KEY idx_node_product (node_id, product_id)
);

-- Tồn hiện tại theo nút (làm mới mỗi lần chạy)
CREATE TABLE IF NOT EXISTS {mart}.fact_inv_stock (
  node_id VARCHAR(30) NOT NULL,
  product_id INT NOT NULL,
  on_hand INT,
  reserved INT,
  available INT,
  unfulfillable INT,
  updated_at DATETIME,
  PRIMARY KEY (node_id, product_id),
  KEY idx_product (product_id)
);

-- Chi tiết tồn CastleGate theo từng kho CG
CREATE TABLE IF NOT EXISTS {mart}.fact_inv_cg_detail (
  store_account_id INT NOT NULL,
  cg_warehouse VARCHAR(100) NOT NULL,
  product_id INT NOT NULL,
  on_hand INT, fulfillable INT, unfulfillable INT, on_order INT,
  PRIMARY KEY (store_account_id, cg_warehouse, product_id)
);

-- Hàng đang về / pipeline (làm mới mỗi lần chạy). source: CONTAINER | PO | FBA_SHIPMENT | CG_ON_ORDER
CREATE TABLE IF NOT EXISTS {mart}.fact_inv_incoming (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source VARCHAR(15) NOT NULL,
  ref VARCHAR(100),
  node_id VARCHAR(30),
  country_code VARCHAR(5),
  product_id INT NOT NULL,
  qty INT NOT NULL,
  eta DATE,
  eta_estimated TINYINT NOT NULL DEFAULT 0,
  stage VARCHAR(40),
  KEY idx_node_product (node_id, product_id),
  KEY idx_product (product_id)
);

-- Tồn FBA theo tài khoản từ Google Sheet "inventory details" (etl/fba_sheet.py). Mỗi ngày giữ lần đọc cuối cùng của
-- ngày đó; sheet không ghi ngày dữ liệu nên read_date = ngày ETL đọc. in_stock / on_order là số trên sheet.
CREATE TABLE IF NOT EXISTS {mart}.fact_fba_sheet_stock (
  read_date DATE NOT NULL,
  sales_channel_id INT NOT NULL,
  product_id INT NOT NULL,
  account VARCHAR(50),
  product_sku VARCHAR(50),
  in_stock INT,
  on_order INT,
  read_at DATETIME,
  PRIMARY KEY (read_date, sales_channel_id, product_id),
  KEY idx_product (product_id)
);

-- Nhật ký mỗi lần đọc sheet FBA: data_hash đổi = số FBA trên sheet đã thay đổi (để cảnh báo sheet không còn cập nhật)
CREATE TABLE IF NOT EXISTS {mart}.fba_sheet_read (
  id INT AUTO_INCREMENT PRIMARY KEY,
  read_at DATETIME NOT NULL,
  status VARCHAR(10) NOT NULL,
  data_hash CHAR(32),
  skus INT,
  in_stock INT,
  note VARCHAR(500)
);

-- Nhu cầu theo bang / tỉnh giao hàng 90 ngày (đơn Amazon + Wayfair + Shopify, etl/geo_sales.py) cho bản đồ tồn kho.
-- channel: amazon | wayfair | shopify; region '?' = không rõ bang. (Thay bảng fact_sales_region chỉ có Amazon.)
DROP TABLE IF EXISTS {mart}.fact_sales_region;
CREATE TABLE IF NOT EXISTS {mart}.fact_demand_region (
  channel VARCHAR(10) NOT NULL,
  country_code CHAR(2) NOT NULL,
  region VARCHAR(5) NOT NULL,
  product_id INT NOT NULL,
  units_90 DOUBLE, units_30 DOUBLE, orders_90 INT,
  as_of DATE,
  PRIMARY KEY (channel, country_code, region, product_id)
);

-- SKU đang xả hàng (Clear Stock) từ Google Sheet (etl/clear_stock.py), nạp lại toàn bộ mỗi lần chạy
CREATE TABLE IF NOT EXISTS {mart}.ref_clear_stock (
  product_sku VARCHAR(100) PRIMARY KEY,
  product_id INT,
  status VARCHAR(50),
  pic VARCHAR(100),
  loaded_at DATETIME,
  KEY idx_product (product_id)
);

-- Kết quả dự báo theo nút x sản phẩm (etl/inventory.py)
CREATE TABLE IF NOT EXISTS {mart}.inv_projection (
  node_id VARCHAR(30) NOT NULL,
  product_id INT NOT NULL,
  on_hand INT, available INT,
  incoming_qty INT, incoming_30d INT, next_eta DATE, next_qty INT,
  units_7 DOUBLE, units_30 DOUBLE, units_90 DOUBLE,
  instock_days_30 INT, instock_days_90 INT,
  velocity DOUBLE,
  days_cover DOUBLE, days_cover_incl_incoming DOUBLE,
  stockout_date DATE, oos_days_before_next INT,
  need_60d INT,
  lost_units_90 DOUBLE, avg_price DOUBLE, lost_sales_90 DOUBLE,
  status VARCHAR(12),
  as_of DATE,
  computed_at DATETIME,
  PRIMARY KEY (node_id, product_id),
  KEY idx_product (product_id),
  KEY idx_status (status)
);

-- ===== Giá vốn, phí và mục tiêu tháng (team tự nhập trên tab "Giá vốn & phí" / "Mục tiêu tháng"; ETL không ghi đè) =====
-- Tiền theo USD. Ô để trống (NULL) = dùng mặc định của kênh; SKU chưa có landed_cost thì không tính lãi.
CREATE TABLE IF NOT EXISTS {mart}.cfg_sku_cost (
  product_id INT PRIMARY KEY,
  landed_cost DOUBLE,
  amz_fee_unit DOUBLE,
  wf_fee_unit DOUBLE,
  amz_referral_pct DOUBLE,
  return_pct DOUBLE,
  note VARCHAR(255),
  updated_at DATETIME
);

-- Giá vốn chuẩn (Standard COGS) do BOD ban hành trên Google Sheet, ETL nạp lại toàn bộ mỗi lần chạy (etl/std_cogs.py).
-- Tiền theo đồng của thị trường (US = USD, CA = CAD, AU = AUD); basis WH = kho, FBA = Amazon FBA, CG = Wayfair CastleGate.
-- Ô trống / 0 trên sheet không nạp. product_id NULL = SKU không có (hoặc trùng) trong dim_product.
CREATE TABLE IF NOT EXISTS {mart}.ref_std_cogs (
  product_sku VARCHAR(100) NOT NULL,
  market CHAR(2) NOT NULL,
  basis VARCHAR(3) NOT NULL,
  product_id INT,
  currency_code VARCHAR(5) NOT NULL,
  cogs DOUBLE NOT NULL,
  title VARCHAR(500),
  brand VARCHAR(100),
  sell_type VARCHAR(20),
  category VARCHAR(100),
  loaded_at DATETIME NOT NULL,
  PRIMARY KEY (product_sku, market, basis),
  KEY idx_product (product_id)
);

CREATE TABLE IF NOT EXISTS {mart}.cfg_channel_cost (
  channel VARCHAR(10) PRIMARY KEY,
  referral_pct DOUBLE NOT NULL DEFAULT 0,
  return_pct DOUBLE NOT NULL DEFAULT 0,
  updated_at DATETIME
);

INSERT IGNORE INTO {mart}.cfg_channel_cost (channel, referral_pct, return_pct) VALUES ('amazon', 0.15, 0), ('wayfair', 0, 0),
  ('shopify', 0.03, 0), ('other', 0.15, 0);

-- Chi phí QC của website Shopify (Google, Meta…) team nhập tay theo tháng, USD; báo cáo chia đều cho các ngày trong tháng
CREATE TABLE IF NOT EXISTS {mart}.cfg_shop_ad_spend (
  month DATE NOT NULL,
  sales_channel_id INT NOT NULL,
  platform VARCHAR(10) NOT NULL,
  spend_usd DOUBLE NOT NULL,
  updated_at DATETIME,
  PRIMARY KEY (month, sales_channel_id, platform)
);

-- account_key: '' = cả kênh; Amazon "<store_account_id>-<nước>", Wayfair "<account_id>-<nước>"
CREATE TABLE IF NOT EXISTS {mart}.cfg_month_target (
  month DATE NOT NULL,
  channel VARCHAR(10) NOT NULL,
  account_key VARCHAR(40) NOT NULL DEFAULT '',
  total_sales DOUBLE,
  ad_sales DOUBLE,
  spend DOUBLE,
  tacos DOUBLE,
  updated_at DATETIME,
  PRIMARY KEY (month, channel, account_key)
);

-- ===== Quy tắc audit từ khóa (team chỉnh trên tab "Quy tắc audit"; ETL không ghi đè) =====
-- scope_key: '*' = mặc định cho mọi tài khoản, hoặc profile_id = ghi đè riêng tài khoản đó.
-- Tham số không có dòng nào thì dùng mặc định trong code (app/audit/rules.py).
CREATE TABLE IF NOT EXISTS {mart}.cfg_audit_param (
  scope_key VARCHAR(25) NOT NULL,
  param VARCHAR(40) NOT NULL,
  value DOUBLE NOT NULL,
  updated_at DATETIME,
  PRIMARY KEY (scope_key, param)
);

-- ACoS mục tiêu riêng: scope_type GROUP (nhóm SP, áp mọi tài khoản) hoặc PORTFOLIO (portfolio_id của một tài khoản).
-- Thứ tự ưu tiên: portfolio > nhóm SP > tham số acos_target của tài khoản > mặc định.
CREATE TABLE IF NOT EXISTS {mart}.cfg_audit_acos (
  scope_type VARCHAR(10) NOT NULL,
  scope_id VARCHAR(25) NOT NULL,
  acos_target DOUBLE NOT NULL,
  updated_at DATETIME,
  PRIMARY KEY (scope_type, scope_id)
);

-- ===== Audit từ khóa từ file bulk (tab "Audit từ khóa"; ETL không ghi đè) =====
-- Mỗi lần upload một file bulk Sponsored Products tải từ Ads Console. Tài khoản tự nhận theo Campaign ID.
CREATE TABLE IF NOT EXISTS {mart}.audit_bulk_upload (
  id INT AUTO_INCREMENT PRIMARY KEY,
  profile_id VARCHAR(25),
  file_name VARCHAR(255),
  file_path VARCHAR(500),
  uploaded_at DATETIME NOT NULL,
  status VARCHAR(12) NOT NULL,   -- PARSING | AUDITING | READY | FAILED
  message VARCHAR(1000),
  n_rows INT,
  n_campaigns INT,
  matched_campaigns INT,
  headers TEXT,                  -- JSON: tiêu đề cột sheet Sponsored Products Campaigns (dùng lại khi xuất)
  KEY idx_profile (profile_id, uploaded_at)
);

-- Các dòng của sheet Sponsored Products Campaigns (chỉ giữ cho vài lần upload gần nhất của mỗi tài khoản)
CREATE TABLE IF NOT EXISTS {mart}.audit_bulk_row (
  upload_id INT NOT NULL,
  row_no INT NOT NULL,
  entity VARCHAR(40),
  campaign_id VARCHAR(25),
  ad_group_id VARCHAR(25),
  portfolio_id VARCHAR(25),
  object_id VARCHAR(25),         -- Keyword ID / Product Targeting ID / Ad ID tuỳ entity
  campaign_name VARCHAR(255),
  ad_group_name VARCHAR(255),
  targeting_type VARCHAR(10),
  state VARCHAR(12),
  campaign_state VARCHAR(12),
  ad_group_state VARCHAR(12),
  bid DOUBLE,
  default_bid DOUBLE,
  keyword_text VARCHAR(255),
  match_type VARCHAR(30),
  expression VARCHAR(500),
  sku VARCHAR(100),
  asin VARCHAR(20),
  PRIMARY KEY (upload_id, row_no),
  KEY idx_entity (upload_id, entity)
);

-- Các dòng của file bulk Wayfair (WSP "Bulk Campaign Edits"), một bảng cho các sheet Edit ...:
-- sheet = campaign | listing | keyword | negative | part. item = listing / keyword / negative / part number tuỳ sheet.
CREATE TABLE IF NOT EXISTS {mart}.audit_wf_bulk_row (
  upload_id INT NOT NULL,
  sheet VARCHAR(10) NOT NULL,
  row_no INT NOT NULL,
  campaign_id VARCHAR(25),
  campaign_name VARCHAR(255),
  campaign_state VARCHAR(12),
  item VARCHAR(255),
  match_type VARCHAR(20),
  state VARCHAR(12),
  bid DOUBLE,
  store VARCHAR(30),
  customer_type VARCHAR(20),
  targeting VARCHAR(30),
  bidding VARCHAR(40),
  daily_cap VARCHAR(20),
  target_roas DOUBLE,
  info VARCHAR(600),             -- tên sản phẩm / part number / listing đi kèm (chỉ để hiển thị)
  PRIMARY KEY (upload_id, sheet, row_no)
);

CREATE TABLE IF NOT EXISTS {mart}.audit_run (
  id INT AUTO_INCREMENT PRIMARY KEY,
  upload_id INT NOT NULL,
  profile_id VARCHAR(25),
  started_at DATETIME NOT NULL,
  finished_at DATETIME,
  status VARCHAR(10) NOT NULL,   -- RUNNING | OK | FAILED
  data_start DATE,
  data_end DATE,
  params TEXT,                   -- JSON: cấu hình quy tắc đã dùng
  n_proposals INT,
  message VARCHAR(1000),
  KEY idx_upload (upload_id)
);

-- Đề xuất của một lần audit. status: pending → exported khi đã nằm trong một file bulk xuất ra.
CREATE TABLE IF NOT EXISTS {mart}.audit_proposal (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  profile_id VARCHAR(25),
  rule VARCHAR(12) NOT NULL,
  action VARCHAR(20) NOT NULL,   -- bid | pause | add_keyword | add_target | negative | negative_target | warn
  campaign_id VARCHAR(25),
  ad_group_id VARCHAR(25),
  object_id VARCHAR(25),
  campaign_name VARCHAR(255),
  ad_group_name VARCHAR(255),
  text VARCHAR(500),
  source VARCHAR(500),          -- keyword / target đã khớp search term (quy tắc 1, 2); search term bị chặn (quy tắc 7)
  match_type VARCHAR(40),
  current_bid DOUBLE,
  new_bid DOUBLE,
  impressions BIGINT, clicks BIGINT, spend DOUBLE, orders INT, sales DOUBLE,
  acos_target DOUBLE,
  reason VARCHAR(500),
  default_on TINYINT NOT NULL DEFAULT 1,
  exportable TINYINT NOT NULL DEFAULT 1,
  status VARCHAR(10) NOT NULL DEFAULT 'pending',
  exported_at DATETIME,
  KEY idx_run (run_id, rule),
  KEY idx_object (profile_id, object_id, exported_at)
);

-- Trạng thái mới nhất của keyword / target Amazon (18_status.sql). SP/SB: keyword (snapshot keyword theo ngày);
-- SD: danh mục target. Target sản phẩm / auto của SP không có nguồn trạng thái riêng.
CREATE TABLE IF NOT EXISTS {mart}.dim_target_state (
  ad_type CHAR(2) NOT NULL,
  target_id VARCHAR(25) NOT NULL,
  state VARCHAR(15),
  as_of DATE,
  PRIMARY KEY (ad_type, target_id)
);

-- P&L theo cấu trúc công ty (etl/pnl.py), USD, theo ngày đặt đơn × kênh × nước × tài khoản (store_account_id) ×
-- hình thức giao × sản phẩm. PL4 = DT thuần − phí kênh − giá vốn − phí hoàn hàng − QC (ĐGMK, chi phí QC thật);
-- PL5 = PL4 − phí kho & vận chuyển − phí vận hành. Cột *_est = phần của khoản đó đang là ước tính (chưa có số thật).
CREATE TABLE IF NOT EXISTS {mart}.fact_pnl_daily (
  report_date DATE NOT NULL,
  ch VARCHAR(10) NOT NULL,          -- amazon | wayfair | shopify | other
  cc VARCHAR(5) NOT NULL,
  acct INT NOT NULL DEFAULT 0,      -- store_account_id (0 = không rõ)
  fulfil VARCHAR(10) NOT NULL,      -- FBA | FBM | CG | DS | WEB | kiểu của kênh khác
  product_id INT NOT NULL DEFAULT 0,
  co VARCHAR(100),                  -- tên tài khoản / mã kênh (để gán công ty)
  units DOUBLE, orders DOUBLE,
  gross_rev DOUBLE, promo DOUBLE, net_rev DOUBLE,
  fee_commission DOUBLE, fee_fulfil DOUBLE, fee_other DOUBLE, channel_fee DOUBLE, channel_fee_est DOUBLE,
  cogs DOUBLE, cogs_est DOUBLE,
  return_fee DOUBLE, return_rate DOUBLE,
  ads DOUBLE,
  pl4 DOUBLE,
  wh_3pl DOUBLE, wh_fba DOUBLE, wh_cg DOUBLE, wh_ship DOUBLE, warehouse_fee DOUBLE, warehouse_fee_est DOUBLE,
  operation_fee DOUBLE, operation_fee_est DOUBLE,
  pl5 DOUBLE,
  PRIMARY KEY (report_date, ch, cc, acct, fulfil, product_id),
  KEY idx_product (product_id)
);

-- Phí vận hành mỗi đơn vị theo SKU × tháng × nước × cột kênh, từ Google Sheet của công ty (etl/op_fee.py), tiền nước đó.
-- col: 'amazon by marketplace' (FBA), 'amazon by merchant' (FBM), 'wayfair dropship', 'fba', 'fbm', 'cg'…
CREATE TABLE IF NOT EXISTS {mart}.ref_operation_fee_unit (
  product_sku VARCHAR(100) NOT NULL,
  month DATE NOT NULL,
  country_code VARCHAR(5) NOT NULL,
  col VARCHAR(60) NOT NULL,
  product_id INT,
  currency_code VARCHAR(5) NOT NULL,
  fee DOUBLE NOT NULL,
  loaded_at DATETIME NOT NULL,
  PRIMARY KEY (product_sku, month, country_code, col),
  KEY idx_product (product_id, month)
);

-- Ghi chú lần tính P&L gần nhất: mốc dữ liệu thật của từng nguồn phí
CREATE TABLE IF NOT EXISTS {mart}.pnl_run (
  source VARCHAR(30) PRIMARY KEY,
  actual_to DATE,
  note VARCHAR(500),
  computed_at DATETIME NOT NULL
);
