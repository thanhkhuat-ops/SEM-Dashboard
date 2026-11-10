"""Quản lý từ điển phân loại từ khóa và chạy phân loại lại."""
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.db import execute, fetch_all, get_engine
from app.keywords.classifier import OVERRIDABLE_CLASSES
from etl.terms import sync_terms

router = APIRouter(prefix="/api/dict")

# kind -> (bảng, cột phụ được phép, giá trị hợp lệ của cột phụ)
DICTS = {
    "brand": ("dict_brand", "brand_type", ("OWN", "COMPETITOR")),
    "attribute": ("dict_attribute", "attr_group", None),
    "product_term": ("dict_product_term", "group_id", None),
    "stopword": ("dict_stopword", None, None),
    "override": ("dict_term_override", "term_class", OVERRIDABLE_CLASSES),
}
_job = {"running": False, "last": None}


class DictItem(BaseModel):
    term: str = Field(min_length=1, max_length=255)
    extra: str | None = None
    note: str | None = Field(None, max_length=255)


def _dict(kind: str) -> tuple[str, str | None, tuple | None]:
    if kind not in DICTS:
        raise HTTPException(404, f"Không có từ điển '{kind}'")
    return DICTS[kind]


@router.get("/{kind}")
def list_items(kind: str) -> list[dict]:
    table, extra, _ = _dict(kind)
    extra_sel = f", {extra} AS extra" if extra else ""
    note_sel = ", note" if kind != "stopword" else ""
    return fetch_all(f"SELECT id, term{extra_sel}{note_sel} FROM {table} ORDER BY term")


@router.post("/{kind}")
def add_item(kind: str, item: DictItem) -> dict:
    table, extra, allowed = _dict(kind)
    term = " ".join(item.term.lower().split())
    params = {"term": term, "note": item.note}
    if extra:
        value = (item.extra or "").strip() or None
        if allowed:
            value = (value or "").upper()
            if value not in allowed:
                raise HTTPException(422, f"{extra} phải là một trong {', '.join(allowed)}")
        if extra == "group_id" and value is not None:
            if not value.isdigit():
                raise HTTPException(422, "group_id phải là số")
            value = int(value)
        params["extra"] = value
    cols = "term" + (f", {extra}" if extra else "") + (", note" if kind != "stopword" else "")
    vals = ":term" + (", :extra" if extra else "") + (", :note" if kind != "stopword" else "")
    updates = ", ".join(f"{c} = VALUES({c})" for c in cols.split(", ")[1:]) or "term = term"
    execute(f"INSERT INTO {table} ({cols}) VALUES ({vals}) ON DUPLICATE KEY UPDATE {updates}", params)
    return {"ok": True, "term": term}


@router.delete("/{kind}/{item_id}")
def delete_item(kind: str, item_id: int) -> dict:
    table, _, _ = _dict(kind)
    return {"ok": True, "deleted": execute(f"DELETE FROM {table} WHERE id = :id", {"id": item_id})}


def _reclassify() -> None:
    started = datetime.now()
    try:
        with get_engine().begin() as conn:
            n = sync_terms(conn, f"`{settings.mart_schema}`", f"`{settings.staging_schema}`",
                           settings.generic_max_words, reclassify_all=True)
        _job["last"] = {"status": "OK", "terms": n, "started": started.isoformat(),
                        "finished": datetime.now().isoformat()}
    except Exception as exc:
        _job["last"] = {"status": "FAILED", "error": str(exc).splitlines()[0], "started": started.isoformat()}
    finally:
        _job["running"] = False


@router.post("/reclassify/run")
def reclassify() -> dict:
    if _job["running"]:
        return {"ok": False, "message": "Đang chạy phân loại lại"}
    _job["running"] = True
    threading.Thread(target=_reclassify, daemon=True).start()
    return {"ok": True, "message": "Đã bắt đầu phân loại lại toàn bộ từ khóa"}


@router.get("/reclassify/status")
def reclassify_status() -> dict:
    return _job
