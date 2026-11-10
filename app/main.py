"""SaleSappV2 – hệ thống báo cáo quảng cáo Amazon.

Chạy:  uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.config import ROOT_DIR
from app.routers import api, audit, dictionaries, export, notify, planning

STATIC_DIR = ROOT_DIR / "app" / "static"

app = FastAPI(title="SaleSappV2 – Amazon Ads Reporting")
app.include_router(api.router)
app.include_router(audit.router)
app.include_router(dictionaries.router)
app.include_router(export.router)
app.include_router(notify.router)
app.include_router(planning.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(SQLAlchemyError)
async def db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    message = str(getattr(exc, "orig", exc)).splitlines()[0]
    return JSONResponse(status_code=503, content={"detail": f"Lỗi cơ sở dữ liệu: {message}"})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    # no-cache: trình duyệt luôn hỏi lại server, nên sau mỗi lần cập nhật nhận ngay index.html mới (kèm app.js?v= mới)
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})
