"""Xuất bảng map SKU sàn ↔ SKU hệ thống (Amazon, Wayfair, eBay) ra Excel.

Đọc trực tiếp từ DWH nguồn (SOURCE_DB_*). SKU hệ thống lấy từ prd_product; nếu product_id
không có ở đó (prd_product trên DWH chỉ có 1.000 dòng) thì lấy từ prd_products_temp (5.417 dòng, khớp 100%).

Chạy: .venv/Scripts/python.exe -m scripts.export_sku_map [đường_dẫn.xlsx]
"""
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings as s  # noqa: E402

MARKETPLACES = {"ATVPDKIKX0DER": "US", "A2EUQ1WTGCTBG2": "CA", "A39IBJ37TRP1C6": "AU",
                "A1AM78C64UM0Y8": "MX", "A1F83G8C2ARO7P": "UK", "A1PA6795UKMFR9": "DE"}

PRODUCT_CTE = """
WITH prod AS (
    SELECT t.id, COALESCE(p.product_sku, t.product_sku) AS product_sku, COALESCE(p.title, t.title) AS title,
           t.life_cycle, CASE WHEN p.id IS NOT NULL THEN 'prd_product' ELSE 'prd_products_temp' END AS src
    FROM prd_products_temp t LEFT JOIN prd_product p ON p.id = t.id
    UNION ALL
    SELECT p.id, p.product_sku, p.title, NULL, 'prd_product'
    FROM prd_product p WHERE NOT EXISTS (SELECT 1 FROM prd_products_temp t WHERE t.id = p.id)
)
"""

QUERIES = {
    "Amazon": PRODUCT_CTE + """
        SELECT l.store_account_id, a.title AS account_name, l.marketplace_id, l.seller_sku, l.fba_sku, l.asin,
               NULLIF(l.product_id, 0) AS product_id, pr.product_sku, pr.title, l.fulfill_channel, l.status,
               l.is_ntc, l.last_updated_dwh
        FROM prd_amazon_listings l
        LEFT JOIN s_sales_store_accounts a ON a.id = l.store_account_id
        LEFT JOIN prod pr ON pr.id = l.product_id
        ORDER BY a.title, l.marketplace_id, l.seller_sku""",
    "Wayfair map": PRODUCT_CTE + """
        SELECT w.account_id, a.account_name, a.currency_code, w.sku AS wayfair_sku, w.supplier_part,
               w.original_supplier_part, w.wayfair_product_id, w.product_id, pr.product_sku, pr.title
        FROM wayfair_map_sku_product_id w
        LEFT JOIN wayfair_accounts a ON a.id = w.account_id
        LEFT JOIN prod pr ON pr.id = w.product_id
        ORDER BY a.account_name, w.sku, w.supplier_part""",
    "Wayfair listings": PRODUCT_CTE + """
        SELECT wp.wayfair_listing_id, wp.supplier_part, wp.supplier_part_id, wp.product_id, pr.product_sku,
               pr.title, wp.options, wp.upc, wp.wholesale_price, wp.quantity, wp.status, wp.published, wp.update_time
        FROM prd_wayfair_products wp
        LEFT JOIN prod pr ON pr.id = wp.product_id
        ORDER BY wp.supplier_part""",
    "eBay": PRODUCT_CTE + """
        SELECT e.store_id, e.ebay_item_id, e.product_sku AS ebay_product_sku, e.product_id, pr.product_sku,
               pr.title, e.price, e.quantity_available, e.listing_status, e.published, e.update_time
        FROM prd_ebay_product e
        LEFT JOIN prod pr ON pr.id = e.product_id
        ORDER BY e.store_id, e.ebay_item_id""",
    "SKU hệ thống": PRODUCT_CTE + "SELECT id AS product_id, product_sku, title, life_cycle, src FROM prod ORDER BY product_sku",
}

HEADERS = {
    "Amazon": ["store_account_id", "Tài khoản", "marketplace_id", "Quốc gia", "SKU sàn (seller_sku)", "FBA SKU (FNSKU)",
               "ASIN", "product_id", "SKU hệ thống", "Tên sản phẩm", "Fulfillment", "Trạng thái", "is_ntc",
               "Cập nhật DWH", "Ghi chú"],
    "Wayfair map": ["account_id", "Tài khoản", "Tiền tệ", "Wayfair SKU", "Supplier part", "Supplier part gốc",
                    "wayfair_product_id", "product_id", "SKU hệ thống", "Tên sản phẩm", "Ghi chú"],
    "Wayfair listings": ["wayfair_listing_id", "Supplier part", "supplier_part_id", "product_id", "SKU hệ thống",
                         "Tên sản phẩm", "Options", "UPC", "Giá wholesale", "Số lượng", "Trạng thái", "published",
                         "Cập nhật", "Ghi chú"],
    "eBay": ["store_id", "eBay item ID", "SKU trên eBay", "product_id", "SKU hệ thống", "Tên sản phẩm", "Giá",
             "SL khả dụng", "Trạng thái listing", "published", "Cập nhật", "Ghi chú"],
    "SKU hệ thống": ["product_id", "SKU hệ thống", "Tên sản phẩm", "life_cycle", "Nguồn"],
}
WIDTHS = {"product_id": 10, "Tên sản phẩm": 45, "Ghi chú": 30, "Tài khoản": 26}


