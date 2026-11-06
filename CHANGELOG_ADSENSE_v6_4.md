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

## 2026-11-06: Website UX and cited editorial improvements
- Corrected the two Armillaria homepage excerpts; original published article contents and dates were preserved.
- Updated public WordPress author display to TaxonGuru 운영자; added active footer CSS to display just the publication date rather than concatenating publication and modification dates.
- Added four researched bilingual comparison sections (Armillaria area record and Victoria species/weight distinctions), independently backed by Guinness and RBG Kew references, with original posts backed up and WordPress re-read validation.
- Restored mutation workflows to dry-run. AI auto-publication and rewriting remain frozen pending editorial sign-off.
- This commit triggers read-only AdSense Recovery/Public Guard/Readiness for a post-change snapshot; no reapplication is requested.

## 2026-11-06 Final 58-article verification
- Re-read all 58 published WordPress articles and checked 4,127 in-text citation links against 480 reference entries; found zero broken internal reference IDs.
- Full bibliography reachability audit: 236 distinct source URLs; final result 180 reachable, 55 access-restricted, 1 network error, zero HTTP 404/410. The remaining DOI network error was independently identified at the original journal's publisher site.
- Corrected six published articles on giant sequoia mass versus trunk-volume records, Quetzalcoatlus shoulder height, and documented mimic-octopus behavior; original posts backed up.
- The single malformed Quetzalcoatlus DOI, affecting two language editions, was repaired and the 236-source URL scan was repeated.
- Independent editorial sign-off remains FALSE. Human fact-check and originality review is NOT complete. Do not imply Google AdSense is approved or guaranteed.
- Trigger read-only readiness validation for the live changes.

## 2026-11-06: Visitor-first site and AdSense pre-application improvements
- Published researched bilingual TaxonGuru reading guide /reading-guide/ with five cross-topic comparisons and verified institutional sources. Linked from live homepage sidebar and existing footer menu; empty recent-comments widget unassigned, not deleted. Public HTTP 200 and visible link verified.
- Corrected Puya raimondii bilingual headlines, excerpts and flowering-age claims using botanical and peer-reviewed sources, including the exceptional 28-year cultivated record. Originals backed up; live updates verified.
- Fixed the previously blank WordPress site tagline with a precise bilingual biological science purpose. Preserved original site URLs, search visibility and AdSense settings.
- Verified public robots.txt, both XML sitemap endpoints, ads.txt with Google DIRECT record, an AdSense client/script, index-follow, policy pages and canonical homepage HTTPS. Technical checks do not prove AdSense approval or ad serving.
- All one-time write workflows restored to read-only previews. Editorial signoff remains FALSE. Run safe automated readiness again, but do not auto-submit AdSense.

## 2026-11-06 Independent originality risk triage and editorial actions
- Applied Google's published criteria concerning useful, original content and scalable AI rewriting as a qualitative EDITORIAL standard, not an imitation of Google's proprietary approval classifier.
- A direct 58-post review surfaced two pairs with under-supported health/science claims: Axolotl/neoteny and regeneration (WordPress IDs 34, 834); Hydnellum peckii/no known lethal toxins and medical anticoagulant implications (IDs 260, 535).
- Four posts temporarily moved from PUBLISHED to DRAFT. All originals and metadata were backed up in Actions artifact; no posts deleted; anonymous REST recheck returned HTTP 401. Publication should resume only after primary-source substantiation and rewritten claims.
- Improved BOTH published ghost pipe (Monotropa uniflora, IDs 254, 518) articles using a human-readable original comparison of two actual 2025 peer-reviewed studies. Explained that non-detection of certain toxins in 50 samples and surveyed traditional uses do NOT prove efficacy or ingestion safety. Original WP content archived and verified.
- Restored all writing workflows to preview-only. Public count expected 54, draft queue expected 54 (including 4 newly held); automatic publishing/editorial signoff remains OFF.
- Google AdSense review status is NOT yet known; no auto-approval or AdSense reapplication has been performed. Independent human expert review is still pending.

## 2026-11-06 54-post progress: eight priority posts actually updated and independently verified
- Full WordPress source preflight and backups for eight published posts (Welwitschia 27/854, Coelacanth 32/839, Riftia 116/797, Archaeopteryx 201/386).
- Added primary-study and institutional evidence comparisons. Narrowed misleading claims about fog uptake and groundwater, lifespan/gestation estimates, vent-fluid temperature vs animal habitat, and reconstructed flight.
- 8/8 posts re-read after REST edits; public status, images and numbered references retained.
- Independently requested all eight public URLs anonymously: HTTP 200 and evidence panels present for 8/8. Run https://github.com/Hwanss/taxon-guide-auto/actions/runs/42193588279.
- Count of currently published posts should remain 54. Cumulative progress for current final editorial batch: 10 targeted updated, remaining 44 need individual source/originality review. This is NOT a claim that expert signoff is complete.
- All editorial workflows restored to no-write preview, no AdSense submission requested.

## 2026-11-06 B-priority eight science topics corrected (review batch 18/54)
- Published precise source-backed corrections in KO/EN for Venus flytrap IDs 26/859, Echiniscus testudo IDs 154/739, Atlantic horseshoe crab IDs 146/763, Tiktaalik IDs 150/751.
- Evidence: Bohm et al 2016 action potentials; Youngsteadt et al 2018 pollinator field observations; Roszkowska et al 2023 species-specific anhydrobiosis; E. testudo multiomics; USP <86> recombinant endotoxin assay; 2026 FDA review; 2006 Nature and 2024 PNAS Tiktaalik axial skeleton.
- Corrected outdated claims including a universal feeding percentage, all-condition invincibility, blanket reagent approval and nonexistent Tiktaalik sacral specialization.
- Original WordPress content backed up in Actions 42196882656; eight live posts re-read; anonymous public page checks HTTP 200 and visible evidence panels for 8/8 in 42197102778.
- Current public content count expected 54. Current focused editorial improvements: 18/54; remaining 36 require source-by-source verification. This does not imply independent expert signoff or Google AdSense approval. Keep auto publishing and rewriting disabled and AdSense reapplication pending.


## 2026-11-06: Third batch eight posts revised and verified, cumulative 26/54
- Titan arum (24,864): Kew Plants of the World Online states systematic natural pollination research is still lacking; replaced unsupported claims that specific insect groups have been proven functional pollinators, retained EN threat status.
- Tyrannosaurus (30,849): replaced misleading "definitive maximum speed 16-40 km/h"; compared 2017 skeletal-stress model, 2021 preferred walking speed 1.28 m/s, and 2024 maximum-body-mass population estimates.
- Great Basin bristlecone pine (111,792): corrected categorical claim that Methuselah is the absolute verified oldest tree; showed disagreement over anonymous 5,000-plus-year-old bristlecone record in US federal, Guinness, and 2026 genome research.
- Rafflesia arnoldii (137,787): distinguished measured 111-cm diameter 2020 Guinness flower from species-level upper mass claim of 11 kg, and official IUCN NE status from conservation warnings.
- Eight full source HTML originals backed up, exact phrase matches checked, posts remained published, original numbered references and media unchanged. WordPress edit verification: https://github.com/Hwanss/taxon-guide-auto/actions/runs/42199550805.
- Anonymous visitor checks for eight live URLs: 8/8 HTTP 200, evidence comparisons visible: https://github.com/Hwanss/taxon-guide-auto/actions/runs/42199888712.
- Total focused articles improved in the current 54-post plan: **26**; **28** still require specific content review. Automatic writing/offline editing and AdSense reapplication remain disabled; human expert signoff is NOT yet complete.
