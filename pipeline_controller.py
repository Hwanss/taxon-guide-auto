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
# TaxonGuru Master Controller v6 · AdSense Recovery
#
# Priority
# 1) Sync already scheduled posts.
# 2) Automatically migrate old '기존비공개완료' rows into the rewrite queue.
# 3) Rewrite one queued legacy post and reserve it in the next free KO/EN slots.
# 4) Audit recent rows whose status is exactly '완료'. A/B/C/D decisions never
#    permanently delete content; unsafe posts are drafts and are queued for rewrite.
# 5) Wait until legacy rewrite reservations have actually published.
# 6) Repair incomplete English versions.
# 7) Only then create a new waiting topic; refill topics when the queue is low.
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
LEGACY_BATCH_SIZE = max(1, min(10, int(os.getenv("LEGACY_BATCH_SIZE", "1"))))
TOPIC_REFILL_THRESHOLD = max(0, int(os.getenv("TOPIC_REFILL_THRESHOLD", "10")))
TOPIC_REFILL_COUNT = max(1, min(30, int(os.getenv("TOPIC_REFILL_COUNT", "12"))))
NEW_WINDOW_START_HOUR = int(os.getenv("NEW_WINDOW_START_HOUR", "2"))
NEW_WINDOW_END_HOUR = int(os.getenv("NEW_WINDOW_END_HOUR", "7"))
FORCE_PHASE = os.getenv("FORCE_PHASE", "auto").strip().lower()
FORCE_NEW_NOW = os.getenv("FORCE_NEW_NOW", "false").lower() == "true"
ADSENSE_RECOVERY_MODE = os.getenv("ADSENSE_RECOVERY_MODE", "false").lower() == "true"
MANUAL_REVIEW_REQUIRED = os.getenv("MANUAL_REVIEW_REQUIRED", "false").lower() == "true" or ADSENSE_RECOVERY_MODE
FORCE_IPV4 = os.getenv("FORCE_IPV4", "true").lower() == "true"
REQUEST_TIMEOUT = max(15, int(os.getenv("REQUEST_TIMEOUT", "45")))
WP_CONNECT_RETRIES = max(1, int(os.getenv("WP_CONNECT_RETRIES", "5")))
WP_CONNECT_RETRY_DELAY = max(1.0, float(os.getenv("WP_CONNECT_RETRY_DELAY", "3")))

if FORCE_IPV4:
    urllib3_connection.HAS_IPV6 = False

KST = ZoneInfo(TIMEZONE_NAME)
LEGACY_REWRITE_STATES = {"기존재작성대기", "기존재작성재시도"}
LEGACY_SCHEDULED_STATES = {
    "기존한영재예약완료",
    "기존재예약완료",
    "기존한국어재예약/영문검수필요",
    "기존한국어공개/영문재예약",
}
ENGLISH_REPAIR_STATES = {
    "한국어예약/영문검수필요",
    "한국어완료/영문검수필요",
}
MANUAL_REVIEW_STATES = {
    "수동검수대기",
    "기존수동검수대기",
    "한국어완료/영문수동검수대기",
}


def log(message: str) -> None:
    print(message, flush=True)


def normalize_header(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def find_header(headers: list[str], aliases: list[str]) -> int | None:
    normalized = [normalize_header(h) for h in headers]
    for alias in aliases:
        key = normalize_header(alias)
        if key in normalized:
            return normalized.index(key)
    return None


def safe_int(value: Any) -> int | None:
    try:
        number = int(str(value).strip())
        return number if number > 0 else None
    except Exception:
        return None


def connect_book() -> tuple[gspread.Spreadsheet, gspread.Worksheet, gspread.Worksheet]:
    creds = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds)
    book = gc.open_by_key(SHEET_ID)
    topic_ws = book.worksheet(SHEET_NAME)
    try:
        control_ws = book.worksheet(CONTROL_SHEET_NAME)
    except gspread.WorksheetNotFound:
        control_ws = book.add_worksheet(title=CONTROL_SHEET_NAME, rows=40, cols=2)
    return book, topic_ws, control_ws


