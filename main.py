import os
import gspread
import requests
import google.generativeai as genai
import json
import time
from requests.auth import HTTPBasicAuth
from oauth2client.service_account import ServiceAccountCredentials
from slugify import slugify

# --- 1. 환경 설정 (GitHub Secrets에서 가져옴) ---
# 구글 서비스 계정 키 파일을 생성 (Actions 환경용)
if not os.path.exists('gcp_key.json'):
    with open('gcp_key.json', 'w') as f:
        f.write(os.environ["GOOGLE_CREDENTIALS"])

# 환경 변수 가져오기
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SHEET_ID = os.environ["SHEET_ID"]

WP_URL = "https://taxonguru.com/wp-json/wp/v2"
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# --- 2. 구글 시트 및 Gemini 연결 ---
creds = ServiceAccountCredentials.from_json_keyfile_name('gcp_key.json', SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet('taxonguru')

# 기존 코어브리프 블로그에서 검증된 모델로 적용합니다.
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

def generate_blog_post(row):
    prompt = f"""
    당신은 전문적인 생물학 저술가입니다. 다음 데이터를 바탕으로 독자가 지적 충만감을 느낄 수 있는 깊이 있는 블로그 글을 작성해주세요.
    
    [데이터]
    - 학명: {row['학명(Scientific Name)']}
    - 국문/영문명: {row['국문/영문명']}
    - 분류 트리: {row['분류 트리']}
    - 스토리 앵글: {row['스토리 앵글']}
    
    [작성 규칙]
    1. 전문적이고 흥미로운 팩트를 포함할 것.
    2. HTML 태그(<p>, <h2>, <ul>, <table> 등)를 활용할 것.
    3. 반드시 JSON 형식으로만 응답할 것.
    
    {{
        "content": "HTML 본문",
        "excerpt": "요약 2줄",
        "tags": ["태그1", "태그2"]
    }}
    """
    response = model.generate_content(prompt)
    clean_res = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_res)

# --- 3. 메인 실행 로직 ---
print("🚀 [TaxonGuru] 시스템 가동...")
data = sheet.get_all_records()

for i, row in enumerate(data):
    if row.get('상태') == '대기':
        print(f"✍️ 작성 중: {row['국문/영문명']}")
        
        # AI 글 생성
        try:
            ai_data = generate_blog_post(row)
        except Exception as e:
            print(f"⚠️ 생성 실패: {e}")
            continue
        
        # 슬러그 생성
        slug = row.get('슬러그 (Slug)') or slugify(row['국문/영문명'])
        
        # 워드프레스 발행
        payload = {
            'title': f"{row['국문/영문명']} ({row['학명(Scientific Name)']})",
            'content': ai_data['content'],
            'excerpt': ai_data['excerpt'],
            'status': 'publish',
            'slug': slug
        }
        res = requests.post(f"{WP_URL}/posts", auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD), json=payload)
        
        if res.status_code == 201:
            print(f"🎉 성공! {row['국문/영문명']} 발행 완료")
            sheet.update_cell(i + 2, 1, '발행완료') # A열 상태 변경
            sheet.update_cell(i + 2, 7, slug)     # G열 슬러그 기입
        else:
            print(f"❌ 실패: {res.text}")
        
        time.sleep(5)
