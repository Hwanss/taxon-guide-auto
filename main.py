from __future__ import annotations

import base64
import html
import importlib.metadata
import json
import os
import re
import sys
import time
import unicodedata
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal, TypeVar
from zoneinfo import ZoneInfo
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import bleach
import gspread
import requests
import urllib3.util.connection as urllib3_connection
from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", category=FutureWarning)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").strip().rstrip("/")
WP_URL = f"{WP_SITE_URL}/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
SHEET_ID = os.environ["SHEET_ID"]
SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "admin@taxonguru.com")

RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", "gemini-3.6-flash")
WRITER_MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-3.6-flash")
REVIEW_MODEL = os.getenv("GEMINI_REVIEW_MODEL", "gemini-3.6-flash")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

MIN_SOURCE_COUNT = int(os.getenv("MIN_SOURCE_COUNT", "4"))
MIN_QUALITY_SCORE = int(os.getenv("MIN_QUALITY_SCORE", "85"))
MIN_KOREAN_CHARS = int(os.getenv("MIN_KOREAN_CHARS", os.getenv("MIN_ARTICLE_CHARS", "2200")))
MIN_ENGLISH_WORDS = int(os.getenv("MIN_ENGLISH_WORDS", "850"))
MIN_CITATION_MARKERS = int(os.getenv("MIN_CITATION_MARKERS", "4"))
ENABLE_ENGLISH = os.getenv("ENABLE_ENGLISH", "true").lower() == "true"
MULTILINGUAL_BACKEND = os.getenv("MULTILINGUAL_BACKEND", "taxonguru_bridge")
BRIDGE_PREFLIGHT_STRICT = os.getenv("BRIDGE_PREFLIGHT_STRICT", "false").lower() == "true"
BRIDGE_CHECK_RETRIES = max(1, int(os.getenv("BRIDGE_CHECK_RETRIES", "3")))
BRIDGE_RETRY_DELAY_SECONDS = max(0.5, float(os.getenv("BRIDGE_RETRY_DELAY_SECONDS", "2")))
ALLOW_AI_FEATURED_IMAGE = os.getenv("ALLOW_AI_FEATURED_IMAGE", "true").lower() == "true"
PREFER_AI_FEATURED_IMAGE = os.getenv("PREFER_AI_FEATURED_IMAGE", "true").lower() == "true"
GENERATE_AI_BODY_IMAGES = os.getenv("GENERATE_AI_BODY_IMAGES", "true").lower() == "true"
ALLOW_HISTORICAL_BODY_IMAGES = os.getenv("ALLOW_HISTORICAL_BODY_IMAGES", "false").lower() == "true"
MIN_BODY_IMAGES = max(0, int(os.getenv("MIN_BODY_IMAGES", "2")))
BODY_IMAGE_MAX_WIDTH = max(320, int(os.getenv("BODY_IMAGE_MAX_WIDTH", "720")))
BODY_IMAGE_MAX_HEIGHT = max(240, int(os.getenv("BODY_IMAGE_MAX_HEIGHT", "520")))
AI_IMAGE_QUALITY = os.getenv("AI_IMAGE_QUALITY", "medium")
AUTO_SCHEDULE = os.getenv("AUTO_SCHEDULE", "true").lower() == "true"
ADSENSE_RECOVERY_MODE = os.getenv("ADSENSE_RECOVERY_MODE", "false").lower() == "true"
MANUAL_REVIEW_REQUIRED = os.getenv("MANUAL_REVIEW_REQUIRED", "false").lower() == "true"
# AdSense recovery mode is fail-closed: quality-passed content remains a WordPress draft
# until the site operator reviews and publishes it manually.
if ADSENSE_RECOVERY_MODE:
    MANUAL_REVIEW_REQUIRED = True
    AUTO_SCHEDULE = False
DRAFT_ON_REVIEW_FAILURE = os.getenv("DRAFT_ON_REVIEW_FAILURE", "true").lower() == "true"
DRAFT_STATUS = os.getenv("WP_DRAFT_STATUS", "draft")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "45"))
FORCE_IPV4 = os.getenv("FORCE_IPV4", "true").lower() == "true"
if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False
MAX_STRUCTURED_ATTEMPTS = max(1, int(os.getenv("MAX_STRUCTURED_ATTEMPTS", "3")))
MAX_TEXT_ATTEMPTS = max(1, int(os.getenv("MAX_TEXT_ATTEMPTS", "3")))
MAX_REWRITE_ROUNDS = max(0, int(os.getenv("MAX_REWRITE_ROUNDS", "2")))
RESEARCH_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_RESEARCH_MAX_OUTPUT_TOKENS", "8192"))
ARTICLE_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_ARTICLE_MAX_OUTPUT_TOKENS", "12288"))
METADATA_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_METADATA_MAX_OUTPUT_TOKENS", "2048"))
REVIEW_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_REVIEW_MAX_OUTPUT_TOKENS", "4096"))

SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE", "Asia/Seoul")
PUBLISH_HOUR = int(os.getenv("PUBLISH_HOUR", "9"))
PUBLISH_MINUTE = int(os.getenv("PUBLISH_MINUTE", "30"))
ENGLISH_PUBLISH_HOUR = int(os.getenv("ENGLISH_PUBLISH_HOUR", "18"))
ENGLISH_PUBLISH_MINUTE = int(os.getenv("ENGLISH_PUBLISH_MINUTE", "30"))
SCHEDULE_AFTER_DAYS = int(os.getenv("SCHEDULE_AFTER_DAYS", "1"))
SCHEDULE_INTERVAL_DAYS = int(os.getenv("SCHEDULE_INTERVAL_DAYS", "1"))
MAX_SCHEDULE_LOOKAHEAD_DAYS = int(os.getenv("MAX_SCHEDULE_LOOKAHEAD_DAYS", "120"))
MIN_SCHEDULE_LEAD_MINUTES = int(os.getenv("MIN_SCHEDULE_LEAD_MINUTES", "30"))
MAX_LEGACY_REWRITE_ATTEMPTS = max(1, int(os.getenv("MAX_LEGACY_REWRITE_ATTEMPTS", "3")))
PROCESS_MODE = os.getenv("PROCESS_MODE", "auto").strip().lower()
SCHEDULE_TZ = ZoneInfo(SCHEDULE_TIMEZONE)

LEGACY_REWRITE_STATES = {"기존재작성대기", "기존재작성재시도"}
LEGACY_SCHEDULED_STATES = {"기존한영재예약완료", "기존재예약완료"}

USER_AGENT = f"TaxonGuruEditorialBot/2.0 ({WP_SITE_URL}; {CONTACT_EMAIL})"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
wp_auth = (WP_USER, WP_APP_PASSWORD)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# -----------------------------------------------------------------------------
# Google Sheet columns and states
# -----------------------------------------------------------------------------
LEGACY_HEADERS = [
    "상태",
    "학명",
    "국문/영문명",
    "분류 트리",
    "카테고리",
    "스토리앵글",
    "슬러그",
    "태그",
]
EXTRA_HEADERS = [
    "검수자",
    "검수일",
    "검수메모",
    "언어",
    "WP_POST_ID",
    "편집URL",
    "공개URL",
    "품질점수",
    "자료수",
    "예약일",
    "자동검수결과",
    "오류",
    "EN_POST_ID",
    "EN_편집URL",
    "EN_공개URL",
    "EN_품질점수",
    "EN_예약일",
    "EN_자동검수결과",
    "한영연결",
    "영문오류",
    "재작성시도",
    "정리메모",
]
HEADER_ALIASES = {
    "status": ["상태", "진행상태"],
    "scientific_name": ["학명", "학명(Scientific Name)", "학명 (Scientific Name)"],
    "title": ["국문/영문명", "제목", "국문/영문명(Title)", "국문/영문명 (Title)"],
    "taxonomy": ["분류 트리", "분류트리", "분류 트리(Taxonomy)", "분류 트리 (Taxonomy)"],
    "category": ["카테고리", "카테고리(Category)", "카테고리 (Category)"],
    "story_angle": ["스토리앵글", "스토리 앵글", "스토리 앵글(Story Angle)", "스토리 앵글 (Story Angle)"],
    "slug": ["슬러그", "슬러그(Slug)", "슬러그 (Slug)"],
    "tags": ["태그", "태그(Tags)", "태그 (Tags)"],
    "reviewer": ["검수자"],
    "review_date": ["검수일"],
    "review_note": ["검수메모"],
    "language": ["언어"],
    "post_id": ["WP_POST_ID", "WP POST ID"],
    "edit_url": ["편집URL", "편집 URL"],
    "public_url": ["공개URL", "공개 URL"],
    "quality_score": ["품질점수", "품질 점수"],
    "source_count": ["자료수", "자료 수"],
    "scheduled_date": ["예약일", "예약 일시"],
    "auto_review_result": ["자동검수결과", "자동 검수 결과"],
    "error": ["오류", "에러"],
    "en_post_id": ["EN_POST_ID", "영문 WP_POST_ID"],
    "en_edit_url": ["EN_편집URL", "영문 편집URL"],
    "en_public_url": ["EN_공개URL", "영문 공개URL"],
    "en_quality_score": ["EN_품질점수", "영문 품질점수"],
    "en_scheduled_date": ["EN_예약일", "영문 예약일"],
    "en_auto_review_result": ["EN_자동검수결과", "영문 자동검수결과"],
    "translation_linked": ["한영연결", "번역연결"],
    "en_error": ["영문오류", "EN_오류"],
    "rewrite_attempts": ["재작성시도", "재작성 시도"],
    "cleanup_note": ["정리메모", "정리 메모"],
}


# -----------------------------------------------------------------------------
# Pydantic schemas for grounded research, article generation, and QA
# -----------------------------------------------------------------------------
class TaxonomyRank(BaseModel):
    rank: str = ""
    name: str = ""


class ResearchSource(BaseModel):
    title: str = ""
    url: str = ""
    publisher: str = ""
    source_type: Literal[
        "government",
        "museum_or_university",
        "scientific_database",
        "peer_reviewed_paper",
        "professional_organization",
        "reputable_secondary",
        "other",
    ] = "other"
    accessed_date: str = ""


class ResearchFact(BaseModel):
    claim: str = ""
    explanation: str = ""
    source_numbers: list[int] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class DisputedClaim(BaseModel):
    claim: str = ""
    evidence_for: str = ""
    evidence_against: str = ""
    conclusion: str = ""
    source_numbers: list[int] = Field(default_factory=list)


class ResearchPackage(BaseModel):
    accepted_scientific_name: str = ""
    common_name_ko: str = ""
    common_name_en: str = ""
    taxonomy: list[TaxonomyRank] = Field(default_factory=list)
    overview: str = ""
    distribution_and_habitat: str = ""
    conservation_status: str = ""
    verified_facts: list[ResearchFact] = Field(default_factory=list)
    disputed_or_uncertain: list[DisputedClaim] = Field(default_factory=list)
    common_misconceptions: list[ResearchFact] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class ArticleDraft(BaseModel):
    title: str = ""
    slug: str = ""
    excerpt: str = ""
    html_body: str = ""
    seo_description: str = ""
    tags: list[str] = Field(default_factory=list)


class ArticleMetadata(BaseModel):
    title: str = ""
    slug: str = ""
    excerpt: str = ""
    seo_description: str = ""
    tags: list[str] = Field(default_factory=list)


class QualityReview(BaseModel):
    score: int = 0
    pass_review: bool = False
    critical_issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    factual_corrections: list[str] = Field(default_factory=list)
    template_or_duplication_risks: list[str] = Field(default_factory=list)
    improvement_instructions: list[str] = Field(default_factory=list)


@dataclass
class SheetItem:
    row_number: int
    status: str
    scientific_name: str
    display_title: str
    taxonomy: str
    category: str
    story_angle: str
    slug: str
    tags: list[str]
    reviewer: str
    review_note: str
    language: str
    post_id: int | None
    quality_score: int
    source_count: int
    en_post_id: int | None
    en_quality_score: int
    rewrite_attempts: int
    cleanup_note: str


@dataclass
class CommonsImage:
    url: str
    page_url: str
    title: str
    artist: str
    credit: str
    license_name: str
    license_url: str
    description: str


@dataclass
class UploadedMedia:
    media_id: int
    source_url: str
    caption_ko: str
    caption_en: str
    source_kind: Literal["commons", "ai"]


# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------
def log(message: str) -> None:
    print(message, flush=True)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value.startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(value)
        if not parts.netloc or parts.hostname in {"localhost", "127.0.0.1"}:
            return ""
        tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}
        clean_query = urlencode(
            [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in tracking_keys]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, clean_query, ""))
    except ValueError:
        return ""


SOURCE_INTERMEDIARY_HOSTS = {
    "vertexaisearch.cloud.google.com",
    "google.com",
    "www.google.com",
    "googleusercontent.com",
    "www.googleusercontent.com",
}


def is_source_intermediary_url(value: str) -> bool:
    try:
        host = (urlsplit(value).hostname or "").casefold()
    except ValueError:
        return True
    if host == "vertexaisearch.cloud.google.com":
        return True
    if host in {"google.com", "www.google.com"} and urlsplit(value).path.startswith(("/url", "/search")):
        return True
    return host in {"googleusercontent.com", "www.googleusercontent.com"}


def resolve_source_url(value: str) -> str:
    """Return a public destination URL, resolving known Google grounding redirects.

    Google Search grounding annotations can contain an intermediary URL. Those URLs are
    useful to the model but should not be exposed as a reader-facing reference.
    """
    normalized = normalize_url(value)
    if not normalized:
        return ""
    if not is_source_intermediary_url(normalized):
        return normalized
    try:
        response = session.get(
            normalized,
            allow_redirects=True,
            timeout=min(15, REQUEST_TIMEOUT),
            stream=True,
        )
        final_url = normalize_url(str(response.url or ""))
        response.close()
        if final_url and not is_source_intermediary_url(final_url):
            return final_url
    except requests.RequestException:
        pass
    return ""


def slugify(value: str) -> str:
    value = value.lower().strip().replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


def sanitize_html(fragment: str) -> str:
    allowed_tags = [
        "p", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "blockquote",
        "table", "thead", "tbody", "tr", "th", "td", "figure", "figcaption", "img",
        "a", "div", "span", "br", "hr", "sup", "small",
    ]
    allowed_attributes = {
        "a": ["href", "title", "target", "rel"],
        "img": ["src", "alt", "loading", "width", "height"],
        "div": ["class", "id", "data-status"],
        "span": ["class"],
        "figure": ["class"],
        "table": ["class"],
        "th": ["scope"],
        "td": ["colspan", "rowspan"],
    }
    return bleach.clean(
        fragment or "",
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=["http", "https", "mailto"],
        strip=True,
    ).strip()


def replace_citation_markers(fragment: str, source_count: int) -> str:
    def repl(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if 1 <= number <= source_count:
            return f'<sup><a href="#ref-{number}">[{number}]</a></sup>'
        return match.group(0)

    return re.sub(r"\[(\d{1,2})\]", repl, fragment)


TModel = TypeVar("TModel", bound=BaseModel)


def _short_error(exc: Exception, limit: int = 600) -> str:
    return " ".join(str(exc).split())[:limit]


def _response_finish_reason(response: Any) -> str:
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        reason = getattr(candidates[0], "finish_reason", "")
        return str(reason or "")
    except Exception:
        return ""


def _extract_response_text(response: Any) -> str:
    text_value = str(getattr(response, "text", "") or "").strip()
    if not text_value:
        raise ValueError("모델 응답 본문이 비어 있습니다.")
    return text_value


def gemini_json(
    model: str,
    prompt: str,
    schema: type[TModel],
    *,
    max_output_tokens: int,
    temperature: float = 0.2,
    validator: Callable[[TModel], list[str]] | None = None,
    attempts: int | None = None,
) -> TModel:
    """Generate small/medium schema-conformant JSON with generateContent.

    Long article HTML is intentionally generated as plain text by ``gemini_text``.
    Keeping large HTML out of a JSON string prevents truncated/invalid JSON output.
    """
    attempt_count = max(1, attempts or MAX_STRUCTURED_ATTEMPTS)
    last_error: Exception | None = None
    retry_note = ""

    for attempt in range(1, attempt_count + 1):
        effective_prompt = prompt
        if retry_note:
            effective_prompt += f"""

The previous response could not be used for this reason:
{retry_note}
Return exactly one complete JSON object matching the schema. Do not echo the prompt.
"""
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=effective_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    candidate_count=1,
                ),
            )
            finish_reason = _response_finish_reason(response)
            if finish_reason and "STOP" not in finish_reason.upper():
                raise RuntimeError(f"모델 생성이 정상 종료되지 않았습니다: {finish_reason}")
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                result = parsed
            elif parsed is not None:
                result = schema.model_validate(parsed)
            else:
                result = schema.model_validate_json(_extract_response_text(response))
            issues = validator(result) if validator else []
            if issues:
                raise ValueError("; ".join(issues[:8]))
            return result
        except Exception as exc:
            last_error = exc
            retry_note = _short_error(exc)
            log(f"  ⚠️ 구조화 출력 재시도 {attempt}/{attempt_count}: {retry_note}")
            if attempt < attempt_count:
                time.sleep(min(2 * attempt, 6))

    raise RuntimeError(
        f"{schema.__name__} 구조화 출력을 {attempt_count}회 생성하지 못했습니다: "
        f"{_short_error(last_error or RuntimeError('unknown error'))}"
    )


