import streamlit as st
import pandas as pd
import requests
import time
import warnings
import logging
from datetime import datetime, timedelta

# ✅ 경고 메시지 억제
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

# ─────────────────────────────────────────
# 네이버금융 공통 헤더 (로그인 불필요)
# ─────────────────────────────────────────
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

KRX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer":      "http://data.krx.co.kr/",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept":       "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

# ─────────────────────────────────────────
# ✅ API 키 직접 입력 (여기서 수정하세요)
# ─────────────────────────────────────────
API_KEY    = "WZGNvZBI3uQ3a4Cz8n6f9WHDOlajAwaBj1RZaJtZW0A"
SECRET_KEY = "q0yYXjZ38XoTbdzWmg9i_Ie943GrkUNow2T3li75BiY"
BASE_URL   = "https://api.kiwoom.com"

# ─────────────────────────────────────────
# 1. 페이지 설정 및 UI
# ─────────────────────────────────────────
st.set_page_config(page_title="Kiwoom Real Master", layout="wide")
st.sidebar.title("⚙️ 스캔 설정")
st.sidebar.caption(f"🌐 실전투자 서버: `{BASE_URL}`")
st.sidebar.divider()

st.sidebar.subheader("🎯 스캔 필터")
f_rising = st.sidebar.checkbox("1. 10% 이상 가격 상승",           value=True)
f_money  = st.sidebar.checkbox("2. 거래대금 200억 이상",           value=True)
f_signal = st.sidebar.checkbox("3. RSI & OBV 골든크로스 후 유지",  value=True)

st.sidebar.divider()
st.sidebar.info("""
**📌 3번 조건 상세**
- RSI(14)가 Signal(9)선을 **아래→위 골든크로스**
- 이후 현재까지 **시그널선 위 유지** 중
- OBV도 동일 조건 동시 만족
""")
# ✅ 수정 후 - session_state로 날짜 실시간 반영
target_date    = st.sidebar.date_input("조회 날짜", datetime.today())
formatted_date = target_date.strftime("%Y%m%d")

# ✅ 주말/공휴일 경고
if target_date.weekday() >= 5:
    st.sidebar.warning(f"⚠️ {target_date.strftime('%Y/%m/%d')}은 주말입니다!\n직전 거래일로 변경해 주세요.")
else:
    st.sidebar.info(f"📅 조회 날짜: {target_date.strftime('%Y년 %m월 %d일')}")

if "last_date" not in st.session_state:
    st.session_state["last_date"] = formatted_date

if st.session_state["last_date"] != formatted_date:
    st.session_state["last_date"] = formatted_date
    st.sidebar.success(f"📅 날짜 변경됨: {formatted_date}")

# ✅ 날짜 변경 감지 → 캐시 초기화는 스캔 시작 버튼 안에서 처리

if not YF_AVAILABLE:
    st.sidebar.warning("⚠️ yfinance 미설치\n`pip install yfinance`")


# ─────────────────────────────────────────
# 2. 섹터 매핑 테이블
# ─────────────────────────────────────────
# (A) yfinance용 영문 industry/sector → 한국어 이모지 섹터
SECTOR_KR = {
    "Technology":                             "💻 기술/IT",
    "Semiconductors":                         "🔬 반도체",
    "Consumer Cyclical":                      "🛍️ 경기소비재",
    "Consumer Defensive":                     "🛒 필수소비재",
    "Healthcare":                             "💊 바이오/헬스케어",
    "Industrials":                            "🏭 산업재",
    "Basic Materials":                        "⚙️ 소재/화학",
    "Financial Services":                     "🏦 금융",
    "Energy":                                 "⛽ 에너지",
    "Communication Services":                 "📡 통신",
    "Real Estate":                            "🏠 부동산",
    "Utilities":                              "💡 유틸리티",
    "Semiconductor Equipment & Materials":    "🔬 반도체장비",
    "Electronic Components":                  "🔬 전자부품",
    "Batteries & Energy Storage":             "🔋 2차전지",
    "Auto Parts":                             "🚗 자동차부품",
    "Biotechnology":                          "🧬 바이오",
    "Drug Manufacturers—General":             "💊 제약",
    "Drug Manufacturers—Specialty & Generic": "💊 제약",
    "Chemicals":                              "🧪 화학",
    "Specialty Chemicals":                    "🧪 특수화학",
    "Steel":                                  "🔩 철강",
    "Personal Products":                      "💄 화장품/생활용품",
    "Software—Application":                   "💻 소프트웨어",
    "Software—Infrastructure":                "💻 소프트웨어",
    "Internet Content & Information":         "🌐 인터넷/플랫폼",
    "Aerospace & Defense":                    "🛡️ 방산/항공",
    "Marine Shipping":                        "🚢 해운",
    "Engineering & Construction":             "🏗️ 건설",
    "Medical Devices":                        "🏥 의료기기",
    "Diagnostics & Research":                 "🧪 진단/연구",
    "Insurance":                              "🏦 보험",
    "Banks—Regional":                         "🏦 은행",
    "Capital Markets":                        "🏦 증권",
    "Entertainment":                          "🎬 엔터테인먼트",
    "Electronic Gaming & Multimedia":         "🎮 게임",
    "Packaged Foods":                         "🍽️ 식품",
    "Auto Manufacturers":                     "🚗 자동차",
    "Airlines":                               "✈️ 항공",
    "Integrated Freight & Logistics":         "📦 물류",
    "Oil & Gas Refining & Marketing":         "⛽ 정유",
    "Solar":                                  "☀️ 태양광",
    "Electrical Equipment & Parts":           "⚡ 전기장비",
    "Farm & Heavy Construction Machinery":    "🚜 기계",
}

