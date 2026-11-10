"""Các báo cáo quảng cáo. Mỗi hàm nhận Filters + opts và trả về dict dùng chung cho API và file HTML xuất ra.

Cấu trúc trả về: {"title", "kpis"?, "charts"?, "tables": [{"key", "title", "columns", "rows", "totals"?}]}
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from app.db import fetch_all
from app.viz import chart as viz_chart, series as viz_series, trend_charts
from app import insights
from app.filters import Filters, Where, campaign_where, wf_where
from app.keywords.classifier import CLASS_LABELS
from app.metrics import (PROFIT_COLUMNS, METRIC_COLUMNS, NTB_COLUMNS, TACOS_COLUMNS, WF_METRIC_COLUMNS, col, grand_cols, order_expr,
                         kpi_series, sum_cols, sum_names, totals, wf_sum_cols, with_ratios)

AD_TYPE_LABELS = {"SP": "Sponsored Products", "SB": "Sponsored Brands", "SD": "Sponsored Display"}
MAX_LIMIT = 5000


@dataclass(frozen=True)
class TermSource:
    """Bảng search term / keyword của một sàn: phân tích từ khóa, n-gram, thêm/phủ định dùng chung cho Amazon và Wayfair."""
    search_term_fact: str
    keyword_fact: str
    campaign_join: str  # JOIN bảng campaign alias c với fact alias f
    where: Callable[[Filters], Where]
    sums: Callable[..., str]
    metrics: list
    exact: str  # match type "chính xác", để biết search term đã được thêm thành keyword chưa
    excluded_classes: tuple[str, ...] = ()


AMAZON = TermSource(
    "fact_search_term_daily", "fact_target_daily",
    "JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type",
    campaign_where, sum_cols, METRIC_COLUMNS, "EXACT", ("AUTO", "PRODUCT_TARGET", "CATEGORY_TARGET", "AUDIENCE"))
WAYFAIR = TermSource(
    "fact_wf_search_term_daily", "fact_wf_keyword_daily", "JOIN dim_wf_campaign c ON c.campaign_id = f.campaign_id",
    wf_where, wf_sum_cols, WF_METRIC_COLUMNS, "SMART EXACT")


def _limit(opts: dict, default: int = 500) -> int:
    try:
        return max(1, min(int(opts.get("limit", default)), MAX_LIMIT))
    except (TypeError, ValueError):
        return default


def _order(opts: dict, default: str = "spend", alias: str = "f") -> str:
    key = str(opts.get("sort", default))
    expr = order_expr(key, alias) or order_expr(default, alias)
    direction = "ASC" if str(opts.get("dir", "desc")).lower() == "asc" else "DESC"
    return f"{expr} {direction}"


def _num(opts: dict, key: str, default: float) -> float:
    try:
        return float(opts.get(key, default))
    except (TypeError, ValueError):
        return default


def _pop_grand(rows: list[dict]) -> dict:
    """Lấy và bỏ các cột do grand_cols() thêm vào (_total_rows, _t_<cột>) khỏi mọi dòng."""
    grand = {}
    for i, r in enumerate(rows):
        for k in [k for k in r if k.startswith("_")]:
            v = r.pop(k)
            if i == 0:
                grand[k[3:] if k.startswith("_t_") else k] = v
    return grand


def _table(key: str, title: str, columns: list[dict], rows: list[dict], with_totals: bool = True,
           extra_additive: tuple[str, ...] = (), state_filter: bool = False) -> dict:
    t = {"key": key, "title": title, "columns": columns, "rows": rows}
    if state_filter:  # bộ lọc mặc định Trạng thái = ENABLED (người dùng bỏ được, xem app/table_filters.py)
        t["default_filter"] = STATE_DEFAULT
    grand = _pop_grand(rows)
    if "_total_rows" in grand:
        t["total_rows"] = int(grand.pop("_total_rows"))
    if with_totals and rows and t.get("total_rows", 0) > len(rows):
        # bảng bị cắt theo LIMIT: dòng Tổng lấy tổng thật của mọi dòng; cột cộng thêm (vd tổng doanh số) không có
        # tổng thật nên để trống thay vì cộng thiếu
        t["totals"] = with_ratios(grand)
    elif with_totals and rows:
        t["totals"] = totals(rows, extra_additive)
        if extra_additive:
            t["additive"] = list(extra_additive)  # để tính lại dòng tổng sau khi lọc (app/table_filters.py)
    return t


# ---------------------------------------------------------------- trạng thái

STATE_ALIASES = {"ACTIVE": "ENABLED", "INACTIVE": "PAUSED", "DELETED": "ARCHIVED"}  # Wayfair -> cách gọi của Amazon
STATE_DEFAULT = {"cols": {"state": ["ENABLED"]}}  # bảng có cột Trạng thái mặc định chỉ hiện dòng đang chạy
STATE_BY_COL = col("state_by", "Trạng thái theo")


def norm_state(value) -> str:
    v = str(value or "").strip().upper()
    return STATE_ALIASES.get(v, v)


def effective_state(levels: list[tuple[str, object]]) -> tuple[str, str]:
    """Trạng thái hiệu lực từ ngoài vào trong (campaign → ad group → target): cấp đầu tiên không ENABLED quyết định.
    Cấp ngoài cùng chưa rõ thì để trống; cấp trong chưa rõ (vd target sản phẩm SP) thì theo cấp ngoài."""
    for i, (label, raw) in enumerate(levels):
        v = norm_state(raw)
        if not v:
            if i == 0:
                return "", ""
            continue
        if v != "ENABLED":
            return v, label
    known = [label for label, raw in levels if norm_state(raw)]
    return "ENABLED", (known[-1] if known and known[-1] != levels[-1][0] else "")


def with_state(rows: list[dict], levels: list[tuple[str, str]]) -> None:
    """Ghi r['state'] (hiệu lực) và r['state_by'] (cấp quyết định) từ các cột trạng thái từng cấp của dòng."""
    for r in rows:
        r["state"], r["state_by"] = effective_state([(label, r.pop(key, None)) for label, key in levels])


def _term_where(f: Filters, w: Where, alias: str = "t") -> None:
    w.add_in(f"{alias}.term_class", f.term_classes)
    w.add_in(f"{alias}.length_bucket", f.length_buckets)


def _label_class(rows: list[dict], key: str = "term_class") -> None:
    for r in rows:
        r[f"{key}_label"] = CLASS_LABELS.get(r.get(key) or "", r.get(key) or "Chưa phân loại")


# ---------------------------------------------------------------- tổng doanh số (TACoS)

def total_sales(f: Filters, group_by: str | None = None) -> list[dict]:
    """Tổng doanh số từ đơn hàng. group_by: None | 'account' | 'date' | 'product' | 'asin' | 'group'."""
    w = Where().add("t.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    scope = Where()
    scope._n = 500
    scope.add_in("a.profile_id", f.profile_ids)
    w.add("EXISTS (SELECT 1 FROM dim_account a WHERE a.store_account_id = t.store_account_id "
          "AND a.country_code = t.country_code" + (" AND " + " AND ".join(scope.clauses) if scope.clauses else "")
          + ")", **scope.params)
    if f.group_ids or f.brand_ids:
        w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    keys = {
        None: ("", ""),
        "account": ("t.store_account_id, t.country_code", "t.store_account_id, t.country_code"),
        "date": ("t.report_date", "t.report_date"),
        "product": ("t.product_id", "t.product_id"),
        "product_country": ("t.product_id, t.country_code", "t.product_id, t.country_code"),
        "asin": ("t.asin", "t.asin"),
        "group": ("p.group_id", "p.group_id"),
    }[group_by]
    select = (keys[0] + ", ") if keys[0] else ""
    group = f"GROUP BY {keys[1]}" if keys[1] else ""
    return fetch_all(f"""
        SELECT {select} SUM(t.sales_usd) AS total_sales, SUM(t.units) AS total_units,
               SUM(t.order_items) AS order_items, SUM(t.fba_order_items) AS fba_order_items,
               SUM(t.fba_units) AS fba_units, SUM(t.fba_sales_usd) AS fba_sales
        FROM fact_total_sales_daily t
        LEFT JOIN dim_product p ON p.product_id = t.product_id
        {w.sql()} {group}""", w.params)


# ---------------------------------------------------------------- tổng quan

def _overview_products(f: Filters) -> list[dict]:
    """Spend / Ad Sales kỳ này và Ad Sales kỳ trước theo sản phẩm × nước (chỉ SP có báo cáo theo ASIN)."""
    prev = f.previous_period()
    w = campaign_where(insights.same_filters(f, start=prev.start, group_ids=[], brand_ids=[]))
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    w.add("f.product_id IS NOT NULL", cur_start=f.start)
    rows = fetch_all(f"""
        SELECT f.product_id, a.country_code AS country, MAX(p.product_sku) AS product_sku,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.cost_usd END) AS spend,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.sales_usd END) AS sales,
               SUM(CASE WHEN f.report_date < :cur_start THEN f.sales_usd END) AS sales0,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.clicks END) AS clicks,
               SUM(CASE WHEN f.report_date >= :cur_start THEN f.orders END) AS orders,
               COUNT(DISTINCT CASE WHEN f.report_date >= :cur_start AND f.cost_usd > 0 THEN f.report_date END) AS spend_days,
               MIN(CASE WHEN f.report_date >= :cur_start AND f.cost_usd > 0 THEN f.report_date END) AS first_spend
        FROM fact_product_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        JOIN dim_account a ON a.profile_id = f.profile_id
        LEFT JOIN dim_product p ON p.product_id = f.product_id
        {w.sql()}
        GROUP BY f.product_id, a.country_code""", w.params)
    for r in rows:
        r["filter_value"] = r["product_sku"] or str(r["product_id"])
        r["label"] = f"{r['filter_value']} · {r['country']}"
    return rows


def month_daily(f: Filters) -> list[dict]:
    """Spend, Ad Sales, tổng doanh số theo ngày từ đầu tháng của f.end tới f.end (cùng bộ lọc)."""
    first, _, _ = insights.month_window(f.end)
    mf = insights.same_filters(f, start=first)
    w = campaign_where(mf)
    rows = fetch_all(f"""SELECT f.report_date AS date, SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
        FROM fact_campaign_daily f JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        {w.sql()} GROUP BY f.report_date""", w.params)
    ts = {r["report_date"]: r["total_sales"] for r in total_sales(mf, "date")}
    out = {r["date"]: {"date": r["date"].isoformat(), "spend": r["spend"], "sales": r["sales"], "total_sales": None} for r in rows}
    for d, v in ts.items():
        out.setdefault(d, {"date": d.isoformat(), "spend": 0, "sales": 0})["total_sales"] = v
    return list(out.values())


def month_by_account(f: Filters) -> dict[str, dict]:
    """Spend, Ad Sales, tổng doanh số theo tài khoản (khóa "<store_account_id>-<nước>") trong khoảng f."""
    w = campaign_where(f)
    rows = fetch_all(f"""SELECT CONCAT(a.store_account_id, '-', a.country_code) AS k, MAX(a.account_label) AS account,
               SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
        FROM fact_campaign_daily f JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        JOIN dim_account a ON a.profile_id = f.profile_id {w.sql()}
        GROUP BY a.store_account_id, a.country_code""", w.params)
    out = {r["k"]: r for r in rows}
    for r in total_sales(f, "account"):
        k = f"{r['store_account_id']}-{r['country_code']}"
        out.setdefault(k, {"k": k, "spend": 0, "sales": 0})["total_sales"] = r["total_sales"]
    return out


def account_options() -> list[dict]:
    return fetch_all("""SELECT CONCAT(store_account_id, '-', country_code) AS id, MAX(account_label) AS label
        FROM dim_account WHERE store_account_id IS NOT NULL GROUP BY store_account_id, country_code ORDER BY label""")


def _target_keys(f: Filters) -> list[str] | None:
    if not f.profile_ids:
        return None
    w = Where().add_in("profile_id", f.profile_ids)
    return sorted({r["k"] for r in fetch_all(f"SELECT CONCAT(store_account_id, '-', country_code) AS k FROM dim_account {w.sql()}",
                                             w.params)})


def _overview_budget(f: Filters) -> list[dict]:
    """Số ngày hết ngân sách của các campaign có chi tiêu (nhanh hơn báo cáo Ngân sách vì chỉ xét ngày có spend)."""
    w = campaign_where(f)
    rows = fetch_all(f"""
        SELECT s.campaign_id, MAX(s.campaign_name) AS campaign_name, COUNT(*) AS days,
               SUM(s.spend >= 0.95 * b.budget_usd) AS days_capped, SUM(s.spend) AS spend, SUM(s.sales) AS sales
        FROM (SELECT f.report_date, f.ad_type, f.campaign_id, MAX(c.campaign_name) AS campaign_name,
                     SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
              FROM fact_campaign_daily f
              JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
              {w.sql()}
              GROUP BY f.report_date, f.ad_type, f.campaign_id HAVING spend > 0) s
        JOIN fact_campaign_budget_daily b
          ON b.report_date = s.report_date AND b.ad_type = s.ad_type AND b.campaign_id = s.campaign_id
        GROUP BY s.ad_type, s.campaign_id""", w.params)
    for r in rows:
        r["acos"] = (r["spend"] / r["sales"]) if r.get("sales") else None
    return rows


def _overview_insights(f: Filters, cur: dict, prev: dict, trend: list[dict]) -> tuple[list[dict], list[dict]]:
    """Đồ thị và thẻ thêm cho Tổng quan Amazon (xem app/insights.py)."""
    rows = _overview_products(f)
    tot = {(r["product_id"], r["country_code"]): r for r in total_sales(f, "product_country")}
    for r in rows:
        t = tot.get((r["product_id"], r["country"]), {})
        r["total_sales"], r["total_units"] = t.get("total_sales"), t.get("total_units")
        r["fbx_units"] = t.get("fba_units")
    costs, chans = insights.load_costs()
    insights.add_profit(rows, costs, chans, "amazon")
    status = insights.stock_status({(r["product_id"], r["country"]) for r in rows})
    movers = insights.movers_chart(rows, "Ad Sales", {"goto": {"tab": "products", "table": "products"},
                                                       "opts": {"level": "product"}, "col": "product_sku"})
    if movers:
        movers["subtitle"] += " Chỉ gồm Sponsored Products."
    risk_chart, risk_spend, lost, _ = insights.stock_risk(rows, status)
    budget_chart, capped, active = insights.budget_summary(_overview_budget(f), "budget")
    daily = month_daily(f)
    month_spend = sum(float(r["spend"] or 0) for r in daily)
    sp_spend = sum(float(r["spend"] or 0) for r in rows)
    goto = {"goto": {"tab": "products", "table": "products"}, "opts": {"level": "product"}, "col": "product_sku"}
    target_chart, target_cards = None, []
    if insights.scoped(f):
        target = insights.target_for(insights.load_targets(f.end, "amazon"), _target_keys(f))
        if target:
            target_chart, target_cards = insights.progress(target, daily, f.end)
    charts = ([target_chart, insights.organic_chart(trend, "Ad Sales")] + trend_charts(trend, "Ad Sales")
              + insights.bridge_charts(cur, prev, "Ad Sales")
              + [movers, insights.profit_chart(rows, goto), insights.matrix_chart(rows, status, "Ad Sales"),
                 insights.no_order_chart(rows, f.end, 7, goto), risk_chart, budget_chart])
    cards = insights.extra_cards(f, month_spend, sp_spend, risk_spend, lost, capped, active)
    cards[1]["note"] += " (Sponsored Products)"
    cards = target_cards + insights.profit_cards(rows, sp_spend, "Spend SP") + cards
    return [c for c in charts if c], cards


def overview(f: Filters, opts: dict) -> dict:
    def kpi_block(ff: Filters) -> dict:
        w = campaign_where(ff)
        row = fetch_all(f"""SELECT {sum_cols()} FROM fact_campaign_daily f
            JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type {w.sql()}""", w.params)[0]
        row["total_sales"] = (total_sales(ff)[0] or {}).get("total_sales")
        return with_ratios(row)

    cur, prev = kpi_block(f), kpi_block(f.previous_period())

    w = campaign_where(f)
    join = "JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type"
    trend = fetch_all(f"""SELECT f.report_date AS date, {sum_cols()} FROM fact_campaign_daily f {join}
        {w.sql()} GROUP BY f.report_date ORDER BY f.report_date""", w.params)
    ts_by_date = {r["report_date"]: r["total_sales"] for r in total_sales(f, "date")}
    for r in trend:
        r["total_sales"] = ts_by_date.get(r["date"])
        with_ratios(r)
        r["date"] = r["date"].isoformat()
    if cur.get("total_sales"):  # khớp với đồ thị: chỉ trừ Ad Sales của ngày đã có doanh số đơn hàng
        cur["organic_sales"] = insights.organic_total(trend)

    by_type = fetch_all(f"""SELECT f.ad_type, {sum_cols()} FROM fact_campaign_daily f {join}
        {w.sql()} GROUP BY f.ad_type ORDER BY spend DESC""", w.params)
    spend_total = sum(r["spend"] or 0 for r in by_type) or None
    for r in by_type:
        with_ratios(r)
        r["ad_type_label"] = AD_TYPE_LABELS.get(r["ad_type"], r["ad_type"])
        r["spend_share"] = (r["spend"] / spend_total) if spend_total else None

    by_acc = fetch_all(f"""SELECT a.store_account_id, a.country_code, MAX(a.account_label) AS account, {sum_cols()}
        FROM fact_campaign_daily f {join} JOIN dim_account a ON a.profile_id = f.profile_id
        {w.sql()} GROUP BY a.store_account_id, a.country_code ORDER BY spend DESC""", w.params)
    ts_acc = {(r["store_account_id"], r["country_code"]): r["total_sales"] for r in total_sales(f, "account")}
    for r in by_acc:
        r["total_sales"] = ts_acc.get((r["store_account_id"], r["country_code"]))
        with_ratios(r)

    viz, cards = _overview_insights(f, cur, prev, trend)
    fulfil_chart, by_fulfil = _fulfilment(f)
    if fulfil_chart:
        viz.insert(next((i + 1 for i, c in enumerate(viz) if c["key"] == "organic"), 0), fulfil_chart)
    return {
        "title": "Tổng quan quảng cáo",
        "viz": viz,
        "cards": cards,
        "kpis": {"current": cur, "previous": prev, "series": kpi_series(trend, f.start, f.end)},
        "charts": {"trend": trend},
        "tables": [
            _table("by_ad_type", "Theo loại quảng cáo",
                   [col("ad_type_label", "Loại QC"), col("spend_share", "% Spend", "pct")] + METRIC_COLUMNS + NTB_COLUMNS,
                   by_type),
            _table("by_account", "Theo tài khoản (kèm TACoS)", [col("account", "Tài khoản")] + METRIC_COLUMNS + TACOS_COLUMNS,
                   by_acc, extra_additive=("total_sales",)),
        ] + ([by_fulfil] if by_fulfil else []),
    }


FULFIL_COLUMNS = [col("country", "Nước"), col("fba_orders", "Đơn FBA", "int"), col("fbm_orders", "Đơn FBM", "int"),
                  col("fba_order_share", "% đơn FBA", "pct"), col("fba_order_share_prev", "% đơn FBA kỳ trước", "pct"),
                  col("fba_units", "Units FBA", "int"), col("fbm_units", "Units FBM", "int"),
                  col("fba_sales", "DS FBA", "money"), col("fbm_sales", "DS FBM", "money"),
                  col("fba_sales_share", "% DS FBA", "pct"), col("fba_aov", "Giá trị dòng đơn FBA", "money"),
                  col("fbm_aov", "Giá trị dòng đơn FBM", "money")]


def _fulfil_row(r: dict) -> dict:
    """Tách tổng (FBA + FBM) thành hai phần. Đơn = dòng đơn hàng (một đơn nhiều ASIN đếm nhiều dòng, ~3–4% đơn)."""
    n, fba = float(r.get("order_items") or 0), float(r.get("fba_order_items") or 0)
    sales, fba_s = float(r.get("total_sales") or 0), float(r.get("fba_sales") or 0)
    units, fba_u = float(r.get("total_units") or 0), float(r.get("fba_units") or 0)
    return {"fba_orders": fba, "fbm_orders": n - fba, "fba_order_share": fba / n if n else None,
            "fba_units": fba_u, "fbm_units": units - fba_u, "fba_sales": fba_s, "fbm_sales": sales - fba_s,
            "fba_sales_share": fba_s / sales if sales else None,
            "fba_aov": fba_s / fba if fba else None, "fbm_aov": (sales - fba_s) / (n - fba) if n > fba else None}


def _fulfilment(f: Filters) -> tuple[dict | None, dict | None]:
    """Tỷ trọng đơn FBA / FBM: đồ thị cột chồng theo ngày (theo tuần nếu kỳ dài) + bảng theo nước, cùng bộ lọc tài khoản /
    nhóm SP / brand với Tổng DS. Nguồn: s__amazon_orders.fulfill_channel (AFN = FBA, MFN = FBM), bỏ đơn Canceled."""
    days = total_sales(f, "date")
    if not any(r.get("order_items") for r in days):
        return None, None
    weekly = (f.end - f.start).days >= 62
    buckets: dict[date, dict] = {}
    for r in days:
        d = r["report_date"] - timedelta(days=r["report_date"].weekday()) if weekly else r["report_date"]
        b = buckets.setdefault(d, {"order_items": 0, "fba_order_items": 0})
        b["order_items"] += r.get("order_items") or 0
        b["fba_order_items"] += r.get("fba_order_items") or 0
    labels = sorted(buckets)
    fba = [buckets[d]["fba_order_items"] for d in labels]
    fbm = [buckets[d]["order_items"] - buckets[d]["fba_order_items"] for d in labels]
    share = [(a / (a + b)) if a + b else None for a, b in zip(fba, fbm)]
    n_fba, n_all = sum(fba), sum(fba) + sum(fbm)
    chart = viz_chart("fulfilment", "Đơn hàng FBA và FBM theo " + ("tuần" if weekly else "ngày"), "bar_stacked",
                      [d.isoformat() for d in labels],
                      [viz_series("FBA", "c1", fba),
                       viz_series("FBM", "c4", fbm),
                       viz_series("% đơn FBA", "n2", share, line=True, unit="pct", total=n_fba / n_all if n_all else None)],
                      unit="int",
                      subtitle="Số dòng đơn hàng Amazon (bỏ đơn hủy) theo hình thức giao: FBA = Amazon giao từ kho FBA, "
                               "FBM = công ty tự giao từ kho nội bộ. Đường = % đơn FBA (trục phải). Ngày gần nhất có thể "
                               "thiếu đơn Pending. Chi tiết theo nước ở bảng 'Theo hình thức giao hàng'.")
    cur = {(r["country_code"]): r for r in _by_country(f)}
    prev = {(r["country_code"]): r for r in _by_country(f.previous_period())}
    rows = []
    for cc in sorted(cur, key=lambda c: -float(cur[c].get("total_sales") or 0)):
        row = {"country": cc, **_fulfil_row(cur[cc])}
        if cc in prev:
            row["fba_order_share_prev"] = _fulfil_row(prev[cc])["fba_order_share"]
        rows.append(row)
    table = _table("by_fulfilment", "Theo hình thức giao hàng (FBA / FBM)", FULFIL_COLUMNS, rows, with_totals=False)
    totals = {"country": "Tổng", **_fulfil_row({k: sum(float(r.get(k) or 0) for r in cur.values())
                                                 for k in ("order_items", "fba_order_items", "total_sales", "fba_sales",
                                                           "total_units", "fba_units")})}
    pt = _fulfil_row({k: sum(float(r.get(k) or 0) for r in prev.values()) for k in ("order_items", "fba_order_items")})
    totals["fba_order_share_prev"] = pt["fba_order_share"]
    table["totals"] = totals
    return chart, table


def _by_country(f: Filters) -> list[dict]:
    out: dict[str, dict] = {}
    for r in total_sales(f, "account"):
        c = out.setdefault(r["country_code"], {"country_code": r["country_code"]})
        for k in ("order_items", "fba_order_items", "total_sales", "fba_sales", "total_units", "fba_units"):
            c[k] = c.get(k, 0) + float(r.get(k) or 0)
    return list(out.values())


# ---------------------------------------------------------------- campaign / ad group

def campaigns(f: Filters, opts: dict) -> dict:
    level = opts.get("level", "campaign")
    w = campaign_where(f)
    ag_select, ag_group, ag_join = "", "", ""
    if level == "adgroup":
        ag_select = "f.adgroup_id, MAX(g.adgroup_name) AS adgroup_name, MAX(g.state) AS adgroup_state,"
        ag_group = ", f.adgroup_id"
        ag_join = "LEFT JOIN dim_adgroup g ON g.adgroup_id = f.adgroup_id AND g.ad_type = f.ad_type"
    rows = fetch_all(f"""
        SELECT f.ad_type, f.campaign_id, {ag_select}
               MAX(c.campaign_name) AS campaign_name, MAX(c.state) AS campaign_state, MAX(c.budget) AS budget,
               MAX(c.budget_type) AS budget_type, MAX(c.targeting_mode) AS targeting_mode,
               MAX(p.portfolio_name) AS portfolio_name, MAX(a.account_label) AS account, {sum_cols()},
               {grand_cols(sum_cols())}
        FROM fact_campaign_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        LEFT JOIN dim_portfolio p ON p.portfolio_id = c.portfolio_id
        LEFT JOIN dim_account a ON a.profile_id = f.profile_id
        {ag_join}
        {w.sql()}
        GROUP BY f.ad_type, f.campaign_id {ag_group}
        ORDER BY {_order(opts)} LIMIT {_limit(opts)}""", w.params)
    for r in rows:
        with_ratios(r)
    with_state(rows, [("Campaign", "campaign_state")] + ([("Ad group", "adgroup_state")] if level == "adgroup" else []))
    cols = [col("account", "Tài khoản"), col("ad_type", "Loại"), col("portfolio_name", "Portfolio"),
            col("campaign_name", "Campaign"), col("targeting_mode", "Auto/Manual"), col("state", "Trạng thái"),
            col("budget", "Ngân sách", "money")]
    if level == "adgroup":
        cols.insert(4, col("adgroup_name", "Ad group"))
        cols.insert(cols.index(next(c for c in cols if c["key"] == "state")) + 1, STATE_BY_COL)
    return {"title": "Campaign" if level != "adgroup" else "Ad group",
            "tables": [_table("campaigns", "Hiệu suất campaign" if level != "adgroup" else "Hiệu suất ad group",
                              cols + METRIC_COLUMNS + NTB_COLUMNS, rows, state_filter=True)]}


# ---------------------------------------------------------------- keyword / target

def targets(f: Filters, opts: dict) -> dict:
    w = campaign_where(f)
    w.add_in("f.match_type", f.match_types)
    _term_where(f, w)
    rows = fetch_all(f"""
        SELECT f.ad_type, f.campaign_id, f.adgroup_id, f.target_id,
               MAX(f.targeting) AS targeting, MAX(f.match_type) AS match_type,
               SUBSTRING_INDEX(GROUP_CONCAT(f.bid ORDER BY f.report_date DESC SEPARATOR '|'), '|', 1) AS bid,
               AVG(f.top_of_search_is) AS top_of_search_is,
               MAX(c.campaign_name) AS campaign_name, MAX(g.adgroup_name) AS adgroup_name,
               MAX(c.state) AS campaign_state, MAX(g.state) AS adgroup_state, MAX(ts.state) AS target_state,
               MAX(t.term_class) AS term_class, MAX(t.length_bucket) AS length_bucket, {sum_cols()},
               {grand_cols(sum_cols())}
        FROM fact_target_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        LEFT JOIN dim_adgroup g ON g.adgroup_id = f.adgroup_id AND g.ad_type = f.ad_type
        LEFT JOIN dim_target_state ts ON ts.ad_type = f.ad_type AND ts.target_id = f.target_id
        LEFT JOIN dim_term t ON t.term_id = f.term_id
        {w.sql()}
        GROUP BY f.ad_type, f.campaign_id, f.adgroup_id, f.target_id
        ORDER BY {_order(opts)} LIMIT {_limit(opts, 1000)}""", w.params)
    for r in rows:
        r["bid"] = float(r["bid"]) if r.get("bid") not in (None, "") else None
        with_ratios(r)
    _label_class(rows)
    with_state(rows, [("Campaign", "campaign_state"), ("Ad group", "adgroup_state"), ("Target", "target_state")])
    cols = [col("ad_type", "Loại"), col("campaign_name", "Campaign"), col("adgroup_name", "Ad group"),
            col("targeting", "Keyword / Target"), col("match_type", "Match"), col("state", "Trạng thái"), STATE_BY_COL,
            col("term_class_label", "Phân nhóm"), col("length_bucket", "Số từ"), col("bid", "Bid", "money"),
            col("top_of_search_is", "TOS IS", "pct")]
    return {"title": "Keyword / Target",
            "note": "Trạng thái là trạng thái hiệu lực hiện tại: keyword chỉ chạy khi cả campaign và ad group đang chạy, "
                    "nên cột “Trạng thái theo” cho biết cấp nào đang tạm dừng / lưu trữ. Target sản phẩm / auto của SP "
                    "không có trạng thái riêng trong DWH nên lấy theo ad group. Mặc định chỉ hiện dòng Đang chạy.",
            "tables": [_table("targets", "Hiệu suất keyword / target", cols + METRIC_COLUMNS + NTB_COLUMNS, rows,
                              state_filter=True)]}


# ---------------------------------------------------------------- search term

def search_terms(f: Filters, opts: dict) -> dict:
    by_target = opts.get("level") == "target"
    w = campaign_where(f)
    w.add_in("f.match_type", f.match_types)
    _term_where(f, w)
    extra_sel = ("f.campaign_id, f.adgroup_id, f.target_id, MAX(c.campaign_name) AS campaign_name, "
                 "MAX(f.targeting) AS targeting, MAX(f.match_type) AS match_type,") if by_target else \
        ("COUNT(DISTINCT f.campaign_id) AS campaigns, "
         "GROUP_CONCAT(DISTINCT f.match_type ORDER BY f.match_type SEPARATOR ', ') AS match_type,")
    extra_grp = ", f.campaign_id, f.adgroup_id, f.target_id" if by_target else ""
    rows = fetch_all(f"""
        SELECT f.term_id, MAX(t.term) AS term, MAX(t.term_class) AS term_class, MAX(t.length_bucket) AS length_bucket,
               MAX(t.brand_hit) AS brand_hit, MAX(t.attribute_hits) AS attribute_hits, {extra_sel}
               EXISTS (SELECT 1 FROM fact_target_daily x WHERE x.term_id = f.term_id AND x.match_type = 'EXACT') AS has_exact,
               {sum_cols()}, {grand_cols(sum_cols())}
        FROM fact_search_term_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
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
    cols += ([col("campaign_name", "Campaign"), col("targeting", "Keyword gốc"), col("match_type", "Match")]
             if by_target else [col("match_type", "Match"), col("campaigns", "Số campaign", "int")])
    cols.append(col("has_exact", "Đã có Exact"))
    return {"title": "Search term",
            "tables": [_table("search_terms", "Hiệu suất search term", cols + METRIC_COLUMNS, rows)]}


