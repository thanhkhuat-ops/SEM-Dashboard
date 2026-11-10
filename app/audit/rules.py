"""Bộ quy tắc audit từ khóa: danh sách tham số, mặc định, và cách gộp mặc định / tài khoản.

Giá trị hiệu lực của một tham số cho một tài khoản = ghi đè của tài khoản (nếu có) → mặc định chung trên app
(scope '*', nếu có) → mặc định trong code. Tỉ lệ lưu dạng 0.2 (giao diện hiện 20%). Tiền (bid_floor) theo tiền
tệ của từng tài khoản, nên tài khoản không dùng CAD/USD nên đặt sàn riêng.
"""
from dataclasses import dataclass

GLOBAL = "*"


@dataclass(frozen=True)
class Param:
    key: str
    rule: str
    label: str
    default: float
    unit: str  # pct | num | money | days | bool
    min: float = 0
    max: float | None = None
    help: str = ""


# (mã nhóm, tên nhóm, mô tả) theo thứ tự hiển thị
RULES = [
    ("general", "Chung", "Áp cho mọi quy tắc bên dưới."),
    ("harvest", "1 · Harvest", "Search term ra đơn tốt nhưng chưa có keyword Exact → tạo keyword Exact, thêm negative exact ở ad group gốc."),
    ("negative", "2 · Negative", "Search term 0 đơn đã tiêu quá nhiều → negative exact ở ad group đó."),
    ("bid_down", "3 · Giảm bid", "ACoS cao hơn mục tiêu → bid mới = bid × (mục tiêu ÷ ACoS), không giảm quá biên độ."),
    ("bid_up", "4 · Tăng bid", "ACoS thấp hơn nhiều so với mục tiêu → tăng bid, không vượt trần."),
    ("pause", "5 · Pause", "Keyword 0 đơn đã tiêu vượt ngưỡng → đề xuất pause (luôn cần người duyệt)."),
    ("no_imp", "6 · Không có impression", "Keyword đang bật mà không có impression → tăng bid; sau vài lần vẫn không có thì đề xuất pause."),
    ("conflict", "7 · Xung đột negative", "Negative đang chặn search term đã ra đơn → chỉ cảnh báo, không tự xoá."),
]

PARAMS = [
    Param("acos_target", "general", "ACoS mục tiêu mặc định", 0.30, "pct", 0.01, 2,
          "Dùng khi portfolio / nhóm SP không có mục tiêu riêng."),
    Param("lookback_days", "general", "Cửa sổ dữ liệu", 60, "days", 7, 180, "Số ngày số liệu dùng cho quy tắc 1–5 và 7."),
    Param("min_clicks", "general", "Click tối thiểu để chỉnh bid", 20, "num", 1, 1000,
          "Keyword ít click hơn thì không chỉnh theo ACoS (quy tắc 3, 4, 5)."),
    Param("cooldown_days", "general", "Thời gian chờ sau khi sửa", 7, "days", 0, 60,
          "Không đề xuất lại cho keyword / campaign đã sửa trong số ngày này."),
    Param("bid_floor", "general", "Bid sàn", 0.20, "money", 0.02, 100, "Theo tiền tệ của tài khoản."),
    Param("bid_ceiling_cpc_mult", "general", "Bid trần (× CPC trung bình)", 2.0, "num", 1, 10,
          "Bid không vượt quá bội số này của CPC trung bình của keyword (hoặc ad group nếu keyword chưa có click)."),

    Param("harvest_enabled", "harvest", "Bật", 1, "bool"),
    Param("harvest_min_orders", "harvest", "Đơn tối thiểu", 2, "num", 1, 100),
    Param("harvest_acos_ratio", "harvest", "ACoS tối đa (× mục tiêu)", 1.0, "num", 0.1, 3,
          "1 = ACoS của search term không vượt mục tiêu."),
    Param("harvest_add_negative", "harvest", "Thêm negative exact ở ad group gốc", 1, "bool"),

    Param("negative_enabled", "negative", "Bật", 1, "bool"),
    Param("negative_cpa_mult", "negative", "Chi tối thiểu (× CPA mục tiêu)", 1.0, "num", 0.1, 10,
          "CPA mục tiêu = ACoS mục tiêu × giá trị đơn trung bình của sản phẩm."),

    Param("bid_down_enabled", "bid_down", "Bật", 1, "bool"),
    Param("bid_max_down", "bid_down", "Giảm tối đa mỗi lần", 0.20, "pct", 0.01, 0.9),

    Param("bid_up_enabled", "bid_up", "Bật", 1, "bool"),
    Param("bid_up_acos_ratio", "bid_up", "Tăng khi ACoS dưới (× mục tiêu)", 0.7, "num", 0.1, 1),
    Param("bid_max_up", "bid_up", "Tăng tối đa mỗi lần", 0.20, "pct", 0.01, 2),

    Param("pause_enabled", "pause", "Bật", 1, "bool"),
    Param("pause_cpa_mult", "pause", "Chi tối thiểu khi 0 đơn (× CPA mục tiêu)", 1.5, "num", 0.1, 20),

    Param("no_imp_enabled", "no_imp", "Bật", 1, "bool"),
    Param("no_imp_days", "no_imp", "Số ngày không có impression", 30, "days", 7, 180),
    Param("no_imp_raise", "no_imp", "Tăng bid mỗi lần", 0.20, "pct", 0.01, 2),
    Param("no_imp_max_rounds", "no_imp", "Số lần tăng trước khi đề xuất pause", 2, "num", 1, 10),

    Param("conflict_enabled", "conflict", "Bật", 1, "bool"),
    Param("conflict_days", "conflict", "Xét đơn trong số ngày gần nhất", 60, "days", 7, 365),
]
BY_KEY = {p.key: p for p in PARAMS}
INTEGER_KEYS = {"min_clicks", "harvest_min_orders", "no_imp_max_rounds"}


