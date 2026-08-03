import re


COMPANY_PATTERNS = [
    r"유한회사",
    r"무역회사",
    r"주식회사",
    r"법인",
    r"공장명",
    r"공장",
    r"제조사",
    r"有限公司",
    r"有限责任公司",
    r"贸易有限公司",
    r"贸易公司",
    r"贸易",
    r"工厂",
    r"厂家",
    r"公司",
    r"深圳",
    r"广州",
    r"东莞",
    r"义乌",
    r"shenzhen",
    r"guangzhou",
    r"dongguan",
    r"yiwu",
]

FORBIDDEN_PATTERNS = [
    r"최저가",
    r"1위",
    r"완벽",
    r"치료",
    r"기적",
    r"특가",
    r"무조건",
]

FEATURE_PRIORITY = [
    "천연",
    "인센스",
    "로프향",
    "명상향",
    "천연향",
    "홈프래그런스",
    "수제",
    "향기",
    "선택형",
]

FALLBACK_FEATURES = ["천연", "홈프래그런스", "로프향", "인센스", "명상향"]


def _clean_text(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _remove_company_terms(value: str) -> str:
    text = _clean_text(value)
    for pattern in COMPANY_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.I)
    text = re.sub(r"[\(\)\[\]\{\}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _remove_chinese_chars(value: str) -> str:
    text = _clean_text(value)
    text = re.sub(r"[\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _remove_forbidden_terms(value: str) -> str:
    text = _clean_text(value)
    for pattern in FORBIDDEN_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_tokens(value: str) -> list:
    text = _clean_text(value)
    if not text:
        return []
    tokens = re.split(r"[\s,|/·]+", text)
    result = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if len(token) <= 1:
            continue
        if token in result:
            continue
        result.append(token)
    return result


def _collect_feature_tokens(*texts) -> list:
    merged = " ".join(_clean_text(x) for x in texts if _clean_text(x))
    merged_lower = merged.lower()

    found = []
    for keyword in FEATURE_PRIORITY:
        if keyword.lower() in merged_lower and keyword not in found:
            found.append(keyword)

    for token in _split_tokens(merged):
        if token in found:
            continue
        if len(token) < 2:
            continue
        if re.search(r"[\u4e00-\u9fff]", token):
            continue
        found.append(token)

    if not found:
        found = FALLBACK_FEATURES.copy()

    return found


def _trim_to_length(value: str, min_len: int = 25, max_len: int = 40) -> str:
    text = _clean_text(value)
    if len(text) > max_len:
        text = text[:max_len].rstrip()

    if len(text) < min_len:
        pad = " 홈프래그런스"
        while len(text) < min_len:
            text = (text + pad).strip()
            if len(text) > max_len:
                text = text[:max_len].rstrip()
                break

    return text


def generate_selling_title(title: str, translated_title: str, price: str, moq: str, options: list) -> str:
    original = _remove_chinese_chars(_remove_company_terms(title))
    translated = _remove_chinese_chars(_remove_company_terms(translated_title))

    option_tokens = []
    for item in options or []:
        cleaned_option = _remove_chinese_chars(_remove_company_terms(str(item)))
        option_tokens.extend(_split_tokens(cleaned_option))

    base_tokens = _split_tokens(translated)
    if not base_tokens:
        base_tokens = _split_tokens(original)

    features = _collect_feature_tokens(translated, original, " ".join(option_tokens), " ".join(base_tokens))
    if not features:
        features = FALLBACK_FEATURES.copy()

    moq_value = 0
    price_value = 0
    moq_digits = re.sub(r"[^0-9]", "", str(moq or ""))
    price_digits = re.sub(r"[^0-9]", "", str(price or ""))
    if moq_digits:
        moq_value = int(moq_digits)
    if price_digits:
        price_value = int(price_digits)

    moq_tag = "소량구매형" if 1 <= moq_value <= 2 else ""
    price_tag = "천연향" if 1 <= price_value <= 100 else ""
    extra_tags = [x for x in [moq_tag, price_tag] if x]

    prioritized = []
    for token in features + extra_tags:
        token = _remove_forbidden_terms(token)
        token = _clean_text(token)
        if not token:
            continue
        if re.search(r"[\u4e00-\u9fff]", token):
            continue
        if token in prioritized:
            continue
        prioritized.append(token)

    if not prioritized:
        prioritized = FALLBACK_FEATURES.copy()

    prioritized = prioritized[:7]
    core = " ".join(prioritized)

    title_candidates = [
        f"{core}",
        f"천연 {core}",
        f"{core} 홈프래그런스",
    ]

    selected = ""
    for candidate in title_candidates:
        candidate = _remove_forbidden_terms(candidate)
        candidate = _trim_to_length(candidate, 25, 40)
        if 25 <= len(candidate) <= 40:
            selected = candidate
            break

    if not selected:
        selected = _trim_to_length(_remove_forbidden_terms(" ".join(FALLBACK_FEATURES)), 25, 40)

    if not selected:
        return "번역 실패"

    return selected
