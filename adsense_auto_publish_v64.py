from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import gspread
import requests
import urllib3.util.connection as urllib3_connection

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
WP_API = f"{WP_SITE_URL}/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID = os.environ.get("SHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))
FORCE_IPV4 = os.getenv("FORCE_IPV4", "true").lower() == "true"
AUTO_PUBLISH_ENABLED = os.getenv("AUTO_PUBLISH_ENABLED", "true").lower() == "true"
AUTO_PUBLISH_BATCH_SIZE = max(1, min(10, int(os.getenv("AUTO_PUBLISH_BATCH_SIZE", "4"))))
AUTO_PUBLISH_MIN_KO_SCORE = max(88, min(100, int(os.getenv("AUTO_PUBLISH_MIN_KO_SCORE", "98"))))
AUTO_PUBLISH_MIN_EN_SCORE = max(88, min(100, int(os.getenv("AUTO_PUBLISH_MIN_EN_SCORE", "96"))))
AUTO_PUBLISH_MIN_SOURCES = max(4, int(os.getenv("AUTO_PUBLISH_MIN_SOURCES", "4")))
AUTO_PUBLISH_MIN_KO_CHARS = max(1800, int(os.getenv("AUTO_PUBLISH_MIN_KO_CHARS", "2600")))
AUTO_PUBLISH_MIN_EN_WORDS = max(700, int(os.getenv("AUTO_PUBLISH_MIN_EN_WORDS", "950")))
AUTO_PUBLISH_REQUIRE_IMAGES = os.getenv("AUTO_PUBLISH_REQUIRE_IMAGES", "true").lower() == "true"
AUTO_PUBLISH_ROLLBACK_ON_RENDER_FAILURE = os.getenv("AUTO_PUBLISH_ROLLBACK_ON_RENDER_FAILURE", "true").lower() == "true"
OUTPUT_DIR = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))

if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False

session = requests.Session()
session.headers.update({
    "User-Agent": "TaxonGuruAutoPublish/6.4",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
})
wp_auth = (WP_USER, WP_APP_PASSWORD)

CANDIDATE_STATES = {
    "기존수동검수대기",
    "수동검수대기",
    "한국어완료/영문수동검수대기",
}

HEADER_ALIASES: dict[str, list[str]] = {
    "status": ["상태", "진행상태"],
    "post_id": ["WP_POST_ID", "WP POST ID"],
    "en_post_id": ["EN_POST_ID", "영문 WP_POST_ID"],
    "public_url": ["공개URL", "공개 URL"],
    "en_public_url": ["EN_공개URL", "EN 공개URL", "영문 공개URL"],
    "quality_score": ["품질점수", "품질 점수"],
    "en_quality_score": ["EN_품질점수", "EN 품질점수", "영문품질점수"],
    "source_count": ["자료수", "출처수", "출처 수"],
    "review_note": ["검수메모", "검수 메모"],
    "cleanup_note": ["정리메모", "정리 메모"],
    "error": ["오류", "에러"],
    "en_error": ["영문오류", "EN_오류", "EN 오류"],
    "guard_status": ["AdSense검수상태"],
    "guard_reason": ["AdSense검수사유"],
}

INTERMEDIARY_HOSTS = {
    "vertexaisearch.cloud.google.com",
    "googleusercontent.com",
    "www.googleusercontent.com",
}

FIXED_TEMPLATE_RE = re.compile(
    r"Hook|Scientific Backbone|Deep Anatomy|Evolutionary Context|Verdict\s*&\s*Trivia|"
    r"핵심\s*요약.{0,120}분류학적\s*위치",
    re.I | re.S,
)
BILINGUAL_RE = re.compile(
    r"Global Readers|English Version|\[2부|Part\s*2\s*:\s*English|"
    r"<h[1-6][^>]*>\s*English",
    re.I,
)
FAKE_EXPERT_RE = re.compile(
    r"수석\s*(?:고생물학자|생물학자|해양생물학자)|제왕적\s*해양생물학자|"
    r"chief\s+(?:paleontologist|biologist)",
    re.I,
)


