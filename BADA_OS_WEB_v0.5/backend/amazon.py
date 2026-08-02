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
        return "/dp/" in lower or "/gp/product/" in lower or "/product/" in lower


def _normalize_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_url(href):
    return urllib.parse.urljoin("https://www.amazon.com", href)


def _extract_category(html):
    for pattern in [
        r"<h1[^>]*>(.*?)</h1>",
        r"<h2[^>]*>(.*?)</h2>",
        r"Best Sellers in ([^<]+)",
    ]:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            text = _normalize_text(re.sub(r"<[^>]+>", " ", match.group(1)))
            if text:
                return text
    return "Amazon Best Sellers"


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
        return []

    category = _extract_category(html)
    parser = _AmazonLinkParser()
    parser.feed(html)

    results = []
    seen = set()

    for href, title in parser.results:
        clean_title = _normalize_text(title)
        url = _normalize_url(href)
        if not clean_title or len(clean_title) < 3 or len(clean_title) > 140:
            continue
        if any(token in clean_title.lower() for token in ("see more", "shop now", "customer reviews", "sign in")):
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

    return results
