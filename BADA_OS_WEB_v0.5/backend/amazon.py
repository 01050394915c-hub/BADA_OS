import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

AMAZON_BESTSELLERS_URL = "https://www.amazon.com/gp/bestsellers"


class _AmazonLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_product_link = False
        self._current_href = None
        self._current_text = []
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href", "")
        if tag == "a" and self._looks_like_product_link(href):
            self._in_product_link = True
            self._current_href = href
            self._current_text = []

    def handle_endtag(self, tag):
        if self._in_product_link and tag == "a":
            text = " ".join(part.strip() for part in self._current_text if part.strip())
            if text:
                self.results.append((self._current_href, text))
            self._in_product_link = False
            self._current_href = None
            self._current_text = []

    def handle_data(self, data):
        if self._in_product_link and data and data.strip():
            self._current_text.append(data.strip())

    @staticmethod
    def _looks_like_product_link(href):
        if not href:
            return False
        lower = href.lower()
        return any(token in lower for token in ("/dp/", "/gp/product/", "/product/"))


def _normalize_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_url(href):
    return urllib.parse.urljoin("https://www.amazon.com", href)


def _extract_category(html):
    for pattern in [
        r"Best Sellers in ([^<]+)",
        r"<h1[^>]*>(.*?)</h1>",
        r"<h2[^>]*>(.*?)</h2>",
        r"<title>(.*?)</title>",
    ]:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            text = _normalize_text(re.sub(r"<[^>]+>", " ", match.group(1)))
            if text:
                return text
    return "Amazon Best Sellers"


def _extract_from_regex(html):
    results = []
    for match in re.finditer(r'href="([^"]+)"', html):
        href = match.group(1)
        if not href.startswith("http"):
            href = urllib.parse.urljoin("https://www.amazon.com", href)
        if any(token in href for token in ("/dp/", "/gp/product/", "/product/")):
            results.append((href, ""))
    return results


def _extract_title_from_href(href):
    if not href:
        return "Amazon Product"
    match = re.search(r'/dp/([A-Z0-9]{3,})', href, re.IGNORECASE)
    if match:
        return f"Amazon Product {match.group(1)}"
    return "Amazon Product"


def _extract_from_playwright(max_items=20):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
            )
            page.goto(AMAZON_BESTSELLERS_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            category = _normalize_text(page.locator("h1").first.text_content(timeout=5000)) or _normalize_text(page.locator("#zg_banner_text").first.text_content(timeout=5000)) or "Amazon Best Sellers"
            rows = page.evaluate(
                """
                () => {
                    const anchors = Array.from(document.querySelectorAll('a[href*="/dp/"]'));
                    const seen = new Set();
                    const rows = [];
                    for (const anchor of anchors) {
                        const href = anchor.getAttribute('href') || '';
                        const text = (anchor.textContent || '').replace(/\s+/g, ' ').trim();
                        if (!href || !text || text.length < 4 || text.length > 140) continue;
                        if (/^\$/.test(text) || /offers? from/i.test(text) || /see more/i.test(text) || /shop now/i.test(text) || /customer reviews/i.test(text) || /sign in/i.test(text) || /amazon basics/i.test(text)) continue;
                        const key = `${href}|${text}`.toLowerCase();
                        if (seen.has(key)) continue;
                        seen.add(key);
                        rows.push({ title: text, href });
                        if (rows.length >= 20) break;
                    }
                    return rows;
                }
                """
            )
            browser.close()
    except Exception:
        return []

    results = []
    for item in rows[:max_items]:
        title = _normalize_text(item.get("title", ""))
        href = item.get("href", "") or ""
        url = _normalize_url(href)
        if not title:
            title = _extract_title_from_href(url)
        if len(title) < 3 or len(title) > 140:
            continue
        results.append({
            "title": title,
            "source": "amazon",
            "region": "US",
            "category": category,
            "url": url,
        })
    return results


def fetch_amazon_best_sellers(max_items=20):
    try:
        request = urllib.request.Request(
            AMAZON_BESTSELLERS_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        html = ""

    category = _extract_category(html)
    parser = _AmazonLinkParser()
    parser.feed(html)
    pattern_results = _extract_from_regex(html)

    combined = parser.results + pattern_results
    results = []
    seen = set()

    for href, title in combined:
        clean_title = _normalize_text(title)
        url = _normalize_url(href)
        if not clean_title:
            clean_title = _extract_title_from_href(url)
        if len(clean_title) < 3 or len(clean_title) > 140:
            continue
        if any(token in clean_title.lower() for token in ("see more", "shop now", "customer reviews", "sign in", "amazon basics")):
            continue
        if url in seen or clean_title in seen:
            continue
        seen.add(url)
        seen.add(clean_title)
        results.append({
            "title": clean_title,
            "source": "amazon",
            "region": "US",
            "category": category,
            "url": url,
        })
        if len(results) >= max_items:
            break

    if len(results) < 3:
        playwright_results = _extract_from_playwright(max_items)
        if playwright_results:
            return playwright_results

    return results[:max_items]
