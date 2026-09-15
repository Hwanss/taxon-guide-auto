from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
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
GUARD_ENABLED = os.getenv("PUBLIC_GUARD_ENABLED", "true").lower() == "true"
GUARD_BATCH_SIZE = max(1, min(6, int(os.getenv("PUBLIC_GUARD_BATCH_SIZE", "2"))))
MANUAL_QUEUE_SOFT_LIMIT = max(0, int(os.getenv("PUBLIC_GUARD_MANUAL_QUEUE_SOFT_LIMIT", "24")))
REQUIRE_MANUAL_CURATION = os.getenv("PUBLIC_GUARD_REQUIRE_MANUAL_CURATION", "true").lower() == "true"
DRAFT_HARD_BLOCKERS = os.getenv("PUBLIC_GUARD_DRAFT_HARD_BLOCKERS", "true").lower() == "true"
OUTPUT_DIR = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))

if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "TaxonGuruPublicGuard/6.3",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
)
wp_auth = (WP_USER, WP_APP_PASSWORD)

MANUAL_REVIEW_STATES = {
    "수동검수대기",
    "기존수동검수대기",
    "한국어완료/영문수동검수대기",
}
REWRITE_STATES = {"기존재작성대기", "기존재작성재시도"}
SKIP_STATES = {
    "대기",
    "완료",  # 기존 v6.2 감사 파이프라인이 담당
    "기존정리오류",
    "기존비공개보류",
    *MANUAL_REVIEW_STATES,
    *REWRITE_STATES,
}
GUARD_STATUS_HEADER = "AdSense검수상태"
GUARD_REASON_HEADER = "AdSense검수사유"
GUARD_REWRITE_REQUIRED = "재작성필요"
GUARD_MANUAL_REQUIRED = "사람검수대기"
GUARD_CONFIRMED = "사람검수확인"

HEADER_ALIASES: dict[str, list[str]] = {
    "status": ["상태", "진행상태"],
    "scientific_name": ["학명", "학명(Scientific Name)", "학명 (Scientific Name)"],
    "slug": ["슬러그", "슬러그(Slug)", "슬러그 (Slug)"],
    "post_id": ["WP_POST_ID", "WP POST ID"],
    "en_post_id": ["EN_POST_ID", "영문 WP_POST_ID"],
    "error": ["오류", "에러"],
    "cleanup_note": ["정리메모", "정리 메모"],
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
INTERMEDIARY_HOSTS = {
    "vertexaisearch.cloud.google.com",
    "googleusercontent.com",
    "www.googleusercontent.com",
}


@dataclass
class RowInfo:
    row_number: int
    values: list[str]
    status: str
    scientific_name: str
    slug: str
    post_id: int | None
    en_post_id: int | None
    guard_status: str
    guard_reason: str


@dataclass
class ContentCheck:
    post_id: int
    title: str
    url: str
    is_english: bool
    hard_blockers: list[str]
    warnings: list[str]
    direct_source_links: int
    intermediary_links: int
    text_length: int
    word_count: int
    images: int


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


def safe_int(value: Any) -> int | None:
    try:
        number = int(str(value or "").strip())
        return number if number > 0 else None
    except Exception:
        return None


def row_value(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx]).strip()


def text_only(value: str) -> str:
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def is_intermediary_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").casefold()
    except ValueError:
        return True
    if host in INTERMEDIARY_HOSTS:
        return True
    return host in {"google.com", "www.google.com"} and parts.path.startswith(("/url", "/search"))


def is_external_url(value: str) -> bool:
    try:
        host = (urlsplit(value).hostname or "").casefold()
    except ValueError:
        return False
    return bool(host and "taxonguru.com" not in host)


