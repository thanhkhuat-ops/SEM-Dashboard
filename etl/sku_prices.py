"""Xuất Excel giá bán của từng SKU trong N ngày gần nhất (mặc định 365) cho Amazon, Wayfair, Walmart, eBay.

Giá đơn vị theo từng kênh:
- Amazon Seller Central: giá sau khuyến mãi = (item_price - promotion_discount) / quantity_ordered, bỏ đơn Canceled.
  Đọc từ bản sao staging nội bộ (ETL hằng ngày đã chép s__amazon_orders + details).
- Wayfair (dropship + CastleGate): wholesale_price (giá bán sỉ cho Wayfair), số lượng = quantity - cancelled_quantity,
  bỏ PO CANCELLED/REJECTED và đơn REPLACEMENT.
- Walmart Marketplace: charge_amount / order_quantity của dòng PRODUCT (charge_amount là tổng dòng), bỏ dòng Cancelled.
- eBay: transaction_price, bỏ đơn Cancelled.
Wayfair/Walmart/eBay đọc thẳng từ DWH nguồn (chỉ SELECT, bảng nhỏ) nếu có SOURCE_DB_*, không thì đọc staging nội bộ.

Median/mode tính theo đơn vị bán (dòng 2 units được tính 2 lần). Quy đổi USD theo tỷ giá ngày đặt hàng (ads_mart.fx_daily).

Chạy:  python -m etl.sku_prices [--days 365] [--end YYYY-MM-DD] [--out duong_dan.xlsx]
"""
import argparse
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pymysql
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text

from app.config import ROOT_DIR, settings
from app.db import get_engine

AMAZON_SQL = """
SELECT DATE(o.purchased_date) AS order_date, o.id AS order_ref, sa.title AS account, o.sales_channel,
       o.fulfill_channel, COALESCE(NULLIF(d.product_id, 0), ms.product_id, ma.product_id) AS product_id,
       d.seller_sku AS channel_sku, d.asin AS market_id, d.quantity_ordered AS qty,
       (d.item_price - COALESCE(d.promotion_discount, 0)) / d.quantity_ordered AS unit_price
FROM {stg}.s__amazon_orders o
JOIN {stg}.s__amazon_order_details d ON d.amazon_order_id = o.id
LEFT JOIN {stg}.s_sales_store_accounts sa ON sa.id = o.store_id
-- product_id còn thiếu: bổ sung theo seller SKU rồi theo ASIN (bảng map của mart quảng cáo)
LEFT JOIN {mart}.map_sku_product ms ON ms.store_account_id = o.store_id AND ms.seller_sku = d.seller_sku
LEFT JOIN {mart}.map_asin_product ma ON ma.asin = d.asin
WHERE o.purchased_date >= %(start)s AND o.purchased_date < %(end)s
  AND COALESCE(o.status, '') <> 'Canceled'
  AND d.quantity_ordered > 0 AND d.item_price > 0
"""

# Kênh bán -> tài khoản, tiền tệ (theo quốc gia của marketplace)
_CHANNEL_JOIN = """
LEFT JOIN s_sales_channels c ON c.id = o.sales_channel_id
LEFT JOIN s_sales_store_accounts sa ON sa.id = c.store_account_id
LEFT JOIN s_sales_marketplaces m ON m.id = c.marketplace_id
LEFT JOIN s_country co ON co.id = m.country_id
"""

WAYFAIR_SQL = """
SELECT DATE(o.po_date) AS order_date, o.id AS order_ref, sa.title AS account, co.code AS country,
       co.currency_code AS currency, o.order_type AS fulfillment,
       COALESCE(NULLIF(d.product_id, 0), pw.product_id) AS product_id, d.item_number AS channel_sku,
       d.wayfair_sku AS market_id, d.quantity - COALESCE(d.cancelled_quantity, 0) AS qty,
       d.wholesale_price AS unit_price
FROM s__wayfair_orders o
JOIN s__wayfair_order_details d ON d.order_id = o.id
LEFT JOIN (SELECT supplier_part, MAX(NULLIF(product_id, 0)) AS product_id FROM prd_wayfair_products
           GROUP BY supplier_part) pw ON pw.supplier_part = d.item_number
""" + _CHANNEL_JOIN + """
WHERE o.po_date >= %(start)s AND o.po_date < %(end)s
  AND UPPER(COALESCE(o.status, '')) NOT IN ('CANCELLED', 'REJECTED')
  AND o.order_type IN ('dropship', 'castle_gate')
  AND d.quantity - COALESCE(d.cancelled_quantity, 0) > 0 AND d.wholesale_price > 0
"""

