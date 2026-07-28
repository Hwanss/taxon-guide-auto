from __future__ import annotations

import html
import os
import sys
from typing import Any

import requests

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
WP_URL = f"{WP_SITE_URL}/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "admin@taxonguru.com")
PAGE_STATUS = os.getenv("SITE_PAGES_STATUS", "draft")  # 검토 전 공개 방지를 위해 draft 기본값

session = requests.Session()
session.headers.update({"User-Agent": f"TaxonGuruSiteSetup/2.0 ({CONTACT_EMAIL})", "Accept": "application/json"})
auth = (WP_USER, WP_APP_PASSWORD)


def request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    response = session.request(method, f"{WP_URL}/{endpoint}", auth=auth, timeout=45, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {endpoint} 실패: {response.status_code} {response.text[:500]}")
    return response


def upsert_page(title: str, slug: str, content: str) -> dict[str, Any]:
    existing: list[dict[str, Any]] = []
    for status in ["draft", "pending", "publish", "future", "private"]:
        found = request(
            "GET",
            "pages",
            params={"slug": slug, "context": "edit", "status": status, "per_page": 10},
        ).json()
        if found:
            existing = found
            break
    payload = {"title": title, "slug": slug, "content": content, "status": PAGE_STATUS}
    if existing:
        return request("POST", f"pages/{existing[0]['id']}", json=payload).json()
    return request("POST", "pages", json=payload).json()


def main() -> int:
    email = html.escape(CONTACT_EMAIL)
    pages = [
        (
            "TaxonGuru 소개",
            "about-taxonguru",
            """
<h2>TaxonGuru가 하는 일</h2>
<p>TaxonGuru는 생물의 분류, 진화, 생태, 크기를 독자가 확인 가능한 자료와 함께 설명하는 자연과학 편집 프로젝트입니다.</p>
<h2>콘텐츠 원칙</h2>
<ul><li>학명과 분류를 먼저 확인합니다.</li><li>주요 사실은 원문 출처와 연결합니다.</li><li>확정 사실과 논쟁 중인 주장을 구분합니다.</li><li>오류가 확인되면 수정 기록을 남깁니다.</li></ul>
<p>운영자 소개와 실제 경력·전문 분야는 사실에 맞게 이 문단에 직접 추가해 주세요. 확인할 수 없는 학위나 직함은 사용하지 않습니다.</p>
""",
        ),
        (
            "편집 및 팩트체크 정책",
            "editorial-policy",
            f"""
<h2>자료 우선순위</h2>
<p>정부기관, 대학·박물관, 과학 데이터베이스, 학술논문을 우선하며, 일반 백과사전은 탐색 보조자료로 사용합니다.</p>
<h2>검수 및 발행 절차</h2>
<ol><li>AI가 조사 자료를 구조화하고 초안을 만듭니다.</li><li>자동 검수 단계에서 출처 수, 인용 표시, 근거 없는 주장과 사실 충돌을 점검합니다.</li><li>기준을 통과한 글은 예약 발행될 수 있으며, 기준 미달 글은 비공개 초안으로 보관합니다.</li><li>모든 글이 공개 전에 사람의 개별 검수를 거치는 것은 아니며, 운영자는 정기적인 표본 점검과 오류 제보를 통해 수정합니다.</li></ol>
<h2>정정 정책</h2>
<p>오류 제보는 <a href="mailto:{email}">{email}</a>로 보내 주세요. 확인된 오류는 가능한 한 신속히 수정하고 필요한 경우 수정일과 사유를 표시합니다.</p>
""",
        ),
        (
            "AI 활용 정책",
            "ai-use-policy",
            """
<h2>AI가 하는 일</h2>
<p>TaxonGuru는 주제 탐색, 자료 정리, 초안 작성, 문장 검수에 생성형 AI를 보조적으로 사용합니다.</p>
<h2>자동 발행 범위</h2>
<p>출처와 품질 기준을 통과한 글은 WordPress 예약 발행으로 자동 등록될 수 있습니다. 자동 기준을 통과하지 못한 글은 공개하지 않고 초안으로 저장합니다. 모든 게시물이 사람의 개별 사전 검수를 거치는 것은 아닙니다.</p>
<h2>책임과 한계</h2>
<p>운영자는 자동화 결과를 정기적으로 점검하고 오류 제보를 반영합니다. AI가 만든 가상 경력이나 전문가 직함은 사용하지 않습니다.</p>
<h2>AI 이미지</h2>
<p>AI 생성 이미지를 사용할 때에는 실제 관찰 사진이 아닌 설명용 이미지임을 캡션에 표시합니다.</p>
""",
        ),
        (
            "문의 및 오류 제보",
            "contact-and-corrections",
            f"""
<h2>문의</h2><p>콘텐츠 오류, 저작권, 이미지 출처, 협업 문의: <a href="mailto:{email}">{email}</a></p>
<h2>오류 제보 시 포함할 내용</h2><ul><li>문제가 있는 글의 주소</li><li>수정이 필요한 문장</li><li>근거가 되는 원문 주소 또는 설명</li></ul>
""",
        ),
        (
            "개인정보처리방침",
            "privacy-policy",
            f"""
<p><strong>중요:</strong> 이 문서는 초안입니다. 실제 사용 중인 분석 도구, 문의 양식, 쿠키, 광고 기능에 맞게 운영자가 검토한 뒤 공개해야 합니다.</p>
<h2>수집할 수 있는 정보</h2><p>방문 기록, 브라우저·기기 정보, 쿠키 정보와 사용자가 문의 과정에서 직접 제공한 정보가 포함될 수 있습니다.</p>
<h2>쿠키와 광고</h2><p>사이트가 Google AdSense 등 제3자 광고 서비스를 사용하게 되면 광고 제공업체가 쿠키를 사용하여 광고를 제공하거나 측정할 수 있습니다. 실제 광고 적용 전에 Google의 최신 필수 고지와 동의 관리 요건을 확인하여 이 문서를 갱신합니다.</p>
<h2>문의</h2><p>개인정보 관련 문의: <a href="mailto:{email}">{email}</a></p>
""",
        ),
    ]

    for title, slug, content in pages:
        page = upsert_page(title, slug, content.strip())
        print(f"✅ {title}: {page.get('status')} · {WP_SITE_URL}/wp-admin/post.php?post={page['id']}&action=edit")
    print("\n상단 메뉴와 푸터 연결은 WordPress 관리자 > 외모/사이트 편집기에서 직접 추가해 주세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