@dataclass
class CheckResult:
    ok: bool
    reasons: list[str]
    warnings: list[str]
    direct_sources: int
    text_length: int
    word_count: int
    image_count: int


def log(message: str) -> None:
    print(message, flush=True)


def normalize_header(value: str) -> str:
    return re.sub(r"[\s_\-/()]+", "", str(value or "")).casefold()


def find_header(headers: list[str], aliases: list[str]) -> int | None:
    normalized = [normalize_header(item) for item in headers]
    for alias in aliases:
        key = normalize_header(alias)
        if key in normalized:
            return normalized.index(key)
    return None


def value(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx]).strip()


def safe_int(raw: Any) -> int | None:
    try:
        n = int(float(str(raw).strip()))
        return n if n > 0 else None
    except Exception:
        return None


def safe_float(raw: Any) -> float:
    try:
        return float(str(raw).strip())
    except Exception:
        return 0.0


def text_only(raw: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw or "")).split())


def is_intermediary_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return True
    host = (parts.hostname or "").casefold()
    if host in INTERMEDIARY_HOSTS:
        return True
    if host in {"google.com", "www.google.com"} and parts.path.startswith(("/url", "/search")):
        return True
    return False


def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = session.request(
                method,
                f"{WP_API}/{endpoint}",
                auth=wp_auth,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"WordPress {method} {endpoint} 실패 {response.status_code}: {response.text[:400]}")
            return response
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 * attempt)
    raise RuntimeError(str(last))


def fetch_post(post_id: int) -> dict[str, Any]:
    return wp_request(
        "GET",
        f"posts/{post_id}",
        params={"context": "edit", "_fields": "id,status,link,title,content,featured_media"},
    ).json()


