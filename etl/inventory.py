"""Tốc độ bán và ngày dự kiến hết hàng cho từng nút tồn kho x sản phẩm -> ads_mart.inv_projection.

Nút: POOL-<nước> (kho nội bộ gộp), CG-<store> (CastleGate), FBA-<kênh> (tồn từ Google Sheet, etl/fba_sheet.py; kênh
không có trên sheet thì chưa có số tồn), ALL-<nước> (cả nước = POOL + CG + các nút FBA đã có số tồn). Doanh số của một
kênh trừ vào nút mà kênh đó lấy hàng (map_channel_node).

Tốc độ bán/ngày = 0.25 x r7 + 0.5 x r30 + 0.25 x r90, với rN = units N ngày / số ngày còn hàng trong N ngày (tối thiểu
N/4 để vài ngày còn hàng không thổi phồng tốc độ). Ngày còn hàng lấy từ lịch sử tồn (fact_inv_stock_daily); những ngày
trước ngày đầu tiên có lịch sử của nút (FBA mới có lịch sử từ khi đọc sheet) chưa biết nên coi là còn hàng. Mô phỏng
từng ngày trong HORIZON ngày: cộng hàng về theo ETA (ETA đã qua = về hôm nay), trừ tốc độ bán, ngày đầu tiên không đủ
hàng bán = ngày hết hàng. Hàng về có ETA quá hạn trên STALE_ETA_DAYS ngày bị bỏ qua. Shipment FBA còn đang chuẩn bị
(hàng vẫn nằm trong kho nội bộ) chỉ cộng cho nút FBA, không cộng cho cả nước.

Doanh số mất ước tính = số unit thiếu trong LOST_DAYS ngày tới (mỗi ngày: tốc độ bán − hàng còn để bán) x giá bán
trung bình USD/unit 90 ngày qua của chính nút đó (doanh thu / units, theo báo cáo bán hàng).
"""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

HORIZON = 180
STALE_ETA_DAYS = 60  # hàng về có ETA đã quá hạn hơn số ngày này coi là dữ liệu cũ chưa đóng, không tính
WEIGHTS = ((7, 0.25), (30, 0.5), (90, 0.25))
COVER_DAYS = 60  # "cần thêm" = lượng thiếu để đủ bán COVER_DAYS ngày, đã tính hàng về trong khoảng đó
LOST_DAYS = 90  # cửa sổ tính doanh số mất ước tính
STATUS_LIMITS = (("CRITICAL", 14), ("LOW", 30), ("OK", 90))  # tồn nhiều: đủ bán ≥ 90 ngày


def status_of(available: float, velocity: float, has_stock: bool) -> str:
    if not has_stock:
        return "NO_DATA"
    if velocity <= 0:
        return "NO_SALES" if available > 0 else "INACTIVE"
    if available <= 0:
        return "OOS"
    cover = available / velocity
    for name, limit in STATUS_LIMITS:
        if cover < limit:
            return name
    return "OVER"


def simulate(available: float, velocity: float, arrivals: dict[date, float], today: date,
             days: int = HORIZON) -> list[dict]:
    """Tồn từng ngày: đầu ngày cộng hàng về, bán tối đa velocity; short = phần không đủ hàng để bán."""
    stock, out = max(available, 0.0), []
    for i in range(days):
        d = today + timedelta(days=i)
        arrived = arrivals.get(d, 0.0)
        stock += arrived
        sold = min(stock, velocity)
        stock -= sold
        out.append({"date": d, "arrived": arrived, "sold": sold, "short": velocity - sold, "stock": stock})
    return out


def project(available: float, velocity: float, arrivals: dict[date, float], today: date) -> tuple[date | None, int | None]:
    """Ngày hết hàng (None nếu đủ hàng hết HORIZON ngày) và số ngày hết hàng trước lô hàng về kế tiếp."""
    if velocity <= 0:
        return None, None
    stockout = next((r["date"] for r in simulate(available, velocity, arrivals, today) if r["short"] > 1e-9), None)
    gap = None
    if stockout:
        later = sorted(d for d in arrivals if d > stockout)
        if later:
            gap = (later[0] - stockout).days
    return stockout, gap


