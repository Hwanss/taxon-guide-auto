from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import gspread
import requests
import urllib3.util.connection as urllib3_connection

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
WP_API = f"{WP_SITE_URL}/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "admin@taxonguru.com")
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))
FORCE_IPV4 = os.getenv("FORCE_IPV4", "true").lower() == "true"
APPLY_SAFE_FIXES = os.getenv("READINESS_APPLY_SAFE_FIXES", "false").lower() == "true"
OUTPUT_DIR = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "").strip()
SHEET_ID = os.getenv("SHEET_ID", "").strip()
SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")

if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False

session = requests.Session()
session.headers.update(
    {
        "User-Agent": f"TaxonGuruReadiness/6.0 ({WP_SITE_URL}; {CONTACT_EMAIL})",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
)
auth = (WP_USER, WP_APP_PASSWORD)

REQUIRED_PAGES = [
    ("about-taxonguru", "TaxonGuru 소개"),
    ("editorial-policy", "편집 및 팩트체크 정책"),
    ("ai-use-policy", "AI 활용 정책"),
    ("contact-and-corrections", "문의 및 오류 제보"),
    ("privacy-policy", "개인정보처리방침"),
]


def log(message: str) -> None:
    print(message, flush=True)


def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    response = session.request(
        method,
        f"{WP_API}/{endpoint}",
        auth=auth,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"WordPress {method} {endpoint} 실패 {response.status_code}: {response.text[:500]}"
        )
    return response


def text_only(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def is_intermediary_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").casefold()
    except ValueError:
        return True
    if host == "vertexaisearch.cloud.google.com":
        return True
    if host in {"google.com", "www.google.com"} and parts.path.startswith(("/url", "/search")):
        return True
    return host in {"googleusercontent.com", "www.googleusercontent.com"}


def find_page(slug: str) -> dict[str, Any] | None:
    for status in ["publish", "draft", "pending", "private", "future"]:
        items = wp_request(
            "GET",
            "pages",
            params={"slug": slug, "status": status, "context": "edit", "per_page": 5},
        ).json()
        if items:
            return items[0]
    return None


def fetch_published_posts() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while page <= 20:
        response = wp_request(
            "GET",
            "posts",
            params={
                "status": "publish",
                "context": "edit",
                "per_page": 100,
                "page": page,
                "orderby": "modified",
                "order": "desc",
            },
        )
        batch = response.json()
        result.extend(batch)
        total_pages = int(response.headers.get("X-WP-TotalPages", "1") or "1")
        if not batch or page >= total_pages:
            break
        page += 1
    return result


def safe_fix_policy_link(content: str) -> tuple[str, bool]:
    updated = re.sub(
        r'href=(["\'])(?:https?://(?:www\.)?taxonguru\.com)?/ai-policy/?\1',
        lambda m: f'href={m.group(1)}/ai-use-policy/{m.group(1)}',
        content,
        flags=re.I,
    )
    return updated, updated != content


def inspect_post(post: dict[str, Any]) -> dict[str, Any]:
    post_id = int(post["id"])
    link = str(post.get("link", ""))
    title = text_only(str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or ""))
    content = str(post.get("content", {}).get("raw") or post.get("content", {}).get("rendered") or "")
    text = text_only(content)
    issues: list[str] = []
    fixes: list[str] = []

    fixed_content, changed = safe_fix_policy_link(content)
    if changed:
        if APPLY_SAFE_FIXES:
            wp_request("POST", f"posts/{post_id}", json={"content": fixed_content})
            content = fixed_content
            text = text_only(content)
            fixes.append("/ai-policy/ → /ai-use-policy/ 링크 수정")
        else:
            issues.append("구형 AI 정책 링크 /ai-policy/ 사용")

    links = re.findall(r'href=["\'](https?://[^"\']+)', content, flags=re.I)
    intermediary = sorted({url for url in links if is_intermediary_url(url)})
    direct_external = {
        url for url in links
        if "taxonguru.com" not in (urlsplit(url).hostname or "").casefold()
        and not is_intermediary_url(url)
    }
    if intermediary:
        issues.append(f"Google/Vertex 중계 출처 링크 {len(intermediary)}건")
    if len(direct_external) < 3:
        issues.append(f"직접 외부 출처 링크 부족({len(direct_external)}개)")

    image_count = len(re.findall(r"<img\b", content, flags=re.I))
    license_mentions = len(
        re.findall(r"CC\s*BY|CC0|Public domain|퍼블릭\s*도메인|Wikimedia Commons|원본\s*파일|AI[- ]generated|AI\s*생성|Created by TaxonGuru", content, re.I)
    )
    if image_count and license_mentions == 0:
        issues.append("이미지 권리/출처 정보 없음")

    is_english = "/en/" in (urlsplit(link).path or "")
    has_han_or_kana = bool(re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", text))
    has_hangul = bool(re.search(r"[가-힣]", text))
    if is_english and (has_hangul or has_han_or_kana):
        issues.append("영문 본문에 한국어/CJK 문자 혼입")
    if not is_english and has_han_or_kana:
        issues.append("한국어 본문에 중국어 한자/일본어 가나 혼입")

    if not re.search(r"참고자료|References|Sources", text, re.I):
        issues.append("참고자료 섹션 없음")
    if len(text) < 1800:
        issues.append(f"본문 분량 부족({len(text)}자)")
    if "/ai-use-policy/" not in content:
        issues.append("AI/편집 정책 링크 없음")

    return {
        "post_id": post_id,
        "title": title,
        "url": link,
        "modified": str(post.get("modified", "")),
        "issues": issues,
        "safe_fixes": fixes,
        "intermediary_links": intermediary[:10],
    }


def public_check(url: str) -> tuple[int, str]:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return response.status_code, str(response.url)
    except requests.RequestException as exc:
        return 0, " ".join(str(exc).split())[:300]


def sheet_status_counts() -> dict[str, int]:
    if not GOOGLE_CREDENTIALS or not SHEET_ID:
        return {}
    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    values = ws.get_all_values()
    if not values:
        return {}
    headers = ["".join(str(v).split()).casefold() for v in values[0]]
    status_idx = None
    for alias in ("상태", "진행상태"):
        key = "".join(alias.split()).casefold()
        if key in headers:
            status_idx = headers.index(key)
            break
    if status_idx is None:
        return {}
    counts: dict[str, int] = {}
    for row in values[1:]:
        status = str(row[status_idx]).strip() if status_idx < len(row) else ""
        if status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "site": WP_SITE_URL,
        "safe_fixes_enabled": APPLY_SAFE_FIXES,
        "required_pages": [],
        "published_posts": [],
        "ads_txt": {},
        "warnings": [],
        "critical_issues": [],
        "homepage": {},
        "sheet_status_counts": {},
    }

    log("=" * 72)
    log("TaxonGuru AdSense 재심사 준비도 검사 v6")
    log("=" * 72)

    # Homepage discoverability / theme sanity checks.
    home_status, home_final = public_check(f"{WP_SITE_URL}/")
    home_html = ""
    if home_status == 200:
        try:
            home_html = session.get(f"{WP_SITE_URL}/", timeout=REQUEST_TIMEOUT).text[:1000000]
        except requests.RequestException:
            home_html = ""
    home_links = {
        slug: bool(re.search(rf'href=["\'][^"\']*/{re.escape(slug)}/?(?:[?#][^"\']*)?["\']', home_html, re.I))
        for slug, _ in REQUIRED_PAGES
    }
    duplicate_date = bool(
        re.search(r"\d{1,2}월\s*\d{1,2}\s*,?\s*20\d{2}\s*\d{1,2}월\s*\d{1,2}", text_only(home_html))
    )
    report["homepage"] = {
        "http_status": home_status,
        "final_url": home_final,
        "required_page_links": home_links,
        "duplicate_date_pattern_detected": duplicate_date,
    }
    if home_status != 200:
        report["critical_issues"].append(f"홈페이지 HTTP 상태 이상: {home_status}")
    missing_nav = [slug for slug, found in home_links.items() if not found]
    if missing_nav:
        report["critical_issues"].append(
            "홈/푸터에서 필수 신뢰 페이지 링크를 찾지 못했습니다: " + ", ".join(missing_nav)
        )
    if duplicate_date:
        report["critical_issues"].append(
            "홈페이지 목록에서 날짜가 연속 중복되는 패턴을 감지했습니다. WordPress 테마 표시를 수정하세요."
        )

    # Required editorial pages must exist and be public.
    for slug, label in REQUIRED_PAGES:
        page = find_page(slug)
        status = str(page.get("status", "")) if page else "missing"
        public_url = f"{WP_SITE_URL}/{slug}/"
        http_status, final_url = public_check(public_url) if status == "publish" else (0, "")
        ok = bool(page and status == "publish" and http_status == 200)
        row = {
            "slug": slug,
            "label": label,
            "wp_status": status,
            "http_status": http_status,
            "url": public_url,
            "final_url": final_url,
            "ok": ok,
        }
        report["required_pages"].append(row)
        if not ok:
            report["critical_issues"].append(
                f"필수 페이지 공개 확인 실패: {label} ({slug}) · WP={status} HTTP={http_status}"
            )

    # Recovery/manual-review queue should be empty before asking AdSense to review again.
    try:
        status_counts = sheet_status_counts()
        report["sheet_status_counts"] = status_counts
        blockers = {
            "완료",
            "기존재작성대기",
            "기존재작성재시도",
            "기존수동검수대기",
            "수동검수대기",
            "한국어완료/영문수동검수대기",
            "기존정리오류",
        }
        pending = {key: status_counts.get(key, 0) for key in blockers if status_counts.get(key, 0)}
        if pending:
            report["critical_issues"].append(
                "Google Sheet에 정리/수동검수 미완료 상태가 남아 있습니다: "
                + ", ".join(f"{key} {value}건" for key, value in sorted(pending.items()))
            )
        if status_counts.get("기존비공개보류", 0):
            report["warnings"].append(
                f"기존비공개보류 {status_counts['기존비공개보류']}건은 공개되지 않지만 원인 확인을 권장합니다."
            )
    except Exception as exc:
        report["warnings"].append(
            "Google Sheet 상태 확인 실패: " + " ".join(str(exc).split())[:300]
        )

    # ads.txt is strongly recommended. Missing/invalid is a warning here because it is
    # separate from the content-quality cleanup performed by this repository.
    ads_url = f"{WP_SITE_URL}/ads.txt"
    ads_status, ads_final = public_check(ads_url)
    ads_body = ""
    if ads_status == 200:
        try:
            ads_body = session.get(ads_url, timeout=REQUEST_TIMEOUT).text[:20000]
        except requests.RequestException:
            ads_body = ""
    ads_google_line = bool(re.search(r"(?im)^google\.com\s*,\s*pub-\d+\s*,\s*DIRECT", ads_body))
    report["ads_txt"] = {
        "url": ads_url,
        "http_status": ads_status,
        "final_url": ads_final,
        "google_publisher_line_found": ads_google_line,
    }
    if ads_status != 200 or not ads_google_line:
        report["warnings"].append("ads.txt에서 Google publisher DIRECT 항목을 확인하지 못했습니다.")

    posts = fetch_published_posts()
    if not posts:
        report["critical_issues"].append("공개 게시물이 0건입니다.")

    problematic = 0
    for post in posts:
        row = inspect_post(post)
        report["published_posts"].append(row)
        if row["issues"]:
            problematic += 1

    if problematic:
        report["critical_issues"].append(f"공개 게시물 {problematic}건에서 품질/링크/언어 이슈가 감지되었습니다.")

    # Theme/UI issues cannot be repaired safely through the REST content pipeline.
    if not duplicate_date:
        report["warnings"].append(
            "자동 패턴 검사에서 날짜 중복은 감지되지 않았지만 홈·카테고리·게시물 화면은 브라우저에서 최종 확인하세요."
        )

    report["summary"] = {
        "published_post_count": len(posts),
        "problematic_published_posts": problematic,
        "required_pages_ok": sum(1 for row in report["required_pages"] if row["ok"]),
        "required_pages_total": len(REQUIRED_PAGES),
        "critical_issue_count": len(report["critical_issues"]),
        "warning_count": len(report["warnings"]),
        "ready_for_manual_adsense_review": len(report["critical_issues"]) == 0,
    }

    json_path = OUTPUT_DIR / "adsense_readiness.json"
    md_path = OUTPUT_DIR / "adsense_readiness.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# TaxonGuru AdSense 재심사 준비도",
        "",
        f"- 검사시각(UTC): {report['checked_at_utc']}",
        f"- 공개 게시물: {len(posts)}건",
        f"- 문제 감지 공개 게시물: {problematic}건",
        f"- 필수 페이지: {report['summary']['required_pages_ok']}/{len(REQUIRED_PAGES)} 정상",
        f"- ads.txt Google 항목: {'확인' if ads_google_line else '미확인'}",
        f"- 홈/푸터 필수 페이지 링크: {sum(1 for found in home_links.values() if found)}/{len(REQUIRED_PAGES)}",
        f"- 홈페이지 날짜 중복 패턴: {'감지' if duplicate_date else '미감지'}",
        f"- Google Sheet 상태 확인: {'확인' if report['sheet_status_counts'] else '미확인'}",
        f"- 결과: {'READY' if report['summary']['ready_for_manual_adsense_review'] else 'NOT READY'}",
        "",
        "## 중요 문제",
    ]
    if report["critical_issues"]:
        lines.extend(f"- {issue}" for issue in report["critical_issues"])
    else:
        lines.append("- 없음")
    lines += ["", "## 경고"]
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines += ["", "## 문제가 있는 공개 글"]
    for row in report["published_posts"]:
        if row["issues"]:
            lines.append(f"- Post {row['post_id']} · {row['title']} · {'; '.join(row['issues'])}")
    if not any(row["issues"] for row in report["published_posts"]):
        lines.append("- 없음")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    log(f"📄 {json_path}")
    log(f"📄 {md_path}")
    if report["summary"]["ready_for_manual_adsense_review"]:
        log("✅ 코드가 검사한 범위에서는 재심사 전 치명적 이슈가 남아 있지 않습니다.")
    else:
        log("⚠️ 아직 재심사 요청 전 정리할 항목이 있습니다. 보고서를 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
