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
print("📊 [TaxonGuru] 스마트 시트 연동 & 유머러스 딥다이브 공장 가동")
print("="*60)

# =====================================================================
# 📋 [Step 0] 구글 시트에서 '대기' 항목 가져오기
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
        
    TARGET_SPECIES = target_data[1].strip()
    TARGET_CATEGORY = target_data[2].strip()
    IMAGE_KEYWORD = target_data[3].strip() if len(target_data) > 3 else "nature"
    TARGET_TAGS = [TARGET_CATEGORY, "생물학", "꿀잼종족", TARGET_SPECIES.split()[0]]

    print(f"🎯 이번 타겟 주제: {TARGET_SPECIES}")
    
except Exception as e:
    print(f"❌ 구글 시트 접근 실패: {e}")
    exit(1)

# =====================================================================
# 🔍 [Step 1] 위키미디어에서 다중 이미지(최대 3장) 주소 추출
# =====================================================================
print("\n[Step 1] 위키미디어에서 본문용 이미지들을 수집합니다...")
wiki_url = "https://en.wikipedia.org/w/api.php"
wiki_params = {
    "action": "query",
    "titles": TARGET_SPECIES,
    "generator": "images",
    "gimlimit": "15",
    "prop": "imageinfo",
    "iiprop": "url",
    "format": "json",
    "redirects": "1"
}

wiki_images = []
try:
    wiki_res = requests.get(wiki_url, params=wiki_params, headers=common_headers, timeout=30)
    pages = wiki_res.json().get("query", {}).get("pages", {})
    for pid, pdata in pages.items():
        if "imageinfo" in pdata:
            img_url = pdata["imageinfo"][0]["url"]
            # 아이콘이나 로고, 쓸데없는 svg 파일 필터링하고 선명한 jpg/png만 수집
            if any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                if "logo" not in img_url.lower() and "icon" not in img_url.lower():
                    wiki_images.append(img_url)
    print(f"  ✅ 유효한 학술 이미지 {len(wiki_images)}장 확보!")
except Exception:
    print("  ⚠️ 위키미디어 이미지 수집 실패 (이미지 없이 진행)")

# =====================================================================
# 🎨 [Step 2] DALL-E 썸네일 이미지 생성
# =====================================================================
dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", 
        prompt=f"A vibrant, cinematic 3D illustration representing: {IMAGE_KEYWORD}. High resolution, eye-catching blog thumbnail style.",
        size="1024x1024", quality="standard", n=1
    )
    dalle_image_url = image_response.data[0].url
except Exception:
    pass

# =====================================================================
# ✍️ [Step 3] 꿀잼 유머 감성 + 한/영 완전 분리 본문 작성 (Gemini 2.5 Flash)
# =====================================================================
print("\n[Step 3] 제미나이가 약 빨고 찰진 드립으로 글을 쓰는 중...")
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = f"""
너는 대한민국에서 가장 유쾌하고 드립력 좋은 스타 과학 유튜버이자 블로그 에디터야. 
오늘 독파할 주제: "{TARGET_SPECIES}"

[반드시 지켜야 할 철칙 가이드라인]
1. 문체 및 드립 (노잼 진지체 절대 금지):
   - 딱딱한 정보 나열은 가라! 독자가 읽다가 웃겨서 침 뱉을 정도로 유쾌하고 찰진 비유, 드립, 인터넷 밈을 팍팍 섞어줘.
   - 친근한 대화체(~했답니다, ~였던 것입니다!, 대박이지 않나요?)를 사용해줘.
2. 완벽한 한/영 구조 분리:
   - 절대로 한 줄씩 한/영 번역을 번갈아 쓰지 마! 가독성 완전히 깨집니다.
   - [1부: 내 영혼을 갈아 넣은 한국어 버전] 도입부(Hook)부터 드립 가득한 본론, 결론까지 오직 한국어로만 먼저 쭉 완성해.
   - [2부: Global Readers English Version] 한국어 본문이 완벽히 끝나면, 맨 아래에 전체 내용을 깔끔하게 영어로 번역해서 이어 붙여줘.
3. 이미지 들어갈 명당 배치:
   - 본문 중간중간 어울리는 맥락에 정확히 `[WIKI_IMAGE_1]`, `[WIKI_IMAGE_2]` 라는 글자를 태그처럼 본문 HTML 안에 삽입해줘. 파이썬이 그 자리에 사진을 꽂을 거야.
4. 출력 형식:
   - 순수 HTML 내용물(h2, h3, p, ul, table 등)만 출력하고 앞뒤에 ```html 기호는 절대로 넣지 마.
"""

