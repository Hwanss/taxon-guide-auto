import os
import gspread
import requests
import google.generativeai as genai
import json
import time
from requests.auth import HTTPBasicAuth
from oauth2client.service_account import ServiceAccountCredentials
from slugify import slugify

# --- 1. 환경 변수 불러오기 ---
# GitHub Actions의 Secrets에 등록된 값들을 가져옵니다.
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SHEET_ID = os.environ["SHEET_ID"]
WP_URL = "https://taxonguru.com/wp-json/wp/v2" # 본인의 도메인 확인!

# 구글 서비스 계정 인증 (JSON 파일을 환경변수로 처리하는 경우를 대비)
# 로컬에서 테스트할 땐 'gcp_key.json' 파일이 같은 폴더에 있어야 합니다.
creds_path = 'gcp_key.json'
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet('taxonguru')

# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def generate_blog_post(row):
    """Gemini를 사용해 전문적인 생물학 포스트 작성"""
    prompt = f"""
    당신은 전문적인 생물학 저술가입니다. 다음 데이터를 바탕으로 독자가 지적 충만감을 느낄 수 있는 깊이 있는 블로그 글을 작성해주세요.
    
    [데이터]
    - 학명: {row['학명(Scientific Name)']}
    - 국문/영문명: {row['국문/영문명']}
    - 분류 트리: {row['분류 트리']}
    - 스토리 앵글(글의 분위기): {row['스토리 앵글']}
    
    [작성 규칙]
    1. 5단 구조를 지킬 것: [Hook], [Scientific Backbone(표 활용)], [Deep Anatomy], [Evolutionary Context], [Verdict & Trivia]
    2. 독자가 친구에게 자랑할 만한 전문적 지식을 포함할 것.
    3. 반드시 JSON 형식으로만 답변할 것.
    
    {{
        "content": "HTML 태그(<p>, <h2>, <ul>, <table> 등)를 활용한 본문 내용",
        "excerpt": "글 요약 (2줄)",
        "tags": ["태그1", "태그2", "태그3"]
    }}
    """
    response = model.generate_content(prompt)
    clean_res = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_res)

def post_to_wordpress(payload):
    """워드프레스에 글 발행"""
    res = requests.post(f"{WP_URL}/posts", auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD), json=payload)
    return res

# --- 메인 실행 로직 ---
print("🚀 [TaxonGuru 자동 발행 시스템] 실행 중...")
data = sheet.get_all_records()

for i, row in enumerate(data):
    if row.get('상태') == '대기':
        print(f"\n✍️ 작성 중: {row['국문/영문명']}")
        
        # 1. AI로 글 생성
        try:
            ai_data = generate_blog_post(row)
        except Exception as e:
            print(f"⚠️ 생성 실패: {e}")
            continue
            
        # 2. 슬러그 설정 (없으면 제목으로 생성)
        slug = row.get('슬러그 (Slug)')
        if not slug:
            slug = slugify(row['국문/영문명'])
            
        # 3. 워드프레스 페이로드 구성
        payload = {
            'title': f"{row['국문/영문명']} ({row['학명(Scientific Name)']})",
            'content': ai_data['content'],
            'excerpt': ai_data['excerpt'],
            'status': 'publish',
            'slug': slug
        }
        
        # 4. 발행
        res = post_to_wordpress(payload)
        
        if res.status_code == 201:
            print(f"🎉 성공! {row['국문/영문명']} 발행 완료")
            # 시트 업데이트 (상태 변경 및 슬러그 기록)
            sheet.update_cell(i + 2, 1, '발행완료')
            sheet.update_cell(i + 2, 7, slug) # G열
        else:
            print(f"❌ 실패: {res.text}")
        
        time.sleep(5) # 서버 부하 방지
