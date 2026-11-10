"""Phần phân tích thêm cho tab Tổng quan (Amazon và Wayfair).

- Doanh số tổng tách QC / tự nhiên theo ngày (tự nhiên = tổng doanh số đơn hàng − doanh số quy về QC, xấp xỉ).
- Cầu nối kỳ trước → kỳ này: Ad Sales = Clicks × CVR × AOV, Spend = Clicks × CPC (thay lần lượt từng yếu tố, tổng
  các bước bằng đúng chênh lệch).
- Sản phẩm tăng / giảm Ad Sales mạnh nhất, ma trận ACoS × Ad Sales tô theo tồn kho, Spend vào SKU hết / sắp hết hàng.
- Thẻ: Spend dự kiến cả tháng, % Spend vào SKU hết / sắp hết hàng, doanh số mất do hết hàng, campaign hết ngân sách.

Tồn kho lấy từ inv_projection ở nút ALL-<nước> (kho nội bộ + CastleGate, chưa có tồn FBA).
"""
from calendar import monthrange
from datetime import date

from app.db import fetch_all
from app.filters import Filters
from app.viz import chart, series, top_n

ACOS_TARGET = 0.3          # cùng mặc định "ACoS tối đa" của tab Thêm / Phủ định
RISK_STATUSES = ("OOS", "CRITICAL")
CAPPED_SHARE = 0.3         # campaign hết ngân sách ≥ 30% số ngày
STOCK_GROUPS = [           # (nhãn, vai trò màu, các trạng thái trong inv_projection)
    ("Hết hàng", "st:OOS", ("OOS",)),
    ("Nguy cấp < 14 ngày", "st:CRITICAL", ("CRITICAL",)),
    ("Thấp < 30 ngày", "st:LOW", ("LOW",)),
    ("Đủ hàng", "st:OK", ("OK", "OVER")),
    ("Chưa rõ tồn", "st:NO_SALES", None),
]


def _nz(v) -> float:
    return float(v or 0)


def short(text: str, n: int = 44) -> str:
    """Nhãn trục đồ thị: tên campaign dài cắt bớt ở giữa (giữ đầu và đuôi vì đuôi thường là kiểu match / mã)."""
    return text if len(text) <= n else text[:n - 15] + "…" + text[-14:]


# ---------------------------------------------------------------- cầu nối kỳ trước → kỳ này

def sales_bridge(cur: dict, prev: dict) -> list[tuple[str, float]] | None:
    """Ad Sales = Clicks × CVR × AOV. Trả các bước (tên, chênh lệch) hoặc None nếu một kỳ không có click / đơn."""
    c0, c1 = _nz(prev.get("clicks")), _nz(cur.get("clicks"))
    o0, o1 = _nz(prev.get("orders")), _nz(cur.get("orders"))
    s0, s1 = _nz(prev.get("sales")), _nz(cur.get("sales"))
    if not (c0 and c1 and o0 and o1):
        return None
    cvr0, cvr1, aov0, aov1 = o0 / c0, o1 / c1, s0 / o0, s1 / o1
    return [("Clicks", (c1 - c0) * cvr0 * aov0),
            ("CVR", c1 * (cvr1 - cvr0) * aov0),
            ("Giá trị đơn (AOV)", c1 * cvr1 * (aov1 - aov0))]


def spend_bridge(cur: dict, prev: dict) -> list[tuple[str, float]] | None:
    """Spend = Clicks × CPC."""
    c0, c1 = _nz(prev.get("clicks")), _nz(cur.get("clicks"))
    if not (c0 and c1):
        return None
    cpc0, cpc1 = _nz(prev.get("spend")) / c0, _nz(cur.get("spend")) / c1
    return [("Clicks", (c1 - c0) * cpc0), ("CPC", c1 * (cpc1 - cpc0))]


