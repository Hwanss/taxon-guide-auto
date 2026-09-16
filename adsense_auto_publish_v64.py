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
AUTO_PUBLISH_DRY_RUN = os.getenv("AUTO_PUBLISH_DRY_RUN", "false").lower() == "true" or "--dry-run" in sys.argv
AUTO_PUBLISH_BATCH_SIZE = max(1, min(10, int(os.getenv("AUTO_PUBLISH_BATCH_SIZE", "4"))))
AUTO_PUBLISH_MIN_KO_SCORE = max(88, min(100, int(os.getenv("AUTO_PUBLISH_MIN_KO_SCORE", "98"))))
AUTO_PUBLISH_MIN_EN_SCORE = max(88, min(100, int(os.getenv("AUTO_PUBLISH_MIN_EN_SCORE", "96"))))
AUTO_PUBLISH_MIN_SOURCES = max(4, int(os.getenv("AUTO_PUBLISH_MIN_SOURCES", "4")))
AUTO_PUBLISH_MIN_KO_CHARS = max(1800, int(os.getenv("AUTO_PUBLISH_MIN_KO_CHARS", "2600")))
AUTO_PUBLISH_MIN_EN_WORDS = max(700, int(os.getenv("AUTO_PUBLISH_MIN_EN_WORDS", "950")))
AUTO_PUBLISH_REQUIRE_IMAGES = os.getenv("AUTO_PUBLISH_REQUIRE_IMAGES", "true").lower() == "true"
AUTO_PUBLISH_CHECK_SOURCE_LINKS = os.getenv("AUTO_PUBLISH_CHECK_SOURCE_LINKS", "true").lower() == "true"
AUTO_PUBLISH_ROLLBACK_ON_RENDER_FAILURE = os.getenv("AUTO_PUBLISH_ROLLBACK_ON_RENDER_FAILURE", "true").lower() == "true"
AUTO_REWRITE_FAILED_LEGACY = os.getenv("AUTO_REWRITE_FAILED_LEGACY", "true").lower() == "true"
MAX_REWRITE_ATTEMPTS = max(1, int(os.getenv("MAX_LEGACY_REWRITE_ATTEMPTS", "3")))
OUTPUT_DIR = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))

if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False

session = requests.Session()
session.headers.update({
    "User-Agent": "TaxonGuruAutoPublish/6.4",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
})
wp_auth = (WP_USER, WP_APP_PASSWORD)

MANUAL_STATES = {
    "기존수동검수대기",
    "수동검수대기",
    "한국어완료/영문수동검수대기",
}
PUBLIC_SKIP_STATES = {
    "대기",
    "완료",
    "기존재작성대기",
    "기존재작성재시도",
    "기존정리오류",
    "기존비공개보류",
    *MANUAL_STATES,
}
AUTO_GUARD_CONFIRMED = "자동최종검수통과"
HUMAN_GUARD_CONFIRMED = "사람검수확인"
GUARD_REWRITE_REQUIRED = "재작성필요"
AUTO_STATUS_HOLD = "사람검수필요"
AUTO_STATUS_PASS = "자동검수통과"
AUTO_STATUS_REWRITE = "자동재작성대기"

HEADER_ALIASES: dict[str, list[str]] = {
    "status": ["상태", "진행상태"],
    "scientific_name": ["학명", "학명(Scientific Name)", "학명 (Scientific Name)"],
    "post_id": ["WP_POST_ID", "WP POST ID"],
    "en_post_id": ["EN_POST_ID", "영문 WP_POST_ID"],
    "public_url": ["공개URL", "공개 URL"],
    "en_public_url": ["EN_공개URL", "EN 공개URL", "영문 공개URL"],
    "quality_score": ["품질점수", "품질 점수"],
    "en_quality_score": ["EN_품질점수", "EN 품질점수", "영문품질점수"],
    "source_count": ["자료수", "출처수", "출처 수"],
    "rewrite_attempts": ["재작성시도", "재작성 시도"],
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
    r"Scientific Backbone|Deep Anatomy|Evolutionary Context|Verdict\s*&\s*Trivia|"
    r"핵심\s*요약.{0,120}분류학적\s*위치",
    re.I | re.S,
)
BILINGUAL_RE = re.compile(
    r"Global Readers|English Version|\[2부|Part\s*2\s*:\s*English",
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
    direct_sources: list[str]
    text_length: int
    word_count: int
    image_count: int


@dataclass
class Candidate:
    mode: str  # manual | public
    row_number: int
    row: list[str]
    ko_post: dict[str, Any] | None = None
    en_post: dict[str, Any] | None = None


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
        number = int(float(str(raw).strip()))
        return number if number > 0 else None
    except Exception:
        return None


def safe_float(raw: Any) -> float:
    try:
        return float(str(raw).strip())
    except Exception:
        return 0.0


def text_only(raw: str) -> str:
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw or "", flags=re.I | re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())


