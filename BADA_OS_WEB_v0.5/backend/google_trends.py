import urllib.request
import xml.etree.ElementTree as ET

def fetch_google_trends(geo, max_items=30):
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 BADA-OS/0.5"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read()

    root = ET.fromstring(raw)
    rows = []
    for item in root.findall(".//item")[:max_items]:
        title = (item.findtext("title") or "").strip()
        if title:
            rows.append({"title": title, "keyword": title, "source": "google", "region": geo})
    return rows
