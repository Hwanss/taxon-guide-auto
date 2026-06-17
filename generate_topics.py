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
print("🧠 [TaxonGuru] 14개(1주일치) 순수 데이터 강제 출력 공장 가동")
print("="*60)

try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    worksheet = gc.open_by_key(sheet_id).worksheet("taxonguru")
except Exception as e:
    print(f"❌ 구글 시트 연결 실패 (SHEET_ID 또는 CREDENTIALS 오류): {e}")
    exit(1)

# 제미나이에게 주제 기획 요청 (14개로 수정)
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = """
우리 블로그에 새로 추가할 '조회수 폭발할 만한' 신선하고 흥미로운 포스팅 주제를 기획해줘.

[기획 조건]
1. 아래 4가지 카테고리를 활용해, 매일 2개씩 7일 동안 발행할 수 있도록 총 14개의 주제를 만들어줘. 카테고리별로 골고루 배분해.
   - 카테고리 종류: '기술', '파이썬 업무 자동화', '로봇 & 스마트팩토리', '게임 트렌드'
2. 제목(주제)은 딱딱하지 않고 인기 유튜브 썸네일처럼 호기심을 자극하며 유머러스하게 지어줘.
3. 반드시 다른 설명이나 인사말 없이 오직 순수한 JSON 배열 데이터만 반환해야 해.

[필수 구조 예시]
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

raw_text = ""
try:
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    raw_text = response.text.strip()
    
    new_topics = json.loads(raw_text)
    print(f"  ✅ 제미나이가 신상 꿀잼 주제 {len(new_topics)}개를 완벽하게 기획했습니다!")
    
    rows_to_append = []
    for topic in new_topics:
        rows_to_append.append([
            "대기",
            topic.get("주제", "").strip(),
            topic.get("카테고리", "").strip(),
            topic.get("이미지 키워드", "").strip(),
            topic.get("슬러그", "").strip()
        ])
        
    worksheet.append_rows(rows_to_append)
    print(f"  📝 구글 시트 [taxonguru] 탭에 새 주제 {len(rows_to_append)}건을 '대기' 상태로 추가 완료했습니다!")

except Exception as e:
    print(f"❌ 주제 생성 및 시트 반영 중 에러 발생: {e}")
    if raw_text:
        print(f"⚠️ 제미나이가 보낸 원본 텍스트:\n{raw_text}")