# (B) ✅ 네이버 모바일 API industryName (한국어) → 이모지 섹터
#    공백/쉼표/가운뎃점 제거 후 매칭 → 매칭률 90% 이상 목표
SECTOR_KR_NAVER = {
    # ── 반도체/전자 ────────────────────────────
    "반도체와반도체장비":     "🔬 반도체",
    "반도체및반도체장비":     "🔬 반도체",
    "반도체":                 "🔬 반도체",
    "전자장비와기기":         "🔬 전자장비",
    "전자장비":               "🔬 전자장비",
    "전자제품":               "🔬 전자부품",
    "전기제품":               "⚡ 전기장비",
    "전기부품":               "🔬 전자부품",
    "하드웨어와장비":         "💻 하드웨어",
    "하드웨어":               "💻 하드웨어",
    "통신장비":               "📡 통신장비",
    "휴대폰":                 "📱 휴대폰",
    "사무용전자제품":         "🖥️ 사무기기",
    "디스플레이장비및부품":   "🔬 전자부품",
    # ── IT/소프트웨어/인터넷/게임 ───────────────
    "IT서비스":               "💻 IT서비스",
    "소프트웨어":             "💻 소프트웨어",
    "응용소프트웨어":         "💻 소프트웨어",
    "시스템소프트웨어":       "💻 소프트웨어",
    "게임엔터테인먼트":       "🎮 게임",
    "게임":                   "🎮 게임",
    "상호작용미디어와서비스": "🌐 인터넷/플랫폼",
    "인터넷서비스":           "🌐 인터넷",
    "인터넷과카탈로그소매":   "🌐 인터넷쇼핑",
    # ── 자동차/조선/항공/해운/물류 ──────────────
    "자동차":                 "🚗 자동차",
    "자동차부품":             "🚗 자동차부품",
    "자동차부품과장비":       "🚗 자동차부품",
    "타이어":                 "🚗 타이어",
    "조선":                   "🚢 조선",
    "항공기부품및장비":       "🛡️ 방산",
    "우주항공과국방":         "🛡️ 방산",
    "방위":                   "🛡️ 방산",
    "항공사":                 "✈️ 항공",
    "항공운수":               "✈️ 항공",
    "해운사":                 "🚢 해운",
    "해상운송":               "🚢 해운",
    "도로와철도":             "🚄 육상운송",
    "도로및철도":             "🚄 육상운송",
    "운송인프라":             "📦 물류",
    "운송":                   "📦 물류",
    "화물운송과물류":         "📦 물류",
    "항공화물운송과물류":     "📦 물류",
    # ── 바이오/제약/의료 ───────────────────────
    "제약":                   "💊 제약",
    "생물공학":               "🧬 바이오",
    "생명과학도구및서비스":   "🧬 바이오",
    "생명과학":               "🧬 바이오",
    "건강관리장비와용품":     "🏥 의료기기",
    "건강관리장비":           "🏥 의료기기",
    "건강관리서비스":         "🏥 의료서비스",
    "건강관리공급업체":       "🏥 의료서비스",
    "건강관리기술":           "🏥 헬스케어IT",
    # ── 화학/정유/철강/소재 ────────────────────
    "화학":                   "🧪 화학",
    "특수화학":               "🧪 특수화학",
    "정유":                   "⛽ 정유",
    "석유와가스":             "⛽ 에너지",
    "통합석유와가스":         "⛽ 에너지",
    "석유와가스장비및서비스": "⛽ 에너지장비",
    "석탄":                   "⛽ 석탄",
    "철강":                   "🔩 철강",
    "비철금속":               "🔩 비철금속",
    "금속과광업":             "🔩 광업",
    "채광":                   "🔩 광업",
    "금속":                   "🔩 금속",
    # ── 건설/건축 ──────────────────────────────
    "건설":                   "🏗️ 건설",
    "건설업체":               "🏗️ 건설",
    "건설과토목":             "🏗️ 건설",
    "건축자재":               "🏗️ 건축자재",
    "건축제품":               "🏗️ 건축자재",
    # ── 2차전지/에너지 ─────────────────────────
    "전력":                   "💡 유틸리티",
    "전기공급":               "💡 유틸리티",
    "발전및에너지판매":       "💡 유틸리티",
    "복합유틸리티":           "💡 유틸리티",
    "가스공급":               "💡 유틸리티",
    "수도공급":               "💡 유틸리티",
    "독립전력생산및에너지거래업자": "💡 유틸리티",
    "재생에너지":             "☀️ 신재생에너지",
    # ── 금융 ───────────────────────────────────
    "은행":                   "🏦 은행",
    "증권":                   "🏦 증권",
    "생명보험":               "🏦 보험",
    "손해보험":               "🏦 보험",
    "보험":                   "🏦 보험",
    "기타금융":               "🏦 금융",
    "창업투자및자본시장":     "🏦 증권",
    "소비자금융":             "🏦 금융",
    "다각화된금융서비스":     "🏦 금융",
    "증권사":                 "🏦 증권",
    # ── 소비재/유통/식품 ───────────────────────
    "화장품":                 "💄 화장품",
    "개인생활용품":           "💄 생활용품",
    "가정용품":               "🏠 생활용품",
    "가정용기기와용품":       "🏠 생활용품",
    "다각화된소비재":         "🛍️ 소비재",
    "의류":                   "👕 의류",
    "의복의류및호화품":       "👕 의류",
    "섬유의류신발및호화품":   "👕 의류",
    "호화품":                 "💎 명품",
    "백화점과일반상점":       "🏬 유통",
    "복합유통업":             "🏬 유통",
    "판매업체":               "🏬 유통",
    "식품과기본식료품소매":   "🛒 식품소매",
    "식품":                   "🍽️ 식품",
    "식료품":                 "🍽️ 식품",
    "포장식품과육류":         "🍽️ 식품",
    "음료":                   "🥤 음료",
    "담배":                   "🚬 담배",
    "농업":                   "🌾 농업",
    "농업및어업":             "🌾 농업",
    "주류":                   "🍺 주류",
    # ── 미디어/엔터/교육/광고 ──────────────────
    "미디어":                 "🎬 미디어",
    "영화와오락":             "🎬 엔터테인먼트",
    "방송과엔터테인먼트":     "🎬 엔터테인먼트",
    "광고":                   "📺 광고",
    "마케팅":                 "📺 광고",
    "교육서비스":             "📚 교육",
    "출판":                   "📚 출판",
    # ── 호텔/레저/외식 ─────────────────────────
    "호텔레저용품과크루즈":   "🏨 레저/호텔",
    "호텔과리조트":           "🏨 호텔",
    "레저용품":               "🎯 레저",
    "레스토랑":               "🍽️ 외식",
    "호텔및레스토랑":         "🏨 레저/호텔",
    "여행과관광":             "✈️ 여행",
    # ── 통신 ───────────────────────────────────
    "통신서비스":             "📡 통신",
    "무선통신서비스":         "📡 통신",
    "다각화된통신서비스":     "📡 통신",
    # ── 기계/산업재 ────────────────────────────
    "기계":                   "🏭 기계",
    "산업기계":               "🏭 기계",
    "상업서비스와공급품":     "🏭 산업재",
    "전문서비스":             "🏭 산업서비스",
    "무역회사와판매업체":     "🏬 유통",
    "인쇄":                   "📄 인쇄",
    "종이와목재":             "📄 제지",
    "컨테이너와포장":         "📦 포장",
    # ── 부동산 ─────────────────────────────────
    "부동산":                 "🏠 부동산",
    "부동산관리및개발":       "🏠 부동산",
    "리츠":                   "🏠 리츠",
    # ── 기타 ───────────────────────────────────
    "지주회사":               "🏢 지주회사",
    "복합기업":               "🏢 지주회사",
}


