"""Đọc file bulk Sponsored Products (Ads Console) vào mart và dựng file bulk để upload lại.

Chỉ dùng sheet "Sponsored Products Campaigns". Sheet SB / SD chưa audit nên bỏ qua.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import openpyxl
from sqlalchemy import text

from app.config import ROOT_DIR
from app.db import fetch_all, get_engine

SP_SHEET = "Sponsored Products Campaigns"
UPLOAD_DIR = ROOT_DIR / "exports" / "bulk"
KEEP_UPLOADS = 3  # số lần upload gần nhất của mỗi tài khoản còn giữ dòng chi tiết
BATCH = 5000

# cột trong mart -> các tiêu đề có thể có (lấy ô đầu tiên có giá trị)
COLUMNS = {
    "entity": ["Entity"],
    "campaign_id": ["Campaign ID"],
    "ad_group_id": ["Ad Group ID"],
    "portfolio_id": ["Portfolio ID"],
    "campaign_name": ["Campaign name", "Campaign name (Informational only)"],
    "ad_group_name": ["Ad group name", "Ad group name (Informational only)"],
    "targeting_type": ["Targeting type"],
    "state": ["State"],
    "campaign_state": ["Campaign state (Informational only)"],
    "ad_group_state": ["Ad group state (Informational only)"],
    "bid": ["Bid"],
    "default_bid": ["Ad Group Default Bid", "Ad Group Default Bid (Informational only)"],
    "keyword_text": ["Keyword text"],
    "match_type": ["Match type"],
    "expression": ["Product targeting expression"],
    "sku": ["SKU"],
    "asin": ["ASIN (Informational only)"],
}
OBJECT_ID = {"Keyword": "Keyword ID", "Negative keyword": "Keyword ID", "Campaign negative keyword": "Keyword ID",
             "Product targeting": "Product Targeting ID", "Negative product targeting": "Product Targeting ID",
             "Campaign Negative Product Targeting": "Product Targeting ID", "Product ad": "Ad ID"}
# tên entity chuẩn hoá (khoá viết thường) -> cách viết bộ máy audit dùng
ENTITY = {e.lower(): e for e in ("Campaign", "Ad group", "Keyword", "Negative keyword", "Campaign negative keyword",
                                 "Product targeting", "Negative product targeting", "Campaign Negative Product Targeting",
                                 "Product ad", "Bidding adjustment")}
REQUIRED = ("Entity", "Campaign ID", "Ad Group ID", "Keyword ID", "Product Targeting ID", "Bid", "State")


class BulkError(ValueError):
    pass


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _str(v, size):
    if v is None:
        return None
    s = str(v).strip()
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    return s[:size] or None


def read_sp_rows(path: Path) -> tuple[list[str], list[dict]]:
    """Đọc sheet SP. File của Amazon ghi sai kích thước sheet, nên phải reset_dimensions mới đọc hết dòng."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if SP_SHEET not in wb.sheetnames:
            raise BulkError(f"Không thấy sheet '{SP_SHEET}'. Hãy tải file bulk Sponsored Products từ Ads Console.")
        ws = wb[SP_SHEET]
        ws.reset_dimensions()
        it = ws.iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else "" for h in next(it, [])]
        # Tuỳ tài khoản / thời điểm, Amazon viết hoa tiêu đề và tên entity khác nhau ("Campaign name" / "Campaign Name",
        # "Ad group" / "Ad Group") nên so khớp không phân biệt hoa thường; tiêu đề trùng thì lấy cột đầu.
        idx = {h.lower(): i for i, h in reversed(list(enumerate(headers)))}
        missing = [h for h in REQUIRED if h.lower() not in idx]
        if missing:
            raise BulkError("File thiếu cột: " + ", ".join(missing))
        rows = []
        for n, r in enumerate(it, start=2):
            if not r or r[idx["entity"]] in (None, ""):
                continue
            get = lambda h: r[idx[h.lower()]] if h.lower() in idx and idx[h.lower()] < len(r) else None  # noqa: E731
            row = {"row_no": n}
            for col, names in COLUMNS.items():
                row[col] = next((get(h) for h in names if get(h) not in (None, "")), None)
            raw = str(row["entity"]).strip()
            row["entity"] = ENTITY.get(raw.lower(), raw)
            row["object_id"] = get(OBJECT_ID[row["entity"]]) if row["entity"] in OBJECT_ID else None
            rows.append(row)
        return headers, rows
    finally:
        wb.close()


def _clean_row(upload_id: int, r: dict) -> dict:
    return {
        "u": upload_id, "row_no": r["row_no"], "entity": _str(r["entity"], 40),
        "campaign_id": _str(r["campaign_id"], 25), "ad_group_id": _str(r["ad_group_id"], 25),
        "portfolio_id": _str(r["portfolio_id"], 25), "object_id": _str(r["object_id"], 25),
        "campaign_name": _str(r["campaign_name"], 255), "ad_group_name": _str(r["ad_group_name"], 255),
        "targeting_type": _str(r["targeting_type"], 10), "state": _str(r["state"], 12),
        "campaign_state": _str(r["campaign_state"], 12), "ad_group_state": _str(r["ad_group_state"], 12),
        "bid": _num(r["bid"]), "default_bid": _num(r["default_bid"]),
        "keyword_text": _str(r["keyword_text"], 255), "match_type": _str(r["match_type"], 30),
        "expression": _str(r["expression"], 500), "sku": _str(r["sku"], 100), "asin": _str(r["asin"], 20),
    }


