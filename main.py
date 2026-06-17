import os
import requests
import json
import warnings
from openai import OpenAI
import google.generativeai as genai

# =====================================================================
# 🛡️ [시스템 코어 설정 & 안전장치]
# =====================================================================

# 1. 호스팅어(Hostinger) 서버와의 고질적인 길찾기 에러(Errno 101) 원천 차단
# -> 파이썬이 최신 IPv6를 무시하고 가장 안정적인 구형(IPv4) 길로만 통신하도록 강제합니다.
import urllib3.util.connection as urllib3_cn
urllib3_cn.HAS_IPV6 = False

# 2. 콘솔 창을 지저분하게 만드는 파이썬 버전 경고 메시지(FutureWarning) 숨기기
warnings.filterwarnings("ignore", category=FutureWarning)

# 3. 환경 변수 (GitHub Secrets에서 안전하게 불러오기)
WP_URL = "https://taxonguru.com/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# 4. API 클라이언트 초기화
genai.configure(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 5. 워드프레스/위키미디어 방화벽의 '악성 봇 차단'을 우회하기 위한 신분증(User-Agent)
common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TaxonGuru-AutoBlogger/2.0"
}

# 테스트용 타겟 생물 (하후 시트와 연동될 변수)
TARGET_SPECIES = "Tyrannosaurus rex"

print("="*60)
print(f"🚀 [TaxonGuru] 하이브리드 다국어 딥다이브 공장 가동: {TARGET_SPECIES}")
print("="*60)


# =====================================================================
# 🔍 [Step 1] 위키미디어 학술 이미지 추출 (무료 & 팩트 검증용)
# =====================================================================
print("\n[Step 1] 위키미디어 학술 이미지 검색을 시작합니다...")
wiki_url = "https://en.wikipedia.org/w/api.php"
wiki_params = {
    "action": "query",
    "titles": TARGET_SPECIES,
    "prop": "pageimages",
    "format": "json",
    "pithumbsize": "800",
    "redirects": "1" # 철자가 살짝 틀려도 위키가 알아서 찾아주는 기능
}

wiki_image_url = ""
try:
    # 타임아웃을 60초로 넉넉하게 주어 연결 끊김을 방지합니다.
    wiki_res = requests.get(wiki_url, params=wiki_params, headers=common_headers, timeout=60)
    wiki_res.raise_for_status()
    wiki_response = wiki_res.json()
    
    pages = wiki_response['query']['pages']
    for page_id in pages:
        if 'thumbnail' in pages[page_id]:
            wiki_image_url = pages[page_id]['thumbnail']['source']
            break
            
    if wiki_image_url:
        print(f"  ✅ 위키미디어 이미지 확보 완료: {wiki_image_url}")
    else:
        print("  ⚠️ 위키미디어에 적합한 썸네일이 없습니다. (이미지 없이 계속 진행)")
except requests.exceptions.RequestException as e:
    print(f"  ❌ 위키미디어 통신 에러 발생 (본문 작성은 계속됩니다): {e}")


# =====================================================================
# 🎨 [Step 2] DALL-E 썸네일 이미지 생성 (시각적 후킹)
# =====================================================================
print("\n[Step 2] DALL-E 썸네일 이미지 생성을 요청합니다...")
dalle_prompt = f"A highly detailed, cinematic, and slightly humorous 3D illustration of a {TARGET_SPECIES}. National Geographic documentary style but with a fun, engaging twist to attract blog readers. High resolution, vibrant colors."

