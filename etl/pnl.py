"""P&L theo cấu trúc công ty, theo ngày đặt đơn (bảng {mart}.fact_pnl_daily, USD).

Các dòng (giống bảng dự báo forecast_daily của công ty trên DWH):
  DT thuần      = doanh thu − khuyến mãi (Amazon: item_price − promotion_discount; Wayfair giá sỉ; Shopify sau giảm giá;
                  kênh khác theo doanh thu backend)
  − Phí kênh    Amazon: phí thật trong settlement theo từng dòng đơn (phí giới thiệu + phí FBA + phí khác); đơn chưa có
                  settlement thì giả lập theo tỷ lệ lịch sử của SKU (thiếu thì theo tham số công ty
                  input_pl_channel_fee_param và phí FBA ước tính amazon_fba_fee_preview). Cộng phí cấp tài khoản không
                  gắn đơn (coupon, deal, subscription, nhãn trả hàng…) trừ bồi hoàn FBA, phân bổ theo tháng × tài khoản.
                  Wayfair: allowance (input_pl_wayfair_allowance). Shopify: % + phí cố định mỗi đơn theo store
                  (fee__shopify_channel_fee_rate), nguồn marketplace theo input_pl_shopify_source_fee. eBay theo
                  input_pl_channel_fee_param; kênh khác theo cfg_channel_cost. Phí FBA cho đơn kênh khác (MCF) tính vào
                  kênh đó.
  − Giá vốn     giá vốn chuẩn BOD (ref_std_cogs) theo hình thức giao (FBA / CastleGate / kho); nhập tay cfg_sku_cost được
                  ưu tiên; SKU chưa có giá vốn ước theo tỷ lệ giá vốn / doanh thu cùng kênh × nước (cogs_est).
                  Giá vốn BOD đã gồm phí vận hành và phí hoàn hàng nên hai dòng đó = 0
                  (COGS_INCLUDES_RETURN_AND_OPERATION; các hàm return_fee / operation_fee giữ lại nếu đổi nguồn giá vốn).
  − Phí hoàn    (khi không gồm trong giá vốn) tỷ lệ của công ty × DT thuần.
  − QC (ĐGMK)   chi phí quảng cáo thật: Amazon / Wayfair theo sản phẩm quảng cáo, phần còn lại của campaign chia theo
                  nhóm SP của campaign rồi theo doanh thu; Shopify nhập tay theo tháng. Walmart chưa có.
  = PL4
  − Phí kho     3PL (fee__warehouse_local, tháng × SKU), phí FBA cấp tài khoản (lưu kho, inbound, hủy / rút hàng…),
                  CastleGate (fee__wayfair_castlegate_fulfillment), nhãn ship (cs__shipworks_shipment).
  − Phí vận hành (khi không gồm trong giá vốn) mỗi đơn vị theo sheet công ty (ref_operation_fee_unit).
  = PL5
Tháng chưa có số thật của một nguồn phí: ước theo tỷ lệ phí / doanh thu của 3 tháng gần nhất đã có (cột *_est).
Tính lại toàn bộ từ PNL_START mỗi lần chạy (phân bổ theo tháng nên không tính từng khúc ngày).

    python -m etl.pnl            # tính lại ngay (cần staging + mart đã nạp)
"""
import calendar
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import text

PNL_START = date(2026, 1, 1)
# Giá vốn chuẩn BOD đã gồm toàn bộ phí vận hành và phí hoàn hàng (xác nhận 2026-11-08): không trừ riêng hai khoản này
# để khỏi trùng. Đặt False nếu đổi sang nguồn giá vốn không gồm hai khoản đó.
COGS_INCLUDES_RETURN_AND_OPERATION = True
RATE_LOOKBACK_DAYS = 180  # lịch sử settlement để học tỷ lệ phí theo SKU
EST_MONTHS = 3  # số tháng gần nhất đã có số thật dùng để ước tháng chưa có

MK_CC = {"amazon.com": "US", "amazon.ca": "CA", "amazon.com.au": "AU", "amazon.com.mx": "MX",
         "non-amazon us": "US", "non-amazon ca": "CA", "non-amazon au": "AU"}
CC_CCY = {"US": "USD", "CA": "CAD", "AU": "AUD", "MX": "MXN"}
AMZ_CC = {"amazon.com": "US", "amazon.ca": "CA", "amazon.com.au": "AU", "amazon.com.mx": "MX"}

# phí cấp tài khoản Amazon (dòng settlement không gắn đơn)
EXCLUDE_ACCOUNT = re.compile(r"cost of advertising|transfer|reserve|payable to amazon|successful charge|^tax on fee|"
                             r"current reserve|previous reserve", re.I)
WAREHOUSE_ACCOUNT = re.compile(r"storage|inbound|removal|disposal|partnered carrier|grade and resell|"
                               r"customer returns fee|liquidation|placement", re.I)
ORDER_TYPES = ("order", "refund", "order_retrocharge", "refund_retrocharge", "chargeback refund")

FIELDS = ("units", "orders", "gross_rev", "promo", "net_rev", "fee_commission", "fee_fulfil", "fee_other", "channel_fee",
          "channel_fee_est", "cogs", "cogs_est", "return_fee", "return_rate", "ads", "pl4", "wh_3pl", "wh_fba", "wh_cg",
          "wh_ship", "warehouse_fee", "warehouse_fee_est", "operation_fee", "operation_fee_est", "pl5")


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def month_of(d: date) -> date:
    return d.replace(day=1)


def next_month(m: date) -> date:
    return (m.replace(day=28) + timedelta(days=4)).replace(day=1)


def prev_month(m: date) -> date:
    return (m - timedelta(days=1)).replace(day=1)


# công ty / tài khoản: so khớp tên giống app/reports_all.company_of (không import app.reports_all để ETL nhẹ)
_CO_RULES = [("SENNO", "Senno"), ("SNN", "Senno"), ("DH INTRA", "DH Intra"), ("DHINTRA", "DH Intra"), ("DHI", "DH Intra"),
             ("MEGSU", "Megsu"), ("AROZU", "Arozu"), ("HURAV", "Hurav"), ("HRV", "Hurav"), ("INFIDEAL", "Infideals"),
             ("INF", "Infideals"), ("IDZO", "Idzo"), ("YES4ALL", "Yes4All"), ("Y4A", "Yes4All"), ("STOZM", "Stozm")]


def company_of(key: str | None) -> str | None:
    norm = (key or "").upper()
    tokens = set(re.split(r"[^A-Z0-9]+", norm))
    for pat, name in _CO_RULES:
        if pat in tokens or (len(pat) >= 5 and pat in norm):
            return name
    return None