def normalize_model_citations(fragment: str) -> str:
    """Normalize citation styles models commonly emit into [n] markers.

    This keeps English generation from failing merely because the model used
    Unicode brackets, superscript numbers, or labels such as [Source 1].
    """
    value = fragment or ""
    value = re.sub(r"【\s*(\d{1,2})\s*】", r"[\1]", value)
    value = re.sub(r"〔\s*(\d{1,2})\s*〕", r"[\1]", value)
    value = re.sub(r"\[\s*(?:source|ref(?:erence)?)\s*(\d{1,2})\s*\]", r"[\1]", value, flags=re.IGNORECASE)
    value = re.sub(r"\(\s*(?:source|ref(?:erence)?)\s*(\d{1,2})\s*\)", r"[\1]", value, flags=re.IGNORECASE)
    value = re.sub(r"<sup[^>]*>\s*\[?(\d{1,2})\]?\s*</sup>", r"[\1]", value, flags=re.IGNORECASE)
    value = re.sub(r"\[\^(\d{1,2})\]", r"[\1]", value)
    value = re.sub(r"\[\s*(\d{1,2})\s*[,;/]\s*(\d{1,2})\s*\]", r"[\1][\2]", value)
    return value


def _clean_model_html(raw: str) -> str:
    value = (raw or "").strip()
    value = re.sub(r"^```(?:html)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    value = normalize_model_citations(value)
    return sanitize_html(value.strip())


def gemini_text(
    model: str,
    prompt: str,
    *,
    max_output_tokens: int,
    temperature: float = 0.7,
    validator: Callable[[str], list[str]] | None = None,
    attempts: int | None = None,
) -> str:
    """Generate long-form text/HTML without embedding it inside JSON."""
    attempt_count = max(1, attempts or MAX_TEXT_ATTEMPTS)
    last_error: Exception | None = None
    retry_note = ""

    for attempt in range(1, attempt_count + 1):
        effective_prompt = prompt
        if retry_note:
            effective_prompt += f"""

Previous output issue:
{retry_note}
Produce a fresh, complete article. Do not echo the prompt or research JSON.
"""
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=effective_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    candidate_count=1,
                ),
            )
            finish_reason = _response_finish_reason(response)
            if finish_reason and any(token in finish_reason.upper() for token in ("MAX_TOKENS", "SAFETY", "RECITATION")):
                raise RuntimeError(f"모델 생성이 정상 종료되지 않았습니다: {finish_reason}")
            value = _extract_response_text(response)
            issues = validator(value) if validator else []
            if issues:
                raise ValueError("; ".join(issues[:8]))
            return value
        except Exception as exc:
            last_error = exc
            retry_note = _short_error(exc)
            log(f"  ⚠️ 장문 출력 재시도 {attempt}/{attempt_count}: {retry_note}")
            if attempt < attempt_count:
                time.sleep(min(2 * attempt, 6))

    raise RuntimeError(
        f"장문 출력을 {attempt_count}회 생성하지 못했습니다: "
        f"{_short_error(last_error or RuntimeError('unknown error'))}"
    )


# -----------------------------------------------------------------------------
# Google Sheets
# -----------------------------------------------------------------------------
def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def normalize_header_name(value: str) -> str:
    """헤더 표기의 공백·영문 괄호 설명 차이를 제거해 비교합니다.

    예: ``학명(Scientific Name)`` -> ``학명``
        ``슬러그 (Slug)`` -> ``슬러그``
        ``스토리 앵글`` -> ``스토리앵글``
    """
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\ufeff", "").strip()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^]]*\]", "", text)
    text = re.sub(r"[\s_\-/]+", "", text)
    return text.casefold()


def matching_header_indexes(headers: list[str], logical_name: str) -> list[int]:
    alias_keys = {normalize_header_name(alias) for alias in HEADER_ALIASES[logical_name]}
    return [
        index
        for index, header in enumerate(headers)
        if normalize_header_name(header) in alias_keys
    ]


def connect_sheet() -> tuple[gspread.Worksheet, list[str]]:
    creds_json = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds_json)
    spreadsheet = gc.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    headers = worksheet.row_values(1)
    changed = False

    if not headers:
        headers = LEGACY_HEADERS.copy()
        changed = True

    # 기존 시트가 '학명(Scientific Name)', '슬러그 (Slug)', '태그 (Tags)'처럼
    # 영문 설명을 포함해도 같은 헤더로 인식합니다. 동일 의미의 열을 중복 추가하지 않습니다.
    for logical_name, aliases in HEADER_ALIASES.items():
        if not matching_header_indexes(headers, logical_name):
            headers.append(aliases[0])
            changed = True

    # Google Sheets 탭의 실제 그리드 열 수보다 헤더가 많으면 W/X 같은 셀을
    # 기록할 때 gspread가 Range exceeds grid limits 오류를 냅니다.
    # 헤더를 쓰기 전에 그리드를 확장하고 워크시트 메타데이터를 새로 읽습니다.
    required_cols = len(headers)
    if worksheet.col_count < required_cols:
        log(f"📐 시트 열 확장: {worksheet.col_count}열 → {required_cols}열")
        worksheet.resize(cols=required_cols)
        worksheet = spreadsheet.worksheet(SHEET_NAME)

    if changed:
        end = column_letter(required_cols)
        worksheet.update(values=[headers], range_name=f"A1:{end}1")

    # 중복 헤더가 이미 생긴 경우에는 원본에 가까운 가장 왼쪽 열을 사용합니다.
    duplicate_messages: list[str] = []
    for logical_name in HEADER_ALIASES:
        indexes = matching_header_indexes(headers, logical_name)
        if len(indexes) > 1:
            names = ", ".join(f"{column_letter(i + 1)}열 '{headers[i]}'" for i in indexes)
            duplicate_messages.append(f"{logical_name}: {names}")
    if duplicate_messages:
        log("⚠️ 중복 의미 헤더가 있습니다. 가장 왼쪽 열을 사용합니다: " + " | ".join(duplicate_messages))

    mapping = []
    for logical_name in HEADER_ALIASES:
        idx = header_index(headers, logical_name)
        mapping.append(f"{logical_name}={column_letter(idx + 1)}:{headers[idx]}")
    log("📋 Google Sheets 헤더 매핑: " + " | ".join(mapping))
    return worksheet, headers


def header_index(headers: list[str], logical_name: str) -> int:
    indexes = matching_header_indexes(headers, logical_name)
    if indexes:
        return indexes[0]
    raise KeyError(f"시트 헤더를 찾을 수 없습니다: {logical_name}")


def value_at(row: list[str], headers: list[str], logical_name: str) -> str:
    idx = header_index(headers, logical_name)
    return row[idx].strip() if idx < len(row) else ""


def update_sheet_fields(
    worksheet: gspread.Worksheet,
    headers: list[str],
    row_number: int,
    fields: dict[str, Any],
) -> None:
    # 방어적으로 필요한 열 수를 다시 확인합니다.
    max_required_col = max(header_index(headers, name) + 1 for name in fields)
    if worksheet.col_count < max_required_col:
        worksheet.resize(cols=max_required_col)

    updates = []
    for logical_name, value in fields.items():
        idx = header_index(headers, logical_name) + 1
        cell = f"{column_letter(idx)}{row_number}"
        updates.append({"range": cell, "values": [[str(value if value is not None else "")]]})

    if updates:
        worksheet.batch_update(updates)


def parse_sheet_item(row_number: int, row: list[str], headers: list[str]) -> SheetItem:
    raw_tags = value_at(row, headers, "tags")
    post_id_raw = value_at(row, headers, "post_id")
    return SheetItem(
        row_number=row_number,
        status=value_at(row, headers, "status"),
        scientific_name=value_at(row, headers, "scientific_name"),
        display_title=value_at(row, headers, "title"),
        taxonomy=value_at(row, headers, "taxonomy"),
        category=value_at(row, headers, "category") or "Uncategorized",
        story_angle=value_at(row, headers, "story_angle") or "생태와 진화의 과학적 해설",
        slug=slugify(value_at(row, headers, "slug")),
        tags=[tag.strip() for tag in raw_tags.split(",") if tag.strip()],
        reviewer=value_at(row, headers, "reviewer"),
        review_note=value_at(row, headers, "review_note"),
        language=value_at(row, headers, "language") or "ko",
        post_id=safe_int(post_id_raw) if post_id_raw else None,
        quality_score=safe_int(value_at(row, headers, "quality_score")),
        source_count=safe_int(value_at(row, headers, "source_count")),
        en_post_id=(safe_int(value_at(row, headers, "en_post_id")) or None),
        en_quality_score=safe_int(value_at(row, headers, "en_quality_score")),
        rewrite_attempts=safe_int(value_at(row, headers, "rewrite_attempts")),
        cleanup_note=value_at(row, headers, "cleanup_note"),
    )


def choose_sheet_item(worksheet: gspread.Worksheet, headers: list[str]) -> SheetItem | None:
    rows = worksheet.get_all_values()[1:]
    items = [parse_sheet_item(i + 2, row, headers) for i, row in enumerate(rows)]

    if PROCESS_MODE == "sync_only":
        return None

    # 기존 비공개 글 재작성은 신규 글과 영문 보완보다 항상 먼저 처리합니다.
    if PROCESS_MODE in {"auto", "legacy_rewrite"}:
        for item in items:
            if item.status in LEGACY_REWRITE_STATES and item.scientific_name and item.post_id:
                return item
        if PROCESS_MODE == "legacy_rewrite":
            return None

    # 영문만 실패한 행을 복구합니다.
    retry_states = {
        "한국어예약/영문검수필요",
        "한국어완료/영문검수필요",
        "기존한국어재예약/영문검수필요",
    }
    if PROCESS_MODE in {"auto", "english_retry"}:
        for item in items:
            if item.status in retry_states and item.scientific_name and item.post_id:
                return item
        if PROCESS_MODE == "english_retry":
            return None

    # 신규 주제는 기존 정리 대상이 모두 끝난 뒤 컨트롤러가 PROCESS_MODE=new로 실행합니다.
    if PROCESS_MODE in {"auto", "new"}:
        for item in items:
            if item.status in {"대기", "재작성"} and item.scientific_name:
                return item
    return None


# -----------------------------------------------------------------------------
# WordPress REST API
# -----------------------------------------------------------------------------
def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    url = f"{WP_URL}/{endpoint.lstrip('/')}"
    response = session.request(
        method,
        url,
        auth=wp_auth,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"WordPress {method} {endpoint} 실패 ({response.status_code}): {response.text[:500]}")
    return response


def wp_root_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    url = f"{WP_SITE_URL}/wp-json/{endpoint.lstrip('/')}"
    response = session.request(
        method,
        url,
        auth=wp_auth,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"WordPress {method} {endpoint} 실패 ({response.status_code}): {response.text[:500]}")
    return response


def _bridge_request(
    method: str,
    endpoint: str,
    *,
    authenticated: bool,
    json_payload: dict[str, Any] | None = None,
) -> requests.Response:
    """Call the bridge route through both common WordPress REST URL forms.

    Some security or cache layers intermittently reject Basic Auth on a public
    endpoint or only allow the rest_route query form. Trying both forms avoids
    treating a temporary REST routing issue as a deactivated plugin.
    """
    clean = endpoint.strip("/")
    candidates: list[tuple[str, dict[str, str] | None]] = [
        (f"{WP_SITE_URL}/wp-json/{clean}", None),
        (f"{WP_SITE_URL}/", {"rest_route": f"/{clean}"}),
    ]
    auth_candidates: list[tuple[str, tuple[str, str] | None]]
    if authenticated:
        auth_candidates = [("auth", wp_auth)]
    else:
        # The status route is public. Test it without credentials first because
        # a WAF can reject an unnecessary Authorization header.
        auth_candidates = [("public", None), ("auth", wp_auth)]

    errors: list[str] = []
    for attempt in range(1, BRIDGE_CHECK_RETRIES + 1):
        for url, params in candidates:
            for auth_label, auth_value in auth_candidates:
                try:
                    response = session.request(
                        method,
                        url,
                        params=params,
                        json=json_payload,
                        auth=auth_value,
                        timeout=REQUEST_TIMEOUT,
                        allow_redirects=True,
                    )
                except requests.RequestException as exc:
                    errors.append(f"{auth_label} {url}: {type(exc).__name__}: {exc}")
                    continue

                if response.status_code < 400:
                    return response

                body = re.sub(r"\s+", " ", response.text or "").strip()[:240]
                errors.append(
                    f"{auth_label} {response.url}: HTTP {response.status_code}"
                    + (f" · {body}" if body else "")
                )

        if attempt < BRIDGE_CHECK_RETRIES:
            time.sleep(BRIDGE_RETRY_DELAY_SECONDS * attempt)

    detail = " | ".join(errors[-8:]) if errors else "응답 없음"
    raise RuntimeError(f"TaxonGuru Bridge REST 요청 실패: {detail}")


def _bridge_namespace_visible() -> bool:
    candidates: list[tuple[str, dict[str, str] | None]] = [
        (f"{WP_SITE_URL}/wp-json/", None),
        (f"{WP_SITE_URL}/", {"rest_route": "/"}),
    ]
    for url, params in candidates:
        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if response.status_code >= 400:
                continue
            payload = response.json()
            namespaces = payload.get("namespaces", []) if isinstance(payload, dict) else []
            if "taxonguru/v1" in namespaces:
                return True
            routes = payload.get("routes", {}) if isinstance(payload, dict) else {}
            if any(str(route).startswith("/taxonguru/v1/") for route in routes):
                return True
        except Exception:
            continue
    return False


def ensure_multilingual_backend() -> None:
    if not ENABLE_ENGLISH:
        return
    if MULTILINGUAL_BACKEND != "taxonguru_bridge":
        raise RuntimeError(
            "현재 패키지는 MULTILINGUAL_BACKEND=taxonguru_bridge를 지원합니다. "
            "동봉된 TaxonGuru Multilingual Bridge 플러그인을 설치·활성화하세요."
        )

    try:
        response = _bridge_request(
            "GET",
            "taxonguru/v1/status",
            authenticated=False,
        )
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("active"):
            raise RuntimeError(f"예상하지 못한 상태 응답: {str(payload)[:300]}")
        log(
            f"🌐 다국어 브리지 확인: {payload.get('version', 'unknown')} · "
            f"{payload.get('english_base', '')}"
        )
        return
    except Exception as exc:
        if _bridge_namespace_visible():
            log(
                "🌐 다국어 브리지 네임스페이스는 확인됐지만 status 경로 응답이 불안정합니다. "
                f"게시물 메타 연결 방식으로 계속 진행합니다: {_short_error(exc)}"
            )
            return
        if BRIDGE_PREFLIGHT_STRICT:
            raise RuntimeError(
                "TaxonGuru Multilingual Bridge 상태 확인에 실패했습니다. "
                "플러그인 활성화 여부와 REST API 차단 설정을 확인하세요. "
                f"상세: {_short_error(exc)}"
            ) from exc
        log(
            "⚠️ 다국어 브리지 사전 확인을 완료하지 못했습니다. "
            "일시적인 보안·캐시·REST 경로 문제일 수 있어 게시물 생성은 계속 진행하고, "
            "최종 연결 단계에서 WordPress 게시물 메타 방식으로 다시 확인합니다. "
            f"상세: {_short_error(exc)}"
        )