# ---------------------------------------------------------------- phân tích từ khóa

def keyword_analysis(f: Filters, opts: dict, src: TermSource = AMAZON) -> dict:
    source = opts.get("source", "search_term")
    fact, term_col = (src.keyword_fact, "f.term_id") if source == "keyword" else (src.search_term_fact, "f.term_id")
    w = src.where(f)
    w.add_in("f.match_type", f.match_types)
    _term_where(f, w)
    base = f"""FROM {fact} f
        {src.campaign_join}
        LEFT JOIN dim_term t ON t.term_id = {term_col}
        {w.sql()}"""
    metrics = src.metrics

    def grouped(select: str, group: str, order: str) -> list[dict]:
        # ORDER BY ở truy vấn ngoài theo alias, tránh lỗi ONLY_FULL_GROUP_BY với biểu thức COALESCE
        rows = fetch_all(f"SELECT * FROM (SELECT {select}, COUNT(DISTINCT {term_col}) AS terms, {src.sums()} {base} "
                         f"GROUP BY {group}) x ORDER BY {order}", w.params)
        for r in rows:
            with_ratios(r)
        _label_class(rows)
        return rows

    bucket_order = "FIELD(x.length_bucket, '1', '2', '3', '4', '5+', 'ASIN', '-')"
    by_len = grouped("COALESCE(t.length_bucket, '?') AS length_bucket", "COALESCE(t.length_bucket, '?')", bucket_order)
    by_class = grouped("COALESCE(t.term_class, 'UNCLASSIFIED') AS term_class", "COALESCE(t.term_class, 'UNCLASSIFIED')",
                       "spend DESC")
    matrix = grouped("COALESCE(t.length_bucket, '?') AS length_bucket, COALESCE(t.term_class, 'UNCLASSIFIED') AS term_class",
                     "COALESCE(t.length_bucket, '?'), COALESCE(t.term_class, 'UNCLASSIFIED')",
                     f"{bucket_order}, spend DESC")
    by_match = grouped("f.match_type, COALESCE(t.term_class, 'UNCLASSIFIED') AS term_class",
                       "f.match_type, COALESCE(t.term_class, 'UNCLASSIFIED')", "x.match_type, x.spend DESC")

    spend_total = sum(r["spend"] for r in by_len) or None
    for rows in (by_len, by_class, matrix):
        for r in rows:
            r["spend_share"] = (r["spend"] / spend_total) if spend_total else None

    share = [col("terms", "Số từ khóa", "int"), col("spend_share", "% Spend", "pct")]
    src_label = "keyword đặt giá thầu" if source == "keyword" else "search term khách gõ"
    return {
        "title": f"Phân tích từ khóa ({src_label})",
        "charts": {"by_length": by_len, "by_class": by_class},
        "tables": [
            _table("by_length", "Theo độ dài (số từ)", [col("length_bucket", "Số từ")] + share + metrics, by_len),
            _table("by_class", "Theo phân nhóm Chung / Mục tiêu / Brand",
                   [col("term_class_label", "Phân nhóm")] + share + metrics, by_class),
            _table("matrix", "Độ dài × Phân nhóm",
                   [col("length_bucket", "Số từ"), col("term_class_label", "Phân nhóm")] + share + metrics, matrix),
            _table("by_match", "Match type × Phân nhóm",
                   [col("match_type", "Match"), col("term_class_label", "Phân nhóm"), col("terms", "Số từ khóa", "int")]
                   + metrics, by_match),
        ],
    }


