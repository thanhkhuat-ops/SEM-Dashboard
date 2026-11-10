"""Báo cáo tồn kho: tồn theo nút, hàng đang về, doanh số theo kênh / nước và ngày dự kiến hết hàng.

Số liệu tồn là ảnh chụp mới nhất (không theo khoảng ngày); riêng doanh số theo kênh dùng khoảng ngày của bộ lọc.
Nút: ALL-<nước> = kho nội bộ + CastleGate + FBA đã có số tồn của nước, POOL-<nước> = kho nội bộ gộp, CG-<store> =
CastleGate một tài khoản, FBA-<kênh> = FBA (tồn từ Google Sheet, etl/fba_sheet.py), WH-<id> = từng kho nội bộ.
"""
import math
from datetime import date, timedelta

from app.config import settings
from app.db import fetch_all, fetch_one
from app.filters import Filters, Where
from app.geo import WAREHOUSE_REGION, cg_region
from app.metrics import col
from app.reports import _limit, _table
from app.viz import STATUS_ORDER as VIZ_STATUSES, chart, series

STATUS_LABELS = {
    "OOS": "Hết hàng", "CRITICAL": "Nguy cấp (< 14 ngày)", "LOW": "Thấp (< 30 ngày)", "OK": "Ổn",
    "OVER": "Tồn nhiều (≥ 90 ngày)", "NO_SALES": "Không bán 90 ngày", "INACTIVE": "Ngừng", "NO_DATA": "Chưa có số tồn",
}
STATUS_ORDER = "FIELD(j.status, 'OOS', 'CRITICAL', 'LOW', 'OK', 'OVER', 'NO_SALES', 'NO_DATA', 'INACTIVE')"
NODE_TYPES = {"ALL": "COUNTRY", "POOL": "POOL", "CG": "CG", "FBA": "FBA"}
FULFIL_LABELS = {"FBA": "Amazon FBA", "CG": "Wayfair CastleGate", "FBM": "FBM / marketplace tự giao",
                 "DROPSHIP": "Dropship (Wayfair…)", "WEBSITE": "Website", "WHOLESALE": "Bán sỉ", "MARKET": "Kho sàn khác",
                 "AVC": "Amazon Vendor"}
FBA_STALE_DAYS = 2  # số FBA trên sheet không đổi quá số ngày này -> cảnh báo


def _dm(t) -> str:
    return t.strftime("%d/%m %H:%M") if t else "–"


def fba_status() -> dict:
    """Trạng thái nguồn tồn FBA (Google Sheet): lần đọc thành công gần nhất, lần số liệu thay đổi gần nhất, lỗi."""
    try:
        reads = fetch_all("SELECT read_at, status, data_hash, note FROM fba_sheet_read ORDER BY read_at DESC LIMIT 200")
    except Exception:  # bảng chưa có (chưa chạy ETL sau khi nâng cấp)
        return {}
    ok = [r for r in reads if r["status"] == "OK"]
    if not ok:
        return {"failed": reads[0] if reads else None}
    last = ok[0]
    changed = last["read_at"]
    for r in ok[1:]:  # lùi lại khi số liệu vẫn y như lần đọc mới nhất
        if r["data_hash"] != last["data_hash"]:
            break
        changed = r["read_at"]
    failed = reads[0] if reads[0]["status"] != "OK" else None
    unchanged_days = (last["read_at"] - changed).days
    return {"read_at": last["read_at"], "changed_at": changed, "unchanged_days": unchanged_days,
            "stale": unchanged_days > FBA_STALE_DAYS, "failed": failed, "note": last.get("note")}


def fba_note() -> str:
    s = fba_status()
    if not s.get("read_at"):
        return ("Chưa có số tồn FBA (DWH đã ngừng cập nhật MYI và chưa đọc được Google Sheet tồn FBA), nên nút FBA chỉ có "
                "doanh số và hàng đang gửi lên, 'Cả nước' chỉ gồm kho nội bộ + CastleGate.")
    msg = (f"Tồn FBA (Megsu, DH Intra CA, Senno AU, Arozu, Hurav) lấy cột In Stock của Google Sheet 'inventory details', "
           f"đọc lúc {_dm(s['read_at'])}; sheet không ghi ngày dữ liệu. Hàng đang về FBA lấy từ shipment trên DWH. "
           "'Cả nước' = kho nội bộ + CastleGate + FBA. ")
    if s["stale"]:
        msg += (f"⚠ Số FBA trên sheet không đổi từ {_dm(s['changed_at'])} ({s['unchanged_days']} ngày), có thể sheet "
                "không còn được cập nhật. ")
    if s.get("failed"):
        msg += f"⚠ Lần đọc sheet gần nhất ({_dm(s['failed']['read_at'])}) bị lỗi, đang dùng lần đọc trước. "
    return msg


def _product_where(f: Filters, w: Where, alias: str = "p") -> None:
    w.add_in(f"{alias}.group_id", f.group_ids).add_in(f"{alias}.brand_id", f.brand_ids)


def _node_where(opts: dict, w: Where, alias: str = "n") -> None:
    node = opts.get("node", "ALL")
    if node in NODE_TYPES:
        w.add(f"{alias}.node_type = :node_type", node_type=NODE_TYPES[node])
    country = opts.get("country") or ""
    if country:
        w.add(f"{alias}.country_code = :country", country=country)


STATUS_SHORT = {"OOS": "Hết hàng", "CRITICAL": "Nguy cấp", "LOW": "Thấp", "OK": "Ổn", "OVER": "Tồn nhiều",
                "NO_SALES": "Không bán"}
# nhóm hình thức bán cho đồ thị: thứ tự cố định = thứ tự màu
FULFIL_GROUPS = [("FBA", "Amazon FBA", ["FBA"]), ("CG", "CastleGate", ["CG"]), ("DROPSHIP", "Dropship", ["DROPSHIP"]),
                 ("FBM", "FBM / tự giao", ["FBM"]), ("WEBSITE", "Website", ["WEBSITE"]),
                 ("OTHER", "Khác", ["WHOLESALE", "MARKET", "AVC"])]
SOURCE_LABELS = {"CONTAINER": "Container về kho", "FBA_SHIPMENT": "Gửi lên FBA", "CG_ON_ORDER": "Gửi lên CastleGate",
                 "PO": "PO chưa đóng container"}
STAGE_ORDER = ["PO: chờ duyệt", "PO: đã duyệt", "PO: đang sản xuất", "Container: chuẩn bị", "Container: đang trên biển",
               "Container: đã cập cảng", "FBA: đang chuẩn bị", "FBA: đã gửi", "FBA: đang vận chuyển",
               "FBA: Amazon đang nhận", "CastleGate: đang gửi lên"]
GANTT_DAYS = 90


def _as_of() -> date:
    row = fetch_one("SELECT MAX(as_of) AS d FROM inv_projection")
    return (row or {}).get("d") or date.today()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------- đơn vị: units hoặc container
# opts["qty_unit"] = "cont": mọi số lượng (tồn, đang về, đã bán, tốc độ bán...) quy ra container 40HQ theo thể tích
# sản phẩm (dim_product.volume, CBM/unit) / settings.container_cbm. Số ngày, tiền, số SKU không đổi.
QTY_KEYS = {"on_hand", "available", "incoming", "units_30", "velocity", "reserved", "qty", "incoming_qty", "incoming_30d",
            "next_qty", "need_60d", "units_7", "units_90", "lost_units_90", "units", "per_day", "u_fba", "u_cg", "u_ds",
            "u_fbm", "u_web", "u_other", "fulfillable", "unfulfillable", "on_order"}


def _cont(opts: dict) -> bool:
    return opts.get("qty_unit") == "cont"


def _qf(opts: dict, alias: str = "p") -> str:
    """Hệ số nhân số lượng trong SQL: 1 (units) hoặc CBM/unit / CBM một container (SKU thiếu thể tích = 0)."""
    return f"(COALESCE({alias}.volume, 0) / {float(settings.container_cbm)})" if _cont(opts) else "1"


def _apply_unit(result: dict, opts: dict) -> dict:
    """Chế độ container: cột / thẻ / đồ thị số lượng hiển thị 2 số lẻ, kèm chú thích đơn vị."""
    if not _cont(opts):
        result["qty_unit"] = "unit"
        return result
    result["qty_unit"] = "cont"
    for t in result.get("tables") or []:
        for c in t["columns"]:
            if c["key"] in QTY_KEYS and c["fmt"] in ("int", "num2"):
                c["fmt"] = "num2"
                c["label"] = c["label"].replace("Units", "Cont").replace("unit", "cont")
    for card in result.get("cards") or []:
        if card.get("qty"):
            card["fmt"] = "num2"
            card["label"] += " (cont)"
    for v in result.get("viz") or []:
        if v.get("qty"):
            v["unit"] = "cont"
            v["title"] = v["title"].replace("Units", "Container")
    note = (f"Đơn vị: container 40HQ = {settings.container_cbm:g} CBM, quy đổi theo thể tích từng sản phẩm; SKU chưa có "
            "thể tích không được tính. ")
    result["note"] = note + (result.get("note") or "")
    return result


def _label(rows: list[dict]) -> None:
    for r in rows:
        if "status" in r:
            r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])


# ---------------------------------------------------------------- tổng quan

