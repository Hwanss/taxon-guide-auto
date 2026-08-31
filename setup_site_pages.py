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
PAGE_STATUS = os.getenv("SITE_PAGES_STATUS", "publish").strip() or "publish"
FORCE_UPDATE = os.getenv("SITE_PAGES_FORCE_UPDATE", "false").lower() == "true"
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))

session = requests.Session()
session.headers.update(
    {
        "User-Agent": f"TaxonGuruSiteSetup/6.0 ({CONTACT_EMAIL})",
        "Accept": "application/json",
    }
)
auth = (WP_USER, WP_APP_PASSWORD)


def request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    response = session.request(
        method,
        f"{WP_URL}/{endpoint}",
        auth=auth,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"{method} {endpoint} 실패: {response.status_code} {response.text[:500]}"
        )
    return response


def find_page(slug: str) -> dict[str, Any] | None:
    for status in ["draft", "pending", "publish", "future", "private"]:
        found = request(
            "GET",
            "pages",
            params={
                "slug": slug,
                "context": "edit",
                "status": status,
                "per_page": 10,
            },
        ).json()
        if found:
            return found[0]
    return None


def upsert_page(title: str, slug: str, content: str) -> dict[str, Any]:
    existing = find_page(slug)
    if existing and not FORCE_UPDATE:
        # 내용은 운영자가 직접 보완했을 수 있으므로 보존하고, 공개 상태만 보장합니다.
        if str(existing.get("status", "")) != PAGE_STATUS:
            return request(
                "POST",
                f"pages/{existing['id']}",
                json={"status": PAGE_STATUS},
            ).json()
        return existing

    payload = {
        "title": title,
        "slug": slug,
        "content": content,
        "status": PAGE_STATUS,
    }
    if existing:
        return request("POST", f"pages/{existing['id']}", json=payload).json()
    return request("POST", "pages", json=payload).json()


