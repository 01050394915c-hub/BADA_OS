import urllib.parse

CATALOG = [
    ("생활·수납","진공 압축팩","真空压缩收纳袋",86,"계절 옷 교체와 공간 절약 수요"),
    ("생활·수납","침대 밑 슬림 수납함","床底收纳盒 超薄",82,"좁은 집 공간 활용 수요"),
    ("생활·수납","접이식 빨래바구니","折叠洗衣篮",80,"접이식·공간절약형 생활용품"),
    ("생활·수납","옷장 칸막이 정리함","衣柜分隔收纳盒",81,"정리 전후 비교가 쉬움"),
    ("청소","창문 틈새 청소 브러시","窗户缝隙清洁刷",88,"전후 비교가 강한 문제 해결형"),
    ("청소","다용도 실리콘 물기 제거기","硅胶刮水器",83,"욕실·주방 공용 사용 가능"),
    ("청소","무선 미니 먼지청소기","桌面迷你吸尘器",84,"책상·차량용 시연이 쉬움"),
    ("청소","신발 세척 브러시 케이스","鞋刷 清洁 收纳",79,"생활 불편 해결형"),
    ("자동차용품","차량용 틈새 수납함","汽车座椅缝隙收纳盒",87,"차량 정리와 분실 방지 수요"),
    ("자동차용품","차량용 헤드레스트 후크","汽车头枕挂钩",82,"간단 설치·명확한 사용 장면"),
    ("자동차용품","차량용 접이식 쓰레기통","汽车折叠垃圾桶",81,"차량 정리 수요"),
    ("자동차용품","차량용 햇빛가리개","汽车遮阳帘",84,"더운 계절 차량용품 수요"),
    ("주방","냉장고 회전 정리 트레이","冰箱旋转收纳盘",89,"보관 전후 비교가 뛰어남"),
    ("주방","싱크대 걸이형 음식물 거름망","水槽挂式过滤网",86,"반복 구매 가능성이 있는 생활소모품"),
    ("주방","밀폐 날짜 표시 클립","食品日期密封夹",80,"식품 보관 문제 해결형"),
    ("주방","접이식 냄비받침","折叠隔热垫",78,"작고 가벼워 배송 부담이 낮음"),
    ("반려동물","반려동물 산책 물병","宠物外出饮水杯",84,"산책 장면에서 효용이 명확"),
    ("반려동물","강아지 발 세척컵","宠物洗脚杯",85,"사용 전후 비교가 쉬움"),
    ("반려동물","반려동물 털 제거 롤러","宠物粘毛器",86,"반복되는 털 문제 해결"),
    ("반려동물","자동차용 반려동물 안전벨트","宠物汽车安全带",77,"안전 관련 수요, 규격 확인 필요"),
    ("여행·캠핑","여행용 압축 파우치","旅行压缩收纳袋",88,"여행 짐 부피 감소 효과가 분명"),
    ("여행·캠핑","휴대용 방수 가방","防水漂流袋",83,"물놀이·여행 시즌 수요"),
    ("여행·캠핑","접이식 피크닉 매트","折叠野餐垫",80,"야외활동 시즌 수요"),
    ("여행·캠핑","캠핑용 다기능 랜턴 걸이","露营灯挂钩 多功能",79,"캠핑 액세서리 수요"),
    ("육아","유모차 컵홀더 수납함","婴儿车杯架收纳",82,"육아 외출 불편 해결형"),
    ("육아","아기 식탁 흡착 수납함","婴儿餐椅吸盘收纳盒",76,"안전·소재 확인이 필요"),
    ("육아","휴대용 기저귀 정리 파우치","便携尿布收纳包",81,"외출 필수품 정리 수요"),
    ("육아","유모차 선풍기 거치대","婴儿车风扇支架",78,"여름철 육아용품 수요"),
    ("뷰티소품","화장대 회전 정리함","旋转化妆品收纳盒",84,"정리 전후 영상에 적합"),
    ("뷰티소품","열기구 수납 실리콘 매트","卷发棒隔热垫",82,"고데기·드라이기 정리 문제 해결"),
    ("뷰티소품","휴대용 브러시 세척통","化妆刷清洗盒",80,"사용법 시연이 쉬움"),
    ("뷰티소품","화장품 샘플 파우치","化妆品分装收纳包",77,"여행·휴대 수요"),
    ("디지털소품","케이블 정리 클립","理线器 数据线固定夹",85,"저가·가벼움·문제 해결형"),
    ("디지털소품","접이식 노트북 거치대","折叠笔记本支架",82,"재택·사무 수요"),
    ("디지털소품","멀티 충전선 정리 케이스","充电线收纳盒",80,"케이블 정리 수요"),
    ("디지털소품","휴대폰 촬영 각도 거치대","手机拍摄支架 多角度",79,"콘텐츠 제작 수요"),
    ("욕실","벽부착 배수 비누받침","壁挂沥水皂盒",84,"무타공·배수 기능 시연 가능"),
    ("욕실","욕실 슬리퍼 건조 걸이","浴室拖鞋架 免打孔",82,"무타공·공간절약형"),
    ("욕실","샤워기 헤드 거치 클립","花洒支架 免打孔",79,"설치 전후 비교가 쉬움"),
    ("욕실","치약 디스펜서 수납 세트","牙膏挤压器 收纳套装",78,"가족 욕실 정리 수요"),
]

