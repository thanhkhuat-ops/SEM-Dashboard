"""Báo cáo quảng cáo Wayfair Sponsored Products. Cùng cấu trúc trả về với app/reports.py.

Quy ước: sales = doanh số quy đổi theo giá sỉ (tiền Wayfair trả công ty), dùng cho ACoS/ROAS/TACoS;
retail_sales = doanh số theo giá bán lẻ trên Wayfair. Quy đổi view-through 14 ngày. Tiền tệ USD.
"""
from datetime import date, timedelta

from app.db import fetch_all
from app import insights
from app.viz import chart as viz_chart, series as viz_series, trend_charts
from app.filters import Filters, Where, wf_where
from app.metrics import (PROFIT_COLUMNS, WF_METRIC_COLUMNS, WF_TACOS_COLUMNS, col, grand_cols, kpi_series, wf_sum_cols,
                         with_ratios)
from app.reports import STATE_BY_COL, WAYFAIR, with_state, _label_class, _limit, _order, _table, _term_where, harvest, keyword_analysis, ngrams

CAMPAIGN_JOIN = "JOIN dim_wf_campaign c ON c.campaign_id = f.campaign_id"
ACCOUNT_LABEL = "CONCAT(COALESCE(MAX(wa.short_name), MAX(f.account_id)), ' - ', MAX(f.country_code))"


# Đơn Wayfair không có Wayfair SKU nên doanh số listing lấy qua các biến thể (product) của listing trong cùng tài
# khoản; biến thể thuộc nhiều listing thì chia đều doanh số cho các listing đó để không đếm trùng.
LISTING_SHARE = """JOIN (SELECT m.listing_id, m.product_id, l.account_id,
                         1 / COUNT(*) OVER (PARTITION BY m.product_id, l.account_id) AS w
                  FROM map_wf_listing_product m JOIN dim_wf_listing l ON l.listing_id = m.listing_id) x
          ON x.product_id = t.product_id AND x.account_id = t.account_id"""


