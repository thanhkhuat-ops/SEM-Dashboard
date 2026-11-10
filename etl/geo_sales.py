"""Nhu cầu theo bang / tỉnh giao hàng (90 ngày) -> {mart}.fact_demand_region, cho bản đồ tồn kho.

Ba kênh có địa chỉ giao cấp bang trong DWH:
  - Amazon: s__amazon_orders.shipping_state(_code) / shipping_country; SL = quantity_ordered; bỏ đơn Canceled.
  - Wayfair: s__wayfair_orders.ship_to_state / ship_to_country; SL = quantity - cancelled_quantity; bỏ PO CANCELLED /
    REJECTED và đơn REPLACEMENT (như 75_wf_total_sales.sql).
  - Shopify: s__shopify_orders_v2.shipping_state / shipping_country; SL = quantity; bỏ đơn voided.
Đơn chưa có dòng hàng (Amazon Pending...) chỉ được đếm đơn, không có số lượng.
"""
from datetime import date, timedelta

from sqlalchemy import text

from app.geo import ship_region

WINDOW = 90

SOURCES = {
    "amazon": """
        SELECT o.shipping_country, o.shipping_state, o.shipping_state_code, COALESCE(NULLIF(d.product_id, 0), 0),
               DATE(o.purchased_date) >= :s30, COUNT(DISTINCT o.id), COALESCE(SUM(d.quantity_ordered), 0)
        FROM {stg}.s__amazon_orders o
        LEFT JOIN {stg}.s__amazon_order_details d ON d.amazon_order_id = o.id
        WHERE o.purchased_date >= :s AND o.purchased_date < :e AND COALESCE(o.status, '') <> 'Canceled'
          AND o.shipping_country IN ('US', 'CA', 'AU')
        GROUP BY 1, 2, 3, 4, 5""",
    "wayfair": """
        SELECT o.ship_to_country, o.ship_to_state, NULL, COALESCE(NULLIF(d.product_id, 0), 0),
               DATE(o.po_date) >= :s30, COUNT(DISTINCT o.id),
               COALESCE(SUM(GREATEST(d.quantity - COALESCE(d.cancelled_quantity, 0), 0)), 0)
        FROM {stg}.s__wayfair_orders o
        LEFT JOIN {stg}.s__wayfair_order_details d ON d.order_id = o.id
        WHERE o.po_date >= :s AND o.po_date < :e
          AND UPPER(COALESCE(o.status, '')) NOT IN ('CANCELLED', 'REJECTED')
          AND UPPER(COALESCE(o.order_type, '')) <> 'REPLACEMENT'
          AND o.ship_to_country IN ('US', 'CA', 'AU')
        GROUP BY 1, 2, 3, 4, 5""",
    "shopify": """
        SELECT o.shipping_country, o.shipping_state, NULL, COALESCE(NULLIF(d.product_id, 0), 0),
               DATE(o.created_at) >= :s30, COUNT(DISTINCT o.shopify_order_id), COALESCE(SUM(d.quantity), 0)
        FROM {stg}.s__shopify_orders_v2 o
        LEFT JOIN {stg}.s__shopify_order_details_v2 d ON d.order_id = o.shopify_order_id
        WHERE o.created_at >= :s AND o.created_at < :e AND COALESCE(o.financial_status, '') <> 'voided'
          AND o.shipping_country IN ('US', 'CA', 'AU')
        GROUP BY 1, 2, 3, 4, 5""",
}


def compute(conn, mart: str, stg: str, today: date | None = None) -> int:
    today = today or date.today()
    params = {"s": today - timedelta(days=WINDOW), "s30": today - timedelta(days=30), "e": today}
    agg: dict = {}
    for channel, sql in SOURCES.items():
        for cc, st, code, pid, in30, orders, units in conn.execute(text(sql.format(stg=stg)), params).fetchall():
            region = ship_region(cc, st, code) or "?"
            a = agg.setdefault((channel, cc, region, int(pid)), [0.0, 0.0, 0])
            a[0] += float(units or 0)
            a[1] += float(units or 0) if in30 else 0.0
            a[2] += int(orders or 0)
    conn.execute(text(f"DELETE FROM {mart}.fact_demand_region"))
    rows = [{"ch": ch, "c": c, "r": r, "p": p, "u90": v[0], "u30": v[1], "o": v[2], "d": today}
            for (ch, c, r, p), v in agg.items()]
    for i in range(0, len(rows), 5000):
        conn.execute(text(f"""INSERT INTO {mart}.fact_demand_region
            (channel, country_code, region, product_id, units_90, units_30, orders_90, as_of)
            VALUES (:ch, :c, :r, :p, :u90, :u30, :o, :d)"""), rows[i:i + 5000])
    return len(rows)
