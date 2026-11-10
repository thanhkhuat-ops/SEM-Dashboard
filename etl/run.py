"""ETL nạp schema ads_mart từ staging.

  python -m etl.run --init                    # tạo schema/bảng, nạp lịch sử từ ETL_BACKFILL_START
  python -m etl.run                           # chạy hằng ngày: nạp lại ETL_REFRESH_DAYS ngày gần nhất
  python -m etl.run --start 2025-01-01 --end 2025-03-31
  python -m etl.run --reclassify              # phân loại lại toàn bộ từ khóa sau khi sửa từ điển

Nếu .env có SOURCE_DB_HOST (DWH ở server khác), mỗi lần chạy sẽ đồng bộ các bảng cần dùng từ DWH về
schema STAGING_SCHEMA trên DB nội bộ trước khi tổng hợp (xem etl/sync_staging.py). Bỏ qua bằng --no-sync.
"""
import argparse
import re
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import bindparam, text

from app.config import settings
from app.db import get_engine
from app.keywords.normalize import DEFAULT_STOPWORDS
from etl import clear_stock, fba_sheet, geo_sales, inventory, op_fee, pnl, std_cogs
from etl.sync_staging import DbConfig, StagingSync
from etl.terms import sync_terms

SQL_DIR = Path(__file__).resolve().parent / "sql"
DATED_STEPS = ["20_fx.sql", "30_campaign.sql", "35_wf_ads.sql", "40_target.sql", "50_search_term.sql",
               "60_product.sql", "70_total_sales.sql", "75_wf_total_sales.sql", "76_channel_sales.sql"]
CHUNK_DAYS = 31


def render(name: str) -> str:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    return sql.replace("{mart}", f"`{settings.mart_schema}`").replace("{stg}", f"`{settings.staging_schema}`")


def split_statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*(?:\n|$)", body) if s.strip()]


class Runner:
    def __init__(self) -> None:
        self.run_id = datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4]
        self.engine = get_engine()

    def log(self, step: str, started: datetime, status: str, rows: int | None = None,
            message: str | None = None, start: date | None = None, end: date | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(f"""INSERT INTO `{settings.mart_schema}`.etl_run_log
                (run_id, step, date_start, date_end, started_at, finished_at, rows_affected, status, message)
                VALUES (:r, :s, :ds, :de, :sa, :fa, :rows, :st, :m)"""),
                         {"r": self.run_id, "s": step, "ds": start, "de": end, "sa": started,
                          "fa": datetime.now(), "rows": rows, "st": status, "m": (message or "")[:4000]})
        span = f" {start}..{end}" if start else ""
        print(f"[{status}] {step}{span} rows={rows} {message or ''}", flush=True)

    def run_file(self, name: str, start: date | None = None, end: date | None = None) -> None:
        params = {}
        if start:
            params = {"start": start, "end": end, "end_excl": end + timedelta(days=1)}
        started, t0, total = datetime.now(), time.time(), 0
        try:
            with self.engine.begin() as conn:
                for stmt in split_statements(render(name)):
                    used = {k: v for k, v in params.items() if f":{k}" in stmt}
                    result = conn.execute(text(stmt), used)
                    total += max(result.rowcount or 0, 0)
        except Exception as exc:
            self.log(name, started, "FAILED", total, str(exc), start, end)
            raise
        self.log(name, started, "OK", total, f"{time.time() - t0:.1f}s", start, end)

    def sync_log(self, step: str, rows: int, seconds: float, note: str) -> None:
        started = datetime.now() - timedelta(seconds=seconds)
        self.log(f"sync:{step}"[:60], started, "OK", rows, f"{seconds:.1f}s {note}".strip())


def run_fba_sheet(runner: "Runner") -> None:
    """Tồn FBA từ Google Sheet. Lỗi (sheet đổi quyền, mạng…) chỉ ghi log; app dùng lần đọc gần nhất (tối đa 7 ngày)."""
    if not settings.fba_sheet_id:
        return
    started = datetime.now()
    mart = f"`{settings.mart_schema}`"
    try:
        res = fba_sheet.run(runner.engine, mart, settings.fba_sheet_id, settings.fba_sheet_gid, settings.google_sa_json)
    except Exception as exc:
        with runner.engine.begin() as conn:
            fba_sheet.log_failure(conn, mart, str(exc))
        runner.log("fba_sheet", started, "FAILED", 0, str(exc))
        return
    runner.log("fba_sheet", started, "OK", res["skus"], f"In Stock {res['in_stock']}. {res['note']}"[:480])


def run_clear_stock(runner: "Runner") -> None:
    """SKU đang xả hàng từ Google Sheet. Lỗi chỉ ghi log, giữ danh sách lần trước."""
    if not settings.clear_sheet_id:
        return
    started = datetime.now()
    try:
        res = clear_stock.run(runner.engine, f"`{settings.mart_schema}`", settings.clear_sheet_id,
                              settings.clear_sheet_gid, settings.google_sa_json)
    except Exception as exc:
        runner.log("clear_stock", started, "FAILED", 0, str(exc))
        return
    runner.log("clear_stock", started, "OK", res["rows"], f"{res['unmatched']} SKU không khớp dim_product")


