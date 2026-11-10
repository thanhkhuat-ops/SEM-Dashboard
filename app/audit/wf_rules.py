"""Bộ quy tắc audit Wayfair (WSP): tham số, mặc định, cách gộp mặc định / tài khoản.

Lưu chung bảng cfg_audit_param với Amazon nhưng khoá phạm vi có tiền tố "wf:": "wf:*" = mặc định chung của Wayfair,
"wf:<account_id>" = ghi đè của một tài khoản. ACoS tính trên doanh số giá sỉ (attr_wholesale_cost) như báo cáo Wayfair.
ACoS mục tiêu riêng theo nhóm SP lưu ở cfg_audit_acos với scope_type 'WF_GROUP' (tách khỏi mục tiêu nhóm của Amazon).
"""
from app.audit.rules import Param, merge, validate as _validate

PREFIX = "wf:"
GLOBAL = "wf:*"
ACOS_SCOPE = "WF_GROUP"

RULES = [
    ("general", "Chung", "Áp cho mọi quy tắc bên dưới. Campaign AI Bidding (TROAS) không bị chỉnh bid."),
    ("harvest", "1 · Harvest", "Search term ra đơn tốt từ keyword Smart Phrase, chưa có keyword Smart Exact → thêm Smart Exact vào campaign Exact cùng part number, thêm negative exact ở campaign gốc."),
    ("negative", "2 · Negative", "Search term 0 đơn đã tiêu quá nhiều → negative exact ở campaign đó."),
    ("bid_down", "3 · Giảm bid keyword", "ACoS cao hơn mục tiêu → bid mới = bid × (mục tiêu ÷ ACoS), không giảm quá biên độ."),
    ("bid_up", "4 · Tăng bid keyword", "ACoS thấp hơn nhiều so với mục tiêu → tăng bid, không vượt trần."),
    ("pause", "5 · Hạ về sàn", "Keyword 0 đơn đã tiêu vượt ngưỡng → hạ bid về sàn (Wayfair không có pause keyword; luôn cần người duyệt)."),
    ("no_imp", "6 · Không có impression", "Keyword trong campaign đang chạy mà không có impression → tăng bid; sau vài lần vẫn không có thì đề xuất gỡ (REMOVE, cần người duyệt)."),
    ("listing", "7 · Listing (Product Targeting)", "Bid mặc định của listing trong campaign Product Targeting theo ACoS; listing 0 đơn tiêu quá nhiều → đề xuất tắt."),
    ("budget", "8 · Daily cap", "Campaign thường xuyên tiêu chạm daily cap mà ACoS đạt mục tiêu → tăng daily cap."),
    ("conflict", "9 · Xung đột negative", "Negative đang chặn search term đã ra đơn → chỉ cảnh báo, không tự xoá."),
]

