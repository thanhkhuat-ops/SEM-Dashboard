"""Chuẩn hóa search term / keyword: tách từ, đưa về số ít, sinh n-gram."""
import re

ASIN_RE = re.compile(r"^b0[a-z0-9]{8}$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_AUTO_TARGETS = {"close-match", "loose-match", "substitutes", "complements"}

DEFAULT_STOPWORDS = (
    "a", "an", "and", "the", "for", "with", "of", "in", "on", "to", "by", "at", "from", "or", "w", "my", "your",
)

# Từ kết thúc bằng 's' nhưng không phải số nhiều
_NOT_PLURAL = {"glass", "dress", "mattress", "chess", "bus", "gas", "yes", "this", "plus", "cactus", "canvas", "series",
               "species", "lens", "bias", "pants", "shorts", "jeans", "scissors", "tongs", "pliers", "goggles", "leggings"}


def tokenize(text: str) -> list[str]:
    """Viết thường, bỏ dấu nháy ('men's' -> 'mens'), tách theo ký tự chữ/số."""
    cleaned = text.lower().replace("'", "").replace("’", "")
    return _TOKEN_RE.findall(cleaned)


def singularize(token: str) -> str:
    if len(token) <= 3 or token in _NOT_PLURAL or token.isdigit() or not token.endswith("s"):
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("sses", "shes", "ches", "xes", "zes")):
        return token[:-2]
    if token.endswith(("ss", "us", "is")):
        return token
    return token[:-1]


def is_asin(text: str) -> bool:
    return bool(ASIN_RE.match(text.strip().lower()))


def target_expression_kind(text: str) -> str | None:
    """Nhận diện biểu thức target (không phải từ khóa người mua gõ)."""
    t = text.strip().lower()
    if t in _AUTO_TARGETS:
        return "AUTO"
    if t.startswith(("asin=", "asin-expanded=", 'asin="', "asinsameas", "asin-same-as")):
        return "PRODUCT_TARGET"
    if t.startswith(("category=", "category-same-as", "asincategorysameas")):
        return "CATEGORY_TARGET"
    if "=" in t or t.startswith(("views", "purchases", "audience", "similar-product", "exact-product", "related")):
        return "AUDIENCE"
    return None


def ngrams(tokens: list[str], max_n: int = 3) -> list[tuple[int, str]]:
    out: set[tuple[int, str]] = set()
    for n in range(1, max_n + 1):
        for i in range(len(tokens) - n + 1):
            out.add((n, " ".join(tokens[i:i + n])[:150]))
    return sorted(out)


def contains_phrase(tokens: list[str], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    if n == 0 or n > len(tokens):
        return False
    return any(tuple(tokens[i:i + n]) == phrase for i in range(len(tokens) - n + 1))