def note(sheet: str, row: tuple) -> str:
    if sheet == "SKU hệ thống":
        return ""
    pid_idx = {"Amazon": 6, "Wayfair map": 7, "Wayfair listings": 3, "eBay": 3}[sheet]
    sku_idx = pid_idx + 1
    if not row[pid_idx]:
        return "Thiếu product_id"
    if not row[sku_idx]:
        return "product_id không có trong danh mục"
    return ""


def shape(sheet: str, row: tuple) -> list:
    r = list(row)
    n = note(sheet, row)
    if sheet == "Amazon":
        r.insert(3,MARKETPLACES.get(r[2] or "", r[2] or ""))
    if sheet == "SKU hệ thống":
        return r
    return r + [n]


def write_sheet(wb: Workbook, name: str, rows: list[list]) -> None:
    ws = wb.create_sheet(name)
    headers = HEADERS[name]
    ws.append(headers)
    for r in rows:
        ws.append(r)
    fill = PatternFill("solid", fgColor="1F4E78")
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = WIDTHS.get(h, max(12, min(24, len(h) + 4)))
    warn = PatternFill("solid", fgColor="FCE4D6")
    if headers[-1] == "Ghi chú":
        for row in ws.iter_rows(min_row=2):
            if row[-1].value:
                row[-1].fill = warn
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def main(out: Path) -> None:
    url = URL.create("mysql+pymysql", username=s.source_db_user, password=s.source_db_password,
                     host=s.source_db_host, port=s.source_db_port, database=s.source_schema,
                     query={"charset": "utf8mb4"})
    engine = create_engine(url, connect_args={"connect_timeout": 20})
    data = {}
    with engine.connect() as conn:
        for name, sql in QUERIES.items():
            data[name] = [shape(name, tuple(r)) for r in conn.execute(text(sql))]

    wb = Workbook()
    info = wb.active
    info.title = "Hướng dẫn"
    lines = [
        ("Bảng map SKU sàn ↔ SKU hệ thống", ""),
        ("Ngày xuất", date.today().isoformat()),
        ("Nguồn", f"DWH {s.source_schema} (đọc trực tiếp)"),
        ("", ""),
        ("Sheet", "Nội dung / khoá nối"),
        ("Amazon", "prd_amazon_listings: seller_sku + store_account_id + marketplace_id → product_id"),
        ("Wayfair map", "wayfair_map_sku_product_id: Wayfair SKU + supplier_part + account_id → product_id"),
        ("Wayfair listings", "prd_wayfair_products: supplier_part → product_id (luôn có product_id)"),
        ("eBay", "prd_ebay_product: ebay_item_id → product_id"),
        ("SKU hệ thống", "Danh mục: product_id → SKU hệ thống. prd_product (1.000 dòng) bổ sung bằng prd_products_temp"),
        ("Walmart / Shopify", "Không có bảng map: hai kênh dùng thẳng SKU hệ thống làm SKU sàn"),
        ("", ""),
        ("Số dòng", ""),
    ]
    for name, rows in data.items():
        missing = sum(1 for r in rows if name != "SKU hệ thống" and r[-1])
        lines.append((name, f"{len(rows):,} dòng" + (f" — {missing:,} dòng có ghi chú (thiếu map)" if missing else "")))
    for a, b in lines:
        info.append([a, b])
    info["A1"].font = Font(bold=True, size=14)
    info["A5"].font = info["B5"].font = info["A13"].font = Font(bold=True)
    info.column_dimensions["A"].width = 20
    info.column_dimensions["B"].width = 100

    for name, rows in data.items():
        write_sheet(wb, name, rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    for name, rows in data.items():
        print(f"{name}: {len(rows)}")
    print(f"Saved {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    default = Path(__file__).resolve().parents[1] / "exports" / f"sku_map_{date.today():%Y%m%d}.xlsx"
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else default)
