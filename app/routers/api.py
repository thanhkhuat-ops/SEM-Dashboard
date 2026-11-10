"""API báo cáo: danh mục bộ lọc, chạy báo cáo, tình trạng dữ liệu."""
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request

from app.db import fetch_all
from app.filters import Filters, get_filters
from app.keywords.classifier import CLASS_LABELS
from app import pic, table_filters
from app.reports import AD_TYPE_LABELS, MAX_LIMIT, REPORTS
from app.reports_all import ALL_REPORTS as SUMMARY_REPORTS
from app.reports_inv import INV_REPORTS
from app.reports_pnl import PNL_REPORTS
from app.reports_shop import SHOP_REPORTS
from app.reports_wf import WF_REPORTS

ALL_REPORTS = {**REPORTS, **WF_REPORTS, **INV_REPORTS, **SHOP_REPORTS, **SUMMARY_REPORTS, **PNL_REPORTS}

router = APIRouter(prefix="/api")
# báo cáo có bảng lọc sẵn Trạng thái = ENABLED: luôn lấy tối đa MAX_LIMIT dòng rồi mới lọc, cắt
# (giá trị = số dòng hiện mặc định của báo cáo, giữ như khi chưa lọc)
DEFAULT_FILTER_REPORTS = {"campaigns": 500, "targets": 1000, "wf_campaigns": 500, "wf_products": 500, "wf_keywords": 1000}
FILTER_KEYS = {"start", "end", "profile_id", "ad_type", "portfolio_id", "group_id", "brand_id", "campaign_q",
               "match_type", "term_class", "length_bucket", "wf_account", "market", "sales_channel", "pic", "hc"}


def report_opts(request: Request) -> dict:
    return {k: v for k, v in request.query_params.items() if k not in FILTER_KEYS}


def jsonable(value):
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_report(name: str, f: Filters, opts: dict) -> dict:
    fn = ALL_REPORTS.get(name)
    if not fn:
        raise HTTPException(404, f"Không có báo cáo '{name}'")
    opts = dict(opts)
    spec = table_filters.parse(opts.pop("tf", None))
    max_rows = None
    if spec or name in DEFAULT_FILTER_REPORTS:
        # lọc trên tối đa MAX_LIMIT dòng (theo thứ tự sắp xếp của báo cáo), sau đó mới cắt theo số dòng người dùng chọn
        if "limit" in opts:
            try:
                max_rows = int(opts["limit"])
            except ValueError:
                pass
        elif name in DEFAULT_FILTER_REPORTS:
            max_rows = DEFAULT_FILTER_REPORTS[name]
        opts["limit"] = MAX_LIMIT
    result = fn(f, opts)
    pic.add_columns(result)
    table_filters.apply(result, spec, max_rows)
    result["report"] = name
    result["filters"] = f.describe()
    return jsonable(result)


@router.get("/report/{name}")
def report(name: str, request: Request, f: Filters = Depends(get_filters)) -> dict:
    return run_report(name, f, report_opts(request))


@router.get("/matrix/catalog")
def matrix_catalog() -> dict:
    from app import matrix
    return matrix.catalog()


@router.get("/matrix")
def matrix_data(metrics: str = "", gran: str = "", f: Filters = Depends(get_filters)) -> dict:
    """Matrix Chart: chuỗi theo kỳ của các chỉ số đã chọn (metrics = id cách nhau bởi dấu phẩy)."""
    from app import matrix
    ids = [m for m in metrics.split(",") if m in matrix.BY_ID][:2 * matrix.MAX_METRICS]
    if not ids:
        raise HTTPException(400, "Chưa chọn chỉ số nào")
    result = matrix.build(f, ids, gran or None)
    result["filters"] = f.describe()
    return jsonable(result)


@router.get("/inv/series")
def inv_series(node_id: str, product_id: int, qty_unit: str = "unit") -> dict:
    """Đường tồn (60 ngày qua + 120 ngày tới) của một SKU x nút tồn kho, cho đồ thị tab Dự kiến hết hàng."""
    from app.reports_inv import sku_series
    data = sku_series(node_id, product_id, qty_unit)
    if not data:
        raise HTTPException(404, "Không có dự báo cho SKU / nút này")
    return jsonable(data)


