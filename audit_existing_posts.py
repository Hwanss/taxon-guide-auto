from __future__ import annotations

import csv
import html
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Literal, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import gspread
import requests
import urllib3.util.connection as urllib3_connection
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# =============================================================================
# TaxonGuru 기존 게시물 감사/수정 전용 파이프라인
# - 최근 수정글부터 처리
# - report_only: 보고서만 생성
# - safe_fix: 자동검수 배너/이미지 크기 등 안전한 구조만 수정
# - rewrite_recent: B/C 등급 글을 최신순으로 재조사하여 기존 URL에 덮어쓰기
# - 삭제하지 않음. D등급은 '삭제검토'로만 표시(옵션 사용 시에만 초안 전환)
# =============================================================================

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
WP_API = f"{WP_SITE_URL}/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
SHEET_ID = os.environ["SHEET_ID"]
TOPIC_SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")
AUDIT_SHEET_NAME = os.getenv("AUDIT_SHEET_NAME", "콘텐츠감사")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "admin@taxonguru.com")

AUDIT_MODE = os.getenv("AUDIT_MODE", "report_only").strip().lower()
BATCH_SIZE = max(1, min(20, int(os.getenv("AUDIT_BATCH_SIZE", "3"))))
INCLUDE_ALREADY_AUDITED = os.getenv("INCLUDE_ALREADY_AUDITED", "false").lower() == "true"
CREATE_ENGLISH = os.getenv("AUDIT_CREATE_ENGLISH", "true").lower() == "true"
DRAFT_GRADE_D = os.getenv("AUDIT_DRAFT_GRADE_D", "false").lower() == "true"
INCLUDE_ENGLISH_POSTS = os.getenv("AUDIT_INCLUDE_ENGLISH_POSTS", "false").lower() == "true"
MIN_SOURCE_COUNT = max(3, int(os.getenv("MIN_SOURCE_COUNT", "4")))
MIN_QUALITY_SCORE = max(70, int(os.getenv("MIN_QUALITY_SCORE", "85")))
BODY_IMAGE_MAX_WIDTH = max(480, int(os.getenv("BODY_IMAGE_MAX_WIDTH", "720")))
BODY_IMAGE_MAX_HEIGHT = max(320, int(os.getenv("BODY_IMAGE_MAX_HEIGHT", "520")))
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))
FORCE_IPV4 = os.getenv("FORCE_IPV4", "true").lower() == "true"
WP_CONNECT_RETRIES = max(1, int(os.getenv("WP_CONNECT_RETRIES", "5")))
WP_CONNECT_RETRY_DELAY = max(1.0, float(os.getenv("WP_CONNECT_RETRY_DELAY", "3")))
RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", "gemini-3.6-flash")
WRITER_MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-3.6-flash")
REVIEW_MODEL = os.getenv("GEMINI_REVIEW_MODEL", "gemini-3.6-flash")
OUTPUT_DIR = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))
AUDIT_TARGET_STATUS = os.getenv("AUDIT_TARGET_STATUS", "").strip()
AUTO_CLEANUP_MODE = os.getenv("AUTO_CLEANUP_MODE", "false").lower() == "true"
AUTO_FAIL_CLOSED_DRAFT = os.getenv("AUTO_FAIL_CLOSED_DRAFT", "true").lower() == "true"
AUTO_TRASH_GRADE_D = os.getenv("AUTO_TRASH_GRADE_D", "false").lower() == "true"
QUEUE_GRADE_D_FOR_REWRITE = os.getenv("QUEUE_GRADE_D_FOR_REWRITE", "true").lower() == "true"
ADSENSE_RECOVERY_MODE = os.getenv("ADSENSE_RECOVERY_MODE", "false").lower() == "true"

if FORCE_IPV4:
    # GitHub-hosted runners can occasionally resolve a site to IPv6 even when the route is unavailable.
    # urllib3 then raises Errno 101 before an HTTP response exists. Force IPv4 for all requests in this run.
    urllib3_connection.HAS_IPV6 = False

VALID_MODES = {"report_only", "safe_fix", "rewrite_recent"}
if AUDIT_MODE not in VALID_MODES:
    raise ValueError(f"AUDIT_MODE은 {sorted(VALID_MODES)} 중 하나여야 합니다: {AUDIT_MODE}")

session = requests.Session()
session.headers.update(
    {
        "User-Agent": f"TaxonGuruContentAuditor/4.0 ({WP_SITE_URL}; {CONTACT_EMAIL})",
        "Accept": "application/json",
    }
)
wp_auth = (WP_USER, WP_APP_PASSWORD)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

AUDIT_HEADERS = [
    "감사상태",
    "감사일시",
    "처리모드",
    "게시물ID",
    "수정일",
    "제목",
    "URL",
    "학명",
    "구조점수",
    "사실점수",
    "종합점수",
    "등급",
    "권장조치",
    "실제처리",
    "출처수",
    "본문글자수",
    "이미지수",
    "외부링크수",
    "주요문제",
    "중대오류",
    "근거부족",
    "백업파일",
    "오류",
]

TOPIC_ALIASES: dict[str, list[str]] = {
    "status": ["상태"],
    "scientific_name": ["학명", "학명(Scientific Name)", "학명 (Scientific Name)"],
    "title": ["국문/영문명"],
    "slug": ["슬러그", "슬러그(Slug)", "슬러그 (Slug)"],
    "post_id": ["WP_POST_ID", "WP POST ID"],
    "en_post_id": ["EN_POST_ID", "영문 WP_POST_ID"],
    "quality_score": ["품질점수"],
    "en_quality_score": ["EN_품질점수"],
    "public_url": ["공개URL"],
    "en_public_url": ["EN_공개URL"],
    "source_count": ["자료수"],
    "error": ["오류"],
    "en_error": ["영문오류"],
    "rewrite_attempts": ["재작성시도", "재작성 시도"],
    "cleanup_note": ["정리메모", "정리 메모"],
}

FIXED_TEMPLATE_RE = re.compile(
    r"Hook|Scientific Backbone|Deep Anatomy|Evolutionary Context|Verdict\s*&\s*Trivia|"
    r"핵심\s*요약.{0,120}분류학적\s*위치",
    re.I | re.S,
)
BILINGUAL_RE = re.compile(
    r"Global Readers|English Version|\[2부|Part\s*2\s*:\s*English|<h[1-6][^>]*>\s*English",
    re.I,
)
FAKE_EXPERT_RE = re.compile(
    r"수석\s*(?:고생물학자|생물학자|해양생물학자)|제왕적\s*해양생물학자|"
    r"chief\s+(?:paleontologist|biologist)",
    re.I,
)
AUTO_REVIEW_BLOCK_RE = re.compile(
    r"<(?P<tag>div|section|p)[^>]*>\s*(?:<[^>]+>\s*)*자동\s*품질(?:검사|검수).*?</(?P=tag)>",
    re.I | re.S,
)
AUTO_REVIEW_TEXT_RE = re.compile(
    r"자동\s*품질(?:검사|검수)\s*(?:통과|결과)?[^<\n]{0,350}(?:예약|점수|출처)[^<\n]{0,350}",
    re.I,
)


