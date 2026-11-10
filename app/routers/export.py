"""Xuất báo cáo ra file HTML độc lập (mở được không cần server)."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.config import ROOT_DIR
from app.filters import Filters, get_filters
from app.reports_inv import sku_series
from app.routers.api import report_opts, run_report

router = APIRouter()
env = Environment(loader=FileSystemLoader(ROOT_DIR / "app" / "templates"), autoescape=select_autoescape(["html"]))


def fmt(value, kind: str) -> str:
    if value is None or value == "":
        return "–"
    try:
        if kind == "int":
            return f"{float(value):,.0f}"
        if kind == "money":
            return f"${float(value):,.2f}"
        if kind == "pct":
            return f"{float(value) * 100:.1f}%"
        if kind == "num2":
            return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        pass
    return str(value)


env.filters["fmt"] = fmt


def spark(series: dict | None, key: str) -> Markup:
    """Đường xu hướng nhỏ tĩnh cho thẻ KPI (bản tương tác: app.js sparkline). Spend, CPC màu cam, còn lại xanh."""
    vals = ((series or {}).get("values") or {}).get(key) or []
    known = [v for v in vals if v is not None]
    if len(known) < 2:
        return Markup("")
    w, h, pad, n = 200, 40, 3, len(vals)
    lo, hi = min(known), max(known)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    line, seg = "", []
    for i, v in enumerate(vals + [None]):
        if v is None:
            if seg:
                line += "M" + "L".join(seg)
            seg = []
        else:
            seg.append(f"{i / (n - 1) * w:.1f},{pad + (1 - (v - lo) / (hi - lo)) * (h - 2 * pad):.1f}")
    cls = "spark cost" if key in ("spend", "cpc") else "spark"
    return Markup(f'<svg class="{cls}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
                  f'<path d="{line}" fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>')


env.filters["spark"] = spark

# bộ vẽ đồ thị data.viz cho file xuất (nhúng thẳng vào HTML để file mở được ở máy khác, chỉ Chart.js tải từ CDN)
CHARTS_JS = ROOT_DIR / "app" / "static" / "export_charts.js"


def script_json(value) -> Markup:
    """JSON an toàn để đặt trong thẻ <script> (không để chuỗi '</' đóng thẻ sớm)."""
    return Markup(json.dumps(value, default=str, ensure_ascii=False).replace("</", "<\\/"))


def embed_sku_lines(viz: list[dict], qty_unit: str) -> None:
    """Đường tồn SKU trên app gọi API khi vẽ; file xuất không có server nên nhúng sẵn số liệu của SKU mặc định."""
    for spec in viz:
        pick = spec.get("initial") if spec.get("kind") == "sku_line" else None
        if pick:
            spec["data"] = sku_series(pick["node_id"], int(pick["product_id"]), qty_unit) or None


def hide_columns(data: dict, raw: str | None) -> None:
    """Bỏ các cột người dùng đã ẩn trên giao diện. hc = JSON {key bảng: [key cột bị ẩn]}; luôn giữ ít nhất một cột."""
    try:
        spec = json.loads(raw) if raw else {}
    except ValueError:
        return
    if not isinstance(spec, dict):
        return
    for t in data.get("tables") or []:
        hidden = spec.get(t["key"])
        if isinstance(hidden, list) and hidden:
            kept = [c for c in t["columns"] if c["key"] not in hidden]
            if kept:
                t["columns"] = kept


@router.get("/export/{name}", response_class=HTMLResponse)
def export(name: str, request: Request, f: Filters = Depends(get_filters)) -> HTMLResponse:
    opts = report_opts(request)
    data = run_report(name, f, opts)
    hide_columns(data, request.query_params.get("hc"))
    viz = data.get("viz") or []
    embed_sku_lines(viz, opts.get("qty_unit", "unit"))
    html = env.get_template("export.html").render(
        data=data, generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        trend_json=json.dumps((data.get("charts") or {}).get("trend") or []),
        viz_json=script_json(viz) if viz else None,
        charts_js=Markup(CHARTS_JS.read_text(encoding="utf-8")) if viz else None,
    )
    filename = f"ads_{name}_{f.start:%Y%m%d}_{f.end:%Y%m%d}.html"
    return HTMLResponse(html, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