def classify_post(post: dict[str, Any]) -> ContentCheck:
    post_id = int(post["id"])
    link = str(post.get("link", ""))
    title_obj = post.get("title") or {}
    title = text_only(str(title_obj.get("raw") or title_obj.get("rendered") or ""))
    content_obj = post.get("content") or {}
    content = str(content_obj.get("raw") or content_obj.get("rendered") or "")
    text = text_only(content)
    is_english = "/en/" in (urlsplit(link).path or "")

    links = re.findall(r'href=["\'](https?://[^"\']+)', content, flags=re.I)
    external_links = {link for link in links if is_external_url(link)}
    intermediary = {link for link in external_links if is_intermediary_url(link)}
    direct = {link for link in external_links if not is_intermediary_url(link)}

    images = len(re.findall(r"<img\b", content, flags=re.I))
    license_mentions = len(
        re.findall(
            r"CC\s*BY|CC0|Public domain|퍼블릭\s*도메인|Wikimedia Commons|"
            r"원본\s*파일|AI[- ]generated|AI\s*생성|Created by TaxonGuru",
            content,
            re.I,
        )
    )
    has_references = bool(re.search(r"참고자료|참고문헌|References|Sources", text, re.I))
    has_hangul = bool(re.search(r"[가-힣]", text))
    has_han_or_kana = bool(re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", text))
    word_count = len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))

    hard: list[str] = []
    warnings: list[str] = []

    if intermediary:
        hard.append(f"Google/Vertex 중계 출처 링크 {len(intermediary)}건")
    if FIXED_TEMPLATE_RE.search(text):
        hard.append("고정형 AI 템플릿 흔적")
    if BILINGUAL_RE.search(content):
        hard.append("한 페이지 내 한영 본문 혼합")
    if FAKE_EXPERT_RE.search(text):
        hard.append("근거 없는 전문가 직함")
    if not has_references:
        hard.append("참고자료 섹션 없음")
    if len(direct) < 3:
        hard.append(f"직접 외부 출처 링크 부족({len(direct)}개)")
    if is_english and (has_hangul or has_han_or_kana):
        hard.append("영문 본문에 한국어/CJK 문자 혼입")
    if not is_english and len(text) < 1200:
        hard.append(f"한국어 본문 분량 매우 부족({len(text)}자)")
    if is_english and word_count < 600:
        hard.append(f"영문 본문 분량 매우 부족({word_count}단어)")

    if images and license_mentions == 0:
        warnings.append("이미지 권리/출처 고지 없음")
    if "/ai-use-policy/" not in content:
        warnings.append("AI/편집 정책 링크 없음")
    if "/ai-policy/" in content:
        warnings.append("구형 AI 정책 링크 사용")
    if not is_english and has_han_or_kana:
        warnings.append("한국어 본문에 한자/가나 문자 포함 — 문맥 확인 필요")

    return ContentCheck(
        post_id=post_id,
        title=title,
        url=link,
        is_english=is_english,
        hard_blockers=list(dict.fromkeys(hard)),
        warnings=list(dict.fromkeys(warnings)),
        direct_source_links=len(direct),
        intermediary_links=len(intermediary),
        text_length=len(text),
        word_count=word_count,
        images=images,
    )


