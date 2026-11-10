"""Chỉ số quảng cáo: biểu thức SUM dùng chung, các chỉ số tính ra và định nghĩa cột hiển thị."""
from datetime import date, timedelta

# Cột cộng dồn được (dùng cả ở SQL lẫn tính dòng tổng)
ADDITIVE = ("impressions", "clicks", "spend", "orders", "units", "sales", "orders_same_sku", "sales_same_sku",
            "ntb_orders", "ntb_sales", "dpv", "retail_sales",
            # Shopify (app/reports_shop.py) và Tổng hợp (app/reports_all.py)
            "gross", "discount", "refunds", "refund_units", "net_sales", "prev_total")


def sum_cols(alias: str = "f") -> str:
    return ", ".join([
        f"SUM({alias}.impressions) AS impressions", f"SUM({alias}.clicks) AS clicks",
        f"SUM({alias}.cost_usd) AS spend", f"SUM({alias}.orders) AS orders", f"SUM({alias}.units) AS units",
        f"SUM({alias}.sales_usd) AS sales", f"SUM({alias}.orders_same_sku) AS orders_same_sku",
        f"SUM({alias}.sales_same_sku_usd) AS sales_same_sku", f"SUM({alias}.ntb_orders) AS ntb_orders",
        f"SUM({alias}.ntb_sales_usd) AS ntb_sales", f"SUM({alias}.dpv) AS dpv",
    ])


def wf_sum_cols(alias: str = "f") -> str:
    """Wayfair: sales = doanh số giá sỉ, retail_sales = doanh số giá bán lẻ (cùng cửa sổ view-through 14 ngày)."""
    return ", ".join([
        f"SUM({alias}.impressions) AS impressions", f"SUM({alias}.clicks) AS clicks",
        f"SUM({alias}.cost_usd) AS spend", f"SUM({alias}.orders) AS orders", f"SUM({alias}.units) AS units",
        f"SUM({alias}.sales_usd) AS sales", f"SUM({alias}.retail_sales_usd) AS retail_sales",
    ])


def grand_cols(sums: str) -> str:
    """Hàm cửa sổ tính trên mọi nhóm trước LIMIT: số dòng thật (_total_rows) và tổng thật (_t_<cột>), để dòng Tổng
    của bảng bị cắt vẫn đúng. `sums` là chuỗi "biểu thức AS tên, ..." như sum_cols(); với truy vấn có GROUP BY thì
    biểu thức là SUM(...) nên thành SUM(SUM(...)) OVER ()."""
    parts = ["COUNT(*) OVER () AS _total_rows"]
    for item in sums.split(", "):
        expr, name = item.rsplit(" AS ", 1)
        parts.append(f"SUM({expr}) OVER () AS _t_{name}")
    return ", ".join(parts)


def sum_names(sums: str) -> list[str]:
    return [item.rsplit(" AS ", 1)[1] for item in sums.split(", ")]


def order_expr(key: str, alias: str = "f") -> str | None:
    """Biểu thức ORDER BY an toàn cho một cột chỉ số (None nếu không hỗ trợ)."""
    sums = {"impressions": f"SUM({alias}.impressions)", "clicks": f"SUM({alias}.clicks)",
            "spend": f"SUM({alias}.cost_usd)", "orders": f"SUM({alias}.orders)", "units": f"SUM({alias}.units)",
            "sales": f"SUM({alias}.sales_usd)", "ntb_orders": f"SUM({alias}.ntb_orders)"}
    if key in sums:
        return sums[key]
    ratios = {
        "ctr": ("clicks", "impressions"), "cpc": ("spend", "clicks"), "cvr": ("orders", "clicks"),
        "acos": ("spend", "sales"), "roas": ("sales", "spend"), "cpa": ("spend", "orders"),
    }
    if key in ratios:
        num, den = ratios[key]
        return f"{sums[num]} / NULLIF({sums[den]}, 0)"
    return None


def _div(a, b):
    return (a / b) if (a is not None and b) else None