class ResearchSource(BaseModel):
    title: str
    url: str
    publisher: str = ""
    source_type: str = "web"
    accessed_date: str = ""


class VerifiedFact(BaseModel):
    claim: str
    source_numbers: list[int] = Field(default_factory=list)


class ResearchPackage(BaseModel):
    accepted_scientific_name: str = ""
    common_name_ko: str = ""
    common_name_en: str = ""
    taxonomy: str = ""
    overview: str = ""
    verified_facts: list[VerifiedFact] = Field(default_factory=list)
    misconceptions: list[VerifiedFact] = Field(default_factory=list)
    uncertain_claims: list[VerifiedFact] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AuditDecision(BaseModel):
    factual_score: int = Field(ge=0, le=100)
    editorial_score: int = Field(ge=0, le=100)
    critical_errors: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    grade: Literal["A", "B", "C", "D"]
    recommended_action: Literal["유지", "안전보완", "전면재작성", "초안전환검토", "삭제통합검토"]
    reason: str


class ArticleMeta(BaseModel):
    title: str
    slug: str
    excerpt: str
    seo_description: str
    tags: list[str] = Field(default_factory=list)


class RewriteReview(BaseModel):
    score: int = Field(ge=0, le=100)
    critical_errors: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    style_issues: list[str] = Field(default_factory=list)
    passed: bool


@dataclass
class StructuralResult:
    score: int
    issues: list[str]
    text_length: int
    source_links: int
    images: int
    fixed_template: bool
    bilingual: bool
    fake_expert: bool
    has_references: bool
    license_mentions: int


@dataclass
class TopicRow:
    row_number: int
    values: list[str]
    status: str
    scientific_name: str
    slug: str
    post_id: int | None
    en_post_id: int | None
    rewrite_attempts: int


TModel = TypeVar("TModel", bound=BaseModel)


def log(message: str) -> None:
    print(message, flush=True)


def safe_int(value: Any) -> int | None:
    try:
        number = int(str(value).strip())
        return number if number > 0 else None
    except Exception:
        return None


def normalize_header(value: str) -> str:
    value = re.sub(r"\([^)]*\)", "", value or "")
    return re.sub(r"[\s_\-/]+", "", value).lower()


def header_index(headers: list[str], key: str) -> int | None:
    normalized = [normalize_header(item) for item in headers]
    # Unknown logical fields should never crash a cleanup run.
    # Fall back to the logical key itself so a newly added sheet column can still match.
    aliases = TOPIC_ALIASES.get(key, [key])
    for alias in aliases:
        target = normalize_header(alias)
        if target in normalized:
            return normalized.index(target)
    return None


def get_value(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index]).strip()


def text_only(value: str) -> str:
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(value).split())


def _is_network_error(exc: BaseException) -> bool:
    text = " ".join(str(exc).split()).lower()
    markers = (
        "network is unreachable",
        "failed to establish a new connection",
        "temporary failure in name resolution",
        "name resolution",
        "connection refused",
        "connection reset",
        "max retries exceeded",
    )
    return isinstance(exc, requests.RequestException) or any(marker in text for marker in markers)


def preflight_wordpress() -> None:
    """Verify WordPress REST connectivity before Sheets/Gemini work starts."""
    url = f"{WP_API}/posts"
    last_error: BaseException | None = None
    for attempt in range(1, WP_CONNECT_RETRIES + 1):
        try:
            response = session.get(
                url,
                params={"per_page": 1, "context": "edit", "_fields": "id,status,modified"},
                auth=wp_auth,
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code in {200, 401, 403}:
                if response.status_code != 200:
                    raise RuntimeError(
                        f"WordPress REST 인증 실패 ({response.status_code}). WP_USER/WP_APP_PASSWORD를 확인하세요: "
                        f"{response.text[:400]}"
                    )
                log(f"🌐 WordPress REST 연결 정상 · IPv4 강제={'ON' if FORCE_IPV4 else 'OFF'}")
                return
            raise RuntimeError(f"WordPress REST 사전확인 실패 ({response.status_code}): {response.text[:400]}")
        except RuntimeError:
            raise
        except BaseException as exc:
            last_error = exc
            if attempt < WP_CONNECT_RETRIES:
                wait = WP_CONNECT_RETRY_DELAY * attempt
                log(f"⚠️ WordPress 연결 재시도 {attempt}/{WP_CONNECT_RETRIES}: {exc} · {wait:.0f}초 후 재시도")
                time.sleep(wait)
    raise RuntimeError(
        "GitHub Runner에서 WordPress에 연결할 수 없습니다. 감사/수정은 시작하지 않았습니다. "
        f"IPv4 강제={'ON' if FORCE_IPV4 else 'OFF'} · 마지막 오류: {last_error}"
    )


def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    last_error: BaseException | None = None
    for attempt in range(1, 4):
        try:
            response = session.request(
                method,
                f"{WP_API}/{endpoint.lstrip('/')}",
                auth=wp_auth,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"WordPress {method} {endpoint} 실패 ({response.status_code}): {response.text[:700]}")
            return response
        except RuntimeError:
            raise
        except BaseException as exc:
            last_error = exc
            if not _is_network_error(exc) or attempt >= 3:
                break
            time.sleep(attempt * 2)
    raise RuntimeError(f"WordPress {method} {endpoint} 네트워크 실패: {last_error}")


def gemini_json(model: str, prompt: str, schema: type[TModel], max_tokens: int = 4096) -> TModel:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=max_tokens,
                    temperature=0.15,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                return parsed
            if parsed is not None:
                return schema.model_validate(parsed)
            return schema.model_validate_json(str(response.text or ""))
        except Exception as exc:
            last_error = exc
            log(f"    ⚠️ JSON 생성 재시도 {attempt}/3: {' '.join(str(exc).split())[:350]}")
            time.sleep(attempt * 2)
    raise RuntimeError(f"Gemini 구조화 응답 실패: {last_error}")


def gemini_text(model: str, prompt: str, max_tokens: int = 12288) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.55,
                ),
            )
            value = str(response.text or "").strip()
            value = re.sub(r"^```(?:html)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
            if len(value) < 1000:
                raise ValueError(f"본문이 너무 짧습니다: {len(value)}자")
            return value
        except Exception as exc:
            last_error = exc
            log(f"    ⚠️ 장문 생성 재시도 {attempt}/3: {' '.join(str(exc).split())[:350]}")
            time.sleep(attempt * 2)
    raise RuntimeError(f"Gemini 장문 응답 실패: {last_error}")


def fetch_posts() -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    page = 1
    while True:
        response = wp_request(
            "GET",
            "posts",
            params={
                "status": "publish",
                "per_page": 100,
                "page": page,
                "context": "edit",
                "orderby": "modified",
                "order": "desc",
            },
        )
        batch = response.json()
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    if not INCLUDE_ENGLISH_POSTS:
        posts = [post for post in posts if "/en/" not in str(post.get("link", ""))]
    return posts


def connect_sheets() -> tuple[gspread.Worksheet, gspread.Worksheet]:
    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    book = gc.open_by_key(SHEET_ID)
    topic_ws = book.worksheet(TOPIC_SHEET_NAME)
    try:
        audit_ws = book.worksheet(AUDIT_SHEET_NAME)
    except gspread.WorksheetNotFound:
        audit_ws = book.add_worksheet(title=AUDIT_SHEET_NAME, rows=1000, cols=len(AUDIT_HEADERS))
    if audit_ws.col_count < len(AUDIT_HEADERS):
        audit_ws.resize(cols=len(AUDIT_HEADERS))
    first_row = audit_ws.row_values(1)
    if first_row != AUDIT_HEADERS:
        audit_ws.update("A1", [AUDIT_HEADERS])
    return topic_ws, audit_ws


def load_topic_rows(ws: gspread.Worksheet) -> tuple[list[str], list[TopicRow]]:
    records = ws.get_all_values()
    if not records:
        return [], []
    headers = records[0]
    indexes = {key: header_index(headers, key) for key in TOPIC_ALIASES}
    rows: list[TopicRow] = []
    for row_number, row in enumerate(records[1:], start=2):
        rows.append(
            TopicRow(
                row_number=row_number,
                values=row,
                status=get_value(row, indexes["status"]),
                scientific_name=get_value(row, indexes["scientific_name"]),
                slug=get_value(row, indexes["slug"]),
                post_id=safe_int(get_value(row, indexes["post_id"])),
                en_post_id=safe_int(get_value(row, indexes["en_post_id"])),
                rewrite_attempts=safe_int(get_value(row, indexes.get("rewrite_attempts"))) or 0,
            )
        )
    return headers, rows


def match_topic_row(post: dict[str, Any], rows: list[TopicRow]) -> TopicRow | None:
    post_id = safe_int(post.get("id"))
    slug = str(post.get("slug", "")).strip()
    for row in rows:
        if row.post_id and row.post_id == post_id:
            return row
    for row in rows:
        if row.slug and row.slug == slug:
            return row

    # 오래된 행은 WP_POST_ID가 비어 있거나 슬러그가 수정된 경우가 있어,
    # 제목/본문에 학명이 명확히 포함되면 마지막 보조 매칭으로 사용합니다.
    title = str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or "")
    content = str(post.get("content", {}).get("raw") or post.get("content", {}).get("rendered") or "")
    haystack = text_only(f"{title} {content[:5000]}").lower()
    for row in rows:
        if row.scientific_name and row.scientific_name.lower() in haystack:
            return row
    return None


