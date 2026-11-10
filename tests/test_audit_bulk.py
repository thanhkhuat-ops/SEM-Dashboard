import openpyxl

from app.audit import bulk

BASE = {"campaign_id": "1", "ad_group_id": "2", "object_id": "3", "text": None, "match_type": None,
        "new_bid": None, "current_bid": 0.5}


def test_bid_update_keyword_and_target():
    kw = bulk.export_rows({**BASE, "action": "bid", "match_type": "Exact", "new_bid": 0.444})
    assert kw == [{"Product": "Sponsored Products", "Campaign ID": "1", "Ad Group ID": "2", "Entity": "Keyword",
                   "Operation": "Update", "Keyword ID": "3", "Bid": 0.44}]
    pt = bulk.export_rows({**BASE, "action": "pause", "match_type": "TARGETING"})
    assert pt[0]["Entity"] == "Product Targeting" and pt[0]["Product Targeting ID"] == "3" and pt[0]["State"] == "paused"


def test_creates():
    kw = bulk.export_rows({**BASE, "action": "add_keyword", "text": "oak bed", "new_bid": 0.7})[0]
    assert (kw["Operation"], kw["Entity"], kw["Match type"], kw["Keyword text"]) == ("Create", "Keyword", "exact", "oak bed")
    neg = bulk.export_rows({**BASE, "action": "negative_target", "text": "b0abcdefgh"})[0]
    assert neg["Entity"] == "Negative Product Targeting" and neg["Product targeting expression"] == 'asin="B0ABCDEFGH"'
    assert bulk.export_rows({**BASE, "action": "warn"}) == []


def test_write_xlsx_keeps_headers(tmp_path):
    headers = ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID", "Bid", "Keyword text"]
    path = tmp_path / "out.xlsx"
    n = bulk.write_xlsx(path, headers, [{**BASE, "action": "bid", "match_type": "Broad", "new_bid": 0.3}])
    rows = list(openpyxl.load_workbook(path)[bulk.SP_SHEET].iter_rows(values_only=True))
    assert n == 1 and list(rows[0]) == headers
    assert rows[1] == ("Sponsored Products", "Keyword", "Update", "1", "2", "3", 0.3, None)


def test_title_case_headers_and_entities(tmp_path):
    # một số tài khoản tải về tiêu đề / entity viết hoa kiểu khác ("Keyword Text", "Ad Group")
    headers = ["Product", "Entity", "Operation", "Campaign ID", "Ad Group ID", "Keyword ID", "Product Targeting ID",
               "Campaign Name", "Ad Group Name", "State", "Bid", "Keyword Text", "Match Type"]
    src = tmp_path / "in.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = bulk.SP_SHEET
    ws.append(headers)
    ws.append(["Sponsored Products", "Ad Group", None, "1", "2", None, None, None, "AG one", "enabled", None, None, None])
    ws.append(["Sponsored Products", "Negative Keyword", None, "1", "2", "9", None, None, None, "enabled", None, "oak", "Negative Exact"])
    wb.save(src)
    _, rows = bulk.read_sp_rows(src)
    assert [r["entity"] for r in rows] == ["Ad group", "Negative keyword"]
    assert rows[0]["ad_group_name"] == "AG one" and rows[1]["keyword_text"] == "oak" and rows[1]["object_id"] == "9"
    out = tmp_path / "out.xlsx"
    bulk.write_xlsx(out, headers, [{**BASE, "action": "negative", "text": "pine"}])
    row = list(openpyxl.load_workbook(out)[bulk.SP_SHEET].iter_rows(values_only=True))[1]
    assert row[headers.index("Keyword Text")] == "pine" and row[headers.index("Match Type")] == "negativeExact"
