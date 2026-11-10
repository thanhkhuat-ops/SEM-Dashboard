"""Đọc file bulk Wayfair (WSP → Bulk Campaign Edits, "*_wf_bulk_campaigns_template.xlsx") vào mart và dựng file để
import lại.

Mỗi sheet có 3 dòng hướng dẫn, tiêu đề cột ở dòng 4, dữ liệu từ dòng 5. Thay đổi ghi vào các cột "New ..." (ô trống =
giữ nguyên). File không có Keyword ID: keyword nhận theo (Campaign ID, keyword, match type). File không có số liệu
hiệu quả; số liệu lấy từ mart (fact_wf_*).
"""
import re
from pathlib import Path

import openpyxl
from sqlalchemy import text

from app.audit.bulk import BulkError, _num, _str
from app.audit.wf_rules import PREFIX
from app.db import fetch_all, get_engine

KEEP_UPLOADS = 3
BATCH = 5000

# sheet -> (mã lưu trong mart, {cột mart: tiêu đề})
SHEETS = {
    "Edit Sponsored Product Campaign": ("campaign", {
        "campaign_name": "Current Campaign Name", "state": "Current Campaign Active", "store": "Store",
        "customer_type": "Customer Type", "daily_cap": "Current Daily Cap", "targeting": "Targeting",
        "bidding": "Bidding Strategy", "target_roas": "Current Target ROAS Percentage"}),
    "Edit Listing Bids": ("listing", {
        "campaign_name": "Campaign Name", "campaign_state": "Campaign Active Status", "item": "Listing",
        "state": "Current Listing Active Status", "bid": "Current Default Bid", "bidding": "Bidding Strategy",
        "info": "Product Name"}),
    "Edit Target Keyword Bids": ("keyword", {
        "campaign_name": "Campaign Name", "campaign_state": "Campaign Active Status", "item": "Target Keyword",
        "match_type": "Current Target Keyword Match Type", "bid": "Current Default Bid"}),
    "Edit Negative Keywords": ("negative", {
        "campaign_name": "Campaign Name", "campaign_state": "Campaign Active Status", "item": "Negative Keyword",
        "match_type": "Current Negative Keyword Match Type"}),
    "Edit Part Numbers": ("part", {
        "campaign_name": "Campaign Name", "campaign_state": "Campaign Active Status", "item": "Part Number",
        "state": "Current Part Number Active Status", "info": "First 10 Listing ID(s)"}),
}
ADD_KEYWORDS = "Add Target Keywords"
ADD_NEGATIVES = "Add Negative Keywords"
SIZES = {"campaign_name": 255, "campaign_state": 12, "item": 255, "match_type": 20, "state": 12, "store": 30,
         "customer_type": 20, "targeting": 30, "bidding": 40, "daily_cap": 20, "info": 600}


def is_wayfair(path: Path) -> bool:
    """Nhận file Wayfair theo tên sheet (file Amazon có sheet "Sponsored Products Campaigns")."""
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return "Edit Target Keyword Bids" in wb.sheetnames
    finally:
        wb.close()


def header_row(ws, limit: int = 10) -> tuple[int, list[str]]:
    """Dòng tiêu đề = dòng đầu tiên có ô "Campaign ID" / "Target Keyword" / "Negative Keyword" (bình thường là dòng 4)."""
    for n, r in enumerate(ws.iter_rows(min_row=1, max_row=limit, values_only=True), start=1):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if {"Campaign ID", "Target Keyword", "Negative Keyword", "Destination Campaign ID"} & set(cells):
            return n, cells
    raise BulkError(f"Sheet '{ws.title}' không có dòng tiêu đề như template Wayfair")


def norm_key(campaign_id, item=None, match_type=None) -> tuple:
    """Khoá so khớp một dòng: campaign + keyword / listing (không phân biệt hoa thường, khoảng trắng thừa) + match type."""
    cid = _str(campaign_id, 25)
    if item is None:
        return (cid,)
    return (cid, " ".join(str(item).split()).lower(), (match_type or "").upper())


