"""Gửi bản tóm tắt hằng ngày cho các PIC đã bật nhận tin.

  python -m app.notify.run --dry-run            # in nội dung sẽ gửi cho mọi PIC, không gửi
  python -m app.notify.run --dry-run --user 231 # xem trước cho một PIC
  python -m app.notify.run                      # gửi (chỉ khi NOTIFY_ENABLED=true); mỗi PIC tối đa 1 lần/ngày
  python -m app.notify.run --force              # gửi lại kể cả khi hôm nay đã gửi
"""
import argparse
import sys
from datetime import date, datetime

from app.config import settings
from app.db import execute, fetch_all, fetch_one
from app.notify import gchat
from app.notify.digest import build, recipients


def deliver(user_id: int, webhook_url: str, kind: str = "digest", force: bool = False) -> dict:
    """Dựng và gửi tin cho một PIC, ghi notify_log. kind='digest' (lịch hằng ngày) bị chặn gửi lặp trong ngày."""
    run_date = date.today()
    if kind == "digest" and not force and fetch_one(
            "SELECT 1 AS x FROM notify_log WHERE run_date = :d AND user_id = :u AND kind = 'digest' AND status = 'OK'",
            {"d": run_date, "u": user_id}):
        return {"user_id": user_id, "status": "SKIPPED", "error": "Hôm nay đã gửi"}
    msg = build(user_id)
    status, http_status, error = "OK", None, None
    try:
        http_status = gchat.send(webhook_url, msg["text"])
    except gchat.SendError as exc:
        status, http_status, error = "FAILED", exc.status, str(exc)
    execute("""INSERT INTO notify_log (run_date, user_id, kind, status, http_status, message, error, sent_at)
               VALUES (:d, :u, :k, :s, :h, :m, :e, :t)""",
            {"d": run_date, "u": user_id, "k": kind, "s": status, "h": http_status, "m": msg["text"],
             "e": error, "t": datetime.now()})
    return {"user_id": user_id, "status": status, "error": error}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Gửi tóm tắt QC cho PIC qua Google Chat")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in nội dung, không gửi")
    ap.add_argument("--user", type=int, help="chỉ một PIC (user_id)")
    ap.add_argument("--force", action="store_true", help="gửi lại kể cả khi hôm nay đã gửi")
    args = ap.parse_args(argv)

    if args.dry_run:
        users = [args.user] if args.user else [r["user_id"] for r in fetch_all(
            "SELECT DISTINCT p.user_id FROM dim_pic p JOIN map_group_pic m ON m.user_id = p.user_id "
            "WHERE p.active = 1 ORDER BY p.user_id")]
        for u in users:
            print(f"===== user_id={u} =====\n{build(u)['text']}\n", flush=True)
        return 0

    if not settings.notify_enabled:
        print("[SKIP] NOTIFY_ENABLED=false trong .env: không gửi tin.")
        return 0
    targets = [r for r in recipients() if not args.user or r["user_id"] == args.user]
    failed = 0
    for r in targets:
        res = deliver(r["user_id"], r["webhook_url"], force=args.force)
        failed += res["status"] == "FAILED"
        print(f"[{res['status']}] {r['name']} ({r['user_id']}) {res['error'] or ''}".rstrip(), flush=True)
    print(f"Đã xử lý {len(targets)} PIC, lỗi {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
