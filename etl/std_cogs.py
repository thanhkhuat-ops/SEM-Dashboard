"""Nạp giá vốn chuẩn (Standard COGS) từ Google Sheet của BOD vào {mart}.ref_std_cogs.

Sheet "All Sales Team - COGS All Products US CA AU": dòng tiêu đề bắt đầu bằng ô "SKU", 8 cột giá vốn theo
thị trường × hình thức (WH / FBA / CG). Cột được nhận theo tên tiêu đề nên đổi thứ tự cột trên sheet không sao.

Hai cách đọc (cấu hình trong .env):
  - GOOGLE_SA_JSON = đường dẫn file khóa JSON của service account đã được chia sẻ quyền xem sheet → Sheets API.
  - để trống → tải CSV qua link export; sheet phải bật "Bất kỳ ai có đường liên kết đều có thể xem".

    python -m etl.std_cogs              # nạp ngay (không cần chạy cả ETL)
    python -m etl.std_cogs --dry-run    # chỉ đọc và in thống kê
"""
import argparse
import base64
import csv
import io
import json
import re
import sys
import time
from datetime import datetime

import httpx
from sqlalchemy import text

# tiêu đề cột (viết thường, bỏ khoảng trắng thừa) → (thị trường, hình thức, tiền tệ)
COLUMNS = {
    "standard wh cogs usa (usd)": ("US", "WH", "USD"),
    "standard wh cogs canada (cad)": ("CA", "WH", "CAD"),
    "standard wh cogs australia (aud)": ("AU", "WH", "AUD"),
    "standard cogs fba us (usd)": ("US", "FBA", "USD"),
    "standard cogs cg us (usd)": ("US", "CG", "USD"),
    "standard cogs fba can (cad)": ("CA", "FBA", "CAD"),
    "standard cogs cg can (cad)": ("CA", "CG", "CAD"),
    "standard cogs fba senno (aud)": ("AU", "FBA", "AUD"),
}
INFO = {"title": "title", "brand": "brand", "sell type": "sell_type", "category": "category"}
TIMEOUT = 60


class SheetError(RuntimeError):
    pass


def _key(header: str) -> str:
    return re.sub(r"\s+", " ", (header or "").strip().lower())


