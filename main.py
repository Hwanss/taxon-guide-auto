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
from typing import Any, Literal
from zoneinfo import ZoneInfo
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import bleach
import gspread
import requests
from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", category=FutureWarning)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
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
ALLOW_AI_FEATURED_IMAGE = os.getenv("ALLOW_AI_FEATURED_IMAGE", "false").lower() == "true"
AUTO_SCHEDULE = os.getenv("AUTO_SCHEDULE", "true").lower() == "true"
DRAFT_ON_REVIEW_FAILURE = os.getenv("DRAFT_ON_REVIEW_FAILURE", "true").lower() == "true"
DRAFT_STATUS = os.getenv("WP_DRAFT_STATUS", "draft")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "45"))

SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE", "Asia/Seoul")
PUBLISH_HOUR = int(os.getenv("PUBLISH_HOUR", "9"))
PUBLISH_MINUTE = int(os.getenv("PUBLISH_MINUTE", "30"))
ENGLISH_PUBLISH_HOUR = int(os.getenv("ENGLISH_PUBLISH_HOUR", "18"))
ENGLISH_PUBLISH_MINUTE = int(os.getenv("ENGLISH_PUBLISH_MINUTE", "30"))
SCHEDULE_AFTER_DAYS = int(os.getenv("SCHEDULE_AFTER_DAYS", "1"))
SCHEDULE_INTERVAL_DAYS = int(os.getenv("SCHEDULE_INTERVAL_DAYS", "1"))
MAX_SCHEDULE_LOOKAHEAD_DAYS = int(os.getenv("MAX_SCHEDULE_LOOKAHEAD_DAYS", "120"))
MIN_SCHEDULE_LEAD_MINUTES = int(os.getenv("MIN_SCHEDULE_LEAD_MINUTES", "30"))
SCHEDULE_TZ = ZoneInfo(SCHEDULE_TIMEZONE)

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


def gemini_structured(
    model: str,
    prompt: str,
    schema: type[BaseModel],
    tools_list: list[str] | None = None,
) -> BaseModel:
    """Use the current Interactions API; fall back to generateContent if needed."""
    tools_list = tools_list or []
    try:
        interaction_kwargs: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema.model_json_schema(),
            },
        }
        if tools_list:
            interaction_kwargs["tools"] = [{"type": tool_name} for tool_name in tools_list]
        interaction = gemini_client.interactions.create(**interaction_kwargs)
        return schema.model_validate_json(interaction.output_text)
    except Exception as interaction_error:
        log(f"  ⚠️ Interactions API 재시도: {interaction_error}")
        fallback_tools = []
        if "google_search" in tools_list:
            fallback_tools.append(types.Tool(google_search=types.GoogleSearch()))
        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if fallback_tools:
            config_kwargs["tools"] = fallback_tools
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return schema.model_validate_json(response.text)


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
    )


def choose_sheet_item(worksheet: gspread.Worksheet, headers: list[str]) -> SheetItem | None:
    rows = worksheet.get_all_values()[1:]
    items = [parse_sheet_item(i + 2, row, headers) for i, row in enumerate(rows)]

    # 하루에 한 건씩 처리합니다. 예약 슬롯은 WordPress의 기존 예약글과 충돌하지 않게 자동 계산합니다.
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


def ensure_multilingual_backend() -> None:
    if not ENABLE_ENGLISH:
        return
    if MULTILINGUAL_BACKEND != "taxonguru_bridge":
        raise RuntimeError(
            "현재 패키지는 MULTILINGUAL_BACKEND=taxonguru_bridge를 지원합니다. "
            "동봉된 TaxonGuru Multilingual Bridge 플러그인을 설치·활성화하세요."
        )
    try:
        payload = wp_root_request("GET", "taxonguru/v1/status").json()
    except Exception as exc:
        raise RuntimeError(
            "영문 /en/ URL과 hreflang 연결에 필요한 'TaxonGuru Multilingual Bridge' 플러그인이 "
            "설치 또는 활성화되지 않았습니다. wordpress-plugin/taxonguru-multilingual-bridge.zip을 "
            "워드프레스 플러그인에서 설치한 뒤 다시 실행하세요."
        ) from exc
    if not payload.get("active"):
        raise RuntimeError("TaxonGuru Multilingual Bridge 플러그인 상태를 확인할 수 없습니다.")
    log(f"🌐 다국어 브리지 확인: {payload.get('version', 'unknown')} · {payload.get('english_base', '')}")