PARAMS = [
    Param("acos_target", "general", "ACoS mục tiêu mặc định (giá sỉ)", 0.20, "pct", 0.01, 2,
          "Dùng khi nhóm SP không có mục tiêu riêng. ACoS = spend ÷ doanh số giá sỉ."),
    Param("lookback_days", "general", "Cửa sổ dữ liệu", 60, "days", 7, 180, "Số ngày số liệu dùng cho các quy tắc."),
    Param("min_clicks", "general", "Click tối thiểu để chỉnh bid", 20, "num", 1, 1000,
          "Keyword / listing ít click hơn thì không chỉnh theo ACoS."),
    Param("cooldown_days", "general", "Thời gian chờ sau khi sửa", 7, "days", 0, 60,
          "Không đề xuất lại cho keyword / listing / campaign đã sửa trong số ngày này."),
    Param("bid_floor", "general", "Bid sàn", 0.10, "money", 0.02, 100,
          "Theo tiền của campaign (wayfair.ca = CAD). Keyword đang để bid dưới sàn coi như cố ý, không tự tăng."),
    Param("bid_ceiling_cpc_mult", "general", "Bid trần (× CPC trung bình)", 2.0, "num", 1, 10,
          "Bid không vượt quá bội số này của CPC trung bình của keyword / listing (hoặc campaign nếu chưa có click)."),

    Param("harvest_enabled", "harvest", "Bật", 1, "bool"),
    Param("harvest_min_orders", "harvest", "Đơn tối thiểu", 2, "num", 1, 100),
    Param("harvest_acos_ratio", "harvest", "ACoS tối đa (× mục tiêu)", 1.0, "num", 0.1, 3),
    Param("harvest_add_negative", "harvest", "Thêm negative exact ở campaign gốc", 1, "bool"),

    Param("negative_enabled", "negative", "Bật", 1, "bool"),
    Param("negative_cpa_mult", "negative", "Chi tối thiểu (× CPA mục tiêu)", 0.5, "num", 0.1, 10,
          "CPA mục tiêu = ACoS mục tiêu × giá trị đơn giá sỉ trung bình của campaign."),

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
    Param("no_imp_max_rounds", "no_imp", "Số lần tăng trước khi đề xuất gỡ", 2, "num", 1, 10),

    Param("listing_enabled", "listing", "Bật", 1, "bool"),
    Param("listing_bid_down_export", "listing", "Cho xuất giảm bid listing", 0, "bool",
          help="Ghi chú trong file bulk của Wayfair nói bid listing mới phải ≥ bid hiện tại. Tắt: đề xuất giảm chỉ để xem, "
               "hạ tay trên WSP. Bật sau khi đã thử import giảm bid thành công."),
    Param("listing_off_cpa_mult", "listing", "Tắt listing khi 0 đơn chi ≥ (× CPA mục tiêu)", 1.5, "num", 0.1, 20),

    Param("budget_enabled", "budget", "Bật", 1, "bool"),
    Param("budget_days", "budget", "Xét trong số ngày gần nhất", 14, "days", 7, 60),
    Param("budget_capped_days", "budget", "Số ngày chạm cap tối thiểu", 5, "num", 1, 60),
    Param("budget_util", "budget", "Coi là chạm cap khi tiêu ≥", 0.90, "pct", 0.5, 1),
    Param("budget_acos_ratio", "budget", "ACoS tối đa (× mục tiêu)", 1.0, "num", 0.1, 3),
    Param("budget_raise", "budget", "Tăng daily cap mỗi lần", 0.20, "pct", 0.01, 2),

    Param("conflict_enabled", "conflict", "Bật", 1, "bool"),
    Param("conflict_days", "conflict", "Xét đơn trong số ngày gần nhất", 60, "days", 7, 365),
]
BY_KEY = {p.key: p for p in PARAMS}
INTEGER_KEYS = {"min_clicks", "harvest_min_orders", "no_imp_max_rounds", "budget_capped_days"}


def validate(key: str, value: float) -> float:
    return _validate(key, value, PARAMS, INTEGER_KEYS)


def account_id(profile_id: str) -> str:
    """'wf:184614' -> '184614'."""
    return profile_id[len(PREFIX):]


def load(profile_id: str) -> dict:
    """Cấu hình hiệu lực của một tài khoản Wayfair (profile_id dạng 'wf:<account_id>')."""
    from app.db import fetch_all

    rows = fetch_all("SELECT scope_key, param, value FROM cfg_audit_param WHERE scope_key IN (:g, :p)",
                     {"g": GLOBAL, "p": profile_id})
    g = {r["param"]: r["value"] for r in rows if r["scope_key"] == GLOBAL}
    a = {r["param"]: r["value"] for r in rows if r["scope_key"] == profile_id}
    acos = fetch_all("SELECT scope_id, acos_target FROM cfg_audit_acos WHERE scope_type = :t", {"t": ACOS_SCOPE})
    return {"params": {k: v["value"] for k, v in merge(g, a, PARAMS).items()},
            "group_targets": {r["scope_id"]: r["acos_target"] for r in acos}}
