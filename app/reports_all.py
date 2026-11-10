"""Trang Tổng hợp: doanh số và chi phí quảng cáo của mọi kênh trên một trang.

Nguồn doanh số (cùng quy ước báo cáo quý):
- Amazon: đơn hàng (fact_total_sales_daily), giá bán lẻ item_price, các tài khoản có trong dim_account.
- Wayfair: đơn hàng theo giá sỉ (fact_wf_total_sales_daily), nước = nước của khách. Không lấy từ
  fact_channel_sales_daily vì doanh thu DHI CastleGate ở đó lệch.
- Shopify: fact_shop_line, sau giảm giá, chưa trừ hoàn tiền.
- Khác (Walmart, eBay, bán sỉ, AVC…): fact_channel_sales_daily, các kênh không phải AMZ- / WAYFAIR- / SPF-.
Bộ lọc kênh (sales_channel) chỉ giữ doanh số / chi phí của các kênh chọn. Tồn kho: nút ALL-<nước> (kho nội bộ +
CastleGate), dự báo hết hàng đã cộng hàng đang về (inv_projection).
Chi phí QC: Amazon + Wayfair (theo campaign) + Shopify (team nhập tay theo tháng, chia đều theo ngày; không tính khi lọc
nhóm SP / brand). "DS sau phí sàn" = doanh số × (1 − phí sàn của kênh) theo
cfg_channel_cost (tab Giá vốn & phí). Bộ lọc: ngày, nước (market), nhóm SP, brand.
"""
import calendar
import re
from datetime import date, timedelta

from app import insights
from app.db import fetch_all
from app.filters import Filters, Where, campaign_where, wf_where
from app.metrics import col, with_ratios
from app.reports import _table
from app.reports_shop import ad_spend_daily, period_key, period_labels
from app.viz import chart, series, top_n

CHANNELS = [("amazon", "Amazon", "c1"), ("wayfair", "Wayfair (giá sỉ)", "c2"), ("shopify", "Shopify", "c3"),
            ("other", "Khác (Walmart, eBay, bán sỉ…)", "c4")]
CHANNEL_LABELS = {k: v for k, v, _ in CHANNELS}
DEFAULT_FEES = {"amazon": 0.15, "wayfair": 0.0, "shopify": 0.03, "other": 0.15}
OTHER_CHANNEL = "m.code NOT LIKE 'AMZ-%' AND m.code NOT LIKE 'WAYFAIR-%' AND m.code NOT LIKE 'SPF-%'"

MARKETS = [("US", "Mỹ (US)", "c5"), ("CA", "Canada (CA)", "c6"), ("AU", "Úc (AU)", "c7")]
MARKET_OTHER = ("OTHER", "Nước khác", "n1")
# công ty: so khớp tên tài khoản (Amazon, Wayfair) hoặc mã kênh (Shopify, kênh khác), theo thứ tự (Senno trước vì kênh
# Amazon Úc tên "Amz Hurav Senno"). Mẫu ngắn so theo từng từ của mã (AMZ-INF-CA-FBA), mẫu dài so theo chuỗi con.
COMPANY_RULES = [("SENNO", "Senno"), ("SNN", "Senno"), ("DH INTRA", "DH Intra"), ("DHINTRA", "DH Intra"),
                 ("DHI", "DH Intra"), ("MEGSU", "Megsu"), ("AROZU", "Arozu"), ("HURAV", "Hurav"), ("HRV", "Hurav"),
                 ("INFIDEAL", "Infideals"), ("INF", "Infideals"), ("IDZO", "Idzo"), ("YES4ALL", "Yes4All"),
                 ("Y4A", "Yes4All"), ("VITRA", "Vitra"), ("STOZM", "Stozm")]
COMPANY_OTHER = "Khác / chưa rõ"


def company_of(key: str | None) -> str:
    """Tên công ty từ tên tài khoản hoặc mã kênh, vd 'DH Intra', 'DHI', 'SPF-SENNO', 'EBAY-INF' -> 'Infideals'."""
    norm = (key or "").upper()
    tokens = set(re.split(r"[^A-Z0-9]+", norm))
    for pat, name in COMPANY_RULES:
        if pat in tokens or (len(pat) >= 5 and pat in norm):
            return name
    return COMPANY_OTHER


KPI_DEF = [
    ["total_sales", "Tổng doanh số", "money", 1, True], ["net_sales", "DS sau phí sàn", "money", 1, True],
    ["spend", "Spend QC", "money", -1, True], ["tacos", "TACoS chung", "pct", -1, True],
    ["after_ads", "DS sau phí sàn và QC", "money", 1, False], ["sales", "DS từ QC", "money", 1, False],
    ["units", "Units", "int", 1, False], ["amazon", "Amazon", "money", 1, False],
    ["wayfair", "Wayfair (giá sỉ)", "money", 1, False], ["shopify", "Shopify", "money", 1, False],
    ["other", "Kênh khác", "money", 1, False],
    ["cogs", "Giá vốn (COGS chuẩn)", "money", -1, False], ["gross_profit", "Lãi gộp", "money", 1, False],
    ["gross_margin", "Biên lãi gộp", "pct", 1, False], ["profit_after_ads", "Lãi gộp sau QC", "money", 1, True],
    ["profit_margin", "Biên lãi sau QC", "pct", 1, False],
]
PROFIT_KPIS = ("cogs", "gross_profit", "gross_margin", "profit_after_ads", "profit_margin")


def _src(f: Filters) -> tuple[str, dict]:
    """Doanh số mọi kênh dạng (ch, cc, co, d, pid, s, u, fx = đơn vị FBA / CastleGate), cùng khoảng ngày và nước. co = tên tài khoản / mã kênh để
    gán công ty (company_of)."""
    params = {"s0": f.start, "s1": f.end}
    cc = ""
    if f.countries:
        names = {f"cc{i}": c for i, c in enumerate(f.countries)}
        params.update(names)
        cc = f"IN ({', '.join(':' + k for k in names)})"

    def where(date_col: str, country_col: str) -> str:
        return f"{date_col} BETWEEN :s0 AND :s1" + (f" AND {country_col} {cc}" if cc else "")

    sql = f"""
        SELECT 'amazon' AS ch, t.country_code AS cc, a.store_account_name AS co, t.report_date AS d, t.product_id AS pid,
               t.sales_usd AS s, t.units AS u, t.fba_units AS fx
        FROM fact_total_sales_daily t
        JOIN (SELECT store_account_id, country_code, MAX(store_account_name) AS store_account_name FROM dim_account
              WHERE store_account_id IS NOT NULL GROUP BY store_account_id, country_code) a
          ON a.store_account_id = t.store_account_id AND a.country_code = t.country_code
        WHERE {where('t.report_date', 't.country_code')}
        UNION ALL
        SELECT 'wayfair', t.country_code, COALESCE(wa.short_name, t.account_id), t.report_date, t.product_id, t.sales_usd,
               t.units, CASE WHEN t.order_type = 'castle_gate' THEN t.units ELSE 0 END
        FROM fact_wf_total_sales_daily t LEFT JOIN dim_wf_account wa ON wa.account_id = t.account_id
        WHERE {where('t.report_date', 't.country_code')}
        UNION ALL
        SELECT 'shopify', l.country_code, sm.code, l.report_date, l.product_id, l.net_usd, l.units, 0
        FROM fact_shop_line l LEFT JOIN map_channel_node sm ON sm.sales_channel_id = l.sales_channel_id
        WHERE {where('l.report_date', 'l.country_code')}
        UNION ALL
        SELECT 'other', m.country_code, m.code, f.report_date, f.product_id, f.revenue_usd, f.units, 0
        FROM fact_channel_sales_daily f JOIN map_channel_node m ON m.sales_channel_id = f.sales_channel_id
        WHERE {where('f.report_date', 'm.country_code')} AND {OTHER_CHANNEL}"""
    return sql, params


def _sales(f: Filters, keys: str, extra: str = "", period: str | None = None) -> list[dict]:
    """Tổng doanh số nhóm theo `keys` (cột của x: ch, cc, d, pid; hoặc p.group_id), thêm cột kỳ `d` nếu có `period`."""
    sql, params = _src(f)
    w = Where()
    w._n = 7000
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    w.add_in("x.ch", f.sales_channels)
    sel, grp = keys, keys
    if period:
        sel, grp = f"{keys}, {period} AS d", f"{keys}, {period}"
    return fetch_all(f"""SELECT {sel}, SUM(x.s) AS total_sales, SUM(x.u) AS units {extra}
        FROM ({sql}) x LEFT JOIN dim_product p ON p.product_id = x.pid
        {w.sql()} GROUP BY {grp}""", {**params, **w.params})


