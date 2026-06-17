import os
import requests
import json
from openai import OpenAI
import google.generativeai as genai

# --- [환경 변수 설정] ---
# GitHub Secrets에서 환경 변수 불러오기
WP_URL = "https://taxonguru.com/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# API 클라이언트 초기화
genai.configure(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 테스트용 타겟 생물 (하드코딩)
TARGET_SPECIES = "Tyrannosaurus rex"

print(f"🚀 [TaxonGuru] 하이브리드 & 다국어 딥다이브 공장 가동: {TARGET_SPECIES}")

# --- [Step 1] 위키미디어 본문 이미지 추출 (무료 & 팩트) ---
print("🔍 위키미디어 학술 이미지 검색 중...")
wiki_api_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={TARGET_SPECIES}&prop=pageimages&format=json&pithumbsize=800"
wiki_response = requests.get(wiki_api_url).json()
pages = wiki_response['query']['pages']
wiki_image_url = ""
for page_id in pages:
    if 'thumbnail' in pages[page_id]:
        wiki_image_url = pages[page_id]['thumbnail']['source']
        break

# --- [Step 2] DALL-E 3 썸네일 이미지 생성 (유쾌함 & 후킹) ---
print("🎨 DALL-E 3 썸네일 생성 중...")
dalle_prompt = f"A highly detailed, cinematic, and slightly humorous 3D illustration of a {TARGET_SPECIES}. National Geographic documentary style but with a fun, engaging twist to attract blog readers. High resolution."

image_response = openai_client.images.generate(
    model="dall-e-3",
    prompt=dalle_prompt,
    size="1024x1024",
    quality="standard",
    n=1,
)
dalle_image_url = image_response.data[0].url

# --- [Step 3] AI 딥다이브 본문 생성 (다국어 듀얼 포맷) ---
print("✍️ AI 딥다이브 본문 작성 중...")
model = genai.GenerativeModel('gemini-pro')
prompt = f"""
너는 'TaxonGuru'라는 전문적이고 유쾌한 생물학 블로그의 에디터야.
타겟 생물: {TARGET_SPECIES}

다음 5단 구조를 반드시 '한국어'와 '영어'가 교차하는 다국어 듀얼 포맷으로 작성해줘. 
(방식: 각 섹션이나 문단별로 한국어 설명을 먼저 적고, 그 바로 아래에 자연스러운 영어 번역을 배치할 것)

1. Hook: 흥미를 끄는 도발적 질문
2. Scientific Backbone: 분류 체계 표 (한/영 병기)
3. Deep Anatomy: 해부학적 특징
4. Evolutionary Context: 진화적 맥락
5. Verdict & Trivia: 재밌는 썰과 요약

문체: 인기 과학 유튜버처럼 찰진 비유와 유머러스한 톤을 섞어줘. HTML 형식으로 작성하되 <body> 태그 없이 내용만 출력해.
"""
response = model.generate_content(prompt)
blog_content = response.text

# 본문 중간에 위키미디어 팩트 이미지 HTML 삽입 (다국어 캡션 반영)
if wiki_image_url:
    image_html = f'<figure><img src="{wiki_image_url}" alt="{TARGET_SPECIES} 학술 자료"><figcaption>[학술 자료 / Academic Resource] {TARGET_SPECIES}의 실제 모습 및 골격도</figcaption></figure>'
    # Deep Anatomy 섹션 쯤에 이미지 삽입 (대략적인 분리 기준)
    blog_content = blog_content.replace("3. Deep Anatomy", f"3. Deep Anatomy<br>{image_html}<br>")

# --- [Step 4] 워드프레스 미디어 라이브러리에 DALL-E 이미지 업로드 ---
print("🌐 DALL-E 이미지를 워드프레스에 업로드 중...")
img_data = requests.get(dalle_image_url).content
media_headers = {
    'Content-Type': 'image/jpeg',
    'Content-Disposition': f'attachment; filename="{TARGET_SPECIES.replace(" ", "_")}_thumbnail.jpg"'
}
media_res = requests.post(
    f"{WP_URL}/media",
    headers=media_headers,
    auth=(WP_USER, WP_APP_PASSWORD),
    data=img_data
)
media_id = media_res.json().get('id')

# --- [Step 5] 워드프레스 최종 발행 ---
print("🚀 워드프레스에 최종 포스팅 전송 중...")
# 제목도 다국어 검색을 위해 한/영 병기로 수정했습니다.
post_title = f"[딥다이브] {TARGET_SPECIES}, 당신이 몰랐던 진짜 모습 | The True Face of {TARGET_SPECIES}"

post_data = {
    "title": post_title,
    "content": blog_content,
    "status": "publish",
    "featured_media": media_id # DALL-E 이미지를 대표(썸네일) 이미지로 설정
}

post_res = requests.post(
    f"{WP_URL}/posts",
    auth=(WP_USER, WP_APP_PASSWORD),
    json=post_data
)

if post_res.status_code == 201:
    print("✅ 발행 성공! 워드프레스를 확인해보세요.")
else:
    print(f"❌ 발행 실패: {post_res.status_code}")
    print(post_res.text)
