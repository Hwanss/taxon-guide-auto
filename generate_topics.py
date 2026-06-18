import os
import json
import warnings
import gspread
from google import genai
from google.genai import types

warnings.filterwarnings("ignore", category=FutureWarning)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ 에러: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다.")
    exit(1)

# 🔥 API 클라이언트 최신화
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

print("="*60)
print("🌿 [TaxonGuru] 한/영 태그 동시 기획 공장 가동 (14개)")
print("="*60)

try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    # 🔥 gspread 공식 최신 내장 함수 사용
    gc = gspread.service_account_from_dict(creds_json)
    worksheet = gc.open_by_key(sheet_id).worksheet("taxonguru")
    
    existing_records = worksheet.get_all_values()
    existing_species = []
    if len(existing_records) > 1:
        for row in existing_records[1:]:
            if len(row) > 1 and row[1].strip():
                existing_species.append(row[1].strip())
                
    existing_species_str = ", ".join(existing_species) if existing_species else "없음"
    
except Exception as e:
    print(f"❌ 구글 시트 연결 및 기존 데이터 읽기 실패: {e}")
    exit(1)

prompt = f"""
너는 생물 분류학 및 자연과학 전문 블로그 'TaxonGuru'의 수석 디렉터야.
우리 블로그에 새로 추가할 '조회수 폭발할 만한' 대박 꿀잼 생물 주제 14개를 기획해줘.

🚨 [중요: 이미 다룬 생물 목록 - 아래 학명들은 절대 중복 금지!]
{existing_species_str}

[필수 지정 카테고리 리스트]
1. 'Botany / 식물학'
2. 'Evolution Mysteries / 진화의 미스터리'
3. 'Extreme Survivors / 극한의 생존자'
4. 'Size Lab / 크기 비교 연구소'

[작성 조건 및 태그 규칙]
- 국문/영문명은 매력적인 타이틀로 지어줘.
- 스토리앵글은 유머러스한 드립과 반전 썰로 1~2줄 요약해줘.
- 🔥 중요: "태그" 필드에는 한국어 핵심 키워드와 영어 핵심 키워드를 반반씩 섞어서 콤마(,)로 작성해줘.
- 반드시 다른 설명 없이 오직 순수한 JSON 배열 데이터만 반환해줘.

[필수 구조 예시]
[
  {{
    "학명": "Echiniscus testudo",
    "국문/영문명": "물곰 (Tardigrade) - 우주에서도 살아남는 불사의 존재",
    "분류 트리": "Animalia > Tardigrada",
    "카테고리": "Extreme Survivors / 극한의 생존자",
    "스토리앵글": "총을 쏴도 끓여도 안 죽는 지구 최강 생명체의 반전 매력",
    "슬러그": "tardigrade-extreme-survivor",
    "태그": "물곰, 타디그레이드, tardigrade, extreme-survivor"
  }}
]
"""

try:
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    raw_text = response.text.strip()
    
    new_topics = json.loads(raw_text)
    print(f"  ✅ 제미나이가 신상 주제 {len(new_topics)}개를 기획했습니다!")
    
    rows_to_append = []
    for topic in new_topics:
        rows_to_append.append([
            "대기", 
            topic.get("학명", "").strip(), 
            topic.get("국문/영문명", "").strip(), 
            topic.get("분류 트리", "").strip(), 
            topic.get("카테고리", "").strip(), 
            topic.get("스토리앵글", "").strip(), 
            topic.get("슬러그", "").strip(), 
            topic.get("태그", "").strip() 
        ])
        
    worksheet.append_rows(rows_to_append)
    print(f"  📝 구글 시트 [taxonguru] 탭에 한/영 태그가 포함된 신규 주제 14건 추가 완료!")

except Exception as e:
    print(f"❌ 주제 생성 실패: {e}")