MANUAL_SECTOR = {
    # ══ 반도체 ══════════════════════════════
    "005930": "🔬 반도체",      # 삼성전자
    "000660": "🔬 반도체",      # SK하이닉스
    "000990": "🔬 반도체",      # DB하이텍
    "042700": "🔬 반도체",      # 한미반도체
    "240810": "🔬 반도체장비",  # 원익IPS
    "084370": "🔬 반도체장비",  # 유진테크
    "058470": "🔬 반도체",      # 리노공업
    "357780": "🔬 반도체",      # 솔브레인
    "260970": "🔬 반도체",      # 에스앤에스텍
    "209640": "🔬 반도체장비",  # 와이제이링크
    "091970": "🔬 반도체",      # 에이치비테크놀러지
    "095340": "🔬 반도체",      # ISC
    "166090": "🔬 반도체",      # 하나머티리얼즈
    "232140": "🔬 반도체장비",  # 에스티아이
    "336370": "🔬 반도체장비",  # 에이피티씨
    "137400": "🔬 반도체장비",  # 피엔티
    "025560": "🔬 반도체장비",  # 미래산업
    "036830": "🔬 반도체",      # 솔브레인홀딩스
    "034220": "🔬 전자부품",    # LG디스플레이
    "009150": "🔬 전자부품",    # 삼성전기
    "265520": "🔬 반도체장비",  # AP시스템
    "222800": "🔬 반도체",      # 심텍
    "178320": "🔬 반도체",      # 서진시스템
    "352480": "🔬 반도체",      # 씨앤씨인터내셔널
    "036170": "🔬 반도체장비",  # 에이치엠넥스
    "049080": "📡 통신장비",    # 기가레인
    "069540": "🌐 광통신/AI인프라", # 빛과전자
    "456010": "🔐 보안반도체",  # 아이씨티케이
    # ══ 2차전지 ═════════════════════════════
    "373220": "🔋 2차전지",     # LG에너지솔루션
    "006400": "🔋 2차전지",     # 삼성SDI
    "247540": "🔋 2차전지",     # 에코프로비엠
    "086520": "🔋 2차전지",     # 에코프로
    "066970": "🔋 2차전지",     # 엘앤에프
    "278280": "🔋 2차전지",     # 천보
    "356800": "🔋 2차전지",     # 엔켐
    "003670": "🔋 2차전지",     # 포스코퓨처엠
    "122860": "🔋 2차전지",     # 포스코DX
    "305090": "🔋 2차전지",     # 이노메트리
    "272290": "🔋 2차전지",     # 이엔드디
    "298040": "🔋 2차전지",     # 효성중공업
    "036200": "🔋 2차전지",     # 유니셈
    "089980": "🔋 2차전지",     # 에코캡
    "025820": "🔋 2차전지",     # 이구산업
    # ══ 바이오/제약 ══════════════════════════
    "207940": "🧬 바이오",      # 삼성바이오로직스
    "068270": "🧬 바이오",      # 셀트리온
    "091990": "🧬 바이오",      # 셀트리온헬스케어
    "299660": "🧬 바이오",      # 셀리드
    "196170": "🧬 바이오",      # 알테오젠
    "141080": "🧬 바이오",      # 레고켐바이오
    "326030": "🧬 바이오",      # SK바이오팜
    "302440": "🧬 바이오",      # SK바이오사이언스
    "214450": "🧬 바이오",      # 파마리서치
    "214370": "🧬 바이오",      # 케어젠
    "086900": "🧬 바이오",      # 메디오젠
    "950130": "🧬 바이오",      # 엑세스바이오
    "253840": "🧪 진단키트",    # 수젠텍
    "096530": "🧪 진단키트",    # 씨젠
    "128940": "💊 제약",        # 한미약품
    "000100": "💊 제약",        # 유한양행
    "185750": "💊 제약",        # 종근당
    "001840": "💊 제약",        # 일양약품
    "069620": "💊 제약",        # 대웅제약
    "048260": "🏥 의료기기",    # 오스템임플란트
    "145020": "🧬 바이오",      # 휴젤
    "220100": "🏥 의료기기",    # 퓨쳐메디컬
    "105630": "💊 제약",        # 한국비엔씨
    "011000": "💊 제약",        # 진원생명과학
    "365550": "🧬 바이오",      # 셀비온
    "019170": "💊 제약",        # 신풍제약
    "093370": "🧪 화학",        # 후성
    # ══ 화장품/뷰티 ══════════════════════════
    "090430": "💄 화장품",      # 아모레퍼시픽
    "002790": "💄 화장품",      # 아모레G
    "051900": "💄 화장품",      # LG생활건강
    "192820": "💄 화장품",      # 코스맥스
    "203690": "💄 화장품",      # 한국콜마
    "166480": "💄 화장품",      # 코스메카코리아
    "078520": "💄 화장품",      # 에이블씨엔씨
    "263720": "💄 화장품",      # 디어유
    "104480": "💄 화장품",      # 티앤엘
    "214150": "💄 화장품",      # 클리오
    # ══ 방산 ════════════════════════════════
    "012450": "🛡️ 방산",       # 한화에어로스페이스
    "272210": "🛡️ 방산",       # 한화시스템
    "079550": "🛡️ 방산",       # LIG넥스원
    "064350": "🛡️ 방산",       # 현대로템
    "077970": "🛡️ 방산",       # STX엔진
    "100840": "🛡️ 방산",       # SNT에너지
    "010140": "🛡️ 방산",       # 삼성중공업
    "047050": "🛡️ 방산",       # 포스코인터내셔널
    # ══ 조선/해운 ════════════════════════════
    "042660": "🚢 조선",        # 한화오션
    "329180": "🚢 조선",        # HD현대중공업
    "009540": "🚢 조선",        # HD한국조선해양
    "010620": "🚢 조선",        # HD현대미포
    "011200": "🚢 해운",        # HMM
    "005880": "🚢 해운",        # 대한해운
    "017960": "🚢 조선기자재",  # 한국카본
    "082740": "🚢 조선기자재",  # HSD엔진
    "000120": "📦 물류",        # CJ대한통운
    # ══ 자동차 ══════════════════════════════
    "005380": "🚗 자동차",      # 현대차
    "000270": "🚗 자동차",      # 기아
    "012330": "🚗 자동차부품",  # 현대모비스
    "204320": "🚗 자동차부품",  # HL만도
    "018880": "🚗 자동차부품",  # 한온시스템
    "241560": "🚗 자동차부품",  # 두산밥캣
    "060720": "🚗 자동차부품",  # KH바텍
    # ══ IT/인터넷/게임 ══════════════════════
    "035420": "🌐 인터넷",      # NAVER
    "035720": "🌐 인터넷",      # 카카오
    "036570": "🎮 게임",        # 엔씨소프트
    "251270": "🎮 게임",        # 넷마블
    "293490": "🎮 게임",        # 카카오게임즈
    "112040": "🎮 게임",        # 위메이드
    "095660": "🎮 게임",        # 네오위즈
    "263750": "🎮 게임",        # 펄어비스
    "078340": "🎮 게임",        # 컴투스
    "053800": "💻 소프트웨어",  # 안랩
    "030520": "💻 소프트웨어",  # 한글과컴퓨터
    "067160": "🎬 엔터",        # 아프리카TV
    # ══ 화학/소재/철강 ══════════════════════
    "051910": "🧪 화학",        # LG화학
    "011790": "🧪 화학",        # SKC
    "004000": "🧪 화학",        # 롯데정밀화학
    "009830": "🧪 화학",        # 한화솔루션
    "005490": "🔩 철강",        # POSCO홀딩스
    "004020": "🔩 철강",        # 현대제철
    "010130": "🔩 비철금속",    # 고려아연
    "298050": "🧪 화학",        # 효성첨단소재
    "006260": "⚡ 전기장비",    # LS
    "001430": "🔩 철강",        # 세아베스틸지주
    # ══ 에너지 ══════════════════════════════
    "096775": "⛽ 에너지",      # SK이노베이션
    "010950": "⛽ 정유",        # S-Oil
    "267250": "⛽ 에너지",      # HD현대
    "161390": "☀️ 태양광",      # 한국전력기술
    "036460": "💡 유틸리티",    # 한국가스공사
    "015760": "💡 유틸리티",    # 한국전력
    # ══ 금융 ════════════════════════════════
    "055550": "🏦 금융",        # 신한지주
    "105560": "🏦 금융",        # KB금융
    "086790": "🏦 금융",        # 하나금융지주
    "316140": "🏦 금융",        # 우리금융지주
    "024110": "🏦 금융",        # 기업은행
    "138930": "🏦 금융",        # BNK금융지주
    "000810": "🏦 보험",        # 삼성화재
    "032830": "🏦 보험",        # 삼성생명
    "003540": "🏦 보험",        # 대한생명
    "006800": "🏦 증권",        # 미래에셋증권
    "039490": "🏦 증권",        # 키움증권
    "016360": "🏦 증권",        # 삼성증권
    "071050": "🏦 증권",        # 한국금융지주
    # ══ 엔터/미디어 ══════════════════════════
    "041510": "🎬 엔터",        # SM엔터테인먼트
    "035900": "🎬 엔터",        # JYP Ent
    "352820": "🎬 엔터",        # 하이브
    "053210": "🎬 미디어",      # 스카이라이프
    "032540": "🎬 엔터",        # TJ미디어
    # ══ 건설 ════════════════════════════════
    "000720": "🏗️ 건설",       # 현대건설
    "047040": "🏗️ 건설",       # 대우건설
    "006360": "🏗️ 건설",       # GS건설
    "028260": "🏗️ 건설",       # 삼성물산
    "000210": "🏗️ 건설",       # DL
    "082640": "🏗️ 건설",       # 동양이엔씨
    # ══ 유통/식품 ════════════════════════════
    "023530": "🏬 유통",        # 롯데쇼핑
    "004170": "🏬 유통",        # 신세계
    "069960": "🏬 유통",        # 현대백화점
    "139480": "🍽️ 식품",       # 이마트
    "003230": "🍽️ 식품",       # 삼양식품
    "097950": "🍽️ 식품",       # CJ제일제당
    "271560": "🍽️ 식품",       # 오리온
    "007310": "🍽️ 식품",       # 오뚜기
    "004370": "🍽️ 식품",       # 농심
    # ══ 통신 ════════════════════════════════
    "017670": "📡 통신",        # SK텔레콤
    "030200": "📡 통신",        # KT
    "032640": "📡 통신",        # LG유플러스
    # ══ 항공 ════════════════════════════════
    "003490": "✈️ 항공",        # 대한항공
    "020560": "✈️ 항공",        # 아시아나항공
    "089590": "✈️ 항공",        # 제주항공
    "272450": "✈️ 항공",        # 진에어
    # ══ 기계/장비 ════════════════════════════
    "042670": "🏭 기계",        # HD현대인프라코어
    "011390": "🏭 기계",        # 부산산업
}