def ngrams(f: Filters, opts: dict, src: TermSource = AMAZON) -> dict:
    n = int(opts.get("n", 1)) if str(opts.get("n", 1)) in ("1", "2", "3") else 1
    min_clicks = _num(opts, "min_clicks", 5)
    w = src.where(f)
    w.add_in("f.match_type", f.match_types)
    inner_where = w.sql()
    tw = Where()
    tw._n = 800
    _term_where(f, tw)
    rows = fetch_all(f"""
        SELECT b.ngram, COUNT(*) AS terms,
               SUM(s.impressions) AS impressions, SUM(s.clicks) AS clicks, SUM(s.spend) AS spend,
               SUM(s.orders) AS orders, SUM(s.units) AS units, SUM(s.sales) AS sales
        FROM (
          SELECT f.term_id, SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks, SUM(f.cost_usd) AS spend,
                 SUM(f.orders) AS orders, SUM(f.units) AS units, SUM(f.sales_usd) AS sales
          FROM {src.search_term_fact} f
          {src.campaign_join}
          {inner_where}
          GROUP BY f.term_id
        ) s
        JOIN bridge_term_ngram b ON b.term_id = s.term_id AND b.n = :n
        JOIN dim_term t ON t.term_id = s.term_id
        {('WHERE ' + ' AND '.join(tw.clauses)) if tw.clauses else ''}
        GROUP BY b.ngram
        HAVING SUM(s.clicks) >= :min_clicks
        ORDER BY {_order(opts, alias='s').replace('s.cost_usd', 's.spend').replace('s.sales_usd', 's.sales')}
        LIMIT {_limit(opts, 1000)}""", {**w.params, **tw.params, "n": n, "min_clicks": min_clicks})
    for r in rows:
        with_ratios(r)
    cols = [col("ngram", f"Cụm {n} từ"), col("terms", "Số search term", "int")] + \
        [c for c in src.metrics if c["key"] not in ("retail_sales", "retail_roas")]
    return {"title": f"N-gram {n} từ",
            "note": "Mỗi cụm nhận toàn bộ số liệu của các search term chứa nó, nên không cộng tổng các dòng.",
            "tables": [_table("ngrams", f"Cụm {n} từ (≥ {min_clicks:g} click)", cols, rows, with_totals=False)]}


