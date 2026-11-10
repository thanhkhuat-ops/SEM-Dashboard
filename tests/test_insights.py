from datetime import date

from app import insights


def test_sales_bridge_steps_sum_to_change():
    prev = {"clicks": 1000, "orders": 50, "sales": 5000}
    cur = {"clicks": 1200, "orders": 48, "sales": 5280}
    steps = insights.sales_bridge(cur, prev)
    assert [s[0] for s in steps] == ["Clicks", "CVR", "Giá trị đơn (AOV)"]
    assert abs(sum(d for _, d in steps) - (5280 - 5000)) < 1e-6
    assert steps[0][1] == 200 * 0.05 * 100  # click tăng, CVR và AOV giữ như kỳ trước


def test_bridge_needs_clicks_and_orders_in_both_periods():
    assert insights.sales_bridge({"clicks": 10, "orders": 1, "sales": 5}, {"clicks": 10, "orders": 0, "sales": 0}) is None
    assert insights.spend_bridge({"clicks": 0, "spend": 0}, {"clicks": 5, "spend": 3}) is None
    steps = insights.spend_bridge({"clicks": 120, "spend": 60}, {"clicks": 100, "spend": 40})
    assert abs(sum(d for _, d in steps) - 20) < 1e-9


def test_waterfall_floating_bars_and_colors():
    ch = insights.waterfall("w", "t", 100, [("A", 30), ("B", -50)], 80, +1, "s")
    s = ch["series"][0]
    assert ch["labels"] == ["Kỳ trước", "A", "B", "Kỳ này"]
    assert s["values"] == [[0, 100], [100, 130], [130, 80], [0, 80]]
    assert s["colors"] == ["n1", "c1", "c2", "n1"]
    assert s["raw"] == [100, 30, -50, 80]
    # tăng chi là xấu: cùng bước +30 thành màu "xấu"
    assert insights.waterfall("w", "t", 100, [("A", 30)], 130, -1, "s")["series"][0]["colors"][1] == "c2"


def test_movers_top_up_and_down():
    rows = [{"label": f"P{i}", "filter_value": f"P{i}", "sales": i * 10, "sales0": 50} for i in range(11)]
    ch = insights.movers_chart(rows, "Ad Sales", {"goto": {"tab": "products"}, "opts": {}, "col": "product_sku"}, n=2)
    assert ch["labels"] == ["P10", "P9", "P1", "P0"]
    assert ch["series"][0]["values"] == [50, 40, -40, -50]
    assert ch["label_filters"][0]["cols"] == {"product_sku": ["P10"]}
    assert insights.movers_chart([{"label": "x", "filter_value": "x", "sales": 5, "sales0": 5}], "S", {
        "goto": {}, "opts": {}, "col": "c"}) is None


def test_stock_risk_counts_lost_sales_once_per_product():
    rows = [{"product_id": 1, "country": "US", "label": "A", "spend": 10},
            {"product_id": 1, "country": "US", "label": "A2", "spend": 5},
            {"product_id": 2, "country": "US", "label": "B", "spend": 7},
            {"product_id": 3, "country": "US", "label": "C", "spend": 0}]
    status = {(1, "US"): {"status": "OOS", "lost_sales_90": 100},
              (2, "US"): {"status": "OK", "lost_sales_90": 0},
              (3, "US"): {"status": "CRITICAL", "lost_sales_90": 40}}
    ch, spend, lost, risky = insights.stock_risk(rows, status)
    assert spend == 15 and lost == 100
    assert [r["label"] for r in risky] == ["A", "A2"]
    assert ch["series"][0]["colors"] == ["st:OOS", "st:OOS"]


def test_budget_summary_only_good_acos_campaigns_in_chart():
    rows = [{"campaign_name": "good", "days": 10, "days_capped": 5, "spend": 50, "sales": 500, "acos": 0.1},
            {"campaign_name": "bad", "days": 10, "days_capped": 9, "spend": 90, "sales": 100, "acos": 0.9},
            {"campaign_name": "rare", "days": 10, "days_capped": 1, "spend": 10, "sales": 100, "acos": 0.1},
            {"campaign_name": "idle", "days": 10, "days_capped": 0, "spend": 0, "sales": 0, "acos": None}]
    ch, capped, active = insights.budget_summary(rows, "budget")
    assert (capped, active) == (2, 3)
    assert ch["labels"] == ["good"] and ch["goto"]["tab"] == "budget"


