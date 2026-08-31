# TaxonGuru AdSense Recovery v6

이 버전은 AdSense의 **"가치가 별로 없는 콘텐츠"** 재심사 전에 기존 공개 글과 사이트 신뢰 요소를 정리하기 위한 복구 모드입니다.

핵심 원칙은 다음과 같습니다.

- 복구 기간에는 **신규 주제 생성·신규 자동발행을 중지**합니다.
- 기존 공개 글을 순차 감사합니다.
- 문제가 있는 글은 삭제하지 않고 WordPress **초안**으로 전환합니다.
- 재작성본은 자동 품질검사를 통과해도 **자동 공개하지 않고 사람 검수 대기**로 저장합니다.
- Google/Vertex 검색 중계 URL, 언어 혼입, 구형 정책 링크 등을 품질 검사에 포함합니다.
- 소개·편집정책·AI 활용정책·문의·개인정보처리방침 페이지를 실제 공개 상태로 생성/갱신합니다.
- 마지막에 `readiness` 검사를 실행해 재심사 전 남은 문제를 보고서로 확인합니다.

---

## 1. GitHub에 덮어쓸 파일

다음 파일을 저장소의 같은 위치에 덮어씁니다.

```text
main.py
audit_existing_posts.py
pipeline_controller.py
setup_site_pages.py
site_readiness.py                 # 신규 파일
README_MASTER.md

.github/workflows/audit.yml
.github/workflows/setup_pages.yml
```

아래 파일은 이번 버전에서 변경하지 않았습니다.

```text
generate_topics.py
requirements.txt
.github/workflows/generate_topics.yml
.github/workflows/schedule.yml
README.md
README_AUDIT.md
```

GitHub `Settings > Secrets and variables`에 저장한 키/비밀번호는 건드리지 않습니다.

---

## 2. 파일 업로드 후 첫 실행 — 정책 페이지

GitHub의 `Actions`에서 다음 Action을 한 번 실행합니다.

```text
Create / Refresh Editorial Pages v6
```

이 Action은 아래 URL을 `publish` 상태로 생성하거나 갱신합니다.

```text
/about-taxonguru/
/editorial-policy/
/ai-use-policy/
/contact-and-corrections/
/privacy-policy/
```

실행 후 각 URL을 브라우저에서 직접 열어 404가 아닌지 확인합니다.

> 주의: 이 Action은 `SITE_PAGES_FORCE_UPDATE=true`로 동작하므로 현재 같은 slug의 페이지가 있으면 v6 기본 내용으로 갱신합니다. 첫 복구 실행 후 운영자 소개나 개인정보 안내를 실제 운영 상황에 맞게 더 자세히 보완해도 됩니다.

---

## 3. 두 번째 실행 — 복구 파이프라인 시험

`Actions`에서 아래 Action을 실행합니다.

```text
TaxonGuru AdSense Recovery v6
```

첫 수동 실행 권장값:

```text
force_phase: auto
legacy_batch_size: 1
```

첫 실행이 초록색으로 끝나면 이후에는 같은 Action이 한국시간 기준 하루 4회 자동 실행됩니다.

```text
03:17
09:17
15:17
21:17
```

복구 모드에서는 **기존 자료 정리만 진행하며 신규 글을 자동 생성·공개하지 않습니다.**

---

## 4. v6에서 달라진 처리 방식

### 기존 공개 글 감사

```text
기존 상태 '완료'
        ↓
구조/출처/언어/정책링크/사실 검수
        ↓
A등급(자동 감사 통과)           → WordPress 초안 전환 → 사람 검수 대기
B/C/D 또는 구조상 중요 문제      → WordPress 초안 전환
                                  ↓
                                재작성
                                  ↓
                             자동 품질검수
                                  ↓
                          기존수동검수대기
```

영구 삭제는 자동으로 하지 않습니다. **복구 모드에서는 A등급도 자동검수만으로 공개 유지하지 않고, 사람 검수를 위해 초안으로 전환합니다.**

### 자동 품질검사 통과 후

이전 버전처럼 예약 발행하지 않습니다.

```text
자동 품질검사 통과
→ WordPress draft
→ Google Sheet 상태: 수동검수대기 / 기존수동검수대기
→ 운영자가 WordPress 편집 화면에서 내용 확인
→ 운영자가 직접 공개
→ 다음 동기화에서 완료 상태로 자동 반영
```

복구 모드 시작 전에 이미 `future`로 예약돼 있던 글도 자동 공개되지 않도록 초안으로 전환하고 사람 검수 대기로 이동시킵니다.

---

## 5. 사람 검수 시 꼭 확인할 것

`수동검수대기` 또는 `기존수동검수대기` 글은 WordPress에서 다음 항목을 확인한 뒤 직접 공개합니다.

