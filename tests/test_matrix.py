from datetime import date

from app import matrix
from app.filters import Filters


def f(start, end):
    return Filters(start=date.fromisoformat(start), end=date.fromisoformat(end))


def test_bucket_labels_week_and_month():
    assert matrix.bucket_labels(f("2026-08-06", "2026-08-20"), "week") == [
        date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17)]
    assert matrix.bucket_labels(f("2026-08-15", "2026-11-03"), "month") == [
        date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)]


def test_pick_gran_auto():
    assert matrix.pick_gran(f("2026-10-01", "2026-10-31"), None) == "day"
    assert matrix.pick_gran(f("2026-01-01", "2026-10-31"), None) == "week"
    assert matrix.pick_gran(f("2025-01-01", "2026-10-31"), "") == "month"
    assert matrix.pick_gran(f("2026-10-01", "2026-10-31"), "month") == "month"


def test_eval_ratio_and_diff():
    sums = {("a", "spend"): 30.0, ("a", "sales"): 100.0, ("t", "total"): 80.0}
    has = {"a": True, "t": True}
    assert matrix._eval(matrix.ratio(("a", "spend"), ("a", "sales")), sums, has) == 0.3
    # tự nhiên âm: vẽ 0, nhưng tổng chú giải giữ phần âm
    assert matrix._eval(matrix.diff(("t", "total"), ("a", "sales")), sums, has) == 0.0
    assert matrix._eval(matrix.diff(("t", "total"), ("a", "sales")), sums, has, clamp=False) == -20.0
    # nguồn không có dòng nào trong kỳ: để trống, không vẽ 0
    assert matrix._eval(matrix.col("t", "total"), sums, {"a": True}) is None
    assert matrix._eval(matrix.ratio(("a", "spend"), ("t", "total")), sums, {"a": True}) is None


def test_catalog_ids_unique_and_presets_valid():
    ids = [m["id"] for m in matrix.METRICS]
    assert len(ids) == len(set(ids))
    for m in matrix.METRICS:
        assert m["unit"] in ("money", "pct", "int")
        assert all(src in matrix.SOURCES for src, _ in matrix._refs(m["formula"]))
    assert all(0 <= i < len(matrix.PRESETS) for i in matrix.DEFAULT)
    for name, ms, mode, _ in matrix.PRESETS:
        assert mode in ("value", "index", "change")
        assert 0 < len(ms) <= matrix.MAX_METRICS
        assert all(i in matrix.BY_ID and style in ("bar", "line") for i, style in ms), name
        if mode == "value":  # mỗi trục một đơn vị
            assert len({matrix.BY_ID[i]["unit"] for i, _ in ms}) <= 2, name
    cat = matrix.catalog()
    assert "formula" not in cat["metrics"][0] and len(cat["presets"]) == len(matrix.PRESETS)


def test_build_series_and_totals(monkeypatch):
    from datetime import date
    days = [date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 12)]
    monkeypatch.setitem(matrix.SOURCES, "amz_ads", lambda f: [
        {"d": days[0], "spend": 10, "sales": 40, "clicks": 5, "impressions": 100, "orders": 1, "units": 1,
         "ntb_orders": 0},
        {"d": days[1], "spend": 20, "sales": 60, "clicks": 5, "impressions": 100, "orders": 1, "units": 1,
         "ntb_orders": 0},
        {"d": days[2], "spend": 30, "sales": 0, "clicks": 0, "impressions": 0, "orders": 0, "units": 0,
         "ntb_orders": 0}])
    monkeypatch.setitem(matrix.SOURCES, "amz_total", lambda f: [
        {"d": days[0], "total_sales": 50, "total_units": 1, "order_items": 1, "fba_order_items": 1},
        {"d": days[2], "total_sales": 20, "total_units": 1, "order_items": 1, "fba_order_items": 0}])
    f = Filters(start=date(2026, 10, 5), end=date(2026, 10, 18))
    out = matrix.build(f, ["amz_spend", "amz_acos", "amz_organic", "nope", "amz_spend"], "week")
    by = {m["id"]: m for m in out["metrics"]}
    assert list(by) == ["amz_spend", "amz_acos", "amz_organic"]
    assert out["labels"] == ["2026-10-05", "2026-10-12"] and not out["partial"]
    assert by["amz_spend"]["values"] == [30.0, 30.0] and by["amz_spend"]["total"] == 60.0
    assert by["amz_acos"]["values"] == [0.3, None] and by["amz_acos"]["total"] == 0.6
    # tuần 1: 50 − 100 → vẽ 0, tuần 2: 20 − 0; tổng giữ phần âm
    assert by["amz_organic"]["values"] == [0.0, 20.0] and by["amz_organic"]["total"] == -30.0