def _normalize_industry(name: str) -> str:
    """네이버 업종명 정규화(공백/특수문자 제거)"""
    if not name:
        return ""
    return (
        str(name)
        .replace(" ", "")
        .replace(",", "")
        .replace("·", "")
        .replace("/", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )


def _map_korean_industry(ind_name: str) -> str:
    """한국어 업종명 → 이모지 섹터. 매칭 실패 시 '📊 {원문}' 반환"""
    if not ind_name:
        return "-"
    norm = _normalize_industry(ind_name)
    # 정확 매칭
    if norm in SECTOR_KR_NAVER:
        return SECTOR_KR_NAVER[norm]
    # 부분 매칭 (contains)
    for key, label in SECTOR_KR_NAVER.items():
        if key in norm or norm in key:
            return label
    # 매칭 실패 → 원문 표시
    return f"📊 {ind_name.strip()}"


# ─────────────────────────────────────────
# 3. 섹터 & 시가총액 조회
# ─────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def _get_naver_stock_info(code: str):
    """
    ✅ 네이버 모바일 주식 API → 시가총액(원화 정확), 섹터
    응답 예시: marketValue(시가총액 원), industryCode, industryName
    """
    try:
        url = f"https://m.stock.naver.com/api/stock/{code}/basic"
        res = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer":    "https://m.stock.naver.com/",
            },
            timeout=8
        )
        if res.status_code != 200:
            return None
        return res.json()
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _get_naver_sector_detail(code: str):
    """
    ✅ 네이버금융 종목 상세 페이지에서 업종명 크롤링 (폴백)
    동일업종 비교 링크(sise_group_detail.naver?type=upjong)에서 업종명 추출
    """
    try:
        from bs4 import BeautifulSoup
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers=NAVER_HEADERS, timeout=8)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        # ① 동일업종 비교 테이블 상단의 업종 링크
        for a in soup.select("a[href*='sise_group_detail.naver']"):
            href = a.get("href", "")
            if "type=upjong" in href:
                txt = a.get_text(strip=True)
                if txt and 2 <= len(txt) <= 30:
                    return txt
        # ② description 영역
        desc = soup.select_one(".description")
        if desc:
            for a in desc.select("a"):
                href = a.get("href", "")
                if "upjong" in href:
                    txt = a.get_text(strip=True)
                    if txt and 2 <= len(txt) <= 30:
                        return txt
        return None
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def _get_krx_marcap(code: str, base_dt: str):
    """
    ✅ KRX 공식 API → 특정 날짜 시가총액 (단위: 백만원)
    data.krx.co.kr MDCSTAT01501 응답의 MKTCAP 필드 사용
    """
    for mkt_id in ["STK", "KSQ"]:
        try:
            payload = (
                f"bld=dbms%2FMDC%2FSTAT%2Fstandard%2FMDCSTAT01501"
                f"&locale=ko_KR&mktId={mkt_id}&trdDd={base_dt}"
                f"&share=1&money=1&csvxls_isNo=false"
            )
            res = requests.post(
                "http://data.krx.co.kr/comm/bfebas/MDCSTAT01501.cmd",
                data=payload, headers=KRX_HEADERS, timeout=15
            )
            if res.status_code != 200:
                continue
            items = res.json().get("OutBlock_1") or []
            for item in items:
                c = str(item.get("ISU_SRT_CD", "")).strip()
                if c == code:
                    mc_raw = str(item.get("MKTCAP", "0")).replace(",", "")
                    mc_million = int(float(mc_raw)) if mc_raw else 0
                    return mc_million * 1_000_000  # 원 단위
        except Exception:
            continue
    return 0


@st.cache_data(ttl=1800, show_spinner=False)
def _get_krx_all_stocks(base_dt: str):
    """
    ✅ KRX MDCSTAT01501 API → 특정 날짜의 전종목 시세 일괄 조회
    반환: [{stk_cd, stk_nm, cur_prc, flu_rt, _money_eok, _marcap_won, pred_pre_sig, _source}]
    
    ※ 과거 날짜의 정확한 등락률·거래대금·시가총액을 한 번에 취득
    """
    all_rows = []
    for mkt_id in ["STK", "KSQ"]:
        try:
            payload = (
                f"bld=dbms%2FMDC%2FSTAT%2Fstandard%2FMDCSTAT01501"
                f"&locale=ko_KR&mktId={mkt_id}&trdDd={base_dt}"
                f"&share=1&money=1&csvxls_isNo=false"
            )
            res = requests.post(
                "http://data.krx.co.kr/comm/bfebas/MDCSTAT01501.cmd",
                data=payload, headers=KRX_HEADERS, timeout=25
            )
            if res.status_code != 200:
                continue
            items = res.json().get("OutBlock_1") or []
            for item in items:
                try:
                    code = str(item.get("ISU_SRT_CD", "")).strip()
                    if not code or len(code) != 6:
                        continue
                    name = str(item.get("ISU_ABBRV", "")).strip()

                    # 종가
                    close_raw = str(item.get("TDD_CLSPRC", "0")).replace(",", "")
                    close = int(float(close_raw)) if close_raw else 0
                    if close == 0:
                        continue  # 정지/상장폐지 등 skip

                    # 등락률
                    rate_raw = str(item.get("FLUC_RT", "0")).replace(",", "")
                    rate = float(rate_raw) if rate_raw else 0.0

                    # 거래대금(원) → 억 단위
                    money_raw = str(item.get("ACC_TRDVAL", "0")).replace(",", "")
                    money_won = int(float(money_raw)) if money_raw else 0
                    money_eok = money_won // 100_000_000

                    # 시가총액(백만원) → 원
                    marcap_raw = str(item.get("MKTCAP", "0")).replace(",", "")
                    marcap_million = int(float(marcap_raw)) if marcap_raw else 0
                    marcap_won = marcap_million * 1_000_000

                    # 전일대비 부호
                    cmpprev = str(item.get("CMPPREVDD_PRC", "0")).replace(",", "")
                    pred_pre_sig = ""
                    try:
                        cmpprev_val = float(cmpprev)
                        if cmpprev_val > 0:
                            pred_pre_sig = "+"
                        elif cmpprev_val < 0:
                            pred_pre_sig = "-"
                    except Exception:
                        pass

                    all_rows.append({
                        "stk_cd":        code,
                        "stk_nm":        name,
                        "cur_prc":       str(close),
                        "flu_rt":        str(rate),
                        "pred_pre_sig":  pred_pre_sig,
                        "now_trde_qty":  "0",
                        "_money_eok":    money_eok,
                        "_marcap_won":   marcap_won,
                        "_source":       "krx",
                    })
                except Exception:
                    continue
            time.sleep(0.3)  # KRX rate-limit 회피
        except Exception:
            continue
    return all_rows


def _fmt_marcap(won: int):
    """원 단위 시가총액 → '몇조 몇억' 표시"""
    if won <= 0:
        return "-", 0
    eok = won / 1e8
    if eok >= 10000:
        return f"{eok / 10000:.2f}조", int(eok)
    return f"{int(eok):,}억", int(eok)


