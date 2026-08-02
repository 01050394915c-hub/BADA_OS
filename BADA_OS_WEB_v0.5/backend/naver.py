from playwright.sync_api import sync_playwright

FALLBACK_KEYWORDS = [
    "차량용 틈새 수납함",
    "여행 압축 파우치",
    "반려동물 산책 물병",
    "냉장고 회전 정리 트레이",
    "창문 틈새 청소 브러시",
]

def _clean(value):
    return " ".join((value or "").split()).strip()

def fetch_naver_keywords(max_items=20):
    results = []
    seen = set()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                locale="ko-KR",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            )
            page = context.new_page()
            page.goto("https://shopping.naver.com/home", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)

            for selector in ["a", "button", "[role='link']", "[class*='keyword']", "[class*='rank']", "[class*='trend']"]:
                count = min(page.locator(selector).count(), 250)
                for i in range(count):
                    try:
                        text = _clean(page.locator(selector).nth(i).inner_text(timeout=500))
                    except Exception:
                        continue
                    if not text or len(text) < 2 or len(text) > 24:
                        continue
                    if any(word in text for word in ("로그인", "회원가입", "고객센터", "장바구니", "쇼핑MY", "판매자", "전체서비스", "검색")):
                        continue
                    if text in seen:
                        continue

                    seen.add(text)
                    results.append({"title": text, "source": "naver", "region": "KR"})
                    if len(results) >= max_items:
                        break

                if len(results) >= max_items:
                    break

            context.close()
            browser.close()
    except Exception:
        results = []

    if results:
        return results[:max_items]

    return [{"title": x, "source": "naver-fallback", "region": "KR"} for x in FALLBACK_KEYWORDS[:max_items]]
