from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import gspread
import requests

from adsense_public_guard_v63 import (
    GUARD_CONFIRMED,
    GUARD_MANUAL_REQUIRED,
    GUARD_REWRITE_REQUIRED,
    GUARD_STATUS_HEADER,
    MANUAL_REVIEW_STATES,
    OUTPUT_DIR,
    REQUEST_TIMEOUT,
    SHEET_ID,
    SHEET_NAME,
    WP_SITE_URL,
    classify_post,
    fetch_published_posts,
    find_header,
    row_value,
)

GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")
STRICT = "--strict" in sys.argv

REQUIRED_PAGES = [
    ("about-taxonguru", "TaxonGuru 소개"),
    ("editorial-policy", "편집 및 팩트체크 정책"),
    ("ai-use-policy", "AI 활용 정책"),
    ("contact-and-corrections", "문의 및 오류 제보"),
    ("privacy-policy", "개인정보처리방침"),
]

session = requests.Session()
session.headers.update({"User-Agent": "TaxonGuruReadiness/6.3"})


def log(message: str) -> None:
    print(message, flush=True)


def public_get(url: str) -> tuple[int, str, str]:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return response.status_code, str(response.url), response.text[:1_500_000]
    except requests.RequestException as exc:
        return 0, " ".join(str(exc).split())[:400], ""


def load_sheet() -> tuple[gspread.Worksheet, list[str], list[list[str]]]:
    if not GOOGLE_CREDENTIALS or not SHEET_ID:
        raise RuntimeError("GOOGLE_CREDENTIALS / SHEET_ID가 없습니다.")
    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    book = gc.open_by_key(SHEET_ID)
    ws = book.worksheet(SHEET_NAME)
    values = ws.get_all_values()
    return ws, values[0] if values else [], values[1:] if values else []


def sheet_summary(headers: list[str], rows: list[list[str]]) -> dict[str, Any]:
    status_idx = find_header(headers, ["상태", "진행상태"])
    guard_status_idx = find_header(headers, [GUARD_STATUS_HEADER])
    counts: Counter[str] = Counter()
    guard_counts: Counter[str] = Counter()
    for row in rows:
        status = row_value(row, status_idx)
        guard_status = row_value(row, guard_status_idx)
        if status:
            counts[status] += 1
        if guard_status:
            guard_counts[guard_status] += 1
    return {"status_counts": dict(counts), "guard_counts": dict(guard_counts)}


