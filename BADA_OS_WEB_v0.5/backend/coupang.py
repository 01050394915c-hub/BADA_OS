import re
import urllib.request
from urllib.parse import quote_plus


def _to_int(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return int(digits) if digits else 0


def _extract_prices(page_html: str) -> list:
    patterns = [
        r'"discountedPrice"\s*:\s*"?([0-9,]{2,})"?',
        r'"salePrice"\s*:\s*"?([0-9,]{2,})"?',
        r'"priceValue"\s*:\s*"?([0-9,]{2,})"?',
        r'"price"\s*:\s*"?([0-9,]{2,})"?',
    ]

    prices = []
    for pattern in patterns:
        for raw in re.findall(pattern, page_html, re.I):
            value = _to_int(raw)
            if value > 0:
                prices.append(value)

    deduped = sorted(set(prices))
    return deduped[:60]


def _extract_review_count(page_html: str) -> int:
    patterns = [
        r'"ratingCount"\s*:\s*"?([0-9,]+)"?',
        r'"reviewCount"\s*:\s*"?([0-9,]+)"?',
    ]

    values = []
    for pattern in patterns:
        for raw in re.findall(pattern, page_html, re.I):
            value = _to_int(raw)
            if value >= 0:
                values.append(value)

    if not values:
        return 0

    values = sorted(values, reverse=True)
    return values[0]


def _extract_seller_count(page_html: str) -> int:
    seller_names = set(re.findall(r'"vendorName"\s*:\s*"([^"\\]+)"', page_html, re.I))
    if seller_names:
        return len(seller_names)

    seller_ids = set(re.findall(r'"vendorId"\s*:\s*"?([0-9]+)"?', page_html, re.I))
    return len(seller_ids)


def fetch_coupang_market(keyword: str) -> dict:
    keyword = str(keyword or "").strip()

    if not keyword:
        return {
            "ok": False,
            "error": "검색어가 비어 있습니다.",
            "low_price": None,
            "avg_price": None,
            "review_count": 0,
            "seller_count": 0,
        }

    try:
        url = f"https://www.coupang.com/np/search?q={quote_plus(keyword)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            page_html = response.read().decode("utf-8", errors="ignore")

        prices = _extract_prices(page_html)
        low_price = min(prices) if prices else None
        avg_price = round(sum(prices) / len(prices)) if prices else None
        review_count = _extract_review_count(page_html)
        seller_count = _extract_seller_count(page_html)

        payload = {
            "ok": True,
            "keyword": keyword,
            "low_price": low_price,
            "avg_price": avg_price,
            "review_count": review_count,
            "seller_count": seller_count,
        }

        if not prices and review_count == 0 and seller_count == 0:
            payload["warning"] = "쿠팡 시세 정보를 찾지 못했습니다."

        return payload

    except Exception as exc:
        return {
            "ok": False,
            "keyword": keyword,
            "error": f"쿠팡 시세 조회 실패: {exc}",
            "low_price": None,
            "avg_price": None,
            "review_count": 0,
            "seller_count": 0,
        }
