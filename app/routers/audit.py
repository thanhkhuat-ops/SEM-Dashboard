"""Audit từ khóa: quy tắc (mặc định chung + ghi đè theo tài khoản, ACoS mục tiêu theo portfolio / nhóm SP),
upload file bulk, chạy audit và xuất file bulk để upload lại Amazon / Wayfair.

Wayfair dùng chung các endpoint: tài khoản / phạm vi quy tắc có tiền tố "wf:" ("wf:*" = mặc định chung Wayfair,
"wf:<account_id>"), các endpoint liệt kê nhận channel=wayfair, file upload tự nhận kênh theo tên sheet."""
import json
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.audit import bulk, engine, rules, wf_bulk, wf_engine, wf_rules
from app.db import execute, fetch_all, fetch_one, get_engine
from app.routers.api import jsonable

router = APIRouter(prefix="/api/audit")
GLOBALS = (rules.GLOBAL, wf_rules.GLOBAL)


def _reg(scope: str | None):
    """Bộ quy tắc theo phạm vi / profile: Wayfair khi có tiền tố 'wf:'."""
    return wf_rules if (scope or "").startswith(wf_rules.PREFIX) else rules


class RuleValues(BaseModel):
    scope: str = Field(..., min_length=1, max_length=25)  # '*' hoặc profile_id
    values: dict[str, float | None]  # None = bỏ ghi đè (về giá trị cấp trên)


class CopyRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=25)
    targets: list[str] = Field(..., min_length=1, max_length=100)


class AcosItem(BaseModel):
    scope_type: str
    scope_id: str = Field(..., min_length=1, max_length=25)
    acos_target: float | None = Field(None, gt=0, le=2)  # None = xoá mục tiêu riêng


def _account_or_404(profile_id: str) -> dict:
    if profile_id.startswith(wf_rules.PREFIX):
        acc = fetch_one("""SELECT CONCAT(:x, account_id) AS profile_id, COALESCE(short_name, account_name) AS account_label,
                                  currency_code FROM dim_wf_account WHERE account_id = :p""",
                        {"x": wf_rules.PREFIX, "p": wf_rules.account_id(profile_id)})
    else:
        acc = fetch_one("SELECT profile_id, account_label, currency_code FROM dim_account WHERE profile_id = :p",
                        {"p": profile_id})
    if not acc:
        raise HTTPException(404, f"Không có tài khoản {profile_id}")
    return acc


def _scope_ok(scope: str) -> None:
    if scope not in GLOBALS:
        _account_or_404(scope)


@router.get("/accounts")
def accounts(channel: str = Query("amazon")) -> list[dict]:
    if channel == "wayfair":
        return fetch_all("""
            SELECT CONCAT(:x, a.account_id) AS profile_id, COALESCE(a.short_name, a.account_name) AS account_label,
                   a.currency_code,
                   (SELECT COUNT(*) FROM cfg_audit_param c WHERE c.scope_key = CONCAT(:x, a.account_id)) AS n_overrides
            FROM dim_wf_account a
            WHERE EXISTS (SELECT 1 FROM dim_wf_campaign c WHERE c.account_id = a.account_id)
            ORDER BY account_label""", {"x": wf_rules.PREFIX})
    return fetch_all("""
        SELECT a.profile_id, a.account_label, a.country_code, a.currency_code,
               (SELECT COUNT(*) FROM cfg_audit_param c WHERE c.scope_key = a.profile_id) AS n_overrides
        FROM dim_account a
        WHERE EXISTS (SELECT 1 FROM dim_campaign c WHERE c.profile_id = a.profile_id)
        ORDER BY a.account_label""")


