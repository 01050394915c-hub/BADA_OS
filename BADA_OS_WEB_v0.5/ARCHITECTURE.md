# BADA OS v1.0 아키텍처 설계도

## 1. 현재 프로젝트 구조와 역할

현재 프로젝트는 아주 작은 웹 기반 소싱 보조 도구입니다. 핵심은 다음 구조로 구성되어 있습니다.

- server.py
  - 웹 서버를 실행하고 `/api/data`, `/api/scan` 요청을 처리하는 중심 진입점입니다.
  - 현재는 Python 표준 라이브러리만으로 HTTP 서버를 띄우고, 브라우저를 자동으로 열어줍니다.

- index.html
  - 사용자 화면입니다.
  - 후보 카드 목록, 통계, 스캔 버튼을 표시합니다.
  - 현재는 단일 HTML 안에 JS 로직이 들어 있어, 향후 모듈화가 필요합니다.

- data.json
  - 앱의 상태를 저장하는 파일입니다.
  - candidates, favorites, last_scan, scan_info, settings를 저장합니다.

- backend/
  - 수집 기능과 추천 점수 계산을 담당하는 Python 모듈들이 모여 있습니다.
  - google_trends.py: Google Trends RSS 수집
  - naver.py: 네이버 쇼핑 키워드 수집
  - amazon.py: Amazon 미국 Best Sellers 수집
  - scoring.py: 후보 점수 계산 및 추천 카드 생성

## 2. 현재 구현된 기능

### 2.1 Google Trends 수집
- Google Trends RSS에서 지역별 인기 키워드를 수집합니다.
- 현재는 KR, US, JP 지역을 순회합니다.
- 수집 실패 시에도 에러를 기록하고 다음 처리로 넘어갑니다.

### 2.2 네이버 쇼핑 수집
- Playwright 기반으로 네이버 쇼핑 페이지에서 텍스트를 수집합니다.
- 수집이 실패하면 fallback 키워드로 대체됩니다.

### 2.3 Amazon 수집
- Amazon 미국 Best Sellers 페이지에서 상품명, 카테고리, 상품 URL을 수집합니다.
- 최대 20개까지 수집하도록 설계되어 있습니다.
- 수집 실패 시 빈 목록을 반환하고 전체 스캔이 멈추지 않도록 처리됩니다.

### 2.4 1688 연결
- 각 후보마다 1688 검색 URL을 생성합니다.
- 사용자는 추천 카드에서 1688 공급처 검색 버튼을 눌러 바로 이동할 수 있습니다.

### 2.5 점수 계산
- scoring.py의 CATALOG와 LIVE_RULES 기반으로 후보 점수를 계산합니다.
- 계절성, 카테고리별 신호, 검색 트렌드 연계로 후보 우선순위를 결정합니다.

## 3. v1.0에서 추가할 핵심 기능

앞으로 BADA OS v1.0에서는 다음 기능을 확장할 예정입니다.

- TikTok Shop 연결
  - 틱톡샵에서 인기 상품/키워드 수집
  - 플랫폼별 트렌드 비교 가능

- 샤오홍슈 연결
  - 샤오홍슈에서 노출되는 제품 키워드, 카테고리 배치 확인
  - 중국 소비 트렌드와 연계

- 쿠팡 경쟁도 분석
  - 쿠팡 검색량, 리뷰 수, 가격대, 판매자 수를 비교
  - 경쟁이 치열한 상품은 가점 낮춤

- KC 인증 정보 안내
  - 대상 제품이 KC 인증이 필요한지 여부를 표시
  - 인증 필요 여부와 리스크를 함께 노출

- 상표권/디자인권 안내
  - 유사 상표, 디자인 침해 가능성 확인 안내
  - 법적 리스크를 추천 카드에 반영

- AI 추천 TOP10
  - 여러 소스의 신호와 리스크를 종합해 최종 TOP10 후보를 생성
  - 사용자에게 가장 현실적인 추천 카드 우선 노출

## 4. 데이터가 수집되어 최종 카드로 표시되는 전체 흐름

현재 흐름은 다음 순서로 동작합니다.

1. 사용자가 화면의 스캔 버튼을 누릅니다.
2. server.py의 run_scan()가 실행됩니다.
3. Google Trends, Naver, Amazon 등 각 backend 모듈이 데이터를 수집합니다.
4. 수집된 결과는 trends 리스트에 합쳐집니다.
5. scoring.py가 trends와 날짜 정보를 기반으로 후보 카드 40개를 생성합니다.
6. 생성된 candidates는 data.json에 저장됩니다.
7. index.html이 `/api/data`로 데이터를 읽어와 카드 UI에 표시합니다.

이 흐름은 앞으로도 유지하되, 각 소스를 독립적인 모듈로 분리해서 확장하기 쉽도록 설계할 수 있습니다.

## 5. backend 모듈로 분리하는 구조

v1.0에서는 각 소스별 수집 기능을 다음처럼 분리하는 것이 좋습니다.

- sources/google_trends.py
  - Google Trends 수집

- sources/naver.py
  - 네이버 쇼핑 키워드 수집