def test_forecast_card_and_short_labels():
    card = insights.forecast_card(2700, date(2026, 10, 27))
    assert round(card["value"]) == 3100 and "27 ngày" in card["note"]
    assert insights.forecast_card(3100, date(2026, 10, 31))["label"].startswith("Spend cả tháng")
    assert insights.short("x" * 10) == "x" * 10
    long = "Thu Ngo | Aurora | Queen - Walnut | SP | Single - TDS - SP - Default Manual - hwtv0ipc"
    assert len(insights.short(long)) == 44 and insights.short(long).endswith("ual - hwtv0ipc")


def test_unit_margin_uses_channel_defaults_and_overrides():
    chan = {"referral_pct": 0.15, "return_pct": 0.02}
    cost = {"landed_cost": 100, "amz_fee_unit": 40, "amz_referral_pct": None, "return_pct": None}
    assert abs(insights.unit_margin(300, cost, chan, "amazon") - (300 * 0.83 - 140)) < 1e-9
    cost2 = {**cost, "amz_referral_pct": 0.10, "return_pct": 0}
    assert abs(insights.unit_margin(300, cost2, chan, "amazon") - (270 - 140)) < 1e-9
    # Wayfair không dùng phí sàn ghi đè của Amazon, phí giao hàng lấy cột Wayfair
    wf = {"landed_cost": 100, "wf_fee_unit": 10, "amz_referral_pct": 0.5, "return_pct": None}
    assert insights.unit_margin(200, wf, {"referral_pct": 0, "return_pct": 0}, "wayfair") == 90
    assert insights.unit_margin(200, None, chan, "amazon") is None
    assert insights.unit_margin(None, cost, chan, "amazon") is None


def test_add_profit_and_cards():
    rows = [{"product_id": 1, "total_sales": 3000, "total_units": 10, "spend": 500, "sales": 2000},
            {"product_id": 2, "total_sales": 1000, "total_units": 5, "spend": 100, "sales": 800}]
    costs = {"manual": {1: {"landed_cost": 150}}, "std": {}}
    insights.add_profit(rows, costs, {"amazon": {"referral_pct": 0.1, "return_pct": 0}}, "amazon")
    r = rows[0]
    assert r["price"] == 300 and r["margin_unit"] == 120 and r["breakeven_acos"] == 0.4
    assert r["profit_before"] == 1200 and r["profit_after"] == 700
    assert rows[1]["profit_after"] is None
    cards = insights.profit_cards(rows, 600)
    assert cards[0]["value"] == 700 and "1 SKU" in cards[0]["note"] and "83%" in cards[0]["note"]
    assert cards[1]["value"] == 0.4
    assert insights.profit_cards([{"profit_after": None}], 10)[0]["value"] is None


def test_targets_scope_and_progress():
    t = {"1-US": {"total_sales": 1000, "ad_sales": None, "spend": 100, "tacos": 0.1},
         "2-US": {"total_sales": 3000, "ad_sales": None, "spend": 300, "tacos": 0.1}}
    both = insights.target_for(t, None)
    assert both["total_sales"] == 4000 and both["ad_sales"] is None and both["tacos"] == 0.1
    assert insights.target_for({**t, "": {"total_sales": 9}}, None)["total_sales"] == 9
    assert insights.target_for(t, ["1-US"])["spend"] == 100
    assert insights.target_for(t, ["1-US", "9-CA"]) is None  # thiếu mục tiêu của một tài khoản: không so
    daily = [{"date": f"2026-04-{d:02d}", "total_sales": 100, "sales": 50, "spend": 10} for d in range(1, 11)]
    ch, cards = insights.progress({"total_sales": 6000, "spend": 300, "tacos": 0.12}, daily, date(2026, 4, 10))
    names = [s["name"] for s in ch["series"]]
    assert names == ["Tổng DS thực tế", "Tổng DS mục tiêu", "Spend thực tế", "Spend mục tiêu"]
    assert ch["series"][0]["values"][9] == 1000 and ch["series"][0]["values"][10] is None
    assert ch["series"][1]["values"][-1] == 6000 and ch["series"][1]["dash"] is True
    sales_card, spend_card, tacos_card = cards
    assert abs(sales_card["value"] - 1000 / 6000) < 1e-9 and sales_card["tone"] == "warn"  # dự báo 3,000 < 95%
    assert spend_card["tone"] is None and "dự báo cuối tháng $300 (100%)" in spend_card["note"]
    assert tacos_card["value"] == 0.1 and tacos_card["tone"] is None
