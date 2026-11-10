"""Báo cáo bán hàng Shopify (website DHIntra.com, Megsu.com, Tranquillo AU). Cùng cấu trúc trả về với app/reports.py.

Nguồn: fact_shop_line (etl/sql/77_shop_sales.sql). sales = doanh số sau giảm giá, chưa trừ hoàn tiền, chưa gồm thuế /
phí ship. Hoàn tiền tính vào ngày đặt đơn. Nước = nước của store. Chi phí quảng cáo (Google, Meta…) do team nhập tay theo
tháng (cfg_shop_ad_spend, tab Shopify › Chi phí QC), chia đều cho các ngày trong tháng; chỉ có TACoS, không có ACoS vì
không biết doanh số nào đến từ QC.
"""
import calendar
from datetime import date, timedelta

from app import insights
from app.db import fetch_all
from app.filters import Filters, Where
from app.metrics import SHOP_COLUMNS, col, with_ratios
from app.reports import _limit, _table
from app.viz import FULL_MAX, chart, series, top_n

CUSTOMER_LABELS = {"NEW": "Khách mới", "RETURNING": "Khách quay lại", "UNKNOWN": "Không rõ (không có mã khách)"}
SOURCE_LABELS = {"web": "Website", "shopify-collective-automatic-payments": "Shopify Collective",
                 "shopify_draft_order": "Đơn tạo tay (draft)", "pos": "POS", "faire": "Faire", "ebay": "eBay",
                 "temu": "Temu"}
COLORS = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]

SUMS = """COUNT(DISTINCT l.order_id) AS orders, SUM(l.units) AS units, SUM(l.gross_usd) AS gross,
          SUM(l.discount_usd) AS discount, SUM(l.net_usd) AS sales, SUM(l.refund_usd) AS refunds,
          SUM(l.refund_units) AS refund_units"""
FROM = """FROM fact_shop_line l
          LEFT JOIN dim_product p ON p.product_id = l.product_id
          LEFT JOIN map_channel_node m ON m.sales_channel_id = l.sales_channel_id"""
STORE = "COALESCE(MAX(m.title), CONCAT('Kênh ', l.sales_channel_id))"

PLATFORMS = [("google", "Google"), ("meta", "Meta"), ("other", "Khác")]

KPI_DEF = [  # [khóa, nhãn, định dạng, hướng tốt (+1 tăng là tốt, -1 giảm là tốt, 0 trung tính), chỉ số chính]
    ["sales", "Doanh số (sau giảm giá)", "money", 1, True], ["orders", "Đơn", "int", 1, True],
    ["aov", "Giá trị đơn (AOV)", "money", 1, True], ["spend", "Chi phí QC (nhập tay)", "money", -1, True],
    ["tacos", "TACoS", "pct", -1, True], ["refund_rate", "% hoàn tiền", "pct", -1, False],
    ["units", "Units", "int", 1, False], ["gross", "DS trước giảm giá", "money", 1, False],
    ["discount", "Giảm giá", "money", 0, False], ["discount_rate", "% giảm giá", "pct", 0, False],
    ["refunds", "Hoàn tiền", "money", -1, False], ["net_after_refund", "DS sau hoàn tiền", "money", 1, False],
    ["new_share", "% đơn khách mới", "pct", 0, False],
]


def shop_where(f: Filters, start: date | None = None) -> Where:
    """Lọc fact_shop_line l (cần LEFT JOIN dim_product p): ngày, nước, nhóm SP / brand."""
    w = Where()
    w._n = 6000
    w.add("l.report_date BETWEEN :start AND :end", start=start or f.start, end=f.end)
    w.add_in("l.country_code", f.countries)
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    return w


def source_label(source: str | None) -> str:
    s = (source or "").strip()
    if not s:
        return "(không rõ)"
    if s.isdigit():
        return f"App #{s}"
    return SOURCE_LABELS.get(s.lower(), s)


