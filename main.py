from __future__ import annotations

import base64
import html
import json
import os
import re
import sys
import time
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
MIN_ARTICLE_CHARS = int(os.getenv("MIN_ARTICLE_CHARS", "2200"))
MIN_CITATION_MARKERS = int(os.getenv("MIN_CITATION_MARKERS", "4"))
ALLOW_AI_FEATURED_IMAGE = os.getenv("ALLOW_AI_FEATURED_IMAGE", "false").lower() == "true"
AUTO_SCHEDULE = os.getenv("AUTO_SCHEDULE", "true").lower() == "true"
DRAFT_ON_REVIEW_FAILURE = os.getenv("DRAFT_ON_REVIEW_FAILURE", "true").lower() == "true"
DRAFT_STATUS = os.getenv("WP_DRAFT_STATUS", "draft")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "45"))

SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE", "Asia/Seoul")
PUBLISH_HOUR = int(os.getenv("PUBLISH_HOUR", "9"))
PUBLISH_MINUTE = int(os.getenv("PUBLISH_MINUTE", "30"))
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
]
HEADER_ALIASES = {
    "status": ["상태"],
    "scientific_name": ["학명"],
    "title": ["국문/영문명", "제목"],
    "taxonomy": ["분류 트리", "분류트리"],
    "category": ["카테고리"],
    "story_angle": ["스토리앵글", "스토리 앵글"],
    "slug": ["슬러그"],
    "tags": ["태그"],
    "reviewer": ["검수자"],
    "review_date": ["검수일"],
    "review_note": ["검수메모"],
    "language": ["언어"],
    "post_id": ["WP_POST_ID"],
    "edit_url": ["편집URL"],
    "public_url": ["공개URL"],
    "quality_score": ["품질점수"],
    "source_count": ["자료수"],
    "scheduled_date": ["예약일"],
    "auto_review_result": ["자동검수결과"],
    "error": ["오류"],
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
    excerpt: str = ""
    html_body: str = ""
    seo_description: str = ""


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
    caption_html: str
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


def connect_sheet() -> tuple[gspread.Worksheet, list[str]]:
    creds_json = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds_json)
    worksheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    headers = worksheet.row_values(1)
    if not headers:
        headers = LEGACY_HEADERS.copy()
    for required in LEGACY_HEADERS + EXTRA_HEADERS:
        if required not in headers:
            headers.append(required)
    end = column_letter(len(headers))
    worksheet.update(values=[headers], range_name=f"A1:{end}1")
    return worksheet, headers


