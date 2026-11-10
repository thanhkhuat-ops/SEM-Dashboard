import json

from app import table_filters
from app.metrics import METRIC_COLUMNS, col, with_ratios


def _result():
    rows = [
        with_ratios({"name": "hammock", "match_type": "EXACT", "impressions": 1000, "clicks": 20, "spend": 30.0,
                     "orders": 3, "units": 3, "sales": 150.0}),
        with_ratios({"name": "hammock stand", "match_type": "BROAD", "impressions": 500, "clicks": 16, "spend": 12.0,
                     "orders": 0, "units": 0, "sales": 0.0}),
        with_ratios({"name": "chair", "match_type": None, "impressions": 200, "clicks": 2, "spend": 1.0,
                     "orders": 1, "units": 1, "sales": 10.0}),
    ]
    from app.metrics import totals
    return {"tables": [{"key": "targets", "title": "t", "rows": rows, "totals": totals(rows),
                        "columns": [col("name", "Keyword"), col("match_type", "Match")] + METRIC_COLUMNS}]}


def test_no_spec_only_adds_facets():
    r = _result()
    table_filters.apply(r, {})
    t = r["tables"][0]
    assert len(t["rows"]) == 3 and "rows_before_filter" not in t
    assert t["facets"]["match_type"] == ["BROAD", "EXACT", ""]


def test_conditions_and_totals_recomputed():
    r = _result()
    spec = table_filters.parse(json.dumps({"targets": {"cond": [{"k": "spend", "op": "gte", "v": 10},
                                                                {"k": "orders", "op": "eq", "v": 0}]}}))
    table_filters.apply(r, spec)
    t = r["tables"][0]
    assert [x["name"] for x in t["rows"]] == ["hammock stand"]
    assert t["rows_before_filter"] == 3
    assert t["totals"]["spend"] == 12.0 and t["totals"]["acos"] is None
    assert t["filter_text"] == ["Spend ≥ $10", "Orders = 0"]


def test_pct_condition_skips_empty_ratio():
    r = _result()
    table_filters.apply(r, {"targets": {"cond": [{"k": "acos", "op": "lte", "v": 0.25}]}})
    assert [x["name"] for x in r["tables"][0]["rows"]] == ["hammock", "chair"]


def test_column_filters_list_and_contains():
    r = _result()
    table_filters.apply(r, {"targets": {"cols": {"match_type": ["EXACT", ""], "name": "HAM"}}})
    assert [x["name"] for x in r["tables"][0]["rows"]] == ["hammock"]


def test_invalid_input_ignored_and_empty_result_drops_totals():
    assert table_filters.parse("not json") == {}
    r = _result()
    table_filters.apply(r, {"targets": {"cond": [{"k": "name", "op": "gte", "v": 1}, {"k": "spend", "op": "bad", "v": 1},
                                                 {"k": "spend", "op": "gt", "v": 1000}]}})
    t = r["tables"][0]
    assert t["rows"] == [] and "totals" not in t
    assert t["filter"]["cond"] == [{"k": "spend", "op": "gt", "v": 1000.0}]
