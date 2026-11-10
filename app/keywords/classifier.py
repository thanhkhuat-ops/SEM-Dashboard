"""Phân loại từ khóa: Branded / Competitor / Chung (Generic) / Mục tiêu (Targeted) / ASIN / biểu thức target.

Thứ tự ưu tiên:
 1. Biểu thức target (auto, asin=, category=, audience)  -> AUTO / PRODUCT_TARGET / CATEGORY_TARGET / AUDIENCE
 2. Search term là ASIN                                    -> ASIN_OWN / ASIN_COMPETITOR
 3. Ghi đè thủ công (dict_term_override)                   -> lớp được chỉ định
 4. Chứa brand của mình / đối thủ (dict_brand)              -> BRANDED / COMPETITOR
 5. Chứa thuộc tính (dict_attribute) hoặc con số/kích thước -> TARGETED
 6. Chỉ gồm từ loại sản phẩm (dict_product_term)            -> GENERIC
 7. Còn lại theo số từ (bỏ stop-word): <= generic_max_words -> GENERIC, ngược lại TARGETED
"""
from dataclasses import dataclass, field

from app.keywords.normalize import (
    DEFAULT_STOPWORDS, contains_phrase, is_asin, ngrams, singularize, target_expression_kind, tokenize,
)

CLASS_LABELS = {
    "GENERIC": "Chung",
    "TARGETED": "Mục tiêu",
    "BRANDED": "Brand mình",
    "COMPETITOR": "Brand đối thủ",
    "ASIN_OWN": "ASIN của mình",
    "ASIN_COMPETITOR": "ASIN đối thủ",
    "AUTO": "Auto target",
    "PRODUCT_TARGET": "Product target",
    "CATEGORY_TARGET": "Category target",
    "AUDIENCE": "Audience (SD)",
}
OVERRIDABLE_CLASSES = ("GENERIC", "TARGETED", "BRANDED", "COMPETITOR")


@dataclass
class Dictionaries:
    own_brands: list[str] = field(default_factory=list)
    competitor_brands: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    product_terms: list[str] = field(default_factory=list)
    stopwords: list[str] = field(default_factory=lambda: list(DEFAULT_STOPWORDS))
    overrides: dict[str, str] = field(default_factory=dict)
    own_asins: set[str] = field(default_factory=set)


@dataclass
class TermInfo:
    term: str
    normalized: str
    word_count: int
    length_bucket: str
    term_class: str
    brand_hit: str | None = None
    attribute_hits: str | None = None
    product_term_hit: str | None = None
    ngrams: list[tuple[int, str]] = field(default_factory=list)


def length_bucket(word_count: int) -> str:
    return str(word_count) if word_count < 5 else "5+"


def _phrases(terms: list[str], singular: bool) -> list[tuple[tuple[str, ...], str]]:
    out = []
    for t in terms:
        toks = tokenize(t)
        if singular:
            toks = [singularize(x) for x in toks]
        if toks:
            out.append((tuple(toks), t))
    # ưu tiên cụm dài trước để báo đúng cụm khớp
    return sorted(out, key=lambda p: -len(p[0]))


class TermClassifier:
    def __init__(self, dicts: Dictionaries, generic_max_words: int = 2):
        self.generic_max_words = generic_max_words
        self.stopwords = {s.lower() for s in dicts.stopwords}
        self.own = _phrases(dicts.own_brands, singular=False)
        self.competitor = _phrases(dicts.competitor_brands, singular=False)
        self.attributes = _phrases(dicts.attributes, singular=True)
        self.product_terms = _phrases(dicts.product_terms, singular=True)
        self.overrides = {" ".join(tokenize(k)): v for k, v in dicts.overrides.items()}
        self.own_asins = {a.lower() for a in dicts.own_asins}

    def classify(self, term: str) -> TermInfo:
        raw = (term or "").strip()
        tokens = tokenize(raw)
        normalized = " ".join(tokens)
        wc = len(tokens)
        info = TermInfo(term=raw, normalized=normalized, word_count=wc, length_bucket=length_bucket(wc), term_class="")

        kind = target_expression_kind(raw)
        if kind:
            info.term_class = kind
            info.word_count, info.length_bucket = 0, "-"
            return info
        if is_asin(raw):
            info.term_class = "ASIN_OWN" if raw.lower() in self.own_asins else "ASIN_COMPETITOR"
            info.word_count, info.length_bucket = 1, "ASIN"
            return info

        core = [singularize(t) for t in tokens if t not in self.stopwords]
        info.ngrams = ngrams(core)

        attr_hits = [label for phrase, label in self.attributes if contains_phrase(core, phrase)]
        if any(any(ch.isdigit() for ch in t) for t in core):
            attr_hits.append("#số/kích thước")
        info.attribute_hits = ", ".join(attr_hits)[:255] or None
        product_hits = [(phrase, label) for phrase, label in self.product_terms if contains_phrase(core, phrase)]
        info.product_term_hit = ", ".join(label for _, label in product_hits)[:150] or None

        own = next((label for phrase, label in self.own if contains_phrase(tokens, phrase)), None)
        comp = next((label for phrase, label in self.competitor if contains_phrase(tokens, phrase)), None)
        info.brand_hit = own or comp

        override = self.overrides.get(normalized)
        if override:
            info.term_class = override
        elif own:
            info.term_class = "BRANDED"
        elif comp:
            info.term_class = "COMPETITOR"
        elif attr_hits:
            info.term_class = "TARGETED"
        elif product_hits and self._only_product_terms(core, [p for p, _ in product_hits]):
            info.term_class = "GENERIC"
        elif len(core) <= self.generic_max_words:
            info.term_class = "GENERIC"
        else:
            info.term_class = "TARGETED"
        return info

    @staticmethod
    def _only_product_terms(core: list[str], phrases: list[tuple[str, ...]]) -> bool:
        covered = [False] * len(core)
        for phrase in phrases:
            n = len(phrase)
            for i in range(len(core) - n + 1):
                if tuple(core[i:i + n]) == phrase:
                    for j in range(i, i + n):
                        covered[j] = True
        return bool(core) and all(covered)
