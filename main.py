import os
import requests
import json
import warnings
import re
import time
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import google.generativeai as genai

# =====================================================================
# 🛡️ [시스템 코어 설정]
# =====================================================================
import urllib3.util.connection as urllib3_cn
urllib3_cn.HAS_IPV6 = False
warnings.filterwarnings("ignore", category=FutureWarning)

WP_URL = "https://taxonguru.com/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TaxonGuru-AutoBlogger/2.0",
    "Accept": "application/json"
}

print("="*60)
print("📊 [TaxonGuru] 구글 시트 연동 및 자동화 프로세스 시작")
print("="*60)

# =====================================================================
# 📋 [Step 0] 구글 시트 '주제리스트'에서 '대기' 항목 가져오기
# =====================================================================
try:
    # GitHub Secrets에 등록해 둔 서비스 계정 JSON과 시트 ID 불러오기
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    
    # 첫 번째 워크시트(주제리스트) 열기
    worksheet = gc.open_by_key(sheet_id).sheet1
    records = worksheet.get_all_values()
    
    target_row_index = -1
    target_data = None
    
    # A열(인덱스 0)이 '대기'인 첫 번째 행 찾기
    for i, row in enumerate(records):
        if i == 0: continue # 첫 번째 줄(헤더)은 건너뜀
        if len(row) > 0 and row[0].strip() == "대기":
            target_row_index = i + 1 # gspread는 1부터 시작하므로 +1
            target_data = row
            break
            
    if not target_data:
        print("✅ 모든 주제가 발행되었습니다! '대기' 상태인 주제가 없습니다.")
        exit(0)
        
    # 시트 데이터 매핑 (B:주제, C:카테고리, D:이미지키워드, E:슬러그)
    TARGET_SPECIES = target_data[1].strip()
    TARGET_CATEGORY = target_data[2].strip()
    IMAGE_KEYWORD = target_data[3].strip() if len(target_data) > 3 else "technology"
    # 주제에서 주요 키워드를 뽑아 임시 태그로 사용
    TARGET_TAGS = [TARGET_CATEGORY, "트렌드", "IT", TARGET_SPECIES.split()[0]]

    print(f"🎯 오늘 작성할 주제: {TARGET_SPECIES}")
    
except Exception as e:
    print(f"❌ 구글 시트 접근 에러 (GOOGLE_CREDENTIALS 또는 SHEET_ID 확인): {e}")
    exit(1)


# =====================================================================
# 🛠️ [Helper] 카테고리/태그 ID 검색 및 생성
# =====================================================================
def get_or_create_wp_term(term_name, taxonomy="categories"):
    url = f"{WP_URL}/{taxonomy}"
    time.sleep(3) # 봇 차단 방지
    try:
        search_res = requests.get(url, params={"search": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if search_res.status_code == 200:
            for item in search_res.json():
                if item['name'].lower() == term_name.lower():
                    return item['id']
        time.sleep(2)
        create_res = requests.post(url, json={"name": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if create_res.status_code == 201:
            print(f"  ✨ 새 {taxonomy} 생성됨: {term_name}")
            return create_res.json()['id']
    except Exception as e:
        print(f"  ⚠️ {taxonomy} 처리 중 에러: {e}")
    return None

# =====================================================================
# 🎨 [Step 1] DALL-E 썸네일 생성 (시트의 '이미지 키워드' 활용)
# =====================================================================
print("\n[Step 1] DALL-E 썸네일 이미지 생성을 요청합니다...")
dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", 
        prompt=f"A highly detailed, cinematic 3D illustration representing: {IMAGE_KEYWORD}. Professional blog cover image style.",
        size="1024x1024", quality="standard", n=1
    )
    dalle_image_url = image_response.data[0].url
except Exception as e:
    print(f"  ❌ DALL-E 썸네일 대기 중: {e}")

# =====================================================================
# ✍️ [Step 2] AI 본문 작성 (주제 리스트 맞춤형)
# =====================================================================
print("\n[Step 2] 본문 작성 중...")
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = f"""
너는 IT 트렌드 및 기술 블로그 에디터야. 주제는 다음과 같아: "{TARGET_SPECIES}"

글은 도입부(Hook) - 본론(상세 설명, 예시, 팩트) - 결론(전망 및 요약)의 3단 구조로 아주 상세하고 전문적으로 작성해줘. 독자가 흥미를 잃지 않게 가독성 높은 소제목을 사용할 것.
출력 형식: HTML로 작성하고, 절대 앞뒤에 ```html 같은 기호를 붙이지 마.
"""

try:
    response = model.generate_content(prompt)
    blog_content = response.text
    blog_content = re.sub(r'^```(html)?\s*', '', blog_content, flags=re.IGNORECASE)
    blog_content = re.sub(r'```\s*$', '', blog_content).strip()
except Exception:
    blog_content = f"<h2>{TARGET_SPECIES}</h2><p>본문 생성 에러</p>"

# =====================================================================
# 🌐 [Step 3] 미디어 업로드 및 카테고리 매핑
# =====================================================================
media_id = None
if dalle_image_url:
    try:
        img_data = requests.get(dalle_image_url, timeout=30).content
        media_headers = common_headers.copy()
        media_headers.update({'Content-Type': 'image/jpeg', 'Content-Disposition': 'attachment; filename="cover_image.jpg"'})
        time.sleep(3)
        media_res = requests.post(f"{WP_URL}/media", headers=media_headers, auth=(WP_USER, WP_APP_PASSWORD), data=img_data, timeout=60)
        if media_res.status_code == 201: media_id = media_res.json().get('id')
    except Exception:
        pass

print("\n[Step 3.5] 카테고리 매핑 중...")
category_id = get_or_create_wp_term(TARGET_CATEGORY, "categories")
tag_ids = []
for tag in TARGET_TAGS:
    t_id = get_or_create_wp_term(tag, "tags")
    if t_id: tag_ids.append(t_id)

# =====================================================================
# 🚀 [Step 4] 최종 발행 및 구글 시트 상태 변경
# =====================================================================
print("\n[Step 4] 최종 발행 중...")
time.sleep(4) 

post_data = {"title": f"{TARGET_SPECIES}", "content": blog_content, "status": "publish"}
if media_id: post_data["featured_media"] = media_id
if category_id: post_data["categories"] = [category_id]
if tag_ids: post_data["tags"] = tag_ids

try:
    post_res = requests.post(f"{WP_URL}/posts", headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), json=post_data, timeout=60)
    if post_res.status_code == 201:
        print("  🎉 [발행 대성공!] 워드프레스에 글이 정상 등록되었습니다.")
        
        # 🟢 마지막 핵심: 구글 시트의 해당 행 '상태(A열)'를 '완료'로 변경!
        worksheet.update_cell(target_row_index, 1, "완료")
        print(f"  📝 구글 시트 {target_row_index}행의 상태를 '완료'로 업데이트했습니다.")
    else:
        print(f"  ❌ 발행 실패: {post_res.text}")
except Exception as e:
    print(f"  ❌ 워드프레스 통신 치명적 에러: {e}")