class Pnl:
    def __init__(self, conn, mart: str, stg: str, start: date = PNL_START, today: date | None = None):
        self.conn, self.mart, self.stg = conn, mart, stg
        self.start, self.today = start, today or date.today()
        self.rows: dict[tuple, dict] = {}
        self.fx: dict[tuple[date, str], float] = {}
        self.latest_fx: dict[str, float] = {}
        self.notes: dict[str, tuple[date | None, str]] = {}

    # ------------------------------------------------------------ tiện ích
    def q(self, sql: str, **params) -> list:
        return self.conn.execute(text(sql.replace("{mart}", self.mart).replace("{stg}", self.stg)), params).fetchall()

    def rate(self, d: date, ccy: str | None) -> float:
        if not ccy or ccy == "USD":
            return 1.0
        r = self.fx.get((d, ccy))
        return r if r is not None else self.latest_fx.get(ccy, 1.0)

    def row(self, d: date, ch: str, cc: str, acct, fulfil: str, pid, co: str | None = None) -> dict:
        key = (d, ch, cc or "", int(acct or 0), fulfil or "", int(pid or 0))
        r = self.rows.get(key)
        if r is None:
            r = self.rows[key] = {k: 0.0 for k in FIELDS}
            r["co"] = co
        elif co and not r["co"]:
            r["co"] = co
        return r

    def allocate(self, amount: float, keys: list[tuple], weight, field: str, est: bool = False,
                 est_field: str | None = None) -> bool:
        """Chia `amount` cho các dòng theo trọng số weight(row); False nếu không có dòng nào có trọng số > 0."""
        if not amount:
            return True
        ws = [(k, max(weight(self.rows[k]), 0.0)) for k in keys]
        tot = sum(w for _, w in ws)
        if tot <= 0:
            return False
        for k, w in ws:
            if w:
                part = amount * w / tot
                self.rows[k][field] += part
                if est and est_field:
                    self.rows[k][est_field] += part
        return True

    def index(self, keyfn) -> dict:
        out = defaultdict(list)
        for k, r in self.rows.items():
            for ik in keyfn(k, r):
                out[ik].append(k)
        return out

    # ------------------------------------------------------------ 1. doanh thu
    def load_fx(self) -> None:
        for d, ccy, r in self.q("SELECT date_key, currency_code, rate_usd FROM {mart}.fx_daily "
                                "WHERE date_key >= :s AND rate_usd IS NOT NULL", s=self.start - timedelta(days=400)):
            self.fx[(d, ccy)] = float(r)
        for ccy, r in self.q("""SELECT x.currency_code, x.rate_usd FROM {mart}.fx_daily x
                JOIN (SELECT currency_code, MAX(date_key) d FROM {mart}.fx_daily WHERE rate_usd IS NOT NULL
                      GROUP BY currency_code) m ON m.currency_code = x.currency_code AND m.d = x.date_key"""):
            self.latest_fx[ccy] = float(r)

    def load_sales(self) -> None:
        # Amazon: từng dòng đơn (giữ lại để tính phí theo đơn)
        self.amz_lines = []
        for (oid, sku, pid, store, mk, fc, d, qty, price, promo, co) in self.q("""
                SELECT o.amazon_order_id, d.seller_sku, NULLIF(d.product_id, 0), o.store_id, LOWER(o.sales_channel),
                       o.fulfill_channel, DATE(o.purchased_date), d.quantity_ordered, d.item_price, d.promotion_discount,
                       a.store_account_name
                FROM {stg}.s__amazon_orders o
                JOIN {stg}.s__amazon_order_details d ON d.amazon_order_id = o.id
                JOIN (SELECT store_account_id, MAX(store_account_name) store_account_name FROM {mart}.dim_account
                      WHERE store_account_id IS NOT NULL GROUP BY store_account_id) a ON a.store_account_id = o.store_id
                WHERE o.purchased_date >= :s AND COALESCE(o.status, '') <> 'Canceled'""", s=self.start):
            cc = AMZ_CC.get(mk or "")
            if not cc:
                continue
            ccy = CC_CCY[cc]
            fx = self.rate(d, ccy)
            fulfil = "FBA" if fc == "AFN" else "FBM"
            price, promo = _f(price), _f(promo)
            r = self.row(d, "amazon", cc, store, fulfil, pid, co)
            r["units"] += _f(qty)
            r["orders"] += 1
            r["gross_rev"] += price * fx
            r["promo"] += promo * fx
            self.amz_lines.append({"oid": oid, "sku": sku, "cc": cc, "ccy": ccy, "fx": fx, "qty": _f(qty),
                                   "price": price, "promo": promo, "key": (d, "amazon", cc, int(store or 0), fulfil,
                                                                           int(pid or 0))})
        # Wayfair: giá sỉ
        for d, cc, acct, otype, pid, units, lines, s, co in self.q("""
                SELECT t.report_date, t.country_code, wa.store_account_id, t.order_type, t.product_id, SUM(t.units),
                       SUM(t.order_lines), SUM(t.sales_usd), MAX(wa.short_name)
                FROM {mart}.fact_wf_total_sales_daily t LEFT JOIN {mart}.dim_wf_account wa ON wa.account_id = t.account_id
                WHERE t.report_date >= :s GROUP BY t.report_date, t.country_code, wa.store_account_id, t.order_type,
                      t.product_id""", s=self.start):
            r = self.row(d, "wayfair", cc, acct, "CG" if otype == "castle_gate" else "DS", pid, co)
            r["units"] += _f(units)
            r["orders"] += _f(lines)
            r["gross_rev"] += _f(s)
        # Shopify: sau giảm giá; phí cố định mỗi đơn chia đều cho các dòng của đơn
        self.shop_src = defaultdict(lambda: defaultdict(float))  # key -> {source: [net, orders]}
        for d, cc, sc, acct, code, title, pid, src, units, net, orders in self.q("""
                SELECT l.report_date, l.country_code, l.sales_channel_id, m.store_account_id, m.code, m.title, l.product_id,
                       COALESCE(l.source_name, ''), SUM(l.units), SUM(l.net_usd), SUM(1 / n.n_lines)
                FROM {mart}.fact_shop_line l
                JOIN (SELECT order_id, COUNT(*) n_lines FROM {mart}.fact_shop_line GROUP BY order_id) n ON n.order_id = l.order_id
                LEFT JOIN {mart}.map_channel_node m ON m.sales_channel_id = l.sales_channel_id
                WHERE l.report_date >= :s
                GROUP BY l.report_date, l.country_code, l.sales_channel_id, m.store_account_id, m.code, m.title,
                         l.product_id, COALESCE(l.source_name, '')""", s=self.start):
            r = self.row(d, "shopify", cc, acct, "WEB", pid, code)
            r["units"] += _f(units)
            r["orders"] += _f(orders)
            r["gross_rev"] += _f(net)
            r.setdefault("_src", []).append((src, _f(net), _f(orders), code, title))
        # kênh khác (Walmart, eBay, bán sỉ…)
        for d, cc, acct, fulfil, code, pid, units, rev in self.q("""
                SELECT f.report_date, m.country_code, m.store_account_id, COALESCE(m.fulfil_type, ''), m.code, f.product_id,
                       SUM(f.units), SUM(f.revenue_usd)
                FROM {mart}.fact_channel_sales_daily f JOIN {mart}.map_channel_node m ON m.sales_channel_id = f.sales_channel_id
                WHERE f.report_date >= :s AND m.code NOT LIKE 'AMZ-%' AND m.code NOT LIKE 'WAYFAIR-%'
                  AND m.code NOT LIKE 'SPF-%'
                GROUP BY f.report_date, m.country_code, m.store_account_id, m.fulfil_type, m.code, f.product_id""",
                                                                   s=self.start):
            r = self.row(d, "other", cc, acct, fulfil, pid, code)
            r["units"] += _f(units)
            r["gross_rev"] += _f(rev)
        for r in self.rows.values():
            r["net_rev"] = r["gross_rev"] - r["promo"]

    # ------------------------------------------------------------ 2. phí kênh
    def amazon_fees(self) -> None:
        mk_list = tuple(AMZ_CC)
        # phí thật theo dòng đơn
        actual: dict[tuple, dict] = {}
        hist: dict[tuple, dict] = defaultdict(lambda: defaultdict(float))  # (cc, sku) -> sums
        cc_hist: dict[str, dict] = defaultdict(lambda: defaultdict(float))
        cutoff: dict[str, date] = {}
        rows = self.q("""SELECT order_id, sku, LOWER(marketplace_name), amount_type, amount_description, SUM(amount),
                                SUM(CASE WHEN amount_type = 'ItemPrice' AND amount_description = 'Principal'
                                         THEN quantity_purchased ELSE 0 END), MAX(posted_date)
                         FROM {stg}.s__amazon_settlement_v2
                         WHERE transaction_type = 'Order' AND LOWER(marketplace_name) IN :mk AND posted_date >= :s
                         GROUP BY order_id, sku, LOWER(marketplace_name), amount_type, amount_description""",
                      mk=mk_list, s=self.start - timedelta(days=RATE_LOOKBACK_DAYS + 60))
        lookback = self.today - timedelta(days=RATE_LOOKBACK_DAYS)
        for oid, sku, mk, atype, desc, amt, qty, posted in rows:
            cc = AMZ_CC[mk]
            cutoff[cc] = max(cutoff.get(cc, posted), posted)
            a = actual.setdefault((oid, sku), defaultdict(float))
            amt = _f(amt)
            if atype == "ItemPrice" and desc == "Principal":
                part = "principal"
                a["qty"] += _f(qty)
            elif atype == "Promotion" and desc == "Principal":
                part = "promo"
            elif atype == "ItemFees" and desc == "Commission":
                part = "commission"
            elif atype == "ItemFees" and desc == "FBAPerUnitFulfillmentFee":
                part = "fulfil"
            elif atype == "ItemFees":
                part = "other"
            else:
                continue
            a[part] += amt
            a["posted"] = max(a.get("posted") or posted, posted)
            a["cc"] = cc
        for (oid, sku), a in actual.items():
            if a.get("posted") and a["posted"] >= lookback and a["principal"] > 0:
                h, c = hist[(a["cc"], sku)], cc_hist[a["cc"]]
                base = a["principal"] + a["promo"]
                for x in (h, c):
                    x["base"] += base
                    x["commission"] += -a["commission"]
                    x["other"] += -a["other"]
                    if a["fulfil"]:
                        x["fulfil"] += -a["fulfil"]
                        x["fqty"] += a["qty"]
                        x["fbase"] += base
        # tham số công ty cho phí giới thiệu ước tính; phí FBA ước tính theo SKU
        p = self.q("""SELECT price_threshold, rate_up_to_threshold, rate_above_threshold FROM {stg}.input_pl_channel_fee_param
                      WHERE marketplace = 'Amazon' AND fee_type = 'commission_est'""")
        thr, r1, r2 = (float(p[0][0]), float(p[0][1]), float(p[0][2])) if p else (200.0, 0.15, 0.10)
        preview = {}
        for sku, cc, fee in self.q("""SELECT f.sku, m.country_code, f.expected_fulfillment_fee_per_unit
                FROM {stg}.amazon_fba_fee_preview f JOIN {mart}.map_channel_node m ON m.sales_channel_id = f.sales_channel_id
                WHERE f.expected_fulfillment_fee_per_unit > 0"""):
            preview[(cc, sku)] = float(fee)
        n_act = n_est = 0
        for ln in self.amz_lines:
            r = self.rows[ln["key"]]
            a = actual.get((ln["oid"], ln["sku"]))
            fx = ln["fx"]
            if a and a["principal"] > 0:
                com, ful, oth = -a["commission"], -a["fulfil"], -a["other"]
                est = False
                n_act += 1
            else:
                base = ln["price"] - ln["promo"]
                h, c = hist.get((ln["cc"], ln["sku"])), cc_hist.get(ln["cc"], {})
                if h and h["base"] > 0:
                    com = h["commission"] / h["base"] * base
                else:
                    unit = base / ln["qty"] if ln["qty"] else base
                    per = min(unit, thr) * r1 + max(unit - thr, 0) * r2
                    com = per * (ln["qty"] or 1)
                ful = 0.0
                if ln["key"][4] == "FBA":
                    if h and h["fqty"] > 0:
                        ful = h["fulfil"] / h["fqty"] * ln["qty"]
                    elif (ln["cc"], ln["sku"]) in preview:
                        ful = preview[(ln["cc"], ln["sku"])] * ln["qty"]
                    elif c.get("fbase"):
                        ful = c["fulfil"] / c["fbase"] * base
                oth = (c["other"] / c["base"] * base) if c.get("base") else 0.0
                est = True
                n_est += 1
            r["fee_commission"] += com * fx
            r["fee_fulfil"] += ful * fx
            r["fee_other"] += oth * fx
            if est:
                r["channel_fee_est"] += (com + ful + oth) * fx
        self.amz_cutoff = cutoff
        last = min(cutoff.values()) if cutoff else None
        self.notes["amazon_order_fee"] = (last, f"{n_act} dòng đơn có settlement, {n_est} dòng giả lập")

    def full_month_end(self, cc: str) -> date | None:
        """Tháng cuối đã đủ settlement của một nước (tháng trước tháng chứa ngày posted mới nhất)."""
        d = self.amz_cutoff.get(cc)
        if not d:
            return None
        return month_of(d) - timedelta(days=1)

    def amazon_account_fees(self) -> None:
        """Phí cấp tài khoản + phí FBA của đơn kênh khác (MCF), phân bổ theo tháng."""
        chan = {sc: (cc, acct, code) for sc, cc, acct, code in self.q(
            "SELECT sales_channel_id, country_code, store_account_id, code FROM {mart}.map_channel_node")}
        merch = {}
        for m, mk, sc, n in self.q("""SELECT merchant_id, LOWER(marketplace_name), MAX(sales_channel_id), COUNT(*)
                FROM {stg}.s__amazon_settlement_v2 WHERE transaction_type = 'Order' AND LOWER(marketplace_name) IN :mk
                GROUP BY merchant_id, LOWER(marketplace_name)""", mk=tuple(AMZ_CC)):
            if m not in merch or n > merch[m][2]:
                merch[m] = (AMZ_CC[mk], chan.get(sc, (None, None, None))[1], n)
        acc = defaultdict(float)  # (bucket, month, cc, acct) -> local amount
        mcf = defaultdict(float)  # (month, cc, pid) -> local amount
        for ttype, mk, sc, merchant, atype, desc, pid, posted, amt in self.q("""
                SELECT transaction_type, LOWER(COALESCE(marketplace_name, '')), sales_channel_id, merchant_id, amount_type,
                       amount_description, product_id, posted_date, SUM(amount)
                FROM {stg}.s__amazon_settlement_v2 WHERE posted_date >= :s
                GROUP BY transaction_type, LOWER(COALESCE(marketplace_name, '')), sales_channel_id, merchant_id,
                         amount_type, amount_description, product_id, posted_date""", s=self.start - timedelta(days=100)):
            ttype_l, label = (ttype or "").lower(), f"{atype or ''} {desc or ''}"
            if mk.startswith("non-amazon"):
                if ttype_l == "order" and atype == "ItemFees":
                    mcf[(month_of(posted), MK_CC[mk], int(pid or 0))] += -_f(amt)
                continue
            if ttype_l in ORDER_TYPES or EXCLUDE_ACCOUNT.search(label) or EXCLUDE_ACCOUNT.search(ttype or ""):
                continue
            cc = AMZ_CC.get(mk) or (chan.get(sc) or (None,))[0] or (merch.get(merchant) or (None,))[0]
            acct = (chan.get(sc) or (None, None))[1] or (merch.get(merchant) or (None, None))[1]
            if not cc:
                continue
            bucket = "wh" if WAREHOUSE_ACCOUNT.search(label) else "ch"
            acc[(bucket, month_of(posted), cc, int(acct or 0))] += -_f(amt)
        # dòng Amazon theo tháng × nước (× tài khoản)
        by_m_cc = self.index(lambda k, r: [(month_of(k[0]), k[2])] if k[1] == "amazon" else [])
        by_m_cc_acct = self.index(lambda k, r: [(month_of(k[0]), k[2], k[3])] if k[1] == "amazon" else [])
        months = sorted({m for (_, m, _, _) in acc} | {m for m, _ in by_m_cc})
        for cc in {k[2] for k in self.rows if k[1] == "amazon"}:
            full_end = self.full_month_end(cc)
            ratios = {}
            for bucket in ("wh", "ch"):
                # tỷ lệ phí / doanh thu (FBA cho phí kho) của các tháng đủ số liệu gần nhất
                ms = [m for m in months if full_end and m <= full_end][-EST_MONTHS:]
                fee = sum(v for (b, m, c, _), v in acc.items() if b == bucket and c == cc and m in ms)
                base = sum(self._amz_base(self.rows[k], bucket) for m in ms for k in by_m_cc.get((m, cc), []))
                ratios[bucket] = fee / base if base else 0.0
            for m in months:
                keys = by_m_cc.get((m, cc), [])
                if not keys:
                    continue
                field = {"wh": "wh_fba", "ch": "fee_other"}
                est_field = {"wh": "warehouse_fee_est", "ch": "channel_fee_est"}
                ccy = CC_CCY.get(cc, "USD")
                fx = self.rate(min(next_month(m) - timedelta(days=1), self.today), ccy)
                if full_end and m <= full_end:
                    for (b, mm, c, acct), v in acc.items():
                        if mm != m or c != cc:
                            continue
                        ks = by_m_cc_acct.get((m, cc, acct)) or keys
                        if not self.allocate(v * fx, ks, lambda r, b=b: self._amz_base(r, b), field[b]):
                            self.allocate(v * fx, keys, lambda r: r["net_rev"], field[b])
                else:
                    for b in ("wh", "ch"):
                        for k in keys:
                            r = self.rows[k]
                            amt = ratios[b] * self._amz_base(r, b)
                            r[field[b]] += amt
                            r[est_field[b]] += amt
        # MCF: phí FBA của đơn Shopify / kênh khác giao từ kho FBA
        non_amz = self.index(lambda k, r: [(month_of(k[0]), k[2])] if k[1] in ("shopify", "other") else [])
        non_amz_pid = self.index(lambda k, r: [(month_of(k[0]), k[2], k[5])] if k[1] in ("shopify", "other") else [])
        for (m, cc, pid), v in mcf.items():
            if m < self.start:
                continue
            fx = self.rate(min(next_month(m) - timedelta(days=1), self.today), CC_CCY.get(cc, "USD"))
            ks = non_amz_pid.get((m, cc, pid)) or non_amz.get((m, cc), [])
            if not self.allocate(v * fx, ks, lambda r: r["units"] or r["net_rev"], "fee_fulfil"):
                self.allocate(v * fx, non_amz.get((m, cc), []), lambda r: r["net_rev"], "fee_fulfil")
        self.notes["amazon_account_fee"] = (min((self.full_month_end(c) for c in self.amz_cutoff), default=None),
                                            "phí cấp tài khoản theo tháng settlement; tháng sau đó ước theo tỷ lệ")

    @staticmethod
    def _amz_base(r: dict, bucket: str) -> float:
        return r["net_rev"] if bucket == "ch" else (r["net_rev"] if r.get("_fba") else 0.0)

    def other_channel_fees(self) -> None:
        allow = {}
        for acc, rate in self.q("SELECT account, allowance_rate FROM {stg}.input_pl_wayfair_allowance"):
            allow[company_of(acc) or acc] = float(rate)
        shop_rates = [(company_of(a), c, ds, de, float(p), float(fx)) for a, c, ds, de, p, fx in self.q(
            "SELECT account, country, date_start, date_end, pct, fixed FROM {stg}.fee__shopify_channel_fee_rate")]
        src_fee = {s.lower(): (float(p), float(fx)) for s, p, fx in self.q(
            "SELECT source_name, rate_pct, fixed_fee FROM {stg}.input_pl_shopify_source_fee")}
        web_src = {s.lower() for (s,) in self.q("SELECT source_name FROM {stg}.input_pl_shopify_web_source")} | {"web", ""}
        ebay = self.q("""SELECT price_threshold, rate_up_to_threshold, rate_above_threshold, fixed_fee_order_threshold,
                                fixed_fee_low, fixed_fee_high FROM {stg}.input_pl_channel_fee_param WHERE marketplace = 'eBay'""")
        cfg = {c: float(p) for c, p in self.q("SELECT channel, referral_pct FROM {mart}.cfg_channel_cost")}
        other_pct = cfg.get("other", 0.15)
        for k, r in self.rows.items():
            d, ch, cc = k[0], k[1], k[2]
            if ch == "wayfair":
                r["fee_other"] += r["net_rev"] * allow.get(company_of(r["co"]) or r["co"], 0.04)
            elif ch == "shopify":
                co = company_of(r["co"])
                pct, fixed = next(((p, fx) for c, cty, ds, de, p, fx in shop_rates
                                   if c == co and ds <= d < de), (cfg.get("shopify", 0.03), 0.30))
                for src, net, orders, _, _ in r.get("_src", []):
                    s = src.lower()
                    if s in src_fee:
                        p2, f2 = src_fee[s]
                        r["fee_commission"] += net * p2 + orders * f2
                    elif s == "ebay" and ebay:
                        r["fee_commission"] += net * float(ebay[0][1])
                    else:  # web và nguồn khác: phí cổng thanh toán của store
                        r["fee_commission"] += net * pct + orders * fixed
            elif ch == "other":
                code = (r["co"] or "").upper()
                if code.startswith("EBAY") and ebay:
                    thr, a1, a2, _, flo, _ = (float(x or 0) for x in ebay[0])
                    unit = r["net_rev"] / r["units"] if r["units"] else r["net_rev"]
                    n = r["units"] or 1
                    r["fee_commission"] += n * (min(unit, thr) * a1 + max(unit - thr, 0) * a2) + n * flo
                else:
                    r["fee_commission"] += r["net_rev"] * other_pct

    # ------------------------------------------------------------ 3. giá vốn
    def cogs(self) -> None:
        from app import insights
        costs, _ = insights.load_costs()
        manual, std = costs["manual"], costs["std"]
        costed = defaultdict(lambda: [0.0, 0.0])
        missing = []
        for k, r in self.rows.items():
            ch, cc, fulfil, pid = k[1], k[2], k[4], k[5]
            if not r["units"]:
                continue
            mkt = cc if cc in ("US", "CA", "AU") else "US"
            unit = None
            m = manual.get(pid)
            if m and m.get("landed_cost") is not None:
                unit = float(m["landed_cost"])
            elif pid:
                basis = "FBA" if fulfil == "FBA" else "CG" if fulfil == "CG" else "WH"
                for b in (basis, "WH", "FBA", "CG"):
                    if (pid, mkt, b) in std:
                        unit = std[(pid, mkt, b)]
                        break
            if unit is None:
                missing.append(k)
                continue
            r["cogs"] = unit * r["units"]
            for ck in ((ch, cc), (ch,), ()):
                costed[ck][0] += r["net_rev"]
                costed[ck][1] += r["cogs"]
        for k in missing:
            r = self.rows[k]
            for ck in ((k[1], k[2]), (k[1],), ()):
                s, c = costed.get(ck, (0, 0))
                if s > 0:
                    r["cogs"] = r["cogs_est"] = r["net_rev"] * c / s
                    break

    # ------------------------------------------------------------ 4. phí hoàn hàng (tỷ lệ công ty)
    def return_fee(self) -> None:
        grp = {pid: (g or "").strip().lower() for pid, g in self.q("SELECT product_id, group_name FROM {mart}.dim_product")}
        rates = defaultdict(list)
        plat = defaultdict(list)
        for g, p, fm, cty, rr in self.q("""SELECT group_name, platform, COALESCE(fulfill_method, ''), country, return_rate
                                           FROM {stg}.input_forecast_sales_return_rate WHERE return_rate IS NOT NULL"""):
            cc = "AU" if cty in ("AUS", "AU") else cty
            rates[((g or "").strip().lower(), p, fm, cc)].append(float(rr))
            plat[(p, fm, cc)].append(float(rr))
        default = {}
        force = {}
        for mk, rate, fo in self.q("SELECT marketplace, default_return_rate, force_override FROM {stg}.input_pl_return_fee_rate"):
            default[mk.lower()] = float(rate)
            if fo:
                force[mk.lower()] = float(rate)
        for k, r in self.rows.items():
            ch, cc, fulfil, pid = k[1], k[2], k[4], k[5]
            code = (r["co"] or "").upper()
            if ch == "amazon":
                p, fm, mk = "AMZ", fulfil, "amazon"
            elif ch == "wayfair":
                p, fm, mk = "WAYFAIR", "CG" if fulfil == "CG" else "", "wayfair"
            elif ch == "shopify":
                p, fm, mk = "SPF", "", "shopify"
            elif code.startswith("WM"):
                p, fm, mk = "WM", "MKP", "walmart"
            elif code.startswith("EBAY"):
                p, fm, mk = "EBAY", "", "ebay"
            elif code.startswith("MYDEAL"):
                p, fm, mk = "MYDEAL", "", ""
            else:
                p, fm, mk = "", "", ""
            if mk in force:
                rate = force[mk]
            else:
                lst = rates.get((grp.get(pid, ""), p, fm, cc)) or plat.get((p, fm, cc))
                rate = sum(lst) / len(lst) if lst else default.get(mk, 0.0)
            r["return_rate"] = rate
            r["return_fee"] = r["net_rev"] * rate

    # ------------------------------------------------------------ 5. QC (ĐGMK) thật
    def ads(self) -> None:
        group_of = {pid: g for pid, g in self.q("SELECT product_id, group_id FROM {mart}.dim_product")}
        by_day = self.index(lambda k, r: [(k[0], k[1], k[2], k[3])])
        by_day_cc = self.index(lambda k, r: [(k[0], k[1], k[2])])
        by_day_pid = self.index(lambda k, r: [(k[0], k[1], k[2], k[3], k[5])])
        by_day_grp = self.index(lambda k, r: [(k[0], k[1], k[2], group_of.get(k[5]))])
        rev = lambda r: r["net_rev"]
        orphan = 0.0

        def put(d, ch, cc, acct, pid, amt, co=None):
            nonlocal orphan
            if not amt:
                return
            ks = by_day_pid.get((d, ch, cc, int(acct or 0), int(pid or 0)))
            if ks and self.allocate(amt, ks, lambda r: r["net_rev"] or 1, "ads"):
                return
            r = self.row(d, ch, cc, acct, "-", pid, co)  # QC của SP không có đơn trong ngày
            r["ads"] += amt
            orphan += amt

        def spread(d, ch, cc, acct, group, amt, co=None):
            for ks in (by_day_grp.get((d, ch, cc, group)) if group else None, by_day.get((d, ch, cc, int(acct or 0))),
                       by_day_cc.get((d, ch, cc))):
                if ks and self.allocate(amt, ks, rev, "ads"):
                    return
            put(d, ch, cc, acct, 0, amt, co)

        # Amazon: chi phí theo sản phẩm quảng cáo, phần còn lại của campaign theo nhóm của campaign
        prod = defaultdict(float)
        camp_prod = defaultdict(float)
        for d, ad, cid, cc, acct, pid, cost in self.q("""
                SELECT f.report_date, f.ad_type, f.campaign_id, a.country_code, a.store_account_id, f.product_id,
                       SUM(f.cost_usd)
                FROM {mart}.fact_product_daily f JOIN {mart}.dim_account a ON a.profile_id = f.profile_id
                WHERE f.report_date >= :s GROUP BY f.report_date, f.ad_type, f.campaign_id, a.country_code,
                      a.store_account_id, f.product_id""", s=self.start):
            prod[(d, cc, acct, pid)] += _f(cost)
            camp_prod[(d, ad, cid)] += _f(cost)
        shares = defaultdict(list)
        for ad, cid, g, w in self.q("""SELECT ad_type, campaign_id, group_id, SUM(COALESCE(weight, weight_share, 1))
                                       FROM {mart}.map_adgroup_product GROUP BY ad_type, campaign_id, group_id"""):
            shares[(ad, cid)].append((g, _f(w)))
        for (d, cc, acct, pid), v in prod.items():
            put(d, "amazon", cc, acct, pid, v)
        for d, ad, cid, cc, acct, cost in self.q("""
                SELECT f.report_date, f.ad_type, f.campaign_id, a.country_code, a.store_account_id, SUM(f.cost_usd)
                FROM {mart}.fact_campaign_daily f JOIN {mart}.dim_account a ON a.profile_id = f.profile_id
                WHERE f.report_date >= :s GROUP BY f.report_date, f.ad_type, f.campaign_id, a.country_code,
                      a.store_account_id""", s=self.start):
            rest = _f(cost) - camp_prod.get((d, ad, cid), 0.0)
            if rest <= 0.005:
                continue
            sh = shares.get((ad, cid))
            tot = sum(w for _, w in sh) if sh else 0
            if tot > 0:
                for g, w in sh:
                    spread(d, "amazon", cc, acct, g, rest * w / tot)
            else:
                spread(d, "amazon", cc, acct, None, rest)
        # Wayfair: theo listing → sản phẩm, phần còn lại theo doanh thu
        lp = defaultdict(list)
        for lid, pid in self.q("SELECT listing_id, product_id FROM {mart}.map_wf_listing_product"):
            lp[lid].append(pid)
        wacct = {a: s for a, s in self.q("SELECT account_id, store_account_id FROM {mart}.dim_wf_account")}
        # report sản phẩm đôi khi cao hơn report campaign cùng ngày: thu nhỏ về đúng tổng của campaign
        camp = {(d, cid, cc): (_f(cost), acc) for d, cid, cc, acc, cost in self.q("""
                SELECT report_date, campaign_id, country_code, MAX(account_id), SUM(cost_usd)
                FROM {mart}.fact_wf_campaign_daily WHERE report_date >= :s
                GROUP BY report_date, campaign_id, country_code""", s=self.start)}
        prows = self.q("""SELECT report_date, campaign_id, listing_id, country_code, account_id, SUM(cost_usd)
                FROM {mart}.fact_wf_product_daily WHERE report_date >= :s
                GROUP BY report_date, campaign_id, listing_id, country_code, account_id""", s=self.start)
        camp_lp = defaultdict(float)
        for d, cid, lid, cc, acc, cost in prows:
            camp_lp[(d, cid, cc)] += _f(cost)
        for d, cid, lid, cc, acc, cost in prows:
            tot = camp_lp[(d, cid, cc)]
            c = camp.get((d, cid, cc), (tot, acc))[0]
            v = _f(cost) * (min(c / tot, 1.0) if tot > 0 else 1.0)
            pids = lp.get(lid)
            if pids:
                for pid in pids:
                    put(d, "wayfair", cc, wacct.get(acc), pid, v / len(pids))
            else:
                spread(d, "wayfair", cc, wacct.get(acc), None, v)
        for (d, cid, cc), (cost, acc) in camp.items():
            rest = cost - camp_lp.get((d, cid, cc), 0.0)
            if rest > 0.005:
                spread(d, "wayfair", cc, wacct.get(acc), None, rest)
        # Shopify: chi phí nhập tay theo tháng × store, chia đều theo ngày rồi theo doanh thu
        stores = {sc: (cc, acct, code) for sc, cc, acct, code in self.q(
            "SELECT sales_channel_id, country_code, store_account_id, code FROM {mart}.map_channel_node")}
        for m, sc, spend in self.q("""SELECT month, sales_channel_id, SUM(spend_usd) FROM {mart}.cfg_shop_ad_spend
                                      WHERE month >= :s GROUP BY month, sales_channel_id""", s=month_of(self.start)):
            cc, acct, code = stores.get(sc, ("US", 0, None))
            days = calendar.monthrange(m.year, m.month)[1]
            for i in range(days):
                d = m + timedelta(days=i)
                if d > self.today:
                    break
                ks = by_day.get((d, "shopify", cc, int(acct or 0)))
                if not (ks and self.allocate(_f(spend) / days, ks, rev, "ads")):
                    put(d, "shopify", cc, acct, 0, _f(spend) / days, code)
        self.notes["ads"] = (None, f"QC thật Amazon + Wayfair + Shopify nhập tay; ${orphan:,.0f} QC rơi vào ngày SP "
                                   f"không có đơn (vẫn tính vào SP đó)")

    # ------------------------------------------------------------ 6. phí kho & vận chuyển
    def warehouse(self) -> None:
        by_m_cc = self.index(lambda k, r: [(month_of(k[0]), k[2])] if k[4] not in ("FBA", "CG", "-") else [])
        by_m_cc_pid = self.index(lambda k, r: [(month_of(k[0]), k[2], k[5])] if k[4] not in ("FBA", "CG", "-") else [])
        by_m_acct = self.index(lambda k, r: [(month_of(k[0]), k[3])] if k[4] not in ("FBA", "CG", "-") else [])
        by_m_cg = self.index(lambda k, r: [(month_of(k[0]), k[3])] if k[4] == "CG" else [])
        by_m_cc_cg = self.index(lambda k, r: [(month_of(k[0]), k[2])] if k[4] == "CG" else [])
        months = sorted({month_of(k[0]) for k in self.rows})
        rev = lambda r: r["net_rev"]

        def with_estimate(name: str, field: str, actual: dict, groups: dict, alloc) -> date | None:
            """actual: {(month, nhóm): số tiền USD}; groups: {(month, nhóm): [keys]} làm mẫu số tỷ lệ ước tính.
            Tháng ≤ tháng cuối có số liệu: phân bổ thật (alloc); tháng sau: tỷ lệ 3 tháng gần nhất × doanh thu."""
            have = sorted({m for m, _ in actual})
            last = have[-1] if have else None
            for (m, g), v in actual.items():
                if m >= self.start:
                    alloc(m, g, v)
            if not last:
                return None
            ms = [m for m in have if m <= last][-EST_MONTHS:]
            for g in {g for _, g in groups}:
                fee = sum(actual.get((m, g), 0.0) for m in ms)
                base = sum(rev(self.rows[k]) for m in ms for k in groups.get((m, g), []))
                ratio = fee / base if base else 0.0
                for m in months:
                    if m <= last:
                        continue
                    for k in groups.get((m, g), []):
                        amt = ratio * rev(self.rows[k])
                        self.rows[k][field] += amt
                        self.rows[k]["warehouse_fee_est"] += amt
            return next_month(last) - timedelta(days=1)

        # 3PL: tháng × SKU × nước (mã kho bắt đầu bằng nước), tiền địa phương
        tpl = defaultdict(float)
        tpl_pid = defaultdict(float)
        for mon, pid, wh, amt in self.q("""SELECT month, product_id, warehouse_id, SUM(amount) FROM {stg}.fee__warehouse_local
                                           GROUP BY month, product_id, warehouse_id"""):
            try:
                m = date.fromisoformat(f"{mon}-01")
            except ValueError:
                continue
            cc = (wh or "US")[:2].upper()
            usd = _f(amt) * self.rate(min(next_month(m) - timedelta(days=1), self.today), CC_CCY.get(cc, "USD"))
            tpl[(m, cc)] += usd
            tpl_pid[(m, cc, int(pid or 0))] += usd

        def alloc_3pl(m, cc, v):
            done = 0.0
            for (mm, c, pid), x in tpl_pid.items():
                if mm == m and c == cc and self.allocate(x, by_m_cc_pid.get((m, cc, pid), []), lambda r: r["units"], "wh_3pl"):
                    done += x
            if v - done:
                self.allocate(v - done, by_m_cc.get((m, cc), []), rev, "wh_3pl")
        to_3pl = with_estimate("3pl", "wh_3pl", tpl, by_m_cc, alloc_3pl)

        # CastleGate: tháng × tài khoản Wayfair
        wacct = {a: s for a, s in self.q("SELECT account_id, store_account_id FROM {mart}.dim_wf_account")}
        cg = defaultdict(float)
        cg_cc = {}
        for m, acc, ccy, amt in self.q("""SELECT DATE_FORMAT(charge_date, '%Y-%m-01'), account_id,
                    COALESCE(original_currency, local_currency), SUM(original_charge_amount)
                FROM {stg}.fee__wayfair_castlegate_fulfillment WHERE original_charge_amount IS NOT NULL
                GROUP BY DATE_FORMAT(charge_date, '%Y-%m-01'), account_id, COALESCE(original_currency, local_currency)"""):
            m = date.fromisoformat(str(m))
            acct = int(wacct.get(str(acc)) or 0)
            cg[(m, acct)] += _f(amt) * self.rate(min(next_month(m) - timedelta(days=1), self.today), ccy or "USD")

        def alloc_cg(m, acct, v):
            if not self.allocate(v, by_m_cg.get((m, acct), []), rev, "wh_cg"):
                ks = [k for k in self.rows if k[1] == "wayfair" and month_of(k[0]) == m and k[3] == acct]
                self.allocate(v, ks, rev, "wh_cg")
        to_cg = with_estimate("cg", "wh_cg", cg, by_m_cg, alloc_cg)

        # nhãn ship (shipworks): tháng × kênh bán → tài khoản; số liệu cập nhật hằng ngày nên tháng hiện tại là số thật
        chan = {sc: (cc, acct) for sc, cc, acct in self.q(
            "SELECT sales_channel_id, country_code, store_account_id FROM {mart}.map_channel_node")}
        ship = defaultdict(float)
        last_print = None
        for m, sc, amt, lp in self.q("""SELECT DATE_FORMAT(print_date, '%Y-%m-01'), sales_channel_id, SUM(cost), MAX(print_date)
                FROM {stg}.cs__shipworks_shipment WHERE voided_date IS NULL AND cost > 0 AND print_date <= :t
                GROUP BY DATE_FORMAT(print_date, '%Y-%m-01'), sales_channel_id""", t=self.today):
            m = date.fromisoformat(str(m))
            if m < self.start:
                continue
            last_print = max(last_print or lp, lp)
            cc, acct = chan.get(sc, ("US", 0))
            ks = by_m_acct.get((m, int(acct or 0))) or by_m_cc.get((m, cc), [])
            if not self.allocate(_f(amt), ks, rev, "wh_ship"):
                self.allocate(_f(amt), by_m_cc.get((m, cc), []), rev, "wh_ship")
        self.notes["wh_3pl"] = (to_3pl, "phí 3PL theo tháng × SKU (fee__warehouse_local)")
        self.notes["wh_cg"] = (to_cg, "phí CastleGate theo tháng × tài khoản")
        self.notes["wh_ship"] = (last_print.date() if isinstance(last_print, datetime) else last_print,
                                 "chi phí nhãn ship theo tháng in nhãn × kênh bán")

    # ------------------------------------------------------------ 7. phí vận hành
    @staticmethod
    def _op_cols(ch: str, fulfil: str, code: str) -> list[str]:
        """Cột của sheet phí vận hành cho một dòng, theo thứ tự ưu tiên."""
        code = (code or "").upper()
        if ch == "amazon":
            first = "amazon by marketplace" if fulfil == "FBA" else "amazon by merchant"
        elif ch == "wayfair":
            first = "wayfair by marketplace" if fulfil == "CG" else "wayfair dropship"
        elif ch == "shopify":
            first = "shopify by merchant"
        elif code.startswith("EBAY"):
            first = "ebay by merchant"
        elif code.startswith("WM"):
            first = "walmart by merchant"
        elif code.startswith("ETSY"):
            first = "etsy by merchant"
        elif code.startswith("CATCH"):
            first = "catch by merchant"
        elif code.startswith("MYDEAL"):
            first = "mydeals by merchant"
        elif code.startswith("AVC"):
            first = "amazon dropship"
        elif code.startswith("WS"):
            first = "wholesales wholesales"
        else:
            first = ""
        base = "fba" if fulfil == "FBA" else "cg" if fulfil == "CG" else "fbm"
        return list(dict.fromkeys(c for c in (first, base, "fbm") if c))

    def operation_fee(self) -> None:
        """Phí vận hành = phí mỗi đơn vị (sheet công ty, SKU × tháng × nước × kênh) × số đơn vị. Tháng chưa có trên sheet
        dùng tháng gần nhất trước đó của SKU; SKU không có trên sheet ước theo tỷ lệ phí / DT của kênh × nước."""
        fee = defaultdict(dict)  # (pid, cc, col) -> {month: (fee, ccy)}
        for pid, m, cc, col, ccy, v in self.q("""SELECT product_id, month, country_code, col, currency_code, fee
                FROM {mart}.ref_operation_fee_unit WHERE product_id IS NOT NULL"""):
            fee[(pid, cc, col)][m] = (float(v), ccy)
        p = {n: float(v) for n, v in self.q("SELECT param_name, param_value FROM {stg}.input_pl_operation_fee_param")}
        au_rate = p.get("non_us_ca_revenue_rate", 0.06)
        last = max((m for d in fee.values() for m in d), default=None)
        costed = defaultdict(lambda: [0.0, 0.0])
        missing = []
        for k, r in self.rows.items():
            if not r["units"]:
                continue
            d, ch, cc, fulfil, pid = k[0], k[1], k[2], k[4], k[5]
            m = month_of(d)
            hit = None
            for col in self._op_cols(ch, fulfil, r["co"]):
                months = fee.get((pid, cc, col))
                if months:
                    usable = [x for x in months if x <= m]
                    if usable:
                        hit = months[max(usable)]
                        break
            if hit is None:
                missing.append(k)
                continue
            v, ccy = hit
            r["operation_fee"] = v * r["units"] * self.rate(d, ccy)
            for ck in ((ch, cc), (cc,), ()):
                costed[ck][0] += r["net_rev"]
                costed[ck][1] += r["operation_fee"]
        for k in missing:
            r = self.rows[k]
            ratio = None
            for ck in ((k[1], k[2]), (k[2],), ()):
                s, c = costed.get(ck, (0, 0))
                if s > 0:
                    ratio = c / s
                    break
            if ratio is None:
                ratio = au_rate if k[2] == "AU" else 0.0
            r["operation_fee"] = r["operation_fee_est"] = r["net_rev"] * ratio
        self.notes["operation_fee"] = (None,
                                       f"phí vận hành mỗi đơn vị theo sheet công ty; {len(missing)} dòng không có SKU "
                                       f"trên sheet, ước theo tỷ lệ của kênh × nước")

    # ------------------------------------------------------------ tổng hợp và ghi
    def finish(self) -> None:
        for r in self.rows.values():
            r["channel_fee"] = r["fee_commission"] + r["fee_fulfil"] + r["fee_other"]
            r["pl4"] = r["net_rev"] - r["channel_fee"] - r["cogs"] - r["return_fee"] - r["ads"]
            r["warehouse_fee"] = r["wh_3pl"] + r["wh_fba"] + r["wh_cg"] + r["wh_ship"]
            r["pl5"] = r["pl4"] - r["warehouse_fee"] - r["operation_fee"]

    def write(self) -> int:
        cols = ["report_date", "ch", "cc", "acct", "fulfil", "product_id", "co", *FIELDS]
        data = []
        for k, r in self.rows.items():
            if k[0] < self.start:
                continue
            data.append(dict(zip(cols[:6], k), co=(r["co"] or "")[:100], **{f: r[f] for f in FIELDS}))
        self.conn.execute(text(f"DELETE FROM {self.mart}.fact_pnl_daily WHERE report_date >= :s"), {"s": self.start})
        sql = text(f"INSERT INTO {self.mart}.fact_pnl_daily ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})")
        for i in range(0, len(data), 5000):
            self.conn.execute(sql, data[i:i + 5000])
        now = datetime.now()
        self.conn.execute(text(f"DELETE FROM {self.mart}.pnl_run"))
        if self.notes:
            self.conn.execute(text(f"INSERT INTO {self.mart}.pnl_run (source, actual_to, note, computed_at) "
                                   f"VALUES (:s, :a, :n, :t)"),
                              [{"s": s, "a": a, "n": n[:500], "t": now} for s, (a, n) in self.notes.items()])
        return len(data)

    def run(self) -> int:
        self.load_fx()
        self.load_sales()
        for k, r in self.rows.items():
            r["_fba"] = k[4] == "FBA"
        self.amazon_fees()
        self.other_channel_fees()
        self.amazon_account_fees()
        self.cogs()
        if not COGS_INCLUDES_RETURN_AND_OPERATION:
            self.return_fee()
        self.ads()
        self.warehouse()
        if not COGS_INCLUDES_RETURN_AND_OPERATION:
            self.operation_fee()
        else:
            self.notes["operation_fee"] = (None, "không trừ riêng: giá vốn chuẩn BOD đã gồm phí vận hành và phí hoàn hàng")
        self.finish()
        return self.write()


def compute(conn, mart: str, stg: str, start: date = PNL_START) -> int:
    return Pnl(conn, mart, stg, start).run()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from app.config import settings
    from app.db import get_engine
    t0 = time.time()
    with get_engine().begin() as conn:
        n = compute(conn, f"`{settings.mart_schema}`", f"`{settings.staging_schema}`")
    print(f"[OK] pnl rows={n} {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