def main() -> int:
    email = html.escape(CONTACT_EMAIL)
    site = html.escape(WP_SITE_URL)

    pages = [
        (
            "TaxonGuru 소개",
            "about-taxonguru",
            f"""
<h2>TaxonGuru 소개</h2>
<p>TaxonGuru는 생물의 분류, 진화, 생태와 생존 전략을 일반 독자가 이해하기 쉽게 설명하는 자연과학 정보 사이트입니다. 각 글은 독자가 원자료를 직접 확인할 수 있도록 학술·기관 자료와 참고 링크를 함께 제공합니다.</p>
<h2>우리가 중요하게 보는 것</h2>
<ul>
<li><strong>정확성:</strong> 학명과 분류를 먼저 확인하고, 확인되지 않은 수치나 과장된 설명을 사실처럼 쓰지 않습니다.</li>
<li><strong>출처 투명성:</strong> 정부기관, 대학·박물관, 과학 데이터베이스와 학술논문을 우선합니다.</li>
<li><strong>읽을 가치:</strong> 단순한 자료 재배열이 아니라 여러 자료의 공통점과 차이를 연결해 독자가 핵심을 이해할 수 있도록 편집합니다.</li>
<li><strong>수정 가능성:</strong> 오류 제보가 확인되면 내용을 다시 검토하고 수정합니다.</li>
</ul>
<h2>운영 및 문의</h2>
<p>사이트 운영, 콘텐츠 오류, 이미지·저작권 문의는 <a href="mailto:{email}">{email}</a>로 보내 주세요.</p>
<p>편집 원칙은 <a href="{site}/editorial-policy/">편집 및 팩트체크 정책</a>, AI 사용 범위는 <a href="{site}/ai-use-policy/">AI 활용 정책</a>에서 확인할 수 있습니다.</p>
""",
        ),
        (
            "편집 및 팩트체크 정책",
            "editorial-policy",
            f"""
<h2>자료 우선순위</h2>
<p>TaxonGuru는 정부기관, 대학·박물관, 공신력 있는 과학 데이터베이스와 학술논문을 우선합니다. 일반 백과사전과 2차 자료는 주제 탐색과 교차 확인을 위한 보조자료로 사용합니다.</p>
<h2>작성과 검수 절차</h2>
<ol>
<li>주제의 학명과 기본 분류를 확인합니다.</li>
<li>여러 독립 출처에서 핵심 사실과 불확실한 주장을 구분합니다.</li>
<li>생성형 AI는 자료 정리, 초안 작성과 문장 검수에 보조적으로 사용할 수 있습니다.</li>
<li>자동 검사에서 출처 수, 인용 표시, 언어 혼입, 근거 없는 주장, 품질 기준을 확인합니다.</li>
<li><strong>신규 또는 재작성 콘텐츠는 자동 검사 통과만으로 바로 공개하지 않고, 운영자가 WordPress 초안을 확인한 뒤 공개합니다.</strong></li>
</ol>
<h2>기존 콘텐츠 정리</h2>
<p>과거에 자동 발행된 글도 순차적으로 다시 검사합니다. 출처가 약하거나 문체·언어·링크 문제가 확인된 글은 공개 상태를 유지하지 않고 초안으로 전환한 뒤 재작성합니다.</p>
<h2>정정 정책</h2>
<p>오류 제보는 <a href="mailto:{email}">{email}</a>로 보내 주세요. 확인된 오류는 원자료를 다시 확인한 뒤 수정하며, 중요한 변경은 글의 수정일에 반영합니다.</p>
""",
        ),
        (
            "AI 활용 정책",
            "ai-use-policy",
            f"""
<h2>AI를 사용하는 범위</h2>
<p>TaxonGuru는 주제 후보 정리, 공개 자료의 구조화, 초안 작성, 번역 보조, 문장·인용 검수에 생성형 AI를 사용할 수 있습니다.</p>
<h2>AI가 결정하지 않는 것</h2>
<p>AI가 생성한 내용만을 근거로 과학 사실을 확정하지 않습니다. 주요 사실은 실제 공개 출처와 연결되어야 하며, 존재하지 않는 논문·URL·전문가 경력·수치가 생성되지 않도록 별도의 검사를 거칩니다.</p>
<h2>공개 전 사람 검토</h2>
<p><strong>현재 TaxonGuru의 신규 및 재작성 글은 자동 품질검사를 통과해도 WordPress 초안으로 저장되며, 운영자가 내용을 확인한 뒤 공개합니다.</strong> 기준 미달 글은 공개하지 않습니다.</p>
<h2>AI 이미지</h2>
<p>AI 생성 이미지를 사용하는 경우 실제 관찰 사진이나 학술 표본 사진으로 오인되지 않도록 설명용 이미지임을 표시합니다. Wikimedia Commons 등 외부 이미지는 사용 가능한 라이선스와 출처를 확인합니다.</p>
<h2>문의와 정정</h2>
<p>AI 사용 또는 콘텐츠 오류에 관한 문의: <a href="mailto:{email}">{email}</a></p>
""",
        ),
        (
            "문의 및 오류 제보",
            "contact-and-corrections",
            f"""
<h2>문의</h2>
<p>콘텐츠 오류, 이미지·저작권, 사이트 운영 관련 문의는 <a href="mailto:{email}">{email}</a>로 보내 주세요.</p>
<h2>오류 제보 시 알려주시면 좋은 내용</h2>
<ul>
<li>문제가 있는 글의 주소</li>
<li>수정이 필요하다고 생각한 문장</li>
<li>가능하면 근거가 되는 원문 자료의 주소 또는 서지정보</li>
</ul>
<h2>처리 방식</h2>
<p>제보 내용은 관련 원자료와 다시 대조합니다. 오류가 확인되면 게시물을 수정하거나 필요한 경우 비공개로 전환해 재검토합니다.</p>
""",
        ),
        (
            "개인정보처리방침",
            "privacy-policy",
            f"""
<h2>개인정보 처리 안내</h2>
<p>TaxonGuru는 사이트 운영과 문의 대응에 필요한 범위에서만 정보를 처리합니다. 서버 또는 분석 도구를 통해 방문 기록, 브라우저·기기 정보, 쿠키 정보가 처리될 수 있으며, 사용자가 이메일로 문의할 경우 사용자가 직접 제공한 연락처와 문의 내용이 처리될 수 있습니다.</p>
<h2>쿠키와 광고</h2>
<p>Google AdSense 등 제3자 광고 서비스가 활성화되는 경우 Google을 포함한 제3자 공급업체가 사용자의 이전 방문 기록을 바탕으로 광고를 제공하기 위해 쿠키를 사용할 수 있습니다. Google과 파트너는 광고 제공·측정·개인화에 쿠키, 웹 비콘, IP 주소 또는 기타 식별자를 사용할 수 있습니다.</p>
<p>사용자는 <a href="https://adssettings.google.com/" target="_blank" rel="noopener noreferrer">Google 광고 설정</a>에서 맞춤 광고 설정을 관리할 수 있습니다. Google이 파트너 사이트의 정보를 사용하는 방식은 <a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener noreferrer">Google의 파트너 사이트 데이터 사용 안내</a>에서 확인할 수 있습니다.</p>
<h2>외부 서비스</h2>
<p>사이트에는 출처 확인을 위해 외부 학술기관·데이터베이스·이미지 제공 사이트로 이동하는 링크가 포함될 수 있으며, 외부 사이트의 개인정보 처리 방식은 각 사이트의 정책을 따릅니다. 광고가 활성화되면 Google 외의 인증된 제3자 광고 공급업체 또는 광고 네트워크가 광고 제공에 참여할 수 있으며, 해당 업체의 쿠키 사용·옵트아웃 방식은 각 공급업체 정책을 따릅니다.</p>
<h2>문의</h2>
<p>개인정보 관련 문의: <a href="mailto:{email}">{email}</a></p>
""",
        ),
    ]

    for title, slug, content in pages:
        page = upsert_page(title, slug, content.strip())
        public_url = f"{WP_SITE_URL}/{slug}/"
        print(
            f"✅ {title}: {page.get('status')} · {public_url} · "
            f"편집 {WP_SITE_URL}/wp-admin/post.php?post={page['id']}&action=edit"
        )

    print("\n필수 페이지 생성/갱신 완료")
    print("- WordPress 메뉴/푸터에 소개, 편집정책, AI 활용정책, 문의, 개인정보처리방침을 연결하세요.")
    print("- 기존 /ai-policy/ 링크는 콘텐츠 감사 코드가 /ai-use-policy/로 정리합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