WALMART_SQL = """
SELECT DATE(o.order_date) AS order_date, o.id AS order_ref, sa.title AS account, co.code AS country,
       co.currency_code AS currency, 'MKP' AS fulfillment,
       NULLIF(d.product_id, 0) AS product_id, d.product_sku AS channel_sku, NULL AS market_id,
       d.order_quantity AS qty, d.charge_amount / d.order_quantity AS unit_price
FROM s__walmart_order o
JOIN s__walmart_order_details d ON d.wm_order_id = o.id
""" + _CHANNEL_JOIN + """
WHERE o.order_date >= %(start)s AND o.order_date < %(end)s
  AND d.charge_type = 'PRODUCT' AND COALESCE(d.status, '') <> 'Cancelled'
  AND d.order_quantity > 0 AND d.charge_amount > 0
"""

EBAY_SQL = """
SELECT DATE(o.order_time) AS order_date, o.id AS order_ref, sa.title AS account, co.code AS country,
       co.currency_code AS currency, 'FBM' AS fulfillment,
       NULLIF(CAST(d.product_id AS SIGNED), 0) AS product_id, d.sku AS channel_sku, d.item_id AS market_id,
       d.quantity_purchased AS qty, d.transaction_price AS unit_price
FROM s__ebay_orders o
JOIN s__ebay_order_detail d ON d.ebay_order_id = o.id
""" + _CHANNEL_JOIN + """
WHERE o.order_time >= %(start)s AND o.order_time < %(end)s
  AND COALESCE(o.order_status, '') <> 'Cancelled'
  AND d.quantity_purchased > 0 AND d.transaction_price > 0
"""

AMAZON_MARKET = {"amazon.com": ("US", "USD"), "amazon.ca": ("CA", "CAD"),
                 "amazon.com.au": ("AU", "AUD"), "amazon.com.mx": ("MX", "MXN")}
FULFILLMENT = {"AFN": "FBA", "MFN": "FBM", "dropship": "Dropship", "castle_gate": "CastleGate"}


@dataclass
class Line:
    channel: str
    account: str
    country: str
    currency: str
    fulfillment: str
    product_id: int | None
    channel_sku: str
    market_id: str
    order_date: date
    order_ref: str
    qty: int
    price: float
    price_usd: float | None = None


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _source_rows(sql: str, params: dict) -> list[dict]:
    """Bảng đơn Wayfair/Walmart/eBay: đọc DWH nguồn nếu cấu hình, không thì staging nội bộ."""
    if settings.sync_enabled:
        conn = pymysql.connect(host=settings.source_db_host, port=settings.source_db_port,
                               user=settings.source_db_user, password=settings.source_db_password,
                               database=settings.source_schema, charset="utf8mb4", read_timeout=600,
                               cursorclass=pymysql.cursors.DictCursor)
    else:
        conn = pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                               password=settings.db_password, database=settings.staging_schema,
                               charset="utf8mb4", read_timeout=600, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def _local_rows(sql: str, params: dict) -> list[dict]:
    raw = get_engine(None).raw_connection()
    try:
        cur = raw.cursor(pymysql.cursors.DictCursor)
        cur.execute(sql, params)
        return list(cur.fetchall())
    finally:
        raw.close()


def load_lines(start: date, end: date) -> list[Line]:
    params = {"start": start, "end": end}
    lines: list[Line] = []
    for r in _local_rows(AMAZON_SQL.format(stg=settings.staging_schema, mart=settings.mart_schema), params):
        market = AMAZON_MARKET.get((r["sales_channel"] or "").lower())
        if not market or _num(r["unit_price"]) <= 0:  # bỏ Non-Amazon (MCF) và dòng giảm giá hết
            continue
        lines.append(Line("Amazon", r["account"] or "", market[0], market[1],
                          FULFILLMENT.get(r["fulfill_channel"], r["fulfill_channel"] or ""),
                          r["product_id"], r["channel_sku"] or "", r["market_id"] or "",
                          r["order_date"], f"AMZ{r['order_ref']}", int(r["qty"]), _num(r["unit_price"])))
    for channel, sql in (("Wayfair", WAYFAIR_SQL), ("Walmart", WALMART_SQL), ("eBay", EBAY_SQL)):
        for r in _source_rows(sql, params):
            lines.append(Line(channel, r["account"] or "", r["country"] or "", r["currency"] or "USD",
                              FULFILLMENT.get(r["fulfillment"], r["fulfillment"] or ""),
                              r["product_id"], r["channel_sku"] or "", r["market_id"] or "",
                              r["order_date"], f"{channel}{r['order_ref']}", int(r["qty"]), _num(r["unit_price"])))
    return lines


