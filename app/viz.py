"""Mô tả đồ thị gửi cho giao diện (app/static/app.js vẽ bằng Chart.js).

Một đồ thị: {"key", "title", "subtitle"?, "kind", "unit", "labels", "series": [{"name", "color", "values"}], ...}
- kind: "hbar_stacked" | "bar_stacked" | "bar" | "hbar" | "line" | "gantt" | "sku_line"
- color: vai trò màu, không phải mã hex - "c1".."c8" (categorical theo thứ tự cố định), "st:<trạng thái>" (màu trạng
  thái), "n1"/"n2" (xám). Giao diện đổi vai trò -> mã màu theo chế độ sáng / tối.
- Bấm vào đồ thị để lọc: mỗi nhãn có label_filters[i] và mỗi series có "filter", dạng {"opts": {...}, "cols": {...}}.
  opts = điều khiển của tab (nút, nước, trạng thái...), cols = lọc cột của bảng (giống bộ lọc cột trong bảng).
  "tables": các bảng của tab hiện tại nhận lọc cột; "goto": {"tab", "table"} = chuyển sang tab khác rồi lọc ở đó.
"""

STATUS_ORDER = ["OOS", "CRITICAL", "LOW", "OK", "OVER", "NO_SALES"]


def chart(key: str, title: str, kind: str, labels: list, series: list[dict], unit: str = "int", **extra) -> dict:
    """Bỏ series toàn 0 (màu của các series còn lại giữ nguyên vì màu gắn với series, không theo thứ tự hiển thị)."""
    kept = [s for s in series if any(v for v in s["values"])] if labels else series
    return {"key": key, "title": title, "kind": kind, "unit": unit, "labels": labels, "series": kept, **extra}


FULL_MAX = 300   # popup "Xem tất cả": tối đa số dòng gửi kèm (canvas quá cao thì trình duyệt không vẽ được)


def top_n(rows: list, n: int, build) -> dict | None:
    """Đồ thị top-N: build(rows) dựng đồ thị từ một danh sách dòng (đã sắp). Vẽ n dòng đầu; còn dòng bị ẩn thì gắn bản
    đầy đủ vào "full" ({title, labels, series, label_filters, count}) để giao diện mở popup Xem tất cả."""
    ch = build(rows[:n]) if rows else None
    if ch and len(rows) > n:
        full = build(rows[:FULL_MAX])
        ch["full"] = {"title": full["title"], "labels": full["labels"], "series": full["series"],
                      "label_filters": full.get("label_filters"), "count": len(rows)}
    return ch


def series(name: str, color: str, values: list, filt: dict | None = None, **extra) -> dict:
    out = {"name": name, "color": color, "values": values, **extra}
    if filt:
        out["filter"] = filt
    return out


def trend_charts(trend: list[dict], sales_label: str) -> list[dict]:
    """Tổng quan quảng cáo: tiền và tỷ lệ tách thành hai đồ thị (không dùng hai trục y)."""
    labels = [r["date"] for r in trend]

    def total(k):
        return sum(r.get(k) or 0 for r in trend)
    spend, sales, ts = total("spend"), total("sales"), total("total_sales")
    return [
        chart("trend_money", f"Spend và {sales_label} theo ngày", "line", labels,
              [series("Spend", "c1", [r.get("spend") for r in trend]),
               series(sales_label, "c2", [r.get("sales") for r in trend])], unit="money"),
        chart("trend_ratio", "ACoS và TACoS theo ngày", "line", labels,
              [series("ACoS", "c1", [r.get("acos") for r in trend], total=spend / sales if sales else None),
               series("TACoS", "c2", [r.get("tacos") for r in trend], total=spend / ts if ts else None)], unit="pct"),
    ]
