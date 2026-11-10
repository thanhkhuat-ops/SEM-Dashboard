"""Cấu hình gửi tin Google Chat cho PIC: webhook, bật/tắt, ACoS mục tiêu, xem trước, gửi thử, lịch sử."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.db import execute, fetch_all, fetch_one
from app.notify import gchat
from app.notify.digest import build
from app.notify.run import deliver
from app.routers.api import jsonable

router = APIRouter(prefix="/api/notify")


class PicConfig(BaseModel):
    webhook_url: str | None = Field(None, max_length=1000)  # None = giữ nguyên, "" = xóa
    enabled: bool = False
    acos_target: float | None = Field(None, ge=0, le=5)


def _pic_or_404(user_id: int) -> dict:
    pic = fetch_one("SELECT user_id, name FROM dim_pic WHERE user_id = :u", {"u": user_id})
    if not pic:
        raise HTTPException(404, f"Không có PIC {user_id}")
    return pic


@router.get("/status")
def status() -> dict:
    return {"enabled": settings.notify_enabled, "lag_days": settings.notify_lag_days,
            "waste_spend": settings.notify_waste_spend, "acos_target": settings.notify_acos_target,
            "app_url": settings.notify_app_url}


@router.get("/pics")
def pics() -> list[dict]:
    rows = fetch_all("""
        SELECT p.user_id, p.name, p.code, p.email, p.active, c.webhook_url, COALESCE(c.enabled, 0) AS enabled, c.acos_target,
               (SELECT COUNT(*) FROM map_group_pic m WHERE m.user_id = p.user_id) AS n_groups,
               (SELECT GROUP_CONCAT(DISTINCT d.group_name ORDER BY d.group_name SEPARATOR ', ')
                  FROM map_group_pic m JOIN dim_product d ON d.group_id = m.group_id WHERE m.user_id = p.user_id) AS group_names,
               (SELECT CONCAT(l.status, ' · ', DATE_FORMAT(l.sent_at, '%d/%m %H:%i')) FROM notify_log l
                  WHERE l.user_id = p.user_id ORDER BY l.id DESC LIMIT 1) AS last_sent
        FROM dim_pic p LEFT JOIN cfg_pic_notify c ON c.user_id = p.user_id
        ORDER BY p.active DESC, p.name""")
    for r in rows:  # không trả URL webhook ra trình duyệt vì có key/token, chỉ trả mã space
        r["space"] = gchat.space_of(r.pop("webhook_url"))
    return jsonable(rows)


@router.put("/pics/{user_id}")
def save(user_id: int, cfg: PicConfig) -> dict:
    _pic_or_404(user_id)
    current = fetch_one("SELECT webhook_url FROM cfg_pic_notify WHERE user_id = :u", {"u": user_id}) or {}
    url = current.get("webhook_url")
    if cfg.webhook_url is not None:
        url = cfg.webhook_url.strip() or None
        if url and not gchat.space_of(url):
            raise HTTPException(422, "Webhook không hợp lệ: phải có dạng https://chat.googleapis.com/v1/spaces/…/messages?key=…&token=…")
    if cfg.enabled and not url:
        raise HTTPException(422, "Cần nhập webhook trước khi bật gửi tin")
    execute("""INSERT INTO cfg_pic_notify (user_id, webhook_url, enabled, acos_target, updated_at)
               VALUES (:u, :w, :e, :a, :t)
               ON DUPLICATE KEY UPDATE webhook_url = VALUES(webhook_url), enabled = VALUES(enabled),
                                       acos_target = VALUES(acos_target), updated_at = VALUES(updated_at)""",
            {"u": user_id, "w": url, "e": int(cfg.enabled), "a": cfg.acos_target, "t": datetime.now()})
    return {"ok": True, "space": gchat.space_of(url)}


@router.get("/preview/{user_id}")
def preview(user_id: int) -> dict:
    _pic_or_404(user_id)
    return jsonable(build(user_id))


@router.post("/send/{user_id}")
def send_test(user_id: int) -> dict:
    """Gửi ngay bản tóm tắt cho PIC (do người dùng bấm "Gửi thử"); không tính vào lịch gửi hằng ngày."""
    _pic_or_404(user_id)
    cfg = fetch_one("SELECT webhook_url FROM cfg_pic_notify WHERE user_id = :u", {"u": user_id}) or {}
    if not cfg.get("webhook_url"):
        raise HTTPException(422, "PIC này chưa có webhook")
    res = deliver(user_id, cfg["webhook_url"], kind="test")
    if res["status"] != "OK":
        raise HTTPException(502, res["error"])
    return res


@router.get("/log")
def log(limit: int = 50) -> list[dict]:
    return jsonable(fetch_all("""SELECT l.id, l.run_date, l.user_id, p.name, l.kind, l.status, l.http_status, l.error, l.sent_at
                                 FROM notify_log l LEFT JOIN dim_pic p ON p.user_id = l.user_id
                                 ORDER BY l.id DESC LIMIT :n""", {"n": max(1, min(limit, 500))}))
