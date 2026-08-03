import copy
import json
import os
import re

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class ProductKeywordResult(dict):
    def __str__(self) -> str:
        return str(self.get("product_keyword", ""))


class AIEngine:
    """Provider-agnostic AI interface with dummy responses.

    This class is intentionally API-free for now so that GPT/Claude/Gemini
    providers can be plugged in later without changing call sites.
    """

    _KEYWORD_CACHE = {}
    _OPENAI_TIMEOUT_SECONDS = 20.0
    _DEFAULT_MODEL = "gpt-4.1-mini"
    _BLOCKED_KEYWORDS = [
        "대통령", "국회", "정당", "선거", "탄핵", "정치", "외교", "장관",
        "사건", "사고", "범죄", "재판", "구속", "속보", "사망", "화재",
        "주식", "코스피", "코스닥", "종목", "상한가", "하한가",
        "비트코인", "이더리움", "코인", "coin", "btc", "eth", "xrp",
        "홍길동", "인물", "사람", "배우", "가수", "연예인", "아이돌", "kpop",
        "선수", "감독",
    ]
    _FALLBACK_RULES = [
        {
            "tokens": ["폭염", "heatwave", "heat wave", "무더위", "열대야"],
            "reason": "여름철 수요 증가",
            "products": ["휴대용 선풍기", "넥쿨러", "쿨매트", "냉감 이불"],
        },
        {
            "tokens": ["장마", "rainy", "rain season"],
            "reason": "장마철 대비 수요",
            "products": ["우산", "제습기", "방수 신발 커버", "빨래 건조대"],
        },
        {
            "tokens": ["캠핑", "camping", "차박", "camp"],
            "reason": "캠핑 시즌 수요",
            "products": ["캠핑 의자", "랜턴", "아이스박스", "캠핑 테이블"],
        },
        {
            "tokens": ["반려", "반려견", "강아지", "dog", "pet"],
            "reason": "반려동물 케어 수요",
            "products": ["강아지 쿨매트", "급수기", "산책용품", "펫 브러시"],
        },
        {
            "tokens": ["고양이", "cat", "반려묘"],
            "reason": "반려묘 케어 수요",
            "products": ["고양이 스크래쳐", "자동 급식기", "고양이 화장실 매트"],
        },
        {
            "tokens": ["여행", "travel", "휴가"],
            "reason": "여행 준비 수요",
            "products": ["여행용 압축 파우치", "목베개", "캐리어 정리 파우치", "보조배터리"],
        },
        {
            "tokens": ["생활", "수납", "청소", "정리"],
            "reason": "생활 편의 수요",
            "products": ["수납 정리함", "욕실 수납 선반", "밀대 청소포", "압축봉"],
        },
        {
            "tokens": ["자동차", "차량", "세차", "주차"],
            "reason": "차량 관리 수요",
            "products": ["세차 타월", "차량용 방향제", "휴대용 청소기", "차량용 거치대"],
        },
        {
            "tokens": ["주방", "조리", "요리", "kitchen"],
            "reason": "주방용품 수요",
            "products": ["도마", "주방 수납 트레이", "실리콘 집게", "밀폐용기"],
        },
        {
            "tokens": ["뷰티", "화장품", "스킨케어", "메이크업", "선크림"],
            "reason": "뷰티 소모품 수요",
            "products": ["선크림", "마스크팩", "앰플", "클렌징 오일"],
        },
        {
            "tokens": ["육아", "아기", "유아", "신생아"],
            "reason": "육아 필수품 수요",
            "products": ["아기 이유식 용기", "유모차 선풍기", "턱받이 세트", "젖병 건조대"],
        },
    ]

    def __init__(self):
        self._client = None

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @classmethod
    def _normalize_cache_key(cls, trend_keywords) -> tuple:
        values = trend_keywords if isinstance(trend_keywords, (list, tuple, set)) else [trend_keywords]
        normalized = []
        for value in values:
            text = cls._normalize_text(value).lower()
            if text:
                normalized.append(text)
        return tuple(sorted(dict.fromkeys(normalized)))

    @classmethod
    def _is_blocked_keyword(cls, keyword: str) -> bool:
        lowered = cls._normalize_text(keyword).lower()
        return any(token.lower() in lowered for token in cls._BLOCKED_KEYWORDS)

    def _get_client(self):
        api_key = self._normalize_text(os.getenv("OPENAI_API_KEY"))
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        if OpenAI is None:
            raise RuntimeError("openai package is not available")
        if self._client is None:
            self._client = OpenAI(api_key=api_key, timeout=self._OPENAI_TIMEOUT_SECONDS)
        return self._client

    def _extract_response_text(self, response) -> str:
        text = getattr(response, "output_text", "")
        if text:
            return text

        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
            output_items = dumped.get("output", [])
            chunks = []
            for item in output_items:
                for content in item.get("content", []):
                    if content.get("type") == "output_text" and content.get("text"):
                        chunks.append(content.get("text"))
            return "\n".join(chunks).strip()

        return ""

    def _fallback_generate_product_keywords(self, trend_keywords) -> dict:
        values = trend_keywords if isinstance(trend_keywords, (list, tuple, set)) else [trend_keywords]
        result = []
        seen = set()

        for value in values:
            source_keyword = self._normalize_text(value)
            if not source_keyword or self._is_blocked_keyword(source_keyword):
                continue

            lowered = source_keyword.lower()
            matched = False
            for rule in self._FALLBACK_RULES:
                tokens = [str(token).lower() for token in rule.get("tokens", [])]
                if not any(token in lowered for token in tokens):
                    continue
                matched = True
                for product_keyword in rule.get("products", []):
                    product_keyword = self._normalize_text(product_keyword)
                    cache_token = (source_keyword.lower(), product_keyword.lower())
                    if not product_keyword or cache_token in seen:
                        continue
                    seen.add(cache_token)
                    result.append(
                        ProductKeywordResult(
                            {
                                "source_keyword": source_keyword,
                                "product_keyword": product_keyword,
                                "reason": rule.get("reason", "쇼핑 전환 가능 키워드"),
                            }
                        )
                    )

            if not matched:
                if any(token in lowered for token in [
                    "생활", "수납", "청소", "욕실", "세탁", "주방", "조리",
                    "여름", "겨울", "장마", "반려", "강아지", "고양이",
                    "자동차", "차량", "캠핑", "여행", "뷰티", "육아", "아기",
                ]):
                    cache_token = (source_keyword.lower(), source_keyword.lower())
                    if cache_token not in seen:
                        seen.add(cache_token)
                        result.append(
                            ProductKeywordResult(
                                {
                                    "source_keyword": source_keyword,
                                    "product_keyword": source_keyword,
                                    "reason": "쇼핑 상품으로 확장 가능한 키워드",
                                }
                            )
                        )

        return {"keywords": result}

    def _normalize_keyword_payload(self, payload: dict, input_keywords) -> dict:
        values = input_keywords if isinstance(input_keywords, (list, tuple, set)) else [input_keywords]
        fallback_sources = [self._normalize_text(value) for value in values if self._normalize_text(value)]
        source_set = {value.lower() for value in fallback_sources}
        output = []
        seen = set()

        for item in payload.get("keywords", []):
            if not isinstance(item, dict):
                continue

            source_keyword = self._normalize_text(item.get("source_keyword"))
            product_keyword = self._normalize_text(item.get("product_keyword"))
            reason = self._normalize_text(item.get("reason")) or "AI 추천 결과"

            if not source_keyword and fallback_sources:
                source_keyword = fallback_sources[0]
            if not source_keyword or not product_keyword:
                continue
            if source_set and source_keyword.lower() not in source_set:
                continue
            if self._is_blocked_keyword(source_keyword) or self._is_blocked_keyword(product_keyword):
                continue

            dedupe_key = (source_keyword.lower(), product_keyword.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            output.append(
                ProductKeywordResult(
                    {
                        "source_keyword": source_keyword,
                        "product_keyword": product_keyword,
                        "reason": reason,
                    }
                )
            )

        if not output:
            raise ValueError("no valid AI product keywords")
        return {"keywords": output}

    def generate_product_keywords(self, seed_keyword: str, context: dict = None) -> dict:
        cache_key = self._normalize_cache_key(seed_keyword)
        if cache_key in self._KEYWORD_CACHE:
            return copy.deepcopy(self._KEYWORD_CACHE[cache_key])

        values = seed_keyword if isinstance(seed_keyword, (list, tuple, set)) else [seed_keyword]
        cleaned_keywords = [self._normalize_text(value) for value in values if self._normalize_text(value)]
        if not cleaned_keywords:
            result = {"keywords": []}
            self._KEYWORD_CACHE[cache_key] = copy.deepcopy(result)
            return result

        try:
            client = self._get_client()
            model = self._normalize_text(os.getenv("OPENAI_MODEL")) or self._DEFAULT_MODEL
            prompt = {
                "trend_keywords": cleaned_keywords,
                "rules": {
                    "market": "한국 온라인 쇼핑",
                    "exclude": ["사람 이름", "정치", "주식", "코인", "사건사고", "스포츠 선수"],
                    "output": {
                        "keywords": [
                            {
                                "source_keyword": "원본 트렌드 키워드",
                                "product_keyword": "쇼핑으로 연결 가능한 상품 키워드",
                                "reason": "짧은 이유"
                            }
                        ]
                    }
                }
            }
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "한국 온라인 쇼핑으로 연결 가능한 상품 키워드만 JSON으로 반환하라. "
                                    "사람 이름, 정치, 주식, 코인, 사건사고, 스포츠 선수는 제외하라."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": json.dumps(prompt, ensure_ascii=False),
                            }
                        ],
                    },
                ],
                text={"format": {"type": "json_object"}},
                max_output_tokens=800,
                timeout=self._OPENAI_TIMEOUT_SECONDS,
            )
            raw_text = self._extract_response_text(response)
            parsed = json.loads(raw_text)
            result = self._normalize_keyword_payload(parsed, cleaned_keywords)
        except Exception:
            result = self._fallback_generate_product_keywords(cleaned_keywords)

        self._KEYWORD_CACHE[cache_key] = copy.deepcopy(result)
        return result

    def generate_product_title(self, keyword: str, context: dict = None) -> dict:
        text = self._normalize_text(keyword)
        title = f"{text} 추천 상품" if text else "휴대용 미니 선풍기"
        return {
            "title": title,
            "provider": "dummy",
            "model": "dummy-v1",
        }

    def generate_product_description(self, keyword: str, context: dict = None) -> dict:
        text = self._normalize_text(keyword)
        name = text or "휴대용 선풍기"
        return {
            "description": f"{name} 관련 수요를 기반으로 검토한 더미 설명입니다.",
            "provider": "dummy",
            "model": "dummy-v1",
        }

    def score_candidate(self, candidate: dict, context: dict = None) -> dict:
        return {
            "score": 90,
            "provider": "dummy",
            "model": "dummy-v1",
        }