def header_index(headers: list[str], logical_name: str) -> int:
    for alias in HEADER_ALIASES[logical_name]:
        if alias in headers:
            return headers.index(alias)
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
    for logical_name, value in fields.items():
        idx = header_index(headers, logical_name) + 1
        worksheet.update_cell(row_number, idx, str(value if value is not None else ""))


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
    caption_html: str,
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
            "caption": caption_html,
            "description": description_html,
            "title": alt_text,
        },
    )
    return UploadedMedia(
        media_id=media_id,
        source_url=payload.get("source_url", ""),
        caption_html=caption_html,
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


def calculate_next_schedule_datetime() -> datetime:
    """Find the next free WordPress publication slot in the configured timezone."""
    now_local = datetime.now(SCHEDULE_TZ)
    minimum_time = now_local + timedelta(minutes=MIN_SCHEDULE_LEAD_MINUTES)

    candidate = (now_local + timedelta(days=max(0, SCHEDULE_AFTER_DAYS))).replace(
        hour=PUBLISH_HOUR,
        minute=PUBLISH_MINUTE,
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
        if item.status != "예약완료" or not item.post_id:
            continue
        try:
            post = get_post(item.post_id)
            wp_status = str(post.get("status", ""))
            if wp_status == "publish":
                update_sheet_fields(
                    worksheet,
                    headers,
                    item.row_number,
                    {
                        "status": "완료",
                        "public_url": post.get("link", ""),
                        "error": "",
                    },
                )
                log(f"  ✅ 예약글 공개 확인: Post ID {item.post_id}")
            elif wp_status == "draft":
                update_sheet_fields(
                    worksheet,
                    headers,
                    item.row_number,
                    {
                        "status": "검수필요",
                        "error": "WordPress 예약글이 초안 상태로 변경되었습니다.",
                    },
                )
            elif wp_status == "future":
                scheduled = parse_wp_local_datetime(str(post.get("date", "")))
                if scheduled:
                    update_sheet_fields(
                        worksheet,
                        headers,
                        item.row_number,
                        {"scheduled_date": scheduled.strftime("%Y-%m-%d %H:%M %Z")},
                    )
        except Exception as exc:
            log(f"  ⚠️ 예약 상태 동기화 실패(Post ID {item.post_id}): {exc}")


# -----------------------------------------------------------------------------
# Grounded research
# -----------------------------------------------------------------------------
def fetch_seed_context(scientific_name: str) -> dict[str, Any]:
    seed: dict[str, Any] = {"gbif": {}, "wikipedia": {}, "crossref": []}

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

    # Wikipedia summary is a seed, never the sole authority.
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

    # Crossref scholarly works
    try:
        response = session.get(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": f'"{scientific_name}"',
                "rows": 5,
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
                    }
                )
    except requests.RequestException as exc:
        log(f"  ⚠️ Crossref 조회 실패: {exc}")

    return seed


def research_subject(item: SheetItem) -> ResearchPackage:
    seed_context = fetch_seed_context(item.scientific_name)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
당신은 자연과학 편집부의 리서처다. 아래 생물을 Google Search와 제공된 데이터로 조사하고,
검증 가능한 사실만 구조화해서 반환하라.

연구 대상
- 학명: {item.scientific_name}
- 현재 제목 후보: {item.display_title}
- 기존 분류 메모: {item.taxonomy}
- 글의 질문/관점: {item.story_angle}
- 조사일: {today}

기초 API 데이터
{json.dumps(seed_context, ensure_ascii=False, indent=2)[:24000]}

엄격한 기준
1. 학명, 분류, 분포, 보전상태, 형태·생태 수치는 서로 다른 신뢰 자료로 교차 확인한다.
2. 정부기관, 대학·박물관, 과학 데이터베이스, 원 논문을 우선한다.
3. Wikipedia는 탐색용 보조자료일 뿐 핵심 사실의 유일한 근거로 사용하지 않는다.
4. 논쟁적 주장과 확정 사실을 분리하고, 자료가 충돌하면 양쪽 근거와 결론을 적는다.
5. 검색결과 요약문이나 AI 문장을 출처로 만들지 말고, 직접 열 수 있는 원문 URL을 기록한다.
6. sources에는 중복 없는 직접 URL을 5~10개 넣고, 본문 사실은 source_numbers로 연결한다.
7. 확인되지 않은 수치, 과장, 의인화, 자극적 표현은 넣지 않는다.
8. 실제 자격을 확인할 수 없으므로 '수석 고생물학자', '전문가' 등의 가상 직함을 만들지 않는다.
"""
    result = gemini_structured(
        RESEARCH_MODEL,
        prompt,
        ResearchPackage,
        tools_list=["google_search", "url_context"],
    )
    assert isinstance(result, ResearchPackage)
    return normalize_research_package(result, item.scientific_name)


def normalize_research_package(package: ResearchPackage, fallback_name: str) -> ResearchPackage:
    old_to_new: dict[int, int] = {}
    seen: set[str] = set()
    clean_sources: list[ResearchSource] = []

    for old_index, source in enumerate(package.sources, start=1):
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
def generate_article(item: SheetItem, research: ResearchPackage) -> ArticleDraft:
    prompt = f"""
당신은 TaxonGuru 편집팀의 과학 콘텐츠 작성자다. 아래 검증 자료만 사용해 한국어 기사 초안을 작성하라.

콘텐츠 목표
- 검색어를 채우기 위한 대량생산 글이 아니라, 독자가 실제로 이해하고 검증할 수 있는 독창적 해설
- 고정된 5단 템플릿을 반복하지 말고 이 주제에 맞는 구조를 선택
- AI 초안처럼 보이는 상투적 문장, 과도한 감탄, '충격', '대박', 근거 없는 세계 최고 표현 금지

주제 정보
- 학명: {item.scientific_name}
- 원래 제목 후보: {item.display_title}
- 핵심 질문/관점: {item.story_angle}
- 카테고리: {item.category}

검증된 연구 패키지
{research.model_dump_json(indent=2)}

작성 규칙
1. 한국어만 작성한다. 같은 글 안에 영어 번역본을 반복하지 않는다.
2. title은 구체적 질문 또는 검증 포인트가 드러나는 자연스러운 제목으로 작성한다.
3. html_body는 순수한 본문 HTML만 반환하고 script, style, iframe, form은 사용하지 않는다.
4. 첫 부분에 3~5개 핵심 요약을 넣고, 정확한 분류표를 포함한다.
5. 핵심 사실 뒤에는 반드시 [1], [2]처럼 연구 패키지의 source 번호를 표기한다.
6. 자료가 불확실하거나 논쟁 중이면 '확인된 사실'과 '아직 불확실한 부분'을 명확히 구분한다.
7. 직접 비교·해석은 '편집부 해설'이라고 표시하고, 새로운 사실처럼 단정하지 않는다.
8. 본문 중간에 [[IMAGE_1]], [[IMAGE_2]]를 각각 정확히 한 번 넣는다.
9. 참고문헌, 이미지 라이선스, AI 활용 고지와 자동 검수 결과는 시스템이 뒤에 붙이므로 본문에 만들지 않는다.
10. 2,500~5,000자 정도의 실질적인 내용으로 작성하되 불필요한 반복은 하지 않는다.
"""
    result = gemini_structured(WRITER_MODEL, prompt, ArticleDraft)
    assert isinstance(result, ArticleDraft)
    result.html_body = sanitize_html(result.html_body)
    return result


def review_article(item: SheetItem, research: ResearchPackage, article: ArticleDraft) -> QualityReview:
    prompt = f"""
아래 자연과학 블로그 초안을 엄격하게 검수하라. 점수는 0~100점이다.

검수 기준
- 연구 패키지에 없는 사실·수치·인과관계를 만들지 않았는가
- 모든 주요 사실에 올바른 출처 번호가 있는가
- 분류학적 오류, 논쟁 중인 내용을 확정 사실로 표현한 문제가 없는가
- 고정 템플릿·번역 반복·과장·클릭베이트·가상 전문가 행세가 없는가
- 독자에게 고유한 비교, 설명, 한계 고지가 있는가
- 제목과 본문이 일치하는가

통과 조건
- 중대한 사실 오류 0건
- 근거 없는 핵심 주장 0건
- 점수 {MIN_QUALITY_SCORE}점 이상

연구 패키지
{research.model_dump_json(indent=2)}

초안
제목: {article.title}
요약: {article.excerpt}
본문 HTML:
{article.html_body}
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
) -> ArticleDraft:
    prompt = f"""
아래 검수 지적을 모두 반영해 기사 초안을 다시 작성하라. 연구 패키지 밖의 사실은 추가하지 않는다.
한국어 단일 언어, 출처 번호, [[IMAGE_1]], [[IMAGE_2]] 규칙을 유지한다.

검수 결과
{review.model_dump_json(indent=2)}

연구 패키지
{research.model_dump_json(indent=2)}

기존 초안
{article.model_dump_json(indent=2)}
"""
    result = gemini_structured(WRITER_MODEL, prompt, ArticleDraft)
    assert isinstance(result, ArticleDraft)
    result.html_body = sanitize_html(result.html_body)
    return result