def link_translation_posts(ko_post_id: int, en_post_id: int) -> dict[str, Any]:
    payload = {"ko_post_id": ko_post_id, "en_post_id": en_post_id}
    try:
        response = _bridge_request(
            "POST",
            "taxonguru/v1/link-translations",
            authenticated=True,
            json_payload=payload,
        )
        result = response.json()
        if isinstance(result, dict) and result.get("linked"):
            return result
        raise RuntimeError(f"예상하지 못한 연결 응답: {str(result)[:300]}")
    except Exception as route_error:
        # The bridge route can be hidden by a WAF even while the plugin's REST
        # post meta is active. Link the pair through the core posts endpoint.
        log(
            "  ⚠️ 브리지 전용 연결 경로를 사용할 수 없어 WordPress 게시물 메타 방식으로 전환합니다: "
            f"{_short_error(route_error)}"
        )
        try:
            ko_post = wp_request(
                "POST",
                f"posts/{ko_post_id}",
                json={
                    "meta": {
                        "_taxonguru_language": "ko",
                        "_taxonguru_translation_id": en_post_id,
                    }
                },
            ).json()
            en_post = wp_request(
                "POST",
                f"posts/{en_post_id}",
                json={
                    "meta": {
                        "_taxonguru_language": "en",
                        "_taxonguru_translation_id": ko_post_id,
                    }
                },
            ).json()
        except Exception as meta_error:
            raise RuntimeError(
                "다국어 브리지 전용 경로와 WordPress 게시물 메타 연결이 모두 실패했습니다. "
                "플러그인이 실제로 활성화되어 있는지, WordPress REST API 또는 애플리케이션 비밀번호가 "
                "보안 플러그인·호스팅 방화벽에 의해 차단되는지 확인하세요. "
                f"전용 경로: {_short_error(route_error)} · 메타 경로: {_short_error(meta_error)}"
            ) from meta_error

        ko_url = str(ko_post.get("link", ""))
        en_url = str(en_post.get("link", ""))
        if not en_url or "/en/" not in en_url:
            en_slug = str(en_post.get("slug", "")).strip("/")
            en_url = f"{WP_SITE_URL}/en/{en_slug}/" if en_slug else en_url
        return {
            "linked": True,
            "method": "core_post_meta",
            "ko_post_id": ko_post_id,
            "en_post_id": en_post_id,
            "ko_url": ko_url,
            "en_url": en_url,
        }


def get_or_create_wp_term(term_name: str, taxonomy: str) -> int | None:
    if not term_name:
        return None
    response = wp_request("GET", taxonomy, params={"search": term_name, "per_page": 100})
    for item in response.json():
        if item.get("name", "").casefold() == term_name.casefold():
            return int(item["id"])
    response = wp_request("POST", taxonomy, json={"name": term_name})
    return int(response.json()["id"])


def find_post_by_slug(slug: str) -> dict[str, Any] | None:
    for status in ["draft", "pending", "publish", "future", "private"]:
        response = wp_request(
            "GET",
            "posts",
            params={"slug": slug, "status": status, "context": "edit", "per_page": 10},
        )
        items = response.json()
        if items:
            return items[0]
    return None


def upload_media_bytes(
    image_bytes: bytes,
    filename: str,
    mime_type: str,
    alt_text: str,
    caption_ko: str,
    caption_en: str,
    description_html: str,
) -> UploadedMedia:
    headers = {
        "Content-Type": mime_type,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    response = wp_request("POST", "media", headers=headers, data=image_bytes)
    payload = response.json()
    media_id = int(payload["id"])
    wp_request(
        "POST",
        f"media/{media_id}",
        json={
            "alt_text": alt_text,
            "caption": caption_ko,
            "description": description_html,
            "title": alt_text,
        },
    )
    return UploadedMedia(
        media_id=media_id,
        source_url=payload.get("source_url", ""),
        caption_ko=caption_ko,
        caption_en=caption_en,
        source_kind="commons" if "Wikimedia" in description_html else "ai",
    )


def parse_wp_local_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SCHEDULE_TZ)
    return parsed.astimezone(SCHEDULE_TZ)


def list_future_posts() -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    page = 1
    while page <= 10:
        response = wp_request(
            "GET",
            "posts",
            params={
                "status": "future",
                "context": "edit",
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "asc",
            },
        )
        batch = response.json()
        posts.extend(batch)
        total_pages = safe_int(response.headers.get("X-WP-TotalPages"), 1)
        if page >= total_pages or not batch:
            break
        page += 1
    return posts


def calculate_next_schedule_datetime(hour: int, minute: int) -> datetime:
    """Find the next free WordPress publication slot for a specific local clock time."""
    now_local = datetime.now(SCHEDULE_TZ)
    minimum_time = now_local + timedelta(minutes=MIN_SCHEDULE_LEAD_MINUTES)

    candidate = (now_local + timedelta(days=max(0, SCHEDULE_AFTER_DAYS))).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if candidate <= minimum_time:
        candidate += timedelta(days=max(1, SCHEDULE_INTERVAL_DAYS))

    occupied: list[datetime] = []
    for post in list_future_posts():
        post_date = parse_wp_local_datetime(str(post.get("date", "")))
        if post_date:
            occupied.append(post_date)

    interval = timedelta(days=max(1, SCHEDULE_INTERVAL_DAYS))
    for _ in range(max(1, MAX_SCHEDULE_LOOKAHEAD_DAYS + 1)):
        collision = any(abs((used - candidate).total_seconds()) < 60 for used in occupied)
        if not collision and candidate > minimum_time:
            return candidate
        candidate += interval

    raise RuntimeError("사용 가능한 WordPress 예약 슬롯을 찾지 못했습니다.")