def read_rows(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        missing = [s for s in SHEETS if s not in wb.sheetnames]
        if missing:
            raise BulkError("Không phải file bulk Wayfair (thiếu sheet: " + ", ".join(missing) + "). "
                            "Tải ở WSP → Bulk Campaign Edits → Download template.")
        rows = []
        for name, (sheet, cols) in SHEETS.items():
            ws = wb[name]
            ws.reset_dimensions()  # như file Amazon: kích thước sheet ghi sai, read_only sẽ bỏ sót dòng
            h, headers = header_row(ws)
            idx = {v: i for i, v in reversed(list(enumerate(headers)))}
            if "Campaign ID" not in idx:
                raise BulkError(f"Sheet '{name}' thiếu cột Campaign ID")
            for n, r in enumerate(ws.iter_rows(min_row=h + 1, values_only=True), start=h + 1):
                get = lambda col: r[idx[col]] if col in idx and idx[col] < len(r) else None  # noqa: E731
                cid = get("Campaign ID")
                if cid in (None, ""):
                    continue
                row = {"sheet": sheet, "row_no": n, "campaign_id": _str(cid, 25)}
                for col, title in cols.items():
                    v = get(title)
                    row[col] = _num(v) if col in ("bid", "target_roas") else _str(v, SIZES[col])
                if sheet == "campaign":
                    row["campaign_state"] = row["state"]
                rows.append(row)
        return rows
    finally:
        wb.close()


COLS = ["upload_id", "sheet", "row_no", "campaign_id", "campaign_name", "campaign_state", "item", "match_type", "state",
        "bid", "store", "customer_type", "targeting", "bidding", "daily_cap", "target_roas", "info"]


def store(upload_id: int, path: Path) -> dict:
    """Đọc file, nhận tài khoản theo Campaign ID (dim_wf_campaign), ghi dòng vào audit_wf_bulk_row."""
    rows = read_rows(path)
    campaign_ids = sorted({r["campaign_id"] for r in rows if r["sheet"] == "campaign"})
    if not campaign_ids:
        raise BulkError("Sheet Edit Sponsored Product Campaign không có campaign nào.")
    found = {}
    for i in range(0, len(campaign_ids), 1000):
        chunk = campaign_ids[i:i + 1000]
        ph = ",".join(f":c{j}" for j in range(len(chunk)))
        for r in fetch_all(f"SELECT account_id, COUNT(*) AS n FROM dim_wf_campaign WHERE campaign_id IN ({ph}) GROUP BY account_id",
                           {f"c{j}": c for j, c in enumerate(chunk)}):
            found[r["account_id"]] = found.get(r["account_id"], 0) + r["n"]
    if not found:
        raise BulkError("Không campaign nào trong file khớp dữ liệu quảng cáo Wayfair của hệ thống. File có đúng tài khoản của công ty không?")
    account_id, matched = max(found.items(), key=lambda kv: kv[1])
    profile_id = PREFIX + account_id
    sql = text(f"INSERT INTO audit_wf_bulk_row ({', '.join(COLS)}) VALUES ({', '.join(':' + c for c in COLS)})")
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM audit_wf_bulk_row WHERE upload_id = :u"), {"u": upload_id})
        for i in range(0, len(rows), BATCH):
            conn.execute(sql, [{c: r.get(c) for c in COLS} | {"upload_id": upload_id} for r in rows[i:i + BATCH]])
        old = conn.execute(text("""SELECT id FROM audit_bulk_upload WHERE profile_id = :p AND id <> :u
                                   ORDER BY id DESC LIMIT 1000 OFFSET :k"""),
                           {"p": profile_id, "u": upload_id, "k": KEEP_UPLOADS - 1}).scalars().all()
        for oid in old:
            conn.execute(text("DELETE FROM audit_wf_bulk_row WHERE upload_id = :u"), {"u": oid})
    return {"profile_id": profile_id, "n_rows": len(rows), "n_campaigns": len(campaign_ids),
            "matched_campaigns": matched, "headers": None}


# ---------------------------------------------------------------- xuất file

def _changes(proposals: list[dict]) -> tuple[dict, list, list]:
    """Đề xuất -> {sheet: {khoá dòng: {tiêu đề cột New: giá trị}}}, dòng thêm keyword, dòng thêm negative."""
    edits = {"campaign": {}, "listing": {}, "keyword": {}}
    add_kw, add_neg = [], []
    for p in proposals:
        a, cid = p["action"], p["campaign_id"]
        if a == "bid" and p["match_type"] == "LISTING":
            edits["listing"].setdefault(norm_key(cid, p["text"], ""), {})["New Default Bid"] = round(p["new_bid"], 2)
        elif a == "bid":
            edits["keyword"].setdefault(norm_key(cid, p["text"], p["match_type"]), {})["New Default Bid"] = round(p["new_bid"], 2)
        elif a == "remove":
            edits["keyword"].setdefault(norm_key(cid, p["text"], p["match_type"]), {})["Remove from Current Campaign"] = "REMOVE"
        elif a == "listing_off":
            edits["listing"].setdefault(norm_key(cid, p["text"], ""), {})["New Listing Active Status"] = "INACTIVE"
        elif a == "budget":
            edits["campaign"].setdefault(norm_key(cid), {})["New Daily Cap"] = f"{p['new_bid']:.2f}"
        elif a == "add_keyword":
            add_kw.append({"Target Keyword": p["text"], "Target Keyword Match Type": "SMART EXACT",
                           "Destination Campaign ID": int(cid), "Destination Campaign Name": p.get("campaign_name"),
                           "Default Bid": round(p["new_bid"], 2)})
        elif a == "negative":
            add_neg.append({"Negative Keyword": p["text"], "Negative Keyword Match Type": "EXACT",
                            "Destination Campaign ID": int(cid), "Destination Campaign Name": p.get("campaign_name")})
    return edits, add_kw, add_neg


def write_xlsx(src: Path, out: Path, proposals: list[dict]) -> int:
    """Chép template gốc đã upload, mỗi sheet chỉ giữ dòng có thay đổi (điền cột New ...), thêm dòng ở các sheet Add.
    Giữ nguyên 4 dòng đầu (hướng dẫn, chú thích ô) để Wayfair nhận đúng template."""
    if not src.exists():
        raise BulkError("File gốc đã upload không còn trên máy chủ, hãy upload lại file bulk mới.")
    edits, add_kw, add_neg = _changes(proposals)
    wb = openpyxl.load_workbook(src)
    n = 0
    for name, (sheet, _) in SHEETS.items():
        ws = wb[name]
        h, headers = header_row(ws)
        pos = {v: i for i, v in reversed(list(enumerate(headers)))}
        want = edits.get(sheet, {})
        keep = []
        for r in ws.iter_rows(min_row=h + 1, values_only=True):
            if not r or r[pos["Campaign ID"]] in (None, ""):
                continue
            if sheet == "campaign":
                key = norm_key(r[pos["Campaign ID"]])
            elif sheet == "listing":
                key = norm_key(r[pos["Campaign ID"]], r[pos["Listing"]], "")
            elif sheet == "keyword":
                key = norm_key(r[pos["Campaign ID"]], r[pos["Target Keyword"]], r[pos["Current Target Keyword Match Type"]])
            else:
                key = None
            if key in want:
                vals = list(r) + [None] * max(0, len(headers) - len(r))
                for col, v in want[key].items():
                    vals[pos[col]] = v
                keep.append(vals)
        if ws.max_row > h:
            ws.delete_rows(h + 1, ws.max_row - h)
        for i, vals in enumerate(keep, start=h + 1):
            for j, v in enumerate(vals, start=1):
                if v is not None:
                    ws.cell(row=i, column=j, value=v)
        n += len(keep)
    for name, rows in ((ADD_KEYWORDS, add_kw), (ADD_NEGATIVES, add_neg)):
        ws = wb[name]
        h, headers = header_row(ws)
        pos = {v: i for i, v in reversed(list(enumerate(headers)))}
        if ws.max_row > h:
            ws.delete_rows(h + 1, ws.max_row - h)
        for i, row in enumerate(rows, start=h + 1):
            for col, v in row.items():
                if col in pos and v is not None:
                    ws.cell(row=i, column=pos[col] + 1, value=v)
        n += len(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return n


def safe_label(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_") or "wayfair"
