import os
import requests
import json
import warnings
import re
import time
import gspread
from openai import OpenAI
from google import genai # 🔥 최신 라이브러리로 변경

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

# 🔥 API 클라이언트 최신화
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TaxonGuru/2.0",
    "Accept": "application/json"
}

print("="*60)
print("📊 [TaxonGuru] 구글 인증 최신화 생물 도감 매핑 & 발행 가동")
print("="*60)

# =====================================================================
# 📋 [Step 0] 구글 시트 정밀 매핑 (에러 픽스)
# =====================================================================
try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
    # 🔥 토큰 충돌을 일으키던 구형 코드를 버리고, gspread 공식 최신 내장 함수 사용
    gc = gspread.service_account_from_dict(creds_json)
    
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
# 🎨 [Step 2] DALL-E 생태계 스펙타클 썸네일 생성
# =====================================================================
print("\n[Step 2] DALL-E 3 썸네일 이미지 생성 중...")
dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", prompt=f"A highly detailed, cinematic National Geographic style 3D illustration of {SCI_NAME}. Natural environment, dynamic lighting.",
        size="1024x1024", quality="standard", n=1
    )
    dalle_image_url = image_response.data[0].url
    print("  ✅ DALL-E 3 썸네일 이미지 생성 성공!")
except Exception as e:
    print(f"  ❌ DALL-E 3 통신 실패: {e}")

# =====================================================================
# ✍️ [Step 3] 본문 사이사이 강제 사진 배치 다큐 본문 작성
# =====================================================================
print("\n[Step 3] 스토리앵글 맞춤형 대본(본문) 작성 중...")

prompt = f"""
너는 'TaxonGuru' 블로그의 수석 고생물학자이자 생태계 스토리텔러야. 

[지정 닉네임 원칙]
- [1부: 한국어 버전]에서는 무조건 '에디터 택슨구루'라고 본인을 지칭해.
- [2부: English Version]에서는 무조건 'Editor TaxonGuru'라고 영어로 지칭해.

[연구 대상 정보]
- 학명: {SCI_NAME}
- 이름: {COMMON_NAME}
- 분류 트리: {TAXONOMY_TREE}
- 스토리앵글(글의 핵심 방향): {STORY_ANGLE}

[작성 가이드라인]
1. 5단 구조(Hook, Scientific Backbone, Deep Anatomy, Evolutionary Context, Verdict & Trivia)로 찰진 비유와 드립을 섞어 작성해.
2. 본문 상단에 분류 트리({TAXONOMY_TREE}) 정보를 마크업해.
3. ⚠️ 중요: 이미지 태그 3개를 본론 흐름 사이사이에 정확히 심어! 
   - [WIKI_IMAGE_1] : 한국어 [1부]의 도입부(Hook) 문단 끝.
   - [WIKI_IMAGE_2] : 한국어 [1부]의 중간 상세 해부(Deep Anatomy) 문단 끝.
   - [WIKI_IMAGE_3] : 영어 [2부]의 중간 파트 내용 끝.
4. [1부: 한국어 버전]을 끝낸 뒤, [2부: Global Readers English Version] 번역본을 맨 아래에 완벽히 분리해.
5. 순수 HTML 내용물만 출력할 것.
"""

try:
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    blog_content = response.text
    
    blog_content = blog_content.replace("```html\n", "")
    blog_content = blog_content.replace("```html", "")
    blog_content = blog_content.replace("```\n", "")
    blog_content = blog_content.replace("```", "")
    blog_content = blog_content.strip()
    
except Exception as e:
    print(f"❌ 치명적 에러: 제미나이 본문 작성 도중 오류가 발생했습니다: {e}")
    exit(1)

if wiki_images:
    for idx, img_url in enumerate(wiki_images[:3]):
        placeholder = f"[WIKI_IMAGE_{idx+1}]"
        image_html = f'<figure style="text-align: center; margin: 30px 0;"><img src="{img_url}" alt="{SCI_NAME} 관찰 사진" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);"><figcaption style="font-size: 0.85em; color: #666; margin-top: 8px;">📸 위키미디어 제공: 자연 상태의 {COMMON_NAME} 기록 사진</figcaption></figure>'
        if placeholder in blog_content:
            blog_content = blog_content.replace(placeholder, image_html)
        else:
            blog_content += "<br>" + image_html

for i in range(1, 4):
    blog_content = blog_content.replace(f"[WIKI_IMAGE_{i}]", "")

# =====================================================================
# 🌐 [Step 4] 워드프레스 미디어 업로드
# =====================================================================
media_id = None
if dalle_image_url:
    print("\n[Step 4] 워드프레스에 썸네일 업로드 중...")
    try:
        img_data = requests.get(dalle_image_url, timeout=30).content
        media_headers = common_headers.copy()
        media_headers.update({'Content-Type': 'image/png', 'Content-Disposition': f'attachment; filename="{SCI_NAME.replace(" ", "_")}.png"'})
        time.sleep(3)
        media_res = requests.post(f"{WP_URL}/media", headers=media_headers, auth=(WP_USER, WP_APP_PASSWORD), data=img_data, timeout=60)
        
        if media_res.status_code == 201: 
            media_id = media_res.json().get('id')
            print(f"  ✅ 썸네일 업로드 성공! (Media ID: {media_id})")
        else:
            print(f"  ❌ 썸네일 업로드 거부됨 (응답 코드 {media_res.status_code}): {media_res.text}")
    except Exception as e: 
        print(f"  ❌ 썸네일 업로드 중 통신 에러: {e}")

print("\n[Step 4.5] 지정 카테고리 고유 ID 변환 및 태그 매핑 중...")
category_id = get_or_create_wp_term(TARGET_CATEGORY, "categories")
tag_ids = []
for tag in TARGET_TAGS:
    t_id = get_or_create_wp_term(tag, "tags")
    if t_id: tag_ids.append(t_id)

# =====================================================================
# 🚀 [Step 5] 최종 포스팅 발행
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
        print("  🎉 [발행 대성공!] 글과 이미지가 정상 발행되었습니다.")
        worksheet.update_cell(target_row_index, 1, "완료")
    else:
        print(f"  ❌ 발행 실패: {post_res.text}")
except Exception as e:
    print(f"  ❌ 최종 발행 중 에러 발생: {e}")