def harvest(f: Filters, opts: dict, src: TermSource = AMAZON) -> dict:
    min_orders = _num(opts, "min_orders", 2)
    max_acos = _num(opts, "max_acos", 0.30)
    neg_clicks = _num(opts, "neg_clicks", 15)
    neg_spend = _num(opts, "neg_spend", 20)
    w = src.where(f)
    w.add("f.term_id <> ''")
    _term_where(f, w)
    excluded = ", ".join(f"'{c}'" for c in src.excluded_classes) or "''"
    base = f"""
        SELECT f.term_id, MAX(t.term) AS term, MAX(t.term_class) AS term_class, MAX(t.length_bucket) AS length_bucket,
               GROUP_CONCAT(DISTINCT f.match_type ORDER BY f.match_type SEPARATOR ', ') AS match_type,
               SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT c.campaign_name ORDER BY c.campaign_name SEPARATOR ' | '), ' | ', 3)
                 AS campaigns,
               EXISTS (SELECT 1 FROM {src.keyword_fact} x WHERE x.term_id = f.term_id AND x.match_type = '{src.exact}')
                 AS has_exact,
               {src.sums()}
        FROM {src.search_term_fact} f
        {src.campaign_join}
        LEFT JOIN dim_term t ON t.term_id = f.term_id
        {w.sql()}
        GROUP BY f.term_id"""
    grand = grand_cols(", ".join(f"h.{k} AS {k}" for k in sum_names(src.sums())))
    harvest_rows = fetch_all(f"""SELECT h.*, {grand} FROM ({base}) h
        WHERE h.orders >= :min_orders AND h.spend / NULLIF(h.sales, 0) <= :max_acos AND h.has_exact = 0
          AND COALESCE(h.term_class, '') NOT IN ({excluded})
        ORDER BY h.orders DESC LIMIT {_limit(opts)}""", {**w.params, "min_orders": min_orders, "max_acos": max_acos})
    negative_rows = fetch_all(f"""SELECT h.*, {grand} FROM ({base}) h
        WHERE (h.clicks >= :neg_clicks AND COALESCE(h.orders, 0) = 0)
           OR (h.spend >= :neg_spend AND h.spend / NULLIF(h.sales, 0) > :neg_acos)
        ORDER BY h.spend DESC LIMIT {_limit(opts)}""",
                              {**w.params, "neg_clicks": neg_clicks, "neg_spend": neg_spend, "neg_acos": max_acos * 2})
    for rows in (harvest_rows, negative_rows):
        for r in rows:
            with_ratios(r)
            r["has_exact"] = "Có" if r.get("has_exact") else ""
        _label_class(rows)
    cols = [col("term", "Search term"), col("term_class_label", "Phân nhóm"), col("length_bucket", "Số từ"),
            col("match_type", "Match nguồn"), col("campaigns", "Campaign")] + src.metrics
    exact = src.exact.title()
    return {
        "title": "Gợi ý thêm từ khóa / phủ định",
        "tables": [
            _table("harvest", f"Nên thêm thành {exact} (≥ {min_orders:g} đơn, ACoS ≤ {max_acos:.0%}, chưa có {exact})",
                   cols, harvest_rows),
            _table("negative", f"Nên cân nhắc phủ định (≥ {neg_clicks:g} click không có đơn, hoặc spend ≥ ${neg_spend:g} "
                               f"và ACoS > {max_acos * 2:.0%})", cols + [col("has_exact", f"Đang là {exact}")], negative_rows),
        ],
    }