def with_ratios(row: dict) -> dict:
    for k in ADDITIVE:
        if k in row:
            row[k] = row[k] or 0
    row["ctr"] = _div(row.get("clicks"), row.get("impressions"))
    row["cpc"] = _div(row.get("spend"), row.get("clicks"))
    row["cvr"] = _div(row.get("orders"), row.get("clicks"))
    row["acos"] = _div(row.get("spend"), row.get("sales"))
    row["roas"] = _div(row.get("sales"), row.get("spend"))
    row["cpa"] = _div(row.get("spend"), row.get("orders"))
    row["aov"] = _div(row.get("sales"), row.get("orders"))
    row["ntb_share"] = _div(row.get("ntb_orders"), row.get("orders"))
    row["same_sku_share"] = _div(row.get("sales_same_sku"), row.get("sales"))
    if "retail_sales" in row:
        row["retail_roas"] = _div(row.get("retail_sales"), row.get("spend"))
    if "total_sales" in row:
        row["total_sales"] = row["total_sales"] or 0
        row["tacos"] = _div(row.get("spend"), row["total_sales"])
        row["ad_sales_share"] = _div(row.get("sales"), row["total_sales"])
        row["organic_sales"] = row["total_sales"] - (row.get("sales") or 0) if row["total_sales"] else None
    if "gross" in row:  # Shopify: sales = doanh số sau giảm giá
        row["discount_rate"] = _div(row.get("discount"), row["gross"])
        row["refund_rate"] = _div(row.get("refunds"), row.get("sales"))
        row["net_after_refund"] = (row.get("sales") or 0) - (row.get("refunds") or 0)
        row["avg_price"] = _div(row.get("sales"), row.get("units"))
        if "spend" in row:  # chi phí QC nhập tay theo tháng: chỉ có TACoS, không biết DS nào từ QC
            row["tacos"] = _div(row.get("spend"), row.get("sales"))
            row["acos"] = row["roas"] = row["cpa"] = None
    if "net_sales" in row:  # Tổng hợp: doanh số sau phí sàn
        row["fee_pct"] = _div((row.get("total_sales") or 0) - row["net_sales"], row.get("total_sales"))
        row["after_ads"] = row["net_sales"] - (row.get("spend") or 0)
    if "gross_profit" in row:  # Tổng hợp: lãi gộp = DS sau phí sàn − giá vốn chuẩn (ước tính cho SKU chưa có giá vốn)
        row["gross_margin"] = _div(row["gross_profit"], row.get("total_sales"))
        row["cogs_cover"] = _div(row.get("costed_sales"), row.get("total_sales"))
        row["profit_after_ads"] = (row["gross_profit"] or 0) - (row.get("spend") or 0)
        row["profit_margin"] = _div(row["profit_after_ads"], row.get("total_sales"))
    if "prev_total" in row:
        row["growth"] = _div((row.get("total_sales") or 0) - row["prev_total"], row["prev_total"])
    return row


def totals(rows: list[dict], extra_additive: tuple[str, ...] = ()) -> dict:
    out = {k: sum((r.get(k) or 0) for r in rows) for k in ADDITIVE + extra_additive if any(k in r for r in rows)}
    return with_ratios(out)


SPARK_MAX_DAYS = 90  # kỳ dài hơn thì đường nhỏ trong thẻ KPI gộp theo tuần (thứ Hai đầu tuần)


