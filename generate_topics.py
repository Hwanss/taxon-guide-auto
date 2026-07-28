from __future__ import annotations

import json
import os
import sys
import warnings
from typing import Literal

import gspread
import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", category=FutureWarning)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
SHEET_ID = os.environ["SHEET_ID"]
SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")
TOPIC_MODEL = os.getenv("GEMINI_TOPIC_MODEL", "gemini-3.5-flash-lite")
TOPIC_COUNT = int(os.getenv("TOPIC_COUNT", "8"))

client = genai.Client(api_key=GEMINI_API_KEY)
session = requests.Session()
session.headers.update({"User-Agent": "TaxonGuruTopicPlanner/2.0 (admin@taxonguru.com)"})

REQUIRED_HEADERS = [
    "상태", "학명", "국문/영문명", "분류 트리", "카테고리", "스토리앵글", "슬러그", "태그",
    "검수자", "검수일", "검수메모", "언어", "WP_POST_ID", "편집URL", "공개URL", "품질점수", "자료수", "예약일", "자동검수결과", "오류",
]


class Topic(BaseModel):
    scientific_name: str = ""
    title_ko: str = ""
    common_name_en: str = ""
    taxonomy_hint: str = ""
    category: Literal[
        "Botany / 식물학",
        "Evolution Mysteries / 진화의 미스터리",
        "Extreme Survivors / 극한의 생존자",
        "Size Lab / 크기 비교 연구소",
    ]
    research_question: str = ""
    slug: str = ""
    tags: list[str] = Field(default_factory=list)


class TopicBatch(BaseModel):
    topics: list[Topic] = Field(default_factory=list)


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def connect_sheet() -> tuple[gspread.Worksheet, list[str]]:
    gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS))
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    headers = ws.row_values(1)
    if not headers:
        headers = REQUIRED_HEADERS.copy()
    for header in REQUIRED_HEADERS:
        if header not in headers:
            headers.append(header)
    ws.update(values=[headers], range_name=f"A1:{column_letter(len(headers))}1")
    return ws, headers


def validate_scientific_name(name: str) -> tuple[bool, str, str]:
    try:
        response = session.get(
            "https://api.gbif.org/v1/species/match",
            params={"name": name, "verbose": "true"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        confidence = int(data.get("confidence", 0))
        match_type = data.get("matchType", "NONE")
        canonical = data.get("canonicalName") or data.get("scientificName") or name
        classification = " > ".join(
            str(data.get(rank, ""))
            for rank in ["kingdom", "phylum", "class", "order", "family", "genus"]
            if data.get(rank)
        )
        return confidence >= 80 and match_type != "NONE", canonical, classification
    except Exception:
        return False, name, ""


def structured_topics(prompt: str) -> TopicBatch:
    try:
        interaction = client.interactions.create(
            model=TOPIC_MODEL,
            input=prompt,
            tools=[{"type": "google_search"}],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": TopicBatch.model_json_schema(),
            },
        )
        return TopicBatch.model_validate_json(interaction.output_text)
    except Exception as error:
        print(f"⚠️ Interactions API 재시도: {error}")
        response = client.models.generate_content(
            model=TOPIC_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json",
                response_schema=TopicBatch,
            ),
        )
        return TopicBatch.model_validate_json(response.text)


def main() -> int:
    ws, headers = connect_sheet()
    rows = ws.get_all_values()[1:]
    sci_idx = headers.index("학명")
    slug_idx = headers.index("슬러그")
    existing_names = {row[sci_idx].strip().casefold() for row in rows if len(row) > sci_idx and row[sci_idx].strip()}
    existing_slugs = {row[slug_idx].strip().casefold() for row in rows if len(row) > slug_idx and row[slug_idx].strip()}

    prompt = f"""
당신은 자연과학 전문 매체의 편집 기획자다. TaxonGuru가 깊이 있게 조사할 새 주제 {TOPIC_COUNT + 4}개를 제안하라.
Google Search를 사용해 실제로 존재하는 생물과 현재 통용되는 학명을 확인하라.

이미 다룬 학명
{json.dumps(sorted(existing_names), ensure_ascii=False)}

기획 원칙
1. '조회수 폭발', '대박', '충격' 같은 클릭베이트를 쓰지 않는다.
2. 각 주제는 단순 생물 소개가 아니라 검증 가능한 하나의 질문을 가진다.
3. 서로 다른 형식을 섞는다: 오해 검증, 유사종 비교, 적응 원리, 분류 논쟁, 크기 비교, 보전 현황.
4. 제목은 한국어 중심이며 괄호에 영어 일반명을 짧게 넣을 수 있다.
5. 스토리앵글 대신 research_question에 출처로 검증할 수 있는 구체적인 질문을 적는다.
6. 태그는 한국어와 영어를 합쳐 4~6개로 제한한다.
7. 슬러그는 소문자 영문과 하이픈만 사용한다.
8. 기존 학명과 중복하지 않는다.
"""
    batch = structured_topics(prompt)

    rows_to_append: list[list[str]] = []
    for topic in batch.topics:
        valid, canonical, gbif_taxonomy = validate_scientific_name(topic.scientific_name)
        if not valid:
            print(f"건너뜀(GBIF 검증 실패): {topic.scientific_name}")
            continue
        if canonical.casefold() in existing_names or topic.slug.casefold() in existing_slugs:
            continue

        values = {
            "상태": "대기",
            "학명": canonical,
            "국문/영문명": topic.title_ko,
            "분류 트리": gbif_taxonomy or topic.taxonomy_hint,
            "카테고리": topic.category,
            "스토리앵글": topic.research_question,
            "슬러그": topic.slug,
            "태그": ", ".join(topic.tags[:6]),
            "언어": "ko",
        }
        row = [""] * len(headers)
        for key, value in values.items():
            row[headers.index(key)] = value
        rows_to_append.append(row)
        existing_names.add(canonical.casefold())
        existing_slugs.add(topic.slug.casefold())
        if len(rows_to_append) >= TOPIC_COUNT:
            break

    if rows_to_append:
        ws.append_rows(rows_to_append, value_input_option="RAW")
    print(f"✅ 검증된 신규 주제 {len(rows_to_append)}건을 추가했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