@st.cache_data(ttl=1800, show_spinner=False)
def get_sector_and_marcap(code: str, token: str = "", base_dt: str = ""):
    """
    섹터 & 시가총액 조회 (개선됨)
    - 섹터: MANUAL_SECTOR → 네이버 모바일 API(한국어 업종) → 네이버 상세페이지 → yfinance
    - 시가총액: 네이버 모바일 API(최신) → KRX(날짜별) → 키움 API → yfinance
    ※ 호출자에서 _marcap_won이 있으면 별도 덮어씀 (과거 날짜 정확성 보장)
    """
    sector     = MANUAL_SECTOR.get(code, None)
    marcap_str = "-"
    marcap_num = 0   # 억 단위

    # ══ 1순위: 네이버 모바일 API (원화, 빠름) ══════════
    nv_ind = ""
    try:
        nv = _get_naver_stock_info(code)
        if nv:
            # 시가총액
            mv = nv.get("marketValue") or nv.get("marketCap") or 0
            try:
                mv = int(str(mv).replace(",", ""))
            except Exception:
                mv = 0
            if mv > 0:
                marcap_str, marcap_num = _fmt_marcap(mv)

            # 섹터: industryName (한국어)
            nv_ind = (
                nv.get("industryName") or
                nv.get("industry")     or
                nv.get("업종")         or ""
            )
            if sector is None and nv_ind:
                sector = _map_korean_industry(nv_ind)
    except Exception:
        pass

    # ══ 2순위: KRX 직접 API (날짜별 정확한 시가총액) ═════════
    if marcap_str == "-" and base_dt:
        try:
            mv = _get_krx_marcap(code, base_dt)
            if mv > 0:
                marcap_str, marcap_num = _fmt_marcap(mv)
        except Exception:
            pass

    # ══ 3순위: 키움 ka10001 API ══════════════════════════════
    if marcap_str == "-" and token:
        try:
            res = requests.post(
                f"{BASE_URL}/api/dostk/stkinfo",
                json={"stk_cd": code},
                headers={
                    "Content-Type":  "application/json;charset=UTF-8",
                    "Authorization": f"Bearer {token}",
                    "api-id":        "ka10001",
                },
                timeout=8
            )
            data = res.json()
            # 키움 ka10001: 시가총액 단위는 억원
            raw = (
                data.get("mrkt_cap")    or
                data.get("tot_mktcap")  or
                data.get("stk_cap")     or
                data.get("mktcap")      or
                data.get("cap")         or ""
            )
            if raw and str(raw).strip() not in ["", "0", "0.0"]:
                raw_clean = str(raw).replace(",", "").replace("+", "").strip()
                eok = int(float(raw_clean))
                if eok > 0:
                    marcap_num = eok
                    if eok >= 10000:
                        marcap_str = f"{eok / 10000:.2f}조"
                    else:
                        marcap_str = f"{eok:,}억"
        except Exception:
            pass

    # ══ 4순위: 네이버 상세페이지 크롤링 (섹터 폴백) ═════════
    if sector is None:
        try:
            det_ind = _get_naver_sector_detail(code)
            if det_ind:
                sector = _map_korean_industry(det_ind)
        except Exception:
            pass

    # ══ 5순위: yfinance (섹터/시가총액 최종 폴백) ════════════
    if YF_AVAILABLE and (sector is None or marcap_str == "-"):
        for suffix in [".KS", ".KQ"]:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    info = yf.Ticker(f"{code}{suffix}").info
                if not info or info.get("regularMarketPrice") is None:
                    continue
                if marcap_str == "-":
                    mc = info.get("marketCap", 0)
                    currency = info.get("currency", "")
                    if mc and mc > 0 and currency == "KRW":
                        marcap_str, marcap_num = _fmt_marcap(mc)
                if sector is None:
                    raw_i = info.get("industry", "")
                    raw_s = info.get("sector",   "")
                    sector = (
                        SECTOR_KR.get(raw_i, None) or
                        SECTOR_KR.get(raw_s, None) or
                        (f"📊 {raw_s}" if raw_s else None)
                    )
                break
            except Exception:
                continue

    return (sector or "-"), marcap_str, marcap_num


# ─────────────────────────────────────────
# 4. RSI & OBV 골든크로스 감지
# ─────────────────────────────────────────
def detect_golden_cross(df: pd.DataFrame):
    if len(df) < 30:
        return False, 0.0, 0.0, 0, 0

    df = df.copy().reset_index(drop=True)

    diff             = df["close"].diff()
    u                = diff.clip(lower=0)
    d                = diff.clip(upper=0).abs()
    rs               = u.rolling(14).mean() / (d.rolling(14).mean() + 1e-9)
    df["rsi"]        = 100 - (100 / (1 + rs))
    df["rsi_signal"] = df["rsi"].rolling(9).mean()

    direction        = (df["close"] > df["close"].shift(1)).astype(int) * 2 - 1
    df["obv"]        = (df["vol"] * direction).fillna(0).cumsum()
    df["obv_signal"] = df["obv"].rolling(9).mean()

    df = df.dropna(
        subset=["rsi", "rsi_signal", "obv", "obv_signal"]
    ).reset_index(drop=True)

    if len(df) < 5:
        return False, 0.0, 0.0, 0, 0

    rsi_now = float(df["rsi"].iloc[-1])
    obv_now = float(df["obv"].iloc[-1])

    if not (rsi_now > float(df["rsi_signal"].iloc[-1]) and
            obv_now > float(df["obv_signal"].iloc[-1])):
        return False, rsi_now, obv_now, 0, 0

    def find_cross(val_col, sig_col):
        for j in range(1, len(df)):
            ic = len(df) - j
            ip = ic - 1
            if ip < 0:
                break
            if not (df[val_col].iloc[ic] > df[sig_col].iloc[ic]):
                break
            if df[val_col].iloc[ip] <= df[sig_col].iloc[ip]:
                return j - 1, True
        return 0, False

    rsi_ago, rsi_ok = find_cross("rsi", "rsi_signal")
    obv_ago, obv_ok = find_cross("obv", "obv_signal")

    return (rsi_ok and obv_ok), round(rsi_now, 1), round(obv_now, 0), rsi_ago, obv_ago