try:
    response = model.generate_content(prompt)
    blog_content = response.text
    blog_content = re.sub(r'^```(html)?\s*', '', blog_content, flags=re.IGNORECASE)
    blog_content = re.sub(r'```\s*$', '', blog_content).strip()
except Exception:
    blog_content = f"<h2>{TARGET_SPECIES}</h2><p>본문 생성 실패</p>"

# 🧩 확보한 위키미디어 이미지들을 제미나이가 지정한 명당 자리에 순서대로 치환
if wiki_images:
    for idx, img_url in enumerate(wiki_images[:3]):
        placeholder = f"[WIKI_IMAGE_{idx+1}]"
        image_html = f'''
        <figure style="text-align: center; margin: 30px 0;">
            <img src="{img_url}" alt="{TARGET_SPECIES} 자료 사진" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
            <figcaption style="font-size: 0.85em; color: #666; margin-top: 8px;">✨ 생생한 현장 포착 자료화면</figcaption>
        </figure>
        '''
        if placeholder in blog_content:
            blog_content = blog_content.replace(placeholder, image_html)
        else:
            # 혹시 태그를 안 적어줬다면 본문 맨 뒤에 보너스로 추가
            blog_content += "<br>" + image_html

# 남아있는 안 쓴 이미지 태그 깔끔하게 청소
blog_content = re.sub(r'\[WIKI_IMAGE_\d+\]', '', blog_content)

# =====================================================================
# 🌐 [Step 4] 미디어 업로드 및 카테고리/태그 매핑 (천천히 봇 차단 방지)
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

media_id = None
if dalle_image_url:
    try:
        img_data = requests.get(dalle_image_url, timeout=30).content
        media_headers = common_headers.copy()
        media_headers.update({'Content-Type': 'image/jpeg', 'Content-Disposition': 'attachment; filename="thumb.jpg"'})
        time.sleep(3)
        media_res = requests.post(f"{WP_URL}/media", headers=media_headers, auth=(WP_USER, WP_APP_PASSWORD), data=img_data, timeout=60)
        if media_res.status_code == 201: media_id = media_res.json().get('id')
    except Exception: pass

print("\n[Step 4] 카테고리 및 태그 안전 매핑 중...")
category_id = get_or_create_wp_term(TARGET_CATEGORY, "categories")
tag_ids = []
for tag in TARGET_TAGS:
    t_id = get_or_create_wp_term(tag, "tags")
    if t_id: tag_ids.append(t_id)

# =====================================================================
# 🚀 [Step 5] 최종 포스팅 발행 및 시트 '완료' 업데이트
# =====================================================================
print("\n[Step 5] 워드프레스에 최종 발행 요청을 보냅니다...")
time.sleep(4)

post_data = {
    "title": f"[딥다이브] {TARGET_SPECIES}의 숨겨진 반전 스펙 알아보기",
    "content": blog_content,
    "status": "publish"
}
if media_id: post_data["featured_media"] = media_id
if category_id: post_data["categories"] = [category_id]
if tag_ids: post_data["tags"] = tag_ids

try:
    post_res = requests.post(f"{WP_URL}/posts", headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), json=post_data, timeout=60)
    if post_res.status_code == 201:
        print("  🎉 [발행 대성공!] 글, 카테고리, 다중 이미지가 완벽히 박혔습니다.")
        # 시트 상태 업데이트
        worksheet.update_cell(target_row_index, 1, "완료")
        print(f"  📝 구글 시트 {target_row_index}행의 상태를 '완료'로 변경했습니다.")
    else:
        print(f"  ❌ 발행 실패: {post_res.text}")
except Exception as e:
    print(f"  ❌ 최종 발행 중 에러 발생: {e}")