@router.get("/rules")
def get_rules(profile_id: str | None = Query(None), channel: str = Query("amazon")) -> dict:
    reg = wf_rules if channel == "wayfair" else _reg(profile_id)
    if profile_id in GLOBALS:
        profile_id = None
    acc = _account_or_404(profile_id) if profile_id else None
    rows = fetch_all("SELECT scope_key, param, value, updated_at FROM cfg_audit_param WHERE scope_key IN (:g, :p)",
                     {"g": reg.GLOBAL, "p": profile_id or reg.GLOBAL})
    g = {r["param"]: r["value"] for r in rows if r["scope_key"] == reg.GLOBAL}
    a = {r["param"]: r["value"] for r in rows if profile_id and r["scope_key"] == profile_id}
    eff = rules.merge(g, a, reg.PARAMS)
    params = [{**asdict(p), "global": g.get(p.key), "account": a.get(p.key),
               "value": eff[p.key]["value"], "source": eff[p.key]["source"]} for p in reg.PARAMS]
    updated = max((r["updated_at"] for r in rows if r["updated_at"]), default=None)
    return jsonable({"account": acc, "rules": [{"id": i, "label": l, "desc": d} for i, l, d in reg.RULES],
                     "params": params, "updated_at": updated})


@router.put("/rules")
def put_rules(body: RuleValues) -> dict:
    _scope_ok(body.scope)
    reg = _reg(body.scope)
    upserts, deletes = [], []
    for key, value in body.values.items():
        if value is None:
            if key not in reg.BY_KEY:
                raise HTTPException(422, f"Không có tham số '{key}'")
            deletes.append(key)
            continue
        try:
            upserts.append({"s": body.scope, "k": key, "v": reg.validate(key, value), "t": datetime.now()})
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    with get_engine().begin() as conn:
        if upserts:
            conn.execute(text("""INSERT INTO cfg_audit_param (scope_key, param, value, updated_at) VALUES (:s, :k, :v, :t)
                                 ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)"""), upserts)
        for key in deletes:
            conn.execute(text("DELETE FROM cfg_audit_param WHERE scope_key = :s AND param = :k"), {"s": body.scope, "k": key})
    return {"ok": True, "saved": len(upserts), "reset": len(deletes)}


@router.post("/rules/copy")
def copy_rules(body: CopyRequest) -> dict:
    """Chép các ghi đè của một tài khoản sang tài khoản khác (thay toàn bộ ghi đè cũ của tài khoản đích).
    Nguồn '*' = đưa tài khoản đích về mặc định chung."""
    _scope_ok(body.source)
    wf = body.source.startswith(wf_rules.PREFIX)
    targets = [t for t in dict.fromkeys(body.targets) if t != body.source and t not in GLOBALS]
    for t in targets:
        if t.startswith(wf_rules.PREFIX) != wf:
            raise HTTPException(422, "Chỉ chép quy tắc giữa các tài khoản cùng kênh (Amazon hoặc Wayfair)")
        _account_or_404(t)
    src = [] if body.source in GLOBALS else fetch_all(
        "SELECT param, value FROM cfg_audit_param WHERE scope_key = :s", {"s": body.source})
    now = datetime.now()
    with get_engine().begin() as conn:
        for t in targets:
            conn.execute(text("DELETE FROM cfg_audit_param WHERE scope_key = :t"), {"t": t})
            if src:
                conn.execute(text("INSERT INTO cfg_audit_param (scope_key, param, value, updated_at) VALUES (:t, :k, :v, :n)"),
                             [{"t": t, "k": r["param"], "v": r["value"], "n": now} for r in src])
    return {"ok": True, "targets": len(targets), "params": len(src)}