# vị trí của hàng: (khóa, nhãn, nhóm). Nhóm STOCK = đã nằm trong kho (on hand), PIPE = chưa tới kho / sàn.
LOCATIONS = [("LOCAL", "Kho nội bộ", "STOCK"), ("CG", "CastleGate", "STOCK"), ("FBA", "FBA", "STOCK"),
             ("FBA_IN", "Đang gửi lên FBA", "PIPE"), ("CG_IN", "Đang gửi lên CastleGate", "PIPE"),
             ("CONTAINER", "Container về kho", "PIPE"), ("PO", "PO chưa đóng container", "PIPE")]
LOC_LABELS = {k: v for k, v, _ in LOCATIONS}
LOC_NODE_TYPE = {"LOCAL": "POOL", "CG": "CG", "FBA": "FBA"}
LOC_SOURCE = {"FBA_IN": "FBA_SHIPMENT", "CG_IN": "CG_ON_ORDER", "CONTAINER": "CONTAINER", "PO": "PO"}
NO_COUNTRY = "Chưa phân nước"
PREP_STAGE = "FBA: đang chuẩn bị"


def _locations(opts: dict) -> list[str]:
    """Bộ lọc Vị trí tồn -> danh sách khóa vị trí được xem."""
    loc = opts.get("loc") or ""
    if loc in ("STOCK", "PIPE"):
        return [k for k, _, g in LOCATIONS if g == loc]
    if loc in LOC_LABELS:
        return [loc]
    return [k for k, _, _ in LOCATIONS]


def _where_is(f: Filters, opts: dict, locs: list[str]) -> list[dict]:
    """Số lượng theo sản phẩm x nước x vị trí. Kho = on hand của nút POOL / CG / FBA; đang về = fact_inv_incoming
    (shipment FBA còn đang chuẩn bị không tính vì hàng vẫn nằm trong kho nội bộ)."""
    q = _qf(opts)
    country = opts.get("country") or ""
    out = []
    types = [LOC_NODE_TYPE[k] for k in locs if k in LOC_NODE_TYPE]
    if types:
        w = Where().add_in("n.node_type", types)
        _product_where(f, w)
        if country:
            w.add("n.country_code = :country", country=country)
        for r in fetch_all(f"""
                SELECT n.node_type, n.country_code, s.product_id, SUM(s.on_hand * {q}) AS qty
                FROM fact_inv_stock s JOIN dim_inv_node n ON n.node_id = s.node_id
                LEFT JOIN dim_product p ON p.product_id = s.product_id
                {w.sql()} GROUP BY n.node_type, n.country_code, s.product_id HAVING qty <> 0""", w.params):
            loc = next(k for k, t in LOC_NODE_TYPE.items() if t == r["node_type"])
            out.append({"loc": loc, "country": r["country_code"] or NO_COUNTRY, "product_id": r["product_id"],
                        "qty": r["qty"]})
    sources = [LOC_SOURCE[k] for k in locs if k in LOC_SOURCE]
    if sources:
        w = Where().add_in("i.source", sources).add("COALESCE(i.stage, '') <> :prep", prep=PREP_STAGE)
        _product_where(f, w)
        if country:
            w.add("i.country_code = :country", country=country)
        for r in fetch_all(f"""
                SELECT i.source, i.country_code, i.product_id, SUM(i.qty * {q}) AS qty
                FROM fact_inv_incoming i LEFT JOIN dim_product p ON p.product_id = i.product_id
                {w.sql()} GROUP BY i.source, i.country_code, i.product_id HAVING qty > 0""", w.params):
            loc = next(k for k, src in LOC_SOURCE.items() if src == r["source"])
            out.append({"loc": loc, "country": r["country_code"] or NO_COUNTRY, "product_id": r["product_id"],
                        "qty": r["qty"]})
    return out


# vị trí tồn -> nhóm kênh bán lấy hàng từ đó (map_channel_node): FBA, CastleGate, kho nội bộ (dropship / FBM / web / sỉ)
LOC_SALES = {"LOCAL": "local", "CG": "cg", "FBA": "fba"}
SALES_LABELS = {"local": "Bán từ kho nội bộ 30 ngày", "cg": "Bán CG 30 ngày", "fba": "Bán FBA 30 ngày"}


def _sales_30_by_place(f: Filters, opts: dict, country: str) -> dict:
    """(product_id, nước) -> {"fba", "cg", "local": số bán 30 ngày gần nhất có số liệu}."""
    q = _qf(opts)
    w = Where()
    _product_where(f, w)
    if country:
        w.add("m.country_code = :country", country=country)
    out: dict = {}
    for r in fetch_all(f"""
            SELECT s.product_id, m.country_code,
                   SUM(IF(m.fulfil_type = 'FBA', s.units, 0) * {q}) AS fba, SUM(IF(m.fulfil_type = 'CG', s.units, 0) * {q}) AS cg,
                   SUM(IF(m.node_id LIKE 'POOL-%', s.units, 0) * {q}) AS local
            FROM fact_channel_sales_daily s JOIN map_channel_node m ON m.sales_channel_id = s.sales_channel_id
            LEFT JOIN dim_product p ON p.product_id = s.product_id
            WHERE s.report_date > (SELECT MAX(report_date) FROM fact_channel_sales_daily) - INTERVAL 30 DAY
              {('AND ' + ' AND '.join(w.clauses)) if w.clauses else ''}
            GROUP BY s.product_id, m.country_code""", w.params):
        out[(r["product_id"], r["country_code"])] = {"fba": r["fba"] or 0, "cg": r["cg"] or 0, "local": r["local"] or 0}
    return out


def _sku_loc_cols(locs: list[str]) -> list[dict]:
    cols = []
    for k in locs:
        cols.append(col(k.lower(), LOC_LABELS[k], "int"))
        if k in LOC_SALES:
            key = LOC_SALES[k]
            cols += [col(f"s_{key}", SALES_LABELS[key], "int"), col(f"dc_{key}", "Đủ bán (ngày)", "num2")]
    return cols


def _cover_status(d):
    return "OOS" if d <= 0 else "CRITICAL" if d < 14 else "LOW" if d < 30 else "OK" if d < 90 else "OVER"


MAP_COUNTRIES = {"US": "Mỹ", "CA": "Canada", "AU": "Úc"}
DEMAND_CHANNELS = {"amazon": "Amazon", "wayfair": "Wayfair", "shopify": "Shopify"}


