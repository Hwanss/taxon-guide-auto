# AdSense Recovery v6.4

- 엄격 자동 최종검수 후 조건부 자동공개 추가
- KO/EN 동시 통과한 글만 공개
- 공개 후 실제 페이지 렌더링 재검증
- 실패 시 초안 롤백
- 애매한 글은 사람검수 유지
- AdSense 재심사 준비도 판단은 기존 v6.3 strict gate 유지

- 2026-09-30: v6.4.2 scheduled-run delay fallback trigger enabled; manual verification run requested.

- 2026-10-04: v6.4.3 WordPress timeout recovery + fail-safe Guard/Readiness verification run.


## 2026-11-04 AdSense 재반려 대응 점검
- 11월 1일 '가치가 별로 없는 콘텐츠' 재반려 확인. 자동발행·자동재작성·AI 이미지 생성을 동결하고 수동 편집검수를 우선합니다.
- 홈/푸터 신뢰 페이지 링크, 중복 날짜, 과학 참고자료 내 SNS 출처, 편집자 승인 여부를 재신청 준비도 차단 조건으로 점검합니다.
- 이 커밋은 공개 콘텐츠 수정 없이 안전 점검과 준비도 보고만 실행합니다.

- 2026-11-04 후속: 기존 카테고리 메뉴를 유지하면서 새 footer 메뉴(ID 1667)에 안내 링크 5개를 추가했고 공개 홈페이지 HTTP 200 및 누락 링크 0건을 검증했습니다. 재점검을 시작합니다.

- 2026-11-04 후속: 과학 참고자료의 SNS 출처가 발견된 공개 글 URL을 AdSense준비도 시트의 CONTENT_REVIEW 행으로 개별 출력하도록 개선했습니다.

## 2026-11-05 Editorial remediation
- Published 12 verified citation fixes across six bilingual biology topics; 58-post re-audit confirmed social reference issue count reduced from 12 to 0.
- Corrected Armillaria's organism-vs-fungus area record in two published articles using Guinness World Records, and removed leaked Commons CSS from two Victoria image credits.
- All original content backed up as downloadable Actions artifacts. One-time editing workflows reverted to dry-run. Editorial freeze still active.
- Next: quality review all 58 articles; fix published-date/theme display; require editor signoff before AdSense reapplication.
