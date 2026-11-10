import openpyxl
import pytest

from app.audit import wf_bulk, wf_engine, wf_rules

# tiêu đề (dòng 4) của các sheet trong template Wayfair, rút gọn đủ cột bộ đọc / bộ xuất dùng
TEMPLATE = {
    "Edit Sponsored Product Campaign": ["Current Campaign Name", "Campaign ID", "Current Campaign Active", "Store",
                                        "Customer Type", "Current Daily Cap", "Targeting", "Bidding Strategy",
                                        "Current Target ROAS Percentage", "New Daily Cap"],
    "Edit Listing Bids": ["Campaign Name", "Campaign ID", "Campaign Active Status", "Listing", "Current Listing Active Status",
                          "Product Name", "Current Default Bid", "Bidding Strategy", "New Default Bid", "New Listing Active Status"],
    "Add Target Keywords": ["Target Keyword", "Target Keyword Match Type", "Destination Campaign ID",
                            "Destination Campaign Name", "Default Bid"],
    "Edit Target Keyword Bids": ["Campaign Name", "Campaign ID", "Campaign Active Status", "Target Keyword",
                                 "Current Target Keyword Match Type", "Current Default Bid", "New Default Bid", "New Match Type",
                                 "Copy to Existing Campaign ID", "Remove from Current Campaign"],
    "Add Negative Keywords": ["Negative Keyword", "Negative Keyword Match Type", "Destination Campaign ID", "Destination Campaign Name"],
    "Edit Negative Keywords": ["Campaign Name", "Campaign ID", "Campaign Active Status", "Negative Keyword",
                               "Current Negative Keyword Match Type"],
    "Edit Part Numbers": ["Campaign Name", "Campaign ID", "Campaign Active Status", "Part Number",
                          "Current Part Number Active Status", "First 10 Listing ID(s)"],
}
DATA = {
    "Edit Sponsored Product Campaign": [["Kw Ph", 100.0, "ACTIVE", "wayfair.ca", "RESIDENTIAL", "3.0", "Target Keyword", "Manual Bidding", "100.0"],
                                        ["PT", 200.0, "ACTIVE", "wayfair.com", "RESIDENTIAL", "NO DAILY CAP", "Product", "Manual Bidding", "100.0"]],
    "Edit Listing Bids": [["PT", 200.0, "ACTIVE", "AAAI1001", "ACTIVE", "Bed", 0.4, "Manual Bidding"]],
    "Edit Target Keyword Bids": [["Kw Ph", 100.0, "ACTIVE", "Oak  Bed", "SMART PHRASE", 0.5],
                                 ["Kw Ph", 100.0, "ACTIVE", "pine bed", "SMART PHRASE", 0.3]],
    "Edit Negative Keywords": [["Kw Ph", 100.0, "ACTIVE", "cheap", "PHRASE"]],
    "Edit Part Numbers": [["Kw Ph", 100.0, "ACTIVE", "abcd", "ACTIVE", "AAAI1001"]],
}


@pytest.fixture
def template(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Instructions"
    for name, headers in TEMPLATE.items():
        ws = wb.create_sheet(name)
        ws.append(["Instructions:"])
        ws.append(["Use this sheet ..."])
        ws.append(["Pre-filled (do not edit)"] * len(headers))
        ws.append(headers)
        for r in DATA.get(name, []):
            ws.append(r)
    path = tmp_path / "wf.xlsx"
    wb.save(path)
    return path


def test_detect_and_read(template):
    assert wf_bulk.is_wayfair(template)
    rows = wf_bulk.read_rows(template)
    by = {(r["sheet"], r.get("item")): r for r in rows}
    assert {r["sheet"] for r in rows} == {"campaign", "listing", "keyword", "negative", "part"}
    camp = next(r for r in rows if r["sheet"] == "campaign" and r["campaign_id"] == "100")
    assert camp["campaign_state"] == "ACTIVE" and camp["daily_cap"] == "3.0"
    assert by[("keyword", "Oak  Bed")]["bid"] == 0.5 and by[("keyword", "Oak  Bed")]["campaign_id"] == "100"


def test_context_negatives_and_destination(template):
    rows = wf_bulk.read_rows(template)
    ctx = wf_engine.Context(rows)
    assert ctx.negated("100", "cheap oak bed") and not ctx.negated("100", "oak bed")
    assert ctx.currency("100") == "CAD" and ctx.currency("200") == "USD"
    assert ctx.destination("100") is None  # chưa có campaign Smart Exact nào


def test_keyword_object_id_is_stable():
    a = wf_engine.keyword_object_id("100", "Oak  Bed", "smart phrase")
    assert a == wf_engine.keyword_object_id("100", "oak bed", "SMART PHRASE") and len(a) <= 25


def test_write_xlsx_only_changed_rows(template, tmp_path):
    out = tmp_path / "out.xlsx"
    props = [
        {"action": "bid", "campaign_id": "100", "text": "oak bed", "match_type": "SMART PHRASE", "new_bid": 0.444},
        {"action": "listing_off", "campaign_id": "200", "text": "AAAI1001", "match_type": "LISTING"},
        {"action": "budget", "campaign_id": "100", "text": "Kw Ph", "match_type": "DAILY CAP", "new_bid": 3.6},
        {"action": "add_keyword", "campaign_id": "100", "campaign_name": "Kw Ph", "text": "oak bed queen",
         "match_type": "SMART EXACT", "new_bid": 0.5},
        {"action": "negative", "campaign_id": "100", "campaign_name": "Kw Ph", "text": "free bed", "match_type": "SMART PHRASE"},
    ]
    assert wf_bulk.write_xlsx(template, out, props) == 5
    wb = openpyxl.load_workbook(out)

    def data(name):
        return [list(r) for r in wb[name].iter_rows(min_row=5, values_only=True)]

    kw = data("Edit Target Keyword Bids")
    assert len(kw) == 1 and kw[0][3] == "Oak  Bed" and kw[0][6] == 0.44  # dòng "pine bed" không đổi đã bị bỏ
    assert data("Edit Listing Bids")[0][9] == "INACTIVE"
    assert data("Edit Sponsored Product Campaign") == [["Kw Ph", 100, "ACTIVE", "wayfair.ca", "RESIDENTIAL", "3.0",
                                                        "Target Keyword", "Manual Bidding", "100.0", "3.60"]]
    assert data("Add Target Keywords") == [["oak bed queen", "SMART EXACT", 100, "Kw Ph", 0.5]]
    assert data("Add Negative Keywords") == [["free bed", "EXACT", 100, "Kw Ph"]]
    assert data("Edit Negative Keywords") == [] and data("Edit Part Numbers") == []
    assert wb["Edit Target Keyword Bids"].cell(row=4, column=7).value == "New Default Bid"  # giữ dòng tiêu đề


def test_rules_validate_and_defaults():
    assert wf_rules.BY_KEY["acos_target"].default == 0.20
    assert wf_rules.validate("budget_capped_days", 5) == 5
    with pytest.raises(ValueError):
        wf_rules.validate("budget_capped_days", 2.5)
    with pytest.raises(ValueError):
        wf_rules.validate("listing_bid_down_export", 2)
    assert wf_rules.account_id("wf:184614") == "184614"
