"""Tab Lợi nhuận (P&L công ty) trong mục Tổng hợp. Nguồn: fact_pnl_daily do etl/pnl.py tính mỗi lần chạy ETL.

PL4 = DT thuần − phí kênh − giá vốn − QC (ĐGMK, chi phí QC thật). PL5 = PL4 − phí kho & vận chuyển.
Giá vốn chuẩn BOD đã gồm phí vận hành và phí hoàn hàng nên không có hai dòng riêng (etl/pnl.py). Phần ước tính (chưa có settlement / hóa đơn) hiện ở cột "% ước tính".
"""
from app.db import fetch_all
from app.filters import Filters, Where
from app.metrics import col
from app.reports import _table
from app.reports_all import CHANNEL_LABELS, COMPANY_OTHER, compare_period, company_of
from app.reports_shop import period_key, period_labels
from app.viz import chart, series

LINES = [  # (khóa, nhãn, dấu khi cộng vào lợi nhuận)
    ("net_rev", "Doanh thu thuần", 1), ("fee_commission", "  Phí giới thiệu / cổng thanh toán", -1),
    ("fee_fulfil", "  Phí FBA / giao hàng của sàn", -1), ("fee_other", "  Phí khác (allowance, coupon, bồi hoàn…)", -1),
    ("channel_fee", "Phí kênh", -1), ("cogs", "Giá vốn chuẩn BOD (gồm vận hành, hoàn hàng)", -1),
    ("ads", "Quảng cáo (ĐGMK, chi phí thật)", -1), ("pl4", "PL4", 1), ("wh_3pl", "  Kho 3PL", -1),
    ("wh_fba", "  Kho FBA (lưu kho, inbound, hủy…)", -1), ("wh_cg", "  CastleGate", -1),
    ("wh_ship", "  Nhãn ship (FBM, dropship, website)", -1), ("warehouse_fee", "Phí kho & vận chuyển", -1),
    ("pl5", "PL5", 1),
]
EST = {"channel_fee": "channel_fee_est", "cogs": "cogs_est", "warehouse_fee": "warehouse_fee_est"}
SUMS = ["units", "gross_rev", "promo", "net_rev", "fee_commission", "fee_fulfil", "fee_other", "channel_fee",
        "channel_fee_est", "cogs", "cogs_est", "return_fee", "ads", "pl4", "wh_3pl", "wh_fba", "wh_cg", "wh_ship",
        "warehouse_fee", "warehouse_fee_est", "operation_fee", "operation_fee_est", "pl5"]
MONEY = [k for k in SUMS if not k.endswith("_est")]

KPI_DEF = [
    ["net_rev", "Doanh thu thuần", "money", 1, True], ["pl4", "PL4", "money", 1, True],
    ["pl4_margin", "Biên PL4", "pct", 1, True], ["pl5", "PL5", "money", 1, True], ["pl5_margin", "Biên PL5", "pct", 1, True],
    ["channel_fee", "Phí kênh", "money", -1, False], ["cogs", "Giá vốn", "money", -1, False],
    ["ads", "Quảng cáo", "money", -1, False], ["warehouse_fee", "Phí kho & vận chuyển", "money", -1, False],
    ["est_share", "% chi phí đang ước tính", "pct", -1, False], ["units", "Units", "int", 1, False],
]


def ratios(r: dict) -> dict:
    for k in SUMS:
        r[k] = float(r.get(k) or 0)
    rev = r["net_rev"]
    div = (lambda a: a / rev) if rev else (lambda a: None)
    r["pl4_margin"], r["pl5_margin"] = div(r["pl4"]), div(r["pl5"])
    for k in ("channel_fee", "cogs", "ads", "warehouse_fee"):
        r[k + "_pct"] = div(r[k])
    costs = sum(r[k] for k in EST)
    r["est_share"] = (sum(r[v] for v in EST.values()) / costs) if costs else None
    r["gross_margin"] = div(rev - r["channel_fee"] - r["cogs"])
    if "prev_pl5" in r:
        r["pl5_change"] = r["pl5"] - float(r["prev_pl5"] or 0)
    return r