@router.get("/acos")
def get_acos(profile_id: str = Query(...)) -> dict:
    """Portfolio của tài khoản và nhóm SP có chạy QC ở tài khoản này (60 ngày gần nhất) hoặc đã có mục tiêu riêng.
    Wayfair: không có portfolio; mục tiêu nhóm SP riêng của Wayfair (scope_type WF_GROUP, ACoS giá sỉ)."""
    _account_or_404(profile_id)
    if profile_id.startswith(wf_rules.PREFIX):
        groups = fetch_all("""
            SELECT g.group_id AS scope_id, g.group_name AS name, ROUND(s.spend, 0) AS spend, t.acos_target
            FROM (SELECT group_id, MAX(group_name) AS group_name FROM dim_product WHERE group_id IS NOT NULL GROUP BY group_id) g
            LEFT JOIN (SELECT l.group_id, SUM(f.cost) AS spend FROM fact_wf_product_daily f
                       JOIN dim_wf_listing l ON l.listing_id = f.listing_id
                       WHERE f.account_id = :a AND f.report_date >= (SELECT MAX(report_date) FROM fact_wf_product_daily) - INTERVAL 60 DAY
                       GROUP BY l.group_id) s ON s.group_id = g.group_id
            LEFT JOIN cfg_audit_acos t ON t.scope_type = :t AND t.scope_id = CAST(g.group_id AS CHAR)
            WHERE s.spend > 0 OR t.acos_target IS NOT NULL
            ORDER BY t.acos_target IS NULL, s.spend DESC""", {"a": wf_rules.account_id(profile_id), "t": wf_rules.ACOS_SCOPE})
        return jsonable({"portfolios": None, "groups": groups, "group_scope": wf_rules.ACOS_SCOPE})
    portfolios = fetch_all("""
        SELECT p.portfolio_id AS scope_id, p.portfolio_name AS name, p.state, t.acos_target
        FROM dim_portfolio p LEFT JOIN cfg_audit_acos t ON t.scope_type = 'PORTFOLIO' AND t.scope_id = p.portfolio_id
        WHERE p.profile_id = :p ORDER BY t.acos_target IS NULL, p.portfolio_name""", {"p": profile_id})
    groups = fetch_all("""
        SELECT g.group_id AS scope_id, g.group_name AS name, ROUND(s.spend, 0) AS spend, t.acos_target
        FROM (SELECT group_id, MAX(group_name) AS group_name FROM dim_product WHERE group_id IS NOT NULL GROUP BY group_id) g
        LEFT JOIN (SELECT d.group_id, SUM(f.cost) AS spend FROM fact_product_daily f JOIN dim_product d USING (product_id)
                   WHERE f.profile_id = :p AND f.report_date >= (SELECT MAX(report_date) FROM fact_product_daily) - INTERVAL 60 DAY
                   GROUP BY d.group_id) s ON s.group_id = g.group_id
        LEFT JOIN cfg_audit_acos t ON t.scope_type = 'GROUP' AND t.scope_id = CAST(g.group_id AS CHAR)
        WHERE s.spend > 0 OR t.acos_target IS NOT NULL
        ORDER BY t.acos_target IS NULL, s.spend DESC""", {"p": profile_id})
    return jsonable({"portfolios": portfolios, "groups": groups, "group_scope": "GROUP"})


@router.put("/acos")
def put_acos(items: list[AcosItem]) -> dict:
    now = datetime.now()
    for it in items:
        if it.scope_type not in ("GROUP", "PORTFOLIO", wf_rules.ACOS_SCOPE):
            raise HTTPException(422, "scope_type phải là GROUP, PORTFOLIO hoặc WF_GROUP")
        if it.acos_target is None:
            execute("DELETE FROM cfg_audit_acos WHERE scope_type = :t AND scope_id = :i", {"t": it.scope_type, "i": it.scope_id})
        else:
            execute("""INSERT INTO cfg_audit_acos (scope_type, scope_id, acos_target, updated_at) VALUES (:t, :i, :a, :n)
                       ON DUPLICATE KEY UPDATE acos_target = VALUES(acos_target), updated_at = VALUES(updated_at)""",
                    {"t": it.scope_type, "i": it.scope_id, "a": it.acos_target, "n": now})
    return {"ok": True, "saved": len(items)}


# ---------------------------------------------------------------- upload file bulk, chạy audit, xuất file

MAX_UPLOAD = 200 * 1024 * 1024
_lock = threading.Lock()  # mỗi lúc chỉ đọc / audit một file (tốn RAM và CPU)


class ExportRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=50000)


def _set_upload(upload_id: int, **cols) -> None:
    sets = ", ".join(f"{k} = :{k}" for k in cols)
    execute(f"UPDATE audit_bulk_upload SET {sets} WHERE id = :id", {**cols, "id": upload_id})


def _process(upload_id: int, path: Path, parse: bool, channel: str = "amazon") -> None:
    wf = channel == "wayfair"
    with _lock:
        try:
            if parse:
                _set_upload(upload_id, status="PARSING", message=None)
                _set_upload(upload_id, **(wf_bulk if wf else bulk).store(upload_id, path))
            _set_upload(upload_id, status="AUDITING", message=None)
            (wf_engine if wf else engine).run(upload_id)
            _set_upload(upload_id, status="READY")
        except Exception as exc:
            _set_upload(upload_id, status="FAILED", message=str(exc).splitlines()[0][:1000])


