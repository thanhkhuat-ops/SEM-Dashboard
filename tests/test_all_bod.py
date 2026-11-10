"""Tổng hợp: kỳ so sánh, kế hoạch và lãi gộp (báo cáo BOD)."""
from datetime import date

from app.filters import Filters
from app.metrics import totals, with_ratios
from app.reports_all import _plan_ratios, compare_period, plan_totals, shift_months


def test_shift_months_clamps_day():
    assert shift_months(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert shift_months(date(2026, 1, 15), 1) == date(2025, 12, 15)
    assert shift_months(date(2026, 11, 7), 12) == date(2025, 11, 7)


def test_compare_period_modes():
    f = Filters(start=date(2026, 11, 1), end=date(2026, 11, 7))
    prev, label = compare_period(f, "month")
    assert (prev.start, prev.end) == (date(2026, 10, 1), date(2026, 10, 7))
    assert label == "cùng kỳ tháng trước (01/10–07/10)"
    prev, label = compare_period(f, None)
    assert (prev.start, prev.end) == (date(2026, 10, 25), date(2026, 10, 31))
    assert label.startswith("kỳ liền trước")
    prev, _ = compare_period(f, "year")
    assert prev.start == date(2025, 11, 1)
    assert f.start == date(2026, 11, 1)  # không sửa bộ lọc gốc


def test_plan_estimate_and_totals():
    a = {"fc_period": 100.0, "actual": 50.0, "fc_month": 400.0, "fc_rest": 300.0}
    b = {"fc_period": 0.0, "actual": 0.0, "fc_month": 60.0, "fc_rest": 60.0, "no_data": True}
    for r in (a, b):
        _plan_ratios(r, True)
    assert a["attain"] == 0.5 and a["est_month"] == 200.0 and a["est_gap"] == -200.0
    assert b["est_month"] is None and b["gap"] is None  # kênh chưa có dữ liệu: không đoán
    tot = plan_totals([a, b], True)
    assert tot["est_month"] == 200.0 and tot["fc_month"] == 460.0
    assert abs(tot["est_attain"] - 200 / 460) < 1e-9
    assert plan_totals([a], False)["est_month"] is None  # không bắt đầu từ ngày 1: không ước cả tháng


def test_profit_ratios_and_totals():
    rows = [with_ratios({"total_sales": 100.0, "net_sales": 88.0, "spend": 10.0, "cogs": 50.0, "costed_sales": 100.0,
                         "gross_profit": 38.0}),
            with_ratios({"total_sales": 100.0, "net_sales": 97.0, "spend": None, "cogs": 40.0, "costed_sales": 50.0,
                         "gross_profit": 57.0})]
    assert rows[0]["gross_margin"] == 0.38 and rows[0]["profit_after_ads"] == 28.0
    assert rows[1]["profit_after_ads"] == 57.0  # chưa có chi phí QC: lãi sau QC = lãi gộp
    t = totals(rows, ("total_sales", "cogs", "costed_sales", "gross_profit"))
    assert t["gross_profit"] == 95.0 and t["cogs_cover"] == 0.75 and t["profit_after_ads"] == 85.0