def _spend(f: Filters, period: str | None = None) -> list[dict]:
    """Spend và DS từ QC theo kênh × nước (× kỳ `d` nếu có `period`, biểu thức trên f.report_date). Amazon + Wayfair lọc
    nhóm SP cùng cách với tab của từng sàn; Shopify là chi phí nhập tay theo tháng (không có DS từ QC)."""
    aw = campaign_where(f)
    aw.add_in("a.country_code", f.countries)
    ww = wf_where(f)
    ww.add_in("f.country_code", f.countries)
    sel, grp = (f", {period} AS d", f", {period}") if period else ("", "")
    want = set(f.sales_channels) or {"amazon", "wayfair", "shopify"}
    amz = [] if "amazon" not in want else fetch_all(f"""SELECT 'amazon' AS ch, a.country_code AS cc {sel}, SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
        FROM fact_campaign_daily f JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        JOIN dim_account a ON a.profile_id = f.profile_id {aw.sql()} GROUP BY a.country_code {grp}""", aw.params)
    wf = [] if "wayfair" not in want else fetch_all(f"""SELECT 'wayfair' AS ch, f.country_code AS cc {sel}, SUM(f.cost_usd) AS spend, SUM(f.sales_usd) AS sales
        FROM fact_wf_campaign_daily f JOIN dim_wf_campaign c ON c.campaign_id = f.campaign_id
        {ww.sql()} GROUP BY f.country_code {grp}""", ww.params)
    shop: dict = {}
    weekly = period_key(f)[1] == "tuần"
    for r in (ad_spend_daily(f) or []) if "shopify" in want else []:
        k = (r["cc"], (r["d"] - timedelta(days=r["d"].weekday()) if weekly else r["d"]) if period else None)
        shop[k] = shop.get(k, 0.0) + r["spend"]
    return amz + wf + [{"ch": "shopify", "cc": cc, "d": d, "spend": v, "sales": 0.0} for (cc, d), v in shop.items()]


def _group_spend(f: Filters) -> dict:
    """Spend theo nhóm SP: chia spend của campaign cho các nhóm theo tỷ trọng sản phẩm quảng cáo (map_adgroup_product /
    map_wf_campaign_group). Spend của campaign chưa map được vào nhóm None."""
    want = set(f.sales_channels) or {"amazon", "wayfair"}
    aw = campaign_where(Filters(start=f.start, end=f.end))
    aw.add_in("a.country_code", f.countries)
    if "amazon" not in want:
        aw.add("1 = 0")
    ww = wf_where(Filters(start=f.start, end=f.end))
    ww.add_in("f.country_code", f.countries)
    if "wayfair" not in want:
        ww.add("1 = 0")
    rows = fetch_all(f"""
        SELECT g.group_id, SUM(f.cost_usd * COALESCE(g.share, 1)) AS spend
        FROM fact_campaign_daily f JOIN dim_campaign c ON c.campaign_id = f.campaign_id AND c.ad_type = f.ad_type
        JOIN dim_account a ON a.profile_id = f.profile_id
        LEFT JOIN (SELECT ad_type, campaign_id, group_id,
                          SUM(COALESCE(weight, weight_share, 1)) / SUM(SUM(COALESCE(weight, weight_share, 1)))
                            OVER (PARTITION BY ad_type, campaign_id) AS share
                   FROM map_adgroup_product GROUP BY ad_type, campaign_id, group_id) g
          ON g.ad_type = f.ad_type AND g.campaign_id = f.campaign_id
        {aw.sql()} GROUP BY g.group_id
        UNION ALL
        SELECT g.group_id, SUM(f.cost_usd * COALESCE(g.share, 1))
        FROM fact_wf_campaign_daily f JOIN dim_wf_campaign c ON c.campaign_id = f.campaign_id
        LEFT JOIN (SELECT campaign_id, group_id,
                          COALESCE(weight_share, 1) / SUM(COALESCE(weight_share, 1)) OVER (PARTITION BY campaign_id) AS share
                   FROM map_wf_campaign_group) g ON g.campaign_id = f.campaign_id
        {ww.sql()} GROUP BY g.group_id""", {**aw.params, **ww.params})
    out: dict = {}
    for r in rows:
        out[r["group_id"]] = out.get(r["group_id"], 0) + (r["spend"] or 0)
    return out


def _fees() -> dict[str, float]:
    fees = dict(DEFAULT_FEES)
    for r in fetch_all("SELECT channel, referral_pct FROM cfg_channel_cost"):
        if r["channel"] in fees:
            fees[r["channel"]] = float(r["referral_pct"] or 0)
    return fees


def _freshness() -> dict[str, date | None]:
    r = fetch_all(f"""SELECT (SELECT MAX(report_date) FROM fact_total_sales_daily) AS amazon,
        (SELECT MAX(report_date) FROM fact_wf_total_sales_daily) AS wayfair,
        (SELECT MAX(report_date) FROM fact_shop_line) AS shopify,
        (SELECT MAX(f.report_date) FROM fact_channel_sales_daily f JOIN map_channel_node m
           ON m.sales_channel_id = f.sales_channel_id WHERE {OTHER_CHANNEL}) AS other""")[0]
    return r


def _kpi(by_cc: list[dict], spend: list[dict], fees: dict) -> dict:
    out = {"total_sales": 0.0, "net_sales": 0.0, "units": 0.0, "spend": 0.0, "sales": 0.0}
    for ch, _, _ in CHANNELS:
        out[ch] = 0.0
    for r in by_cc:
        s = float(r["total_sales"] or 0)
        out["total_sales"] += s
        out["net_sales"] += s * (1 - fees[r["ch"]])
        out["units"] += float(r["units"] or 0)
        out[r["ch"]] += s
    for r in spend:
        out["spend"] += float(r["spend"] or 0)
        out["sales"] += float(r["sales"] or 0)
    return with_ratios(out)


# ---------------------------------------------------------------- kỳ so sánh

COMPARE_MODES = {"prev": "kỳ liền trước", "month": "cùng kỳ tháng trước", "year": "cùng kỳ năm trước"}


def shift_months(d: date, n: int) -> date:
    """Lùi n tháng, giữ ngày (ngày 31 sang tháng ít ngày hơn thì lấy ngày cuối tháng)."""
    m = d.month - 1 - n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def compare_period(f: Filters, mode: str | None) -> tuple[Filters, str]:
    """Kỳ so sánh và nhãn ngắn. prev = cùng số ngày ngay trước; month / year = cùng ngày tháng trước / năm trước."""
    mode = mode if mode in COMPARE_MODES else "prev"
    if mode == "prev":
        prev = f.previous_period()
    else:
        prev = Filters(**f.__dict__)
        k = 1 if mode == "month" else 12
        prev.start, prev.end = shift_months(f.start, k), shift_months(f.end, k)
    fmt = "%d/%m/%Y" if mode == "year" else "%d/%m"
    return prev, f"{COMPARE_MODES[mode]} ({prev.start:{fmt}}–{prev.end:{fmt}})"


# ---------------------------------------------------------------- kế hoạch (forecast sheet Q4)

# salesapp_db.sales_forecasts: kế hoạch theo ngày × nước × sàn × SKU, tiền địa phương (Wayfair theo giá sỉ)
FC_CHANNEL = {"amazon": "amazon", "wayfair": "wayfair", "shopify": "shopify", "walmart": "other", "mydeals": "other"}
FC_COUNTRY = {"US": "US", "CA": "CA", "AUS": "AU", "AU": "AU"}
FC_CCY = {"US": "USD", "CA": "CAD", "AU": "AUD"}


def _forecast(start: date, end: date) -> dict[tuple[str, str, date], float] | None:
    """Kế hoạch doanh số USD theo (kênh, nước, ngày), quy đổi theo tỷ giá mới nhất. None nếu chưa có bảng kế hoạch."""
    try:
        rows = fetch_all("""SELECT event_date, country, marketplace, SUM(revenue_fc) AS fc FROM salesapp_db.sales_forecasts
            WHERE event_date BETWEEN :a AND :b GROUP BY event_date, country, marketplace""",
                         {"a": start.isoformat(), "b": end.isoformat()})
    except Exception:
        return None
    fx = {r["currency_code"]: float(r["rate_usd"]) for r in fetch_all("""
        SELECT x.currency_code, x.rate_usd FROM fx_daily x
        JOIN (SELECT currency_code, MAX(date_key) AS d FROM fx_daily WHERE rate_usd IS NOT NULL GROUP BY currency_code) m
          ON m.currency_code = x.currency_code AND m.d = x.date_key""")}
    out: dict = {}
    for r in rows:
        ch, cc = FC_CHANNEL.get(str(r["marketplace"]).lower()), FC_COUNTRY.get(str(r["country"]).upper())
        rate = fx.get(FC_CCY.get(cc, ""), 1.0 if cc == "US" else None)
        if not ch or not cc or rate is None:
            continue
        d = r["event_date"] if isinstance(r["event_date"], date) else date.fromisoformat(str(r["event_date"])[:10])
        out[(ch, cc, d)] = out.get((ch, cc, d), 0.0) + float(r["fc"] or 0) * rate
    return out or None