def run_inventory(runner: "Runner") -> None:
    """Ảnh chụp tồn kho + hàng đang về (90_inventory.sql), tồn FBA từ sheet, rồi tốc độ bán và ngày dự kiến hết hàng
    (etl/inventory.py)."""
    runner.run_file("90_inventory.sql")
    run_fba_sheet(runner)
    run_clear_stock(runner)
    started = datetime.now()
    with runner.engine.begin() as conn:
        mart = f"`{settings.mart_schema}`"
        fba_sheet.apply(conn, mart)
        n = inventory.compute(conn, mart)
        geo_sales.compute(conn, mart, f"`{settings.staging_schema}`")
    runner.log("inventory_projection", started, "OK", n)


def run_std_cogs(runner: "Runner") -> None:
    """Giá vốn chuẩn từ Google Sheet. Lỗi (sheet chưa chia sẻ, mạng…) chỉ ghi log, giữ bản đã nạp lần trước."""
    if not settings.cogs_sheet_id:
        return
    started = datetime.now()
    try:
        res = std_cogs.run(runner.engine, f"`{settings.mart_schema}`", settings.cogs_sheet_id,
                           settings.cogs_sheet_gid, settings.google_sa_json)
    except Exception as exc:
        runner.log("std_cogs", started, "FAILED", 0, str(exc))
        return
    runner.log("std_cogs", started, "OK", res["rows"],
               f"{res['skus']} SKU, {res['unmatched_skus']} SKU không khớp dim_product")


def run_operation_fee(runner: "Runner") -> None:
    """Phí vận hành từ Google Sheet của công ty. Lỗi chỉ ghi log, giữ bản đã nạp lần trước."""
    if not settings.opfee_sheet_id:
        return
    started = datetime.now()
    try:
        res = op_fee.run(runner.engine, f"`{settings.mart_schema}`", settings.opfee_sheet_id,
                         settings.opfee_sheet_gid, settings.google_sa_json)
    except Exception as exc:
        runner.log("operation_fee", started, "FAILED", 0, str(exc))
        return
    runner.log("operation_fee", started, "OK", res["rows"], res.get("note", ""))


def run_pnl(runner: "Runner") -> None:
    """P&L công ty theo ngày (etl/pnl.py), tính lại toàn bộ từ PNL_START. Lỗi chỉ ghi log."""
    started = datetime.now()
    try:
        with runner.engine.begin() as conn:
            n = pnl.compute(conn, f"`{settings.mart_schema}`", f"`{settings.staging_schema}`")
    except Exception as exc:
        runner.log("pnl", started, "FAILED", 0, str(exc))
        return
    runner.log("pnl", started, "OK", n)


def make_sync() -> StagingSync:
    """Kết nối DWH nguồn và tạo schema bản sao staging ở DB nội bộ (cần có trước khi tạo mart)."""
    source = DbConfig(settings.source_db_host, settings.source_db_port, settings.source_db_user,
                      settings.source_db_password, settings.source_schema)
    target = DbConfig(settings.db_host, settings.db_port, settings.db_user, settings.db_password,
                      settings.staging_schema)
    return StagingSync(source, target)


# Cột thêm vào bảng đã có (CREATE TABLE IF NOT EXISTS không sửa bảng cũ): (bảng, cột, kiểu)
ADDED_COLUMNS = [
    ("inv_projection", "lost_units_90", "DOUBLE"), ("inv_projection", "avg_price", "DOUBLE"),
    ("inv_projection", "lost_sales_90", "DOUBLE"), ("inv_projection", "as_of", "DATE"),
    ("dim_product", "volume", "DOUBLE"),
    # phần FBA (fulfill_channel = AFN) của tổng doanh số; FBM = tổng − FBA
    ("fact_total_sales_daily", "fba_order_items", "INT"), ("fact_total_sales_daily", "fba_units", "INT"),
    ("fact_total_sales_daily", "fba_sales_usd", "DOUBLE"),
    ("audit_proposal", "source", "VARCHAR(500)"),
    ("audit_bulk_upload", "channel", "VARCHAR(10) NOT NULL DEFAULT 'amazon'"),  # amazon | wayfair
    ("audit_proposal", "currency_code", "VARCHAR(5)"),  # Wayfair: tiền theo store của campaign
    ("dim_adgroup", "state", "VARCHAR(15)"), ("dim_wf_listing", "state", "VARCHAR(15)"),  # do 18_status.sql ghi
]


