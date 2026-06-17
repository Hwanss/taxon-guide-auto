import os
import json
import warnings
import gspread
import re
from google.oauth2.service_account import Credentials
import google.generativeai as genai

warnings.filterwarnings("ignore", category=FutureWarning)

# API 및 구글 시트 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ 에러: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다. YML 설정을 확인하세요.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

print("="*60)
print("🧠 [TaxonGuru] 철벽 방어 신규 주제 기획 공장 가동")
print("="*60)

try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    worksheet = gc.open_by_key(sheet_id).sheet1
except Exception as e:
    print(f"❌ 구글 시트 연결 실패 (SHEET_ID 또는 CREDENTIALS 오류): {e}")
    exit(1)

# 제미나이에게 주제 기획 요청
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = """
우리 블로그에 새로 추가할 '조회수 폭발할 만한' 신선하고 흥미로운 포스팅 주제를 기획해줘.

[기획 조건]
1. 아래 4가지 카테고리별로 가장 트렌디하고 자극적인(어그로 잘 끌리는) 주제를 각각 3개씩, 총 12개를 만들어줘.
   - 카테고리 종류: '기술', '파이썬 업무 자동화', '로봇 & 스마트팩토리', '게임 트렌드'
2. 제목(주제)은 딱딱하지 않고 인기 유튜브 썸네일처럼 호기심을 자극하며 유머러스하게 지어줘.
3. 출력 형식은 파이썬이 바로 읽을 수 있게 반드시 다른 설명 없이 오직 순수한 JSON 배열 형식으로만 출력해줘.

[출력 형식 예시]
[
  {
    "상태": "대기",
    "주제": "제목 문구",
    "카테고리": "카테고리 이름",
    "이미지 키워드": "영어 키워드",
    "슬러그": "영어-슬러그"
  }
]
"""

try:
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    
    # 🔥 [무적의 방어막] 앞뒤에 어떤 문자열이나 마크다운이 붙어도 [ ] 구간만 완벽하게 추출
    json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
    
    if json_match:
        clean_json_text = json_match.group(0)
    else:
        # 정규식 실패 시 기존 방식으로 보완
        clean_json_text = re.sub(r'^```(json)?\s*', '', raw_text, flags=re.IGNORECASE)
        clean_json_text = re.sub(r'```\s*$', '', clean_json_text).strip()
    
    new_topics = json.loads(clean_json_text)
    print(f"  ✅ 제미나이가 신상 꿀잼 주제 {len(new_topics)}개를 기획했습니다!")
    
    rows_to_append = []
    for topic in new_topics:
        rows_to_append.append(