dalle_image_url = ""
try:
    image_response = openai_client.images.generate(
        model="dall-e-3", 
        prompt=dalle_prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    dalle_image_url = image_response.data[0].url
    print("  ✅ DALL-E 이미지 생성 완료!")
except Exception as e:
    print(f"  ❌ DALL-E 생성 실패 (API 권한 동기화 대기 중이거나 크레딧 부족): {e}")


# =====================================================================
# ✍️ [Step 3] AI 딥다이브 본문 작성 (Gemini 2.5 Flash 최적화)
# =====================================================================
print("\n[Step 3] 제미나이(Gemini) 본문 생성을 시작합니다...")
# 가성비와 속도가 가장 뛰어난 검증된 2.5 Flash 모델 사용!
model = genai.GenerativeModel('gemini-2.5-flash')
prompt = f"""
너는 'TaxonGuru'라는 전문적이고 유쾌한 생물학 블로그의 수석 에디터야.
타겟 생물: {TARGET_SPECIES}

다음 5단 구조를 반드시 '한국어' 설명 바로 아래에 '영어' 번역이 이어지는 '다국어 듀얼 포맷'으로 작성해줘. 

1. Hook: 독자의 흥미를 확 끄는 도발적인 질문이나 팩트
2. Scientific Backbone: 분류 체계 표 (계/문/강/목/과/속/종 - 한/영 병기)
3. Deep Anatomy: 해부학적 특징과 생존 무기
4. Evolutionary Context: 진화적 맥락과 역사
5. Verdict & Trivia: 에디터의 한 줄 평 및 재밌는 썰

문체: 인기 과학 유튜버처럼 찰진 비유와 유머러스한 톤을 섞어줘. 전문 용어는 쉽게 풀어서 설명할 것.
출력 형식: HTML 코드로 작성하되, HTML 뼈대(<html>, <body> 태그 등)는 제외하고 순수 내용물(h2, h3, p, ul, table 태그 등)만 출력해.
"""

blog_content = ""
try:
    response = model.generate_content(prompt)
    blog_content = response.text
    print("  ✅ 제미나이 딥다이브 본문 작성 완료!")
except Exception as e:
    print(f"  ❌ 제미나이 본문 생성 에러 발생: {e}")
    blog_content = f"<h2>{TARGET_SPECIES}</h2><p>본문 생성에 실패했습니다. 관리자에게 문의하세요.</p>"

# 위키미디어에서 가져온 팩트 이미지가 있다면, 본문의 'Deep Anatomy' 섹션 아래에 자연스럽게 삽입
if wiki_image_url and "3. Deep Anatomy" in blog_content:
    print("  🔗 본문에 위키미디어 학술 이미지를 결합합니다.")
    image_html = f'''
    <figure style="text-align: center; margin: 20px 0;">
        <img src="{wiki_image_url}" alt="{TARGET_SPECIES} 학술 자료" style="max-width: 100%; height: auto; border-radius: 8px;">
        <figcaption style="font-size: 0.9em; color: #666; margin-top: 8px;">[학술 자료 / Academic Resource] {TARGET_SPECIES}의 실제 모습 및 관련 골격도</figcaption>
    </figure>
    '''
    blog_content = blog_content.replace("3. Deep Anatomy", f"3. Deep Anatomy<br>{image_html}<br>")


# =====================================================================
# 🌐 [Step 4] 워드프레스에 DALL-E 이미지 업로드 (미디어 라이브러리)
# =====================================================================
media_id = None
if dalle_image_url:
    print("\n[Step 4] 생성된 DALL-E 썸네일을 워드프레스에 업로드합니다...")
    try:
        # 1. DALL-E 서버에서 이미지 다운로드
        img_data = requests.get(dalle_image_url, timeout=60).content
        
        # 2. 워드프레스 전송용 헤더 세팅
        media_upload_headers = common_headers.copy()
        media_upload_headers.update({
            'Content-Type': 'image/jpeg',
            'Content-Disposition': f'attachment; filename="{TARGET_SPECIES.replace(" ", "_")}_TaxonGuru.jpg"'
        })
        
        # 3. 워드프레스 서버로 업로드 발사 (호스팅어 타임아웃 고려하여 120초 넉넉히 부여)
        media_res = requests.post(
            f"{WP_URL}/media",
            headers=media_upload_headers,
            auth=(WP_USER, WP_APP_PASSWORD),
            data=img_data,
            timeout=120
        )
        
        if media_res.status_code == 201:
            media_id = media_res.json().get('id')
            print(f"  ✅ 썸네일 업로드 성공! (Media ID: {media_id})")
        else:
            print(f"  ⚠️ 미디어 업로드 실패 (HTTP {media_res.status_code}): {media_res.text}")
    except Exception as e:
        print(f"  ⚠️ 워드프레스 이미지 업로드 에러 (글은 썸네일 없이 발행됩니다): {e}")


# =====================================================================
# 🚀 [Step 5] 워드프레스 최종 글 발행
# =====================================================================
print("\n[Step 5] 딥다이브 포스팅을 워드프레스에 최종 발행합니다...")
post_title = f"[딥다이브] {TARGET_SPECIES}, 당신이 몰랐던 진짜 모습 | The True Face of {TARGET_SPECIES}"

# 발행할 데이터 포장
post_data = {
    "title": post_title,
    "content": blog_content,
    "status": "publish" # 초안은 "draft", 즉시 발행은 "publish"
}

# 썸네일이 정상적으로 올라갔다면 대표 이미지(Featured Media)로 설정
if media_id:
    post_data["featured_media"] = media_id

try:
    # 최종 전송 발사 (타임아웃 120초)
    post_res = requests.post(
        f"{WP_URL}/posts",
        headers=common_headers,
        auth=(WP_USER, WP_APP_PASSWORD),
        json=post_data,
        timeout=120
    )

    if post_res.status_code == 201:
        print("  🎉 [발행 대성공!] 워드프레스 사이트에 접속하여 첫 글을 확인해 보세요!")
    else:
        print(f"  ❌ 발행 실패 (HTTP {post_res.status_code}): {post_res.text}")
        
except Exception as e:
    print(f"  ❌ 워드프레스 통신 중 치명적 에러 발생: {e}")

print("="*60)
print("🏁 TaxonGuru 자동화 프로세스가 모두 종료되었습니다.")
print("="*60)