def update_topic_fields(ws: gspread.Worksheet, headers: list[str], row_number: int, fields: dict[str, Any]) -> None:
    cells: list[gspread.Cell] = []
    for key, value in fields.items():
        index = header_index(headers, key)
        if index is None:
            continue
        cells.append(gspread.Cell(row_number, index + 1, str(value)))
    if cells:
        ws.update_cells(cells, value_input_option="USER_ENTERED")


def audited_post_ids(audit_ws: gspread.Worksheet, current_mode: str) -> set[int]:
    """Return post IDs already completed for the current processing stage.

    A report-only run must not prevent a later safe-fix or rewrite run. Likewise,
    a safe-fix run must not block a later full rewrite. Only the same or a stronger
    processing mode is treated as completed.
    """
    mode_rank = {"report_only": 1, "safe_fix": 2, "rewrite_recent": 3}
    required_rank = mode_rank.get(current_mode, 1)
    result: set[int] = set()
    for row in audit_ws.get_all_values()[1:]:
        if len(row) < 4 or row[0] not in {"완료", "유지", "수정완료", "삭제검토", "초안전환"}:
            continue
        previous_mode = row[2].strip() if len(row) > 2 else "report_only"
        if mode_rank.get(previous_mode, 1) < required_rank:
            continue
        post_id = safe_int(row[3])
        if post_id:
            result.add(post_id)
    return result


def append_audit_row(audit_ws: gspread.Worksheet, data: dict[str, Any]) -> None:
    row = [str(data.get(header, "")) for header in AUDIT_HEADERS]
    audit_ws.append_row(row, value_input_option="USER_ENTERED")


