"""Kết nối MySQL. Ứng dụng web chỉ đọc schema mart; ETL đọc staging và ghi mart."""
from decimal import Decimal
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

from app.config import settings


def make_url(database: str | None) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=database,
        query={"charset": "utf8mb4"},
    )


@lru_cache(maxsize=4)
def get_engine(database: str | None = "__mart__") -> Engine:
    db = settings.mart_schema if database == "__mart__" else database
    return create_engine(make_url(db), pool_pre_ping=True, pool_recycle=3600)


def _clean(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [{k: _clean(v) for k, v in row.items()} for row in result.mappings()]


def fetch_one(sql: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: dict | None = None) -> int:
    with get_engine().begin() as conn:
        return conn.execute(text(sql), params or {}).rowcount