def _where(f: Filters) -> Where:
    w = Where()
    w._n = 8000
    w.add("x.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    w.add_in("x.cc", f.countries)
    w.add_in("x.ch", f.sales_channels)
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    return w


def _query(f: Filters, keys: str = "", group: str | None = None, period: str | None = None, order: str = "",
           limit: int | None = None) -> list[dict]:
    """Tổng các khoản theo `keys` (cột chọn), nhóm theo `group` (mặc định = keys), thêm cột kỳ `d` nếu có `period`."""
    w = _where(f)
    grp = [g for g in ((keys if group is None else group), period) if g]
    sel = ", ".join(x for x in (keys, f"{period} AS d" if period else "") if x)
    sums = ", ".join(f"SUM(x.{k}) AS {k}" for k in SUMS)
    sql = f"""SELECT {sel + ', ' if sel else ''}{sums} FROM fact_pnl_daily x LEFT JOIN dim_product p ON p.product_id = x.product_id
              {w.sql()} {('GROUP BY ' + ', '.join(grp)) if grp else ''} {order} {f'LIMIT {int(limit)}' if limit else ''}"""
    return fetch_all(sql, w.params)


def _freshness() -> list[dict]:
    try:
        return fetch_all("SELECT source, actual_to, note, computed_at FROM pnl_run ORDER BY source")
    except Exception:
        return []


SOURCE_LABELS = {"amazon_order_fee": "Phí Amazon theo đơn (settlement)", "amazon_account_fee": "Phí Amazon cấp tài khoản",
                 "ads": "Quảng cáo", "wh_3pl": "Kho 3PL", "wh_cg": "CastleGate", "wh_ship": "Nhãn ship",
                 "operation_fee": "Phí vận hành & hoàn hàng"}


def pnl_overview(f: Filters, opts: dict) -> dict:
    prev, prev_label = compare_period(f, opts.get("compare"))
    cur = ratios((_query(f) or [{}])[0])
    prv = ratios((_query(prev) or [{}])[0])

    # ---- bảng P&L dạng dòng
    pl_rows = []
    rev = cur["net_rev"] or None
    for k, label, sign in LINES:
        v = cur[k]
        pl_rows.append({"line": label, "amount": v if sign > 0 else -v, "pct": (v / rev) if rev else None,
                        "prev": prv[k] if sign > 0 else -prv[k],
                        "prev_pct": (prv[k] / prv["net_rev"]) if prv["net_rev"] else None,
                        "est": (cur[EST[k]] / v) if k in EST and v else None})
    t_pl = _table("pnl", "Báo cáo P&L", [col("line", "Khoản mục"), col("amount", "Kỳ này", "money"),
                                         col("pct", "% DT thuần", "pct"), col("prev", "Kỳ so sánh", "money"),
                                         col("prev_pct", "% DT kỳ so sánh", "pct"), col("est", "Phần ước tính", "pct")],
                  pl_rows, with_totals=False)

    line_cols = [col("net_rev", "DT thuần", "money"), col("channel_fee", "Phí kênh", "money"),
                 col("channel_fee_pct", "% phí kênh", "pct"), col("cogs", "Giá vốn", "money"), col("cogs_pct", "% giá vốn", "pct"),
                 col("gross_margin", "Biên sau phí & giá vốn", "pct"),
                 col("ads", "QC", "money"), col("ads_pct", "% QC", "pct"), col("pl4", "PL4", "money"),
                 col("pl4_margin", "Biên PL4", "pct"), col("warehouse_fee", "Kho & ship", "money"),
                 col("warehouse_fee_pct", "% kho & ship", "pct"),
                 col("pl5", "PL5", "money"), col("pl5_margin", "Biên PL5", "pct"), col("est_share", "% CP ước tính", "pct")]

    def table(key, title, first_cols, rows):
        for r in rows:
            ratios(r)
        t = _table(key, title, first_cols + line_cols, rows, with_totals=False)
        if rows:
            tot = {k: sum(float(r.get(k) or 0) for r in rows) for k in SUMS}
            t["totals"] = ratios(tot)
        t["keep_order"] = True
        return t

    # ---- kênh × nước
    by_cc = _query(f, "x.ch, x.cc", order="ORDER BY SUM(x.net_rev) DESC")
    for r in by_cc:
        r["channel"], r["country"] = CHANNEL_LABELS.get(r["ch"], r["ch"]), r["cc"]
    t_cc = table("by_channel", "Theo kênh × nước", [col("channel", "Kênh"), col("country", "Nước")], by_cc)

    # ---- công ty
    companies: dict = {}
    for r in _query(f, "x.co"):
        name = company_of(r["co"]) if r["co"] else COMPANY_OTHER
        c = companies.setdefault(name, {"company": name})
        for k in SUMS:
            c[k] = c.get(k, 0.0) + float(r[k] or 0)
    by_co = sorted(companies.values(), key=lambda c: (c["company"] == COMPANY_OTHER, -c["net_rev"]))
    t_co = table("by_company", "Theo công ty", [col("company", "Công ty")], by_co)

    # ---- nhóm SP
    by_grp = _query(f, "p.group_id, MAX(p.group_name) AS group_name", group="p.group_id", order="ORDER BY SUM(x.net_rev) DESC")
    for r in by_grp:
        r["group_name"] = r["group_name"] or "(chưa gán nhóm / QC chung)"
    t_grp = table("by_group", "Theo nhóm SP", [col("group_name", "Nhóm SP")], by_grp)

    # ---- SKU: 300 SKU doanh thu cao nhất + 100 SKU lỗ PL5 nhiều nhất
    sku_keys = "x.product_id, MAX(p.product_sku) AS product_sku, MAX(p.short_name) AS product, MAX(p.group_name) AS group_name"
    top = _query(f, sku_keys, group="x.product_id", order="ORDER BY SUM(x.net_rev) DESC", limit=300)
    worst = _query(f, sku_keys, group="x.product_id", order="ORDER BY SUM(x.pl5) ASC", limit=100)
    seen, skus = set(), []
    for r in top + worst:
        if r["product_id"] in seen:
            continue
        seen.add(r["product_id"])
        r["product_sku"] = r["product_sku"] or ("(không gắn SP)" if not r["product_id"] else r["product_id"])
        skus.append(r)
    skus.sort(key=lambda r: -float(r["net_rev"] or 0))
    sku_cols = [col("product_sku", "SKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"), col("units", "Units", "int")]
    t_sku = table("by_sku", "Theo SKU (300 SKU doanh thu cao nhất + 100 SKU lỗ PL5 nhiều nhất)", sku_cols, skus)
    t_sku.pop("totals", None)

    # ---- độ mới của từng nguồn phí
    fresh = [{"source": SOURCE_LABELS.get(r["source"], r["source"]), "actual_to": r["actual_to"], "note": r["note"],
              "computed_at": r["computed_at"]} for r in _freshness()]
    t_fresh = _table("sources", "Nguồn phí: số thật đến ngày", [col("source", "Nguồn"), col("actual_to", "Số thật đến", "date"),
                                                             col("note", "Ghi chú"), col("computed_at", "Tính lúc")],
                     fresh, with_totals=False)

    # ---- đồ thị theo ngày / tuần
    pk, unit = period_key(f, "x.report_date")
    labels = period_labels(f, unit == "tuần")
    idx = {d: i for i, d in enumerate(labels)}
    vals = {k: [0.0] * len(labels) for k in ("net_rev", "pl4", "pl5", "channel_fee", "cogs", "ads", "warehouse_fee")}
    for r in _query(f, period=pk):
        if r["d"] and r["d"].isoformat() in idx:
            i = idx[r["d"].isoformat()]
            for k in vals:
                vals[k][i] += float(r[k] or 0)
    margin4 = [(a / b) if b else None for a, b in zip(vals["pl4"], vals["net_rev"])]
    margin5 = [(a / b) if b else None for a, b in zip(vals["pl5"], vals["net_rev"])]
    # thác nước: DT thuần → PL4 → PL5
    steps = [("Phí kênh", cur["channel_fee"]), ("Giá vốn", cur["cogs"]), ("Quảng cáo", cur["ads"]), ("PL4", None),
             ("Kho & ship", cur["warehouse_fee"]), ("PL5", None)]
    level = cur["net_rev"]
    wf_labels, wf_vals, wf_raw, wf_colors = ["DT thuần"], [[0, level]], [level], ["n1"]
    for name, v in steps:
        wf_labels.append(name)
        if v is None:  # cột tổng
            wf_vals.append([0, level])
            wf_raw.append(level)
            wf_colors.append("c1" if level >= 0 else "c2")
        else:
            wf_vals.append([level - v, level])
            wf_raw.append(-v)
            wf_colors.append("c2" if v >= 0 else "c1")
            level -= v
    viz = [
        chart("pnl_waterfall", "Từ doanh thu thuần đến PL4, PL5", "waterfall", wf_labels,
              [series("P&L", "c1", wf_vals, colors=wf_colors, raw=wf_raw)], unit="money",
              min=min(0, min(min(v) for v in wf_vals)),
              subtitle="Số của cả kỳ đang xem, đã gồm phần ước tính."),
        chart("pnl_trend", f"Doanh thu thuần, PL4 và PL5 theo {unit}", "bar", labels,
              [series("DT thuần", "c1", vals["net_rev"]), series("PL4", "c3", vals["pl4"]), series("PL5", "c2", vals["pl5"])],
              unit="money", subtitle="Ngày gần nhất: phí đang ước tính nhiều hơn (xem bảng Nguồn phí)."),
        chart("pnl_costs", f"Cơ cấu chi phí theo {unit}", "bar_stacked", labels,
              [series("Giá vốn", "c1", vals["cogs"]), series("Phí kênh", "c2", vals["channel_fee"]),
               series("QC", "c3", vals["ads"]), series("Kho & ship", "c5", vals["warehouse_fee"])],
              unit="money"),
        chart("pnl_margin", f"Biên PL4 / PL5 theo {unit}", "line", labels,
              [series("Biên PL4", "c3", margin4, line=True, unit="pct"),
               series("Biên PL5", "c2", margin5, line=True, unit="pct")], unit="pct"),
    ]
    viz = [v for v in viz if v["series"]]

    note = ("P&L theo cấu trúc của công ty: PL4 = DT thuần − phí kênh − giá vốn − quảng cáo; PL5 = PL4 − phí kho & "
            "vận chuyển. Giá vốn chuẩn BOD đã gồm phí vận hành và phí hoàn hàng nên không trừ riêng hai khoản này. "
            "Tính theo ngày đặt đơn, USD. "
            "DT thuần: Amazon giá bán − khuyến mãi (bỏ đơn hủy), Wayfair giá sỉ, Shopify sau giảm giá. "
            "Phí Amazon lấy từ settlement theo từng đơn; đơn chưa có settlement (khoảng 2–3 tuần gần nhất) được giả lập theo "
            "tỷ lệ phí lịch sử của SKU (sai lệch khi kiểm tra lại khoảng ±1–3%). Phí cấp tài khoản Amazon, 3PL, CastleGate: "
            "tháng chưa có số thật ước theo tỷ lệ phí / doanh thu của 3 tháng gần nhất. "
            "Quảng cáo là chi phí thật (Amazon, Wayfair, Shopify nhập tay; chưa có Walmart). "
            f"So sánh với {prev_label}.")
    return {
        "title": "Lợi nhuận (P&L công ty)",
        "note": note,
        "viz": viz,
        "kpis": {"current": cur, "previous": prv, "prev_label": prev_label, "def": KPI_DEF},
        "tables": [t_pl, t_cc, t_co, t_grp, t_sku, t_fresh],
    }


PNL_REPORTS = {"pnl_overview": pnl_overview}
