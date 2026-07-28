from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import gspread
import requests
import urllib3.util.connection as urllib3_connection

# =============================================================================
# TaxonGuru Master Controller
# 1) Google Sheets 상태가 정확히 '완료'인 기존 글만 최근순으로 정리
# 2) '한영예약완료' 및 다른 상태는 기존 정리 단계에서 건드리지 않음
# 3) '완료'가 0건이 되면 신규 한·영 작성 단계로 자동 전환
# 4) 대기 주제가 기준보다 적어지면 주제 목록을 자동 보충
# =============================================================================

WP_SITE_URL = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
SHEET_ID = os.environ["SHEET_ID"]
SHEET_NAME = os.getenv("SHEET_NAME", "taxonguru")
CONTROL_SHEET_NAME = os.getenv("CONTROL_SHEET_NAME", "파이프라인상태")
TIMEZONE_NAME = os.getenv("SCHEDULE_TIMEZONE", "Asia/Seoul")

LEGACY_TARGET_STATUS = os.getenv("LEGACY_TARGET_STATUS", "완료").strip()
LEGACY_BATCH_SIZE = max(1, min(10, int(os.getenv("LEGACY_BATCH_SIZE", "2"))))
TOPIC_REFILL_THRESHOLD = max(0, int(os.getenv("TOPIC_REFILL_THRESHOLD", "10")))
TOPIC_REFILL_COUNT = max(1, min(30, int(os.getenv("TOPIC_REFILL_COUNT", "12"))))
NEW_WINDOW_START_HOUR = int(os.getenv("NEW_WINDOW_START_HOUR", "2"))
NEW_WINDOW_END_HOUR = int(os.getenv("NEW_WINDOW_END_HOUR", "7"))
FORCE_PHASE = os.getenv("FORCE_PHASE", "auto").strip().lower()
FORCE_NEW_NOW = os.getenv("FORCE_NEW_NOW", "false").lower() == "true"
FORCE_IPV4 = os.getenv("FORCE_IPV4", "true").lower() == "true"
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))
WP_CONNECT_RETRIES = max(1, int(os.getenv("WP_CONNECT_RETRIES", "5")))
WP_CONNECT_RETRY_DELAY = max(1.0, float(os.getenv("WP_CONNECT_RETRY_DELAY", "3")))

if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False

KST = ZoneInfo(TIMEZONE_NAME)
REPAIR_STATUSES = {
    "한국어예약/영문검수필요",
    "한국어완료/영문검수필요",
    "검수필요",
    "재작성",
}


def log(message: str) -> None:
    print(message, flush=True)


def normalize_header(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def connect_book() -> tuple[gspread.Spreadsheet, gspread.Worksheet, gspread.Worksheet]:
    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    book = gc.open_by_key(SHEET_ID)
    topic_ws = book.worksheet(SHEET_NAME)
    try:
        control_ws = book.worksheet(CONTROL_SHEET_NAME)
    except gspread.WorksheetNotFound:
        control_ws = book.add_worksheet(title=CONTROL_SHEET_NAME, rows=30, cols=2)
    return book, topic_ws, control_ws


def read_status_counts(topic_ws: gspread.Worksheet) -> tuple[Counter[str], list[str]]:
    values = topic_ws.get_all_values()
    if not values:
        return Counter(), []
    headers = values[0]
    normalized = [normalize_header(h) for h in headers]
    try:
        status_index = normalized.index(normalize_header("상태"))
    except ValueError as exc:
        raise RuntimeError("taxonguru 시트 1행에서 '상태' 헤더를 찾지 못했습니다.") from exc
    statuses: list[str] = []
    for row in values[1:]:
        value = str(row[status_index]).strip() if status_index < len(row) else ""
        if value:
            statuses.append(value)
    return Counter(statuses), headers


def update_control(control_ws: gspread.Worksheet, **data: Any) -> None:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")
    rows = [["항목", "값"], ["최근실행", now]]
    for key, value in data.items():
        rows.append([str(key), str(value)])
    control_ws.clear()
    control_ws.update("A1", rows, value_input_option="USER_ENTERED")


def preflight_wordpress() -> tuple[bool, str]:
    url = f"{WP_SITE_URL}/wp-json/wp/v2/posts"
    last_error = ""
    for attempt in range(1, WP_CONNECT_RETRIES + 1):
        try:
            response = requests.get(
                url,
                params={"per_page": 1, "context": "edit", "_fields": "id,status,modified"},
                auth=(WP_USER, WP_APP_PASSWORD),
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "TaxonGuruMasterController/2.0"},
            )
            if response.status_code == 200:
                return True, "WordPress REST 연결 정상"
            if response.status_code in {401, 403}:
                return False, f"WordPress 인증 실패 HTTP {response.status_code}: {response.text[:300]}"
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:
            last_error = " ".join(str(exc).split())[:600]
        if attempt < WP_CONNECT_RETRIES:
            time.sleep(WP_CONNECT_RETRY_DELAY * attempt)
    return False, last_error


