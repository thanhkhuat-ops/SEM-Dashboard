"""Bộ máy audit từ khóa Sponsored Products: file bulk (cấu trúc, bid hiện tại) + số liệu mart → đề xuất.

Tiền theo tiền tệ của tài khoản (cột cost / sales gốc của mart), vì bid trong file bulk là tiền gốc.
Quy tắc và tham số: app/audit/rules.py. Mỗi đề xuất ghi lý do và số liệu để người duyệt.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import text

from app.audit import rules
from app.audit.bulk import ASIN_RE
from app.db import fetch_all, fetch_one, get_engine

ACTIVE = "enabled"


def _metrics(m: dict | None) -> dict:
    m = m or {}
    return {"impressions": int(m.get("impressions") or 0), "clicks": int(m.get("clicks") or 0),
            "spend": float(m.get("cost") or 0), "orders": int(m.get("orders") or 0), "sales": float(m.get("sales") or 0)}


def _pct(v: float) -> str:
    return f"{v * 100:.0f}%"


class Context:
    """Cấu trúc tài khoản lấy từ file bulk."""

    def __init__(self, rows: list[dict]):
        self.campaigns, self.adgroups = {}, {}
        self.keywords, self.targets = [], []
        self.ag_skus = defaultdict(set)
        self.neg_ag, self.neg_camp = set(), set()  # (ad_group_id|campaign_id, text, 'exact'|'phrase')
        self.neg_pt_ag = set()  # (ad_group_id, asin)
        self.negatives = []  # để kiểm tra xung đột
        self.exact_texts = set()  # keyword Exact mọi trạng thái trừ archived
        self.asin_targets = set()
        self.ag_exact = defaultdict(int)  # ad group -> số keyword Exact đang bật
        self.ag_asin = defaultdict(int)
        for r in rows:
            e = r["entity"]
            if e == "Campaign":
                self.campaigns[r["campaign_id"]] = r
            elif e == "Ad group":
                self.adgroups[r["ad_group_id"]] = r
        for r in rows:
            e, state = r["entity"], (r["state"] or "").lower()
            if e == "Keyword":
                self.keywords.append(r)
                if (r["match_type"] or "").lower() == "exact" and state != "archived":
                    self.exact_texts.add((r["keyword_text"] or "").lower())
                    if self.active(r):
                        self.ag_exact[r["ad_group_id"]] += 1
            elif e == "Product targeting":
                self.targets.append(r)
                expr = (r["expression"] or "").lower()
                if expr.startswith('asin="') and state != "archived":
                    self.asin_targets.add(expr[6:-1])
                    if self.active(r):
                        self.ag_asin[r["ad_group_id"]] += 1
            elif e == "Product ad" and state == ACTIVE and r["sku"]:
                self.ag_skus[r["ad_group_id"]].add(r["sku"])
            elif e in ("Negative keyword", "Campaign negative keyword") and state == ACTIVE:
                kind = "phrase" if "phrase" in (r["match_type"] or "").lower() else "exact"
                t = (r["keyword_text"] or "").lower()
                if e == "Negative keyword":
                    self.neg_ag.add((r["ad_group_id"], t, kind))
                else:
                    self.neg_camp.add((r["campaign_id"], t, kind))
                self.negatives.append(r)
            elif e in ("Negative product targeting", "Campaign Negative Product Targeting") and state == ACTIVE:
                expr = (r["expression"] or "").lower()
                if expr.startswith('asin="'):
                    self.neg_pt_ag.add((r["ad_group_id"] or r["campaign_id"], expr[6:-1]))

    def active(self, r: dict) -> bool:
        c = self.campaigns.get(r["campaign_id"]) or {}
        a = self.adgroups.get(r["ad_group_id"]) or {}
        return ((r["state"] or "").lower() == ACTIVE and (c.get("state") or "").lower() == ACTIVE
                and (a.get("state") or ACTIVE).lower() == ACTIVE)

    def manual(self, campaign_id: str) -> bool:
        return ((self.campaigns.get(campaign_id) or {}).get("targeting_type") or "").lower() == "manual"

    def negated(self, ad_group_id: str, campaign_id: str, term: str) -> bool:
        if ASIN_RE.match(term):
            return (ad_group_id, term) in self.neg_pt_ag or (campaign_id, term) in self.neg_pt_ag
        for scope, key in ((self.neg_ag, ad_group_id), (self.neg_camp, campaign_id)):
            if (key, term, "exact") in scope:
                return True
        # negative phrase: chỉ kiểm tra các cụm con của term (tránh duyệt toàn bộ danh sách)
        words = term.split()
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                sub = " ".join(words[i:j])
                if (ad_group_id, sub, "phrase") in self.neg_ag or (campaign_id, sub, "phrase") in self.neg_camp:
                    return True
        return False

    def destination(self, src_ag: str, asin: bool) -> str | None:
        """Ad group manual đang bật, cùng SKU với ad group nguồn, đã có keyword Exact (hoặc target ASIN)."""
        skus = self.ag_skus.get(src_ag) or set()
        if not skus:
            return None
        counts = self.ag_asin if asin else self.ag_exact
        best, best_n = None, 0
        for ag, n in counts.items():
            a = self.adgroups.get(ag) or {}
            if n > best_n and self.manual(a.get("campaign_id")) and (a.get("state") or "").lower() == ACTIVE \
                    and (self.campaigns.get(a.get("campaign_id")) or {}).get("state", "").lower() == ACTIVE \
                    and skus & self.ag_skus.get(ag, set()):
                best, best_n = ag, n
        return best


def run(upload_id: int) -> int:
    upload = fetch_one("SELECT id, profile_id FROM audit_bulk_upload WHERE id = :u", {"u": upload_id})
    profile_id = upload["profile_id"]
    cfg = rules.load(profile_id)
    started = datetime.now()
    with get_engine().begin() as conn:
        run_id = conn.execute(text("""INSERT INTO audit_run (upload_id, profile_id, started_at, status, params)
                                      VALUES (:u, :p, :s, 'RUNNING', :j)"""),
                              {"u": upload_id, "p": profile_id, "s": started, "j": json.dumps(cfg)}).lastrowid
    try:
        proposals, d0, d1 = build(upload_id, profile_id, cfg)
        for p in proposals:
            p.update(run_id=run_id, profile_id=profile_id)
        cols = ["run_id", "profile_id", "rule", "action", "campaign_id", "ad_group_id", "object_id", "campaign_name",
                "ad_group_name", "text", "source", "match_type", "current_bid", "new_bid", "impressions", "clicks", "spend",
                "orders", "sales", "acos_target", "reason", "default_on", "exportable"]
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
    ctx = Context(fetch_all("SELECT * FROM audit_bulk_row WHERE upload_id = :u", {"u": upload_id}))
    d1 = fetch_one("SELECT MAX(report_date) AS d FROM fact_target_daily WHERE profile_id = :p AND ad_type = 'SP'",
                   {"p": profile_id})["d"]
    if d1 is None:
        raise ValueError("Tài khoản chưa có số liệu Sponsored Products trong mart")
    d0 = d1 - timedelta(days=int(P["lookback_days"]) - 1)
    q = {"p": profile_id, "d0": d0, "d1": d1}

    # ---- số liệu theo keyword / target
    tm = {r["target_id"]: r for r in fetch_all("""
        SELECT target_id, SUM(impressions) impressions, SUM(clicks) clicks, SUM(cost) cost, SUM(orders) orders, SUM(sales) sales
        FROM fact_target_daily WHERE profile_id = :p AND ad_type = 'SP' AND report_date BETWEEN :d0 AND :d1
        GROUP BY target_id""", q)}
    imp_start = d1 - timedelta(days=int(P["no_imp_days"]) - 1)
    has_imp = {r["target_id"] for r in fetch_all("""
        SELECT DISTINCT target_id FROM fact_target_daily WHERE profile_id = :p AND ad_type = 'SP'
        AND report_date BETWEEN :s AND :d1 AND impressions > 0""", {**q, "s": imp_start})}
    # ad group có impression trong cùng khoảng: chỉ khi đó keyword 0 impression mới là vấn đề của riêng keyword
    # (cả ad group không chạy thường do hết ngân sách / hết hàng / campaign tắt, tăng bid không giải quyết)
    ag_has_imp = {r["adgroup_id"] for r in fetch_all("""
        SELECT DISTINCT adgroup_id FROM fact_target_daily WHERE profile_id = :p AND ad_type = 'SP'
        AND report_date BETWEEN :s AND :d1 AND impressions > 0""", {**q, "s": imp_start})}
    ag_stats = {r["adgroup_id"]: r for r in fetch_all("""
        SELECT adgroup_id, campaign_id, SUM(clicks) clicks, SUM(cost) cost, SUM(orders) orders, SUM(sales) sales
        FROM fact_target_daily WHERE profile_id = :p AND ad_type = 'SP' AND report_date BETWEEN :d0 AND :d1
        GROUP BY adgroup_id, campaign_id""", q)}
    camp_stats = defaultdict(lambda: {"clicks": 0, "cost": 0.0, "orders": 0, "sales": 0.0})
    acct = {"clicks": 0, "cost": 0.0, "orders": 0, "sales": 0.0}
    for r in ag_stats.values():
        for k in acct:
            camp_stats[r["campaign_id"]][k] += float(r[k] or 0)
            acct[k] += float(r[k] or 0)
    ag_group = {r["adgroup_id"]: r["group_id"] for r in fetch_all("""
        SELECT m.adgroup_id, m.group_id FROM map_adgroup_product m JOIN dim_campaign c ON c.campaign_id = m.campaign_id AND c.ad_type = 'SP'
        WHERE m.ad_type = 'SP' AND m.is_dominant = 1 AND c.profile_id = :p""", q)}

    def aov(ag: str, camp: str) -> float:
        for s in (ag_stats.get(ag), camp_stats.get(camp), acct):
            if s and float(s["orders"] or 0) >= 1:
                return float(s["sales"]) / float(s["orders"])
        return 0.0

    def avg_cpc(*stats) -> float | None:
        for s in stats:
            if s and float(s["clicks"] or 0) > 0:
                return float(s["cost"]) / float(s["clicks"])
        return None

    def target_acos(ag: str, camp: str) -> float:
        c = ctx.campaigns.get(camp) or {}
        return rules.acos_target(P["acos_target"], cfg["group_targets"], cfg["portfolio_targets"],
                                 c.get("portfolio_id"), ag_group.get(ag))

    # ---- lịch sử đã xuất (thời gian chờ, số lần tăng do không có impression)
    cooldown_from = datetime.now() - timedelta(days=int(P["cooldown_days"]))
    recent = {r["object_id"] for r in fetch_all("""
        SELECT DISTINCT object_id FROM audit_proposal WHERE profile_id = :p AND status = 'exported'
        AND exported_at >= :c AND object_id IS NOT NULL""", {"p": profile_id, "c": cooldown_from})}
    recent_terms = {(r["ad_group_id"], r["text"]) for r in fetch_all("""
        SELECT DISTINCT ad_group_id, text FROM audit_proposal WHERE profile_id = :p AND status = 'exported'
        AND exported_at >= :c AND action IN ('negative', 'negative_target', 'add_keyword', 'add_target')""",
        {"p": profile_id, "c": cooldown_from})}
    no_imp_rounds = {r["object_id"]: r["n"] for r in fetch_all("""
        SELECT object_id, COUNT(*) n FROM audit_proposal WHERE profile_id = :p AND status = 'exported' AND rule = 'no_imp'
        AND action = 'bid' GROUP BY object_id""", {"p": profile_id})}

    floor, ceil_mult = float(P["bid_floor"]), float(P["bid_ceiling_cpc_mult"])
    out: list[dict] = []

    def base(r: dict, rule: str, action: str, **kw) -> dict:
        c = ctx.campaigns.get(r["campaign_id"]) or {}
        a = ctx.adgroups.get(r["ad_group_id"]) or {}
        d = {"rule": rule, "action": action, "campaign_id": r["campaign_id"], "ad_group_id": r["ad_group_id"],
             "campaign_name": c.get("campaign_name") or r.get("campaign_name"),
             "ad_group_name": a.get("ad_group_name") or r.get("ad_group_name"),
             "default_on": 1, "exportable": 1}
        d.update(kw)
        return d

    # ---- quy tắc 3–6: keyword và product target đang bật
    for r in ctx.keywords + ctx.targets:
        if not ctx.active(r) or r["object_id"] in recent:
            continue
        is_target = r["entity"] == "Product targeting"
        label = r["expression"] if is_target else r["keyword_text"]
        mt = "TARGETING" if is_target else r["match_type"]
        bid = r["bid"] or (ctx.adgroups.get(r["ad_group_id"]) or {}).get("default_bid")
        if not bid:
            continue
        m = _metrics(tm.get(r["object_id"]))
        tgt = target_acos(r["ad_group_id"], r["campaign_id"])
        cpa = tgt * aov(r["ad_group_id"], r["campaign_id"])
        common = dict(object_id=r["object_id"], text=label, match_type=mt, current_bid=bid, acos_target=tgt, **m)
        new, rule, reason, action = None, None, None, "bid"
        if m["clicks"] >= P["min_clicks"]:
            cpc = m["spend"] / m["clicks"] if m["clicks"] else None
            if m["orders"] == 0:
                if P["pause_enabled"] and cpa > 0 and m["spend"] >= P["pause_cpa_mult"] * cpa:
                    rule, action = "pause", "pause"
                    reason = f"{m['clicks']} click, chi {m['spend']:.2f} mà 0 đơn (≥ {P['pause_cpa_mult']:g}× CPA mục tiêu {cpa:.2f})"
                elif P["bid_down_enabled"]:
                    rule, new = "bid_down", bid * (1 - P["bid_max_down"])
                    reason = f"{m['clicks']} click, 0 đơn → giảm tối đa {_pct(P['bid_max_down'])}"
            else:
                acos = m["spend"] / m["sales"] if m["sales"] else float("inf")
                if acos > tgt and P["bid_down_enabled"]:
                    rule, new = "bid_down", max(bid * tgt / acos, bid * (1 - P["bid_max_down"]))
                    reason = f"ACoS {_pct(acos)} > mục tiêu {_pct(tgt)}"
                elif acos < P["bid_up_acos_ratio"] * tgt and P["bid_up_enabled"]:
                    new = min(bid * tgt / acos if acos > 0 else bid * (1 + P["bid_max_up"]), bid * (1 + P["bid_max_up"]))
                    if cpc:
                        new = min(new, ceil_mult * cpc)
                    rule, reason = "bid_up", f"ACoS {_pct(acos)} < {P['bid_up_acos_ratio']:g}× mục tiêu {_pct(tgt)}"
        elif P["no_imp_enabled"] and r["object_id"] not in has_imp and r["ad_group_id"] in ag_has_imp and bid >= floor:
            # bid dưới sàn thường là keyword được "để dành" có chủ ý → không tự tăng
            rounds = no_imp_rounds.get(r["object_id"], 0)
            if rounds >= P["no_imp_max_rounds"]:
                rule, action = "no_imp", "pause"
                reason = f"Không có impression {int(P['no_imp_days'])} ngày dù đã tăng bid {rounds} lần"
            else:
                cpc = avg_cpc(ag_stats.get(r["ad_group_id"]), camp_stats.get(r["campaign_id"]), acct)
                new = bid * (1 + P["no_imp_raise"])
                if cpc:
                    new = min(new, ceil_mult * cpc)
                rule = "no_imp"
                reason = f"Không có impression {int(P['no_imp_days'])} ngày → tăng {_pct(P['no_imp_raise'])} (lần {rounds + 1})"
        if not rule:
            continue
        if action == "pause":
            out.append(base(r, rule, "pause", default_on=0, reason=reason, **common))
            continue
        new = round(max(new, floor), 2)
        if abs(new - bid) < 0.01 or (rule in ("bid_up", "no_imp") and new <= bid) or (rule == "bid_down" and new >= bid):
            continue
        out.append(base(r, rule, "bid", new_bid=new, reason=reason, **common))

    # ---- quy tắc 1, 2: search term
    terms = fetch_all("""
        SELECT f.campaign_id, f.adgroup_id AS ad_group_id, t.term, MAX(f.match_type) AS match_type,
               SUBSTRING(GROUP_CONCAT(DISTINCT f.targeting ORDER BY f.targeting SEPARATOR ' | '), 1, 500) AS source,
               SUM(f.impressions) impressions, SUM(f.clicks) clicks, SUM(f.cost) cost, SUM(f.orders) orders, SUM(f.sales) sales
        FROM fact_search_term_daily f JOIN dim_term t ON t.term_id = f.term_id
        WHERE f.profile_id = :p AND f.ad_type = 'SP' AND f.report_date BETWEEN :d0 AND :d1 AND f.match_type <> 'EXACT'
        GROUP BY f.campaign_id, f.adgroup_id, t.term""", q)
    harvest_best: dict[str, dict] = {}
    for s in terms:
        term = (s["term"] or "").strip().lower()
        ag, camp = s["ad_group_id"], s["campaign_id"]
        if not term or ag not in ctx.adgroups or not ctx.active({**ctx.adgroups[ag], "state": "enabled"}):
            continue
        m = _metrics(s)
        tgt = target_acos(ag, camp)
        if m["orders"] >= P["harvest_min_orders"] and P["harvest_enabled"]:
            acos = m["spend"] / m["sales"] if m["sales"] else float("inf")
            if acos <= P["harvest_acos_ratio"] * tgt:
                is_asin = bool(ASIN_RE.match(term))
                if (term in ctx.asin_targets) if is_asin else (term in ctx.exact_texts):
                    continue
                prev = harvest_best.get(term)
                if not prev or m["orders"] > prev["m"]["orders"]:
                    harvest_best[term] = {"s": s, "m": m, "tgt": tgt, "acos": acos, "asin": is_asin,
                                          "sources": (prev["sources"] if prev else []) + [s]}
                else:
                    prev["sources"].append(s)
        elif m["orders"] == 0 and P["negative_enabled"]:
            cpa = tgt * aov(ag, camp)
            if cpa > 0 and m["spend"] >= P["negative_cpa_mult"] * cpa and not ctx.negated(ag, camp, term) \
                    and (ag, term) not in recent_terms:
                is_asin = bool(ASIN_RE.match(term))
                out.append(base(s, "negative", "negative_target" if is_asin else "negative", text=term, source=s["source"],
                                match_type=s["match_type"], acos_target=tgt, **m,
                                reason=f"Chi {m['spend']:.2f}, {m['clicks']} click, 0 đơn (≥ {P['negative_cpa_mult']:g}× CPA mục tiêu {cpa:.2f})"))

    for term, h in harvest_best.items():
        s, m = h["s"], h["m"]
        dest = ctx.destination(s["ad_group_id"], h["asin"])
        # đã xuất trong thời gian chờ: file bulk tải trước khi upload thay đổi chưa có keyword mới → không tạo trùng
        if (dest, term) in recent_terms:
            continue
        cpc = m["spend"] / m["clicks"] if m["clicks"] else floor
        reason = f"{m['orders']} đơn, ACoS {_pct(h['acos'])} ≤ mục tiêu {_pct(h['tgt'])} (nguồn: {s['match_type'].lower()})"
        if dest:
            a = ctx.adgroups[dest]
            out.append(base({"campaign_id": a["campaign_id"], "ad_group_id": dest}, "harvest",
                            "add_target" if h["asin"] else "add_keyword", text=term, source=s["source"], match_type="exact",
                            new_bid=round(max(cpc, floor), 2), acos_target=h["tgt"], **m, reason=reason))
        else:
            out.append(base(s, "harvest", "add_target" if h["asin"] else "add_keyword", text=term, source=s["source"], match_type="exact",
                            new_bid=round(max(cpc, floor), 2), acos_target=h["tgt"], **m, default_on=0, exportable=0,
                            reason=reason + " · chưa có ad group Exact cùng SKU để thêm, cần tạo thủ công"))
            continue
        if P["harvest_add_negative"]:
            for src in h["sources"]:
                if src["ad_group_id"] == dest or ctx.negated(src["ad_group_id"], src["campaign_id"], term) \
                        or (src["ad_group_id"], term) in recent_terms:
                    continue
                out.append(base(src, "harvest", "negative_target" if h["asin"] else "negative", text=term, source=src["source"],
                                match_type=src["match_type"], acos_target=h["tgt"], **_metrics(src),
                                reason="Chặn ở ad group nguồn sau khi thêm Exact, để không tự cạnh tranh"))

    # ---- quy tắc 7: negative đang chặn search term từng ra đơn trong cùng campaign
    if P["conflict_enabled"]:
        c0 = d1 - timedelta(days=int(P["conflict_days"]) - 1)
        winners = defaultdict(list)
        for r in fetch_all("""
            SELECT f.campaign_id, t.term, SUM(f.orders) orders, SUM(f.sales) sales, SUM(f.cost) cost, SUM(f.clicks) clicks
            FROM fact_search_term_daily f JOIN dim_term t ON t.term_id = f.term_id
            WHERE f.profile_id = :p AND f.ad_type = 'SP' AND f.report_date BETWEEN :c0 AND :d1
            GROUP BY f.campaign_id, t.term HAVING SUM(f.orders) > 0""", {**q, "c0": c0}):
            winners[r["campaign_id"]].append(r)
        for n in ctx.negatives:
            text_ = (n["keyword_text"] or "").lower()
            phrase = "phrase" in (n["match_type"] or "").lower()
            hits = [w for w in winners.get(n["campaign_id"], [])
                    if (f" {text_} " in f" {w['term'].lower()} " if phrase else w["term"].lower() == text_)]
            if not hits:
                continue
            orders = sum(int(w["orders"]) for w in hits)
            sample = ", ".join(w["term"] for w in hits[:3])
            out.append(base(n, "conflict", "warn", object_id=n["object_id"], text=n["keyword_text"],
                            source=", ".join(w["term"] for w in hits[:5])[:500],
                            match_type=n["match_type"], orders=orders, sales=sum(float(w["sales"]) for w in hits),
                            spend=sum(float(w["cost"]) for w in hits), clicks=sum(int(w["clicks"]) for w in hits),
                            default_on=0, exportable=0,
                            reason=f"{n['entity']} chặn search term đã ra {orders} đơn trong {int(P['conflict_days'])} ngày: {sample}"))
    return out, d0, d1
