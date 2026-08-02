import urllib.request
import xml.etree.ElementTree as ET

def fetch_google_trends(geo):
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 BADA-OS/0.5"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read()

    root = ET.fromstring(raw)
    rows = []
    for item in root.findall(".//item")[:30]:
        title = (item.findtext("title") or "").strip()
        if title:
            rows.append({"title": title, "source": "google", "region": geo})
    return rows
