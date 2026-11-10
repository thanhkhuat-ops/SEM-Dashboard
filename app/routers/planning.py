"""Giá vốn & phí theo SKU, phí mặc định theo kênh, mục tiêu tháng, chi phí QC Shopify theo tháng (team tự nhập; ETL
không ghi đè)."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import insights, reports, reports_shop, reports_wf
from app.db import execute, fetch_all, fetch_one
from app.filters import Filters
from app.routers.api import jsonable

router = APIRouter(prefix="/api")
CHANNELS = ("amazon", "wayfair")
COST_CHANNELS = CHANNELS + ("shopify", "other")  # phí sàn mặc định (trang Tổng hợp dùng cả Shopify và kênh khác)
COST_FIELDS = ("landed_cost", "amz_fee_unit", "wf_fee_unit", "amz_referral_pct", "return_pct")


# ---------------------------------------------------------------- giá vốn & phí

class CostRow(BaseModel):
    product_id: int | None = None
    product_sku: str | None = Field(None, max_length=100)  # dùng khi dán CSV (không có product_id)
    landed_cost: float | None = Field(None, ge=0)
    amz_fee_unit: float | None = Field(None, ge=0)
    wf_fee_unit: float | None = Field(None, ge=0)
    amz_referral_pct: float | None = Field(None, ge=0, le=1)
    return_pct: float | None = Field(None, ge=0, le=1)
    note: str | None = Field(None, max_length=255)


class CostBatch(BaseModel):
    rows: list[CostRow] = Field(..., max_length=5000)


class ChannelCost(BaseModel):
    referral_pct: float = Field(..., ge=0, le=1)
    return_pct: float = Field(..., ge=0, le=1)


@router.get("/costs")
def costs() -> dict:
    """SKU có chạy QC 30 ngày gần nhất (Amazon SP hoặc Wayfair) hoặc đã có giá vốn, xếp theo Spend giảm dần."""
    last = fetch_one("SELECT GREATEST(MAX(report_date), (SELECT MAX(report_date) FROM fact_wf_product_daily)) AS d "
                     "FROM fact_product_daily")["d"] or date.today()
    start = last - timedelta(days=29)
    rows = fetch_all("""
        SELECT d.product_id, d.product_sku, d.title, d.group_name,
               COALESCE(a.spend, 0) AS amz_spend, COALESCE(w.spend, 0) AS wf_spend,
               c.landed_cost, c.amz_fee_unit, c.wf_fee_unit, c.amz_referral_pct, c.return_pct, c.note, c.updated_at
        FROM dim_product d
        LEFT JOIN (SELECT product_id, SUM(cost_usd) AS spend FROM fact_product_daily
                   WHERE report_date BETWEEN :s AND :e GROUP BY product_id) a ON a.product_id = d.product_id
        LEFT JOIN (SELECT l.product_id, SUM(f.cost_usd) AS spend FROM fact_wf_product_daily f
                   JOIN dim_wf_listing l ON l.listing_id = f.listing_id
                   WHERE f.report_date BETWEEN :s AND :e GROUP BY l.product_id) w ON w.product_id = d.product_id
        LEFT JOIN cfg_sku_cost c ON c.product_id = d.product_id
        WHERE a.spend > 0 OR w.spend > 0 OR c.product_id IS NOT NULL
        ORDER BY COALESCE(a.spend, 0) + COALESCE(w.spend, 0) DESC, d.product_sku""", {"s": start, "e": last})
    chans = {r["channel"]: r for r in fetch_all("SELECT channel, referral_pct, return_pct FROM cfg_channel_cost")}
    std, std_info = _std_cogs()
    for r in rows:
        r["std"] = std.get(r["product_id"])
    cover = {}
    for ch, key in (("amazon", "amz_spend"), ("wayfair", "wf_spend")):
        total = sum(r[key] for r in rows)
        done = sum(r[key] for r in rows if r["landed_cost"] is not None or r["std"])
        cover[ch] = done / total if total else None
    return jsonable({"rows": rows, "channels": chans, "coverage": cover, "std_cogs": std_info,
                     "window": {"start": start, "end": last}})


def _std_cogs() -> tuple[dict[int, dict], dict]:
    """Giá vốn chuẩn (sheet BOD) theo product_id: {"US": {"WH": .., "FBA": .., "CG": ..}, "CA": {...}, ...} tiền gốc."""
    try:
        rows = fetch_all("SELECT product_sku, product_id, market, basis, cogs, loaded_at FROM ref_std_cogs")
    except Exception:  # chưa chạy ETL tạo bảng
        return {}, {"loaded_at": None, "skus": 0, "unmatched": []}
    out = {}
    for r in rows:
        if r["product_id"] is not None:
            out.setdefault(r["product_id"], {}).setdefault(r["market"], {})[r["basis"]] = r["cogs"]
    unmatched = sorted({r["product_sku"] for r in rows if r["product_id"] is None})
    return out, {"loaded_at": max((r["loaded_at"] for r in rows), default=None),
                 "skus": len({r["product_sku"] for r in rows}), "unmatched": unmatched}


@router.put("/costs")
def save_costs(batch: CostBatch) -> dict:
    """Ghi đè giá vốn & phí của các SKU gửi lên. Dòng mọi ô trống = xóa. SKU không nhận ra được trả về `unknown`."""
    skus = [r.product_sku.strip() for r in batch.rows if r.product_id is None and r.product_sku]
    by_sku = {}
    if skus:
        names = {f"s{i}": v for i, v in enumerate(sorted(set(skus)))}
        found = fetch_all(f"SELECT product_sku, MIN(product_id) AS product_id, COUNT(*) AS n FROM dim_product "
                          f"WHERE product_sku IN ({', '.join(':' + k for k in names)}) GROUP BY product_sku", names)
        by_sku = {r["product_sku"].lower(): r["product_id"] for r in found if r["n"] == 1}
    saved, deleted, unknown, now = 0, 0, [], datetime.now()
    for r in batch.rows:
        pid = r.product_id if r.product_id is not None else by_sku.get((r.product_sku or "").strip().lower())
        if pid is None:
            unknown.append(r.product_sku or "?")
            continue
        vals = {k: getattr(r, k) for k in COST_FIELDS}
        if all(v is None for v in vals.values()) and not r.note:
            deleted += execute("DELETE FROM cfg_sku_cost WHERE product_id = :p", {"p": pid})
            continue
        execute("""INSERT INTO cfg_sku_cost (product_id, landed_cost, amz_fee_unit, wf_fee_unit, amz_referral_pct, return_pct,
                                            note, updated_at)
                   VALUES (:p, :landed_cost, :amz_fee_unit, :wf_fee_unit, :amz_referral_pct, :return_pct, :note, :t)
                   ON DUPLICATE KEY UPDATE landed_cost = VALUES(landed_cost), amz_fee_unit = VALUES(amz_fee_unit),
                       wf_fee_unit = VALUES(wf_fee_unit), amz_referral_pct = VALUES(amz_referral_pct),
                       return_pct = VALUES(return_pct), note = VALUES(note), updated_at = VALUES(updated_at)""",
                {"p": pid, **vals, "note": r.note, "t": now})
        saved += 1
    return {"saved": saved, "deleted": deleted, "unknown": unknown}


@router.put("/costs/channels/{channel}")
def save_channel(channel: str, cfg: ChannelCost) -> dict:
    if channel not in COST_CHANNELS:
        raise HTTPException(404, f"Không có kênh {channel}")
    if cfg.referral_pct + cfg.return_pct >= 1:
        raise HTTPException(422, "Phí sàn + hoàn trả phải nhỏ hơn 100%")
    execute("""INSERT INTO cfg_channel_cost (channel, referral_pct, return_pct, updated_at) VALUES (:c, :r, :x, :t)
               ON DUPLICATE KEY UPDATE referral_pct = VALUES(referral_pct), return_pct = VALUES(return_pct),
                                       updated_at = VALUES(updated_at)""",
            {"c": channel, "r": cfg.referral_pct, "x": cfg.return_pct, "t": datetime.now()})
    return {"ok": True}


# ---------------------------------------------------------------- mục tiêu tháng

class TargetRow(BaseModel):
    account_key: str = Field("", max_length=40)
    total_sales: float | None = Field(None, ge=0)
    ad_sales: float | None = Field(None, ge=0)
    spend: float | None = Field(None, ge=0)
    tacos: float | None = Field(None, ge=0, le=1)


class TargetBatch(BaseModel):
    rows: list[TargetRow] = Field(..., max_length=200)


def _month(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        raise HTTPException(422, "Tháng phải có dạng YYYY-MM")


def _module(channel: str):
    if channel not in CHANNELS:
        raise HTTPException(404, f"Không có kênh {channel}")
    return reports if channel == "amazon" else reports_wf


@router.get("/targets/{channel}")
def targets(channel: str, month: str = Query(..., pattern=r"^\d{4}-\d{2}$")) -> dict:
    """Mục tiêu tháng (cả kênh + từng tài khoản) kèm số thực tế từ đầu tháng tới ngày có dữ liệu mới nhất."""
    mod, first = _module(channel), _month(month)
    _, _, days = insights.month_window(first)
    fresh_col = "fact_campaign_daily" if channel == "amazon" else "fact_wf_campaign_daily"
    last = fetch_one(f"SELECT MAX(report_date) AS d FROM {fresh_col}")["d"] or first
    end = min(first.replace(day=days), last)
    actual = mod.month_by_account(Filters(start=first, end=end)) if end >= first else {}
    saved = insights.load_targets(first, channel)
    rows = [{"account_key": "", "label": "Cả kênh"}] + [{"account_key": a["id"], "label": a["label"]}
                                                         for a in mod.account_options()]
    for r in rows:
        if r["account_key"]:
            a = actual.get(r["account_key"], {})
        else:
            a = {k: sum(float(v.get(k) or 0) for v in actual.values()) for k in ("spend", "sales", "total_sales")}
        r.update({f"actual_{k}": a.get(k) for k in ("spend", "sales", "total_sales")})
        r.update({k: saved.get(r["account_key"], {}).get(k) for k in insights.TARGET_FIELDS})
    return jsonable({"month": first, "actual_end": end if end >= first else None, "days": days, "rows": rows})


@router.put("/targets/{channel}")
def save_targets(channel: str, batch: TargetBatch, month: str = Query(..., pattern=r"^\d{4}-\d{2}$")) -> dict:
    _module(channel)
    first, now, saved = _month(month), datetime.now(), 0
    for r in batch.rows:
        vals = {k: getattr(r, k) for k in insights.TARGET_FIELDS}
        if all(v is None for v in vals.values()):
            execute("DELETE FROM cfg_month_target WHERE month = :m AND channel = :c AND account_key = :a",
                    {"m": first, "c": channel, "a": r.account_key})
            continue
        execute("""INSERT INTO cfg_month_target (month, channel, account_key, total_sales, ad_sales, spend, tacos, updated_at)
                   VALUES (:m, :c, :a, :total_sales, :ad_sales, :spend, :tacos, :t)
                   ON DUPLICATE KEY UPDATE total_sales = VALUES(total_sales), ad_sales = VALUES(ad_sales),
                       spend = VALUES(spend), tacos = VALUES(tacos), updated_at = VALUES(updated_at)""",
                {"m": first, "c": channel, "a": r.account_key, **vals, "t": now})
        saved += 1
    return {"saved": saved}


# ---------------------------------------------------------------- chi phí QC Shopify theo tháng

class ShopSpendRow(BaseModel):
    sales_channel_id: int
    platform: str = Field(..., pattern="^(google|meta|other)$")
    spend_usd: float | None = Field(None, ge=0)  # None = xóa


class ShopSpendBatch(BaseModel):
    rows: list[ShopSpendRow] = Field(..., max_length=100)


@router.get("/shop/ad-spend")
def shop_ad_spend(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")) -> dict:
    """Chi phí QC đã nhập của tháng theo store × nền tảng, kèm doanh số Shopify tháng đó và tổng đã nhập 12 tháng gần nhất."""
    first = _month(month)
    _, _, days = insights.month_window(first)
    last_day = first.replace(day=days)
    hist_start = (first.replace(day=1) - timedelta(days=330)).replace(day=1)
    stores = fetch_all("""
        SELECT m.sales_channel_id, m.title AS store, m.country_code AS country
        FROM map_channel_node m
        WHERE m.code LIKE 'SPF-%'
          AND (EXISTS (SELECT 1 FROM fact_shop_line l WHERE l.sales_channel_id = m.sales_channel_id
                         AND l.report_date >= :since)
               OR EXISTS (SELECT 1 FROM cfg_shop_ad_spend s WHERE s.sales_channel_id = m.sales_channel_id))
        ORDER BY m.country_code = 'US' DESC, m.country_code, m.title""", {"since": hist_start})
    saved = fetch_all("SELECT sales_channel_id, platform, spend_usd, updated_at FROM cfg_shop_ad_spend WHERE month = :m",
                      {"m": first})
    sales = {r["sales_channel_id"]: r for r in fetch_all("""
        SELECT sales_channel_id, SUM(net_usd) AS sales, MAX(report_date) AS last_date FROM fact_shop_line
        WHERE report_date BETWEEN :s AND :e GROUP BY sales_channel_id""", {"s": first, "e": last_day})}
    for st in stores:
        r = sales.get(st["sales_channel_id"], {})
        st["sales"], st["last_date"] = r.get("sales"), r.get("last_date")
        for key, _ in reports_shop.PLATFORMS:
            st[key] = next((x["spend_usd"] for x in saved if x["sales_channel_id"] == st["sales_channel_id"]
                            and x["platform"] == key), None)
    history = fetch_all("""
        SELECT s.month, s.sales_channel_id, SUM(s.spend_usd) AS spend
        FROM cfg_shop_ad_spend s WHERE s.month BETWEEN :s AND :e GROUP BY s.month, s.sales_channel_id""",
                        {"s": hist_start, "e": first})
    hist_sales = fetch_all("""
        SELECT DATE_SUB(report_date, INTERVAL DAYOFMONTH(report_date) - 1 DAY) AS month, sales_channel_id,
               SUM(net_usd) AS sales
        FROM fact_shop_line WHERE report_date BETWEEN :s AND :e GROUP BY 1, 2""", {"s": hist_start, "e": last_day})
    return jsonable({"month": first, "days": days, "platforms": reports_shop.PLATFORMS, "stores": stores,
                     "history": history, "history_sales": hist_sales,
                     "updated_at": max((x["updated_at"] for x in saved if x["updated_at"]), default=None)})


@router.put("/shop/ad-spend")
def save_shop_ad_spend(batch: ShopSpendBatch, month: str = Query(..., pattern=r"^\d{4}-\d{2}$")) -> dict:
    first, now, saved, deleted = _month(month), datetime.now(), 0, 0
    known = {r["sales_channel_id"] for r in fetch_all("SELECT sales_channel_id FROM map_channel_node WHERE code LIKE 'SPF-%'")}
    for r in batch.rows:
        if r.sales_channel_id not in known:
            raise HTTPException(422, f"Kênh {r.sales_channel_id} không phải store Shopify")
        key = {"m": first, "c": r.sales_channel_id, "p": r.platform}
        if r.spend_usd is None:
            deleted += execute("DELETE FROM cfg_shop_ad_spend WHERE month = :m AND sales_channel_id = :c AND platform = :p",
                               key)
            continue
        execute("""INSERT INTO cfg_shop_ad_spend (month, sales_channel_id, platform, spend_usd, updated_at)
                   VALUES (:m, :c, :p, :v, :t)
                   ON DUPLICATE KEY UPDATE spend_usd = VALUES(spend_usd), updated_at = VALUES(updated_at)""",
                {**key, "v": r.spend_usd, "t": now})
        saved += 1
    return {"saved": saved, "deleted": deleted}