def kpi_series(trend: list[dict], start: date, end: date) -> dict:
    """Chuỗi số cho đường xu hướng nhỏ trong thẻ KPI, từ các dòng theo ngày ({"date": ISO, cột cộng dồn...}).

    Đủ mọi ngày trong kỳ (ngày không có dòng = 0 chi tiêu, tổng DS trống). Trả {"grain": "day"|"week", "labels": [...],
    "values": {chỉ số: [...]}}. Theo tuần: chỉ số tỷ lệ tính lại trên tổng tuần, số tiền/số lượng là trung bình mỗi ngày
    để tuần lẻ ở đầu/cuối kỳ không trông như bị tụt.
    """
    weekly = (end - start).days + 1 > SPARK_MAX_DAYS
    by_date = {r["date"]: r for r in trend}
    zero = {k for r in trend for k in ADDITIVE if k in r}
    buckets: dict[str, dict] = {}
    days: dict[str, int] = {}
    d = start
    while d <= end:
        key = (d - timedelta(days=d.weekday()) if weekly else d).isoformat()
        b = buckets.setdefault(key, dict.fromkeys(zero, 0.0))
        days[key] = days.get(key, 0) + 1
        r = by_date.get(d.isoformat()) or {}
        for k in ADDITIVE + ("total_sales",):
            if r.get(k) is not None:
                b[k] = b.get(k, 0) + float(r[k])
        d += timedelta(days=1)
    rows = [with_ratios(b) for b in buckets.values()]
    if weekly:
        for r, n in zip(rows, days.values()):
            for k in ADDITIVE + ("total_sales", "organic_sales"):
                if r.get(k) is not None:
                    r[k] /= n
    keys = {k for r in rows for k, v in r.items() if isinstance(v, (int, float))}
    return {"grain": "week" if weekly else "day", "labels": list(buckets),
            "values": {k: [r.get(k) for r in rows] for k in sorted(keys)}}


# (key, nhãn, định dạng). Định dạng: text | int | money | pct | num2 | date
def col(key: str, label: str, fmt: str = "text") -> dict:
    return {"key": key, "label": label, "fmt": fmt}


METRIC_COLUMNS = [
    col("impressions", "Impr", "int"), col("clicks", "Clicks", "int"), col("ctr", "CTR", "pct"),
    col("spend", "Spend", "money"), col("cpc", "CPC", "money"), col("orders", "Orders", "int"),
    col("units", "Units", "int"), col("cvr", "CVR", "pct"), col("sales", "Ad Sales", "money"),
    col("acos", "ACoS", "pct"), col("roas", "ROAS", "num2"), col("cpa", "CPA", "money"),
]
NTB_COLUMNS = [col("ntb_orders", "NTB Orders", "int"), col("ntb_share", "NTB %", "pct"), col("dpv", "DPV", "int")]
TACOS_COLUMNS = [col("total_sales", "Tổng DS", "money"), col("tacos", "TACoS", "pct"),
                 col("ad_sales_share", "% DS từ QC", "pct")]

# lãi theo giá vốn nhập tay, hoặc giá vốn chuẩn từ sheet BOD (app/insights.py: add_profit)
PROFIT_COLUMNS = [col("price", "Giá bán BQ", "money"), col("landed_cost", "Giá vốn/đv", "money"),
                  col("breakeven_acos", "ACoS hòa vốn", "pct"),
                  col("profit_after", "Lãi sau QC", "money")]

WF_METRIC_COLUMNS = [
    col("impressions", "Impr", "int"), col("clicks", "Clicks", "int"), col("ctr", "CTR", "pct"),
    col("spend", "Spend", "money"), col("cpc", "CPC", "money"), col("orders", "Orders", "int"),
    col("units", "Units", "int"), col("cvr", "CVR", "pct"), col("sales", "DS QC (giá sỉ)", "money"),
    col("acos", "ACoS", "pct"), col("roas", "ROAS", "num2"), col("cpa", "CPA", "money"),
    col("retail_sales", "DS QC (giá lẻ)", "money"), col("retail_roas", "ROAS giá lẻ", "num2"),
]
SHOP_COLUMNS = [
    col("orders", "Đơn", "int"), col("units", "Units", "int"), col("gross", "DS trước giảm giá", "money"),
    col("discount", "Giảm giá", "money"), col("discount_rate", "% giảm giá", "pct"), col("sales", "Doanh số", "money"),
    col("aov", "Giá trị đơn (AOV)", "money"), col("refunds", "Hoàn tiền", "money"), col("refund_rate", "% hoàn tiền", "pct"),
    col("net_after_refund", "DS sau hoàn tiền", "money"),
]
WF_TACOS_COLUMNS = [col("total_sales", "Tổng DS sỉ", "money"), col("tacos", "TACoS", "pct"),
                    col("ad_sales_share", "% DS từ QC", "pct")]