def attach_usd(lines: list[Line], start: date, end: date) -> None:
    rows = _local_rows(f"SELECT date_key, currency_code, rate_usd FROM {settings.mart_schema}.fx_daily "
                       "WHERE date_key >= %(start)s AND date_key < %(end)s", {"start": start, "end": end})
    fx = {(r["date_key"], r["currency_code"]): _num(r["rate_usd"]) for r in rows}
    for ln in lines:
        rate = 1.0 if ln.currency == "USD" else fx.get((ln.order_date, ln.currency))
        ln.price_usd = ln.price * rate if rate else None


def load_products() -> dict[int, tuple[str, str]]:
    rows = _local_rows(f"SELECT id, product_sku, title FROM {settings.staging_schema}.prd_product", {})
    return {r["id"]: (r["product_sku"] or "", r["title"] or "") for r in rows}


def weighted_median(values: list[tuple[float, int]]) -> float | None:
    expanded = [v for v, w in values if v is not None for _ in range(w)]
    return round(statistics.median(expanded), 2) if expanded else None


def weighted_mode(values: list[tuple[float, int, date]]) -> float | None:
    """Giá có nhiều units nhất; hòa thì lấy giá bán gần nhất."""
    units: Counter = Counter()
    last: dict[float, date] = {}
    for v, w, d in values:
        p = round(v, 2)
        units[p] += w
        last[p] = max(last.get(p, d), d)
    if not units:
        return None
    return max(units, key=lambda p: (units[p], last[p]))


def group_key(ln: Line) -> tuple:
    return (ln.channel, ln.account, ln.country, ln.fulfillment, ln.currency, ln.product_id, ln.channel_sku)


def summarize(lines: list[Line]) -> tuple[list[tuple], list[tuple]]:
    groups: dict[tuple, list[Line]] = defaultdict(list)
    for ln in lines:
        groups[group_key(ln)].append(ln)
    summary, daily = [], []
    for key, items in groups.items():
        market_id = max((x.market_id for x in items), default="")
        summary.append((key, market_id, {
            "orders": len({x.order_ref for x in items}),
            "units": sum(x.qty for x in items),
            "days": len({x.order_date for x in items}),
            "median": weighted_median([(x.price, x.qty) for x in items]),
            "mode": weighted_mode([(x.price, x.qty, x.order_date) for x in items]),
            "median_usd": weighted_median([(x.price_usd, x.qty) for x in items]),
            "first": min(x.order_date for x in items),
            "last": max(x.order_date for x in items),
        }))
        by_day: dict[date, list[Line]] = defaultdict(list)
        for x in items:
            by_day[x.order_date].append(x)
        for d, day_items in by_day.items():
            daily.append((d, key, {
                "orders": len({x.order_ref for x in day_items}),
                "units": sum(x.qty for x in day_items),
                "median": weighted_median([(x.price, x.qty) for x in day_items]),
                "median_usd": weighted_median([(x.price_usd, x.qty) for x in day_items]),
            }))
    summary.sort(key=lambda s: (s[0][0], s[0][1], s[0][2], -s[2]["units"]))
    daily.sort(key=lambda s: (s[1][0], s[1][1], s[1][2], s[1][3], s[1][6], s[0]))
    return summary, daily


HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _sheet(wb: Workbook, title: str, headers: list[str], widths: list[int], rows, money_cols: set[int],
           date_cols: set[int]):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for i, w in enumerate(widths, start=1):
        cell = ws.cell(row=1, column=i)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in rows:
        ws.append(row)
    for col in money_cols | date_cols:
        fmt = "#,##0.00" if col in money_cols else "yyyy-mm-dd"
        for (cell,) in ws.iter_rows(min_row=2, min_col=col, max_col=col):
            cell.number_format = fmt
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def write_excel(path: Path, start: date, end: date, summary, daily, products, lines: list[Line]) -> None:
    def prod(pid, channel="", channel_sku=""):
        sku, title = products.get(pid, ("", "")) if pid else ("", "")
        # Wayfair/Walmart/eBay dùng SKU nội bộ làm SKU kênh; prd_product thiếu một số product_id
        if not sku and channel != "Amazon":
            sku = channel_sku
        return sku, title

    wb = Workbook()
    wb.remove(wb.active)
    _sheet(wb, "Tổng hợp",
           ["Kênh", "Tài khoản", "Quốc gia", "Fulfillment", "Tiền tệ", "product_id", "SKU nội bộ", "Tên sản phẩm",
            "SKU kênh", "ASIN / Wayfair SKU / eBay item", "Số đơn", "Units", "Số ngày có bán",
            "Median", "Mode", "Median (USD)", "Ngày bán đầu", "Ngày bán cuối"],
           [10, 14, 9, 12, 8, 10, 12, 45, 30, 18, 9, 9, 10, 11, 11, 12, 12, 12],
           [(k[0], k[1], k[2], k[3], k[4], k[5], *prod(k[5], k[0], k[6]), k[6], mid,
             m["orders"], m["units"], m["days"], m["median"], m["mode"], m["median_usd"], m["first"], m["last"])
            for k, mid, m in summary],
           money_cols={14, 15, 16}, date_cols={17, 18})
    _sheet(wb, "Median theo ngày",
           ["Ngày", "Kênh", "Tài khoản", "Quốc gia", "Fulfillment", "Tiền tệ", "product_id", "SKU nội bộ",
            "SKU kênh", "Số đơn", "Units", "Median", "Median (USD)"],
           [12, 10, 14, 9, 12, 8, 10, 12, 30, 9, 9, 11, 12],
           [(d, k[0], k[1], k[2], k[3], k[4], k[5], prod(k[5], k[0], k[6])[0], k[6], m["orders"], m["units"], m["median"],
             m["median_usd"]) for d, k, m in daily],
           money_cols={12, 13}, date_cols={1})

    ws = wb.create_sheet("Ghi chú")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 110
    counts = Counter(ln.channel for ln in lines)
    notes = [
        ("Khoảng ngày đặt hàng", f"{start} đến {end - timedelta(days=1)} ({(end - start).days} ngày)"),
        ("Tạo lúc", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Số dòng đơn đã dùng", ", ".join(f"{c}: {n:,}" for c, n in sorted(counts.items()))),
        ("Amazon", "Giá sau khuyến mãi = (item_price − promotion_discount) / quantity_ordered. Bỏ đơn Canceled, "
                   "dòng chưa có giá (thường là đơn Pending) và đơn MCF (Non-Amazon). Nguồn: s__amazon_orders + details."),
        ("Wayfair", "Giá wholesale bán cho Wayfair (wholesale_price), KHÔNG phải giá khách lẻ trả trên Wayfair. "
                    "Units = quantity − cancelled_quantity. Bỏ PO CANCELLED/REJECTED và đơn REPLACEMENT. "
                    "Dropship và CastleGate tách dòng riêng."),
        ("Walmart", "Giá = charge_amount / order_quantity của dòng PRODUCT (charge_amount là tổng dòng). Bỏ dòng Cancelled."),
        ("eBay", "Giá = transaction_price. Bỏ đơn Cancelled. Số đơn ít nên median/mode kém ổn định."),
        ("Median / Mode", "Tính theo đơn vị bán: dòng 2 units được đếm 2 lần. Mode = giá có nhiều units nhất "
                          "(làm tròn 2 số lẻ), hòa thì lấy giá bán gần nhất."),
        ("USD", "Quy đổi từng dòng theo tỷ giá ngày đặt hàng (exchange_rate_usd) rồi mới lấy median. "
                "Ô trống = thiếu tỷ giá ngày đó."),
        ("Lưu ý dữ liệu", "Amazon Infideals-US và Hurav-US gần như không còn đơn sau 06/2026 trong nguồn đơn hàng. "
                          "product_id trống = sàn chưa map được sản phẩm nội bộ. Một số product_id không có trong "
                          "prd_product nên thiếu tên sản phẩm (Wayfair/Walmart/eBay vẫn hiện SKU nội bộ = SKU kênh)."),
    ]
    for k, v in notes:
        ws.append((k, v))
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        ws.cell(row=ws.max_row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--end", type=date.fromisoformat, default=date.today(),
                    help="Ngày kết thúc (không tính), mặc định hôm nay")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    end = args.end
    start = end - timedelta(days=args.days)
    out = args.out or ROOT_DIR / "exports" / f"gia_ban_sku_{start:%Y%m%d}_{end - timedelta(days=1):%Y%m%d}.xlsx"

    lines = load_lines(start, end)
    attach_usd(lines, start, end)
    summary, daily = summarize(lines)
    write_excel(out, start, end, summary, daily, load_products(), lines)
    print(f"{len(lines):,} dòng đơn -> {len(summary):,} SKU x kênh, {len(daily):,} dòng theo ngày: {out}")


if __name__ == "__main__":
    main()