def _plan(f: Filters, fresh: dict, order: list[str]) -> tuple[list[dict], list[dict], str] | None:
    """Thực tế so với kế hoạch theo kênh × nước. Mỗi kênh chỉ so đến ngày có dữ liệu của kênh đó (đơn về trễ).
    Kỳ bắt đầu từ ngày 1 và nằm trong một tháng thì ước cả tháng = thực tế + kế hoạch các ngày còn lại × % đạt.
    Trả về (dòng bảng, thẻ, ghi chú) hoặc None khi lọc nhóm SP / brand (kế hoạch không có id nhóm) hoặc chưa có kế hoạch."""
    if f.group_ids or f.brand_ids:
        return None
    m0 = f.end.replace(day=1)
    m1 = f.end.replace(day=calendar.monthrange(f.end.year, f.end.month)[1])
    mtd = f.start == m0
    fc = _forecast(min(f.start, m0), m1)
    if not fc:
        return None
    # ngày mới nhất đã nạp thường chưa đủ đơn (đơn về trễ): chỉ so đến ngày trước đó
    cut = {ch: min(f.end, (fresh[ch] - timedelta(days=1)) if fresh.get(ch) else f.end) for ch in order}
    actual: dict = {}
    daily: dict = {}  # (kênh, nước, ngày) -> doanh số, chỉ các ngày đủ dữ liệu
    for r in _sales(f, "x.ch, x.cc", period="x.d"):
        if r["d"] and r["d"] <= cut[r["ch"]]:
            k = (r["ch"], r["cc"])
            actual[k] = actual.get(k, 0.0) + float(r["total_sales"] or 0)
            daily[(r["ch"], r["cc"], r["d"])] = daily.get((r["ch"], r["cc"], r["d"]), 0.0) + float(r["total_sales"] or 0)
    rows: dict = {}
    for (ch, cc, d), v in fc.items():
        if ch not in order or (f.countries and cc not in f.countries):
            continue
        x = rows.setdefault((ch, cc), {"ch": ch, "cc": cc, "fc_period": 0.0, "fc_month": 0.0, "fc_rest": 0.0})
        if f.start <= d <= cut[ch]:
            x["fc_period"] += v
        if m0 <= d <= m1:
            x["fc_month"] += v
            if d > cut[ch]:
                x["fc_rest"] += v
    for k, v in actual.items():
        if k[0] in order:
            rows.setdefault(k, {"ch": k[0], "cc": k[1], "fc_period": 0.0, "fc_month": 0.0, "fc_rest": 0.0})
    out = []
    for (ch, cc), r in sorted(rows.items(), key=lambda kv: (order.index(kv[0][0]), -kv[1]["fc_month"])):
        r.update({"channel": CHANNEL_LABELS[ch], "country": cc, "data_to": cut[ch], "actual": actual.get((ch, cc), 0.0)})
        r["no_data"] = cut[ch] < f.start
        _plan_ratios(r, mtd)
        out.append(r)
    tot = plan_totals(out, mtd)
    est = tot.get("est_month")
    cards = [
        {"label": "Thực tế so với kế hoạch", "value": tot["attain"], "fmt": "pct",
         "tone": "bad" if tot["attain"] is not None and tot["attain"] < 0.9 else None,
         "note": f"${tot['actual']:,.0f} / KH ${tot['fc_period']:,.0f}, mỗi kênh tính đến ngày đủ dữ liệu"},
        {"label": f"Kế hoạch tháng {f.end:%m/%Y}", "value": tot["fc_month"], "fmt": "money", "note": "sheet kế hoạch Q4"},
    ]
    if mtd:
        cards += [
            {"label": "Ước cả tháng theo tốc độ hiện tại", "value": est, "fmt": "money",
             "note": "thực tế + KH các ngày còn lại × % đạt của từng kênh × nước"},
            {"label": "Ước cả tháng so với KH", "value": tot["est_gap"], "fmt": "money",
             "tone": "bad" if (tot["est_gap"] or 0) < 0 else None,
             "note": f"đạt {tot['est_attain']:.0%} kế hoạch tháng" if tot["est_attain"] is not None else ""},
        ]
    lag = ", ".join(f"{CHANNEL_LABELS[c].split(' (')[0]} {cut[c]:%d/%m}" for c in order if c != "other")
    note = ("Kế hoạch = sheet forecast Q4 (salesapp_db.sales_forecasts), quy USD theo tỷ giá mới nhất; Walmart, MyDeals "
            f"tính vào Kênh khác. Bảng kế hoạch so thực tế với kế hoạch đến ngày đủ dữ liệu của từng kênh ({lag}; ngày "
            "nạp mới nhất chưa đủ đơn nên chưa tính), vì vậy cột Thực tế có thể thấp hơn Tổng doanh số ở trên.")
    if any(r["no_data"] and r["fc_month"] for r in out):
        note += (" Kênh khác chưa có số bán trong kỳ (dữ liệu đến "
                 f"{fresh.get('other'):%d/%m}): ước cả tháng tính 0 cho kênh này." if fresh.get("other") else
                 " Kênh khác chưa có số bán: ước cả tháng tính 0 cho kênh này.")
    curve = _plan_curve(out, fc, daily, cut, m0, m1) if mtd else None
    return out, cards, note, tot, curve


def _plan_curve(rows: list[dict], fc: dict, daily: dict, cut: dict, m0: date, m1: date) -> dict | None:
    """Lũy kế theo ngày trong tháng: kế hoạch, thực tế (đến ngày đủ dữ liệu sớm nhất giữa các kênh) và đường ước
    (thực tế, các ngày chưa có dữ liệu của từng kênh × nước = kế hoạch ngày đó × % đạt). Điểm cuối đường ước = ước cả tháng."""
    live = [r for r in rows if not r["no_data"]]
    if not live:
        return None
    d0 = min(cut[r["ch"]] for r in live)
    days = [m0 + timedelta(days=i) for i in range((m1 - m0).days + 1)]
    plan_c, act_c, est_c = [], [], []
    p = a = e = 0.0
    for d in days:
        p += sum(fc.get((r["ch"], r["cc"], d), 0.0) for r in rows)
        for r in live:
            k = (r["ch"], r["cc"])
            if d <= cut[r["ch"]]:
                v = daily.get((*k, d), 0.0)
                e += v
                if d <= d0:
                    a += v
            else:
                e += fc.get((*k, d), 0.0) * (r["attain"] if r["attain"] is not None else 1.0)
        plan_c.append(p)
        act_c.append(a if d <= d0 else None)
        est_c.append(e if d >= d0 else None)
    return {"labels": [d.isoformat() for d in days], "plan": plan_c, "actual": act_c, "est": est_c, "d0": d0}


def _plan_ratios(r: dict, mtd: bool) -> None:
    r["attain"] = r["actual"] / r["fc_period"] if r["fc_period"] else None
    r["gap"] = r["actual"] - r["fc_period"] if not r.get("no_data") else None
    r["est_month"] = r["est_gap"] = r["est_attain"] = None
    if mtd and not r.get("no_data"):
        pace = r["attain"] if r["attain"] is not None else 1.0
        r["est_month"] = r["actual"] + r["fc_rest"] * pace
        r["est_gap"] = r["est_month"] - r["fc_month"]
        r["est_attain"] = r["est_month"] / r["fc_month"] if r["fc_month"] else None


def plan_totals(rows: list[dict], mtd: bool) -> dict:
    """Dòng tổng: cộng từng cột; ước cả tháng = tổng ước của các dòng (dòng chưa có dữ liệu tính 0)."""
    tot = {k: sum(r[k] for r in rows) for k in ("fc_period", "actual", "fc_month", "fc_rest")}
    tot["attain"] = tot["actual"] / tot["fc_period"] if tot["fc_period"] else None
    tot["gap"] = tot["actual"] - tot["fc_period"]
    tot["est_month"] = tot["est_gap"] = tot["est_attain"] = None
    if mtd:
        tot["est_month"] = sum(r["est_month"] or 0 for r in rows)
        tot["est_gap"] = tot["est_month"] - tot["fc_month"]
        tot["est_attain"] = tot["est_month"] / tot["fc_month"] if tot["fc_month"] else None
    return tot


