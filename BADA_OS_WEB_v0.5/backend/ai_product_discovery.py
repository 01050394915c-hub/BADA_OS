from pathlib import Path
import json
import re
import urllib.parse


DEFAULT_RULES = {
    "version": "v1",
    "invalid_title_tokens": ["from krw", "krw", "offers"],
    "hard_exclude_tokens": [],
    "blocked_categories_without_mapping": [],
    "shoppable_tokens": [],
    "generic_product_markers": ["용품", "세트", "파우치", "케이스"],
    "categories": [],
    "keyword_mappings": [],
    "search": {
        "template": "https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}"
    },
}


class MappingRuleBasedDiscoveryEngine:
    """Rule-based product discovery engine designed to be replaceable with AI inference later."""

    def __init__(self, rules: dict):
        self.rules = rules or {}
        self.invalid_title_tokens = [str(x).lower() for x in self.rules.get("invalid_title_tokens", [])]
        self.hard_exclude_tokens = [str(x).lower() for x in self.rules.get("hard_exclude_tokens", [])]
        self.blocked_categories_without_mapping = set(self.rules.get("blocked_categories_without_mapping", []))
        self.shoppable_tokens = [str(x).lower() for x in self.rules.get("shoppable_tokens", [])]
        self.generic_product_markers = [str(x).lower() for x in self.rules.get("generic_product_markers", [])]
        self.categories = self.rules.get("categories", [])
        self.keyword_mappings = self.rules.get("keyword_mappings", [])
        self.search_template = self.rules.get("search", {}).get(
            "template", "https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}"
        )

    @classmethod
    def from_rules_file(cls, rules_path: Path):
        try:
            data = json.loads(Path(rules_path).read_text(encoding="utf-8"))
            merged = dict(DEFAULT_RULES)
            merged.update(data)
            return cls(merged)
        except Exception:
            return cls(dict(DEFAULT_RULES))

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _normalize_keyword(value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        text = re.sub(r"[^0-9a-zA-Z가-힣\s]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def _is_invalid_title(self, value: str) -> bool:
        text = self._clean_text(value)
        if not text:
            return True
        lowered = text.lower()
        return any(token and token in lowered for token in self.invalid_title_tokens)

    def classify_keyword(self, keyword: str) -> str:
        text = self._clean_text(keyword).lower()
        if not text:
            return "미분류"
        for rule in self.categories:
            category = str(rule.get("name", "")).strip()
            tokens = [str(x).lower() for x in rule.get("tokens", [])]
            if category and any(token and token in text for token in tokens):
                return category
        return "미분류"

    def _generate_mapped_products(self, keyword: str, category: str) -> tuple:
        text = self._clean_text(keyword).lower()
        generated = []
        intent = ""
        for rule in self.keyword_mappings:
            tokens = [str(x).lower() for x in rule.get("tokens", [])]
            mapped_category = str(rule.get("category", "")).strip()
            if not any(token and token in text for token in tokens):
                continue
            if mapped_category and category != "미분류" and mapped_category != category:
                continue
            generated.extend(rule.get("products", []))
            if not intent:
                intent = str(rule.get("intent", "")).strip()
        return generated, intent

    def _is_shoppable_keyword(self, keyword: str) -> bool:
        text = self._clean_text(keyword).lower()
        if not text:
            return False
        if any(token and token in text for token in self.shoppable_tokens):
            return True
        return any(token and token in text for token in self.generic_product_markers)

    def _dedupe_keywords(self, keywords: list) -> list:
        result = []
        seen = set()
        for keyword in keywords or []:
            text = self._clean_text(keyword)
            if self._is_invalid_title(text):
                continue
            norm = self._normalize_keyword(text)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            result.append(text)
        return result

    def interpret_keyword(self, keyword: str) -> dict:
        trend_keyword = self._clean_text(keyword)
        if self._is_invalid_title(trend_keyword):
            return {
                "include": False,
                "reason": "invalid_title",
                "category": "미분류",
                "shopping_keywords": [],
                "intent": "",
            }

        lowered = trend_keyword.lower()
        if any(token and token in lowered for token in self.hard_exclude_tokens):
            return {
                "include": False,
                "reason": "hard_excluded",
                "category": self.classify_keyword(trend_keyword),
                "shopping_keywords": [],
                "intent": "",
            }

        category = self.classify_keyword(trend_keyword)
        mapped_products, intent = self._generate_mapped_products(trend_keyword, category)

        if not mapped_products and category in self.blocked_categories_without_mapping:
            return {
                "include": False,
                "reason": "blocked_category",
                "category": category,
                "shopping_keywords": [],
                "intent": intent,
            }

        generated = list(mapped_products)
        if not generated and self._is_shoppable_keyword(trend_keyword):
            generated.append(trend_keyword)
            if not intent:
                intent = "직접 상품 키워드"

        deduped = self._dedupe_keywords(generated)
        if not deduped:
            return {
                "include": False,
                "reason": "no_related_product",
                "category": category,
                "shopping_keywords": [],
                "intent": intent,
            }

        return {
            "include": True,
            "reason": "ok",
            "category": category,
            "shopping_keywords": deduped[:8],
            "intent": intent,
        }

    def build_1688_search_url(self, keyword: str) -> str:
        encoded = urllib.parse.quote(self._clean_text(keyword))
        if not encoded:
            return ""
        return self.search_template.replace("{keyword}", encoded)

    def build_search_candidates(self, collected_rows: list) -> tuple:
        generated_rows = []
        interpreted_count = 0
        excluded_count = 0
        generated_count = 0

        for row in collected_rows or []:
            trend_keyword = self._clean_text(row.get("keyword") or row.get("title") or "")
            interpreted = self.interpret_keyword(trend_keyword)
            interpreted_count += 1
            if not interpreted.get("include"):
                excluded_count += 1
                continue

            for shopping_keyword in interpreted.get("shopping_keywords", []):
                generated_count += 1
                generated_rows.append(
                    {
                        "keyword": shopping_keyword,
                        "source": row.get("source", "unknown"),
                        "region": row.get("region", ""),
                        "url": self.build_1688_search_url(shopping_keyword),
                        "trend_keyword": trend_keyword,
                        "ai_intent": interpreted.get("intent", ""),
                        "ai_category": interpreted.get("category", "미분류"),
                        "ai_reason": interpreted.get("reason", "ok"),
                    }
                )

        stats = {
            "interpreted_source_count": interpreted_count,
            "generated_keyword_count": generated_count,
            "excluded_non_product_count": excluded_count,
        }
        return generated_rows, stats
