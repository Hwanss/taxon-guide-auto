# TaxonGuru 자동 품질검수 + 예약 발행 파이프라인

기존의 `AI 작성 → 즉시 공개` 또는 `초안 생성 → 사람이 매번 승인` 방식 대신 다음 흐름으로 동작합니다.

`주제 선택 → 자료 조사 → 출처 구조화 → 한국어 기사 작성 → 1차 자동검수 → 필요 시 자동 재작성 → 2차 자동검수 → 통과 글만 WordPress 예약 → 예약일 자동 공개`

품질 기준을 통과한 글은 Google Sheets에서 `검수자`와 `승인`을 입력하지 않아도 됩니다. 기준을 통과하지 못한 글만 WordPress의 비공개 초안과 시트의 `검수필요` 상태로 남습니다.

---

## 핵심 동작

### 자동 예약되는 조건

기본 설정은 다음 조건을 모두 만족해야 합니다.

- 자동 검수점수 85점 이상
- 중대한 사실 오류 0건
- 근거 없는 핵심 주장 0건
- 유효한 원문 출처 4개 이상
- 본문 인용 표시 4개 이상
- 본문 텍스트 2,200자 이상
- `[[IMAGE_1]]`, `[[IMAGE_2]]` 자리표시자가 정상 생성됨

통과하면 WordPress REST API에 다음 값으로 저장합니다.

- `status`: `future`
- `date`: 한국시간 기준 예약일
- `date_gmt`: UTC 기준 예약일

기준 미달이면 다음 값으로 저장합니다.

- `status`: `draft`
- Google Sheets 상태: `검수필요`

### 예약일 계산

기본값은 다음과 같습니다.

- GitHub Actions 실행: 매일 오전 6시 23분 KST
- 최초 예약일: 실행일 다음 날
- 공개시간: 오전 9시 30분 KST
- 발행 간격: 하루 1건

이미 같은 시각의 WordPress 예약글이 있으면 그다음 빈 날짜를 자동으로 찾습니다. 수동으로 workflow를 여러 번 실행해도 같은 시각에 여러 글이 겹치지 않습니다.

---

## 저장소에 적용할 파일

저장소 루트에 다음 파일과 폴더를 그대로 업로드하거나 교체합니다.

```text
main.py
generate_topics.py
setup_site_pages.py
audit_existing_posts.py
requirements.txt
README.md
.github/workflows/schedule.yml
.github/workflows/generate_topics.yml
.github/workflows/setup_pages.yml
.github/workflows/audit.yml
```

---

## GitHub Secrets

`Settings → Secrets and variables → Actions → Secrets`에 다음 값을 설정합니다.

- `WP_USER`
- `WP_APP_PASSWORD`
- `GEMINI_API_KEY`
- `OPENAI_API_KEY` — AI 이미지 기능을 끄면 없어도 됩니다.
- `GOOGLE_CREDENTIALS`
- `SHEET_ID`

## GitHub Variables

`Settings → Secrets and variables → Actions → Variables`에 다음 값을 권장합니다.

- `WP_SITE_URL`: `https://taxonguru.com`
- `CONTACT_EMAIL`: 실제 문의 이메일

---

## schedule.yml 기본 설정

```yaml
AUTO_SCHEDULE: 'true'
DRAFT_ON_REVIEW_FAILURE: 'true'
ALLOW_AI_FEATURED_IMAGE: 'false'

SCHEDULE_TIMEZONE: 'Asia/Seoul'
PUBLISH_HOUR: '9'
PUBLISH_MINUTE: '30'
SCHEDULE_AFTER_DAYS: '1'
SCHEDULE_INTERVAL_DAYS: '1'
MIN_SCHEDULE_LEAD_MINUTES: '30'
MAX_SCHEDULE_LOOKAHEAD_DAYS: '120'

MIN_SOURCE_COUNT: '4'
MIN_QUALITY_SCORE: '85'
MIN_ARTICLE_CHARS: '2200'
MIN_CITATION_MARKERS: '4'
```

### 예약시간 변경 예시

매일 오후 7시에 발행하려면 다음 두 값만 바꿉니다.

```yaml
PUBLISH_HOUR: '19'
PUBLISH_MINUTE: '0'
```

작성 당일 예약하려면 다음과 같이 바꿀 수 있습니다.

```yaml
SCHEDULE_AFTER_DAYS: '0'
```

다만 설정한 발행시각이 이미 지났거나 현재 시각에서 30분 이내이면 다음 예약일로 자동 이동합니다.

### 발행 빈도 변경

이틀에 한 번 예약하려면 다음처럼 설정합니다.

```yaml
SCHEDULE_INTERVAL_DAYS: '2'
```

GitHub Actions 자체 실행 빈도도 바꾸려면 `.github/workflows/schedule.yml`의 cron을 변경합니다. 현재 값은 매일 오전 6시 23분 KST입니다.

```yaml
- cron: '23 21 * * *'
```

GitHub Actions cron은 UTC 기준이므로 위 값은 한국시간으로 다음 날 오전 6시 23분입니다.

---

## Google Sheets 상태값

코드가 기존 열 뒤에 필요한 열을 자동 추가합니다.

### 상태