@router.post("/upload")
async def upload(request: Request) -> dict:
    """Nhận nguyên file .xlsx trong body (header X-File-Name), lưu lại rồi đọc + audit ở luồng nền.
    Kênh nhận theo nội dung file; header X-Channel (trang đang upload) chỉ để báo nhầm kênh."""
    name = unquote(request.headers.get("x-file-name", "bulk.xlsx"))
    if not name.lower().endswith(".xlsx"):
        raise HTTPException(422, "Chỉ nhận file .xlsx tải từ Ads Console (Bulk operations) hoặc WSP (Bulk Campaign Edits)")
    path = bulk.new_upload_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with path.open("wb") as f:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_UPLOAD:
                break
            f.write(chunk)
    if size == 0 or size > MAX_UPLOAD:
        path.unlink(missing_ok=True)
        raise HTTPException(413 if size else 422, "File quá lớn (tối đa 200 MB)" if size else "File rỗng")
    try:
        channel = "wayfair" if wf_bulk.is_wayfair(path) else "amazon"
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "Không đọc được file .xlsx")
    page = request.headers.get("x-channel")
    if page and page != channel:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "Đây là file bulk " + ("Wayfair" if channel == "wayfair" else "Amazon") +
                            ", hãy upload ở tab Audit từ khóa của kênh " + ("Wayfair" if channel == "wayfair" else "Amazon"))
    with get_engine().begin() as conn:
        upload_id = conn.execute(text("""INSERT INTO audit_bulk_upload (file_name, file_path, uploaded_at, status, channel)
                                         VALUES (:n, :p, :t, 'QUEUED', :c)"""),
                                 {"n": name[:255], "p": str(path), "t": datetime.now(), "c": channel}).lastrowid
    threading.Thread(target=_process, args=(upload_id, path, True, channel), daemon=True).start()
    return {"ok": True, "upload_id": upload_id, "channel": channel}


@router.get("/uploads")
def uploads(profile_id: str | None = Query(None), channel: str = Query("amazon"), limit: int = 20) -> list[dict]:
    """Các lần upload (mới nhất trước) của một kênh kèm lần audit gần nhất. Upload chưa nhận ra tài khoản vẫn hiện."""
    return jsonable(fetch_all("""
        SELECT u.id, u.profile_id, COALESCE(a.account_label, wa.short_name, wa.account_name) AS account_label,
               COALESCE(a.currency_code, wa.currency_code) AS currency_code, u.file_name, u.uploaded_at, u.status, u.message,
               u.n_rows, u.n_campaigns, u.matched_campaigns,
               r.id AS run_id, r.started_at AS run_at, r.status AS run_status, r.data_start, r.data_end, r.n_proposals,
               r.message AS run_message,
               (SELECT COUNT(*) FROM audit_proposal x WHERE x.run_id = r.id AND x.status = 'exported') AS n_exported
        FROM audit_bulk_upload u
        LEFT JOIN dim_account a ON a.profile_id = u.profile_id
        LEFT JOIN dim_wf_account wa ON CONCAT(:x, wa.account_id) = u.profile_id
        LEFT JOIN audit_run r ON r.id = (SELECT MAX(id) FROM audit_run WHERE upload_id = u.id)
        WHERE u.channel = :c AND (:p IS NULL OR u.profile_id = :p OR u.profile_id IS NULL)
        ORDER BY u.id DESC LIMIT :n""", {"p": profile_id, "c": channel, "x": wf_rules.PREFIX, "n": max(1, min(limit, 100))}))


@router.post("/uploads/{upload_id}/rerun")
def rerun(upload_id: int) -> dict:
    """Chạy lại audit cho file đã upload (vd sau khi sửa quy tắc)."""
    u = fetch_one("SELECT id, file_path, status, channel, "
                  "(SELECT COUNT(*) FROM audit_bulk_row WHERE upload_id = :u) + "
                  "(SELECT COUNT(*) FROM audit_wf_bulk_row WHERE upload_id = :u) AS n "
                  "FROM audit_bulk_upload WHERE id = :u", {"u": upload_id})
    if not u:
        raise HTTPException(404, "Không có lần upload này")
    if u["status"] in ("QUEUED", "PARSING", "AUDITING"):
        raise HTTPException(409, "File này đang được xử lý")
    parse = not u["n"]  # dòng chi tiết đã bị dọn (upload cũ) thì đọc lại file
    if parse and not Path(u["file_path"] or "").exists():
        raise HTTPException(410, "File gốc không còn, hãy upload lại")
    _set_upload(upload_id, status="QUEUED", message=None)
    threading.Thread(target=_process, args=(upload_id, Path(u["file_path"]), parse, u["channel"]), daemon=True).start()
    return {"ok": True}