# ---------------------------------------------------------------- sản phẩm

def products(f: Filters, opts: dict) -> dict:
    level = opts.get("level", "product")
    nf = Filters(**{**f.__dict__, "group_ids": [], "brand_ids": []})
    w = campaign_where(nf)
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    if level == "asin":
        key_sel = "f.asin, MAX(f.sku) AS sku, MAX(p.product_sku) AS product_sku, MAX(p.title) AS title, MAX(p.group_name) AS group_name"
        group, ts_key, ts_field = "f.asin", "asin", "asin"
        cols = [col("asin", "ASIN"), col("sku", "Seller SKU"), col("product_sku", "SKU nội bộ"), col("title", "Sản phẩm"),
                col("group_name", "Nhóm")]
    elif level == "group":
        key_sel = "p.group_id, MAX(p.group_name) AS group_name, MAX(p.brand_name) AS brand_name, COUNT(DISTINCT f.asin) AS asins"
        group, ts_key, ts_field = "p.group_id", "group", "group_id"
        cols = [col("group_name", "Nhóm sản phẩm"), col("brand_name", "Brand"), col("asins", "Số ASIN QC", "int")]
    else:
        key_sel = ("f.product_id, MAX(p.product_sku) AS product_sku, MAX(p.title) AS title, MAX(p.brand_name) AS brand_name, "
                   "MAX(p.group_name) AS group_name, COUNT(DISTINCT f.asin) AS asins")
        group, ts_key, ts_field = "f.product_id", "product", "product_id"
        cols = [col("product_sku", "SKU"), col("title", "Sản phẩm"), col("brand_name", "Brand"),
                col("group_name", "Nhóm"), col("asins", "Số ASIN", "int")]
    rows = fetch_all(f"""
        SELECT {key_sel}, {sum_cols()}, {grand_cols(sum_cols())}
        FROM fact_product_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        LEFT JOIN dim_product p ON p.product_id = f.product_id
        {w.sql()}
        GROUP BY {group}
        ORDER BY {_order(opts)} LIMIT {_limit(opts)}""", w.params)
    ts = {r[ts_field]: r for r in total_sales(f, ts_key)}
    for r in rows:
        t = ts.get(r.get(ts_field), {})
        r["total_sales"], r["total_units"] = t.get("total_sales"), t.get("total_units")
        with_ratios(r)
    extra, profit_cols = ("total_sales",), []
    if level == "product":
        mix = {}  # giá vốn chuẩn theo từng nước bán, gộp theo số đơn vị
        for t in total_sales(f, "product_country"):
            mix.setdefault(t["product_id"], []).append((t["country_code"], t["total_units"], t["fba_units"]))
        for r in rows:
            r["mix"] = mix.get(r["product_id"])
        costs, chans = insights.load_costs()
        insights.add_profit(rows, costs, chans, "amazon")
        profit_cols = PROFIT_COLUMNS
        extra = ("total_sales", "profit_after")
    return {"title": "Sản phẩm (Sponsored Products)",
            "note": "Chỉ gồm SP vì chỉ SP có báo cáo theo ASIN quảng cáo. TACoS = Spend SP / Tổng doanh số của sản phẩm. "
                    "Giá vốn/đv: nhập tay ở tab Giá vốn & phí nếu có, nếu không lấy giá vốn chuẩn (sheet BOD) của từng nước "
                    "bán, FBA cho đơn FBA và WH cho đơn FBM, quy USD theo tỷ giá mới nhất.",
            "tables": [_table("products", "Hiệu suất theo sản phẩm", cols + METRIC_COLUMNS + TACOS_COLUMNS + profit_cols, rows,
                              extra_additive=extra)]}