def waterfall(key: str, title: str, start: float, steps: list[tuple[str, float]], end: float, good: int,
              subtitle: str) -> dict:
    """Thác nước: cột Kỳ trước, các bước (thanh nổi), cột Kỳ này. good = +1 nếu tăng là tốt, -1 nếu tăng là xấu.
    Trục không bắt đầu từ 0 để thấy rõ các bước (ghi trong subtitle)."""
    labels, values, raw, colors, level = ["Kỳ trước"], [[0, start]], [start], ["n1"], start
    for name, d in steps:
        labels.append(name)
        values.append([level, level + d])
        raw.append(d)
        colors.append("c1" if d * good >= 0 else "c2")
        level += d
    labels.append("Kỳ này")
    values.append([0, end])
    raw.append(end)
    colors.append("n1")
    levels = [start, end] + [v[1] for v in values[1:-1]]
    lo, hi = min(levels), max(levels)
    floor = max(0.0, lo - (hi - lo) * 0.6) if hi > lo else 0.0
    return chart(key, title, "waterfall", labels, [series(title, "c1", values, colors=colors, raw=raw)],
                 unit="money", subtitle=subtitle, min=round(floor, -2) if floor > 1000 else floor)


def bridge_charts(cur: dict, prev: dict, sales_label: str) -> list[dict]:
    out = []
    sb = sales_bridge(cur, prev)
    if sb:
        out.append(waterfall("bridge_sales", f"Vì sao {sales_label} thay đổi so với kỳ trước", _nz(prev.get("sales")), sb,
                             _nz(cur.get("sales")), +1,
                             "Xanh = làm tăng, cam = làm giảm. Tách lần lượt: lượng click, tỉ lệ chuyển đổi, giá trị "
                             "đơn. Trục không bắt đầu từ 0."))
    pb = spend_bridge(cur, prev)
    if pb:
        out.append(waterfall("bridge_spend", "Vì sao Spend thay đổi so với kỳ trước", _nz(prev.get("spend")), pb,
                             _nz(cur.get("spend")), -1,
                             "Xanh = giúp giảm chi, cam = làm tăng chi. Spend = Clicks × CPC. Trục không bắt đầu từ 0."))
    return out


# ---------------------------------------------------------------- doanh số tổng: QC + tự nhiên

def organic_total(trend: list[dict]) -> float | None:
    """Tự nhiên cả kỳ = Σ (tổng DS − DS QC) chỉ trên các ngày đã có doanh số đơn hàng (không cắt ngày âm về 0),
    để Ad Sales + tự nhiên khớp đúng Tổng DS."""
    days = [r for r in trend if r.get("total_sales")]
    return sum(_nz(r["total_sales"]) - _nz(r.get("sales")) for r in days) if days else None


def organic_chart(trend: list[dict], sales_label: str) -> dict:
    """Cột QC + tự nhiên theo ngày. Ngày có DS QC nhưng chưa có doanh số đơn hàng tách ra series xám; ngày DS QC lớn
    hơn tổng DS vẽ tự nhiên = 0 nhưng tổng chú giải vẫn tính số âm, nên chú giải cộng lại đúng bằng thẻ Tổng DS."""
    labels = [r["date"] for r in trend]
    has_total = [bool(r.get("total_sales")) for r in trend]
    ad = [r.get("sales") if h else None for r, h in zip(trend, has_total)]
    ad_only = [None if h else r.get("sales") for r, h in zip(trend, has_total)]
    org = [max(_nz(r["total_sales"]) - _nz(r.get("sales")), 0) if h else None for r, h in zip(trend, has_total)]
    neg = sum(1 for r, h in zip(trend, has_total) if h and _nz(r.get("sales")) > _nz(r["total_sales"]))
    org_total = organic_total(trend)
    ad_total = sum(_nz(v) for v in ad)
    sub = ("Tự nhiên = tổng doanh số đơn hàng − doanh số quy về QC. Là số xấp xỉ: QC tính đơn trong cửa sổ quy đổi "
           "và cả đơn của SKU khác, nên phần tự nhiên có thể thấp hơn thực tế.")
    if neg:
        sub += (f" {neg} ngày có DS QC lớn hơn tổng DS (đơn quy về QC ghi nhận khác ngày): cột tự nhiên vẽ 0, tổng "
                f"chú giải vẫn trừ phần âm để {sales_label} + tự nhiên = Tổng DS.")
    if any(ad_only):
        sub += " Cột xám: ngày đã có số QC nhưng chưa có doanh số đơn hàng, không tính vào tự nhiên."
    return chart("organic", "Tổng doanh số: từ quảng cáo và tự nhiên", "bar_stacked", labels,
                 [series(sales_label, "c1", ad, total=ad_total),
                  series("Tự nhiên (ước tính)", "c3", org, total=org_total),
                  series(f"{sales_label} (chưa có DS đơn hàng)", "n1", ad_only)],
                 unit="money", subtitle=sub)