def _geo_maps(f: Filters, opts: dict, locs: list[str], countries: list[str]) -> tuple[list[dict], list[dict]]:
    """Bản đồ phân bổ theo bang / tỉnh: màu = tỷ trọng nhu cầu (Amazon + Wayfair + Shopify 90 ngày theo bang giao), bong bóng = on
    hand kho nội bộ / CastleGate nằm trong bang. FBA chưa có số theo trung tâm nên ghi riêng. -> (đồ thị, dòng bảng)."""
    q = _qf(opts)
    show_local, show_cg = "LOCAL" in locs, "CG" in locs
    wp = Where()
    _product_where(f, wp)
    pclause = (" AND " + " AND ".join(wp.clauses)) if wp.clauses else ""
    demand: dict = {}
    by_ch: dict = {}  # (nước, vùng) -> {kênh: SL}
    for r in fetch_all(f"""SELECT s.country_code, s.region, s.channel, SUM(s.units_90 * {q}) AS u, SUM(s.orders_90) AS o
            FROM fact_demand_region s LEFT JOIN dim_product p ON p.product_id = s.product_id
            WHERE 1 = 1 {pclause} GROUP BY s.country_code, s.region, s.channel""", wp.params):
        k = (r["country_code"], r["region"])
        u, o = demand.get(k, (0, 0))
        demand[k] = (u + (r["u"] or 0), o + (r["o"] or 0))
        by_ch.setdefault(k, {})[r["channel"]] = r["u"] or 0
    stock: dict = {}     # (nước, vùng) -> {"local", "cg", "whs": [[tên, loại, sl]]}
    unmapped: dict = {}  # nước -> [[tên, loại, sl]]

    def put(cc, region, kind, name, qty):
        if not qty:
            return
        if not region:
            unmapped.setdefault(cc, []).append([name, kind, round(qty, 2)])
            return
        s = stock.setdefault((cc, region), {"local": 0, "cg": 0, "whs": []})
        s["local" if kind == "Kho nội bộ" else "cg"] += qty
        s["whs"].append([name, kind, round(qty, 2)])
    if show_local:
        for r in fetch_all(f"""SELECT n.warehouse_id, n.title, n.country_code, SUM(s.on_hand * {q}) AS qty
                FROM fact_inv_stock s JOIN dim_inv_node n ON n.node_id = s.node_id
                LEFT JOIN dim_product p ON p.product_id = s.product_id
                WHERE n.node_type = 'WH' AND n.is_virtual = 0 {pclause}
                GROUP BY n.warehouse_id, n.title, n.country_code""", wp.params):
            cc, region = WAREHOUSE_REGION.get(int(r["warehouse_id"] or 0), (r["country_code"], None))
            put(cc, region, "Kho nội bộ", r["title"], r["qty"] or 0)
    if show_cg:
        for r in fetch_all(f"""SELECT d.cg_warehouse, SUM(d.on_hand * {q}) AS qty FROM fact_inv_cg_detail d
                LEFT JOIN dim_product p ON p.product_id = d.product_id WHERE 1 = 1 {pclause}
                GROUP BY d.cg_warehouse""", wp.params):
            cc, region = cg_region(r["cg_warehouse"])
            put(cc, region, "CastleGate", "CastleGate " + r["cg_warehouse"].title(), r["qty"] or 0)
    fba = {}
    if "FBA" in locs:
        for r in fetch_all(f"""SELECT n.country_code, SUM(s.on_hand * {q}) AS qty FROM fact_inv_stock s
                JOIN dim_inv_node n ON n.node_id = s.node_id LEFT JOIN dim_product p ON p.product_id = s.product_id
                WHERE n.node_type = 'FBA' {pclause} GROUP BY n.country_code""", wp.params):
            fba[r["country_code"]] = r["qty"] or 0

    maps, rows = [], []
    for cc in countries:
        if cc not in MAP_COUNTRIES:
            continue
        d_tot = sum(v[0] for (c, rg), v in demand.items() if c == cc and rg != "?") or 0
        s_tot = sum(v["local"] + v["cg"] for (c, _), v in stock.items() if c == cc) or 0
        codes = sorted({rg for (c, rg) in demand if c == cc and rg != "?"} | {rg for (c, rg) in stock if c == cc})
        regions = {}
        for rg in codes:
            du, do = demand.get((cc, rg), (0, 0))
            st = stock.get((cc, rg), {"local": 0, "cg": 0, "whs": []})
            d_sh = du / d_tot if d_tot else 0
            s_sh = (st["local"] + st["cg"]) / s_tot if s_tot else 0
            chs = by_ch.get((cc, rg), {})
            regions[rg] = {"demand": round(du, 2), "orders": do, "demand_share": round(d_sh, 4),
                           "channels": [[DEMAND_CHANNELS[c], round(chs[c], 2)] for c in DEMAND_CHANNELS if chs.get(c)],
                           "local": round(st["local"], 2), "cg": round(st["cg"], 2), "stock_share": round(s_sh, 4),
                           "whs": sorted(st["whs"], key=lambda x: -x[2])}
            rows.append({"country": cc, "region": rg, "demand": du, "orders": do, "demand_share": d_sh,
                         "d_amazon": chs.get("amazon", 0), "d_wayfair": chs.get("wayfair", 0),
                         "d_shopify": chs.get("shopify", 0),
                         "local": st["local"], "cg": st["cg"], "stock": st["local"] + st["cg"], "stock_share": s_sh,
                         "gap": s_sh - d_sh})
        kinds = " + ".join(k for k, on in (("kho nội bộ", show_local), ("CastleGate", show_cg)) if on) or "không có kho"
        maps.append(chart(
            f"map_{cc}", f"Phân bổ tồn kho và nhu cầu – {MAP_COUNTRIES[cc]}", "geo_map", list(regions),
            [series("Nhu cầu 90 ngày", "c1", [regions[k]["demand"] for k in regions])],
            country=cc, regions=regions, unmapped=unmapped.get(cc, []), fba=round(fba.get(cc, 0), 2),
            show_fba="FBA" in locs, demand_total=round(d_tot, 2), stock_total=round(s_tot, 2), qty=True,
            subtitle=f"Màu = tỷ trọng nhu cầu (số lượng bán 90 ngày qua Amazon + Wayfair + Shopify theo bang / tỉnh "
                     f"giao hàng). "
                     f"Vòng tròn = on hand {kinds} nằm trong bang. Rê chuột để xem chi tiết."))
    return maps, rows


