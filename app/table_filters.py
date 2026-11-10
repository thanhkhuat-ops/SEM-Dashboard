"""Lọc dòng trong từng bảng của báo cáo: ngưỡng chỉ số (Spend ≥ 10, ACoS ≤ 30%…) và lọc theo cột chữ.

Tham số `tf` (JSON) theo key của bảng:
  {"targets": {"cond": [{"k": "spend", "op": "gte", "v": 10}, {"k": "orders", "op": "eq", "v": 0}],
               "cols": {"match_type": ["EXACT", "PHRASE"], "campaign_name": "hammock"}}}
- cond: các điều kiện AND; giá trị tỷ lệ (ACoS, CVR…) tính theo phân số (0.3 = 30%). Ô trống (vd ACoS khi chưa
  có doanh số) không thỏa điều kiện nào.
- cols: danh sách giá trị → giữ dòng có giá trị nằm trong danh sách ("" = ô trống); chuỗi → chứa chuỗi đó;
  null → không lọc cột đó (dùng để bỏ bộ lọc mặc định của bảng).
- Bảng có `default_filter` (vd Trạng thái = ENABLED) được lọc theo đó khi spec không nhắc tới cột tương ứng.
Lọc chạy sau khi báo cáo đã tính xong, rồi tính lại dòng Tổng theo các dòng còn lại, nên dùng chung được cho mọi
bảng và cho file HTML xuất ra.
"""
import json

from app.metrics import totals

OPS = {
    "gte": lambda x, v: x >= v - 1e-9, "lte": lambda x, v: x <= v + 1e-9,
    "gt": lambda x, v: x > v + 1e-9, "lt": lambda x, v: x < v - 1e-9,
    "eq": lambda x, v: abs(x - v) <= 1e-9, "ne": lambda x, v: abs(x - v) > 1e-9,
}
OP_LABELS = {"gte": "≥", "lte": "≤", "gt": ">", "lt": "<", "eq": "=", "ne": "≠"}
STATE_LABELS = {"ENABLED": "Đang chạy", "PAUSED": "Tạm dừng", "ARCHIVED": "Lưu trữ", "COMPLETED": "Đã kết thúc"}
FACET_MAX = 300  # cột chữ có nhiều giá trị hơn thì giao diện dùng ô "chứa…" thay cho danh sách chọn


def parse(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        spec = json.loads(raw)
    except ValueError:
        return {}
    return spec if isinstance(spec, dict) else {}


def _conditions(spec: dict, cols: dict) -> list[tuple[str, str, float]]:
    out = []
    for c in spec.get("cond") or []:
        if not isinstance(c, dict) or c.get("op") not in OPS or cols.get(c.get("k"), {}).get("fmt") in (None, "text"):
            continue
        try:
            out.append((c["k"], c["op"], float(c["v"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _column_filters(spec: dict, cols: dict) -> dict:
    out = {}
    for k, v in (spec.get("cols") or {}).items():
        if k not in cols:
            continue
        if isinstance(v, list) and v:
            out[k] = {"" if x is None else str(x) for x in v}
        elif isinstance(v, str) and v.strip():
            out[k] = v.strip().lower()
    return out


def _cell(value) -> str:
    return "" if value is None else str(value)


def _match(row: dict, conds, col_filters) -> bool:
    for k, op, v in conds:
        x = row.get(k)
        if x is None or isinstance(x, str) or not OPS[op](float(x), v):
            return False
    for k, want in col_filters.items():
        cell = _cell(row.get(k))
        if isinstance(want, set):
            if cell not in want:
                return False
        elif want not in cell.lower():
            return False
    return True


def facets(table: dict) -> dict:
    """Các giá trị khác nhau của mỗi cột chữ (trước khi lọc), để giao diện hiện danh sách chọn như Excel."""
    out = {}
    for c in table["columns"]:
        if c.get("fmt") != "text":
            continue
        values = {_cell(r.get(c["key"])) for r in table["rows"]}
        if len(values) <= FACET_MAX:
            out[c["key"]] = sorted(values, key=lambda s: (s == "", s.lower()))
    return out


def describe(table: dict) -> list[str]:
    """Mô tả bộ lọc đang áp cho bảng, dùng ở file HTML xuất ra."""
    cols = {c["key"]: c for c in table["columns"]}
    applied = table.get("filter") or {}
    parts = []
    for c in applied.get("cond", []):
        col = cols[c["k"]]
        v = f"{c['v'] * 100:g}%" if col["fmt"] == "pct" else (f"${c['v']:g}" if col["fmt"] == "money" else f"{c['v']:g}")
        parts.append(f"{col['label']} {OP_LABELS[c['op']]} {v}")
    for k, want in applied.get("cols", {}).items():
        label = cols[k]["label"]
        if isinstance(want, list):
            if k == "state":
                want = [STATE_LABELS.get(x, x) for x in want]
            shown = ", ".join(x or "(trống)" for x in want[:5]) + (f" … (+{len(want) - 5})" if len(want) > 5 else "")
            parts.append(f"{label}: {shown}")
        else:
            parts.append(f"{label} chứa “{want}”")
    return parts


def apply(result: dict, spec: dict, max_rows: int | None = None) -> None:
    for t in result.get("tables") or []:
        t["facets"] = facets(t)
        s = spec.get(t["key"])
        s = dict(s) if isinstance(s, dict) else {}
        default_cols = (t.pop("default_filter", None) or {}).get("cols") or {}
        if default_cols:
            t["default_cols"] = default_cols  # để giao diện hiện bộ lọc đang áp sẵn
            cols_spec = dict(s.get("cols") or {})
            for k, v in default_cols.items():
                cols_spec.setdefault(k, v)
            s["cols"] = cols_spec
        cols = {c["key"]: c for c in t["columns"]}
        conds, col_filters = _conditions(s, cols), _column_filters(s, cols)
        if not conds and not col_filters:
            if max_rows and len(t["rows"]) > max_rows:  # đã lấy thừa dòng để lọc nhưng không có bộ lọc nào: cắt lại
                t["total_rows"] = t.get("total_rows") or len(t["rows"])
                t["rows"] = t["rows"][:max_rows]
            continue
        before = len(t["rows"])
        rows = [r for r in t["rows"] if _match(r, conds, col_filters)]
        all_rows = rows  # dòng Tổng tính trên mọi dòng thỏa bộ lọc, không chỉ các dòng hiện ra
        if max_rows:
            rows = rows[:max_rows]
        t["rows"] = rows
        t["rows_before_filter"] = before
        t["filter"] = {"cond": [{"k": k, "op": op, "v": v} for k, op, v in conds],
                       "cols": {k: sorted(v) if isinstance(v, set) else v for k, v in col_filters.items()}}
        t["filter_text"] = describe(t)
        if t.get("total_rows", 0) > before:  # báo cáo đã bị cắt trước khi lọc: chỉ lọc được trong `before` dòng đầu
            t["filter_text"].append(f"chỉ lọc trong {before:,} / {t['total_rows']:,} dòng đầu")
        if len(all_rows) > len(rows):
            t["filter_text"].append(f"hiện {len(rows):,} / {len(all_rows):,} dòng thỏa bộ lọc")
        if "totals" in t:
            if rows:
                t["totals"] = totals(all_rows, tuple(t.get("additive") or ()))
            else:
                del t["totals"]