def link_translation_posts(ko_post_id: int, en_post_id: int) -> dict[str, Any]:
    response = wp_root_request(
        "POST",
        "taxonguru/v1/link-translations",
        json={"ko_post_id": ko_post_id, "en_post_id": en_post_id},
    )
    return response.json()


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
) -> dict[str, Any]:
    existing = find_post_by_slug(slug)
    if existing and existing.get("status") == "publish":
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
    """Reflect Korean and English future→publish transitions back into Google Sheets."""
    rows = worksheet.get_all_values()[1:]
    for index, row in enumerate(rows, start=2):
        item = parse_sheet_item(index, row, headers)
        if "예약" not in item.status and item.status not in {"완료", "한국어공개/영문예약"}:
            continue
        if not item.post_id:
            continue

        try:
            ko_post = get_post(item.post_id)
            ko_status = str(ko_post.get("status", ""))
            en_post = get_post(item.en_post_id) if item.en_post_id else None
            en_status = str(en_post.get("status", "")) if en_post else "disabled"

            fields: dict[str, Any] = {}
            if ko_status == "publish":
                fields["public_url"] = ko_post.get("link", "")
            elif ko_status == "future":
                scheduled = parse_wp_local_datetime(str(ko_post.get("date", "")))
                if scheduled:
                    fields["scheduled_date"] = scheduled.strftime("%Y-%m-%d %H:%M %Z")
            elif ko_status == "draft":
                fields.update({"status": "검수필요", "error": "한국어 예약글이 초안 상태로 변경되었습니다."})

            if en_post:
                if en_status == "publish":
                    fields["en_public_url"] = en_post.get("link", "")
                elif en_status == "future":
                    en_scheduled = parse_wp_local_datetime(str(en_post.get("date", "")))
                    if en_scheduled:
                        fields["en_scheduled_date"] = en_scheduled.strftime("%Y-%m-%d %H:%M %Z")
                elif en_status == "draft" and ko_status == "publish":
                    fields.update({"status": "한국어완료/영문검수필요", "en_error": "영문 예약글이 초안 상태로 변경되었습니다."})

            if ko_status == "publish" and (not ENABLE_ENGLISH or en_status == "publish"):
                fields.update({"status": "완료", "error": "", "en_error": ""})
            elif ko_status == "publish" and en_status == "future":
                fields["status"] = "한국어공개/영문예약"

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
            normalized = normalize_url(source.url)
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
                url = normalize_url(str(_obj_value(annotation, "url", "")))
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

    result = gemini_structured(RESEARCH_MODEL, prompt, ResearchPackage)
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
        normalized = normalize_url(source.url)
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
            "극한 환경의 한 장면에서 시작해 생물이 맞닥뜨리는 문제와 생존 해법을 따라가는 자연 다큐멘터리형"
            if language == "ko"
            else "a cinematic survival narrative that begins inside the animal's extreme habitat and follows the problems it must solve"
        )
    if "evolution mysteries" in category_key or "진화의 미스터리" in category:
        return (
            "널리 알려진 주장이나 오해를 먼저 제시하고 증거를 하나씩 확인하는 과학 탐정형"
            if language == "ko"
            else "a science-detective story that opens with a popular claim, then tests it against evidence step by step"
        )
    if "size lab" in category_key or "크기 비교" in category:
        return (
            "숫자를 사람·자동차·건물·익숙한 동물과 비교해 실제 크기를 상상하게 만드는 실험형"
            if language == "ko"
            else "a scale-comparison feature that turns measurements into vivid comparisons with people, vehicles, buildings, or familiar animals"
        )
    if "botany" in category_key or "식물학" in category:
        return (
            "서식지의 풍경과 계절감에서 출발해 형태·번식·생존전략을 관찰하는 자연 에세이형"
            if language == "ko"
            else "a field-note style botanical essay that begins with place and season, then reveals form, reproduction, and survival strategy"
        )
    return "친근한 과학 교양 스토리텔링형" if language == "ko" else "an engaging popular-science narrative"


