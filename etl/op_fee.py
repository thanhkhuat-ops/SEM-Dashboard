"""Nạp phí vận hành (operation fee) mỗi đơn vị từ Google Sheet của công ty vào {mart}.ref_operation_fee_unit.

Tab "operation_fee_sales_fc": mỗi dòng = SKU × tháng (month_, year_); cột = phí vận hành mỗi đơn vị theo nước × kênh,
vd "US_Amazon_by Marketplace" (FBA), "US_Amazon_by Merchant" (FBM), "CA_Wayfair_Dropship", "AUS_Shopify_by Merchant",
và các cột gộp theo nước × hình thức giao "US_FBM", "US_FBA", "US_CG"… Tiền theo nước: US = USD, CA = CAD, AUS = AUD.
Đọc giống sheet giá vốn chuẩn (etl/std_cogs.fetch: link công khai hoặc service account).

    python -m etl.op_fee              # nạp ngay
    python -m etl.op_fee --dry-run    # chỉ đọc và in thống kê
"""
import argparse
import re
import sys
from datetime import date, datetime

from sqlalchemy import text

from etl.std_cogs import SheetError, _money, fetch

CCY = {"US": "USD", "CA": "CAD", "AUS": "AUD", "AU": "AUD"}


def _key(h: str) -> str:
    """'US_Amazon_by Merchant' -> 'US|amazon by merchant'; 'AUS_FBA' -> 'AU|fba'."""
    h = re.sub(r"\s+", " ", (h or "").strip())
    m = re.match(r"^(US|CA|AUS|AU)_(.+)$", h, re.I)
    if not m:
        return ""
    cc = "AU" if m.group(1).upper() in ("AUS", "AU") else m.group(1).upper()
    rest = re.sub(r"[_\s]+", " ", m.group(2)).strip().lower()
    return f"{cc}|{rest}"


def parse(table: list[list[str]]) -> list[dict]:
    head_idx = next((i for i, r in enumerate(table) if r and r[0].strip().lower() == "sku"), None)
    if head_idx is None:
        raise SheetError("Không thấy dòng tiêu đề có ô đầu là 'sku'")
    header = [h.strip() for h in table[head_idx]]
    low = [h.lower() for h in header]
    try:
        i_m, i_y = low.index("month_"), low.index("year_")
    except ValueError as exc:
        raise SheetError("Thiếu cột month_ / year_") from exc
    cols = {i: _key(h) for i, h in enumerate(header) if _key(h)}
    out, seen = [], set()
    for r in table[head_idx + 1:]:
        if not r or not r[0].strip():
            continue
        try:
            m, y = int(float(r[i_m])), int(float(r[i_y]))
            month = date(y, m, 1)
        except (ValueError, IndexError):
            continue  # tháng ghi sai (13, -2…) thì bỏ
        sku = r[0].strip()
        for i, k in cols.items():
            v = _money(r[i]) if i < len(r) else None
            if v is None or (sku, month, k) in seen:
                continue
            seen.add((sku, month, k))
            cc, col = k.split("|", 1)
            out.append({"product_sku": sku, "month": month, "country_code": cc, "col": col[:60],
                        "currency_code": CCY[cc], "fee": v})
    return out


def load(conn, mart: str, rows: list[dict]) -> int:
    if not rows:
        raise SheetError("Sheet không có dòng phí vận hành nào, giữ nguyên dữ liệu cũ")
    now = datetime.now()
    conn.execute(text(f"DELETE FROM {mart}.ref_operation_fee_unit"))
    sql = text(f"""INSERT INTO {mart}.ref_operation_fee_unit
        (product_sku, month, country_code, col, currency_code, fee, loaded_at)
        VALUES (:product_sku, :month, :country_code, :col, :currency_code, :fee, :t)""")
    for i in range(0, len(rows), 5000):
        conn.execute(sql, [{**r, "t": now} for r in rows[i:i + 5000]])
    conn.execute(text(f"""UPDATE {mart}.ref_operation_fee_unit s
        JOIN (SELECT product_sku, MIN(product_id) AS product_id FROM {mart}.dim_product
              GROUP BY product_sku HAVING COUNT(*) = 1) d ON d.product_sku = s.product_sku
        SET s.product_id = d.product_id"""))
    return len(rows)


def run(engine, mart: str, sheet_id: str, gid: str, sa_path: str = "") -> dict:
    rows = parse(fetch(sheet_id, gid, sa_path))
    with engine.begin() as conn:
        n = load(conn, mart, rows)
        unmatched = conn.execute(text(f"SELECT COUNT(DISTINCT product_sku) FROM {mart}.ref_operation_fee_unit "
                                      "WHERE product_id IS NULL")).scalar()
    months = sorted({r["month"] for r in rows})
    return {"rows": n, "note": f"{len({r['product_sku'] for r in rows})} SKU, tháng {months[0]:%m/%Y}–{months[-1]:%m/%Y}, "
                               f"{unmatched} SKU không khớp dim_product"}


def main(argv: list[str] | None = None) -> int:
    from app.config import settings
    from app.db import get_engine

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Nạp phí vận hành từ Google Sheet")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not settings.opfee_sheet_id:
        print("Chưa cấu hình OPFEE_SHEET_ID trong .env")
        return 1
    if args.dry_run:
        rows = parse(fetch(settings.opfee_sheet_id, settings.opfee_sheet_gid, settings.google_sa_json))
        cols = sorted({(r["country_code"], r["col"]) for r in rows})
        print(f"{len(rows)} ô, {len({r['product_sku'] for r in rows})} SKU; cột: {cols}")
        return 0
    print(run(get_engine(), f"`{settings.mart_schema}`", settings.opfee_sheet_id, settings.opfee_sheet_gid,
              settings.google_sa_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