def halo(f: Filters, opts: dict) -> dict:
    w = campaign_where(f, date_col="report_date")
    base_join = "JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type"
    summary = fetch_all(f"""SELECT f.ad_type, f.attribution, SUM(f.orders) AS orders, SUM(f.units) AS units,
            SUM(f.sales_usd) AS sales, SUM(f.ntb_orders) AS ntb_orders
        FROM fact_purchased_product_daily f {base_join} {w.sql()}
        GROUP BY f.ad_type, f.attribution ORDER BY sales DESC""", w.params)
    top = fetch_all(f"""SELECT f.purchased_asin, MAX(p.product_sku) AS product_sku, MAX(p.title) AS title,
            MAX(p.group_name) AS group_name, f.attribution, SUM(f.orders) AS orders, SUM(f.units) AS units,
            SUM(f.sales_usd) AS sales
        FROM fact_purchased_product_daily f {base_join}
        LEFT JOIN map_asin_product m ON m.asin = f.purchased_asin
        LEFT JOIN dim_product p ON p.product_id = m.product_id
        {w.sql()}
        GROUP BY f.purchased_asin, f.attribution ORDER BY sales DESC LIMIT {_limit(opts)}""", w.params)
    labels = {"SP_HALO": "SP - mua ASIN khác", "PROMOTED": "SB - Promoted", "BRAND_HALO": "SB - Brand Halo"}
    for r in summary + top:
        r["attribution_label"] = labels.get(r["attribution"], r["attribution"])
        r["sales"] = r["sales"] or 0
    m = [col("orders", "Orders", "int"), col("units", "Units", "int"), col("sales", "Sales", "money")]
    return {"title": "Halo & Brand Halo",
            "tables": [
                _table("summary", "Tổng hợp theo loại quy đổi", [col("ad_type", "Loại"), col("attribution_label", "Quy đổi")] + m
                       + [col("ntb_orders", "NTB Orders", "int")], summary, with_totals=False),
                _table("top", "ASIN được mua nhiều nhất", [col("purchased_asin", "ASIN được mua"), col("product_sku", "SKU"),
                       col("title", "Sản phẩm"), col("group_name", "Nhóm"), col("attribution_label", "Quy đổi")] + m,
                       top, with_totals=False),
            ]}