def generate_article(
    item: SheetItem,
    research: ResearchPackage,
    language: Literal["ko", "en"],
) -> ArticleDraft:
    style = story_style_for(item.category, language)
    if language == "ko":
        prompt = f"""
당신은 TaxonGuru 편집팀의 과학 스토리텔러다. 아래 검증 자료만 사용해 정확하면서도 끝까지 읽고 싶은 한국어 기사를 작성하라.

이번 글의 서술 방식
- {style}
- 유명 과학 교양 블로그처럼 자연스럽고 개성 있게 쓰되 실제 인물의 문체를 모방하거나 전문가를 사칭하지 않는다.

주제 정보
- 학명: {item.scientific_name}
- 제목 후보: {item.display_title}
- 핵심 질문/관점: {item.story_angle}
- 카테고리: {item.category}

검증된 연구 패키지
{research.model_dump_json(indent=2)}

작성 규칙
1. 한국어만 작성한다. 같은 페이지에 영어 번역을 넣지 않는다.
2. 보고서나 백과사전처럼 시작하지 말고, 장면·질문·의외의 사실 중 하나로 시작한다.
3. 첫 문장에서 모든 결론을 요약하지 않는다. 독자의 궁금증을 조금씩 풀어간다.
4. 문단은 2~4문장으로 짧게 구성하고 짧은 문장과 긴 문장을 섞는다.
5. 전문용어는 쉬운 설명을 먼저 제시한 뒤 괄호 안에 표기한다.
6. 적절한 비유와 가벼운 재치를 사용하되 억지 농담, 유행어, 과도한 감탄사는 피한다.
7. '대박', '충격', '소름', 근거 없는 '세계 최고' 표현은 사용하지 않는다.
8. '핵심 요약' 같은 고정 구성을 매번 반복하지 않는다. 주제에 맞게 4~7개의 자연스러운 소제목을 만든다.
9. 분류표가 필요하면 독자가 생물에 흥미를 느낀 뒤 배치한다.
10. 주요 사실 뒤에는 연구 패키지의 출처 번호를 [1], [2] 형식으로 표시한다.
11. 논쟁 중인 내용은 확정 사실처럼 쓰지 않고, 확인된 부분과 불확실한 부분을 구분한다.
12. 직접 비교나 해석은 사실과 구분되도록 자연스럽게 표현한다.
13. [[IMAGE_1]], [[IMAGE_2]]를 각각 정확히 한 번 넣는다.
14. 참고문헌, 이미지 라이선스, 자동검수 점수, 예약시간, AI 사용 안내는 본문에 작성하지 않는다.
15. 순수 본문 기준 3,000~4,800자 정도로 작성한다. 반복으로 분량을 채우지 않는다.
16. 마지막은 도입부의 장면이나 질문으로 돌아가 여운 있게 끝낸다.
17. title은 자연스럽고 구체적으로, slug는 짧은 영문 소문자 하이픈 형식으로 작성한다.
18. tags는 한국어·영어 핵심 검색어를 합쳐 6~10개 제안한다.
19. html_body는 script, style, iframe, form 없이 순수 본문 HTML만 반환한다.
"""
    else:
        prompt = f"""
You are the science storyteller for TaxonGuru. Write an original English feature using only the verified research package below.
Do not translate the Korean title or imitate any real writer. Rebuild the story for curious international readers in natural, polished English.

Narrative approach
- {style}
- Aim for the warmth and momentum of a strong popular-science blog: vivid, clear, lightly witty, and trustworthy.

Topic
- Scientific name: {item.scientific_name}
- Korean working-title context: {item.display_title}
- Central question/angle: {item.story_angle}
- Category: {item.category}

Verified research package
{research.model_dump_json(indent=2)}

Writing rules
1. Write only in English. Do not include Korean text or a side-by-side translation.
2. Open with a scene, question, or surprising fact—not a dictionary definition or summary list.
3. Reveal the answer progressively instead of giving every conclusion in the first paragraph.
4. Keep paragraphs compact, usually two to four sentences, and vary sentence rhythm.
5. Explain technical terms in plain language before using the formal term.
6. Use vivid comparisons and restrained humor, but avoid clickbait, memes, hype, or forced jokes.
7. Do not use phrases such as "mind-blowing," "shocking," or unsupported superlatives.
8. Do not repeat a fixed template. Create four to seven topic-specific section headings.
9. Place taxonomy after the reader has become interested, not as the opening block.
10. Attach source markers such as [1] and [2] to every important factual claim.
11. Separate confirmed evidence from disputed or uncertain claims.
12. Use both metric and familiar imperial equivalents when a measurement matters to international readers.
13. Insert [[IMAGE_1]] and [[IMAGE_2]] exactly once each.
14. Do not write the references, image license section, automated review score, scheduling details, or AI disclosure inside the article body.
15. Target 1,000–1,500 substantive English words without padding or repetition.
16. End by returning to the opening image or question.
17. title should be natural and search-friendly; slug must be concise lowercase ASCII words separated by hyphens.
18. tags should contain 6–10 useful English search terms.
19. html_body must contain clean body HTML only, with no script, style, iframe, or form elements.
"""

    result = gemini_structured(WRITER_MODEL, prompt, ArticleDraft)
    assert isinstance(result, ArticleDraft)
    result.html_body = sanitize_html(result.html_body)
    result.slug = slugify(result.slug or result.title)
    result.tags = [tag.strip() for tag in result.tags if tag.strip()][:12]
    return result


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
- 연구 패키지에 없는 사실·수치·인과관계를 만들지 않았는가
- 모든 주요 사실에 올바른 출처 번호가 있는가
- 분류학적 오류나 논쟁 중인 내용을 확정 사실로 표현한 문제가 없는가
- 문체가 보고서처럼 딱딱하거나 고정 템플릿을 반복하지 않는가
- 도입부가 장면·질문·반전으로 독자의 관심을 끄는가
- 문단 리듬, 쉬운 설명, 절제된 유머가 자연스러운가
- 클릭베이트, 가상 전문가 행세, 번역투가 없는가
- 제목과 본문이 일치하고 독자에게 고유한 해설이 있는가
- {language_name} 페이지에 다른 언어 문장이 불필요하게 섞이지 않았는가

