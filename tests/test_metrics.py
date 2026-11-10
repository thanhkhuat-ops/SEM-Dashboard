from datetime import date

from app.metrics import kpi_series


def test_kpi_series_daily_fills_missing_days():
    trend = [{"date": "2026-10-01", "spend": 10, "sales": 50, "clicks": 20, "orders": 2, "total_sales": 200},
             {"date": "2026-10-03", "spend": 5, "sales": 0, "clicks": 10, "orders": 0, "total_sales": None}]
    s = kpi_series(trend, date(2026, 10, 1), date(2026, 10, 3))
    assert s["grain"] == "day"
    assert s["labels"] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert s["values"]["spend"] == [10, 0, 5]  # ngày không có dòng = 0 chi tiêu
    assert s["values"]["acos"] == [0.2, None, None]
    assert s["values"]["tacos"] == [0.05, None, None]  # chưa có tổng DS thì để trống, không phải 0


def test_kpi_series_weekly_uses_daily_average_and_week_ratios():
    trend = [{"date": f"2026-10-{d:02d}", "spend": 10, "sales": 40, "total_sales": 100} for d in range(1, 29)]
    s = kpi_series(trend, date(2026, 6, 1), date(2026, 10, 28))
    assert s["grain"] == "week"
    assert s["labels"][0] == "2026-06-01" and s["labels"][-1] == "2026-10-26"  # thứ Hai đầu tuần
    assert s["values"]["spend"][-1] == 10  # tuần lẻ 26–28/10: trung bình mỗi ngày, không tụt
    assert s["values"]["acos"][-1] == 0.25 and s["values"]["tacos"][-1] == 0.1
