# TaxonGuru AdSense Recovery v6 — 빠른 적용 안내

상세 설명은 `README_MASTER.md`를 참고하세요.

## 덮어쓸 파일

- `main.py`
- `audit_existing_posts.py`
- `pipeline_controller.py`
- `setup_site_pages.py`
- `site_readiness.py` (신규)
- `README_MASTER.md`
- `.github/workflows/audit.yml`
- `.github/workflows/setup_pages.yml`

## 업로드 직후

1. `Create / Refresh Editorial Pages v6`를 1회 실행합니다.
2. `/about-taxonguru/`, `/editorial-policy/`, `/ai-use-policy/`, `/contact-and-corrections/`, `/privacy-policy/`가 공개되는지 확인합니다.
3. `TaxonGuru AdSense Recovery v6`를 `force_phase=auto`, `legacy_batch_size=1`로 1회 실행합니다.
4. 이후 기존 공개 글 정리는 예약 실행에 맡깁니다.
5. `수동검수대기`/`기존수동검수대기` 글은 WordPress에서 직접 확인 후 공개합니다.
6. 정리가 끝나면 `force_phase=readiness`로 최종 보고서를 생성합니다.

복구 모드에서는 신규 자동발행이 중지됩니다.
