from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timedelta
import copy
import json
import threading
import urllib.parse
import webbrowser

from backend.google_trends import fetch_google_trends
from backend.naver import fetch_naver_keywords
from backend.amazon import fetch_amazon_best_sellers
from backend.scoring import build_candidates

BASE = Path(__file__).resolve().parent
DATA = BASE / "data.json"
PORT = 8766

DEFAULT = {
    "settings": {"lead_days": 30, "regions": ["KR", "US", "JP"], "naver_enabled": True},
    "candidates": [],
    "favorites": [],
    "last_scan": None,
    "scan_info": {}
}

LATEST_PAYLOAD = None


def load_data():
    if LATEST_PAYLOAD is not None:
        return copy.deepcopy(LATEST_PAYLOAD)
    if not DATA.exists():
        save_data(DEFAULT.copy())
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
        for key, value in DEFAULT.items():
            data.setdefault(key, value)
        return data
    except Exception:
        return json.loads(json.dumps(DEFAULT, ensure_ascii=False))

def save_data(data):
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def run_scan():
    data = load_data()
    settings = data.get("settings", {})
    regions = settings.get("regions", ["KR", "US", "JP"])
    lead_days = int(settings.get("lead_days", 30))

    trends = []
    source_counts = {}
    errors = []

    for region in regions:
        try:
            rows = fetch_google_trends(region)
            trends.extend(rows)
            source_counts[f"google_{region}"] = len(rows)
        except Exception as exc:
            source_counts[f"google_{region}"] = 0
            errors.append(f"Google {region}: {type(exc).__name__}")

    if settings.get("naver_enabled", True):
        try:
            rows = fetch_naver_keywords(max_items=20)
            trends.extend(rows)
            source_counts["naver"] = len(rows)
            source_counts["naver_fallback"] = sum(1 for row in rows if row.get("source") == "naver-fallback")
        except Exception as exc:
            source_counts["naver"] = 0
            errors.append(f"Naver: {type(exc).__name__}")

    try:
        rows = fetch_amazon_best_sellers(max_items=20)
        trends.extend(rows)
        source_counts["amazon"] = len(rows)
        if not rows:
            errors.append("Amazon: 수집 0개")
    except Exception as exc:
        source_counts["amazon"] = 0
        errors.append(f"Amazon: {type(exc).__name__}")

    arrival = datetime.now().date() + timedelta(days=lead_days)
    data["settings"] = settings
    data["candidates"] = build_candidates(trends, arrival)[:40]
    data["last_scan"] = datetime.now().isoformat(timespec="seconds")
    data["scan_info"] = {
        "trend_items": len(trends),
        "source_counts": source_counts,
        "errors": errors,
        "mode": "live" if trends else "catalog-fallback"
    }
    if "amazon" not in data["scan_info"]["source_counts"]:
        data["scan_info"]["source_counts"]["amazon"] = 0
    save_data(data)
    global LATEST_PAYLOAD
    LATEST_PAYLOAD = copy.deepcopy(data)
    return copy.deepcopy(data)

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = urllib.parse.urlparse(path).path.lstrip("/") or "index.html"
        return str(BASE / rel)

    def send_json(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/api/data"):
            self.send_json(load_data())
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/scan"):
            try:
                self.send_json(run_scan())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 500)
            return
        if self.path.startswith("/api/data"):
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
                save_data(payload)
                global LATEST_PAYLOAD
                LATEST_PAYLOAD = copy.deepcopy(payload)
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        self.send_error(404)

def open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")

if __name__ == "__main__":
    print(f"BADA OS WEB v0.5 running at http://127.0.0.1:{PORT}")
    print("Ctrl+C 또는 창을 닫으면 종료됩니다.")
    threading.Timer(1.0, open_browser).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