def _load_nodes(conn: Connection, mart: str) -> dict:
    return {r[0]: {"type": r[1], "country": r[2], "has_stock": bool(r[3])}
            for r in conn.execute(text(f"SELECT node_id, node_type, country_code, has_stock FROM {mart}.dim_inv_node "
                                       "WHERE node_type IN ('POOL', 'CG', 'FBA')"))}


PREP_STAGE = "FBA: đang chuẩn bị"  # shipment chưa rời kho nội bộ: không phải hàng về của cả nước


def _bucket(nodes: dict, node_id: str) -> list[str]:
    """Nút nhận số liệu: chính nó, và nút cả nước nếu là POOL / CG / FBA đã có số tồn."""
    n = nodes.get(node_id)
    if not n:
        return []
    in_country = n["type"] in ("POOL", "CG") or (n["type"] == "FBA" and n["has_stock"])
    return [node_id] + ([f"ALL-{n['country']}"] if n["country"] and in_country else [])


def _arrival_targets(nodes: dict, node_id: str, stage: str | None) -> list[str]:
    return [b for b in _bucket(nodes, node_id) if not (stage == PREP_STAGE and b.startswith("ALL-"))]


INCOMING_SQL = """
    SELECT COALESCE(IF(n.node_type = 'WH' AND n.is_virtual = 0, CONCAT('POOL-', n.country_code), NULL), i.node_id) AS node_id,
           i.product_id, i.qty, i.eta, i.source, i.stage, i.ref
    FROM {mart}.fact_inv_incoming i LEFT JOIN {mart}.dim_inv_node n ON n.node_id = i.node_id
    WHERE i.node_id IS NOT NULL"""


def as_of_date(conn: Connection, mart: str) -> date:
    """Ngày tính = ngày sau ngày có doanh số cuối cùng (thường là hôm nay), không quá hôm nay."""
    last = conn.execute(text(f"SELECT MAX(report_date) FROM {mart}.fact_channel_sales_daily")).scalar()
    return min(date.today(), last + timedelta(days=1)) if last else date.today()


def node_series(conn: Connection, mart: str, node_id: str, product_id: int, history_days: int = 60) -> dict:
    """Dữ liệu đồ thị một SKU x nút: tồn thực tế history_days ngày qua (POOL / CG / cả nước) + mô phỏng HORIZON ngày tới
    với cùng tốc độ bán và hàng về như inv_projection."""
    row = conn.execute(text(f"""SELECT available, velocity, as_of FROM {mart}.inv_projection
                              WHERE node_id = :n AND product_id = :p"""), {"n": node_id, "p": product_id}).fetchone()
    if not row:
        return {}
    available, velocity = float(row[0] or 0), float(row[1] or 0)
    today = row[2] or as_of_date(conn, mart)
    nodes = _load_nodes(conn, mart)
    arrivals: dict = defaultdict(float)
    events = []
    for src_node, pid, qty, eta, source, stage, ref in conn.execute(
            text(INCOMING_SQL.format(mart=mart) + " AND i.product_id = :p"), {"p": product_id}):
        if node_id not in _arrival_targets(nodes, src_node, stage) or (eta and eta < today - timedelta(days=STALE_ETA_DAYS)):
            continue
        d = max(eta or today, today)
        arrivals[d] += float(qty or 0)
        events.append({"date": d, "eta": eta, "qty": float(qty or 0), "source": source, "stage": stage, "ref": ref})
    # lịch sử: nút trực tiếp; cả nước = tổng POOL + CG + FBA có số tồn của nước
    hist_nodes = [n for n in nodes if node_id in _bucket(nodes, n)]
    history = []
    if hist_nodes:
        start = today - timedelta(days=history_days)
        found = {r[0]: float(r[1] or 0) for r in conn.execute(text(
            f"""SELECT stock_date, SUM(on_hand) FROM {mart}.fact_inv_stock_daily
                WHERE product_id = :p AND stock_date >= :s AND stock_date < :t AND node_id IN :ns
                GROUP BY stock_date""").bindparams(bindparam("ns", expanding=True)),
            {"p": product_id, "s": start, "t": today, "ns": hist_nodes})}
        d = start
        while d < today:
            history.append({"date": d, "on_hand": found.get(d, 0.0)})  # trace chỉ lưu dòng tồn > 0
            d += timedelta(days=1)
    return {"as_of": today, "available": available, "velocity": velocity, "history": history,
            "projection": simulate(available, velocity, arrivals, today) if nodes.get(node_id, {}).get("has_stock", True) else [],
            "events": sorted(events, key=lambda e: e["date"])}


