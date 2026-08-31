# TaxonGuru AdSense Recovery v6 변경 요약

## 자동발행 안전장치
- `ADSENSE_RECOVERY_MODE=true`
- `MANUAL_REVIEW_REQUIRED=true`
- 복구 기간 신규 주제 생성/신규 자동발행 중지
- 기존 예약(`future`) 글을 사람 검수용 초안으로 전환
- 기존 글 A등급도 자동 판정만으로 공개 유지하지 않고 사람 검수용 초안으로 전환

## 기존 글 품질 감사 강화
- Google/Vertex 중계 출처 URL 탐지
- 직접 외부 출처 링크 부족 탐지
- 참고자료 섹션 누락 탐지
- 짧은 본문 탐지
- 고정형 AI 템플릿 탐지
- 한국어 글의 중국어 한자/일본어 가나 혼입 탐지
- 영어 글의 한국어/CJK 혼입 탐지
- 이미지 출처/라이선스 또는 AI 생성 고지 탐지
- `/ai-policy/` 구형 링크 → `/ai-use-policy/` 안전 수정

## 신규/재작성 글
- 검색 중계 URL은 실제 최종 출처 URL로 해석 후 사용
- 중계 URL이 실제 출처로 해석되지 않으면 참고자료에서 제외
- 근거 기반의 주제별 분석/비교/의미 설명을 작성 프롬프트에 강화
- 언어 혼입 자동검수 강화
- 품질 통과 후 WordPress `draft` 저장 → 사람 검수 후 직접 공개

## 신뢰 페이지
`setup_site_pages.py`가 다음 페이지를 공개 상태로 생성/갱신
- `/about-taxonguru/`
- `/editorial-policy/`
- `/ai-use-policy/`
- `/contact-and-corrections/`
- `/privacy-policy/`

## 재심사 준비도 검사
신규 `site_readiness.py`
- 필수 페이지 HTTP/WP 공개 상태
- 홈/푸터의 신뢰 페이지 링크
- 공개 글 출처/언어/정책링크/이미지 고지
- Google Sheet 정리·수동검수 미완료 상태
- ads.txt 상태
- 홈페이지 날짜 중복 패턴

결과 파일
- `audit_output/adsense_readiness.md`
- `audit_output/adsense_readiness.json`