@router.get("/runs/{run_id}/proposals")
def proposals(run_id: int) -> dict:
    run = fetch_one("""SELECT r.*, COALESCE(a.account_label, wa.short_name, wa.account_name) AS account_label,
                              COALESCE(a.currency_code, wa.currency_code) AS currency_code
                       FROM audit_run r LEFT JOIN dim_account a ON a.profile_id = r.profile_id
                       LEFT JOIN dim_wf_account wa ON CONCAT(:x, wa.account_id) = r.profile_id
                       WHERE r.id = :r""", {"r": run_id, "x": wf_rules.PREFIX})
    if not run:
        raise HTTPException(404, "Không có lần audit này")
    rows = fetch_all("""SELECT id, rule, action, campaign_name, ad_group_name, text, source, match_type, current_bid, new_bid,
                               impressions, clicks, spend, orders, sales, acos_target, reason, default_on, exportable,
                               status, exported_at, currency_code
                        FROM audit_proposal WHERE run_id = :r ORDER BY rule, spend DESC, id""", {"r": run_id})
    run["params"] = json.loads(run["params"] or "{}").get("params")
    reg = _reg(run["profile_id"])
    if reg is wf_rules:  # tài khoản Wayfair có thể có campaign ở cả wayfair.com và wayfair.ca
        run["currency_code"] = "/".join(sorted({r["currency_code"] for r in rows if r["currency_code"]})) or run["currency_code"]
    return jsonable({"run": run, "rules": [{"id": i, "label": l} for i, l, _ in reg.RULES if i != "general"],
                     "proposals": rows})


@router.post("/runs/{run_id}/export")
def export(run_id: int, body: ExportRequest) -> FileResponse:
    """Dựng file bulk từ các đề xuất được chọn, đánh dấu đã xuất (để tính thời gian chờ / số lần tăng)."""
    run = fetch_one("""SELECT r.id, r.profile_id, u.headers, u.channel, u.file_path,
                              COALESCE(a.account_label, wa.short_name) AS account_label
                       FROM audit_run r JOIN audit_bulk_upload u ON u.id = r.upload_id
                       LEFT JOIN dim_account a ON a.profile_id = r.profile_id
                       LEFT JOIN dim_wf_account wa ON CONCAT(:x, wa.account_id) = r.profile_id
                       WHERE r.id = :r""", {"r": run_id, "x": wf_rules.PREFIX})
    if not run:
        raise HTTPException(404, "Không có lần audit này")
    ids = sorted(set(body.ids))
    picked = []
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        ph = ",".join(f":i{j}" for j in range(len(chunk)))
        picked += fetch_all(f"SELECT * FROM audit_proposal WHERE run_id = :r AND exportable = 1 AND id IN ({ph})",
                            {"r": run_id, **{f"i{j}": v for j, v in enumerate(chunk)}})
    if not picked:
        raise HTTPException(422, "Không có đề xuất nào xuất được trong các dòng đã chọn")
    label = "".join(ch if ch.isalnum() else "_" for ch in (run["account_label"] or run["profile_id"]))
    if run["channel"] == "wayfair":
        path = bulk.UPLOAD_DIR / "out" / f"audit_WF_{label}_run{run_id}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        try:
            wf_bulk.write_xlsx(Path(run["file_path"] or ""), path, picked)
        except bulk.BulkError as exc:
            raise HTTPException(410, str(exc))
    else:
        path = bulk.UPLOAD_DIR / "out" / f"audit_{label}_run{run_id}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        bulk.write_xlsx(path, json.loads(run["headers"]), picked)
    now = datetime.now()
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE audit_proposal SET status = 'exported', exported_at = :t WHERE id = :i"),
                     [{"t": now, "i": p["id"]} for p in picked])
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