# ─────────────────────────────────────────
# 5. 일봉 데이터 수집
# ─────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_daily_df_kiwoom(token, code, base_dt):
    for api_id in ["ka10081", "ka10005"]:
        try:
            res = requests.post(
                f"{BASE_URL}/api/dostk/chart",
                json={
                    "stk_cd":        code,
                    "base_dt":       base_dt,
                    "upd_stkprc_tp": "1",
                },
                headers={
                    "Content-Type":  "application/json;charset=UTF-8",
                    "Authorization": f"Bearer {token}",
                    "api-id":        api_id,
                },
                timeout=10
            )
            data = res.json()
            rows = (
                data.get("stk_dt_pole_chart_qry") or
                data.get("output1") or
                data.get("output") or []
            )
            if len(rows) >= 20:
                df        = pd.DataFrame(rows)
                close_col = next(
                    (c for c in ["stck_clpr", "close", "cls_prc"] if c in df.columns), None
                )
                vol_col = next(
                    (c for c in ["acml_vol", "vol", "trde_qty"] if c in df.columns), None
                )
                date_col = next(
                    (c for c in ["stck_bsop_date", "dt", "date", "bas_dt", "trd_dt"] if c in df.columns), None
                )
                if close_col and vol_col:
                    df["close"] = pd.to_numeric(df[close_col], errors="coerce")
                    df["vol"]   = pd.to_numeric(df[vol_col],   errors="coerce")
                    df = df.dropna(subset=["close", "vol"])
                    if date_col:
                        df["_dt"] = df[date_col].astype(str).str.replace("-", "").str[:8]
                        df = df[df["_dt"] <= base_dt]
                        df = df.drop(columns=["_dt"])
                    if len(df) < 20:
                        continue
                    return (
                        df.iloc[::-1]
                        .reset_index(drop=True)[["close", "vol"]]
                    )
        except Exception:
            continue
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_daily_df_yfinance(code, base_dt):
    """
    ✅ base_dt 기준으로 과거 데이터 조회 (base_dt 포함, 이후 데이터 제거)
    base_dt: "YYYYMMDD" 형식
    """
    if not YF_AVAILABLE:
        return None

    try:
        end_dt    = datetime.strptime(base_dt, "%Y%m%d")
        start_dt  = end_dt - pd.Timedelta(days=180)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str   = (end_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        start_str = None
        end_str   = None

    for suffix in [".KS", ".KQ"]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ticker = yf.Ticker(f"{code}{suffix}")
                if start_str and end_str:
                    df = ticker.history(
                        start=start_str,
                        end=end_str,
                        auto_adjust=True,
                        repair=False,
                    )
                else:
                    df = ticker.history(
                        period="6mo",
                        auto_adjust=True,
                        repair=False,
                    )
            if df is None or len(df) < 20:
                continue

            df.index = pd.to_datetime(df.index).tz_localize(None)
            cutoff   = pd.Timestamp(end_dt)
            df       = df[df.index <= cutoff]

            if len(df) < 20:
                continue

            return (
                df.rename(columns={"Close": "close", "Volume": "vol"})
                [["close", "vol"]]
                .dropna()
                .reset_index(drop=True)
            )
        except Exception:
            continue
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_ohlcv_naver(code, base_dt):
    """
    ✅ 네이버금융 일봉 차트 API로 날짜 기준 데이터 조회
    """
    try:
        # ① fchart API (XML)
        url = (
            f"https://fchart.stock.naver.com/sise.nhn"
            f"?symbol={code}&timeframe=day&count=200&requestType=0"
        )
        res = requests.get(url, headers=NAVER_HEADERS, timeout=10)
        if res.status_code == 200 and "<item" in res.text:
            import re
            records = []
            for m in re.finditer(r'data="([^"]+)"', res.text):
                parts = m.group(1).split("|")
                if len(parts) < 6:
                    continue
                dt_str = parts[0].strip()[:8]
                if dt_str > base_dt:
                    continue
                try:
                    close = float(parts[4])
                    vol   = float(parts[5])
                    records.append({"close": close, "vol": vol})
                except Exception:
                    continue
            if len(records) >= 20:
                return pd.DataFrame(records)

        # ② siseJson fallback
        end_dt   = datetime.strptime(base_dt, "%Y%m%d")
        start_dt = end_dt - timedelta(days=200)
        url2 = (
            f"https://api.finance.naver.com/siseJson.naver"
            f"?symbol={code}"
            f"&requestType=1"
            f"&startTime={start_dt.strftime('%Y%m%d')}"
            f"&endTime={base_dt}"
            f"&timeframe=day"
        )
        res2 = requests.get(url2, headers=NAVER_HEADERS, timeout=10)
        if res2.status_code != 200:
            return None

        import json
        text = res2.text.strip()
        if not text or text in ["[]", "null", ""]:
            return None

        raw = json.loads(text)
        if not isinstance(raw, list) or len(raw) < 2:
            return None

        headers_row = raw[0]
        data_rows   = raw[1:]
        h = [str(x) for x in headers_row]

        close_idx = next((i for i, c in enumerate(h) if "종가" in c or "Close" in c), None)
        vol_idx   = next((i for i, c in enumerate(h) if "거래량" in c or "Volume" in c), None)
        date_idx  = next((i for i, c in enumerate(h) if "날짜" in c or "Date" in c), 0)

        if close_idx is None or vol_idx is None:
            return None

        records = []
        for row in data_rows:
            try:
                if not isinstance(row, list) or len(row) <= max(close_idx, vol_idx):
                    continue
                dt_str = str(row[date_idx]).replace(".", "").replace("-", "")[:8]
                if dt_str > base_dt:
                    continue
                close_val = row[close_idx]
                vol_val   = row[vol_idx]
                if close_val is None or vol_val is None:
                    continue
                close = float(str(close_val).replace(",", ""))
                vol   = float(str(vol_val).replace(",", ""))
                records.append({"close": close, "vol": vol})
            except Exception:
                continue

        if len(records) < 20:
            return None
        return pd.DataFrame(records)

    except Exception:
        return None


def get_ohlcv(token, code, base_dt):
    """✅ base_dt 기준 일봉 조회 (네이버 → 키움 → yfinance)"""
    df = get_ohlcv_naver(code, base_dt)
    if df is not None and len(df) >= 20:
        return df
    df = get_daily_df_kiwoom(token, code, base_dt)
    if df is not None and len(df) >= 20:
        return df
    return get_daily_df_yfinance(code, base_dt)

# ─────────────────────────────────────────
# 6. 토큰 / 랭킹 API
# ─────────────────────────────────────────
def get_access_token():
    try:
        res = requests.post(
            f"{BASE_URL}/oauth2/token",
            json={
                "grant_type": "client_credentials",
                "appkey":     API_KEY,
                "secretkey":  SECRET_KEY,
            },
            headers={"Content-Type": "application/json;charset=UTF-8"},
            timeout=10
        )
        data = res.json()
        if res.status_code == 200:
            token = data.get("token") or data.get("access_token")
            return (token, None) if token else (None, f"토큰 키 없음: {data}")
        return None, f"HTTP {res.status_code} | {data}"
    except requests.exceptions.Timeout:
        return None, "요청 시간 초과 (10s)"
    except Exception as e:
        return None, str(e)


def _parse_naver_sise_page(sosok, page, base_dt, headers):
    """네이버금융 등락률 상위(sise_rise) 페이지 파싱"""
    from bs4 import BeautifulSoup
    url = (
        f"https://finance.naver.com/sise/sise_rise.naver"
        f"?sosok={sosok}&page={page}"
    )
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return [], False
        soup  = BeautifulSoup(res.text, "html.parser")
        table = soup.select_one("table.type_2")
        if not table:
            return [], False

        rows = []
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) < 10:
                continue
            try:
                name_tag = tds[1].select_one("a")
                if not name_tag:
                    continue
                name  = name_tag.text.strip()
                href  = name_tag.get("href", "")
                code_ = href.split("code=")[-1].strip() if "code=" in href else ""
                if not code_ or len(code_) != 6:
                    continue

                cur_prc_txt = tds[2].text.strip().replace(",", "")
                cur_prc = int(cur_prc_txt) if cur_prc_txt.lstrip("-").isdigit() else 0

                rate_txt = (
                    tds[4].text.strip()
                    .replace(",", "").replace("+", "")
                    .replace("%", "").replace(" ", "")
                )
                try:
                    rate = float(rate_txt)
                except Exception:
                    rate = 0.0

                rows.append({
                    "stk_cd":       code_,
                    "stk_nm":       name,
                    "flu_rt":       str(rate),
                    "cur_prc":      str(cur_prc),
                    "now_trde_qty": "0",
                    "_money_eok":   0,
                    "_source":      "naver",
                })
            except Exception:
                continue

        has_next = soup.select_one("a.pgR") is not None and len(rows) > 0
        return rows, has_next
    except Exception:
        return [], False


def _fetch_naver_quant_page(sosok, page, headers):
    """네이버금융 거래대금 상위(sise_quant) 페이지 파싱"""
    from bs4 import BeautifulSoup
    url = (
        f"https://finance.naver.com/sise/sise_quant.naver"
        f"?sosok={sosok}&page={page}"
    )
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return {}
        soup  = BeautifulSoup(res.text, "html.parser")
        table = soup.select_one("table.type_2")
        if not table:
            return {}

        result = {}
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) < 10:
                continue
            try:
                name_tag = tds[1].select_one("a")
                if not name_tag:
                    continue
                href  = name_tag.get("href", "")
                code_ = href.split("code=")[-1].strip() if "code=" in href else ""
                if not code_ or len(code_) != 6:
                    continue
                amt_txt       = tds[6].text.strip().replace(",", "")
                money_million = int(amt_txt) if amt_txt.lstrip("-").isdigit() else 0
                result[code_] = money_million // 100  # 백만 → 억
            except Exception:
                continue
        return result
    except Exception:
        return {}


