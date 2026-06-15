import os
import gspread
import requests
import google.generativeai as genai
import json
import time
from requests.auth import HTTPBasicAuth
from oauth2client.service_account import ServiceAccountCredentials
from slugify import slugify

# --- 1. 환경 설정 ---
if not os.path.exists('gcp_key.json'):
    with open('gcp_key.json', 'w') as f:
        f.write(os.environ["GOOGLE_CREDENTIALS"])

WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SHEET_ID = os.environ["SHEET_ID"]

WP_URL = "https://taxonguru.com/wp-json/wp/v2"
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name('gcp_key.json', SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet('taxonguru')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

# --- 2. 🌐 위키피디아 팩트 수집 ---
def get_wikipedia_info(scientific_name):
    try:
        search_term = scientific_name.replace(' ', '_')
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_term}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json().get('extract', '')
        return ""
    except:
        return ""

# --- 3. 🧠 연쇄적 생성 (Chain-of-Generation) 로직 ---
def generate_deep_dive_post(row):
    scientific_name = row['학명(Scientific Name)']
    title = row['국문/영문명']
    
    # [Step 1] 데이터 수집
    print(f"   🔍 [Step 1] {title} 위키피디아 데이터 검색 중...")
    wiki_fact = get_wikipedia_info(scientific_name)
    
    # [Step 2] 구조 설계 (Outline & Fact Extraction)
    print(f"   ⚙️ [Step 2] AI 상세 개요 및 핵심 팩트 추출 중...")
    outline_prompt = f"""
    아래 위키피디아 데이터를 분석하여, 깊이 있는 생물학 블로그 글을 쓰기 위한 '핵심 개요'를 JSON으로 추출해.
    - 대상: {title} ({scientific_name})
    - 데이터: {wiki_fact}
    
    출력 형식 (JSON):
    {{
        "hook_idea": "독자의 시선을 끌 강렬한 첫 문장 아이디어",
        "key_facts": ["팩트1", "팩트2", "팩트3"],
        "evolutionary_context": "진화적 또는 생태학적 의의 요약",
        "difficult_terms": {{"용어1": "뜻", "용어2": "뜻"}}
    }}
    """
    outline_res = model.generate_content(outline_prompt)
    outline_data = json.loads(outline_res.text.replace("```json", "").replace("```", "").strip())
    
    # [Step 3 & 4] 본문 작성 및 윤문 (Deep-Dive Drafting)
    print(f"   ✍️ [Step 3] 5단 구조 딥다이브 본문 작성 중...")
    draft_prompt = f"""
    당신은 전문적인 생물학 저술가입니다. 앞서 정리한 [개요 데이터]와 [기획 앵글]을 바탕으로, 독자가 지적 충만감을 느낄 수 있는 2,000자 이상의 밀도 높은 글을 작성하세요.
    
    [개요 데이터]
    {json.dumps(outline_data, ensure_ascii=False)}
    
    [기획 앵글]
    - 분류 트리: {row['분류 트리']}
    - 스토리 앵글: {row['스토리 앵글']}
    
    [작성 규칙 : 반드시 아래 5단 구조를 지킬 것]
    1. [Hook]: '{outline_data['hook_idea']}'를 활용하여 고정관념을 깨는 질문으로 시작.
    2. [Scientific Backbone]: 분류 체계({row['분류 트리']})와 생태적 지위를 <table> 태그를 사용하여 깔끔한 표로 제시.
    3. [Deep Anatomy]: 신체 특징과 생존 전략을 '작동 원리'처럼 구체적으로 설명. (비유 사용)
    4. [Evolutionary Context]: 진화적 맥락과 생태계에서의 역할 서술.
    5. [Verdict & Trivia]: 강렬한 한 줄 정의와 함께, 친구에게 자랑할 만한 썰(Trivia)로 마무리.
    * 글 하단에 <div class="glossary"> 태그를 활용해 '용어 사전'을 박스 형태로 덧붙일 것.
    
    출력 형식 (반드시 JSON만 출력):
    {{
        "content": "HTML 구조로 작성된 전체 본문 (h2, p, table, ul, div 등 적극 활용)",
        "excerpt": "글의 내용을 요약한 2줄 요약문",
        "tags": ["태그1", "태그2", "태그3"]
    }}
    """
    final_res = model.generate_content(draft_prompt)
    return json.loads(final_res.text.replace("```json", "").replace("```", "").strip())

# --- 4. 메인 실행 로직 ---
print("🚀 [TaxonGuru] 딥다이브(Deep-Dive) 자동화 공장 가동...")
data = sheet.get_all_records()

for i, row in enumerate(data):
    if row.get('상태') == '대기':
        print(f"\n======================================")
        print(f"▶ 타겟 생물: {row['국문/영문명']}")
        
        try:
            ai_data = generate_deep_dive_post(row)
        except Exception as e:
            print(f"⚠️ 생성 에러: {e}")
            continue
        
        slug = row.get('슬러그 (Slug)') or slugify(row['국문/영문명'])
        
        payload = {
            'title': f"{row['국문/영문명']} ({row['학명(Scientific Name)']})",
            'content': ai_data['content'],
            'excerpt': ai_data['excerpt'],
            'status': 'publish',
            'slug': slug
        }
        
        print(f"   🌐 [Step 4] 워드프레스 서버로 전송 중...")
        res = requests.post(f"{WP_URL}/posts", auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD), json=payload)
        
        if res.status_code == 201:
            print(f"🎉 성공! 하나의 완벽한 리포트가 발행되었습니다.")
            sheet.update_cell(i + 2, 1, '발행완료') 
            sheet.update_cell(i + 2, 7, slug)     
        else:
            print(f"❌ 실패: {res.text}")
        
        time.sleep(5)