def inv_overview(f: Filters, opts: dict) -> dict:
    locs = _locations(opts)
    country = opts.get("country") or ""
    q = _qf(opts)

    # ---------- tồn đang nằm ở đâu
    where = _where_is(f, opts, locs)
    countries_order = [c for c in ("US", "CA", "AU") if not country or c == country]
    countries_order += sorted({r["country"] for r in where} - set(countries_order) - {NO_COUNTRY})  # vd kho ở nước khác
    if any(r["country"] == NO_COUNTRY for r in where):
        countries_order.append(NO_COUNTRY)
    by_cl: dict = {}
    skus_cl: dict = {}
    for r in where:
        k = (r["country"], r["loc"])
        by_cl[k] = by_cl.get(k, 0) + (r["qty"] or 0)
        skus_cl.setdefault(k, set()).add(r["product_id"])
    loc_total = {k: sum(v for (_, l), v in by_cl.items() if l == k) for k in locs}
    stock_sum = sum(v for k, v in loc_total.items() if k in LOC_NODE_TYPE)
    pipe_sum = sum(v for k, v in loc_total.items() if k in LOC_SOURCE)
    cards = [{"label": LOC_LABELS[k], "value": loc_total[k], "fmt": "int", "qty": True,
              "note": "on hand" if k in LOC_NODE_TYPE else ("chưa phân nước" if k == "PO" else "chưa tới nơi")}
             for k in locs]
    if len(locs) > 1:
        cards.append({"label": "Tổng trong kho + đang về", "value": stock_sum + pipe_sum, "fmt": "int", "qty": True})
    where_chart = chart(
        "where", "Tồn kho đang nằm ở đâu", "hbar_stacked", countries_order,
        [series(LOC_LABELS[k], f"c{i + 1}", [round(by_cl.get((c, k), 0), 2) for c in countries_order])
         for i, (k, _, _) in enumerate(LOCATIONS) if k in locs],
        subtitle="On hand ở kho nội bộ / CastleGate / FBA và hàng chưa tới nơi, theo nước. PO chưa đóng container "
                 "chưa biết về nước nào.", qty=True)
    loc_rows = [{"country": c, "location": LOC_LABELS[k],
                 "kind": "Trong kho" if k in LOC_NODE_TYPE else "Đang về / đang gửi",
                 "skus": len(skus_cl.get((c, k), ())), "qty": by_cl.get((c, k), 0)}
                for c in countries_order for k in locs if by_cl.get((c, k))]

    # theo sản phẩm x nước: mỗi vị trí một cột, cạnh tồn FBA / CG / kho nội bộ là số bán 30 ngày của đúng hình thức đó
    sales = _sales_30_by_place(f, opts, country) if any(k in LOC_SALES for k in locs) else {}
    for (pid, cc), v in sales.items():  # SKU có bán nhưng hết sạch hàng vẫn hiện (tồn = 0)
        if any(v.get(LOC_SALES[k]) for k in locs if k in LOC_SALES):
            where.append({"loc": "_sales", "country": cc, "product_id": pid, "qty": 0})
    pids = sorted({int(r["product_id"]) for r in where}) or [0]
    names = {r["product_id"]: r for r in fetch_all(
        f"SELECT product_id, product_sku, title, group_name FROM dim_product WHERE product_id IN ({','.join(map(str, pids))})")}
    piv: dict = {}
    for r in where:
        row = piv.setdefault((r["product_id"], r["country"]), {"product_id": r["product_id"], "country": r["country"]})
        if r["loc"] != "_sales":
            row[r["loc"].lower()] = row.get(r["loc"].lower(), 0) + (r["qty"] or 0)
    where[:] = [r for r in where if r["loc"] != "_sales"]
    sku_rows = []
    for (pid, _), row in piv.items():
        info = names.get(pid, {})
        row.update({"product_sku": info.get("product_sku"), "product": info.get("title"),
                    "group_name": info.get("group_name"),
                    "in_stock": sum(row.get(k.lower(), 0) for k in locs if k in LOC_NODE_TYPE),
                    "pipeline": sum(row.get(k.lower(), 0) for k in locs if k in LOC_SOURCE)})
        row["total"] = row["in_stock"] + row["pipeline"]
        sv = sales.get((pid, row["country"]), {})
        for k, key in LOC_SALES.items():
            if k in locs:
                u = sv.get(key, 0)
                row[f"s_{key}"] = u
                stock = row.get(k.lower(), 0)
                row[f"dc_{key}"] = round(stock / (u / 30), 1) if u else None
        sku_rows.append(row)
    sku_rows.sort(key=lambda r: -r["total"])
    sku_total_rows = len(sku_rows)
    sku_rows = sku_rows[:_limit(opts, 500)]

    # ---------- sức khỏe tồn kho (dự báo) trong phạm vi vị trí đang xem
    node_types = [LOC_NODE_TYPE[k] for k in locs if k in LOC_NODE_TYPE]
    w = Where()
    _product_where(f, w)
    if country:
        w.add("n.country_code = :country", country=country)
    by_node = fetch_all(f"""
        SELECT n.node_id, n.node_type, n.country_code, n.title, n.has_stock, COUNT(*) AS skus,
               SUM(j.on_hand * {q}) AS on_hand, SUM(j.available * {q}) AS available, SUM(j.incoming_qty * {q}) AS incoming,
               SUM(j.units_30 * {q}) AS units_30, SUM(j.velocity * {q}) AS velocity,
               SUM(j.status = 'OOS') AS oos, SUM(j.status = 'CRITICAL') AS critical, SUM(j.status = 'LOW') AS low,
               SUM(j.status = 'OK') AS ok, SUM(j.status = 'OVER') AS over_stock, SUM(j.status = 'NO_SALES') AS no_sales
        FROM inv_projection j JOIN dim_inv_node n ON n.node_id = j.node_id
        LEFT JOIN dim_product p ON p.product_id = j.product_id
        {w.sql()}
        GROUP BY n.node_id, n.node_type, n.country_code, n.title, n.has_stock
        ORDER BY FIELD(n.node_type, 'COUNTRY', 'POOL', 'CG', 'FBA'), n.country_code, n.node_id""", w.params)
    for r in by_node:
        r["days_cover"] = (r["available"] / r["velocity"]) if r.get("velocity") and r.get("has_stock") else None
    nodes = [r for r in by_node if r["node_type"] in node_types]
    stock_labels = [LOC_LABELS[k] for k in locs if k in LOC_NODE_TYPE]
    if set(node_types) == {"POOL", "CG", "FBA"}:
        scope = [r for r in by_node if r["node_type"] == "COUNTRY"]
    else:  # một / hai loại nút: cộng các nút cùng nước (số SKU tính theo từng nút)
        agg: dict = {}
        for r in nodes:
            a = agg.setdefault(r["country_code"], {"node_type": "COUNTRY", "country_code": r["country_code"],
                                                   "has_stock": 0,
                                                   "title": f"{' + '.join(stock_labels)} {r['country_code']}"})
            a["has_stock"] = a["has_stock"] or r["has_stock"]
            for k in ("skus", "on_hand", "available", "incoming", "units_30", "velocity", "oos", "critical", "low",
                      "ok", "over_stock", "no_sales"):
                a[k] = (a.get(k) or 0) + (r.get(k) or 0)
        scope = [agg[c] for c in ("US", "CA", "AU") if c in agg]
        for r in scope:
            r["days_cover"] = (r["available"] / r["velocity"]) if r.get("velocity") and r.get("has_stock") else None
    scope_label = " + ".join(stock_labels)

    def total(key):
        return sum((r.get(key) or 0) for r in scope)
    map_countries = [c for c in ("US", "CA", "AU") if not country or c == country]
    maps, region_rows = _geo_maps(f, opts, locs, map_countries) if node_types else ([], [])
    viz = [where_chart] + maps
    tables = [
        _table("by_location", "Theo nước × vị trí", [col("country", "Nước"), col("location", "Vị trí"),
               col("kind", "Trạng thái"), col("skus", "Số SKU", "int"), col("qty", "Số lượng", "int")], loc_rows,
               extra_additive=("qty",)),
        dict(_table("where_sku", "Theo sản phẩm: tồn đang nằm ở đâu",
                    [col("product_sku", "SKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"),
                     col("country", "Nước")] + _sku_loc_cols(locs)
                    + [col("in_stock", "Trong kho", "int"), col("pipeline", "Đang về", "int"), col("total", "Tổng", "int")],
                    sku_rows, extra_additive=tuple(k.lower() for k in locs) + ("in_stock", "pipeline", "total")
                    + tuple(f"s_{LOC_SALES[k]}" for k in locs if k in LOC_SALES)),
             total_rows=sku_total_rows),
    ]
    if region_rows:
        region_rows.sort(key=lambda r: (r["country"], -r["demand"]))
        tables.append(_table("by_region", "Phân bổ theo bang / tỉnh (tồn kho so với nhu cầu)",
                             [col("country", "Nước"), col("region", "Bang / tỉnh"), col("orders", "Số đơn 90 ngày", "int"),
                              col("demand", "SL bán 90 ngày", "int"), col("d_amazon", "Amazon", "int"),
                              col("d_wayfair", "Wayfair", "int"), col("d_shopify", "Shopify", "int"), col("demand_share", "Tỷ trọng nhu cầu", "pct"),
                              col("local", "Tồn kho nội bộ", "int"), col("cg", "Tồn CastleGate", "int"),
                              col("stock_share", "Tỷ trọng tồn", "pct"), col("gap", "Chênh (tồn − nhu cầu)", "pct")],
                             region_rows, with_totals=False))
    if node_types:
        cards += [
            {"label": "Bán 30 ngày", "value": total("units_30"), "fmt": "int", "qty": True,
             "note": "trừ kênh FBA chưa có số tồn"},
            {"label": "SKU hết hàng", "value": total("oos"), "fmt": "int", "tone": "bad", "note": "theo từng nước"},
            {"label": "SKU nguy cấp < 14 ngày", "value": total("critical"), "fmt": "int", "tone": "bad"},
            {"label": "SKU thấp < 30 ngày", "value": total("low"), "fmt": "int", "tone": "warn"},
            {"label": "SKU tồn nhiều ≥ 90 ngày", "value": total("over_stock"), "fmt": "int"},
            {"label": "SKU có tồn, không bán 90 ngày", "value": total("no_sales"), "fmt": "int"},
        ]
        status_key = {"OOS": "oos", "CRITICAL": "critical", "LOW": "low", "OK": "ok", "OVER": "over_stock",
                      "NO_SALES": "no_sales"}
        node_opt = {"POOL": "POOL", "CG": "CG", "FBA": "FBA"}.get(node_types[0]) if len(node_types) == 1 else "ALL"
        viz.append(chart(
            "health", f"Sức khỏe tồn kho theo nước ({scope_label})", "hbar_stacked",
            [r["title"] for r in scope],
            [series(STATUS_SHORT[st], f"st:{st}", [r.get(status_key[st]) or 0 for r in scope],
                    {"opts": {"status": st}}) for st in VIZ_STATUSES],
            subtitle="Số SKU theo trạng thái. Bấm một đoạn để xem danh sách SKU.",
            label_filters=[{"opts": {"node": node_opt, "country": r["country_code"]}} for r in scope],
            goto={"tab": "inv_products", "table": "projection"}))
        cover_nodes = sorted([r for r in nodes if r.get("days_cover") is not None], key=lambda r: r["days_cover"])
        viz.append(chart(
            "cover", "Số ngày đủ bán theo nút tồn kho", "hbar",
            [r["title"] for r in cover_nodes],
            [series("Số ngày đủ bán", "c1", [round(min(r["days_cover"], 180), 1) for r in cover_nodes],
                    colors=[f"st:{_cover_status(r['days_cover'])}" for r in cover_nodes],
                    raw=[round(r["days_cover"], 1) for r in cover_nodes])],
            unit="days", refs=[{"value": 14, "label": "14 ngày"}, {"value": 30, "label": "30 ngày"}], max=180,
            subtitle="Tồn khả dụng / tốc độ bán của cả nút (trên 180 ngày hiển thị là 180). Bấm để xem SKU của nút.",
            label_filters=[{"opts": {"node": "", "country": "", "status": "RISK"}, "cols": {"node": [r["title"]]}}
                           for r in cover_nodes],
            goto={"tab": "inv_products", "table": "projection"}))
        status_cols = [col("oos", "Hết hàng", "int"), col("critical", "Nguy cấp", "int"), col("low", "Thấp", "int"),
                       col("over_stock", "Tồn nhiều", "int"), col("no_sales", "Không bán", "int")]
        base_cols = [col("skus", "Số SKU", "int"), col("on_hand", "On hand", "int"), col("available", "Khả dụng", "int"),
                     col("incoming", "Đang về", "int"), col("units_30", "Bán 30 ngày", "int"),
                     col("velocity", "Bán / ngày", "num2"), col("days_cover", "Số ngày đủ bán", "num2")]
        tables += [
            _table("by_country", f"Theo nước ({scope_label})", [col("title", "Nước")] + base_cols + status_cols,
                   scope, with_totals=False),
            _table("by_node", "Theo nút tồn kho (tài khoản / kho)", [col("title", "Nút"), col("node_type", "Loại"),
                   col("country_code", "Nước")] + base_cols + status_cols, nodes, with_totals=False),
        ]
    if "LOCAL" in locs or "CONTAINER" in locs:
        ww = Where()
        _product_where(f, ww)
        if country:
            ww.add("n.country_code = :country", country=country)
        wh = fetch_all(f"""
            SELECT n.title, n.country_code, IF(n.is_virtual, 'Kho ảo (không tính)', 'Kho thật') AS kind,
                   COUNT(DISTINCT IF(s.on_hand <> 0, s.product_id, NULL)) AS skus, SUM(s.on_hand * {q}) AS on_hand,
                   SUM(s.reserved * {q}) AS reserved, SUM(s.available * {q}) AS available,
                   (SELECT SUM(i.qty * {_qf(opts, 'pi')}) FROM fact_inv_incoming i
                    LEFT JOIN dim_product pi ON pi.product_id = i.product_id WHERE i.node_id = n.node_id) AS incoming
            FROM dim_inv_node n LEFT JOIN fact_inv_stock s ON s.node_id = n.node_id
            LEFT JOIN dim_product p ON p.product_id = s.product_id
            WHERE n.node_type = 'WH' {('AND ' + ' AND '.join(ww.clauses)) if ww.clauses else ''}
            GROUP BY n.node_id, n.title, n.country_code, n.is_virtual
            HAVING on_hand <> 0 OR incoming > 0
            ORDER BY n.is_virtual, n.country_code, on_hand DESC""", ww.params)
        tables.append(_table("by_warehouse", "Từng kho nội bộ / 3PL", [col("title", "Kho"), col("country_code", "Nước"),
                      col("kind", "Loại"), col("skus", "Số SKU có tồn", "int"), col("on_hand", "On hand", "int"),
                      col("reserved", "Giữ cho đơn", "int"), col("available", "Khả dụng", "int"),
                      col("incoming", "Container đang về", "int")], wh, with_totals=False))
    sources = [LOC_SOURCE[k] for k in locs if k in LOC_SOURCE]
    if sources:
        wi = Where().add_in("i.source", sources)
        _product_where(f, wi)
        if country:
            wi.add("i.country_code = :country", country=country)
        incoming = fetch_all(f"""
            SELECT i.source, i.stage, COALESCE(i.country_code, :nc) AS country, COUNT(DISTINCT i.product_id) AS skus,
                   SUM(i.qty * {q}) AS qty, MIN(i.eta) AS first_eta, MAX(i.eta) AS last_eta, SUM(i.eta < CURDATE()) AS overdue
            FROM fact_inv_incoming i LEFT JOIN dim_product p ON p.product_id = i.product_id
            {wi.sql()}
            GROUP BY i.source, i.stage, COALESCE(i.country_code, :nc)
            ORDER BY FIELD(i.source, 'PO', 'CONTAINER', 'FBA_SHIPMENT', 'CG_ON_ORDER'), country""",
                             {**wi.params, "nc": NO_COUNTRY})
        for r in incoming:
            r["source"] = SOURCE_LABELS.get(r["source"], r["source"])
        tables.append(_table("incoming", "Hàng đang về / đang gửi theo giai đoạn", [col("source", "Nguồn"),
                      col("stage", "Giai đoạn"), col("country", "Nước"), col("skus", "Số SKU", "int"),
                      col("qty", "Số lượng", "int"), col("first_eta", "ETA sớm nhất"), col("last_eta", "ETA muộn nhất"),
                      col("overdue", "Dòng quá ETA", "int")], incoming, with_totals=False))
    note = fba_note() + ("Kho nội bộ không gồm kho ảo Direct Import. Shipment FBA đang chuẩn bị vẫn tính trong kho nội "
                         "bộ, chưa tính vào 'Đang gửi lên FBA' (bảng giai đoạn vẫn liệt kê). ")
    if country and "PO" in locs:
        note += "PO chưa đóng container chưa có nước nên không hiện khi lọc theo nước. "
    return _apply_unit({"title": "Tổng quan tồn kho", "note": note, "cards": cards, "viz": viz, "tables": tables}, opts)


