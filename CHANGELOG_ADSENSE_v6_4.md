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