# ---------------------------------------------------------------- theo sản phẩm

def stock_status(pairs: set[tuple[int, str]]) -> dict[tuple[int, str], dict]:
    """(product_id, nước) -> {status, days_cover, lost_sales_90} ở nút ALL-<nước>."""
    ids = sorted({p for p, _ in pairs if p})
    if not ids:
        return {}
    names = {f"i{n}": v for n, v in enumerate(ids)}
    rows = fetch_all(f"""SELECT product_id, SUBSTRING(node_id, 5) AS country, status, days_cover, lost_sales_90
        FROM inv_projection WHERE node_id LIKE 'ALL-%' AND product_id IN ({', '.join(':' + k for k in names)})""", names)
    return {(r["product_id"], r["country"]): r for r in rows}


def stock_group(status: str | None) -> tuple[str, str]:
    for label, color, statuses in STOCK_GROUPS:
        if statuses and status in statuses:
            return label, color
    return STOCK_GROUPS[-1][0], STOCK_GROUPS[-1][1]


def movers_chart(rows: list[dict], sales_label: str, goto: dict, n: int = 5) -> dict | None:
    """rows: {label, filter_value, sales, sales0}. n sản phẩm tăng và n sản phẩm giảm Ad Sales mạnh nhất."""
    for r in rows:
        r["delta"] = _nz(r.get("sales")) - _nz(r.get("sales0"))
    up = sorted([r for r in rows if r["delta"] > 0], key=lambda r: -r["delta"])[:n]
    down = sorted([r for r in rows if r["delta"] < 0], key=lambda r: r["delta"])[:n]
    picked = up + list(reversed(down))
    if not picked:
        return None
    return chart("movers", f"Sản phẩm có {sales_label} tăng / giảm mạnh nhất", "hbar", [r["label"] for r in picked],
                 [series(f"Chênh lệch {sales_label}", "c1", [r["delta"] for r in picked],
                         colors=["c1" if r["delta"] > 0 else "c2" for r in picked])],
                 unit="money", signed=True,
                 subtitle="So với kỳ trước cùng số ngày. Xanh = tăng, cam = giảm. Bấm một thanh để xem sản phẩm đó.",
                 goto=goto["goto"],
                 label_filters=[{"opts": goto["opts"], "cols": {goto["col"]: [r["filter_value"]]}} for r in picked])


def matrix_chart(rows: list[dict], status: dict, sales_label: str, n: int = 40) -> dict | None:
    """Ma trận ACoS × Ad Sales của n sản phẩm chi nhiều nhất; kích thước = Spend, màu = tình trạng tồn kho."""
    top = sorted([r for r in rows if _nz(r.get("spend")) > 0], key=lambda r: -_nz(r["spend"]))[:n]
    if not top:
        return None
    max_spend = max(_nz(r["spend"]) for r in top) or 1
    groups: dict[str, dict] = {}
    no_sales = 0
    for r in top:
        if not _nz(r.get("sales")):
            no_sales += 1
            continue
        st = status.get((r.get("product_id"), r.get("country")), {}).get("status")
        label, color = stock_group(st)
        g = groups.setdefault(label, {"color": color, "points": []})
        acos, be = _nz(r["spend"]) / _nz(r["sales"]), r.get("breakeven_acos")
        g["points"].append({"x": min(acos, 1.5), "y": _nz(r["sales"]),
                            "r": 4 + 14 * (_nz(r["spend"]) / max_spend) ** 0.5, "label": r["label"],
                            "spend": _nz(r["spend"]), "acos": acos, "be": be,
                            # hình: tròn = ACoS dưới mức hòa vốn của SKU, tam giác = trên mức hòa vốn, thoi = chưa có giá vốn
                            "pt": "rectRot" if be is None else ("circle" if acos <= be else "triangle")})
    order = [g[0] for g in STOCK_GROUPS]
    ser = [series(k, groups[k]["color"], groups[k]["points"]) for k in order if k in groups]
    note = (f"{len(top)} sản phẩm chi nhiều nhất. Kích thước = Spend, màu = tồn kho (nội bộ + CastleGate theo nước). "
            f"Hình: tròn = ACoS dưới mức hòa vốn của SKU (QC có lãi), tam giác = trên mức hòa vốn, thoi = chưa nhập "
            f"giá vốn. Trái trên: ACoS tốt, bán nhiều → tăng ngân sách. Phải trên: bán nhiều nhưng ACoS cao → tối ưu "
            f"bid. Phải dưới: cân nhắc giảm / dừng.")
    if no_sales:
        note += f" {no_sales} sản phẩm có Spend nhưng chưa có đơn: xem đồ thị riêng bên cạnh."
    return chart("matrix", f"Ma trận sản phẩm: ACoS × {sales_label}", "scatter", [], ser, unit="money", x_unit="pct",
                 subtitle=note, refs=[{"value": ACOS_TARGET, "label": f"ACoS mục tiêu {ACOS_TARGET:.0%}"}])