# ---------------------------------------------------------------- dự kiến hết hàng theo sản phẩm

def inv_products(f: Filters, opts: dict) -> dict:
    w = Where()
    _node_where(opts, w)
    _product_where(f, w)
    status = opts.get("status") or ""
    if status == "RISK":
        w.add("j.status IN ('OOS', 'CRITICAL', 'LOW')")
    elif status:
        w.add("j.status = :status", status=status)
    node_id = opts.get("node_id") or ""
    if node_id:
        w.add("j.node_id = :node_id", node_id=node_id)
    gw = Where()  # đồ thị lịch đứt hàng: cùng nút / nước / nhóm SP nhưng không lọc trạng thái
    gw._n = 100
    _node_where(opts, gw)
    _product_where(f, gw)
    if node_id:
        gw.add("j.node_id = :node_id", node_id=node_id)
    q = _qf(opts)
    rows = fetch_all(f"""
        SELECT j.node_id, j.product_id, n.title AS node, n.country_code, p.product_sku, p.title AS product,
               p.group_name, p.brand_name, j.on_hand * {q} AS on_hand, j.available * {q} AS available,
               j.incoming_qty * {q} AS incoming_qty, j.incoming_30d * {q} AS incoming_30d, j.next_eta,
               j.next_qty * {q} AS next_qty, j.units_7 * {q} AS units_7, j.units_30 * {q} AS units_30,
               j.units_90 * {q} AS units_90, j.instock_days_30, j.velocity * {q} AS velocity, j.days_cover,
               j.days_cover_incl_incoming, j.stockout_date, j.oos_days_before_next, j.need_60d * {q} AS need_60d, j.status,
               j.lost_units_90 * {q} AS lost_units_90, j.lost_sales_90, j.avg_price
        FROM inv_projection j
        JOIN dim_inv_node n ON n.node_id = j.node_id
        LEFT JOIN dim_product p ON p.product_id = j.product_id
        {w.sql()}
        ORDER BY {STATUS_ORDER}, j.lost_sales_90 DESC, j.velocity DESC
        LIMIT {_limit(opts, 2000)}""", w.params)
    top = fetch_all(f"""
        SELECT j.node_id, j.product_id, n.title AS node, p.product_sku, p.title AS product, j.available * {q} AS available,
               j.velocity * {q} AS velocity, j.stockout_date, j.oos_days_before_next, j.lost_units_90 * {q} AS lost_units_90,
               j.lost_sales_90, j.as_of
        FROM inv_projection j
        JOIN dim_inv_node n ON n.node_id = j.node_id
        LEFT JOIN dim_product p ON p.product_id = j.product_id
        {gw.sql() + (' AND' if gw.clauses else 'WHERE')} j.lost_sales_90 > 0
        ORDER BY j.lost_sales_90 DESC LIMIT 20""", gw.params)
    _label(rows)
    for r in rows:
        r["stockout_date"] = r["stockout_date"].isoformat() if isinstance(r.get("stockout_date"), date) else r.get("stockout_date")
        if r.get("days_cover_incl_incoming") == 180:
            r["stockout_date"] = "> 180 ngày"
    gantt_rows = []
    for t in top:
        as_of = t["as_of"] or date.today()
        start = (t["stockout_date"] - as_of).days if t.get("stockout_date") else GANTT_DAYS
        start = max(0, min(start, GANTT_DAYS))
        gap = t.get("oos_days_before_next")
        end = min(start + gap, GANTT_DAYS) if gap is not None else GANTT_DAYS
        gantt_rows.append({"label": f"{t['product_sku']} · {t['node']}", "node_id": t["node_id"],
                           "product_id": t["product_id"], "product_sku": t["product_sku"], "node": t["node"],
                           "product": t["product"], "stock_days": start, "gap_end": end,
                           "arrival_day": end if gap is not None and end < GANTT_DAYS else None,
                           "lost_sales": t["lost_sales_90"], "lost_units": t["lost_units_90"],
                           "velocity": t["velocity"], "available": t["available"]})
    as_of = (top[0]["as_of"] if top else None) or _as_of()
    viz = [
        chart("gantt", f"Lịch đứt hàng: {len(gantt_rows)} SKU mất doanh số nhiều nhất (90 ngày tới)", "gantt", [], [],
              unit="days", rows=gantt_rows, horizon=GANTT_DAYS, as_of=as_of.isoformat(),
              subtitle="Xanh = còn đủ bán, đỏ = đứt hàng tới khi lô hàng kế tiếp về (◆). Sắp theo doanh số mất ước tính. "
                       "Bấm một dòng để xem đường tồn và lọc bảng.",
              tables=["projection"], qty_unit="cont" if _cont(opts) else "unit"),
        chart("sku_line", "Đường tồn dự kiến", "sku_line", [], [], unit="int", qty=True,
              initial=({"node_id": gantt_rows[0]["node_id"], "product_id": gantt_rows[0]["product_id"],
                        "label": gantt_rows[0]["label"]} if gantt_rows else None)),
    ]
    cols = [col("node", "Nút"), col("product_sku", "SKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"),
            col("brand_name", "Brand"), col("status_label", "Trạng thái"),
            col("lost_sales_90", "DS mất ước tính 90 ngày", "money"), col("on_hand", "On hand", "int"),
            col("available", "Khả dụng", "int"), col("velocity", "Bán / ngày", "num2"), col("days_cover", "Đủ bán (ngày)", "num2"),
            col("stockout_date", "Dự kiến hết hàng"), col("oos_days_before_next", "Số ngày đứt hàng trước lô kế", "int"),
            col("next_eta", "Lô kế: ETA"), col("next_qty", "Lô kế: SL", "int"), col("incoming_qty", "Tổng đang về", "int"),
            col("incoming_30d", "Về trong 30 ngày", "int"), col("need_60d", "Thiếu để đủ 60 ngày", "int"),
            col("units_7", "Bán 7 ngày", "int"), col("units_30", "Bán 30 ngày", "int"), col("units_90", "Bán 90 ngày", "int"),
            col("instock_days_30", "Ngày còn hàng / 30", "int"), col("lost_units_90", "Unit thiếu 90 ngày", "num2"),
            col("avg_price", "Giá TB / unit (USD)", "money")]
    return _apply_unit({
        "title": "Dự kiến hết hàng theo sản phẩm",
        "viz": viz,
        "note": "Bán / ngày = 25% tốc độ 7 ngày + 50% tốc độ 30 ngày + 25% tốc độ 90 ngày, chỉ tính những ngày còn hàng. "
                "Dự kiến hết hàng đã cộng hàng đang về theo ETA (PO chưa phân kho không tính). Doanh số mất ước tính = "
                "unit thiếu trong 90 ngày tới × giá bán trung bình 90 ngày qua của nút. " + fba_note(),
        "tables": [_table("projection", "Sản phẩm × nút tồn kho", cols, rows, with_totals=False)],
    }, opts)


# ---------------------------------------------------------------- doanh số theo kênh / nước

