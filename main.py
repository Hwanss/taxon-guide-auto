import os
import gspread
import requests
import google.generativeai as genai
import json
import time
import datetime
from requests.auth import HTTPBasicAuth
from oauth2client.service_account import ServiceAccountCredentials

# 깃허브 비밀 금고(Secrets)에서 안전하게 정보 불러오기
WP_USER_EMAIL = os.environ["WP_USER_EMAIL"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"] 
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]
SHEET_ID = '1l8prCSHVmsQr7PQpuzMq8DYjpN-glyNg2n0iJ_-9wrs'
json_keyfile = 'gcp_key.json'

WP_URL = "https://" + "core-briefman.com/wp-json/wp/v2"
UNSPLASH_URL = "https://" + "api.unsplash.com/search/photos"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(json_keyfile, SCOPES)
sheet = gspread.authorize(creds).open_by_key(SHEET_ID).sheet1

def get_category_id(slug):
    if not slug: return 1
    try:
        # 타임아웃 30초 설정
        res = requests.get(f"{WP_URL}/categories?slug={slug}", auth=HTTPBasicAuth(WP_USER_EMAIL, WP_APP_PASSWORD), timeout=30)
        if res.status_code == 200 and len(res.json()) > 0:
            return res.json()[0]['id']
    except: pass
    return 1 

def get_tag_ids(tags_list):
    tag_ids = []
    for tag_name in tags_list:
        if not tag_name: continue
        try:
            res = requests.get(f"{WP_URL}/tags?search={tag_name.strip()}", auth=HTTPBasicAuth(WP_USER_EMAIL, WP_APP_PASSWORD), timeout=30)
            if res.status_code == 200 and len(res.json()) > 0:
                tag_ids.append(res.json()[0]['id'])
            else: 
                new_tag = requests.post(f"{WP_URL}/tags", auth=HTTPBasicAuth(WP_USER_EMAIL, WP_APP_PASSWORD), json={"name": tag_name.strip()}, timeout=30)
                if new_tag.status_code == 201:
                    tag_ids.append(new_tag.json()['id'])
        except: pass
    return tag_ids

print("🚀 [깃허브 자동 발행 시스템] 실행...")
data = sheet.get_all_records()

for i, row in enumerate(data):
    if row.get('A (상태)') == '대기':
        topic = row.get('B (주제)')
        img_keyword = row.get('D (이미지 키워드)')
        category_slug = str(row.get('슬러그', '')).strip()

        print(f"\n✍️ [작성 준비] '{topic}'")
        
        current_year = datetime.datetime.now().year
        
        prompt = f"""주제: {topic}
위 주제로 블로그에 올릴 전문적인 정보성 글을 작성해줘. 
현재 시점은 {current_year}년입니다. 글을 작성할 때 반드시 {current_year}년 최신 트렌드와 기술 기준에 맞춰 작성하고, 2024년 등 과거를 현재인 것처럼 묘사하지 마세요.
반드시 아래의 JSON 형식으로만 답변을 출력해. 마크다운 기호 없이 순수 JSON 구조만 출력해줘.
{{
    "content": "블로그 본문 내용 (HTML 태그 <p>, <h2> 등을 활용해서 가독성 좋게, 깊이 있게 작성)",
    "excerpt": "글의 내용을 요약한 2줄짜리 요약문",
    "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""
        
        ai_data = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                clean_res = response.text.replace("```json", "").replace("```", "").strip()
                ai_data = json.loads(clean_res)
                print("✅ AI 원고 및 태그 생성 완료")
                break
            except Exception as e:
                print(f"⚠️ AI 작성 에러 발생 (시도 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("⏰ 15초 대기 후 재시도합니다...")
                    time.sleep(15)
                else:
                    print("❌ 최종 실패. 건너뜁니다.")
        
        if not ai_data:
            break

        images_data = []
        if UNSPLASH_ACCESS_KEY and img_keyword:
            try:
                # 이미지 검색에도 타임아웃 추가
                res = requests.get(UNSPLASH_URL, params={"query": img_keyword, "client_id": UNSPLASH_ACCESS_KEY, "per_page": 3}, timeout=30).json()
                if 'results' in res:
                    for item in res['results']:
                        images_data.append(item['urls']['regular'])
            except: pass

        media_id = None
        if len(images_data) > 0:
            try:
                img_binary = requests.get(images_data[0], timeout=30).content
                media_res = requests.post(f"{WP_URL}/media", 
                                          auth=HTTPBasicAuth(WP_USER_EMAIL, WP_APP_PASSWORD),
                                          headers={"Content-Disposition": "attachment; filename=featured.jpg", "Content-Type": "image/jpeg"},
                                          data=img_binary,
                                          timeout=60) # 이미지 업로드는 60초 넉넉하게 대기
                if media_res.status_code == 201:
                    media_id = media_res.json()['id']
                    print("✅ 썸네일 등록 완료")
            except: pass

        raw_content = ai_data.get('content', '')
        final_content = ""
        
        if raw_content:
            paragraphs = [p + "</p>" for p in raw_content.split("</p>") if p.strip() != ""]
            total_p = len(paragraphs)
            img_idx = 1 
            
            for idx, p in enumerate(paragraphs):
                final_content += p + "\n"
                
                if img_idx < len(images_data) and total_p >= 3:
                    insert_point = (total_p // len(images_data)) * img_idx
                    if idx == insert_point:
                        img_url = images_data[img_idx]
                        final_content += f"\n<figure style='margin: 35px 0; text-align: center;'><img src='{img_url}' alt='{topic} 관련 이미지 {img_idx}' style='width:100%; max-width:800px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);'></figure>\n\n"
                        img_idx += 1
        else:
            final_content = raw_content

        cat_id = get_category_id(category_slug)
        tag_ids = get_tag_ids(ai_data.get('tags', []))

        post_payload = {
            'title': topic,
            'content': final_content,
            'excerpt': ai_data.get('excerpt', ''),
            'status': 'publish',
            'categories': [cat_id],
            'tags': tag_ids
        }
        if media_id: post_payload['featured_media'] = media_id

        # --- 🌐 워드프레스 발행 재시도 및 타임아웃 로직 ---
        wp_max_retries = 3
        wp_success = False

        for attempt in range(wp_max_retries):
            try:
                # timeout=30 추가로 30초 이상 서버가 대답 없으면 에러 발생 후 재시도
                res = requests.post(f"{WP_URL}/posts", auth=HTTPBasicAuth(WP_USER_EMAIL, WP_APP_PASSWORD), json=post_payload, timeout=30)
                
                if res.status_code == 201:
                    sheet.update_cell(i + 2, 1, '완료')
                    print(f"🎉 워드프레스 발행 완료: {topic} (이미지 {len(images_data)}장 적용)")
                    wp_success = True
                    break
                else:
                    print(f"❌ 발행 실패 (응답 코드: {res.status_code}) - {res.text}")
                    time.sleep(10)
            except Exception as e:
                print(f"⚠️ 워드프레스 서버 통신 에러 (시도 {attempt+1}/{wp_max_retries}): {e}")
                if attempt < wp_max_retries - 1:
                    print("⏰ 호스팅 서버가 응답하지 않습니다. 15초 후 다시 노크합니다...")
                    time.sleep(15)
                
        if not wp_success:
            print("❌ 워드프레스 서버 문제로 최종 발행에 실패했습니다. (다음 스케줄에 재시도)")
            
        break 

print("종료합니다.")
