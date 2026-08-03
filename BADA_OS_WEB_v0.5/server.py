from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import copy
import json
import re
import threading
import urllib.parse
import webbrowser

from backend.google_trends import fetch_google_trends
from backend.naver import fetch_naver_keywords
from backend.scoring import build_candidates
from backend.analyzer1688 import analyze_1688_url
from backend.coupang import fetch_coupang_market
from backend.product_title import generate_selling_title
from backend.ai_product_discovery import MappingRuleBasedDiscoveryEngine

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
SCAN_LOCK = threading.Lock()


def _ensure_favorites(data):
    favorites = data.get("favorites")
    if not isinstance(favorites, list):
        data["favorites"] = []
    return data["favorites"]


def _ensure_candidates(data):
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        data["candidates"] = []
    return data["candidates"]


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


def _normalize_keyword(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    text = re.sub(r"[^0-9a-zA-Z가-힣\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_discovery_engine():
    return MappingRuleBasedDiscoveryEngine.from_rules_file(BASE / "mapping_rules.json")

def run_scan():
    data = load_data()
    existing_candidates = _ensure_candidates(data)
    existing_status_by_id = {}
    for item in existing_candidates:
        candidate_id = str(item.get("id", "")).strip()
        status = str(item.get("status", "")).strip()
        if candidate_id and status:
            existing_status_by_id[candidate_id] = status

    discovery_engine = _load_discovery_engine()
    settings = data.get("settings", {})
    regions = settings.get("regions", ["KR", "US", "JP"])
    source_counts = {"google": 0, "naver": 0, "amazon": 0}
    errors = []
    collected_rows = []

    google_rows = []
    google_region_errors = []
    for region in regions:
        if len(google_rows) >= 30:
            break
        try:
            rows = fetch_google_trends(region, max_items=30)
            for row in rows:
                if len(google_rows) >= 30:
                    break
                google_rows.append({
                    "keyword": row.get("keyword") or row.get("title") or "",
                    "source": "google",
                    "region": region,
                })
        except Exception as exc:
            google_region_errors.append(f"{region}: {type(exc).__name__}")

    source_counts["google"] = len(google_rows)
    collected_rows.extend(google_rows)
    if google_region_errors:
        errors.append("Google Trends 실패 - " + ", ".join(google_region_errors))

    if settings.get("naver_enabled", True):
        try:
            rows = fetch_naver_keywords(max_items=20)
            naver_rows = [
                {
                    "keyword": row.get("keyword") or row.get("title") or "",
                    "source": "naver",
                    "region": "KR",
                }
                for row in rows[:20]
            ]
            source_counts["naver"] = len(naver_rows)
            collected_rows.extend(naver_rows)
            if not naver_rows:
                errors.append("Naver: 수집 0개 (페이지 구조 또는 접근 제한 가능)")
        except Exception as exc:
            errors.append(f"Naver: {type(exc).__name__}")

    # Temporary: exclude Amazon sourcing to prevent low-quality titles and wasted credits.
    source_counts["amazon"] = 0

    filtered_rows, discovery_stats = discovery_engine.build_search_candidates(collected_rows)

    deduped_map = {}
    for row in filtered_rows:
        keyword = str(row.get("keyword", "")).strip()
        norm = _normalize_keyword(keyword)
        if not norm:
            continue

        if norm not in deduped_map:
            deduped_map[norm] = {
                "keyword": keyword,
                "source": row.get("source", "unknown"),
                "region": row.get("region", ""),
                "url": row.get("url", ""),
            }
            continue

        old = deduped_map[norm]
        if len(keyword) > len(str(old.get("keyword", ""))):
            old["keyword"] = keyword
        if not old.get("url") and row.get("url"):
            old["url"] = row.get("url")
    deduped_rows = list(deduped_map.values())
    scanned_at = datetime.now().isoformat(timespec="seconds")
    candidates = build_candidates(filtered_rows, created_at=scanned_at)

    trend_by_candidate = {}
    for row in filtered_rows:
        norm = _normalize_keyword(row.get("keyword", ""))
        if not norm:
            continue
        trend_origin = str(row.get("trend_keyword", "")).strip()
        if not trend_origin:
            continue
        trend_by_candidate.setdefault(norm, [])
        if trend_origin not in trend_by_candidate[norm]:
            trend_by_candidate[norm].append(trend_origin)

    for candidate in candidates:
        norm = _normalize_keyword(candidate.get("keyword", ""))
        if not norm:
            continue
        candidate_id = str(candidate.get("id", "")).strip()
        if candidate_id and candidate_id in existing_status_by_id:
            candidate["status"] = existing_status_by_id[candidate_id]
        if not candidate.get("search_url"):
            candidate["search_url"] = discovery_engine.build_1688_search_url(candidate.get("keyword", ""))
        origins = trend_by_candidate.get(norm, [])
        if origins:
            candidate["trend_keywords"] = origins[:3]

    top_candidates = candidates[:40]

    data["settings"] = settings
    data["candidates"] = top_candidates
    data["last_scan"] = scanned_at
    data["scan_info"] = {
        "total_collected": len(deduped_rows),
        "total_saved": len(top_candidates),
        "scanned_at": scanned_at,
        "source_counts": source_counts,
        "errors": errors,
        "pipeline": {
            "steps": [
                "실시간 키워드 수집",
                "키워드 분류",
                "상품 가능 여부 판단",
                "상품 검색 키워드 생성",
                "1688 검색 후보 생성",
                "기존 분석 엔진 연결",
            ],
            "interpreted_source_count": discovery_stats.get("interpreted_source_count", 0),
            "generated_keyword_count": discovery_stats.get("generated_keyword_count", 0),
            "excluded_non_product_count": discovery_stats.get("excluded_non_product_count", 0),
            "engine": "mapping_rules_v1",
        },
        "source_notes": {
            "google": "실데이터 RSS 기반",
            "naver": "실데이터 수집 시도(접근/구조 제한 가능)",
            "amazon": "임시 제외됨",
        },
    }

    save_data(data)
    global LATEST_PAYLOAD
    LATEST_PAYLOAD = copy.deepcopy(data)
    return copy.deepcopy(data)


def _parse_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body or "{}")

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
        if self.path.startswith("/api/favorites"):
            data = load_data()
            favorites = _ensure_favorites(data)
            self.send_json({"ok": True, "favorites": favorites})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/1688/analyze"):
            request_data = _parse_json_body(self)
            url = request_data.get("url", "").strip()
            self.send_json(analyze_1688_url(url))
            return
        if self.path.startswith("/api/coupang/market"):
            try:
                request_data = _parse_json_body(self)
                keyword = str(request_data.get("keyword", "")).strip()
                self.send_json(fetch_coupang_market(keyword))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        if self.path.startswith("/api/selling-title/generate"):
            try:
                request_data = _parse_json_body(self)
                selling_title = generate_selling_title(
                    title=str(request_data.get("title", "")),
                    translated_title=str(request_data.get("translated_title", "")),
                    price=str(request_data.get("price", "")),
                    moq=str(request_data.get("moq", "")),
                    options=request_data.get("options", []) if isinstance(request_data.get("options", []), list) else [],
                )
                self.send_json({
                    "ok": True,
                    "selling_title": selling_title,
                })
            except Exception as exc:
                self.send_json({
                    "ok": False,
                    "selling_title": "번역 실패",
                    "error": str(exc),
                })
            return
        if self.path.startswith("/api/favorites/add"):
            try:
                payload = _parse_json_body(self)
                data = load_data()
                favorites = _ensure_favorites(data)

                offer_id = str(payload.get("offer_id", "")).strip()
                if offer_id and any(str(x.get("offer_id", "")).strip() == offer_id for x in favorites):
                    self.send_json({
                        "ok": False,
                        "duplicate": True,
                        "message": "이미 관심상품에 저장되어 있습니다.",
                        "favorites": favorites,
                    })
                    return

                options = payload.get("options", [])
                if not isinstance(options, list):
                    options = []

                favorite_item = {
                    "offer_id": offer_id,
                    "title": str(payload.get("title", "")).strip(),
                    "translated_title": str(payload.get("translated_title", "")).strip(),
                    "selling_title": str(payload.get("selling_title", "")).strip(),
                    "url": str(payload.get("url", "")).strip(),
                    "price": str(payload.get("price", "")).strip(),
                    "moq": str(payload.get("moq", "")).strip(),
                    "options": [str(x).strip() for x in options if str(x).strip()],
                    "image": str(payload.get("image", "")).strip(),
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }

                favorites.insert(0, favorite_item)
                save_data(data)
                global LATEST_PAYLOAD
                LATEST_PAYLOAD = copy.deepcopy(data)
                self.send_json({
                    "ok": True,
                    "message": "관심상품에 저장되었습니다.",
                    "favorites": favorites,
                })
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        if self.path.startswith("/api/favorites/delete"):
            try:
                payload = _parse_json_body(self)
                offer_id = str(payload.get("offer_id", "")).strip()
                url = str(payload.get("url", "")).strip()

                data = load_data()
                favorites = _ensure_favorites(data)
                before = len(favorites)

                if offer_id:
                    data["favorites"] = [x for x in favorites if str(x.get("offer_id", "")).strip() != offer_id]
                elif url:
                    data["favorites"] = [x for x in favorites if str(x.get("url", "")).strip() != url]

                removed = len(data["favorites"]) < before
                save_data(data)
                LATEST_PAYLOAD = copy.deepcopy(data)
                self.send_json({
                    "ok": True,
                    "removed": removed,
                    "favorites": data["favorites"],
                })
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        if self.path.startswith("/api/favorites/update-selling-title"):
            try:
                payload = _parse_json_body(self)
                offer_id = str(payload.get("offer_id", "")).strip()
                url = str(payload.get("url", "")).strip()
                selling_title = str(payload.get("selling_title", "")).strip()

                data = load_data()
                favorites = _ensure_favorites(data)

                updated = False
                for item in favorites:
                    item_offer_id = str(item.get("offer_id", "")).strip()
                    item_url = str(item.get("url", "")).strip()
                    if (offer_id and item_offer_id == offer_id) or (not offer_id and url and item_url == url):
                        item["selling_title"] = selling_title
                        updated = True
                        break

                if updated:
                    save_data(data)
                    LATEST_PAYLOAD = copy.deepcopy(data)

                self.send_json({
                    "ok": True,
                    "updated": updated,
                    "favorites": favorites,
                })
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        if self.path.startswith("/api/candidates/approval-pending"):
            try:
                payload = _parse_json_body(self)
                candidate_id = str(payload.get("candidate_id", "")).strip()
                if not candidate_id:
                    self.send_json({"ok": False, "error": "candidate_id가 필요합니다."}, 400)
                    return

                data = load_data()
                candidates = _ensure_candidates(data)
                target = None
                for item in candidates:
                    if str(item.get("id", "")).strip() == candidate_id:
                        target = item
                        break

                if target is None:
                    self.send_json({"ok": False, "error": "후보를 찾을 수 없습니다."}, 404)
                    return

                current_status = str(target.get("status", "")).strip()
                if current_status == "approval_pending":
                    self.send_json({
                        "ok": True,
                        "duplicate": True,
                        "message": "이미 승인 대기 중입니다.",
                        "candidate_id": candidate_id,
                        "status": "approval_pending",
                    })
                    return

                target["status"] = "approval_pending"
                save_data(data)
                LATEST_PAYLOAD = copy.deepcopy(data)
                self.send_json({
                    "ok": True,
                    "duplicate": False,
                    "message": "승인 대기 상태로 변경되었습니다.",
                    "candidate_id": candidate_id,
                    "status": "approval_pending",
                })
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        if self.path.startswith("/api/scan"):
            if not SCAN_LOCK.acquire(blocking=False):
                self.send_json({"ok": False, "error": "이미 스캔이 진행 중입니다. 잠시 후 다시 시도해주세요."}, 429)
                return
            try:
                self.send_json(run_scan())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 500)
            finally:
                SCAN_LOCK.release()
            return
        if self.path.startswith("/api/data"):
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
                save_data(payload)
        
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