1. 제목이 과장되거나 클릭베이트처럼 보이지 않는지
2. 첫 문단이 실제 독자 질문/주제를 명확히 설명하는지
3. 학명·분류·수치가 참고자료와 맞는지
4. `[1]`, `[2]` 같은 인용 표시와 하단 참고자료가 연결되는지
5. 참고자료 링크가 GBIF, NCBI, 대학, 박물관, 논문 등 **실제 원문 주소**인지
6. `vertexaisearch.cloud.google.com` 또는 Google 검색 중계 URL이 보이지 않는지
7. 한국어 글에 `照射` 같은 중국어/일본어 문자가 섞이지 않았는지
8. 영어 글에 한국어/CJK 문자가 섞이지 않았는지
9. 이미지와 캡션·라이선스 정보가 자연스러운지
10. 글 하단의 편집정책/AI 활용정책 링크가 정상 열리는지

영문판을 운영할 경우 한국어와 영어 **둘 다 검수 후 공개**하는 것을 권장합니다.

---

## 6. Google Sheet에서 볼 주요 상태

```text
완료                         기존 공개 글 감사 대상
기존재작성대기               기존 글 초안 전환 후 재작성 대기
기존재작성재시도             재작성 품질검수 재시도
기존수동검수대기             재작성 성공, 사람 검수 필요
수동검수대기                 신규/일반 글 사람 검수 필요
한국어완료/영문수동검수대기   한국어 공개, 영어는 사람 검수 필요
기존비공개보류               자동 처리하기 어려워 비공개 보관
기존한영수정완료             사람 검수 후 한·영 공개 완료
```

`파이프라인상태` 탭에는 현재 단계와 남은 수량이 표시됩니다.

---

## 7. AdSense 재신청 직전 검사

기존 글 정리가 끝나고 수동검수 대기 글도 모두 처리한 뒤, `TaxonGuru AdSense Recovery v6` Action을 다시 수동 실행합니다.

```text
force_phase: readiness
legacy_batch_size: 1   # readiness에서는 값이 중요하지 않음
```

Action 실행 결과의 Artifact에 다음 파일이 생성됩니다.

```text
audit_output/adsense_readiness.md
audit_output/adsense_readiness.json
```

`adsense_readiness.md`에서 결과가 `READY`인지 확인합니다.

검사 항목:

- 필수 정책/신뢰 페이지 공개 여부
- 공개 글 품질/링크/언어 이상
- `/ai-policy/` 구형 링크
- Google/Vertex 중계 출처 링크
- 참고자료 섹션
- AI 정책 링크
- ads.txt 기본 상태

---

## 8. 코드만으로 자동 수정하지 않는 두 항목

### ads.txt

`site_readiness.py`가 `/ads.txt`를 확인하지만, WordPress REST 게시물 코드만으로 웹사이트 루트의 실제 `ads.txt` 파일을 안전하게 설치할 수는 없습니다.

AdSense에서 제공하는 정확한 publisher ID를 사용해 WordPress의 ads.txt 관리 기능/플러그인 또는 호스팅 루트에 적용한 뒤 다음 주소가 일반 텍스트로 열리는지 확인합니다.

```text
https://taxonguru.com/ads.txt
```

### 홈페이지 날짜 중복 표시

홈/카테고리 목록의 날짜가 `8월 31, 2026 8월 16, 2026`처럼 중복되는 문제는 게시물 본문이 아니라 **WordPress 테마 템플릿 영역**이므로 이 Python 자동화가 임의로 수정하지 않습니다.

AdSense 재신청 전 실제 브라우저에서 홈·카테고리·게시물 화면을 확인해 날짜가 한 번만 자연스럽게 표시되도록 테마 설정을 수정하세요.

---

## 9. 신규 자동발행 재개 시점

AdSense 승인 전에는 `ADSENSE_RECOVERY_MODE=true`를 유지하는 것을 권장합니다.

승인 후에도 Google 정책에 맞게 **자동 생성 → 자동 공개**가 아니라 **자동 작성 → 사람 검수 → 직접 공개** 흐름을 유지하는 편이 안전합니다.

신규 글 자동 생성 자체를 다시 사용하려면 복구 완료 후 별도의 운영 모드로 전환할 수 있지만, `MANUAL_REVIEW_REQUIRED=true`는 유지하는 것을 권장합니다.

---

## 가장 간단한 실행 순서

```text
1. v6 파일 GitHub에 덮어쓰기 + Commit
2. Actions > Create / Refresh Editorial Pages v6 > Run workflow 1회
3. 정책 페이지 5개가 브라우저에서 정상 공개되는지 확인
4. Actions > TaxonGuru AdSense Recovery v6 > auto / batch 1 로 1회 시험
5. 정상이라면 자동 실행에 맡기기
6. Google Sheet의 기존수동검수대기 글을 WordPress에서 직접 확인·공개
7. 기존 정리 + 수동검수 완료 후 force_phase=readiness 실행
8. readiness 보고서의 문제 해결
9. ads.txt 및 홈페이지 날짜 표시 확인
10. 그 다음 AdSense에서 '문제를 수정했음을 확인합니다' 체크 후 검토 요청
```