def ensure_schema() -> None:
    # Dùng cùng charset/collation với staging để so sánh chuỗi giữa hai schema không lỗi "Illegal mix of collations"
    with get_engine(None).begin() as conn:
        row = conn.execute(text("SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA "
                                "WHERE SCHEMA_NAME = :s"), {"s": settings.staging_schema}).first()
        charset, collation = row if row else ("utf8mb4", "utf8mb4_unicode_ci")
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.mart_schema}` "
                          f"CHARACTER SET {charset} COLLATE {collation}"))
    with get_engine().begin() as conn:
        for stmt in split_statements(render("00_schema.sql")):
            conn.execute(text(stmt))
        conn.execute(text(f"INSERT IGNORE INTO `{settings.mart_schema}`.dict_stopword (term) VALUES (:t)"),
                     [{"t": w} for w in DEFAULT_STOPWORDS])
        have = {(r[0].lower(), r[1].lower()) for r in conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = :s"),
            {"s": settings.mart_schema})}
        for table, column, kind in ADDED_COLUMNS:
            if (table, column) not in have:
                conn.execute(text(f"ALTER TABLE `{settings.mart_schema}`.`{table}` ADD COLUMN `{column}` {kind}"))
    print(f"[OK] schema {settings.mart_schema} sẵn sàng")


def fill_dim_date(start: date, end: date) -> None:
    rows, d = [], start
    while d <= end:
        rows.append({"d": d, "y": d.year, "m": d.month, "ms": d.replace(day=1), "ws": d - timedelta(days=d.weekday())})
        d += timedelta(days=1)
    with get_engine().begin() as conn:
        conn.execute(text(f"""INSERT IGNORE INTO `{settings.mart_schema}`.dim_date
            (date_key, year, month, month_start, week_start) VALUES (:d, :y, :m, :ms, :ws)"""), rows)


def date_chunks(start: date, end: date, days: int = CHUNK_DAYS):
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=days - 1), end)
        yield cur, stop
        cur = stop + timedelta(days=1)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # console Windows mặc định cp1252, không in được tiếng Việt
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="ETL ads_mart")
    ap.add_argument("--init", action="store_true", help="tạo schema và nạp lịch sử")
    ap.add_argument("--start", type=date.fromisoformat)
    ap.add_argument("--end", type=date.fromisoformat)
    ap.add_argument("--days", type=int, help="số ngày gần nhất cần nạp lại")
    ap.add_argument("--reclassify", action="store_true", help="chỉ phân loại lại toàn bộ từ khóa")
    ap.add_argument("--skip-terms", action="store_true")
    ap.add_argument("--no-sync", action="store_true", help="không đồng bộ từ DWH nguồn (dùng bản sao staging đang có)")
    args = ap.parse_args(argv)

    sync = None
    if settings.sync_enabled and not args.no_sync and not args.reclassify:
        sync = make_sync()
    if not args.reclassify:
        ensure_schema()  # idempotent: tạo bảng mới / thêm cột mới khi nâng cấp
    runner = Runner()
    if sync:
        sync.log = runner.sync_log
        sync.ensure_tables()
        sync.sync_full()
    mart, stg = f"`{settings.mart_schema}`", f"`{settings.staging_schema}`"

    if args.reclassify:
        started = datetime.now()
        with runner.engine.begin() as conn:
            n = sync_terms(conn, mart, stg, settings.generic_max_words, reclassify_all=True)
        runner.log("terms_reclassify", started, "OK", n)
        return 0

    today = date.today()
    end = args.end or today
    if args.start:
        start = args.start
    elif args.init:
        start = settings.etl_backfill_start
    else:
        start = end - timedelta(days=(args.days or settings.etl_refresh_days))

    fill_dim_date(min(start, settings.etl_backfill_start), today + timedelta(days=1))
    runner.run_file("10_dims.sql")
    runner.run_file("15_wf_dims.sql")
    if settings.excluded_profile_ids:
        with runner.engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {mart}.dim_account WHERE profile_id IN :ids").bindparams(
                bindparam("ids", expanding=True)), {"ids": list(settings.excluded_profile_ids)})

    if sync:
        # đồng bộ cả khoảng ngày một lần: phần lớn bảng report ở DWH không có index theo ngày,
        # chia đợt sẽ phải quét toàn bảng ở nguồn nhiều lần
        sync.sync_window(start, end)
    for c_start, c_end in date_chunks(start, end):
        for step in DATED_STEPS:
            runner.run_file(step, c_start, c_end)
    if sync:
        sync.sync_states(mart)  # cần fact_target_daily đã nạp để biết keyword nào cần tra trạng thái
    runner.run_file("18_status.sql")
    runner.run_file("80_post.sql")
    runner.run_file("85_wf_post.sql")
    runner.run_file("77_shop_sales.sql")  # Shopify: dựng lại toàn bộ (cần fx_daily của mọi ngày có đơn)
    run_inventory(runner)
    run_std_cogs(runner)  # sau 10_dims.sql: cần dim_product để gán product_id
    if not pnl.COGS_INCLUDES_RETURN_AND_OPERATION:
        run_operation_fee(runner)
    run_pnl(runner)  # sau mọi bảng doanh số / QC / giá vốn
    if sync:
        sync.close()

    if not args.skip_terms:
        started = datetime.now()
        with runner.engine.begin() as conn:
            n = sync_terms(conn, mart, stg, settings.generic_max_words, start, end)
        runner.log("terms_sync", started, "OK", n, start=start, end=end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
