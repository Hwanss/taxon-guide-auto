import os
import json
import warnings
import gspread
import re
from google.oauth2.service_account import Credentials
import google.generativeai as genai

warnings.filterwarnings("ignore", category=FutureWarning)

# API 및 구글 시트 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)

print("="*60)
print("🧠 [TaxonGuru] 제미나이 신규 블로그 주제 기획 공장 가동")
print("="*60)

try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    worksheet = gc.open_by_key(sheet_id).sheet1
except Exception as e:
    print(f"❌ 구글 시트 연결 실패: {e}")
    exit(1)

# 제미나이에게 주제 기획 요청 (대표님 블로그 카테고리 맞춤형)
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = """
너는 대한민국에서 가장 감각적이고 유쾌한 블로그 콘텐츠 디렉터야.
우리 블로그에 새로 추가할 '조회수 폭발할 만한' 신선하고 흥미로운 포스팅 주제를 기획해줘.

[기획 조건]
1. 아래 4가지 카테고리별로 가장 트렌디하고 자극적인(어그로 잘 끌리는) 주제를 각각 3개씩, 총 12개를 만들어줘.
   - 카테고리 종류: '기술', '파이썬 업무 자동화', '로봇 & 스마트팩토리', '게임 트렌드'
2. 제목(주제)은 딱딱하지 않고 인기 유튜브 썸네일처럼 호기심을 자극하며 유머러스하게 지어줘.
3. 출력 형식은 파이썬이 바로 읽을 수 있게 반드시 다른 설명 없이 오직 순수한 JSON 배열 형식으로만 출력해줘. JSON 키값은 아래 가이드라인을 100% 지켜야 해.

[출력 JSON 형식 예시]
[
  {
    "상태": "대기",
    "주제": "찰지고 재미있는 제목 문구 (예: 아직도 손으로 복붙 하세요? 파이썬 웹 크롤러로 1분 만에...)",
    "카테고리": "카테고리 이름 중 하나",
    "이미지 키워드": "DALL-E가 멋진 썸네일을 그릴 수 있도록 돕는 구체적인 영어 단어 조합 (예: automated robot hands typing computer code, futuristic high tech)",
    "슬러그": "영어-소문자-하이픈-조합-슬러그 (예: python-web-crawler-tips)"
  }
]
"""

try:
    response = model.generate_content(prompt)
    raw_text = response.text
    
    # 제미나이가 혹시 넣었을지 모를 마크다운 껍데기 제거
    raw_text = re.sub(r'^```(json)?\s*', '', raw_text, flags=re.IGNORECASE)
    raw_text = re.sub(r'```\s*$', '', raw_text).strip()
    
    new_topics = json.loads(raw_text)
    print(f"  ✅ 제미나이가 신상 꿀잼 주제 {len(new_topics)}개를 성공적으로 기획했습니다!")
    
    # 구글 시트에 행 추가하기 위해 리스트 형태로 가공
    rows_to_append = []
    for topic in new_topics:
        rows_to_append.append([
            "대기",
            topic.get("주제", "").strip(),
            topic.get("카테고리", "").strip(),
            topic.get("이미지 키워드", "").strip(),
            topic.get("슬러그", "").strip()
        ])
        
    # 시트 맨 아래에 한 번에 12개 주제 밀어넣기
    worksheet.append_rows(rows_to_append)
    print(f"  📝 구글 시트에 새 주제 {len(rows_to_append)}건을 '대기' 상태로 추가 완료했습니다!")

except Exception as e:
    print(f"❌ 주제 생성 및 시트 반영 중 에러 발생: {e}")
    print(f"제미나이 원본 출력물 참고용: {response.text}")