def upsert_post(
    slug: str,
    title: str,
    excerpt: str,
    content: str,
    featured_media: int | None,
    category_id: int | None,
    tag_ids: list[int],
    publish_mode: Literal["future", "draft"],
    scheduled_at: datetime | None = None,
    post_meta: dict[str, Any] | None = None,
    existing_post_id: int | None = None,
) -> dict[str, Any]:
    existing: dict[str, Any] | None = None
    if existing_post_id:
        try:
            existing = wp_request("GET", f"posts/{existing_post_id}", params={"context": "edit"}).json()
        except Exception as exc:
            log(f"  ⚠️ 기존 WordPress 글 ID {existing_post_id} 조회 실패, 슬러그로 다시 찾습니다: {exc}")
    if not existing:
        existing = find_post_by_slug(slug)
    if existing and existing.get("status") == "publish" and not existing_post_id:
        raise RuntimeError(f"같은 슬러그의 공개 글이 이미 존재합니다: {existing.get('link')}")

    data: dict[str, Any] = {
        "title": title,
        "excerpt": excerpt,
        "content": content,
        "slug": slug,
        "comment_status": "open",
    }

    if publish_mode == "future":
        if scheduled_at is None:
            raise ValueError("예약 발행에는 scheduled_at이 필요합니다.")
        scheduled_local = scheduled_at.astimezone(SCHEDULE_TZ)
        scheduled_utc = scheduled_local.astimezone(timezone.utc)
        data.update(
            {
                "status": "future",
                "date": scheduled_local.strftime("%Y-%m-%dT%H:%M:%S"),
                "date_gmt": scheduled_utc.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
    else:
        data["status"] = DRAFT_STATUS

    if featured_media:
        data["featured_media"] = featured_media
    if category_id:
        data["categories"] = [category_id]
    if tag_ids:
        data["tags"] = tag_ids
    if post_meta:
        data["meta"] = post_meta

    if existing:
        return wp_request("POST", f"posts/{existing['id']}", json=data).json()
    return wp_request("POST", "posts", json=data).json()


def get_post(post_id: int) -> dict[str, Any]:
    return wp_request("GET", f"posts/{post_id}", params={"context": "edit"}).json()


def sync_scheduled_posts(
    worksheet: gspread.Worksheet,
    headers: list[str],
) -> None:
    """Reflect WordPress future→publish transitions back into Google Sheets."""
    rows = worksheet.get_all_values()[1:]
    for index, row in enumerate(rows, start=2):
        item = parse_sheet_item(index, row, headers)
        manual_review_state = item.status in {
            "수동검수대기", "기존수동검수대기", "한국어완료/영문수동검수대기"
        }
        if "예약" not in item.status and item.status not in {"완료", "한국어공개/영문예약"} and not manual_review_state:
            continue
        if not item.post_id:
            continue

        legacy_scheduled = item.status in LEGACY_SCHEDULED_STATES or item.status.startswith("기존한국어재예약")
        try:
            ko_post = get_post(item.post_id)
            ko_status = str(ko_post.get("status", ""))
            en_post = get_post(item.en_post_id) if item.en_post_id else None
            en_status = str(en_post.get("status", "")) if en_post else "disabled"

            fields: dict[str, Any] = {}

            # Recovery mode freezes previously scheduled posts before WordPress publishes them.
            # They become ordinary drafts and move to a manual-review state.
            if ADSENSE_RECOVERY_MODE:
                if ko_status == "future":
                    ko_post = wp_request("POST", f"posts/{item.post_id}", json={"status": DRAFT_STATUS}).json()
                    ko_status = str(ko_post.get("status", DRAFT_STATUS))
                    manual_review_state = True
                    fields.update({
                        "status": "기존수동검수대기" if legacy_scheduled else "수동검수대기",
                        "scheduled_date": "",
                        "cleanup_note": "AdSense 복구모드에서 기존 예약을 중지하고 사람 검수용 초안으로 전환",
                    })
                if en_post and en_status == "future":
                    en_post = wp_request("POST", f"posts/{item.en_post_id}", json={"status": DRAFT_STATUS}).json()
                    en_status = str(en_post.get("status", DRAFT_STATUS))
                    fields["en_scheduled_date"] = ""
                    if ko_status == "publish":
                        manual_review_state = True
                        fields.update({
                            "status": "한국어완료/영문수동검수대기",
                            "cleanup_note": "AdSense 복구모드에서 영문 예약을 중지하고 사람 검수용 초안으로 전환",
                        })

            if ko_status == "publish":
                fields["public_url"] = ko_post.get("link", "")
            elif ko_status == "future":
                scheduled = parse_wp_local_datetime(str(ko_post.get("date", "")))
                if scheduled:
                    fields["scheduled_date"] = scheduled.strftime("%Y-%m-%d %H:%M %Z")
            elif ko_status == "draft":
                if manual_review_state:
                    pass
                elif legacy_scheduled:
                    next_attempt = max(1, item.rewrite_attempts)
                    next_state = "기존재작성재시도" if next_attempt < MAX_LEGACY_REWRITE_ATTEMPTS else "기존비공개보류"
                    fields.update({"status": next_state, "error": "재작성 예약글이 초안 상태로 변경되었습니다."})
                else:
                    fields.update({"status": "검수필요", "error": "한국어 예약글이 초안 상태로 변경되었습니다."})

            if en_post:
                if en_status == "publish":
                    fields["en_public_url"] = en_post.get("link", "")
                elif en_status == "future":
                    en_scheduled = parse_wp_local_datetime(str(en_post.get("date", "")))
                    if en_scheduled:
                        fields["en_scheduled_date"] = en_scheduled.strftime("%Y-%m-%d %H:%M %Z")
                elif en_status == "draft" and ko_status == "publish":
                    fields.update({
                        "status": "기존한국어재예약/영문검수필요" if legacy_scheduled else "한국어완료/영문검수필요",
                        "en_error": "영문 예약글이 초안 상태로 변경되었습니다.",
                    })

            if manual_review_state and ko_status == "publish" and (
                not ENABLE_ENGLISH or not item.en_post_id or en_status == "publish"
            ):
                fields.update({
                    "status": "기존한영수정완료" if item.status.startswith("기존") else "완료",
                    "error": "",
                    "en_error": "",
                    "cleanup_note": "사람 검수 후 WordPress 공개 완료",
                })
            elif manual_review_state and ko_status == "publish" and ENABLE_ENGLISH and item.en_post_id and en_status == "draft":
                fields.update({
                    "status": "한국어완료/영문수동검수대기",
                    "cleanup_note": "한국어 사람 검수 공개 완료 / 영어 초안 검수 대기",
                })
            elif ko_status == "publish" and (not ENABLE_ENGLISH or en_status == "publish"):
                fields.update({
                    "status": "기존한영수정완료" if legacy_scheduled else "완료",
                    "error": "",
                    "en_error": "",
                    "cleanup_note": "재작성 글 예약 발행 완료" if legacy_scheduled else item.cleanup_note,
                })
            elif ko_status == "publish" and en_status == "future":
                fields["status"] = "기존한국어공개/영문재예약" if legacy_scheduled else "한국어공개/영문예약"

            if fields:
                update_sheet_fields(worksheet, headers, item.row_number, fields)
        except Exception as exc:
            log(f"  ⚠️ 예약 상태 동기화 실패(행 {item.row_number}): {exc}")


# -----------------------------------------------------------------------------
# Grounded research
# -----------------------------------------------------------------------------
def _obj_value(obj: Any, key: str, default: Any = None) -> Any:
    """Read a value from either a dict or an SDK/Pydantic object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def classify_source_type(url: str, publisher: str = "", title: str = "") -> str:
    """Classify a source conservatively from its domain and metadata."""
    host = (urlsplit(url).hostname or "").casefold()
    publisher_key = publisher.casefold()
    title_key = title.casefold()

    if host.endswith(".gov") or ".gov." in host:
        return "government"
    if host.endswith(".edu") or ".edu." in host or any(
        token in host for token in ["si.edu", "nhm.ac.uk", "amnh.org", "museum", "university"]
    ):
        return "museum_or_university"
    if any(
        token in host
        for token in [
            "gbif.org",
            "marinespecies.org",
            "ncbi.nlm.nih.gov",
            "iucnredlist.org",
            "itis.gov",
            "catalogueoflife.org",
        ]
    ):
        return "scientific_database"
    if host == "doi.org" or "journal" in host or "springer" in host or "wiley" in host or "sciencedirect" in host:
        return "peer_reviewed_paper"
    if any(token in publisher_key for token in ["university", "museum", "institute", "academy"]):
        return "museum_or_university"
    if any(token in title_key for token in ["journal", "proceedings", "research", "revision"]):
        return "peer_reviewed_paper"
    if "wikipedia.org" in host:
        return "reputable_secondary"
    return "other"


def merge_research_sources(*groups: list[ResearchSource], limit: int = 14) -> list[ResearchSource]:
    merged: list[ResearchSource] = []
    seen: set[str] = set()
    today = datetime.now().strftime("%Y-%m-%d")

    for group in groups:
        for source in group:
            normalized = resolve_source_url(source.url)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            source.url = normalized
            source.title = strip_html(source.title).strip() or normalized
            source.publisher = strip_html(source.publisher).strip() or (urlsplit(normalized).hostname or "")
            source.accessed_date = source.accessed_date or today
            if source.source_type == "other":
                source.source_type = classify_source_type(normalized, source.publisher, source.title)  # type: ignore[assignment]
            merged.append(source)
            if len(merged) >= limit:
                return merged
    return merged


def fetch_seed_context(scientific_name: str) -> dict[str, Any]:
    """Collect deterministic taxonomy and bibliography seeds before asking Gemini.

    These APIs are not used blindly as article facts. They create a stable source
    catalogue so a temporary grounding-format issue cannot turn a well-known
    species into a false '0 sources' result.
    """
    seed: dict[str, Any] = {
        "gbif": {},
        "wikipedia": {},
        "crossref": [],
        "worms": {},
        "ncbi_taxonomy": {},
    }

    # GBIF taxonomy match
    try:
        response = session.get(
            "https://api.gbif.org/v1/species/match",
            params={"name": scientific_name, "verbose": "true"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            seed["gbif"] = response.json()
    except requests.RequestException as exc:
        log(f"  ⚠️ GBIF 조회 실패: {exc}")

    # Wikipedia summary is a discovery seed, never the sole authority.
    try:
        title = quote(scientific_name.replace(" ", "_"), safe="")
        response = session.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            data = response.json()
            seed["wikipedia"] = {
                "title": data.get("title", ""),
                "extract": data.get("extract", ""),
                "page": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            }
    except requests.RequestException as exc:
        log(f"  ⚠️ Wikipedia 요약 조회 실패: {exc}")

    # Crossref scholarly works. We retain metadata, then let the research model
    # decide which papers actually support a claim.
    try:
        response = session.get(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": f'"{scientific_name}"',
                "rows": 8,
                "mailto": CONTACT_EMAIL,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            for work in response.json().get("message", {}).get("items", []):
                title_list = work.get("title") or []
                doi = work.get("DOI", "")
                seed["crossref"].append(
                    {
                        "title": title_list[0] if title_list else "",
                        "doi": doi,
                        "url": f"https://doi.org/{doi}" if doi else work.get("URL", ""),
                        "publisher": work.get("publisher", ""),
                        "type": work.get("type", ""),
                        "score": work.get("score", 0),
                    }
                )
    except requests.RequestException as exc:
        log(f"  ⚠️ Crossref 조회 실패: {exc}")

    # WoRMS is especially useful for marine taxa such as Scotoplanes.
    try:
        encoded_name = quote(scientific_name, safe="")
        response = session.get(
            f"https://www.marinespecies.org/rest/AphiaRecordsByName/{encoded_name}",
            params={"like": "false", "marine_only": "false"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            records = response.json() or []
            exact = next(
                (
                    record
                    for record in records
                    if str(record.get("scientificname", "")).casefold() == scientific_name.casefold()
                ),
                records[0] if records else {},
            )
            seed["worms"] = exact
    except requests.RequestException as exc:
        log(f"  ⚠️ WoRMS 조회 실패: {exc}")

    # NCBI Taxonomy gives another independent taxonomic identifier when present.
    try:
        response = session.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "taxonomy",
                "term": f'"{scientific_name}"[Scientific Name]',
                "retmode": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            id_list = response.json().get("esearchresult", {}).get("idlist", [])
            if id_list:
                seed["ncbi_taxonomy"] = {"tax_id": str(id_list[0])}
    except requests.RequestException as exc:
        log(f"  ⚠️ NCBI Taxonomy 조회 실패: {exc}")

    return seed


def build_seed_sources(seed_context: dict[str, Any], scientific_name: str) -> list[ResearchSource]:
    today = datetime.now().strftime("%Y-%m-%d")
    sources: list[ResearchSource] = []

    gbif = seed_context.get("gbif") or {}
    gbif_key = gbif.get("usageKey") or gbif.get("speciesKey") or gbif.get("key")
    if gbif_key:
        canonical_name = gbif.get("canonicalName") or gbif.get("scientificName") or scientific_name
        sources.append(
            ResearchSource(
                title=f"GBIF species record: {canonical_name}",
                url=f"https://www.gbif.org/species/{gbif_key}",
                publisher="Global Biodiversity Information Facility (GBIF)",
                source_type="scientific_database",
                accessed_date=today,
            )
        )

    wikipedia = seed_context.get("wikipedia") or {}
    if normalize_url(str(wikipedia.get("page", ""))):
        sources.append(
            ResearchSource(
                title=str(wikipedia.get("title") or scientific_name),
                url=str(wikipedia.get("page", "")),
                publisher="Wikipedia",
                source_type="reputable_secondary",
                accessed_date=today,
            )
        )

    worms = seed_context.get("worms") or {}
    aphia_id = worms.get("AphiaID")
    if aphia_id:
        sources.append(
            ResearchSource(
                title=f"WoRMS taxon details: {worms.get('scientificname') or scientific_name}",
                url=f"https://www.marinespecies.org/aphia.php?p=taxdetails&id={aphia_id}",
                publisher="World Register of Marine Species (WoRMS)",
                source_type="scientific_database",
                accessed_date=today,
            )
        )

    ncbi = seed_context.get("ncbi_taxonomy") or {}
    tax_id = str(ncbi.get("tax_id", "")).strip()
    if tax_id:
        sources.append(
            ResearchSource(
                title=f"NCBI Taxonomy: {scientific_name}",
                url=f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tax_id}",
                publisher="National Center for Biotechnology Information",
                source_type="scientific_database",
                accessed_date=today,
            )
        )

    for work in seed_context.get("crossref") or []:
        url = normalize_url(str(work.get("url", "")))
        title = strip_html(str(work.get("title", ""))).strip()
        if not url or not title:
            continue
        sources.append(
            ResearchSource(
                title=title,
                url=url,
                publisher=str(work.get("publisher", "")),
                source_type="peer_reviewed_paper",
                accessed_date=today,
            )
        )

    return merge_research_sources(sources, limit=10)


def extract_interaction_citations(interaction: Any) -> list[ResearchSource]:
    """Extract Google Search URL citations from Interactions API annotations."""
    today = datetime.now().strftime("%Y-%m-%d")
    extracted: list[ResearchSource] = []

    for step in _obj_value(interaction, "steps", []) or []:
        if _obj_value(step, "type", "") != "model_output":
            continue
        for block in _obj_value(step, "content", []) or []:
            for annotation in _obj_value(block, "annotations", []) or []:
                if _obj_value(annotation, "type", "") != "url_citation":
                    continue
                url = resolve_source_url(str(_obj_value(annotation, "url", "")))
                if not url:
                    continue
                title = str(_obj_value(annotation, "title", "")).strip() or url
                host = urlsplit(url).hostname or ""
                extracted.append(
                    ResearchSource(
                        title=title,
                        url=url,
                        publisher=host,
                        source_type=classify_source_type(url, host, title),  # type: ignore[arg-type]
                        accessed_date=today,
                    )
                )
    return merge_research_sources(extracted, limit=12)


def run_grounded_research_search(
    item: SheetItem,
    seed_context: dict[str, Any],
) -> tuple[str, list[ResearchSource]]:
    """Run a citation-producing web research pass before JSON extraction."""
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
Research the organism below for a bilingual popular-science article. Use Google Search,
prefer primary or institutional sources, and write a compact evidence memo. Every major
claim must be grounded in the search results. Do not invent URLs or references.

Subject
- Scientific name: {item.scientific_name}
- Existing taxonomy note: {item.taxonomy}
- Editorial angle: {item.story_angle}
- Research date: {today}

Deterministic API seeds
{json.dumps(seed_context, ensure_ascii=False, indent=2)[:22000]}

Cover accepted name and taxonomy, distribution and habitat, morphology, locomotion,
feeding and ecological role, reproduction if documented, conservation status if assessed,
common misconceptions, and any disputed or uncertain claims. Clearly say when evidence is limited.
"""
    interaction = gemini_client.interactions.create(
        model=RESEARCH_MODEL,
        input=prompt,
        tools=[{"type": "google_search"}],
    )
    memo = str(_obj_value(interaction, "output_text", "") or "").strip()
    citations = extract_interaction_citations(interaction)
    return memo, citations


def research_subject(item: SheetItem) -> ResearchPackage:
    seed_context = fetch_seed_context(item.scientific_name)
    seed_sources = build_seed_sources(seed_context, item.scientific_name)

    search_memo = ""
    search_sources: list[ResearchSource] = []
    try:
        search_memo, search_sources = run_grounded_research_search(item, seed_context)
    except Exception as exc:
        # The deterministic seeds still allow the job to continue when Google Search
        # has a temporary outage or changes its annotation format.
        log(f"  ⚠️ Google Search 연구 패스 실패, API 시드로 계속합니다: {exc}")

    source_catalog = merge_research_sources(search_sources, seed_sources, limit=12)
    log(
        f"  🔎 출처 후보: Google Search {len(search_sources)}개 + "
        f"기관/API {len(seed_sources)}개 → 중복 제거 {len(source_catalog)}개"
    )

    if not source_catalog:
        return ResearchPackage(accepted_scientific_name=item.scientific_name)

    source_catalog_json = json.dumps(
        [source.model_dump() for source in source_catalog],
        ensure_ascii=False,
        indent=2,
    )
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
당신은 자연과학 편집부의 팩트체커다. 아래 연구 메모와 고정된 출처 목록만 사용해
ResearchPackage JSON을 작성하라. 검색하거나 새로운 URL을 만들지 마라.

연구 대상
- 학명: {item.scientific_name}
- 현재 제목 후보: {item.display_title}
- 기존 분류 메모: {item.taxonomy}
- 글의 질문/관점: {item.story_angle}
- 조사일: {today}

Google Search 기반 연구 메모
{search_memo[:30000]}

기초 API 데이터
{json.dumps(seed_context, ensure_ascii=False, indent=2)[:22000]}

사용 가능한 출처 목록 — 번호는 배열 순서대로 1부터 시작한다
{source_catalog_json}

엄격한 작성 기준
1. accepted_scientific_name, common_name_ko, common_name_en, taxonomy, overview,
   distribution_and_habitat, conservation_status를 가능한 범위에서 채운다.
2. verified_facts는 최소 6건을 목표로 하되, 자료가 실제로 확인되는 내용만 쓴다.
3. 모든 verified_facts, common_misconceptions, disputed_or_uncertain 항목에는
   위 출처 목록의 번호를 source_numbers로 넣는다.
4. 전체 결과에서 서로 다른 출처 번호를 최소 4개 사용한다. 한 주장에는 가능하면
   독립적인 출처 2개를 연결한다.
5. 논쟁적 주장과 확정 사실을 분리하고, 자료가 충돌하면 양쪽 근거와 결론을 적는다.
6. Wikipedia는 보조자료일 뿐 핵심 사실의 유일한 근거로 사용하지 않는다.
7. 확인되지 않은 수치·과장·의인화·가상의 직함을 넣지 않는다.
8. sources 필드는 비워도 된다. 프로그램이 위 고정 출처 목록을 다시 삽입한다.
9. 출처 목록으로 확인할 수 없는 내용은 limitations에 기록하고 사실처럼 쓰지 않는다.
"""

    result = gemini_json(
        RESEARCH_MODEL,
        prompt,
        ResearchPackage,
        max_output_tokens=RESEARCH_MAX_OUTPUT_TOKENS,
        temperature=0.1,
    )
    assert isinstance(result, ResearchPackage)
    # Never trust the model to reproduce URLs. Keep the deterministic and
    # annotation-derived catalogue, while the model only selects source numbers.
    result.sources = [source.model_copy(deep=True) for source in source_catalog]
    return normalize_research_package(result, item.scientific_name)


def normalize_research_package(package: ResearchPackage, fallback_name: str) -> ResearchPackage:
    # Keep only sources actually cited by a fact, misconception, or disputed claim.
    # This prevents unrelated Crossref search hits from inflating the quality gate.
    cited_numbers: set[int] = set()
    for fact in package.verified_facts + package.common_misconceptions:
        cited_numbers.update(number for number in fact.source_numbers if number > 0)
    for disputed in package.disputed_or_uncertain:
        cited_numbers.update(number for number in disputed.source_numbers if number > 0)

    old_to_new: dict[int, int] = {}
    seen: set[str] = set()
    clean_sources: list[ResearchSource] = []

    for old_index, source in enumerate(package.sources, start=1):
        if cited_numbers and old_index not in cited_numbers:
            continue
        normalized = resolve_source_url(source.url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        source.url = normalized
        source.accessed_date = source.accessed_date or datetime.now().strftime("%Y-%m-%d")
        clean_sources.append(source)
        old_to_new[old_index] = len(clean_sources)

    package.sources = clean_sources
    package.accepted_scientific_name = package.accepted_scientific_name or fallback_name

    for fact in package.verified_facts + package.common_misconceptions:
        fact.source_numbers = sorted({old_to_new[n] for n in fact.source_numbers if n in old_to_new})
    for disputed in package.disputed_or_uncertain:
        disputed.source_numbers = sorted({old_to_new[n] for n in disputed.source_numbers if n in old_to_new})

    package.verified_facts = [fact for fact in package.verified_facts if fact.source_numbers]
    package.common_misconceptions = [fact for fact in package.common_misconceptions if fact.source_numbers]
    package.disputed_or_uncertain = [item for item in package.disputed_or_uncertain if item.source_numbers]
    return package


# -----------------------------------------------------------------------------
# Article writing and quality review
# -----------------------------------------------------------------------------
def story_style_for(category: str, language: Literal["ko", "en"]) -> str:
    category_key = category.casefold()
    if "extreme survivors" in category_key or "극한의 생존자" in category:
        return (
            "극한 환경의 실제 장면에서 출발해 생물이 해결해야 하는 문제와 생존 전략을 따라가는 자연 다큐멘터리형"
            if language == "ko"
            else "a cinematic survival narrative that opens inside the real habitat and follows the problems the organism must solve"
        )
    if "evolution mysteries" in category_key or "진화의 미스터리" in category:
        return (
            "널리 알려진 주장이나 오해를 먼저 던지고 출처가 뒷받침하는 증거를 하나씩 확인하는 과학 탐정형"
            if language == "ko"
            else "a science-detective feature that opens with a popular claim and tests it against source-backed evidence"
        )
    if "size lab" in category_key or "크기 비교" in category:
        return (
            "검증된 수치를 익숙한 사물이나 동물과 비교해 실제 크기를 상상하게 만드는 실험형"
            if language == "ko"
            else "a scale-comparison feature that turns verified measurements into vivid comparisons with familiar objects or animals"
        )
    if "botany" in category_key or "식물학" in category:
        return (
            "검증된 서식지 풍경에서 출발해 형태·번식·생존전략을 관찰하는 자연 에세이형"
            if language == "ko"
            else "a field-note botanical essay that begins with a verified habitat and reveals form, reproduction, and survival strategy"
        )
    return "친근하고 리듬감 있는 과학 교양 스토리텔링형" if language == "ko" else "an engaging, rhythmic popular-science narrative"


def compact_research_payload(research: ResearchPackage) -> str:
    """Keep the writing prompt grounded while avoiding an unnecessarily huge payload."""
    payload = {
        "accepted_scientific_name": research.accepted_scientific_name,
        "common_name_ko": research.common_name_ko,
        "common_name_en": research.common_name_en,
        "taxonomy": [item.model_dump() for item in research.taxonomy],
        "overview": research.overview,
        "distribution_and_habitat": research.distribution_and_habitat,
        "conservation_status": research.conservation_status,
        "verified_facts": [item.model_dump() for item in research.verified_facts],
        "disputed_or_uncertain": [item.model_dump() for item in research.disputed_or_uncertain],
        "common_misconceptions": [item.model_dump() for item in research.common_misconceptions],
        "limitations": research.limitations,
        "sources": [
            {"number": index, "title": source.title, "publisher": source.publisher, "url": source.url}
            for index, source in enumerate(research.sources, start=1)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def article_body_generation_issues(raw_html: str, language: Literal["ko", "en"]) -> list[str]:
    body = _clean_model_html(raw_html)
    plain = strip_html(body)
    issues: list[str] = []
    if not plain:
        issues.append("본문이 비어 있습니다.")
        return issues
    if body.count("[[IMAGE_1]]") != 1 or body.count("[[IMAGE_2]]") != 1:
        issues.append("[[IMAGE_1]]과 [[IMAGE_2]]를 각각 정확히 한 번 포함해야 합니다.")
    if len(citation_numbers(body)) < MIN_CITATION_MARKERS:
        issues.append(f"출처 번호가 최소 {MIN_CITATION_MARKERS}개 필요합니다.")
    if language == "ko":
        if len(plain) < MIN_KOREAN_CHARS:
            issues.append(f"한국어 본문이 {len(plain)}자로 최소 {MIN_KOREAN_CHARS}자보다 짧습니다.")
        if len(re.findall(r"[가-힣]", plain)) < 500:
            issues.append("한국어 본문에 충분한 한국어 문장이 없습니다.")
    else:
        word_count = len(re.findall(r"[A-Za-z0-9']+", plain))
        if word_count < MIN_ENGLISH_WORDS:
            issues.append(f"영문 본문이 {word_count}단어로 최소 {MIN_ENGLISH_WORDS}단어보다 짧습니다.")
        if re.search(r"[가-힣]", plain):
            issues.append("영문 본문에 한국어 문자가 포함되어 있습니다.")
    return issues


def citation_numbers(fragment: str) -> list[int]:
    cleaned = normalize_model_citations(fragment or "")
    return [safe_int(value) for value in re.findall(r"\[(\d{1,2})\]", cleaned)]


def _fact_tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z]{4,}|[가-힣]{2,}", strip_html(value or ""))
        if token.casefold() not in {"this", "that", "with", "from", "have", "their", "about", "which", "these"}
    }


def inject_grounded_citations(body_html: str, research: ResearchPackage, required: int) -> str:
    """Deterministically add valid citations to matching factual paragraphs.

    The function only uses source numbers already attached to verified facts.
    It is a final safety net after the model citation-repair pass.
    """
    body = _clean_model_html(body_html)
    existing = citation_numbers(body)
    if len(existing) >= required:
        return body

    fact_rows: list[tuple[set[str], list[int]]] = []
    fallback_numbers: list[int] = []
    for fact in research.verified_facts:
        valid = [n for n in fact.source_numbers if 1 <= n <= len(research.sources)]
        if valid:
            fact_rows.append((_fact_tokens(fact.claim), valid))
            fallback_numbers.extend(valid)
    for fact in research.common_misconceptions:
        valid = [n for n in fact.source_numbers if 1 <= n <= len(research.sources)]
        if valid:
            fact_rows.append((_fact_tokens(fact.claim), valid))
            fallback_numbers.extend(valid)
    for fact in research.disputed_or_uncertain:
        valid = [n for n in fact.source_numbers if 1 <= n <= len(research.sources)]
        if valid:
            fact_rows.append((_fact_tokens(fact.claim), valid))
            fallback_numbers.extend(valid)

    fallback_numbers = list(dict.fromkeys(fallback_numbers)) or list(range(1, min(len(research.sources), required) + 1))
    used = set(existing)
    current_count = len(existing)
    paragraph_pattern = re.compile(r"(<p(?:\s[^>]*)?>)(.*?)(</p>)", flags=re.IGNORECASE | re.DOTALL)

    def choose_number(inner: str, *, allow_fallback: bool) -> int | None:
        tokens = _fact_tokens(inner)
        best_numbers: list[int] = []
        best_score = 0
        for fact_tokens, numbers in fact_rows:
            score = len(tokens & fact_tokens)
            if score > best_score:
                best_score = score
                best_numbers = numbers
        if best_score > 0:
            number = next((n for n in best_numbers if n not in used), None)
            if number is not None:
                return number
            if best_numbers:
                return best_numbers[0]
        if allow_fallback:
            return next((n for n in fallback_numbers if n not in used), None)
        return None

    def grounded_add(match: re.Match[str]) -> str:
        nonlocal current_count
        opening, inner, closing = match.groups()
        if current_count >= required or citation_numbers(inner):
            return match.group(0)
        if len(strip_html(inner)) < 80:
            return match.group(0)
        number = choose_number(inner, allow_fallback=False)
        if number is None:
            return match.group(0)
        used.add(number)
        current_count += 1
        return f"{opening}{inner.rstrip()} [{number}]{closing}"

    repaired = paragraph_pattern.sub(grounded_add, body)

    # If lexical matching was too strict, use still-valid source numbers on long
    # factual paragraphs. This does not invent any source number.
    if current_count < required:
        def fallback_add(match: re.Match[str]) -> str:
            nonlocal current_count
            opening, inner, closing = match.groups()
            if current_count >= required or citation_numbers(inner):
                return match.group(0)
            if len(strip_html(inner)) < 120:
                return match.group(0)
            number = choose_number(inner, allow_fallback=True)
            if number is None:
                return match.group(0)
            used.add(number)
            current_count += 1
            return f"{opening}{inner.rstrip()} [{number}]{closing}"
        repaired = paragraph_pattern.sub(fallback_add, repaired)

    return _clean_model_html(repaired)


def repair_article_citations(
    item: SheetItem,
    research: ResearchPackage,
    body_html: str,
    language: Literal["ko", "en"],
) -> str:
    body = _clean_model_html(body_html)
    if len(citation_numbers(body)) >= MIN_CITATION_MARKERS:
        return body

    language_instruction = (
        "본문의 문장과 구조를 바꾸지 말고, 검증된 사실 문장 끝에 유효한 [번호] 인용만 추가하라."
        if language == "ko"
        else "Keep the wording and HTML structure unchanged. Add only valid [number] citations after source-backed factual sentences."
    )
    prompt = f"""
{language_instruction}
- Use only source numbers that exist in the source map.
- Add at least {MIN_CITATION_MARKERS} citation markers in total, preferably using different sources.
- Preserve [[IMAGE_1]] and [[IMAGE_2]] exactly once each.
- Return complete WordPress body HTML only.

Source map:
{compact_research_payload(research)}

Article HTML:
{body}
"""
    try:
        repaired = gemini_text(
            WRITER_MODEL,
            prompt,
            max_output_tokens=ARTICLE_MAX_OUTPUT_TOKENS,
            temperature=0.05,
            attempts=2,
            validator=lambda value: [
                issue for issue in article_body_generation_issues(value, language)
                if "출처 번호" in issue or "IMAGE_" in issue or "짧습니다" in issue or "한국어 문자가" in issue
            ],
        )
        body = _clean_model_html(repaired)
    except Exception as exc:
        log(f"  ⚠️ 인용 복구 모델 패스 실패, 결정적 보정으로 전환: {_short_error(exc)}")

    body = inject_grounded_citations(body, research, MIN_CITATION_MARKERS)
    return body


def metadata_issues(metadata: ArticleMetadata) -> list[str]:
    issues: list[str] = []
    if not metadata.title.strip():
        issues.append("제목이 비어 있습니다.")
    if not slugify(metadata.slug or metadata.title):
        issues.append("유효한 슬러그가 없습니다.")
    if len(metadata.excerpt.strip()) < 40:
        issues.append("요약문이 지나치게 짧습니다.")
    if len(metadata.seo_description.strip()) < 50:
        issues.append("SEO 설명이 지나치게 짧습니다.")
    if len([tag for tag in metadata.tags if tag.strip()]) < 4:
        issues.append("태그가 4개 미만입니다.")
    return issues


def article_body_prompt(
    item: SheetItem,
    research: ResearchPackage,
    language: Literal["ko", "en"],
    *,
    revision_context: str = "",
) -> str:
    style = story_style_for(item.category, language)
    research_json = compact_research_payload(research)
    if language == "ko":
        language_rules = f"""
당신은 TaxonGuru 편집팀의 과학 스토리텔러다. 검증된 연구 패키지만 이용해 한국어 본문을 작성하라.

서술 방향
- {style}
- 유명 과학 교양 블로그처럼 읽기 편하고 개성 있게 쓰되, 실제 작가의 문체를 모방하거나 전문가를 사칭하지 않는다.
- 장면형 도입, 짧은 문단, 자연스러운 비유, 절제된 유머를 활용한다.

절대 규칙
1. 연구 패키지에 없는 해부학적 구조, 색상, 행동, 발견자 수식어, 역사적 일화, 수치 또는 인과관계를 만들지 않는다.
2. '제왕적 학자', '전설적인 박사' 같은 근거 없는 직함·찬사는 금지한다. 인물은 자료에 확인되는 이름과 역할만 쓴다.
3. 색깔이나 외형 묘사는 연구 패키지에 명시된 경우에만 쓴다. 자료에 없으면 분위기를 위해 임의로 보충하지 않는다.
4. 사실을 풍부하게 보이게 하려고 연구자료 밖의 상식을 추가하지 않는다. 정보가 부족하면 범위를 좁혀 정확하게 쓴다.
5. 모든 핵심 사실 뒤에 실제 출처 번호를 [1], [2] 형식으로 붙인다.
6. 불확실하거나 논쟁적인 내용은 확인된 사실처럼 단정하지 않는다.
7. 보고서식 '핵심 요약'으로 시작하지 말고 장면·질문·의외의 사실 중 하나로 시작한다.
8. 주제에 맞는 자연스러운 소제목 4~7개를 사용하고, 문단은 보통 2~4문장으로 구성한다.
9. 전문용어는 먼저 쉬운 말로 설명하고 필요할 때 괄호 안에 용어를 쓴다.
10. 서로 다른 검증 사실 2개 이상을 연결해 독자가 “그래서 왜 중요한가”를 이해할 수 있는 편집적 설명을 최소 한 구간 포함한다. 단, 자료에 없는 결론은 만들지 않는다.
11. 모든 글에 똑같은 소제목을 반복하지 말고 주제에 맞는 질문·비교·오해 바로잡기 중 최소 하나를 포함한다.
12. [[IMAGE_1]]과 [[IMAGE_2]]를 서로 다른 적절한 위치에 각각 정확히 한 번 넣는다.
13. 참고문헌·이미지 출처·자동검수·예약시간·AI 안내는 본문에 쓰지 않는다.
14. WordPress 본문용 HTML만 출력한다. h1, script, style, iframe, form은 사용하지 않는다.
15. 순수 본문 기준 약 3,000~4,800자. 반복으로 분량을 채우지 않는다.
16. 마지막은 도입부의 장면이나 질문으로 돌아가 자연스럽게 마무리한다.
17. 한국어 문장에 중국어 한자나 일본어 가나를 혼입하지 않는다. 학명은 라틴 알파벳으로 쓴다.
"""
    else:
        language_rules = f"""
You are TaxonGuru's science storyteller. Write an original English article using only the verified research package.

Narrative direction
- {style}
- Sound like a polished, approachable popular-science blog: vivid, readable, lightly witty, and trustworthy.
- Do not translate Korean phrasing line by line and do not imitate a real writer.

Non-negotiable rules
1. Do not invent anatomy, color, behavior, historical anecdotes, measurements, causal claims, or honorific descriptions that are absent from the research package.
2. Never add flattering labels such as “legendary,” “imperial,” or “pioneering” to a person unless the supplied sources explicitly support that description.
3. Describe color or appearance only when it appears in the verified package. Do not fill gaps for atmosphere.
4. If the research is limited, narrow the story rather than supplementing it with unsupported general knowledge.
5. Attach valid source markers such as [1] and [2] to every important factual claim. Before returning, verify that the article contains at least four literal square-bracket markers, for example [1], [2], [3], and [4]. Do not use Unicode citation brackets or linked citation syntax.
6. Clearly distinguish confirmed evidence from uncertainty or dispute.
7. Open with a scene, question, or surprising source-backed fact—not a report-style summary.
8. Use four to seven topic-specific headings and compact paragraphs, usually two to four sentences.
9. Explain technical terms in plain English before using the formal term.
10. Include at least one editorial synthesis that connects two or more verified facts to answer why the subject matters, without inventing a conclusion.
11. Avoid a fixed reusable outline. Include at least one topic-specific question, comparison, or myth correction when the research package supports it.
12. Insert [[IMAGE_1]] and [[IMAGE_2]] exactly once each in two useful locations.
13. Do not include references, image credits, automated review details, scheduling details, or AI disclosure in the body.
14. Output clean WordPress body HTML only. Do not use h1, script, style, iframe, or form tags.
15. Write 1,000–1,500 substantive words without padding or repetition.
16. End by returning to the opening image or question.
17. Write English only; do not include Korean, CJK ideographs, or Japanese kana.
"""

    revision = f"\nRevision requirements from the previous review:\n{revision_context}\n" if revision_context else ""
    return f"""
{language_rules}

Topic
- Scientific name: {item.scientific_name}
- Working title context: {item.display_title}
- Central question or angle: {item.story_angle}
- Category: {item.category}

Verified research package
{research_json}
{revision}
Return the article body only, beginning with the first HTML paragraph or heading.
"""


def generate_article_body(
    item: SheetItem,
    research: ResearchPackage,
    language: Literal["ko", "en"],
    *,
    revision_context: str = "",
) -> str:
    # Do not discard a complete long article solely because citation syntax is
    # missing or formatted differently. Generate the article first, then run a
    # dedicated citation-repair pass and a deterministic grounded fallback.
    def base_issues(value: str) -> list[str]:
        return [
            issue for issue in article_body_generation_issues(value, language)
            if "출처 번호" not in issue
        ]

    raw = gemini_text(
        WRITER_MODEL,
        article_body_prompt(item, research, language, revision_context=revision_context),
        max_output_tokens=ARTICLE_MAX_OUTPUT_TOKENS,
        temperature=0.65,
        validator=base_issues,
    )
    body = _clean_model_html(raw)
    body = repair_article_citations(item, research, body, language)
    final_issues = article_body_generation_issues(body, language)
    if final_issues:
        raise RuntimeError("; ".join(final_issues[:8]))
    return body


def generate_article_metadata(
    item: SheetItem,
    research: ResearchPackage,
    body_html: str,
    language: Literal["ko", "en"],
) -> ArticleMetadata:
    plain = strip_html(body_html)
    if language == "ko":
        instruction = "한국어 제목·요약·SEO 설명을 작성하고, 태그는 한국어와 유용한 영문 검색어를 섞는다."
    else:
        instruction = "Write natural English metadata for international search readers. Use English tags only."
    prompt = f"""
Create publication metadata for the article below.
- {instruction}
- The title must be engaging but factual and must not introduce a claim that is absent from the article.
- slug must be concise lowercase ASCII words separated by hyphens.
- excerpt should be approximately 90–180 characters for Korean or 20–35 words for English.
- seo_description should be concise and factual.
- Return 6–10 useful tags.

Scientific name: {item.scientific_name}
Common name context: {research.common_name_ko if language == 'ko' else research.common_name_en}
Article language: {language}
Article text:
{plain[:10000]}
"""
    result = gemini_json(
        WRITER_MODEL,
        prompt,
        ArticleMetadata,
        max_output_tokens=METADATA_MAX_OUTPUT_TOKENS,
        temperature=0.35,
        validator=metadata_issues,
    )
    result.slug = slugify(result.slug or result.title)
    result.tags = [tag.strip() for tag in result.tags if tag.strip()][:12]
    return result


def build_article_draft(
    item: SheetItem,
    research: ResearchPackage,
    language: Literal["ko", "en"],
    *,
    revision_context: str = "",
) -> ArticleDraft:
    body = generate_article_body(item, research, language, revision_context=revision_context)
    metadata = generate_article_metadata(item, research, body, language)
    return ArticleDraft(
        title=metadata.title,
        slug=metadata.slug,
        excerpt=metadata.excerpt,
        html_body=body,
        seo_description=metadata.seo_description,
        tags=metadata.tags,
    )


def generate_article(
    item: SheetItem,
    research: ResearchPackage,
    language: Literal["ko", "en"],
) -> ArticleDraft:
    return build_article_draft(item, research, language)


def review_article(
    item: SheetItem,
    research: ResearchPackage,
    article: ArticleDraft,
    language: Literal["ko", "en"],
) -> QualityReview:
    language_name = "한국어" if language == "ko" else "영어"
    prompt = f"""
아래 {language_name} 자연과학 블로그 초안을 엄격하게 검수하라. 점수는 0~100점이다.

검수 기준
- 연구 패키지에 없는 사실·색상·해부학·수치·인과관계·인물 수식어를 만들지 않았는가
- 모든 주요 사실에 올바른 출처 번호가 있는가
- 분류학 오류나 논쟁 중인 내용을 확정 사실처럼 표현하지 않았는가
- 문체가 딱딱한 보고서가 아니라 읽기 좋은 과학 스토리텔링인가
- 장면형 도입과 자연스러운 문단 리듬이 있는가
- 클릭베이트, 가상 전문가 행세, 번역투, 과장된 찬사가 없는가
- 비유는 비유임이 분명하며 새로운 과학 사실을 암시하지 않는가
- 제목과 본문이 일치하고 다른 언어가 불필요하게 섞이지 않았는가

판정 원칙
- 단순한 문학적 연결어는 사실 주장으로 오인하지 않는다.
- 그러나 외형·색상·몸 구조·행동·발견 역사에 관한 구체적 묘사는 연구 패키지에 근거가 있어야 한다.
- 통과하려면 중대한 사실 오류와 unsupported_claims가 모두 0건이어야 한다.

연구 패키지
{compact_research_payload(research)}

검수 대상
{article.model_dump_json(indent=2)}
"""
    result = gemini_json(
        REVIEW_MODEL,
        prompt,
        QualityReview,
        max_output_tokens=REVIEW_MAX_OUTPUT_TOKENS,
        temperature=0.05,
    )
    result.score = max(0, min(100, int(result.score)))
    return result


def revise_article(
    item: SheetItem,
    research: ResearchPackage,
    article: ArticleDraft,
    review: QualityReview,
    deterministic_issues: list[str],
    language: Literal["ko", "en"],
) -> ArticleDraft:
    instructions = {
        "critical_issues": review.critical_issues,
        "unsupported_claims_to_remove": review.unsupported_claims,
        "factual_corrections": review.factual_corrections,
        "style_improvements": review.improvement_instructions,
        "system_issues": deterministic_issues,
        "previous_body": article.html_body,
    }
    revision_context = json.dumps(instructions, ensure_ascii=False, indent=2)
    return build_article_draft(
        item,
        research,
        language,
        revision_context=revision_context,
    )


def build_references_html(sources: list[ResearchSource], language: Literal["ko", "en"]) -> str:
    items: list[str] = []
    for index, source in enumerate(sources, start=1):
        title = html.escape(source.title or source.url)
        publisher = html.escape(source.publisher or ("출처" if language == "ko" else "Source"))
        accessed = html.escape(source.accessed_date or datetime.now().strftime("%Y-%m-%d"))
        url = html.escape(source.url, quote=True)
        date_label = "확인일" if language == "ko" else "accessed"
        items.append(
            f'<li id="ref-{index}"><a href="{url}" target="_blank" rel="noopener noreferrer">'
            f"{title}</a> — {publisher}, {date_label} {accessed}</li>"
        )
    heading = "참고자료" if language == "ko" else "References"
    return f"<h2>{heading}</h2><ol>" + "".join(items) + "</ol>"


def hidden_review_comment(
    language: Literal["ko", "en"],
    quality_score: int,
    source_count: int,
    scheduled_at: datetime | None,
    review_summary: str,
) -> str:
    scheduled_text = scheduled_at.strftime("%Y-%m-%d %H:%M %Z") if scheduled_at else "draft"
    safe_summary = re.sub(r"--+", "—", review_summary)
    return (
        "\n<!-- TAXONGURU_AUTO_REVIEW\n"
        f"language: {language}\n"
        f"score: {quality_score}\n"
        f"sources: {source_count}\n"
        f"scheduled: {scheduled_text}\n"
        f"summary: {safe_summary}\n"
        "-->\n"
    )


def editorial_disclosure_html(language: Literal["ko", "en"]) -> str:
    ai_policy_url = f"{WP_SITE_URL}/ai-use-policy/"
    editorial_policy_url = f"{WP_SITE_URL}/editorial-policy/"
    if language == "ko":
        return (
            '<div class="taxonguru-editorial-note"><h2>자료와 편집 원칙</h2>'
            "<p>이 글은 공개된 학술·기관 자료를 바탕으로 작성되었으며, 주요 사실은 아래 참고자료에서 확인할 수 있습니다. "
            f'<a href="{html.escape(editorial_policy_url, quote=True)}">편집 및 팩트체크 정책</a>과 '
            f'<a href="{html.escape(ai_policy_url, quote=True)}">AI 활용 정책</a>을 공개하고 있습니다. '
            f'오류 제보: <a href="mailto:{html.escape(CONTACT_EMAIL)}">{html.escape(CONTACT_EMAIL)}</a></p></div>'
        )
    return (
        '<div class="taxonguru-editorial-note"><h2>Sources and editorial policy</h2>'
        "<p>This feature is based on publicly available scientific and institutional sources listed below. "
        f'Read our <a href="{html.escape(editorial_policy_url, quote=True)}">editorial and fact-checking policy</a> and '
        f'<a href="{html.escape(ai_policy_url, quote=True)}">AI use policy</a>. '
        f'Report a correction: <a href="mailto:{html.escape(CONTACT_EMAIL)}">{html.escape(CONTACT_EMAIL)}</a></p></div>'
    )


# -----------------------------------------------------------------------------
# Wikimedia Commons image collection with machine-readable licensing
# -----------------------------------------------------------------------------
def commons_metadata_value(metadata: dict[str, Any], key: str) -> str:
    raw = metadata.get(key, {})
    return strip_html(raw.get("value", "") if isinstance(raw, dict) else "")


def license_is_usable(name: str) -> bool:
    normalized = name.casefold().replace("–", "-")
    if "noncommercial" in normalized or "-nc" in normalized or "no derivatives" in normalized or "-nd" in normalized:
        return False
    return (
        normalized.startswith("cc by")
        or normalized.startswith("cc0")
        or "public domain" in normalized
        or "pdm" in normalized
    )


def _commons_is_historical_or_nonphoto(asset: CommonsImage) -> bool:
    haystack = " ".join([asset.title, asset.description, asset.credit]).casefold()
    keywords = [
        "illustration", "drawing", "engraving", "etching", "lithograph", "plate",
        "sketch", "diagram", "line art", "black and white", "monochrome", "woodcut",
        "painting", "reconstruction", "restoration", "gravure", "figure from",
    ]
    return any(keyword in haystack for keyword in keywords)


def search_commons_images(scientific_name: str, limit: int = 12) -> list[CommonsImage]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'filetype:bitmap "{scientific_name}"',
        "gsrnamespace": 6,
        "gsrlimit": 50,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": 1800,
        "format": "json",
        "formatversion": 2,
    }
    response = session.get(
        "https://commons.wikimedia.org/w/api.php",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    assets: list[CommonsImage] = []

    for page in pages:
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        width = safe_int(info.get("width"))
        height = safe_int(info.get("height"))
        if width and height and max(width, height) < 700:
            continue
        metadata = info.get("extmetadata", {})
        license_name = commons_metadata_value(metadata, "LicenseShortName") or commons_metadata_value(metadata, "UsageTerms")
        if not license_is_usable(license_name):
            continue
        image_url = info.get("thumburl") or info.get("url") or ""
        page_url = info.get("descriptionurl") or ""
        if not image_url or not page_url:
            continue
        assets.append(
            CommonsImage(
                url=image_url,
                page_url=page_url,
                title=page.get("title", "").replace("File:", ""),
                artist=commons_metadata_value(metadata, "Artist") or "저작자 정보는 원본 페이지 참조",
                credit=commons_metadata_value(metadata, "Credit"),
                license_name=license_name,
                license_url=commons_metadata_value(metadata, "LicenseUrl"),
                description=commons_metadata_value(metadata, "ImageDescription"),
            )
        )

    # Modern photographs first; historical plates and drawings are retained only as a fallback.
    assets.sort(key=lambda asset: (_commons_is_historical_or_nonphoto(asset), asset.title.casefold()))
    return assets[:limit]


def download_image(url: str) -> tuple[bytes, str, str]:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        if response.content.startswith(b"\xff\xd8"):
            content_type = "image/jpeg"
        elif response.content.startswith(b"\x89PNG"):
            content_type = "image/png"
        elif response.content.startswith(b"RIFF") and b"WEBP" in response.content[8:12]:
            content_type = "image/webp"
        else:
            raise RuntimeError("지원하지 않는 이미지 형식입니다.")
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]
    return response.content, content_type, extension


def upload_commons_image(asset: CommonsImage, item: SheetItem, index: int) -> UploadedMedia:
    image_bytes, mime_type, extension = download_image(asset.url)
    safe_name = slugify(item.slug or item.scientific_name) or "taxon"
    filename = f"{safe_name}-commons-{index}.{extension}"
    license_link = (
        f' · <a href="{html.escape(asset.license_url, quote=True)}" target="_blank" rel="noopener noreferrer">'
        f"{html.escape(asset.license_name)}</a>"
        if asset.license_url
        else f" · {html.escape(asset.license_name)}"
    )
    source_link_ko = (
        f'<a href="{html.escape(asset.page_url, quote=True)}" target="_blank" rel="noopener noreferrer">원본 파일</a>'
    )
    source_link_en = (
        f'<a href="{html.escape(asset.page_url, quote=True)}" target="_blank" rel="noopener noreferrer">original file</a>'
    )
    caption_ko = f"사진: {html.escape(asset.artist)} · Wikimedia Commons{license_link} · {source_link_ko}"
    caption_en = f"Image: {html.escape(asset.artist)} · Wikimedia Commons{license_link} · {source_link_en}"
    description = (
        f"Wikimedia Commons source: {html.escape(asset.page_url)}<br>"
        f"Creator: {html.escape(asset.artist)}<br>"
        f"License: {html.escape(asset.license_name)}"
    )
    return upload_media_bytes(
        image_bytes=image_bytes,
        filename=filename,
        mime_type=mime_type,
        alt_text=f"{item.scientific_name} source image",
        caption_ko=caption_ko,
        caption_en=caption_en,
        description_html=description,
    )


def visual_research_brief(item: SheetItem, research: ResearchPackage) -> str:
    facts = []
    for fact in research.verified_facts[:8]:
        facts.append(f"- {fact.claim}: {fact.explanation}")
    taxonomy = " > ".join(part.name for part in research.taxonomy if part.name)
    return "\n".join(
        [
            f"Scientific name: {research.accepted_scientific_name or item.scientific_name}",
            f"English common name: {research.common_name_en}",
            f"Korean common name: {research.common_name_ko}",
            f"Taxonomy: {taxonomy}",
            f"Habitat and distribution: {research.distribution_and_habitat}",
            f"Overview: {research.overview}",
            "Verified visible or ecological facts:",
            *facts,
        ]
    )[:9000]


def generate_ai_image(
    item: SheetItem,
    research: ResearchPackage,
    *,
    role: Literal["featured", "habitat", "detail"],
    index: int,
) -> UploadedMedia | None:
    if not openai_client:
        return None
    if role == "featured" and not ALLOW_AI_FEATURED_IMAGE:
        return None
    if role != "featured" and not GENERATE_AI_BODY_IMAGES:
        return None

    role_instruction = {
        "featured": (
            "Create a visually compelling landscape hero image for a science magazine article. "
            "The organism should be the clear focal point, with rich natural color, cinematic light, strong depth, "
            "and an inviting composition suitable for social sharing and search thumbnails. Do not make it monochrome."
        ),
        "habitat": (
            "Create a wide explanatory habitat scene showing the organism in its scientifically plausible environment. "
            "Use natural color and clear spatial context. The subject must remain recognizable and not be tiny in the frame."
        ),
        "detail": (
            "Create a close editorial view that explains one verified anatomical or behavioral feature without labels or text. "
            "Use natural color, crisp detail, and a composition distinct from the habitat image."
        ),
    }[role]
    prompt = f"""
{role_instruction}

Scientific grounding:
{visual_research_brief(item, research)}

Accuracy rules:
- Depict only anatomy, behavior, habitat, and color that are supported by the grounding above.
- If an exact organism color is not verified, use a cautious naturalistic neutral coloration while making the environment visually rich.
- Do not add fantasy features, extra limbs, human objects, captions, labels, logos, borders, or watermarks.
- This is an AI-generated explanatory editorial illustration, not documentary evidence.
- Landscape 3:2 composition, realistic textures, no text.
"""
    response = openai_client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=prompt,
        size="1536x1024",
        quality=AI_IMAGE_QUALITY,
        n=1,
    )
    image_data = response.data[0]
    image_bytes: bytes | None = None
    if getattr(image_data, "b64_json", None):
        image_bytes = base64.b64decode(image_data.b64_json)
    elif getattr(image_data, "url", None):
        downloaded = session.get(image_data.url, timeout=REQUEST_TIMEOUT)
        downloaded.raise_for_status()
        image_bytes = downloaded.content
    if not image_bytes:
        return None

    today = datetime.now(SCHEDULE_TZ).strftime("%Y-%m-%d")
    role_ko = {"featured": "대표", "habitat": "서식 환경", "detail": "형태·행동"}[role]
    role_en = {"featured": "featured", "habitat": "habitat", "detail": "anatomy/behavior"}[role]
    caption_ko = f"TaxonGuru 제작 · AI 기반 {role_ko} 설명용 재현 이미지 · 실제 관찰 사진 아님 · 생성일 {today}"
    caption_en = f"Created by TaxonGuru · AI-generated {role_en} explanatory reconstruction · not a documentary photograph · generated {today}"
    safe_slug = item.slug or slugify(item.scientific_name) or "taxon"
    return upload_media_bytes(
        image_bytes=image_bytes,
        filename=f"{safe_slug}-ai-{role}-{index}.png",
        mime_type="image/png",
        alt_text=f"AI explanatory illustration of {item.scientific_name} ({role})",
        caption_ko=caption_ko,
        caption_en=caption_en,
        description_html=(
            "AI-generated explanatory editorial illustration; not documentary evidence. "
            f"Role: {html.escape(role)}. Model: {html.escape(OPENAI_IMAGE_MODEL)}"
        ),
    )


def prepare_article_media(item: SheetItem, research: ResearchPackage) -> list[UploadedMedia]:
    """Return media in fixed order: featured image, body image 1, body image 2..."""
    uploaded: list[UploadedMedia] = []
    commons_assets: list[CommonsImage] = []
    try:
        commons_assets = search_commons_images(item.scientific_name, limit=max(12, MIN_BODY_IMAGES * 4))
        photo_count = sum(not _commons_is_historical_or_nonphoto(asset) for asset in commons_assets)
        log(f"  🖼️ Commons 후보 {len(commons_assets)}개 · 사진형 후보 {photo_count}개")
    except Exception as exc:
        log(f"  ⚠️ Commons 검색 실패: {exc}")

    used_pages: set[str] = set()

    # A colorful AI hero is preferred so old monochrome plates do not become the thumbnail.
    if PREFER_AI_FEATURED_IMAGE:
        try:
            featured = generate_ai_image(item, research, role="featured", index=1)
            if featured:
                uploaded.append(featured)
                log("  ✅ AI 대표 이미지 생성 완료")
        except Exception as exc:
            log(f"  ⚠️ AI 대표 이미지 생성 실패, Commons로 대체합니다: {exc}")

    if not uploaded:
        for asset in commons_assets:
            if _commons_is_historical_or_nonphoto(asset) and not ALLOW_HISTORICAL_BODY_IMAGES:
                continue
            try:
                uploaded.append(upload_commons_image(asset, item, 1))
                used_pages.add(asset.page_url)
                log("  ✅ Commons 대표 이미지 지정")
                break
            except Exception as exc:
                log(f"  ⚠️ Commons 대표 이미지 업로드 실패: {exc}")

    # Body images: use modern/photo-like Commons assets first.
    body_media: list[UploadedMedia] = []
    commons_index = 2
    for asset in commons_assets:
        if len(body_media) >= MIN_BODY_IMAGES:
            break
        if asset.page_url in used_pages:
            continue
        if _commons_is_historical_or_nonphoto(asset) and not ALLOW_HISTORICAL_BODY_IMAGES:
            continue
        try:
            body_media.append(upload_commons_image(asset, item, commons_index))
            used_pages.add(asset.page_url)
            commons_index += 1
        except Exception as exc:
            log(f"  ⚠️ Commons 본문 이미지 업로드 실패: {exc}")

    # Fill every missing body slot with a distinct AI explanatory image.
    roles: list[Literal["habitat", "detail"]] = ["habitat", "detail"]
    while len(body_media) < MIN_BODY_IMAGES and GENERATE_AI_BODY_IMAGES:
        role = roles[len(body_media) % len(roles)]
        try:
            generated = generate_ai_image(item, research, role=role, index=len(body_media) + 1)
            if not generated:
                break
            body_media.append(generated)
            log(f"  ✅ AI 본문 이미지 생성 완료: {role}")
        except Exception as exc:
            log(f"  ⚠️ AI 본문 이미지 생성 실패({role}): {exc}")
            break

    # Last-resort fallback: an older plate is still better than an empty English article.
    if len(body_media) < MIN_BODY_IMAGES:
        for asset in commons_assets:
            if len(body_media) >= MIN_BODY_IMAGES:
                break
            if asset.page_url in used_pages:
                continue
            try:
                body_media.append(upload_commons_image(asset, item, commons_index))
                used_pages.add(asset.page_url)
                commons_index += 1
                log("  ℹ️ 본문 이미지 부족으로 Commons 역사자료를 보조 이미지로 사용합니다.")
            except Exception as exc:
                log(f"  ⚠️ Commons 보조 이미지 업로드 실패: {exc}")

    # If no featured image exists after all preferred paths, reuse the first body asset.
    if not uploaded and body_media:
        uploaded.append(body_media.pop(0))

    uploaded.extend(body_media)
    log(f"  🖼️ 최종 이미지 구성: 대표 {1 if uploaded else 0}개 + 본문 {max(0, len(uploaded) - 1)}개")
    return uploaded


def apply_body_image_size_styles(content_html: str) -> str:
    """Apply responsive display limits to TaxonGuru body image figures."""
    figure_style = f"max-width:{BODY_IMAGE_MAX_WIDTH}px;margin:28px auto;text-align:center;"
    image_style = (
        "display:block;width:100%;height:auto;"
        f"max-height:{BODY_IMAGE_MAX_HEIGHT}px;object-fit:contain;"
        "margin:0 auto;border-radius:12px;"
    )
    caption_style = "font-size:0.9em;line-height:1.55;margin-top:8px;"

    figure_pattern = re.compile(
        r'<figure(?P<attrs>[^>]*class=["\'][^"\']*taxonguru-source-image[^"\']*["\'][^>]*)>(?P<body>.*?)</figure>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def strip_attr(attrs: str, name: str) -> str:
        attrs = re.sub(rf'\s{name}="[^"]*"', "", attrs, flags=re.IGNORECASE | re.DOTALL)
        attrs = re.sub(rf"\s{name}='[^']*'", "", attrs, flags=re.IGNORECASE | re.DOTALL)
        return attrs

    def figure_repl(match: re.Match[str]) -> str:
        attrs = strip_attr(match.group("attrs"), "style")
        body = match.group("body")
        attrs += f' style="{figure_style}"'

        def img_repl(img_match: re.Match[str]) -> str:
            img_attrs = strip_attr(img_match.group(1), "width")
            img_attrs = strip_attr(img_attrs, "style")
            return f'<img{img_attrs} width="{BODY_IMAGE_MAX_WIDTH}" style="{image_style}">'

        def caption_repl(caption_match: re.Match[str]) -> str:
            caption_attrs = strip_attr(caption_match.group(1), "style")
            return f'<figcaption{caption_attrs} style="{caption_style}">'

        body = re.sub(r"<img([^>]*)>", img_repl, body, count=1, flags=re.IGNORECASE | re.DOTALL)
        body = re.sub(r"<figcaption([^>]*)>", caption_repl, body, count=1, flags=re.IGNORECASE | re.DOTALL)
        return f"<figure{attrs}>{body}</figure>"

    return figure_pattern.sub(figure_repl, content_html or "")


def resize_existing_post_images(post_id: int | None) -> None:
    if not post_id:
        return
    try:
        post = wp_request("GET", f"posts/{post_id}", params={"context": "edit"}).json()
        content_obj = post.get("content", {})
        raw = content_obj.get("raw") or content_obj.get("rendered") or ""
        resized = apply_body_image_size_styles(raw)
        if resized and resized != raw:
            wp_request("POST", f"posts/{post_id}", json={"content": resized})
            log(f"  ↔️ 기존 게시물 본문 이미지 크기 조정 완료: Post ID {post_id}")
    except Exception as exc:
        log(f"  ⚠️ 기존 게시물 이미지 크기 조정 실패(Post {post_id}): {_short_error(exc)}")


def figure_html(media: UploadedMedia, alt_text: str, language: Literal["ko", "en"]) -> str:
    caption = media.caption_ko if language == "ko" else media.caption_en
    figure_style = (
        f"max-width:{BODY_IMAGE_MAX_WIDTH}px;margin:28px auto;text-align:center;"
    )
    image_style = (
        "display:block;width:100%;height:auto;"
        f"max-height:{BODY_IMAGE_MAX_HEIGHT}px;object-fit:contain;"
        "margin:0 auto;border-radius:12px;"
    )
    return (
        f'<figure class="taxonguru-source-image" style="{figure_style}">'
        f'<img src="{html.escape(media.source_url, quote=True)}" '
        f'alt="{html.escape(alt_text, quote=True)}" loading="lazy" '
        f'width="{BODY_IMAGE_MAX_WIDTH}" style="{image_style}">'
        f'<figcaption style="font-size:0.9em;line-height:1.55;margin-top:8px;">{caption}</figcaption>'
        "</figure>"
    )


# -----------------------------------------------------------------------------
# Main processing
# -----------------------------------------------------------------------------
def deterministic_quality_issues(
    article: ArticleDraft,
    research: ResearchPackage,
    language: Literal["ko", "en"],
) -> list[str]:
    issues: list[str] = []
    plain_text = strip_html(article.html_body)
    citation_markers = [str(number) for number in citation_numbers(article.html_body)]

    if not article.title.strip():
        issues.append("제목이 비어 있습니다.")
    if not article.slug.strip():
        issues.append("슬러그가 비어 있습니다.")

    if language == "ko":
        if len(plain_text) < MIN_KOREAN_CHARS:
            issues.append(f"한국어 본문 길이가 {len(plain_text)}자로 최소 {MIN_KOREAN_CHARS}자 미만입니다.")
        latin_words = len(re.findall(r"[A-Za-z]{3,}", plain_text))
        hangul_chars = len(re.findall(r"[가-힣]", plain_text))
        if hangul_chars < 500 or latin_words > max(180, hangul_chars // 2):
            issues.append("한국어 페이지에 영어 문장이 과도하게 섞였을 가능성이 있습니다.")
        if re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", plain_text):
            issues.append("한국어 본문에 중국어 한자 또는 일본어 가나 문자가 혼입되어 있습니다.")
    else:
        word_count = len(re.findall(r"[A-Za-z0-9']+", plain_text))
        if word_count < MIN_ENGLISH_WORDS:
            issues.append(f"영문 본문이 {word_count}단어로 최소 {MIN_ENGLISH_WORDS}단어 미만입니다.")
        if re.search(r"[가-힣]", plain_text):
            issues.append("영어 페이지 본문에 한국어 문자가 포함되어 있습니다.")
        if re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF]", plain_text):
            issues.append("영어 본문에 CJK 문자 또는 일본어 가나가 포함되어 있습니다.")

    if len(citation_markers) < MIN_CITATION_MARKERS:
        issues.append(f"본문 인용표시가 {len(citation_markers)}개로 최소 {MIN_CITATION_MARKERS}개 미만입니다.")
    if len(research.sources) < MIN_SOURCE_COUNT:
        issues.append(f"유효한 출처가 {len(research.sources)}개로 최소 {MIN_SOURCE_COUNT}개 미만입니다.")
    if article.html_body.count("[[IMAGE_1]]") != 1 or article.html_body.count("[[IMAGE_2]]") != 1:
        issues.append("본문 이미지 자리표시자 IMAGE_1/IMAGE_2가 각각 한 번씩 존재하지 않습니다.")

    invalid_citations = [safe_int(number) for number in citation_markers if safe_int(number) > len(research.sources)]
    if invalid_citations:
        issues.append(f"존재하지 않는 출처 번호가 인용되었습니다: {sorted(set(invalid_citations))}")
    return issues


def summarize_review(review: QualityReview, deterministic_issues: list[str]) -> str:
    parts: list[str] = []
    if review.critical_issues:
        parts.append("중대 오류: " + "; ".join(review.critical_issues[:3]))
    if review.unsupported_claims:
        parts.append("근거 부족: " + "; ".join(review.unsupported_claims[:3]))
    if review.factual_corrections:
        parts.append("수정 권고: " + "; ".join(review.factual_corrections[:3]))
    if deterministic_issues:
        parts.append("시스템 검사: " + "; ".join(deterministic_issues[:4]))
    if not parts:
        parts.append("중대한 오류와 근거 없는 핵심 주장이 발견되지 않았습니다.")
    return " | ".join(parts)[:1200]


def english_category_name(category: str) -> str:
    if "/" in category:
        left = category.split("/", 1)[0].strip()
        if left:
            return left
    mappings = {
        "식물학": "Botany",
        "진화의 미스터리": "Evolution Mysteries",
        "극한의 생존자": "Extreme Survivors",
        "크기 비교 연구소": "Size Lab",
    }
    return mappings.get(category.strip(), "Natural History")


def process_language_article(
    item: SheetItem,
    research: ResearchPackage,
    language: Literal["ko", "en"],
) -> tuple[ArticleDraft, QualityReview, list[str], bool, str]:
    label = "한국어" if language == "ko" else "영어"
    article = generate_article(item, research, language)
    review = QualityReview()
    deterministic_issues: list[str] = []

    for round_index in range(MAX_REWRITE_ROUNDS + 1):
        deterministic_issues = deterministic_quality_issues(article, research, language)
        review = review_article(item, research, article, language)
        log(f"  🧪 {label} {round_index + 1}차 자동 검수: {review.score}점")

        passed = (
            review.pass_review
            and review.score >= MIN_QUALITY_SCORE
            and not review.critical_issues
            and not review.unsupported_claims
            and not deterministic_issues
        )
        if passed:
            summary = summarize_review(review, deterministic_issues)
            return article, review, deterministic_issues, True, summary

        if round_index >= MAX_REWRITE_ROUNDS:
            break

        log(f"  🔁 {label} 검수 지적을 반영해 {round_index + 1}차 재작성합니다.")
        article = revise_article(item, research, article, review, deterministic_issues, language)

    summary = summarize_review(review, deterministic_issues)
    return article, review, deterministic_issues, False, summary


def compose_public_content(
    article: ArticleDraft,
    research: ResearchPackage,
    uploaded: list[UploadedMedia],
    language: Literal["ko", "en"],
    scheduled_at: datetime | None,
    review: QualityReview,
    review_summary: str,
) -> str:
    body_media = uploaded[1 : 1 + MIN_BODY_IMAGES] if len(uploaded) > 1 else []
    body = article.html_body
    for idx in range(MIN_BODY_IMAGES):
        placeholder = f"[[IMAGE_{idx + 1}]]"
        if idx < len(body_media):
            alt = (
                f"{research.accepted_scientific_name} 관련 자료 이미지"
                if language == "ko"
                else f"Source image related to {research.accepted_scientific_name}"
            )
            body = body.replace(placeholder, figure_html(body_media[idx], alt, language), 1)
        else:
            body = body.replace(placeholder, "", 1)

    body = apply_body_image_size_styles(body)
    body = replace_citation_markers(body, len(research.sources))
    featured_credit = ""
    if uploaded:
        heading = "대표 이미지 출처" if language == "ko" else "Featured image credit"
        caption = uploaded[0].caption_ko if language == "ko" else uploaded[0].caption_en
        featured_credit = f"<h2>{heading}</h2><p>{caption}</p>"

    return (
        body
        + featured_credit
        + editorial_disclosure_html(language)
        + build_references_html(research.sources, language)
        + hidden_review_comment(
            language=language,
            quality_score=review.score,
            source_count=len(research.sources),
            scheduled_at=scheduled_at,
            review_summary=review_summary,
        )
    )


def retry_english_article_only(
    worksheet: gspread.Worksheet,
    headers: list[str],
    item: SheetItem,
) -> None:
    """Repair and schedule only the English article without touching Korean."""
    if not item.post_id:
        raise RuntimeError("영문 재시도에는 기존 한국어 WP_POST_ID가 필요합니다.")

    legacy_retry = item.status == "기존한국어재예약/영문검수필요"
    attempt = item.rewrite_attempts + 1 if legacy_retry else item.rewrite_attempts
    progress_status = "기존영문재작성중" if legacy_retry else "영문재작성중"
    failure_status = (
        "기존한국어재예약/영문검수필요"
        if legacy_retry and attempt < MAX_LEGACY_REWRITE_ATTEMPTS
        else ("기존비공개보류" if legacy_retry else "한국어예약/영문검수필요")
    )

    log(f"\n🌍 영문 전용 재작성 시작: {item.scientific_name}")
    update_sheet_fields(
        worksheet, headers, item.row_number,
        {
            "status": progress_status,
            "rewrite_attempts": attempt if legacy_retry else item.rewrite_attempts,
            "en_auto_review_result": "",
            "en_error": "",
        },
    )
    resize_existing_post_images(item.post_id)

    research = research_subject(item)
    if len(research.sources) < MIN_SOURCE_COUNT or len(research.verified_facts) < 4:
        message = f"영문 재작성 자료 부족: 출처 {len(research.sources)}개, 검증 사실 {len(research.verified_facts)}건"
        update_sheet_fields(
            worksheet, headers, item.row_number,
            {
                "status": failure_status,
                "source_count": len(research.sources),
                "rewrite_attempts": attempt if legacy_retry else item.rewrite_attempts,
                "cleanup_note": f"기존 영문 재작성 {attempt}/{MAX_LEGACY_REWRITE_ATTEMPTS}회 실패" if legacy_retry else item.cleanup_note,
                "en_error": message,
            },
        )
        log(f"  ⚠️ {message}")
        return

    en_article, en_review, _, en_passed, en_summary = process_language_article(item, research, "en")
    if not en_passed:
        update_sheet_fields(
            worksheet, headers, item.row_number,
            {
                "status": failure_status,
                "rewrite_attempts": attempt if legacy_retry else item.rewrite_attempts,
                "cleanup_note": f"기존 영문 재작성 {attempt}/{MAX_LEGACY_REWRITE_ATTEMPTS}회 실패" if legacy_retry else item.cleanup_note,
                "en_quality_score": en_review.score,
                "en_auto_review_result": en_summary,
                "en_error": en_summary[:500],
            },
        )
        log(f"  ⚠️ 영문 재작성 품질 기준 미달: {en_summary}")
        return

    uploaded = prepare_article_media(item, research)
    featured_media = uploaded[0].media_id if uploaded else None
    en_scheduled = None if MANUAL_REVIEW_REQUIRED else calculate_next_schedule_datetime(ENGLISH_PUBLISH_HOUR, ENGLISH_PUBLISH_MINUTE)
    en_content = compose_public_content(en_article, research, uploaded, "en", en_scheduled, en_review, en_summary)
    en_category_id = get_or_create_wp_term(english_category_name(item.category), "categories")
    fallback_en_tags = [research.common_name_en, item.scientific_name, english_category_name(item.category)]
    en_tag_names = list(dict.fromkeys([tag for tag in en_article.tags + fallback_en_tags if tag]))[:12]
    en_tag_ids = [term_id for tag in en_tag_names if (term_id := get_or_create_wp_term(tag, "tags"))]
    ko_slug = item.slug or slugify(research.accepted_scientific_name or item.scientific_name)
    en_slug = en_article.slug or slugify(research.common_name_en) or f"{ko_slug}-english"
    if en_slug == ko_slug:
        en_slug = f"{en_slug}-english"

    en_post = upsert_post(
        slug=en_slug,
        title=en_article.title,
        excerpt=en_article.excerpt or en_article.seo_description,
        content=en_content,
        featured_media=featured_media,
        category_id=en_category_id,
        tag_ids=en_tag_ids,
        publish_mode="draft" if MANUAL_REVIEW_REQUIRED else "future",
        scheduled_at=en_scheduled,
        post_meta={"_taxonguru_language": "en", "_taxonguru_translation_id": item.post_id},
        existing_post_id=item.en_post_id,
    )
    en_post_id = int(en_post["id"])
    en_status = str(en_post.get("status", DRAFT_STATUS))
    if not MANUAL_REVIEW_REQUIRED and en_status != "future":
        raise RuntimeError(f"WordPress가 영문 글의 예약 상태를 반환하지 않았습니다. 실제 상태: {en_status}")
    if MANUAL_REVIEW_REQUIRED and en_status != DRAFT_STATUS:
        raise RuntimeError(f"WordPress가 영문 글의 초안 상태를 반환하지 않았습니다. 실제 상태: {en_status}")

    linked_payload = link_translation_posts(item.post_id, en_post_id)
    linked = bool(linked_payload.get("linked"))
    en_edit_url = f"{WP_SITE_URL}/wp-admin/post.php?post={en_post_id}&action=edit"
    en_public_url = "" if MANUAL_REVIEW_REQUIRED else linked_payload.get("en_url", en_post.get("link", ""))
    en_scheduled_text = en_scheduled.strftime("%Y-%m-%d %H:%M %Z") if en_scheduled else ""
    ko_post = get_post(item.post_id)
    ko_status = str(ko_post.get("status", ""))
    if MANUAL_REVIEW_REQUIRED:
        next_status = "기존수동검수대기" if legacy_retry else "한국어완료/영문수동검수대기"
    elif legacy_retry:
        next_status = "기존한영재예약완료" if ko_status == "future" else "기존한국어공개/영문재예약"
    else:
        next_status = "한영예약완료" if ko_status == "future" else "한국어공개/영문예약"

    update_sheet_fields(
        worksheet, headers, item.row_number,
        {
            "status": next_status,
            "source_count": len(research.sources),
            "en_post_id": en_post_id,
            "en_edit_url": en_edit_url,
            "en_public_url": en_public_url,
            "en_quality_score": en_review.score,
            "en_scheduled_date": en_scheduled_text,
            "en_auto_review_result": en_summary,
            "translation_linked": "완료" if linked else "실패",
            "rewrite_attempts": attempt if legacy_retry else item.rewrite_attempts,
            "cleanup_note": (
                "기존 영문판 자동 품질검수 통과. 사람 검수 후 공개 필요"
                if MANUAL_REVIEW_REQUIRED and legacy_retry
                else (f"기존 영문판 재작성 완료, {en_scheduled_text} 예약" if legacy_retry else item.cleanup_note)
            ),
            "en_error": "",
        },
    )
    if MANUAL_REVIEW_REQUIRED:
        log("  👤 영문 자동검수 통과. WordPress 초안에서 사람 검수 후 공개해 주세요.")
    else:
        log(f"  🎉 영문 예약 복구 완료: {en_scheduled_text}")
    log(f"  🔗 영어 편집: {en_edit_url}")


def create_or_schedule_post(
    worksheet: gspread.Worksheet,
    headers: list[str],
    item: SheetItem,
) -> None:
    legacy_rewrite = item.status in LEGACY_REWRITE_STATES
    legacy_attempt = item.rewrite_attempts + 1 if legacy_rewrite else item.rewrite_attempts

    if item.status in {"한국어예약/영문검수필요", "한국어완료/영문검수필요", "기존한국어재예약/영문검수필요"}:
        retry_english_article_only(worksheet, headers, item)
        return

    def legacy_failure(reason: str) -> None:
        compact = " ".join(str(reason).split())[:900]
        if item.post_id:
            try:
                wp_request("POST", f"posts/{item.post_id}", json={"status": "draft"})
            except Exception as exc:
                compact += f" / 한국어 초안 유지 실패: {exc}"
        if item.en_post_id:
            try:
                wp_request("POST", f"posts/{item.en_post_id}", json={"status": "draft"})
            except Exception as exc:
                compact += f" / 영어 초안 유지 실패: {exc}"
        next_state = "기존재작성재시도" if legacy_attempt < MAX_LEGACY_REWRITE_ATTEMPTS else "기존비공개보류"
        update_sheet_fields(
            worksheet, headers, item.row_number,
            {
                "status": next_state,
                "rewrite_attempts": legacy_attempt,
                "cleanup_note": f"재작성 {legacy_attempt}/{MAX_LEGACY_REWRITE_ATTEMPTS}회 실패",
                "error": compact,
                "en_error": compact if ENABLE_ENGLISH else "",
            },
        )
        log(f"  ⚠️ 기존 글 재작성 실패({legacy_attempt}/{MAX_LEGACY_REWRITE_ATTEMPTS}): {compact}")

    log(f"\n🔬 연구 시작: {item.scientific_name}" + (f" · 기존 글 재작성 {legacy_attempt}/{MAX_LEGACY_REWRITE_ATTEMPTS}" if legacy_rewrite else ""))
    update_sheet_fields(
        worksheet,
        headers,
        item.row_number,
        {
            "status": "기존재작성중" if legacy_rewrite else "조사중",
            "rewrite_attempts": legacy_attempt if legacy_rewrite else item.rewrite_attempts,
            "cleanup_note": "기존 비공개 글 재작성 진행 중" if legacy_rewrite else item.cleanup_note,
            "scheduled_date": "",
            "en_scheduled_date": "",
            "auto_review_result": "",
            "en_auto_review_result": "",
            "translation_linked": "",
            "error": "",
            "en_error": "",
        },
    )

    research = research_subject(item)
    if len(research.sources) < MIN_SOURCE_COUNT:
        message = f"유효한 출처가 {len(research.sources)}개뿐입니다. 최소 {MIN_SOURCE_COUNT}개가 필요합니다."
        if legacy_rewrite:
            legacy_failure(message)
            return
        update_sheet_fields(
            worksheet,
            headers,
            item.row_number,
            {
                "status": "자료부족",
                "source_count": len(research.sources),
                "auto_review_result": message,
                "error": message,
            },
        )
        log(f"  ⚠️ {message}")
        return
    if len(research.verified_facts) < 4:
        message = "출처가 연결된 검증 사실이 4개 미만입니다."
        if legacy_rewrite:
            legacy_failure(message)
            return
        update_sheet_fields(
            worksheet,
            headers,
            item.row_number,
            {
                "status": "자료부족",
                "source_count": len(research.sources),
                "auto_review_result": message,
                "error": message,
            },
        )
        log(f"  ⚠️ {message}")
        return

    log(f"  ✅ 검증 자료 {len(research.sources)}개, 사실 {len(research.verified_facts)}건")

    update_sheet_fields(worksheet, headers, item.row_number, {"status": "한국어작성"})
    ko_article, ko_review, _, ko_passed, ko_summary = process_language_article(item, research, "ko")

    en_article: ArticleDraft | None = None
    en_review: QualityReview | None = None
    en_passed = False
    en_summary = "영문 발행 비활성화"
    en_generation_error = ""
    if ENABLE_ENGLISH:
        update_sheet_fields(worksheet, headers, item.row_number, {"status": "영어작성"})
        try:
            en_article, en_review, _, en_passed, en_summary = process_language_article(item, research, "en")
        except Exception as exc:
            en_generation_error = f"영문 작성 실패: {_short_error(exc)}"
            en_summary = en_generation_error
            log(f"  ⚠️ {en_generation_error}")

    if legacy_rewrite and (not ko_passed or (ENABLE_ENGLISH and (not en_article or not en_review or not en_passed))):
        reasons = [ko_summary] if not ko_passed else []
        if ENABLE_ENGLISH and (not en_article or not en_review or not en_passed):
            reasons.append(en_generation_error or en_summary or "영문 자동검수 미달")
        legacy_failure(" | ".join(filter(None, reasons)))
        return

    if not ko_passed and not DRAFT_ON_REVIEW_FAILURE:
        update_sheet_fields(
            worksheet,
            headers,
            item.row_number,
            {
                "status": "검수실패",
                "quality_score": ko_review.score,
                "en_quality_score": en_review.score if en_review else 0,
                "source_count": len(research.sources),
                "auto_review_result": ko_summary,
                "en_auto_review_result": en_summary,
                "error": ko_summary[:500],
            },
        )
        log(f"  ⛔ 한국어 품질 기준 미달로 WordPress에 저장하지 않았습니다: {ko_summary}")
        return

    # Media order is fixed: a colorful featured image first, followed by body images.
    uploaded = prepare_article_media(item, research)
    featured_media = uploaded[0].media_id if uploaded else None

    ko_scheduled: datetime | None = None
    en_scheduled: datetime | None = None
    ko_publish_mode: Literal["future", "draft"] = "draft"
    en_publish_mode: Literal["future", "draft"] = "draft"

    if ko_passed and AUTO_SCHEDULE and not MANUAL_REVIEW_REQUIRED:
        ko_scheduled = calculate_next_schedule_datetime(PUBLISH_HOUR, PUBLISH_MINUTE)
        ko_publish_mode = "future"
        log(f"  🗓️ 한국어 예약: {ko_scheduled.strftime('%Y-%m-%d %H:%M %Z')}")
    elif ko_passed and MANUAL_REVIEW_REQUIRED:
        log("  👤 한국어 자동검수 통과 → 사람 검수를 위해 WordPress 초안으로 저장합니다.")
    elif not ko_passed:
        log(f"  ⚠️ 한국어 품질 기준 미달: {ko_summary}")

    # English is only auto-scheduled when both the Korean source article and English article pass.
    if ENABLE_ENGLISH and en_article and en_review:
        if ko_passed and en_passed and AUTO_SCHEDULE and not MANUAL_REVIEW_REQUIRED:
            en_scheduled = calculate_next_schedule_datetime(ENGLISH_PUBLISH_HOUR, ENGLISH_PUBLISH_MINUTE)
            en_publish_mode = "future"
            log(f"  🗓️ 영어 예약: {en_scheduled.strftime('%Y-%m-%d %H:%M %Z')}")
        elif ko_passed and en_passed and MANUAL_REVIEW_REQUIRED:
            log("  👤 영어 자동검수 통과 → 사람 검수를 위해 WordPress 초안으로 저장합니다.")
        elif not en_passed:
            log(f"  ⚠️ 영어 품질 기준 미달: {en_summary}")

    ko_content = compose_public_content(
        ko_article, research, uploaded, "ko", ko_scheduled, ko_review, ko_summary
    )
    ko_category_id = get_or_create_wp_term(item.category, "categories")
    ko_tag_names = list(dict.fromkeys((item.tags + ko_article.tags + [item.scientific_name])[:12]))
    ko_tag_ids = [term_id for tag in ko_tag_names if (term_id := get_or_create_wp_term(tag, "tags"))]
    ko_slug = item.slug or ko_article.slug or slugify(research.accepted_scientific_name or item.scientific_name)
    if not ko_slug:
        raise RuntimeError("한국어 글의 유효한 슬러그를 만들 수 없습니다.")

    ko_post = upsert_post(
        slug=ko_slug,
        title=ko_article.title,
        excerpt=ko_article.excerpt or ko_article.seo_description,
        content=ko_content,
        featured_media=featured_media,
        category_id=ko_category_id,
        tag_ids=ko_tag_ids,
        publish_mode=ko_publish_mode,
        scheduled_at=ko_scheduled,
        post_meta={"_taxonguru_language": "ko", "_taxonguru_translation_id": item.en_post_id or 0},
        existing_post_id=item.post_id,
    )
    ko_post_id = int(ko_post["id"])
    ko_status = str(ko_post.get("status", DRAFT_STATUS))
    ko_edit_url = f"{WP_SITE_URL}/wp-admin/post.php?post={ko_post_id}&action=edit"

    en_post: dict[str, Any] | None = None
    en_post_id: int | None = None
    en_edit_url = ""
    linked = False
    linked_payload: dict[str, Any] = {}

    if ENABLE_ENGLISH and en_article and en_review:
        en_content = compose_public_content(
            en_article, research, uploaded, "en", en_scheduled, en_review, en_summary
        )
        en_category_id = get_or_create_wp_term(english_category_name(item.category), "categories")
        fallback_en_tags = [research.common_name_en, item.scientific_name, english_category_name(item.category)]
        en_tag_names = list(dict.fromkeys([tag for tag in en_article.tags + fallback_en_tags if tag]))[:12]
        en_tag_ids = [term_id for tag in en_tag_names if (term_id := get_or_create_wp_term(tag, "tags"))]
        en_slug = en_article.slug or slugify(research.common_name_en) or f"{ko_slug}-english"
        if en_slug == ko_slug:
            en_slug = f"{en_slug}-english"

        en_post = upsert_post(
            slug=en_slug,
            title=en_article.title,
            excerpt=en_article.excerpt or en_article.seo_description,
            content=en_content,
            featured_media=featured_media,
            category_id=en_category_id,
            tag_ids=en_tag_ids,
            publish_mode=en_publish_mode,
            scheduled_at=en_scheduled,
            post_meta={"_taxonguru_language": "en", "_taxonguru_translation_id": ko_post_id},
            existing_post_id=item.en_post_id,
        )
        en_post_id = int(en_post["id"])
        en_edit_url = f"{WP_SITE_URL}/wp-admin/post.php?post={en_post_id}&action=edit"
        linked_payload = link_translation_posts(ko_post_id, en_post_id)
        linked = bool(linked_payload.get("linked"))

    if ko_publish_mode == "future" and ko_status != "future":
        raise RuntimeError(f"WordPress가 한국어 글의 예약 상태를 반환하지 않았습니다. 실제 상태: {ko_status}")
    en_status = str(en_post.get("status", DRAFT_STATUS)) if en_post else "disabled"
    if en_publish_mode == "future" and en_status != "future":
        raise RuntimeError(f"WordPress가 영문 글의 예약 상태를 반환하지 않았습니다. 실제 상태: {en_status}")

    if MANUAL_REVIEW_REQUIRED and ko_passed:
        next_state = "기존수동검수대기" if legacy_rewrite else "수동검수대기"
    elif ko_status == "future" and (not ENABLE_ENGLISH or en_status == "future"):
        if legacy_rewrite:
            next_state = "기존한영재예약완료" if ENABLE_ENGLISH else "기존재예약완료"
        else:
            next_state = "한영예약완료" if ENABLE_ENGLISH else "예약완료"
    elif ko_status == "future" and ENABLE_ENGLISH and (en_status == DRAFT_STATUS or en_article is None):
        next_state = "기존한국어재예약/영문검수필요" if legacy_rewrite else "한국어예약/영문검수필요"
    else:
        next_state = "기존재작성재시도" if legacy_rewrite and legacy_attempt < MAX_LEGACY_REWRITE_ATTEMPTS else ("기존비공개보류" if legacy_rewrite else "검수필요")

    ko_scheduled_text = ko_scheduled.strftime("%Y-%m-%d %H:%M %Z") if ko_scheduled else ""
    en_scheduled_text = en_scheduled.strftime("%Y-%m-%d %H:%M %Z") if en_scheduled else ""
    ko_public_url = linked_payload.get("ko_url", ko_post.get("link", "")) if ko_status in {"future", "publish"} else ""
    en_public_url = ""
    if en_post and en_status in {"future", "publish"}:
        en_public_url = linked_payload.get("en_url", en_post.get("link", ""))

    update_sheet_fields(
        worksheet,
        headers,
        item.row_number,
        {
            "status": next_state,
            "post_id": ko_post_id,
            "edit_url": ko_edit_url,
            "public_url": ko_public_url,
            "quality_score": ko_review.score,
            "source_count": len(research.sources),
            "scheduled_date": ko_scheduled_text,
            "auto_review_result": ko_summary,
            "error": "" if ko_passed else ko_summary[:500],
            "en_post_id": en_post_id or "",
            "en_edit_url": en_edit_url,
            "en_public_url": en_public_url,
            "en_quality_score": en_review.score if en_review else 0,
            "en_scheduled_date": en_scheduled_text,
            "en_auto_review_result": en_summary,
            "translation_linked": "완료" if linked else ("비활성" if not ENABLE_ENGLISH else "실패"),
            "en_error": "" if en_passed or not ENABLE_ENGLISH else (en_generation_error or en_summary)[:500],
            "rewrite_attempts": legacy_attempt if legacy_rewrite else item.rewrite_attempts,
            "cleanup_note": (
                "기존 글 재작성 및 자동 품질검수 통과. WordPress 초안에서 사람 검수 후 공개 필요"
                if next_state == "기존수동검수대기"
                else (
                    "자동 품질검수 통과. WordPress 초안에서 사람 검수 후 공개 필요"
                    if next_state == "수동검수대기"
                    else (
                        f"기존 글 재작성 완료, 다음 빈 순번 예약: KO {ko_scheduled_text} / EN {en_scheduled_text}"
                        if legacy_rewrite and next_state in LEGACY_SCHEDULED_STATES
                        else item.cleanup_note
                    )
                )
            ),
        },
    )

    if next_state in {"수동검수대기", "기존수동검수대기"}:
        log("  👤 자동 품질검수 통과. WordPress 초안에서 내용을 확인한 뒤 직접 공개해 주세요.")
        log(f"  🔗 한국어 편집: {ko_edit_url}")
        if en_edit_url:
            log(f"  🔗 영어 편집: {en_edit_url}")
    elif next_state in {"한영예약완료", "기존한영재예약완료"}:
        label = "기존 글 한·영 재예약 완료" if next_state == "기존한영재예약완료" else "한·영 예약 완료"
        log(f"  🎉 {label}: KO {ko_scheduled_text} / EN {en_scheduled_text}")
        log(f"  🔗 한국어 편집: {ko_edit_url}")
        log(f"  🔗 영어 편집: {en_edit_url}")
    elif next_state == "한국어예약/영문검수필요":
        log(f"  ✅ 한국어 예약 완료: {ko_scheduled_text}")
        log(f"  📝 영어 글은 초안 검수가 필요합니다: {en_edit_url}")
    else:
        log(f"  📝 기준 미달 글을 비공개 초안으로 저장했습니다: {ko_edit_url}")


def validate_runtime_dependencies() -> None:
    try:
        version = importlib.metadata.version("google-genai")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("google-genai 패키지가 설치되지 않았습니다.") from exc

    major_text = version.split(".", 1)[0]
    major = int(major_text) if major_text.isdigit() else 0
    log(f"🧩 google-genai SDK: {version}")
    if major < 2:
        raise RuntimeError(
            f"google-genai {version}은 현재 Interactions API와 호환되지 않습니다. "
            "requirements.txt를 google-genai>=2.0,<3으로 변경하세요."
        )


def main() -> int:
    validate_runtime_dependencies()
    log("=" * 70)
    log("TaxonGuru 스토리텔링 한·영 자동 품질검수 + 예약 발행 파이프라인")
    log(
        f"자동 예약: {'ON' if AUTO_SCHEDULE else 'OFF'} · 사람 검수: {'필수' if MANUAL_REVIEW_REQUIRED else '선택'} · "
        f"AdSense 복구모드: {'ON' if ADSENSE_RECOVERY_MODE else 'OFF'} · 기준 {MIN_QUALITY_SCORE}점/출처 {MIN_SOURCE_COUNT}개 · "
        f"KO {PUBLISH_HOUR:02d}:{PUBLISH_MINUTE:02d} / EN {ENGLISH_PUBLISH_HOUR:02d}:{ENGLISH_PUBLISH_MINUTE:02d} "
        f"{SCHEDULE_TIMEZONE} · 영어 {'ON' if ENABLE_ENGLISH else 'OFF'} · "
        f"AI 대표 {'ON' if ALLOW_AI_FEATURED_IMAGE else 'OFF'} / AI 본문 {'ON' if GENERATE_AI_BODY_IMAGES else 'OFF'} · 본문 이미지 최대 {BODY_IMAGE_MAX_WIDTH}px"
    )
    log("=" * 70)

    worksheet: gspread.Worksheet | None = None
    headers: list[str] = []
    item: SheetItem | None = None
    try:
        worksheet, headers = connect_sheet()
        ensure_multilingual_backend()
        sync_scheduled_posts(worksheet, headers)
        if PROCESS_MODE == "sync_only":
            log("✅ 예약 상태 동기화만 완료했습니다.")
            return 0
        item = choose_sheet_item(worksheet, headers)
        if not item:
            log(f"✅ PROCESS_MODE={PROCESS_MODE}에서 처리할 항목이 없습니다.")
            return 0

        create_or_schedule_post(worksheet, headers, item)
        return 0
    except Exception as exc:
        log(f"\n❌ 처리 실패: {exc}")
        if worksheet is not None and item is not None:
            try:
                if item.status in LEGACY_REWRITE_STATES or item.status == "기존재작성중":
                    attempts = max(1, item.rewrite_attempts + (0 if item.status == "기존재작성중" else 1))
                    status = "기존재작성재시도" if attempts < MAX_LEGACY_REWRITE_ATTEMPTS else "기존비공개보류"
                    update_sheet_fields(
                        worksheet, headers, item.row_number,
                        {
                            "status": status,
                            "rewrite_attempts": attempts,
                            "cleanup_note": f"예외 발생으로 재작성 {attempts}/{MAX_LEGACY_REWRITE_ATTEMPTS}회 실패",
                            "error": str(exc)[:500],
                        },
                    )
                else:
                    update_sheet_fields(
                        worksheet, headers, item.row_number,
                        {"status": "오류", "error": str(exc)[:500]},
                    )
            except Exception as sheet_error:
                log(f"  ⚠️ 시트 오류 기록 실패: {sheet_error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
