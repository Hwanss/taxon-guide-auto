"""Precision updates to 8 priority TaxonGuru pages; no article duplication.

Four KO/EN topics: Welwitschia water; coelacanth scale age; Riftia heat;
Archaeopteryx flight fossil. Preflight EVERY post, save originals, then update.
Dry-run default. Does not modify original media, slugs, post status, or signoff.
"""
from __future__ import annotations
import os,json,re
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime,timezone
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("PRIORITY8_APPLY","false").lower()=="true"
OUT=Path("audit_output/priority8_evidence");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
MARKER="taxonguru-priority8-source-review"
SOURCES={
 "genome":"https://www.nature.com/articles/s41467-021-24528-4",
 "sanbi":"https://pza.sanbi.org/welwitschia-mirabilis",
 "fog1973":"https://journals.co.za/doi/10.10520/AJA10115498_87",
 "coel":"https://pubmed.ncbi.nlm.nih.gov/34143958/",
 "noaa":"https://www.fisheries.noaa.gov/species/african-coelacanth",
 "smithsonian":"https://ocean.si.edu/ecosystems/deep-sea/microbes-keep-hydrothermal-vents-pumping",
 "riftia":"https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0333996",
 "flight2018":"https://www.nature.com/articles/s41467-018-03296-8",
 "flight2025":"https://www.nature.com/articles/s41586-025-08912-4",
}
def link(key,label):
 return f'<a href="{SOURCES[key]}" target="_blank" rel="noopener noreferrer">{label}</a>'
