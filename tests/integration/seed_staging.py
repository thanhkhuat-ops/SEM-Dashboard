"""Tạo schema `staging` giả lập (đúng cấu trúc theo từ điển dữ liệu) và nạp dữ liệu thử có kiểm soát.

Chỉ dùng cho MySQL thử nghiệm trong Docker. Các giá trị được chọn để kiểm tra những quy tắc quan trọng của ETL:
quy đổi tỷ giá (CAD, có ngày thiếu tỷ giá), SB bảng _video bị bảng thường ghi đè, SD vCPM/CPC và lỗi đảo cột NTB,
map SKU/ASIN -> sản phẩm, campaign Auto/Manual, search term để phân loại từ khóa.
"""
import hashlib
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
START, END = date(2026, 9, 1), date(2026, 10, 20)
US, CA = "PUS001", "PCA001"


def tid(term: str) -> str:
    return hashlib.md5(term.lower().strip().encode()).hexdigest()[:12]


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


class Seeder:
    def __init__(self, conn):
        self.conn = conn
        self.rows: dict[str, list[dict]] = {}

    def add(self, table: str, **row) -> None:
        self.rows.setdefault(table, []).append(row)

    def flush(self) -> None:
        with self.conn.cursor() as cur:
            for table, rows in self.rows.items():
                cols = sorted({k for r in rows for k in r})
                sql = (f"INSERT INTO `{table}` ({', '.join('`' + c + '`' for c in cols)}) "
                       f"VALUES ({', '.join(['%s'] * len(cols))})")
                cur.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        self.conn.commit()


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def seed(host: str, port: int, user: str, password: str, schema: str = "staging") -> dict:
    conn = pymysql.connect(host=host, port=port, user=user, password=password, charset="utf8mb4", autocommit=True)
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{schema}`")
        cur.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
        cur.execute(f"USE `{schema}`")
        for stmt in (HERE / "staging_schema.sql").read_text(encoding="utf-8").split(";\n"):
            if stmt.strip() and "CREATE TABLE" in stmt:
                cur.execute(stmt)
    conn.autocommit(False)
    s = Seeder(conn)
    rnd = random.Random(42)

    # ---------- master data ----------
    s.add("s_sales_store_companies", id=1, title="Hurav", published=1)
    s.add("s_sales_store_companies", id=2, title="DH Intra", published=1)
    s.add("s_sales_store_accounts", id=15, sales_store_company_id=1, sales_marketplace_id=1, title="Hurav", type=1, published=1)
    s.add("s_sales_store_accounts", id=16, sales_store_company_id=2, sales_marketplace_id=2, title="DH Intra", type=1, published=1)
    s.add("amazon_profiles_base", id="ATVPDKIKX0DER_M1", profile_id=US, marketplace_id="ATVPDKIKX0DER", merchant_id="M1",
          store_account_id=15, country_code="US", profile_name="Hurav LLC", currency_code="USD", lastupdate=END)
    s.add("amazon_profiles_base", id="A2EUQ1WTGCTBG2_M2", profile_id=CA, marketplace_id="A2EUQ1WTGCTBG2", merchant_id="M2",
          store_account_id=16, country_code="CA", profile_name="DH International", currency_code="CAD", lastupdate=END)
    s.add("prd_brands", id=1, brand_name="Tranquillo", published=1)
    s.add("prd_brands", id=2, brand_name="No Brand", published=1)
    s.add("prd_groups", id=10, title="Hammock", published=1)
    s.add("prd_groups", id=20, title="Office Chair", published=1)
    # PIC: user 501 từng phụ trách cả hai nhóm, phiên bản mới nhất chỉ còn Hammock; user 502 phụ trách Office Chair
    # (giao trực tiếp theo sản phẩm); 503 là phòng ban (type = 2), không phải PIC
    s.add("prd_product_assigned", id="1_20240101000000", it_id=1, user_id=501, cate_id="[]", group_id='["10","20"]',
          product_id="[]", assign_date=datetime(2024, 1, 1), last_update=date(2024, 1, 1), last_updated_dwh=date(2024, 1, 1))
    s.add("prd_product_assigned", id="1_20250301000000", it_id=1, user_id=501, cate_id="[]", group_id='["10"]',
          product_id="[]", assign_date=datetime(2025, 3, 1), last_update=date(2025, 3, 1), last_updated_dwh=date(2025, 3, 1))
    s.add("prd_product_assigned", id="2_20250301000000", it_id=2, user_id=502, cate_id="[]", group_id="[]",
          product_id='["201"]', assign_date=datetime(2025, 3, 1), last_update=date(2025, 3, 1), last_updated_dwh=date(2025, 3, 1))
    s.add("s_users", id=501, name="PIC Hammock", email="pic.hammock@example.com", code="T0501", manager_id=0, type=1, published=1)
    s.add("s_users", id=502, name="PIC Chair", email="pic.chair@example.com", code="T0502", manager_id=501, type=1, published=1)
    s.add("s_users", id=503, name="Sales Team", type=2, published=1)
    for pid, sku, title, grp, vol in [(101, "AX01", "Hammock Chair Grey", 10, 0.2), (102, "AX02", "Hammock Chair Blue", 10, 0.1),
                                      (201, "CH01", "Office Chair Mesh", 20, 0.34)]:
        s.add("prd_product", id=pid, product_sku=sku, title=title, short_name=title, brand_id=1, group_id=grp, company_id=2,
              volume=vol)
    asins = {"B0HAM00001": 101, "B0HAM00002": 102, "B0CHR00001": 201}
    for i, (asin, pid) in enumerate(asins.items(), 1):
        s.add("prd_asin", id=i, asin=asin, product_id=pid)
    for i, (store, sku, asin, pid, mp) in enumerate([
            (15, "SKU-101", "B0HAM00001", 101, "ATVPDKIKX0DER"), (15, "SKU-102", "B0HAM00002", 102, "ATVPDKIKX0DER"),
            (16, "SKU-201-CA", "B0CHR00001", 0, "A2EUQ1WTGCTBG2")], 1):
        s.add("prd_amazon_listings", id=i, store_account_id=store, product_id=pid, seller_sku=sku, asin=asin, marketplace_id=mp)
    s.add("sem__portfolios_base", portfolio_id="PF1", profile_id=US, portfolio_name="HMD - Hammock", state="ENABLED")

    campaigns = [  # campaign_id, type, profile, name
        ("C_SP_AUTO", 2, US, "HAM_SP_Auto"), ("C_SP_MAN", 2, US, "HAM_SP_Manual_Exact"), ("C_SB1", 1, US, "HAM_SB_Video"),
        ("C_SD1", 3, US, "HAM_SD_vCPM_Views"), ("C_SD2", 3, US, "HAM_SD_CPC"), ("C_SP_CA", 2, CA, "CHR_SP_CA")]
    for cid, st, prof, name in campaigns:
        s.add("sem__campaigns_base", id=f"{cid}_{st}", campaign_id=cid, sponsored_type_id=st,
              portfolio_id="PF1" if prof == US else None, profile_id=prof, campaign_name=name)
        for d in days():
            s.add("sem__campaigns_base_daily", id=f"{cid}_{st}_{ymd(d)}", campaign_id=cid, sponsored_type_id=st,
                  budget=50.0, budget_type="DAILY", state="ENABLED", start_date=START, report_date=d)
    adgroups = [("AG1", "C_SP_AUTO", 2), ("AG2", "C_SP_MAN", 2), ("AG3", "C_SB1", 1), ("AG4", "C_SD1", 3),
                ("AG6", "C_SD2", 3), ("AG5", "C_SP_CA", 2)]
    for ag, cid, st in adgroups:
        s.add("sem__adgroups_base", id=f"{cid}_{ag}_{st}", adgroup_id=ag, campaign_id=cid, sponsored_type_id=st,
              adgroup_name=f"{ag} group")
    for pid_, name in [("1", "Top of Search on-Amazon"), ("3", "Other Placements")]:
        s.add("sem__sb_placement_mapping", placement_id=pid_, placement=name)

    # Tỷ giá: CAD thiếu ngày 2026-09-10 để kiểm tra lấy tỷ giá gần nhất
    for d in days():
        if d != date(2026, 9, 10):
            s.add("exchange_rate_usd", id=f"CAD-{ymd(d)}", currency_code="CAD", exchange_rate_usd=0.72, date=d)
        s.add("exchange_rate_usd", id=f"USD-{ymd(d)}", currency_code="USD", exchange_rate_usd=1.0, date=d)

    # ---------- SP ----------
    sp_targets = {  # adgroup -> [(keyword_id, targeting, match_type, bid)]
        "AG1": [("T1", "close-match", "TARGETING_EXPRESSION_PREDEFINED", None), ("T2", "loose-match", "TARGETING_EXPRESSION_PREDEFINED", None)],
        "AG2": [("K1", "hammock", "EXACT", "1.25"), ("K2", "hammock chair for bedroom", "PHRASE", "0.90"),
                ("K3", "tranquillo hammock", "EXACT", "0.60")],
        "AG5": [("K4", "office chair", "BROAD", "1.10")],
    }
    search_terms = {
        "T1": ["hammock swing chair", "cotton hammock 2 person", "b0zzz99999"],
        "T2": ["vivere hammock stand", "hammock chair for bedroom"],
        "K1": ["hammock"], "K2": ["hammock chair for bedroom", "hammock chair for bedroom grey"],
        "K3": ["tranquillo hammock"], "K4": ["office chair", "ergonomic office chair with lumbar support"],
    }
    ads = {"AG1": [("AD1", "B0HAM00001", "SKU-101"), ("AD2", "B0HAM00002", "SKU-102")], "AG2": [("AD3", "B0HAM00001", "SKU-101")],
           "AG5": [("AD4", "B0CHR00001", "SKU-201-CA")]}
    campaign_of = {ag: cid for ag, cid, _ in adgroups}
    for t in sorted({t for terms in search_terms.values() for t in terms}):
        s.add("sem__sp_customer_search_term", customer_search_term_id=tid(t), customer_search_term=t, report_date=END)
    for kid in ("K1", "K2", "K3", "K4"):
        text_, bid = next((t, b) for v in sp_targets.values() for k, t, _, b in v if k == kid)
        for d in days():
            s.add("sem__keywords_base_daily", id=f"{kid}_2_{ymd(d)}", keyword_id=kid, sponsored_type_id=2,
                  keyword_text=text_, keyword_state="ENABLED", keyword_bid=bid, match_type="EXACT", report_date=d)

    for d in days():
        s.add("sem__sp_campaigns_topofsearch", id=f"C_SP_MAN_{d}", campaign_id="C_SP_MAN",
              top_ofsearch_impression_share=0.25, report_date=d)
        for ag, targets in sp_targets.items():
            cid = campaign_of[ag]
            ag_tot = {"impressions": 0, "clicks": 0, "cost": 0.0, "p7": 0, "s7": 0.0, "u7": 0}
            for kid, targeting, mt, _ in targets:
                kt = {"impressions": 0, "clicks": 0, "cost": 0.0, "p7": 0, "s7": 0.0, "u7": 0}
                for term in search_terms[kid]:
                    clicks = rnd.randint(0, 6)
                    cost = round(clicks * 0.8, 2)
                    orders = 1 if (clicks >= 4 and "vivere" not in term and term != "b0zzz99999") else 0
                    sales = 35.0 * orders
                    imp = clicks * 40 + 20
                    s.add("sem__sp_search_term", id=f"{cid}_{ag}_{tid(term)}_{kid}_{d}", campaign_id=cid, adgroup_id=ag,
                          keyword_id=kid, customer_search_term_id=tid(term), targeting=targeting, match_type=mt,
                          impressions=imp, clicks=clicks, cost=cost, purchases_7d=orders, purchases_14d=orders,
                          units_sold_clicks_7d=orders, sales_7d=sales, sales_14d=sales, purchases_same_sku_7d=orders,
                          attributed_sales_same_sku_7d=sales, report_date=d, lastupdate=END)
                    for k, v in (("impressions", imp), ("clicks", clicks), ("cost", cost), ("p7", orders), ("s7", sales), ("u7", orders)):
                        kt[k] += v
                s.add("sem__sp_targeting", id=f"{cid}_{ag}_{kid}_{d}", campaign_id=cid, adgroup_id=ag, keyword_id=kid,
                      targeting=targeting, match_type=mt, impressions=kt["impressions"], clicks=kt["clicks"], cost=kt["cost"],
                      purchases_7d=kt["p7"], purchases_14d=kt["p7"], units_sold_clicks_7d=kt["u7"], sales_7d=kt["s7"],
                      sales_14d=kt["s7"], purchases_same_sku_7d=kt["p7"], attributed_sales_same_sku_7d=kt["s7"],
                      top_ofsearch_impression_share=0.2, report_date=d, lastupdate=END)
                for k in ag_tot:
                    ag_tot[k] += kt[k]
            s.add("sem__sp_campaigns", id=f"{cid}_{ag}_{d}", campaign_id=cid, adgroup_id=ag, campaign_bidding_strategy="legacy",
                  impressions=ag_tot["impressions"], clicks=ag_tot["clicks"], cost=ag_tot["cost"], purchases_7d=ag_tot["p7"],
                  purchases_14d=ag_tot["p7"], units_sold_clicks_7d=ag_tot["u7"], sales_7d=ag_tot["s7"], sales_14d=ag_tot["s7"],
                  purchases_same_sku_7d=ag_tot["p7"], attributed_sales_same_sku_7d=ag_tot["s7"], report_date=d, lastupdate=END)
            n_ads = len(ads[ag])
            for i, (ad_id, asin, sku) in enumerate(ads[ag]):
                share = 0.7 if (n_ads > 1 and i == 0) else (0.3 if n_ads > 1 else 1.0)
                s.add("sem__sp_advertised_product", id=f"{cid}_{ag}_{ad_id}_{d}", campaign_id=cid, adgroup_id=ag, ad_id=ad_id,
                      advertised_asin=asin, advertised_sku=sku, impressions=int(ag_tot["impressions"] * share),
                      clicks=int(ag_tot["clicks"] * share), cost=round(ag_tot["cost"] * share, 2),
                      purchases_7d=int(ag_tot["p7"] * share), units_sold_clicks_7d=int(ag_tot["u7"] * share),
                      sales_7d=round(ag_tot["s7"] * share, 2), report_date=d, lastupdate=END)
        s.add("sem__sp_purchased_product", id=f"pp_{d}", campaign_id="C_SP_AUTO", adgroup_id="AG1", keyword_id="T1",
              advertised_asin="B0HAM00001", advertised_sku="SKU-101", purchased_asin="B0HAM00002", match_type="TARGETING_EXPRESSION",
              purchases_other_sku_7d=1, units_sold_other_sku_7d=1, sales_other_sku_7d=30.0, report_date=d, lastupdate=END)

    # ---------- SB: _video và bảng thường trùng khóa ngày START (bảng thường phải thắng) ----------
    sb_terms = ["outdoor hammock", "outdoor hammock with stand"]
    for t in sb_terms:
        s.add("sem__sb_customer_search_term", customer_search_term_id=tid(t), customer_search_term=t)
    for d in days():
        s.add("sem__keywords_base_daily", id=f"KB1_1_{ymd(d)}", keyword_id="KB1", sponsored_type_id=1, keyword_text="outdoor hammock",
              keyword_state="ENABLED", keyword_bid="1.50", match_type="BROAD", report_date=d)
        s.add("sem__sb_keywords", id=f"KB1_C_SB1_AG3_{d}", keyword_id="KB1", campaign_id="C_SB1", adgroup_id="AG3",
              targeting="outdoor hammock", match_type="BROAD", impressions=500, clicks=10, cost=12.0, total_sales_14d=80.0,
              total_orders_14d=2, total_units_14d=2, order_new2_brand_14d=1, sales_new2_brand_14d=40.0, detail_pageview_14d=30,
              report_date=d, lastupdate=END)
        s.add("sem__sb_search_term", id=f"KB1_{tid(sb_terms[0])}_{d}", keyword_id="KB1", campaign_id="C_SB1", adgroup_id="AG3",
              customer_search_term_id=tid(sb_terms[0]), targeting="outdoor hammock", match_type="BROAD", impressions=300,
              clicks=6, cost=7.0, total_sales_14d=40.0, total_orders_14d=1, report_date=d, lastupdate=END)
        s.add("sem__sb_search_term", id=f"KB1_{tid(sb_terms[1])}_{d}", keyword_id="KB1", campaign_id="C_SB1", adgroup_id="AG3",
              customer_search_term_id=tid(sb_terms[1]), targeting="outdoor hammock", match_type="BROAD", impressions=200,
              clicks=4, cost=5.0, total_sales_14d=40.0, total_orders_14d=1, report_date=d, lastupdate=END)
        for pl, share in (("1", 0.6), ("3", 0.4)):
            s.add("sem__sb_campaigns_placement", id=f"{pl}_C_SB1_{d}", campaign_id="C_SB1", placement_id=pl,
                  impressions=int(500 * share), clicks=int(10 * share), cost=12.0 * share, total_sales_14d=80.0 * share,
                  total_orders_14d=int(2 * share) or 1, total_units_14d=1, order_new2_brand_14d=1, sales_new2_brand_14d=20.0,
                  detail_pageview_clicks_14d=10, report_date=d, lastupdate=END)
        s.add("sem__sb_purchased_product", id=f"sbpp_{d}", campaign_id="C_SB1", adgroup_id="AG3", purchased_asin="B0HAM00001",
              attribution_type="Promoted", total_sales_14d=60.0, total_orders_14d=2, total_units_14d=2, report_date=d)
        s.add("sem__sb_purchased_product", id=f"sbpp2_{d}", campaign_id="C_SB1", adgroup_id="AG3", purchased_asin="B0HAM00002",
              attribution_type="Brand Halo", total_sales_14d=20.0, total_orders_14d=1, total_units_14d=1, report_date=d)
    # bản ghi video trùng khóa với bảng thường (giá trị sai, phải bị ghi đè)
    s.add("sem__sb_keywords_video", id="dup", keyword_id="KB1", campaign_id="C_SB1", adgroup_id="AG3", targeting="outdoor hammock",
          match_type="BROAD", impressions=99999, clicks=999, cost=999.0, total_sales_14d=1.0, total_orders_14d=0, report_date=START)
    s.add("sem__sb_campaigns_placement_video", id="dupp", campaign_id="C_SB1", placement_id="1", impressions=99999, clicks=999,
          cost=999.0, total_sales_14d=1.0, total_orders_14d=0, report_date=START)

    # ---------- SD: C_SD1 vCPM (dùng view_*), C_SD2 CPC (dùng attributed_*, cột NTB bị đảo ở nguồn) ----------
    s.add("sem__targetings_base", id="TD1_AG4", target_id="TD1", adgroup_id="AG4", state="enabled", bid=2.0, sponsored_type_id=3)
    s.add("sem__targetings_base", id="TD2_AG6", target_id="TD2", adgroup_id="AG6", state="enabled", bid=0.8, sponsored_type_id=3)
    for d in days():
        s.add("sem__sdp_campaigns", id=f"C_SD1_{d}", campaign_id="C_SD1", impressions=10000, clicks=20, cost=15.0, cost_type="vCPM",
              attributed_conversions_14d=1, attributed_sales_14d=30.0, view_attributed_conversions_14d=3,
              view_attributed_sales_14d=90.0, view_attributed_units_ordered_14d=3, view_attributed_orders_new_to_brand_14d=2,
              view_attributed_sales_new_to_brand_14d=60.0, report_date=d, lastupdate=END)
        s.add("sem__sdp_campaigns", id=f"C_SD2_{d}", campaign_id="C_SD2", impressions=4000, clicks=30, cost=10.0, cost_type="CPC",
              attributed_conversions_14d=2, attributed_sales_14d=50.0, attributed_units_ordered_14d=2,
              attributed_orders_new_to_brand_14d=25,  # thực tế là doanh số NTB
              attributed_sales_new_to_brand_14d=1,    # thực tế là số đơn NTB
              report_date=d, lastupdate=END)
        s.add("sem__sdp_targetings", id=f"C_SD1_AG4_TD1_{d}", campaign_id="C_SD1", adgroup_id="AG4", target_id="TD1",
              impressions=10000, clicks=20, cost=15.0, targeting_expression="views=(exact-product lookback=30)",
              attributed_conversions_14d=1, attributed_sales_14d=30.0, view_attributed_conversions_14d=3,
              view_attributed_sales_14d=90.0, report_date=d, lastupdate=END)
        s.add("sem__sdp_targetings", id=f"C_SD2_AG6_TD2_{d}", campaign_id="C_SD2", adgroup_id="AG6", target_id="TD2",
              impressions=4000, clicks=30, cost=10.0, targeting_expression='asin="B0COMP0001"',
              attributed_conversions_14d=2, attributed_sales_14d=50.0, report_date=d, lastupdate=END)

    # ---------- đơn hàng (tổng doanh số cho TACoS) ----------
    oid = 0
    for d in days():
        for store, channel, asin, price in ((15, "Amazon.com", "B0HAM00001", 35.0), (15, "Amazon.com", "B0HAM00002", 30.0),
                                            (16, "Amazon.ca", "B0CHR00001", 120.0)):
            for _ in range(3):
                oid += 1
                s.add("s__amazon_orders", id=oid, store_id=store, amazon_order_id=f"111-{oid}", sales_channel=channel,
                      purchased_date=f"{d} 10:00:00", status="Shipped", currency_code="USD" if store == 15 else "CAD")
                s.add("s__amazon_order_details", id=oid, amazon_order_id=oid, asin=asin, quantity_ordered=1,
                      item_price=price, product_id=0, currency_code="USD" if store == 15 else "CAD")
        oid += 1  # đơn bị hủy: không được tính
        s.add("s__amazon_orders", id=oid, store_id=15, amazon_order_id=f"111-{oid}", sales_channel="Amazon.com",
              purchased_date=f"{d} 11:00:00", status="Canceled")
        s.add("s__amazon_order_details", id=oid, amazon_order_id=oid, asin="B0HAM00001", quantity_ordered=1, item_price=999.0)

    seed_wayfair(s)
    seed_shopify(s)
    seed_inventory(s)
    s.flush()
    counts = {t: len(r) for t, r in s.rows.items()}
    conn.close()
    return counts


WF_EXACT, WF_PHRASE = "125661628762", "178159907513"


def seed_wayfair(s: Seeder) -> None:
    """Wayfair: Arozu (USD, wayfair.com) có 1 campaign Keyword Targeting (W1) + 1 Product Targeting (W2); DHI (CAD)
    chạy W3 trên wayfair.ca. Mỗi ngày: W1 spend 10, W2 spend 20, W3 spend 10 CAD; đơn Arozu 2 x 60 dropship
    + 1 x 60 CastleGate + 1 PO bị hủy; đơn DHI 1 x 100 CAD."""
    s.add("wayfair_accounts", id="293856", account_name="Arozu", currency_code="USD", store_account_id=37)
    s.add("wayfair_accounts", id="184614", account_name="DH International Trading Inc.", currency_code="CAD",
          store_account_id=17)
    s.add("s_country", id=1, code="US", currency_code="USD")
    s.add("s_country", id=4, code="CA", currency_code="CAD")
    s.add("s_sales_marketplaces", id=31, country_id=1)
    s.add("s_sales_marketplaces", id=32, country_id=4)
    for cid, code, title, store, mp, fm in ((56, "WAYFAIR-AROZU", "Wayfair Arozu", 37, 31, 3),
                                            (58, "WAYFAIR-AROZU-CG", "Wayfair Arozu CG", 37, 31, 2),
                                            (27, "WAYFAIR-DHI", "Wayfair DHIntra", 17, 32, 3),
                                            (53, "AMZ-AROZU-FBA", "Amz Arozu FBA", 35, 31, 2),
                                            (52, "AMZ-AROZU-FBM", "Amz Arozu\xa0FBM", 35, 31, 1)):
        s.add("s_sales_channels", id=cid, code=code, title=title, store_account_id=store, marketplace_id=mp,
              fulfill_method_id=fm, published=1)
    s.add("sem_wayfair__keyword_matchtype", id=WF_EXACT, keyword_match_type="Smart Exact")
    s.add("sem_wayfair__keyword_matchtype", id=WF_PHRASE, keyword_match_type="Smart Phrase")
    for kid, kw, mt in (("KW1", "hammock stand", WF_EXACT), ("KW2", "tranquillo hammock", WF_PHRASE)):
        s.add("sem_wayfair__keyword_info", id=f"{kid}_{mt}", keyword_id=kid, keyword_match_type_id=mt, keyword_value=kw)
    s.add("sem_wayfair__product_info", id="AAAI1001_293856", wayfair_sku="AAAI1001", product_name="Hammock Stand",
          first_10_part_numbers="HAM1, HAM2", account_id="293856")
    s.add("sem_wayfair__product_info", id="AAAI2001_184614", wayfair_sku="AAAI2001", product_name="Mesh Office Chair",
          first_10_part_numbers="CHR1", account_id="184614")
    # listing Arozu map qua bảng của team SEM; listing DHI chỉ map được qua part number
    for part, pid in (("HAM1", 101), ("HAM2", 102)):
        s.add("wayfair_map_sku_product_id", sem_wayfair_id="AAAI1001_293856", sku="AAAI1001", account_id="293856",
              original_supplier_part=part, supplier_part=part, wayfair_product_id=pid, product_id=pid)
    for i, (part, pid) in enumerate((("HAM1", 101), ("HAM2", 102), ("CHR1", 201)), 1):
        s.add("prd_wayfair_products", id=i, product_id=pid, supplier_part=part, wholesale_price=60.0)
    s.add("sem_wayfair__search_term_info", id="ST1", customer_search_term="hammock stand")
    camps = [("W1", "293856", "Arozu | Hammock | KW", "Keyword Targeting", "https://www.wayfair.com", 10.0, 1, 50.0),
             ("W2", "293856", "Arozu | Hammock | PT", "Product Targeting", "https://www.wayfair.com", 20.0, 2, 100.0),
             ("W3", "184614", "DHI | Chair | PT", "Product Targeting", "https://www.wayfair.ca", 10.0, 1, 40.0)]
    for cid, acc, name, *_ in camps:
        s.add("sem_wayfair__campaign_info", campaign_id=cid, campaign_name=name, account_id=acc, last_updated_dwh=END)
    oid = 0
    for d in days():
        for cid, acc, name, ttype, store, spend, orders, ws in camps:
            s.add("sem_wayfair__campaign_info_daily", id=f"{cid}_{ymd(d)}", campaign_id=cid, campaign_date_run=d,
                  campaign_status="ACTIVE", campaign_is_active=1, campaign_daily_cap="20",
                  campaign_lifetime_budget="NO LIFETIME BUDGET", campaign_init_date=START, campaign_end_date="NO END DATE")
            s.add("sem_wayfair__wsp_campaign", id=f"{cid}_{ymd(d)}", campaign_date_run=d, campaign_id=cid,
                  targeting_type=ttype, store_url=store, clicks=20, impressions=1000, spend=spend,
                  attr_rsales_wview_through_Day_14=ws * 1.8, attr_wholesale_cost_wview_through_Day_14=ws,
                  attr_orders_wview_through_Day_14=orders, attr_units_wview_through_Day_14=orders)
        for cid, listing, store, spend, orders, ws in (("W2", "AAAI1001_293856", "https://www.wayfair.com", 20.0, 2, 100.0),
                                                       ("W3", "AAAI2001_184614", "https://www.wayfair.ca", 10.0, 1, 40.0)):
            s.add("sem_wayfair__wsp_product", id=f"{cid}_{listing}_{ymd(d)}", campaign_id=cid, product_info_id=listing,
                  name_of_class="Hammocks", store_url=store, campaign_date_run=d, clicks=20, impressions=1000,
                  spend=spend, attr_wholesale_cost_wview_through_Day_14=ws, attr_rsales_wview_through_Day_14=ws * 1.8,
                  attr_orders_wview_through_Day_14=orders, attr_units_wview_through_Day_14=orders)
        for kinfo, spend, orders, ws in ((f"KW1_{WF_EXACT}", 6.0, 1, 50.0), (f"KW2_{WF_PHRASE}", 4.0, 0, 0.0)):
            s.add("sem_wayfair__wsp_keyword_targeting", id=f"W1_{kinfo}_AAAI1001_293856_{ymd(d)}", campaign_id="W1",
                  keyword_info_id=kinfo, store_url="https://www.wayfair.com", campaign_date_run=d, clicks=10,
                  impressions=500, spend=spend, attr_wholesale_cost_wview_through_Day_14=ws,
                  attr_rsales_wview_through_Day_14=ws * 1.8, attr_orders_wview_through_Day_14=orders,
                  name_of_class="Hammocks", wayfair_sku="AAAI1001", product_name="Hammock Stand",
                  product_info_id="AAAI1001_293856")
            s.add("sem_wayfair__keyword_info_daily", id=f"{kinfo}_{ymd(d)}", keyword_info_id=kinfo, campaign_date_run=d,
                  keyword_max_bid=0.55)
        # keyword optimization: "hammock stand" có 2 dòng (2 tổ hợp thuộc tính lọc, khác hoa/thường) -> gộp spend 5
        for seq, (kinfo, term, spend, orders, ws) in enumerate((
                (f"KW1_{WF_EXACT}", "hammock stand", 3.0, 1, 50.0), (f"KW1_{WF_EXACT}", "Hammock Stand", 2.0, 0, 0.0),
                (f"KW2_{WF_PHRASE}", "tranquillo hammock stand heavy duty", 3.0, 0, 0.0),
                (f"KW2_{WF_PHRASE}", None, 1.0, 0, 0.0)), 1):
            s.add("sem_wayfair__wsp_keyword_optimization", id=f"W1_{kinfo}_{ymd(d)}_{seq}", campaign_id="W1",
                  keyword_info_id=kinfo, store_url="https://www.wayfair.com", campaign_date_run=d, clicks=5,
                  impressions=200, spend=spend, attr_wholesale_cost_wview_through_Day_14=ws,
                  attr_rsales_wview_through_Day_14=ws * 1.8, attr_units_wview_through_Day_14=orders,
                  attr_orders_wview_through_Day_14=orders, customer_search_term=term)
        s.add("sem_wayfair__wsp_search_term_research", id=f"ST1_293856_{ymd(d)}|WAYFAIR_US",
              customer_search_term_id="ST1", brand_catalog="Wayfair US", name_of_class="Hammocks",
              total_search_term_impressions_in_the_last_30_days=5000,
              search_term_share_of_impressions_for_given_class_percent=1.5, supplier_share_of_search_percent=12.5,
              supplier_share_of_page_1_percent=8.0, supplier_share_of_top_8_percent=2.0, account_id="293856",
              report_date=d)
        for channel, otype, item, sku, qty, price, status, country in (
                (56, "dropship", "HAM1", "AAAI1001", 2, 60.0, "SHIPPED", "US"),
                (58, "castle_gate", "HAM2", "AAAI1001", 1, 60.0, "DELIVERED", "US"),
                (56, "dropship", "HAM1", "AAAI1001", 1, 60.0, "CANCELLED", "US"),
                (27, "dropship", "CHR1", "AAAI2001", 1, 100.0, "SHIPPED", "CA")):
            oid += 1
            s.add("s__wayfair_orders", id=oid, sales_channel_id=channel, po_number=f"CS{oid}", order_type=otype,
                  po_date=f"{d} 09:00:00", status=status, customer_country=country)
            s.add("s__wayfair_order_details", id=oid, order_id=oid, product_id=0, item_number=item, wayfair_sku=sku,
                  quantity=qty, wholesale_price=price, cancelled_quantity=0)


def seed_shopify(s: Seeder) -> None:
    """Shopify Megsu.com (US): mỗi ngày 1 đơn 1 x 101 giá 80, giảm 5. Khách C1 mua ngày đầu (khách mới) và ngày thứ
    hai (quay lại); các ngày khác mỗi đơn một khách mới. Ngày đầu hoàn 1 unit (75). Thêm 1 đơn voided (bị bỏ)."""
    s.add("s_sales_channels", id=44, code="SPF-MEGSU", title="Megsu.com", store_account_id=30, marketplace_id=31,
          fulfill_method_id=1, published=1)
    for i, d in enumerate(days()):
        oid = f"SO{i}"
        s.add("s__shopify_orders_v2", shopify_order_id=oid, sales_channel_id=44, customer_id="C1" if i < 2 else f"C{i}",
              created_at=f"{d} 15:00:00", total_price=80.0, subtotal_price=75.0, total_tax=0, total_discounts=5.0,
              financial_status="partially_refunded" if i == 0 else "paid", currency="USD",
              source_name="web" if i % 2 else "shopify-collective-automatic-payments")
        s.add("s__shopify_order_details_v2", line_item_id=f"L{i}", order_id=oid, product_id=101, sku="HAM1", quantity=1,
              price=80.0, total_discount=0, discount_allocations_amount=5.0)
    s.add("s__shopify_order_refund_line_items", id="R0", line_item_id="L0", order_id="SO0", refund_id="RF0", quantity=1,
          subtotal=75.0, total_tax=0)
    s.add("s__shopify_orders_v2", shopify_order_id="SOV", sales_channel_id=44, customer_id="CX", created_at=f"{START} 10:00:00",
          total_price=999.0, subtotal_price=999.0, total_tax=0, total_discounts=0, financial_status="voided", currency="USD",
          source_name="web")
    s.add("s__shopify_order_details_v2", line_item_id="LV", order_id="SOV", product_id=101, sku="HAM1", quantity=1,
          price=999.0, total_discount=0, discount_allocations_amount=0)


def seed_inventory(s: Seeder) -> None:
    """Tồn kho. Kho 58 (US, thật), 51 (CA), 55 (Direct Import, ảo - không tính). Mỗi ngày bán: 101 dropship US 2,
    CastleGate 1, FBA 3; 201 dropship CA 1; combo 150 (= 101 + 2 x 102) 1 bộ/ngày trong 20 ngày đầu, sau đó 102 hết hàng.
    Hàng về: container 200 x 101 về kho 58 (ETA END + 10), container cũ quá hạn 50 x 102, PO 500 x 101 (200 đã đóng
    container), FBA đã gửi 60 / Amazon nhận 20, CastleGate đang gửi 40."""
    s.add("s_country", id=2, code="VN", currency_code="VND")
    for wid, title, country, virtual in ((58, "US- NEO - Pico", "1", 0), (51, "Canada - BJ - Missi", "4", 0),
                                         (55, "Direct Import Warehouse US", "2", 1)):
        s.add("wh_warehouses", id=wid, title=title, code=f"W{wid}", country_id=country, company_id=0,
              is_virtual=virtual, is_managed=1, published=1)
    s.add("wh_wayfair_castlegate_warehouses", id=4, title="IL - ROMEOVILLE")
    s.add("prd_productcombo", id=1, product_id=150, child_id=101, quantity=1, published=1)
    s.add("prd_productcombo", id=2, product_id=150, child_id=102, quantity=2, published=1)
    stamp = datetime.combine(END, datetime.min.time()).replace(hour=8)
    for i, (pid, wid, qty, res) in enumerate(((101, 58, 100, 10), (102, 58, 0, 0), (201, 51, 50, 0), (101, 55, 1000, 0)), 1):
        s.add("wh_product_inventory", id=i, product_id=pid, warehouse_id=wid, quantity=qty, reserved=res, lastupdated=stamp)
        s.add("wh_product_inventory_available", id=f"{pid}_{wid}_{END:%Y_%m_%d}", product_id=pid, warehouse_id=wid,
              quantity=qty, reserved=res, inventory_available=qty - res, last_updated_dwh=stamp)
    s.add("wh_wayfair_castlegate_inventory", id=1, sales_store_account_id=37, castlegate_warehouse_id=4, product_id=101,
          part_number="HAM1", qty_on_order=40, qty_on_hand=30, qty_in_stock=30, qty_fulfillable=25, qty_unfulfillable=5,
          qty_on_transfers=0, qty_held=0, qty_unpickable=0, qty_expired=0, qty_allocated=0, qty_unreconciled=0,
          update_at=stamp, last_updated=END)
    sid = tid_ = 0
    for n, d in enumerate(days()):
        tid_ += 1
        s.add("wh_product_inventory_trace", id=f"T{tid_}", product_id=101, warehouse_id=58, quantity=100, reserved=0, the_date=d)
        s.add("wh_product_inventory_trace", id=f"V{tid_}", product_id=101, warehouse_id=55, quantity=1000, reserved=0, the_date=d)
        if n < 20:
            s.add("wh_product_inventory_trace", id=f"P{tid_}", product_id=102, warehouse_id=58, quantity=40, reserved=0, the_date=d)
        s.add("wh_wayfair_castlegate_inventory_history", id=tid_, date=d, sales_store_account_id=37, castlegate_warehouse_id=4,
              product_id=101, part_number="HAM1", on_hand_quantity=30)
        rows = [(56, 101, 2, 120.0, "USD"), (58, 101, 1, 60.0, "USD"), (53, 101, 3, 105.0, "USD"), (27, 201, 1, 100.0, "CAD")]
        if n < 20:
            rows.append((56, 150, 1, 150.0, "USD"))
        for ch, pid, qty, rev, cur in rows:
            sid += 1
            s.add("s_sales_report_data_by_orderdate", id=f"{pid}_{ch}_{ymd(d)}", report_date=d, sales_channel_id=ch,
                  product_id=pid, invoice_count=1, total_quantity=qty, revenue=rev, currency=cur)
    s.add("pu_shipments", id=1, shipment_number="HMD-TEST-01", shipment_type=1, status=2,
          estimated_time_arrival=END + timedelta(days=5))
    s.add("pu_shipment_containers", id=1, shipment_id=1, warehouse_id=58, container_number="CONT0001",
          eta_warehouse=END + timedelta(days=10), status=2)
    s.add("pu_shipment_container_details", id=1, container_id=1, product_id=101, quantity=200, received_quantity=0)
    s.add("pu_shipment_containers", id=2, shipment_id=1, warehouse_id=58, container_number="CONT_OLD",
          eta_warehouse=START - timedelta(days=100), status=1)
    s.add("pu_shipment_container_details", id=2, container_id=2, product_id=102, quantity=50, received_quantity=0)
    s.add("pu_sc_purchase_orders", id=1, order_number="PO-TEST-01", order_date=END - timedelta(days=20), status=3)
    s.add("pu_sc_purchase_order_details", id=1, purchase_order_id=1, product_id=101, quantity=500)
    s.add("sc_delivery_receipts", id=1, purchase_order_id=1, receipt_number="R1", status=1)
    s.add("sc_delivery_receipt_containers", id=1, receipt_id=1, container_id=1, product_id=101, quantity=200, received_quantity=0)
    s.add("shipment__fbashipments", id=1, sales_channel_id=53, shipment_id="FBA15TEST", warehouse_id=58,
          shipped_date=END - timedelta(days=5), status=6)
    s.add("shipment__fbashipment_details", id=1, fbashipment_id=1, product_id=101, quantityshipped=60,
          quantityactualshipped=60, quantityreceived=20)