NO_ORDER_CLICKS = 20        # dưới mức này chưa đủ click để kết luận sản phẩm không ra đơn


def no_order_chart(rows: list[dict], end: date, window: int, goto: dict, n: int = 12) -> dict | None:
    """Sản phẩm có Spend nhưng chưa có đơn quy về QC trong kỳ (ma trận không vẽ được vì ACoS vô hạn).
    Cam = đủ dữ liệu để xem lại (≥ NO_ORDER_CLICKS click và bắt đầu chi trước cửa sổ quy đổi); xám = còn sớm."""
    picked = sorted([r for r in rows if _nz(r.get("spend")) > 0 and not _nz(r.get("orders"))],
                    key=lambda r: -_nz(r["spend"]))
    if not picked:
        return None
    total = sum(_nz(r["spend"]) for r in picked)

    def ready(r):
        first = r.get("first_spend")
        return _nz(r.get("clicks")) >= NO_ORDER_CLICKS and first is not None and (end - first).days >= window

    def build(top):
        labels = [f"{r['label']} · {int(_nz(r.get('clicks')))} click · {int(_nz(r.get('spend_days')))} ngày" for r in top]
        return chart("no_orders", "Sản phẩm có Spend nhưng chưa có đơn từ QC", "hbar", labels,
                     [series("Spend", "c2", [r["spend"] for r in top], colors=["c2" if ready(r) else "n1" for r in top])],
                     unit="money",
                     subtitle=(f"{len(picked)} sản phẩm, tổng ${total:,.0f} trong kỳ (hiện {len(top)} chi nhiều nhất). "
                               f"Cam = ≥ {NO_ORDER_CLICKS} click và đã chi từ ≥ {window} ngày trước (hết cửa sổ quy đổi) "
                               f"→ nên xem lại listing, giá, bid. Xám = còn ít click hoặc mới chạy, đơn có thể chưa quy "
                               f"về. Bấm một thanh để xem sản phẩm đó."),
                     goto=goto["goto"],
                     label_filters=[{"opts": goto["opts"], "cols": {goto["col"]: [r["filter_value"]]}} for r in top])
    return top_n(picked, n, build)


def stock_risk(rows: list[dict], status: dict, n: int = 10) -> tuple[dict | None, float, float, list[dict]]:
    """Spend vào SKU hết / sắp hết hàng. Trả (đồ thị, spend rủi ro, DS mất do hết hàng 90 ngày, dòng chi tiết)."""
    risky, lost = [], 0.0
    seen = set()
    for r in rows:
        key = (r.get("product_id"), r.get("country"))
        s = status.get(key)
        if not s or _nz(r.get("spend")) <= 0:
            continue
        if key not in seen:
            seen.add(key)
            lost += _nz(s.get("lost_sales_90"))
        if s["status"] in RISK_STATUSES:
            risky.append({**r, "status": s["status"], "status_label": stock_group(s["status"])[0],
                          "days_cover": s.get("days_cover")})
    risky.sort(key=lambda r: -_nz(r["spend"]))
    spend = sum(_nz(r["spend"]) for r in risky)
    ch = top_n(risky, n, lambda top: chart(
        "stock_risk", "Spend vào SKU hết / sắp hết hàng", "hbar", [r["label"] for r in top],
        [series("Spend", "c1", [r["spend"] for r in top], colors=["st:" + r["status"] for r in top])],
        unit="money", subtitle="Đỏ = hết hàng, cam = còn dưới 14 ngày (kho nội bộ + CastleGate theo nước, "
                               "chưa có tồn FBA). Nên giảm bid hoặc tạm dừng tới khi có hàng về."))
    return ch, spend, lost, risky


