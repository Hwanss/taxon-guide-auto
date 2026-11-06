"""Evidence-led corrections to eight public TaxonGuru science articles.

Subjects: Architeuthis, Dracaena cinnabari, goblin shark, Nautilus.
Safeguards: read all eight WP originals + strict exact phrase check before writing;
back up originals; preserve HTML, images, existing refs, status, dates and slugs;
verify each WordPress write; no AdSense signoff. Dry-run is default.
"""
import os,re,json
from datetime import datetime,timezone
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("FOUR_TOPICS_APPLY","false").lower()=="true"
OUT=Path("audit_output/four_topic_evidence");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
MARK="taxonguru-verified-20261106-topic-review"
SOURCES={
"squid_museum":"https://ocean.si.edu/ocean-life/invertebrates/giant-squid",
"squid_genetics":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3619516/",
"dragon_review":"https://pubmed.ncbi.nlm.nih.gov/34337055/",
"dragon_fog":"https://www.mdpi.com/2071-1050/11/13/3557",
"dragon_liver":"https://www.ncbi.nlm.nih.gov/books/NBK604848/",
"goblin_primary":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4901258/",
"goblin_museum":"https://www.floridamuseum.ufl.edu/discover-fish/species-profiles/goblin-shark/",
"nautilus_noaa":"https://www.fisheries.noaa.gov/species/chambered-nautilus",
"nautilus_geometry":"https://doi.org/10.1007/s00004-018-0419-3",
}
def l(src,text):
 return f'<a href="{SOURCES[src]}" target="_blank" rel="noopener noreferrer">{text}</a>'
