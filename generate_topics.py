import os
import json
import warnings
import gspread
import re
from google.oauth2.service_account import Credentials
import google.generativeai as genai

warnings.filterwarnings("ignore", category=FutureWarning)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ 에러: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

print("="*60)
print("🌿 [TaxonGuru] 공식 카테고리 맞춤형 주제 기획 가동 (14개)")
print("="*60)

try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    worksheet = gc.open_by_key(sheet_id).worksheet("taxonguru")
except Exception as e:
    print(f"❌ 구글 시트 연결 실패: {e}")
    exit(1)

model = genai.GenerativeModel('gemini-2.5-flash')
prompt = """
너는 생물 분류학 및 자연과학 전문 블로그 'TaxonGuru'의 수석 디렉터야.
우리 블로그에 새로 추가할 '조회수 폭발할 만한' 대박 꿀잼 생물(동물, 식물, 고생물, 미생물 등) 주제 14개를 기획해줘.

[필수 지정 카테고리 리스트]
다음 4가지 카테고리 안에서만 생물을 선정하고, 골고루 배분해줘. (텍스트 토시 하나 안 틀리게 똑같이 지정해야 해)
1. 'Botany / 식물학'
2. 'Evolution Mysteries / 진화의 미스터리'
3. 'Extreme Survivors / 극한의 생존자'
4. 'Size Lab / 크기 비교 연구소'

[작성 조건]
- 국문/영문명은 독자의 호기심을 끄는 매력적인 타이틀로 지어줘.
- 스토리앵글은 이 생물을 설명할 때 어떤 유머러스한 드립과 반전 썰로 풀어낼지 1~2줄로 요약해줘.
- 반드시 다른 설명 없이 오직 순수한 JSON 배열 데이터만 반환해줘.

[필수 구조 예시]
[
  {
    "학명": "Echiniscus testudo",
    "국문/영문명": "물곰 (Tardigrade) - 우주에서도 살아남는 불사의 존재",
    "분류 트리": "Animalia > Tardigrada > Heterotardigrada > Echiniscidae",
    "카테고리": "Extreme Survivors / 극한의 생존자",
    "스토리앵글": "총을 쏴도 끓여도 안 죽는 지구 최강 생명체의 하찮고 귀여운 걸음걸이 반전 매력",
    "슬러그": "tardigrade-extreme-survivor",
    "태그": "물곰, 타디그레이드, 극한생물, 우주생물"
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
    print(f"  ✅ 제미나이가 공식 카테고리 기반 주제 {len(new_topics)}개를 기획했습니다!")
    
    rows_to_append = []
    for topic in new_topics:
        # A~H열까지 총 8열 매핑
        rows_to_append.append([
            "대기",  # A열: 상태
            topic.get("학명", "").strip(),  # B열: 학명
            topic.get("국문/영문명", "").strip(),  # C열: 국/영문명
            topic.get("분류 트리", "").strip(),  # D열: 분류 트리
            topic.get("카테고리", "").strip(),  # E열: 카테고리
            topic.get("스토리앵글", "").strip(),  # F열: 스토리 앵글
            topic.get("슬러그", "").strip(),  # G열: 슬러그
            topic.get("태그", "").strip()   # H열: 태그
        ])
        
    worksheet.append_rows(rows_to_append)
    print(f"  📝 구글 시트 [taxonguru] 탭에 공식 카테고리 맞춤 주제 14건 추가 완료!")

except Exception as e:
    print(f"❌ 주제 생성 실패: {e}")