def store(upload_id: int, path: Path) -> dict:
    """Đọc file, nhận tài khoản theo Campaign ID, ghi dòng vào audit_bulk_row. Trả về thông tin để cập nhật upload."""
    headers, rows = read_sp_rows(path)
    if not rows:
        raise BulkError("Sheet Sponsored Products không có dòng dữ liệu nào.")
    campaign_ids = sorted({_str(r["campaign_id"], 25) for r in rows if r["entity"] == "Campaign" and r["campaign_id"]})
    if not campaign_ids:
        raise BulkError("Không thấy dòng Campaign nào trong file.")
    found = {}
    for i in range(0, len(campaign_ids), 1000):
        chunk = campaign_ids[i:i + 1000]
        ph = ",".join(f":c{j}" for j in range(len(chunk)))
        for r in fetch_all(f"SELECT profile_id, COUNT(*) AS n FROM dim_campaign WHERE ad_type = 'SP' AND campaign_id IN ({ph}) "
                           "GROUP BY profile_id", {f"c{j}": c for j, c in enumerate(chunk)}):
            found[r["profile_id"]] = found.get(r["profile_id"], 0) + r["n"]
    if not found:
        raise BulkError("Không campaign nào trong file khớp dữ liệu quảng cáo của hệ thống. File có đúng tài khoản Amazon của công ty không?")
    profile_id, matched = max(found.items(), key=lambda kv: kv[1])
    cols = list(_clean_row(0, rows[0]).keys())
    sql = text(f"INSERT INTO audit_bulk_row ({', '.join(c if c != 'u' else 'upload_id' for c in cols)}) "
               f"VALUES ({', '.join(':' + c for c in cols)})")
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM audit_bulk_row WHERE upload_id = :u"), {"u": upload_id})
        for i in range(0, len(rows), BATCH):
            conn.execute(sql, [_clean_row(upload_id, r) for r in rows[i:i + BATCH]])
        # bỏ dòng chi tiết của các lần upload cũ (giữ thông tin upload và đề xuất)
        old = conn.execute(text("""SELECT id FROM audit_bulk_upload WHERE profile_id = :p AND id <> :u
                                   ORDER BY id DESC LIMIT 1000 OFFSET :k"""),
                           {"p": profile_id, "u": upload_id, "k": KEEP_UPLOADS - 1}).scalars().all()
        for oid in old:
            conn.execute(text("DELETE FROM audit_bulk_row WHERE upload_id = :u"), {"u": oid})
    return {"profile_id": profile_id, "n_rows": len(rows), "n_campaigns": len(campaign_ids),
            "matched_campaigns": matched, "headers": json.dumps(headers, ensure_ascii=False)}


# ---------------------------------------------------------------- xuất file bulk

ASIN_RE = re.compile(r"^b0[0-9a-z]{8}$", re.I)


def export_rows(p: dict) -> list[dict]:
    """Một đề xuất -> các dòng bulk (theo tiêu đề cột của Amazon)."""
    base = {"Product": "Sponsored Products", "Campaign ID": p["campaign_id"], "Ad Group ID": p["ad_group_id"]}
    action = p["action"]
    is_target = (p.get("match_type") or "").startswith("TARGETING") or p.get("entity") == "Product targeting"
    if action in ("bid", "pause"):
        row = {**base, "Entity": "Product Targeting" if is_target else "Keyword", "Operation": "Update"}
        row["Product Targeting ID" if is_target else "Keyword ID"] = p["object_id"]
        if action == "bid":
            row["Bid"] = round(p["new_bid"], 2)
        else:
            row["State"] = "paused"
        return [row]
    if action == "add_keyword":
        return [{**base, "Entity": "Keyword", "Operation": "Create", "State": "enabled", "Keyword text": p["text"],
                 "Match type": "exact", "Bid": round(p["new_bid"], 2)}]
    if action == "add_target":
        return [{**base, "Entity": "Product Targeting", "Operation": "Create", "State": "enabled",
                 "Product targeting expression": f'asin="{p["text"].upper()}"', "Bid": round(p["new_bid"], 2)}]
    if action == "negative":
        return [{**base, "Entity": "Negative Keyword", "Operation": "Create", "State": "enabled", "Keyword text": p["text"],
                 "Match type": "negativeExact"}]
    if action == "negative_target":
        return [{**base, "Entity": "Negative Product Targeting", "Operation": "Create", "State": "enabled",
                 "Product targeting expression": f'asin="{p["text"].upper()}"'}]
    return []


def write_xlsx(path: Path, headers: list[str], proposals: list[dict]) -> int:
    """Ghi file bulk chỉ gồm các dòng thay đổi. Giữ đúng bộ cột của file Amazon đã upload."""
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet(SP_SHEET)
    ws.append(headers)
    pos = {h.lower(): i for i, h in reversed(list(enumerate(headers)))}
    n = 0
    for p in proposals:
        for row in export_rows(p):
            out = [None] * len(headers)
            for k, v in row.items():
                if k.lower() in pos:
                    out[pos[k.lower()]] = v
            ws.append(out)
            n += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return n


def new_upload_path(file_name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file_name).name)[-120:] or "bulk.xlsx"
    return UPLOAD_DIR / "uploads" / f"{datetime.now():%Y%m%d_%H%M%S}_{safe}"