통과 조건
- 중대한 사실 오류 0건
- 근거 없는 핵심 주장 0건
- 점수 {MIN_QUALITY_SCORE}점 이상

연구 패키지
{research.model_dump_json(indent=2)}

초안
{article.model_dump_json(indent=2)}
"""
    result = gemini_structured(REVIEW_MODEL, prompt, QualityReview)
    assert isinstance(result, QualityReview)
    result.score = max(0, min(100, result.score))
    return result


def revise_article(
    item: SheetItem,
    research: ResearchPackage,
    article: ArticleDraft,
    review: QualityReview,
    deterministic_issues: list[str],
    language: Literal["ko", "en"],
) -> ArticleDraft:
    plain_text = strip_html(article.html_body)
    current_measure = len(plain_text) if language == "ko" else len(re.findall(r"[A-Za-z0-9']+", plain_text))
    target_text = (
        f"현재 {current_measure}자, 최소 {MIN_KOREAN_CHARS}자, 목표 3,000~4,800자"
        if language == "ko"
        else f"currently {current_measure} words, minimum {MIN_ENGLISH_WORDS} words, target 1,000–1,500 words"
    )
    language_instruction = (
        "한국어 단일 언어로, 장면형 도입과 자연스러운 과학 블로그 문체를 유지한다."
        if language == "ko"
        else "Write English only, rebuild awkward translated phrasing, and preserve a lively popular-science voice."
    )
    prompt = f"""
