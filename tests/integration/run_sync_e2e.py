"""Kiểm thử bước đồng bộ DWH -> DB nội bộ. Chạy SAU run_e2e (cần schema staging + ads_mart đã có).

Giả lập: nguồn = schema `staging` trên MySQL thử; đích = schema `staging_local` + mart `ads_mart_sync` cùng server.
ETL chạy với SOURCE_DB_* rồi so sánh mart thu được với ads_mart (chạy trực tiếp trên staging) phải giống hệt.

  .venv/Scripts/python -m tests.integration.run_sync_e2e
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for line in (HERE / "test.env").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()
os.environ.update({
    "SOURCE_DB_HOST": os.environ["DB_HOST"], "SOURCE_DB_PORT": os.environ["DB_PORT"],
    "SOURCE_DB_USER": os.environ["DB_USER"], "SOURCE_DB_PASSWORD": os.environ["DB_PASSWORD"],
    "SOURCE_SCHEMA": "staging", "STAGING_SCHEMA": "staging_local", "MART_SCHEMA": "ads_mart_sync",
})

import pymysql  # noqa: E402

from app.config import settings  # noqa: E402
from etl import run as etl_run  # noqa: E402
from tests.integration.seed_staging import END, START  # noqa: E402

CHECKS = {
    "fact_campaign_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), ROUND(SUM(sales_usd), 4), SUM(orders), SUM(ntb_orders)",
    "fact_target_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), SUM(orders), ROUND(SUM(bid), 4)",
    "fact_search_term_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), SUM(orders)",
    "fact_product_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), SUM(product_id)",
    "fact_purchased_product_daily": "COUNT(*), ROUND(SUM(sales_usd), 4)",
    "fact_placement_daily": "COUNT(*), ROUND(SUM(cost_usd), 4)",
    "fact_campaign_budget_daily": "COUNT(*), ROUND(SUM(budget_usd), 4), ROUND(SUM(top_of_search_is), 4)",
    "fact_total_sales_daily": "COUNT(*), ROUND(SUM(sales_usd), 4), SUM(units)",
    # bỏ 'vivere hammock stand': run_e2e thêm rồi xóa brand đối thủ này mà không phân loại lại
    "dim_term": "COUNT(*), SUM(term_class = 'GENERIC' AND term <> 'vivere hammock stand'), "
                "SUM(term_class = 'TARGETED' AND term <> 'vivere hammock stand')",
    "bridge_term_ngram": "COUNT(*)",
    "map_adgroup_product": "COUNT(*), SUM(is_dominant)",
    "fact_wf_campaign_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), ROUND(SUM(sales_usd), 4)",
    "fact_wf_keyword_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), ROUND(SUM(bid), 4)",
    "fact_wf_search_term_daily": "COUNT(*), ROUND(SUM(cost_usd), 4), SUM(orders)",
    "fact_wf_total_sales_daily": "COUNT(*), ROUND(SUM(sales_usd), 4), SUM(units)",
    "fact_wf_share_of_search": "COUNT(*), ROUND(SUM(share_search), 4)",
    "map_wf_campaign_group": "COUNT(*), SUM(is_dominant)",
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                           password=settings.db_password, autocommit=True)
    with conn.cursor() as cur:
        cur.execute("DROP DATABASE IF EXISTS staging_local")
        cur.execute("DROP DATABASE IF EXISTS ads_mart_sync")
    # chạy 2 lần: lần 2 kiểm tra đồng bộ lại không nhân đôi và chỉ tra bid còn thiếu
    etl_run.main(["--init", "--start", START.isoformat(), "--end", END.isoformat()])
    etl_run.main(["--start", START.isoformat(), "--end", END.isoformat()])

    fails = []
    with conn.cursor() as cur:
        for table, expr in CHECKS.items():
            cur.execute(f"SELECT {expr} FROM ads_mart.{table}")
            a = cur.fetchone()
            cur.execute(f"SELECT {expr} FROM ads_mart_sync.{table}")
            b = cur.fetchone()
            ok = a == b
            print(("  ok   " if ok else "  FAIL ") + f"{table}: {a}" + ("" if ok else f" vs {b}"))
            if not ok:
                fails.append(table)
        cur.execute("SELECT step, rows_affected, message FROM ads_mart_sync.etl_run_log "
                    "WHERE step = 'sync:sem__keywords_base_daily' ORDER BY id")
        bids = cur.fetchall()
        second_run = bids[len(bids) // 2:]
        no_refetch = all(r[1] == 0 for r in second_run)
        print(("  ok   " if no_refetch else "  FAIL ") + f"lần chạy 2 không tra lại bid đã có: {second_run}")
        if not no_refetch:
            fails.append("bids")
        cur.execute("SELECT COUNT(*) FROM ads_mart_sync.etl_run_log WHERE status = 'FAILED'")
        failed = cur.fetchone()[0]
        print(("  ok   " if failed == 0 else "  FAIL ") + f"bước lỗi: {failed}")
    print("\nTẤT CẢ ĐẠT" if not fails and failed == 0 else f"\nLỖI: {fails}")
    return 1 if fails or failed else 0


if __name__ == "__main__":
    sys.exit(main())