def _money(raw: str) -> float | None:
    s = (raw or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s or s in ("-", "#N/A", "#REF!", "#VALUE!"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def parse(table: list[list[str]]) -> list[dict]:
    """Bảng ô (list dòng) → các dòng ref_std_cogs. Lỗi nếu không thấy dòng tiêu đề hoặc thiếu cột giá vốn."""
    head_idx = next((i for i, r in enumerate(table) if r and _key(r[0]) == "sku"), None)
    if head_idx is None:
        raise SheetError("Không thấy dòng tiêu đề có ô đầu là 'SKU'")
    header = [_key(h) for h in table[head_idx]]
    cost_cols = {i: COLUMNS[h] for i, h in enumerate(header) if h in COLUMNS}
    missing = set(COLUMNS.values()) - set(cost_cols.values())
    if missing:
        raise SheetError("Thiếu cột giá vốn: " + ", ".join(f"{m} {b}" for m, b, _ in sorted(missing)))
    info_cols = {INFO[h]: i for i, h in enumerate(header) if h in INFO}
    out, seen = [], set()
    for r in table[head_idx + 1:]:
        sku = (r[0] if r else "").strip()
        if not sku or sku in seen:
            continue
        seen.add(sku)
        cell = lambda i: r[i].strip() if i is not None and i < len(r) else ""
        info = {k: cell(i) or None for k, i in info_cols.items()}
        for i, (market, basis, cur) in cost_cols.items():
            v = _money(cell(i))
            if v is not None:
                out.append({"product_sku": sku, "market": market, "basis": basis, "currency_code": cur, "cogs": v, **info})
    return out


# ---------------------------------------------------------------- đọc sheet

def fetch_csv(sheet_id: str, gid: str) -> list[list[str]]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    body = resp.content.decode("utf-8-sig", errors="replace")
    if resp.status_code != 200 or "accounts.google.com" in str(resp.url) or body.lstrip().startswith("<"):
        raise SheetError("Không tải được sheet qua link (cần bật chia sẻ 'Bất kỳ ai có đường liên kết đều có thể xem' "
                         f"hoặc cấu hình GOOGLE_SA_JSON). HTTP {resp.status_code}")
    return list(csv.reader(io.StringIO(body)))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sa_token(sa_path: str) -> str:
    """Access token của service account (JWT RS256 ký bằng private key trong file JSON)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    with open(sa_path, encoding="utf-8") as fh:
        sa = json.load(fh)
    now = int(time.time())
    claims = {"iss": sa["client_email"], "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
              "aud": sa.get("token_uri", "https://oauth2.googleapis.com/token"), "iat": now, "exp": now + 3600}
    unsigned = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()) + "." + _b64(json.dumps(claims).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = key.sign(unsigned.encode(), padding.PKCS1v15(), hashes.SHA256())
    resp = httpx.post(claims["aud"], timeout=TIMEOUT, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": unsigned + "." + _b64(sig)})
    if resp.status_code != 200:
        raise SheetError(f"Service account không lấy được token: HTTP {resp.status_code} {resp.text[:200]}")
    return resp.json()["access_token"]


def fetch_api(sheet_id: str, gid: str, sa_path: str) -> list[list[str]]:
    headers = {"Authorization": f"Bearer {sa_token(sa_path)}"}
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    meta = httpx.get(base, params={"fields": "sheets.properties(sheetId,title)"}, headers=headers, timeout=TIMEOUT)
    if meta.status_code != 200:
        raise SheetError(f"Sheets API: HTTP {meta.status_code} {meta.text[:200]} (đã chia sẻ sheet cho service account chưa?)")
    titles = {str(s["properties"]["sheetId"]): s["properties"]["title"] for s in meta.json().get("sheets", [])}
    title = titles.get(str(gid))
    if not title:
        raise SheetError(f"Không có tab gid={gid} trong sheet")
    title_ref = "'" + title.replace("'", "''") + "'"
    resp = httpx.get(f"{base}/values:batchGet", headers=headers, timeout=TIMEOUT,
                     params={"ranges": title_ref, "valueRenderOption": "FORMATTED_VALUE"})
    if resp.status_code != 200:
        raise SheetError(f"Sheets API: HTTP {resp.status_code} {resp.text[:200]}")
    ranges = resp.json().get("valueRanges", [])
    return [[str(c) for c in row] for row in (ranges[0].get("values", []) if ranges else [])]


def fetch(sheet_id: str, gid: str, sa_path: str = "") -> list[list[str]]:
    return fetch_api(sheet_id, gid, sa_path) if sa_path else fetch_csv(sheet_id, gid)


# ---------------------------------------------------------------- ghi mart

def load(conn, mart: str, rows: list[dict]) -> int:
    """Thay toàn bộ ref_std_cogs bằng rows (trong một transaction) rồi gán product_id theo dim_product.product_sku."""
    if not rows:
        raise SheetError("Sheet không có dòng giá vốn nào, giữ nguyên dữ liệu cũ")
    now = datetime.now()
    conn.execute(text(f"DELETE FROM {mart}.ref_std_cogs"))
    conn.execute(text(f"""INSERT INTO {mart}.ref_std_cogs
        (product_sku, market, basis, currency_code, cogs, title, brand, sell_type, category, loaded_at)
        VALUES (:product_sku, :market, :basis, :currency_code, :cogs, :title, :brand, :sell_type, :category, :t)"""),
                 [{"title": None, "brand": None, "sell_type": None, "category": None, **r, "t": now} for r in rows])
    # SKU trùng nhiều product_id trong dim_product thì bỏ trống (giống nhập giá vốn bằng CSV ở tab Giá vốn & phí)
    conn.execute(text(f"""UPDATE {mart}.ref_std_cogs s
        JOIN (SELECT product_sku, MIN(product_id) AS product_id FROM {mart}.dim_product
              GROUP BY product_sku HAVING COUNT(*) = 1) d ON d.product_sku = s.product_sku
        SET s.product_id = d.product_id"""))
    return len(rows)


def run(engine, mart: str, sheet_id: str, gid: str, sa_path: str = "") -> dict:
    rows = parse(fetch(sheet_id, gid, sa_path))
    with engine.begin() as conn:
        n = load(conn, mart, rows)
        unmatched = conn.execute(text(f"SELECT COUNT(DISTINCT product_sku) FROM {mart}.ref_std_cogs "
                                      "WHERE product_id IS NULL")).scalar()
    return {"rows": n, "skus": len({r["product_sku"] for r in rows}), "unmatched_skus": unmatched}


def main(argv: list[str] | None = None) -> int:
    from app.config import settings
    from app.db import get_engine

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Nạp giá vốn chuẩn từ Google Sheet")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not settings.cogs_sheet_id:
        print("Chưa cấu hình COGS_SHEET_ID trong .env")
        return 1
    if args.dry_run:
        rows = parse(fetch(settings.cogs_sheet_id, settings.cogs_sheet_gid, settings.google_sa_json))
        by = {}
        for r in rows:
            by[(r["market"], r["basis"])] = by.get((r["market"], r["basis"]), 0) + 1
        print(f"{len({r['product_sku'] for r in rows})} SKU, {len(rows)} ô giá vốn: "
              + ", ".join(f"{m}-{b} {n}" for (m, b), n in sorted(by.items())))
        return 0
    print(run(get_engine(), f"`{settings.mart_schema}`", settings.cogs_sheet_id, settings.cogs_sheet_gid,
              settings.google_sa_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