# ---------------------------------------------------------------- ngân sách, dự báo

def budget_summary(rows: list[dict], tab: str, n: int = 10) -> tuple[dict | None, int, int]:
    """rows từ báo cáo Ngân sách. Trả (đồ thị campaign hết NS mà ACoS tốt, số campaign hết NS thường xuyên, tổng số)."""
    active = [r for r in rows if r.get("days") and _nz(r.get("spend")) > 0]
    capped = [r for r in active if _nz(r.get("days_capped")) >= CAPPED_SHARE * r["days"]]
    good = sorted([r for r in capped if r.get("acos") is not None and r["acos"] <= ACOS_TARGET],
                  key=lambda r: (-_nz(r["days_capped"]), -_nz(r.get("sales"))))
    ch = top_n(good, n, lambda rows: chart(
        "budget_capped", "Campaign ACoS tốt nhưng hay hết ngân sách", "hbar",
        [short(r["campaign_name"] or "?") for r in rows],
        [series("Ngày hết ngân sách", "c1", [r["days_capped"] for r in rows])], unit="int", sum_mode="none",
        subtitle=f"ACoS ≤ {ACOS_TARGET:.0%} và hết ngân sách ≥ {CAPPED_SHARE:.0%} số ngày: đang bỏ lỡ doanh "
                 f"số, nên tăng ngân sách. Bấm để xem ở tab Ngân sách.",
        goto={"tab": tab, "table": "budget"},
        label_filters=[{"cols": {"campaign_name": [r["campaign_name"]]}} for r in rows]))
    return ch, len(capped), len(active)


def month_window(end: date) -> tuple[date, int, int]:
    """(ngày đầu tháng của end, số ngày đã qua, số ngày trong tháng)."""
    first = end.replace(day=1)
    return first, (end - first).days + 1, monthrange(end.year, end.month)[1]


def forecast_card(month_spend: float, end: date) -> dict:
    first, elapsed, days = month_window(end)
    value = month_spend / elapsed * days if elapsed else None
    done = elapsed == days
    return {"label": f"Spend {'cả' if done else 'dự kiến'} tháng {end.month:02d}/{end.year}", "value": value,
            "fmt": "money",
            "note": "đã đủ tháng" if done else f"theo tốc độ {elapsed} ngày đầu tháng (đến {end:%d/%m})"}


def extra_cards(f: Filters, month_spend: float, total_spend: float, risk_spend: float, lost: float,
                capped: int, active: int) -> list[dict]:
    share = risk_spend / total_spend if total_spend else None
    return [
        forecast_card(month_spend, f.end),
        {"label": "% Spend vào SKU hết / sắp hết hàng", "value": share, "fmt": "pct",
         "tone": "bad" if share and share >= 0.05 else None, "note": f"${risk_spend:,.0f} trong kỳ"},
        {"label": "DS mất do hết hàng (90 ngày)", "value": lost, "fmt": "money", "tone": "warn" if lost else None,
         "note": "ước tính, mọi kênh bán, chỉ các SKU có chi QC trong kỳ ở sàn này (khác thẻ ở tab Tổng hợp)"},
        {"label": "Campaign hay hết ngân sách", "value": capped, "fmt": "int", "tone": "warn" if capped else None,
         "note": f"hết NS ≥ {CAPPED_SHARE:.0%} số ngày, trên {active} campaign có chi tiêu"},
    ]


def same_filters(f: Filters, **kw) -> Filters:
    return Filters(**{**f.__dict__, **kw})


# ---------------------------------------------------------------- lãi và ACoS hòa vốn (giá vốn nhập tay)

def load_std_cogs() -> dict[tuple[int, str, str], float]:
    """Giá vốn chuẩn (sheet BOD, ref_std_cogs) quy USD theo tỷ giá mới nhất: {(product_id, thị trường, WH|FBA|CG): USD}."""
    rows = fetch_all("""
        SELECT s.product_id, s.market, s.basis, s.cogs * COALESCE(fx.rate_usd, CASE WHEN s.currency_code = 'USD' THEN 1 END)
               AS cogs_usd
        FROM ref_std_cogs s
        LEFT JOIN fx_daily fx ON fx.currency_code = s.currency_code
             AND fx.date_key = (SELECT MAX(date_key) FROM fx_daily x WHERE x.currency_code = s.currency_code
                                AND x.rate_usd IS NOT NULL)
        WHERE s.product_id IS NOT NULL""")
    return {(r["product_id"], r["market"], r["basis"]): float(r["cogs_usd"]) for r in rows if r["cogs_usd"] is not None}