def build_references_html(sources: list[ResearchSource]) -> str:
    items = []
    for index, source in enumerate(sources, start=1):
        title = html.escape(source.title or source.url)
        publisher = html.escape(source.publisher or "출처")
        accessed = html.escape(source.accessed_date or datetime.now().strftime("%Y-%m-%d"))
        url = html.escape(source.url, quote=True)
        items.append(
            f'<li id="ref-{index}"><a href="{url}" target="_blank" rel="noopener noreferrer">'
            f"{title}</a> — {publisher}, 확인일 {accessed}</li>"
        )
    return "<h2>참고자료</h2><ol>" + "".join(items) + "</ol>"


def automation_status_box(
    quality_passed: bool,
    quality_score: int,
    source_count: int,
    scheduled_at: datetime | None,
    review_summary: str,
) -> str:
    if quality_passed and scheduled_at:
        status = "scheduled"
        title = "자동 품질검사 통과"
        detail = (
            f"출처 {source_count}개와 자동 검수점수 {quality_score}점을 확인하여 "
            f"{scheduled_at.strftime('%Y-%m-%d %H:%M %Z')}에 예약되었습니다."
        )
    else:
        status = "needs-review"
        title = "자동 품질검사 기준 미달"
        detail = "이 글은 공개되지 않고 WordPress 비공개 초안으로 저장되었습니다."

    summary_html = f"<br><small>{html.escape(review_summary)}</small>" if review_summary else ""
    return (
        "<!-- TAXONGURU_REVIEW_BOX_START -->"
        f'<div class="taxonguru-review-note" data-status="{status}">'
        f"<strong>{title}:</strong> {detail}{summary_html}"
        "</div>"
        "<!-- TAXONGURU_REVIEW_BOX_END -->"
    )


