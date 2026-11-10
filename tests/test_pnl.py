from datetime import date

from etl.op_fee import parse
from etl.pnl import Pnl, company_of


def test_op_fee_parse_columns_and_months():
    table = [
        ["sku", "US_FBM", "US_FBA", "AUS_FBA", "month_", "year_", "US_Amazon_by Merchant", "CA_Wayfair_Dropship"],
        ["ABC", "10", "12.5", "20", "9", "2026", "11", ""],
        ["ABC", "1", "1", "1", "13", "2027", "1", "1"],  # tháng sai: bỏ
    ]
    rows = parse(table)
    got = {(r["country_code"], r["col"]): (r["fee"], r["currency_code"], r["month"]) for r in rows}
    assert got[("US", "fbm")] == (10.0, "USD", date(2026, 9, 1))
    assert got[("AU", "fba")] == (20.0, "AUD", date(2026, 9, 1))
    assert got[("US", "amazon by merchant")][0] == 11.0
    assert ("CA", "wayfair dropship") not in got  # ô trống
    assert len(rows) == 4


def test_op_cols_priority():
    assert Pnl._op_cols("amazon", "FBA", "") == ["amazon by marketplace", "fba", "fbm"]
    assert Pnl._op_cols("wayfair", "DS", "") == ["wayfair dropship", "fbm"]
    assert Pnl._op_cols("other", "FBM", "EBAY-AUS")[0] == "ebay by merchant"


def test_company_of():
    assert company_of("SPF-DHI") == company_of("DHIntra.com") == "DH Intra"
    assert company_of("Senno.com") == "Senno"
