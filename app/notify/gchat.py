"""Gửi tin nhắn văn bản vào một space Google Chat qua incoming webhook."""
import re

import httpx

# Chỉ chấp nhận webhook của Google Chat, để dữ liệu không bị gửi tới địa chỉ khác do nhập nhầm
WEBHOOK_RE = re.compile(r"^https://chat\.googleapis\.com/v1/spaces/([A-Za-z0-9_-]+)/messages\?\S+$")
MAX_TEXT = 4000  # Google Chat giới hạn khoảng 4.096 ký tự cho tin nhắn văn bản


class SendError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def space_of(url: str | None) -> str | None:
    """Mã space trong webhook (phần không bí mật, để hiển thị); None nếu URL không hợp lệ."""
    m = WEBHOOK_RE.match((url or "").strip())
    return m.group(1) if m else None


def truncate(text: str) -> str:
    if len(text) <= MAX_TEXT:
        return text
    return text[:MAX_TEXT - 40].rsplit("\n", 1)[0] + "\n… (đã rút gọn, xem đủ trên web app)"


def send(url: str, text: str) -> int:
    """Gửi tin, trả về HTTP status. Lỗi không kèm URL vì URL chứa key/token của webhook."""
    if not space_of(url):
        raise SendError("Webhook không hợp lệ: phải có dạng https://chat.googleapis.com/v1/spaces/…/messages?key=…&token=…")
    try:
        r = httpx.post(url.strip(), json={"text": truncate(text)}, timeout=20,
                       headers={"Content-Type": "application/json; charset=UTF-8"})
    except httpx.HTTPError as exc:
        raise SendError(f"Không kết nối được Google Chat: {type(exc).__name__}") from None
    if r.status_code >= 300:
        detail = r.text[:300].replace("\n", " ")
        raise SendError(f"Google Chat trả lỗi {r.status_code}: {detail}", r.status_code)
    return r.status_code
