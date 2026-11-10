"""Sao chép cấu trúc bảng (không dữ liệu) của DWH nguồn về máy.

Đọc DWH bằng SOURCE_DB_* trong .env (chỉ SHOW CREATE TABLE), ghi toàn bộ DDL ra exports/dwh_schema.sql.
Thêm --apply <schema> để tạo các bảng rỗng đó trong MySQL nội bộ (DB_*); bảng đã có thì bỏ qua.

    python scripts/dump_dwh_schema.py
    python scripts/dump_dwh_schema.py --apply staging_schema
"""
import argparse
import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCHEMA = "staging"


def _connect(prefix: str, schema: str | None = None) -> pymysql.connections.Connection:
    g = lambda k, d="": os.getenv(f"{prefix}{k}", d).strip()
    return pymysql.connect(host=g("HOST"), port=int(g("PORT", "3306")), user=g("USER"), password=g("PASSWORD"),
                           database=schema, charset="utf8mb4")


def dump(out: Path) -> list[tuple[str, str]]:
    conn = _connect("SOURCE_DB_", SOURCE_SCHEMA)
    ddls = []
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name", (SOURCE_SCHEMA,))
        for (table,) in cur.fetchall():
            cur.execute(f"SHOW CREATE TABLE `{table}`")
            ddl = cur.fetchone()[1]
            # Bỏ AUTO_INCREMENT=n để bản rỗng bắt đầu lại từ đầu.
            ddl = re.sub(r" AUTO_INCREMENT=\d+", "", ddl).replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
            ddls.append((table, ddl))
    conn.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"-- {t}\n{d};\n\n" for t, d in ddls), encoding="utf-8")
    return ddls


def apply(ddls: list[tuple[str, str]], schema: str) -> list[str]:
    conn = _connect("DB_")
    failed = []
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{schema}` CHARACTER SET utf8mb4")
        cur.execute(f"USE `{schema}`")
        for table, ddl in ddls:
            try:
                cur.execute(ddl)
            except pymysql.MySQLError as e:
                failed.append(f"{table}: {e}")
    conn.commit()
    conn.close()
    return failed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "exports" / "dwh_schema.sql"))
    parser.add_argument("--apply", metavar="SCHEMA", help="tạo bảng rỗng trong schema này ở MySQL nội bộ")
    args = parser.parse_args()

    ddls = dump(Path(args.out))
    print(f"Đã ghi DDL {len(ddls)} bảng -> {args.out}")
    if args.apply:
        failed = apply(ddls, args.apply)
        print(f"Đã tạo {len(ddls) - len(failed)}/{len(ddls)} bảng trong `{args.apply}`")
        for f in failed:
            print("  lỗi", f)


if __name__ == "__main__":
    main()
