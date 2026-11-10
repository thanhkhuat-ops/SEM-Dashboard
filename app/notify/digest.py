"""Dựng bản tóm tắt hằng ngày cho một PIC từ các báo cáo sẵn có, lọc theo nhóm sản phẩm được phân công.

Một tin gồm phần Amazon và phần Wayfair (CHANNELS), mỗi kênh có kỳ báo cáo riêng: kết thúc NOTIFY_LAG_DAYS ngày trước
ngày dữ liệu mới nhất của kênh đó, vì đơn quy đổi về trễ (ngày gần nhất luôn trông như "0 đơn"). Các phần cảnh báo
dùng đúng bộ lọc trong bảng của web app (app/table_filters).
"""
import json
from datetime import timedelta

from app.config import settings
from app.db import fetch_all, fetch_one
from app.filters import Filters
from app.routers.api import run_report

TOP = 3  # số dòng mỗi cảnh báo; hai kênh chung một tin nên giữ ngắn cho vừa giới hạn ký tự của Google Chat

CHANNELS = [
    {"key": "amazon", "label": "Amazon", "fact": "fact_campaign_daily", "sales": "Ad Sales", "exact": "Exact",
     "reports": {"overview": "overview", "campaigns": "campaigns", "search_terms": "search_terms",
                 "harvest": "harvest", "budget": "budget"}},
    {"key": "wayfair", "label": "Wayfair", "fact": "fact_wf_campaign_daily", "sales": "DS QC (giá sỉ)",
     "exact": "Smart Exact",
     "reports": {"overview": "wf_overview", "campaigns": "wf_campaigns", "search_terms": "wf_search_terms",
                 "harvest": "wf_harvest", "budget": "wf_budget"}},
]


def pic_info(user_id: int) -> dict | None:
    pic = fetch_one("""SELECT p.user_id, p.name, p.email, p.code, p.active, c.acos_target
                       FROM dim_pic p LEFT JOIN cfg_pic_notify c ON c.user_id = p.user_id
                       WHERE p.user_id = :u""", {"u": user_id})
    if pic:
        pic["groups"] = fetch_all("""SELECT m.group_id, MAX(d.group_name) AS group_name FROM map_group_pic m
                                     LEFT JOIN dim_product d ON d.group_id = m.group_id
                                     WHERE m.user_id = :u GROUP BY m.group_id ORDER BY group_name""", {"u": user_id})
    return pic


def period(fact: str = "fact_campaign_daily") -> dict | None:
    latest = (fetch_one(f"SELECT MAX(report_date) AS d FROM {fact}") or {}).get("d")
    if not latest:
        return None
    end = latest - timedelta(days=settings.notify_lag_days)
    return {"latest": latest, "end": end, "start": end - timedelta(days=6), "start14": end - timedelta(days=13)}


def _money(v) -> str:
    v = float(v or 0)
    return f"${v:,.2f}" if abs(v) < 100 else f"${v:,.0f}"


def _pct(v) -> str:
    return "–" if v is None else f"{v * 100:.1f}%"


def _delta(cur, prev, kind: str) -> str:
    if cur is None or prev is None:
        return ""
    if kind == "pct":
        d = (cur - prev) * 100
        return "" if abs(d) < 0.05 else f" ({'▲' if d > 0 else '▼'} {abs(d):.1f} điểm)"
    if not prev:
        return ""
    d = (cur - prev) / abs(prev) * 100
    return "" if abs(d) < 0.05 else f" ({'▲' if d > 0 else '▼'} {abs(d):.1f}%)"


def _table(name: str, f: Filters, key: str, cond: list[dict] | None = None, opts: dict | None = None) -> dict:
    opts = dict(opts or {})
    if cond:
        opts["tf"] = json.dumps({key: {"cond": cond}})
    data = run_report(name, f, opts)
    return next(t for t in data["tables"] if t["key"] == key)