def structural_audit(post: dict[str, Any]) -> StructuralResult:
    content = str(post.get("content", {}).get("raw") or post.get("content", {}).get("rendered") or "")
    text = text_only(content)
    all_external_links = {
        link
        for link in re.findall(r'href=["\'](https?://[^"\']+)', content, flags=re.I)
        if "taxonguru.com" not in link
    }
    intermediary_links = sorted(link for link in all_external_links if is_source_intermediary_url(link))
    external = {link for link in all_external_links if not is_source_intermediary_url(link)}
    post_link = str(post.get("link", ""))
    is_english_page = "/en/" in (urlsplit(post_link).path or "")
    has_han_or_kana = bool(re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", text))
    has_hangul = bool(re.search(r"[가-힣]", text))
    old_policy_link = "/ai-policy/" in content
    missing_editorial_policy_link = "/ai-use-policy/" not in content
    images = len(re.findall(r"<img\b", content, flags=re.I))
    license_mentions = len(
        re.findall(r"CC\s*BY|CC0|Public domain|퍼블릭\s*도메인|Wikimedia Commons|원본\s*파일|AI[- ]generated|AI\s*생성|Created by TaxonGuru", content, re.I)
    )
    fixed_template = bool(FIXED_TEMPLATE_RE.search(text))
    bilingual = bool(BILINGUAL_RE.search(content))
    fake_expert = bool(FAKE_EXPERT_RE.search(text))
    has_references = bool(re.search(r"참고자료|참고문헌|References|Sources", text, re.I))

    score = 100
    issues: list[str] = []
    if len(text) < 1800:
        score -= 22
        issues.append("본문 분량 부족")
    if len(external) < 3:
        score -= 20
        issues.append("외부 출처 링크 3개 미만")
    if not has_references:
        score -= 15
        issues.append("참고자료 섹션 없음")
    if images and license_mentions == 0:
        score -= 12
        issues.append("이미지 권리정보 없음")
    if fixed_template:
        score -= 10
        issues.append("고정형 AI 템플릿 흔적")
    if bilingual:
        score -= 10
        issues.append("한 페이지 내 한영 본문 혼합")
    if fake_expert:
        score -= 15
        issues.append("근거 없는 전문가 직함 표현")
    if AUTO_REVIEW_TEXT_RE.search(text):
        score -= 6
        issues.append("공개용 본문에 자동검수 안내 노출")
    if intermediary_links:
        score -= 22
        issues.append(f"Google/Vertex 중계 출처 링크 노출 {len(intermediary_links)}건")
    if old_policy_link:
        score -= 8
        issues.append("구형 AI 정책 링크(/ai-policy/) 사용")
    if missing_editorial_policy_link:
        score -= 5
        issues.append("AI/편집 정책 링크 없음")
    if not is_english_page and has_han_or_kana:
        score -= 15
        issues.append("한국어 본문에 중국어 한자/일본어 가나 혼입")
    if is_english_page and (has_hangul or has_han_or_kana):
        score -= 15
        issues.append("영문 본문에 한국어/CJK 문자 혼입")

    return StructuralResult(
        score=max(0, score),
        issues=issues,
        text_length=len(text),
        source_links=len(external),
        images=images,
        fixed_template=fixed_template,
        bilingual=bilingual,
        fake_expert=fake_expert,
        has_references=has_references,
        license_mentions=license_mentions,
    )


def _obj_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value.startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(value)
        if not parts.netloc or parts.hostname in {"localhost", "127.0.0.1"}:
            return ""
        tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}
        query = urlencode(
            [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.casefold() not in tracking_keys]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
    except ValueError:
        return ""


def is_source_intermediary_url(value: str) -> bool:
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


def resolve_source_url(value: str) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return ""
    if not is_source_intermediary_url(normalized):
        return normalized
    try:
        response = session.get(
            normalized, allow_redirects=True, timeout=min(15, REQUEST_TIMEOUT), stream=True
        )
        final_url = normalize_url(str(response.url or ""))
        response.close()
        if final_url and not is_source_intermediary_url(final_url):
            return final_url
    except requests.RequestException:
        pass
    return ""


def extract_search_sources(interaction: Any) -> list[ResearchSource]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results: list[ResearchSource] = []
    seen: set[str] = set()
    for step in _obj_value(interaction, "steps", []) or []:
        if _obj_value(step, "type", "") != "model_output":
            continue
        for block in _obj_value(step, "content", []) or []:
            for annotation in _obj_value(block, "annotations", []) or []:
                if _obj_value(annotation, "type", "") != "url_citation":
                    continue
                url = resolve_source_url(str(_obj_value(annotation, "url", "")))
                if not url or url in seen:
                    continue
                seen.add(url)
                title = str(_obj_value(annotation, "title", "")).strip() or url
                results.append(
                    ResearchSource(
                        title=title,
                        url=url,
                        publisher=urlsplit(url).hostname or "",
                        source_type="google_search",
                        accessed_date=today,
                    )
                )
    return results[:12]


def deterministic_sources(scientific_name: str) -> tuple[list[ResearchSource], dict[str, Any]]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sources: list[ResearchSource] = []
    seed: dict[str, Any] = {}

    # GBIF
    try:
        data = session.get(
            "https://api.gbif.org/v1/species/match",
            params={"name": scientific_name},
            timeout=REQUEST_TIMEOUT,
        ).json()
        key = data.get("usageKey") or data.get("speciesKey")
        if key:
            seed["gbif"] = data
            sources.append(
                ResearchSource(
                    title=f"GBIF species record: {data.get('scientificName') or scientific_name}",
                    url=f"https://www.gbif.org/species/{key}",
                    publisher="Global Biodiversity Information Facility",
                    source_type="scientific_database",
                    accessed_date=today,
                )
            )
    except Exception:
        pass

    # WoRMS
    try:
        response = session.get(
            f"https://www.marinespecies.org/rest/AphiaRecordsByName/{scientific_name}",
            params={"like": "false", "marine_only": "false", "offset": 1},
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok and isinstance(response.json(), list) and response.json():
            data = response.json()[0]
            seed["worms"] = data
            aphia_id = data.get("AphiaID")
            if aphia_id:
                sources.append(
                    ResearchSource(
                        title=f"WoRMS taxon details: {data.get('scientificname') or scientific_name}",
                        url=f"https://www.marinespecies.org/aphia.php?p=taxdetails&id={aphia_id}",
                        publisher="World Register of Marine Species",
                        source_type="scientific_database",
                        accessed_date=today,
                    )
                )
    except Exception:
        pass

    # NCBI Taxonomy
    try:
        search = session.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "taxonomy", "term": f'"{scientific_name}"[Scientific Name]', "retmode": "json"},
            timeout=REQUEST_TIMEOUT,
        ).json()
        ids = search.get("esearchresult", {}).get("idlist", [])
        if ids:
            tax_id = ids[0]
            seed["ncbi_tax_id"] = tax_id
            sources.append(
                ResearchSource(
                    title=f"NCBI Taxonomy: {scientific_name}",
                    url=f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tax_id}",
                    publisher="NCBI",
                    source_type="scientific_database",
                    accessed_date=today,
                )
            )
    except Exception:
        pass

    # Wikipedia (보조자료)
    try:
        response = session.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts|info",
                "inprop": "url",
                "exintro": 1,
                "explaintext": 1,
                "redirects": 1,
                "titles": scientific_name,
                "format": "json",
            },
            timeout=REQUEST_TIMEOUT,
        ).json()
        page = next(iter(response.get("query", {}).get("pages", {}).values()), {})
        if page.get("fullurl"):
            seed["wikipedia_extract"] = page.get("extract", "")
            sources.append(
                ResearchSource(
                    title=str(page.get("title") or scientific_name),
                    url=str(page["fullurl"]),
                    publisher="Wikipedia",
                    source_type="encyclopedia",
                    accessed_date=today,
                )
            )
    except Exception:
        pass

    # Crossref: 제목에 학명이 실제 포함된 상위 논문만 사용
    try:
        response = session.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": scientific_name, "rows": 5, "select": "title,URL,publisher,DOI"},
            timeout=REQUEST_TIMEOUT,
        ).json()
        for item in response.get("message", {}).get("items", []):
            title = " ".join(item.get("title") or []).strip()
            if scientific_name.lower() not in title.lower():
                continue
            url = str(item.get("URL") or "").strip()
            if not url:
                continue
            sources.append(
                ResearchSource(
                    title=title,
                    url=url,
                    publisher=str(item.get("publisher") or "Crossref"),
                    source_type="peer_reviewed_paper",
                    accessed_date=today,
                )
            )
    except Exception:
        pass

    return dedupe_sources(sources), seed


def dedupe_sources(sources: list[ResearchSource]) -> list[ResearchSource]:
    result: list[ResearchSource] = []
    seen: set[str] = set()
    for source in sources:
        url = resolve_source_url(source.url)
        if not url or url in seen:
            continue
        seen.add(url)
        source.url = url
        result.append(source)
    return result[:14]


def grounded_research(scientific_name: str, title: str, original_text: str) -> tuple[str, list[ResearchSource]]:
    prompt = f"""
Audit the scientific accuracy of this TaxonGuru article. Use Google Search and prefer
peer-reviewed papers, official scientific databases, museums, universities and government sources.
Do not trust the article itself. Identify inaccurate, exaggerated, outdated or unsupported claims.

Subject: {scientific_name or title}
Article title: {title}
Article excerpt:
{original_text[:18000]}

Produce a compact evidence memo covering taxonomy, habitat/distribution, morphology,
behavior/feeding, ecological role, conservation status, myths and disputed claims.
"""
    interaction = gemini_client.interactions.create(
        model=RESEARCH_MODEL,
        input=prompt,
        tools=[{"type": "google_search"}],
    )
    memo = str(_obj_value(interaction, "output_text", "") or "").strip()
    return memo, extract_search_sources(interaction)