- sources/amazon.py
  - Amazon Best Sellers 수집

- sources/tiktok_shop.py
  - TikTok Shop 수집

- sources/xiaohongshu.py
  - 샤오홍슈 수집

- sources/coupang.py
  - 쿠팡 경쟁도 분석

- sources/compliance.py
  - KC 인증, 상표권, 디자인권 검토

- scoring.py
  - 각 소스 결과를 종합해 후보 점수 계산

- pipeline.py
  - 수집 → 정제 → 점수 계산 → 저장까지 전체 흐름 조율

이 구조를 적용하면 기존 server.py는 단순히 API 요청과 데이터 저장 역할만 담당하게 할 수 있습니다.

## 6. 오류가 나도 전체 프로그램이 멈추지 않는 구조

현재 구현은 이미 다음 원칙을 따르고 있습니다.

- 각 수집 함수는 예외를 내부에서 처리합니다.
- 서버의 run_scan()는 각 소스 수집을 개별 try/except로 감쌉니다.
- 실패한 소스는 errors 리스트에 기록하고, 이후 단계는 계속 진행합니다.
- 수집 결과가 비어 있더라도 후보 생성은 계속 진행됩니다.

v1.0에서도 이 원칙을 계속 유지해야 합니다.

권장 방식:
- 각 수집 모듈은 실패 시 빈 리스트를 반환한다.
- scan_info에 source_counts와 errors를 기록한다.
- 후보 생성 단계는 수집 결과가 비어 있어도 동작하도록 한다.
- 중요한 오류는 로그로 남기되, 사용자 화면은 계속 보여준다.

## 7. data.json에 저장할 권장 데이터 구조

현재 data.json은 작지만, v1.0에서는 아래처럼 확장하는 것이 좋습니다.

```json
{
  "settings": {
    "lead_days": 30,
    "regions": ["KR", "US", "JP"],
    "naver_enabled": true,
    "amazon_enabled": true,
    "tiktok_enabled": false,
    "xiaohongshu_enabled": false,
    "coupang_enabled": false
  },
  "candidates": [
    {
      "name": "상품명",
      "category": "카테고리",
      "score": 90,
      "status": "우선 검토",
      "reason": "추천 이유",
      "signals": ["Google Trends", "Amazon", "TikTok"],
      "risk": "KC 인증 필요",
      "search_url": "https://...",
      "source_breakdown": {
        "google": 1,
        "naver": 1,
        "amazon": 1,
        "tiktok": 0
      }
    }
  ],
  "favorites": [],
  "last_scan": "2026-08-02T11:00:00",
  "scan_info": {
    "trend_items": 50,
    "source_counts": {
      "google_KR": 10,
      "google_US": 10,
      "google_JP": 10,
      "naver": 7,
      "amazon": 5,
      "tiktok": 0
    },
    "errors": [],
    "mode": "live"
  }
}
```

이 구조를 쓰면 화면과 API가 확장되어도 기존 데이터 포맷을 크게 깨지 않게 유지할 수 있습니다.

## 8. 설정 화면에서 각 소스를 켜고 끄는 구조

v1.0에서는 설정 화면이 있어야 합니다. 권장 방식은 다음과 같습니다.

- 각 소스별 ON/OFF 토글
  - Google Trends
  - Naver
  - Amazon
  - TikTok Shop
  - XiaoHongShu
  - Coupang

- 각 소스마다 옵션값을 가질 수 있음
  - 최대 수집 개수
  - 지역 설정
  - 언어 설정
  - 스캔 우선순위

- 설정은 data.json의 settings 안에 저장
  - 서버가 재시작해도 유지됨

이 구조를 쓰면 사용자가 필요한 소스만 켜서 스캔할 수 있고, 기존 기본 흐름도 유지할 수 있습니다.

## 9. API 키나 개인정보는 .env에 보관하는 원칙

v1.0 개발에서는 다음 원칙을 정하는 것이 좋습니다.

- API 키, 토큰, 계정 정보는 코드에 직접 쓰지 않는다.
- .env 파일에 보관한다.
- Python에서는 `python-dotenv` 같은 라이브러리로 읽어온다.
- `.env.example` 파일을 같이 두어 개발자가 필요한 값을 적을 수 있게 한다.

예시:

```text
GOOGLE_TRENDS_API=optional
TIKTOK_TOKEN=
XIAOHONGSHU_TOKEN=
```

## 10. 현재 코드를 최대한 유지하면서 확장하는 방법

기존 코드를 그대로 살리되, 다음 방식으로 점진적으로 확장하는 것이 가장 안전합니다.

1. 기존 server.py의 `run_scan()`는 유지한다.
2. 기존 backend 모듈은 그대로 둔다.
3. 새 기능은 새 파일로 추가한다.
4. server.py에서 새 모듈을 import해서 호출만 추가한다.
5. index.html은 기존 구조를 유지하되, 나중에 설정 패널과 상세 정보를 추가한다.
6. data.json의 구조를 확장하되, 기존 키는 유지한다.

즉, v1.0은 “기존 앱을 크게 바꾸지 않으면서 기능만 확장하는 방향”으로 설계하는 것이 좋습니다.
