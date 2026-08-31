# TaxonGuru AdSense Recovery v6.1 — Gemini 429 Hotfix

## 왜 필요한가
v6.0에서는 Gemini API가 `429 RESOURCE_EXHAUSTED`, `monthly spending cap`으로 멈춘 경우에도
기존 글의 `재작성시도`를 1회 실패로 계산할 수 있었습니다.
따라서 3/3 시점에 외부 API 한도 오류가 나면 글이 `기존비공개보류`로 이동할 수 있었습니다.

v6.1은 이 문제를 수정합니다.

## 변경점
- Gemini 429 / 월 지출한도 / quota / rate-limit 오류를 콘텐츠 품질 실패와 분리합니다.
- 429가 확인되면 Gemini 재시도를 즉시 중단합니다.
- 기존 글 재작성 횟수를 차감하지 않습니다.
- v6.0에서 429 때문에 마지막 시도를 잘못 소모한 행은 다음 실행 시 자동 복구합니다.
  - `기존비공개보류` → `기존재작성재시도`
  - 재작성시도 3 → 2처럼 잘못 소모된 1회를 복원
- 기존 공개 글 감사 중 429가 나면 WordPress 게시물을 초안으로 바꾸지 않습니다.
- 429는 GitHub Actions 전체 실패(빨간 X)가 아니라 `외부AI한도대기` 상태의 정상 보류로 처리합니다.
- Google Sheets `worksheet.update()` deprecation warning도 수정했습니다.

## 덮어쓸 파일
- `main.py`
- `pipeline_controller.py`
- `audit_existing_posts.py`
- `.github/workflows/audit.yml`

## 적용 후 실행
1. 위 파일을 저장소 같은 위치에 덮어쓰기
2. GitHub Desktop에서 Commit → Push origin
3. GitHub Actions에서 `TaxonGuru AdSense Recovery v6.1` 실행
4. `force_phase: auto`, `legacy_batch_size: 1`

Gemini 월 지출한도가 아직 해제되지 않았다면 작업은 진행되지 않지만 초록색으로 안전 종료되고,
시트의 재작성 횟수는 소모되지 않습니다. 한도가 해제된 뒤 다음 자동 실행에서 같은 글부터 계속합니다.