def is_intermediary_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return True
    host = (parts.hostname or "").casefold()
    if host in INTERMEDIARY_HOSTS:
        return True
    return host in {"google.com", "www.google.com"} and parts.path.startswith(("/url", "/search"))


def is_external_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold()
    except ValueError:
        return False
    return bool(host and "taxonguru.com" not in host)


def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
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
                f"WordPress {method} {endpoint} 실패 HTTP {response.status_code}: {response.text[:400]}"
            )
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(str(last_error))


def fetch_post(post_id: int) -> dict[str, Any]:
    return wp_request(
        "GET",
        f"posts/{post_id}",
        params={"context": "edit", "_fields": "id,status,link,title,content,featured_media,modified_gmt"},
    ).json()


def check_post(post: dict[str, Any], *, is_english: bool) -> CheckResult:
    title_obj = post.get("title") or {}
    content_obj = post.get("content") or {}
    title = text_only(str(title_obj.get("raw") or title_obj.get("rendered") or ""))
    content = str(content_obj.get("raw") or content_obj.get("rendered") or "")
    text = text_only(content)
    reasons: list[str] = []

    if not title or len(title) < 8:
        reasons.append("제목 부족")
    if FIXED_TEMPLATE_RE.search(text):
        reasons.append("AI 고정 템플릿 흔적")
    if BILINGUAL_RE.search(content):
        reasons.append("한 페이지 내 한영 반복 흔적")
    if FAKE_EXPERT_RE.search(text):
        reasons.append("과장된 전문가/직함 표현")
    if "/ai-use-policy/" not in content:
        reasons.append("AI 활용정책 링크 없음")
    if not re.search(r"참고자료|참고문헌|References|Sources", text, re.I):
        reasons.append("참고자료 섹션 없음")

    links = re.findall(r'href=["\'](https?://[^"\']+)', content, flags=re.I)
    external_links = {url for url in links if is_external_url(url)}
    intermediary = {url for url in external_links if is_intermediary_url(url)}
    direct_external = sorted(url for url in external_links if not is_intermediary_url(url))
    if intermediary:
        reasons.append(f"Google/Vertex 중계링크 {len(intermediary)}건")
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
            r"CC\s*BY|CC0|Public domain|퍼블릭\s*도메인|Wikimedia Commons|"
            r"원본\s*파일|AI[- ]generated|AI\s*생성|Created by TaxonGuru",
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
    return CheckResult(
        ok=not reasons,
        reasons=list(dict.fromkeys(reasons)),
        warnings=[],
        direct_sources=direct_external,
        text_length=len(text),
        word_count=word_count,
        image_count=image_count,
    )


def check_source_links(urls: list[str]) -> tuple[list[str], list[str]]:
    broken: list[str] = []
    warnings: list[str] = []
    if not AUTO_PUBLISH_CHECK_SOURCE_LINKS:
        return broken, warnings
    for url in urls[:8]:
        try:
            response = session.head(url, timeout=min(12, REQUEST_TIMEOUT), allow_redirects=True)
            if response.status_code in {405, 501}:
                response = session.get(url, timeout=min(12, REQUEST_TIMEOUT), allow_redirects=True, stream=True)
            if response.status_code in {404, 410}:
                broken.append(f"{response.status_code} {url}")
            elif response.status_code >= 500:
                warnings.append(f"출처 서버 {response.status_code}: {url}")
        except requests.RequestException as exc:
            warnings.append(f"출처 접속 확인 보류: {url} · {type(exc).__name__}")
    return broken, warnings