ROWS={
162:{
 "edits":[
 ("단 하나의 범세계적 종(panmictic global species)임이 과학적으로 입증되었습니다",
  "단일 범세계적 종이라는 가설과 부합하는 결과가 나왔지만, 미토콘드리아 DNA 이외의 핵 유전체 검증까지 마친 최종 증명은 아닙니다"),
 ],
 "insert":f'''<section class="{MARK}"><h2>13m 기록과 43개 유전체: 무엇을 측정한 연구일까요?</h2>
<p>대왕오징어가 ‘얼마나 큰가’와 ‘몇 종인가’는 서로 다른 자료와 실험 방법으로 검증해야 합니다.</p>
<table><thead><tr><th>비교할 질문</th><th>실제 조사 방법</th><th>해석의 한계</th></tr></thead><tbody>
<tr><td>최대 길이</td><td>{l("squid_museum","스미스소니언 자연사박물관")}은 실물 확인된 전체 길이 약 13m와 최대 외투장 약 2.25m를 구분합니다.</td><td>긴 촉완은 사후 늘어나거나 훼손될 수 있어 역사적 20m 보고와 같은 신뢰도로 비교하면 안 됩니다. 20m 가능성에 관한 간접 추정도 실물 기록은 아닙니다.</td></tr>
<tr><td>세계에 한 종만 있나요?</td><td>{l("squid_genetics","2013년 Proceedings B 연구")}는 세계 각지 표본 43개에서 미토콘드리아 유전체 차이가 매우 적고 지역별 계통 분화가 뚜렷하지 않다고 보고했습니다.</td><td>연구진 스스로 단일 종 가설을 더 확실히 검증하려면 핵 DNA 분석이 필요하다고 밝혔습니다.</td></tr>
</tbody></table>
<p><strong>편집 판단:</strong> 표본으로 <em>관측된 최댓값</em>, 생물학적 최대치에 대한 <em>모델 추정</em>, 특정 유전자 표지에서 도출한 <em>종 가설</em>을 같은 수준의 확정 사실로 취급하지 않습니다.</p></section>'''
},
715:{
 "edits":[
 ("researchers confirmed that all giant squids across the globe belong to a single, global, panmictic species—meaning a single, interconnected breeding population without localized genetic isolation: Architeuthis dux",
  "a study of 43 globally sourced specimens found little mitochondrial variation and no clear geographic structure, supporting a one-species hypothesis for Architeuthis dux; the authors expressly called for nuclear-DNA verification"),
 ],
 "insert":f'''<section class="{MARK}"><h2>Two different kinds of evidence: measured length versus genetic species hypotheses</h2>
<p>The words “verified” and “single species” need different tests. The strongest accessible sources do not justify claiming that either a 20 m living squid or complete genetic mixing has been conclusively demonstrated.</p>
<table><thead><tr><th>Evidence</th><th>What was observed</th><th>What remains open</th></tr></thead><tbody>
<tr><td>{l("squid_museum","Smithsonian squid specimen overview")}</td><td>Largest documented total length about 13 m; longest mantle measurement about 2.25 m.</td><td>Flexible tentacles, incomplete carcasses and inferred larger animals make reports of 20 m distinct from an actual measured specimen.</td></tr>
<tr><td>{l("squid_genetics","2013 Proceedings B research")}</td><td>43 specimens showed very low mitochondrial diversity and no detectable mitochondrial geographic structure.</td><td>The study concluded that a single species is strongly supported but nuclear markers are needed to test that interpretation fully.</td></tr>
</tbody></table>
<p><strong>Scientific takeaway:</strong> direct measurements, model-based upper bounds and results from one class of DNA are all valuable, but should not be presented as interchangeable proof.</p></section>'''
},
176:{
 "edits":[
 ("이 붉은 수지 속에는 비플라보노이드와 찰콘 등 다량의 항균 및 약리 성분이 포함되어 있습니다",
  "이 붉은 수지에서는 플라보노이드류와 찰콘 등 다양한 화합물이 분리됐으며, 일부 추출물의 생리활성은 실험실 수준에서 연구됐습니다"),
 ("이러한 화학 성분 덕분에 용혈수는 외부 감염으로부터 자신을 보호할 수 있습니다",
  "상처를 덮는 수지의 역할은 연구 대상이지만, 특정 성분의 시험관 항균 활성이 나무의 모든 감염을 차단하거나 사람의 치료 효능까지 입증하는 것은 아닙니다"),
 ],
 "insert":f'''<section class="{MARK}"><h2>용혈수의 붉은 수지는 약일까요? 생태학과 약리 연구를 구분해 읽기</h2>
<p>소코트라 용혈수의 붉은 수지는 문화재료이자 전통적으로 사용된 약재입니다. 그러나 <strong>전통적인 사용 기록·성분 분리·시험관 생리활성·사람의 임상 효능</strong>은 각각 다른 단계의 근거입니다.</p>
<table><thead><tr><th>자료</th><th>확인된 사실</th><th>결론에서 제외할 것</th></tr></thead><tbody>
<tr><td>{l("dragon_review","2021년 수지 성분 문헌 검토")}</td><td>여러 계열의 화합물과 항균·항염 등 실험적 활성 연구를 정리했습니다.</td><td>이 자료 자체가 모든 전통적 사용법의 치료 효과나 복용 안전성을 입증하는 임상시험은 아닙니다.</td></tr>
<tr><td>{l("dragon_liver","미국 NIH LiverTox 자료")}</td><td>‘용혈’이라는 상품명에는 <em>Dracaena</em>뿐 아니라 <em>Croton</em>, 등나무류 등 다른 식물의 붉은 수지도 포함될 수 있다고 설명합니다.</td><td>서로 다른 종에서 채취한 수지의 성분·효능·안전성을 동일한 것으로 취급할 수 없습니다.</td></tr>
<tr><td>{l("dragon_fog","2019년 소코트라 보전 연구")}</td><td>우산형 수관이 안개와 물방울을 포집해 토양의 수분과 미세서식 환경 유지에 기여할 수 있다고 설명합니다.</td><td>안개 포집의 생태학적 기능은 수지가 약효를 갖는다는 근거가 아닙니다.</td></tr>
</tbody></table><p>따라서 이 글은 생물학과 문화사를 다루며 수지 복용·자가치료를 권하지 않습니다.</p></section>'''
},
673:{
 "edits":[
 ("Chemical isolation studies show high concentrations of non-flavonoids and chalcones, which exhibit powerful antimicrobial and pharmacological properties",
  "Chemical studies have isolated flavonoid-related compounds, chalcones and other constituents; some extracts have shown biological activity in laboratory settings, which is not the same as established medical effectiveness"),
 ("The red color is simply a visual byproduct of these defensive chemical compounds working together to sterilize injured plant tissue",
  "The red color reflects chemical constituents of the resin, while its ecological defensive functions and laboratory bioactivity are separate questions; no evidence here proves complete sterilization of every tree wound"),
 ],
 "insert":f'''<section class="{MARK}"><h2>What a red resin can tell us—and what it cannot</h2>
<p>The appearance of resin, its possible role in protecting wounded bark, and a medicine proven effective in patients are not the same claim.</p>
<table><thead><tr><th>Research level</th><th>What is supported</th><th>What is not shown</th></tr></thead><tbody>
<tr><td>{l("dragon_review","2021 phytochemistry review")}</td><td>Catalogues chemical constituents and experimental antioxidant, antimicrobial and other bioactivities.</td><td>Isolating compounds or studying extracts does not prove human clinical treatment or safe self-medication.</td></tr>
<tr><td>{l("dragon_liver","NIH LiverTox background")}</td><td>The commercial term “dragon’s blood” can refer to red resins from multiple plant genera, not just <em>Dracaena cinnabari</em>.</td><td>Traditional observations about one species cannot automatically be transferred to another resin product.</td></tr>
<tr><td>{l("dragon_fog","Socotra vegetation and cloud-water study")}</td><td>The dense canopy can intercept cloud droplets and affect water retention and habitat beneath the tree.</td><td>Hydrological ecosystem services do not provide evidence of clinical pharmacological efficacy.</td></tr>
</tbody></table><p><strong>Evidence boundary:</strong> this article explains published biology; it neither demonstrates a medical treatment nor recommends ingesting resin.</p></section>'''
},
231:{
 "edits":[
 ("이는 변동성이 적고 안정한 심해 환경이 이 고대 계통의 유전적 구조를 오랜 세월 동안 커다란 분화 없이 안정적으로 지켜주었음을 보여주는 중요한 과학적 증거입니다",
  "하지만 제한된 분자자료만으로 심해 환경이 1억 2,500만 년 동안 진화를 멈추게 했거나 유전적 분화가 없었다고 입증할 수는 없습니다"),
 ],
 "insert":f'''<section class="{MARK}"><h2>2016년 촬영 연구에서 실제로 확인한 고블린상어 턱의 속도</h2>
<p>고블린상어의 턱은 ‘괴물처럼 늘 튀어나온’ 구조가 아닙니다. 핵심은 실제 해양 현장에서 촬영한 <strong>두 개체의 다섯 차례 먹이 포획 동작</strong>을 수치로 분석했다는 점입니다.</p>
<table><thead><tr><th>실제 측정</th><th>논문의 값</th><th>해석상의 한계</th></tr></thead><tbody>
<tr><td>{l("goblin_primary","Nakaya 외, Scientific Reports (2016)")}</td><td>하악 선단의 최대 전방 이동 속도 약 3.14m/s, 턱 선단의 이동 거리 전체 길이의 약 8.6~9.4%입니다.</td><td>상어 몸 전체의 헤엄 속도나 모든 개체의 고정 능력치가 아니라 특정 촬영 개체·동작에서 측정한 턱의 값입니다.</td></tr>
<tr><td>{l("goblin_museum","플로리다 자연사박물관의 분류 자료")}</td><td>고블린상어는 현재 마귀상어과의 유일한 현생 종이지만, 관련 화석 분류군과의 관계는 논의돼 왔습니다.</td><td>현생 종의 DNA가 1억 년 이상 변하지 않았다는 뜻이 아닙니다. 오래된 것은 보다 넓은 진화 계통입니다.</td></tr>
</tbody></table><p><strong>독자가 알아야 할 점:</strong> 턱의 발사 속도, 유영 속도, 계통의 나이는 서로 다른 변수입니다. 고대 계통에 속한다고 해서 진화가 중단됐다고 해석할 수 없습니다.</p></section>'''
},
460:{
 "edits":[
 ("The dramatic jaw extension occurs exclusively during prey capture",
  "The best-documented filmed jaw extensions were feeding strikes; a handful of recordings does not establish that the jaws can never extend for any other reason"),
 ],
 "insert":f'''<section class="{MARK}"><h2>Slingshot feeding: what five filmed strikes can establish</h2>
<p>The most useful evidence is not a dramatic illustration but the time-resolved underwater footage of two individual sharks during five prey-capture events.</p>
<table><thead><tr><th>Question</th><th>Direct observation</th><th>Limit</th></tr></thead><tbody>
<tr><td>{l("goblin_primary","Nakaya et al., Scientific Reports (2016)")}</td><td>Maximum lower-jaw tip extension speed was approximately 3.14 m/s; jaw-tip projection covered around 8.6–9.4% of body length.</td><td>This is jaw velocity, not shark swimming speed, and is a small sample of behavior, not a universal fixed maximum for every specimen.</td></tr>
<tr><td>{l("goblin_museum","Florida Museum of Natural History")}</td><td>The only extant goblin-shark species belongs to a lineage with extinct relatives inferred from fossils.</td><td>An ancient family does not prove that the modern species or its DNA has been unchanged for 125 million years.</td></tr>
</tbody></table><p>Separating movement measured on video from evolutionary inference tells a more reliable story than the ‘unchanged monster’ label.</p></section>'''
},
209:{
 "edits":[
 ("는 플라이스토세 이후에야 비로소 등장한 비교적 최근의 종입니다",
  "의 정확한 출현 시점을 플라이스토세 이후라고 확정할 근거는 부족합니다. 약 5억 년이라는 수치는 현대 종 하나가 아니라 훨씬 오래된 앵무조개아강 계통에 관한 것입니다"),
 ("실제 측정된 앵무조개 껍데기의 성장 비율은 약 1.31에서 1.33 사이를 형성합니다",
  "껍데기의 나선 측정값은 종과 개체, 측정하는 기하학적 비율에 따라 달라집니다. 일부 대규모 표본 분석에서 앵무조개속의 비율 약 1.31이 보고됐지만 모든 껍데기의 고정된 수치라는 뜻은 아닙니다"),
 ],
 "insert":f'''<section class="{MARK}"><h2>앵무조개의 ‘완벽한 수학’과 실제 생물학의 차이</h2>
<p>앵무조개의 나선은 보기 아름답지만 모든 표본이 황금비 1.618을 따르는 것은 아닙니다. 또한 <strong>계통의 나이와 현생 종의 나이</strong>를 구별해야 합니다.</p>
<table><thead><tr><th>자료·측정</th><th>확인 가능한 사실</th><th>잘못된 일반화</th></tr></thead><tbody>
<tr><td>{l("nautilus_geometry","2019년 Nautilus 나선 실측 연구")}</td><td>여러 표본을 비교해 앵무조개속의 특정 형상비가 약 1.310에 가까울 수 있다고 보고하고, 황금비 신화에 반론을 제시했습니다.</td><td>표본·종·성장단계 및 비율의 정의를 무시한 ‘모든 앵무조개는 정확히 1.31’이라는 명제도 연구 결과가 아닙니다.</td></tr>
<tr><td>{l("nautilus_noaa","미국 NOAA 현생 앵무조개 자료")}</td><td>껍데기 내 여러 격실과 체관(siphuncle)의 수분·기체 조절, 약 10~15년의 늦은 성숙과 낮은 번식률을 설명합니다.</td><td>이 생리학적 기능으로 현생 종이 5억 년 동안 변하지 않았다는 주장까지 입증되지 않습니다.</td></tr>
</tbody></table><p><strong>편집 결론:</strong> 황금비와 다른 값이 측정됐다는 사실보다, 무엇의 비율을 어떻게 측정했는지를 알려주는 것이 더 중요한 과학 정보입니다.</p></section>'''
},
401:{
 "edits":[
 ("its actual expansion ratio consistently measures between 1.31 and 1.33",
  "measured shell proportions differ by specimen, species and how the ratio is defined; a multi-shell study reported a value near 1.31 for one Nautilus geometric aspect, not a universal growth constant"),
 ("This specific species appeared long after the Pleistocene epoch",
  "The exact first appearance of the present species cannot be fixed as 'long after the Pleistocene' solely from the long evolutionary history of its much older Nautiloidea lineage"),
 ],
 "insert":f'''<section class="{MARK}"><h2>Measuring Nautilus: a spiral is not a universal golden-ratio template</h2>
<p>Two numbers must not be conflated: the ancient age of the wider nautiloid lineage and the much younger, uncertain first appearance of a living species. Nor is every shell bound to one precise geometric constant.</p>
<table><thead><tr><th>Evidence</th><th>Observed or documented</th><th>Not established</th></tr></thead><tbody>
<tr><td>{l("nautilus_geometry","Empirical 2019 shell-geometry study")}</td><td>Measurements across Nautilus samples challenged the golden ratio 1.618 myth and identified ratios near 1.310 for particular shell aspects.</td><td>A single fixed 1.31 expansion ratio for every species, individual, chamber or life stage.</td></tr>
<tr><td>{l("nautilus_noaa","NOAA chambered nautilus species profile")}</td><td>Chambers and a siphuncle regulate buoyancy; slow maturation and low reproductive output contribute to conservation vulnerability.</td><td>These traits are not evidence that Nautilus pompilius is an unchanged 500-million-year-old species.</td></tr>
</tbody></table><p>Understanding measurement definitions and the lineage/species distinction provides more information than simply repeating the golden-spiral myth.</p></section>'''
}
}
def api(method,path,**kwargs):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=80,**kwargs)
 if r.status_code>=400:raise RuntimeError(f"{method} {path} HTTP {r.status_code}: {r.text[:200]}")
 return r.json()