def build_research_package(
    scientific_name: str,
    title: str,
    memo: str,
    seed: dict[str, Any],
    sources: list[ResearchSource],
) -> ResearchPackage:
    source_json = json.dumps([source.model_dump() for source in sources], ensure_ascii=False, indent=2)
    prompt = f"""
아래 고정 출처 목록과 연구 메모만 사용해 과학 기사 재작성용 ResearchPackage JSON을 작성하세요.
새 URL, 가상 논문, 추정 수치, 근거 없는 직함을 만들지 마세요.

학명/주제: {scientific_name or title}
원 제목: {title}
연구 메모:
{memo[:26000]}

기관 API 데이터:
{json.dumps(seed, ensure_ascii=False, indent=2)[:14000]}

고정 출처 목록(배열 순서가 출처 번호):
{source_json}

요건:
- verified_facts 최소 6건을 목표로 하되 확인된 사실만 작성
- 각 사실은 source_numbers에 실제 출처 번호를 연결
- 오해와 논쟁적 주장은 별도 배열로 분리
- 서로 다른 출처 번호를 가능한 한 4개 이상 사용
- sources 필드는 비워도 됨
"""
    result = gemini_json(RESEARCH_MODEL, prompt, ResearchPackage, max_tokens=8192)
    result.sources = [source.model_copy(deep=True) for source in sources]
    return result


def audit_decision(
    post: dict[str, Any],
    structural: StructuralResult,
    scientific_name: str,
    memo: str,
    sources: list[ResearchSource],
) -> AuditDecision:
    title = text_only(str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or ""))
    content = str(post.get("content", {}).get("raw") or post.get("content", {}).get("rendered") or "")
    prompt = f"""
당신은 애드센스 재심사를 준비하는 자연과학 블로그의 엄격한 편집 감사자입니다.
원문과 검색 기반 연구 메모를 비교해 AuditDecision JSON을 작성하세요.

학명: {scientific_name}
제목: {title}
구조 감사 점수: {structural.score}
구조 문제: {structural.issues}
확보 출처 수: {len(sources)}

원문:
{text_only(content)[:26000]}

검색 기반 사실검증 메모:
{memo[:22000]}

등급 기준:
A: 사실·출처·문체가 양호해 공개 유지 가능
B: 주제는 유효하지만 출처/문체/한영혼합/템플릿 문제로 재작성 권장
C: 중요한 사실 오류·과장·근거 부족으로 전면 재작성 필요
D: 중복/테스트/극단적으로 빈약한 글로 삭제 또는 통합 검토

주의:
- 삭제는 신중하게 판단
- 단순히 AI 문체라는 이유만으로 C/D를 주지 말 것
- factual_score와 editorial_score를 각각 0~100으로 작성
"""
    return gemini_json(REVIEW_MODEL, prompt, AuditDecision, max_tokens=4096)


def resize_images(content: str) -> str:
    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        style_match = re.search(r'\sstyle=["\']([^"\']*)["\']', tag, flags=re.I)
        additions = (
            f"display:block;max-width:100%;width:auto;height:auto;max-height:{BODY_IMAGE_MAX_HEIGHT}px;"
            "object-fit:contain;margin:0 auto;border-radius:10px;"
        )
        if style_match:
            old_style = style_match.group(1)
            tag = tag[: style_match.start()] + f' style="{old_style};{additions}"' + tag[style_match.end() :]
        else:
            tag = tag[:-1] + f' style="{additions}" loading="lazy">'
        tag = re.sub(r'\swidth=["\'][^"\']*["\']', "", tag, flags=re.I)
        tag = re.sub(r'\sheight=["\'][^"\']*["\']', "", tag, flags=re.I)
        return tag

    content = re.sub(r"<img\b[^>]*>", repl, content, flags=re.I)
    def figure_repl(match: re.Match[str]) -> str:
        attrs = match.group(1)
        attrs = re.sub(r'\sstyle=["\'][^"\']*["\']', "", attrs, flags=re.I)
        return (
            f'<figure{attrs} style="max-width:{BODY_IMAGE_MAX_WIDTH}px;'
            'margin:28px auto;text-align:center;overflow:hidden;">'
        )

    content = re.sub(r"<figure\b([^>]*)>", figure_repl, content, flags=re.I)
    return content


def safe_fix_content(content: str) -> tuple[str, list[str]]:
    changed: list[str] = []
    updated = AUTO_REVIEW_BLOCK_RE.sub("", content)
    updated = AUTO_REVIEW_TEXT_RE.sub("", updated)
    if updated != content:
        changed.append("공개 본문의 자동검수 안내 제거")
    content = updated

    policy_fixed = re.sub(
        r'href=(["\'])(?:https?://(?:www\.)?taxonguru\.com)?/ai-policy/?\1',
        lambda m: f'href={m.group(1)}/ai-use-policy/{m.group(1)}',
        content,
        flags=re.I,
    )
    if policy_fixed != content:
        changed.append("구형 AI 정책 링크를 /ai-use-policy/로 통일")
    content = policy_fixed

    if "/ai-use-policy/" not in content:
        content += (
            '<section class="taxonguru-editorial-note"><h2>자료와 편집 원칙</h2>'
            '<p>이 글의 편집 기준과 AI 사용 범위는 '
            '<a href="/ai-use-policy/">AI 활용 정책</a>과 '
            '<a href="/editorial-policy/">편집 및 팩트체크 정책</a>에서 확인할 수 있습니다.</p></section>'
        )
        changed.append("AI/편집 정책 링크 추가")

    replacements = {
        "수석 고생물학자": "TaxonGuru 편집팀",
        "수석 생물학자": "TaxonGuru 편집팀",
        "수석 해양생물학자": "TaxonGuru 편집팀",
        "제왕적 해양생물학자": "해양생물학자",
    }
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            changed.append(f"과장된 직함 표현 수정: {old}")

    resized = resize_images(content)
    if resized != content:
        changed.append("본문 이미지 표시 크기 표준화")
    content = resized
    return content, list(dict.fromkeys(changed))


def extract_preserved_figures(content: str) -> list[str]:
    figures = re.findall(r"<figure\b.*?</figure>", content, flags=re.I | re.S)
    if not figures:
        figures = [match.group(0) for match in re.finditer(r"<img\b[^>]*>", content, flags=re.I)]
    cleaned = [resize_images(figure) for figure in figures[:2]]
    return cleaned


def research_payload(package: ResearchPackage) -> str:
    return json.dumps(
        {
            "accepted_scientific_name": package.accepted_scientific_name,
            "common_name_ko": package.common_name_ko,
            "common_name_en": package.common_name_en,
            "taxonomy": package.taxonomy,
            "overview": package.overview,
            "verified_facts": [fact.model_dump() for fact in package.verified_facts],
            "misconceptions": [fact.model_dump() for fact in package.misconceptions],
            "uncertain_claims": [fact.model_dump() for fact in package.uncertain_claims],
            "limitations": package.limitations,
        },
        ensure_ascii=False,
        indent=2,
    )