def read_sheet(topic_ws: gspread.Worksheet) -> tuple[list[str], list[list[str]], Counter[str]]:
    values = topic_ws.get_all_values()
    if not values:
        return [], [], Counter()
    headers = values[0]
    status_index = find_header(headers, ["상태", "진행상태"])
    if status_index is None:
        raise RuntimeError("taxonguru 시트 1행에서 '상태' 헤더를 찾지 못했습니다.")
    statuses: list[str] = []
    for row in values[1:]:
        status = row[status_index].strip() if status_index < len(row) else ""
        if status:
            statuses.append(status)
    return headers, values[1:], Counter(statuses)


def batch_update_statuses(
    topic_ws: gspread.Worksheet,
    headers: list[str],
    rows: list[list[str]],
) -> int:
    """Migrate old terminal private rows without requiring user edits.

    A row is requeued only when it has a scientific name and an existing Korean
    post ID. Otherwise it remains safely hidden as '기존비공개보류'.
    """
    status_idx = find_header(headers, ["상태"])
    sci_idx = find_header(headers, ["학명", "학명(Scientific Name)", "학명 (Scientific Name)"])
    post_idx = find_header(headers, ["WP_POST_ID", "WP POST ID"])
    note_idx = find_header(headers, ["정리메모", "정리 메모"])
    error_idx = find_header(headers, ["오류", "에러"])
    if status_idx is None:
        return 0

    cells: list[gspread.Cell] = []
    migrated = 0
    for row_number, row in enumerate(rows, start=2):
        status = row[status_idx].strip() if status_idx < len(row) else ""
        if status != "기존비공개완료":
            continue
        scientific_name = row[sci_idx].strip() if sci_idx is not None and sci_idx < len(row) else ""
        post_id = safe_int(row[post_idx]) if post_idx is not None and post_idx < len(row) else None
        next_status = "기존재작성대기" if scientific_name and post_id else "기존비공개보류"
        cells.append(gspread.Cell(row_number, status_idx + 1, next_status))
        if note_idx is not None:
            cells.append(
                gspread.Cell(
                    row_number,
                    note_idx + 1,
                    "기존 비공개 글 자동 재작성 대기열 편입" if next_status == "기존재작성대기" else "자동 재작성에 필요한 학명 또는 게시물 ID 없음",
                )
            )
        if error_idx is not None and next_status == "기존재작성대기":
            cells.append(gspread.Cell(row_number, error_idx + 1, ""))
        migrated += 1
    if cells:
        topic_ws.update_cells(cells, value_input_option="USER_ENTERED")
    return migrated


def _row_value(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index]).strip()


def _wp_post_status(post_id: int) -> str:
    try:
        response = requests.get(
            f"{WP_SITE_URL}/wp-json/wp/v2/posts/{post_id}",
            params={"context": "edit", "_fields": "id,status,link"},
            auth=(WP_USER, WP_APP_PASSWORD),
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "TaxonGuruMasterController/5.0"},
        )
        if response.status_code == 200:
            return str(response.json().get("status", "")).strip()
        if response.status_code == 404:
            return "missing"
        return f"http_{response.status_code}"
    except Exception as exc:
        return f"error:{' '.join(str(exc).split())[:180]}"


