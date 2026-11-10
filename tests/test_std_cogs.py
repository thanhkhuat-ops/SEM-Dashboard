import pytest

from app import insights
from etl import std_cogs

HEADER = ["SKU", "Title", "Brand", "Sell type", "Category", "Group",
          "Standard WH COGS USA (USD)", "Standard WH COGS Canada (CAD)", "Standard WH COGS Australia (AUD)",
          "Standard COGS FBA US (USD)", "Standard COGS CG US (USD)", "Standard COGS FBA CAN (CAD)",
          "Standard COGS CG CAN (CAD)", "Standard COGS FBA Senno (AUD)"]


def test_parse_skips_title_rows_blanks_and_zero():
    table = [["", "Giá vốn hàng bán (COGS)…"], [], HEADER,
             ["CVYY", "Bed", "Acacia", "Single", "Bed Frame", "G", "$204.36", "$1,263.45", "", "$237.71", "$220.21",
              "$313.48", "$307.62", ""],
             ["NTC-1-CA", "x", "NTC", "Single", "Patio", "G", "$0.00", "$0.00", "$0.00", "$0.00", "$0.00", "$0.00", "$0.00"],
             ["CVYY", "dup", "", "", "", "", "$1.00"] + [""] * 7,
             ["", "trailing"]]
    rows = std_cogs.parse(table)
    got = {(r["product_sku"], r["market"], r["basis"]): r["cogs"] for r in rows}
    assert got == {("CVYY", "US", "WH"): 204.36, ("CVYY", "CA", "WH"): 1263.45, ("CVYY", "US", "FBA"): 237.71,
                   ("CVYY", "US", "CG"): 220.21, ("CVYY", "CA", "FBA"): 313.48, ("CVYY", "CA", "CG"): 307.62}
    first = rows[0]
    assert first["brand"] == "Acacia" and first["sell_type"] == "Single" and first["currency_code"] == "USD"


def test_parse_requires_header_and_all_cost_columns():
    with pytest.raises(std_cogs.SheetError):
        std_cogs.parse([["a", "b"], ["c", "d"]])
    with pytest.raises(std_cogs.SheetError, match="Thiếu cột"):
        std_cogs.parse([HEADER[:8], ["X", "", "", "", "", "", "1", "2"]])


def test_std_cost_blends_fulfilment_and_markets():
    std = {(1, "US", "WH"): 100.0, (1, "US", "FBA"): 120.0, (1, "CA", "WH"): 80.0}
    # 25% đơn FBA: 100 × 0.75 + 120 × 0.25
    assert insights.std_cost(std, 1, "amazon", [("US", 4, 1)]) == pytest.approx(105.0)
    # CA không có cột FBA → dùng WH; gộp theo số đơn vị: (105 × 4 + 80 × 1) / 5
    assert insights.std_cost(std, 1, "amazon", [("US", 4, 1), ("CA", 1, 1)]) == pytest.approx(100.0)
    # không có đơn: coi như giao từ kho
    assert insights.std_cost(std, 1, "amazon", [("US", None, None)]) == 100.0
    # Wayfair dùng cột CG, sản phẩm chỉ có WH
    assert insights.std_cost(std, 1, "wayfair", [("US", 10, 10)]) == 100.0
    assert insights.std_cost(std, 2, "amazon", [("US", 1, 0)]) is None


def test_manual_cost_wins_and_keeps_fees_with_std():
    costs = {"manual": {1: {"landed_cost": 50.0, "amz_fee_unit": 5.0}, 2: {"landed_cost": None, "amz_fee_unit": 7.0}},
             "std": {(2, "US", "WH"): 90.0, (3, "CA", "WH"): 70.0}}
    r1, r2, r3 = {"product_id": 1}, {"product_id": 2, "country": "US"}, {"product_id": 3, "country": "CA"}
    assert insights.row_cost(r1, costs, "amazon")["landed_cost"] == 50.0 and r1["cost_source"] == "manual"
    assert insights.row_cost(r2, costs, "amazon") == {"landed_cost": 90.0, "amz_fee_unit": 7.0}
    assert r2["cost_source"] == "std"
    assert insights.row_cost(r3, costs, "wayfair")["landed_cost"] == 70.0
    r4 = {"product_id": 3}  # không có nước → US, không có giá vốn
    assert insights.row_cost(r4, costs, "amazon") is None and r4["cost_source"] is None


def test_add_profit_uses_std_cost():
    rows = [{"product_id": 2, "country": "US", "total_sales": 1000.0, "total_units": 5, "fbx_units": 0, "spend": 100.0}]
    insights.add_profit(rows, {"manual": {}, "std": {(2, "US", "WH"): 90.0}}, {"amazon": {"referral_pct": 0.15}}, "amazon")
    r = rows[0]
    assert r["landed_cost"] == 90.0
    assert r["margin_unit"] == pytest.approx(200 * 0.85 - 90)
    assert r["profit_after"] == pytest.approx((200 * 0.85 - 90) * 5 - 100)