def public_render_ok(url: str, *, is_english: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    except Exception as exc:
        return False, [f"공개 페이지 접속 실패: {type(exc).__name__}"]
    if response.status_code != 200:
        return False, [f"공개 페이지 HTTP {response.status_code}"]
    html_text = response.text
    text = text_only(html_text)
    if len(text) < 1500:
        reasons.append("공개 페이지 렌더링 본문이 비정상적으로 짧음")
    if FIXED_TEMPLATE_RE.search(text) or BILINGUAL_RE.search(html_text) or FAKE_EXPERT_RE.search(text):
        reasons.append("공개 렌더링에서 금지 패턴 재검출")
    if is_english and re.search(r"[가-힣\u3040-\u30FF]", text):
        reasons.append("공개 영문 페이지에 언어 혼입")
    if not is_english and re.search(r"[\u3040-\u30FF]", text):
        reasons.append("공개 한국어 페이지에 일본어 혼입")
    return not reasons, reasons


def ensure_header(ws: gspread.Worksheet, headers: list[str], name: str) -> tuple[list[str], int]:
    idx = find_header(headers, [name])
    if idx is not None:
        return headers, idx
    if ws.col_count < len(headers) + 1:
        ws.resize(cols=len(headers) + 1)
    ws.update_cell(1, len(headers) + 1, name)
    headers = headers + [name]
    return headers, len(headers) - 1


def write_cells(ws: gspread.Worksheet, row_number: int, updates: dict[int | None, str]) -> None:
    cells = [gspread.Cell(row_number, idx + 1, item) for idx, item in updates.items() if idx is not None]
    if cells:
        ws.update_cells(cells, value_input_option="USER_ENTERED")


def run_self_test() -> int:
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
    if not check_post(sample_good, is_english=False).ok:
        raise SystemExit("SELF_TEST_FAIL_GOOD")
    sample_bad = {
        "title": {"raw": "짧음"},
        "content": {"raw": "<p>Scientific Backbone English Version</p>"},
        "featured_media": 0,
    }
    if check_post(sample_bad, is_english=False).ok:
        raise SystemExit("SELF_TEST_FAIL_BAD")
    sample_hook = dict(sample_good)
    sample_hook["content"] = {"raw": str(sample_good["content"]["raw"]) + "<p>hook-and-loop 구조라는 일반 표현</p>"}
    if not check_post(sample_hook, is_english=False).ok:
        raise SystemExit("SELF_TEST_FAIL_FALSE_POSITIVE_HOOK")
    print("SELF_TEST_OK")
    return 0


def row_base_reasons(row: list[str], idx: dict[str, int | None]) -> list[str]:
    reasons: list[str] = []
    ko_score = safe_float(value(row, idx["quality_score"]))
    en_score = safe_float(value(row, idx["en_quality_score"])) if idx["en_quality_score"] is not None else 0.0
    source_count = safe_int(value(row, idx["source_count"])) or 0
    if ko_score < AUTO_PUBLISH_MIN_KO_SCORE:
        reasons.append(f"KO 점수 {ko_score:g}<{AUTO_PUBLISH_MIN_KO_SCORE}")
    if en_score < AUTO_PUBLISH_MIN_EN_SCORE:
        reasons.append(f"EN 점수 {en_score:g}<{AUTO_PUBLISH_MIN_EN_SCORE}")
    if source_count < AUTO_PUBLISH_MIN_SOURCES:
        reasons.append(f"자료수 {source_count}<{AUTO_PUBLISH_MIN_SOURCES}")
    if idx["error"] is not None and value(row, idx["error"]):
        reasons.append("한국어 오류 필드 존재")
    if idx["en_error"] is not None and value(row, idx["en_error"]):
        reasons.append("영문 오류 필드 존재")
    return reasons


def evaluate_pair(
    row: list[str],
    idx: dict[str, int | None],
    ko_post: dict[str, Any] | None,
    en_post: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    reasons = row_base_reasons(row, idx)
    warnings: list[str] = []
    if ko_post is None:
        reasons.append("한국어 WordPress 글 확인 실패")
    else:
        ko_check = check_post(ko_post, is_english=False)
        reasons.extend(f"KO: {item}" for item in ko_check.reasons)
        broken, link_warnings = check_source_links(ko_check.direct_sources)
        reasons.extend(f"KO: 깨진 출처 {item}" for item in broken)
        warnings.extend(f"KO: {item}" for item in link_warnings)
    if en_post is None:
        reasons.append("영문 WordPress 글 확인 실패")
    else:
        en_check = check_post(en_post, is_english=True)
        reasons.extend(f"EN: {item}" for item in en_check.reasons)
        broken, link_warnings = check_source_links(en_check.direct_sources)
        reasons.extend(f"EN: 깨진 출처 {item}" for item in broken)
        warnings.extend(f"EN: {item}" for item in link_warnings)
    return list(dict.fromkeys(reasons)), list(dict.fromkeys(warnings))


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_test()
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
    candidates: list[Candidate] = []

    # 1) 사람검수대기 초안을 우선 처리합니다. 한 번 실패해 사람검수가 필요하다고 판정된
    # 행은 매 실행의 앞자리를 계속 차지하지 않도록 자동 큐에서 제외합니다.
    for row_number, row in enumerate(rows, start=2):
        if len(candidates) >= AUTO_PUBLISH_BATCH_SIZE:
            break
        if value(row, idx["status"]) not in MANUAL_STATES:
            continue
        if value(row, auto_status_idx) == AUTO_STATUS_HOLD:
            continue
        candidates.append(Candidate("manual", row_number, row))

    # 2) 수동 큐가 줄어들면 과거 공개 글 중 Public Guard 확인이 비어 있는 행도 엄격하게
    # 다시 검사합니다. 통과하면 자동검수 확인으로 기록하고, 실패하면 재작성 큐로 보냅니다.
    if len(candidates) < AUTO_PUBLISH_BATCH_SIZE:
        for row_number, row in enumerate(rows, start=2):
            if len(candidates) >= AUTO_PUBLISH_BATCH_SIZE:
                break
            status = value(row, idx["status"])
            guard_status = value(row, idx["guard_status"])
            if status in PUBLIC_SKIP_STATES or "대기" in status or "오류" in status or "예약" in status:
                continue
            if guard_status in {HUMAN_GUARD_CONFIRMED, AUTO_GUARD_CONFIRMED}:
                continue
            post_id = safe_int(value(row, idx["post_id"]))
            en_post_id = safe_int(value(row, idx["en_post_id"])) if idx["en_post_id"] is not None else None
            if not post_id or not en_post_id:
                continue
            try:
                ko_post = fetch_post(post_id)
                en_post = fetch_post(en_post_id)
            except Exception:
                continue
            if str(ko_post.get("status")) == "publish" and str(en_post.get("status")) == "publish":
                candidates.append(Candidate("public", row_number, row, ko_post, en_post))

    log(
        f"🚦 v6.4 자동 최종검수 시작: 후보 {len(candidates)}건 / "
        f"KO≥{AUTO_PUBLISH_MIN_KO_SCORE}, EN≥{AUTO_PUBLISH_MIN_EN_SCORE}, "
        f"직접출처≥{AUTO_PUBLISH_MIN_SOURCES} · dry_run={AUTO_PUBLISH_DRY_RUN}"
    )

    published = 0
    verified_public = 0
    requeued = 0
    held = 0
    errors = 0
    dry_passed = 0

    for candidate in candidates:
        row_number, row, mode = candidate.row_number, candidate.row, candidate.mode
        status = value(row, idx["status"])
        scientific_name = value(row, idx["scientific_name"])
        post_id = safe_int(value(row, idx["post_id"]))
        en_post_id = safe_int(value(row, idx["en_post_id"])) if idx["en_post_id"] is not None else None
        rewrite_attempts = safe_int(value(row, idx["rewrite_attempts"])) or 0

        ko_post = candidate.ko_post
        en_post = candidate.en_post
        try:
            if not post_id:
                raise RuntimeError("WP_POST_ID 없음")
            if not en_post_id:
                raise RuntimeError("EN_POST_ID 없음")
            ko_post = ko_post or fetch_post(post_id)
            en_post = en_post or fetch_post(en_post_id)
            reasons, warnings = evaluate_pair(row, idx, ko_post, en_post)
        except Exception as exc:
            reasons = [f"검증 준비 실패: {type(exc).__name__}: {exc}"]
            warnings = []

        if reasons:
            can_rewrite = bool(
                AUTO_REWRITE_FAILED_LEGACY
                and scientific_name
                and post_id
                and status.startswith("기존")
                and rewrite_attempts < MAX_REWRITE_ATTEMPTS
            )
            if mode == "public" and scientific_name and post_id and rewrite_attempts < MAX_REWRITE_ATTEMPTS:
                can_rewrite = True

            if can_rewrite and not AUTO_PUBLISH_DRY_RUN:
                # 이미 공개된 과거 글의 경우 품질 미달 상태를 계속 노출하지 않도록 초안으로
                # 내리고, 기존 안전 재작성 파이프라인에 넘깁니다.
                if mode == "public":
                    for pid, post in ((post_id, ko_post), (en_post_id, en_post)):
                        if pid and post and str(post.get("status")) == "publish":
                            wp_request("POST", f"posts/{pid}", json={"status": "draft"})
                write_cells(ws, row_number, {
                    idx["status"]: "기존재작성대기",
                    idx["guard_status"]: GUARD_REWRITE_REQUIRED,
                    idx["guard_reason"]: " | ".join(reasons)[:1800],
                    idx["cleanup_note"]: "v6.4 엄격 자동검수 미달 → 기존 재작성 대기열 자동 편입",
                    idx["error"]: "",
                    auto_status_idx: AUTO_STATUS_REWRITE,
                    auto_reason_idx: " | ".join(reasons)[:45000],
                    auto_publish_idx: "재작성후재검수",
                })
                requeued += 1
                log(f"  🔁 행 {row_number}: 자동검수 미달 → 재작성 대기열 편입")
            else:
                held += 1
                if not AUTO_PUBLISH_DRY_RUN:
                    write_cells(ws, row_number, {
                        auto_status_idx: AUTO_STATUS_HOLD,
                        auto_reason_idx: " | ".join(reasons)[:45000],
                        auto_publish_idx: "미공개" if mode == "manual" else "기존공개-사람확인필요",
                    })
                log(f"  👤 행 {row_number}: 사람검수 필요 · " + "; ".join(reasons[:6]))
            continue

        if AUTO_PUBLISH_DRY_RUN:
            dry_passed += 1
            log(f"  🧪 행 {row_number}: {mode} DRY-RUN 엄격 조건 통과")
            continue

        # 이미 공개된 행은 상태 변경 없이 실제 페이지를 재검증하고 auto-confirm만 기록합니다.
        if mode == "public":
            try:
                assert ko_post is not None and en_post is not None
                ko_url = str(ko_post.get("link", "")).strip()
                en_url = str(en_post.get("link", "")).strip()
                ko_ok, ko_reasons = public_render_ok(ko_url, is_english=False)
                en_ok, en_reasons = public_render_ok(en_url, is_english=True)
                if not ko_ok or not en_ok:
                    raise RuntimeError("공개 렌더링 검증 실패: " + "; ".join([
                        *("KO: " + item for item in ko_reasons),
                        *("EN: " + item for item in en_reasons),
                    ]))
                write_cells(ws, row_number, {
                    idx["guard_status"]: AUTO_GUARD_CONFIRMED,
                    idx["guard_reason"]: "v6.4 엄격 자동 최종검수 및 실제 공개 렌더링 검증 통과",
                    auto_status_idx: AUTO_STATUS_PASS,
                    auto_reason_idx: ("엄격 조건 전체 통과" + (" · 경고: " + " | ".join(warnings[:4]) if warnings else ""))[:45000],
                    auto_publish_idx: "기존공개검증완료",
                })
                verified_public += 1
                log(f"  ✅ 행 {row_number}: 기존 공개 KO/EN 엄격 재검증 통과")
            except Exception as exc:
                errors += 1
                write_cells(ws, row_number, {
                    auto_status_idx: "공개검증실패",
                    auto_reason_idx: str(exc)[:45000],
                    auto_publish_idx: "기존공개-재확인필요",
                })
                log(f"  ⚠️ 행 {row_number}: 기존 공개 페이지 재검증 실패: {exc}")
            continue

        # 수동검수대기 초안: 조건 통과 시 KO/EN을 조건부 자동 공개합니다.
        changed_posts: list[tuple[int, str]] = []
        try:
            assert ko_post is not None and en_post is not None and post_id and en_post_id
            for pid, post in ((post_id, ko_post), (en_post_id, en_post)):
                old_status = str(post.get("status", "draft"))
                if old_status not in {"draft", "pending", "private", "publish"}:
                    raise RuntimeError(f"자동공개 허용 대상이 아닌 WordPress 상태: {pid}={old_status}")
                if old_status != "publish":
                    wp_request("POST", f"posts/{pid}", json={"status": "publish"})
                    changed_posts.append((pid, old_status))

            ko_live = fetch_post(post_id)
            en_live = fetch_post(en_post_id)
            ko_url = str(ko_live.get("link", "")).strip()
            en_url = str(en_live.get("link", "")).strip()
            if not ko_url or not en_url:
                raise RuntimeError("공개 URL 확인 실패")
            ko_ok, ko_reasons = public_render_ok(ko_url, is_english=False)
            en_ok, en_reasons = public_render_ok(en_url, is_english=True)
            if not ko_ok or not en_ok:
                raise RuntimeError("공개 후 렌더링 검증 실패: " + "; ".join([
                    *("KO: " + item for item in ko_reasons),
                    *("EN: " + item for item in en_reasons),
                ]))

            final_state = "기존한영수정완료" if status.startswith("기존") else "완료"
            write_cells(ws, row_number, {
                idx["status"]: final_state,
                idx["public_url"]: ko_url,
                idx["en_public_url"]: en_url,
                idx["guard_status"]: AUTO_GUARD_CONFIRMED,
                idx["guard_reason"]: "v6.4 엄격 자동 최종검수 및 공개 후 렌더링 재검증 통과",
                idx["cleanup_note"]: "v6.4 조건부 자동공개 완료 · 공개 후 렌더링 재검증 통과",
                auto_status_idx: AUTO_STATUS_PASS,
                auto_reason_idx: ("엄격 조건 전체 통과" + (" · 경고: " + " | ".join(warnings[:4]) if warnings else ""))[:45000],
                auto_publish_idx: "공개완료",
            })
            published += 1
            log(f"  ✅ 행 {row_number}: KO/EN 자동 최종검수 통과 → 공개 및 렌더링 재검증 완료")
        except Exception as exc:
            errors += 1
            if AUTO_PUBLISH_ROLLBACK_ON_RENDER_FAILURE:
                for pid, old_status in reversed(changed_posts):
                    try:
                        wp_request("POST", f"posts/{pid}", json={"status": old_status})
                    except Exception as rollback_exc:
                        log(f"    ⚠️ 롤백 실패 {pid}: {type(rollback_exc).__name__}")
            write_cells(ws, row_number, {
                auto_status_idx: "공개실패",
                auto_reason_idx: str(exc)[:45000],
                auto_publish_idx: "롤백/미공개",
            })
            log(f"  ⚠️ 행 {row_number}: 자동공개 실패 → 변경분 롤백: {exc}")

    manual_total = sum(status_counter.get(state, 0) for state in MANUAL_STATES)
    log(
        f"✅ v6.4 자동 최종검수 종료: 자동공개 {published} · 기존공개검증 {verified_public} · "
        f"재작성회송 {requeued} · DRY통과 {dry_passed} · 사람확인 {held} · 오류 {errors} · "
        f"실행 전 수동큐 {manual_total}"
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "auto_publish_v64_summary.json").write_text(
        json.dumps({
            "dry_run": AUTO_PUBLISH_DRY_RUN,
            "published": published,
            "verified_public": verified_public,
            "requeued": requeued,
            "dry_passed": dry_passed,
            "held": held,
            "errors": errors,
            "candidate_count": len(candidates),
            "manual_queue_before": manual_total,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