def recover_known_cleanup_errors(
    topic_ws: gspread.Worksheet,
    headers: list[str],
    rows: list[list[str]],
) -> dict[str, int]:
    """Recover the v4 cleanup_note header-mapping bug without user edits.

    v4 successfully moved many WordPress posts to draft, but then failed while
    writing the Google-Sheets field ``cleanup_note`` because that logical alias
    was missing in audit_existing_posts.py. Those rows were left as
    ``기존정리오류`` even though they are safe to retry.

    Already repaired/published bilingual rows are preserved rather than rewritten.
    """
    status_idx = find_header(headers, ["상태"])
    sci_idx = find_header(headers, ["학명", "학명(Scientific Name)", "학명 (Scientific Name)"])
    post_idx = find_header(headers, ["WP_POST_ID", "WP POST ID"])
    en_post_idx = find_header(headers, ["EN_POST_ID", "영문 WP_POST_ID"])
    note_idx = find_header(headers, ["정리메모", "정리 메모"])
    error_idx = find_header(headers, ["오류", "에러"])
    attempt_idx = find_header(headers, ["재작성시도", "재작성 시도"])

    result = {"requeued": 0, "published": 0, "scheduled": 0, "held": 0}
    if status_idx is None:
        return result

    cells: list[gspread.Cell] = []
    for row_number, row in enumerate(rows, start=2):
        status = _row_value(row, status_idx)
        if status != "기존정리오류":
            continue
        error_text = _row_value(row, error_idx)
        # Only auto-recover the known v4 bug. Other cleanup errors stay visible.
        if "cleanup_note" not in error_text:
            continue

        scientific_name = _row_value(row, sci_idx)
        post_id = safe_int(_row_value(row, post_idx))
        en_post_id = safe_int(_row_value(row, en_post_idx))
        note = _row_value(row, note_idx)

        next_status = "기존비공개보류"
        next_note = "v5 자동복구: cleanup_note 오류였으나 재작성에 필요한 학명 또는 게시물 ID가 없습니다."

        # One row may have been fully rewritten before the sheet write failed.
        # Preserve it if WordPress says the repaired posts are already live/future.
        if scientific_name and post_id:
            ko_status = _wp_post_status(post_id)
            en_status = _wp_post_status(en_post_id) if en_post_id else ""
            if en_post_id and ko_status == "publish" and en_status == "publish":
                next_status = "기존한영수정완료"
                next_note = "v5 자동복구: 기존 재작성 글의 한·영 공개 상태를 확인하여 완료 처리했습니다."
                result["published"] += 1
            elif en_post_id and ko_status == "future" and en_status == "future":
                next_status = "기존한영재예약완료"
                next_note = "v5 자동복구: 기존 재작성 글의 한·영 예약 상태를 확인했습니다."
                result["scheduled"] += 1
            elif en_post_id and ko_status == "publish" and en_status == "future":
                next_status = "기존한국어공개/영문재예약"
                next_note = "v5 자동복구: 한국어 공개·영문 예약 상태를 확인했습니다."
                result["scheduled"] += 1
            else:
                next_status = "기존재작성대기"
                next_note = f"v5 자동복구: cleanup_note 헤더 매핑 오류 복구. WordPress KO={ko_status}, EN={en_status or '-'}"
                result["requeued"] += 1
        else:
            result["held"] += 1

        cells.append(gspread.Cell(row_number, status_idx + 1, next_status))
        if note_idx is not None:
            cells.append(gspread.Cell(row_number, note_idx + 1, next_note))
        if error_idx is not None:
            cells.append(gspread.Cell(row_number, error_idx + 1, ""))
        if attempt_idx is not None and next_status == "기존재작성대기" and not _row_value(row, attempt_idx):
            cells.append(gspread.Cell(row_number, attempt_idx + 1, "0"))

    if cells:
        topic_ws.update_cells(cells, value_input_option="USER_ENTERED")
    return result


def update_control(control_ws: gspread.Worksheet, **data: Any) -> None:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")
    rows = [["항목", "값"], ["최근실행", now]]
    rows.extend([[str(key), str(value)] for key, value in data.items()])
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
                headers={"User-Agent": "TaxonGuruMasterController/5.0"},
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


def count_any(counts: Counter[str], states: set[str]) -> int:
    return sum(counts.get(state, 0) for state in states)


def summary_values(counts: Counter[str]) -> dict[str, Any]:
    return {
        "기존완료잔여": counts.get(LEGACY_TARGET_STATUS, 0),
        "기존재작성대기": count_any(counts, LEGACY_REWRITE_STATES),
        "기존재예약대기": count_any(counts, LEGACY_SCHEDULED_STATES),
        "기존비공개보류": counts.get("기존비공개보류", 0),
        "기존정리오류": counts.get("기존정리오류", 0),
        "한영예약완료보존": counts.get("한영예약완료", 0),
        "대기주제": counts.get("대기", 0),
        "영문재검수": count_any(counts, ENGLISH_REPAIR_STATES),
        "수동검수대기": count_any(counts, MANUAL_REVIEW_STATES),
    }


