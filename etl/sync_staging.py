"""Đồng bộ các bảng staging mà ETL cần từ DWH (server khác) về schema staging trên MySQL nội bộ.

- Bảng danh mục / nhỏ: chép lại toàn bộ mỗi lần.
- Bảng report theo ngày: xóa rồi chép lại đúng khoảng ngày đang nạp.
- Đơn hàng: theo purchased_date; chi tiết đơn lấy theo các đơn trong khoảng đó.
- Bid keyword (sem__keywords_base_daily ~26GB, sem_wayfair__keyword_info_daily ~4 triệu dòng): chỉ tra theo khóa
  chính những cặp keyword x ngày có trong report đã chép về và còn thiếu ở bản sao, không quét cả bảng.
- Một số bảng chỉ chép các cột cần dùng (COLUMNS): bỏ dữ liệu nhạy cảm và cột text lớn không dùng tới.
Bảng được tạo ở bản sao bằng SHOW CREATE TABLE của nguồn, cộng thêm index theo cột ngày để ETL chạy nhanh.
"""
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

import pymysql
from pymysql.cursors import SSCursor

BATCH = 5000
BID_BATCH = 1000

# (bảng, điều kiện lọc ở nguồn)
FULL_TABLES = [
    ("amazon_profiles_base", None), ("s_sales_store_accounts", None), ("s_sales_store_companies", None),
    ("sem__portfolios_base", None), ("sem__campaigns_base", None), ("sem__adgroups_base", None),
    ("sem__targetings_base", None), ("sem__sb_placement_mapping", None),
    ("prd_product", None), ("prd_brands", None), ("prd_groups", None), ("prd_amazon_listings", None), ("prd_asin", None),
    ("exchange_rate_usd", "currency_code IN ('USD', 'CAD', 'AUD', 'MXN')"),
    ("sem__sp_customer_search_term", None), ("sem__sb_customer_search_term", None),
    ("prd_product_assigned", None), ("s_users", None),
    # Wayfair: danh mục quảng cáo, map listing -> sản phẩm, kênh bán, đơn hàng (để tính TACoS)
    ("wayfair_accounts", None), ("sem_wayfair__campaign_info", None), ("sem_wayfair__keyword_info", None),
    ("sem_wayfair__keyword_matchtype", None), ("sem_wayfair__product_info", None),
    ("sem_wayfair__search_term_info", None), ("wayfair_map_sku_product_id", None),
    ("sem_wayfair__product_info_daily", None),  # trạng thái listing theo ngày (~200 nghìn dòng)
    ("sem_wayfair_map_sku_product_id", None), ("prd_wayfair_products", None),
    ("s_sales_channels", None), ("s_sales_marketplaces", None), ("s_country", None),
    ("s__wayfair_orders", None), ("s__wayfair_order_details", None),
    # Shopify (website): bảng v2 lấy qua API, cập nhật lại 3 tháng gần nhất mỗi ngày; vài nghìn đơn nên chép toàn bộ
    ("s__shopify_orders_v2", None), ("s__shopify_order_details_v2", None), ("s__shopify_order_refund_line_items", None),
    # Tồn kho: kho nội bộ / 3PL, CastleGate, combo, hàng đang về (PO, container, shipment lên FBA / CastleGate)
    ("wh_warehouses", None), ("wh_product_inventory", None),
    ("wh_product_inventory_available", "last_updated_dwh >= CURDATE() - INTERVAL 2 DAY"),
    ("wh_wayfair_castlegate_inventory", None), ("wh_wayfair_castlegate_warehouses", None),
    ("prd_productcombo", None), ("s_sales_fulfill_methods", None),
    ("pu_sc_purchase_orders", None), ("pu_sc_purchase_order_details", None),
    ("pu_shipments", None), ("pu_shipment_containers", None), ("pu_shipment_container_details", None),
    ("sc_delivery_receipts", None), ("sc_delivery_receipt_containers", None),
    ("shipment__fbashipments", None), ("shipment__fbashipment_details", None),
    ("shipment__wayfair_castlegate_inbound_shipments", None),
    ("shipment__wayfair_castlegate_inbound_shipment_details", None),
    # P&L công ty (etl/pnl.py): tham số phí kênh / hoàn hàng / allowance do team tài chính duy trì trên DWH,
    # phí ước tính FBA theo SKU, phí kho 3PL theo tháng × SKU
    ("input_pl_channel_fee_param", None), ("input_pl_return_fee_rate", None), ("input_pl_wayfair_allowance", None),
    ("input_pl_shopify_source_fee", None), ("input_pl_shopify_web_source", None), ("input_pl_operation_fee_param", None),
    ("input_forecast_sales_return_rate", None), ("fee__shopify_channel_fee_rate", None),
    ("amazon_fba_fee_preview", None), ("fee__warehouse_local", None),
]
# Chỉ chép các cột này, cột đầu tiên là khóa chính. s_users ở nguồn có cả mật khẩu đã băm và API token;
# đơn Wayfair có tên/địa chỉ/điện thoại khách; attribute_and_option (longtext) chiếm phần lớn dung lượng
# của report keyword optimization mà báo cáo không dùng.
COLUMNS = {
    "s_users": ("id", "name", "email", "code", "manager_id", "type", "published"),
    # bang / nước giao hàng (cấp bang, không lấy tên / địa chỉ chi tiết) cho bản đồ nhu cầu ở tab Tồn kho
    "s__wayfair_orders": ("id", "sales_channel_id", "po_number", "order_type", "po_date", "status", "customer_country",
                          "ship_to_state", "ship_to_country"),
    "s__wayfair_order_details": ("id", "order_id", "product_id", "item_number", "wayfair_sku", "quantity",
                                 "wholesale_price", "cancelled_quantity"),
    # đơn Shopify có email, địa chỉ giao / thanh toán của khách: không chép (chỉ lấy bang / nước giao cho bản đồ nhu cầu);
    # customer_id chỉ dùng để biết khách mới / cũ
    "s__shopify_orders_v2": ("shopify_order_id", "sales_channel_id", "customer_id", "created_at", "total_price",
                             "subtotal_price", "total_tax", "total_discounts", "financial_status", "fulfillment_status",
                             "currency", "source_name", "shipping_state", "shipping_country"),
    "s__shopify_order_details_v2": ("line_item_id", "order_id", "product_id", "sku", "quantity", "price", "total_discount",
                                    "discount_allocations_amount", "fulfillment_status"),
    "s__shopify_order_refund_line_items": ("id", "line_item_id", "order_id", "refund_id", "quantity", "subtotal",
                                           "total_tax"),
    "sem_wayfair__wsp_keyword_optimization": (
        "id", "campaign_id", "keyword_info_id", "store_url", "campaign_date_run", "clicks", "impressions", "spend",
        "attr_rsales_wview_through_Day_14", "attr_wholesale_cost_wview_through_Day_14",
        "attr_units_wview_through_Day_14", "attr_orders_wview_through_Day_14", "customer_search_term"),
    # bảng kho / mua hàng / vận chuyển có địa chỉ, điện thoại, ghi chú, giá: chỉ lấy cột cần cho báo cáo tồn kho
    "wh_warehouses": ("id", "title", "code", "country_id", "company_id", "is_virtual", "is_managed", "published"),
    "pu_sc_purchase_orders": ("id", "order_number", "order_date", "estimate_delivery_date", "status"),
    "pu_sc_purchase_order_details": ("id", "purchase_order_id", "product_id", "quantity"),
    "pu_shipments": ("id", "shipment_number", "shipment_type", "status", "estimated_time_departure",
                     "actual_time_departure", "estimated_time_arrival", "actual_time_arrival", "estimated_time_import"),
    "pu_shipment_containers": ("id", "shipment_id", "warehouse_id", "container_number", "eta_warehouse", "import_date",
                               "status"),
    "pu_shipment_container_details": ("id", "container_id", "product_id", "quantity", "received_quantity"),
    "sc_delivery_receipts": ("id", "purchase_order_id", "receipt_number", "received_date", "status"),
    "sc_delivery_receipt_containers": ("id", "receipt_id", "container_id", "product_id", "quantity", "received_quantity"),
    "shipment__fbashipments": ("id", "sales_channel_id", "shipment_id", "shipment_name", "warehouse_id", "fulfillcenter",
                               "store_id", "working_date", "shipped_date", "delivered_date", "closed_date",
                               "canceled_date", "estimate_ship_date", "status"),
    "shipment__fbashipment_details": ("id", "fbashipment_id", "product_id", "sku", "quantityshipped",
                                      "quantityactualshipped", "quantityreceived", "fnsku"),
    "shipment__wayfair_castlegate_inbound_shipments": ("id", "store_account_id", "order_number", "status",
                                                       "planned_shipdate", "date_shipped", "wf_warehouse", "warehouse_id",
                                                       "eta", "create_date"),
    # P&L: dòng settlement Amazon (phí thật theo đơn và phí cấp tài khoản), phí CastleGate, chi phí nhãn ship
    # (shipworks: bỏ tên / địa chỉ người nhận)
    "s__amazon_settlement_v2": ("id", "settlement_id", "merchant_id", "transaction_type", "order_id", "sku", "product_id",
                                "sales_channel_id", "marketplace_name", "amount_type", "amount_description", "amount",
                                "quantity_purchased", "posted_date", "purchased_date", "is_mcf"),
    "fee__wayfair_castlegate_fulfillment": ("id", "account_id", "sales_channel_id", "charge_date", "charge_group",
                                            "charge_type", "part_number", "local_currency", "original_currency",
                                            "original_charge_amount", "charge_units"),
    "cs__shipworks_shipment": ("id", "print_date", "order_date", "transaction_id", "sales_channel_id", "warehouse_id",
                               "cost", "carrier", "status", "voided_date", "label_status"),
}
# bảng -> cột ngày
WINDOW_TABLES = {
    "sem__campaigns_base_daily": "report_date",
    "sem__sp_campaigns": "report_date", "sem__sp_campaigns_topofsearch": "report_date",
    "sem__sp_targeting": "report_date", "sem__sp_search_term": "report_date",
    "sem__sp_advertised_product": "report_date", "sem__sp_purchased_product": "report_date",
    "sem__sb_campaigns_placement": "report_date", "sem__sb_campaigns_placement_video": "report_date",
    "sem__sb_keywords": "report_date", "sem__sb_keywords_video": "report_date",
    "sem__sb_search_term": "report_date", "sem__sb_search_term_video": "report_date",
    "sem__sb_purchased_product": "report_date",
    "sem__sdp_campaigns": "report_date", "sem__sdp_targetings": "report_date",
    # Wayfair Sponsored Products (nguồn không có index theo ngày: mỗi bảng bị quét toàn bộ một lần mỗi lần chạy;
    # keyword optimization ~22 triệu dòng mất khoảng 5 phút)
    "sem_wayfair__wsp_campaign": "campaign_date_run", "sem_wayfair__wsp_product": "campaign_date_run",
    "sem_wayfair__wsp_keyword_targeting": "campaign_date_run",
    "sem_wayfair__wsp_keyword_optimization": "campaign_date_run",
    "sem_wayfair__wsp_search_term_research": "report_date",
    "sem_wayfair__campaign_info_daily": "campaign_date_run",
    # tồn kho: doanh số theo kênh x sản phẩm x ngày và lịch sử tồn theo ngày (để bỏ ngày hết hàng khi tính tốc độ bán)
    "s_sales_report_data_by_orderdate": "report_date",
    "wh_product_inventory_trace": "the_date",
    "wh_wayfair_castlegate_inventory_history": "date",
    # P&L (etl/pnl.py). Settlement ghi theo ngày Amazon trả tiền (posted_date), sau ngày đặt đơn 1–3 tuần.
    "s__amazon_settlement_v2": "posted_date",
    "fee__wayfair_castlegate_fulfillment": "charge_date",
    "cs__shipworks_shipment": "print_date",
}
ORDER_TABLES = ("s__amazon_orders", "s__amazon_order_details")
BID_TABLE = "sem__keywords_base_daily"
WF_BID_TABLE = "sem_wayfair__keyword_info_daily"  # ~4 triệu dòng, tra theo khóa chính keyword_info_id_YYYYMMDD
ADGROUP_STATE_TABLE = "sem__adgroups_base_daily"  # ~5 triệu dòng, chỉ tra snapshot mới nhất theo khóa chính
ALL_TABLES = [t for t, _ in FULL_TABLES] + list(WINDOW_TABLES) + list(ORDER_TABLES) + [BID_TABLE, WF_BID_TABLE,
                                                                                          ADGROUP_STATE_TABLE]


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    schema: str

    def connect(self, use_schema: bool = True) -> pymysql.connections.Connection:
        return pymysql.connect(host=self.host, port=self.port, user=self.user, password=self.password,
                               database=self.schema if use_schema else None, charset="utf8mb4",
                               autocommit=False, read_timeout=3600, write_timeout=3600)


