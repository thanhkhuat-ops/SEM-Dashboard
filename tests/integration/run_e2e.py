"""Kiểm thử đầu-cuối trên MySQL Docker: seed staging -> ETL --init -> kiểm tra số liệu -> gọi mọi API/báo cáo.

  docker run -d --name ssv2-mysql-test -e MYSQL_ROOT_PASSWORD=... -p 33306:3306 mysql:8.0
  .venv/Scripts/python -m tests.integration.run_e2e
"""
import calendar
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
for line in (HERE / "test.env").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

import pymysql  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import execute, fetch_all, fetch_one  # noqa: E402
from app.main import app  # noqa: E402
from etl import run as etl_run  # noqa: E402
from tests.integration.seed_staging import END, START, seed, tid  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def close(a, b, tol=0.01) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def wait_mysql() -> None:
    for _ in range(60):
        try:
            pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                            password=settings.db_password).close()
            return
        except pymysql.MySQLError:
            time.sleep(2)
    raise SystemExit("MySQL chưa sẵn sàng")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    wait_mysql()
    counts = seed(settings.db_host, settings.db_port, settings.db_user, settings.db_password, settings.staging_schema)
    print(f"seed: {sum(counts.values())} dòng / {len(counts)} bảng")
    conn = pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                           password=settings.db_password, autocommit=True)
    conn.cursor().execute(f"DROP DATABASE IF EXISTS `{settings.mart_schema}`")
    conn.close()

    etl_run.main(["--init", "--start", START.isoformat(), "--end", END.isoformat()])
    # chạy lại lần 2 để chắc ETL idempotent (không nhân đôi số liệu)
    etl_run.main(["--start", START.isoformat(), "--end", END.isoformat()])

    stg = settings.staging_schema
    print("\nKiểm tra số liệu mart:")
    src = fetch_one(f"SELECT SUM(cost) c, SUM(sales_7d) s FROM {stg}.sem__sp_campaigns WHERE campaign_id <> 'C_SP_CA'")
    mart = fetch_one("SELECT SUM(cost_usd) c, SUM(sales_usd) s FROM fact_campaign_daily WHERE ad_type='SP' AND profile_id='PUS001'")
    check("SP US: spend & sales khớp nguồn", close(src["c"], mart["c"]) and close(src["s"], mart["s"]), f"{src} vs {mart}")

    ca = fetch_one(f"SELECT SUM(cost) c FROM {stg}.sem__sp_campaigns WHERE campaign_id = 'C_SP_CA'")
    ca_m = fetch_one("SELECT SUM(cost) c, SUM(cost_usd) u FROM fact_campaign_daily WHERE campaign_id='C_SP_CA'")
    check("SP CA: quy đổi CAD -> USD = 0.72", close(ca_m["u"], ca["c"] * 0.72), f"{ca_m}")
    fx = fetch_one("SELECT rate_usd FROM fx_daily WHERE currency_code='CAD' AND date_key='2026-09-10'")
    check("Tỷ giá ngày thiếu lấy ngày gần nhất", close(fx["rate_usd"], 0.72), str(fx))

    sb = fetch_one(f"SELECT impressions, clicks FROM fact_target_daily WHERE ad_type='SB' AND report_date='{START}'")
    check("SB keyword: bảng thường ghi đè bản ghi _video trùng khóa", sb and sb["impressions"] == 500, str(sb))
    pl = fetch_one(f"SELECT impressions FROM fact_placement_daily WHERE placement_id='1' AND report_date='{START}'")
    check("SB placement: bảng thường ghi đè _video", pl and pl["impressions"] == 300, str(pl))
    sbc = fetch_one(f"SELECT SUM(cost_usd) c FROM fact_campaign_daily WHERE ad_type='SB'")
    days_n = (END - START).days + 1
    check("SB campaign = tổng placement", close(sbc["c"], 12.0 * days_n), str(sbc))

    sd1 = fetch_one("SELECT SUM(orders) o, SUM(sales_usd) s, SUM(ntb_orders) n FROM fact_campaign_daily WHERE campaign_id='C_SD1'")
    check("SD vCPM dùng quy đổi view + click", sd1["o"] == 3 * days_n and close(sd1["s"], 90.0 * days_n), str(sd1))
    sd2 = fetch_one("SELECT SUM(orders) o, SUM(ntb_orders) n, SUM(ntb_sales_usd) ns FROM fact_campaign_daily WHERE campaign_id='C_SD2'")
    check("SD CPC: đảo lại cột NTB bị map sai", sd2["n"] == 1 * days_n and close(sd2["ns"], 25.0 * days_n), str(sd2))

    bid = fetch_one("SELECT bid FROM fact_target_daily WHERE target_id='K1' LIMIT 1")
    check("Bid SP tra từ keywords_base_daily", bid and close(bid["bid"], 1.25), str(bid))
    modes = {r["campaign_id"]: r["targeting_mode"] for r in fetch_all("SELECT campaign_id, targeting_mode FROM dim_campaign WHERE ad_type='SP'")}
    check("Auto/Manual", modes.get("C_SP_AUTO") == "AUTO" and modes.get("C_SP_MAN") == "MANUAL", str(modes))

    unmapped = fetch_one("SELECT COUNT(*) n FROM fact_product_daily WHERE product_id IS NULL")
    check("Mọi ASIN quảng cáo đều map được sản phẩm", unmapped["n"] == 0, str(unmapped))
    dom = fetch_all("SELECT adgroup_id, product_id, ROUND(weight_share, 2) s FROM map_adgroup_product WHERE adgroup_id='AG1' AND is_dominant=1")
    check("Ad group nhiều ASIN: sản phẩm chủ đạo theo spend", len(dom) == 1 and dom[0]["product_id"] == 101, str(dom))

    ts = fetch_one("SELECT SUM(sales_usd) s, SUM(units) u FROM fact_total_sales_daily WHERE store_account_id=15")
    check("Tổng doanh số: bỏ đơn Canceled", close(ts["s"], (35 + 30) * 3 * days_n), str(ts))
    ts_ca = fetch_one("SELECT SUM(sales_usd) s FROM fact_total_sales_daily WHERE store_account_id=16")
    check("Tổng doanh số CA quy USD", close(ts_ca["s"], 120 * 3 * days_n * 0.72, 0.5), str(ts_ca))

    classes = {r["term"]: r["term_class"] for r in fetch_all("SELECT term, term_class FROM dim_term")}
    expect = {"hammock": "GENERIC", "tranquillo hammock": "BRANDED", "b0zzz99999": "ASIN_COMPETITOR",
              "close-match": "AUTO", "hammock chair for bedroom": "TARGETED", 'views=(exact-product lookback=30)': "AUDIENCE",
              "ergonomic office chair with lumbar support": "TARGETED"}
    bad = {k: classes.get(k) for k, v in expect.items() if classes.get(k) != v}
    check("Phân loại từ khóa", not bad, str(bad))
    ng = fetch_one("SELECT COUNT(*) n FROM bridge_term_ngram WHERE ngram='hammock' AND n=1")
    check("N-gram được sinh", ng["n"] >= 5, str(ng))

    print("\nKiểm tra Wayfair:")
    wf = {r["country_code"]: r for r in fetch_all("""SELECT country_code, SUM(cost) c, SUM(cost_usd) u, SUM(sales_usd) s,
        SUM(retail_sales_usd) r FROM fact_wf_campaign_daily GROUP BY country_code""")}
    check("WF campaign US: spend, DS sỉ, DS lẻ", close(wf["US"]["u"], 30 * days_n) and close(wf["US"]["s"], 150 * days_n)
          and close(wf["US"]["r"], 150 * 1.8 * days_n), str(wf.get("US")))
    check("WF campaign wayfair.ca quy CAD -> USD", close(wf["CA"]["u"], 10 * 0.72 * days_n), str(wf.get("CA")))
    wts = {(r["account_id"], r["order_type"]): r["s"] for r in fetch_all(
        "SELECT account_id, order_type, SUM(sales_usd) s FROM fact_wf_total_sales_daily GROUP BY account_id, order_type")}
    check("WF tổng DS sỉ: dropship + CastleGate, bỏ PO hủy",
          close(wts.get(("293856", "dropship")), 120 * days_n) and close(wts.get(("293856", "castle_gate")), 60 * days_n)
          and close(wts.get(("184614", "dropship")), 100 * 0.72 * days_n, 0.5), str(wts))
    wbid = fetch_one("SELECT MIN(bid) lo, MAX(bid) hi, SUM(units IS NOT NULL) u FROM fact_wf_keyword_daily")
    check("WF bid tra từ keyword_info_daily", close(wbid["lo"], 0.55) and close(wbid["hi"], 0.55) and wbid["u"] == 0, str(wbid))
    wst = {r["term_id"]: r for r in fetch_all("SELECT term_id, SUM(cost_usd) c, COUNT(*) n FROM fact_wf_search_term_daily GROUP BY term_id")}
    hs = wst.get(tid("hammock stand")) or {}
    check("WF search term: gộp tổ hợp thuộc tính (không phân biệt hoa/thường)",
          close(hs.get("c"), 5 * days_n) and hs.get("n") == days_n and close((wst.get("") or {}).get("c"), days_n), str(hs))
    check("WF search term được phân loại",
          classes.get("tranquillo hammock stand heavy duty") == "BRANDED" and classes.get("hammock stand") is not None,
          str({k: classes.get(k) for k in ("tranquillo hammock stand heavy duty", "hammock stand")}))
    lst = {r["listing_id"]: r for r in fetch_all("SELECT listing_id, product_id, group_id, n_products FROM dim_wf_listing")}
    check("WF listing -> sản phẩm (map SEM / part number), đại diện = bán nhiều nhất",
          lst["AAAI1001_293856"]["product_id"] == 101 and lst["AAAI1001_293856"]["n_products"] == 2
          and lst["AAAI2001_184614"]["product_id"] == 201, str(lst))
    grp = {r["campaign_id"]: r["group_id"] for r in fetch_all("SELECT campaign_id, group_id FROM map_wf_campaign_group WHERE is_dominant=1")}
    check("WF campaign -> nhóm SP", grp == {"W1": 10, "W2": 10, "W3": 20}, str(grp))
    wcamp = {r["campaign_id"]: r for r in fetch_all("SELECT campaign_id, targeting_type, country_code, daily_cap FROM dim_wf_campaign")}
    check("WF dim campaign: targeting, store, daily cap",
          wcamp["W1"]["targeting_type"] == "Keyword Targeting" and wcamp["W3"]["country_code"] == "CA"
          and close(wcamp["W2"]["daily_cap"], 20), str(wcamp))
    sos = fetch_one("SELECT COUNT(*) n, MAX(share_search) s FROM fact_wf_share_of_search")
    check("WF share of search (% -> phân số)", sos["n"] == days_n and close(sos["s"], 0.125, 1e-6), str(sos))

    print("\nKiểm tra tồn kho:")
    stock = {(r["node_id"], r["product_id"]): r for r in fetch_all("SELECT * FROM fact_inv_stock")}
    check("POOL-US không tính kho ảo Direct Import", stock[("POOL-US", 101)]["on_hand"] == 100
          and stock[("POOL-US", 101)]["available"] == 90 and stock[("WH-55", 101)]["on_hand"] == 1000,
          str({k: v["on_hand"] for k, v in stock.items()}))
    cs = {r["product_id"]: r for r in fetch_all("""SELECT product_id, SUM(units) u, SUM(combo_units) cu, ROUND(SUM(revenue), 2) r
        FROM fact_channel_sales_daily WHERE sales_channel_id = 56 GROUP BY product_id""")}
    check("Doanh số combo tách ra sản phẩm con (số lượng, doanh thu chia theo tỷ lệ)",
          cs[102]["u"] == 40 and cs[101]["cu"] == 20 and close(cs[101]["r"], 120 * days_n + 50 * 20)
          and close(cs[102]["r"], 100 * 20) and 150 not in cs, str(cs))
    proj = {(r["node_id"], r["product_id"]): r for r in fetch_all("SELECT * FROM inv_projection")}
    p101, p102 = proj[("POOL-US", 101)], proj[("POOL-US", 102)]
    check("Tốc độ bán POOL-US: 0.25·r7 + 0.5·r30 + 0.25·r90, chỉ tính ngày còn hàng",
          close(p101["velocity"], 2.1, 1e-3) and p101["status"] == "OK" and p101["incoming_qty"] == 200
          # 102: r90 = 40 unit / max(20 ngày còn hàng, 90/4) -> 0.25 x 40 / 22.5
          and close(p102["velocity"], 0.25 * 40 / 22.5, 1e-3) and p102["status"] == "OOS", str((p101, p102)))
    check("Container quá ETA lâu không tính vào hàng về", p102["incoming_qty"] == 0, str(p102))
    cg, all_us, fba = proj[("CG-37", 101)], proj[("ALL-US", 101)], proj[("FBA-53", 101)]
    check("CastleGate: tồn bán được, đang gửi lên, trạng thái",
          cg["available"] == 25 and cg["incoming_qty"] == 40 and close(cg["velocity"], 1) and cg["status"] == "LOW", str(cg))
    check("Cả nước = nội bộ + CastleGate (chưa gồm FBA)",
          all_us["available"] == 115 and close(all_us["velocity"], 3.1, 1e-3), str(all_us))
    check("FBA: chưa có tồn, vẫn có doanh số và hàng đang gửi",
          fba["status"] == "NO_DATA" and fba["units_30"] == 90 and fba["incoming_qty"] == 40, str(fba))
    # kho CA không có lịch sử tồn -> tính đủ số ngày của cửa sổ; seed chỉ có 50 ngày doanh số nên r90 = 50 / 90
    check("Cả nước CA", close(proj[("ALL-CA", 201)]["velocity"], 0.75 + 0.25 * 50 / 90, 1e-3)
          and proj[("ALL-CA", 201)]["status"] == "OK",
          str(proj.get(("ALL-CA", 201))))
    po = fetch_one("SELECT SUM(qty) q FROM fact_inv_incoming WHERE source='PO'")
    check("PO còn mở = đặt − đã đóng container", po["q"] == 300, str(po))
    ch = fetch_one("SELECT title, node_id FROM map_channel_node WHERE sales_channel_id = 52")
    check("Kênh FBM -> POOL, bỏ ký tự NBSP trong tên", ch == {"title": "Amz Arozu FBM", "node_id": "POOL-US"}, str(ch))

    dup = fetch_one("SELECT COUNT(*) n FROM etl_run_log WHERE status='FAILED'")
    check("Không có bước ETL lỗi", dup["n"] == 0, str(dup))

    print("\nKiểm tra API:")
    client = TestClient(app)
    q = f"start={START}&end={END}"
    check("GET /", client.get("/").status_code == 200)
    meta = client.get("/api/meta").json()
    check("/api/meta", len(meta["accounts"]) == 2 and meta["freshness"]["campaign"] == END.isoformat(), str(meta["freshness"]))
    reports = {
        "overview": "", "campaigns": "", "campaigns#ag": "&level=adgroup", "targets": "", "search_terms": "",
        "search_terms#t": "&level=target", "keyword_analysis": "", "keyword_analysis#kw": "&source=keyword",
        "ngrams": "&n=2&min_clicks=1", "harvest": "", "products": "", "products#asin": "&level=asin",
        "products#group": "&level=group", "halo": "", "placements": "", "budget": "",
        "campaigns#filtered": "&ad_type=SP&profile_id=PUS001&group_id=10&campaign_q=HAM",
        "targets#kwfilter": "&term_class=GENERIC&length_bucket=1&match_type=EXACT",
        "all_overview": "", "all_overview#mkt": "&market=US&group_id=10", "all_overview#ch": "&sales_channel=amazon",
        "shop_overview": "",
        "shop_products": "", "shop_products#group": "&level=group",
        "wf_overview": "", "wf_campaigns": "", "wf_products": "", "wf_products#group": "&level=group",
        "wf_keywords": "", "wf_keywords#listing": "&level=listing", "wf_search_terms": "",
        "wf_search_terms#kw": "&level=keyword", "wf_keyword_analysis": "", "wf_keyword_analysis#kw": "&source=keyword",
        "wf_ngrams": "&n=2&min_clicks=1", "wf_harvest": "&min_orders=1&neg_clicks=5", "wf_share_of_search": "",
        "wf_budget": "",
        "wf_campaigns#filtered": "&wf_account=293856-US&group_id=10&campaign_q=Hammock",
        "wf_search_terms#kwfilter": "&match_type=SMART%20EXACT&term_class=GENERIC",
        "inv_overview": "", "inv_products": "&node=ALL&status=", "inv_products#cg": "&node=CG&country=US&status=LOW",
        "inv_products#fba": "&node=FBA&status=", "inv_channel_sales": "", "inv_channel_sales#ca": "&country=CA",
        "inv_incoming": "", "inv_incoming#po": "&source=PO", "inv_castlegate": "", "inv_overview#group": "&group_id=10",
    }
    results = {}
    for key, extra in reports.items():
        name = key.split("#")[0]
        r = client.get(f"/api/report/{name}?{q}{extra}")
        # wf_harvest: search term có đơn duy nhất đã là Smart Exact nên bảng "nên thêm" rỗng, kiểm bảng phủ định
        first = slice(1, 2) if name == "wf_harvest" else slice(0, 1)
        ok = r.status_code == 200 and all(t["rows"] for t in r.json()["tables"][first])
        check(f"/api/report/{key}", ok, f"HTTP {r.status_code} {r.text[:200] if r.status_code != 200 else ''}")
        if r.status_code == 200:
            results[key] = r.json()

    sov = (results.get("shop_overview") or {}).get("kpis", {}).get("current", {})
    n_days = (END - START).days + 1
    check("Shopify: bỏ đơn voided, doanh số = (80 - 5) x số ngày, hoàn 75, khách C1 quay lại 1 lần",
          sov.get("orders") == n_days and abs((sov.get("sales") or 0) - 75 * n_days) < 0.01
          and abs((sov.get("refunds") or 0) - 75) < 0.01
          and abs((sov.get("new_share") or 0) - (n_days - 1) / n_days) < 1e-9, str(sov))
    aov_ = (results.get("all_overview") or {}).get("kpis", {}).get("current", {})
    check("Tổng hợp: Shopify vào tổng doanh số, phí sàn 3%",
          abs((aov_.get("shopify") or 0) - 75 * n_days) < 0.01
          and abs(aov_.get("total_sales", 0) - aov_.get("amazon", 0) - aov_.get("wayfair", 0) - aov_.get("shopify", 0)
                  - aov_.get("other", 0)) < 0.01, str({k: aov_.get(k) for k in ("total_sales", "amazon", "wayfair", "shopify", "other")}))
    full_t = {t["key"]: t for t in (results.get("all_overview") or {}).get("tables", [])}
    co_rows = (full_t.get("by_company") or {}).get("rows", [])
    check("Tổng hợp: doanh số theo công ty cộng lại bằng tổng",
          co_rows and abs(sum(r["total_sales"] for r in co_rows) - aov_.get("total_sales", 0)) < 0.01,
          str([(r["company"], r["total_sales"]) for r in co_rows]))
    keys = [v["key"] for v in (results.get("all_overview") or {}).get("viz", [])]
    check("Tổng hợp: 5 đồ thị chính đúng thứ tự",
          keys[:5] == ["sales_by_market", "sales_by_channel", "sales_by_company", "spend_by_market", "stock_forecast"],
          str(keys))
    ach = (results.get("all_overview#ch") or {}).get("kpis", {}).get("current", {})
    check("Tổng hợp: lọc kênh Amazon chỉ còn doanh số Amazon",
          abs(ach.get("total_sales", 0) - aov_.get("amazon", 0)) < 0.01 and not ach.get("wayfair") and not ach.get("shopify"),
          str({k: ach.get(k) for k in ("total_sales", "amazon", "wayfair", "shopify")}))
    full = results.get("all_overview") or {}
    inv_t = {t["key"]: t for t in full.get("tables", [])}
    cards = {c["label"]: c["value"] for c in full.get("cards", [])}
    check("Tổng hợp: có tồn kho và dự báo hết hàng 14 / 30 ngày",
          "inv_country" in inv_t and "stock_risk" in inv_t and "SKU hết trong 14 ngày" in cards
          and cards.get("SKU hết trong 30 ngày", -1) >= cards.get("SKU hết trong 14 ngày", 0)
          and all(r["bucket"] in ("OOS", "D14", "D30") for r in inv_t["stock_risk"]["rows"]),
          str(cards))
    # chi phí QC Shopify nhập tay: mỗi tháng = số ngày × $10 → $10/ngày sau khi chia đều
    months, d = [], START.replace(day=1)
    while d <= END:
        months.append(d)
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    for m in months:
        days_in = calendar.monthrange(m.year, m.month)[1]
        client.put(f"/api/shop/ad-spend?month={m:%Y-%m}",
                   json={"rows": [{"sales_channel_id": 44, "platform": "google", "spend_usd": days_in * 6.0},
                                  {"sales_channel_id": 44, "platform": "meta", "spend_usd": days_in * 4.0}]})
    form = client.get(f"/api/shop/ad-spend?month={START:%Y-%m}").json()
    check("Chi phí QC Shopify: lưu và đọc lại theo store × nền tảng",
          any(st["sales_channel_id"] == 44 and st["google"] and st["meta"] for st in form["stores"]), str(form["stores"]))
    check("Chi phí QC Shopify: từ chối kênh không phải Shopify",
          client.put(f"/api/shop/ad-spend?month={START:%Y-%m}",
                     json={"rows": [{"sales_channel_id": 1, "platform": "google", "spend_usd": 1}]}).status_code == 422)
    sov2 = client.get(f"/api/report/shop_overview?{q}").json()["kpis"]["current"]
    aov2 = client.get(f"/api/report/all_overview?{q}").json()["kpis"]["current"]
    check("Shopify: chi phí QC chia đều theo ngày, TACoS = chi phí ÷ doanh số",
          abs((sov2.get("spend") or 0) - 10 * n_days) < 0.01
          and abs((sov2.get("tacos") or 0) - 10 / 75) < 1e-9, str({k: sov2.get(k) for k in ("spend", "tacos")}))
    check("Tổng hợp: Spend QC cộng thêm chi phí Shopify",
          abs(aov2.get("spend", 0) - aov_.get("spend", 0) - 10 * n_days) < 0.01, f"{aov2.get('spend')} vs {aov_.get('spend')}")
    sg = client.get(f"/api/report/shop_overview?{q}&group_id=10").json()["kpis"]["current"]
    check("Shopify: lọc nhóm SP thì không tính chi phí QC", sg.get("spend") is None, str(sg.get("spend")))
    for m in months:
        client.put(f"/api/shop/ad-spend?month={m:%Y-%m}",
                   json={"rows": [{"sales_channel_id": 44, "platform": k, "spend_usd": None} for k in ("google", "meta")]})
    wov = (results.get("wf_overview") or {}).get("kpis", {}).get("current", {})
    check("WF tổng quan: TACoS = spend / tổng DS sỉ (USD)",
          close(wov.get("tacos"), (30 + 7.2) / (180 + 72), 1e-4) and close(wov.get("roas"), (150 + 40 * 0.72) / 37.2, 1e-4),
          str({k: wov.get(k) for k in ("spend", "sales", "total_sales", "tacos", "roas")}))
    wfc = results.get("wf_campaigns#filtered", {}).get("tables", [{}])[0].get("rows", [])
    check("WF lọc tài khoản + nhóm SP + tên campaign",
          sorted(r["campaign_name"] for r in wfc) == ["Arozu | Hammock | KW", "Arozu | Hammock | PT"],
          str([r.get("campaign_name") for r in wfc]))
    wfh = results.get("wf_harvest", {}).get("tables", [{}])[0].get("rows", [])
    check("WF thêm từ khóa: search term có đơn nhưng đã là Smart Exact thì không gợi ý",
          all(r["term"] != "hammock stand" for r in wfh), str([r.get("term") for r in wfh]))
    viz = {k: [v["key"] for v in r.get("viz", [])] for k, r in results.items() if r.get("viz")}
    check("Đồ thị: mỗi tab tồn kho có 1-2 đồ thị",
          all(1 <= len(viz.get(k, [])) <= 2 for k in ("inv_overview", "inv_products", "inv_channel_sales", "inv_incoming",
                                                        "inv_castlegate")), str(viz))
    # tổng quan QC: luôn có 3 đồ thị theo ngày; các đồ thị phân tích (app/insights.py) chỉ hiện khi đủ dữ liệu
    check("Đồ thị: tổng quan QC có doanh số QC + tự nhiên, Spend / Sales, ACoS / TACoS",
          all(viz.get(k, [])[:3] == ["organic", "trend_money", "trend_ratio"] for k in ("overview", "wf_overview")), str(viz))
    gantt = next(v for v in results["inv_products"]["viz"] if v["kind"] == "gantt")
    g102 = next((r for r in gantt["rows"] if r["product_id"] == 102 and r["node_id"] == "ALL-US"), None)  # tab đang chọn nút Cả nước
    check("Lịch đứt hàng: SKU hết hàng có doanh số mất > 0, đứt từ hôm nay",
          g102 is not None and g102["stock_days"] == 0 and g102["lost_sales"] > 0, str(g102))
    health = results["inv_overview"]["viz"][0]
    oos = next(s_ for s_ in health["series"] if s_["filter"]["opts"]["status"] == "OOS")
    check("Đồ thị sức khỏe: bấm -> sang tab dự kiến hết hàng", health["goto"]["tab"] == "inv_products"
          and sum(oos["values"]) == fetch_one("SELECT COUNT(*) n FROM inv_projection WHERE node_id LIKE 'ALL-%' AND status='OOS'")["n"],
          str(oos))
    r = client.get("/api/inv/series", params={"node_id": "POOL-US", "product_id": 101})
    ser = r.json() if r.status_code == 200 else {}
    arrived = sum(p_["arrived"] for p_ in ser.get("projection", []))
    check("Đường tồn SKU: 60 ngày lịch sử + 120 ngày dự kiến, có lô container 200",
          len(ser.get("history", [])) == 60 and len(ser.get("projection", [])) == 120 and arrived == 200
          and ser["history"][-1]["on_hand"] == 100, str({k: ser.get(k) for k in ("available", "velocity", "events")}))
    rc = client.get(f"/api/report/inv_products?{q}&node=POOL&country=US&status=&qty_unit=cont").json()
    p101c = next(r_ for r_ in rc["tables"][0]["rows"] if r_["product_sku"] == "AX01")
    avail_col = next(c_ for c_ in rc["tables"][0]["columns"] if c_["key"] == "available")
    check("Đơn vị container: số lượng x thể tích / 68 CBM, cột hiển thị số lẻ",
          rc["qty_unit"] == "cont" and close(p101c["available"], 90 * 0.2 / 68, 1e-6)
          and close(p101c["velocity"], 2.1 * 0.2 / 68, 1e-6) and avail_col["fmt"] == "num2", str(p101c.get("available")))
    oc = client.get(f"/api/report/inv_overview?{q}&qty_unit=cont").json()
    card = next(c_ for c_ in oc["cards"] if c_.get("qty") and "Tồn khả dụng" in c_["label"])
    check("Đơn vị container: thẻ tổng quan", close(card["value"], (115 * 0.2 + 50 * 0.34 + 0 * 0.1) / 68, 1e-6), str(card))
    sc = client.get("/api/inv/series", params={"node_id": "POOL-US", "product_id": 101, "qty_unit": "cont"}).json()
    check("Đơn vị container: đường tồn SKU", close(sc["available"], 90 * 0.2 / 68, 1e-6)
          and close(sum(p_["arrived"] for p_ in sc["projection"]), 200 * 0.2 / 68, 1e-6), str(sc.get("available")))
    check("Đường tồn SKU không có dự báo -> 404",
          client.get("/api/inv/series", params={"node_id": "POOL-US", "product_id": 999}).status_code == 404)
    ov = results.get("overview", {})
    if ov:
        cur = ov["kpis"]["current"]
        total_spend = fetch_one("SELECT SUM(cost_usd) c FROM fact_campaign_daily")["c"]
        check("Overview: spend = tổng mart", close(cur["spend"], total_spend), f"{cur['spend']} vs {total_spend}")
        check("Overview: có TACoS", cur.get("tacos") is not None and 0 < cur["tacos"] < 1, str(cur.get("tacos")))
    fl = results.get("campaigns#filtered", {})
    if fl:
        names = {r["campaign_name"] for r in fl["tables"][0]["rows"]}
        check("Lọc theo loại/tài khoản/nhóm/tên", names == {"HAM_SP_Auto", "HAM_SP_Manual_Exact"}, str(names))
    kf = results.get("targets#kwfilter", {})
    if kf:
        check("Lọc phân nhóm + số từ + match", [r["targeting"] for r in kf["tables"][0]["rows"]] == ["hammock"],
              str([r["targeting"] for r in kf["tables"][0]["rows"]]))
    hv = results.get("harvest", {})
    if hv:
        neg = {r["term"] for r in hv["tables"][1]["rows"]}
        check("Gợi ý phủ định chứa search term không ra đơn", "vivere hammock stand" in neg, str(neg))

    tf = json.dumps({"targets": {"cond": [{"k": "clicks", "op": "gte", "v": 1}], "cols": {"match_type": ["EXACT"]}}})
    r = client.get(f"/api/report/targets?{q}", params={"tf": tf})
    t = r.json()["tables"][0] if r.status_code == 200 else {}
    check("Lọc trong bảng (tf): chỉ còn EXACT, có số dòng trước lọc",
          t.get("rows") and {x["match_type"] for x in t["rows"]} == {"EXACT"} and t.get("rows_before_filter", 0) > len(t["rows"]),
          str({k: t.get(k) for k in ("rows_before_filter", "filter_text")}))

    print("\nKiểm tra PIC / gửi tin (không gửi thật):")
    pics = {r["group_id"]: r["user_id"] for r in fetch_all("SELECT group_id, user_id FROM map_group_pic")}
    check("PIC theo phiên bản phân công mới nhất + sản phẩm giao trực tiếp", pics == {10: 501, 20: 502}, str(pics))
    plist = client.get("/api/notify/pics").json()
    check("/api/notify/pics: chỉ user (không có phòng ban), không lộ URL webhook",
          {p["user_id"] for p in plist} == {501, 502} and all("webhook_url" not in p for p in plist), str(plist))
    bad = client.put("/api/notify/pics/501", json={"webhook_url": "https://example.com/hook", "enabled": True})
    check("Từ chối webhook không phải Google Chat", bad.status_code == 422, bad.text)
    good = client.put("/api/notify/pics/501", json={"webhook_url": "https://chat.googleapis.com/v1/spaces/AAAAtest/messages?key=k&token=t",
                                                   "enabled": False, "acos_target": 0.25})
    check("Lưu webhook hợp lệ", good.status_code == 200 and good.json()["space"] == "AAAAtest", good.text)
    pv = client.get("/api/notify/preview/501")
    check("Xem trước tin nhắn cho PIC", pv.status_code == 200 and "PIC Hammock" in pv.json()["text"]
          and "Tổng quan" in pv.json()["text"], pv.text[:300])
    execute("DELETE FROM cfg_pic_notify")

    r = client.get(f"/export/overview?{q}")
    check("Xuất HTML", r.status_code == 200 and "attachment" in r.headers.get("content-disposition", "")
          and "Tổng quan" in r.text, r.headers.get("content-disposition", ""))
    (HERE / "export_overview_sample.html").write_text(r.text, encoding="utf-8")
    r = client.get(f"/export/keyword_analysis?{q}")
    check("Xuất HTML phân tích từ khóa", r.status_code == 200 and "Theo độ dài" in r.text)
    for rep in ("overview", "all_overview", "inv_products"):
        r = client.get(f"/export/{rep}?{q}")
        check(f"Xuất HTML {rep}: có đồ thị như trên app", r.status_code == 200 and "window.renderExportViz(" in r.text
              and '"kind": "' in r.text and (rep != "inv_products" or '"history": [' in r.text),
              f"HTTP {r.status_code}")

    r = client.post("/api/dict/brand", json={"term": "Vivere", "extra": "COMPETITOR"})
    check("Thêm brand đối thủ", r.status_code == 200, r.text)
    check("Từ chối loại brand sai", client.post("/api/dict/brand", json={"term": "x", "extra": "BAD"}).status_code == 422)
    client.post("/api/dict/reclassify/run")
    for _ in range(30):
        st = client.get("/api/dict/reclassify/status").json()
        if not st["running"]:
            break
        time.sleep(1)
    cls = fetch_one("SELECT term_class FROM dim_term WHERE term='vivere hammock stand'")
    check("Phân loại lại sau khi thêm brand đối thủ", cls and cls["term_class"] == "COMPETITOR", f"{cls} {st}")
    items = client.get("/api/dict/brand").json()
    vid = next(i["id"] for i in items if i["term"] == "vivere")
    check("Xóa mục từ điển", client.delete(f"/api/dict/brand/{vid}").json()["deleted"] == 1)

    print(f"\n{'TẤT CẢ ĐẠT' if not FAILS else str(len(FAILS)) + ' LỖI: ' + ', '.join(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
