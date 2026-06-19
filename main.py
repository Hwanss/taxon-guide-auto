import os
import requests
import json
import warnings
import re
import time
import gspread
from openai import OpenAI
from google import genai 

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

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 워드프레스용 일반 헤더
common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

# 🔥 위키피디아 전용 공식 봇 헤더 (차단 회피용 신분증)
wiki_headers = {
    "User-Agent": "TaxonGuruBot/1.0 (https://taxonguru.com; admin@taxonguru.com)"
}

print("="*60)
print("📊 [TaxonGuru] WP 철통보안 & 위키 차단 우회 시스템 가동")
print("="*60)

# =====================================================================
# 📋 [Step 0] 구글 시트 정밀 매핑
# =====================================================================
try:
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sheet_id = os.environ["SHEET_ID"]
    
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
# 🔍 [Step 1] 위키미디어 이미지 수집 (공식 봇 헤더 사용)
# =====================================================================
wiki_url = "https://en.wikipedia.org/w/api.php"
wiki_params = {"action": "query", "titles": SCI_NAME, "generator": "images", "gimlimit": "10", "prop": "imageinfo", "iiprop": "url", "format": "json", "redirects": "1"}
wiki_images = []
try:
    wiki_res = requests.get(wiki_url, params=wiki_params, headers=wiki_headers, timeout=20)
    pages = wiki_res.json().get("query", {}).get("pages", {})
    for pid, pdata in pages.items():
        if "imageinfo" in pdata:
            img_url = pdata["imageinfo"][0]["url"]
            if any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]) and "logo" not in img_url.lower() and "icon" not in img_url.lower():
                wiki_images.append(img_url)
except Exception: pass

# =====================================================================
# 🎨 [Step 2] 썸네일 이미지 생성 시도 (4중 순위 기반 라우팅)
# =====================================================================
print("\n[Step 2] 썸네일 대표 이미지 준비 중 (4중 순위 안전장치 가동)...")
thumbnail_url = ""
is_dalle_success = False

# 🔥 해결책 1: AI 검열(방사능 등)을 피하기 위해 완전히 안전하고 아름다운 과학 일러스트로 프롬프트 전면 수정
safe_prompt = "A highly detailed, cinematic National Geographic style 3D macro photography of a beautiful glowing microscopic cell in nature, educational science illustration, completely safe abstract biology concept, 8k resolution."
dalle_prompt = "A cinematic, highly detailed 3D illustration of an abstract cellular organism, beautiful nature environment, dynamic lighting, 8k resolution."

# [1순위] gpt-image-2 시도
try:
    image_response = openai_client.images.generate(
        model="gpt-image-2", 
        prompt=safe_prompt,
        size="1024x1024", quality="auto", n=1
    )
    thumbnail_url = image_response.data[0].url
    is_dalle_success = True
    print("  ✅ [1순위 성공] gpt-image-2 썸네일 이미지 생성 완료!")
    
except Exception as e1:
    print(f"  ❌ 1순위(gpt-image-2) 실패: {e1}")
    print("  🔄 [2순위 가동] dall-e-3 엔진으로 전환하여 즉시 재시도합니다...")
    
    # [2순위] dall-e-3 시도
    try:
        image_response = openai_client.images.generate(
            model="dall-e-3", 
            prompt=dalle_prompt,
            size="1024x1024", quality="standard", n=1
        )
        thumbnail_url = image_response.data[0].url
        is_dalle_success = True
        print("  ✅ [2순위 성공] dall-e-3 썸네일 이미지 생성 완료!")
        
    except Exception as e2:
        print(f"  ❌ 2순위(dall-e-3) 실패: {e2}")
        print("  🔄 [3순위 가동] gpt-image-1 엔진으로 전환하여 즉시 재시도합니다...")
        
        # [3순위] gpt-image-1 시도
        try:
            image_response = openai_client.images.generate(
                model="gpt-image-1", 
                prompt=safe_prompt,
                size="1024x1024", quality="auto", n=1
            )
            thumbnail_url = image_response.data[0].url
            is_dalle_success = True
            print("  ✅ [3순위 성공] gpt-image-1 썸네일 이미지 생성 완료!")
            
        except Exception as e3:
            print(f"  ❌ 3순위(gpt-image-1) 실패: {e3}")
            print("  🔄 [4순위 가동] AI 생성 전원 실패. 위키미디어 사진으로 썸네일 대체를 준비합니다.")

