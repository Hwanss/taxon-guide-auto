# TaxonGuru 최종 재신청 준비 점검 — 2026-11-11 (KST)

**결론: 재신청 보류 / 실질 개선 6개 공개 글 반영 / 재검증 통과.** Google AdSense의 승인 가능성을 점수나 백분율로 환산하지 않음. 사이트 전체 편집 승인, 애드센스 제출, 자동 게시 재개는 수행하지 않음.

## 검증된 변경 사항

| 내용 | 게시물 ID | GitHub Actions 증빙 | 결과 |
|---|---|---|---|
| 빅토리아수련 영문: 참조 1/4/6/7/9의 정확한 원자료 지정, 발열 원논문 분석·기존 분류학 오인용 정리 | 775 | https://github.com/Hwanss/taxon-guide-auto/actions/runs/42936441876 | `LIVE_UPDATED_AND_VERIFIED`, 공개 200, 원본 백업 |
| 빅토리아수련 국문: 참조 1/4/6/7/9 원자료 정비, 꽃 발열·건축 주장에 걸린 부정확한 분류학 인용 13개 제거, 꽃 현장 측정 결과·한계 설명 및 가시 과장 완화 | 141 | https://github.com/Hwanss/taxon-guide-auto/actions/runs/42937558516 | `LIVE_UPDATED_AND_VERIFIED`, 공개 200, 원본 백업 |
| 라플레시아와 타이탄 아룸의 '단일 꽃 vs 꽃차례' 구분을 활용한 한영 상호 관련 글 링크 4개 | 137,24,787,864 | https://github.com/Hwanss/taxon-guide-auto/actions/runs/42938232069 | 4/4 실제 공개 검증, 원본 4개 백업 |

각 변경 전 프리뷰는 별도 Actions에서 통과: EN 775 #42936242398; KO 141 #42937419032; 관련 글 4건 #42938148260. 모든 변경은 기존 게시 상태·이미지 수·제목 구조 보존 조건과 공개 WordPress 재조회 확인. 해당 세 쓰기 워크플로는 사용 후 **preview-only**로 복구함.

## 변경 후 독립 전수 재검증 (읽기 전용)

- [전수 기술 검사](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42938423064): 공개 54/54 HTTP 200, KO 27/EN 27, 27/27 hreflang 양방향 일치, canonical 불일치 0, robots.txt/ads.txt/sitemap/주요 정책 URL 8/8 HTTP 200, ads.txt 레코드 통과, 이미지 108, 번호 참고문헌 450, SNS 인용 0, 깨진 내부 연결 0, 본문 고유 내부 URL 6개 (이전 2개보다 개선). 이 결과는 사람의 모바일 체험·웹 전체 독창성 심사가 아님.
- [독립 콘텐츠 감사](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42938430043): 약한 도메인 출처 68개가 50개 글에 분포, 정확한 URL이 중복된 참고문헌을 포함한 글 4건·추가 중복 슬롯 4개. 단순 도메인 분류는 과학적 오류를 확정하지 않음.
- **기존 미인용 47개 집계는 검사 버그였음**: 기존 정규식은 본문에 문자로 쓰인 `[1, 2, 3]` 형식을 빠뜨려 과다계상했으며, 새 검사로 재집계한 결과 현재 기준 번호 참고문헌 미인용 0, 존재하지 않는 번호 인용 0. 450개 링크의 과학적 정확성을 개별 검증했다는 뜻은 아님.
- 현존 고위험 비공개 4개 (아홀로틀 34/834, 피흘리는이빨버섯 260/535)는 **공개 전환 금지**.

## 재신청 전 남은 핵심 과제

1. 단순 68개 출처를 무조건 없애기보다, 주요 수치·기전·의학/안전성·분류 등의 사실을 실제 원자료와 연결하는 개별 검증. 특히 푸야 라이몬디 한국어/영어 227/449, 앵무조개 209/401에 동일 URL 참고문헌 중복 4개 슬롯 남음. 그림 출처와 학술적 인용은 구분, 무작정 DOI 교체 금지.
2. 개별 글의 독창적 비교·연구 한계·원자료에 근거한 결론이 **독자에게 실제 새 가치를 주는지** 실제 사람이 검토. 같은 공통 안내 문단이 한영 각 27개 글에 있어도 그 자체는 규정 위반 확정 아님.
3. 108개 본문 이미지의 현행 저작권·저자표시 요구 준수 및 실제 스마트폰 사용성 최종 확인.
4. Google Search Console의 실제 색인/제외 사유 확인 (공개 meta index 허용과 실제 색인 완료는 다름).
5. Google AdSense 계정의 사이트 상태·정책 메시지를 운영자가 직접 확인. 연동 Gmail에서는 2026-10-31 TaxonGuru에 대한 반려 안내가 확인됐으나 메일 본문에는 세부 위반 항목이 없음. 재신청 버튼을 누르지 않음.