LIVE_RULES = {
    "pet": ["pet","dog","cat","강아지","고양이","반려","犬","猫"],
    "car": ["car","vehicle","자동차","차량","車"],
    "home": ["home","storage","organizer","수납","정리","収納"],
    "clean": ["clean","cleaning","청소","세척","掃除"],
    "travel": ["travel","camping","여행","캠핑","旅行"],
    "kitchen": ["kitchen","cooking","주방","요리","厨房"],
    "baby": ["baby","kids","육아","아기","ベビー"],
}

CATEGORY_BONUS = {
    "pet":"반려동물","car":"자동차용품","home":"생활·수납","clean":"청소",
    "travel":"여행·캠핑","kitchen":"주방","baby":"육아"
}

def _hits(trends):
    hits = {k: 0 for k in LIVE_RULES}
    examples = {k: [] for k in LIVE_RULES}
    for item in trends:
        title = str(item.get("title", "")).lower()
        for key, words in LIVE_RULES.items():
            if any(word.lower() in title for word in words):
                hits[key] += 1
                if len(examples[key]) < 3:
                    examples[key].append(item.get("title", ""))
    return hits, examples

def _seasonal(name, category, month):
    bonus, reasons = 0, []
    if month in (7,8) and category in ("여행·캠핑","자동차용품","육아"):
        bonus += 5; reasons.append("여름·휴가 수요")
    if month in (8,9,10) and ("수납" in name or category == "생활·수납"):
        bonus += 5; reasons.append("계절 옷 정리 수요")
    if month in (3,4,5) and category in ("청소","여행·캠핑"):
        bonus += 4; reasons.append("봄 청소·나들이 수요")
    if month in (11,12,1,2) and category in ("생활·수납","자동차용품"):
        bonus += 3; reasons.append("겨울 실내·차량 정리 수요")
    return bonus, reasons


def _build_ai_reasons(trends, name, category, china, score, seasonal_reasons, is_amazon=False):
    reasons = []
    google_hits = 0
    naver_hits = 0
    amazon_hits = 0
    category_hits = 0

    category_key = None
    for key, matched_category in CATEGORY_BONUS.items():
        if matched_category == category:
            category_key = key
            break

    for item in trends:
        source = str(item.get("source", "") or "").lower()
        title = str(item.get("title", "") or "").lower()
        if source.startswith("google"):
            google_hits += 1
        elif source in {"naver", "naver-fallback"}:
            naver_hits += 1
        elif source == "amazon":
            amazon_hits += 1

        if category_key:
            words = LIVE_RULES.get(category_key, [])
            if any(word.lower() in title for word in words):
                category_hits += 1

    if google_hits >= 1:
        reasons.append("Google 검색량 증가")
    if naver_hits >= 1:
        reasons.append("네이버 검색 증가")
    if amazon_hits >= 1 or is_amazon:
        reasons.append("Amazon Bestseller")
    if category_hits >= 1 and category:
        reasons.append(f"{category} 카테고리 강세")
    if seasonal_reasons:
        reasons.append("계절성 상승")
    if not reasons:
        reasons.append("실시간 검색 신호 기반 후보")

    return " · ".join(reasons[:5])


def _collect_sources(trends):
    sources = set()
    for item in trends:
        source = str(item.get("source", "")).lower()
        if source.startswith("google"):
            sources.add("google")
        elif source in {"naver", "naver-fallback"}:
            sources.add("naver")
        elif source == "amazon":
            sources.add("amazon")
    return sorted(sources)


def _build_amazon_candidates(trends, arrival_date):
    rows = []
    for item in trends:
        if str(item.get("source", "")).lower() != "amazon":
            continue
        title = str(item.get("title") or "Amazon 상품").strip()
        category = str(item.get("category") or "Amazon Best Sellers").strip()
        url = str(item.get("url") or "").strip()
        score = 88
        rows.append({
            "name": title,
            "category": category,
            "china_keyword": "",
            "score": score,
            "reason": _build_ai_reasons(trends, title, category, "", score, [], is_amazon=True),
            "signals": ["Amazon US", "Best Sellers"],
            "arrival_date": arrival_date.isoformat(),
            "status": "우선 검토",
            "risk": "KC·상표권·디자인권·실제 쿠팡 경쟁도 확인 필요",
            "search_url": url,
            "amazon_url": url,
            "source": "amazon",
            "source_label": "Amazon US",
            "sources": ["amazon"]
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def build_candidates(trends, arrival_date):
    hits, examples = _hits(trends)
    sources = _collect_sources(trends)
    rows = []
    for category, name, china, base, reason in CATALOG:
        score = base
        signals = []
        for key, matched in CATEGORY_BONUS.items():
            if matched == category and hits.get(key, 0):
                score += min(8, hits[key] * 2)
                signals.extend(examples[key][:2])
        seasonal, seasonal_reasons = _seasonal(name, category, arrival_date.month)
        score += seasonal
        signals.extend(seasonal_reasons)
        rows.append({
            "name": name,
            "category": category,
            "china_keyword": china,
            "score": min(97, score),
            "reason": _build_ai_reasons(trends, name, category, china, min(97, score), seasonal_reasons, is_amazon=False),
            "signals": signals[:3] or [f"{arrival_date.month}월 판매 시작 기준 기본 후보"],
            "arrival_date": arrival_date.isoformat(),
            "status": "우선 검토" if score >= 86 else "관찰 후보",
            "risk": "KC·상표권·디자인권·실제 쿠팡 경쟁도 확인 필요",
            "search_url": "https://s.1688.com/selloffer/offer_search.htm?keywords=" + urllib.parse.quote(china),
            "source": "catalog",
            "source_label": "기본 추천",
            "sources": sources
        })
    rows.extend(_build_amazon_candidates(trends, arrival_date))
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows[:40]
