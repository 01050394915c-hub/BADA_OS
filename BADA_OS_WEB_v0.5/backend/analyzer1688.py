import html
import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from playwright.sync_api import sync_playwright


PROFILE_DIR = Path(__file__).resolve().parent / ".1688_profile"


def _translate_title_to_korean(text: str) -> str:
    text = _clean_text(text)
    if not text:
        return "번역 실패"

    try:
        query = quote(text)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx&sl=zh-CN&tl=ko&dt=t&q=" + query
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = response.read().decode("utf-8", errors="ignore")

        parsed = json.loads(payload)
        chunks = parsed[0] if isinstance(parsed, list) and parsed else []
        translated = "".join(
            chunk[0] for chunk in chunks if isinstance(chunk, list) and chunk and chunk[0]
        )
        translated = _clean_text(translated)
        return translated if translated else "번역 실패"
    except Exception:
        return "번역 실패"


def _clean_text(value: str) -> str:
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _extract_offer_id(url: str) -> str:
    match = re.search(r"/offer/(\d+)\.html", url)
    return match.group(1) if match else ""


def _decode_json_text(value: str) -> str:
    if not value:
        return ""

    try:
        return _clean_text(json.loads(f'"{value}"'))
    except Exception:
        return _clean_text(value)


def _extract_title_from_html(page_html: str) -> str:
    patterns = [
        r'"subject"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"offerTitle"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"productTitle"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title[^>]*>(.*?)</title>",
    ]

    blocked_titles = [
        "请按照说明进行验证",
        "亲，请按照说明进行验证",
        "登录",
        "验证码",
        "安全验证",
        "阿里巴巴",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, re.I | re.S)

        if not match:
            continue

        title = _decode_json_text(match.group(1))

        if not title or len(title) < 4:
            continue

        if any(blocked in title for blocked in blocked_titles):
            continue

        return title

    return ""