# ---------------------------------------------------------------- lãi gộp theo giá vốn chuẩn

def _cogs(f: Filters, fees: dict) -> dict:
    """Giá vốn theo dòng (kênh, nước, product_id, nhóm SP). Giá vốn mỗi đơn vị: nhập tay (cfg_sku_cost) nếu có, nếu không
    là giá vốn chuẩn BOD: Amazon / Wayfair trộn WH với FBA / CastleGate theo số đơn vị giao từ kho sàn, Shopify / kênh
    khác lấy WH. SKU chưa có giá vốn: ước theo tỷ lệ giá vốn / doanh số của SKU có giá vốn cùng kênh × nước
    (không có thì cùng kênh, rồi toàn bộ). Trả về {"rows": [...], ...} với cogs, costed_sales, gross_profit mỗi dòng."""
    costs, _ = insights.load_costs()
    rows = _sales(f, "x.ch, x.cc, x.pid, p.group_id", extra=", SUM(x.fx) AS fbx")
    costed: dict = {}  # khóa tỷ lệ -> [doanh số có giá vốn, giá vốn]
    for r in rows:
        s, u = float(r["total_sales"] or 0), float(r["units"] or 0)
        mkt = r["cc"] if r["cc"] in ("US", "CA", "AU") else "US"
        manual = costs["manual"].get(r["pid"])
        if manual and manual.get("landed_cost") is not None:
            unit = float(manual["landed_cost"])
        elif r["ch"] in insights.FULFIL_BASIS:
            unit = insights.std_cost(costs["std"], r["pid"], r["ch"], [(mkt, u, float(r["fbx"] or 0))])
        else:
            std = costs["std"]
            unit = next((std[k] for k in ((r["pid"], mkt, b) for b in ("WH", "FBA", "CG")) if k in std), None)
        r["s"], r["c"] = s, (unit * u if unit is not None and r["pid"] else None)
        if r["c"] is not None:
            for k in ((r["ch"], r["cc"]), (r["ch"],), ()):
                x = costed.setdefault(k, [0.0, 0.0])
                x[0] += s
                x[1] += r["c"]

    def ratio(r):
        for k in ((r["ch"], r["cc"]), (r["ch"],), ()):
            x = costed.get(k)
            if x and x[0] > 0:
                return x[1] / x[0]
        return None
    for r in rows:
        r["costed_sales"] = r["s"] if r["c"] is not None else 0.0
        if r["c"] is None:
            q = ratio(r)
            r["c"] = r["s"] * q if q is not None else None
        r["cogs"] = r["c"] or 0.0
        r["gross_profit"] = r["s"] * (1 - fees[r["ch"]]) - r["cogs"] if r["c"] is not None else None
    return {"rows": rows, "has_cost": any(costed.values())}


def _sum_cogs(rows: list[dict], key) -> dict:
    out: dict = {}
    for r in rows:
        x = out.setdefault(key(r), {"cogs": 0.0, "costed_sales": 0.0, "gross_profit": 0.0})
        x["cogs"] += r["cogs"]
        x["costed_sales"] += r["costed_sales"]
        x["gross_profit"] += r["gross_profit"] or 0.0
    return out


# ---------------------------------------------------------------- tồn kho & dự báo hết hàng

# (khóa, nhãn, màu). Hết hàng / 14 / 30 ngày theo ngày dự kiến hết hàng (đã cộng hàng đang về theo ETA); ổn / tồn
# nhiều theo số ngày đủ bán với tồn hiện có, cùng ngưỡng 90 ngày với tab Tồn kho (etl/inventory.py)
STOCK_BUCKETS = [("OOS", "Đang hết hàng", "st:OOS"), ("D14", "Hết trong 14 ngày", "st:CRITICAL"),
                 ("D30", "Hết trong 15–30 ngày", "st:LOW"), ("OK", "Ổn (30–90 ngày)", "st:OK"),
                 ("OVER", "Tồn nhiều (≥ 90 ngày)", "st:OVER"), ("NO_SALES", "Có tồn, không bán 90 ngày", "st:NO_SALES")]
OVER_DAYS = 90
BUCKET_LABELS = {k: v for k, v, _ in STOCK_BUCKETS}


def stock_bucket(available: float | None, velocity: float | None, days_left: float | None) -> str | None:
    """Nhóm dự báo của một SKU × nước. days_left = số ngày tới ngày dự kiến hết hàng (đã cộng hàng đang về).
    None = không bán và không còn tồn."""
    if not velocity or velocity <= 0:
        return "NO_SALES" if (available or 0) > 0 else None
    if (available or 0) <= 0:
        return "OOS"
    if days_left is not None and days_left <= 14:
        return "D14"
    if days_left is not None and days_left <= 30:
        return "D30"
    return "OVER" if available / velocity >= OVER_DAYS else "OK"


def _inventory(f: Filters, sold: dict, keep: set | None = None) -> tuple[list[dict], list[dict], list[dict], date | None]:
    """Tồn kho nút ALL-<nước> (kho nội bộ + CastleGate) của các SKU trong phạm vi lọc. Lọc kênh thì chỉ giữ SKU × nước
    có bán trên kênh đó trong kỳ (`sold`). Trả về (thẻ, dòng theo nước, dòng SKU sắp hết, ngày dự báo)."""
    w = Where()
    w._n = 8000
    w.add("j.node_id LIKE 'ALL-%'")
    w.add("j.status NOT IN ('INACTIVE', 'NO_DATA')")
    w.add_in("j.node_id", [f"ALL-{c}" for c in f.countries])
    w.add_in("p.group_id", f.group_ids).add_in("p.brand_id", f.brand_ids)
    rows = fetch_all(f"""
        SELECT j.product_id, SUBSTRING(j.node_id, 5) AS country, p.product_sku, p.title AS product, p.group_name,
               j.available, j.incoming_qty, j.incoming_30d, j.next_eta, j.next_qty, j.velocity, j.days_cover,
               j.days_cover_incl_incoming, j.stockout_date, j.oos_days_before_next, j.need_60d, j.lost_sales_90,
               j.avg_price, j.units_30, j.as_of
        FROM inv_projection j LEFT JOIN dim_product p ON p.product_id = j.product_id
        {w.sql()}""", w.params)
    if f.sales_channels:
        rows = [r for r in rows if (r["product_id"], r["country"]) in (keep if keep is not None else sold)]
    as_of = max((r["as_of"] for r in rows if r["as_of"]), default=None)
    by_cc: dict = {}
    risk = []
    for r in rows:
        r["bucket"] = stock_bucket(r["available"], r["velocity"], r["days_cover_incl_incoming"])
        c = by_cc.setdefault(r["country"], {"country": r["country"], "skus": 0, "available": 0.0, "incoming": 0.0,
                                            "velocity": 0.0, "available_selling": 0.0, "lost_sales_90": 0.0,
                                            **{k: 0 for k, _, _ in STOCK_BUCKETS}})
        c["skus"] += 1
        c["available"] += max(r["available"] or 0, 0)
        c["incoming"] += r["incoming_qty"] or 0
        c["lost_sales_90"] += r["lost_sales_90"] or 0
        if r["bucket"]:
            c[r["bucket"]] += 1
        if r["bucket"] and r["bucket"] != "NO_SALES":
            c["velocity"] += r["velocity"]
            c["available_selling"] += max(r["available"] or 0, 0)
        if r["bucket"] in ("OOS", "D14", "D30"):
            x = sold.get((r["product_id"], r["country"]), {})
            r["status_label"] = BUCKET_LABELS[r["bucket"]]
            r["channels"] = ", ".join(CHANNEL_LABELS[c_].split(" (")[0] for c_, _, _ in CHANNELS if x.get(c_))
            r["total_sales"] = sum(x.values()) if x else 0.0
            r["sales_day"] = r["velocity"] * (r["avg_price"] or 0)
            # ngày dự kiến hết tính tròn ngày: còn < 1 ngày hàng thì lấy số ngày lẻ (tồn ÷ tốc độ bán)
            r["days_left"] = 0 if r["bucket"] == "OOS" else (r["days_cover_incl_incoming"] or r["days_cover"])
            risk.append(r)
    countries = sorted(by_cc.values(), key=lambda c: ["US", "CA", "AU"].index(c["country"])
                       if c["country"] in ("US", "CA", "AU") else 9)
    for c in countries:
        c["days_cover"] = c["available_selling"] / c["velocity"] if c["velocity"] else None
        c["d30_total"] = c["D14"] + c["D30"]
    order = {"OOS": 0, "D14": 1, "D30": 2}
    risk.sort(key=lambda r: (order[r["bucket"]], -(r["lost_sales_90"] or 0), -(r["sales_day"] or 0)))

    def tot(k):
        return sum(c[k] for c in countries)
    vel = tot("velocity")
    lost_risk = sum(r["lost_sales_90"] or 0 for r in risk)
    cards = [
        {"label": "Tồn khả dụng (nội bộ + CastleGate)", "value": tot("available"), "fmt": "int",
         "note": f"units, dự báo ngày {as_of:%d/%m/%Y}" if as_of else "units"},
        {"label": "Đang về / pipeline", "value": tot("incoming"), "fmt": "int", "note": "units: PO + container + CastleGate"},
        {"label": "Số ngày đủ bán", "value": (tot("available_selling") / vel) if vel else None, "fmt": "num2",
         "note": "tồn ÷ tốc độ bán, SKU đang bán, chưa cộng hàng về"},
        {"label": "SKU đang hết hàng", "value": tot("OOS"), "fmt": "int", "tone": "bad", "note": "SKU × nước còn bán 90 ngày qua"},
        {"label": "SKU hết trong 14 ngày", "value": tot("D14"), "fmt": "int", "tone": "bad",
         "note": "đã cộng hàng về theo ETA"},
        {"label": "SKU hết trong 30 ngày", "value": tot("D14") + tot("D30"), "fmt": "int", "tone": "warn",
         "note": f"gồm {tot('D14')} SKU hết trong 14 ngày"},
        {"label": "SKU ổn (30–90 ngày)", "value": tot("OK"), "fmt": "int"},
        {"label": "SKU tồn nhiều ≥ 90 ngày", "value": tot("OVER"), "fmt": "int",
         "note": f"thêm {tot('NO_SALES')} SKU có tồn nhưng không bán 90 ngày"},
        {"label": "DS mất ước tính 90 ngày (SKU hết trong 30 ngày)", "value": lost_risk, "fmt": "money",
         "tone": "bad" if lost_risk else None,
         "note": f"chỉ SKU đang hết / hết trong 30 ngày; tính mọi SKU (bảng Theo nước, Theo nhóm SP): "
                 f"${sum(c['lost_sales_90'] for c in countries):,.0f}"},
    ]
    return cards, countries, risk, as_of