def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    if not WP_USER or not WP_APP_PASSWORD:
        raise RuntimeError("WP_USER / WP_APP_PASSWORD가 없습니다.")
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = session.request(
                method,
                f"{WP_API}/{endpoint}",
                auth=wp_auth,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
            if response.status_code < 400:
                return response
            raise RuntimeError(
                f"WordPress {method} {endpoint} 실패 HTTP {response.status_code}: "
                f"{response.text[:400]}"
            )
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(str(last_error))


def fetch_published_posts() -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
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
        for post in batch:
            result[int(post["id"])] = post
        total_pages = int(response.headers.get("X-WP-TotalPages", "1") or "1")
        if not batch or page >= total_pages:
            break
        page += 1
    return result


def ensure_guard_columns(ws: gspread.Worksheet) -> tuple[list[str], int, int]:
    headers = ws.row_values(1)
    changed = False
    for header in (GUARD_STATUS_HEADER, GUARD_REASON_HEADER):
        if find_header(headers, [header]) is None:
            headers.append(header)
            changed = True
    if changed:
        if ws.col_count < len(headers):
            ws.resize(cols=len(headers))
        ws.update(values=[headers], range_name="A1", value_input_option="USER_ENTERED")
    status_idx = find_header(headers, [GUARD_STATUS_HEADER])
    reason_idx = find_header(headers, [GUARD_REASON_HEADER])
    if status_idx is None or reason_idx is None:
        raise RuntimeError("AdSense 검수 열 생성에 실패했습니다.")
    return headers, status_idx, reason_idx


def load_rows(ws: gspread.Worksheet) -> tuple[list[str], list[RowInfo]]:
    headers, guard_status_idx, guard_reason_idx = ensure_guard_columns(ws)
    records = ws.get_all_values()
    if not records:
        return headers, []
    indexes = {
        key: find_header(headers, aliases)
        for key, aliases in HEADER_ALIASES.items()
    }
    result: list[RowInfo] = []
    for row_number, row in enumerate(records[1:], start=2):
        result.append(
            RowInfo(
                row_number=row_number,
                values=row,
                status=row_value(row, indexes["status"]),
                scientific_name=row_value(row, indexes["scientific_name"]),
                slug=row_value(row, indexes["slug"]),
                post_id=safe_int(row_value(row, indexes["post_id"])),
                en_post_id=safe_int(row_value(row, indexes["en_post_id"])),
                guard_status=row_value(row, guard_status_idx),
                guard_reason=row_value(row, guard_reason_idx),
            )
        )
    return headers, result


def update_row(
    ws: gspread.Worksheet,
    headers: list[str],
    row_number: int,
    fields: dict[str, Any],
) -> None:
    aliases = {
        **HEADER_ALIASES,
        "guard_status": [GUARD_STATUS_HEADER],
        "guard_reason": [GUARD_REASON_HEADER],
    }
    cells: list[gspread.Cell] = []
    for key, value in fields.items():
        idx = find_header(headers, aliases.get(key, [key]))
        if idx is not None:
            cells.append(gspread.Cell(row_number, idx + 1, str(value)))
    if cells:
        ws.update_cells(cells, value_input_option="USER_ENTERED")


def manual_queue_count(rows: list[RowInfo]) -> int:
    return sum(1 for row in rows if row.status in MANUAL_REVIEW_STATES)


def expected_published(row: RowInfo, posts: dict[int, dict[str, Any]]) -> bool:
    if not row.post_id or row.post_id not in posts:
        return False
    if row.en_post_id and row.en_post_id not in posts:
        return False
    return True


def inspect_row_posts(
    row: RowInfo,
    posts: dict[int, dict[str, Any]],
) -> tuple[list[ContentCheck], list[str]]:
    checks: list[ContentCheck] = []
    reasons: list[str] = []
    for label, post_id in (("KO", row.post_id), ("EN", row.en_post_id)):
        if not post_id:
            continue
        post = posts.get(post_id)
        if not post:
            continue
        check = classify_post(post)
        checks.append(check)
        reasons.extend(f"{label}: {reason}" for reason in check.hard_blockers)
    return checks, list(dict.fromkeys(reasons))


def set_posts_draft(row: RowInfo, posts: dict[int, dict[str, Any]]) -> list[int]:
    drafted: list[int] = []
    for post_id in (row.post_id, row.en_post_id):
        if post_id and post_id in posts:
            wp_request("POST", f"posts/{post_id}", json={"status": "draft"})
            drafted.append(post_id)
    return drafted


def should_skip_row(row: RowInfo) -> bool:
    status = row.status.strip()
    if not row.post_id:
        return True
    if status in SKIP_STATES:
        return True
    if status.startswith("기존한영재예약") or "예약" in status:
        return True
    if "오류" in status or "대기" in status:
        return True
    return False


def run_guard() -> int:
    if not GUARD_ENABLED:
        log("🛡️ Public Guard 비활성화")
        return 0
    if not GOOGLE_CREDENTIALS or not SHEET_ID:
        raise RuntimeError("GOOGLE_CREDENTIALS / SHEET_ID가 없습니다.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    headers, rows = load_rows(ws)
    posts = fetch_published_posts()

    initial_manual = manual_queue_count(rows)
    report_rows: list[dict[str, Any]] = []
    changed = 0
    rewrites_queued = 0
    reviews_queued = 0
    confirmed = 0
    unmatched_public_ids = set(posts)

    for row in rows:
        if row.post_id:
            unmatched_public_ids.discard(row.post_id)
        if row.en_post_id:
            unmatched_public_ids.discard(row.en_post_id)

    for row in rows:
        if row.guard_status not in {GUARD_REWRITE_REQUIRED, GUARD_MANUAL_REQUIRED}:
            continue
        if row.status in MANUAL_REVIEW_STATES or row.status in REWRITE_STATES:
            continue
        if not expected_published(row, posts):
            continue
        checks, hard_reasons = inspect_row_posts(row, posts)
        if hard_reasons:
            continue
        update_row(
            ws,
            headers,
            row.row_number,
            {
                "guard_status": GUARD_CONFIRMED,
                "guard_reason": "Public Guard 대기 이후 WordPress 공개 상태를 확인했습니다. 현재 하드 블로커 없음.",
                "error": "",
            },
        )
        confirmed += 1

    headers, rows = load_rows(ws)
    manual_waiting = manual_queue_count(rows)

    candidates: list[tuple[int, RowInfo, list[ContentCheck], list[str], list[str]]] = []
    for row in rows:
        if should_skip_row(row):
            continue
        if row.guard_status == GUARD_CONFIRMED:
            continue
        checks, hard_reasons = inspect_row_posts(row, posts)
        if not checks:
            continue
        warnings = list(dict.fromkeys(
            f"{'EN' if check.is_english else 'KO'}: {warning}"
            for check in checks
            for warning in check.warnings
        ))
        if hard_reasons:
            priority = 0
        elif REQUIRE_MANUAL_CURATION and manual_waiting < MANUAL_QUEUE_SOFT_LIMIT:
            priority = 1
        else:
            priority = 2
        candidates.append((priority, row, checks, hard_reasons, warnings))

    candidates.sort(key=lambda item: (item[0], item[1].row_number))

    for priority, row, checks, hard_reasons, warnings in candidates:
        if changed >= GUARD_BATCH_SIZE:
            break
        if priority == 2:
            continue

        if hard_reasons:
            if not row.scientific_name:
                report_rows.append(
                    {
                        "row": row.row_number,
                        "status": row.status,
                        "post_id": row.post_id,
                        "en_post_id": row.en_post_id,
                        "action": "보류",
                        "hard_blockers": " | ".join(hard_reasons),
                        "warnings": " | ".join(warnings),
                        "note": "학명이 없어 자동 재작성 대기열로 보낼 수 없음",
                    }
                )
                continue

            drafted = set_posts_draft(row, posts) if DRAFT_HARD_BLOCKERS else []
            update_row(
                ws,
                headers,
                row.row_number,
                {
                    "status": "기존재작성대기",
                    "guard_status": GUARD_REWRITE_REQUIRED,
                    "guard_reason": " | ".join(hard_reasons)[:1800],
                    "cleanup_note": (
                        "Public Guard v6.3: 공개 글 하드 블로커 감지 → "
                        "비공개 후 기존 재작성 대기열 편입"
                    ),
                    "error": "",
                },
            )
            changed += 1
            rewrites_queued += 1
            report_rows.append(
                {
                    "row": row.row_number,
                    "status": row.status,
                    "post_id": row.post_id,
                    "en_post_id": row.en_post_id,
                    "action": f"재작성대기 / draft={','.join(map(str, drafted))}",
                    "hard_blockers": " | ".join(hard_reasons),
                    "warnings": " | ".join(warnings),
                    "note": row.scientific_name,
                }
            )
            continue

        if REQUIRE_MANUAL_CURATION and manual_waiting + reviews_queued < MANUAL_QUEUE_SOFT_LIMIT:
            drafted = set_posts_draft(row, posts)
            update_row(
                ws,
                headers,
                row.row_number,
                {
                    "status": "기존수동검수대기",
                    "guard_status": GUARD_MANUAL_REQUIRED,
                    "guard_reason": (
                        "자동 생성 이력이 있는 기존 공개 글입니다. 하드 블로커는 없지만 "
                        "AdSense 복구 기준상 사람 최종 검수 후 공개가 필요합니다."
                    ),
                    "cleanup_note": "Public Guard v6.3: 기존 자동 생성 공개 글 → 사람 검수 대기",
                    "error": "",
                },
            )
            changed += 1
            reviews_queued += 1
            report_rows.append(
                {
                    "row": row.row_number,
                    "status": row.status,
                    "post_id": row.post_id,
                    "en_post_id": row.en_post_id,
                    "action": f"사람검수대기 / draft={','.join(map(str, drafted))}",
                    "hard_blockers": "",
                    "warnings": " | ".join(warnings),
                    "note": row.scientific_name,
                }
            )

    remaining_hard = 0
    remaining_unreviewed_clean = 0
    headers_after, rows_after = load_rows(ws)
    posts_after = fetch_published_posts()
    for row in rows_after:
        if should_skip_row(row) or row.guard_status == GUARD_CONFIRMED:
            continue
        checks, hard_reasons = inspect_row_posts(row, posts_after)
        if not checks:
            continue
        if hard_reasons:
            remaining_hard += 1
        elif REQUIRE_MANUAL_CURATION:
            remaining_unreviewed_clean += 1

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "site": WP_SITE_URL,
        "batch_size": GUARD_BATCH_SIZE,
        "manual_queue_soft_limit": MANUAL_QUEUE_SOFT_LIMIT,
        "initial_manual_queue": initial_manual,
        "changed_rows": changed,
        "rewrites_queued": rewrites_queued,
        "manual_reviews_queued": reviews_queued,
        "manual_reviews_confirmed": confirmed,
        "remaining_public_hard_blocker_rows": remaining_hard,
        "remaining_public_unreviewed_clean_rows": remaining_unreviewed_clean,
        "unmatched_public_post_ids": sorted(unmatched_public_ids),
        "actions": report_rows,
    }
    (OUTPUT_DIR / "adsense_public_guard.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (OUTPUT_DIR / "adsense_public_guard.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row",
                "status",
                "post_id",
                "en_post_id",
                "action",
                "hard_blockers",
                "warnings",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    log(
        "🛡️ Public Guard v6.3: "
        f"재작성대기 {rewrites_queued} · 사람검수대기 {reviews_queued} · "
        f"사람검수확인 {confirmed} · 남은 공개 하드블로커 {remaining_hard} · "
        f"남은 미검수 공개글 {remaining_unreviewed_clean}"
    )
    if unmatched_public_ids:
        log(
            "⚠️ Google Sheet와 매칭되지 않은 공개 Post ID: "
            + ", ".join(map(str, sorted(unmatched_public_ids)[:20]))
        )
    return 0


def self_test() -> int:
    cases = [
        (
            "vertex",
            '<p>본문</p><h2>참고자료</h2><a href="https://vertexaisearch.cloud.google.com/x">x</a>',
            False,
            "Google/Vertex 중계 출처 링크",
        ),
        (
            "fixed-template",
            "<h2>Scientific Backbone</h2><p>text</p><h2>References</h2>",
            True,
            "고정형 AI 템플릿 흔적",
        ),
        (
            "bilingual",
            "<p>[2부: Global Readers English Version]</p><h2>참고자료</h2>",
            False,
            "한 페이지 내 한영 본문 혼합",
        ),
    ]
    for name, content, english, expected in cases:
        post = {
            "id": 1,
            "link": "https://taxonguru.com/en/test/" if english else "https://taxonguru.com/test/",
            "title": {"raw": name},
            "content": {"raw": content},
        }
        result = classify_post(post)
        if not any(expected in issue for issue in result.hard_blockers):
            raise AssertionError(f"{name}: expected {expected}, got {result.hard_blockers}")

    clean_links = "".join(
        f'<a href="https://example{i}.org/paper">src</a>' for i in range(1, 5)
    )
    clean = {
        "id": 2,
        "link": "https://taxonguru.com/test-clean/",
        "title": {"raw": "clean"},
        "content": {
            "raw": (
                "<p>" + ("검증된 자연과학 설명입니다. " * 100) + "</p>"
                "<h2>참고자료</h2>" + clean_links
                + '<p><a href="/ai-use-policy/">정책</a></p>'
            )
        },
    }
    result = classify_post(clean)
    unexpected = [
        issue
        for issue in result.hard_blockers
        if "한자/가나" not in issue
    ]
    if unexpected:
        raise AssertionError(f"clean case unexpectedly blocked: {unexpected}")
    print("SELF_TEST_OK")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    return run_guard()


if __name__ == "__main__":
    sys.exit(main())