def load_costs() -> tuple[dict, dict[str, dict]]:
    """({"manual": phí & giá vốn nhập tay theo product_id, "std": giá vốn chuẩn}, mặc định phí theo kênh).
    Giá vốn nhập tay (landed_cost) được ưu tiên; SKU chưa nhập thì dùng giá vốn chuẩn."""
    manual = {r["product_id"]: r for r in fetch_all("SELECT * FROM cfg_sku_cost")}
    try:
        std = load_std_cogs()
    except Exception:  # bảng chưa tạo (chưa chạy ETL sau khi nâng cấp)
        std = {}
    chans = {r["channel"]: r for r in fetch_all("SELECT channel, referral_pct, return_pct FROM cfg_channel_cost")}
    return {"manual": manual, "std": std}, chans


# hình thức giao hàng của phần đơn "kho ngoài": Amazon = FBA, Wayfair = CastleGate; phần còn lại giao từ kho (WH)
FULFIL_BASIS = {"amazon": "FBA", "wayfair": "CG"}


def std_cost(std: dict, product_id, channel: str, mix: list[tuple[str, float, float]]) -> float | None:
    """Giá vốn chuẩn bình quân mỗi đơn vị (USD). mix = [(thị trường, số đơn vị, số đơn vị FBA/CG)].
    Mỗi thị trường: WH × phần giao từ kho + FBA/CG × phần giao từ kho sàn; thiếu một trong hai thì dùng cái còn lại.
    Gộp các thị trường theo số đơn vị (không có đơn thì coi như 1 đơn vị, giao từ kho)."""
    alt = FULFIL_BASIS[channel]
    total = weight = 0.0
    for market, units, fbx in mix:
        wh, other = std.get((product_id, market, "WH")), std.get((product_id, market, alt))
        if wh is None and other is None:
            continue
        units = _nz(units)
        share = min(max(_nz(fbx) / units, 0.0), 1.0) if units > 0 else 0.0
        if wh is None:
            cost = other
        elif other is None:
            cost = wh
        else:
            cost = wh * (1 - share) + other * share
        w = units if units > 0 else 1.0
        total += cost * w
        weight += w
    return total / weight if weight else None


def unit_margin(price: float | None, cost: dict | None, chan: dict, channel: str) -> float | None:
    """Lãi mỗi đơn vị trước QC = giá bán × (1 − phí sàn − dự phòng hoàn trả) − giá vốn − phí giao hàng.
    Ô để trống ở SKU dùng mặc định của kênh. None nếu chưa có giá bán hoặc giá vốn."""
    if not price or not cost or cost.get("landed_cost") is None:
        return None
    referral = cost.get("amz_referral_pct") if channel == "amazon" else None
    referral = _nz(chan.get("referral_pct")) if referral is None else referral
    ret = _nz(chan.get("return_pct")) if cost.get("return_pct") is None else cost["return_pct"]
    fee = _nz(cost.get("amz_fee_unit" if channel == "amazon" else "wf_fee_unit"))
    return price * (1 - referral - ret) - _nz(cost["landed_cost"]) - fee


def row_cost(r: dict, costs: dict, channel: str) -> dict | None:
    """Giá vốn & phí của một dòng: nhập tay nếu có landed_cost, nếu không thì giá vốn chuẩn (giữ phí nhập tay nếu có).
    Thị trường lấy từ r["mix"] (list (nước, đơn vị, đơn vị FBA/CG)) hoặc r["country"], mặc định US. Ghi r["cost_source"]."""
    pid = r.get("product_id")
    manual = costs["manual"].get(pid)
    if manual and manual.get("landed_cost") is not None:
        r["cost_source"] = "manual"
        return manual
    mix = r.get("mix") or [(r.get("country") or "US", r.get("total_units"), r.get("fbx_units"))]
    cost = std_cost(costs["std"], pid, channel, mix)
    if cost is None:
        r["cost_source"] = None
        return None
    r["cost_source"] = "std"
    return {**(manual or {}), "landed_cost": cost}