CONTENT={
27:{
 "changes":[
  ("웰위치아가 잎 표면으로 안개 수분을 흡수하는 것은 어디까지나 보조적인 수단일 뿐입니다",
   "웰위치아 잎에 응결된 안개 물방울은 잎을 따라 뿌리 주변으로 흘러갈 수 있습니다. 그러나 기공을 통한 직접 흡수 여부는 연구·자료에 따라 서로 다른 설명이 존재합니다"),
  ("이 뿌리가 지표면 아래 아득히 깊은 지하수층에 도달함으로써 비가 거의 내리지 않는 사막에서도 안정적으로 물을 퍼 올릴 수 있습니다",
   "뿌리를 통한 수분 흡수에는 안개가 지표에 남기는 수분과 드문 강우, 지역별 토양 조건도 관여합니다. 모든 개체가 깊은 지하수층에 닿는다고 단정하기보다 실제 서식지의 물 공급을 구분해야 합니다"),
 ],
 "ref_replace":(3,"genome"),
 "note":f'''<section class="{MARKER}"><h2>연구 근거를 비교해 본 웰위치아의 물 확보 방식</h2><table><thead><tr><th>질문</th><th>자료가 보여주는 사실</th><th>확정할 수 없는 부분</th></tr></thead><tbody>
<tr><td>안개가 물 공급에 기여할까요?</td><td>{link("sanbi","남아프리카국가생물다양성연구소(SANBI)")}는 잎에 맺힌 응결수가 뿌리 주변으로 흐르는 구조와 안개·강우의 기여를 설명합니다.</td><td>안개 수분이 모든 지역·모든 개체에서 같은 비율로 공급된다는 뜻은 아닙니다.</td></tr>
<tr><td>잎이 물을 직접 흡수할까요?</td><td>{link("fog1973","1973년 추적자 연구")}에서는 잎에 맺힌 물의 흡수·이동 가능성을 제시했습니다. 반면 SANBI의 식물 소개는 기공을 통한 직접 흡수가 확인되지 않았다고 설명합니다.</td><td>서로 다른 시기·방법의 설명을 한 문장으로 단정해선 안 됩니다.</td></tr>
<tr><td>수천 년 수명을 만드는 유전자는 무엇일까요?</td><td>{link("genome","2021년 Nature Communications 유전체 연구")}는 두 장의 잎이 계속 자라는 기부 분열조직, 약 8,600만 년 전 유전체 배가와 DNA 메틸화 양상을 분석했습니다.</td><td>유전적 특징 하나가 장수의 유일한 원인이라는 인과관계까지 입증한 것은 아닙니다.</td></tr>
</tbody></table><p>기록의 핵심은 '안개만 마신다' 또는 '깊은 지하수만 이용한다' 같은 이분법을 피하고, <strong>잎 구조·토양 수분·생장 방식</strong>을 함께 살펴보는 데 있습니다.</p></section>'''
},
854:{
 "changes":[
  ("fog condensation on leaf surfaces provides valuable supplemental water",
   "condensed fog water can run off the leaves towards the root zone, contributing to local soil moisture"),
  ("taproot that descends far underground to tap into deep subterranean water tables",
   "taproot that accesses soil moisture; claiming that every plant reliably reaches a deep water table goes beyond the available field evidence"),
 ],
 "ref_replace":(3,"genome"),
 "note":f'''<section class="{MARKER}"><h2>Comparing the evidence: fog, roots and genome in Welwitschia</h2><table><thead><tr><th>Question</th><th>Evidence</th><th>Limit</th></tr></thead><tbody>
<tr><td>What does coastal fog contribute?</td><td>The {link("sanbi","South African National Biodiversity Institute")} describes condensation dripping from broad leaves towards the roots, alongside other moisture sources.</td><td>This does not establish an identical water budget for every plant in the Namib.</td></tr>
<tr><td>Do leaves directly absorb fog?</td><td>A {link("fog1973","1973 tracer study")} proposed uptake of condensed water through leaf tissue; SANBI's account cautions that direct stomatal uptake was not confirmed.</td><td>Contrasting methods and interpretations should not be presented as one proven mechanism.</td></tr>
<tr><td>Why can two leaves persist?</td><td>A {link("genome","2021 genome study")} describes the basal growth zone, a lineage-specific whole-genome duplication around 86 million years ago, and unusual methylation patterns.</td><td>The study does not identify a single gene that guarantees thousand-year survival.</td></tr>
</tbody></table><p><strong>Reader takeaway:</strong> distinguish plant structure, the route taken by water, and long-term genetic adaptation. They are connected hypotheses and observations, not interchangeable explanations.</p></section>'''
},
32:{
 "changes":[
  ("임신 기간은 약 5년에 이릅니다","임신 기간은 배아의 성장선 분석을 근거로 약 5년으로 추정됩니다"),
  ("최대 수명은 100년에 달하는 것으로 측정되어","최대 수명은 약 100년으로 추정되어"),
 ],
 "ref_replace":(8,"coel"),
 "note":f'''<section class="{MARKER}"><h2>실러캔스 수명 20년과 100년: 연구 결과를 읽는 방법</h2><table><thead><tr><th>연구·자료</th><th>근거</th><th>해석상의 한계</th></tr></thead><tbody>
<tr><td>초기 비늘 연구</td><td>눈에 잘 보이는 비늘 성장 무늬에 따라 최대 수명 약 20년이라는 추정이 제시됐습니다.</td><td>매우 가는 성장선이 누락되면 나이가 크게 과소평가됩니다.</td></tr>
<tr><td>{link("coel","Mahé 외, Current Biology (2021)")}</td><td>표본 27개의 비늘을 편광현미경으로 다시 분석해 약 100년 수명, 성숙 연령 40~69년, 임신 기간 약 5년을 재추정했습니다.</td><td>장기간 살아있는 개체를 직접 추적한 결과가 아닙니다. 임신 기간도 배아 성장선과 발달을 바탕으로 한 추정입니다.</td></tr>
<tr><td>{link("noaa","미국 NOAA 생물종 설명")}</td><td>장수·늦은 성숙·낮은 번식률 때문에 어업 혼획과 서식지 교란에 취약하다고 설명합니다.</td><td>보전상 위험을 이해하는 근거이지 정확한 개체수나 생존연령을 직접 측정한 자료는 아닙니다.</td></tr>
</tbody></table><p><strong>핵심:</strong> 100년과 5년은 중요한 연구 추정치이지만, 관찰로 확정된 모든 개체의 수명·임신 기간처럼 표현해서는 안 됩니다.</p></section>'''
},
839:{
 "changes":[
  ("requiring decades to mature and five years for a single pregnancy",
   "taking decades to reach maturity and with gestation estimated at roughly five years from scale and embryo data"),
 ],
 "ref_replace":(8,"coel"),
 "note":f'''<section class="{MARKER}"><h2>Why did the coelacanth lifespan estimate change fivefold?</h2><table><thead><tr><th>Evidence</th><th>Finding</th><th>Limit</th></tr></thead><tbody>
<tr><td>Earlier scale-line studies</td><td>Conspicuous lines suggested a lifespan of about 20 years.</td><td>Extremely fine annual markings were difficult to see.</td></tr>
<tr><td>{link("coel","Mahé et al., Current Biology (2021)")}</td><td>Polarized-light study of 27 museum specimens found fine annual circuli, suggesting a lifespan around 100 years and maturity at around 40–69 years. Embryonic scale growth supported an approximately five-year gestation.</td><td>The population was not tracked in the wild for a century. Gestation remains inferred, not directly observed across five years.</td></tr>
<tr><td>{link("noaa","NOAA Fisheries")}</td><td>Slow maturation and reproduction increase sensitivity to bycatch and disturbance.</td><td>Conservation risk is a separate question from lifespan measurement.</td></tr>
</tbody></table><p><strong>Scientific distinction:</strong> 'estimated from preserved specimens' is not the same as 'directly observed living to 100 years.' Interpretation changed because the method detected finer growth marks.</p></section>'''
},
116:{
 "changes":[],
 "note":f'''<section class="{MARKER}"><h2>섭씨 350도의 열수와 튜브벌레의 체온을 구분해야 하는 이유</h2><table><thead><tr><th>장소·방법</th><th>온도·결과</th><th>튜브벌레에 대한 해석</th></tr></thead><tbody>
<tr><td>열수분출구의 고온 굴뚝</td><td>{link("smithsonian","스미스소니언 해양 안내")}에 따르면 분출구 고온 유체는 약 250~400°C이며 주변에 확산되는 흐름은 약 5~100°C 등으로 폭넓습니다.</td><td>고온 유체의 온도가 그곳 동물의 몸이 견디는 온도는 아닙니다.</td></tr>
<tr><td>주변 바닷물과 섞이는 구역</td><td>차가운 심해수와 섞이면서 동물이 서식할 수 있는 상대적으로 낮은 온도 영역이 형성됩니다.</td><td>서식 지점의 수온은 위치와 시간에 따라 달라집니다.</td></tr>
<tr><td>{link("riftia","2025년 PLOS ONE의 열내성 문헌 검토")}</td><td>선행 실험을 인용해 <em>Riftia pachyptila</em>는 약 32~35°C를 2시간 노출했을 때 전 개체가 폐사한 시험 사례를 보고합니다.</td><td>2시간 실험의 치사 범위를 모든 자연환경의 절대 임계온도로 일반화해서는 안 됩니다.</td></tr>
</tbody></table><p><strong>핵심:</strong> 이 종의 독특함은 300°C에 버티는 몸이 아니라, 적절한 위치에 정착하고 황화수소를 이용하는 공생 세균에 물질을 공급하는 생리적 구조에 있습니다.</p></section>'''
},
797:{
 "changes":[],
 "note":f'''<section class="{MARKER}"><h2>Vent fluid temperature versus the temperature an animal can survive</h2><table><thead><tr><th>Evidence</th><th>Measurement</th><th>What it means</th></tr></thead><tbody>
<tr><td>{link("smithsonian","Smithsonian Ocean, vent overview")}</td><td>Superheated vent chimney fluids can reach approximately 250–400°C, whereas diffuse emissions span far cooler ranges.</td><td>The temperature of vent fluid is not the body temperature of a tubeworm living nearby.</td></tr>
<tr><td>Mixing-zone habitat</td><td>Cold seawater mixes with sulfide-rich warm water, creating much cooler microhabitats.</td><td>Local conditions fluctuate. A single habitat temperature is not a universal safe range.</td></tr>
<tr><td>{link("riftia","2025 PLOS ONE synthesis of thermal tolerance")}</td><td>It cites prior experiments in which all exposed <em>Riftia pachyptila</em> died after two hours at around 32–35°C.</td><td>This is a laboratory exposure result, not an exact upper survival limit for every natural circumstance.</td></tr>
</tbody></table><p><strong>Reader takeaway:</strong> their astonishing adaptation involves position, symbiotic chemosynthesis and sulfide transport; it does not mean living in 300°C water.</p></section>'''
},
201:{
 "changes":[
 ("또한 강력한 뒷다리 근육을 이용해 지면이나 나뭇가지에서 튀어 오르는 점프 이륙 메커니즘을 갖추고 있었습니다",
  "뒷다리 근육을 활용한 점프 이륙 방식은 일부 연구에서 제안한 가능성이지만, 실제 이륙 행동을 화석으로 직접 관찰한 것은 아닙니다"),
 ("시조새가 단순한 활강에 그치지 않고 날개를 펄럭여 짧은 거리를 강력하게 이동하는",
  "시조새가 단순한 활강만 한 것이 아니라 능동적으로 날갯짓할 능력을 지녔을 가능성을 지지했지만, 정확한 비행 거리까지 입증한 것은 아닙니다. 이런 근거로 연구자들은"),
 ("CT 스캔 연구로 밝혀진 '능동적인 구동력 비행 능력'",
  "날개뼈 CT 분석이 뒷받침하는 '능동적 날갯짓 비행 가능성'"),
 ],
 "note":f'''<section class="{MARKER}"><h2>화석 증거 비교: 시조새는 정말 비행했을까요?</h2><table><thead><tr><th>연구</th><th>화석에서 측정한 것</th><th>결론의 범위</th></tr></thead><tbody>
<tr><td>{link("flight2018","Voeten 외, Nature Communications (2018)")}</td><td>세 표본의 날개뼈 단면을 싱크로트론 CT로 분석하고 현대 조류·비행하지 않는 공룡과 비교했습니다.</td><td>능동적으로 날개를 움직여 짧은 거리 비행을 했을 가능성을 지지하지만, 실제 비행 시간과 특정 이륙 방식까지 관찰한 것은 아닙니다.</td></tr>
<tr><td>{link("flight2025","O'Connor 외, Nature (2025)")}</td><td>새롭게 연구된 시카고 표본에서 세 번째 날개깃(tertial)의 특수한 배열과 발바닥 구조를 상세히 확인했습니다.</td><td>날개의 공기역학적 구조에 대한 단서를 강화하지만 현대 조류와 같은 비행법을 입증하지는 않습니다.</td></tr>
</tbody></table><p><strong>편집 판단:</strong> 깃털·날개뼈의 비행 적응은 확인되지만, 진화의 중간 단계를 현대 새의 실제 비행 행동처럼 단정하지 않는 것이 정확합니다.</p></section>'''
},
386:{
 "changes":[
  ("it was equipped for short <strong>burst-powered flapping flight</strong>",
   "wing anatomy supports the interpretation of active flapping flight, although exact takeoff behavior and flight distance remain inferred"),
  ("<em>Archaeopteryx</em> proves that the physical mechanics of powered flapping flight evolved earlier in deep time than the rapid growth rates that define modern birds",
   "<em>Archaeopteryx</em> suggests that wing features supporting active flapping emerged before the rapid growth characteristics typical of many modern birds"),
 ],
 "note":f'''<section class="{MARKER}"><h2>What fossils can and cannot tell us about Archaeopteryx flight</h2><table><thead><tr><th>Study</th><th>Direct fossil evidence</th><th>Reasonable interpretation</th></tr></thead><tbody>
<tr><td>{link("flight2018","Voeten et al., Nature Communications (2018)")}</td><td>Synchrotron scans of wing-bone cross sections from three specimens compared with living birds and other archosaurs.</td><td>Supports active wing flapping, likely for relatively short flights; it does not directly observe flight duration or takeoff maneuvers.</td></tr>
<tr><td>{link("flight2025","O'Connor et al., Nature (2025)")}</td><td>The newly studied Chicago specimen preserves specialized tertial feathers and foot-pad features that refine reconstructions.</td><td>Indicates a more complete aerodynamic wing surface, without proving the animal flew exactly like modern birds.</td></tr>
</tbody></table><p><strong>Evidence rule:</strong> distinguish observable bone and feather structure from the behavior reconstructed by scientific models. Active flight is well supported but not filmed or directly measured.</p></section>'''
}
}
# Update a low-quality citation only where new original study directly addresses
# the originally cited topic. Existing numeric reference anchors are preserved.
UPGRADE={27:(3,"genome"),854:(3,"genome"),32:(8,"coel"),839:(8,"coel")}
def request(method,route,**kwargs):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+route,timeout=80,**kwargs)
 if r.status_code>=400:raise RuntimeError(f"{method} {route}: HTTP {r.status_code}: {r.text[:180]}")
 return r.json()