# ---------------------------------------------------------------- placement SB, ngân sách

def placements(f: Filters, opts: dict) -> dict:
    nf = Filters(**{**f.__dict__, "ad_types": []})
    w = campaign_where(nf)
    rows = fetch_all(f"""SELECT f.placement_id, COALESCE(MAX(pl.placement_name), f.placement_id) AS placement, {sum_cols()}
        FROM fact_placement_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        LEFT JOIN dim_placement pl ON pl.placement_id = f.placement_id
        {w.sql()} GROUP BY f.placement_id ORDER BY spend DESC""", w.params)
    by_campaign = fetch_all(f"""SELECT f.campaign_id, MAX(c.campaign_name) AS campaign_name,
            COALESCE(MAX(pl.placement_name), f.placement_id) AS placement, {sum_cols()}, {grand_cols(sum_cols())}
        FROM fact_placement_daily f
        JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        LEFT JOIN dim_placement pl ON pl.placement_id = f.placement_id
        {w.sql()} GROUP BY f.campaign_id, f.placement_id ORDER BY {_order(opts)} LIMIT {_limit(opts)}""", w.params)
    for r in rows + by_campaign:
        with_ratios(r)
    return {"title": "Placement Sponsored Brands",
            "tables": [_table("placements", "Theo vị trí hiển thị", [col("placement", "Placement")] + METRIC_COLUMNS + NTB_COLUMNS, rows),
                       _table("by_campaign", "Campaign × Placement", [col("campaign_name", "Campaign"), col("placement", "Placement")]
                              + METRIC_COLUMNS + NTB_COLUMNS, by_campaign)]}