def _extract_price_from_html(page_html: str) -> str:
    patterns = [
        r'"price"\s*:\s*"([0-9]+(?:\.[0-9]+)?)"',
        r'"promotionPrice"\s*:\s*"([0-9]+(?:\.[0-9]+)?)"',
        r'"discountPrice"\s*:\s*"([0-9]+(?:\.[0-9]+)?)"',
        r'"priceRange"\s*:\s*"([^"]+)"',
        r"[¥￥]\s*([0-9]+(?:\.[0-9]+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, re.I)

        if match:
            return _clean_text(match.group(1))

    return ""


def _normalize_image_url(value: str, page_url: str) -> str:
    if not value:
        return ""

    value = _decode_json_text(value)
    value = value.replace("\\/", "/").strip()

    if not value:
        return ""

    lowered = value.lower()
    if lowered.startswith("data:image"):
        return ""
    if ".svg" in lowered:
        return ""
    if "icon" in lowered or "favicon" in lowered:
        return ""

    absolute_url = ""
    if value.startswith("//"):
        absolute_url = "https:" + value
    elif value.startswith("http://") or value.startswith("https://"):
        absolute_url = value
    else:
        absolute_url = urljoin(page_url, value)

    parsed = urlparse(absolute_url)
    if parsed.scheme.lower() != "https":
        return ""
    if not parsed.netloc:
        return ""
    if parsed.path.lower().endswith(".svg"):
        return ""

    return absolute_url


def _extract_image_from_html(page_html: str, page_url: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'"mainPicUrl"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"imageUrl"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"image"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"images"\s*:\s*\[\s*"((?:\\.|[^"\\])*)"',
        r'"picUrl"\s*:\s*"((?:\\.|[^"\\])*)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, re.I | re.S)
        if not match:
            continue

        image_url = _normalize_image_url(match.group(1), page_url)
        if image_url:
            return image_url

    return ""


def _extract_moq_from_html(page_html: str) -> str:
    patterns = [
        r'"(?:moq|minOrderQuantity|minOrderNum|beginAmount)"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',
        r"起订量[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)",
        r"最小起订量[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, re.I | re.S)
        if match:
            return _clean_text(match.group(1))

    return ""


def _extract_options_from_html(page_html: str) -> list:
    option_set = []

    patterns = [
        r'"(?:skuValueName|valueName|specValue|attributeValue)"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"name"\s*:\s*"[^"\\]*(?:颜色|颜色分类|色|尺码|尺寸|规格|型号)[^"\\]*"\s*,\s*"value"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"value"\s*:\s*"((?:\\.|[^"\\])*)"\s*,\s*"name"\s*:\s*"[^"\\]*(?:颜色|颜色分类|色|尺码|尺寸|规格|型号)[^"\\]*"',
    ]

    for pattern in patterns:
        for raw_value in re.findall(pattern, page_html, re.I | re.S):
            text = _decode_json_text(raw_value)
            text = re.sub(r"\s+", " ", text).strip(" ,/|\\")

            if not text:
                continue
            if len(text) > 40:
                continue
            if re.fullmatch(r"[0-9.]+", text):
                continue
            if text.lower().startswith("http"):
                continue
            if text in option_set:
                continue

            option_set.append(text)
            if len(option_set) >= 20:
                return option_set

    return option_set


def _is_verification_page(page) -> bool:
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False

    verification_words = [
        "请按照说明进行验证",
        "亲，请按照说明进行验证",
        "安全验证",
        "滑动验证",
    ]

    return any(word in body_text for word in verification_words)


def _extract_visible_title(page) -> str:
    selectors = [
        "h1",
        "[class*='title'] h1",
        "[class*='title']",
        "[class*='subject']",
        "meta[property='og:title']",
    ]

    blocked_titles = [
        "请按照说明进行验证",
        "亲，请按照说明进行验证",
        "登录",
        "验证码",
        "安全验证",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first

            if locator.count() == 0:
                continue

            if selector.startswith("meta"):
                value = locator.get_attribute("content") or ""
            else:
                value = locator.inner_text(timeout=3000) or ""

            value = _clean_text(value)

            if not value or len(value) < 4:
                continue

            if any(blocked in value for blocked in blocked_titles):
                continue

            return value

        except Exception:
            continue

    return ""


def _extract_visible_price(page) -> str:
    selectors = [
        "[class*='price']",
        "[class*='Price']",
        "[data-testid*='price']",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first

            if locator.count() == 0:
                continue

            text = _clean_text(locator.inner_text(timeout=3000))

            match = re.search(r"[¥￥]?\s*([0-9]+(?:\.[0-9]+)?)", text)

            if match:
                return match.group(1)

        except Exception:
            continue

    return ""


def analyze_1688_url(url: str) -> dict:
    url = url.strip()

    if not url:
        return {
            "ok": False,
            "error": "URL이 비어 있습니다.",
        }

    parsed = urlparse(url)

    if "1688.com" not in parsed.netloc.lower():
        return {
            "ok": False,
            "error": "1688 주소가 아닙니다.",
        }

    result = {
        "ok": True,
        "url": url,
        "offer_id": _extract_offer_id(url),
        "title": "",
        "translated_title": "번역 실패",
        "price": "",
        "image": "",
        "moq": "",
        "options": [],
    }

    context = None
    page = None

    def _page_is_alive(target_page) -> bool:
        if target_page is None:
            return False
        try:
            return not target_page.is_closed()
        except Exception:
            return False

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                channel="chrome",
                locale="zh-CN",
                viewport={
                    "width": 1440,
                    "height": 1000,
                },
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            if context.pages:
                page = context.pages[0]
            else:
                page = context.new_page()

            if not _page_is_alive(page):
                result["warning"] = "브라우저 페이지가 닫혀 분석을 진행할 수 없습니다."
                return result

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=45000,
            )

            if _page_is_alive(page):
                page.wait_for_timeout(5000)
            else:
                result["warning"] = "페이지가 닫혀 상품 정보를 추출하지 못했습니다."
                return result

            # 인증 화면이면 사용자가 열린 크롬에서 인증할 시간을 준다.
            if _page_is_alive(page) and _is_verification_page(page):
                print(
                    "1688 인증 화면입니다. 열린 크롬에서 인증을 완료하면 "
                    "자동으로 분석을 계속합니다."
                )

                wait_limit_seconds = 120
                started_at = time.time()

                while time.time() - started_at < wait_limit_seconds:
                    if not _page_is_alive(page):
                        result["warning"] = "인증 대기 중 페이지가 닫혀 분석이 중단되었습니다."
                        return result

                    page.wait_for_timeout(2000)

                    if not _is_verification_page(page):
                        break

                if _page_is_alive(page) and _is_verification_page(page):
                    result["warning"] = (
                        "1688 인증이 완료되지 않았습니다. "
                        "열린 크롬에서 로그인 또는 인증을 완료한 뒤 다시 분석하세요."
                    )
                    return result

            if _page_is_alive(page):
                page.wait_for_timeout(4000)
            else:
                result["warning"] = "페이지가 닫혀 상품 정보를 추출하지 못했습니다."
                return result

            if _page_is_alive(page):
                result["title"] = _extract_visible_title(page)
                result["price"] = _extract_visible_price(page)
            else:
                result["warning"] = "페이지가 닫혀 상품 정보를 추출하지 못했습니다."
                return result

            page_html = ""
            if _page_is_alive(page):
                page_html = page.content()

            if page_html:
                if not result["title"]:
                    result["title"] = _extract_title_from_html(page_html)

                if not result["price"]:
                    result["price"] = _extract_price_from_html(page_html)

                if not result["image"]:
                    result["image"] = _extract_image_from_html(page_html, url)

                if not result["moq"]:
                    result["moq"] = _extract_moq_from_html(page_html)

                if not result["options"]:
                    result["options"] = _extract_options_from_html(page_html)

            if not result["title"]:
                result["warning"] = "상품명을 찾지 못했습니다."
            else:
                result["translated_title"] = _translate_title_to_korean(result["title"])

            if not result["price"]:
                result["price_warning"] = "가격을 찾지 못했습니다."

    except Exception as exc:
        result["warning"] = f"1688 브라우저 분석 실패: {exc}"

    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass

    return result