def main():
 planned={}
 for pid,spec in ROWS.items():
  p=api("GET",f"posts/{pid}",params={"context":"edit"})
  if p.get("status")!="publish":raise RuntimeError(f"{pid}: not published")
  old=p["content"].get("raw") or p["content"].get("rendered") or ""
  if MARK in old:
   print("FOUR_ALREADY_APPLIED",pid,flush=True);continue
  new=old
  for before,after in spec["edits"]:
   n=new.count(before)
   if n!=1:raise RuntimeError(f"{pid}: unexpected exact phrase match count {n} on {before[:90]}")
   new=new.replace(before,after,1)
  first=re.search(r"<h2\b",new,re.I)
  if not first:raise RuntimeError(f"{pid}: no H2 insertion point")
  new=new[:first.start()]+spec["insert"]+new[first.start():]
  refs=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',old))
  if not refs or refs!=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',new)):
   raise RuntimeError(f"{pid}: original reference IDs changed")
  imgs=len(re.findall(r"<img\b",old,re.I))
  if imgs!=len(re.findall(r"<img\b",new,re.I)):raise RuntimeError(f"{pid}: images changed")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False),encoding="utf8")
  planned[pid]={"old":old,"new":new,"refs":refs,"imgs":imgs,"url":p.get("link")}
 print("FOUR_PREFLIGHT",len(planned),"complete original WordPress backups",flush=True)
 results=[]
 for pid,row in planned.items():
  if APPLY:
   api("POST",f"posts/{pid}",json={"content":row["new"]})
   final=api("GET",f"posts/{pid}",params={"context":"edit"})
   content=final["content"].get("raw") or ""
   if final["status"]!="publish" or content.count(MARK)!=1:raise RuntimeError(f"{pid}: article verification failed")
   if set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',content))!=row["refs"]:raise RuntimeError(f"{pid}: reference IDs missing")
   if len(re.findall(r"<img\b",content,re.I))!=row["imgs"]:raise RuntimeError(f"{pid}: image count changed")
  res={"id":pid,"status":"UPDATED" if APPLY else "PREVIEW","original_length":len(row["old"]),
       "new_length":len(row["new"]),"url":row["url"]}
  results.append(res)
  print("FOUR_ARTICLE="+json.dumps(res,ensure_ascii=False),flush=True)
 (OUT/"report.json").write_text(json.dumps({"apply":APPLY,"checked":len(planned),"items":results,
   "generated_utc":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("FOUR_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(r["status"]=="UPDATED" for r in results),"preview":sum(r["status"]=="PREVIEW" for r in results)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
