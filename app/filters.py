"""Bộ lọc dùng chung cho mọi báo cáo và trình dựng mệnh đề WHERE có tham số."""
from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import Query

AD_TYPES = ("SP", "SB", "SD")


@dataclass
class Filters:
    start: date
    end: date
    profile_ids: list[str] = field(default_factory=list)
    ad_types: list[str] = field(default_factory=list)
    portfolio_ids: list[str] = field(default_factory=list)
    group_ids: list[int] = field(default_factory=list)
    brand_ids: list[int] = field(default_factory=list)
    campaign_q: str | None = None
    match_types: list[str] = field(default_factory=list)
    term_classes: list[str] = field(default_factory=list)
    length_buckets: list[str] = field(default_factory=list)
    wf_accounts: list[str] = field(default_factory=list)  # Wayfair: "account_id-country", vd "293856-US"
    countries: list[str] = field(default_factory=list)  # Tổng hợp / Shopify: US, CA, AU (tham số "market"; "country" là control của tab Tồn kho)
    sales_channels: list[str] = field(default_factory=list)  # Tổng hợp: amazon, wayfair, shopify, other (tham số "sales_channel")
    pic_ids: list[int] = field(default_factory=list)  # PIC đã chọn (tham số "pic"); đã đổi thành group_ids ở get_filters

    def previous_period(self) -> "Filters":
        days = (self.end - self.start).days + 1
        prev = Filters(**self.__dict__)
        prev.end = self.start - timedelta(days=1)
        prev.start = prev.end - timedelta(days=days - 1)
        return prev

    def describe(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in self.__dict__.items() if v}


def get_filters(
    start: date | None = Query(None),
    end: date | None = Query(None),
    profile_id: list[str] = Query([]),
    ad_type: list[str] = Query([]),
    portfolio_id: list[str] = Query([]),
    group_id: list[int] = Query([]),
    brand_id: list[int] = Query([]),
    campaign_q: str | None = Query(None),
    match_type: list[str] = Query([]),
    term_class: list[str] = Query([]),
    length_bucket: list[str] = Query([]),
    wf_account: list[str] = Query([]),
    market: list[str] = Query([]),
    sales_channel: list[str] = Query([]),
    pic: list[int] = Query([]),
) -> Filters:
    end = end or date.today() - timedelta(days=1)
    start = start or end - timedelta(days=29)
    if start > end:
        start, end = end, start
    if pic:  # PIC = các nhóm SP người đó phụ trách, giao với bộ lọc Nhóm SP nếu có
        from app.pic import groups_for
        groups = groups_for(pic)
        if group_id:
            groups = [g for g in groups if g in set(group_id)] or [-1]
        group_id = groups
    return Filters(
        start=start, end=end, profile_ids=profile_id,
        ad_types=[a.upper() for a in ad_type if a.upper() in AD_TYPES],
        portfolio_ids=portfolio_id, group_ids=group_id, brand_ids=brand_id,
        campaign_q=(campaign_q or "").strip() or None,
        match_types=[m.upper() for m in match_type], term_classes=[t.upper() for t in term_class],
        length_buckets=length_bucket, wf_accounts=wf_account, countries=[c.upper() for c in market],
        sales_channels=[c.lower() for c in sales_channel if c.lower() in ("amazon", "wayfair", "shopify", "other")],
        pic_ids=pic,
    )


class Where:
    def __init__(self) -> None:
        self.clauses: list[str] = []
        self.params: dict = {}
        self._n = 0

    def add(self, clause: str, **params) -> "Where":
        self.clauses.append(clause)
        self.params.update(params)
        return self

    def add_in(self, column: str, values: list) -> "Where":
        if not values:
            return self
        names = []
        for v in values:
            self._n += 1
            name = f"p{self._n}"
            self.params[name] = v
            names.append(f":{name}")
        self.clauses.append(f"{column} IN ({', '.join(names)})")
        return self

    def sql(self) -> str:
        return ("WHERE " + " AND ".join(self.clauses)) if self.clauses else ""


def campaign_where(f: Filters, alias: str = "f", campaign_alias: str = "c", date_col: str = "report_date") -> Where:
    """Lọc cho các bảng fact có report_date, ad_type, campaign_id, profile_id. Cần JOIN dim_campaign {campaign_alias}."""
    w = Where()
    w.add(f"{alias}.{date_col} BETWEEN :start AND :end", start=f.start, end=f.end)
    w.add_in(f"{alias}.profile_id", f.profile_ids)
    w.add_in(f"{alias}.ad_type", f.ad_types)
    w.add_in(f"{campaign_alias}.portfolio_id", f.portfolio_ids)
    if f.campaign_q:
        w.add(f"{campaign_alias}.campaign_name LIKE :campaign_q", campaign_q=f"%{f.campaign_q}%")
    if f.group_ids or f.brand_ids:
        sub = Where()
        sub._n = 1000
        sub.add_in("m.group_id", f.group_ids).add_in("m.brand_id", f.brand_ids)
        w.add(f"EXISTS (SELECT 1 FROM map_adgroup_product m WHERE m.campaign_id = {alias}.campaign_id "
              f"AND m.ad_type = {alias}.ad_type AND {' AND '.join(sub.clauses)})", **sub.params)
    return w


def wf_where(f: Filters, alias: str = "f", campaign_alias: str = "c", group_by_listing: str | None = None) -> Where:
    """Lọc cho các bảng fact Wayfair (report_date, campaign_id, account_id, country_code). Cần JOIN dim_wf_campaign
    {campaign_alias}. group_by_listing: alias của dim_wf_listing để lọc Nhóm SP/Brand theo listing thay vì campaign."""
    w = Where()
    w._n = 2000
    w.add(f"{alias}.report_date BETWEEN :start AND :end", start=f.start, end=f.end)
    w.add_in(f"CONCAT({alias}.account_id, '-', {alias}.country_code)", f.wf_accounts)
    if f.campaign_q:
        w.add(f"{campaign_alias}.campaign_name LIKE :campaign_q", campaign_q=f"%{f.campaign_q}%")
    if group_by_listing:
        w.add_in(f"{group_by_listing}.group_id", f.group_ids).add_in(f"{group_by_listing}.brand_id", f.brand_ids)
    elif f.group_ids or f.brand_ids:
        sub = Where()
        sub._n = 3000
        sub.add_in("m.group_id", f.group_ids).add_in("m.brand_id", f.brand_ids)
        w.add(f"EXISTS (SELECT 1 FROM map_wf_campaign_group m WHERE m.campaign_id = {alias}.campaign_id "
              f"AND {' AND '.join(sub.clauses)})", **sub.params)
    return w