def _short(s, n: int = 60) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def _section(ch: dict, group_ids: list[int], target: float) -> dict:
    """Phần tin của một kênh: {"lines", "counts", "period"}. Nhóm SP của PIC không chạy QC ở kênh này trong
    14 ngày qua thì chỉ in một dòng ngắn."""
    rep, label = ch["reports"], ch["label"]
    p = period(ch["fact"])
    if not p:
        return {"lines": [f"*━━ {label.upper()} ━━*", "Chưa có dữ liệu quảng cáo."], "counts": {}, "period": None}
    iso = {k: v.isoformat() for k, v in p.items()}
    f7 = Filters(start=p["start"], end=p["end"], group_ids=group_ids)
    f14 = Filters(start=p["start14"], end=p["end"], group_ids=group_ids)
    head = f"*━━ {label.upper()} ━━* {p['start']:%d/%m}–{p['end']:%d/%m}/{p['end']:%Y}"

    kpis = run_report(rep["overview"], f7, {})["kpis"]
    cur, prev = kpis["current"], kpis["previous"]
    if not (cur.get("spend") or prev.get("spend")):
        return {"lines": [head, "Nhóm SP của bạn không chạy QC ở kênh này trong 14 ngày qua."], "counts": {}, "period": iso}

    lines = [head, "*Tổng quan* (so với 7 ngày trước)"]
    for key, name, kind in [("spend", "Spend", "money"), ("sales", ch["sales"], "money"), ("acos", "ACoS", "pct"),
                            ("orders", "Orders", "int"), ("cvr", "CVR", "pct"), ("tacos", "TACoS", "pct")]:
        v = cur.get(key)
        shown_v = _money(v) if kind == "money" else _pct(v) if kind == "pct" else f"{v or 0:,.0f}"
        lines.append(f"• {name}: {shown_v}{_delta(v, prev.get(key), kind)}")

    counts = {}
    zero = _table(rep["campaigns"], f7, "campaigns", [{"k": "spend", "op": "gte", "v": 20}, {"k": "orders", "op": "eq", "v": 0}])
    counts["zero_orders"] = len(zero["rows"])
    if zero["rows"]:
        lines += ["", f"*🚨 Campaign tiêu ≥ $20 không ra đơn* (7 ngày): {counts['zero_orders']} campaign, "
                      f"tổng {_money((zero.get('totals') or {}).get('spend'))}"]
        lines += [f"• {_short(r['campaign_name'])} — {_money(r['spend'])} · {r['clicks'] or 0:,.0f} click" for r in zero["rows"][:TOP]]

    high = _table(rep["campaigns"], f7, "campaigns", [{"k": "spend", "op": "gte", "v": 20}, {"k": "acos", "op": "gt", "v": target}])
    counts["high_acos"] = len(high["rows"])
    if high["rows"]:
        lines += ["", f"*🔥 Campaign ACoS > {_pct(target)}* (7 ngày, spend ≥ $20): {counts['high_acos']} campaign"]
        lines += [f"• {_short(r['campaign_name'])} — {_money(r['spend'])} · ACoS {_pct(r.get('acos'))}" for r in high["rows"][:TOP]]

    waste = _table(rep["search_terms"], f14, "search_terms",
                   [{"k": "spend", "op": "gte", "v": settings.notify_waste_spend}, {"k": "orders", "op": "eq", "v": 0}])
    counts["waste"] = len(waste["rows"])
    if waste["rows"]:
        lines += ["", f"*⚠️ Search term tiêu ≥ ${settings.notify_waste_spend:g} không ra đơn* (14 ngày, cân nhắc phủ định): "
                      f"{counts['waste']} term, tổng {_money((waste.get('totals') or {}).get('spend'))}"]
        lines += [f"• \"{_short(r['term'])}\" — {_money(r['spend'])} · {r['clicks'] or 0:,.0f} click" for r in waste["rows"][:TOP]]

    harvest = _table(rep["harvest"], f14, "harvest")
    counts["harvest"] = len(harvest["rows"])
    if harvest["rows"]:
        lines += ["", f"*✅ Nên thêm thành {ch['exact']}* (14 ngày): {counts['harvest']} search term"]
        lines += [f"• \"{_short(r['term'])}\" — {r['orders']:,.0f} đơn · ACoS {_pct(r.get('acos'))}" for r in harvest["rows"][:TOP]]

    capped = _table(rep["budget"], f7, "budget", [{"k": "days_capped", "op": "gte", "v": 3}, {"k": "acos", "op": "lte", "v": target}])
    counts["budget"] = len(capped["rows"])
    if capped["rows"]:
        lines += ["", f"*⏱ Hết ngân sách ≥ 3/7 ngày mà ACoS ≤ {_pct(target)}* (cân nhắc tăng ngân sách): {counts['budget']} campaign"]
        lines += [f"• {_short(r['campaign_name'])} — hết NS {r['days_capped']:.0f}/{r['days']:.0f} ngày · ACoS {_pct(r.get('acos'))}"
                  for r in capped["rows"][:TOP]]

    if not any(counts.values()):
        lines += ["", "Không có cảnh báo nào 👍"]
    return {"lines": lines, "counts": counts, "period": iso}


def build(user_id: int) -> dict:
    """Trả về {"text", "period", "counts", "has_alerts"} để xem trước hoặc gửi; period và counts tách theo kênh."""
    pic = pic_info(user_id)
    if not pic:
        raise LookupError(f"Không có PIC {user_id} trong dim_pic")
    name = pic["name"] or f"PIC {user_id}"
    if not pic["groups"]:
        return {"text": f"*📊 QC Amazon + Wayfair · {name}*\nKhông có báo cáo: chưa được phân công nhóm sản phẩm nào.",
                "period": {}, "counts": {}, "has_alerts": False}

    target = pic["acos_target"] or settings.notify_acos_target
    group_ids = [g["group_id"] for g in pic["groups"]]
    names = [g["group_name"] or f"Nhóm {g['group_id']}" for g in pic["groups"]]
    shown = ", ".join(names[:4]) + (f" (+{len(names) - 4})" if len(names) > 4 else "")
    lines = [f"*📊 QC Amazon + Wayfair · {name}*",
             f"7 ngày, bỏ {settings.notify_lag_days} ngày gần nhất vì đơn về trễ · Nhóm SP: {shown}"]

    periods, counts = {}, {}
    for ch in CHANNELS:
        sec = _section(ch, group_ids, target)
        lines += [""] + sec["lines"]
        periods[ch["key"]], counts[ch["key"]] = sec["period"], sec["counts"]

    if settings.notify_app_url:
        lines += ["", f"<{settings.notify_app_url}/|Mở báo cáo trên web app>"]
    has_alerts = any(v for c in counts.values() for v in c.values())
    return {"text": "\n".join(lines), "has_alerts": has_alerts, "counts": counts, "period": periods}


def recipients() -> list[dict]:
    """PIC đã bật nhận tin và có webhook."""
    return fetch_all("""SELECT c.user_id, c.webhook_url, p.name FROM cfg_pic_notify c
                        JOIN dim_pic p ON p.user_id = c.user_id
                        WHERE c.enabled = 1 AND c.webhook_url IS NOT NULL AND c.webhook_url <> '' AND p.active = 1""")
