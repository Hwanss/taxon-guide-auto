from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any

import gspread
import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
SHEET_ID = os.environ["SHEET_ID"]
SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")
TOPIC_COUNT = max(1, min(30, int(os.getenv("TOPIC_COUNT", "12"))))
MODEL = os.getenv("GEMINI_TOPIC_MODEL", "gemini-3.6-flash")
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))

CATEGORY_VALUES = [
    "Botany / 식물학",
    "Evolution Mysteries / 진화의 미스터리",
    "Extreme Survivors / 극한의 생존자",
    "Size Lab / 크기 비교 연구소",
]


class TopicCandidate(BaseModel):
    scientific_name: str
    display_title: str
    taxonomy: str
    category: str
    story_angle: str
    slug: str
    tags: list[str] = Field(default_factory=list)


class TopicBatch(BaseModel):
    topics: list[TopicCandidate] = Field(default_factory=list)


def log(message: str) -> None:
    print(message, flush=True)


def normalize_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:100]


def gbif_validate(name: str) -> tuple[bool, str, str]:
    try:
        response = requests.get(
            "https://api.gbif.org/v1/species/match",
            params={"name": name},
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            return False, name, ""
        data: dict[str, Any] = response.json()
        if data.get("matchType") == "NONE" or not (data.get("usageKey") or data.get("speciesKey")):
            return False, name, ""
        confidence = int(data.get("confidence") or 0)
        rank = str(data.get("rank") or "").upper()
        if confidence < 80 or rank not in {"SPECIES", "SUBSPECIES"}:
            return False, name, ""
        accepted = str(data.get("scientificName") or name).strip()
        lineage = " > ".join(
            str(data.get(key) or "").strip()
            for key in ("kingdom", "phylum", "class", "order", "family")
            if str(data.get(key) or "").strip()
        )
        return True, accepted, lineage
    except Exception:
        return False, name, ""


def generate_candidates(existing_species: set[str], existing_slugs: set[str], count: int) -> list[TopicCandidate]:
    existing_preview = ", ".join(sorted(existing_species)[-250:]) or "없음"
    prompt = f"""
You are the editorial topic planner for TaxonGuru, a Korean-English popular-science biology site.
Generate {max(count * 2, 16)} candidate topics. Return TopicBatch JSON only.

Already used scientific names — never repeat them:
{existing_preview}

Rules:
- Use a real species-level binomial scientific name, not 'spp.', a fictional taxon, or a broad genus.
- Pick subjects with enough reliable institutional or scholarly sources for a 4-source article.
- Category must be exactly one of: {CATEGORY_VALUES}
- display_title: attractive Korean title with the English common name in parentheses where useful.
- story_angle: one concrete reader question or scientific mystery, not generic hype.
- taxonomy: concise lineage such as Animalia > Chordata > Mammalia.
- slug: lowercase English, unique, 3-8 words, no year.
- tags: 6-10 useful Korean and English tags.
- Avoid clickbait words such as shocking, unbelievable, 대박, 충격, 소름.
- Balance the four categories.
"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TopicBatch,
            max_output_tokens=8192,
            temperature=0.65,
        ),
    )
    parsed = getattr(response, "parsed", None)
    batch = parsed if isinstance(parsed, TopicBatch) else TopicBatch.model_validate(parsed or json.loads(response.text))

    result: list[TopicCandidate] = []
    for candidate in batch.topics:
        raw_name = " ".join(candidate.scientific_name.split())
        if raw_name.lower() in {name.lower() for name in existing_species}:
            continue
        valid, accepted, lineage = gbif_validate(raw_name)
        if not valid:
            continue
        slug = normalize_slug(candidate.slug)
        if not slug or slug in existing_slugs:
            continue
        if candidate.category not in CATEGORY_VALUES:
            continue
        candidate.scientific_name = accepted
        candidate.taxonomy = candidate.taxonomy.strip() or lineage
        candidate.slug = slug
        candidate.tags = [str(tag).strip() for tag in candidate.tags if str(tag).strip()][:10]
        result.append(candidate)
        existing_species.add(accepted)
        existing_slugs.add(slug)
        if len(result) >= count:
            break
    return result


def main() -> int:
    log("=" * 64)
    log(f"TaxonGuru 주제 자동 보충 · 목표 {TOPIC_COUNT}건")
    log("=" * 64)

    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    worksheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = worksheet.get_all_values()
    if not records:
        raise RuntimeError("taxonguru 시트에 헤더가 없습니다.")

    headers = records[0]
    required = ["상태", "학명(Scientific Name)", "국문/영문명", "분류 트리", "카테고리", "스토리 앵글", "슬러그 (Slug)", "태그 (Tags)"]
    if len(headers) < 8:
        raise RuntimeError("taxonguru 시트의 기본 A:H 열이 부족합니다.")

    existing_species = {
        str(row[1]).strip()
        for row in records[1:]
        if len(row) > 1 and str(row[1]).strip()
    }
    existing_slugs = {
        normalize_slug(str(row[6]))
        for row in records[1:]
        if len(row) > 6 and str(row[6]).strip()
    }

    collected: list[TopicCandidate] = []
    for attempt in range(1, 4):
        needed = TOPIC_COUNT - len(collected)
        if needed <= 0:
            break
        log(f"🔎 후보 생성·GBIF 검증 {attempt}/3 · 남은 목표 {needed}건")
        try:
            batch = generate_candidates(existing_species, existing_slugs, needed)
            collected.extend(batch)
        except Exception as exc:
            log(f"⚠️ 주제 생성 재시도: {' '.join(str(exc).split())[:500]}")
        time.sleep(attempt)

    if not collected:
        raise RuntimeError("검증된 신규 주제를 만들지 못했습니다.")

    rows = []
    for topic in collected[:TOPIC_COUNT]:
        rows.append(
            [
                "대기",
                topic.scientific_name,
                topic.display_title.strip(),
                topic.taxonomy.strip(),
                topic.category,
                topic.story_angle.strip(),
                topic.slug,
                ", ".join(topic.tags),
            ]
        )
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    log(f"✅ 검증된 신규 주제 {len(rows)}건을 대기 상태로 추가했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