def sync_reservations(topic_ws: gspread.Worksheet, control_ws: gspread.Worksheet) -> int:
    code = run_script(
        "WordPress 예약 상태 동기화",
        "main.py",
        {
            "PROCESS_MODE": "sync_only",
            "FORCE_IPV4": "true",
            "ADSENSE_RECOVERY_MODE": "true" if ADSENSE_RECOVERY_MODE else "false",
            "MANUAL_REVIEW_REQUIRED": "true" if MANUAL_REVIEW_REQUIRED else "false",
        },
    )
    if code != 0:
        _, _, counts = read_sheet(topic_ws)
        update_control(
            control_ws,
            단계="예약동기화오류",
            결과=f"main.py 종료코드 {code}",
            **summary_values(counts),
            다음작업="다음 자동 실행에서 재시도",
            오류="예약 상태 동기화 로그 확인",
        )
    return code


def process_one_legacy_rewrite(topic_ws: gspread.Worksheet, control_ws: gspread.Worksheet) -> int:
    _, _, before = read_sheet(topic_ws)
    update_control(
        control_ws,
        단계="기존글자동재작성",
        결과="비공개된 기존 글 1건을 한·영으로 재작성하고 다음 빈 순번에 예약합니다.",
        **summary_values(before),
        다음작업="main.py PROCESS_MODE=legacy_rewrite",
        오류="",
    )
    code = run_script(
        "기존 비공개 글 자동 재작성·재예약",
        "main.py",
        {
            "PROCESS_MODE": "legacy_rewrite",
            "FORCE_IPV4": "true",
            "ENABLE_ENGLISH": "true",
            "AUTO_SCHEDULE": "false" if MANUAL_REVIEW_REQUIRED else "true",
            "ADSENSE_RECOVERY_MODE": "true" if ADSENSE_RECOVERY_MODE else "false",
            "MANUAL_REVIEW_REQUIRED": "true" if MANUAL_REVIEW_REQUIRED else "false",
        },
    )
    _, _, after = read_sheet(topic_ws)
    update_control(
        control_ws,
        단계="기존글자동재작성" if count_any(after, LEGACY_REWRITE_STATES) else "기존재작성대기열소진",
        결과="정상 처리" if code == 0 else f"종료코드 {code}",
        **summary_values(after),
        다음작업="다음 자동 실행에서 계속" if count_any(after, LEGACY_REWRITE_STATES) else "기존 완료 글 감사 또는 예약 발행 대기",
        오류="" if code == 0 else "main.py 로그 확인",
    )
    return code