def add_profit(rows: list[dict], costs: dict, chans: dict, channel: str) -> None:
    """rows có product_id, total_sales, total_units, spend (và country hoặc mix, fbx_units = đơn vị FBA/CastleGate để chọn
    giá vốn chuẩn). Thêm price (giá bán bình quân), landed_cost, cost_source, margin_unit, breakeven_acos (= biên trước
    QC / giá bán), profit_before (lãi trước QC trên mọi đơn), profit_after (trừ Spend)."""
    chan = chans.get(channel, {})
    for r in rows:
        units, ts = _nz(r.get("total_units")), _nz(r.get("total_sales"))
        price = ts / units if units else None
        cost = row_cost(r, costs, channel)
        r.pop("mix", None)
        r["landed_cost"] = cost["landed_cost"] if cost else None
        m = unit_margin(price, cost, chan, channel)
        r["price"] = price
        r["margin_unit"] = m
        r["breakeven_acos"] = m / price if m is not None and price else None
        r["profit_before"] = m * units if m is not None else None
        r["profit_after"] = r["profit_before"] - _nz(r.get("spend")) if m is not None else None


def profit_cards(rows: list[dict], total_spend: float, spend_label: str = "Spend") -> list[dict]:
    costed = [r for r in rows if r.get("profit_after") is not None]
    if not costed:
        return [{"label": "Lãi sau QC", "value": None, "fmt": "money", "tone": "warn",
                 "note": "chưa có giá vốn: nhập ở tab Công cụ › Giá vốn & phí hoặc chạy ETL để nạp giá vốn chuẩn"}]
    spend = sum(_nz(r.get("spend")) for r in costed)
    profit = sum(r["profit_after"] for r in costed)
    sales = sum(_nz(r.get("total_sales")) for r in costed)
    ad_sales = sum(_nz(r.get("sales")) for r in costed)
    be = sum(r["profit_before"] for r in costed) / sales if sales else None
    cover = spend / total_spend if total_spend else None
    return [
        {"label": "Lãi sau QC (SKU có giá vốn)", "value": profit, "fmt": "money", "tone": "bad" if profit < 0 else None,
         "note": f"{len(costed)} SKU, chiếm {cover:.0%} {spend_label}" if cover is not None else f"{len(costed)} SKU"},
        {"label": "ACoS hòa vốn bình quân", "value": be, "fmt": "pct",
         "tone": "bad" if be is not None and sales and spend / sales > be else None,
         "note": (f"ACoS thực tế {spend / ad_sales:.1%} · TACoS {spend / sales:.1%}" if ad_sales and sales else "")
                 + " (cùng nhóm SKU)"},
    ]


def profit_chart(rows: list[dict], goto: dict, n: int = 5) -> dict | None:
    costed = [r for r in rows if r.get("profit_after") is not None]
    gain = sorted([r for r in costed if r["profit_after"] > 0], key=lambda r: -r["profit_after"])[:n]
    loss = sorted([r for r in costed if r["profit_after"] < 0], key=lambda r: r["profit_after"])[:n]
    picked = gain + list(reversed(loss))
    if not picked:
        return None
    return chart("profit", "Sản phẩm lãi / lỗ nhiều nhất sau QC", "hbar", [r["label"] for r in picked],
                 [series("Lãi sau QC", "c1", [r["profit_after"] for r in picked],
                         colors=["c1" if r["profit_after"] > 0 else "c2" for r in picked])],
                 unit="money", signed=True,
                 subtitle="Lãi sau QC = (giá bán bình quân × (1 − phí sàn − hoàn trả) − giá vốn − phí giao hàng) × số đơn "
                          "vị bán ra − Spend. Giá vốn: nhập tay nếu có, nếu không là giá vốn chuẩn của BOD. Bấm một thanh để xem sản phẩm đó.",
                 goto=goto["goto"],
                 label_filters=[{"opts": goto["opts"], "cols": {goto["col"]: [r["filter_value"]]}} for r in picked])


# ---------------------------------------------------------------- mục tiêu tháng

TARGET_FIELDS = ("total_sales", "ad_sales", "spend", "tacos")


