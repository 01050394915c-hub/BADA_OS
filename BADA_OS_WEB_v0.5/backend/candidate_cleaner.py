import re

from .ai_engine import AIEngine


_PRICE_ONLY_RE = re.compile(
    r"^(?:krw|usd|jpy|cny|eur|\$|₩|¥|€)?\s*\d[\d,]*(?:\.\d+)?\s*(?:원|달러|yen|usd|krw)?$",
    re.IGNORECASE,
)
_OFFERS_ONLY_RE = re.compile(r"^\d+\s*offers?$", re.IGNORECASE)

_CLEANER_STATS = {
    "seen": 0,
    "kept": 0,
    "dropped": {
        "empty": 0,
        "price_or_offer_only": 0,
        "too_short_or_invalid": 0,
    },
}

_AI_ENGINE = AIEngine()


def _log_zero_kept_if_needed() -> None:
    # If a batch keeps no candidates, emit reason-count diagnostics.
    if _CLEANER_STATS["seen"] >= 5 and _CLEANER_STATS["kept"] == 0 and _CLEANER_STATS["seen"] % 5 == 0:
        dropped = _CLEANER_STATS["dropped"]
        print(
            "[candidate_cleaner] 후보 0개 가능성 - 탈락 사유 카운트: "
            f"empty={dropped['empty']}, "
            f"price_or_offer_only={dropped['price_or_offer_only']}, "
            f"too_short_or_invalid={dropped['too_short_or_invalid']}"
        )


def _record_drop(reason: str) -> None:
    _CLEANER_STATS["seen"] += 1
    _CLEANER_STATS["dropped"][reason] = _CLEANER_STATS["dropped"].get(reason, 0) + 1
    _log_zero_kept_if_needed()


def _record_keep() -> None:
    _CLEANER_STATS["seen"] += 1
    _CLEANER_STATS["kept"] += 1


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_unwanted_phrases(text: str) -> str:
    text = re.sub(r"\bamazon\s+best\s+sellers?\s+in\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bamazon\s+best\s+sellers?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*offers?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\boffers?\s+from\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"^in\s+", "", text, flags=re.IGNORECASE)
    return _normalize_space(text)


def _remove_unnecessary_numbers(text: str) -> str:
    # Remove standalone long numbers, ranks, and most year-like tokens.
    text = re.sub(r"\b#?\d{2,}\b", " ", text)
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _trim_to_length(text: str, min_len: int = 2, max_len: int = 40) -> str:
    text = _normalize_space(text)
    if len(text) > max_len:
        cut = text[:max_len]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut.strip(" ,-/")
    if len(text) < min_len:
        return ""
    return text


def clean_candidate_name(raw_text: str) -> str:
    text = _normalize_space(raw_text)
    if not text:
        _record_drop("empty")
        return ""

    lowered = text.lower()
    if _PRICE_ONLY_RE.match(lowered) or _OFFERS_ONLY_RE.match(lowered):
        _record_drop("price_or_offer_only")
        return ""

    text = _strip_unwanted_phrases(text)
    text = _remove_unnecessary_numbers(text)
    text = re.sub(r"[^0-9A-Za-z가-힣\s\-_/,&()]", " ", text)
    text = _normalize_space(text)

    lowered = text.lower()
    if _PRICE_ONLY_RE.match(lowered) or _OFFERS_ONLY_RE.match(lowered):
        _record_drop("price_or_offer_only")
        return ""

    # Allow short but valid commerce keywords (e.g. 랜턴, 장마, 여행) to pass.
    text = _trim_to_length(text, min_len=2, max_len=40)
    if not text:
        _record_drop("too_short_or_invalid")
        return ""

    ai_result = _AI_ENGINE.generate_product_keywords(text)
    ai_keywords = ai_result.get("keywords") if isinstance(ai_result, dict) else None
    if isinstance(ai_keywords, list) and ai_keywords:
        preferred = _normalize_space(ai_keywords[0])
        if preferred:
            text = preferred
            text = _trim_to_length(text, min_len=2, max_len=40)

    if not text:
        _record_drop("too_short_or_invalid")
        return ""

    _record_keep()
    return text


def classify_category(product_name: str) -> str:
    text = _normalize_space(product_name).lower()

    categories = {
        "주방": ["kitchen", "cook", "pan", "pot", "knife", "spoon", "fork", "dish", "cup", "bottle", "텀블러", "주방", "조리", "냄비", "프라이팬"],
        "반려동물": ["pet", "dog", "cat", "puppy", "kitten", "반려", "강아지", "고양이", "사료", "장난감"],
        "자동차": ["car", "auto", "vehicle", "dash", "tire", "motor", "차량", "자동차", "세차", "주차", "블랙박스"],
        "계절용품": ["summer", "winter", "rain", "snow", "heat", "cool", "fan", "heater", "여름", "겨울", "장마", "우산", "선풍기", "히터"],
        "생활용품": ["home", "house", "storage", "clean", "organizer", "bath", "laundry", "생활", "수납", "청소", "욕실", "세탁"],
    }

    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "생활용품"


def build_recommend_reasons(product_name: str, sources: list) -> list:
    text = _normalize_space(product_name).lower()
    source_set = {str(x).strip().lower() for x in (sources or []) if str(x).strip()}
    reasons = []

    if any(token in text for token in ["summer", "여름", "cool", "fan"]):
        reasons.append("여름 시즌")
    elif any(token in text for token in ["winter", "겨울", "heater", "snow"]):
        reasons.append("겨울 시즌")

    if len(source_set) >= 2:
        reasons.append("검색량 증가")

    if "amazon" not in source_set:
        reasons.append("경쟁도 낮음")

    if not reasons:
        reasons.append("트렌드 기반 검토 필요")

    return reasons[:3]
