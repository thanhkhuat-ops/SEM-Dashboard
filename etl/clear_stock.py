"""Danh sách SKU đang xả hàng (Clear Stock) từ Google Sheet -> {mart}.ref_clear_stock.

Sheet có các cột "pic", "Product SKU", "status" (nhận theo tên tiêu đề). SKU trong danh sách không được đề xuất gửi
thêm lên FBA / CastleGate (tab Đề xuất inbound). Lỗi đọc sheet thì giữ bản đã nạp lần trước.

    python -m etl.clear_stock              # nạp ngay
"""
import sys
from datetime import datetime

from sqlalchemy import text

from etl.std_cogs import SheetError, fetch


def parse(table: list[list[str]]) -> list[dict]:
    head_idx = next((i for i, r in enumerate(table[:20]) if any(c.strip().lower() == "product sku" for c in r)), None)
    if head_idx is None:
        raise SheetError("Không thấy cột 'Product SKU' trên sheet Clear Stock")
    head = [c.strip().lower() for c in table[head_idx]]
    i_sku, i_st = head.index("product sku"), head.index("status") if "status" in head else None
    i_pic = head.index("pic") if "pic" in head else None
    out, seen = [], set()
    for r in table[head_idx + 1:]:
        sku = (r[i_sku] if i_sku < len(r) else "").strip().upper()
        if not sku or sku in seen:
            continue
        seen.add(sku)
        get = lambda i: (r[i].strip() if i is not None and i < len(r) else "") or None  # noqa: E731
        out.append({"product_sku": sku, "status": get(i_st) or "Clear Stock", "pic": get(i_pic)})
    return out


def load(conn, mart: str, rows: list[dict]) -> dict:
    if not rows:
        raise SheetError("Sheet Clear Stock không có SKU nào, giữ dữ liệu cũ")
    now = datetime.now().replace(microsecond=0)
    conn.execute(text(f"DELETE FROM {mart}.ref_clear_stock"))
    conn.execute(text(f"""INSERT INTO {mart}.ref_clear_stock (product_sku, status, pic, loaded_at)
        VALUES (:product_sku, :status, :pic, :t)"""), [{**r, "t": now} for r in rows])
    conn.execute(text(f"""UPDATE {mart}.ref_clear_stock c
        JOIN (SELECT UPPER(TRIM(product_sku)) AS sku, MIN(product_id) AS product_id FROM {mart}.dim_product
              WHERE product_sku IS NOT NULL GROUP BY UPPER(TRIM(product_sku)) HAVING COUNT(*) = 1) d ON d.sku = c.product_sku
        SET c.product_id = d.product_id"""))
    unmatched = conn.execute(text(f"SELECT COUNT(*) FROM {mart}.ref_clear_stock WHERE product_id IS NULL")).scalar()
    return {"rows": len(rows), "unmatched": unmatched}


def run(engine, mart: str, sheet_id: str, gid: str, sa_path: str = "") -> dict:
    rows = parse(fetch(sheet_id, gid, sa_path))
    with engine.begin() as conn:
        return load(conn, mart, rows)


def main() -> int:
    from app.config import settings
    from app.db import get_engine

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not settings.clear_sheet_id:
        print("Chưa cấu hình CLEAR_SHEET_ID trong .env")
        return 1
    print(run(get_engine(), f"`{settings.mart_schema}`", settings.clear_sheet_id, settings.clear_sheet_gid,
              settings.google_sa_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
