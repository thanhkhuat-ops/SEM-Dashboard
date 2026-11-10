"""Tồn FBA theo tài khoản từ Google Sheet "inventory details" -> {mart}.fact_fba_sheet_stock (+ lịch sử, + nút FBA).

DWH không còn ảnh chụp tồn FBA mới (báo cáo MYI dừng 16/09/2026), nên dùng sheet do team tồn kho duy trì. Sheet có
mỗi dòng một SKU nội bộ (cột "Product SKU") và cặp cột "FBA <tài khoản>-In Stock" / "FBA <tài khoản>-On Order".
Sheet không ghi ngày dữ liệu nên ngày của ảnh chụp = ngày ETL đọc; mỗi ngày giữ lần đọc cuối.

Dùng trong app:
  - In Stock -> tồn của nút FBA-<kênh> (on_hand = available = In Stock), đưa vào dự báo hết hàng và vào "Cả nước".
  - Lịch sử theo ngày đọc -> fact_inv_stock_daily (để biết ngày còn hàng của nút FBA từ nay về sau).
  - On Order chỉ lưu để đối chiếu; hàng đang về FBA vẫn lấy từ shipment trên DWH (có ETA, theo từng shipment).

Tài khoản trên sheet -> kênh bán FBA (s_sales_channels): xem ACCOUNTS. Cột FBA của tài khoản chưa có trong ACCOUNTS bị bỏ
qua và ghi vào nhật ký.

    python -m etl.fba_sheet              # đọc sheet và lưu ngay (không cần chạy cả ETL)
    python -m etl.fba_sheet --dry-run    # chỉ đọc và in thống kê
"""
import argparse
import hashlib
import re
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import text

from etl.std_cogs import SheetError, fetch

# tên tài khoản trên sheet (viết thường) -> sales_channel_id của kênh FBA
ACCOUNTS = {
    "megsu": 51,     # AMZ-MEGSU-FBA (US)
    "dh intra": 22,  # AMZ-DHI-FBA (CA)
    "senno": 33,     # AMZ-AUS-SNN-FBA (AU)
    "arozu": 53,     # AMZ-AROZU-FBA (US)
    "hurav": 20,     # AMZ-HRV-FBA (US)
}
SKU_HEADER = "product sku"
FBA_COL = re.compile(r"^fba\s+(.+?)\s*-\s*(in stock|on order)$")
MAX_AGE_DAYS = 7  # ảnh chụp cũ hơn số ngày này thì không dùng làm tồn hiện tại


def _num(raw: str) -> int:
    s = (raw or "").strip().replace(",", "")
    if not s or s in ("-", "#N/A"):
        return 0
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def parse(table: list[list[str]]) -> dict:
    """-> {"rows": [{account, sales_channel_id, product_sku, in_stock, on_order}], "unknown_accounts", "conflicts"}."""
    head_idx = next((i for i, r in enumerate(table[:20]) if any(c.strip().lower() == SKU_HEADER for c in r)), None)
    if head_idx is None:
        raise SheetError("Không thấy cột 'Product SKU' trên sheet FBA")
    head = [c.strip().lower() for c in table[head_idx]]
    sku_col = head.index(SKU_HEADER)
    cols: dict[str, dict[str, int]] = {}  # account -> {"in stock": idx, "on order": idx}; cột trùng tên lấy cột đầu
    for i, h in enumerate(head):
        m = FBA_COL.match(re.sub(r"\s+", " ", h))
        if m:
            cols.setdefault(m.group(1), {}).setdefault(m.group(2), i)
    unknown = sorted(a for a in cols if a not in ACCOUNTS)
    if not any(a in ACCOUNTS for a in cols):
        raise SheetError("Sheet không có cột 'FBA <tài khoản>-In Stock' nào khớp danh sách tài khoản")

    seen: dict[tuple, tuple] = {}
    conflicts, rows = set(), []
    for r in table[head_idx + 1:]:
        sku = (r[sku_col] if sku_col < len(r) else "").strip().upper()
        if not sku:
            continue
        for acc, idx in cols.items():
            ch = ACCOUNTS.get(acc)
            if ch is None:
                continue
            get = lambda k: _num(r[idx[k]]) if k in idx and idx[k] < len(r) else 0  # noqa: E731
            val = (get("in stock"), get("on order"))
            key = (ch, sku)
            if key in seen:  # SKU lặp dòng: giữ dòng đầu, ghi nhận nếu số khác nhau
                if seen[key] != val:
                    conflicts.add(sku)
                continue
            seen[key] = val
            if val != (0, 0):
                rows.append({"account": acc, "sales_channel_id": ch, "product_sku": sku,
                             "in_stock": val[0], "on_order": val[1]})
    return {"rows": rows, "unknown_accounts": unknown, "conflicts": sorted(conflicts),
            "accounts": sorted(a for a in cols if a in ACCOUNTS)}


def data_hash(rows: list[dict]) -> str:
    key = "|".join(f"{r['sales_channel_id']}:{r['product_sku']}:{r['in_stock']}:{r['on_order']}"
                   for r in sorted(rows, key=lambda r: (r["sales_channel_id"], r["product_sku"])))
    return hashlib.md5(key.encode()).hexdigest()


