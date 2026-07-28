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
from urllib.parse import urlsplit

import gspread
import requests
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
RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", "gemini-3.6-flash")
WRITER_MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-3.6-flash")
REVIEW_MODEL = os.getenv("GEMINI_REVIEW_MODEL", "gemini-3.6-flash")
OUTPUT_DIR = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))

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
    scientific_name: str
    slug: str
    post_id: int | None
    en_post_id: int | None


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
    for alias in TOPIC_ALIASES[key]:
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


def wp_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
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
                scientific_name=get_value(row, indexes["scientific_name"]),
                slug=get_value(row, indexes["slug"]),
                post_id=safe_int(get_value(row, indexes["post_id"])),
                en_post_id=safe_int(get_value(row, indexes["en_post_id"])),
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
    external = {
        link
        for link in re.findall(r'href=["\'](https?://[^"\']+)', content, flags=re.I)
        if "taxonguru.com" not in link
    }
    images = len(re.findall(r"<img\b", content, flags=re.I))
    license_mentions = len(
        re.findall(r"CC\s*BY|CC0|Public domain|퍼블릭\s*도메인|Wikimedia Commons|원본\s*파일", content, re.I)
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
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        return ""
    parts = urlsplit(value)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")


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
                url = normalize_url(str(_obj_value(annotation, "url", "")))
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
        url = normalize_url(source.url)
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
        f'<a href="/ai-policy/">{"AI 활용 및 편집 정책" if language == "ko" else "AI and editorial policy"}</a></p></section>'
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
    if language == "en" and len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", text_only(body))) < 850:
        result.passed = False
        result.style_issues.append("영문 본문 850단어 미만")
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
    error = ""

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
        combined_score = round((structural.score * 0.35) + (decision.factual_score * 0.45) + (decision.editorial_score * 0.20))

        # 안전 보완 모드: 사실관계를 건드리지 않는 범위만 수정
        if AUDIT_MODE == "safe_fix":
            fixed_content, changes = safe_fix_content(original_content)
            if fixed_content != original_content:
                wp_request("POST", f"posts/{post_id}", json={"content": fixed_content})
                actual_action = " / ".join(changes)
            else:
                actual_action = "안전 보완 항목 없음"

        # 최신순 전면 재작성: B/C 글만 기존 URL에 덮어씀
        elif AUDIT_MODE == "rewrite_recent" and decision.grade in {"B", "C"}:
            if not scientific_name:
                actual_action = "학명 매칭 실패로 재작성 보류"
            elif len(sources) < MIN_SOURCE_COUNT:
                actual_action = f"출처 {len(sources)}개로 재작성 보류"
            else:
                package = build_research_package(scientific_name, title, memo, seed, sources)
                used_sources = {
                    number
                    for fact in package.verified_facts + package.misconceptions + package.uncertain_claims
                    for number in fact.source_numbers
                    if 1 <= number <= len(package.sources)
                }
                if len(used_sources) < MIN_SOURCE_COUNT:
                    actual_action = f"검증 사실에 연결된 출처 {len(used_sources)}개로 재작성 보류"
                else:
                    # 실제 사용된 출처만 유지하고 번호를 다시 매김
                    old_to_new: dict[int, int] = {}
                    selected_sources: list[ResearchSource] = []
                    for old_num in sorted(used_sources):
                        old_to_new[old_num] = len(selected_sources) + 1
                        selected_sources.append(package.sources[old_num - 1])
                    for fact in package.verified_facts + package.misconceptions + package.uncertain_claims:
                        fact.source_numbers = [old_to_new[n] for n in fact.source_numbers if n in old_to_new]
                    package.sources = selected_sources

                    figures = extract_preserved_figures(original_content)
                    ko_body = generate_article(package, "ko", figures)
                    ko_meta = generate_meta(package, ko_body, "ko", str(post.get("slug", "")))
                    ko_review = review_rewrite(ko_body, package, "ko")
                    if not ko_review.passed:
                        actual_action = "한국어 재작성 검수 미달: " + " | ".join(
                            (ko_review.critical_errors + ko_review.unsupported_claims + ko_review.style_issues)[:5]
                        )
                    else:
                        ko_content = ko_body + build_references(package, "ko")
                        payload = {
                            "title": ko_meta.title,
                            "excerpt": ko_meta.excerpt or ko_meta.seo_description,
                            "content": ko_content,
                            "status": "publish",
                            "slug": str(post.get("slug", "")),
                        }
                        updated_post = wp_request("POST", f"posts/{post_id}", json=payload).json()
                        actual_action = "한국어 기존 URL 재작성 완료"

                        en_id: int | None = None
                        en_url = ""
                        en_score = ""
                        if CREATE_ENGLISH:
                            en_body = generate_article(package, "en", figures)
                            en_meta = generate_meta(package, en_body, "en", "")
                            en_review = review_rewrite(en_body, package, "en")
                            en_score = str(en_review.score)
                            if en_review.passed:
                                en_content = en_body + build_references(package, "en")
                                en_id, en_url = upsert_english_post(topic, post_id, updated_post, en_meta, en_content)
                                actual_action += " / 영어 별도 글 완료"
                            else:
                                actual_action += " / 영어 검수 미달"

                        if topic:
                            update_fields: dict[str, Any] = {
                                "status": "한영수정완료" if CREATE_ENGLISH and en_id else "수정완료",
                                "post_id": post_id,
                                "quality_score": ko_review.score,
                                "public_url": str(updated_post.get("link", url)),
                            }
                            if en_id:
                                update_fields.update(
                                    {
                                        "en_post_id": en_id,
                                        "en_quality_score": en_score,
                                        "en_public_url": en_url,
                                    }
                                )
                            update_topic_fields(topic_ws, topic_headers, topic.row_number, update_fields)

        elif AUDIT_MODE == "rewrite_recent" and decision.grade == "D":
            if DRAFT_GRADE_D:
                wp_request("POST", f"posts/{post_id}", json={"status": "draft"})
                actual_action = "D등급 자동 초안 전환"
            else:
                actual_action = "삭제·통합 검토만 표시(자동 삭제 안 함)"

        return {
            "감사상태": "수정완료" if "완료" in actual_action else ("삭제검토" if decision.grade == "D" else "완료"),
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
        return {
            "감사상태": "오류",
            "감사일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "처리모드": AUDIT_MODE,
            "게시물ID": post_id,
            "수정일": str(post.get("modified", "")),
            "제목": title,
            "URL": url,
            "학명": scientific_name,
            "구조점수": structural.score,
            "사실점수": "",
            "종합점수": "",
            "등급": "",
            "권장조치": "재시도",
            "실제처리": "처리 실패",
            "출처수": "",
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
    log(f"모드={AUDIT_MODE} · 최근순 · 최대 {BATCH_SIZE}건 · 영어별도작성={'ON' if CREATE_ENGLISH else 'OFF'}")
    log("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    topic_ws, audit_ws = connect_sheets()
    topic_headers, topic_rows = load_topic_rows(topic_ws)
    completed = audited_post_ids(audit_ws, AUDIT_MODE)
    posts = fetch_posts()
    targets = [post for post in posts if INCLUDE_ALREADY_AUDITED or int(post["id"]) not in completed][:BATCH_SIZE]

    if not targets:
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
