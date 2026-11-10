"""Cấu hình ứng dụng, đọc từ biến môi trường / file .env ở thư mục gốc dự án."""
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _list(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(x.strip() for x in raw.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    staging_schema: str
    mart_schema: str
    etl_backfill_start: date
    etl_refresh_days: int
    generic_max_words: int
    excluded_profile_ids: tuple[str, ...]
    # DWH nguồn ở server khác (để trống nếu staging nằm cùng server với DB_*)
    source_db_host: str
    source_db_port: int
    source_db_user: str
    source_db_password: str
    source_schema: str
    # Gửi tin cho PIC qua Google Chat (app/notify)
    notify_enabled: bool
    notify_lag_days: int
    notify_app_url: str
    notify_waste_spend: float
    notify_acos_target: float
    # Tồn kho: thể tích (CBM) của một container 40HQ khi quy đổi số lượng ra container
    container_cbm: float
    # Giá vốn chuẩn trên Google Sheet (etl/std_cogs.py): id + gid của tab; file JSON service account nếu sheet không công khai
    cogs_sheet_id: str
    cogs_sheet_gid: str
    google_sa_json: str
    # Phí vận hành mỗi đơn vị (tab operation_fee_sales_fc, etl/op_fee.py) cho P&L công ty
    opfee_sheet_id: str
    opfee_sheet_gid: str
    # Tồn FBA trên Google Sheet "inventory details" (etl/fba_sheet.py): id + gid của tab
    fba_sheet_id: str
    fba_sheet_gid: str
    # SKU đang xả hàng (Clear Stock) trên Google Sheet (etl/clear_stock.py): không đề xuất gửi thêm lên FBA / CG
    clear_sheet_id: str
    clear_sheet_gid: str

    @property
    def sync_enabled(self) -> bool:
        return bool(self.source_db_host)


def load_settings() -> Settings:
    return Settings(
        db_host=os.getenv("DB_HOST", "127.0.0.1"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        staging_schema=os.getenv("STAGING_SCHEMA", "staging"),
        mart_schema=os.getenv("MART_SCHEMA", "ads_mart"),
        etl_backfill_start=date.fromisoformat(os.getenv("ETL_BACKFILL_START", "2025-01-01")),
        etl_refresh_days=int(os.getenv("ETL_REFRESH_DAYS", "60")),
        generic_max_words=int(os.getenv("GENERIC_MAX_WORDS", "2")),
        excluded_profile_ids=_list("EXCLUDED_PROFILE_IDS"),
        source_db_host=os.getenv("SOURCE_DB_HOST", ""),
        source_db_port=int(os.getenv("SOURCE_DB_PORT", "3306")),
        source_db_user=os.getenv("SOURCE_DB_USER", ""),
        source_db_password=os.getenv("SOURCE_DB_PASSWORD", ""),
        source_schema=os.getenv("SOURCE_SCHEMA", "staging"),
        notify_enabled=os.getenv("NOTIFY_ENABLED", "false").strip().lower() in ("1", "true", "yes"),
        notify_lag_days=int(os.getenv("NOTIFY_LAG_DAYS", "2")),
        notify_app_url=os.getenv("NOTIFY_APP_URL", "").rstrip("/"),
        notify_waste_spend=float(os.getenv("NOTIFY_WASTE_SPEND", "10")),
        notify_acos_target=float(os.getenv("NOTIFY_ACOS_TARGET", "0.3")),
        container_cbm=float(os.getenv("INV_CONTAINER_CBM", "68")),
        cogs_sheet_id=os.getenv("COGS_SHEET_ID", "").strip(),
        cogs_sheet_gid=os.getenv("COGS_SHEET_GID", "0").strip(),
        google_sa_json=os.getenv("GOOGLE_SA_JSON", "").strip(),
        opfee_sheet_id=os.getenv("OPFEE_SHEET_ID", "").strip(),
        opfee_sheet_gid=os.getenv("OPFEE_SHEET_GID", "0").strip(),
        fba_sheet_id=os.getenv("FBA_SHEET_ID", "").strip(),
        fba_sheet_gid=os.getenv("FBA_SHEET_GID", "0").strip(),
        clear_sheet_id=os.getenv("CLEAR_SHEET_ID", "").strip(),
        clear_sheet_gid=os.getenv("CLEAR_SHEET_GID", "0").strip(),
    )


settings = load_settings()