def editorial_disclosure_html() -> str:
    today = datetime.now(SCHEDULE_TZ).strftime("%Y-%m-%d")
    return (
        "<h2>작성 방법과 한계</h2>"
        "<p>TaxonGuru는 자료 탐색·구조화·초안 작성과 품질 점검에 생성형 AI를 사용합니다. "
        "출처 수, 인용 표시, 중대한 오류와 근거 없는 주장 여부를 자동 검사하며, 기준을 통과한 글은 예약 발행될 수 있습니다. "
        "모든 게시물이 공개 전에 사람의 개별 검수를 거치는 것은 아닙니다. 참고자료 원문과 비교해 읽어주시고, "
        f'오류는 <a href="mailto:{html.escape(CONTACT_EMAIL)}">{html.escape(CONTACT_EMAIL)}</a>로 알려주세요. '
        f"자료 조사 기준일은 {today}입니다.</p>"
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
    caption = (
        f"사진: {html.escape(asset.artist)} · Wikimedia Commons"
        f"{license_link} · "
        f'<a href="{html.escape(asset.page_url, quote=True)}" target="_blank" rel="noopener noreferrer">원본 파일</a>'
    )
    description = (
        f"Wikimedia Commons 원본: {html.escape(asset.page_url)}<br>"
        f"저작자: {html.escape(asset.artist)}<br>"
        f"라이선스: {html.escape(asset.license_name)}"
    )
    return upload_media_bytes(
        image_bytes=image_bytes,
        filename=filename,
        mime_type=mime_type,
        alt_text=f"{item.scientific_name} 관찰 사진",
        caption_html=caption,
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
    caption = f"TaxonGuru 제작 · AI 생성 설명용 이미지 · 실제 관찰 사진 아님 · 생성일 {today}"
    return upload_media_bytes(
        image_bytes=image_bytes,
        filename=f"{item.slug or slugify(item.scientific_name)}-ai-cover.png",
        mime_type="image/png",
        alt_text=f"{item.scientific_name} 설명용 AI 일러스트",
        caption_html=caption,
        description_html=f"AI 생성 설명용 이미지. 실제 관찰 사진이 아닙니다. 모델: {html.escape(OPENAI_IMAGE_MODEL)}",
    )


def figure_html(media: UploadedMedia, alt_text: str) -> str:
    return (
        '<figure class="taxonguru-source-image">'
        f'<img src="{html.escape(media.source_url, quote=True)}" alt="{html.escape(alt_text, quote=True)}" loading="lazy">'
        f"<figcaption>{media.caption_html}</figcaption>"
        "</figure>"
    )


# -----------------------------------------------------------------------------
# Main processing
# -----------------------------------------------------------------------------
def deterministic_quality_issues(
    article: ArticleDraft,
    research: ResearchPackage,
) -> list[str]:
    issues: list[str] = []
    plain_text = strip_html(article.html_body)
    citation_markers = re.findall(r"\[(\d{1,2})\]", article.html_body)

    if not article.title.strip():
        issues.append("제목이 비어 있습니다.")
    if len(plain_text) < MIN_ARTICLE_CHARS:
        issues.append(f"본문 길이가 {len(plain_text)}자로 최소 {MIN_ARTICLE_CHARS}자 미만입니다.")
    if len(citation_markers) < MIN_CITATION_MARKERS:
        issues.append(
            f"본문 인용표시가 {len(citation_markers)}개로 최소 {MIN_CITATION_MARKERS}개 미만입니다."
        )
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
        {"status": "조사중", "scheduled_date": "", "auto_review_result": "", "error": ""},
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
    update_sheet_fields(worksheet, headers, item.row_number, {"status": "작성중"})

    article = generate_article(item, research)
    update_sheet_fields(worksheet, headers, item.row_number, {"status": "자동검수중"})
    review = review_article(item, research, article)
    deterministic_issues = deterministic_quality_issues(article, research)
    log(f"  🧪 1차 자동 검수: {review.score}점")

    first_passed = (
        review.pass_review
        and review.score >= MIN_QUALITY_SCORE
        and not review.critical_issues
        and not review.unsupported_claims
        and not deterministic_issues
    )

    if not first_passed:
        log("  🔁 검수 지적을 반영해 한 번 재작성합니다.")
        article = revise_article(item, research, article, review)
        review = review_article(item, research, article)
        deterministic_issues = deterministic_quality_issues(article, research)
        log(f"  🧪 2차 자동 검수: {review.score}점")

    quality_passed = (
        review.pass_review
        and review.score >= MIN_QUALITY_SCORE
        and not review.critical_issues
        and not review.unsupported_claims
        and not deterministic_issues
    )
    review_summary = summarize_review(review, deterministic_issues)

    if not quality_passed and not DRAFT_ON_REVIEW_FAILURE:
        update_sheet_fields(
            worksheet,
            headers,
            item.row_number,
            {
                "status": "검수실패",
                "quality_score": review.score,
                "source_count": len(research.sources),
                "auto_review_result": review_summary,
                "error": review_summary[:500],
            },
        )
        log(f"  ⛔ 품질 기준 미달로 WordPress에 저장하지 않았습니다: {review_summary}")
        return

    scheduled_at: datetime | None = None
    publish_mode: Literal["future", "draft"] = "draft"
    if quality_passed and AUTO_SCHEDULE:
        scheduled_at = calculate_next_schedule_datetime()
        publish_mode = "future"
        log(f"  🗓️ 예약 슬롯 확정: {scheduled_at.strftime('%Y-%m-%d %H:%M %Z')}")
    elif quality_passed:
        log("  ℹ️ AUTO_SCHEDULE이 꺼져 있어 통과 글도 초안으로 저장합니다.")
    else:
        log(f"  ⚠️ 자동 품질 기준 미달: {review_summary}")

    # Collect and upload licensed images. Wikimedia Commons is preferred.
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
    body_media = uploaded[1:3] if len(uploaded) > 1 else []

    body = article.html_body
    for idx in range(2):
        placeholder = f"[[IMAGE_{idx + 1}]]"
        if idx < len(body_media):
            figure = figure_html(body_media[idx], f"{item.scientific_name} 관련 자료 이미지")
            body = body.replace(placeholder, figure, 1)
        else:
            body = body.replace(placeholder, "", 1)

    body = replace_citation_markers(body, len(research.sources))
    featured_credit = ""
    if uploaded:
        featured_credit = "<h2>대표 이미지 출처</h2>" f"<p>{uploaded[0].caption_html}</p>"

    full_content = (
        automation_status_box(
            quality_passed=quality_passed,
            quality_score=review.score,
            source_count=len(research.sources),
            scheduled_at=scheduled_at,
            review_summary=review_summary,
        )
        + body
        + featured_credit
        + editorial_disclosure_html()
        + build_references_html(research.sources)
    )

    category_id = get_or_create_wp_term(item.category, "categories")
    tag_names = item.tags or [item.category, item.scientific_name]
    tag_ids = [term_id for tag in tag_names if (term_id := get_or_create_wp_term(tag, "tags"))]
    slug = item.slug or slugify(research.accepted_scientific_name or item.scientific_name)
    if not slug:
        raise RuntimeError("유효한 슬러그를 만들 수 없습니다.")

    post = upsert_post(
        slug=slug,
        title=article.title,
        excerpt=article.excerpt or article.seo_description,
        content=full_content,
        featured_media=featured_media,
        category_id=category_id,
        tag_ids=tag_ids,
        publish_mode=publish_mode,
        scheduled_at=scheduled_at,
    )
    post_id = int(post["id"])
    wp_status = str(post.get("status", DRAFT_STATUS))
    edit_url = f"{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit"

    if publish_mode == "future" and wp_status != "future":
        raise RuntimeError(f"WordPress가 예약 상태를 반환하지 않았습니다. 실제 상태: {wp_status}")

    next_state = "예약완료" if wp_status == "future" else "검수필요"
    scheduled_text = scheduled_at.strftime("%Y-%m-%d %H:%M %Z") if scheduled_at else ""
    update_sheet_fields(
        worksheet,
        headers,
        item.row_number,
        {
            "status": next_state,
            "post_id": post_id,
            "edit_url": edit_url,
            "public_url": post.get("link", "") if wp_status in {"future", "publish"} else "",
            "quality_score": review.score,
            "source_count": len(research.sources),
            "scheduled_date": scheduled_text,
            "auto_review_result": review_summary,
            "error": "" if quality_passed else review_summary[:500],
        },
    )

    if wp_status == "future":
        log(f"  🎉 WordPress 예약 완료: {scheduled_text}")
        log(f"  🔗 편집: {edit_url}")
    else:
        log(f"  📝 기준 미달 글을 비공개 초안으로 저장했습니다: {edit_url}")


def main() -> int:
    log("=" * 70)
    log("TaxonGuru 자동 품질검수 + WordPress 예약 발행 파이프라인")
    log(
        f"자동 예약: {'ON' if AUTO_SCHEDULE else 'OFF'} · 기준 {MIN_QUALITY_SCORE}점/출처 {MIN_SOURCE_COUNT}개 · "
        f"발행시각 {PUBLISH_HOUR:02d}:{PUBLISH_MINUTE:02d} {SCHEDULE_TIMEZONE}"
    )
    log("=" * 70)

    worksheet: gspread.Worksheet | None = None
    headers: list[str] = []
    item: SheetItem | None = None
    try:
        worksheet, headers = connect_sheet()
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