# =====================================================================
# ✍️ [Step 3] 다큐 본문 작성 (제미나이 2.5 버전 환경 유지)
# =====================================================================
print("\n[Step 3] 스토리앵글 맞춤형 대본(본문) 작성 중 (제미나이 2.5 고정)...")

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
    response = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    blog_content = response.text
    blog_content = blog_content.replace("```html\n", "").replace("```html", "").replace("```\n", "").replace("```", "").strip()
except Exception as e:
    print(f"❌ 치명적 에러: 제미나이 본문 작성 도중 오류 발생: {e}")
    exit(1)

# 본문 사진 배치
body_images = wiki_images[1:] if (not is_dalle_success and wiki_images) else wiki_images

if body_images:
    for idx, img_url in enumerate(body_images[:3]):
        placeholder = f"[WIKI_IMAGE_{idx+1}]"
        image_html = f'<figure style="text-align: center; margin: 30px 0;"><img src="{img_url}" alt="{SCI_NAME} 관찰 사진" style="max-width: 100%; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);"><figcaption style="font-size: 0.85em; color: #666; margin-top: 8px;">📸 위키미디어 제공: 자연 상태의 {COMMON_NAME} 기록 사진</figcaption></figure>'
        if placeholder in blog_content:
            blog_content = blog_content.replace(placeholder, image_html)
        else:
            blog_content += "<br>" + image_html

for i in range(1, 4):
    blog_content = blog_content.replace(f"[WIKI_IMAGE_{i}]", "")

# =====================================================================
# 🌐 [Step 4] 미디어 업로드 (마법의 바이트 판독기 장착)
# =====================================================================
media_id = None
urls_to_try = [thumbnail_url] if is_dalle_success else wiki_images

print("\n[Step 4] 워드프레스에 썸네일 업로드 중...")
if not urls_to_try:
    print("  ⚠️ 업로드할 이미지 소스가 없습니다.")
else:
    for attempt_idx, url in enumerate(urls_to_try):
        if not url: continue
        try:
            img_res = requests.get(url, headers=wiki_headers if not is_dalle_success else common_headers, timeout=30)
            image_bytes = img_res.content
            
            # 🔥 해결책 2: 파일 내용물(Byte)을 직접 스캔하여 100% 정확한 확장자 부여
            if image_bytes.startswith(b'\x89PNG'):
                ext, mime_type = 'png', 'image/png'
            elif image_bytes.startswith(b'\xff\xd8'):
                ext, mime_type = 'jpg', 'image/jpeg'
            elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[8:12]:
                ext, mime_type = 'webp', 'image/webp'
            else:
                # 헤더 정보를 통한 최후의 보루
                actual_type = img_res.headers.get('Content-Type', '').lower()
                if 'webp' in actual_type: ext, mime_type = 'webp', 'image/webp'
                elif 'jpeg' in actual_type or 'jpg' in actual_type: ext, mime_type = 'jpg', 'image/jpeg'
                else: ext, mime_type = 'png', 'image/png'
                
            safe_slug = re.sub(r'[^a-zA-Z0-9]', '_', TARGET_SLUG)
            safe_filename = f"cover_{safe_slug}_{int(time.time())}.{ext}"
                
            media_headers = common_headers.copy()
            media_headers.update({
                'Content-Type': mime_type, 
                'Content-Disposition': f'attachment; filename="{safe_filename}"'
            })
            
            time.sleep(2)
            media_upload_res = requests.post(f"{WP_URL}/media", headers=media_headers, auth=(WP_USER, WP_APP_PASSWORD), data=image_bytes, timeout=60)
            
            if media_upload_res.status_code == 201: 
                media_id = media_upload_res.json().get('id')
                print(f"  ✅ 썸네일 업로드 성공! (Media ID: {media_id})")
                break 
            else:
                print(f"  ❌ 업로드 거부: 응답코드 {media_upload_res.status_code}, 상세이유: {media_upload_res.text[:100]}")
        except Exception as e: 
            print(f"  ❌ 썸네일 처리 중 통신 에러 발생: {e}")

    if not media_id:
        print("  ❌ 모든 썸네일 후보가 업로드에 실패했습니다. 썸네일 없이 발행합니다.")

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
    post_res = requests.post(f"{WP_URL}/posts", headers=common_headers, auth=(WP_USER, WP_APP_PASSWORD), json=post_data, timeout=120)
    if post_res.status_code == 201:
        print("  🎉 [발행 대성공!] 글과 이미지가 정상 발행되었습니다.")
        worksheet.update_cell(target_row_index, 1, "완료")
    else:
        print(f"  ❌ 발행 실패: {post_res.text}")
except Exception as e:
    print(f"  ❌ 최종 발행 중 에러 발생: {e}")
