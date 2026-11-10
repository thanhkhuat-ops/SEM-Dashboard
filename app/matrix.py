"""Matrix Chart: một đồ thị chính (và một đồ thị phụ) với các chỉ số người dùng tự chọn, chung trục thời gian.

Mỗi chỉ số trong METRICS là một công thức trên các nguồn theo ngày (SOURCES):
- ("col", nguồn, cột): cộng dồn được (tiền, số lượng)
- ("ratio", (nguồn, cột), (nguồn, cột)): tỷ lệ tính lại từ tổng tử / tổng mẫu của từng kỳ (ngày / tuần / tháng),
  không lấy trung bình các ngày, vd ACoS tuần = Spend tuần ÷ Ad Sales tuần
- ("diff", (nguồn, cột), (nguồn, cột)): hiệu, vd doanh số tự nhiên = tổng DS − DS QC (âm thì vẽ 0)
Chỉ chạy những nguồn mà các đồ thị đang chọn cần, song song.

Bộ lọc: ngày, Nhóm SP, Brand, PIC (đã đổi thành nhóm SP), Nước áp cho mọi nguồn. Tài khoản / Loại QC / Portfolio
Amazon chỉ áp cho nguồn Amazon, tài khoản Wayfair chỉ cho nguồn Wayfair. Loại QC, Portfolio, tên campaign không áp
được cho tổng doanh số (đơn hàng không gắn với campaign), giống các tab Tổng quan.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from app.db import fetch_all
from app.filters import Filters, Where, campaign_where, wf_where

GRANS = {"day": "ngày", "week": "tuần", "month": "tháng"}


# ---------------------------------------------------------------- nguồn theo ngày

def _amz_market(w: Where, f: Filters, alias: str) -> None:
    if f.countries:
        sub = Where()
        sub._n = 6000
        sub.add_in("a.country_code", f.countries)
        w.add(f"EXISTS (SELECT 1 FROM dim_account a WHERE a.profile_id = {alias}.profile_id AND {sub.clauses[0]})",
              **sub.params)


def _amz_ads(f: Filters) -> list[dict]:
    w = campaign_where(f)
    _amz_market(w, f, "f")
    return fetch_all(f"""SELECT f.report_date AS d, SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks,
            SUM(f.cost_usd) AS spend, SUM(f.orders) AS orders, SUM(f.units) AS units, SUM(f.sales_usd) AS sales,
            SUM(f.ntb_orders) AS ntb_orders
        FROM fact_campaign_daily f JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        {w.sql()} GROUP BY f.report_date""", w.params)


def _amz_total(f: Filters) -> list[dict]:
    """Như reports.total_sales(f, 'date'), thêm lọc nước."""
    w = Where().add("t.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    w._n = 6100
    scope = Where()
    scope._n = 6200
    scope.add_in("a.profile_id", f.profile_ids)
    w.add("EXISTS (SELECT 1 FROM dim_account a WHERE a.store_account_id = t.store_account_id "
          "AND a.country_code = t.country_code" + (" AND " + " AND ".join(scope.clauses) if scope.clauses else "")
          + ")", **scope.params)
    w.add_in("t.country_code", f.countries)
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    return fetch_all(f"""SELECT t.report_date AS d, SUM(t.sales_usd) AS total_sales, SUM(t.units) AS total_units,
            SUM(t.order_items) AS order_items, SUM(t.fba_order_items) AS fba_order_items
        FROM fact_total_sales_daily t LEFT JOIN dim_product p ON p.product_id = t.product_id
        {w.sql()} GROUP BY t.report_date""", w.params)


def _wf_ads(f: Filters) -> list[dict]:
    w = wf_where(f)
    w.add_in("f.country_code", f.countries)
    return fetch_all(f"""SELECT f.report_date AS d, SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks,
            SUM(f.cost_usd) AS spend, SUM(f.orders) AS orders, SUM(f.units) AS units, SUM(f.sales_usd) AS sales,
            SUM(f.retail_sales_usd) AS retail_sales
        FROM fact_wf_campaign_daily f JOIN dim_wf_campaign c ON c.campaign_id = f.campaign_id
        {w.sql()} GROUP BY f.report_date""", w.params)


def _wf_total(f: Filters) -> list[dict]:
    """Như reports_wf.wf_total_sales(f, 'date'), thêm lọc nước."""
    w = Where().add("t.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    w._n = 6300
    w.add_in("CONCAT(t.account_id, '-', t.country_code)", f.wf_accounts)
    w.add_in("t.country_code", f.countries)
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    return fetch_all(f"""SELECT t.report_date AS d, SUM(t.sales_usd) AS total_sales, SUM(t.units) AS total_units,
            SUM(t.order_lines) AS order_lines,
            SUM(CASE WHEN t.order_type = 'castle_gate' THEN t.order_lines END) AS cg_lines
        FROM fact_wf_total_sales_daily t LEFT JOIN dim_product p ON p.product_id = t.product_id
        {w.sql()} GROUP BY t.report_date""", w.params)


SOURCES = {"amz_ads": _amz_ads, "amz_total": _amz_total, "wf_ads": _wf_ads, "wf_total": _wf_total}


# ---------------------------------------------------------------- danh mục chỉ số

def col(src, c):
    return ("col", src, c)


def ratio(a, b):
    return ("ratio", a, b)


def diff(a, b):
    return ("diff", a, b)


AMZ_NOTE = "Amazon QC: lọc theo tài khoản, loại QC, portfolio, campaign, nhóm SP, brand, nước."
AMZ_TOTAL_NOTE = ("Amazon tổng: mọi đơn (bỏ đơn hủy) theo giá bán lẻ; loại QC / portfolio / campaign không áp cho đơn "
                  "hàng.")
WF_NOTE = "Wayfair QC: lọc theo tài khoản, campaign, nhóm SP, brand, nước; doanh số theo giá sỉ."
WF_TOTAL_NOTE = "Wayfair tổng: mọi đơn theo giá sỉ (đã trừ hoa hồng); campaign không áp cho đơn hàng."


def _m(id_, group, label, unit, formula, note):
    return {"id": id_, "group": group, "label": label, "unit": unit, "formula": formula, "note": note}


def _platform(p: str, ads: str, total: str, note: str, total_note: str, sales_label: str) -> list[dict]:
    """Bộ chỉ số giống nhau cho hai sàn (p = amz / wf)."""
    g = "Amazon" if p == "amz" else "Wayfair"
    sx = " (sỉ)" if p == "wf" else ""
    return [
        _m(f"{p}_spend", g, "Spend", "money", col(ads, "spend"), note),
        _m(f"{p}_ad_sales", g, sales_label, "money", col(ads, "sales"), note),
        _m(f"{p}_total_sales", g, "Tổng doanh số" + sx, "money", col(total, "total_sales"), total_note),
        _m(f"{p}_organic", g, "DS tự nhiên (ước tính)" + sx, "money", diff((total, "total_sales"), (ads, "sales")),
           f"DS tự nhiên = tổng DS − {sales_label}, âm thì 0."),
        _m(f"{p}_acos", g, "ACoS", "pct", ratio((ads, "spend"), (ads, "sales")), f"ACoS = Spend ÷ {sales_label}."),
        _m(f"{p}_tacos", g, "TACoS", "pct", ratio((ads, "spend"), (total, "total_sales")),
           "TACoS = Spend ÷ tổng doanh số."),
        _m(f"{p}_ad_share", g, "Tỷ trọng DS QC", "pct", ratio((ads, "sales"), (total, "total_sales")),
           f"Tỷ trọng DS QC = {sales_label} ÷ tổng doanh số."),
        _m(f"{p}_impressions", g, "Impressions", "int", col(ads, "impressions"), note),
        _m(f"{p}_clicks", g, "Clicks", "int", col(ads, "clicks"), note),
        _m(f"{p}_orders", g, "Orders từ QC", "int", col(ads, "orders"), note),
        _m(f"{p}_ctr", g, "CTR", "pct", ratio((ads, "clicks"), (ads, "impressions")), "CTR = Clicks ÷ Impressions."),
        _m(f"{p}_cvr", g, "CVR", "pct", ratio((ads, "orders"), (ads, "clicks")), "CVR = Orders ÷ Clicks."),
        _m(f"{p}_cpc", g, "CPC", "money", ratio((ads, "spend"), (ads, "clicks")), "CPC = Spend ÷ Clicks."),
        _m(f"{p}_cpa", g, "CPA", "money", ratio((ads, "spend"), (ads, "orders")), "CPA = Spend ÷ Orders."),
        _m(f"{p}_total_units", g, "Tổng đơn vị bán", "int", col(total, "total_units"), total_note),
    ]


METRICS = (
    _platform("amz", "amz_ads", "amz_total", AMZ_NOTE, AMZ_TOTAL_NOTE, "Ad Sales")
    + [_m("amz_ntb_orders", "Amazon", "Orders khách mới (NTB)", "int", col("amz_ads", "ntb_orders"), AMZ_NOTE),
       _m("amz_fba_lines", "Amazon", "Dòng đơn FBA", "int", col("amz_total", "fba_order_items"), AMZ_TOTAL_NOTE),
       _m("amz_fbm_lines", "Amazon", "Dòng đơn FBM", "int",
          diff(("amz_total", "order_items"), ("amz_total", "fba_order_items")), AMZ_TOTAL_NOTE)]
    + _platform("wf", "wf_ads", "wf_total", WF_NOTE, WF_TOTAL_NOTE, "DS QC (sỉ)")
    + [_m("wf_cg_lines", "Wayfair", "Dòng đơn CastleGate", "int", col("wf_total", "cg_lines"), WF_TOTAL_NOTE),
       _m("wf_ds_lines", "Wayfair", "Dòng đơn Dropship", "int",
          diff(("wf_total", "order_lines"), ("wf_total", "cg_lines")), WF_TOTAL_NOTE)]
)
BY_ID = {m["id"]: m for m in METRICS}

# bộ chọn sẵn: (tên, [(chỉ số, kiểu vẽ)], chế độ, chồng cột). Kiểu: bar / line. Chế độ: value / index / change.
PRESETS = [
    ("Amazon: Spend, ACoS và TACoS", [("amz_spend", "bar"), ("amz_acos", "line"), ("amz_tacos", "line")], "value", False),
    ("Amazon: Spend và tổng DS (kỳ đầu = 100)", [("amz_spend", "line"), ("amz_total_sales", "line")], "index", False),
    ("Amazon: Spend và ACoS", [("amz_spend", "bar"), ("amz_acos", "line")], "value", False),
    ("Amazon: DS từ QC và tự nhiên", [("amz_ad_sales", "bar"), ("amz_organic", "bar"), ("amz_tacos", "line")],
     "value", True),
    ("Amazon: phễu QC (kỳ đầu = 100)", [("amz_impressions", "line"), ("amz_clicks", "line"), ("amz_orders", "line"),
                                        ("amz_spend", "line")], "index", False),
    ("Amazon: CTR và CVR", [("amz_ctr", "line"), ("amz_cvr", "line")], "value", False),
    ("Amazon: CPC và CPA", [("amz_cpc", "line"), ("amz_cpa", "line")], "value", False),
    ("Amazon: dòng đơn FBA và FBM", [("amz_fba_lines", "bar"), ("amz_fbm_lines", "bar")], "value", True),
    ("Wayfair: Spend, ACoS và TACoS", [("wf_spend", "bar"), ("wf_acos", "line"), ("wf_tacos", "line")], "value", False),
    ("Wayfair: Spend và tổng DS (kỳ đầu = 100)", [("wf_spend", "line"), ("wf_total_sales", "line")], "index", False),
    ("Wayfair: Spend và ACoS", [("wf_spend", "bar"), ("wf_acos", "line")], "value", False),
    ("Wayfair: DS từ QC và tự nhiên", [("wf_ad_sales", "bar"), ("wf_organic", "bar"), ("wf_tacos", "line")],
     "value", True),
    ("Wayfair: phễu QC (kỳ đầu = 100)", [("wf_impressions", "line"), ("wf_clicks", "line"), ("wf_orders", "line"),
                                         ("wf_spend", "line")], "index", False),
    ("Wayfair: CTR và CVR", [("wf_ctr", "line"), ("wf_cvr", "line")], "value", False),
    ("Wayfair: dòng đơn CastleGate và Dropship", [("wf_cg_lines", "bar"), ("wf_ds_lines", "bar")], "value", True),
    ("Hai sàn: Spend", [("amz_spend", "line"), ("wf_spend", "line")], "value", False),
    ("Hai sàn: tổng DS (kỳ đầu = 100)", [("amz_total_sales", "line"), ("wf_total_sales", "line")], "index", False),
    ("Hai sàn: ACoS và TACoS", [("amz_acos", "line"), ("wf_acos", "line"), ("amz_tacos", "line"),
                                ("wf_tacos", "line")], "value", False),
]
DEFAULT = [0, 8]  # bộ chọn sẵn cho đồ thị chính, đồ thị phụ
MAX_METRICS = 6  # mỗi đồ thị


def catalog() -> dict:
    return {"metrics": [{k: m[k] for k in ("id", "group", "label", "unit", "note")} for m in METRICS],
            "presets": [{"name": n, "metrics": [{"id": i, "style": s} for i, s in ms], "mode": mode, "stack": stack}
                        for n, ms, mode, stack in PRESETS],
            "default": DEFAULT, "grans": GRANS, "max_metrics": MAX_METRICS}


# ---------------------------------------------------------------- tính

def _refs(formula) -> list[tuple[str, str]]:
    return [(formula[1], formula[2])] if formula[0] == "col" else [formula[1], formula[2]]


def bucket_of(d: date, gran: str) -> date:
    if gran == "week":
        return d - timedelta(days=d.weekday())
    if gran == "month":
        return d.replace(day=1)
    return d


def bucket_labels(f: Filters, gran: str) -> list[date]:
    out, d = [], bucket_of(f.start, gran)
    while d <= f.end:
        out.append(d)
        d = (d + timedelta(days=32)).replace(day=1) if gran == "month" else d + timedelta(days=7 if gran == "week" else 1)
    return out


def pick_gran(f: Filters, gran: str | None) -> str:
    if gran in GRANS:
        return gran
    days = (f.end - f.start).days + 1
    return "day" if days <= 62 else "week" if days <= 370 else "month"


def _num(v) -> float | None:
    return float(v) if v is not None else None


def _eval(formula, sums: dict, src_has: dict, clamp: bool = True):
    """sums[(nguồn, cột)] = tổng trong kỳ; src_has[nguồn] = nguồn có dòng nào trong kỳ (không thì để trống, không vẽ 0).
    clamp=False: hiệu giữ cả phần âm (để tổng chú giải khớp tab Tổng quan: QC + tự nhiên = tổng DS)."""
    kind = formula[0]
    if kind == "col":
        return sums.get((formula[1], formula[2]), 0.0) if src_has.get(formula[1]) else None
    a, b = formula[1], formula[2]
    if not src_has.get(a[0]) or not src_has.get(b[0]):
        return None
    va, vb = sums.get(a, 0.0), sums.get(b, 0.0)
    if kind == "ratio":
        return va / vb if vb else None
    return max(va - vb, 0.0) if clamp else va - vb


def build(f: Filters, ids: list[str], gran: str | None = None) -> dict:
    metrics = [BY_ID[i] for i in dict.fromkeys(ids) if i in BY_ID]
    gran = pick_gran(f, gran)
    need = sorted({ref[0] for m in metrics for ref in _refs(m["formula"])})
    with ThreadPoolExecutor(max_workers=max(len(need), 1)) as ex:
        data = dict(zip(need, ex.map(lambda s: SOURCES[s](f), need)))
    labels = bucket_labels(f, gran)
    index = {d: i for i, d in enumerate(labels)}
    # cộng theo kỳ: per[i][(nguồn, cột)]; has[i][nguồn]
    per = [dict() for _ in labels]
    has = [dict() for _ in labels]
    total, total_has = {}, {}
    for src, rows in data.items():
        for r in rows:
            i = index.get(bucket_of(r["d"], gran))
            if i is None:
                continue
            has[i][src] = total_has[src] = True
            for k, v in r.items():
                if k == "d" or v is None:
                    continue
                per[i][(src, k)] = per[i].get((src, k), 0.0) + float(v)
                total[(src, k)] = total.get((src, k), 0.0) + float(v)
    out = []
    for m in metrics:
        fm = m["formula"]
        values = [_eval(fm, per[i], has[i]) for i in range(len(labels))]
        if fm[0] == "ratio":  # tỷ lệ cả kỳ (không cộng / trung bình theo kỳ được)
            tot = _eval(fm, total, total_has)
        else:  # tiền / số lượng: cộng các kỳ; hiệu giữ phần âm (QC + tự nhiên = tổng DS như tab Tổng quan)
            vals = [_eval(fm, per[i], has[i], clamp=False) for i in range(len(labels))]
            vals = [v for v in vals if v is not None]
            tot = sum(vals) if vals else None
        out.append({"id": m["id"], "values": values, "total": tot})
    # tuần / tháng đầu hoặc cuối chỉ gồm một phần trong khoảng ngày đang lọc -> giao diện ghi chú
    partial = gran != "day" and (labels[0] < f.start or bucket_of(f.end + timedelta(days=1), gran) == labels[-1])
    return {"gran": gran, "gran_label": GRANS[gran], "labels": [d.isoformat() for d in labels], "metrics": out,
            "partial": partial}
