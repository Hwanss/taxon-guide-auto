from __future__ import annotations

import csv
import os
import re
from html import unescape
from pathlib import Path
from typing import Any

import requests

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
WP_URL = f"{WP_SITE_URL}/wp-json/wp/v2"
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
OUTPUT_FILE = Path(os.getenv("AUDIT_OUTPUT", "taxonguru_content_audit.csv"))

session = requests.Session()
session.headers.update({"User-Agent": "TaxonGuruContentAudit/2.0"})
auth = (WP_USER, WP_APP_PASSWORD) if WP_USER and WP_APP_PASSWORD else None


def text_only(value: str) -> str:
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(value).split())


def fetch_all_posts() -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    page = 1
    while True:
        response = session.get(
            f"{WP_URL}/posts",
            params={"status": "publish", "per_page": 100, "page": page, "context": "view"},
            auth=auth,
            timeout=45,
        )
        if response.status_code == 400 and page > 1:
            break
        response.raise_for_status()
        batch = response.json()
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return posts


def evaluate(post: dict[str, Any]) -> dict[str, Any]:
    html_body = post.get("content", {}).get("rendered", "")
    text = text_only(html_body)
    links = re.findall(r'href=["\'](https?://[^"\']+)', html_body, flags=re.I)
    external_links = [link for link in links if "taxonguru.com" not in link]
    images = len(re.findall(r"<img\b", html_body, flags=re.I))
    licensed_images = len(re.findall(r"CC BY|CC0|Public domain|Wikimedia Commons|원본 파일", html_body, flags=re.I))
    fixed_template = bool(re.search(r"Hook|Scientific Backbone|Deep Anatomy|Evolutionary Context|Verdict & Trivia", text, flags=re.I))
    bilingual_repeat = bool(re.search(r"Global Readers|English Version|\[2부", text, flags=re.I))
    has_references = bool(re.search(r"참고자료|참고문헌|References", text, flags=re.I))
    has_ai_policy = bool(re.search(r"AI.*초안|AI.*보조|생성형 AI", text, flags=re.I))

    score = 100
    issues: list[str] = []
    if len(text) < 1800:
        score -= 25
        issues.append("본문이 짧음")
    if len(set(external_links)) < 3:
        score -= 25
        issues.append("외부 원문 출처 3개 미만")
    if not has_references:
        score -= 15
        issues.append("참고자료 섹션 없음")
    if images and licensed_images == 0:
        score -= 15
        issues.append("이미지 라이선스 표기 없음")
    if fixed_template:
        score -= 10
        issues.append("고정 AI 템플릿 흔적")
    if bilingual_repeat:
        score -= 10
        issues.append("한 페이지 내 한영 중복")
    if not has_ai_policy:
        score -= 5
        issues.append("AI 활용 고지 없음")

    return {
        "post_id": post.get("id"),
        "title": text_only(post.get("title", {}).get("rendered", "")),
        "url": post.get("link", ""),
        "characters": len(text),
        "external_source_links": len(set(external_links)),
        "images": images,
        "licensed_image_mentions": licensed_images,
        "structural_score": max(0, score),
        "issues": " | ".join(issues),
        "note": "구조 감사 점수이며 과학적 사실의 정확성을 직접 검증한 점수는 아닙니다.",
    }


def main() -> None:
    rows = [evaluate(post) for post in fetch_all_posts()]
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["note"])
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        else:
            writer.writerow({"note": "공개 글을 찾지 못했습니다."})
    print(f"✅ 감사 보고서 생성: {OUTPUT_FILE.resolve()} ({len(rows)}개 글)")


if __name__ == "__main__":
    main()
