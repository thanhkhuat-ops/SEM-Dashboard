from datetime import date

from app.filters import Filters
from app.metrics import totals, with_ratios
from app.reports_shop import period_key, period_labels, source_label


def test_source_label():
    assert source_label("web") == "Website"
    assert source_label("shopify-collective-automatic-payments") == "Shopify Collective"
    assert source_label("3890849") == "App #3890849"
    assert source_label("TEMU") == "Temu"
    assert source_label(None) == "(không rõ)"


def test_shop_ratios():
    r = with_ratios({"orders": 4, "units": 5, "gross": 1000.0, "discount": 100.0, "sales": 900.0, "refunds": 90.0})
    assert r["aov"] == 225
    assert r["discount_rate"] == 0.1
    assert r["refund_rate"] == 0.1
    assert r["net_after_refund"] == 810
    assert r["avg_price"] == 180


def test_summary_ratios_and_totals():
    rows = [with_ratios({"total_sales": 100.0, "net_sales": 85.0, "spend": 10.0, "sales": 50.0, "prev_total": 80.0}),
            with_ratios({"total_sales": 100.0, "net_sales": 100.0, "spend": 0.0, "sales": 0.0, "prev_total": 120.0})]
    assert rows[0]["fee_pct"] == 0.15 and rows[0]["after_ads"] == 75 and rows[0]["growth"] == 0.25
    t = totals(rows, ("total_sales",))
    assert t["total_sales"] == 200 and t["net_sales"] == 185
    assert t["tacos"] == 0.05 and t["growth"] == 0
    assert abs(t["fee_pct"] - 0.075) < 1e-9


def test_period_axis():
    short = Filters(start=date(2026, 10, 1), end=date(2026, 10, 3))
    assert period_key(short) == ("l.report_date", "ngày")
    assert period_labels(short, False) == ["2026-10-01", "2026-10-02", "2026-10-03"]
    long = Filters(start=date(2026, 8, 5), end=date(2026, 10, 28))
    assert period_key(long, "x.d")[1] == "tuần"
    weeks = period_labels(long, True)
    assert weeks[0] == "2026-08-03" and weeks[-1] == "2026-10-26"  # thứ Hai


def test_ad_spend_spread_evenly(monkeypatch):
    from app import reports_shop
    rows = [{"month": date(2026, 9, 1), "sales_channel_id": 44, "cc": "US", "spend": 300.0},
            {"month": date(2026, 10, 1), "sales_channel_id": 44, "cc": "US", "spend": 310.0}]
    monkeypatch.setattr(reports_shop, "fetch_all", lambda sql, params: rows)
    daily = reports_shop.ad_spend_daily(Filters(start=date(2026, 9, 29), end=date(2026, 10, 3)))
    assert len(daily) == 5 and reports_shop.sum_spend(daily) == 2 * 10 + 3 * 10
    by_day = reports_shop.sum_spend(daily, lambda r: r["d"])
    assert by_day[date(2026, 9, 30)] == 10 and by_day[date(2026, 10, 1)] == 10
    # lọc nhóm SP: chi phí nhập theo store nên không tính
    assert reports_shop.ad_spend_daily(Filters(start=date(2026, 9, 29), end=date(2026, 10, 3), group_ids=[10])) is None
    monkeypatch.setattr(reports_shop, "fetch_all", lambda sql, params: [])
    assert reports_shop.ad_spend_daily(Filters(start=date(2026, 9, 29), end=date(2026, 10, 3))) is None


def test_shop_tacos_in_totals():
    t = totals([with_ratios({"orders": 1, "gross": 100.0, "sales": 100.0, "spend": 10.0}),
                with_ratios({"orders": 1, "gross": 100.0, "sales": 300.0, "spend": 0.0})])
    assert t["tacos"] == 10 / 400 and t["acos"] is None


def test_stock_bucket():
    from app.reports_all import stock_bucket
    assert stock_bucket(10, 0, None) == "NO_SALES"    # có tồn, không bán
    assert stock_bucket(0, 0, None) is None
    assert stock_bucket(0, 1.5, 0) == "OOS"
    assert stock_bucket(5, 1.0, 14) == "D14"
    assert stock_bucket(5, 1.0, 15) == "D30"           # hết sau 15 ngày nhờ hàng về
    assert stock_bucket(5, 1.0, 30) == "D30"
    assert stock_bucket(50, 1.0, 31) == "OK"
    assert stock_bucket(89, 1.0, 89) == "OK"
    assert stock_bucket(90, 1.0, 180) == "OVER"        # tồn nhiều theo tồn hiện có, cùng ngưỡng tab Tồn kho


def test_company_of():
    from app.reports_all import COMPANY_OTHER, company_of
    assert company_of("DH Intra") == company_of("DHI") == company_of("SPF-DHI") == company_of("EBAY-DHI") == "DH Intra"
    assert company_of("AMZ-AUS-SNN-FBA") == company_of("SPF-SENNO") == company_of("MYDEAL-AUS-SENNO") == "Senno"
    assert company_of("Infideals") == company_of("AMZ-INF-CA-FBA") == "Infideals"
    assert company_of("AMZ-MEGSU-CA-FBM") == "Megsu" and company_of("Arozu") == "Arozu"
    assert company_of("EBAY-INC") == company_of("LOCAL") == company_of(None) == COMPANY_OTHER
