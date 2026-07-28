# TaxonGuru 한·영 스토리텔링 자동 예약발행 v4

이 버전은 하나의 검증 자료 패키지로 **한국어 글과 영어 글을 각각 새로 작성**하고, 두 글을 별도 URL로 예약 발행합니다.

- 한국어: 기존 일반 게시물 URL
- 영어: `https://taxonguru.com/en/english-slug/`
- 한국어 예약: 기본 다음 빈 날짜 오전 9:30 KST
- 영어 예약: 기본 다음 빈 날짜 오후 6:30 KST
- 두 언어 모두 별도 품질검사
- 자동 품질점수와 예약정보는 공개 본문에 표시하지 않고 Google Sheets와 숨은 HTML 주석에만 기록
- 글 문체는 보고서형이 아니라 카테고리별 과학 스토리텔링형
- 한국어·영어 페이지 상호 `hreflang` 및 언어 전환 링크 자동 출력

## 중요: WordPress 플러그인을 먼저 설치하세요

영문 `/en/` URL과 `hreflang` 연결을 위해 동봉된 플러그인이 필요합니다. Polylang 유료 버전은 필요하지 않습니다.

설치 파일:

```text
wordpress-plugin/taxonguru-multilingual-bridge.zip
```

WordPress 관리자에서 다음 순서로 설치합니다.

```text
플러그인 → 플러그인 추가 → 플러그인 업로드
→ taxonguru-multilingual-bridge.zip 선택
→ 지금 설치 → 활성화
```

활성화 후 아래 주소를 브라우저에서 열었을 때 JSON이 보이면 정상입니다.

```text
https://taxonguru.com/wp-json/taxonguru/v1/status
```

예상 결과:

```json
{
  "active": true,
  "version": "1.0.0",
  "english_base": "https://taxonguru.com/en/"
}
```

## GitHub에 교체할 파일

ZIP을 압축 해제한 뒤 다음 파일과 폴더를 같은 경로에 덮어씁니다.

```text
main.py
requirements.txt
.github/workflows/schedule.yml
```

나머지 파일은 기존 저장소에 함께 유지해도 됩니다.

## 기존 GitHub Secrets와 Variables

기존 값을 그대로 사용합니다.

### Secrets

```text
WP_USER
WP_APP_PASSWORD
GEMINI_API_KEY
OPENAI_API_KEY
GOOGLE_CREDENTIALS
SHEET_ID
```

`OPENAI_API_KEY`는 `ALLOW_AI_FEATURED_IMAGE=false`인 동안 필수는 아닙니다.

### Variables

```text
WP_SITE_URL=https://taxonguru.com
CONTACT_EMAIL=실제 문의 이메일
```

## 자동 처리 흐름

```text
Google Sheets 대기 주제 1건
→ 공통 연구자료 조사
→ 한국어 스토리텔링 기사 작성
→ 한국어 자동검수 및 필요 시 1회 재작성
→ 영어권 독자를 위한 영어 기사 별도 작성
→ 영어 자동검수 및 필요 시 1회 재작성
→ Commons 이미지 업로드 및 언어별 캡션 적용
→ 한국어 오전 9:30 예약
→ 영어 오후 6:30 예약
→ 두 게시물 번역 관계 연결
→ hreflang와 언어 전환 링크 자동 출력
```

영어 글은 한국어 글을 직역하지 않고 같은 연구자료를 바탕으로 영어권 독자에게 맞게 다시 작성합니다.

## 공개 본문에서 제거된 내용

이전 버전에 있던 다음 문구는 더 이상 방문자에게 표시되지 않습니다.

```text
자동 품질검사 통과
출처 6개와 자동 검수점수 96점을 확인하여 예약되었습니다.
```

검수점수, 출처 수, 예약일, 수정 권고는 Google Sheets에만 기록되고 게시물 HTML에는 보이지 않는 주석으로 보관됩니다.

## 글쓰기 스타일

카테고리별로 구조와 분위기를 달리합니다.

- `Extreme Survivors`: 극한 환경의 장면에서 시작하는 자연 다큐멘터리형
- `Evolution Mysteries`: 오해와 증거를 하나씩 검증하는 과학 탐정형
- `Size Lab`: 익숙한 대상과 크기를 비교하는 실험형
- `Botany`: 서식지 풍경과 계절감에서 시작하는 자연 관찰 에세이형

공통적으로 짧은 문단, 자연스러운 비유, 절제된 유머, 장면형 도입을 사용합니다. 사실검증과 출처 번호는 그대로 유지합니다.

## 품질 기준

한국어와 영어를 별도로 검사합니다.

```text
품질점수 85점 이상
유효 출처 4개 이상
인용표시 4개 이상
한국어 본문 2,200자 이상
영어 본문 850단어 이상
중대한 사실 오류 0건
근거 없는 핵심 주장 0건
각 페이지에 다른 언어가 과도하게 섞이지 않음
```

영어 글만 실패하면 한국어는 예약되고 영어는 초안으로 저장됩니다.

## Google Sheets에 추가되는 영문 관리 열

코드가 없는 열을 자동 추가하고 시트 그리드도 자동 확장합니다.

```text
EN_POST_ID
EN_편집URL
EN_공개URL
EN_품질점수
EN_예약일
EN_자동검수결과
한영연결
영문오류
```

기존 `WP_POST_ID`, `편집URL`, `공개URL`, `품질점수`, `예약일`은 한국어 글을 의미합니다.

## 상태값

```text
대기
조사중
한국어작성
영어작성
한영예약완료
한국어예약/영문검수필요
검수필요
자료부족
오류
완료
```

## 현재 예약된 기존 글을 새 버전으로 다시 만들기

이미 예약된 글에는 이전 버전의 `자동 품질검사 통과` 상자가 남아 있습니다. 해당 행의 상태를 다음으로 바꾼 뒤 새 코드를 실행하면 같은 슬러그의 예약글을 갱신합니다.

```text
재작성
```

현재 예약글을 직접 편집해 상자만 삭제할 수도 있지만, 스토리텔링 문체와 영어판까지 함께 적용하려면 `재작성`을 권장합니다.

## 첫 실행 순서

1. WordPress에 `TaxonGuru Multilingual Bridge` 설치 및 활성화
2. GitHub에 새 `main.py`, `requirements.txt`, `schedule.yml` 업로드
3. Google Sheets의 테스트 행 상태를 `대기` 또는 `재작성`으로 설정
4. GitHub `Actions → TaxonGuru Bilingual Story Auto-Publish → Run workflow`
5. 로그에서 다음 항목 확인

```text
다국어 브리지 확인
한국어 자동 검수
영어 자동 검수
한국어 예약
영어 예약
한·영 예약 완료
```

6. WordPress `글 → 모든 글 → 예약됨`에서 한국어와 영어 글 2건 확인
7. 영어 글의 공개주소가 `/en/`으로 시작하는지 확인

## 검색엔진 다국어 원칙

Google은 한 페이지에 번역을 나란히 붙이는 방식보다 언어별 별도 URL과 양방향 `hreflang` 사용을 권장합니다.

- https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites
- https://developers.google.com/search/docs/specialty/international/localized-versions

## 참고

자동화 구조를 개선해도 애드센스 승인을 보장하지는 않습니다. 기존 저품질 게시물 정리, 사이트 소개·편집정책·개인정보처리방침, 이미지 라이선스, 사용자 탐색 구조도 함께 점검해야 합니다.
