"""Đồng bộ dim_term + bridge_term_ngram: chuẩn hóa, phân loại và tách n-gram cho search term / keyword."""
import hashlib
from datetime import date, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.keywords.classifier import Dictionaries, TermClassifier

BATCH = 2000


def _term_id(term: str) -> str:
    """Giống LEFT(MD5(LOWER(TRIM(term))), 12) trong SQL ETL."""
    return hashlib.md5(term.strip(" ").lower().encode("utf-8")).hexdigest()[:12]


def load_dictionaries(conn: Connection, mart: str) -> Dictionaries:
    def col(sql: str) -> list[str]:
        return [r[0] for r in conn.execute(text(sql))]

    stopwords = col(f"SELECT term FROM {mart}.dict_stopword")
    return Dictionaries(
        own_brands=col(f"SELECT term FROM {mart}.dict_brand WHERE brand_type = 'OWN'"),
        competitor_brands=col(f"SELECT term FROM {mart}.dict_brand WHERE brand_type = 'COMPETITOR'"),
        attributes=col(f"SELECT term FROM {mart}.dict_attribute"),
        product_terms=col(f"SELECT term FROM {mart}.dict_product_term"),
        stopwords=stopwords or Dictionaries().stopwords,
        overrides={r[0]: r[1] for r in conn.execute(text(f"SELECT term, term_class FROM {mart}.dict_term_override"))},
        own_asins={r[0].lower() for r in conn.execute(text(f"SELECT asin FROM {mart}.map_asin_product"))},
    )


def _collect(conn: Connection, mart: str, stg: str, start: date | None, end: date | None,
             reclassify_all: bool) -> dict[str, tuple[str, int, int]]:
    """term_id -> (term, is_search_term, is_keyword) cần (re)classify."""
    existing = {r[0] for r in conn.execute(text(f"SELECT term_id FROM {mart}.dim_term"))}
    todo: dict[str, tuple[str, int, int]] = {}

    def add(term_id: str, term: str, is_st: int, is_kw: int) -> None:
        if not term_id or term is None:
            return
        if term_id in existing and not reclassify_all:
            return
        old = todo.get(term_id)
        todo[term_id] = (term, max(is_st, old[1] if old else 0), max(is_kw, old[2] if old else 0))

    for table in ("sem__sp_customer_search_term", "sem__sb_customer_search_term"):
        for tid, term in conn.execute(text(f"SELECT customer_search_term_id, customer_search_term FROM {stg}.{table}")):
            add(tid, term, 1, 0)

    date_filter = "WHERE report_date BETWEEN :start AND :end" if (start and end and not reclassify_all) else ""
    params = {"start": start, "end": end} if date_filter else {}
    for tid, term in conn.execute(
            text(f"SELECT term_id, MAX(targeting) FROM {mart}.fact_target_daily {date_filter} GROUP BY term_id"), params):
        add(tid, term, 0, 1)

    # Wayfair: term_id = 12 ký tự đầu MD5 của chữ thường (cùng quy tắc Amazon) nên dùng chung dim_term và từ điển
    for tid, term in conn.execute(
            text(f"SELECT term_id, MAX(keyword) FROM {mart}.fact_wf_keyword_daily {date_filter} GROUP BY term_id"), params):
        add(tid, term, 0, 1)
    # search term Wayfair chỉ có trong bản sao report (~20 triệu dòng); khi phân loại lại toàn bộ thì đã nằm trong dim_term
    if date_filter:
        for term, in conn.execute(text(f"""
                SELECT DISTINCT customer_search_term FROM {stg}.sem_wayfair__wsp_keyword_optimization
                WHERE campaign_date_run BETWEEN :start AND :end AND TRIM(COALESCE(customer_search_term, '')) <> ''"""),
                params):
            add(_term_id(term), term, 1, 0)

    if reclassify_all:
        for tid, term, is_st, is_kw in conn.execute(
                text(f"SELECT term_id, term, is_search_term, is_keyword FROM {mart}.dim_term")):
            add(tid, term, is_st, is_kw)
    return todo


def sync_terms(conn: Connection, mart: str, stg: str, generic_max_words: int,
               start: date | None = None, end: date | None = None, reclassify_all: bool = False) -> int:
    classifier = TermClassifier(load_dictionaries(conn, mart), generic_max_words)
    todo = _collect(conn, mart, stg, start, end, reclassify_all)
    now = datetime.utcnow().replace(microsecond=0)
    items = list(todo.items())

    upsert = text(f"""
        INSERT INTO {mart}.dim_term
          (term_id, term, normalized, word_count, length_bucket, term_class, brand_hit, attribute_hits,
           product_term_hit, is_search_term, is_keyword, classified_at)
        VALUES (:term_id, :term, :normalized, :word_count, :length_bucket, :term_class, :brand_hit, :attribute_hits,
                :product_term_hit, :is_search_term, :is_keyword, :classified_at)
        ON DUPLICATE KEY UPDATE
          term = VALUES(term), normalized = VALUES(normalized), word_count = VALUES(word_count),
          length_bucket = VALUES(length_bucket), term_class = VALUES(term_class), brand_hit = VALUES(brand_hit),
          attribute_hits = VALUES(attribute_hits), product_term_hit = VALUES(product_term_hit),
          is_search_term = GREATEST(is_search_term, VALUES(is_search_term)),
          is_keyword = GREATEST(is_keyword, VALUES(is_keyword)), classified_at = VALUES(classified_at)""")
    delete_ngrams = text(f"DELETE FROM {mart}.bridge_term_ngram WHERE term_id IN :ids").bindparams(
        bindparam("ids", expanding=True))
    insert_ngram = text(f"INSERT IGNORE INTO {mart}.bridge_term_ngram (term_id, n, ngram) VALUES (:term_id, :n, :ngram)")

    for i in range(0, len(items), BATCH):
        batch = items[i:i + BATCH]
        term_rows, ngram_rows = [], []
        for term_id, (term, is_st, is_kw) in batch:
            info = classifier.classify(term)
            term_rows.append({
                "term_id": term_id, "term": info.term[:255], "normalized": info.normalized[:255],
                # cột TINYINT; vài search term Wayfair là cả đoạn văn dài hàng trăm từ
                "word_count": min(info.word_count, 127), "length_bucket": info.length_bucket, "term_class": info.term_class,
                "brand_hit": info.brand_hit, "attribute_hits": info.attribute_hits,
                "product_term_hit": info.product_term_hit, "is_search_term": is_st, "is_keyword": is_kw,
                "classified_at": now,
            })
            ngram_rows.extend({"term_id": term_id, "n": n, "ngram": g} for n, g in info.ngrams)
        conn.execute(upsert, term_rows)
        ids = [r["term_id"] for r in term_rows]
        conn.execute(delete_ngrams, {"ids": ids})
        if ngram_rows:
            conn.execute(insert_ngram, ngram_rows)
    return len(items)