def check_post(post: dict[str, Any], *, is_english: bool) -> CheckResult:
    title = text_only(str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or ""))
    content = str(post.get("content", {}).get("raw") or post.get("content", {}).get("rendered") or "")
    text = text_only(content)
    reasons: list[str] = []
    warnings: list[str] = []

    if not title or len(title) < 8:
        reasons.append("제목 부족")
    if FIXED_TEMPLATE_RE.search(content):
        reasons.append("AI 고정 템플릿 흔적")
    if BILINGUAL_RE.search(content):
        reasons.append("한 페이지 내 한영 반복 흔적")
    if FAKE_EXPERT_RE.search(text):
        reasons.append("과장된 전문가/직함 표현")
    if "/ai-use-policy/" not in content:
        reasons.append("AI 활용정책 링크 없음")
    if not re.search(r"참고자료|References|Sources", text, re.I):
        reasons.append("참고자료 섹션 없음")

    links = re.findall(r'href=["\'](https?://[^"\']+)', content, flags=re.I)
    intermediary = [url for url in links if is_intermediary_url(url)]
    if intermediary:
        reasons.append(f"Google/Vertex 중계링크 {len(intermediary)}건")
    direct_external = {
        url for url in links
        if "taxonguru.com" not in (urlsplit(url).hostname or "").casefold()
        and not is_intermediary_url(url)
    }
    if len(direct_external) < AUTO_PUBLISH_MIN_SOURCES:
        reasons.append(f"직접 외부 출처 부족({len(direct_external)})")

    image_count = len(re.findall(r"<img\b", content, flags=re.I))
    featured_media = safe_int(post.get("featured_media"))
    if AUTO_PUBLISH_REQUIRE_IMAGES and image_count < 2:
        reasons.append(f"본문 이미지 부족({image_count})")
    if AUTO_PUBLISH_REQUIRE_IMAGES and not featured_media:
        reasons.append("대표 이미지 없음")

    if image_count:
        license_mentions = len(re.findall(
            r"CC\s*BY|CC0|Public domain|퍼블릭\s*도메인|Wikimedia Commons|원본\s*파일|AI[- ]generated|AI\s*생성|Created by TaxonGuru",
            content,
            re.I,
        ))
        if license_mentions == 0:
            reasons.append("이미지 권리/출처 표시 없음")

    has_han_or_kana = bool(re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", text))
    has_hangul = bool(re.search(r"[가-힣]", text))
    if is_english:
        if has_hangul or has_han_or_kana:
            reasons.append("영문 본문에 한국어/CJK 혼입")
        word_count = len(re.findall(r"\b[A-Za-z][A-Za-z'’-]*\b", text))
        if word_count < AUTO_PUBLISH_MIN_EN_WORDS:
            reasons.append(f"영문 분량 부족({word_count} words)")
    else:
        if has_han_or_kana:
            reasons.append("한국어 본문에 한자/가나 혼입")
        word_count = 0
        hangul_count = len(re.findall(r"[가-힣]", text))
        if hangul_count < AUTO_PUBLISH_MIN_KO_CHARS:
            reasons.append(f"한국어 분량 부족({hangul_count}자)")

    if re.search(r"\b(?:TBD|TODO|PLACEHOLDER|lorem ipsum)\b", text, re.I):
        reasons.append("템플릿/미완성 문구")
    if re.search(r"(?:https?://\S+){4,}", text):
        warnings.append("본문에 URL이 과도하게 직접 노출됨")

    return CheckResult(
        ok=not reasons,
        reasons=reasons,
        warnings=warnings,
        direct_sources=len(direct_external),
        text_length=len(text),
        word_count=word_count,
        image_count=image_count,
    )


def public_render_ok(url: str, *, is_english: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    except Exception as exc:
        return False, [f"공개 페이지 접속 실패: {exc}"]
    if response.status_code != 200:
        return False, [f"공개 페이지 HTTP {response.status_code}"]
    html_text = response.text
    text = text_only(html_text)
    if len(text) < 1500:
        reasons.append("공개 페이지 렌더링 본문이 비정상적으로 짧음")
    if FIXED_TEMPLATE_RE.search(html_text) or BILINGUAL_RE.search(html_text) or FAKE_EXPERT_RE.search(text):
        reasons.append("공개 렌더링에서 금지 패턴 재검출")
    if is_english:
        if re.search(r"[가-힣\u3040-\u30FF]", text):
            reasons.append("공개 영문 페이지에 언어 혼입")
    else:
        if re.search(r"[\u3040-\u30FF]", text):
            reasons.append("공개 한국어 페이지에 일본어 혼입")
    return not reasons, reasons


def ensure_header(ws: gspread.Worksheet, headers: list[str], name: str) -> tuple[list[str], int]:
    idx = find_header(headers, [name])
    if idx is not None:
        return headers, idx
    ws.update_cell(1, len(headers) + 1, name)
    headers = headers + [name]
    return headers, len(headers) - 1


def main() -> int:
    if "--self-test" in sys.argv:
        sample_good = {
            "title": {"raw": "벌새의 생태와 진화: 검증된 과학 자료로 살펴보기"},
            "content": {"raw": (
                "<p>" + "가" * 2700 + "</p>"
                "<h2>참고자료</h2>"
                + "".join(f'<a href="https://example{i}.org/source">src</a>' for i in range(4))
                + '<p><a href="/ai-use-policy/">AI 활용 정책</a></p>'
                + '<figure><img src="a.jpg"><figcaption>AI 생성 · Created by TaxonGuru</figcaption></figure>'
                + '<figure><img src="b.jpg"><figcaption>AI 생성 · Created by TaxonGuru</figcaption></figure>'
            )},
            "featured_media": 123,
        }
        result = check_post(sample_good, is_english=False)
        if not result.ok:
            raise SystemExit("SELF_TEST_FAIL: " + "; ".join(result.reasons))
        sample_bad = {"title": {"raw": "짧음"}, "content": {"raw": "<p>Hook English Version</p>"}, "featured_media": 0}
        if check_post(sample_bad, is_english=False).ok:
            raise SystemExit("SELF_TEST_FAIL_BAD")
        print("SELF_TEST_OK")
        return 0

    if not AUTO_PUBLISH_ENABLED:
        log("⏸️ v6.4 자동 최종검수/조건부 공개 비활성화")
        return 0
    if not all([WP_USER, WP_APP_PASSWORD, GOOGLE_CREDENTIALS, SHEET_ID]):
        raise RuntimeError("v6.4 자동공개에 필요한 WordPress/Google Sheets 설정이 없습니다.")

    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    values = ws.get_all_values()
    if not values:
        return 0
    headers = values[0]
    rows = values[1:]
    headers, auto_status_idx = ensure_header(ws, headers, "자동최종검수상태")
    headers, auto_reason_idx = ensure_header(ws, headers, "자동최종검수사유")
    headers, auto_publish_idx = ensure_header(ws, headers, "자동공개결과")

    idx = {key: find_header(headers, aliases) for key, aliases in HEADER_ALIASES.items()}
    if idx["status"] is None or idx["post_id"] is None:
        raise RuntimeError("상태 또는 WP_POST_ID 헤더를 찾지 못했습니다.")

    status_counter = Counter(value(row, idx["status"]) for row in rows)
    candidates: list[tuple[int, list[str]]] = []
    for row_number, row in enumerate(rows, start=2):
        if value(row, idx["status"]) in CANDIDATE_STATES:
            candidates.append((row_number, row))
    candidates = candidates[:AUTO_PUBLISH_BATCH_SIZE]

    log(
        f"🚦 v6.4 자동 최종검수 시작: 후보 {len(candidates)}건 / "
        f"KO≥{AUTO_PUBLISH_MIN_KO_SCORE}, EN≥{AUTO_PUBLISH_MIN_EN_SCORE}, 출처≥{AUTO_PUBLISH_MIN_SOURCES}"
    )

    published = 0
    held = 0
    errors = 0
    for row_number, row in candidates:
        status = value(row, idx["status"])
        post_id = safe_int(value(row, idx["post_id"]))
        en_post_id = safe_int(value(row, idx["en_post_id"])) if idx["en_post_id"] is not None else None
        reasons: list[str] = []

        ko_score = safe_float(value(row, idx["quality_score"]))
        en_score = safe_float(value(row, idx["en_quality_score"])) if idx["en_quality_score"] is not None else 0.0
        source_count = safe_int(value(row, idx["source_count"])) or 0
        if ko_score < AUTO_PUBLISH_MIN_KO_SCORE:
            reasons.append(f"KO 점수 {ko_score:g}<{AUTO_PUBLISH_MIN_KO_SCORE}")
        if source_count < AUTO_PUBLISH_MIN_SOURCES:
            reasons.append(f"자료수 {source_count}<{AUTO_PUBLISH_MIN_SOURCES}")
        if idx["error"] is not None and value(row, idx["error"]):
            reasons.append("한국어 오류 필드 존재")
        if idx["en_error"] is not None and value(row, idx["en_error"]):
            reasons.append("영문 오류 필드 존재")
        if not post_id:
            reasons.append("WP_POST_ID 없음")
        if status in {"기존수동검수대기", "수동검수대기", "한국어완료/영문수동검수대기"}:
            if not en_post_id:
                reasons.append("EN_POST_ID 없음")
            if en_score < AUTO_PUBLISH_MIN_EN_SCORE:
                reasons.append(f"EN 점수 {en_score:g}<{AUTO_PUBLISH_MIN_EN_SCORE}")

        ko_post: dict[str, Any] | None = None
        en_post: dict[str, Any] | None = None
        try:
            if post_id:
                ko_post = fetch_post(post_id)
                ko_check = check_post(ko_post, is_english=False)
                reasons.extend(f"KO: {r}" for r in ko_check.reasons)
            if en_post_id:
                en_post = fetch_post(en_post_id)
                en_check = check_post(en_post, is_english=True)
                reasons.extend(f"EN: {r}" for r in en_check.reasons)
        except Exception as exc:
            reasons.append(f"WordPress 검증 실패: {exc}")

        if reasons:
            held += 1
            ws.update_cell(row_number, auto_status_idx + 1, "사람검수유지")
            ws.update_cell(row_number, auto_reason_idx + 1, " | ".join(reasons)[:45000])
            ws.update_cell(row_number, auto_publish_idx + 1, "미공개")
            log(f"  👤 행 {row_number}: 사람검수 유지 · " + "; ".join(reasons[:5]))
            continue

        previous_statuses: list[tuple[int, str]] = []
        try:
            assert ko_post is not None and en_post is not None and post_id and en_post_id
            previous_statuses = [(post_id, str(ko_post.get("status", "draft"))), (en_post_id, str(en_post.get("status", "draft")))]
            wp_request("POST", f"posts/{post_id}", json={"status": "publish"})
            wp_request("POST", f"posts/{en_post_id}", json={"status": "publish"})

            ko_live = fetch_post(post_id)
            en_live = fetch_post(en_post_id)
            ko_url = str(ko_live.get("link", "")).strip()
            en_url = str(en_live.get("link", "")).strip()
            if not ko_url or not en_url:
                raise RuntimeError("공개 URL 확인 실패")
            ko_render_ok, ko_render_reasons = public_render_ok(ko_url, is_english=False)
            en_render_ok, en_render_reasons = public_render_ok(en_url, is_english=True)
            if not ko_render_ok or not en_render_ok:
                raise RuntimeError(
                    "공개 후 렌더링 검증 실패: "
                    + "; ".join([*("KO: " + r for r in ko_render_reasons), *("EN: " + r for r in en_render_reasons)])
                )

            final_state = "기존한영수정완료" if status.startswith("기존") else "완료"
            ws.update_cell(row_number, idx["status"] + 1, final_state)
            if idx["public_url"] is not None:
                ws.update_cell(row_number, idx["public_url"] + 1, ko_url)
            if idx["en_public_url"] is not None:
                ws.update_cell(row_number, idx["en_public_url"] + 1, en_url)
            if idx["guard_status"] is not None:
                ws.update_cell(row_number, idx["guard_status"] + 1, "사람검수확인")
            if idx["guard_reason"] is not None:
                ws.update_cell(row_number, idx["guard_reason"] + 1, "v6.4 엄격 자동 최종검수 통과 후 공개")
            if idx["cleanup_note"] is not None:
                ws.update_cell(row_number, idx["cleanup_note"] + 1, "v6.4 조건부 자동공개 완료 · 공개 후 렌더링 재검증 통과")
            ws.update_cell(row_number, auto_status_idx + 1, "자동검수통과")
            ws.update_cell(row_number, auto_reason_idx + 1, "엄격 조건 전체 통과")
            ws.update_cell(row_number, auto_publish_idx + 1, "공개완료")
            published += 1
            log(f"  ✅ 행 {row_number}: KO/EN 자동 최종검수 통과 → 공개 및 렌더링 재검증 완료")
        except Exception as exc:
            errors += 1
            if AUTO_PUBLISH_ROLLBACK_ON_RENDER_FAILURE and previous_statuses:
                for pid, old_status in previous_statuses:
                    try:
                        wp_request("POST", f"posts/{pid}", json={"status": old_status if old_status in {"draft", "pending", "private"} else "draft"})
                    except Exception:
                        pass
            ws.update_cell(row_number, auto_status_idx + 1, "공개실패")
            ws.update_cell(row_number, auto_reason_idx + 1, str(exc)[:45000])
            ws.update_cell(row_number, auto_publish_idx + 1, "롤백/미공개")
            log(f"  ⚠️ 행 {row_number}: 자동공개 실패 → 초안 안전복귀: {exc}")

    remaining = sum(status_counter.get(s, 0) for s in CANDIDATE_STATES) - len(candidates) + held + errors
    log(f"✅ v6.4 자동 최종검수 종료: 자동공개 {published} · 사람검수 유지 {held} · 오류 {errors} · 추정 잔여 {max(0, remaining)}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "auto_publish_v64_summary.json").open("w", encoding="utf-8") as fp:
        json.dump({
            "published": published,
            "held": held,
            "errors": errors,
            "candidate_count": len(candidates),
            "remaining_estimate": max(0, remaining),
        }, fp, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