Log = Callable[[str, int, float, str], None]


def _print_log(step: str, rows: int, seconds: float, note: str = "") -> None:
    print(f"[SYNC] {step} rows={rows} {seconds:.1f}s {note}".rstrip(), flush=True)


class StagingSync:
    def __init__(self, source: DbConfig, target: DbConfig, log: Log = _print_log):
        self.source, self.target, self.log = source, target, log
        self.src = source.connect()
        boot = target.connect(use_schema=False)
        with boot.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{target.schema}` CHARACTER SET utf8mb4")
        boot.commit()
        boot.close()
        self.dst = target.connect()

    def close(self) -> None:
        self.src.close()
        self.dst.close()

    # ---------------------------------------------------------------- cấu trúc bảng
    def ensure_tables(self) -> None:
        with self.dst.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (self.target.schema,))
            existing = {r[0].lower() for r in cur.fetchall()}
        for table in ALL_TABLES:
            if table.lower() in existing:
                if table in COLUMNS:
                    self._add_missing_columns(table)
                continue
            ddl = self._column_ddl(table) if table in COLUMNS else self._source_ddl(table)
            with self.dst.cursor() as cur:
                cur.execute(ddl)
                date_col = WINDOW_TABLES.get(table) or {"s__amazon_orders": "purchased_date",
                                                         "s__amazon_order_details": "amazon_order_id",
                                                         "s__wayfair_order_details": "order_id",
                                                         "s__shopify_order_details_v2": "order_id",
                                                         "s__shopify_order_refund_line_items": "line_item_id"}.get(table)
                if date_col:
                    cur.execute(f"ALTER TABLE `{table}` ADD INDEX idx_sync ({date_col})")
            self.dst.commit()
            self.log(f"create {table}", 0, 0, "")

    def _add_missing_columns(self, table: str) -> None:
        """Bảng chép theo COLUMNS đã có sẵn: thêm cột mới được bổ sung vào COLUMNS (kiểu như nguồn)."""
        with self.dst.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                        (self.target.schema, table))
            have = {r[0].lower() for r in cur.fetchall()}
        missing = [c for c in COLUMNS[table] if c.lower() not in have]
        if not missing:
            return
        with self.src.cursor() as cur:
            cur.execute("""SELECT column_name, column_type FROM information_schema.columns
                           WHERE table_schema = %s AND table_name = %s""", (self.source.schema, table))
            types = {r[0].lower(): r[1] for r in cur.fetchall()}
        with self.dst.cursor() as cur:
            for c in missing:
                cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{c}` {types[c.lower()]}")
        self.dst.commit()
        self.log(f"alter {table}", 0, 0, "thêm cột " + ", ".join(missing))

    def _source_ddl(self, table: str) -> str:
        with self.src.cursor() as cur:
            cur.execute(f"SHOW CREATE TABLE `{table}`")
            ddl = cur.fetchone()[1]
        return re.sub(r"\s+AUTO_INCREMENT=\d+", "", ddl)

    def _column_ddl(self, table: str) -> str:
        """Tạo bảng chỉ gồm các cột trong COLUMNS, giữ đúng kiểu dữ liệu của nguồn; cột đầu tiên là khóa chính."""
        cols = COLUMNS[table]
        with self.src.cursor() as cur:
            cur.execute("""SELECT column_name, column_type FROM information_schema.columns
                           WHERE table_schema = %s AND table_name = %s""", (self.source.schema, table))
            types = {r[0].lower(): r[1] for r in cur.fetchall()}
        defs = ", ".join(f"`{c}` {types[c.lower()]}" + (" NOT NULL" if i == 0 else "") for i, c in enumerate(cols))
        return f"CREATE TABLE `{table}` ({defs}, PRIMARY KEY (`{cols[0]}`))"

    # ---------------------------------------------------------------- chép dữ liệu
    def _copy(self, table: str, select_sql: str, params: tuple = ()) -> int:
        """Đọc dạng stream từ nguồn, ghi theo lô và commit từng lô (bảng lớn có thể hàng triệu dòng)."""
        n, t0 = 0, time.time()
        with self.src.cursor(SSCursor) as sc, self.dst.cursor() as dc:
            sc.execute(select_sql, params)
            cols = ", ".join(f"`{d[0]}`" for d in sc.description)
            insert = f"REPLACE INTO `{table}` ({cols}) VALUES ({', '.join(['%s'] * len(sc.description))})"
            while True:
                rows = sc.fetchmany(BATCH)
                if not rows:
                    break
                dc.executemany(insert, rows)
                self.dst.commit()
                n += len(rows)
                if n % (BATCH * 100) == 0:
                    print(f"       … {table}: {n:,} dòng, {n / (time.time() - t0):,.0f} dòng/s", flush=True)
        return n

    @staticmethod
    def _select_list(table: str) -> str:
        return ", ".join(f"`{c}`" for c in COLUMNS[table]) if table in COLUMNS else "*"

    def sync_full(self) -> None:
        for table, where in FULL_TABLES:
            t0 = time.time()
            with self.dst.cursor() as cur:
                cur.execute(f"DELETE FROM `{table}`")
            n = self._copy(table, f"SELECT {self._select_list(table)} FROM `{table}`" + (f" WHERE {where}" if where else ""))
            self.dst.commit()
            self.log(table, n, time.time() - t0, "full")

    def sync_window(self, start: date, end: date) -> None:
        end_excl = end + timedelta(days=1)
        for table, col in WINDOW_TABLES.items():
            t0 = time.time()
            with self.dst.cursor() as cur:
                cur.execute(f"DELETE FROM `{table}` WHERE `{col}` >= %s AND `{col}` < %s", (start, end_excl))
            n = self._copy(table, f"SELECT {self._select_list(table)} FROM `{table}` WHERE `{col}` >= %s AND `{col}` < %s",
                           (start, end_excl))
            self.dst.commit()
            self.log(table, n, time.time() - t0, f"{start}..{end}")
        self.sync_orders(start, end)
        # bid tra theo khóa chính nên chia đợt 31 ngày cho danh sách cặp keyword x ngày không quá lớn
        cur = start
        while cur <= end:
            stop = min(cur + timedelta(days=30), end)
            self.sync_bids(cur, stop)
            self.sync_wf_bids(cur, stop)
            cur = stop + timedelta(days=1)

    def sync_orders(self, start: date, end: date) -> None:
        t0, end_excl = time.time(), end + timedelta(days=1)
        with self.dst.cursor() as cur:
            cur.execute("""DELETE d FROM s__amazon_order_details d JOIN s__amazon_orders o ON o.id = d.amazon_order_id
                           WHERE o.purchased_date >= %s AND o.purchased_date < %s""", (start, end_excl))
            cur.execute("DELETE FROM s__amazon_orders WHERE purchased_date >= %s AND purchased_date < %s", (start, end_excl))
        n = self._copy("s__amazon_orders", "SELECT * FROM s__amazon_orders WHERE purchased_date >= %s AND purchased_date < %s",
                       (start, end_excl))
        m = self._copy("s__amazon_order_details",
                       """SELECT d.* FROM s__amazon_order_details d JOIN s__amazon_orders o ON o.id = d.amazon_order_id
                          WHERE o.purchased_date >= %s AND o.purchased_date < %s""", (start, end_excl))
        self.dst.commit()
        self.log("s__amazon_orders + details", n + m, time.time() - t0, f"{start}..{end}")

    def sync_bids(self, start: date, end: date) -> None:
        """Chỉ lấy bid cho các cặp keyword x ngày có trong report đã chép về mà bản sao còn thiếu."""
        t0, end_excl = time.time(), end + timedelta(days=1)
        with self.dst.cursor() as cur:
            cur.execute(f"""
                SELECT x.id FROM (
                  SELECT DISTINCT CONCAT(keyword_id, '_2_', DATE_FORMAT(report_date, '%%Y%%m%%d')) AS id
                  FROM sem__sp_targeting
                  WHERE report_date >= %s AND report_date < %s AND UPPER(match_type) IN ('EXACT', 'PHRASE', 'BROAD')
                  UNION
                  SELECT DISTINCT CONCAT(keyword_id, '_1_', DATE_FORMAT(report_date, '%%Y%%m%%d'))
                  FROM sem__sb_keywords WHERE report_date >= %s AND report_date < %s
                  UNION
                  SELECT DISTINCT CONCAT(keyword_id, '_1_', DATE_FORMAT(report_date, '%%Y%%m%%d'))
                  FROM sem__sb_keywords_video WHERE report_date >= %s AND report_date < %s
                ) x LEFT JOIN `{BID_TABLE}` k ON k.id = x.id
                WHERE k.id IS NULL""", (start, end_excl) * 3)
            missing = [r[0] for r in cur.fetchall()]
        n = 0
        for i in range(0, len(missing), BID_BATCH):
            ids = missing[i:i + BID_BATCH]
            n += self._copy(BID_TABLE, f"SELECT * FROM `{BID_TABLE}` WHERE id IN ({', '.join(['%s'] * len(ids))})",
                            tuple(ids))
            self.dst.commit()
        self.log(BID_TABLE, n, time.time() - t0, f"{len(missing)} cặp keyword x ngày cần tra")

    def _copy_by_ids(self, table: str, ids: list[str]) -> int:
        n = 0
        for i in range(0, len(ids), BID_BATCH):
            chunk = ids[i:i + BID_BATCH]
            n += self._copy(table, f"SELECT * FROM `{table}` WHERE id IN ({', '.join(['%s'] * len(chunk))})", tuple(chunk))
            self.dst.commit()
        return n

    def sync_states(self, mart: str) -> None:
        """Trạng thái mới nhất (snapshot ngày gần nhất) của ad group và keyword Amazon, tra theo khóa chính.

        Report keyword chỉ có dòng khi keyword có hiển thị, nên keyword đã tạm dừng sẽ không còn dòng bid mới:
        phải tra snapshot ngày mới nhất cho mọi keyword từng có số liệu thì mới biết trạng thái hiện tại."""
        t0 = time.time()
        with self.dst.cursor() as cur:
            cur.execute("SELECT MAX(report_date) FROM sem__campaigns_base_daily")
            snap = cur.fetchone()[0]
            if not snap:
                return
            day = snap.strftime("%Y%m%d")
            cur.execute("""SELECT DISTINCT CONCAT(adgroup_id, '_', sponsored_type_id, '_', %s) FROM sem__adgroups_base
                           WHERE sponsored_type_id IN (1, 2, 3)""", (day,))
            ag_ids = [r[0] for r in cur.fetchall()]
        n = self._copy_by_ids(ADGROUP_STATE_TABLE, ag_ids)
        with self.dst.cursor() as cur:  # giữ vài snapshot gần nhất cho bảng nhỏ
            cur.execute(f"DELETE FROM `{ADGROUP_STATE_TABLE}` WHERE report_date < %s - INTERVAL 14 DAY", (snap,))
        self.dst.commit()
        self.log(ADGROUP_STATE_TABLE, n, time.time() - t0, f"snapshot {snap:%Y-%m-%d}, {len(ag_ids)} ad group")

        t0 = time.time()
        with self.dst.cursor() as cur:
            cur.execute(f"""
                SELECT x.id FROM (
                  SELECT DISTINCT CONCAT(target_id, IF(ad_type = 'SP', '_2_', '_1_'), %s) AS id
                  FROM {mart}.fact_target_daily
                  WHERE ad_type IN ('SP', 'SB') AND match_type IN ('EXACT', 'PHRASE', 'BROAD')
                ) x LEFT JOIN `{BID_TABLE}` k ON k.id = x.id
                WHERE k.id IS NULL""", (day,))
            kw_ids = [r[0] for r in cur.fetchall()]
        n = self._copy_by_ids(BID_TABLE, kw_ids)
        self.log(f"{BID_TABLE} (trạng thái)", n, time.time() - t0, f"snapshot {snap:%Y-%m-%d}, {len(kw_ids)} keyword cần tra")

    def sync_wf_bids(self, start: date, end: date) -> None:
        """Bid keyword Wayfair: chỉ tra các cặp keyword x ngày có trong report keyword targeting mà bản sao còn thiếu."""
        t0, end_excl = time.time(), end + timedelta(days=1)
        with self.dst.cursor() as cur:
            cur.execute(f"""
                SELECT x.id FROM (
                  SELECT DISTINCT CONCAT(keyword_info_id, '_', DATE_FORMAT(campaign_date_run, '%%Y%%m%%d')) AS id
                  FROM sem_wayfair__wsp_keyword_targeting WHERE campaign_date_run >= %s AND campaign_date_run < %s
                ) x LEFT JOIN `{WF_BID_TABLE}` k ON k.id = x.id
                WHERE k.id IS NULL""", (start, end_excl))
            missing = [r[0] for r in cur.fetchall()]
        n = 0
        for i in range(0, len(missing), BID_BATCH):
            ids = missing[i:i + BID_BATCH]
            n += self._copy(WF_BID_TABLE, f"SELECT * FROM `{WF_BID_TABLE}` WHERE id IN ({', '.join(['%s'] * len(ids))})",
                            tuple(ids))
            self.dst.commit()
        self.log(WF_BID_TABLE, n, time.time() - t0, f"{len(missing)} cặp keyword x ngày cần tra")
