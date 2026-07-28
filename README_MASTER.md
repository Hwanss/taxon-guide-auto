# TaxonGuru 마스터 자동 운영 v2

기존 게시물 정리가 끝날 때까지 신규 글을 만들지 않고, 정리가 완료되면 자동으로 신규 한·영 작성과 주제 보충으로 전환하는 조건형 파이프라인입니다.

## 핵심 동작

### 1단계: 기존 글 정리

Google Sheets `taxonguru` 탭의 **상태가 정확히 `완료`인 행만** 처리합니다.

- `한영예약완료`는 건드리지 않습니다.
- `한국어예약/영문검수필요`, `대기` 등 다른 상태도 기존 정리 단계에서는 건드리지 않습니다.
- WordPress 공개 글을 최근 수정된 순서로 찾습니다.
- 한 번 실행할 때 기본 2건 처리합니다.
- 매일 한국시간 03:17과 15:17에 실행되므로 최대 하루 4건을 정리합니다.

상태 변경 기준:

| 판정 | WordPress 처리 | 시트 상태 |
|---|---|---|
| A등급 | 공개 유지 | `기존검수완료` |
| B/C등급 | 기존 URL에 한국어 재작성, 영어 별도 글 생성 시도 | `기존한영수정완료` 또는 `기존수정완료` |
| D등급 | 영구 삭제 대신 복구 가능한 초안 전환 | `기존비공개완료` |
| 재작성 실패·자료 부족 | 안전을 위해 초안 전환 | `기존비공개완료` |
| 공개 게시물 자체가 없음 | 이미 비공개된 것으로 분류 | `기존비공개완료` |

영구 삭제는 자동으로 하지 않습니다. 애드센스 정리 목적에서는 공개 중단만으로 충분하며, 잘못 분류됐을 때 복구할 수 있도록 초안으로 이동합니다.

### 2단계: 신규 자동 운영

시트에서 상태가 정확히 `완료`인 행이 0건이 되면 자동 전환합니다.

1. `한국어예약/영문검수필요` 등 재검수 상태가 있으면 먼저 복구합니다.
2. 그다음 `대기` 주제 1건을 한국어·영어로 작성하고 예약합니다.
3. 신규 작성은 한국시간 오전 실행에서만 하루 1건 진행합니다.
4. 오후 실행은 상태만 확인하고 종료합니다.
5. `대기` 주제가 10건 미만이면 검증된 주제 12건을 자동 추가합니다.

따라서 사용자가 매번 감사, 신규 작성, 주제 생성을 각각 실행할 필요가 없습니다.

## 제공 파일

```text
pipeline_controller.py
├─ 전체 단계 판단 및 자동 전환

audit_existing_posts.py
├─ 상태가 정확히 '완료'인 기존 글만 최근순 정리

main.py
├─ 기존 최신 한·영 스토리텔링 예약발행 코드
├─ IPv4 강제 설정 추가

generate_topics.py
├─ 대기 주제 부족 시 Gemini 생성
├─ GBIF에서 실제 종 학명 검증 후 추가

requirements.txt

.github/workflows/
├─ audit.yml             # 실제 자동 운영 마스터 Action
├─ schedule.yml          # 직접 실행 방지 안내용
└─ generate_topics.yml   # 직접 실행 방지 안내용
```

## GitHub 적용

ZIP을 저장소에 올리지 말고 압축 해제 후 아래 파일을 저장소의 같은 위치에 덮어씁니다.

```text
pipeline_controller.py
audit_existing_posts.py
main.py
generate_topics.py
requirements.txt
.github/workflows/audit.yml
.github/workflows/schedule.yml
.github/workflows/generate_topics.yml
```

기존 `setup_site_pages.py`와 `setup_pages.yml`, WordPress 다국어 브리지 플러그인은 유지합니다.

## Actions 목록 사용법

### TaxonGuru Master Cleanup & Publish

유일한 자동 운영 Action입니다.

- 매일 자동 실행됩니다.
- 평소에는 `Run workflow`를 누르지 않아도 됩니다.
- 처음 적용한 뒤 한 번만 수동 실행해 작동 여부를 확인할 수 있습니다.

수동 입력:

- `auto`: 현재 상태에 맞춰 자동 판단
- `cleanup`: 기존 `완료` 글만 처리
- `new`: 정리 완료 후 신규 1건 강제 실행
- `status_only`: 변경 없이 상태만 확인

### TaxonGuru Bilingual Story Auto-Publish (CONTROLLED)

실제 글을 만들지 않고 안내만 출력합니다. 실행할 필요가 없습니다.

### TaxonGuru Topic Planner (CONTROLLED)

마스터가 대기 주제 수를 확인해 자동 실행합니다. 직접 실행할 필요가 없습니다.

### Create Editorial Pages

사이트 소개·편집정책·AI 활용정책 페이지가 아직 없을 때 한 번만 실행합니다. 이미 생성됐다면 다시 실행하지 않습니다.

## 파이프라인 상태 확인

Google Sheets에 `파이프라인상태` 탭이 자동 생성됩니다.

```text
최근실행
단계
결과
기존완료잔여
한영예약완료보존
대기주제
영문재검수등
다음작업
오류
```

사용자가 GitHub 로그를 매번 열지 않아도 현재 단계와 남은 수량을 시트에서 확인할 수 있습니다.

## 예상 기간

제공된 시트처럼 기존 `완료`가 약 81건이라면 기본 설정은 하루 최대 4건이므로 약 21일에 정리가 끝나는 구조입니다. WordPress 연결 실패나 외부 API 지연이 발생한 날에는 다음 예약 실행에서 자동 재시도하므로 실제 기간은 조금 늘어날 수 있습니다.

## WordPress 연결 장애 처리

작업 시작 전에 WordPress REST API를 확인합니다.

- 연결 정상: 감사·수정 또는 신규 작성 시작
- 네트워크 연결 실패: Gemini/OpenAI를 호출하지 않고 이번 실행 보류
- 다음 예약 시간에 자동 재시도

GitHub Runner가 연결할 수 없는 IPv6 경로를 선택하는 문제를 줄이기 위해 IPv4를 강제합니다.