def budget(f: Filters, opts: dict) -> dict:
    w = campaign_where(f, alias="b")
    rows = fetch_all(f"""
        SELECT b.ad_type, b.campaign_id, MAX(c.campaign_name) AS campaign_name, MAX(a.account_label) AS account,
               SUBSTRING_INDEX(GROUP_CONCAT(b.state ORDER BY b.report_date DESC SEPARATOR '|'), '|', 1) AS state,
               MAX(b.budget_type) AS budget_type, AVG(b.budget_usd) AS avg_budget,
               SUM(b.budget_usd) AS budget_sum, SUM(COALESCE(s.spend, 0)) AS spend, SUM(COALESCE(s.sales, 0)) AS sales,
               COUNT(*) AS days, SUM(COALESCE(s.spend, 0) >= 0.95 * b.budget_usd) AS days_capped,
               AVG(b.top_of_search_is) AS top_of_search_is
        FROM fact_campaign_budget_daily b
        JOIN dim_campaign c ON c.campaign_id = b.campaign_id AND c.ad_type = b.ad_type
        LEFT JOIN dim_account a ON a.profile_id = b.profile_id
        LEFT JOIN (SELECT report_date, ad_type, campaign_id, SUM(cost_usd) AS spend, SUM(sales_usd) AS sales
                   FROM fact_campaign_daily WHERE report_date BETWEEN :start AND :end
                   GROUP BY report_date, ad_type, campaign_id) s
               ON s.report_date = b.report_date AND s.ad_type = b.ad_type AND s.campaign_id = b.campaign_id
        {w.sql()}
        GROUP BY b.ad_type, b.campaign_id
        ORDER BY days_capped DESC, spend DESC LIMIT {_limit(opts)}""", w.params)
    for r in rows:
        r["utilization"] = (r["spend"] / r["budget_sum"]) if r.get("budget_sum") else None
        r["acos"] = (r["spend"] / r["sales"]) if r.get("sales") else None
    cols = [col("account", "Tài khoản"), col("ad_type", "Loại"), col("campaign_name", "Campaign"), col("state", "Trạng thái"),
            col("budget_type", "Loại NS"), col("avg_budget", "NS TB/ngày", "money"), col("spend", "Spend", "money"),
            col("utilization", "% dùng NS", "pct"), col("days", "Số ngày", "int"), col("days_capped", "Ngày hết NS", "int"),
            col("acos", "ACoS", "pct"), col("top_of_search_is", "TOS IS", "pct")]
    return {"title": "Ngân sách campaign",
            "note": "Ngày hết NS = ngày có spend ≥ 95% ngân sách ngày. Campaign hết ngân sách thường xuyên mà ACoS tốt nên tăng ngân sách.",
            "tables": [_table("budget", "Mức sử dụng ngân sách", cols, rows, with_totals=False)]}


REPORTS = {
    "overview": overview,
    "campaigns": campaigns,
    "targets": targets,
    "search_terms": search_terms,
    "keyword_analysis": keyword_analysis,
    "ngrams": ngrams,
    "harvest": harvest,
    "products": products,
    "halo": halo,
    "placements": placements,
    "budget": budget,
}