def validate(key: str, value: float, params: list[Param] | None = None, integer_keys: set | None = None) -> float:
    """Kiểm tra một giá trị nhập; trả về giá trị đã chuẩn hoá hoặc raise ValueError (thông báo tiếng Việt).
    params / integer_keys: bộ tham số của kênh khác (Wayfair: app/audit/wf_rules.py), mặc định là Amazon."""
    p = {x.key: x for x in params}.get(key) if params else BY_KEY.get(key)
    if p is None:
        raise ValueError(f"Không có tham số '{key}'")
    v = float(value)
    if p.unit == "bool":
        if v not in (0, 1):
            raise ValueError(f"{p.label}: chỉ nhận 0 hoặc 1")
        return v
    if (p.unit == "days" or key in (INTEGER_KEYS if integer_keys is None else integer_keys)) and v != int(v):
        raise ValueError(f"{p.label}: phải là số nguyên")
    if v < p.min or (p.max is not None and v > p.max):
        raise ValueError(f"{p.label}: phải trong khoảng {p.min:g}–{p.max:g}")
    return v


def merge(global_vals: dict[str, float], account_vals: dict[str, float], params: list[Param] | None = None) -> dict[str, dict]:
    """Gộp mặc định code → mặc định chung → tài khoản. Trả về {param: {value, source}}."""
    out = {}
    for p in params or PARAMS:
        if p.key in account_vals:
            out[p.key] = {"value": account_vals[p.key], "source": "account"}
        elif p.key in global_vals:
            out[p.key] = {"value": global_vals[p.key], "source": "global"}
        else:
            out[p.key] = {"value": p.default, "source": "default"}
    return out


def acos_target(account_target: float, group_targets: dict, portfolio_targets: dict,
                portfolio_id: str | None = None, group_id: int | str | None = None) -> float:
    """ACoS mục tiêu cho một campaign / keyword: portfolio > nhóm SP > tài khoản."""
    if portfolio_id and str(portfolio_id) in portfolio_targets:
        return portfolio_targets[str(portfolio_id)]
    if group_id is not None and str(group_id) in group_targets:
        return group_targets[str(group_id)]
    return account_target


def load(profile_id: str | None) -> dict:
    """Đọc cấu hình hiệu lực của một tài khoản từ mart (dùng cho bộ máy audit)."""
    from app.db import fetch_all

    rows = fetch_all("SELECT scope_key, param, value FROM cfg_audit_param WHERE scope_key IN ('*', :p)",
                     {"p": profile_id or GLOBAL})
    g = {r["param"]: r["value"] for r in rows if r["scope_key"] == GLOBAL}
    a = {r["param"]: r["value"] for r in rows if profile_id and r["scope_key"] == profile_id}
    params = {k: v["value"] for k, v in merge(g, a).items()}
    acos = fetch_all("SELECT scope_type, scope_id, acos_target FROM cfg_audit_acos")
    return {
        "params": params,
        "group_targets": {r["scope_id"]: r["acos_target"] for r in acos if r["scope_type"] == "GROUP"},
        "portfolio_targets": {r["scope_id"]: r["acos_target"] for r in acos if r["scope_type"] == "PORTFOLIO"},
    }
