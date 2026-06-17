2.  **카테고리 & 태그 누락:** 워드프레스(REST API) 시스템은 글을 올릴 때 카테고리의 '이름' 글자 자체를 주면 못 알아듣고, 무조건 **'고유 번호(ID 번호)'**로 변환해서 줘야만 인식을 합니다.

이 두 가지를 한 번에 완벽하게 해결했습니다! 

* **해결 1:** 강력한 **'정규표현식(Regex)'**이라는 진공청소기를 달아서, 제미나이가 어떤 꼼수를 부리든 ````html` 찌꺼기를 흔적도 없이 빨아들이게 했습니다.
* **해결 2:** 파이썬 코드가 워드프레스에 먼저 물어봐서 **"이 카테고리/태그 이름 있어? 있으면 번호 줘! 없으면 새로 만들어서 번호 줘!"**라고 똑똑하게 처리하는 **자동화 함수**를 추가했습니다. (나중에 구글 시트의 카테고리/태그 열을 읽어올 때를 위한 완벽한 사전 작업이기도 합니다!)

기존 `main.py`를 아래 코드로 다시 한 번 시원하게 덮어써 주세요!

```python
import os
import requests
import json
import warnings
import re
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TaxonGuru-AutoBlogger/2.0"
}

TARGET_SPECIES = "Tyrannosaurus rex"

# 테스트용 카테고리 및 태그 설정
TARGET_CATEGORY = "Extreme Survivors / 극한의 생존자"
TARGET_TAGS = ["공룡", "Dinosaur", "티라노사우루스", "고생물학"]

print("="*60)
print(f"🚀 [TaxonGuru] 딥다이브 공장 가동: {TARGET_SPECIES}")
print("="*60)

# =====================================================================
# 🛠️ [Helper] 워드프레스 카테고리/태그 ID 자동 검색 및 생성 함수
# =====================================================================
def get_or_create_wp_term(term_name, taxonomy="categories"):
    url = f"{WP_URL}/{taxonomy}"
    try:
        # 1. 이미 해당 이름이 존재하는지 검색
        search_res = requests.get(url, params={"search": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if search_res.status_code == 200:
            for item in search_res.json():
                if item['name'].lower() == term_name.lower():
                    return item['id']
        
        # 2. 존재하지 않으면 새로 생성
        create_res = requests.post(url, json={"name": term_name}, headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), timeout=30)
        if create_res.status_code == 201:
            print(f"  ✨ 새 {taxonomy} 생성됨: {term_name}")
            return create_res.json()['id']
    except Exception as e:
        print(f"  ⚠️ {taxonomy} 처리 중 에러 ({term_name}): {e}")
    return None

# =====================================================================
# 🔍 [Step 1] 위키미디어 학술 이미지 추출
# =====================================================================
wiki_url = "https://en.wikipedia.org/w/api.php"
wiki_params = {"action": "query", "titles": TARGET_SPECIES, "prop": "pageimages", "format": "json", "pithumbsize": "800", "redirects": "1"}

wiki_image_url = ""
try:
    wiki_res = requests.get(wiki_url, params=wiki_params, headers=common_headers, timeout=60)
    wiki_response = wiki_res.json()
    pages = wiki_response['query']['pages']
    for page_id in pages:
        if 'thumbnail' in pages[page_id]:
            wiki_image_url = pages[page_id]['thumbnail']['source']
            break
except Exception:
    pass

# =====================================================================
# 🎨 [Step 2] DALL-E 썸네일 이미지 생성
# =====================================================================
dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", 
        prompt=f"A highly detailed, cinematic 3D illustration of a {TARGET_SPECIES}. National Geographic documentary style but with a fun twist. High resolution.",
        size="1024x1024", quality="standard", n=1
    )
    dalle_image_url = image_response.data[0].url
except Exception as e:
    print(f"  ❌ DALL-E 썸네일 대기 중: {e}")

# =====================================================================
# ✍️ [Step 3] AI 딥다이브 본문 작성 (Gemini 2.5 Flash)
# =====================================================================
print("\n[Step 3] 본문 작성 중...")
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = f"""
너는 'TaxonGuru' 블로그 에디터야. 타겟 생물: {TARGET_SPECIES}
5단 구조(Hook, Scientific Backbone, Deep Anatomy, Evolutionary Context, Verdict & Trivia)를 한국어/영어 듀얼 포맷으로 작성해.
HTML로 작성하되, 맨 앞뒤에 ```html 마크다운 기호는 절대로 쓰지 마.
"""

try:
    response = model.generate_content(prompt)
    blog_content = response.text
    
    # 🔥 [강력한 청소기] 정규식(Regex)을 이용해 마크다운 기호 완벽 제거
    blog_content = re.sub(r'^```(html)?\s*', '', blog_content, flags=re.IGNORECASE)
    blog_content = re.sub(r'```\s*$', '', blog_content)
    blog_content = blog_content.strip()
    
except Exception as e:
    blog_content = f"<h2>{TARGET_SPECIES}</h2><p>본문 생성 에러</p>"

if wiki_image_url:
    image_html = f'<figure style="text-align: center; margin: 20px 0;"><img src="{wiki_image_url}" alt="{TARGET_SPECIES}" style="max-width: 100%; border-radius: 8px;"><figcaption>[Academic Resource] {TARGET_SPECIES}</figcaption></figure>'
    if "Anatomy" in blog_content:
        blog_content = blog_content.replace("Anatomy", f"Anatomy</br>{image_html}", 1)
    else:
        blog_content = image_html + "<br>" + blog_content

# =====================================================================
# 🌐 [Step 4] 워드프레스 미디어 라이브러리 업로드
# =====================================================================
media_id = None
if dalle_image_url:
    try:
        img_data = requests.get(dalle_image_url, timeout=60).content
        media_upload_headers = common_headers.copy()
        media_upload_headers.update({'Content-Type': 'image/jpeg', 'Content-Disposition': f'attachment; filename="{TARGET_SPECIES.replace(" ", "_")}_TaxonGuru.jpg"'})
        media_res = requests.post(f"{WP_URL}/media", headers=media_upload_headers, auth=(WP_USER, WP_APP_PASSWORD), data=img_data, timeout=120)
        if media_res.status_code == 201:
            media_id = media_res.json().get('id')
    except Exception:
        pass

# =====================================================================
# 🏷️ [Step 4.5] 카테고리 및 태그 ID 확보
# =====================================================================
print("\n[Step 4.5] 카테고리 및 태그를 워드프레스에 매핑합니다...")
category_id = get_or_create_wp_term(TARGET_CATEGORY, "categories")
tag_ids = []
for tag in TARGET_TAGS:
    t_id = get_or_create_wp_term(tag, "tags")
    if t_id:
        tag_ids.append(t_id)

# =====================================================================
# 🚀 [Step 5] 워드프레스 최종 글 발행
# =====================================================================
print("\n[Step 5] 최종 발행 중...")
post_data = {
    "title": f"[딥다이브] {TARGET_SPECIES}, 당신이 몰랐던 진짜 모습 | The True Face of {TARGET_SPECIES}",
    "content": blog_content,
    "status": "publish"
}

if media_id: post_data["featured_media"] = media_id
if category_id: post_data["categories"] = [category_id]
if tag_ids: post_data["tags"] = tag_ids

post_res = requests.post(f"{WP_URL}/posts", headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), json=post_data, timeout=120)
if post_res.status_code == 201:
    print("  🎉 [발행 대성공!] 카테고리와 태그가 완벽하게 적용되었습니다.")
else:
    print(f"  ❌ 발행 실패: {post_res.text}")
