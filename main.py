import os
import requests
import json
import warnings
import re
import time  # 🔥 [추가] 사람처럼 천천히 행동하기 위한 시간 모듈
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

TARGET_SPECIES = "Tyrannosaurus rex"
TARGET_CATEGORY = "Extreme Survivors / 극한의 생존자"
TARGET_TAGS = ["공룡", "Dinosaur", "티라노사우루스", "고생물학"]

print("="*60)
print(f"🚀 [TaxonGuru] 딥다이브 공장 가동: {TARGET_SPECIES}")
print("="*60)

# =====================================================================
# 🛠️ [Helper] 카테고리/태그 ID 검색 (디도스 오해 방지를 위한 휴식 포함)
# =====================================================================
def get_or_create_wp_term(term_name, taxonomy="categories"):
    url = f"{WP_URL}/{taxonomy}"
    time.sleep(3) # 🔥 봇 차단 방지: 한 번 통신할 때마다 3초씩 대기
    try:
        search_res = requests.get(url, params={"search": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if search_res.status_code == 200:
            for item in search_res.json():
                if item['name'].lower() == term_name.lower():
                    return item['id']
        
        time.sleep(2) # 🔥 생성 전 2초 대기
        create_res = requests.post(url, json={"name": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if create_res.status_code == 201:
            print(f"  ✨ 새 {taxonomy} 생성됨: {term_name}")
            return create_res.json()['id']
    except Exception as e:
        print(f"  ⚠️ {taxonomy} 처리 중 에러 ({term_name}): {e}")
    return None

# =====================================================================
# 🔍 [Step 1] 위키미디어 이미지
# =====================================================================
wiki_url = "https://en.wikipedia.org/w/api.php"
wiki_params = {"action": "query", "titles": TARGET_SPECIES, "prop": "pageimages", "format": "json", "pithumbsize": "800", "redirects": "1"}
wiki_image_url = ""
try:
    wiki_res = requests.get(wiki_url, params=wiki_params, headers=common_headers, timeout=30)
    pages = wiki_res.json()['query']['pages']
    for page_id in pages:
        if 'thumbnail' in pages[page_id]:
            wiki_image_url = pages[page_id]['thumbnail']['source']
            break
except Exception:
    pass

# =====================================================================
# 🎨 [Step 2] DALL-E 썸네일
# =====================================================================
dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", prompt=f"A highly detailed, cinematic 3D illustration of a {TARGET_SPECIES}. National Geographic style.",
        size="1024x1024", quality="standard", n=1
    )
    dalle_image_url = image_response.data[0].url
except Exception as e:
    print(f"  ❌ DALL-E 썸네일 대기 중: {e}")

# =====================================================================
# ✍️ [Step 3] AI 본문 작성
# =====================================================================
print("\n[Step 3] 본문 작성 중...")
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = f"너는 'TaxonGuru' 블로그 에디터야. {TARGET_SPECIES}에 대해 5단 구조를 한국어/영어 듀얼 포맷으로 작성해. 앞뒤에 ```html 기호 쓰지마."

try:
    response = model.generate_content(prompt)
    blog_content = response.text
    blog_content = re.sub(r'^```(html)?\s*', '', blog_content, flags=re.IGNORECASE)
    blog_content = re.sub(r'```\s*$', '', blog_content).strip()
except Exception:
    blog_content = f"<h2>{TARGET_SPECIES}</h2><p>본문 생성 에러</p>"

if wiki_image_url:
    image_html = f'<figure style="text-align: center; margin: 20px 0;"><img src="{wiki_image_url}" alt="{TARGET_SPECIES}" style="max-width: 100%; border-radius: 8px;"></figure>'
    if "Anatomy" in blog_content:
        blog_content = blog_content.replace("Anatomy", f"Anatomy</br>{image_html}", 1)
    else:
        blog_content = image_html + "<br>" + blog_content

# =====================================================================
# 🌐 [Step 4] 미디어 업로드 및 카테고리 매핑
# =====================================================================
media_id = None
if dalle_image_url:
    try:
        img_data = requests.get(dalle_image_url, timeout=30).content
        media_headers = common_headers.copy()
        media_headers.update({'Content-Type': 'image/jpeg', 'Content-Disposition': f'attachment; filename="{TARGET_SPECIES}_TaxonGuru.jpg"'})
        time.sleep(3) # 🔥 봇 차단 방지
        media_res = requests.post(f"{WP_URL}/media", headers=media_headers, auth=(WP_USER, WP_APP_PASSWORD), data=img_data, timeout=60)
        if media_res.status_code == 201: media_id = media_res.json().get('id')
    except Exception:
        pass

print("\n[Step 4.5] 카테고리 및 태그 매핑 중 (천천히 진행됩니다)...")
category_id = get_or_create_wp_term(TARGET_CATEGORY, "categories")
tag_ids = []
for tag in TARGET_TAGS:
    t_id = get_or_create_wp_term(tag, "tags")
    if t_id: tag_ids.append(t_id)

# =====================================================================
# 🚀 [Step 5] 최종 발행
# =====================================================================
print("\n[Step 5] 최종 발행 중...")
time.sleep(4) # 🔥 최종 발행 전 4초 대기 (가장 중요)

post_data = {"title": f"[딥다이브] {TARGET_SPECIES}", "content": blog_content, "status": "publish"}
if media_id: post_data["featured_media"] = media_id
if category_id: post_data["categories"] = [category_id]
if tag_ids: post_data["tags"] = tag_ids

try:
    post_res = requests.post(f"{WP_URL}/posts", headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), json=post_data, timeout=60)
    if post_res.status_code == 201:
        print("  🎉 [발행 대성공!] 카테고리와 태그가 완벽하게 적용되었습니다.")
    else:
        print(f"  ❌ 발행 실패: {post_res.text}")
except Exception as e:
    print(f"  ❌ 워드프레스 통신 치명적 에러: {e}")
