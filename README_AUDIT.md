# TaxonGuru 기존 콘텐츠 감사·수정 전용 Action

## 목적

- 신규 글 자동작성과 주제 자동추가를 잠시 중지
- 공개 글을 **최근 수정일 순서**로 감사
- 원본 JSON을 매번 백업
- Google Sheets에 `콘텐츠감사` 탭을 자동 생성
- A/B/C/D 등급 및 권장조치 기록
- 삭제는 기본적으로 자동 수행하지 않음

## 설치 파일

저장소에 다음 파일을 같은 경로로 업로드합니다.

```text
audit_existing_posts.py
.github/workflows/audit.yml
.github/workflows/schedule.yml
.github/workflows/generate_topics.yml
```

기존 `main.py`, `requirements.txt`, WordPress 플러그인은 유지합니다.

## 권장 실행 순서

### 1차: 보고서만

Actions → `TaxonGuru Content Audit & Repair` → Run workflow

- mode: `report_only`
- batch_size: `3`
- include_already_audited: 꺼짐
- create_english: 켜짐
- draft_grade_d: 꺼짐

게시물은 변경되지 않습니다. Artifacts와 Google Sheets `콘텐츠감사` 탭을 확인합니다.

### 2차: 안전한 구조 보완

- mode: `safe_fix`
- batch_size: 3~5

자동검수 공개 문구 제거, 과장된 가상 직함 중립화, 본문 이미지 표시 크기 표준화만 수행합니다.

### 3차: 최신 글부터 전면 재작성

- mode: `rewrite_recent`
- 처음에는 batch_size `1`
- create_english: 켜짐
- draft_grade_d: 꺼짐

B/C 등급만 최신 자료로 재조사하고 기존 한국어 URL을 유지한 채 갱신합니다. 영어 글은 별도 URL로 생성·연결합니다.
A등급은 유지하고 D등급은 삭제하지 않고 검토 대상으로만 표시합니다.

## Actions 4개를 모두 실행해야 하나요?

아닙니다.

- `TaxonGuru Content Audit & Repair`: 기존 글 정리 중 사용하는 핵심 Action
- `Create Editorial Pages`: 소개/편집정책 페이지가 없을 때 한 번만 실행
- `TaxonGuru Bilingual Story Auto-Publish (PAUSED)`: 지금은 실행하지 않음. 나중에 신규 발행 재개 시 사용
- `TaxonGuru Topic Planner (PAUSED)`: 대기 주제가 부족할 때만 수동 실행

## 감사 결과

Google Sheets에 `콘텐츠감사` 탭이 생성되며 다음을 기록합니다.

- 게시물 ID와 URL
- 구조/사실/종합 점수
- A/B/C/D 등급
- 주요 문제와 중대 오류
- 권장조치와 실제 처리
- 원본 백업파일 경로

GitHub Actions Artifacts에는 CSV, JSON, 원본 게시물 백업이 저장됩니다.