아래 AI 검수와 시스템 검사 지적을 모두 반영해 기사를 다시 작성하라. 연구 패키지 밖의 사실은 추가하지 않는다.
- 언어 규칙: {language_instruction}
- 분량: {target_text}
- 출처 번호와 [[IMAGE_1]], [[IMAGE_2]] 규칙을 유지한다.
- 반복 문장으로 분량을 채우지 말고, 장면·비교·과학적 맥락·오해 검증을 구체화한다.
- 자동검수 점수나 예약정보는 본문에 넣지 않는다.

AI 검수 결과
{review.model_dump_json(indent=2)}

시스템 검사 결과
{json.dumps(deterministic_issues, ensure_ascii=False)}

연구 패키지
{research.model_dump_json(indent=2)}

기존 초안
{article.model_dump_json(indent=2)}
"""
    result = gemini_structured(WRITER_MODEL, prompt, ArticleDraft)
    assert isinstance(result, ArticleDraft)
    result.html_body = sanitize_html(result.html_body)
    result.slug = slugify(result.slug or result.title)
    result.tags = [tag.strip() for tag in result.tags if tag.strip()][:12]
    return result


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
    policy_url = f"{WP_SITE_URL}/ai-use-policy/"
    if language == "ko":
        return (
            '<div class="taxonguru-editorial-note"><h2>자료와 편집 원칙</h2>'
            "<p>이 글은 공개된 학술·기관 자료를 바탕으로 작성되었으며, 주요 사실은 아래 참고자료에서 확인할 수 있습니다. "
            f'작성 과정은 <a href="{html.escape(policy_url, quote=True)}">AI 활용 및 편집 정책</a>에 공개합니다. '
            f'오류 제보: <a href="mailto:{html.escape(CONTACT_EMAIL)}">{html.escape(CONTACT_EMAIL)}</a></p></div>'
        )
    return (
        '<div class="taxonguru-editorial-note"><h2>Sources and editorial policy</h2>'
        "<p>This feature is based on publicly available scientific and institutional sources listed below. "
        f'Read our <a href="{html.escape(policy_url, quote=True)}">AI and editorial policy</a>. '
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


def search_commons_images(scientific_name: str, limit: int = 8) -> list[CommonsImage]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'filetype:bitmap "{scientific_name}"',
        "gsrnamespace": 6,
        "gsrlimit": 20,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1600,
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
        if len(assets) >= limit:
            break
    return assets


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


def generate_ai_image(item: SheetItem, research: ResearchPackage) -> UploadedMedia | None:
    if not ALLOW_AI_FEATURED_IMAGE or not openai_client:
        return None
    prompt = (
        f"Museum-quality scientific editorial illustration of {research.accepted_scientific_name or item.scientific_name} "
        f"in a plausible natural habitat. Accurately reflect the visible anatomy described in reliable zoological or botanical sources. "
        "Landscape composition, no text, no logo, no watermark. This is an explanatory illustration, not documentary photography."
    )
    response = openai_client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=prompt,
        size="1536x1024",
        quality="medium",
        n=1,
    )
    image_data = response.data[0]
    if not getattr(image_data, "b64_json", None):
        return None
    image_bytes = base64.b64decode(image_data.b64_json)
    today = datetime.now(SCHEDULE_TZ).strftime("%Y-%m-%d")
    caption_ko = f"TaxonGuru 제작 · AI 생성 설명용 이미지 · 실제 관찰 사진 아님 · 생성일 {today}"
    caption_en = f"Created by TaxonGuru · AI-generated explanatory image · not a documentary photograph · generated {today}"
    return upload_media_bytes(
        image_bytes=image_bytes,
        filename=f"{item.slug or slugify(item.scientific_name)}-ai-cover.png",
        mime_type="image/png",
        alt_text=f"Scientific illustration of {item.scientific_name}",
        caption_ko=caption_ko,
        caption_en=caption_en,
        description_html=f"AI-generated explanatory image, not a documentary photograph. Model: {html.escape(OPENAI_IMAGE_MODEL)}",
    )


def figure_html(media: UploadedMedia, alt_text: str, language: Literal["ko", "en"]) -> str:
    caption = media.caption_ko if language == "ko" else media.caption_en
    return (
        '<figure class="taxonguru-source-image">'
        f'<img src="{html.escape(media.source_url, quote=True)}" alt="{html.escape(alt_text, quote=True)}" loading="lazy">'
        f"<figcaption>{caption}</figcaption>"
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
    citation_markers = re.findall(r"\[(\d{1,2})\]", article.html_body)

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
    else:
        word_count = len(re.findall(r"[A-Za-z0-9']+", plain_text))
        if word_count < MIN_ENGLISH_WORDS:
            issues.append(f"영문 본문이 {word_count}단어로 최소 {MIN_ENGLISH_WORDS}단어 미만입니다.")
        if re.search(r"[가-힣]", plain_text):
            issues.append("영어 페이지 본문에 한국어 문자가 포함되어 있습니다.")

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
    article = generate_article(item, research, language)
    review = review_article(item, research, article, language)
    deterministic_issues = deterministic_quality_issues(article, research, language)
    label = "한국어" if language == "ko" else "영어"
    log(f"  🧪 {label} 1차 자동 검수: {review.score}점")

    passed = (
        review.pass_review
        and review.score >= MIN_QUALITY_SCORE
        and not review.critical_issues
        and not review.unsupported_claims
        and not deterministic_issues
    )
    if not passed:
        log(f"  🔁 {label} 검수 지적을 반영해 한 번 재작성합니다.")
        article = revise_article(item, research, article, review, deterministic_issues, language)
        review = review_article(item, research, article, language)
        deterministic_issues = deterministic_quality_issues(article, research, language)
        log(f"  🧪 {label} 2차 자동 검수: {review.score}점")

    passed = (
        review.pass_review
        and review.score >= MIN_QUALITY_SCORE
        and not review.critical_issues
        and not review.unsupported_claims
        and not deterministic_issues
    )
    summary = summarize_review(review, deterministic_issues)
    return article, review, deterministic_issues, passed, summary


def compose_public_content(
    article: ArticleDraft,
    research: ResearchPackage,
    uploaded: list[UploadedMedia],
    language: Literal["ko", "en"],
    scheduled_at: datetime | None,
    review: QualityReview,
    review_summary: str,
) -> str:
    body_media = uploaded[1:3] if len(uploaded) > 1 else []
    body = article.html_body
    for idx in range(2):
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


def create_or_schedule_post(
    worksheet: gspread.Worksheet,
    headers: list[str],
    item: SheetItem,
) -> None:
    log(f"\n🔬 연구 시작: {item.scientific_name}")
    update_sheet_fields(
        worksheet,
        headers,
        item.row_number,
        {
            "status": "조사중",
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
    if ENABLE_ENGLISH:
        update_sheet_fields(worksheet, headers, item.row_number, {"status": "영어작성"})
        en_article, en_review, _, en_passed, en_summary = process_language_article(item, research, "en")

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

    # Wikimedia Commons images are shared by both language versions; captions are localized per page.
    uploaded: list[UploadedMedia] = []
    try:
        commons_assets = search_commons_images(item.scientific_name)
        for idx, asset in enumerate(commons_assets[:3], start=1):
            try:
                uploaded.append(upload_commons_image(asset, item, idx))
            except Exception as image_error:
                log(f"  ⚠️ Commons 이미지 {idx} 업로드 실패: {image_error}")
    except Exception as commons_error:
        log(f"  ⚠️ Commons 검색 실패: {commons_error}")

    if not uploaded:
        ai_media = generate_ai_image(item, research)
        if ai_media:
            uploaded.append(ai_media)
    featured_media = uploaded[0].media_id if uploaded else None

    ko_scheduled: datetime | None = None
    en_scheduled: datetime | None = None
    ko_publish_mode: Literal["future", "draft"] = "draft"
    en_publish_mode: Literal["future", "draft"] = "draft"

    if ko_passed and AUTO_SCHEDULE:
        ko_scheduled = calculate_next_schedule_datetime(PUBLISH_HOUR, PUBLISH_MINUTE)
        ko_publish_mode = "future"
        log(f"  🗓️ 한국어 예약: {ko_scheduled.strftime('%Y-%m-%d %H:%M %Z')}")
    elif not ko_passed:
        log(f"  ⚠️ 한국어 품질 기준 미달: {ko_summary}")

    # English is only auto-scheduled when both the Korean source article and English article pass.
    if ENABLE_ENGLISH and en_article and en_review:
        if ko_passed and en_passed and AUTO_SCHEDULE:
            en_scheduled = calculate_next_schedule_datetime(ENGLISH_PUBLISH_HOUR, ENGLISH_PUBLISH_MINUTE)
            en_publish_mode = "future"
            log(f"  🗓️ 영어 예약: {en_scheduled.strftime('%Y-%m-%d %H:%M %Z')}")
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

    if ko_status == "future" and (not ENABLE_ENGLISH or en_status == "future"):
        next_state = "한영예약완료" if ENABLE_ENGLISH else "예약완료"
    elif ko_status == "future" and en_status == DRAFT_STATUS:
        next_state = "한국어예약/영문검수필요"
    else:
        next_state = "검수필요"

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
            "en_error": "" if en_passed or not ENABLE_ENGLISH else en_summary[:500],
        },
    )

    if next_state == "한영예약완료":
        log(f"  🎉 한·영 예약 완료: KO {ko_scheduled_text} / EN {en_scheduled_text}")
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
        f"자동 예약: {'ON' if AUTO_SCHEDULE else 'OFF'} · 기준 {MIN_QUALITY_SCORE}점/출처 {MIN_SOURCE_COUNT}개 · "
        f"KO {PUBLISH_HOUR:02d}:{PUBLISH_MINUTE:02d} / EN {ENGLISH_PUBLISH_HOUR:02d}:{ENGLISH_PUBLISH_MINUTE:02d} "
        f"{SCHEDULE_TIMEZONE} · 영어 {'ON' if ENABLE_ENGLISH else 'OFF'}"
    )
    log("=" * 70)

    worksheet: gspread.Worksheet | None = None
    headers: list[str] = []
    item: SheetItem | None = None
    try:
        worksheet, headers = connect_sheet()
        ensure_multilingual_backend()
        sync_scheduled_posts(worksheet, headers)
        item = choose_sheet_item(worksheet, headers)
        if not item:
            log("✅ 처리할 '대기' 또는 '재작성' 항목이 없습니다.")
            return 0

        create_or_schedule_post(worksheet, headers, item)
        return 0
    except Exception as exc:
        log(f"\n❌ 처리 실패: {exc}")
        if worksheet is not None and item is not None:
            try:
                update_sheet_fields(
                    worksheet,
                    headers,
                    item.row_number,
                    {"status": "오류", "error": str(exc)[:500]},
                )
            except Exception as sheet_error:
                log(f"  ⚠️ 시트 오류 기록 실패: {sheet_error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