def generate_article(package: ResearchPackage, language: Literal["ko", "en"], figures: list[str]) -> str:
    if language == "ko":
        language_rule = "한국어로 2,800~4,500자"
        tone = (
            "유명 과학 교양 블로거처럼 장면이나 질문으로 시작하고, 짧고 긴 문장을 섞어 자연스럽게 쓴다. "
            "보고서형 핵심요약을 맨 앞에 두지 말고, 절제된 유머와 반전을 사용한다."
        )
    else:
        language_rule = "natural English in 900~1,400 words"
        tone = (
            "Write like a polished popular-science feature for international readers. Start with a scene or question, "
            "avoid literal translation and textbook stiffness, and use restrained humor."
        )

    prompt = f"""
You are rewriting an existing TaxonGuru article after a scientific content audit.
Write {language_rule} as clean WordPress HTML only.

Style:
{tone}

Verified research package:
{research_payload(package)}

Rules:
1. Use only facts in the research package. No invented color, size, behavior, expert title or historical anecdote.
2. Add source markers [1], [2] etc. to major factual claims and use at least four distinct source numbers.
3. Separate uncertain/disputed claims from established facts.
4. Do not include a References section, AI notice, quality score or editor biography; the program adds references later.
5. Insert [[IMAGE_1]] and [[IMAGE_2]] exactly once each, between meaningful sections.
6. Use <h2>, <h3>, <p>, <ul>, <li>, <table> only when useful.
7. Do not include markdown fences.
"""
    body = gemini_text(WRITER_MODEL, prompt)
    for index in range(2):
        placeholder = f"[[IMAGE_{index + 1}]]"
        replacement = figures[index] if index < len(figures) else ""
        body = body.replace(placeholder, replacement, 1)
    body = re.sub(r"\[\[IMAGE_[12]\]\]", "", body)
    return resize_images(body)


def generate_meta(package: ResearchPackage, body: str, language: Literal["ko", "en"], original_slug: str) -> ArticleMeta:
    prompt = f"""
Create ArticleMeta JSON for this {'Korean' if language == 'ko' else 'English'} popular-science article.
The title must be engaging but accurate. Do not use shock/clickbait words.
Keep the existing Korean slug when language is ko: {original_slug}
For English, make a concise English slug.

Scientific name: {package.accepted_scientific_name}
Common names: KO={package.common_name_ko}, EN={package.common_name_en}
Article excerpt:
{text_only(body)[:5000]}
"""
    meta = gemini_json(WRITER_MODEL, prompt, ArticleMeta, max_tokens=2048)
    if language == "ko" and original_slug:
        meta.slug = original_slug
    return meta


def build_references(package: ResearchPackage, language: Literal["ko", "en"]) -> str:
    heading = "참고자료" if language == "ko" else "References"
    items = []
    for index, source in enumerate(package.sources, start=1):
        items.append(
            f'<li id="ref-{index}"><a href="{html.escape(source.url)}" target="_blank" rel="noopener noreferrer">'
            f"{html.escape(source.title)}</a> — {html.escape(source.publisher)}</li>"
        )
    note = (
        f'<section class="taxonguru-editorial-note"><h2>{"자료와 편집 원칙" if language == "ko" else "Sources and editorial policy"}</h2>'
        f'<p>{"공개된 학술·기관 자료를 바탕으로 기존 글을 재검토하고 갱신했습니다." if language == "ko" else "This article was reviewed and updated using public scientific and institutional sources."} '
        f'<a href="/ai-use-policy/">{"AI 활용 및 편집 정책" if language == "ko" else "AI and editorial policy"}</a></p></section>'
    )
    return note + f'<section class="taxonguru-references"><h2>{heading}</h2><ol>' + "".join(items) + "</ol></section>"


def review_rewrite(body: str, package: ResearchPackage, language: Literal["ko", "en"]) -> RewriteReview:
    prompt = f"""
Audit this rewritten {'Korean' if language == 'ko' else 'English'} article against the fixed research package.
Return RewriteReview JSON. passed=true only when score >= {MIN_QUALITY_SCORE}, there are no critical errors,
unsupported claims are empty, at least four citation markers are present, and the article is readable popular science.

Research package:
{research_payload(package)}

Article:
{text_only(body)[:26000]}
"""
    result = gemini_json(REVIEW_MODEL, prompt, RewriteReview, max_tokens=4096)
    citation_count = len(set(re.findall(r"\[(\d{1,2})\]", body)))
    if citation_count < 4:
        result.passed = False
        result.style_issues.append(f"서로 다른 인용번호가 {citation_count}개로 4개 미만")
    if language == "ko" and len(text_only(body)) < 2200:
        result.passed = False
        result.style_issues.append("한국어 본문 2,200자 미만")
    if language == "ko" and re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", text_only(body)):
        result.passed = False
        result.style_issues.append("한국어 본문에 중국어 한자/일본어 가나 혼입")
    if language == "en" and len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", text_only(body))) < 850:
        result.passed = False
        result.style_issues.append("영문 본문 850단어 미만")
    if language == "en" and re.search(r"[가-힣\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", text_only(body)):
        result.passed = False
        result.style_issues.append("영문 본문에 한국어/CJK 문자 혼입")
    return result


def upsert_english_post(
    topic: TopicRow | None,
    ko_post_id: int,
    ko_post: dict[str, Any],
    meta: ArticleMeta,
    content: str,
) -> tuple[int, str]:
    existing_id = topic.en_post_id if topic else None
    payload: dict[str, Any] = {
        "title": meta.title,
        "slug": meta.slug,
        "excerpt": meta.excerpt or meta.seo_description,
        "content": content,
        "status": "publish",
        "featured_media": ko_post.get("featured_media") or 0,
        "categories": ko_post.get("categories") or [],
        "tags": ko_post.get("tags") or [],
        "meta": {"_taxonguru_language": "en", "_taxonguru_translation_id": ko_post_id},
    }
    if existing_id:
        post = wp_request("POST", f"posts/{existing_id}", json=payload).json()
    else:
        post = wp_request("POST", "posts", json=payload).json()
    en_id = int(post["id"])
    try:
        bridge = session.post(
            f"{WP_SITE_URL}/wp-json/taxonguru/v1/link",
            auth=wp_auth,
            json={"ko_post_id": ko_post_id, "en_post_id": en_id},
            timeout=REQUEST_TIMEOUT,
        )
        if bridge.status_code >= 400:
            raise RuntimeError(bridge.text[:500])
    except Exception:
        # 메타 방식으로 한 번 더 연결
        wp_request(
            "POST",
            f"posts/{ko_post_id}",
            json={"meta": {"_taxonguru_language": "ko", "_taxonguru_translation_id": en_id}},
        )
        wp_request(
            "POST",
            f"posts/{en_id}",
            json={"meta": {"_taxonguru_language": "en", "_taxonguru_translation_id": ko_post_id}},
        )
    return en_id, str(post.get("link", ""))


def backup_post(post: dict[str, Any]) -> Path:
    backup_dir = OUTPUT_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"post_{post['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def queue_for_rewrite(
    topic_ws: gspread.Worksheet,
    topic_headers: list[str],
    topic: TopicRow | None,
    post_id: int,
    en_post_id: int | None,
    reason: str,
    *,
    quality_score: int | str = "",
    source_count: int = 0,
) -> str:
    """Move legacy posts to recoverable drafts and place them in the automatic rewrite queue."""
    compact = " ".join(str(reason).split())[:900]
    wp_request("POST", f"posts/{post_id}", json={"status": "draft"})
    if en_post_id:
        try:
            wp_request("POST", f"posts/{en_post_id}", json={"status": "draft"})
        except Exception as exc:
            compact += f" / 기존 영문글 초안 전환 실패: {' '.join(str(exc).split())[:250]}"
    if topic:
        update_topic_fields(
            topic_ws, topic_headers, topic.row_number,
            {
                "status": "기존재작성대기",
                "post_id": post_id,
                "en_post_id": en_post_id or "",
                "quality_score": quality_score,
                "source_count": source_count,
                "cleanup_note": "감사 후 자동 재작성 대기",
                "error": compact,
            },
        )
    return f"비공개(초안) 전환 후 자동 재작성 대기: {compact}"


