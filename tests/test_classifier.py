from app.keywords.classifier import Dictionaries, TermClassifier
from app.keywords.normalize import ngrams, singularize, target_expression_kind, tokenize


def make(**kw) -> TermClassifier:
    d = Dictionaries(
        own_brands=["tranquillo", "yes4all"],
        competitor_brands=["vivere", "sorbus"],
        attributes=["cotton", "outdoor", "for bedroom", "kids"],
        product_terms=["hammock", "swing", "chair", "hammock chair"],
        own_asins={"b0abc12345"},
    )
    for k, v in kw.items():
        setattr(d, k, v)
    return TermClassifier(d, generic_max_words=2)


def test_tokenize_and_singular():
    assert tokenize("Men's Hammock-Chair, 2 PACK") == ["mens", "hammock", "chair", "2", "pack"]
    assert singularize("hammocks") == "hammock"
    assert singularize("batteries") == "battery"
    assert singularize("boxes") == "box"
    assert singularize("glass") == "glass"
    assert singularize("mattress") == "mattress"


def test_ngrams_distinct():
    assert ngrams(["hammock", "swing", "chair"]) == [
        (1, "chair"), (1, "hammock"), (1, "swing"),
        (2, "hammock swing"), (2, "swing chair"), (3, "hammock swing chair")]


def test_target_expressions():
    assert target_expression_kind("close-match") == "AUTO"
    assert target_expression_kind('asin="B0D3FL8L9G"') == "PRODUCT_TARGET"
    assert target_expression_kind('category="123"') == "CATEGORY_TARGET"
    assert target_expression_kind("views=(exact-product lookback=30)") == "AUDIENCE"
    assert target_expression_kind("hammock chair") is None


def test_classes():
    c = make()
    assert c.classify("hammock").term_class == "GENERIC"
    assert c.classify("hammock swing chair").term_class == "GENERIC"  # chỉ gồm từ loại sản phẩm
    assert c.classify("hammock chair for bedroom").term_class == "TARGETED"
    assert c.classify("cotton hammock").term_class == "TARGETED"
    assert c.classify("hammock 2 person").term_class == "TARGETED"  # có số
    assert c.classify("tranquillo hammock").term_class == "BRANDED"
    assert c.classify("vivere hammock stand").term_class == "COMPETITOR"
    assert c.classify("b0abc12345").term_class == "ASIN_OWN"
    assert c.classify("b0zzz99999").term_class == "ASIN_COMPETITOR"
    assert c.classify("loose-match").term_class == "AUTO"
    # không có trong từ điển: theo số từ
    assert c.classify("patio set").term_class == "GENERIC"
    assert c.classify("large patio set cover").term_class == "TARGETED"


def test_stopwords_not_counted_and_buckets():
    c = make()
    info = c.classify("swing for the porch")
    assert info.word_count == 4 and info.length_bucket == "4"
    assert info.term_class == "GENERIC"  # bỏ stop-word còn 2 từ
    assert c.classify("a b c d e f").length_bucket == "5+"


def test_override_wins():
    c = make(overrides={"patio set": "TARGETED"})
    assert c.classify("Patio  Set").term_class == "TARGETED"


def test_plural_matches_dictionary():
    c = make()
    info = c.classify("hammocks for kids")
    assert info.term_class == "TARGETED"
    assert "kids" in info.attribute_hits
