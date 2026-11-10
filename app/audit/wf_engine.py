"""Bộ máy audit Wayfair Sponsored Products: file bulk WSP (cấu trúc, bid, daily cap hiện tại) + số liệu mart → đề xuất.

Khác Amazon: không có ad group; keyword không có ID và không có trạng thái riêng (chỉ đổi bid hoặc REMOVE); negative
chỉ ở cấp campaign keyword; campaign Product Targeting đặt bid theo listing. ACoS tính trên doanh số giá sỉ.
Tiền theo store của campaign (wayfair.ca = CAD, còn lại USD), cùng tiền với bid trong file.
Ghi chung bảng audit_run / audit_proposal với Amazon (profile_id = 'wf:<account_id>').
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import text

from app.audit import wf_rules
from app.audit.engine import _metrics, _pct
from app.audit.wf_bulk import norm_key
from app.db import fetch_all, fetch_one, get_engine

ACTIVE = "ACTIVE"
EXACT = "SMART EXACT"
MAX_KEYWORD_LEN = 100  # giới hạn độ dài keyword của Wayfair


def keyword_object_id(campaign_id: str, keyword: str, match_type: str) -> str:
    """Keyword Wayfair không có ID trong file bulk → mã ổn định từ (campaign, keyword, match type), vừa VARCHAR(25)."""
    k = "|".join(norm_key(campaign_id, keyword, match_type))
    return "K:" + hashlib.md5(k.encode("utf-8")).hexdigest()[:20]


class Context:
    """Cấu trúc tài khoản lấy từ file bulk Wayfair."""

    def __init__(self, rows: list[dict]):
        self.campaigns = {}
        self.keywords, self.listings = [], []
        self.exact_texts = set()          # keyword Smart Exact ở mọi campaign trong file
        self.camp_exact = defaultdict(int)  # campaign -> số keyword Smart Exact
        self.camp_parts = defaultdict(set)  # campaign keyword -> part number đang bật
        self.neg = set()                    # (campaign_id, text, 'EXACT' | 'PHRASE')
        self.negatives = []
        for r in rows:
            if r["sheet"] == "campaign":
                self.campaigns[r["campaign_id"]] = r
        for r in rows:
            s = r["sheet"]
            if s == "keyword":
                self.keywords.append(r)
                if (r["match_type"] or "").upper() == EXACT:
                    self.exact_texts.add(norm_key(None, r["item"])[1])
                    self.camp_exact[r["campaign_id"]] += 1
            elif s == "listing":
                self.listings.append(r)
            elif s == "part" and (r["state"] or "").upper() == ACTIVE and r["item"]:
                self.camp_parts[r["campaign_id"]].add(r["item"].strip().upper())
            elif s == "negative":
                self.neg.add((r["campaign_id"], norm_key(None, r["item"])[1], (r["match_type"] or "").upper()))
                self.negatives.append(r)

    def camp(self, campaign_id: str) -> dict:
        return self.campaigns.get(campaign_id) or {}

    def active(self, campaign_id: str) -> bool:
        return (self.camp(campaign_id).get("state") or "").upper() == ACTIVE

    def manual(self, campaign_id: str) -> bool:
        return (self.camp(campaign_id).get("bidding") or "").lower().startswith("manual")

    def hold_bid(self, campaign_id: str) -> bool:
        """Team ghi "không hạ bid" trong tên campaign (vd campaign Ranking) → không đề xuất giảm bid / hạ về sàn."""
        name = (self.camp(campaign_id).get("campaign_name") or "").lower()
        return "không hạ bid" in name or "khong ha bid" in name

    def keyword_campaign(self, campaign_id: str) -> bool:
        return "keyword" in (self.camp(campaign_id).get("targeting") or "").lower()

    def currency(self, campaign_id: str) -> str:
        return "CAD" if "wayfair.ca" in (self.camp(campaign_id).get("store") or "").lower() else "USD"

    def negated(self, campaign_id: str, term: str) -> bool:
        if (campaign_id, term, "EXACT") in self.neg:
            return True
        words = term.split()
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                if (campaign_id, " ".join(words[i:j]), "PHRASE") in self.neg:
                    return True
        return False

    def destination(self, src: str) -> str | None:
        """Campaign keyword đang bật, bid thủ công, cùng store, có part number chung với campaign nguồn, nhiều keyword
        Smart Exact nhất (thường là cặp "… Kw | Exact" của campaign "… Kw | Phrase")."""
        parts = self.camp_parts.get(src) or set()
        if not parts:
            return None
        store = self.camp(src).get("store")
        best, best_n = None, 0
        for cid, n in self.camp_exact.items():
            if cid != src and n > best_n and self.active(cid) and self.manual(cid) and self.keyword_campaign(cid) \
                    and self.camp(cid).get("store") == store and parts & self.camp_parts.get(cid, set()):
                best, best_n = cid, n
        return best


def run(upload_id: int) -> int:
    upload = fetch_one("SELECT id, profile_id FROM audit_bulk_upload WHERE id = :u", {"u": upload_id})
    profile_id = upload["profile_id"]
    cfg = wf_rules.load(profile_id)
    with get_engine().begin() as conn:
        run_id = conn.execute(text("""INSERT INTO audit_run (upload_id, profile_id, started_at, status, params)
                                      VALUES (:u, :p, :s, 'RUNNING', :j)"""),
                              {"u": upload_id, "p": profile_id, "s": datetime.now(), "j": json.dumps(cfg)}).lastrowid
    try:
        proposals, d0, d1 = build(upload_id, profile_id, cfg)
        for p in proposals:
            p.update(run_id=run_id, profile_id=profile_id)
        cols = ["run_id", "profile_id", "rule", "action", "campaign_id", "ad_group_id", "object_id", "campaign_name",
                "ad_group_name", "text", "source", "match_type", "current_bid", "new_bid", "impressions", "clicks", "spend",
                "orders", "sales", "acos_target", "reason", "default_on", "exportable", "currency_code"]
        with get_engine().begin() as conn:
            sql = text(f"INSERT INTO audit_proposal ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})")
            for i in range(0, len(proposals), 5000):
                conn.execute(sql, [{c: p.get(c) for c in cols} for p in proposals[i:i + 5000]])
            conn.execute(text("""UPDATE audit_run SET status = 'OK', finished_at = :f, n_proposals = :n,
                                 data_start = :d0, data_end = :d1 WHERE id = :r"""),
                         {"f": datetime.now(), "n": len(proposals), "d0": d0, "d1": d1, "r": run_id})
    except Exception as exc:
        with get_engine().begin() as conn:
            conn.execute(text("UPDATE audit_run SET status = 'FAILED', finished_at = :f, message = :m WHERE id = :r"),
                         {"f": datetime.now(), "m": str(exc).splitlines()[0][:1000], "r": run_id})
        raise
    return run_id


def build(upload_id: int, profile_id: str, cfg: dict) -> tuple[list[dict], object, object]:
    P = cfg["params"]
    account = wf_rules.account_id(profile_id)
    ctx = Context(fetch_all("SELECT * FROM audit_wf_bulk_row WHERE upload_id = :u", {"u": upload_id}))
    d1 = fetch_one("SELECT MAX(report_date) AS d FROM fact_wf_campaign_daily WHERE account_id = :a", {"a": account})["d"]
    if d1 is None:
        raise ValueError("Tài khoản chưa có số liệu quảng cáo Wayfair trong mart")
    d0 = d1 - timedelta(days=int(P["lookback_days"]) - 1)
    imp_start = d1 - timedelta(days=int(P["no_imp_days"]) - 1)
    # Khoảng 1% đơn có doanh số giá sỉ = 0 nhưng có giá lẻ (lỗi nguồn): ước tính giá sỉ = giá lẻ × tỉ lệ sỉ / lẻ của
    # tài khoản (:wr), để ACoS không thành vô cực
    wr = fetch_one("""SELECT SUM(sales) / NULLIF(SUM(retail_sales), 0) AS r FROM fact_wf_campaign_daily
                      WHERE account_id = :a AND report_date BETWEEN :d0 AND :d1 AND sales > 0""",
                   {"a": account, "d0": d0, "d1": d1})["r"]
    q = {"a": account, "d0": d0, "d1": d1, "s": imp_start, "wr": float(wr or 0.5)}

    # ---- số liệu
    kw_stats, kw_imp = {}, set()
    for r in fetch_all("""
        SELECT campaign_id, keyword, match_type, SUM(impressions) impressions, SUM(clicks) clicks, SUM(cost) cost,
               SUM(orders) orders, SUM(CASE WHEN COALESCE(sales, 0) = 0 AND orders > 0 THEN COALESCE(retail_sales, 0) * :wr ELSE COALESCE(sales, 0) END) sales, SUM(CASE WHEN report_date >= :s THEN impressions ELSE 0 END) imp_recent
        FROM fact_wf_keyword_daily WHERE account_id = :a AND report_date BETWEEN :d0 AND :d1
        GROUP BY campaign_id, keyword, match_type""", q):
        k = norm_key(r["campaign_id"], r["keyword"] or "", r["match_type"])
        s = kw_stats.setdefault(k, {"impressions": 0, "clicks": 0, "cost": 0.0, "orders": 0, "sales": 0.0})
        for f in s:
            s[f] += float(r[f] or 0)
        if float(r["imp_recent"] or 0) > 0:
            kw_imp.add(k)
    camp_stats = {r["campaign_id"]: r for r in fetch_all("""
        SELECT campaign_id, SUM(impressions) impressions, SUM(clicks) clicks, SUM(cost) cost, SUM(orders) orders, SUM(CASE WHEN COALESCE(sales, 0) = 0 AND orders > 0 THEN COALESCE(retail_sales, 0) * :wr ELSE COALESCE(sales, 0) END) sales,
               SUM(CASE WHEN report_date >= :s THEN impressions ELSE 0 END) imp_recent,
               (SELECT MIN(x.report_date) FROM fact_wf_campaign_daily x WHERE x.campaign_id = f.campaign_id) AS first_date
        FROM fact_wf_campaign_daily f WHERE account_id = :a AND report_date BETWEEN :d0 AND :d1 GROUP BY campaign_id""", q)}
    # campaign chạy chưa đủ số ngày xét "không có impression" (keyword còn mới) thì không áp quy tắc 6
    young = {cid for cid, r in camp_stats.items() if r["first_date"] and r["first_date"] > imp_start}
    acct = {k: sum(float(c[k] or 0) for c in camp_stats.values()) for k in ("clicks", "cost", "orders", "sales")}
    listing_stats = {(r["campaign_id"], r["listing_id"]): r for r in fetch_all("""
        SELECT campaign_id, listing_id, SUM(impressions) impressions, SUM(clicks) clicks, SUM(cost) cost, SUM(orders) orders, SUM(CASE WHEN COALESCE(sales, 0) = 0 AND orders > 0 THEN COALESCE(retail_sales, 0) * :wr ELSE COALESCE(sales, 0) END) sales
        FROM fact_wf_product_daily WHERE account_id = :a AND report_date BETWEEN :d0 AND :d1 GROUP BY campaign_id, listing_id""", q)}
    listing_group = {r["listing_id"]: r["group_id"] for r in fetch_all(
        "SELECT listing_id, group_id FROM dim_wf_listing WHERE account_id = :a AND group_id IS NOT NULL", q)}
    # nhóm SP của campaign = nhóm có spend lớn nhất (listing của campaign Product Targeting / listing gắn với keyword)
    camp_group_spend = defaultdict(lambda: defaultdict(float))
    for (cid, lid), r in listing_stats.items():
        if lid in listing_group:
            camp_group_spend[cid][listing_group[lid]] += float(r["cost"] or 0)
    for r in fetch_all("""SELECT campaign_id, listing_id, SUM(cost) cost FROM fact_wf_keyword_daily
                          WHERE account_id = :a AND report_date BETWEEN :d0 AND :d1 AND listing_id <> ''
                          GROUP BY campaign_id, listing_id""", q):
        if r["listing_id"] in listing_group:
            camp_group_spend[r["campaign_id"]][listing_group[r["listing_id"]]] += float(r["cost"] or 0)
    camp_group = {cid: max(g.items(), key=lambda kv: kv[1])[0] for cid, g in camp_group_spend.items() if g}

    def target_acos(cid: str, listing_id: str | None = None) -> float:
        g = listing_group.get(listing_id) if listing_id else None
        g = g if g is not None else camp_group.get(cid)
        return cfg["group_targets"].get(str(g), P["acos_target"]) if g is not None else P["acos_target"]

    def aov(cid: str) -> float:
        for s in (camp_stats.get(cid), acct):
            if s and float(s["orders"] or 0) >= 1:
                return float(s["sales"] or 0) / float(s["orders"])
        return 0.0

    def avg_cpc(*stats) -> float | None:
        for s in stats:
            if s and float(s["clicks"] or 0) > 0:
                return float(s["cost"] or 0) / float(s["clicks"])
        return None

    # ---- lịch sử đã xuất
    cooldown_from = datetime.now() - timedelta(days=int(P["cooldown_days"]))
    recent = {r["object_id"] for r in fetch_all("""
        SELECT DISTINCT object_id FROM audit_proposal WHERE profile_id = :p AND status = 'exported'
        AND exported_at >= :c AND object_id IS NOT NULL""", {"p": profile_id, "c": cooldown_from})}
    recent_terms = {(r["campaign_id"], r["text"]) for r in fetch_all("""
        SELECT DISTINCT campaign_id, text FROM audit_proposal WHERE profile_id = :p AND status = 'exported'
        AND exported_at >= :c AND action IN ('negative', 'add_keyword')""", {"p": profile_id, "c": cooldown_from})}
    no_imp_rounds = {r["object_id"]: r["n"] for r in fetch_all("""
        SELECT object_id, COUNT(*) n FROM audit_proposal WHERE profile_id = :p AND status = 'exported' AND rule = 'no_imp'
        AND action = 'bid' GROUP BY object_id""", {"p": profile_id})}

    floor, ceil_mult = float(P["bid_floor"]), float(P["bid_ceiling_cpc_mult"])
    out: list[dict] = []

    def base(cid: str, rule: str, action: str, **kw) -> dict:
        d = {"rule": rule, "action": action, "campaign_id": cid, "campaign_name": ctx.camp(cid).get("campaign_name"),
             "currency_code": ctx.currency(cid), "default_on": 1, "exportable": 1}
        d.update(kw)
        return d

    def bid_rule(bid: float, m: dict, tgt: float, cpa: float, zero_mult: float | None) -> tuple:
        """Quy tắc ACoS chung cho keyword và listing → (rule, action, bid mới, lý do) hoặc (None, ...).
        zero_mult: ngưỡng chi khi 0 đơn (× CPA) để đề xuất mạnh hơn giảm bid (None = tắt)."""
        if m["orders"] == 0:
            if zero_mult and cpa > 0 and m["spend"] >= zero_mult * cpa:
                return "pause", "floor", None, f"{m['clicks']} click, chi {m['spend']:.2f} mà 0 đơn (≥ {zero_mult:g}× CPA mục tiêu {cpa:.2f})"
            if not P["bid_down_enabled"]:
                return None, None, None, None
            return "bid_down", "bid", bid * (1 - P["bid_max_down"]), f"{m['clicks']} click, 0 đơn → giảm tối đa {_pct(P['bid_max_down'])}"
        acos = m["spend"] / m["sales"] if m["sales"] else float("inf")
        if acos > tgt and P["bid_down_enabled"]:
            return "bid_down", "bid", max(bid * tgt / acos, bid * (1 - P["bid_max_down"])), f"ACoS {_pct(acos)} > mục tiêu {_pct(tgt)}"
        if acos < P["bid_up_acos_ratio"] * tgt and P["bid_up_enabled"]:
            new = min(bid * tgt / acos if acos > 0 else bid * (1 + P["bid_max_up"]), bid * (1 + P["bid_max_up"]))
            if m["clicks"]:
                new = min(new, ceil_mult * m["spend"] / m["clicks"])
            return "bid_up", "bid", new, f"ACoS {_pct(acos)} < {P['bid_up_acos_ratio']:g}× mục tiêu {_pct(tgt)}"
        return None, None, None, None

    # ---- quy tắc 3–6: keyword trong campaign keyword đang chạy, bid thủ công
    for r in ctx.keywords:
        cid = r["campaign_id"]
        if not (ctx.active(cid) and ctx.manual(cid)) or not r["bid"]:
            continue
        oid = keyword_object_id(cid, r["item"], r["match_type"])
        if oid in recent:
            continue
        k = norm_key(cid, r["item"], r["match_type"])
        bid = float(r["bid"])
        m = _metrics(kw_stats.get(k))
        tgt = target_acos(cid)
        cpa = tgt * aov(cid)
        common = dict(object_id=oid, text=r["item"], match_type=r["match_type"], current_bid=bid, acos_target=tgt, **m)
        rule = action = new = reason = None
        if m["clicks"] >= P["min_clicks"]:
            rule, action, new, reason = bid_rule(bid, m, tgt, cpa, P["pause_cpa_mult"] if P["pause_enabled"] else None)
            if rule in ("bid_down", "pause") and ctx.hold_bid(cid):
                continue
        elif P["no_imp_enabled"] and k not in kw_imp and cid not in young \
                and float((camp_stats.get(cid) or {}).get("imp_recent") or 0) > 0 \
                and bid >= floor:
            rounds = no_imp_rounds.get(oid, 0)
            if rounds >= P["no_imp_max_rounds"]:
                rule, action = "no_imp", "remove"
                reason = f"Không có impression {int(P['no_imp_days'])} ngày dù đã tăng bid {rounds} lần → gỡ khỏi campaign (REMOVE)"
            else:
                cpc = avg_cpc(camp_stats.get(cid), acct)
                new = bid * (1 + P["no_imp_raise"])
                if cpc:
                    new = min(new, ceil_mult * cpc)
                rule, action = "no_imp", "bid"
                reason = f"Không có impression {int(P['no_imp_days'])} ngày → tăng {_pct(P['no_imp_raise'])} (lần {rounds + 1})"
        if not rule:
            continue
        if action == "remove":
            out.append(base(cid, rule, "remove", default_on=0, reason=reason, **common))
            continue
        if action == "floor":
            if bid <= floor:
                continue
            out.append(base(cid, rule, "bid", new_bid=round(floor, 2), default_on=0,
                            reason=reason + f" → hạ về sàn {floor:.2f} (Wayfair không có pause keyword)", **common))
            continue
        new = round(max(new, floor), 2)
        if abs(new - bid) < 0.01 or (rule in ("bid_up", "no_imp") and new <= bid) or (rule == "bid_down" and new >= bid):
            continue
        out.append(base(cid, rule, "bid", new_bid=new, reason=reason, **common))

    # ---- quy tắc 7: listing trong campaign Product Targeting
    if P["listing_enabled"]:
        export_down = int(P["listing_bid_down_export"])
        for r in ctx.listings:
            cid = r["campaign_id"]
            if not (ctx.active(cid) and ctx.manual(cid)) or (r["state"] or "").upper() != ACTIVE or not r["bid"]:
                continue
            oid = f"L:{cid}:{r['item']}"[:25]
            if oid in recent:
                continue
            lid = f"{r['item']}_{account}"
            bid = float(r["bid"])
            m = _metrics(listing_stats.get((cid, lid)))
            if m["clicks"] < P["min_clicks"]:
                continue
            tgt = target_acos(cid, lid)
            cpa = tgt * aov(cid)
            common = dict(object_id=oid, text=r["item"], ad_group_name=r["info"], match_type="LISTING", current_bid=bid,
                          acos_target=tgt, **m)
            rule, action, new, reason = bid_rule(bid, m, tgt, cpa, P["listing_off_cpa_mult"])
            if not rule or (rule in ("bid_down", "pause") and ctx.hold_bid(cid)):
                continue
            if rule == "pause":
                out.append(base(cid, "listing", "listing_off", default_on=0, reason=reason + " → tắt listing trong campaign", **common))
                continue
            new = round(max(new, floor), 2)
            if abs(new - bid) < 0.01 or (rule == "bid_up" and new <= bid) or (rule == "bid_down" and new >= bid):
                continue
            if rule == "bid_down" and not export_down:
                out.append(base(cid, "listing", "bid", new_bid=new, default_on=0, exportable=0, **common,
                                reason=reason + " · giảm bid listing: hạ tay trên WSP (file bulk Wayfair chỉ nhận bid listing ≥ bid hiện tại)"))
            else:
                out.append(base(cid, "listing", "bid", new_bid=new, reason=reason, **common))

    # ---- quy tắc 1, 2: search term (chỉ campaign keyword có số liệu search term)
    terms = fetch_all("""
        SELECT f.campaign_id, t.term, MAX(f.match_type) AS match_type,
               SUBSTRING(GROUP_CONCAT(DISTINCT f.keyword ORDER BY f.keyword SEPARATOR ' | '), 1, 500) AS source,
               SUM(f.impressions) impressions, SUM(f.clicks) clicks, SUM(f.cost) cost, SUM(f.orders) orders, SUM(CASE WHEN COALESCE(f.sales, 0) = 0 AND f.orders > 0 THEN COALESCE(f.retail_sales, 0) * :wr ELSE COALESCE(f.sales, 0) END) sales
        FROM fact_wf_search_term_daily f JOIN dim_term t ON t.term_id = f.term_id
        WHERE f.account_id = :a AND f.report_date BETWEEN :d0 AND :d1 AND f.term_id <> ''
        GROUP BY f.campaign_id, t.term""", q)
    harvest_best: dict[str, dict] = {}
    for s in terms:
        term = " ".join((s["term"] or "").split()).lower()
        cid = s["campaign_id"]
        if not term or not ctx.active(cid) or not ctx.keyword_campaign(cid):
            continue
        m = _metrics(s)
        tgt = target_acos(cid)
        if m["orders"] >= P["harvest_min_orders"] and P["harvest_enabled"]:
            acos = m["spend"] / m["sales"] if m["sales"] else float("inf")
            if acos <= P["harvest_acos_ratio"] * tgt and (s["match_type"] or "") != EXACT \
                    and term not in ctx.exact_texts and len(term) <= MAX_KEYWORD_LEN:
                prev = harvest_best.get(term)
                if not prev or m["orders"] > prev["m"]["orders"]:
                    harvest_best[term] = {"s": s, "m": m, "tgt": tgt, "acos": acos, "sources": (prev["sources"] if prev else []) + [s]}
                else:
                    prev["sources"].append(s)
        elif m["orders"] == 0 and P["negative_enabled"]:
            cpa = tgt * aov(cid)
            if cpa > 0 and m["spend"] >= P["negative_cpa_mult"] * cpa and not ctx.negated(cid, term) \
                    and (cid, term) not in recent_terms and len(term) <= MAX_KEYWORD_LEN:
                out.append(base(cid, "negative", "negative", text=term, source=s["source"], match_type=s["match_type"],
                                acos_target=tgt, **m,
                                reason=f"Chi {m['spend']:.2f}, {m['clicks']} click, 0 đơn (≥ {P['negative_cpa_mult']:g}× CPA mục tiêu {cpa:.2f})"))

    for term, h in harvest_best.items():
        s, m = h["s"], h["m"]
        dest = ctx.destination(s["campaign_id"])
        if (dest, term) in recent_terms or (s["campaign_id"], term) in recent_terms:
            continue
        cpc = m["spend"] / m["clicks"] if m["clicks"] else floor
        reason = f"{m['orders']} đơn, ACoS {_pct(h['acos'])} ≤ mục tiêu {_pct(h['tgt'])} (nguồn: {(s['match_type'] or '').lower()})"
        common = dict(text=term, source=s["source"], match_type=EXACT, new_bid=round(max(cpc, floor), 2), acos_target=h["tgt"], **m)
        if not dest:
            out.append(base(s["campaign_id"], "harvest", "add_keyword", default_on=0, exportable=0, **common,
                            reason=reason + " · chưa có campaign Smart Exact đang chạy cùng part number để thêm, cần tạo thủ công"))
            continue
        out.append(base(dest, "harvest", "add_keyword", reason=reason, **common))
        if P["harvest_add_negative"]:
            for src in h["sources"]:
                if src["campaign_id"] == dest or ctx.negated(src["campaign_id"], term):
                    continue
                out.append(base(src["campaign_id"], "harvest", "negative", text=term, source=src["source"],
                                match_type=src["match_type"], acos_target=h["tgt"], **_metrics(src),
                                reason="Chặn ở campaign nguồn sau khi thêm Smart Exact, để không tự cạnh tranh"))

    # ---- quy tắc 8: daily cap
    if P["budget_enabled"]:
        b0 = d1 - timedelta(days=int(P["budget_days"]) - 1)
        capped = defaultdict(int)
        for r in fetch_all("""
            SELECT f.campaign_id, f.report_date, SUM(f.cost) cost, MAX(b.daily_cap) cap
            FROM fact_wf_campaign_daily f
            JOIN fact_wf_budget_daily b ON b.campaign_id = f.campaign_id AND b.report_date = f.report_date
            WHERE f.account_id = :a AND f.report_date BETWEEN :b0 AND :d1 AND b.daily_cap > 0
            GROUP BY f.campaign_id, f.report_date""", {**q, "b0": b0}):
            if float(r["cost"] or 0) >= P["budget_util"] * float(r["cap"]):
                capped[r["campaign_id"]] += 1
        for cid, n in capped.items():
            c = ctx.camp(cid)
            if n < P["budget_capped_days"] or not ctx.active(cid) or f"C:{cid}" in recent:
                continue
            try:
                cap = float(c.get("daily_cap") or "")
            except ValueError:
                continue  # NO DAILY CAP
            st = _metrics(camp_stats.get(cid))
            tgt = target_acos(cid)
            if not st["orders"] or not st["sales"] or st["spend"] / st["sales"] > P["budget_acos_ratio"] * tgt:
                continue
            new = round(cap * (1 + P["budget_raise"]), 2)
            out.append(base(cid, "budget", "budget", object_id=f"C:{cid}", text=c.get("campaign_name"), match_type="DAILY CAP",
                            current_bid=cap, new_bid=new, acos_target=tgt, **st,
                            reason=f"Chạm ≥ {_pct(P['budget_util'])} daily cap {n}/{int(P['budget_days'])} ngày, "
                                   f"ACoS {_pct(st['spend'] / st['sales'])} ≤ mục tiêu {_pct(tgt)} → tăng {_pct(P['budget_raise'])}"))

    # ---- quy tắc 9: negative đang chặn search term từng ra đơn trong cùng campaign
    if P["conflict_enabled"]:
        c0 = d1 - timedelta(days=int(P["conflict_days"]) - 1)
        winners = defaultdict(list)
        for r in fetch_all("""
            SELECT f.campaign_id, t.term, SUM(f.orders) orders, SUM(CASE WHEN COALESCE(f.sales, 0) = 0 AND f.orders > 0 THEN COALESCE(f.retail_sales, 0) * :wr ELSE COALESCE(f.sales, 0) END) sales, SUM(f.cost) cost, SUM(f.clicks) clicks
            FROM fact_wf_search_term_daily f JOIN dim_term t ON t.term_id = f.term_id
            WHERE f.account_id = :a AND f.report_date BETWEEN :c0 AND :d1 AND f.term_id <> ''
            GROUP BY f.campaign_id, t.term HAVING SUM(f.orders) > 0""", {**q, "c0": c0}):
            winners[r["campaign_id"]].append(r)
        for n in ctx.negatives:
            if not ctx.active(n["campaign_id"]):
                continue
            text_ = norm_key(None, n["item"])[1]
            phrase = (n["match_type"] or "").upper() == "PHRASE"
            hits = [w for w in winners.get(n["campaign_id"], [])
                    if (f" {text_} " in f" {w['term'].lower()} " if phrase else w["term"].lower() == text_)]
            if not hits:
                continue
            orders = sum(int(w["orders"]) for w in hits)
            out.append(base(n["campaign_id"], "conflict", "warn", text=n["item"], source=", ".join(w["term"] for w in hits[:5])[:500],
                            match_type=n["match_type"], orders=orders, sales=sum(float(w["sales"]) for w in hits),
                            spend=sum(float(w["cost"]) for w in hits), clicks=sum(int(w["clicks"]) for w in hits),
                            default_on=0, exportable=0,
                            reason=f"Negative {(n['match_type'] or '').lower()} chặn search term đã ra {orders} đơn trong "
                                   f"{int(P['conflict_days'])} ngày: " + ", ".join(w["term"] for w in hits[:3])))
    return out, d0, d1
