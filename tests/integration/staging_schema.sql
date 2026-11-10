-- Sinh tự động từ staging_data_dictionary.xlsx (chỉ các bảng ETL dùng). Mọi cột cho phép NULL để dễ seed dữ liệu thử.

CREATE TABLE `amazon_profiles_base` (
  `id` varchar(60),
  `profile_id` varchar(25),
  `marketplace_id` varchar(25),
  `merchant_id` varchar(25),
  `store_account_id` int,
  `country_code` varchar(5),
  `profile_name` varchar(40),
  `currency_code` varchar(5),
  `lastupdate` date,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_sales_store_accounts` (
  `id` int,
  `sales_store_company_id` int,
  `sales_marketplace_id` int,
  `title` varchar(20),
  `type` tinyint(1),
  `store_code` varchar(30),
  `store_url` varchar(250),
  `logo` varchar(200),
  `description` varchar(500),
  `published` tinyint(1),
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_sales_store_companies` (
  `id` int,
  `title` varchar(50),
  `published` tinyint(1),
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__portfolios_base` (
  `portfolio_id` varchar(25),
  `profile_id` varchar(25),
  `portfolio_name` varchar(100),
  `state` varchar(10),
  `lastupdate` datetime,
  PRIMARY KEY (`portfolio_id`)
);

CREATE TABLE `sem__campaigns_base` (
  `id` varchar(50),
  `campaign_id` varchar(25),
  `sponsored_type_id` int,
  `portfolio_id` varchar(25),
  `profile_id` varchar(25),
  `campaign_name` text,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__campaigns_base_daily` (
  `id` varchar(50),
  `campaign_id` varchar(25),
  `sponsored_type_id` int,
  `budget` float,
  `budget_type` varchar(10),
  `state` varchar(10),
  `start_date` datetime,
  `report_date` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__adgroups_base` (
  `id` varchar(50),
  `adgroup_id` varchar(25),
  `campaign_id` varchar(25),
  `sponsored_type_id` int,
  `adgroup_name` varchar(150),
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_product` (
  `id` int,
  `parent_id` int,
  `company_id` tinyint,
  `brand_id` int,
  `title` varchar(500),
  `short_name` varchar(500),
  `description` mediumtext,
  `product_sku` varchar(100),
  `weight` float,
  `weight_tier` char(5),
  `cubic_feet` float,
  `msf` float,
  `dip` float,
  `length` float,
  `width` float,
  `height` float,
  `volume` float,
  `fba_size_tier` varchar(30),
  `box_count` int,
  `appotion_price` float,
  `fob_price` float,
  `tax_rate` float,
  `tax_by_item` float,
  `is_virtual` tinyint,
  `published` tinyint,
  `warranty` varchar(150),
  `return_policy` varchar(100),
  `creator` int,
  `createtime` datetime,
  `active_date` date,
  `purchasing` tinyint(1),
  `sell_type` tinyint,
  `level` int,
  `level_inventory` int,
  `level_tier` int,
  `status` tinyint(1),
  `sell_status` int,
  `prop65_warning` int,
  `version` varchar(20),
  `season` varchar(100),
  `slogan` varchar(500),
  `shipping_memo` varchar(500),
  `fbm_shipping_type` int,
  `retire_date` date,
  `selling_date` date,
  `life_cycle` int,
  `product_type` tinyint,
  `group_id` int,
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_brands` (
  `id` int,
  `brand_name` varchar(45),
  `brand_owner_id` bit(1),
  `published` bit(1),
  `abbreviation` varchar(50),
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_groups` (
  `id` int,
  `title` varchar(500),
  `parent_product_group` int,
  `product_id` varchar(1000),
  `is_parent` tinyint,
  `product_group_sku` varchar(45),
  `update_time` datetime,
  `updator` int,
  `published` tinyint(1),
  `company_id` int,
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_amazon_listings` (
  `id` int,
  `store_account_id` int,
  `product_id` int,
  `amazon_asin_id` int,
  `seller_sku` varchar(50),
  `fba_sku` varchar(45),
  `asin` varchar(191),
  `item_name` varchar(250),
  `quantity` int,
  `condition_type` varchar(50),
  `fulfill_channel` varchar(191),
  `status` varchar(50),
  `published` tinyint(1),
  `last_update_date` datetime,
  `is_ntc` tinyint(1),
  `last_updated_dwh` date,
  `marketplace_id` varchar(45),
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_asin` (
  `id` int,
  `asin` varchar(100),
  `fnsku` varchar(50),
  `parent_asin_id` int,
  `y4a_asin` tinyint,
  `product_id` int,
  `product_name` varchar(1000),
  `company` varchar(1000),
  `feature` mediumtext,
  `description` mediumtext,
  `dimension` mediumtext,
  `small_image` varchar(500),
  `date` date,
  `regular_price` float,
  `updatedate` date,
  `landed_price` float,
  `listing_price` float,
  `shipping_price` float,
  `landed_price_amazon` float,
  `listing_price_amazon` float,
  `shipping_price_amazon` float,
  `landed_price_merchant` float,
  `listing_price_merchant` float,
  `shipping_price_merchant` float,
  `landed_price_avc` float,
  `listing_price_avc` float,
  `shipping_price_avc` float,
  `verified_fba_price` float,
  `verified_fbm_price` float,
  `ssa_price` float,
  `avc_price` float,
  `avc_cost` float,
  `category_id` varchar(250),
  `category_rank` int,
  `subcategory_id` varchar(150),
  `subcategory_rank` int,
  `all_rank` mediumtext,
  `all_rank_json` mediumtext,
  `tracking` tinyint,
  `warning` tinyint,
  `warning_count` int,
  `type` tinyint,
  `product_type` tinyint,
  `ssa_sales` tinyint,
  `avc_sales` tinyint,
  `avc_sales_confirm_status` tinyint(1),
  `avc_sales_confirm` varchar(100),
  `ssa_update_date` date,
  `avc_update_date` date,
  `buy_box_warning` tinyint(1),
  `fulfilled_by` varchar(50),
  `seller` varchar(50),
  `lowest_price` float,
  `processed` int,
  `published` tinyint,
  `note` varchar(50),
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_placement_mapping` (
  `placement_id` varchar(12),
  `placement` varchar(100),
  `lastupdate` datetime,
  PRIMARY KEY (`placement_id`)
);

CREATE TABLE `exchange_rate_usd` (
  `id` varchar(15),
  `currency_code` varchar(5),
  `currency_name` varchar(20),
  `exchange_rate_usd` float,
  `updated_date` datetime,
  `date` date,
  `source` varchar(5),
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_campaigns_placement` (
  `id` varchar(50),
  `campaign_id` varchar(25),
  `placement_id` varchar(12),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `total_sales_14d` float,
  `total_orders_14d` int,
  `total_units_14d` int,
  `branded_searches_14d` int,
  `detail_pageview_14d` int,
  `order_new2_brand_14d` int,
  `sales_new2_brand_14d` float,
  `units_new2_brand_14d` int,
  `conversions_same_SKU_14d` int,
  `detail_pageview_clicks_14d` int,
  `sales_same_SKU_14d` float,
  `campaign_budget` int,
  `campaign_budget_type` varchar(50),
  `campaign_status` varchar(10),
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_campaigns_placement_video` (
  `id` varchar(50),
  `campaign_id` varchar(25),
  `placement_id` varchar(12),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `total_sales_14d` float,
  `total_orders_14d` int,
  `viewable_impressions` int,
  `video_first_quartile_views` int,
  `video_midpoint_views` int,
  `video_third_quartile_views` int,
  `video_complete_views` int,
  `video_unmutes` int,
  `video_5Second_views` int,
  `branded_searches_14d` int,
  `detail_pageview_14d` int,
  `order_new2_brand_14d` int,
  `sales_new2_brand_14d` float,
  `units_new2_brand_14d` int,
  `conversions_same_SKU_14d` int,
  `detail_pageview_clicks_14d` int,
  `sales_same_SKU_14d` float,
  `campaign_budget` int,
  `campaign_budget_type` varchar(25),
  `campaign_status` varchar(10),
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sp_campaigns` (
  `id` varchar(100),
  `campaign_id` varchar(20),
  `adgroup_id` varchar(20),
  `campaign_bidding_strategy` varchar(20),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `purchases_1d` int,
  `purchases_7d` int,
  `purchases_14d` int,
  `purchases_30d` int,
  `purchases_same_sku_1d` int,
  `purchases_same_sku_7d` int,
  `purchases_same_sku_14d` int,
  `purchases_same_sku_30d` int,
  `units_sold_clicks_1d` int,
  `units_sold_clicks_7d` int,
  `units_sold_clicks_14d` int,
  `units_sold_clicks_30d` int,
  `sales_1d` float,
  `sales_7d` float,
  `sales_14d` float,
  `sales_30d` float,
  `attributed_sales_same_sku_1d` float,
  `attributed_sales_same_sku_7d` float,
  `attributed_sales_same_sku_14d` float,
  `attributed_sales_same_sku_30d` float,
  `units_sold_same_sku_1d` int,
  `units_sold_same_sku_7d` int,
  `units_sold_same_sku_14d` int,
  `units_sold_same_sku_30d` int,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sdp_campaigns` (
  `id` varchar(100),
  `campaign_id` varchar(25),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `cost_type` varchar(10),
  `attributed_conversions_1d` int,
  `attributed_conversions_7d` int,
  `attributed_conversions_14d` int,
  `attributed_conversions_30d` int,
  `attributed_conversions_same_sku_1d` int,
  `attributed_conversions_same_sku_7d` int,
  `attributed_conversions_same_sku_14d` int,
  `attributed_conversions_same_sku_30d` int,
  `attributed_sales_1d` float,
  `attributed_sales_7d` float,
  `attributed_sales_14d` float,
  `attributed_sales_30d` float,
  `attributed_sales_same_sku_1d` float,
  `attributed_sales_same_sku_7d` float,
  `attributed_sales_same_sku_14d` float,
  `attributed_sales_same_sku_30d` float,
  `attributed_units_ordered_1d` int,
  `attributed_units_ordered_7d` int,
  `attributed_units_ordered_14d` int,
  `attributed_units_ordered_30d` int,
  `attributed_detail_pageview_14d` int,
  `attributed_orders_new_to_brand_14d` int,
  `attributed_units_ordered_new_to_brand_14d` int,
  `attributed_sales_new_to_brand_14d` float,
  `view_attributed_conversions_14d` int,
  `view_attributed_detail_pageview_14d` int,
  `view_attributed_sales_14d` float,
  `view_attributed_units_ordered_14d` int,
  `view_attributed_orders_new_to_brand_14d` int,
  `view_attributed_sales_new_to_brand_14d` float,
  `view_attributed_units_ordered_new_to_brand_14d` int,
  `view_attributed_branded_searches_14d` int,
  `view_impressions` int,
  `attributed_branded_searches_14d` int,
  `video_complete_views` int,
  `video_first_quartile_views` int,
  `video_midpoint_views` int,
  `video_third_quartile_views` int,
  `video_unmutes` int,
  `cumulative_reach` int,
  `avg_impressions_freq` float,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sp_campaigns_topofsearch` (
  `id` varchar(50),
  `campaign_id` varchar(20),
  `top_ofsearch_impression_share` float,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sp_targeting` (
  `id` varchar(100),
  `campaign_id` varchar(20),
  `adgroup_id` varchar(20),
  `keyword_id` varchar(20),
  `targeting` varchar(100),
  `match_type` varchar(40),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `purchases_1d` int,
  `purchases_7d` int,
  `purchases_14d` int,
  `purchases_30d` int,
  `purchases_same_sku_1d` int,
  `purchases_same_sku_7d` int,
  `purchases_same_sku_14d` int,
  `purchases_same_sku_30d` int,
  `units_sold_clicks_1d` int,
  `units_sold_clicks_7d` int,
  `units_sold_clicks_14d` int,
  `units_sold_clicks_30d` int,
  `sales_1d` float,
  `sales_7d` float,
  `sales_14d` float,
  `sales_30d` float,
  `attributed_sales_same_sku_1d` float,
  `attributed_sales_same_sku_7d` float,
  `attributed_sales_same_sku_14d` float,
  `attributed_sales_same_sku_30d` float,
  `units_sold_same_sku_1d` int,
  `units_sold_same_sku_7d` int,
  `units_sold_same_sku_14d` int,
  `units_sold_same_sku_30d` int,
  `sales_other_sku_7d` float,
  `units_sold_other_sku_7d` int,
  `top_ofsearch_impression_share` float,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__keywords_base_daily` (
  `id` varchar(50),
  `keyword_id` varchar(25),
  `sponsored_type_id` int,
  `keyword_text` varchar(100),
  `keyword_state` varchar(10),
  `keyword_bid` varchar(10),
  `match_type` varchar(10),
  `report_date` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_keywords` (
  `id` varchar(70),
  `keyword_id` varchar(20),
  `campaign_id` varchar(20),
  `adgroup_id` varchar(20),
  `targeting` varchar(100),
  `match_type` varchar(8),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `total_sales_14d` float,
  `total_orders_14d` int,
  `total_units_14d` int,
  `branded_searches_14d` int,
  `detail_pageview_14d` int,
  `order_new2_brand_14d` int,
  `sales_new2_brand_14d` float,
  `units_new2_brand_14d` int,
  `conversions_same_SKU_14d` int,
  `detail_pageview_clicks_14d` int,
  `sales_same_SKU_14d` float,
  `campaign_budget` int,
  `campaign_budget_type` varchar(25),
  `campaign_status` varchar(10),
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_keywords_video` (
  `id` varchar(70),
  `keyword_id` varchar(25),
  `campaign_id` varchar(25),
  `adgroup_id` varchar(25),
  `targeting` varchar(100),
  `match_type` varchar(8),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `total_sales_14d` float,
  `total_orders_14d` int,
  `viewable_impressions` int,
  `video_first_quartile_views` int,
  `video_midpoint_views` int,
  `video_third_quartile_views` int,
  `video_complete_views` int,
  `video_unmutes` int,
  `video_5Second_views` int,
  `branded_searches_14d` int,
  `detail_pageview_14d` int,
  `order_new2_brand_14d` int,
  `sales_new2_brand_14d` float,
  `units_new2_brand_14d` int,
  `conversions_same_SKU_14d` int,
  `detail_pageview_clicks_14d` int,
  `sales_same_SKU_14d` float,
  `campaign_budget` int,
  `campaign_budget_type` varchar(25),
  `campaign_status` varchar(10),
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sdp_targetings` (
  `id` varchar(100),
  `campaign_id` varchar(25),
  `adgroup_id` varchar(25),
  `target_id` varchar(25),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `targeting_expression` varchar(70),
  `targeting_text` varchar(100),
  `targeting_type` varchar(50),
  `attributed_conversions_1d` int,
  `attributed_conversions_7d` int,
  `attributed_conversions_14d` int,
  `attributed_conversions_30d` int,
  `attributed_conversions_same_sku_1d` int,
  `attributed_conversions_same_sku_7d` int,
  `attributed_conversions_same_sku_14d` int,
  `attributed_conversions_same_sku_30d` int,
  `attributed_sales_1d` float,
  `attributed_sales_7d` float,
  `attributed_sales_14d` float,
  `attributed_sales_30d` float,
  `attributed_sales_same_sku_1d` float,
  `attributed_sales_same_sku_7d` float,
  `attributed_sales_same_sku_14d` float,
  `attributed_sales_same_sku_30d` float,
  `attributed_units_ordered_1d` int,
  `attributed_units_ordered_7d` int,
  `attributed_units_ordered_14d` int,
  `attributed_units_ordered_30d` int,
  `attributed_detail_pageview_14d` int,
  `attributed_orders_new_to_brand_14d` int,
  `attributed_units_ordered_new_to_brand_14d` int,
  `attributed_sales_new_to_brand_14d` float,
  `view_attributed_conversions_14d` int,
  `view_attributed_detail_pageview_14d` int,
  `view_attributed_sales_14d` float,
  `view_attributed_units_ordered_14d` int,
  `view_attributed_orders_new_to_brand_14d` int,
  `view_attributed_sales_new_to_brand_14d` float,
  `view_attributed_units_ordered_new_to_brand_14d` int,
  `view_attributed_branded_searches_14d` int,
  `view_impressions` int,
  `attributed_branded_searches_14d` int,
  `video_complete_views` int,
  `video_first_quartile_views` int,
  `video_midpoint_views` int,
  `video_third_quartile_views` int,
  `video_unmutes` int,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__targetings_base` (
  `id` varchar(50),
  `target_id` varchar(25),
  `adgroup_id` varchar(25),
  `state` varchar(10),
  `expression_type` varchar(25),
  `bid` float,
  `target_expression_type` varchar(35),
  `target_expression_value` varchar(150),
  `resolved_expression_type` varchar(35),
  `resolved_expression_value` varchar(200),
  `sponsored_type_id` int,
  `start_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sp_search_term` (
  `id` varchar(100),
  `campaign_id` varchar(20),
  `adgroup_id` varchar(20),
  `keyword_id` varchar(20),
  `customer_search_term_id` varchar(12),
  `targeting` varchar(100),
  `match_type` varchar(40),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `purchases_1d` int,
  `purchases_7d` int,
  `purchases_14d` int,
  `purchases_30d` int,
  `purchases_same_sku_1d` int,
  `purchases_same_sku_7d` int,
  `purchases_same_sku_14d` int,
  `purchases_same_sku_30d` int,
  `units_sold_clicks_1d` int,
  `units_sold_clicks_7d` int,
  `units_sold_clicks_14d` int,
  `units_sold_clicks_30d` int,
  `sales_1d` float,
  `sales_7d` float,
  `sales_14d` float,
  `sales_30d` float,
  `attributed_sales_same_sku_1d` float,
  `attributed_sales_same_sku_7d` float,
  `attributed_sales_same_sku_14d` float,
  `attributed_sales_same_sku_30d` float,
  `units_sold_same_sku_1d` int,
  `units_sold_same_sku_7d` int,
  `units_sold_same_sku_14d` int,
  `units_sold_same_sku_30d` int,
  `sales_other_sku_7d` float,
  `units_sold_other_sku_7d` int,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_search_term` (
  `id` varchar(100),
  `keyword_id` varchar(25),
  `campaign_id` varchar(25),
  `adgroup_id` varchar(25),
  `customer_search_term_id` varchar(12),
  `targeting` varchar(100),
  `match_type` varchar(8),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `total_sales_14d` float,
  `total_orders_14d` int,
  `campaign_budget` int,
  `campaign_budget_type` varchar(20),
  `campaign_status` varchar(10),
  `keyword_bid` float,
  `keyword_status` varchar(10),
  `search_term_impression_rank` int,
  `search_term_impression_share` float,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_search_term_video` (
  `id` varchar(100),
  `keyword_id` varchar(25),
  `campaign_id` varchar(25),
  `adgroup_id` varchar(25),
  `customer_search_term_id` varchar(12),
  `targeting` varchar(100),
  `match_type` varchar(20),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `total_sales_14d` float,
  `total_orders_14d` int,
  `campaign_budget` int,
  `campaign_budget_type` varchar(25),
  `campaign_status` varchar(10),
  `keyword_bid` float,
  `keyword_status` varchar(10),
  `viewable_impressions` int,
  `video_first_quartile_views` int,
  `video_midpoint_views` int,
  `video_third_quartile_views` int,
  `video_complete_views` int,
  `video_unmutes` int,
  `video_5Second_views` int,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sp_customer_search_term` (
  `customer_search_term_id` varchar(12),
  `customer_search_term` varchar(200),
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`customer_search_term_id`)
);

CREATE TABLE `sem__sb_customer_search_term` (
  `customer_search_term_id` varchar(12),
  `customer_search_term` varchar(200),
  `lastupdate` datetime,
  PRIMARY KEY (`customer_search_term_id`)
);

CREATE TABLE `sem__sp_advertised_product` (
  `id` varchar(80),
  `campaign_id` varchar(20),
  `adgroup_id` varchar(20),
  `ad_id` varchar(20),
  `advertised_asin` varchar(15),
  `advertised_sku` varchar(50),
  `impressions` int,
  `clicks` int,
  `cost` float,
  `purchases_1d` int,
  `purchases_7d` int,
  `purchases_14d` int,
  `purchases_30d` int,
  `purchases_same_sku_1d` int,
  `purchases_same_sku_7d` int,
  `purchases_same_sku_14d` int,
  `purchases_same_sku_30d` int,
  `units_sold_clicks_1d` int,
  `units_sold_clicks_7d` int,
  `units_sold_clicks_14d` int,
  `units_sold_clicks_30d` int,
  `sales_1d` float,
  `sales_7d` float,
  `sales_14d` float,
  `sales_30d` float,
  `attributed_sales_same_sku_1d` float,
  `attributed_sales_same_sku_7d` float,
  `attributed_sales_same_sku_14d` float,
  `attributed_sales_same_sku_30d` float,
  `units_sold_same_sku_1d` int,
  `units_sold_same_sku_7d` int,
  `units_sold_same_sku_14d` int,
  `units_sold_same_sku_30d` int,
  `units_sold_other_sku_7d` int,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sp_purchased_product` (
  `id` varchar(150),
  `campaign_id` varchar(20),
  `adgroup_id` varchar(20),
  `keyword_id` varchar(20),
  `advertised_asin` varchar(15),
  `advertised_sku` varchar(20),
  `purchased_asin` varchar(15),
  `match_type` varchar(40),
  `purchases_1d` int,
  `purchases_7d` int,
  `purchases_14d` int,
  `purchases_30d` int,
  `units_sold_clicks_1d` int,
  `units_sold_clicks_7d` int,
  `units_sold_clicks_14d` int,
  `units_sold_clicks_30d` int,
  `sales_1d` float,
  `sales_7d` float,
  `sales_14d` float,
  `sales_30d` float,
  `units_sold_other_sku_1d` int,
  `units_sold_other_sku_7d` int,
  `units_sold_other_sku_14d` int,
  `units_sold_other_sku_30d` int,
  `sales_other_sku_1d` float,
  `sales_other_sku_7d` float,
  `sales_other_sku_14d` float,
  `sales_other_sku_30d` float,
  `purchases_other_sku_1d` int,
  `purchases_other_sku_7d` int,
  `purchases_other_sku_14d` int,
  `purchases_other_sku_30d` int,
  `report_date` datetime,
  `lastupdate` datetime,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem__sb_purchased_product` (
  `id` varchar(100),
  `campaign_id` varchar(25),
  `adgroup_id` varchar(25),
  `purchased_asin` varchar(15),
  `attribution_type` varchar(12),
  `product_name` varchar(220),
  `product_category` varchar(70),
  `total_sales_14d` float,
  `total_orders_14d` int,
  `total_units_14d` int,
  `sales_new2_brand_14d` float,
  `order_new2_brand_14d` int,
  `units_new2_brand_14d` int,
  `report_date` datetime,
  `lastupdate` datetime,
  `attribution_id` int,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s__amazon_orders` (
  `id` int,
  `store_id` int,
  `sales_channel_id` int,
  `amazon_order_id` varchar(20),
  `seller_order_id` varchar(30),
  `order_type` varchar(100),
  `sales_channel` varchar(50),
  `buyer_email` varchar(100),
  `buyer_name` varchar(500),
  `shipping_name` varchar(500),
  `shipping_add1` varchar(1000),
  `shipping_add2` varchar(1000),
  `shipping_state` varchar(20),
  `shipping_state_code` varchar(5),
  `shipping_city` varchar(100),
  `shipping_phone` varchar(20),
  `shipping_country` varchar(5),
  `shipping_postal_code` varchar(20),
  `ship_service_level` varchar(100),
  `ship_service_level_category` varchar(100),
  `fulfill_channel` varchar(20),
  `item_shipped` int,
  `item_unshipped` int,
  `total` float,
  `currency_code` varchar(10),
  `payment_method` varchar(50),
  `is_business_order` int,
  `is_premium_order` int,
  `is_prime` int,
  `replaced_order_id` varchar(25),
  `purchased_date` datetime,
  `latest_ship_date` datetime,
  `earliest_ship_date` datetime,
  `last_updated_source` datetime,
  `invoice_id` int,
  `status` varchar(50),
  `send_protect_mail` int,
  `last_updated_dwh` date,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s__amazon_order_details` (
  `id` int,
  `amazon_order_id` int,
  `amazon_order_item_id` varchar(20),
  `asin` varchar(20),
  `seller_sku` varchar(100),
  `item_title` varchar(200),
  `product_id` int,
  `warehouse_id` int,
  `quantity_ordered` int,
  `quantity_shipped` int,
  `currency_code` varchar(10),
  `item_price` float,
  `shipping_price` float,
  `giftwrap_price` float,
  `item_tax` float,
  `shipping_tax` float,
  `giftwrap_tax` float,
  `shipping_discount` float,
  `promotion_discount` float,
  `promotion_ids` varchar(500),
  `condition_note` varchar(500),
  `condition_id` varchar(20),
  `condition_subtype_id` varchar(50),
  `price_designtaion` varchar(50),
  `add_reserved` int,
  `last_updated_dwh` date,
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_product_assigned` (
  `id` varchar(45),
  `it_id` int,
  `user_id` int,
  `cate_id` text,
  `group_id` text,
  `product_id` text,
  `target_quantity` int,
  `assign_date` datetime,
  `last_update` date,
  `last_updated_dwh` date,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_users` (
  `id` int,
  `name` varchar(100),
  `email` char(50),
  `code` char(20),
  `manager_id` int,
  `type` tinyint,
  `published` tinyint(1),
  PRIMARY KEY (`id`)
);


-- Wayfair (sinh từ SHOW CREATE TABLE của bản sao staging nội bộ, bỏ NOT NULL để dễ seed; bảng đơn hàng chỉ gồm các cột được chép về)

CREATE TABLE `wayfair_accounts` (
  `id` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `account_name` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `currency_code` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `amz_merchant_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `store_account_id` int,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__campaign_info` (
  `campaign_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `account_id` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `last_updated_dwh` date,
  PRIMARY KEY (`campaign_id`)
);

CREATE TABLE `sem_wayfair__keyword_info` (
  `id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `keyword_id` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `keyword_match_type_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `keyword_value` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__keyword_matchtype` (
  `id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `keyword_match_type` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__product_info` (
  `id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `wayfair_sku` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `product_name` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `first_10_part_numbers` varchar(600) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `account_id` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `last_updated_dwh` date,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__search_term_info` (
  `id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `customer_search_term` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `wayfair_map_sku_product_id` (
  `sem_wayfair_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sku` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `account_id` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `original_supplier_part` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `supplier_part` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `wayfair_product_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  PRIMARY KEY (`sku`,`original_supplier_part`,`supplier_part`,`account_id`)
);

CREATE TABLE `sem_wayfair_map_sku_product_id` (
  `id` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `sem_wayfair_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sku` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `account_id` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `original_supplier_part` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `supplier_part` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `wayfair_product_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `time_upload_bulk_ads` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_id` varchar(20) DEFAULT NULL,
  `campaign_active_status` varchar(20) DEFAULT NULL,
  `current_part_number_active_status` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_wayfair_products` (
  `id` int,
  `wayfair_listing_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `supplier_part` varchar(60) DEFAULT NULL,
  `options` varchar(255) DEFAULT NULL,
  `wholesale_price` float DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `supplier_part_id` varchar(25) DEFAULT NULL,
  `wayfair_jjid` varchar(50) DEFAULT NULL,
  `status` varchar(25) DEFAULT NULL,
  `published` tinyint DEFAULT NULL,
  `update_time` datetime DEFAULT NULL,
  `upc` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_sales_channels` (
  `id` int,
  `code` varchar(45),
  `title` varchar(45),
  `store_account_id` int,
  `it__store_account_id` int DEFAULT NULL,
  `fulfill_method_id` int,
  `description` varchar(95) DEFAULT NULL,
  `published` int,
  `marketplace_id` int,
  `company_id` int,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_sales_marketplaces` (
  `id` int AUTO_INCREMENT,
  `title` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `original_marketplace_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT 'Marketplace ID',
  `marketplace_url` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `product_url` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `country_id` int COMMENT 'Table: country',
  `published` tinyint(1) DEFAULT '1',
  `main_marketplace` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_country` (
  `id` int AUTO_INCREMENT,
  `title` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `published` tinyint(1) DEFAULT '1',
  `business` int,
  `currency_code` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s__wayfair_orders` (
  `id` int,
  `sales_channel_id` int DEFAULT NULL,
  `po_number` varchar(50) DEFAULT NULL,
  `order_type` varchar(20) DEFAULT NULL,
  `po_date` datetime DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `customer_country` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s__wayfair_order_details` (
  `id` int,
  `order_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `item_number` varchar(20) DEFAULT NULL,
  `wayfair_sku` varchar(20) DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `wholesale_price` float DEFAULT NULL,
  `cancelled_quantity` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__wsp_campaign` (
  `id` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_date_run` date DEFAULT NULL,
  `campaign_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `targeting_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `store_url` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `impressions` int DEFAULT NULL,
  `spend` float DEFAULT NULL,
  `attr_rsales_wview_through_Day_14` float DEFAULT NULL,
  `attr_wholesale_cost_wview_through_Day_14` float DEFAULT NULL,
  `attr_orders_wview_through_Day_14` int DEFAULT NULL,
  `cost_per_attr_order_wview_through_Day_14` float DEFAULT NULL,
  `retail_roas_wview_through_Day_14` float DEFAULT NULL,
  `wholesale_cost_roas_wview_through_Day_14` float DEFAULT NULL,
  `attr_units_wview_through_Day_14` int DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__wsp_product` (
  `id` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `product_info_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `first_10_part_numbers` varchar(600) DEFAULT NULL,
  `name_of_class` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `store_url` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campaign_date_run` date DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `impressions` int DEFAULT NULL,
  `spend` float DEFAULT NULL,
  `attr_rsales_wview_through_Day_14` float DEFAULT NULL,
  `attr_wholesale_cost_wview_through_Day_14` float DEFAULT NULL,
  `attr_orders_wview_through_Day_14` int DEFAULT NULL,
  `cost_per_attr_order_wview_through_Day_14` float DEFAULT NULL,
  `retail_roas_wview_through_Day_14` float DEFAULT NULL,
  `wholesale_cost_roas_wview_through_Day_14` float DEFAULT NULL,
  `attr_units_wview_through_Day_14` int DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__wsp_keyword_targeting` (
  `id` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `keyword_info_id` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `store_url` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campaign_date_run` date DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `impressions` int DEFAULT NULL,
  `spend` decimal(10,2) DEFAULT NULL,
  `effective_cost_per_thousand_impressions` float DEFAULT NULL,
  `attr_rsales_wview_through_Day_14` float DEFAULT NULL,
  `attr_wholesale_cost_wview_through_Day_14` float DEFAULT NULL,
  `attr_orders_wview_through_Day_14` int DEFAULT NULL,
  `cost_per_attr_order_wview_through_Day_14` float DEFAULT NULL,
  `retail_roas_wview_through_Day_14` float DEFAULT NULL,
  `wholesale_cost_roas_wview_through_Day_14` float DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  `name_of_class` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `wayfair_sku` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `product_name` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `product_info_id` varchar(30) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__wsp_keyword_optimization` (
  `id` varchar(120),
  `campaign_id` varchar(30) DEFAULT NULL,
  `keyword_info_id` varchar(150) DEFAULT NULL,
  `store_url` varchar(100) DEFAULT NULL,
  `campaign_date_run` date DEFAULT NULL,
  `clicks` int DEFAULT NULL,
  `impressions` int DEFAULT NULL,
  `spend` float DEFAULT NULL,
  `attr_rsales_wview_through_Day_14` float DEFAULT NULL,
  `attr_wholesale_cost_wview_through_Day_14` float DEFAULT NULL,
  `attr_units_wview_through_Day_14` int DEFAULT NULL,
  `attr_orders_wview_through_Day_14` int DEFAULT NULL,
  `customer_search_term` text,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__wsp_search_term_research` (
  `id` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `customer_search_term_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `brand_catalog` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `name_of_class` varchar(70) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `total_search_term_impressions_in_the_last_30_days` int DEFAULT NULL,
  `search_term_share_of_impressions_for_given_class_percent` float DEFAULT NULL,
  `supplier_share_of_search_percent` float DEFAULT NULL,
  `supplier_share_of_page_1_percent` float DEFAULT NULL,
  `supplier_share_of_top_8_percent` float DEFAULT NULL,
  `account_id` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `report_date` date DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__campaign_info_daily` (
  `id` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `campaign_date_run` date DEFAULT NULL,
  `campaign_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campaign_is_active` tinyint(1) DEFAULT NULL,
  `campaign_daily_cap` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campaign_lifetime_budget` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campaign_init_date` date DEFAULT NULL,
  `campaign_end_date` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sem_wayfair__keyword_info_daily` (
  `id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `keyword_info_id` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campaign_date_run` date DEFAULT NULL,
  `keyword_max_bid` float DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);


-- Tồn kho (sinh từ SHOW CREATE TABLE của bản sao staging nội bộ, bỏ NOT NULL để dễ seed)

CREATE TABLE `wh_warehouses` (
  `id` int,
  `title` varchar(64) DEFAULT NULL,
  `code` varchar(20) DEFAULT NULL,
  `country_id` varchar(15) DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  `is_virtual` tinyint(1) DEFAULT NULL,
  `is_managed` tinyint DEFAULT NULL,
  `published` tinyint DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `wh_product_inventory` (
  `id` int AUTO_INCREMENT,
  `product_id` int,
  `warehouse_id` int,
  `quantity` int,
  `reserved` int DEFAULT '0',
  `locked_quantity` int,
  `returned_quantity` int,
  `lastupdated` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`)
);

CREATE TABLE `wh_product_inventory_available` (
  `id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `product_id` int,
  `warehouse_id` int,
  `quantity` int DEFAULT NULL,
  `reserved` int DEFAULT NULL,
  `inventory_available` int DEFAULT NULL,
  `last_updated_dwh` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `wh_wayfair_castlegate_inventory` (
  `id` int,
  `sales_store_account_id` int DEFAULT '0',
  `castlegate_warehouse_id` int DEFAULT '0',
  `product_id` int DEFAULT '0',
  `part_number` varchar(100) DEFAULT NULL,
  `item_number` varchar(100) DEFAULT NULL,
  `qty_on_order` int DEFAULT '0',
  `qty_on_hand` int DEFAULT '0',
  `qty_in_stock` int DEFAULT '0',
  `qty_fulfillable` int DEFAULT '0',
  `qty_unfulfillable` int DEFAULT '0',
  `qty_on_transfers` int DEFAULT '0',
  `qty_held` int DEFAULT '0',
  `qty_unpickable` int DEFAULT '0',
  `qty_expired` int DEFAULT '0',
  `qty_allocated` int DEFAULT '0',
  `qty_unreconciled` int DEFAULT '0',
  `in_stock_update` datetime DEFAULT NULL,
  `update_at` datetime DEFAULT NULL,
  `last_updated` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `wh_wayfair_castlegate_warehouses` (
  `id` int unsigned,
  `title` varchar(100) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `prd_productcombo` (
  `id` int AUTO_INCREMENT,
  `product_id` int,
  `child_id` int,
  `quantity` int COMMENT 'Quantity of child in combo',
  `dedicate_quantity` int COMMENT 'Virtual Quantity from Calculator',
  `inventorytype` tinyint DEFAULT NULL COMMENT '1: Check Inventory by Combo Product; 0: Check Inventory by Single Product',
  `updator` int,
  `update_time` datetime,
  `published` tinyint,
  PRIMARY KEY (`id`),
  KEY `idx_0001` (`product_id`),
  KEY `idx_0002` (`child_id`)
);

CREATE TABLE `s_sales_fulfill_methods` (
  `id` int AUTO_INCREMENT,
  `title` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `fulfill_process` int COMMENT 'enumeration',
  `pay_shipment` tinyint(1) DEFAULT '1',
  `published` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`)
);

CREATE TABLE `pu_sc_purchase_orders` (
  `id` int,
  `order_number` varchar(125) DEFAULT NULL,
  `order_date` date DEFAULT NULL,
  `estimate_delivery_date` date DEFAULT NULL,
  `status` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `pu_sc_purchase_order_details` (
  `id` int,
  `purchase_order_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `pu_shipments` (
  `id` int,
  `shipment_number` varchar(50) DEFAULT NULL,
  `shipment_type` int DEFAULT NULL,
  `status` tinyint(1) DEFAULT NULL,
  `estimated_time_departure` date DEFAULT NULL,
  `actual_time_departure` date DEFAULT NULL,
  `estimated_time_arrival` date DEFAULT NULL,
  `actual_time_arrival` date DEFAULT NULL,
  `estimated_time_import` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `pu_shipment_containers` (
  `id` int,
  `shipment_id` int DEFAULT NULL,
  `warehouse_id` int DEFAULT NULL,
  `container_number` varchar(225) DEFAULT NULL,
  `eta_warehouse` date DEFAULT NULL,
  `import_date` date DEFAULT NULL,
  `status` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `pu_shipment_container_details` (
  `id` int,
  `container_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `received_quantity` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sc_delivery_receipts` (
  `id` int,
  `purchase_order_id` int DEFAULT NULL,
  `receipt_number` varchar(100) DEFAULT NULL,
  `received_date` date DEFAULT NULL,
  `status` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `sc_delivery_receipt_containers` (
  `id` int,
  `receipt_id` int DEFAULT NULL,
  `container_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `received_quantity` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `shipment__fbashipments` (
  `id` int,
  `sales_channel_id` int DEFAULT NULL,
  `shipment_id` varchar(100) DEFAULT NULL,
  `shipment_name` varchar(250) DEFAULT NULL,
  `warehouse_id` int DEFAULT NULL,
  `fulfillcenter` varchar(20) DEFAULT NULL,
  `store_id` int DEFAULT NULL,
  `working_date` date DEFAULT NULL,
  `shipped_date` date DEFAULT NULL,
  `delivered_date` date DEFAULT NULL,
  `closed_date` date DEFAULT NULL,
  `canceled_date` date DEFAULT NULL,
  `estimate_ship_date` date DEFAULT NULL,
  `status` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `shipment__fbashipment_details` (
  `id` int,
  `fbashipment_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `sku` varchar(100) DEFAULT NULL,
  `quantityshipped` int DEFAULT NULL,
  `quantityactualshipped` int DEFAULT NULL,
  `quantityreceived` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `shipment__wayfair_castlegate_inbound_shipments` (
  `id` int,
  `store_account_id` int DEFAULT NULL,
  `order_number` varchar(100) DEFAULT NULL,
  `status` int DEFAULT NULL,
  `planned_shipdate` date DEFAULT NULL,
  `date_shipped` date DEFAULT NULL,
  `wf_warehouse` varchar(100) DEFAULT NULL,
  `warehouse_id` int DEFAULT NULL,
  `eta` date DEFAULT NULL,
  `create_date` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `shipment__wayfair_castlegate_inbound_shipment_details` (
  `id` int,
  `order_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `part_number` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `shipped_qty` int DEFAULT NULL,
  `received_quantity` int DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `s_sales_report_data_by_orderdate` (
  `id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `report_date` date DEFAULT NULL,
  `sales_channel_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `invoice_count` int DEFAULT NULL,
  `total_quantity` decimal(32,0) DEFAULT NULL,
  `revenue` double DEFAULT NULL,
  `profit` double DEFAULT NULL,
  `profit_4` float DEFAULT NULL,
  `profit_5` float DEFAULT NULL,
  `cogs` float DEFAULT NULL,
  `return_fee` float DEFAULT NULL,
  `channel_fee` float DEFAULT NULL,
  `dgmk_fee` float DEFAULT NULL,
  `wh_fee` float DEFAULT NULL,
  `vn_fee` float DEFAULT NULL,
  `last_updated_dwh` date DEFAULT NULL,
  `currency` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `wh_product_inventory_trace` (
  `id` varchar(45),
  `product_id` int,
  `warehouse_id` int,
  `quantity` int,
  `reserved` int DEFAULT '0',
  `locked_quantity` int,
  `returned_quantity` int,
  `lastupdated` datetime DEFAULT NULL,
  `the_date` date,
  `id_wh_pi` int,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`)
);

CREATE TABLE `wh_wayfair_castlegate_inventory_history` (
  `id` int,
  `date` date,
  `sales_store_account_id` int DEFAULT '0',
  `castlegate_warehouse_id` int DEFAULT '0',
  `product_id` int DEFAULT '0',
  `part_number` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci,
  `on_hand_quantity` int DEFAULT '0',
  `last_updated` date DEFAULT NULL,
  PRIMARY KEY (`id`)
);

-- Shopify (chỉ các cột ETL chép về, xem COLUMNS trong etl/sync_staging.py)
CREATE TABLE `s__shopify_orders_v2` (
  `shopify_order_id` varchar(30) NOT NULL,
  `sales_channel_id` int DEFAULT NULL,
  `customer_id` varchar(30) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `total_price` float DEFAULT NULL,
  `subtotal_price` float DEFAULT NULL,
  `total_tax` float DEFAULT NULL,
  `total_discounts` float DEFAULT NULL,
  `financial_status` varchar(30) DEFAULT NULL,
  `fulfillment_status` varchar(30) DEFAULT NULL,
  `currency` varchar(30) DEFAULT NULL,
  `source_name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`shopify_order_id`)
);

CREATE TABLE `s__shopify_order_details_v2` (
  `line_item_id` varchar(30) NOT NULL,
  `order_id` varchar(30) NOT NULL,
  `product_id` int DEFAULT NULL,
  `sku` varchar(50) DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `price` float DEFAULT NULL,
  `total_discount` float DEFAULT NULL,
  `discount_allocations_amount` float DEFAULT NULL,
  `fulfillment_status` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`line_item_id`)
);

CREATE TABLE `s__shopify_order_refund_line_items` (
  `id` varchar(30) NOT NULL,
  `line_item_id` varchar(30) DEFAULT NULL,
  `order_id` varchar(30) DEFAULT NULL,
  `refund_id` varchar(30) NOT NULL,
  `quantity` int DEFAULT NULL,
  `subtotal` decimal(18,4) DEFAULT NULL,
  `total_tax` decimal(18,4) DEFAULT NULL,
  PRIMARY KEY (`id`)
);