def get_market_ranking(token, base_dt):
    """
    ✅ 날짜별 전종목 등락률·거래대금·시가총액 조회
    
    - 과거 날짜 (1순위): KRX MDCSTAT01501 API (날짜별 정확한 데이터)
                   ※ 4/17, 4/16 등 각 거래일별 고유 데이터 보장
    - 오늘 (1순위): 네이버금융 sise_rise + sise_quant (실시간)
    - 최종 폴백: 키움 ka10027 REST API
    """
    today_str = datetime.today().strftime("%Y%m%d")
    is_today  = (base_dt == today_str)

    # ──────────────────────────────────────────
    # 과거 날짜 → KRX API 최우선 (날짜별 정확)
    # ──────────────────────────────────────────
    if not is_today:
        try:
            st.info(f"📅 과거 날짜({base_dt}) → KRX 공식 API 조회 중...")
            rows = _get_krx_all_stocks(base_dt)
            if rows:
                st.session_state["last_ranking_response"] = {
                    "source":         "krx",
                    "requested_date": base_dt,
                    "count":          len(rows),
                }
                st.success(f"✅ KRX {base_dt} 전종목 {len(rows)}개 수신")
                return rows, None
            else:
                st.warning(f"⚠️ KRX {base_dt} 데이터 없음 (주말/공휴일 가능) → 키움 API fallback")
        except Exception as e:
            st.warning(f"⚠️ KRX 오류: {e} → 키움 API fallback")

    # ──────────────────────────────────────────
    # 오늘 → 네이버금융 스크래핑
    # ──────────────────────────────────────────
    if is_today:
        try:
            quant_map = {}
            rows      = []

            # ① 거래대금 수집
            for sosok in ["0", "1"]:
                for pg in range(1, 6):
                    chunk = _fetch_naver_quant_page(sosok, pg, NAVER_HEADERS)
                    if not chunk:
                        break
                    quant_map.update(chunk)
                    time.sleep(0.05)

            # ② 등락률 수집
            for sosok in ["0", "1"]:
                page = 1
                while page <= 10:
                    chunk, has_next = _parse_naver_sise_page(
                        sosok, page, base_dt, NAVER_HEADERS
                    )
                    for r in chunk:
                        r["_money_eok"] = quant_map.get(r["stk_cd"], 0)
                        rows.append(r)
                    if not has_next:
                        break
                    page += 1
                    time.sleep(0.05)

            if rows:
                st.session_state["last_ranking_response"] = {
                    "source":         "naver",
                    "requested_date": base_dt,
                    "count":          len(rows),
                }
                return rows, None
            else:
                st.warning("⚠️ 네이버금융 파싱 결과 없음 → KRX/키움 API fallback")
                # 오늘도 KRX 시도
                try:
                    rows = _get_krx_all_stocks(base_dt)
                    if rows:
                        return rows, None
                except Exception:
                    pass
        except Exception as e:
            st.warning(f"⚠️ 네이버금융 오류: {e} → 키움 API fallback")

    # ──────────────────────────────────────────
    # 최종 폴백: 키움 ka10027
    # ──────────────────────────────────────────
    try:
        res = requests.post(
            f"{BASE_URL}/api/dostk/rkinfo",
            json={
                "sort_tp":        "1",
                "mrkt_tp":        "0",
                "flu_pl_sign":    "2",
                "flu_strt_rate":  "0",
                "flu_end_rate":   "0",
                "trde_qty_cnd":   "0000",
                "stk_cnd":        "0",
                "crd_cnd":        "0",
                "pric_cnd":       "0",
                "trde_prica_cnd": "0",
                "updown_incls":   "1",
                "stex_tp":        "1",
                "base_dt":        base_dt,
            },
            headers={
                "Content-Type":  "application/json;charset=UTF-8",
                "Authorization": f"Bearer {token}",
                "api-id":        "ka10027",
            },
            timeout=15
        )
        data = res.json()
        st.session_state["last_ranking_response"] = data
        if res.status_code == 200:
            rows = (
                data.get("pred_pre_flu_rt_upper") or
                data.get("item_inq_rank")          or
                data.get("output1")                or
                data.get("output")                 or []
            )
            return rows, None
        return [], f"HTTP {res.status_code} | {data}"
    except Exception as e:
        return [], str(e)


# ─────────────────────────────────────────
# 7. 메인 실행
# ─────────────────────────────────────────
st.title("🏹 키움증권 실전투자 통합 스캐너")
st.caption("RSI(14) & OBV 골든크로스 + 섹터 + 시가총액 통합 분석")
st.info("📡 **데이터 소스**: 네이버금융(오늘) + KRX(과거 날짜별 정확) + 키움 API(차트·인증)")

# ✅ API 키 설정 상태 표시
if API_KEY == "여기에_APP_KEY_입력" or SECRET_KEY == "여기에_SECRET_KEY_입력":
    st.error("⚠️ 코드 상단의 `API_KEY` 와 `SECRET_KEY` 를 실제 값으로 변경하세요!")
    st.code("""
API_KEY    = "실제_APP_KEY_입력"
SECRET_KEY = "실제_SECRET_KEY_입력"
    """)
    st.stop()
else:
    st.sidebar.success("✅ API 키 설정 완료")


col1, col2 = st.columns([1, 3])
with col1:
    test_btn = st.button("🔌 연결 테스트")
with col2:
    scan_btn = st.button("🚀 스캔 시작")


# ── 연결 테스트 ──────────────────────────
if test_btn:
    with st.spinner("토큰 발급 중..."):
        token, err = get_access_token()
    if not token:
        st.error(f"❌ 인증 실패: {err}")
    else:
        st.success(f"✅ 인증 성공! `{token[:20]}...`")
        with st.spinner("랭킹 API 확인 중..."):
            rows, err2 = get_market_ranking(token, formatted_date)
        resp = st.session_state.get("last_ranking_response", {})
        st.subheader("📦 API 응답")
        st.caption(f"응답 키: `{list(resp.keys())}`")
        st.json(resp)
        if rows:
            st.success(f"📊 {len(rows)}건 수신")
            st.caption(f"필드명: `{list(rows[0].keys())}`")
            date_keys = ["dt", "date", "bas_dt", "trd_dt", "stk_bsop_date", "base_dt"]
            found_dates = {k: rows[0].get(k) for k in date_keys if k in rows[0]}
            if found_dates:
                st.info(f"📅 날짜 필드 확인: `{found_dates}` (조회요청: `{formatted_date}`)")
            st.json(rows[:2])
        else:
            st.error(f"랭킹 API 오류: {err2}")