def period_key(f: Filters, date_col: str = "l.report_date") -> tuple[str, str]:
    """Trục thời gian của đồ thị: theo ngày nếu kỳ ≤ 62 ngày, ngược lại theo tuần (thứ Hai)."""
    if (f.end - f.start).days < 62:
        return date_col, "ngày"
    return f"DATE_SUB({date_col}, INTERVAL WEEKDAY({date_col}) DAY)", "tuần"


def period_labels(f: Filters, weekly: bool) -> list[str]:
    d = f.start - timedelta(days=f.start.weekday()) if weekly else f.start
    out = []
    while d <= f.end:
        out.append(d.isoformat())
        d += timedelta(days=7 if weekly else 1)
    return out


def ad_spend_daily(f: Filters) -> list[dict] | None:
    """Chi phí QC Shopify nhập tay theo tháng, chia đều cho các ngày trong tháng: [{d, sales_channel_id, cc, spend}] trong
    kỳ và nước đang lọc. None khi không tính được: lọc nhóm SP / brand (chi phí không gắn với sản phẩm) hoặc kỳ chưa nhập
    tháng nào."""
    if f.group_ids or f.brand_ids:
        return None
    w = Where()
    w.add("s.month BETWEEN :m0 AND :m1", m0=f.start.replace(day=1), m1=f.end)
    w.add_in("m.country_code", f.countries)
    rows = fetch_all(f"""SELECT s.month, s.sales_channel_id, m.country_code AS cc, SUM(s.spend_usd) AS spend
        FROM cfg_shop_ad_spend s JOIN map_channel_node m ON m.sales_channel_id = s.sales_channel_id
        {w.sql()} GROUP BY s.month, s.sales_channel_id, m.country_code""", w.params)
    if not rows:
        return None
    out = []
    for r in rows:
        days = calendar.monthrange(r["month"].year, r["month"].month)[1]
        per_day = float(r["spend"] or 0) / days
        d, last = max(f.start, r["month"]), min(f.end, r["month"].replace(day=days))
        while d <= last:
            out.append({"d": d, "sales_channel_id": r["sales_channel_id"], "cc": r["cc"], "spend": per_day})
            d += timedelta(days=1)
    return out


def sum_spend(daily: list[dict] | None, key=None) -> dict | float | None:
    """Cộng chi phí QC theo `key(row)` (vd lambda r: r["cc"]), hoặc tổng nếu không có key. None nếu chưa nhập."""
    if daily is None:
        return None
    if key is None:
        return sum(r["spend"] for r in daily)
    out: dict = {}
    for r in daily:
        out[key(r)] = out.get(key(r), 0.0) + r["spend"]
    return out


def add_spend(row: dict, spend: float | None) -> dict:
    """Gắn chi phí QC và TACoS (= chi phí ÷ doanh số sau giảm giá) vào một dòng Shopify đã có `sales`."""
    row["spend"] = spend
    row["tacos"] = (spend / row["sales"]) if spend is not None and row.get("sales") else None
    row["acos"] = row["roas"] = row["cpa"] = None
    return row


def _kpi(f: Filters) -> dict:
    w = shop_where(f)
    row = fetch_all(f"""SELECT {SUMS},
            COUNT(DISTINCT CASE WHEN l.customer_type = 'NEW' THEN l.order_id END) AS new_orders,
            COUNT(DISTINCT CASE WHEN l.customer_type <> 'UNKNOWN' THEN l.order_id END) AS known_orders
        {FROM} {w.sql()}""", w.params)[0]
    with_ratios(row)
    row["new_share"] = (row["new_orders"] / row["known_orders"]) if row.get("known_orders") else None
    return add_spend(row, sum_spend(ad_spend_daily(f)))