def load_targets(month: date, channel: str) -> dict[str, dict]:
    rows = fetch_all("""SELECT account_key, total_sales, ad_sales, spend, tacos FROM cfg_month_target
                        WHERE month = :m AND channel = :c""", {"m": month.replace(day=1), "c": channel})
    return {r["account_key"]: r for r in rows}


def combine_targets(rows: list[dict]) -> dict | None:
    """Cộng mục tiêu của nhiều tài khoản. TACoS gộp = Spend mục tiêu / Tổng DS mục tiêu (khi đủ hai số)."""
    if not rows:
        return None
    out = {}
    for k in ("total_sales", "ad_sales", "spend"):
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = sum(vals) if vals and len(vals) == len(rows) else None
    if len(rows) == 1:
        out["tacos"] = rows[0].get("tacos")
    else:
        out["tacos"] = out["spend"] / out["total_sales"] if out["spend"] and out["total_sales"] else None
    return out


def target_for(targets: dict[str, dict], keys: list[str] | None) -> dict | None:
    """keys = tài khoản đang lọc (None = cả kênh: dùng dòng cả kênh, nếu không có thì cộng các tài khoản)."""
    if keys:
        return combine_targets([targets[k] for k in keys]) if all(k in targets for k in keys) else None
    if "" in targets:
        return targets[""]
    return combine_targets([v for k, v in targets.items() if k])


def progress(target: dict, daily: list[dict], end: date) -> tuple[dict | None, list[dict]]:
    """Đồ thị lũy kế thực tế so với mục tiêu chia đều theo ngày, và thẻ % mục tiêu + dự báo cuối tháng.
    daily: [{date (iso), total_sales, sales, spend}] từ đầu tháng tới end."""
    first, elapsed, days = month_window(end)
    labels = [first.replace(day=d).isoformat() for d in range(1, days + 1)]
    by_date = {r["date"]: r for r in daily}
    actual = {"total_sales": 0.0, "ad_sales": 0.0, "spend": 0.0}
    cum = {k: [] for k in actual}
    for i, d in enumerate(labels):
        r = by_date.get(d, {})
        for k, src in (("total_sales", "total_sales"), ("ad_sales", "sales"), ("spend", "spend")):
            actual[k] += _nz(r.get(src))
            cum[k].append(round(actual[k], 2) if i < elapsed else None)
    names = {"total_sales": "Tổng DS", "ad_sales": "DS QC", "spend": "Spend"}
    ser, cards = [], []
    for k, color in (("total_sales", "c1"), ("ad_sales", "c3"), ("spend", "c2")):
        t = target.get(k)
        if not t:
            continue
        ser.append(series(f"{names[k]} thực tế", color, cum[k]))
        ser.append(series(f"{names[k]} mục tiêu", color, [round(t * (i + 1) / days, 2) for i in range(days)], dash=True))
        forecast = actual[k] / elapsed * days
        ratio = forecast / t
        tone = ("warn" if ratio > 1.05 else None) if k == "spend" else ("warn" if ratio < 0.95 else None)
        cards.append({"label": f"{names[k]} tháng {end.month:02d}: % mục tiêu", "value": actual[k] / t, "fmt": "pct",
                      "tone": tone, "note": f"mục tiêu ${t:,.0f} · dự báo cuối tháng ${forecast:,.0f} ({ratio:.0%})"})
    if target.get("tacos") and actual["total_sales"]:
        tacos = actual["spend"] / actual["total_sales"]
        cards.append({"label": f"TACoS tháng {end.month:02d}", "value": tacos, "fmt": "pct",
                      "tone": "warn" if tacos > target["tacos"] else None, "note": f"mục tiêu {target['tacos']:.1%}"})
    ch = None
    if ser:
        ch = chart("target_progress", f"Tiến độ tháng {end.month:02d}/{end.year} so với mục tiêu", "line", labels, ser,
                   unit="money", sum_mode="last", subtitle=f"Lũy kế từ đầu tháng tới {end:%d/%m}. Nét đứt = mục tiêu chia đều theo ngày.")
    return ch, cards


def scoped(f: Filters) -> bool:
    """Mục tiêu đặt theo kênh / tài khoản: lọc thêm nhóm SP, brand, loại QC, portfolio, campaign thì không so được."""
    return not (f.group_ids or f.brand_ids or f.ad_types or f.portfolio_ids or f.campaign_q)
