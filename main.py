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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TaxonGuru/2.0",
    "Accept": "application/json"
}

print("="*60)
print("📊 [TaxonGuru] 8열 구조 생물 도감 매핑 & 블로그 발행 가동")
print("="*60)

# =====================================================================
# 📋 [Step 0] 구글 시트 8열 정밀 매핑
# =====================================================================
try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    
    worksheet = gc.open_by_key(sheet_id).worksheet("taxonguru")
    records = worksheet.get_all_values()
    
    target_row_index = -1
    target_data = None
    
    for i, row in enumerate(records):
        if i == 0: continue
        if len(row) > 0 and row[0].strip() == "대기":
            target_row_index = i + 1
            target_data = row
            break
            
    if not target_data:
        print("✅ '대기' 상태인 주제가 없습니다. 프로세스를 종료합니다.")
        exit(0)
        
    SCI_NAME = target_data[1].strip()
    COMMON_NAME = target_data[2].strip() if len(target_data) > 2 else SCI_NAME
    TAXONOMY_TREE = target_data[3].strip() if len(target_data) > 3 else ""
    TARGET_CATEGORY = target_data[4].strip() if len(target_data) > 4 else "Uncategorized"
    STORY_ANGLE = target_data[5].strip() if len(target_data) > 5 else "진화와 생태의 신비"
    TARGET_SLUG = target_data[6].strip() if len(target_data) > 6 else SCI_NAME.replace(" ", "-").lower()
    
    raw_tags = target_data[7].strip() if len(target_data) > 7 else ""
    TARGET_TAGS = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else [TARGET_CATEGORY]

    print(f"🎯 발행 생물: {SCI_NAME} ({COMMON_NAME})")
    
except Exception as e:
    print(f"❌ 구글 시트 매핑 실패: {e}")
    exit(1)