def shop_overview(f: Filters, opts: dict) -> dict:
    cur, prev = _kpi(f), _kpi(f.previous_period())
    w = shop_where(f)
    pk, unit = period_key(f)
    labels = period_labels(f, unit == "tuần")

    by_period = fetch_all(f"""SELECT {pk} AS d, l.sales_channel_id, {STORE} AS store, SUM(l.net_usd) AS sales
        {FROM} {w.sql()} GROUP BY {pk}, l.sales_channel_id""", w.params)
    stores = sorted({(r["sales_channel_id"], r["store"]) for r in by_period},
                    key=lambda s: -sum(r["sales"] or 0 for r in by_period if r["sales_channel_id"] == s[0]))
    idx = {d: i for i, d in enumerate(labels)}
    store_series = []
    for n, (cid, name) in enumerate(stores):
        vals = [0.0] * len(labels)
        for r in by_period:
            if r["sales_channel_id"] == cid and r["d"].isoformat() in idx:
                vals[idx[r["d"].isoformat()]] += r["sales"] or 0
        store_series.append(series(name, COLORS[n % len(COLORS)], vals))

    cust = fetch_all(f"""SELECT {pk} AS d, l.customer_type, COUNT(DISTINCT l.order_id) AS orders
        {FROM} {w.sql()} GROUP BY {pk}, l.customer_type""", w.params)
    cust_series = []
    for key, color in (("NEW", "c1"), ("RETURNING", "c2"), ("UNKNOWN", "n1")):
        vals = [0] * len(labels)
        for r in cust:
            if r["customer_type"] == key and r["d"].isoformat() in idx:
                vals[idx[r["d"].isoformat()]] += r["orders"] or 0
        cust_series.append(series(CUSTOMER_LABELS[key], color, vals))

    by_store = fetch_all(f"""SELECT l.sales_channel_id, {STORE} AS store, MAX(l.country_code) AS country, {SUMS},
            COUNT(DISTINCT CASE WHEN l.customer_type = 'NEW' THEN l.order_id END) AS new_orders
        {FROM} {w.sql()} GROUP BY l.sales_channel_id ORDER BY sales DESC""", w.params)
    by_source = fetch_all(f"""SELECT COALESCE(l.source_name, '') AS source_name, {SUMS}
        {FROM} {w.sql()} GROUP BY COALESCE(l.source_name, '') ORDER BY sales DESC""", w.params)
    by_cust = fetch_all(f"""SELECT l.customer_type, {SUMS} {FROM} {w.sql()}
        GROUP BY l.customer_type ORDER BY FIELD(l.customer_type, 'NEW', 'RETURNING', 'UNKNOWN')""", w.params)
    by_date = fetch_all(f"""SELECT l.report_date AS date, {SUMS} {FROM} {w.sql()}
        GROUP BY l.report_date ORDER BY l.report_date""", w.params)
    top = fetch_all(f"""SELECT p.product_sku, MAX(p.title) AS product, SUM(l.net_usd) AS sales
        {FROM} {w.sql()} AND l.product_id > 0 GROUP BY p.product_sku ORDER BY sales DESC LIMIT {FULL_MAX}""", w.params)
    for rows in (by_store, by_source, by_cust, by_date):
        for r in rows:
            with_ratios(r)
    for r in by_store:
        r["new_share"] = (r["new_orders"] / r["orders"]) if r.get("orders") else None
    daily = ad_spend_daily(f)
    store_spend = sum_spend(daily, lambda r: r["sales_channel_id"]) or {}
    date_spend = sum_spend(daily, lambda r: r["d"]) or {}
    spend_cols = []
    if daily is not None:
        for r in by_store:
            add_spend(r, store_spend.get(r["sales_channel_id"], 0.0))
        for r in by_date:
            add_spend(r, date_spend.get(r["date"], 0.0))
        spend_cols = [col("spend", "Chi phí QC", "money"), col("tacos", "TACoS", "pct")]
    if daily is None:
        spend_note = (" Chi phí QC không tính khi lọc nhóm SP / brand (chi phí nhập theo store, không theo sản phẩm)."
                      if f.group_ids or f.brand_ids else
                      " Kỳ này chưa nhập chi phí QC: nhập ở tab Chi phí QC để có TACoS.")
    else:
        spend_note = (" Chi phí QC (Google, Meta…) nhập tay theo tháng ở tab Chi phí QC, chia đều cho các ngày trong tháng; "
                      "TACoS = chi phí QC ÷ doanh số. Store / tháng chưa nhập được tính là 0.")
    for r in by_source:
        r["source"] = source_label(r["source_name"])
    for r in by_cust:
        r["customer"] = CUSTOMER_LABELS.get(r["customer_type"], r["customer_type"])

    viz = [
        chart("sales_by_store", f"Doanh số theo store, theo {unit}", "bar_stacked", labels, store_series, unit="money",
              subtitle="Doanh số sau giảm giá, chưa trừ hoàn tiền, chưa gồm thuế và phí ship. USD theo tỷ giá ngày đặt."),
        chart("orders_by_customer", f"Số đơn: khách mới và khách quay lại, theo {unit}", "bar_stacked", labels,
              cust_series, unit="int",
              subtitle="Khách mới = đơn đầu tiên của mã khách trong store (dữ liệu đơn có từ 01/2025, nên khách mua "
                       "trước đó bị tính là khách mới)."),
        chart("by_source", "Doanh số theo nguồn đơn", "hbar", [r["source"] for r in by_source],
              [series("Doanh số", "c1", [r["sales"] for r in by_source])], unit="money", tables=["by_source"],
              label_filters=[{"cols": {"source": [r["source"]]}} for r in by_source],
              subtitle="Website = đơn khách tự đặt trên web. Shopify Collective = đơn qua cửa hàng đối tác. "
                       "App #… = đơn từ ứng dụng / kênh bán gắn với Shopify (nguồn chỉ ghi mã số)."),
    ]
    top_viz = top_n(top, 10, lambda rows: chart(
        "top_products", f"{len(rows)} sản phẩm doanh số cao nhất", "hbar",
        [f"{r['product_sku']} · {insights.short(r['product'] or '', 22)}" for r in rows],
        [series("Doanh số", "c2", [r["sales"] for r in rows])], unit="money",
        goto={"tab": "shop_products", "table": "products"},
        label_filters=[{"opts": {"level": "product"}, "cols": {"product_sku": [r["product_sku"]]}} for r in rows],
        subtitle="Bấm một thanh để xem sản phẩm đó ở tab Sản phẩm."))
    if top_viz:
        viz.append(top_viz)

    extra = ("orders", "gross", "discount", "refunds", "refund_units")
    return {
        "title": "Tổng quan bán hàng Shopify",
        "note": "Doanh số = tiền hàng sau giảm giá (chưa trừ hoàn tiền, chưa gồm thuế / phí ship), USD theo tỷ giá ngày "
                "đặt. Hoàn tiền tính vào ngày đặt đơn." + spend_note,
        "viz": viz,
        "kpis": {"current": cur, "previous": prev, "def": KPI_DEF},
        "tables": [
            _table("by_store", "Theo store", [col("store", "Store"), col("country", "Nước")] + SHOP_COLUMNS + spend_cols
                   + [col("new_share", "% đơn khách mới", "pct")], by_store, extra_additive=extra),
            _table("by_source", "Theo nguồn đơn", [col("source", "Nguồn")] + SHOP_COLUMNS, by_source, extra_additive=extra),
            _table("by_customer", "Khách mới / quay lại", [col("customer", "Loại khách")] + SHOP_COLUMNS, by_cust,
                   extra_additive=extra),
            _table("by_date", "Theo ngày", [col("date", "Ngày", "date")] + SHOP_COLUMNS + spend_cols, by_date,
                   extra_additive=extra),
        ],
    }