def inv_channel_sales(f: Filters, opts: dict) -> dict:
    w = Where().add("s.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    _product_where(f, w)
    country = opts.get("country") or ""
    if country:
        w.add("m.country_code = :country", country=country)
    days = (f.end - f.start).days + 1
    q = _qf(opts)
    by_channel = fetch_all(f"""
        SELECT m.country_code, m.fulfil_type, m.title AS channel, m.node_id, SUM(s.units * {q}) AS units,
               SUM(s.revenue_usd) AS revenue, COUNT(DISTINCT s.product_id) AS skus
        FROM fact_channel_sales_daily s JOIN map_channel_node m ON m.sales_channel_id = s.sales_channel_id
        LEFT JOIN dim_product p ON p.product_id = s.product_id
        {w.sql()}
        GROUP BY m.sales_channel_id, m.country_code, m.fulfil_type, m.title, m.node_id
        ORDER BY units DESC""", w.params)
    total_units = sum(r["units"] or 0 for r in by_channel) or None
    for r in by_channel:
        r["fulfil_label"] = FULFIL_LABELS.get(r["fulfil_type"], r["fulfil_type"])
        r["share"] = (r["units"] / total_units) if total_units else None
        r["per_day"] = (r["units"] or 0) / days

    pivot = fetch_all(f"""
        SELECT s.product_id, MAX(p.product_sku) AS product_sku, MAX(p.title) AS product, MAX(p.group_name) AS group_name,
               m.country_code, SUM(s.units * {q}) AS units,
               SUM(IF(m.fulfil_type = 'FBA', s.units, 0) * {q}) AS u_fba, SUM(IF(m.fulfil_type = 'CG', s.units, 0) * {q}) AS u_cg,
               SUM(IF(m.fulfil_type = 'DROPSHIP', s.units, 0) * {q}) AS u_ds,
               SUM(IF(m.fulfil_type = 'FBM', s.units, 0) * {q}) AS u_fbm,
               SUM(IF(m.fulfil_type = 'WEBSITE', s.units, 0) * {q}) AS u_web,
               SUM(IF(m.fulfil_type NOT IN ('FBA', 'CG', 'DROPSHIP', 'FBM', 'WEBSITE'), s.units, 0) * {q}) AS u_other,
               SUM(s.revenue_usd) AS revenue
        FROM fact_channel_sales_daily s JOIN map_channel_node m ON m.sales_channel_id = s.sales_channel_id
        LEFT JOIN dim_product p ON p.product_id = s.product_id
        {w.sql()}
        GROUP BY s.product_id, m.country_code
        ORDER BY units DESC LIMIT {_limit(opts, 1000)}""", w.params)
    stock = {(r["product_id"], r["country_code"]): r for r in fetch_all(f"""
        SELECT j.product_id, n.country_code, j.available * {q} AS available, j.days_cover, j.status
        FROM inv_projection j JOIN dim_inv_node n ON n.node_id = j.node_id LEFT JOIN dim_product p ON p.product_id = j.product_id
        WHERE n.node_type = 'COUNTRY'""")}
    for r in pivot:
        s = stock.get((r["product_id"], r["country_code"])) or {}
        r["available"], r["days_cover"], r["status"] = s.get("available"), s.get("days_cover"), s.get("status")
        r["per_day"] = (r["units"] or 0) / days
    _label(pivot)
    weekly = fetch_all(f"""
        SELECT DATE_SUB(s.report_date, INTERVAL WEEKDAY(s.report_date) DAY) AS wk, m.fulfil_type, SUM(s.units * {q}) AS units
        FROM fact_channel_sales_daily s JOIN map_channel_node m ON m.sales_channel_id = s.sales_channel_id
        LEFT JOIN dim_product p ON p.product_id = s.product_id
        {w.sql()}
        GROUP BY wk, m.fulfil_type""", w.params)
    weeks = sorted({r["wk"] for r in weekly})
    group_of = {t: g for g, _, types in FULFIL_GROUPS for t in types}
    wk_val = {}
    for r in weekly:
        k = (r["wk"], group_of.get(r["fulfil_type"], "OTHER"))
        wk_val[k] = wk_val.get(k, 0) + (r["units"] or 0)
    labels_of = {g: [FULFIL_LABELS[t] for t in types] for g, _, types in FULFIL_GROUPS}
    weekly_chart = chart(
        "weekly", "Units bán theo tuần, theo hình thức bán", "bar_stacked",
        [f"{d:%d/%m}" for d in weeks],
        [series(name, f"c{i + 1}", [round(wk_val.get((d, g), 0), 2) for d in weeks], {"cols": {"fulfil_label": labels_of[g]}})
         for i, (g, name, _) in enumerate(FULFIL_GROUPS)],
        subtitle="Tuần bắt đầu thứ Hai; tuần đầu / cuối có thể chưa đủ 7 ngày. Bấm để lọc bảng theo hình thức bán.",
        tables=["by_channel"], qty=True)
    ctry = {}
    for r in by_channel:
        g = group_of.get(r["fulfil_type"], "OTHER")
        ctry.setdefault(r["country_code"], {}).setdefault(g, 0)
        ctry[r["country_code"]][g] += r["units"] or 0
    countries = sorted(ctry, key=lambda c: -sum(ctry[c].values()))
    share_chart = chart(
        "share", "Tỷ trọng hình thức bán theo nước", "hbar_stacked",
        [c or "?" for c in countries],
        [series(name, f"c{i + 1}", [round(ctry[c].get(g, 0) / (sum(ctry[c].values()) or 1), 4) for c in countries],
                {"cols": {"fulfil_label": labels_of[g]}}) for i, (g, name, _) in enumerate(FULFIL_GROUPS)],
        unit="pct", max=1, subtitle="% units trong kỳ. Bấm để lọc hai bảng theo nước và hình thức bán.",
        label_filters=[{"cols": {"country_code": [c]}} for c in countries], tables=["by_channel", "by_product"])
    return _apply_unit({
        "title": "Doanh số theo kênh bán và nước",
        "viz": [weekly_chart, share_chart],
        "note": f"Doanh số {f.start} → {f.end} ({days} ngày) từ báo cáo bán hàng của backend, combo đã tách ra sản phẩm con. "
                "Doanh thu quy USD theo tỷ giá ngày. Tồn khả dụng / số ngày đủ bán là của cả nước (kho nội bộ + CastleGate + FBA đã có số tồn).",
        "tables": [
            _table("by_channel", "Theo kênh bán", [col("country_code", "Nước"), col("fulfil_label", "Hình thức"),
                   col("channel", "Kênh"), col("units", "Units", "int"), col("per_day", "Units / ngày", "num2"),
                   col("share", "% units", "pct"), col("revenue", "Doanh thu", "money"), col("skus", "Số SKU", "int")],
                   by_channel, extra_additive=("units", "revenue")),
            _table("by_product", "Sản phẩm × nước", [col("product_sku", "SKU"), col("product", "Sản phẩm"),
                   col("group_name", "Nhóm"), col("country_code", "Nước"), col("units", "Units", "int"),
                   col("per_day", "Units / ngày", "num2"), col("u_fba", "FBA", "int"), col("u_cg", "CastleGate", "int"),
                   col("u_ds", "Dropship", "int"), col("u_fbm", "FBM", "int"), col("u_web", "Website", "int"),
                   col("u_other", "Khác", "int"), col("revenue", "Doanh thu", "money"), col("available", "Tồn khả dụng", "int"),
                   col("days_cover", "Đủ bán (ngày)", "num2"), col("status_label", "Trạng thái tồn")],
                   pivot, extra_additive=("units", "u_fba", "u_cg", "u_ds", "u_fbm", "u_web", "u_other", "revenue")),
        ],
    }, opts)


# ---------------------------------------------------------------- hàng đang về

def inv_incoming(f: Filters, opts: dict) -> dict:
    w = Where()
    _product_where(f, w)
    source = opts.get("source") or ""
    if source:
        w.add("i.source = :source", source=source)
    country = opts.get("country") or ""
    if country:
        w.add("i.country_code = :country", country=country)
    q = _qf(opts)
    rows = fetch_all(f"""
        SELECT i.source, i.stage, i.ref, COALESCE(n.title, 'Chưa phân kho') AS destination,
               COALESCE(i.country_code, '') AS country_code, p.product_sku, p.title AS product, p.group_name,
               i.qty * {q} AS qty, i.eta, IF(i.eta_estimated, 'Ước tính', '') AS eta_note,
               IF(i.eta < CURDATE(), DATEDIFF(CURDATE(), i.eta), NULL) AS overdue_days
        FROM fact_inv_incoming i
        LEFT JOIN dim_inv_node n ON n.node_id = i.node_id
        LEFT JOIN dim_product p ON p.product_id = i.product_id
        {w.sql()}
        ORDER BY i.eta, i.source LIMIT {_limit(opts, 3000)}""", w.params)
    as_of = _as_of()
    first_week = _monday(as_of)
    buckets = ["Quá ETA"] + [f"Tuần {first_week + timedelta(weeks=k):%d/%m}" for k in range(16)] + ["Sau 16 tuần"]

    def bucket(eta):
        if eta is None:
            return "Chưa có ETA"
        if eta < as_of:
            return "Quá ETA"
        k = (_monday(eta) - first_week).days // 7
        return buckets[1 + k] if k < 16 else "Sau 16 tuần"
    for r in rows:
        r["eta_bucket"] = bucket(r["eta"])
        r["source_label"] = SOURCE_LABELS.get(r["source"], r["source"])
    agg = fetch_all(f"""SELECT i.source, i.stage, i.eta, SUM(i.qty * {q}) AS qty FROM fact_inv_incoming i
        LEFT JOIN dim_product p ON p.product_id = i.product_id {w.sql()} GROUP BY i.source, i.stage, i.eta""", w.params)
    by_bucket, by_stage = {}, {}
    for r in agg:
        k = (bucket(r["eta"]), r["source"])
        by_bucket[k] = by_bucket.get(k, 0) + (r["qty"] or 0)
        by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + (r["qty"] or 0)
    sources = ["CONTAINER", "FBA_SHIPMENT", "CG_ON_ORDER", "PO"]
    used = [b for b in buckets if any(by_bucket.get((b, src)) for src in sources)]
    stages = [st for st in STAGE_ORDER if by_stage.get(st)] + [st for st in by_stage if st not in STAGE_ORDER]
    viz = [
        chart("arrivals", "Hàng về theo tuần", "bar_stacked", used,
              [series(SOURCE_LABELS[src], f"c{i + 1}", [round(by_bucket.get((b, src), 0), 2) for b in used],
                      {"cols": {"source_label": [SOURCE_LABELS[src]]}}) for i, src in enumerate(sources)],
              subtitle="Số lượng theo tuần của ETA (tuần bắt đầu thứ Hai). PO dùng ETA ước tính. Bấm để lọc bảng.",
              label_filters=[{"cols": {"eta_bucket": [b]}} for b in used], tables=["incoming"], qty=True),
        chart("stages", "Pipeline theo giai đoạn", "hbar", stages,
              [series("Số lượng", "c1", [round(by_stage[st], 2) for st in stages])],
              subtitle="Tổng số lượng đang ở từng giai đoạn. Bấm để lọc bảng.",
              label_filters=[{"cols": {"stage": [st]}} for st in stages], tables=["incoming"], qty=True),
    ]
    cols = [col("source_label", "Nguồn"), col("stage", "Giai đoạn"), col("eta_bucket", "Tuần về"), col("ref", "Chứng từ"),
            col("destination", "Về đâu"),
            col("country_code", "Nước"), col("product_sku", "SKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"),
            col("qty", "Số lượng", "int"), col("eta", "ETA"), col("eta_note", "ETA"), col("overdue_days", "Quá ETA (ngày)", "int")]
    return _apply_unit({
        "title": "Hàng đang về / pipeline",
        "viz": viz,
        "note": "PO: phần đặt hàng chưa đóng container (chưa biết về kho nào; trạng thái 1–3 suy từ nhật ký, ETA thiếu = ngày "
                "đặt + 90 ngày). Container: chưa nhập kho, ETA về kho. FBA: shipment chưa nhận xong (đã gửi − Amazon đã "
                "nhận; 'đang chuẩn bị' = hàng còn ở kho nội bộ). CastleGate: số Wayfair ghi nhận đang về, chưa có ETA "
                "(giả định 14 ngày). Hàng quá ETA trên 60 ngày không được tính vào dự báo.",
        "tables": [_table("incoming", "Chi tiết hàng đang về", cols, rows, extra_additive=("qty",))],
    }, opts)


# ---------------------------------------------------------------- CastleGate theo kho

def inv_castlegate(f: Filters, opts: dict) -> dict:
    w = Where()
    _product_where(f, w)
    q = _qf(opts)
    rows = fetch_all(f"""
        SELECT n.title AS account, d.cg_warehouse, p.product_sku, p.title AS product, p.group_name,
               d.on_hand * {q} AS on_hand, d.fulfillable * {q} AS fulfillable, d.unfulfillable * {q} AS unfulfillable,
               d.on_order * {q} AS on_order
        FROM fact_inv_cg_detail d
        LEFT JOIN dim_inv_node n ON n.node_id = CONCAT('CG-', d.store_account_id)
        LEFT JOIN dim_product p ON p.product_id = d.product_id
        {w.sql()}
        ORDER BY n.title, d.cg_warehouse, d.on_hand DESC LIMIT {_limit(opts, 3000)}""", w.params)
    agg = fetch_all(f"""SELECT n.title AS account, d.cg_warehouse, SUM(d.on_hand * {q}) AS on_hand
        FROM fact_inv_cg_detail d LEFT JOIN dim_inv_node n ON n.node_id = CONCAT('CG-', d.store_account_id)
        LEFT JOIN dim_product p ON p.product_id = d.product_id {w.sql()}
        GROUP BY n.title, d.cg_warehouse""", w.params)
    accounts = sorted({r["account"] for r in agg}, key=lambda a: -sum(r["on_hand"] or 0 for r in agg if r["account"] == a))
    whs = sorted({r["cg_warehouse"] for r in agg},
                 key=lambda x: -sum(r["on_hand"] or 0 for r in agg if r["cg_warehouse"] == x))
    val = {(r["account"], r["cg_warehouse"]): r["on_hand"] or 0 for r in agg}
    # bản đồ: tên kho bắt đầu bằng mã bang ("CA - LATHROP"); "CAN - ..." là Canada, hiện riêng ngoài bản đồ Mỹ
    by_region: dict[str, list] = {}
    for x in whs:
        code = x.split(" - ")[0].strip().upper()
        by_region.setdefault(code, []).append([x, round(sum(val.get((a, x), 0) for a in accounts), 2)])
    regions = sorted(by_region, key=lambda c: -sum(v for _, v in by_region[c]))
    viz = [chart("cg_map", "Bản đồ tồn CastleGate theo bang", "us_map", regions,
                 [series("On hand", "c1", [round(sum(v for _, v in by_region[c]), 2) for c in regions])],
                 subtitle="Màu càng đậm = càng nhiều on hand (cộng mọi kho trong bang). Bấm một bang để lọc bảng.",
                 label_filters=[{"cols": {"cg_warehouse": [x for x, _ in by_region[c]]}} for c in regions],
                 details=by_region, tables=["cg"], qty=True),
           chart("cg", "Tồn theo kho CastleGate", "hbar_stacked", whs,
                 [series(a.replace("CastleGate ", ""), f"c{i + 1}", [round(val.get((a, x), 0), 2) for x in whs],
                         {"cols": {"account": [a]}}) for i, a in enumerate(accounts[:8])],
                 subtitle="On hand theo kho, chia theo tài khoản. Bấm để lọc bảng.",
                 label_filters=[{"cols": {"cg_warehouse": [x]}} for x in whs], tables=["cg"], qty=True)]
    cols = [col("account", "Tài khoản"), col("cg_warehouse", "Kho CastleGate"), col("product_sku", "SKU"),
            col("product", "Sản phẩm"), col("group_name", "Nhóm"), col("on_hand", "On hand", "int"),
            col("fulfillable", "Bán được", "int"), col("unfulfillable", "Không bán được", "int"),
            col("on_order", "Đang gửi lên", "int")]
    return _apply_unit({"title": "Tồn CastleGate theo kho",
            "viz": viz,
            "note": "Wayfair tự phân bổ đơn CastleGate giữa các kho; doanh số chỉ có theo tài khoản nên ngày hết hàng tính "
                    "ở cấp tài khoản (tab Dự kiến hết hàng, nút CastleGate).",
            "tables": [_table("cg", "Tồn theo kho CastleGate", cols, rows,
                              extra_additive=("on_hand", "fulfillable", "unfulfillable", "on_order"))]}, opts)


# ---------------------------------------------------------------- đề xuất inbound FBA / CastleGate

INBOUND_DEFAULTS = {"lt_fba_us": 50, "lt_fba_ca": 30, "lt_fba_au": 25, "lt_cg": 21, "cover": 45, "reserve": 10}


def _opt_num(opts: dict, key: str) -> float:
    try:
        v = float(opts.get(key, INBOUND_DEFAULTS[key]))
        return v if v >= 0 else INBOUND_DEFAULTS[key]
    except (TypeError, ValueError):
        return INBOUND_DEFAULTS[key]


def inv_inbound(f: Filters, opts: dict) -> dict:
    """Số lượng nên gửi thêm lên từng tài khoản FBA / CastleGate để đủ bán `cover` ngày sau khi hàng tới nơi.

    Cần gửi = tốc độ bán × (thời gian gửi + cover) − tồn hiện tại − hàng đang gửi lên (làm tròn lên từng sản phẩm).
    Nguồn hàng = tồn khả dụng kho nội bộ cùng nước − phần giữ lại đủ `reserve` ngày bán cho kênh lấy hàng từ kho nội bộ
    (dropship, FBM, website, sỉ). Kho nội bộ không đủ thì chia cho nơi sắp hết hàng sớm nhất trước. SKU Clear Stock
    không đề xuất. Tốc độ bán lấy từ dự báo hết hàng (inv_projection)."""
    lt = {("FBA", "US"): _opt_num(opts, "lt_fba_us"), ("FBA", "CA"): _opt_num(opts, "lt_fba_ca"),
          ("FBA", "AU"): _opt_num(opts, "lt_fba_au")}
    lt_cg, cover, reserve = _opt_num(opts, "lt_cg"), _opt_num(opts, "cover"), _opt_num(opts, "reserve")
    country = opts.get("country") or ""
    target_type = opts.get("target") or ""
    w = Where().add("n.node_type IN ('FBA', 'CG', 'POOL')").add("(n.node_type <> 'FBA' OR n.has_stock = 1)")
    _product_where(f, w)
    if country:
        w.add("n.country_code = :country", country=country)
    proj = fetch_all(f"""
        SELECT j.node_id, n.node_type, n.country_code, n.title, n.sales_channel_id, j.product_id, p.product_sku,
               p.title AS product, p.group_name, j.available, j.incoming_qty, j.velocity, j.units_30
        FROM inv_projection j JOIN dim_inv_node n ON n.node_id = j.node_id
        LEFT JOIN dim_product p ON p.product_id = j.product_id
        {w.sql()}""", w.params)
    clear = {r["product_id"] for r in fetch_all("SELECT product_id FROM ref_clear_stock WHERE product_id IS NOT NULL")}
    # seller SKU / FNSKU theo kênh FBA: lấy từ shipment FBA gần nhất có sản phẩm đó
    ids: dict = {}
    for r in fetch_all(f"""SELECT f.sales_channel_id, d.product_id, d.sku, d.fnsku
            FROM `{settings.staging_schema}`.shipment__fbashipment_details d
            JOIN `{settings.staging_schema}`.shipment__fbashipments f ON f.id = d.fbashipment_id
            WHERE d.product_id > 0 ORDER BY f.id"""):
        ids[(r["sales_channel_id"], r["product_id"])] = (r["sku"], r["fnsku"])

    pool, reqs = {}, []
    for r in proj:
        av, inc, vel = float(r["available"] or 0), float(r["incoming_qty"] or 0), float(r["velocity"] or 0)
        if r["node_type"] == "POOL":
            pool[(r["country_code"], r["product_id"])] = (av, vel)
            continue
        if target_type and r["node_type"] != target_type:
            continue
        lead = lt_cg if r["node_type"] == "CG" else lt.get(("FBA", r["country_code"]), 30)
        if vel <= 0:
            continue
        target = vel * (lead + cover)
        need = max(0, math.ceil(target - max(av, 0) - inc - 1e-9))
        if need <= 0:
            continue
        sku, fnsku = ids.get((r["sales_channel_id"], r["product_id"]), (None, None)) if r["node_type"] == "FBA" else (None, None)
        reqs.append({**r, "type": "FBA" if r["node_type"] == "FBA" else "CastleGate", "available": av, "incoming": inc,
                     "velocity": vel, "lead": lead, "target": math.ceil(target), "need": need,
                     "days_left": (max(av, 0) + inc) / vel, "seller_sku": sku, "fnsku": fnsku})
    # chia nguồn kho nội bộ theo nước x sản phẩm: nơi sắp hết sớm nhất trước
    by_key: dict = {}
    for r in reqs:
        by_key.setdefault((r["country_code"], r["product_id"]), []).append(r)
    for (cc, pid), items in by_key.items():
        pav, pvel = pool.get((cc, pid), (0.0, 0.0))
        keep = math.ceil(pvel * reserve)
        left = max(0, math.floor(pav - keep))
        for r in sorted(items, key=lambda x: x["days_left"]):
            r["local_available"], r["local_keep"] = pav, keep
            if pid in clear:
                r["suggest"], r["note"] = 0, "Clear Stock: không gửi thêm"
            else:
                r["suggest"] = min(r["need"], left)
                left -= r["suggest"]
                r["note"] = ("" if r["suggest"] >= r["need"] else
                             "Kho nội bộ không đủ" if r["suggest"] else "Kho nội bộ hết hàng (sau phần giữ lại)")
            r["short"] = r["need"] - r["suggest"]
            r["cover_after"] = round((max(r["available"], 0) + r["incoming"] + r["suggest"]) / r["velocity"], 1)
            r["days_left"] = round(r["days_left"], 1)
    rows = sorted(reqs, key=lambda r: (r["country_code"], r["title"], -r["suggest"], r["days_left"]))

    sent = [r for r in rows if r["suggest"] > 0]
    def tot(key, typ=None):
        return sum(r[key] for r in rows if typ is None or r["type"] == typ)
    cards = [
        {"label": "Đề xuất gửi lên FBA", "value": tot("suggest", "FBA"), "fmt": "int",
         "note": f"{len({(r['node_id'], r['product_id']) for r in sent if r['type'] == 'FBA'})} SKU × tài khoản"},
        {"label": "Đề xuất gửi lên CastleGate", "value": tot("suggest", "CastleGate"), "fmt": "int",
         "note": f"{len({(r['node_id'], r['product_id']) for r in sent if r['type'] == 'CastleGate'})} SKU × tài khoản"},
        {"label": "Cần thêm nhưng kho nội bộ thiếu", "value": sum(r["short"] for r in rows if r["note"] != "Clear Stock: không gửi thêm"),
         "fmt": "int", "tone": "warn", "note": "phải chờ container / PO"},
        {"label": "SKU Clear Stock bỏ qua", "value": len({r["product_id"] for r in rows if r["note"].startswith("Clear")}),
         "fmt": "int"},
    ]
    nodes = sorted({r["title"] for r in rows}, key=lambda t: -sum(r["suggest"] for r in rows if r["title"] == t))
    viz = [chart("inbound", "Đề xuất gửi theo tài khoản", "hbar_stacked", nodes,
                 [series("Đề xuất gửi", "c1", [sum(r["suggest"] for r in rows if r["title"] == t) for t in nodes],
                         {"cols": {"title": None}}),
                  series("Thiếu (kho nội bộ không đủ)", "st:CRITICAL",
                         [sum(r["short"] for r in rows if r["title"] == t and not r["note"].startswith("Clear")) for t in nodes])],
                 subtitle="Số sản phẩm nên gửi thêm và phần còn thiếu vì kho nội bộ không đủ. Bấm để lọc bảng.",
                 label_filters=[{"cols": {"title": [t]}} for t in nodes], tables=["inbound"])]
    for s_ in viz[0]["series"]:
        s_.pop("filter", None)
    cols = [col("country_code", "Nước"), col("type", "Loại"), col("title", "Tài khoản"), col("product_sku", "SKU"),
            col("seller_sku", "Seller SKU"), col("fnsku", "FNSKU"), col("product", "Sản phẩm"), col("group_name", "Nhóm"),
            col("velocity", "Bán / ngày", "num2"), col("units_30", "Bán 30 ngày", "int"), col("available", "Tồn hiện tại", "int"),
            col("incoming", "Đang gửi lên", "int"), col("days_left", "Đủ bán hiện tại (ngày)", "num2"),
            col("lead", "Thời gian gửi (ngày)", "int"), col("target", f"Cần có (gửi + {cover:g} ngày)", "int"),
            col("need", "Cần gửi", "int"), col("suggest", "Đề xuất gửi", "int"), col("short", "Thiếu", "int"),
            col("cover_after", "Đủ bán sau khi gửi (ngày)", "num2"), col("local_available", "Kho nội bộ khả dụng", "int"),
            col("local_keep", f"Giữ lại {reserve:g} ngày", "int"), col("note", "Ghi chú")]
    note = (f"Cần gửi = tốc độ bán × (thời gian gửi + {cover:g} ngày) − tồn hiện tại − hàng đang gửi lên. Thời gian gửi: "
            f"FBA US {lt[('FBA', 'US')]:g}, CA {lt[('FBA', 'CA')]:g}, AU {lt[('FBA', 'AU')]:g} ngày, CastleGate {lt_cg:g} ngày "
            f"(đổi ở ô phía trên). Kho nội bộ giữ lại đủ {reserve:g} ngày bán cho dropship / FBM / website; phần còn lại chia "
            "cho nơi sắp hết hàng sớm nhất trước. Tốc độ bán = dự báo hết hàng (25% 7 ngày + 50% 30 ngày + 25% 90 ngày, chỉ "
            "ngày còn hàng). Chỉ đề xuất cho tài khoản đã có bán SKU; SKU Clear Stock (Google Sheet) không gửi thêm; chưa tính "
            "hạn mức lưu kho FBA và số sản phẩm mỗi thùng (1 sản phẩm = 1 thùng). Seller SKU / FNSKU lấy từ shipment FBA gần "
            "nhất. Bấm 'Tải CSV' ở bảng để xuất. " + fba_note())
    return {"title": "Đề xuất inbound FBA / CastleGate", "note": note, "cards": cards, "viz": viz,
            "tables": [_table("inbound", "Đề xuất gửi theo SKU × tài khoản", cols, rows,
                              extra_additive=("need", "suggest", "short", "units_30"))]}


INV_REPORTS = {
    "inv_overview": inv_overview,
    "inv_products": inv_products,
    "inv_channel_sales": inv_channel_sales,
    "inv_incoming": inv_incoming,
    "inv_castlegate": inv_castlegate,
    "inv_inbound": inv_inbound,
}


def sku_series(node_id: str, product_id: int, qty_unit: str = "unit") -> dict:
    """Đường tồn của một SKU x nút cho đồ thị (lịch sử 60 ngày + mô phỏng 120 ngày), theo units hoặc container."""
    from app.config import settings
    from app.db import get_engine
    from etl.inventory import node_series
    with get_engine().connect() as conn:
        data = node_series(conn, f"`{settings.mart_schema}`", node_id, product_id)
    if not data:
        return {}
    info = fetch_one("""SELECT n.title AS node, p.product_sku, p.title AS product FROM dim_inv_node n
                        LEFT JOIN dim_product p ON p.product_id = :p WHERE n.node_id = :n""", {"n": node_id, "p": product_id})
    data["projection"] = data["projection"][:120]
    data["qty_unit"] = "unit"
    if qty_unit == "cont":
        vol = (fetch_one("SELECT volume FROM dim_product WHERE product_id = :p", {"p": product_id}) or {}).get("volume") or 0
        k = vol / settings.container_cbm
        data["available"] *= k
        data["velocity"] *= k
        for h in data["history"]:
            h["on_hand"] *= k
        for r in data["projection"]:
            for key in ("arrived", "sold", "short", "stock"):
                r[key] *= k
        for e in data["events"]:
            e["qty"] *= k
        data["qty_unit"] = "cont"
        data["no_volume"] = not vol
    return {**data, **(info or {})}