**내부 판단:** 기술적 사이트 회귀 검사에선 통과, 품질 개선은 실제 이루어졌으나 콘텐츠 가치는 부분 미검증. 사용자에게 '애드센스 통과 준비 완료'라고 보고하지 않고 보수적으로 보류 권고. 향후 작업은 백업 → 원문-주장 대조 → 읽기 전용 프리뷰 → 변경 → 게시물/공개 URL 검증 → 작업대장 갱신 순으로 진행.


## 2026-11-11 자동 실행 추가 차수 — 중복 참고 URL 4슬롯 실수정 및 재검증

- 사전 근거 감사: [GitHub Actions #42940893421](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42940893421). 실제 공개 WordPress 참고문헌 번호와 연결되는 본문 문장을 교차검토함. 단순 URL 중복만으로 참고문헌을 지우거나 번호를 병합하지 않음.
- 푸야 라이몬디 한국어 227 / 영어 449의 **ref-5**: Frontiers 2024 종합 리뷰(ref-2와 중복)를 직접 현장 관찰에 해당하는 Rees & Roe (1980) `https://doi.org/10.1139/b80-157`로 교체. 새의 가시 걸림 및 잠재적 영양 공급은 **가설**이지 식물의 육식성이 실증됐다는 주장은 아님.
- 앵무조개 한국어 209 / 영어 401의 **ref-4**: NOAA 일반 소개(ref-5와 중복)를 야생 표지·재포획에 의한 성숙/수명 원논문 Dunstan et al. (2011) `https://doi.org/10.1371/journal.pone.0016312`로 교체. 원논문의 약 15.5년 성숙 추정·20년 초과 수명 근거와 문장 문맥을 맞춤. 기존 ref-5는 NOAA 기관 자료로 유지.
- [쓰기 금지 사전 검사/4건 전체 백업](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42941108324) 성공 후, [실제 WordPress 수정·4/4 재조회·4/4 공개 200·원본 artifact 보관](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42941199593) 완료. 수정 후 workflow `.github/workflows/primary-source-repair.yml`은 다시 `DUPLICATE_SOURCE_APPLY=false`로 복구.
- [수정 후 54건 독립 품질 감사](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42941317652): **참고문헌 동일 URL 중복 글 0건 / 중복 슬롯 0개**로 감소, 번호 본문 미인용 0건, 존재하지 않는 번호 인용 0건, 약한 도메인 출처 68개 / 50개 글로 유지 (이 68개가 모두 잘못됐다는 뜻 아님).
- [수정 후 54건 기술 및 27쌍 hreflang 검사](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42941322886): 공개 54/54 정상, 한국어 27/영어 27, 27/27쌍 정상, Canonical 오류 0, 총 이미지 108개, 번호 참고문헌 450개, robots.txt/ads.txt/sitemap/정책 주요 8개 URL HTTP 200, 내부 URL 6개 검사 중 깨진 링크 0개. 이것은 Google의 고유한 가치 심사 통과 판정이 아님.
- **여전히 미완료**: 남은 약한 출처 68개의 개별 주장 적합성 판정/정리, 독자 관점의 독창적 분석과 이미지 108개 라이선스 육안 검증, Google Search Console 색인 및 애드센스 관리자 세부 반려 사유 확인. 재신청·자동 새 게시/승인 서명/유료 API 과금 변경 **0건**. 이 상태에서 재신청 완료라고 기록하지 말 것.


## 2026-11-11 OpenSEO 독립 사이트 크롤링 및 Search Console 연결 상태

- OpenSEO 전용 프로젝트: https://app.openseo.so/p/b23abd92-03bc-4c4a-a969-4958c019f6b9
- 무료 JavaScript 비렌더링/비Lighthouse 사이트 크롤링: https://app.openseo.so/p/b23abd92-03bc-4c4a-a969-4958c019f6b9/audit?auditId=b500fb68-c4e2-4bd6-8c14-86f06f5cdb4b
- **크롤러 완료:** 50페이지 조사, HTTP 200 **45**, 301 **4**, 429 **1** (영어 라플레시아 `/en/rafflesia-arnoldii-worlds-largest-single-flower/`). 429는 해당 OpenSEO 자동 수집기에 한 번 관측된 응답이며 Googlebot 차단·방문자 오류·AdSense 반려 원인이라고 단정할 수 없음. 기존 GitHub Actions 54/54 HTTP 200 검사는 다른 시간·수집자로서 결과가 다르므로 캐시/요청 빈도/UA 차이 등 근거 추가 필요.
- 크롤러 경고: 누락된 메타 설명 **6** (운영자 작성자 페이지 1 + 영어 카테고리 5), 중복 메타 설명 **3** (홈 및 /page/2/ /page/6/), 단문 분류 **1** (/contact-and-corrections/). 단문 판정은 정책 페이지가 부실하다는 증거가 아님. 참고 정보: title too long **17**, meta too long **11**, meta too short **10**, author noindex **1** (설정 의도 확인 전 수정 금지).
- OpenSEO 검색 성능 조회 결과: Search Console 연결 `not_connected`; OpenSEO에서 보이는 Google 계정 및 GSC 속성 **0개**. Google이 실제 색인한 URL 수, 제외 이유, 자연 검색 클릭/노출은 **현재 확인 불가**. 사용자 Google 인증 필요: https://app.openseo.so/p/b23abd92-03bc-4c4a-a969-4958c019f6b9/search-performance
- **우선 판단:** (A) Search Console 인증 후 대표 글 10개 URL 색인 상태/이유를 읽기 전용으로 검사, (B) 429 반복·UA/시간대별 재현 여부만 추가 점검, (C) 사이트 전체 사용자 경험/독창성·출처 적합성을 최우선으로 유지, (D) 메타 길이와 아카이브 설명은 검증 가능한 범위의 안전 변경만 실시. Google 접근을 위해 사이트 보안 설정을 무조건 완화하지 말고, 억지로 50개 경고를 0으로 만들기 위한 SEO 전면 개조를 피할 것.
- OpenSEO 프로젝트 생성, 사이트 크롤링, Search Console 확인에는 **추가 연구 크레딧을 쓰지 않았음**. 유료 API·AI 추적·정기 구독 설정 없음.


## 2026-11-11 실제 Google Search Console 연결 및 공개 54건 전수 색인 판정

- OpenSEO 프로젝트 `b23abd92-03bc-4c4a-a969-4958c019f6b9`에서 Google Search Console 속성 `https://taxonguru.com/`을 직접 연결했음을 API로 확인. 연결 Google 계정에 해당 속성 소유자 권한이 있음. GSC API 확인은 무료/읽기 전용.
- 2026-10-12~2026-11-08 Search Analytics **완료된 28일** 기준 페이지 행 76개, 클릭 합계 **11**, 노출 합계 **822**, 클릭 발생 페이지 **10개**. 과거 초안, 카테고리, 정책 페이지 URL이 실적에 포함되므로 76개를 현시점 공개/색인 글 개수로 오해하지 말 것. 검색 실적은 AdSense 정책 승인 여부와 별개.
- 실제 WordPress 인증 REST의 [읽기 전용 현재 공개 상태 비교](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42974335204): `colossal-squid-giant-cephalopod` 한국어는 현재 초안(ID 190)이고 공개 주소 HTTP 404; 해당 영어 공개 슬러그는 404이면서 API 검색에 공개/현 초안 자료 없음. `hydnellum-peckii-devils-tooth` 한국어(ID 260)와 `bleeding-tooth-fungus-hydnellum-peckii-guide` 영어(ID 535)는 모두 현재 초안이고 실제 공개 URL HTTP 404. 이 중 hydnellum 2 URL은 GSC에서 마지막 크롤일 11/2~3 기준 **색인 PASS(과거 정보)**로 보임. 반대로 colossal squid 2 URL은 GSC에서 11/9 **NOT_FOUND 404**로 반영됨. **절대 자동으로 초안을 재공개하지 말 것.** 실제 실험 User-Agent의 `Googlebot` 문자열 요청은 403이었으나 이는 인증된 실제 Googlebot이 아니며 실제 Google 차단 증거로 간주하지 말 것. 최근 실제 GSC가 Googlebot MOBILE 정상 색인 53건을 보고하므로 사이트 보안을 임의로 약화시키지 말 것.
- [WordPress 공개 54개 URL 목록 추출 증거](https://github.com/Hwanss/taxon-guide-auto/actions/runs/42974552411): 54개 모두 `status=publish`와 URL을 실제 확인. 이 목록 **54개 전체**를 OpenSEO `inspect_urls`로 10개 이하 단위로 전수 조회한 결과: **53개 PASS, 1개 NEUTRAL(“Google에는 아직 알려지지 않은 URL입니다”), 0개 canonical 불일치**. PASS 53건은 Google의 마지막 저장 색인 상태이며 현재 실시간 크롤링을 뜻하지 않음; 그래도 대규모 미색인 문제는 발견되지 않음. 예외 공개 페이지 `https://taxonguru.com/corpse-flower-giant-stinker/` (Titan arum 한국어). GitHub QA에서는 공개 URL HTTP 200이며 GSC는 아직 해당 URL의 색인/크롤 기록이 없다고 표시. 다음에는 실제 sitemap 및 관련 내부 링크 노출/정규 URL/noindex 여부 검토; 필요한 경우 사용자가 Search Console에서 URL 검사→색인 생성 요청을 수동 실행할 수 있음.
- [Google 공식 URL Inspection 문서](https://support.google.com/webmasters/answer/9012289/): URL 검사 API/일반 기본 결과는 **Google에 저장된 마지막 색인 상태**이며 실시간 테스트와 다르므로 공개 초안/404 및 최신 사이트 수정과의 시차를 정상적으로 해석해야 함.
- Google AdSense 관리자 내 구체적 반려 사유/정책 센터 화면과 Search Console **수동 조치** 보고서는 이 단계에서 조회하지 않았으며, **53/54 색인 성공도 광고 승인 보장은 아님**. 현재 최우선 과제는 과학 주장별 남은 출처 68건 개별 검수, 사용자 관점의 독창성, 108개 이미지 이용 근거 확인, 품질 미달 초안 비공개 유지.