def shop_products(f: Filters, opts: dict) -> dict:
    level = "group" if opts.get("level") == "group" else "product"
    prev = f.previous_period()
    w = shop_where(f, start=prev.start)
    w.add("1 = 1", cur_start=f.start)
    if level == "group":
        key, select = "p.group_id, l.country_code", "COALESCE(MAX(p.group_name), '(chưa gán nhóm)') AS group_name"
    else:
        key = "l.product_id, l.country_code"
        select = ("l.product_id, COALESCE(MAX(p.product_sku), MAX(l.sku), '(không map)') AS product_sku, "
                  "MAX(p.title) AS product, MAX(p.group_name) AS group_name, MAX(p.brand_name) AS brand_name")
    cur = "l.report_date >= :cur_start"
    rows = fetch_all(f"""
        SELECT {select}, l.country_code AS country,
               SUM(CASE WHEN {cur} THEN l.units END) AS units, SUM(CASE WHEN {cur} THEN l.gross_usd END) AS gross,
               SUM(CASE WHEN {cur} THEN l.discount_usd END) AS discount, SUM(CASE WHEN {cur} THEN l.net_usd END) AS sales,
               SUM(CASE WHEN {cur} THEN l.refund_usd END) AS refunds,
               SUM(CASE WHEN {cur} THEN l.refund_units END) AS refund_units,
               COUNT(DISTINCT CASE WHEN {cur} THEN l.order_id END) AS orders,
               SUM(CASE WHEN NOT ({cur}) THEN l.net_usd END) AS sales_prev
        {FROM} {w.sql()}
        GROUP BY {key}
        HAVING SUM(CASE WHEN {cur} THEN l.units END) <> 0 OR sales_prev <> 0
        ORDER BY SUM(CASE WHEN {cur} THEN l.net_usd END) DESC
        LIMIT {_limit(opts, 2000)}""", w.params)
    for r in rows:
        with_ratios(r)
        r["sales_growth"] = ((r["sales"] - r["sales_prev"]) / r["sales_prev"]) if r.get("sales_prev") else None
    stock_cols = []
    if level == "product":
        status = insights.stock_status({(r["product_id"], r["country"]) for r in rows})
        for r in rows:
            s = status.get((r["product_id"], r["country"]), {})
            r["stock"] = insights.stock_group(s.get("status"))[0] if s else None
            r["days_cover"] = s.get("days_cover")
        stock_cols = [col("stock", "Tồn kho (cả nước)"), col("days_cover", "Đủ bán (ngày)", "num2")]
    name_cols = ([col("group_name", "Nhóm SP")] if level == "group" else
                 [col("product_sku", "SKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"), col("brand_name", "Brand")])
    cols = (name_cols + [col("country", "Nước"), col("units", "Units", "int"), col("sales", "Doanh số", "money"),
                         col("sales_prev", "DS kỳ trước", "money"), col("sales_growth", "± kỳ trước", "pct"),
                         col("avg_price", "Giá bán BQ", "money"), col("discount", "Giảm giá", "money"),
                         col("discount_rate", "% giảm giá", "pct"), col("refunds", "Hoàn tiền", "money"),
                         col("refund_units", "Units hoàn", "int"), col("refund_rate", "% hoàn tiền", "pct")] + stock_cols)
    name = "group_name" if level == "group" else "product_sku"
    top_viz = top_n(rows, 15, lambda top: chart(
        "top", f"{len(top)} {'nhóm SP' if level == 'group' else 'sản phẩm'} doanh số cao nhất", "hbar",
        [f"{r[name]} · {r['country']}" for r in top],
        [series("Doanh số", "c1", [r["sales"] for r in top]),
         series("Kỳ trước", "n1", [r["sales_prev"] or 0 for r in top])], unit="money", tables=["products"],
        label_filters=[{"cols": {name: [r[name]], "country": [r["country"]]}} for r in top],
        subtitle="Bấm một thanh để lọc bảng bên dưới."))
    viz = [top_viz] if top_viz else []
    return {
        "title": "Sản phẩm bán trên Shopify",
        "note": "Doanh số sau giảm giá, chưa trừ hoàn tiền. Kỳ trước = cùng số ngày ngay trước kỳ đang xem. "
                "Tồn kho = kho nội bộ + CastleGate của nước (nút ALL-<nước>), website bán từ kho nội bộ.",
        "viz": viz,
        "tables": [_table("products", "Theo nhóm SP" if level == "group" else "Theo sản phẩm", cols, rows,
                          extra_additive=("gross", "discount", "refunds", "refund_units", "sales_prev"))],
    }


SHOP_REPORTS = {
    "shop_overview": shop_overview,
    "shop_products": shop_products,
}