- `대기`: 새 글 작성 대상
- `조사중`: 원문 자료와 분류 정보 수집 중
- `작성중`: 기사 본문 작성 중
- `자동검수중`: 자동 사실·품질 검사 중
- `예약완료`: WordPress 예약글 등록 완료
- `완료`: WordPress에서 실제 공개 완료
- `검수필요`: 자동 기준 미달로 비공개 초안 저장
- `자료부족`: 신뢰할 수 있는 자료 또는 검증 사실 부족
- `재작성`: 같은 주제를 다시 작성하도록 요청
- `검수실패`: 설정상 초안 저장을 끈 상태에서 품질검사 실패
- `오류`: API, 인증, WordPress 처리 등의 실행 오류
- `보류`: 자동 처리 대상에서 제외

### 추가 열

- `WP_POST_ID`
- `편집URL`
- `공개URL`
- `품질점수`
- `자료수`
- `예약일`
- `자동검수결과`
- `오류`

기존의 `검수자`, `검수일`, `검수메모` 열은 호환성을 위해 남겨두지만 자동 예약에는 필수로 사용하지 않습니다.

---

## 실제 운영 순서

1. Google Sheets의 주제 상태를 `대기`로 둡니다.
2. GitHub Actions의 `TaxonGuru Scheduled Auto-Publish`가 매일 자동 실행됩니다.
3. 글이 기준을 통과하면 시트 상태가 `예약완료`로 바뀌고 `예약일`이 기록됩니다.
4. 예약일이 되면 WordPress가 글을 공개합니다.
5. 다음 workflow 실행 때 WordPress 상태를 확인해 시트 상태를 `완료`로 동기화합니다.
6. 기준 미달 글만 `검수필요`로 남으므로 필요할 때만 확인합니다.

글마다 `검수자` 이름을 입력하거나 상태를 `승인`으로 바꿀 필요가 없습니다.

---

## WordPress 필수 확인

### 사이트 시간대

WordPress 관리자에서 다음 위치를 확인합니다.

`설정 → 일반 → 시간대 → 서울`

코드는 `date`와 `date_gmt`를 모두 전송하지만, 관리자 화면과 예약시간을 일치시키기 위해 사이트 시간대를 서울로 설정하는 것이 좋습니다.

### 예약 발행 지연 방지

WordPress의 WP-Cron은 사이트 방문 요청을 계기로 동작할 수 있으므로 방문자가 적으면 예약 발행이 늦어질 수 있습니다. 호스팅에서 실제 Cron을 지원하면 5분 간격 실행을 권장합니다.

```bash
*/5 * * * * curl -s https://taxonguru.com/wp-cron.php?doing_wp_cron >/dev/null 2>&1
```

호스팅 환경에 따라 `wget`을 사용할 수도 있습니다.

```bash
*/5 * * * * wget -q -O - https://taxonguru.com/wp-cron.php?doing_wp_cron >/dev/null 2>&1
```

서버 Cron을 설정했다면 WordPress 설정에 따라 기본 WP-Cron 비활성화 여부를 호스팅 업체 안내에 맞춰 결정하십시오.

---

## 이미지 처리

- Wikimedia Commons의 CC BY, CC BY-SA, CC0, Public Domain 이미지를 우선합니다.
- 저작자, 라이선스, 원본 파일 링크를 WordPress 캡션과 미디어 설명에 기록합니다.
- 비상업적 전용, 변경금지, 불명확한 라이선스는 자동 제외합니다.
- `ALLOW_AI_FEATURED_IMAGE` 기본값은 `false`입니다.
- AI 이미지를 켜면 실제 관찰 사진이 아닌 설명용 이미지라는 캡션을 자동으로 붙입니다.

---

## 운영 페이지 생성

GitHub Actions에서 `Create Editorial Pages`를 수동 실행하면 다음 페이지를 WordPress 초안으로 생성합니다.

- TaxonGuru 소개
- 편집 및 팩트체크 정책
- AI 활용 정책
- 문의 및 오류 제보
- 개인정보처리방침

자동 운영 사실을 숨기지 않도록 정책 페이지에는 자동 검수와 예약 발행, 사람의 개별 검수가 항상 수행되는 것은 아니라는 설명이 포함됩니다. 실제 운영 방식과 개인정보·광고 설정에 맞게 확인한 뒤 공개하십시오.

---

## 기존 글 감사

`Audit Existing Posts` workflow를 실행하면 `taxonguru_content_audit.csv`가 GitHub Actions Artifacts로 생성됩니다.

확인 항목:

- 본문 분량
- 외부 원문 링크 수
- 참고자료 섹션
- 이미지 라이선스 표기
- 고정 5단 템플릿 흔적
- 한 페이지의 한국어·영어 반복
- AI 활용 고지

---

## 주의사항

이 코드는 저품질 글의 즉시 공개를 막고, 기준을 통과한 글만 예약하도록 설계한 자동화입니다. 그러나 자동 품질점수와 출처 개수만으로 과학적 정확성이나 애드센스 승인이 보장되지는 않습니다. `검수필요`, `자료부족`, 오류 제보가 발생한 글은 사람이 확인하고, 공개된 글도 정기적으로 표본 점검하는 것이 안전합니다.