def _inventory_viz(countries: list[dict], risk: list[dict]) -> list[dict]:
    out = []
    if countries:
        out.append(chart("stock_forecast", "Dự báo tồn kho theo nước (số SKU)", "hbar_stacked",
                         [c["country"] for c in countries],
                         [series(label, color, [c[k] for c in countries]) for k, label, color in STOCK_BUCKETS],
                         unit="int", tables=["stock_risk"],
                         label_filters=[{"cols": {"country": [c["country"]]}} for c in countries],
                         subtitle="Kho nội bộ + CastleGate (FBA chưa có số tồn). Hết hàng / 14 / 30 ngày theo ngày dự kiến "
                                  "hết hàng đã cộng hàng đang về theo ETA; ổn / tồn nhiều theo số ngày đủ bán với tồn hiện "
                                  "có. Bấm để lọc bảng SKU đang hết / sắp hết."))
    soon = sorted([r for r in risk if r["bucket"] in ("D14", "D30")], key=lambda r: -(r["sales_day"] or 0))

    def soon_chart(rows):
        return chart("stock_soon", f"{len(rows)} SKU sắp hết hàng bán nhiều nhất: còn bao nhiêu ngày", "hbar",
                     [f"{r['product_sku']} · {r['country']}" for r in rows],
                     [series("Số ngày tới khi hết hàng", "c1", [r["days_left"] for r in rows],
                             colors=["st:CRITICAL" if r["bucket"] == "D14" else "st:LOW" for r in rows])],
                     unit="days", refs=[{"value": 14, "label": "14 ngày"}], tables=["stock_risk"],
                     label_filters=[{"cols": {"product_sku": [r["product_sku"]], "country": [r["country"]]}}
                                    for r in rows],
                     subtitle="Sắp theo doanh số mỗi ngày (tốc độ bán × giá bán TB). Đã cộng hàng đang về theo ETA. "
                              "Bấm một thanh để lọc bảng.")
    ch = top_n(soon, 15, soon_chart)
    if ch:
        out.append(ch)
    oos = sorted([r for r in risk if r["bucket"] == "OOS"], key=lambda r: (-(r["lost_sales_90"] or 0), -(r["sales_day"] or 0)))

    def oos_chart(rows):
        return chart("stock_oos", f"{len(rows)} SKU đang hết hàng mất doanh số nhiều nhất", "hbar",
                     [f"{r['product_sku']} · {r['country']}" for r in rows],
                     [series("DS mất ước tính 90 ngày", "st:OOS", [r["lost_sales_90"] or 0 for r in rows])],
                     unit="money", tables=["stock_risk"],
                     label_filters=[{"cols": {"product_sku": [r["product_sku"]], "country": [r["country"]]}}
                                    for r in rows],
                     subtitle="DS mất ước tính 90 ngày = tốc độ bán × giá × số ngày đứt hàng tới khi hàng về. "
                              "Bấm một thanh để lọc bảng.")
    ch = top_n(oos, 15, oos_chart)
    if ch:
        out.append(ch)
    return out


def _cc_label(r: dict) -> str:
    return f"{CHANNEL_LABELS[r['ch']].split(' (')[0]} {r['cc']}"


def _bod_viz(curve: dict | None, plan_rows: list[dict], cur: dict, prv: dict, prev_label: str, by_cc: list[dict],
             order: list[str], fees: dict, has_cost: bool, f: Filters) -> list[dict]:
    """Đồ thị tóm tắt cho BOD, đặt trên cùng: kế hoạch lũy kế, thực tế vs kế hoạch, cầu doanh số so với kỳ so sánh,
    thác nước doanh số -> lãi sau QC, biên lãi theo kênh × nước."""
    out = []
    if curve:
        ch = chart("plan_curve", f"Doanh số lũy kế tháng {f.end:%m/%Y} so với kế hoạch", "line", curve["labels"],
                   [series("Kế hoạch", "n1", curve["plan"], dash=True), series("Thực tế", "c1", curve["actual"]),
                    series("Ước theo tốc độ hiện tại", "c2", curve["est"], dash=True)], unit="money",
                   subtitle=f"Thực tế đến {curve['d0']:%d/%m} (ngày đủ dữ liệu); đường ước = KH còn lại × % đạt.")
        ch["sum_mode"] = "none"
        out.append(ch)
    live = [r for r in plan_rows if not r["no_data"] and (r["fc_period"] or r["actual"])]
    if live:
        out.append(chart("plan_by_cc", "Thực tế so với kế hoạch theo kênh × nước", "bar", [_cc_label(r) for r in live],
                         [series("Kế hoạch", "n1", [r["fc_period"] for r in live]),
                          series("Thực tế", "c1", [r["actual"] for r in live],
                                 colors=["c1" if (r["attain"] or 0) >= 0.9 else "c2" for r in live])],
                         unit="money", tables=["plan"], subtitle="Đến ngày đủ dữ liệu của từng kênh. Đỏ = đạt < 90% KH."))
    steps = [(CHANNEL_LABELS[c].split(" (")[0], float(cur.get(c) or 0) - float(prv.get(c) or 0)) for c in order]
    steps = [s for s in steps if abs(s[1]) >= 1]
    if steps:
        wf = insights.waterfall("sales_bridge", "Doanh số tăng / giảm theo kênh", float(prv["total_sales"] or 0), steps,
                                float(cur["total_sales"] or 0), 1, f"So với {prev_label}.")
        wf["labels"][0], wf["labels"][-1] = prev_label.split(" (")[0].capitalize(), "Kỳ này"
        out.append(wf)
    rows = [r for r in by_cc if r["total_sales"] > 0]
    if rows:
        out.append(chart("sales_vs_prev", "Doanh số theo kênh × nước: kỳ này và kỳ so sánh", "bar",
                         [_cc_label(r) for r in rows],
                         [series(prev_label.split(" (")[0].capitalize(), "n1", [r["prev_total"] for r in rows]),
                          series("Kỳ này", "c1", [r["total_sales"] for r in rows])], unit="money", tables=["by_channel"]))
    if has_cost:
        ts = float(cur["total_sales"] or 0)
        fee = ts - float(cur["net_sales"] or 0)
        labels = ["Tổng doanh số", "Phí sàn", "Giá vốn", "Spend QC", "Lãi gộp sau QC"]
        level, values, raw = ts, [[0, ts]], [ts]
        for v in (fee, float(cur["cogs"] or 0), float(cur["spend"] or 0)):
            values.append([level - v, level])
            raw.append(-v)
            level -= v
        values.append([0, level])
        raw.append(level)
        out.append(chart("profit_waterfall", "Từ doanh số đến lãi gộp sau QC", "waterfall", labels,
                         [series("Từ doanh số đến lãi", "c1", values, colors=["n1", "c2", "c2", "c2", "c1"], raw=raw)],
                         unit="money", min=0,
                         subtitle="Chưa trừ phí FBA / CastleGate, giao hàng, hoàn trả."))
        out.append(chart("margin_by_cc", "Biên lãi theo kênh × nước", "bar", [_cc_label(r) for r in rows],
                         [series("Biên lãi gộp", "c3", [r.get("gross_margin") for r in rows]),
                          series("Biên sau QC", "c1", [r.get("profit_margin") for r in rows])],
                         unit="pct", tables=["by_channel"], sum_mode="none",
                         subtitle="Lãi gộp = DS sau phí sàn − giá vốn chuẩn."))
    return out