def store(conn, mart: str, parsed: dict, now: datetime | None = None) -> dict:
    """Ghi ảnh chụp của ngày đọc (thay lần đọc trước trong cùng ngày) + lịch sử tồn của nút FBA + nhật ký."""
    now = now or datetime.now().replace(microsecond=0)
    today = now.date()
    sku2pid = {r[0]: r[1] for r in conn.execute(text(
        f"""SELECT UPPER(TRIM(product_sku)), MIN(product_id) FROM {mart}.dim_product WHERE product_sku IS NOT NULL
            GROUP BY UPPER(TRIM(product_sku)) HAVING COUNT(*) = 1"""))}
    rows, unmatched = [], set()
    for r in parsed["rows"]:
        pid = sku2pid.get(r["product_sku"])
        if pid is None:
            unmatched.add(r["product_sku"])
            continue
        rows.append({**r, "product_id": pid, "d": today, "t": now})
    conn.execute(text(f"DELETE FROM {mart}.fact_fba_sheet_stock WHERE read_date = :d"), {"d": today})
    if rows:
        conn.execute(text(f"""INSERT INTO {mart}.fact_fba_sheet_stock
            (read_date, sales_channel_id, product_id, account, product_sku, in_stock, on_order, read_at)
            VALUES (:d, :sales_channel_id, :product_id, :account, :product_sku, :in_stock, :on_order, :t)"""), rows)
    # lịch sử on-hand của nút FBA (chỉ dòng tồn > 0, như POOL / CG)
    conn.execute(text(f"DELETE FROM {mart}.fact_inv_stock_daily WHERE stock_date = :d AND node_id LIKE 'FBA-%'"),
                 {"d": today})
    conn.execute(text(f"""INSERT INTO {mart}.fact_inv_stock_daily (stock_date, node_id, product_id, on_hand)
        SELECT read_date, CONCAT('FBA-', sales_channel_id), product_id, in_stock
        FROM {mart}.fact_fba_sheet_stock WHERE read_date = :d AND in_stock > 0"""), {"d": today})
    notes = []
    if unmatched:
        notes.append(f"{len(unmatched)} SKU không khớp dim_product: " + ", ".join(sorted(unmatched)[:10]))
    if parsed["conflicts"]:
        notes.append(f"{len(parsed['conflicts'])} SKU lặp dòng với số khác nhau (lấy dòng đầu): "
                     + ", ".join(parsed["conflicts"][:10]))
    if parsed["unknown_accounts"]:
        notes.append("Tài khoản FBA chưa gán kênh: " + ", ".join(parsed["unknown_accounts"]))
    res = {"skus": len({r["product_id"] for r in rows}), "in_stock": sum(r["in_stock"] for r in rows),
           "hash": data_hash(parsed["rows"]), "note": "; ".join(notes)[:500]}
    conn.execute(text(f"""INSERT INTO {mart}.fba_sheet_read (read_at, status, data_hash, skus, in_stock, note)
        VALUES (:t, 'OK', :h, :s, :i, :n)"""), {"t": now, "h": res["hash"], "s": res["skus"], "i": res["in_stock"],
                                              "n": res["note"] or None})
    return res


def log_failure(conn, mart: str, message: str) -> None:
    conn.execute(text(f"INSERT INTO {mart}.fba_sheet_read (read_at, status, note) VALUES (:t, 'FAILED', :n)"),
                 {"t": datetime.now().replace(microsecond=0), "n": message[:500]})


def latest_read_date(conn, mart: str) -> date | None:
    return conn.execute(text(f"SELECT MAX(read_date) FROM {mart}.fact_fba_sheet_stock")).scalar()


def apply(conn, mart: str, today: date | None = None) -> int:
    """Sau 90_inventory.sql: đưa ảnh chụp mới nhất (nếu chưa quá MAX_AGE_DAYS) thành tồn hiện tại của nút FBA-<kênh>,
    và đánh dấu các nút đó đã có số tồn. Trả về số dòng tồn FBA đã ghi."""
    today = today or date.today()
    last = latest_read_date(conn, mart)
    if not last or last < today - timedelta(days=MAX_AGE_DAYS):
        return 0
    ids = ", ".join(str(int(c)) for c in ACCOUNTS.values())
    conn.execute(text(f"UPDATE {mart}.dim_inv_node SET has_stock = 1 WHERE node_type = 'FBA' AND sales_channel_id IN ({ids})"))
    conn.execute(text(f"DELETE FROM {mart}.fact_inv_stock WHERE node_id LIKE 'FBA-%'"))
    return conn.execute(text(f"""INSERT INTO {mart}.fact_inv_stock
            (node_id, product_id, on_hand, reserved, available, unfulfillable, updated_at)
        SELECT CONCAT('FBA-', f.sales_channel_id), f.product_id, f.in_stock, 0, f.in_stock, 0, f.read_at
        FROM {mart}.fact_fba_sheet_stock f
        JOIN {mart}.dim_inv_node n ON n.node_id = CONCAT('FBA-', f.sales_channel_id)
        WHERE f.read_date = :d AND f.in_stock <> 0"""), {"d": last}).rowcount


def run(engine, mart: str, sheet_id: str, gid: str, sa_path: str = "") -> dict:
    parsed = parse(fetch(sheet_id, gid, sa_path))
    with engine.begin() as conn:
        return store(conn, mart, parsed)


def main(argv: list[str] | None = None) -> int:
    from app.config import settings
    from app.db import get_engine

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Đọc tồn FBA từ Google Sheet")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not settings.fba_sheet_id:
        print("Chưa cấu hình FBA_SHEET_ID trong .env")
        return 1
    if args.dry_run:
        p = parse(fetch(settings.fba_sheet_id, settings.fba_sheet_gid, settings.google_sa_json))
        by: dict = {}
        for r in p["rows"]:
            by[r["account"]] = by.get(r["account"], 0) + r["in_stock"]
        print(f"{len(p['rows'])} dòng có số; In Stock theo tài khoản: {by}; SKU lặp khác số: {p['conflicts']}; "
              f"tài khoản chưa gán: {p['unknown_accounts']}")
        return 0
    print(run(get_engine(), f"`{settings.mart_schema}`", settings.fba_sheet_id, settings.fba_sheet_gid,
              settings.google_sa_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