def process_post(
    post: dict[str, Any],
    topic_ws: gspread.Worksheet,
    topic_headers: list[str],
    topic_rows: list[TopicRow],
) -> dict[str, Any]:
    post_id = int(post["id"])
    title = text_only(str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or ""))
    url = str(post.get("link", ""))
    original_content = str(post.get("content", {}).get("raw") or post.get("content", {}).get("rendered") or "")
    structural = structural_audit(post)
    topic = match_topic_row(post, topic_rows)
    scientific_name = topic.scientific_name if topic else ""
    if not scientific_name:
        match = re.search(r"\b([A-Z][a-z]{2,}\s+[a-z][a-z-]{2,})\b", f"{title} {text_only(original_content)[:3000]}")
        scientific_name = match.group(1) if match else ""

    backup_path = backup_post(post)
    actual_action = "보고서만 생성"
    decision: AuditDecision | None = None
    combined_score: int | str = ""
    sources: list[ResearchSource] = []

    def update_topic(status: str, **extra: Any) -> None:
        if not topic:
            return
        fields: dict[str, Any] = {
            "status": status,
            "post_id": post_id,
            "public_url": url,
            "error": "",
        }
        fields.update(extra)
        update_topic_fields(topic_ws, topic_headers, topic.row_number, fields)

    def fail_closed(reason: str) -> str:
        """Hide unsafe legacy content and queue it for automatic reconstruction."""
        compact = " ".join(reason.split())[:900]
        if not (AUTO_CLEANUP_MODE and AUTO_FAIL_CLOSED_DRAFT):
            return compact
        try:
            return queue_for_rewrite(
                topic_ws, topic_headers, topic, post_id, topic.en_post_id if topic else None, compact,
                quality_score=combined_score, source_count=len(sources),
            )
        except Exception as draft_exc:
            if topic:
                update_topic_fields(
                    topic_ws, topic_headers, topic.row_number,
                    {
                        "status": "기존정리오류",
                        "post_id": post_id,
                        "error": f"{compact} / 초안전환 실패: {' '.join(str(draft_exc).split())[:500]}",
                    },
                )
            return f"검수 실패 및 초안전환 실패: {compact} / {draft_exc}"

    try:
        seed_sources, seed = deterministic_sources(scientific_name or title)
        memo = ""
        search_sources: list[ResearchSource] = []
        try:
            memo, search_sources = grounded_research(scientific_name, title, text_only(original_content))
        except Exception as exc:
            log(f"    ⚠️ Google Search 연구 실패, 기관/API 자료로 계속: {' '.join(str(exc).split())[:350]}")
        sources = dedupe_sources(search_sources + seed_sources)
        decision = audit_decision(post, structural, scientific_name, memo, sources)
        hard_rewrite_issues = [
            issue for issue in structural.issues
            if issue.startswith((
                "본문 분량 부족",
                "외부 출처 링크 3개 미만",
                "참고자료 섹션 없음",
                "이미지 권리정보 없음",
                "Google/Vertex 중계 출처 링크",
                "한국어 본문에 중국어",
                "영문 본문에 한국어",
                "한 페이지 내 한영 본문 혼합",
                "고정형 AI 템플릿 흔적",
            ))
        ]
        if len(sources) < MIN_SOURCE_COUNT:
            hard_rewrite_issues.append(f"검증 가능한 직접 출처 {len(sources)}개로 최소 {MIN_SOURCE_COUNT}개 미만")
        if hard_rewrite_issues and decision.grade == "A":
            decision.grade = "B"
            decision.recommended_action = "전면재작성"
            decision.reason = "자동 강등: " + "; ".join(hard_rewrite_issues[:4])
        combined_score = round((structural.score * 0.35) + (decision.factual_score * 0.45) + (decision.editorial_score * 0.20))

        if AUDIT_MODE == "safe_fix":
            fixed_content, changes = safe_fix_content(original_content)
            if fixed_content != original_content:
                wp_request("POST", f"posts/{post_id}", json={"content": fixed_content})
                actual_action = " / ".join(changes)
            else:
                actual_action = "안전 보완 항목 없음"

        elif AUDIT_MODE == "rewrite_recent":
            # A: 정확성과 편집 품질이 충분하면 공개 상태를 유지하고 정리 완료로 표시합니다.
            if decision.grade == "A":
                fixed_content, changes = safe_fix_content(original_content)
                if ADSENSE_RECOVERY_MODE:
                    # AdSense recovery does not treat an automatic A grade as a substitute for
                    # human editorial review. Keep the URL/post recoverable, but require a person
                    # to open the WordPress draft and publish it deliberately.
                    wp_request(
                        "POST",
                        f"posts/{post_id}",
                        json={"content": fixed_content, "status": "draft"},
                    )
                    if topic and topic.en_post_id:
                        try:
                            wp_request("POST", f"posts/{topic.en_post_id}", json={"status": "draft"})
                        except Exception as exc:
                            log(
                                "    ⚠️ A등급 기존 영문 글 초안 전환 실패: "
                                + " ".join(str(exc).split())[:300]
                            )
                    actual_action = "A등급 자동 감사 통과 / 사람 검수용 초안 전환"
                    if changes:
                        actual_action += " / 안전보완: " + ", ".join(changes[:4])
                    update_topic(
                        "기존수동검수대기",
                        quality_score=combined_score,
                        source_count=len(sources),
                        public_url="",
                        en_public_url="",
                        cleanup_note="자동 감사 A등급 통과. AdSense 복구모드에서 사람 검수 후 직접 공개 필요",
                    )
                else:
                    if fixed_content != original_content:
                        wp_request("POST", f"posts/{post_id}", json={"content": fixed_content})
                    actual_action = "A등급 공개 유지(자동 감사 통과)"
                    if changes:
                        actual_action += " / 안전보완: " + ", ".join(changes[:4])
                    update_topic(
                        "기존검수완료",
                        quality_score=combined_score,
                        source_count=len(sources),
                        cleanup_note="자동 감사 통과 및 공개 상태 유지" + (" / 안전보완 적용" if changes else ""),
                    )

            # D: 영구 삭제하지 않고 초안으로 숨긴 뒤, 기본값에서는 자동 재작성 대기열로 보냅니다.
            elif decision.grade == "D":
                if QUEUE_GRADE_D_FOR_REWRITE and scientific_name:
                    actual_action = queue_for_rewrite(
                        topic_ws, topic_headers, topic, post_id, topic.en_post_id if topic else None,
                        "D등급 판정: " + decision.reason,
                        quality_score=combined_score, source_count=len(sources),
                    )
                elif DRAFT_GRADE_D or AUTO_CLEANUP_MODE:
                    wp_request("POST", f"posts/{post_id}", json={"status": "draft"})
                    actual_action = "D등급 비공개 보류"
                    update_topic(
                        "기존비공개보류",
                        quality_score=combined_score, source_count=len(sources),
                        cleanup_note="자동 재작성에 필요한 학명 또는 근거 부족",
                    )
                else:
                    actual_action = "삭제·통합 검토만 표시(자동 삭제 안 함)"

            # B/C: 공개 중단 후 main.py의 최신 한·영 생성기로 넘깁니다.
            elif decision.grade in {"B", "C"}:
                if not scientific_name:
                    actual_action = fail_closed("학명을 기존 주제 행 또는 본문에서 확인하지 못했습니다.")
                else:
                    actual_action = queue_for_rewrite(
                        topic_ws, topic_headers, topic, post_id, topic.en_post_id if topic else None,
                        f"{decision.grade}등급 자동 재작성 대상: {decision.reason}",
                        quality_score=combined_score, source_count=len(sources),
                    )

        audit_state = "수정완료" if "완료" in actual_action else ("삭제검토" if decision.grade == "D" else "완료")
        if "비공개" in actual_action or "휴지통" in actual_action:
            audit_state = "초안전환"
        if decision.grade == "A":
            audit_state = "초안전환" if ADSENSE_RECOVERY_MODE else "유지"

        return {
            "감사상태": audit_state,
            "감사일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "처리모드": AUDIT_MODE,
            "게시물ID": post_id,
            "수정일": str(post.get("modified", "")),
            "제목": title,
            "URL": url,
            "학명": scientific_name,
            "구조점수": structural.score,
            "사실점수": decision.factual_score,
            "종합점수": combined_score,
            "등급": decision.grade,
            "권장조치": decision.recommended_action,
            "실제처리": actual_action,
            "출처수": len(sources),
            "본문글자수": structural.text_length,
            "이미지수": structural.images,
            "외부링크수": structural.source_links,
            "주요문제": " | ".join(structural.issues + [decision.reason]),
            "중대오류": " | ".join(decision.critical_errors),
            "근거부족": " | ".join(decision.unsupported_claims),
            "백업파일": str(backup_path),
            "오류": "",
        }
    except Exception as exc:
        error = " ".join(str(exc).split())[:1000]
        actual_action = fail_closed(error)
        return {
            "감사상태": "초안전환" if "비공개" in actual_action else "오류",
            "감사일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "처리모드": AUDIT_MODE,
            "게시물ID": post_id,
            "수정일": str(post.get("modified", "")),
            "제목": title,
            "URL": url,
            "학명": scientific_name,
            "구조점수": structural.score,
            "사실점수": decision.factual_score if decision else "",
            "종합점수": combined_score,
            "등급": decision.grade if decision else "",
            "권장조치": "안전 비공개" if "비공개" in actual_action else "재시도",
            "실제처리": actual_action,
            "출처수": len(sources),
            "본문글자수": structural.text_length,
            "이미지수": structural.images,
            "외부링크수": structural.source_links,
            "주요문제": " | ".join(structural.issues),
            "중대오류": "",
            "근거부족": "",
            "백업파일": str(backup_path),
            "오류": error,
        }