@router.get("/meta")
def meta() -> dict:
    accounts = fetch_all("""SELECT profile_id, account_label, company_name, country_code, currency_code
                            FROM dim_account ORDER BY account_label""")
    portfolios = fetch_all("""SELECT p.portfolio_id, p.portfolio_name, a.account_label FROM dim_portfolio p
                              LEFT JOIN dim_account a ON a.profile_id = p.profile_id ORDER BY p.portfolio_name""")
    # nhóm SP / brand có quảng cáo trên Amazon hoặc Wayfair, hoặc có bán trên Shopify
    shop = "SELECT p2.{k} FROM dim_product p2 JOIN (SELECT DISTINCT product_id FROM fact_shop_line) s ON s.product_id = p2.product_id"
    groups = fetch_all(f"""SELECT p.group_id, MAX(p.group_name) AS group_name FROM dim_product p
                          WHERE p.group_id IN (SELECT m.group_id FROM map_adgroup_product m
                                               UNION SELECT g.group_id FROM map_wf_campaign_group g
                                               UNION {shop.format(k='group_id')})
                          GROUP BY p.group_id ORDER BY group_name""")
    brands = fetch_all(f"""SELECT p.brand_id, MAX(p.brand_name) AS brand_name FROM dim_product p
                          WHERE p.brand_id IN (SELECT m.brand_id FROM map_adgroup_product m
                                               UNION SELECT g.brand_id FROM map_wf_campaign_group g
                                               UNION {shop.format(k='brand_id')})
                          GROUP BY p.brand_id ORDER BY brand_name""")
    wf_accounts = fetch_all("""SELECT CONCAT(f.account_id, '-', f.country_code) AS id,
                                 CONCAT(COALESCE(MAX(a.short_name), f.account_id), ' - ', f.country_code) AS label
                               FROM (SELECT DISTINCT account_id, country_code FROM fact_wf_campaign_daily) f
                               LEFT JOIN dim_wf_account a ON a.account_id = f.account_id
                               GROUP BY f.account_id, f.country_code ORDER BY label""")
    freshness = fetch_all("""
        SELECT 'campaign' AS fact, MAX(report_date) AS max_date FROM fact_campaign_daily
        UNION ALL SELECT 'target', MAX(report_date) FROM fact_target_daily
        UNION ALL SELECT 'search_term', MAX(report_date) FROM fact_search_term_daily
        UNION ALL SELECT 'product', MAX(report_date) FROM fact_product_daily
        UNION ALL SELECT 'total_sales', MAX(report_date) FROM fact_total_sales_daily
        UNION ALL SELECT 'wf_campaign', MAX(report_date) FROM fact_wf_campaign_daily
        UNION ALL SELECT 'wf_total_sales', MAX(report_date) FROM fact_wf_total_sales_daily
        UNION ALL SELECT 'shop_sales', MAX(report_date) FROM fact_shop_line
        UNION ALL SELECT 'inv_sales', MAX(report_date) FROM fact_channel_sales_daily
        UNION ALL SELECT 'inv_stock', DATE(MAX(computed_at)) FROM inv_projection
        UNION ALL SELECT 'inv_fba', MAX(read_date) FROM fact_fba_sheet_stock""")
    return jsonable({
        "accounts": accounts, "portfolios": portfolios, "groups": groups, "brands": brands, "wf_accounts": wf_accounts,
        "wf_match_types": ["SMART EXACT", "SMART PHRASE"],
        "pics": pic.options(),
        "markets": ["US", "CA", "AU"],
        "sales_channels": [{"id": "amazon", "label": "Amazon"}, {"id": "wayfair", "label": "Wayfair"},
                           {"id": "shopify", "label": "Shopify"}, {"id": "other", "label": "Khác (Walmart, eBay, bán sỉ…)"}],
        "ad_types": [{"id": k, "label": v} for k, v in AD_TYPE_LABELS.items()],
        "match_types": ["EXACT", "PHRASE", "BROAD", "TARGETING_EXPRESSION", "TARGETING_EXPRESSION_PREDEFINED", "SD_TARGET"],
        "term_classes": [{"id": k, "label": v} for k, v in CLASS_LABELS.items()],
        "length_buckets": ["1", "2", "3", "4", "5+", "ASIN"],
        "freshness": {r["fact"]: r["max_date"] for r in freshness},
    })


@router.get("/health")
def health() -> dict:
    try:
        runs = fetch_all("""SELECT run_id, step, date_start, date_end, finished_at, rows_affected, status, message
                            FROM etl_run_log ORDER BY id DESC LIMIT 20""")
    except Exception as exc:  # DB chưa cấu hình hoặc chưa chạy ETL --init
        return {"ok": False, "error": str(exc).splitlines()[0]}
    return jsonable({"ok": True, "last_runs": runs})