# =====================================================================
# 🛠️ [Helper] 카테고리/태그 ID 매핑 자동화
# =====================================================================
def get_or_create_wp_term(term_name, taxonomy="categories"):
    url = f"{WP_URL}/{taxonomy}"
    time.sleep(3)
    try:
        search_res = requests.get(url, params={"search": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if search_res.status_code == 200:
            for item in search_res.json():
                if item['name'].lower() == term_name.lower(): return item['id']
        time.sleep(2)
        create_res = requests.post(url, json={"name": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if create_res.status_code == 201: return create_res.json()['id']
    except Exception: pass
    return None

# =====================================================================
# 🔍 [Step 1] 위키미디어 이미지 수집
# =====================================================================
wiki_url = "https://en.wikipedia.org/w/api.php"
wiki_params = {"action": "query", "titles": SCI_NAME, "generator": "images", "gimlimit": "10", "prop": "imageinfo", "iiprop": "url", "format": "json", "redirects": "1"}
wiki_images = []
try:
    wiki_res = requests.get(wiki_url, params=wiki_params, headers=common_headers, timeout=20)
    pages = wiki_res.json().get("query", {}).get("pages", {})
    for pid, pdata in pages.items():
        if "imageinfo" in pdata:
            img_url = pdata["imageinfo"][0]["url"]
            if any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]) and "logo" not in img_url.lower() and "icon" not in img_url.lower():
                wiki_images.append(img_url)
except Exception: pass

# =====================================================================
# 🎨 [Step 2] DALL-E 생태계 썸네일 생성
# =====================================================================
dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", prompt=f"A highly detailed, cinematic National Geographic style 3D illustration of {SCI_NAME}. Natural environment, dynamic lighting.",
        size="1024x1024", quality="standard", n=1
    )
    dalle_image_url = image_response.data[0].url
except Exception: pass

# =====================================================================
# ✍️ [Step 3] 스토리앵글 맞춤형 꿀잼 다큐 본문 작성 (다국어 닉네임 반영)
# =====================================================================
print("\n[Step 3] 스토리앵글 맞춤형 대본(본문) 작성 중...")
model = genai.GenerativeModel('gemini-2.5-flash')

# 🔥 영문/국문 닉네임을 스마트하게 분리해서 쓰도록 프롬프트 수정
prompt = f"""
너는 'TaxonGuru' 블로그의 수석 고생물학자이자 생태계 스토리텔러야. 
너의 공식 닉네임은 한국어로는 '에디터 택슨구루', 영어로는 'Editor TaxonGuru'야. 
글 안에서 본인을 소개하거나 마무리 인사를 할 때 [당신의 닉네임] 같은 빈칸 템플릿을 절대 쓰지 마!
대신 [1부: 한국어 버전]에서는 당당하게 '에디터 택슨구루'라고 인사하고, [2부: Global Readers English Version]에서는 'Editor TaxonGuru'라고 아주 자연스럽게 사용해.

[연구 대상 정보]
- 학명: {SCI_NAME}
- 이름: {COMMON_NAME}
- 분류 트리: {TAXONOMY_TREE}
- 스토리앵글(글의 핵심 방향): {STORY_ANGLE}

[작성 가이드라인]
1. 5단 구조(Hook, Scientific Backbone, Deep Anatomy, Evolutionary Context, Verdict & Trivia)를 무조건 갖춰줘.
2. 지정된 '스토리앵글'에 맞춰 아주 흥미롭고 위트 있는 찰진 썰(대화체 팍팍 섞어서)로 독자들을 몰입시켜줘. 딱딱한 백과사전 톤 절대 금지!
3. 본문 상단에 분류 트리({TAXONOMY_TREE}) 정보를 표나 깔끔한 리스트로 마크업해줘.
4. 가독성을 위해 [1부: 한국어 버전]을 먼저 끝낸 뒤, [2부: Global Readers English Version] 전체 번역본을 맨 아래에 완벽히 분리해서 작성해. (한 줄씩 번갈아 쓰지 마!)
5. 본론 중간중간 알맞은 위치에 `[WIKI_IMAGE_1]`, `[WIKI_IMAGE_2]` 위치 태그를 정확히 삽입해줘. 
6. 순수 HTML 내용물만 출력할 것(```html 기호 절대 금지).
"""

try:
    response = model.generate_content(prompt)
    blog_content = response.text
    blog_content = re.sub(r'^```(html)?\s*', '', blog_content, flags=re.IGNORECASE)
    blog_content = re.sub(r'```\s*$', '', blog_content).strip()
except Exception:
    blog_content = f"<h2>{COMMON_NAME}</h2><p>본문 작성 중 에러가 발생했습니다.</p>"

if wiki_images:
    for idx, img_url in enumerate(wiki_images[:3]):
        placeholder = f"[WIKI_IMAGE_{idx+1}]"
        image_html = f'<figure style="text-align: center; margin: 30px 0;"><img src="{img_url}" alt="{SCI_NAME} 자료화면" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);"><figcaption style="font-size: 0.85em; color: #666; margin-top: 8px;">🌍 {SCI_NAME} 실제 현장 자료화면</figcaption></figure>'
        if placeholder in blog_content:
            blog_content = blog_content.replace(placeholder, image_html)
        else:
            blog_content += "<br>" + image_html

blog_content = re.sub(r'\[WIKI_IMAGE_\d+\]', '', blog_content)

# =====================================================================
# 🌐 [Step 4] 워드프레스 미디어 업로드 및 카테고리 매핑
# =====================================================================
media_id = None
if dalle_image_url:
    try:
        img_data = requests.get(dalle_image_url, timeout=30).content
        media_headers = common_headers.copy()
        media_headers.update({'Content-Type': 'image/jpeg', 'Content-Disposition': f'attachment; filename="{SCI_NAME.replace(" ", "_")}.jpg"'})
        time.sleep(3)
        media_res = requests.post(f"{WP_URL}/media", headers=media_headers, auth=(WP_USER, WP_APP_PASSWORD), data=img_data, timeout=60)
        if media_res.status_code == 201: media_id = media_res.json().get('id')
    except Exception: pass

print("\n[Step 4.5] 지정 카테고리 고유 ID 변환 및 태그 매핑 중...")
category_id = get_or_create_wp_term(TARGET_CATEGORY, "categories")
tag_ids = []
for tag in TARGET_TAGS:
    t_id = get_or_create_wp_term(tag, "tags")
    if t_id: tag_ids.append(t_id)

# =====================================================================
# 🚀 [Step 5] 최종 포스팅 발행 및 시트 '완료' 처리
# =====================================================================
print("\n[Step 5] 워드프레스 최종 포스팅 발행 중...")
time.sleep(4)

post_data = {
    "title": f"{COMMON_NAME}",
    "content": blog_content,
    "slug": TARGET_SLUG,
    "status": "publish"
}
if media_id: post_data["featured_media"] = media_id
if category_id: post_data["categories"] = [category_id]
if tag_ids: post_data["tags"] = tag_ids

try:
    post_res = requests.post(f"{WP_URL}/posts", headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), json=post_data, timeout=60)
    if post_res.status_code == 201:
        print("  🎉 [발행 대성공!] 공식 카테고리에 맞춰 글이 정상 발행되었습니다.")
        worksheet.update_cell(target_row_index, 1, "완료")
        print(f"  📝 구글 시트 {target_row_index}행의 상태를 '완료'로 변경했습니다.")
    else:
        print(f"  ❌ 발행 실패: {post_res.text}")
except Exception as e:
    print(f"  ❌ 최종 발행 중 에러 발생: {e}")