def write_reports(rows: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "taxonguru_content_audit.csv"
    json_path = OUTPUT_DIR / "taxonguru_content_audit.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"📄 보고서: {csv_path} / {json_path}")


def main() -> int:
    log("=" * 72)
    log("TaxonGuru 기존 콘텐츠 감사·수정 전용 파이프라인")
    target_label = AUDIT_TARGET_STATUS or "전체 공개 글"
    log(f"모드={AUDIT_MODE} · 대상상태={target_label} · 최근순 · 최대 {BATCH_SIZE}건 · 영어별도작성={'ON' if CREATE_ENGLISH else 'OFF'}")
    log("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    preflight_wordpress()
    topic_ws, audit_ws = connect_sheets()
    topic_headers, topic_rows = load_topic_rows(topic_ws)
    completed = audited_post_ids(audit_ws, AUDIT_MODE)
    posts = fetch_posts()

    if AUDIT_TARGET_STATUS:
        # 자동 정리에서는 Google Sheets의 상태가 정확히 일치하는 글만 다룹니다.
        # 예: "완료"만 처리하므로 "한영예약완료" 등은 절대 선택되지 않습니다.
        matched_row_numbers: set[int] = set()
        for post in posts:
            topic = match_topic_row(post, topic_rows)
            if topic:
                matched_row_numbers.add(topic.row_number)

        # 시트에는 완료로 남아 있지만 공개 게시물이 이미 없거나 초안인 행은
        # 추가 수정 대상이 아니므로 안전하게 정리 완료 상태로 이동합니다.
        unmatched = [
            row for row in topic_rows
            if row.status.strip() == AUDIT_TARGET_STATUS and row.row_number not in matched_row_numbers
        ]
        for row in unmatched:
            next_status = "기존재작성대기" if row.post_id and row.scientific_name else "기존비공개보류"
            update_topic_fields(
                topic_ws, topic_headers, row.row_number,
                {
                    "status": next_status,
                    "cleanup_note": "공개 게시물 미발견; 기존 ID가 있으면 자동 재작성",
                    "error": "공개 상태의 WordPress 게시물을 찾지 못했습니다.",
                },
            )
        if unmatched:
            log(f"ℹ️ 공개 게시물 미발견 행 {len(unmatched)}건을 재작성대기 또는 비공개보류로 분류했습니다.")

        targets = []
        for post in posts:
            topic = match_topic_row(post, topic_rows)
            if not topic or topic.status.strip() != AUDIT_TARGET_STATUS:
                continue
            if not INCLUDE_ALREADY_AUDITED and int(post["id"]) in completed:
                continue
            targets.append(post)
            if len(targets) >= BATCH_SIZE:
                break
    else:
        targets = [post for post in posts if INCLUDE_ALREADY_AUDITED or int(post["id"]) not in completed][:BATCH_SIZE]

    if not targets:
        if AUDIT_TARGET_STATUS:
            log(f"✅ 상태가 정확히 '{AUDIT_TARGET_STATUS}'인 기존 게시물이 없습니다.")
        else:
            log("✅ 감사할 신규 게시물이 없습니다. 이미 처리된 글을 다시 보려면 INCLUDE_ALREADY_AUDITED=true로 실행하세요.")
        write_reports([])
        return 0

    results: list[dict[str, Any]] = []
    for index, post in enumerate(targets, start=1):
        title = text_only(str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or ""))
        log(f"\n[{index}/{len(targets)}] 감사 시작: Post {post['id']} · {title}")
        result = process_post(post, topic_ws, topic_headers, topic_rows)
        results.append(result)
        append_audit_row(audit_ws, result)
        log(f"  → 등급 {result.get('등급') or '-'} / {result.get('실제처리')} / {result.get('오류')}")

    write_reports(results)
    log("\n✅ 최근 게시물 감사 작업을 완료했습니다. 삭제는 자동으로 수행하지 않았습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