# ── 스캔 시작 ────────────────────────────
if scan_btn:
    with st.status("분석 중...", expanded=True) as status:

        # ✅ 날짜 변경 시 캐시 초기화
        if st.session_state.get("cached_date") != formatted_date:
            st.session_state["cached_date"] = formatted_date
            get_sector_and_marcap.clear()
            _get_naver_stock_info.clear()
            _get_naver_sector_detail.clear()
            _get_krx_marcap.clear()
            _get_krx_all_stocks.clear()
            get_daily_df_kiwoom.clear()
            get_daily_df_yfinance.clear()
            get_ohlcv_naver.clear()

        token, err = get_access_token()
        if not token:
            status.update(label="인증 실패", state="error")
            st.error(f"인증 실패: {err}")
            st.stop()

        st.write(f"✅ 인증 성공! 조회 날짜: **{formatted_date}**")

        stocks, err2 = get_market_ranking(token, formatted_date)
        if not stocks:
            status.update(label="데이터 없음", state="error")
            st.error("랭킹 데이터를 가져오지 못했습니다.")
            with st.expander("🔍 서버 응답 확인"):
                st.json(st.session_state.get("last_ranking_response", {}))
            st.stop()

        st.write(f"📊 **{len(stocks)}개** 종목 분석 시작")

        progress_bar  = st.progress(0)
        final_results = []
        sample        = stocks[0] if stocks else {}

        # ✅ 성능 개선: 10% 이상 상승 + 거래대금 200억 이상인 종목만 골라서 처리
        #   (KRX는 전종목 ~2500개 반환하므로 사전 필터링 필수)
        pre_filtered = []
        for s in stocks:
            try:
                rate_raw = (
                    s.get("flu_rt")         or
                    s.get("base_comp_chgr") or
                    s.get("prdy_ctrt")      or "0"
                )
                rate = float(
                    str(rate_raw).replace("%", "").replace("+", "").replace(",", "")
                )
                if f_rising and rate < 10.0:
                    continue

                # 거래대금 사전 필터
                if s.get("_source") in ("naver", "pykrx", "krx"):
                    money = int(s.get("_money_eok", 0))
                else:
                    cur_prc_raw = s.get("cur_prc") or "0"
                    cur_prc_tmp = abs(int(str(cur_prc_raw).replace(",", "").replace("+", "").replace("-", ""))) if cur_prc_raw else 0
                    trde_qty_raw = s.get("now_trde_qty") or "0"
                    trde_qty = int(str(trde_qty_raw).replace(",", "")) if trde_qty_raw else 0
                    money = int((cur_prc_tmp * trde_qty) / 100_000_000)

                if f_money and money < 200:
                    continue

                s["_rate"]  = rate
                s["_money"] = money
                pre_filtered.append(s)
            except Exception:
                continue

        st.write(f"🎯 사전 필터 통과: **{len(pre_filtered)}개** (등락률·거래대금)")

        for i, s in enumerate(pre_filtered):
            progress_bar.progress((i + 1) / max(len(pre_filtered), 1))
            try:
                rate = s["_rate"]
                money = s["_money"]

                code = (
                    s.get("stk_cd")   or
                    s.get("isu_cd")   or
                    s.get("stk_code") or ""
                )
                if not code:
                    continue

                cur_prc_raw = s.get("cur_prc") or "0"
                cur_prc = abs(int(
                    str(cur_prc_raw).replace(",", "").replace("+", "").replace("-", "")
                )) if cur_prc_raw else 0

                sector, marcap_str, marcap_num = get_sector_and_marcap(code, token, formatted_date)

                # ✅ KRX에서 받은 정확한 날짜별 시가총액이 있으면 덮어쓰기 (과거 날짜 정확성)
                prefetched = s.get("_marcap_won", 0)
                if prefetched > 0:
                    marcap_str, marcap_num = _fmt_marcap(prefetched)

                rsi_display = obv_display = "-"
                rsi_ago_str = obv_ago_str = "-"
                is_sig      = False

                df_ohlcv = get_ohlcv(token, code, formatted_date)
                if df_ohlcv is not None and len(df_ohlcv) >= 20:
                    is_sig, rsi_v, obv_v, rsi_ago, obv_ago = detect_golden_cross(df_ohlcv)
                    rsi_display = f"{rsi_v:.1f}"
                    obv_display = f"{obv_v:,.0f}"
                    rsi_ago_str = f"{rsi_ago}봉 전" if rsi_ago > 0 else "현재봉"
                    obv_ago_str = f"{obv_ago}봉 전" if obv_ago > 0 else "현재봉"

                if f_signal and not is_sig:
                    continue

                pred_pre_sig = s.get("pred_pre_sig", "")
                prc_display  = f"{pred_pre_sig}{cur_prc:,}" if cur_prc else "-"

                final_results.append({
                    "신호":          "🔴▲" if is_sig else "⬜",
                    "섹터":          sector,
                    "종목명":        s.get("stk_nm") or "-",
                    "코드":          code,
                    "현재가":        prc_display,
                    "등락률":        f"{rate:+.2f}%",
                    "거래대금(억)":  money,
                    "시가총액":      marcap_str,
                    "RSI":           rsi_display,
                    "RSI크로스":     rsi_ago_str,
                    "OBV":           obv_display,
                    "OBV크로스":     obv_ago_str,
                })

                time.sleep(0.03)

            except Exception:
                continue

        progress_bar.empty()

        if final_results:
            status.update(
                label=f"✅ {formatted_date} 기준 {len(final_results)}개 종목 발견",
                state="complete"
            )
            df_res    = pd.DataFrame(final_results)
            money_num = pd.to_numeric(
                df_res["거래대금(억)"], errors="coerce"
            ).fillna(0)
            df_display = df_res.copy()
            df_display["거래대금(억)"] = money_num.apply(
                lambda x: f"{int(x):,}"
            )

            # ✅ 섹터 커버리지 체크
            sector_filled = (df_display["섹터"] != "-").sum()
            sector_coverage = sector_filled / len(df_display) * 100 if len(df_display) else 0
            st.metric(
                "🎯 섹터 매칭률",
                f"{sector_coverage:.1f}%",
                f"{sector_filled}/{len(df_display)}개 종목"
            )

            def bg_color(row):
                is_sig_row   = "🔴▲" in str(row.get("신호", ""))
                is_big_money = money_num.iloc[row.name] >= 500
                if is_sig_row and is_big_money:
                    return ["background-color:#FF6B6B; font-weight:bold"] * len(row)
                elif is_sig_row:
                    return ["background-color:#FFD6E0"] * len(row)
                elif is_big_money:
                    return ["background-color:#FFF3CD"] * len(row)
                return [""] * len(row)

            st.subheader(f"📊 [{formatted_date}] 섹터별 종목 분포")
            sector_counts = (
                df_display["섹터"]
                .value_counts()
                .reset_index()
            )
            sector_counts.columns = ["섹터", "종목수"]
            st.dataframe(
                sector_counts,
                use_container_width=True,
                hide_index=True
            )
            st.divider()
            st.subheader(f"📋 [{formatted_date}] 전체 스캔 결과")
            st.dataframe(
                df_display.style.apply(bg_color, axis=1),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("""
| 색상 | 의미 |
|------|------|
| 🔴 진분홍+굵게 | 매수신호 + 거래대금 500억↑ **(최우선 주목)** |
| 🌸 연분홍 | 매수신호 (RSI & OBV 골든크로스 유지) |
| 🟡 노랑 | 거래대금 500억↑ 주도주 (신호 미발생) |
""")

            # ═══════════════════════════════════════════════
            # ✅ 노션 복사용 출력 (TSV + 마크다운)
            # ═══════════════════════════════════════════════
            st.divider()
            st.subheader("📋 노션(Notion) 복사용")

            # (1) TSV 형식 — 노션에 붙여넣으면 자동으로 테이블 블록 변환
            tsv_cols = [
                "신호", "섹터", "종목명", "코드", "현재가", "등락률",
                "거래대금(억)", "시가총액", "RSI", "RSI크로스", "OBV", "OBV크로스"
            ]
            tsv_header = "\t".join(tsv_cols)
            tsv_lines  = [tsv_header]
            for r in final_results:
                tsv_lines.append("\t".join([
                    str(r["신호"]),
                    str(r["섹터"]),
                    str(r["종목명"]),
                    str(r["코드"]),
                    str(r["현재가"]),
                    str(r["등락률"]),
                    f"{int(r['거래대금(억)']):,}",
                    str(r["시가총액"]),
                    str(r["RSI"]),
                    str(r["RSI크로스"]),
                    str(r["OBV"]),
                    str(r["OBV크로스"]),
                ]))
            tsv_output = "\n".join(tsv_lines)

            # (2) 마크다운 테이블
            md_header = "| " + " | ".join(tsv_cols) + " |"
            md_sep    = "|" + "|".join(["---"] * len(tsv_cols)) + "|"
            md_lines  = [md_header, md_sep]
            for r in final_results:
                md_lines.append("| " + " | ".join([
                    str(r["신호"]),
                    str(r["섹터"]),
                    str(r["종목명"]),
                    str(r["코드"]),
                    str(r["현재가"]),
                    str(r["등락률"]),
                    f"{int(r['거래대금(억)']):,}",
                    str(r["시가총액"]),
                    str(r["RSI"]),
                    str(r["RSI크로스"]),
                    str(r["OBV"]),
                    str(r["OBV크로스"]),
                ]) + " |")
            md_output = "\n".join(md_lines)

            tab1, tab2 = st.tabs(["🟢 TSV (노션 자동 테이블)", "🔵 마크다운 테이블"])

            with tab1:
                st.caption(
                    "📌 사용법: 아래 박스 오른쪽 **복사 버튼** 클릭 → 노션 페이지에 붙여넣기 "
                    "→ 노션이 자동으로 테이블 블록으로 변환합니다."
                )
                st.code(tsv_output, language="text")

            with tab2:
                st.caption(
                    "📌 사용법: 아래 박스 오른쪽 **복사 버튼** 클릭 → 노션의 `/코드` 블록 또는 "
                    "마크다운 지원 에디터에 붙여넣기."
                )
                st.code(md_output, language="markdown")

            # (3) CSV 다운로드 버튼 (보너스)
            csv_buffer = df_display.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="💾 CSV 다운로드",
                data=csv_buffer,
                file_name=f"kiwoom_scan_{formatted_date}.csv",
                mime="text/csv",
            )

        else:
            status.update(label="조건 만족 종목 없음", state="error")
            if sample:
                st.warning(f"📋 API 필드명: `{list(sample.keys())}`")
            st.info("필터를 완화하거나 날짜를 조정해 보세요.")
