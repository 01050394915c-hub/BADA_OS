import hashlib
import re
from datetime import datetime

from .candidate_cleaner import build_recommend_reasons, classify_category, clean_candidate_name


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_keyword(value: str) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"[^0-9a-zA-Z가-힣\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _make_id(keyword: str) -> str:
    digest = hashlib.md5(keyword.encode("utf-8")).hexdigest()[:12]
    return f"cand-{digest}"


def _score_candidate(item: dict) -> tuple:
    score = 0
    reasons = []

    sources = item.get("sources", [])
    source_set = set(sources)

    if "google" in source_set:
        score += 25
        reasons.append("Google Trends에서 확인된 키워드")
    if "naver" in source_set:
        score += 20
        reasons.append("Naver 쇼핑 트렌드에서 확인됨")
    if "amazon" in source_set:
        score += 25
        reasons.append("Amazon Best Sellers 연관 신호")

    if len(source_set) >= 2:
        score += 20
        reasons.append("복수 소스에서 중복 확인")

    keyword = item.get("keyword", "")
    if 3 <= len(keyword) <= 24:
        score += 10
        reasons.append("검색 키워드 길이가 적정 범위")

    if item.get("url"):
        score += 5
        reasons.append("원문 링크가 포함되어 후속 검토 가능")

    score = max(0, min(100, score))
    if score >= 80:
        status = "우선 검토"
    elif score >= 60:
        status = "관찰 후보"
    else:
        status = "보류"

    if not reasons:
        reasons = ["수집 데이터 기반 기본 후보"]

    return score, status, reasons[:5]


def build_candidates(collected_rows: list, created_at: str = None) -> list:
    created_at = created_at or datetime.now().isoformat(timespec="seconds")

    merged = {}
    for row in collected_rows or []:
        raw_keyword = row.get("keyword") or row.get("title") or ""
        keyword = _clean_text(raw_keyword)
        norm = _normalize_keyword(keyword)
        if not norm:
            continue

        source = _clean_text(row.get("source", "unknown")).lower()
        canonical_source = "google" if source.startswith("google") else "naver" if source.startswith("naver") else "amazon" if source == "amazon" else source
        url = _clean_text(row.get("url", ""))

        if norm not in merged:
            merged[norm] = {
                "keyword": keyword,
                "sources": [],
                "url": url,
            }

        entry = merged[norm]
        if canonical_source and canonical_source not in entry["sources"]:
            entry["sources"].append(canonical_source)

        if not entry.get("url") and url:
            entry["url"] = url

        if len(keyword) > len(entry.get("keyword", "")):
            entry["keyword"] = keyword

    candidates = []
    for _, entry in merged.items():
        score, status, reasons = _score_candidate(entry)
        raw_keyword = entry["keyword"]
        cleaned_keyword = clean_candidate_name(raw_keyword)
        if not cleaned_keyword:
            continue

        category = classify_category(cleaned_keyword)
        recommend_reasons = build_recommend_reasons(cleaned_keyword, entry.get("sources", []))
        source_text = ", ".join(entry["sources"]) if entry["sources"] else "unknown"

        candidate = {
            "id": _make_id(cleaned_keyword),
            "keyword": cleaned_keyword,
            "source": source_text,
            "sources": entry["sources"],
            "score": score,
            "status": status,
            "created_at": created_at,
            "reasons": reasons,
            "category": category,
            "recommend_reasons": recommend_reasons,
            "raw_keyword": raw_keyword,
            # compatibility fields for existing UI paths
            "name": cleaned_keyword,
            "reason": " · ".join(reasons),
            "signals": reasons,
            "search_url": entry.get("url") or "",
            "source_label": source_text,
            "risk": "실제 판매 전 상세 규격/인증/권리 검토 필요",
        }
        candidates.append(candidate)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates
