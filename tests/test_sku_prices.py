from datetime import date

from etl.sku_prices import weighted_median, weighted_mode


def test_median_counts_units():
    # 1 unit giá 10, 3 units giá 20 -> median là 20
    assert weighted_median([(10.0, 1), (20.0, 3)]) == 20.0
    assert weighted_median([(10.0, 1), (20.0, 1)]) == 15.0


def test_median_skips_missing_usd():
    assert weighted_median([(None, 2), (12.5, 1)]) == 12.5
    assert weighted_median([(None, 2)]) is None


def test_mode_by_units_then_latest():
    d1, d2 = date(2026, 1, 1), date(2026, 2, 1)
    assert weighted_mode([(9.99, 1, d1), (9.99, 1, d1), (12.0, 3, d1)]) == 12.0
    # hòa units -> lấy giá bán gần nhất
    assert weighted_mode([(9.99, 2, d1), (12.0, 2, d2)]) == 12.0
    assert weighted_mode([(9.994, 1, d1), (9.99, 1, d1)]) == 9.99