def wf_total_sales(f: Filters, group_by: str | None = None) -> list[dict]:
    """Tổng doanh số giá sỉ từ đơn Wayfair. group_by: None | 'account' | 'date' | 'listing' | 'group' | 'order_type'."""
    w = Where().add("t.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    w._n = 4000
    w.add_in("CONCAT(t.account_id, '-', t.country_code)", f.wf_accounts)
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    key = {
        None: None,
        "account": "t.account_id, t.country_code",
        "date": "t.report_date",
        "listing": "x.listing_id",
        "group": "p.group_id",
        "order_type": "t.order_type",
        "product_country": "t.product_id, t.country_code",
    }[group_by]
    select = f"{key} AS k, " if key else ""
    wt = "x.w" if group_by == "listing" else "1"
    if group_by in ("account", "product_country"):  # khóa nhiều cột: trả từng cột
        select = key + ", "
    return fetch_all(f"""
        SELECT {select} SUM(t.sales_usd * {wt}) AS total_sales, SUM(t.units * {wt}) AS total_units,
               SUM(t.order_lines * {wt}) AS order_lines,
               SUM(CASE WHEN t.order_type = 'castle_gate' THEN t.order_lines * {wt} END) AS cg_lines,
               SUM(CASE WHEN t.order_type = 'castle_gate' THEN t.units * {wt} END) AS cg_units,
               SUM(CASE WHEN t.order_type = 'castle_gate' THEN t.sales_usd * {wt} END) AS cg_sales
        FROM fact_wf_total_sales_daily t
        LEFT JOIN dim_product p ON p.product_id = t.product_id
        {LISTING_SHARE if group_by == "listing" else ""}
        {w.sql()} {'GROUP BY ' + key if key else ''}""", w.params)


def _ts_map(f: Filters, group_by: str) -> dict:
    return {r["k"]: r["total_sales"] for r in wf_total_sales(f, group_by)}


# ---------------------------------------------------------------- tổng quan

# chi phí theo listing: gộp báo cáo sản phẩm và báo cáo keyword để có đủ chi phí của mọi listing
LISTING_SRC = """(SELECT report_date, campaign_id, listing_id, account_id, country_code, impressions, clicks, cost_usd,
                      orders, units, sales_usd, retail_sales_usd FROM fact_wf_product_daily
               WHERE report_date BETWEEN :start AND :end
               UNION ALL
               SELECT report_date, campaign_id, listing_id, account_id, country_code, impressions, clicks, cost_usd,
                      orders, units, sales_usd, retail_sales_usd FROM fact_wf_keyword_daily
               WHERE report_date BETWEEN :start AND :end)"""


def _overview_listings(f: Filters) -> list[dict]:
    """Spend / DS QC kỳ này và DS QC kỳ trước theo listing × nước."""
    prev = f.previous_period()
    w = wf_where(insights.same_filters(f, start=prev.start), group_by_listing="l")
    w.add("f.listing_id IS NOT NULL", cur_start=f.start)
    rows = fetch_all(f"""
        SELECT f.listing_id, f.country_code AS country, MAX(l.wayfair_sku) AS wayfair_sku, MAX(l.product_id) AS product_id,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.cost_usd END) AS spend,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.sales_usd END) AS sales,
               SUM(CASE WHEN f.report_date < :cur_start THEN f.sales_usd END) AS sales0,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.clicks END) AS clicks,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.orders END) AS orders,
               COUNT(DISTINCT CASE WHEN f.report_date >= :cur_start AND f.cost_usd > 0 THEN f.report_date END) AS spend_days,
               MIN(CASE WHEN f.report_date >= :cur_start AND f.cost_usd > 0 THEN f.report_date END) AS first_spend
        FROM {LISTING_SRC} f {CAMPAIGN_JOIN}
        LEFT JOIN dim_wf_listing l ON l.listing_id = f.listing_id
        {w.sql()}
        GROUP BY f.listing_id, f.country_code""", w.params)
    for r in rows:
        r["filter_value"] = r["wayfair_sku"] or str(r["listing_id"])
        r["label"] = f"{r['filter_value']} · {r['country']}"
    return rows


def month_daily(f: Filters) -> list[dict]:
    """Spend, DS QC, tổng DS sỉ theo ngày từ đầu tháng của f.end tới f.end (cùng bộ lọc)."""
    first, _, _ = insights.month_window(f.end)
    mf = insights.same_filters(f, start=first)
    w = wf_where(mf)
    rows = fetch_all(f"""SELECT f.report_date AS date, SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
        FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN} {w.sql()} GROUP BY f.report_date""", w.params)
    out = {r["date"]: {"date": r["date"].isoformat(), "spend": r["spend"], "sales": r["sales"], "total_sales": None} for r in rows}
    for d, v in _ts_map(mf, "date").items():
        out.setdefault(d, {"date": d.isoformat(), "spend": 0, "sales": 0})["total_sales"] = v
    return list(out.values())


def month_by_account(f: Filters) -> dict[str, dict]:
    """Spend, DS QC, tổng DS sỉ theo tài khoản (khóa "<account_id>-<nước>") trong khoảng f."""
    w = wf_where(f)
    rows = fetch_all(f"""SELECT CONCAT(f.account_id, '-', f.country_code) AS k, SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
        FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN} {w.sql()} GROUP BY f.account_id, f.country_code""", w.params)
    out = {r["k"]: r for r in rows}
    for r in wf_total_sales(f, "account"):
        k = f"{r['account_id']}-{r['country_code']}"
        out.setdefault(k, {"k": k, "spend": 0, "sales": 0})["total_sales"] = r["total_sales"]
    return out


def account_options() -> list[dict]:
    return fetch_all("""SELECT CONCAT(f.account_id, '-', f.country_code) AS id,
                                 CONCAT(COALESCE(MAX(a.short_name), f.account_id), ' - ', f.country_code) AS label
                         FROM (SELECT DISTINCT account_id, country_code FROM fact_wf_campaign_daily) f
                         LEFT JOIN dim_wf_account a ON a.account_id = f.account_id
                         GROUP BY f.account_id, f.country_code ORDER BY label""")


def _overview_insights(f: Filters, cur: dict, prev: dict, trend: list[dict]) -> tuple[list[dict], list[dict]]:
    """Đồ thị và thẻ thêm cho Tổng quan Wayfair (xem app/insights.py)."""
    label = "DS QC (giá sỉ)"
    rows = _overview_listings(f)
    tot = {(r["product_id"], r["country_code"]): r for r in wf_total_sales(f, "product_country")}
    for r in rows:
        t = tot.get((r["product_id"], r["country"]), {})
        r["total_sales"], r["total_units"] = t.get("total_sales"), t.get("total_units")
        r["fbx_units"] = t.get("cg_units")
    costs, chans = insights.load_costs()
    insights.add_profit(rows, costs, chans, "wayfair")
    status = insights.stock_status({(r["product_id"], r["country"]) for r in rows})
    movers = insights.movers_chart(rows, label, {"goto": {"tab": "wf_products", "table": "products"},
                                                 "opts": {"level": "listing"}, "col": "wayfair_sku"})
    risk_chart, risk_spend, lost, _ = insights.stock_risk(rows, status)
    budget_chart, capped, active = insights.budget_summary(wf_budget(f, {"limit": 5000})["tables"][0]["rows"], "wf_budget")
    daily = month_daily(f)
    month_spend = sum(float(r["spend"] or 0) for r in daily)
    goto = {"goto": {"tab": "wf_products", "table": "products"}, "opts": {"level": "listing"}, "col": "wayfair_sku"}
    target_chart, target_cards = None, []
    if insights.scoped(f):
        target = insights.target_for(insights.load_targets(f.end, "wayfair"), f.wf_accounts or None)
        if target:
            target_chart, target_cards = insights.progress(target, daily, f.end)
    charts = ([target_chart, insights.organic_chart(trend, label)] + trend_charts(trend, label)
              + insights.bridge_charts(cur, prev, label)
              + [movers, insights.profit_chart(rows, goto), insights.matrix_chart(rows, status, label),
                 insights.no_order_chart(rows, f.end, 14, goto), risk_chart, budget_chart])
    spend = float(cur.get("spend") or 0)
    cards = (target_cards + insights.profit_cards(rows, spend)
             + insights.extra_cards(f, month_spend, spend, risk_spend, lost, capped, active))
    return [c for c in charts if c], cards


def wf_overview(f: Filters, opts: dict) -> dict:
    def kpi_block(ff: Filters) -> dict:
        w = wf_where(ff)
        row = fetch_all(f"SELECT {wf_sum_cols()} FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN} {w.sql()}", w.params)[0]
        row["total_sales"] = (wf_total_sales(ff)[0] or {}).get("total_sales")
        return with_ratios(row)

    cur, prev = kpi_block(f), kpi_block(f.previous_period())
    w = wf_where(f)
    trend = fetch_all(f"""SELECT f.report_date AS date, {wf_sum_cols()} FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN}
        {w.sql()} GROUP BY f.report_date ORDER BY f.report_date""", w.params)
    ts_date = _ts_map(f, "date")
    for r in trend:
        r["total_sales"] = ts_date.get(r["date"])
        with_ratios(r)
        r["date"] = r["date"].isoformat()
    if cur.get("total_sales"):  # khớp với đồ thị: chỉ trừ DS QC của ngày đã có doanh số đơn hàng
        cur["organic_sales"] = insights.organic_total(trend)

    by_acc = fetch_all(f"""SELECT f.account_id, f.country_code, {ACCOUNT_LABEL} AS account, {wf_sum_cols()}
        FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN} LEFT JOIN dim_wf_account wa ON wa.account_id = f.account_id
        {w.sql()} GROUP BY f.account_id, f.country_code ORDER BY spend DESC""", w.params)
    ts_acc = {(r["account_id"], r["country_code"]): r["total_sales"] for r in wf_total_sales(f, "account")}
    for r in by_acc:
        r["total_sales"] = ts_acc.get((r["account_id"], r["country_code"]))
        with_ratios(r)

    by_type = fetch_all(f"""SELECT COALESCE(f.targeting_type, '?') AS targeting_type, {wf_sum_cols()}
        FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN} {w.sql()}
        GROUP BY COALESCE(f.targeting_type, '?') ORDER BY spend DESC""", w.params)
    spend_total = sum(r["spend"] or 0 for r in by_type) or None
    for r in by_type:
        with_ratios(r)
        r["spend_share"] = (r["spend"] / spend_total) if spend_total else None

    viz, cards = _overview_insights(f, cur, prev, trend)
    fulfil_chart, by_fulfil = _fulfilment(f)
    if fulfil_chart:
        viz.insert(next((i + 1 for i, c in enumerate(viz) if c["key"] == "organic"), 0), fulfil_chart)

    return {
        "title": "Tổng quan quảng cáo Wayfair",
        "viz": viz,
        "cards": cards,
        "note": "Doanh số quảng cáo, ACoS, ROAS và TACoS tính theo giá sỉ (tiền Wayfair trả công ty); "
                "cột giá lẻ để tham khảo. Quy đổi view-through 14 ngày nên không so trực tiếp với ACoS Amazon.",
        "kpis": {"current": cur, "previous": prev, "series": kpi_series(trend, f.start, f.end)},
        "charts": {"trend": trend},
        "tables": [
            _table("by_account", "Theo tài khoản (kèm TACoS)", [col("account", "Tài khoản")] + WF_METRIC_COLUMNS
                   + WF_TACOS_COLUMNS, by_acc, extra_additive=("total_sales",)),
            _table("by_targeting", "Theo loại targeting", [col("targeting_type", "Targeting"),
                   col("spend_share", "% Spend", "pct")] + WF_METRIC_COLUMNS, by_type),
        ] + ([by_fulfil] if by_fulfil else []),
    }


FULFIL_KEYS = ("order_lines", "cg_lines", "total_units", "cg_units", "total_sales", "cg_sales")
FULFIL_COLUMNS = [col("account", "Tài khoản"), col("cg_orders", "Đơn CastleGate", "int"),
                  col("ds_orders", "Đơn Dropship", "int"), col("cg_order_share", "% đơn CG", "pct"),
                  col("cg_order_share_prev", "% đơn CG kỳ trước", "pct"), col("cg_units", "Units CG", "int"),
                  col("ds_units", "Units Dropship", "int"), col("cg_sales", "DS sỉ CG", "money"),
                  col("ds_sales", "DS sỉ Dropship", "money"), col("cg_sales_share", "% DS CG", "pct"),
                  col("cg_aov", "Giá trị dòng đơn CG", "money"), col("ds_aov", "Giá trị dòng đơn Dropship", "money")]


def _fulfil_row(r: dict) -> dict:
    """Tách tổng (CastleGate + Dropship) thành hai phần. Đơn = dòng đơn (gần như trùng số PO)."""
    n, cg = float(r.get("order_lines") or 0), float(r.get("cg_lines") or 0)
    sales, cg_s = float(r.get("total_sales") or 0), float(r.get("cg_sales") or 0)
    units, cg_u = float(r.get("total_units") or 0), float(r.get("cg_units") or 0)
    return {"cg_orders": cg, "ds_orders": n - cg, "cg_order_share": cg / n if n else None,
            "cg_units": cg_u, "ds_units": units - cg_u, "cg_sales": cg_s, "ds_sales": sales - cg_s,
            "cg_sales_share": cg_s / sales if sales else None,
            "cg_aov": cg_s / cg if cg else None, "ds_aov": (sales - cg_s) / (n - cg) if n > cg else None}


def _fulfilment(f: Filters) -> tuple[dict | None, dict | None]:
    """Tỷ trọng đơn CastleGate / Dropship: đồ thị cột chồng theo ngày (theo tuần nếu kỳ dài) + bảng theo tài khoản ×
    nước của khách, cùng bộ lọc tài khoản / nhóm SP / brand với Tổng DS sỉ. Nguồn: s__wayfair_orders.order_type."""
    days = wf_total_sales(f, "date")
    if not any(r.get("order_lines") for r in days):
        return None, None
    weekly = (f.end - f.start).days >= 62
    buckets: dict[date, list[float]] = {}
    for r in days:
        d = r["k"] - timedelta(days=r["k"].weekday()) if weekly else r["k"]
        b = buckets.setdefault(d, [0.0, 0.0])
        b[0] += float(r.get("cg_lines") or 0)
        b[1] += float(r.get("order_lines") or 0) - float(r.get("cg_lines") or 0)
    labels = sorted(buckets)
    cg, ds = [buckets[d][0] for d in labels], [buckets[d][1] for d in labels]
    share = [(a / (a + b)) if a + b else None for a, b in zip(cg, ds)]
    n_all = sum(cg) + sum(ds)
    chart = viz_chart("fulfilment", "Đơn hàng CastleGate và Dropship theo " + ("tuần" if weekly else "ngày"),
                      "bar_stacked", [d.isoformat() for d in labels],
                      [viz_series("CastleGate", "c1", cg), viz_series("Dropship", "c4", ds),
                       viz_series("% đơn CastleGate", "n2", share, line=True, unit="pct",
                                  total=sum(cg) / n_all if n_all else None)],
                      unit="int",
                      subtitle="Số dòng đơn Wayfair (bỏ PO hủy / bị từ chối và đơn thay thế) theo hình thức giao: "
                               "CastleGate = Wayfair giao từ kho CastleGate, Dropship = công ty tự giao từ kho nội bộ. "
                               "Đường = % đơn CastleGate (trục phải). Chi tiết theo tài khoản ở bảng 'Theo hình thức "
                               "giao hàng'.")
    labels_acc = {r["account_id"]: r["short_name"] for r in fetch_all("SELECT account_id, short_name FROM dim_wf_account")}
    cur = {(r["account_id"], r["country_code"]): r for r in wf_total_sales(f, "account")}
    prev = {(r["account_id"], r["country_code"]): r for r in wf_total_sales(f.previous_period(), "account")}
    rows = []
    for k in sorted(cur, key=lambda k: -float(cur[k].get("total_sales") or 0)):
        row = {"account": f"{labels_acc.get(k[0], k[0])} - {k[1]}", **_fulfil_row(cur[k])}
        if k in prev:
            row["cg_order_share_prev"] = _fulfil_row(prev[k])["cg_order_share"]
        rows.append(row)
    table = _table("by_fulfilment", "Theo hình thức giao hàng (CastleGate / Dropship)", FULFIL_COLUMNS, rows,
                   with_totals=False)

    def total(src):
        return {k: sum(float(r.get(k) or 0) for r in src.values()) for k in FULFIL_KEYS}
    table["totals"] = {"account": "Tổng", **_fulfil_row(total(cur)),
                       "cg_order_share_prev": _fulfil_row(total(prev))["cg_order_share"]}
    return chart, table


# ---------------------------------------------------------------- campaign

def wf_campaigns(f: Filters, opts: dict) -> dict:
    w = wf_where(f)
    rows = fetch_all(f"""
        SELECT f.campaign_id, f.country_code, {ACCOUNT_LABEL} AS account, MAX(c.campaign_name) AS campaign_name,
               MAX(f.targeting_type) AS targeting_type, MAX(c.state) AS campaign_state, MAX(c.daily_cap) AS daily_cap,
               MAX(m.group_name) AS group_name, {wf_sum_cols()}, {grand_cols(wf_sum_cols())}
        FROM fact_wf_campaign_daily f {CAMPAIGN_JOIN}
        LEFT JOIN dim_wf_account wa ON wa.account_id = f.account_id
        LEFT JOIN (SELECT g.campaign_id, p.group_name FROM map_wf_campaign_group g
                   JOIN (SELECT DISTINCT group_id, group_name FROM dim_product) p ON p.group_id = g.group_id
                   WHERE g.is_dominant = 1) m ON m.campaign_id = f.campaign_id
        {w.sql()}
        GROUP BY f.campaign_id, f.country_code
        ORDER BY {_order(opts)} LIMIT {_limit(opts)}""", w.params)
    for r in rows:
        with_ratios(r)
    with_state(rows, [("Campaign", "campaign_state")])
    cols = [col("account", "Tài khoản"), col("campaign_name", "Campaign"), col("targeting_type", "Targeting"),
            col("group_name", "Nhóm SP chính"), col("state", "Trạng thái"),
            col("daily_cap", "NS/ngày (tiền gốc)", "num2")]
    return {"title": "Campaign Wayfair",
            "note": "Trạng thái Wayfair quy về cách gọi chung: ACTIVE = Đang chạy (ENABLED), INACTIVE = Tạm dừng (PAUSED). "
                    "Mặc định chỉ hiện campaign Đang chạy.",
            "tables": [_table("campaigns", "Hiệu suất campaign", cols + WF_METRIC_COLUMNS, rows, state_filter=True)]}


# ---------------------------------------------------------------- listing / nhóm sản phẩm

def wf_products(f: Filters, opts: dict) -> dict:
    """Product Targeting có số liệu theo listing ở report SKU; Keyword Targeting ở report keyword x listing.
    Gộp hai nguồn để có đủ chi phí của mọi listing."""
    level = opts.get("level", "listing")
    w = wf_where(f, group_by_listing="l")
    src = LISTING_SRC
    if level == "group":
        key_sel = ("l.group_id, MAX(p.group_name) AS group_name, MAX(p.brand_name) AS brand_name, "
                   "COUNT(DISTINCT f.listing_id) AS listings")
        group, ts_key, ts_field = "l.group_id", "group", "group_id"
        cols = [col("group_name", "Nhóm sản phẩm"), col("brand_name", "Brand"), col("listings", "Số listing QC", "int")]
    else:
        key_sel = (f"f.listing_id, MAX(l.wayfair_sku) AS wayfair_sku, {ACCOUNT_LABEL} AS account, "
                   "MAX(l.product_name) AS product_name, MAX(p.product_sku) AS product_sku, MAX(p.group_name) AS group_name, "
                   "MAX(l.n_products) AS n_products, COUNT(DISTINCT f.campaign_id) AS campaigns, MAX(l.product_id) AS product_id, "
                   "MAX(l.state) AS listing_state, MAX(f.country_code) AS country")
        group, ts_key, ts_field = "f.listing_id", "listing", "listing_id"
        cols = [col("wayfair_sku", "Wayfair SKU"), col("account", "Tài khoản"), col("product_name", "Tên trên Wayfair"),
                col("product_sku", "SKU nội bộ chính"), col("group_name", "Nhóm"), col("state", "Trạng thái listing"),
                col("n_products", "Số biến thể", "int"), col("campaigns", "Số campaign", "int")]
    rows = fetch_all(f"""
        SELECT {key_sel}, {wf_sum_cols()}, {grand_cols(wf_sum_cols())}
        FROM {src} f {CAMPAIGN_JOIN}
        LEFT JOIN dim_wf_listing l ON l.listing_id = f.listing_id
        LEFT JOIN dim_wf_account wa ON wa.account_id = f.account_id
        LEFT JOIN dim_product p ON p.product_id = l.product_id
        {w.sql()}
        GROUP BY {group}
        ORDER BY {_order(opts)} LIMIT {_limit(opts)}""", w.params)
    ts = {r["k"]: r for r in wf_total_sales(f, ts_key)}
    for r in rows:
        t = ts.get(r.get(ts_field), {})
        r["total_sales"], r["total_units"] = t.get("total_sales"), t.get("total_units")
        r["fbx_units"] = t.get("cg_units")
        with_ratios(r)
    if level != "group":
        with_state(rows, [("Listing", "listing_state")])
        for r in rows:
            r.pop("state_by", None)
    extra, profit_cols = ("total_sales",), []
    if level != "group":
        costs, chans = insights.load_costs()
        insights.add_profit(rows, costs, chans, "wayfair")
        profit_cols = PROFIT_COLUMNS
        extra = ("total_sales", "profit_after")
    return {"title": "Listing / Nhóm sản phẩm Wayfair",
            "note": "Listing = Wayfair SKU × tài khoản, gồm nhiều biến thể (part number). Tổng DS sỉ của listing lấy từ "
                    "đơn dropship + CastleGate của các biến thể trong cùng tài khoản, mọi thị trường (biến thể thuộc nhiều "
                    "listing thì chia đều). ACoS hòa vốn và Lãi sau QC dùng giá vốn của SKU chính của listing: nhập tay nếu có, nếu "
                    "không lấy giá vốn chuẩn (sheet BOD) theo nước của tài khoản, CG cho đơn CastleGate và WH cho đơn "
                    "dropship, quy USD theo tỷ giá mới nhất.",
            "tables": [_table("products", "Hiệu suất theo listing" if level != "group" else "Hiệu suất theo nhóm sản phẩm",
                              cols + WF_METRIC_COLUMNS + WF_TACOS_COLUMNS + profit_cols, rows, extra_additive=extra,
                              state_filter=level != "group")]}


# ---------------------------------------------------------------- keyword

def wf_keywords(f: Filters, opts: dict) -> dict:
    by_listing = opts.get("level") == "listing"
    w = wf_where(f)
    w.add_in("f.match_type", f.match_types)
    _term_where(f, w)
    extra_sel = "f.listing_id, MAX(l.wayfair_sku) AS wayfair_sku, MAX(l.product_name) AS product_name," if by_listing else \
        "COUNT(DISTINCT f.listing_id) AS listings,"
    rows = fetch_all(f"""
        SELECT f.campaign_id, f.keyword_info_id, MAX(c.campaign_name) AS campaign_name, {ACCOUNT_LABEL} AS account,
               MAX(c.state) AS campaign_state, MAX(l.state) AS listing_state,
               MAX(f.keyword) AS keyword, MAX(f.match_type) AS match_type, {extra_sel}
               SUBSTRING_INDEX(GROUP_CONCAT(f.bid ORDER BY f.report_date DESC SEPARATOR '|'), '|', 1) AS bid,
               MAX(t.term_class) AS term_class, MAX(t.length_bucket) AS length_bucket, {wf_sum_cols()},
               {grand_cols(wf_sum_cols())}
        FROM fact_wf_keyword_daily f {CAMPAIGN_JOIN}
        LEFT JOIN dim_wf_account wa ON wa.account_id = f.account_id
        LEFT JOIN dim_wf_listing l ON l.listing_id = f.listing_id
        LEFT JOIN dim_term t ON t.term_id = f.term_id
        {w.sql()}
        GROUP BY f.campaign_id, f.keyword_info_id, f.country_code {', f.listing_id' if by_listing else ''}
        ORDER BY {_order(opts)} LIMIT {_limit(opts, 1000)}""", w.params)
    for r in rows:
        r["bid"] = float(r["bid"]) if r.get("bid") not in (None, "") else None
        with_ratios(r)
    _label_class(rows)
    with_state(rows, [("Campaign", "campaign_state")] + ([("Listing", "listing_state")] if by_listing else []))
    if not by_listing:
        for r in rows:
            r.pop("listing_state", None)
    cols = [col("account", "Tài khoản"), col("campaign_name", "Campaign"), col("keyword", "Keyword"),
            col("match_type", "Match"), col("state", "Trạng thái")] + ([STATE_BY_COL] if by_listing else []) +            [col("term_class_label", "Phân nhóm"), col("length_bucket", "Số từ")]
    cols += [col("wayfair_sku", "Wayfair SKU"), col("product_name", "Listing")] if by_listing else \
        [col("listings", "Số listing", "int")]
    cols.append(col("bid", "Max bid (tiền gốc)", "num2"))
    return {"title": "Keyword Wayfair",
            "note": "Report keyword của Wayfair không có Units. Bid là max bid mới nhất trong kỳ, theo tiền tệ của store. "
                    "Wayfair không cung cấp trạng thái riêng của keyword: Trạng thái lấy theo campaign"
                    + (" và listing" if by_listing else "") + ". Mặc định chỉ hiện dòng Đang chạy.",
            "tables": [_table("keywords", "Hiệu suất keyword", cols + WF_METRIC_COLUMNS, rows, state_filter=True)]}


# ---------------------------------------------------------------- search term

def wf_search_terms(f: Filters, opts: dict) -> dict:
    by_keyword = opts.get("level") == "keyword"
    w = wf_where(f)
    w.add_in("f.match_type", f.match_types)
    _term_where(f, w)
    extra_sel = ("f.campaign_id, f.keyword_info_id, MAX(c.campaign_name) AS campaign_name, MAX(f.keyword) AS keyword, "
                 "MAX(f.match_type) AS match_type,") if by_keyword else \
        ("COUNT(DISTINCT f.campaign_id) AS campaigns, "
         "GROUP_CONCAT(DISTINCT f.match_type ORDER BY f.match_type SEPARATOR ', ') AS match_type,")
    extra_grp = ", f.campaign_id, f.keyword_info_id" if by_keyword else ""
    rows = fetch_all(f"""
        SELECT f.term_id, COALESCE(MAX(t.term), IF(f.term_id = '', '(Wayfair không trả search term)', NULL)) AS term,
               MAX(t.term_class) AS term_class, MAX(t.length_bucket) AS length_bucket,
               MAX(t.brand_hit) AS brand_hit, MAX(t.attribute_hits) AS attribute_hits, {extra_sel}
               EXISTS (SELECT 1 FROM fact_wf_keyword_daily x WHERE x.term_id = f.term_id AND x.match_type = 'SMART EXACT')
                 AS has_exact,
               {wf_sum_cols()}, {grand_cols(wf_sum_cols())}
        FROM fact_wf_search_term_daily f {CAMPAIGN_JOIN}
        LEFT JOIN dim_term t ON t.term_id = f.term_id
        {w.sql()}
        GROUP BY f.term_id {extra_grp}
        ORDER BY {_order(opts)} LIMIT {_limit(opts, 1000)}""", w.params)
    for r in rows:
        with_ratios(r)
        r["has_exact"] = "Có" if r.get("has_exact") else ""
    _label_class(rows)
    cols = [col("term", "Search term"), col("term_class_label", "Phân nhóm"), col("length_bucket", "Số từ"),
            col("brand_hit", "Brand"), col("attribute_hits", "Thuộc tính")]
    cols += ([col("campaign_name", "Campaign"), col("keyword", "Keyword gốc"), col("match_type", "Match")]
             if by_keyword else [col("match_type", "Match"), col("campaigns", "Số campaign", "int")])
    cols.append(col("has_exact", "Đã có Smart Exact"))
    return {"title": "Search term Wayfair",
            "note": "Từ report Keyword Optimization (chỉ campaign Keyword Targeting), đã cộng gộp các bộ lọc thuộc tính.",
            "tables": [_table("search_terms", "Hiệu suất search term", cols + WF_METRIC_COLUMNS, rows)]}


def wf_keyword_analysis(f: Filters, opts: dict) -> dict:
    out = keyword_analysis(f, opts, WAYFAIR)
    out["title"] = "Wayfair · " + out["title"]
    return out


def wf_ngrams(f: Filters, opts: dict) -> dict:
    out = ngrams(f, opts, WAYFAIR)
    out["title"] = "Wayfair · " + out["title"]
    return out


def wf_harvest(f: Filters, opts: dict) -> dict:
    out = harvest(f, opts, WAYFAIR)
    out["title"] = "Wayfair · " + out["title"]
    return out


# ---------------------------------------------------------------- share of search

def wf_share_of_search(f: Filters, opts: dict) -> dict:
    """Snapshot Search Term Research mới nhất trong kỳ của mỗi tài khoản x catalog, kèm số liệu QC của search term."""
    w = Where()
    w._n = 5000
    w.add_in("CONCAT(s.account_id, '-', IF(s.catalog LIKE '%Canada%', 'CA', 'US'))", f.wf_accounts)
    _term_where(f, w)
    try:
        min_impr = max(0, int(float(opts.get("min_impr", 100))))
    except (TypeError, ValueError):
        min_impr = 100
    rows = fetch_all(f"""
        SELECT CONCAT(COALESCE(wa.short_name, s.account_id), ' - ', s.catalog) AS account, s.term_id, s.term,
               s.class_name, s.report_date, s.impressions_30d, s.class_share, s.share_search, s.share_page1, s.share_top8,
               t.term_class, t.length_bucket, a.spend, a.orders, a.sales, a.clicks
        FROM fact_wf_share_of_search s
        JOIN (SELECT account_id, catalog, MAX(report_date) AS d FROM fact_wf_share_of_search
              WHERE report_date BETWEEN :start AND :end GROUP BY account_id, catalog) last
          ON last.account_id = s.account_id AND last.catalog = s.catalog AND last.d = s.report_date
        LEFT JOIN dim_wf_account wa ON wa.account_id = s.account_id
        LEFT JOIN dim_term t ON t.term_id = s.term_id
        LEFT JOIN (SELECT term_id, account_id, SUM(cost_usd) AS spend, SUM(orders) AS orders, SUM(sales_usd) AS sales,
                          SUM(clicks) AS clicks
                   FROM fact_wf_search_term_daily WHERE report_date BETWEEN :start AND :end
                   GROUP BY term_id, account_id) a ON a.term_id = s.term_id AND a.account_id = s.account_id
        {('WHERE ' + ' AND '.join(w.clauses + ['s.impressions_30d >= :min_impr'])) }
        ORDER BY s.impressions_30d DESC LIMIT {_limit(opts, 1000)}""",
                     {**w.params, "start": f.start, "end": f.end, "min_impr": min_impr})
    for r in rows:
        r["acos"] = (r["spend"] / r["sales"]) if r.get("sales") else None
        r["gap"] = "Thị phần thấp, chưa chạy QC" if (r.get("share_page1") or 0) < 0.1 and not r.get("spend") else ""
    _label_class(rows)
    cols = [col("account", "Tài khoản · catalog"), col("term", "Search term"), col("class_name", "Class"),
            col("term_class_label", "Phân nhóm"), col("report_date", "Ngày snapshot"),
            col("impressions_30d", "Impr 30 ngày (toàn Wayfair)", "int"), col("class_share", "% Impr của class", "pct"),
            col("share_search", "Share of search", "pct"), col("share_page1", "Share trang 1", "pct"),
            col("share_top8", "Share top 8", "pct"), col("spend", "Spend QC", "money"), col("orders", "Orders QC", "int"),
            col("acos", "ACoS", "pct"), col("gap", "Gợi ý")]
    return {"title": "Share of search Wayfair",
            "note": "Số liệu thị phần hiển thị của công ty trên kết quả tìm kiếm Wayfair (Search Term Research), lấy "
                    "snapshot mới nhất trong kỳ. Spend/Orders QC là số liệu quảng cáo của chính search term đó trong kỳ.",
            "tables": [_table("share_of_search", f"Search term (≥ {min_impr} impression 30 ngày)", cols, rows,
                              with_totals=False)]}


# ---------------------------------------------------------------- ngân sách

def wf_budget(f: Filters, opts: dict) -> dict:
    w = wf_where(f, alias="b")
    w.clauses = [c.replace("b.country_code", "COALESCE(c.country_code, 'US')") for c in w.clauses]
    rows = fetch_all(f"""
        SELECT b.campaign_id, MAX(c.campaign_name) AS campaign_name,
               CONCAT(COALESCE(MAX(wa.short_name), b.account_id), ' - ', COALESCE(MAX(c.country_code), '?')) AS account,
               SUBSTRING_INDEX(GROUP_CONCAT(b.state ORDER BY b.report_date DESC SEPARATOR '|'), '|', 1) AS state,
               AVG(b.daily_cap_usd) AS avg_budget, SUM(b.daily_cap_usd) AS budget_sum,
               SUM(COALESCE(s.spend, 0)) AS spend, SUM(COALESCE(s.sales, 0)) AS sales, COUNT(*) AS days,
               SUM(b.daily_cap_usd > 0 AND COALESCE(s.spend, 0) >= 0.95 * b.daily_cap_usd) AS days_capped
        FROM fact_wf_budget_daily b
        JOIN dim_wf_campaign c ON c.campaign_id = b.campaign_id
        LEFT JOIN dim_wf_account wa ON wa.account_id = b.account_id
        LEFT JOIN (SELECT report_date, campaign_id, SUM(cost_usd) AS spend, SUM(sales_usd) AS sales
                   FROM fact_wf_campaign_daily WHERE report_date BETWEEN :start AND :end
                   GROUP BY report_date, campaign_id) s
               ON s.report_date = b.report_date AND s.campaign_id = b.campaign_id
        {w.sql()}
        GROUP BY b.campaign_id, b.account_id
        HAVING spend > 0 OR state = 'ACTIVE'
        ORDER BY days_capped DESC, spend DESC LIMIT {_limit(opts)}""", w.params)
    for r in rows:
        r["utilization"] = (r["spend"] / r["budget_sum"]) if r.get("budget_sum") else None
        r["acos"] = (r["spend"] / r["sales"]) if r.get("sales") else None
        r["roas"] = (r["sales"] / r["spend"]) if r.get("spend") else None
    cols = [col("account", "Tài khoản"), col("campaign_name", "Campaign"), col("state", "Trạng thái"),
            col("avg_budget", "NS TB/ngày", "money"), col("spend", "Spend", "money"), col("utilization", "% dùng NS", "pct"),
            col("days", "Số ngày", "int"), col("days_capped", "Ngày hết NS", "int"), col("sales", "DS QC (giá sỉ)", "money"),
            col("acos", "ACoS", "pct"), col("roas", "ROAS", "num2")]
    return {"title": "Ngân sách campaign Wayfair",
            "note": "Ngày hết NS = ngày có spend ≥ 95% daily cap. Campaign hết ngân sách thường xuyên mà ACoS tốt nên tăng ngân sách.",
            "tables": [_table("budget", "Mức sử dụng ngân sách", cols, rows, with_totals=False)]}


WF_REPORTS = {
    "wf_overview": wf_overview,
    "wf_campaigns": wf_campaigns,
    "wf_products": wf_products,
    "wf_keywords": wf_keywords,
    "wf_search_terms": wf_search_terms,
    "wf_keyword_analysis": wf_keyword_analysis,
    "wf_ngrams": wf_ngrams,
    "wf_harvest": wf_harvest,
    "wf_share_of_search": wf_share_of_search,
    "wf_budget": wf_budget,
}