def write_readiness_sheet(report: dict[str, Any]) -> None:
    try:
        creds = json.loads(GOOGLE_CREDENTIALS)
        gc = gspread.service_account_from_dict(creds)
        book = gc.open_by_key(SHEET_ID)
        try:
            ws = book.worksheet("AdSense준비도")
        except gspread.WorksheetNotFound:
            ws = book.add_worksheet(title="AdSense준비도", rows=120, cols=4)
        rows: list[list[str]] = [
            ["항목", "값", "판정", "설명"],
            ["최근검사", report["checked_at_utc"], "", ""],
            ["최종판정", report["verdict"], report["verdict"], "READY일 때만 재심사 권장"],
            ["공개글수", str(report["published_posts"]["count"]), "", ""],
            ["공개글하드블로커", str(report["published_posts"]["hard_blocker_posts"]), "", ""],
            ["수동검수대기", str(report["sheet"]["manual_review_waiting"]), "", ""],
            ["재작성/정리대기", str(report["sheet"]["cleanup_waiting"]), "", ""],
            ["PublicGuard미확인공개글", str(report["sheet"]["published_guard_unconfirmed"]), "", ""],
            ["홈날짜중복", str(report["homepage"]["duplicate_date_pattern"]), "", ""],
            ["홈신뢰링크부족", ", ".join(report["homepage"]["missing_trust_links"]), "", ""],
            ["ads.txt", str(report["ads_txt"]["ok"]), "", report["ads_txt"].get("detail", "")],
        ]
        for issue in report["critical_issues"]:
            rows.append(["CRITICAL", issue, "수정필요", ""])
        for warning in report["warnings"]:
            rows.append(["WARNING", warning, "확인권장", ""])
        ws.clear()
        ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    except Exception as exc:
        log(f"⚠️ AdSense준비도 시트 갱신 실패: {' '.join(str(exc).split())[:300]}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    critical: list[str] = []
    warnings: list[str] = []

    home_status, home_final, home_html = public_get(f"{WP_SITE_URL}/")
    plain_home = re.sub(r"<[^>]+>", " ", home_html)
    duplicate_date = bool(
        re.search(
            r"\d{1,2}월\s*\d{1,2}\s*,?\s*20\d{2}\s*"
            r"\d{1,2}월\s*\d{1,2}\s*,?\s*20\d{2}",
            plain_home,
        )
    )
    trust_links: dict[str, bool] = {}
    for slug, _label in REQUIRED_PAGES:
        trust_links[slug] = bool(
            re.search(
                rf'href=["\'][^"\']*/{re.escape(slug)}/?(?:[?#][^"\']*)?["\']',
                home_html,
                flags=re.I,
            )
        )
    missing_trust = [slug for slug, found in trust_links.items() if not found]
    if home_status != 200:
        critical.append(f"홈페이지 HTTP 상태 이상: {home_status}")
    if duplicate_date:
        warnings.append(
            "홈페이지/글 목록에서 수정일+게시일이 붙어 보이는 날짜 중복 패턴이 있습니다. "
            "콘텐츠 품질 문제는 아니지만 재심사 전 테마 표시 개선을 권장합니다."
        )
    if missing_trust:
        warnings.append(
            "홈/푸터에서 일부 신뢰 페이지 링크가 보이지 않습니다: " + ", ".join(missing_trust)
        )

    page_results: list[dict[str, Any]] = []
    for slug, label in REQUIRED_PAGES:
        status, final_url, body = public_get(f"{WP_SITE_URL}/{slug}/")
        ok = status == 200 and len(re.sub(r"<[^>]+>", " ", body).strip()) > 120
        page_results.append(
            {"slug": slug, "label": label, "http_status": status, "url": final_url, "ok": ok}
        )
        if not ok:
            critical.append(f"필수 신뢰 페이지 공개 실패: {label} ({slug}) HTTP {status}")

    ads_status, ads_final, ads_body = public_get(f"{WP_SITE_URL}/ads.txt")
    ads_google_line = bool(
        re.search(r"(?im)^google\.com\s*,\s*pub-\d+\s*,\s*DIRECT(?:\s*,|$)", ads_body)
    )
    ads_ok = ads_status == 200 and ads_google_line
    if not ads_ok:
        warnings.append(
            "ads.txt에서 Google publisher DIRECT 라인을 확인하지 못했습니다. "
            "AdSense 승인 필수 조건은 아니지만 재심사 전 권장합니다."
        )

    posts = fetch_published_posts()
    post_results: list[dict[str, Any]] = []
    hard_count = 0
    for post_id, post in posts.items():
        check = classify_post(post)
        if check.hard_blockers:
            hard_count += 1
        post_results.append(
            {
                "post_id": post_id,
                "title": check.title,
                "url": check.url,
                "hard_blockers": check.hard_blockers,
                "warnings": check.warnings,
                "direct_source_links": check.direct_source_links,
                "intermediary_links": check.intermediary_links,
            }
        )
    if hard_count:
        critical.append(f"현재 공개 글 중 AdSense 하드 블로커가 남은 글: {hard_count}건")

    _ws, headers, rows = load_sheet()
    summary = sheet_summary(headers, rows)
    status_counts = Counter(summary["status_counts"])
    guard_counts = Counter(summary["guard_counts"])
    manual_waiting = sum(status_counts.get(s, 0) for s in MANUAL_REVIEW_STATES)
    cleanup_states = {
        "완료",
        "기존재작성대기",
        "기존재작성재시도",
        "기존정리오류",
    }
    cleanup_waiting = sum(status_counts.get(s, 0) for s in cleanup_states)
    if manual_waiting:
        critical.append(f"사람 최종 검수 대기: {manual_waiting}건")
    if cleanup_waiting:
        critical.append(f"기존 글 정리/재작성 대기: {cleanup_waiting}건")

    guard_status_idx = find_header(headers, [GUARD_STATUS_HEADER])
    post_id_idx = find_header(headers, ["WP_POST_ID", "WP POST ID"])
    en_post_id_idx = find_header(headers, ["EN_POST_ID", "영문 WP_POST_ID"])
    published_guard_unconfirmed = 0
    for row in rows:
        ids: list[int] = []
        for value in (row_value(row, post_id_idx), row_value(row, en_post_id_idx)):
            try:
                ids.append(int(value))
            except Exception:
                pass
        if not ids or not any(item_id in posts for item_id in ids):
            continue
        guard_status = row_value(row, guard_status_idx)
        if guard_status in {GUARD_REWRITE_REQUIRED, GUARD_MANUAL_REQUIRED, ""}:
            published_guard_unconfirmed += 1
    if published_guard_unconfirmed:
        critical.append(
            f"Public Guard 사람검수 확인이 끝나지 않은 공개 행: {published_guard_unconfirmed}건"
        )

    # Conservative internal gate. Google does not publish a numeric minimum,
    # so this is not presented as an official requirement.
    if len(posts) < 10:
        warnings.append(
            f"현재 공개 글이 {len(posts)}건입니다. Google은 공식 최소 글 수를 제시하지 않지만 "
            "사이트 전체 가치가 충분히 보이는지 확인을 권장합니다."
        )

    verdict = "READY" if not critical else "NOT READY"
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "site": WP_SITE_URL,
        "strict_mode": STRICT,
        "verdict": verdict,
        "homepage": {
            "http_status": home_status,
            "final_url": home_final,
            "duplicate_date_pattern": duplicate_date,
            "trust_links": trust_links,
            "missing_trust_links": missing_trust,
        },
        "required_pages": page_results,
        "ads_txt": {
            "http_status": ads_status,
            "final_url": ads_final,
            "google_direct_line": ads_google_line,
            "ok": ads_ok,
            "detail": "Google DIRECT line 확인" if ads_ok else "미확인",
        },
        "published_posts": {
            "count": len(posts),
            "hard_blocker_posts": hard_count,
            "items": post_results,
        },
        "sheet": {
            "status_counts": dict(status_counts),
            "guard_counts": dict(guard_counts),
            "manual_review_waiting": manual_waiting,
            "cleanup_waiting": cleanup_waiting,
            "published_guard_unconfirmed": published_guard_unconfirmed,
        },
        "critical_issues": critical,
        "warnings": warnings,
    }
    (OUTPUT_DIR / "adsense_readiness_v63.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_readiness_sheet(report)

    log("=" * 72)
    log("TaxonGuru AdSense Readiness v6.3")
    log(f"판정: {verdict}")
    log(
        f"공개글 {len(posts)} · 하드블로커 {hard_count} · "
        f"수동검수대기 {manual_waiting} · 정리대기 {cleanup_waiting} · "
        f"PublicGuard 미확인공개 {published_guard_unconfirmed}"
    )
    for issue in critical[:20]:
        log(f"❌ {issue}")
    for warning in warnings[:20]:
        log(f"⚠️ {warning}")
    log("=" * 72)

    if STRICT and verdict != "READY":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