def main() -> int:
    log("=" * 76)
    log("TaxonGuru Master v6: AdSense 복구 → 기존 감사 → 안전 재작성 → 사람 검수 대기")
    log(
        f"기존 감사 대상='{LEGACY_TARGET_STATUS}' 정확히 일치 · 감사 회당 {LEGACY_BATCH_SIZE}건 · "
        f"재작성 최대 {os.getenv('MAX_LEGACY_REWRITE_ATTEMPTS', '3')}회 · "
        f"AdSense 복구={'ON' if ADSENSE_RECOVERY_MODE else 'OFF'} · 사람검수={'필수' if MANUAL_REVIEW_REQUIRED else '선택'}"
    )
    log("=" * 76)

    _, topic_ws, control_ws = connect_book()
    headers, rows, counts = read_sheet(topic_ws)
    migrated = batch_update_statuses(topic_ws, headers, rows)
    if migrated:
        log(f"🔁 기존비공개완료 {migrated}건을 자동 재작성대기/비공개보류로 전환했습니다.")
        headers, rows, counts = read_sheet(topic_ws)

    wp_ok, wp_message = preflight_wordpress()
    if not wp_ok:
        update_control(
            control_ws,
            단계="연결대기",
            결과="WordPress 연결 실패로 이번 실행을 보류했습니다.",
            **summary_values(counts),
            다음작업="다음 예약 실행에서 자동 재시도",
            오류=wp_message,
        )
        log(f"⚠️ {wp_message}")
        return 0

    # Self-heal rows stranded by the v4 cleanup_note sheet-mapping bug.
    recovery = recover_known_cleanup_errors(topic_ws, headers, rows)
    recovered_total = sum(recovery.values())
    if recovered_total:
        log(
            "🛠️ 기존정리오류 자동복구: "
            f"재작성대기 {recovery['requeued']} / 이미공개완료 {recovery['published']} / "
            f"예약복구 {recovery['scheduled']} / 보류 {recovery['held']}"
        )
        headers, rows, counts = read_sheet(topic_ws)

    # Always synchronize future→publish before deciding the next phase.
    if sync_reservations(topic_ws, control_ws) != 0:
        return 0
    headers, rows, counts = read_sheet(topic_ws)

    if FORCE_PHASE == "status_only":
        update_control(control_ws, 단계="상태확인", 결과="변경 없이 상태만 확인했습니다.", **summary_values(counts), 다음작업="자동 운영", 오류="")
        return 0

    if FORCE_PHASE == "readiness":
        update_control(
            control_ws,
            단계="애드센스준비도검사",
            결과="필수 페이지, ads.txt, 공개 글 링크/언어 이상을 검사합니다.",
            **summary_values(counts),
            다음작업="site_readiness.py",
            오류="",
        )
        return run_script(
            "AdSense 재심사 준비도 검사",
            "site_readiness.py",
            {"FORCE_IPV4": "true", "READINESS_APPLY_SAFE_FIXES": "true"},
        )

    # 1) Existing rewrite queue has absolute priority.
    if FORCE_PHASE in {"auto", "cleanup"} and count_any(counts, LEGACY_REWRITE_STATES) > 0:
        return process_one_legacy_rewrite(topic_ws, control_ws)

    # 2) Audit recent exact-'완료' legacy posts. The audit queues B/C/D posts.
    legacy_remaining = counts.get(LEGACY_TARGET_STATUS, 0)
    if FORCE_PHASE == "cleanup" or (FORCE_PHASE == "auto" and legacy_remaining > 0):
        update_control(
            control_ws,
            단계="기존자료감사",
            결과="최근 기존 글을 감사하고 유지 또는 자동 재작성 대기열로 분류합니다.",
            **summary_values(counts),
            다음작업=f"최근 {min(LEGACY_BATCH_SIZE, legacy_remaining)}건 감사",
            오류="",
        )
        code = run_script(
            "기존 완료 게시물 감사·대기열 분류",
            "audit_existing_posts.py",
            {
                "AUDIT_MODE": "rewrite_recent",
                "AUDIT_BATCH_SIZE": str(LEGACY_BATCH_SIZE),
                "AUDIT_TARGET_STATUS": LEGACY_TARGET_STATUS,
                "AUTO_CLEANUP_MODE": "true",
                "AUTO_FAIL_CLOSED_DRAFT": "true",
                "AUTO_TRASH_GRADE_D": "false",
                "QUEUE_GRADE_D_FOR_REWRITE": "true",
                "INCLUDE_ALREADY_AUDITED": "true",
                "AUDIT_CREATE_ENGLISH": "false",
                "AUDIT_DRAFT_GRADE_D": "true",
                "AUDIT_INCLUDE_ENGLISH_POSTS": "false",
                "FORCE_IPV4": "true",
                "ADSENSE_RECOVERY_MODE": "true" if ADSENSE_RECOVERY_MODE else "false",
            },
        )
        _, _, after = read_sheet(topic_ws)
        if code == 0 and count_any(after, LEGACY_REWRITE_STATES) > 0:
            # Complete one full audit→rewrite cycle in the same workflow run.
            return process_one_legacy_rewrite(topic_ws, control_ws)
        update_control(
            control_ws,
            단계="기존자료감사" if after.get(LEGACY_TARGET_STATUS, 0) else "기존자료감사완료",
            결과="정상 처리" if code == 0 else f"감사 종료코드 {code}",
            **summary_values(after),
            다음작업="다음 자동 실행에서 계속",
            오류="" if code == 0 else "audit_existing_posts.py 로그 확인",
        )
        return code

    if FORCE_PHASE == "cleanup":
        update_control(control_ws, 단계="기존정리완료", 결과="감사·재작성 대기 대상이 없습니다.", **summary_values(counts), 다음작업="수동검수 또는 준비도 검사", 오류="")
        return 0

    # 3) AdSense recovery mode intentionally stops all new/automatic publication.
    if ADSENSE_RECOVERY_MODE:
        update_control(
            control_ws,
            단계="애드센스복구모드",
            결과="기존 공개 글 감사가 완료되었습니다. 신규 자동발행은 중지되어 있습니다.",
            **summary_values(counts),
            다음작업="WordPress 초안의 수동검수 → 준비도 검사(readiness) → AdSense 재검토",
            오류="",
        )
        log("🛡️ AdSense 복구모드: 신규 주제 생성·자동 예약발행을 실행하지 않습니다.")
        return 0

    # 4) Do not start new work until repaired legacy reservations are published.
    if count_any(counts, LEGACY_SCHEDULED_STATES) > 0:
        update_control(
            control_ws,
            단계="기존재작성예약발행대기",
            결과="재작성된 기존 글이 다음 순번에 예약되어 실제 발행을 기다리고 있습니다.",
            **summary_values(counts),
            다음작업="예약일 발행 후 자동으로 기존한영수정완료 전환",
            오류="",
        )
        return 0

    # 4) Repair ordinary English failures before generating new topics.
    if count_any(counts, ENGLISH_REPAIR_STATES) > 0:
        update_control(control_ws, 단계="영문복구", 결과="한국어 완료 글의 영문판을 자동 복구합니다.", **summary_values(counts), 다음작업="main.py PROCESS_MODE=english_retry", 오류="")
        code = run_script(
            "영문판 자동 복구",
            "main.py",
            {
                "PROCESS_MODE": "english_retry", "FORCE_IPV4": "true", "ENABLE_ENGLISH": "true",
                "AUTO_SCHEDULE": "false" if MANUAL_REVIEW_REQUIRED else "true",
                "MANUAL_REVIEW_REQUIRED": "true" if MANUAL_REVIEW_REQUIRED else "false",
            },
        )
        return code

    # 5) New publishing only in the configured morning window.
    if not new_publish_window_open():
        update_control(
            control_ws,
            단계="신규작성대기",
            결과="기존 정리가 끝났습니다. 신규 작성 허용 시간까지 대기합니다.",
            **summary_values(counts),
            다음작업=f"{NEW_WINDOW_START_HOUR:02d}:00~{NEW_WINDOW_END_HOUR:02d}:00 {TIMEZONE_NAME}",
            오류="",
        )
        return 0

    if counts.get("대기", 0) == 0:
        code = run_script("대기 주제 자동 보충", "generate_topics.py", {"TOPIC_COUNT": str(TOPIC_REFILL_COUNT)})
        if code != 0:
            update_control(control_ws, 단계="주제보충오류", 결과=f"종료코드 {code}", **summary_values(counts), 다음작업="다음 실행에서 재시도", 오류="generate_topics.py 실패")
            return code
        _, _, counts = read_sheet(topic_ws)

    update_control(control_ws, 단계="신규한영작성", 결과="대기 주제 1건을 작성·검수·예약합니다.", **summary_values(counts), 다음작업="main.py PROCESS_MODE=new", 오류="")
    code = run_script(
        "신규 한·영 게시물 작성",
        "main.py",
        {
            "PROCESS_MODE": "new", "FORCE_IPV4": "true", "ENABLE_ENGLISH": "true",
            "AUTO_SCHEDULE": "false" if MANUAL_REVIEW_REQUIRED else "true",
            "MANUAL_REVIEW_REQUIRED": "true" if MANUAL_REVIEW_REQUIRED else "false",
        },
    )
    _, _, after = read_sheet(topic_ws)
    if code == 0 and after.get("대기", 0) < TOPIC_REFILL_THRESHOLD:
        refill_code = run_script("주제 목록 자동 보충", "generate_topics.py", {"TOPIC_COUNT": str(TOPIC_REFILL_COUNT)})
        if refill_code != 0:
            log(f"⚠️ 신규 작성은 완료됐지만 주제 보충은 실패했습니다: {refill_code}")
        _, _, after = read_sheet(topic_ws)

    update_control(
        control_ws,
        단계="신규자동운영",
        결과="신규 1건 처리 완료" if code == 0 else f"신규 작성 종료코드 {code}",
        **summary_values(after),
        다음작업="다음 오전 자동 실행",
        오류="" if code == 0 else "main.py 로그 확인",
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