def compute(conn: Connection, mart: str, today: date | None = None) -> int:
    q = lambda sql, **p: conn.execute(text(sql), p).fetchall()  # noqa: E731
    today = today or as_of_date(conn, mart)
    end = today - timedelta(days=1)  # ngày đang diễn ra chưa đủ doanh số
    start90 = end - timedelta(days=89)

    nodes = _load_nodes(conn, mart)
    countries = sorted({n["country"] for n in nodes.values() if n["country"]})

    def bucket(node_id: str) -> list[str]:
        return _bucket(nodes, node_id)

    available: dict = defaultdict(float)
    on_hand: dict = defaultdict(float)
    for node_id, pid, oh, av in q(f"SELECT node_id, product_id, on_hand, available FROM {mart}.fact_inv_stock"):
        for b in bucket(node_id):
            available[(b, pid)] += float(av or 0)
            on_hand[(b, pid)] += float(oh or 0)

    # hàng về: container về kho nội bộ thật -> POOL của nước đó; FBA / CG -> nút tương ứng; PO chưa có nước -> bỏ qua
    arrivals: dict = defaultdict(lambda: defaultdict(float))
    for node_id, pid, qty, eta, _source, stage, _ref in q(INCOMING_SQL.format(mart=mart)):
        if eta and eta < today - timedelta(days=STALE_ETA_DAYS):
            continue
        d = max(eta or today, today)
        for b in _arrival_targets(nodes, node_id, stage):
            arrivals[(b, pid)][d] += float(qty or 0)

    units: dict = defaultdict(lambda: defaultdict(float))
    revenue: dict = defaultdict(float)
    sold_at: dict = defaultdict(set)  # (nút, sản phẩm) có bán trong 90 ngày -> các nút trực tiếp đã bán
    rows = q(f"""SELECT m.node_id, s.product_id, DATEDIFF(:end, s.report_date) AS age, SUM(s.units), SUM(s.revenue_usd)
                 FROM {mart}.fact_channel_sales_daily s JOIN {mart}.map_channel_node m ON m.sales_channel_id = s.sales_channel_id
                 WHERE s.report_date BETWEEN :start AND :end AND m.node_id IS NOT NULL
                 GROUP BY m.node_id, s.product_id, s.report_date""", start=start90, end=end)
    for node_id, pid, age, u, rev in rows:
        for b in bucket(node_id):
            revenue[(b, pid)] += float(rev or 0)
            sold_at[(b, pid)].add(node_id)
            for w, _ in WEIGHTS:
                if age < w:
                    units[(b, pid)][w] += float(u or 0)

    # ngày còn hàng trong cửa sổ: nút có lịch sử tồn; ALL = ngày mà ít nhất một nút của nước còn hàng
    days_in: dict = defaultdict(set)
    history_nodes = set()
    rows = q(f"""SELECT node_id, product_id, stock_date FROM {mart}.fact_inv_stock_daily
                 WHERE stock_date BETWEEN :start AND :end AND on_hand > 0""", start=start90, end=end)
    for node_id, pid, d in rows:
        history_nodes.add(node_id)
        for b in bucket(node_id):
            days_in[(b, pid)].add(d)
    # nút có số tồn nhưng lịch sử bắt đầu sau đầu cửa sổ (FBA đọc từ sheet): ngày trước đó chưa biết -> coi là còn hàng,
    # nếu nút đó có bán sản phẩm (áp cho chính nút và cả nước)
    first_hist = {r[0]: r[1] for r in q(f"SELECT node_id, MIN(stock_date) FROM {mart}.fact_inv_stock_daily GROUP BY node_id")}
    for nid, n in nodes.items():
        if n["type"] == "FBA" and n["has_stock"]:
            history_nodes.add(nid)
            first_hist.setdefault(nid, today)
    for key, sellers in sold_at.items():
        unknown_until = max((first_hist[s] for s in sellers if s in history_nodes and first_hist.get(s)), default=None)
        if unknown_until and unknown_until > start90:
            d = start90
            while d < unknown_until and d <= end:
                days_in[key].add(d)
                d += timedelta(days=1)
    instock: dict = defaultdict(lambda: defaultdict(int))
    for key, ds in days_in.items():
        for d in ds:
            age = (end - d).days
            for w, _ in WEIGHTS:
                if age < w:
                    instock[key][w] += 1
    has_history = history_nodes | {f"ALL-{nodes[h]['country']}" for h in history_nodes if h in nodes and nodes[h]["country"]}

    keys = set(available) | set(arrivals) | set(units)
    now = datetime.now().replace(microsecond=0)
    out = []
    for key in keys:
        node_id, pid = key
        if node_id.startswith("ALL-"):
            node_has_stock = True
        else:
            node_has_stock = nodes.get(node_id, {}).get("has_stock", False)
        u = units.get(key, {})
        rate = 0.0
        for w, weight in WEIGHTS:
            days = instock[key][w] if node_id in has_history else w
            rate += weight * (u.get(w, 0.0) / max(days, w / 4))
        av = available.get(key, 0.0)
        arr = arrivals.get(key, {})
        stockout, gap = project(av, rate, arr, today) if node_has_stock else (None, None)
        lost_units = sum(r["short"] for r in simulate(av, rate, arr, today, LOST_DAYS)) if node_has_stock and rate > 0 else 0.0
        price = revenue[key] / u[90] if u.get(90) and revenue.get(key) else None
        incoming = sum(arr.values())
        in30 = sum(q_ for d, q_ in arr.items() if d <= today + timedelta(days=30))
        in_cover = sum(q_ for d, q_ in arr.items() if d <= today + timedelta(days=COVER_DAYS))
        nxt = min(arr) if arr else None
        status = status_of(av, rate, node_has_stock)
        if status == "INACTIVE" and not incoming:
            continue
        out.append({
            "node_id": node_id, "product_id": pid, "on_hand": round(on_hand.get(key, 0.0)), "available": round(av),
            "incoming_qty": round(incoming), "incoming_30d": round(in30), "next_eta": nxt,
            "next_qty": round(arr[nxt]) if nxt else None,
            "units_7": u.get(7, 0.0), "units_30": u.get(30, 0.0), "units_90": u.get(90, 0.0),
            "instock_days_30": instock[key][30] if node_id in has_history else None,
            "instock_days_90": instock[key][90] if node_id in has_history else None,
            "velocity": round(rate, 4),
            "days_cover": round(av / rate, 1) if rate > 0 and node_has_stock else None,
            "days_cover_incl_incoming": ((stockout - today).days if stockout else HORIZON) if rate > 0 and node_has_stock else None,
            "stockout_date": stockout, "oos_days_before_next": gap,
            "need_60d": max(0, math.ceil(rate * COVER_DAYS - max(av, 0) - in_cover)) if node_has_stock and rate > 0 else None,
            "lost_units_90": round(lost_units, 1), "avg_price": round(price, 2) if price else None,
            "lost_sales_90": round(lost_units * price, 2) if price else None,
            "status": status, "as_of": today, "computed_at": now,
        })

    conn.execute(text(f"DELETE FROM {mart}.inv_projection"))
    conn.execute(text(f"DELETE FROM {mart}.dim_inv_node WHERE node_type = 'COUNTRY'"))
    if countries:
        conn.execute(text(f"""INSERT INTO {mart}.dim_inv_node (node_id, node_type, country_code, title, has_stock)
                             VALUES (:n, 'COUNTRY', :c, :t, 1)"""),
                     [{"n": f"ALL-{c}", "c": c, "t": f"Cả nước {c}"} for c in countries])
    cols = list(out[0]) if out else []
    for i in range(0, len(out), 2000):
        conn.execute(text(f"INSERT INTO {mart}.inv_projection ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"),
                     out[i:i + 2000])
    return len(out)