SHORT_NOTE = "Amazon giá bán lẻ, Wayfair giá sỉ. Kế hoạch = sheet forecast Q4. Tồn kho: kho nội bộ + CastleGate, chưa có FBA."
PROFIT_NOTE = " Lãi gộp = DS sau phí sàn − giá vốn chuẩn BOD, chưa trừ phí FBA / CastleGate, giao hàng, hoàn trả."


def all_overview(f: Filters, opts: dict) -> dict:
    prev, prev_label = compare_period(f, opts.get("compare"))
    fees, fresh = _fees(), _freshness()
    active = [c for c in CHANNELS if not f.sales_channels or c[0] in f.sales_channels]
    shop_spend = ad_spend_daily(f) is not None and (not f.sales_channels or "shopify" in f.sales_channels)
    cur_cc = _sales(f, "x.ch, x.cc")
    prev_cc = _sales(prev, "x.ch, x.cc")
    spend_cc, spend_prev = _spend(f), _spend(prev)
    cur, prv = _kpi(cur_cc, spend_cc, fees), _kpi(prev_cc, spend_prev, fees)
    # lãi gộp theo giá vốn chuẩn: cùng cách cho kỳ này và kỳ so sánh
    cg_cur, cg_prev = _cogs(f, fees), _cogs(prev, fees)
    has_cost = cg_cur["has_cost"] and opts.get("profit") != "0"  # profit=0: bản không có thông tin lợi nhuận
    if has_cost:
        for k, cg in ((cur, cg_cur), (prv, cg_prev)):
            k.update(_sum_cogs(cg["rows"], lambda r: 0).get(0, {"cogs": 0.0, "costed_sales": 0.0, "gross_profit": 0.0}))
            with_ratios(k)
    cogs_cc = _sum_cogs(cg_cur["rows"], lambda r: (r["ch"], r["cc"]))
    cogs_grp = _sum_cogs(cg_cur["rows"], lambda r: r["group_id"])

    # ---- kênh × nước
    rows: dict[tuple, dict] = {}
    for r in cur_cc:
        rows[(r["ch"], r["cc"])] = {"ch": r["ch"], "cc": r["cc"], "total_sales": r["total_sales"], "units": r["units"]}
    for r in prev_cc:
        rows.setdefault((r["ch"], r["cc"]), {"ch": r["ch"], "cc": r["cc"]})["prev_total"] = r["total_sales"]
    for r in spend_cc:
        x = rows.setdefault((r["ch"], r["cc"]), {"ch": r["ch"], "cc": r["cc"]})
        x["spend"], x["sales"] = r["spend"], r["sales"]
    total = float(cur["total_sales"] or 0) or None
    order = [c for c, _, _ in active]
    by_cc = []
    for (ch, cc), r in sorted(rows.items(), key=lambda kv: (order.index(kv[0][0]), -float(kv[1].get("total_sales") or 0))):
        r.update({"channel": CHANNEL_LABELS[ch], "country": cc, "fee": fees[ch], "fresh": fresh.get(ch)})
        for k in ("total_sales", "units", "prev_total", "spend", "sales"):
            r[k] = float(r.get(k) or 0)
        r["net_sales"] = r["total_sales"] * (1 - fees[ch])
        if has_cost:
            r.update(cogs_cc.get((ch, cc), {"cogs": 0.0, "costed_sales": 0.0, "gross_profit": 0.0}))
        with_ratios(r)
        r["share"] = r["total_sales"] / total if total else None
        if ch == "other" or (ch == "shopify" and not shop_spend):  # chưa có chi phí QC: để trống thay vì 0
            r["spend"] = r["sales"] = r["acos"] = r["tacos"] = r["ad_sales_share"] = None
        elif ch == "shopify":  # chi phí nhập tay, không biết DS nào đến từ QC
            r["sales"] = r["acos"] = r["ad_sales_share"] = None
        by_cc.append(r)

    # ---- theo kỳ (ngày / tuần)
    pk, unit = period_key(f, "x.d")
    labels = period_labels(f, unit == "tuần")
    idx = {d: i for i, d in enumerate(labels)}
    sales_by = {c: [0.0] * len(labels) for c, _, _ in CHANNELS}
    for r in _sales(f, "x.ch", period=pk):
        if r["d"] and r["d"].isoformat() in idx:
            sales_by[r["ch"]][idx[r["d"].isoformat()]] += float(r["total_sales"] or 0)
    ch_series = [series(label, color, sales_by[ch], {"cols": {"channel": [CHANNEL_LABELS[ch]]}})
                 for ch, label, color in active]

    def market_of(cc):
        return cc if cc in ("US", "CA", "AU") else "OTHER"
    markets = MARKETS + [MARKET_OTHER]
    mk_sales = {m: [0.0] * len(labels) for m, _, _ in markets}
    for r in _sales(f, "x.cc", period=pk):
        if r["d"] and r["d"].isoformat() in idx:
            mk_sales[market_of(r["cc"])][idx[r["d"].isoformat()]] += float(r["total_sales"] or 0)
    mk_series = [series(label, color, mk_sales[m], {"cols": {"country": [m]}} if m != "OTHER" else None)
                 for m, label, color in markets]

    # công ty: theo kỳ cho đồ thị, tổng kỳ này / kỳ trước cho bảng
    co_by: dict = {}
    for r in _sales(f, "x.co", period=pk):
        name = company_of(r["co"])
        vals = co_by.setdefault(name, [0.0] * len(labels))
        if r["d"] and r["d"].isoformat() in idx:
            vals[idx[r["d"].isoformat()]] += float(r["total_sales"] or 0)
    companies: dict = {}
    for r in _sales(f, "x.co, x.ch"):
        c = companies.setdefault(company_of(r["co"]), {"company": company_of(r["co"]), "units": 0.0,
                                                       **{ch: 0.0 for ch, _, _ in CHANNELS}})
        c[r["ch"]] += float(r["total_sales"] or 0)
        c["units"] += float(r["units"] or 0)
    for r in _sales(prev, "x.co"):
        c = companies.setdefault(company_of(r["co"]), {"company": company_of(r["co"]), "units": 0.0,
                                                       **{ch: 0.0 for ch, _, _ in CHANNELS}})
        c["prev_total"] = c.get("prev_total", 0.0) + float(r["total_sales"] or 0)
    by_company = []
    for c in companies.values():
        c["total_sales"] = sum(c[ch] for ch, _, _ in CHANNELS)
        c["prev_total"] = c.get("prev_total", 0.0)
        with_ratios(c)
        c["share"] = c["total_sales"] / total if total else None
        if c["total_sales"] or c["prev_total"]:
            by_company.append(c)
    by_company.sort(key=lambda c: (c["company"] == COMPANY_OTHER, -c["total_sales"]))
    co_order = [c["company"] for c in by_company if c["total_sales"]]
    co_colors = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]
    co_series = [series(name, "n1" if name == COMPANY_OTHER else co_colors[i % len(co_colors)], co_by.get(name, [0.0] * len(labels)),
                        {"cols": {"company": [name]}}) for i, name in enumerate(co_order)]
    # Shopify: kỳ thuộc tháng chưa nhập chi phí để trống (None) thay vì TACoS 0
    spend_by = {c: [0.0 if c != "shopify" else None] * len(labels) for c in ("amazon", "wayfair", "shopify")}
    for r in _spend(f, period=period_key(f, "f.report_date")[0]):
        if r["d"].isoformat() in idx:
            i = idx[r["d"].isoformat()]
            spend_by[r["ch"]][i] = (spend_by[r["ch"]][i] or 0) + float(r["spend"] or 0)
    mk_spend = {m: [0.0] * len(labels) for m, _, _ in markets}
    for r in _spend(f, period=period_key(f, "f.report_date")[0]):
        if r["d"].isoformat() in idx:
            mk_spend[market_of(r["cc"])][idx[r["d"].isoformat()]] += float(r["spend"] or 0)
    all_sales = [sum(v[i] for v in sales_by.values()) for i in range(len(labels))]
    all_spend = [sum(v[i] for v in mk_spend.values()) for i in range(len(labels))]
    spend_series = [series(f"Spend {label}", color, mk_spend[m], {"cols": {"country": [m]}} if m != "OTHER" else None)
                    for m, label, color in markets]
    spend_series.append(series("TACoS tổng (trục phải)", "n1",
                               [(x / y) if y else None for x, y in zip(all_spend, all_sales)], line=True, unit="pct",
                               total=sum(all_spend) / sum(all_sales) if sum(all_sales) else None))

    # ---- theo nhóm SP
    grp = _sales(f, "x.ch, p.group_id", extra=", MAX(p.group_name) AS group_name")
    grp_prev = {r["group_id"]: float(r["total_sales"] or 0) for r in _sales(prev, "p.group_id")}
    gspend = _group_spend(f)
    groups: dict = {}
    for r in grp:
        g = groups.setdefault(r["group_id"], {"group_id": r["group_id"],
                                              "group_name": r["group_name"] or "(chưa gán nhóm)",
                                              "risk_skus": 0, "lost_sales_90": 0.0, **{c: 0.0 for c, _, _ in CHANNELS}})
        g[r["ch"]] += float(r["total_sales"] or 0)
    # tồn kho: số SKU hết / sắp hết hàng (nút ALL-<nước>) trong các SKU có bán trong kỳ
    sold_ch = _sales(f, "x.pid, x.cc, x.ch, p.group_id")
    sold_map: dict = {}  # (product_id, nước) -> {kênh: doanh số}
    sold = {}
    for r in sold_ch:
        if r["pid"]:
            sold_map.setdefault((r["pid"], r["cc"]), {})[r["ch"]] = float(r["total_sales"] or 0)
            sold[(r["pid"], r["cc"])] = r
    sold = list(sold.values())
    # lọc kênh: giữ SKU × nước có bán trên các kênh đó trong 90 ngày tới ngày cuối kỳ (SKU hết hàng cả kỳ thì trong kỳ
    # không có đơn nhưng vẫn phải hiện trong danh mục thiếu hàng)
    keep = None
    if f.sales_channels:
        f90 = Filters(**f.__dict__)
        f90.start = f.end - timedelta(days=89)
        keep = {(r["pid"], r["cc"]) for r in _sales(f90, "x.pid, x.cc") if r["pid"]}
    inv_cards, inv_cc, risk, inv_as_of = _inventory(f, sold_map, keep)
    status = insights.stock_status({(r["pid"], r["cc"]) for r in sold})
    for r in sold:
        s = status.get((r["pid"], r["cc"]))
        g = groups.get(r["group_id"])
        if g is None or not s:
            continue
        if s["status"] in insights.RISK_STATUSES:
            g["risk_skus"] += 1
        g["lost_sales_90"] += float(s.get("lost_sales_90") or 0)
    by_group = []
    for g in groups.values():
        g["total_sales"] = sum(g[c] for c in order)
        g["prev_total"] = grp_prev.get(g["group_id"], 0.0)
        g["spend"] = gspend.get(g["group_id"], 0.0)
        if has_cost:
            g.update(cogs_grp.get(g["group_id"], {"cogs": 0.0, "costed_sales": 0.0, "gross_profit": 0.0}))
        with_ratios(g)
        g["share"] = g["total_sales"] / total if total else None
        by_group.append(g)
    by_group.sort(key=lambda g: -g["total_sales"])
    filtered = bool(f.group_ids or f.brand_ids)
    unmapped = gspend.get(None, 0.0) if not filtered else 0.0

    top = [g for g in by_group if g["group_id"] is not None]
    late = " Cột cuối có thể thấp vì đơn về trễ."
    viz = [
        chart("sales_by_market", f"Doanh số theo thị trường, theo {unit}", "bar_stacked", labels, mk_series, unit="money",
              tables=["by_channel"],
              subtitle="Nước của khách (Wayfair) / của tài khoản, store. Bấm một đoạn để lọc bảng Kênh × nước." + late),
        chart("sales_by_channel", f"Doanh số theo kênh bán, theo {unit}", "bar_stacked", labels, ch_series, unit="money",
              tables=["by_channel"],
              subtitle="Amazon theo giá bán lẻ, Wayfair theo giá sỉ (đã trừ hoa hồng), Shopify sau giảm giá. "
                       "Bấm một đoạn để lọc bảng." + late),
        chart("sales_by_company", f"Doanh số theo công ty, theo {unit}", "bar_stacked", labels, co_series, unit="money",
              tables=["by_company"],
              subtitle="Công ty theo tài khoản Amazon / Wayfair, store Shopify, mã kênh khác (vd EBAY-DHI = DH Intra). "
                       "Bấm một đoạn để lọc bảng Theo công ty." + late),
        chart("spend_by_market", f"Chi phí quảng cáo theo thị trường, theo {unit}", "bar_stacked", labels, spend_series,
              unit="money", tables=["by_channel"],
              subtitle="Spend Amazon + Wayfair" + (" + chi phí Shopify nhập tay" if shop_spend else "")
                       + ". Đường = TACoS tổng (spend ÷ doanh số các kênh đang xem)."),
    ]
    viz += _inventory_viz(inv_cc, risk)[:1]
    def groups_chart(rows):
        return chart("groups_by_channel", f"{len(rows)} nhóm SP doanh số cao nhất, chia theo kênh", "hbar_stacked",
                     [insights.short(g["group_name"], 34) for g in rows],
                     [series(label, color, [g[ch] for g in rows]) for ch, label, color in active],
                     unit="money", tables=["by_group"],
                     label_filters=[{"cols": {"group_name": [g["group_name"]]}} for g in rows],
                     subtitle="Nhóm bán tốt ở một kênh nhưng yếu ở kênh khác là chỗ nên xem lại listing / QC. "
                              "Bấm một thanh để lọc bảng.")
    groups_viz = top_n(top, 15, groups_chart)
    if groups_viz:
        viz.append(groups_viz)

    viz += _inventory_viz(inv_cc, risk)[1:]
    viz = [v for v in viz if v["series"]]  # vd chỉ xem Shopify chưa nhập chi phí: không có đường TACoS nào

    fee_txt = ", ".join(f"{CHANNEL_LABELS[c].split(' (')[0]} {fees[c]:.0%}" for c in order)
    cc_cols = [col("channel", "Kênh"), col("country", "Nước"), col("total_sales", "Tổng DS", "money"),
               col("share", "Tỷ trọng", "pct"), col("prev_total", "DS kỳ so sánh", "money"), col("growth", "± kỳ so sánh", "pct"),
               col("fee", "Phí sàn", "pct"), col("net_sales", "DS sau phí sàn", "money"), col("units", "Units", "int"),
               col("spend", "Spend QC", "money"), col("sales", "DS từ QC", "money"), col("acos", "ACoS", "pct"),
               col("tacos", "TACoS", "pct"), col("after_ads", "DS sau phí & QC", "money")]
    profit_cols = [col("cogs", "Giá vốn", "money"), col("gross_profit", "Lãi gộp", "money"),
                   col("gross_margin", "Biên lãi gộp", "pct"), col("profit_after_ads", "Lãi gộp sau QC", "money"),
                   col("profit_margin", "Biên sau QC", "pct"), col("cogs_cover", "% DS có giá vốn", "pct")]
    if has_cost:
        cc_cols += profit_cols
    cc_cols.append(col("fresh", "Dữ liệu đến", "date"))
    g_cols = ([col("group_name", "Nhóm SP")] + [col(c, CHANNEL_LABELS[c], "money") for c in order]
              + [col("total_sales", "Tổng DS", "money"), col("share", "Tỷ trọng", "pct"),
                 col("prev_total", "DS kỳ so sánh", "money"), col("growth", "± kỳ so sánh", "pct"),
                 col("spend", "Spend QC (chia theo SP)", "money"), col("tacos", "TACoS", "pct")]
              + (profit_cols if has_cost else [])
              + [
                 col("risk_skus", "SKU hết / sắp hết", "int"), col("lost_sales_90", "DS mất ước tính 90 ngày (mọi SKU)", "money")])
    pa = ("cogs", "costed_sales", "gross_profit") if has_cost else ()
    t_cc = _table("by_channel", "Theo kênh × nước", cc_cols, by_cc, extra_additive=("total_sales",) + pa)
    if t_cc.get("totals"):
        t_cc["totals"]["fee"] = t_cc["totals"].get("fee_pct")
    t_grp = _table("by_group", "Theo nhóm SP", g_cols, by_group,
                   extra_additive=("total_sales",) + tuple(order) + ("risk_skus", "lost_sales_90") + pa)
    inv_cols = [col("country", "Nước"), col("skus", "Số SKU", "int"), col("available", "Tồn khả dụng", "int"),
                col("incoming", "Đang về", "int"), col("velocity", "Bán / ngày", "num2"),
                col("days_cover", "Số ngày đủ bán", "num2"), col("OOS", "Đang hết hàng", "int"),
                col("D14", "Hết trong 14 ngày", "int"), col("D30", "Hết trong 15–30 ngày", "int"),
                col("d30_total", "Hết trong 30 ngày (gồm 14)", "int"), col("OK", "Ổn 30–90 ngày", "int"),
                col("OVER", "Tồn nhiều ≥ 90 ngày", "int"), col("NO_SALES", "Có tồn, không bán", "int"),
                col("lost_sales_90", "DS mất ước tính 90 ngày (mọi SKU)", "money")]
    risk_cols = [col("product_sku", "SKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"), col("country", "Nước"),
                 col("status_label", "Dự báo"), col("stockout_date", "Dự kiến hết hàng", "date"),
                 col("days_left", "Còn (ngày)", "num2"), col("channels", "Kênh có bán trong kỳ"),
                 col("total_sales", "DS kỳ này", "money"), col("available", "Tồn khả dụng", "int"),
                 col("velocity", "Bán / ngày", "num2"), col("sales_day", "DS / ngày", "money"),
                 col("next_eta", "Lô kế: ETA", "date"), col("next_qty", "Lô kế: SL", "int"),
                 col("oos_days_before_next", "Ngày đứt hàng trước lô kế", "int"), col("incoming_30d", "Về trong 30 ngày", "int"),
                 col("need_60d", "Thiếu để đủ 60 ngày", "int"), col("lost_sales_90", "DS mất ước tính 90 ngày", "money")]
    co_cols = ([col("company", "Công ty")] + [col(c, CHANNEL_LABELS[c], "money") for c in order]
               + [col("total_sales", "Tổng DS", "money"), col("share", "Tỷ trọng", "pct"),
                  col("prev_total", "DS kỳ so sánh", "money"), col("growth", "± kỳ so sánh", "pct"), col("units", "Units", "int")])
    t_co = _table("by_company", "Theo công ty", co_cols, by_company, extra_additive=("total_sales",) + tuple(order))
    t_inv = _table("inv_country", "Tồn kho & dự báo theo nước", inv_cols, inv_cc, with_totals=False)
    t_risk = _table("stock_risk", "Danh mục sản phẩm thiếu hàng: đang hết / hết trong 30 ngày", risk_cols, risk,
                    with_totals=False)
    tables = [t_risk, t_cc, t_co, t_grp, t_inv]  # danh mục thiếu hàng lên đầu (sau bảng kế hoạch)
    card_groups = []
    plan = _plan(f, fresh, order)
    if plan:
        plan_rows, plan_cards, plan_note, plan_tot, plan_curve = plan
        plan_cols = [col("channel", "Kênh"), col("country", "Nước"), col("data_to", "Dữ liệu đến", "date"),
                     col("fc_period", "Kế hoạch (đến ngày đủ DL)", "money"), col("actual", "Thực tế (cùng khoảng)", "money"),
                     col("attain", "% đạt", "pct"), col("gap", "Chênh lệch", "money"),
                     col("fc_month", f"KH tháng {f.end:%m/%Y}", "money")]
        if f.start == f.end.replace(day=1):
            plan_cols += [col("est_month", "Ước cả tháng", "money"), col("est_attain", "Ước % KH tháng", "pct"),
                          col("est_gap", "Ước thiếu / vượt KH", "money")]
        t_plan = _table("plan", "Thực tế so với kế hoạch", plan_cols, plan_rows, with_totals=False)
        t_plan["totals"] = plan_tot
        tables.insert(0, t_plan)
        card_groups.append({"title": f"Kế hoạch tháng {f.end:%m/%Y}", "cards": plan_cards})
    viz = _bod_viz(plan[4] if plan else None, plan[0] if plan else [], cur, prv, prev_label, by_cc, order, fees,
                   has_cost, f) + viz
    for t in tables:
        t["keep_order"] = True
    if shop_spend:
        shop_txt = ("Spend QC gồm Amazon, Wayfair và chi phí Shopify nhập tay theo tháng (tab Shopify › Chi phí QC, chia "
                    "đều cho các ngày trong tháng, store / tháng chưa nhập tính là 0)")
    elif f.group_ids or f.brand_ids:
        shop_txt = "Spend QC gồm Amazon + Wayfair (chi phí Shopify nhập theo store nên không tính khi lọc nhóm SP / brand)"
    else:
        shop_txt = "Spend QC gồm Amazon + Wayfair (kỳ này chưa nhập chi phí QC Shopify ở tab Shopify › Chi phí QC)"
    note = (f"Doanh số mỗi kênh tính theo cách của kênh đó: Amazon giá bán lẻ (item_price, bỏ đơn hủy), Wayfair giá sỉ "
            f"(tiền Wayfair trả công ty), Shopify sau giảm giá, kênh khác theo doanh thu backend. DS sau phí sàn trừ phí "
            f"theo kênh ({fee_txt}; sửa ở Amazon › Công cụ › Giá vốn & phí). {shop_txt}. Lọc nhóm SP / brand dùng cùng "
            f"cách với tab của từng sàn (giữ campaign có sản phẩm thuộc nhóm).")
    if unmapped:
        note += f" Bảng theo nhóm SP chia spend theo sản phẩm quảng cáo; ${unmapped:,.0f} spend chưa gán được nhóm."
    note += (" Tồn kho (nhóm thẻ thứ hai, đồ thị dự báo tồn kho, 15 SKU sắp hết và 2 bảng cuối) là ảnh chụp mới nhất, không "
             "theo khoảng ngày: kho nội bộ + CastleGate của từng nước, chưa có FBA. Dự kiến hết hàng đã cộng hàng đang về "
             "theo ETA; tồn nhiều = đủ bán ≥ 90 ngày với tồn hiện có.")
    if has_cost:
        cover = cur.get("cogs_cover")
        note += (" Lãi gộp = DS sau phí sàn − giá vốn chuẩn BOD (sheet COGS; Amazon trộn giá WH / FBA, Wayfair trộn WH / "
                 "CastleGate theo số đơn vị giao từ kho sàn; Shopify, kênh khác giá WH; quy USD theo tỷ giá mới nhất)"
                 + (f"; {cover:.0%} doanh số có giá vốn, phần còn lại ước theo tỷ lệ giá vốn của cùng kênh × nước"
                    if cover is not None else "")
                 + ". Chưa trừ phí FBA / CastleGate, phí giao hàng, hoàn trả. Lãi gộp sau QC = lãi gộp − Spend QC.")
    note += f" So sánh với {prev_label}."
    if plan:
        note += " " + plan_note
    if f.sales_channels:
        note += " Đang lọc kênh: tồn kho chỉ gồm SKU × nước có bán trên kênh đó trong kỳ (kho dùng chung cho mọi kênh)."
    if shop_spend:
        note += " Chi phí QC Shopify không chia được theo nhóm SP nên không có trong bảng Theo nhóm SP."
    if opts.get("compact") == "1":  # bản gọn cho BOD: ghi chú ngắn, bỏ phụ đề đồ thị
        lag = ", ".join(f"{CHANNEL_LABELS[c].split(' (')[0]} {fresh[c]:%d/%m}" for c in order
                        if c != "other" and fresh.get(c))
        note = (SHORT_NOTE + (PROFIT_NOTE if has_cost else "") + (" Shopify sau giảm giá." if "shopify" in order else " Không gồm Shopify.")
                + f" So sánh với {prev_label}. Dữ liệu đến: {lag}.")
        for v in viz:
            v.pop("subtitle", None)
    return {
        "title": "Tổng hợp bán hàng mọi kênh",
        "note": note,
        "viz": viz,
        "kpis": {"current": cur, "previous": prv, "prev_label": prev_label,
                 "def": [d for d in KPI_DEF if (d[0] not in CHANNEL_LABELS or d[0] in order)
                         and (has_cost or d[0] not in PROFIT_KPIS)]},
        "cards": inv_cards,
        "cards_title": "Tồn kho & dự báo hết hàng" + (f" (ngày {inv_as_of:%d/%m/%Y}, không theo khoảng ngày)" if inv_as_of else ""),
        "tables": tables,
        "card_groups": card_groups,
    }


ALL_REPORTS = {"all_overview": all_overview}