def update_ref(html,pid,num,key):
 pat=rf'(<li\s+id="ref-{num}"[^>]*>\s*<a\b[^>]*href=")([^"]+)("[^>]*>)([^<]+)(</a>\s*—\s*)([^,<]+)'
 m=re.search(pat,html,re.I|re.S)
 if not m:raise ValueError(f"Reference {pid} ref-{num} missing")
 u=SOURCES[key];domain=urlsplit(u).hostname.removeprefix("www.")
 def repl(q):
  return q.group(1)+u+q.group(3)+domain+q.group(5)+domain
 return re.sub(pat,repl,html,count=1,flags=re.I|re.S)
def main():
 changes={}
 for pid,spec in CONTENT.items():
  p=request("GET",f"posts/{pid}",params={"context":"edit"})
  if p.get("status")!="publish":raise RuntimeError(f"{pid} not published")
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  if MARKER in raw:
   print("PRIORITY8_ALREADY_PRESENT",pid,flush=True);continue
  new=raw
  for old,replacement in spec["changes"]:
   if new.count(old)!=1:raise RuntimeError(f"{pid}: expected exact phrase once, found {new.count(old)}: {old[:75]}")
   new=new.replace(old,replacement,1)
  if pid in UPGRADE:
   num,key=UPGRADE[pid]
   new=update_ref(new,pid,num,key)
  mt=re.search(r"<h2\b",new,re.I)
  if not mt:raise RuntimeError(f"{pid}: no H2 insertion point")
  new=new[:mt.start()]+spec["note"]+new[mt.start():]
  if len(new)<len(raw)*0.95:raise RuntimeError(f"{pid}: unexpected source HTML loss")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"id":pid,"title":p.get("title"),"excerpt":p.get("excerpt"),
     "status":p.get("status"),"modified":p.get("modified"),"content":raw},ensure_ascii=False,indent=2),encoding="utf8")
  changes[pid]=(p,raw,new)
 print("PRIORITY8_PREFLIGHT",len(changes),"all original backups created",flush=True)
 rows=[]
 for pid,(p,raw,new) in changes.items():
  if APPLY:
   request("POST",f"posts/{pid}",json={"content":new})
   check=request("GET",f"posts/{pid}",params={"context":"edit"})
   actual=check["content"].get("raw") or ""
   if check.get("status")!="publish" or actual.count(MARKER)!=1:
    raise RuntimeError(f"{pid}: post-update verification failed")
   if len(re.findall(r"<img\b",raw,re.I))!=len(re.findall(r"<img\b",actual,re.I)):
    raise RuntimeError(f"{pid}: image count changed unexpectedly")
   if set(re.findall(r'id="ref-(\d+)"',raw))!=set(re.findall(r'id="ref-(\d+)"',actual)):
    raise RuntimeError(f"{pid}: original reference numbers changed")
  row={"id":pid,"status":"UPDATED" if APPLY else "PREVIEW","before_html_chars":len(raw),
       "after_html_chars":len(new),"new_source_note_chars":len(CONTENT[pid]["note"])}
  rows.append(row);print("PRIORITY8_ITEM="+json.dumps(row,ensure_ascii=False),flush=True)
 (OUT/"report.json").write_text(json.dumps({"apply":APPLY,"total":8,"checked":len(changes),
   "result":rows,"date_utc":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("PRIORITY8_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(r["status"]=="UPDATED" for r in rows),"passed":len(rows)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