def run_script(label: str, script: str, extra_env: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    log(f"\n▶ {label}: python {script}")
    process = subprocess.Popen([sys.executable, script], env=env)
    return process.wait()


def new_publish_window_open() -> bool:
    if FORCE_NEW_NOW or FORCE_PHASE == "new":
        return True
    hour = datetime.now(KST).hour
    return NEW_WINDOW_START_HOUR <= hour < NEW_WINDOW_END_HOUR


def summary_values(counts: Counter[str]) -> dict[str, Any]:
    return {
        "기존완료잔여": counts.get(LEGACY_TARGET_STATUS, 0),
        "한영예약완료보존": counts.get("한영예약완료", 0),
        "대기주제": counts.get("대기", 0),
        "영문재검수등": sum(counts.get(status, 0) for status in REPAIR_STATUSES),
    }


def main() -> int:
    log("=" * 72)
    log("TaxonGuru 마스터 자동 운영: 기존 완료 정리 → 신규 한·영 작성 → 주제 보충")
    log(
        f"기존대상='{LEGACY_TARGET_STATUS}' 정확히 일치 · 회당 {LEGACY_BATCH_SIZE}건 · "
        f"대기 {TOPIC_REFILL_THRESHOLD}건 미만이면 {TOPIC_REFILL_COUNT}건 보충"
    )
    log("=" * 72)

    _, topic_ws, control_ws = connect_book()
    counts, _ = read_status_counts(topic_ws)
    values = summary_values(counts)

    wp_ok, wp_message = preflight_wordpress()
    if not wp_ok:
        update_control(
            control_ws,
            단계="연결대기",
            결과="WordPress 연결 실패로 이번 실행을 보류했습니다. 다음 예약 실행에서 자동 재시도합니다.",
            **values,
            다음작업="자동 재시도",
            오류=wp_message,
        )
        log(f"⚠️ {wp_message}")
        return 0

    legacy_remaining = counts.get(LEGACY_TARGET_STATUS, 0)

    # ------------------------------------------------------------------
    # Phase 1: exact status '완료' only. Other statuses are untouched.
    # ------------------------------------------------------------------
    if FORCE_PHASE == "cleanup" or (FORCE_PHASE == "auto" and legacy_remaining > 0):
        update_control(
            control_ws,
            단계="기존자료정리",
            결과="기존 완료 글을 최근순으로 감사·수정 중",
            **values,
            다음작업=f"최근 글 {min(LEGACY_BATCH_SIZE, legacy_remaining)}건 처리",
            오류="",
        )
        code = run_script(
            "기존 완료 게시물 감사·수정",
            "audit_existing_posts.py",
            {
                "AUDIT_MODE": "rewrite_recent",
                "AUDIT_BATCH_SIZE": str(LEGACY_BATCH_SIZE),
                "AUDIT_TARGET_STATUS": LEGACY_TARGET_STATUS,
                "AUTO_CLEANUP_MODE": "true",
                "AUTO_FAIL_CLOSED_DRAFT": "true",
                "AUTO_TRASH_GRADE_D": "false",
                "INCLUDE_ALREADY_AUDITED": "true",
                "AUDIT_CREATE_ENGLISH": "true",
                "AUDIT_DRAFT_GRADE_D": "true",
                "AUDIT_INCLUDE_ENGLISH_POSTS": "false",
                "FORCE_IPV4": "true",
            },
        )
        counts_after, _ = read_status_counts(topic_ws)
        after_values = summary_values(counts_after)
        update_control(
            control_ws,
            단계="기존자료정리" if counts_after.get(LEGACY_TARGET_STATUS, 0) else "기존자료정리완료",
            결과="정상 처리" if code == 0 else f"감사 스크립트 종료코드 {code}",
            **after_values,
            다음작업=(
                "다음 예약 실행에서 기존 완료 글 계속 처리"
                if counts_after.get(LEGACY_TARGET_STATUS, 0)
                else "다음 오전 실행부터 신규 한·영 작성 시작"
            ),
            오류="" if code == 0 else "audit_existing_posts.py 로그 확인",
        )
        return code

    if FORCE_PHASE == "cleanup" and legacy_remaining == 0:
        update_control(control_ws, 단계="기존자료정리완료", 결과="처리할 완료 상태가 없습니다.", **values, 다음작업="신규단계", 오류="")
        return 0

    # ------------------------------------------------------------------
    # Phase 2: one new/retry item per morning. Afternoon schedule only monitors.
    # ------------------------------------------------------------------
    if FORCE_PHASE == "status_only" or not new_publish_window_open():
        update_control(
            control_ws,
            단계="신규작성대기",
            결과="기존 완료 글 정리가 끝났습니다. 신규 작성 허용 시간까지 대기합니다.",
            **values,
            다음작업=f"{NEW_WINDOW_START_HOUR:02d}:00~{NEW_WINDOW_END_HOUR:02d}:00 {TIMEZONE_NAME} 자동 실행",
            오류="",
        )
        log("ℹ️ 신규 작성 시간대가 아니므로 상태만 확인하고 종료합니다.")
        return 0

    # No waiting topics: refill before running main.py.
    if counts.get("대기", 0) == 0 and sum(counts.get(status, 0) for status in REPAIR_STATUSES) == 0:
        code = run_script(
            "대기 주제 자동 보충",
            "generate_topics.py",
            {"TOPIC_COUNT": str(TOPIC_REFILL_COUNT)},
        )
        if code != 0:
            update_control(control_ws, 단계="주제보충오류", 결과=f"종료코드 {code}", **values, 다음작업="다음 예약 실행에서 재시도", 오류="generate_topics.py 실패")
            return code
        counts, _ = read_status_counts(topic_ws)

    update_control(
        control_ws,
        단계="신규한영작성",
        결과="대기 또는 재검수 항목 1건 처리 중",
        **summary_values(counts),
        다음작업="main.py 실행",
        오류="",
    )
    code = run_script(
        "신규/재검수 한·영 게시물 작성",
        "main.py",
        {
            "FORCE_IPV4": "true",
            "ENABLE_ENGLISH": "true",
            "AUTO_SCHEDULE": "true",
        },
    )
    if code != 0:
        counts_after, _ = read_status_counts(topic_ws)
        update_control(
            control_ws,
            단계="신규작성오류",
            결과=f"main.py 종료코드 {code}",
            **summary_values(counts_after),
            다음작업="다음 오전 예약 실행에서 자동 재시도",
            오류="main.py 실행 로그 확인",
        )
        return code

    counts_after, _ = read_status_counts(topic_ws)
    if counts_after.get("대기", 0) < TOPIC_REFILL_THRESHOLD:
        refill_code = run_script(
            "주제 목록 자동 보충",
            "generate_topics.py",
            {"TOPIC_COUNT": str(TOPIC_REFILL_COUNT)},
        )
        if refill_code != 0:
            log(f"⚠️ 게시물 작성은 완료됐지만 주제 보충은 실패했습니다: {refill_code}")
        counts_after, _ = read_status_counts(topic_ws)

    update_control(
        control_ws,
        단계="신규자동운영",
        결과="신규/재검수 1건 처리 완료",
        **summary_values(counts_after),
        다음작업="다음 오전에 1건 자동 작성",
        오류="",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
