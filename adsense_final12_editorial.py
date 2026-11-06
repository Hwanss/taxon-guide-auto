"""Final 12 TaxonGuru science posts: exact-phrase corrections with evidence.

Prior fixes are retained. Every post must preflight successfully and be backed
up before any write. Publication status, excerpts, media and numbered references
must not change. This is editorial analysis, not an independent expert signoff.
"""
import os,re,json
from pathlib import Path
from datetime import datetime,timezone
import requests

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("FINAL12_APPLY","false").lower()=="true"
OUT=Path("audit_output/final12_evidence");OUT.mkdir(parents=True,exist_ok=True)
MARK="taxonguru-final12-editorial-2026"
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
SOURCES={
"quetz":"https://doi.org/10.1080/02724634.2020.1780247",
"quetz_news":"https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/",
"lily":"https://www.kew.org/kew-gardens/whats-in-the-gardens/waterlily-house",
"lily_spec":"https://www.kew.org/plants/giant-waterlily",
"lily_102":"https://www.kew.org/about-us/press-media/waterlily-weigh-off-2026",
"sequoia_nps":"https://www.nps.gov/seki/learn/nature/largest-trees-in-world.htm",
"sequoia_usfs":"https://research.fs.usda.gov/feis/species-reviews/seqgig",
"sequoia_guinness":"https://www.guinnessworldrecords.com/world-records/largest-living-tree",
"fungus":"https://research.fs.usda.gov/treesearch/20135",
"fungus_gt":"https://www.guinnessworldrecords.com/world-records/66481-largest-fungi",
"puya":"https://www.frontiersin.org/journals/conservation-science/articles/10.3389/fcosc.2024.1349553/full",
"ghost":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12961686/",
"ghost_uses":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12900251/",
}
def a(key,label):
 return '<a href="'+SOURCES[key]+'" target="_blank" rel="noopener noreferrer">'+label+'</a>'
DATA={
123:{
"edits":[
 ("바이오매커니믹스(생체역학) 연구 결과에 따르면, 케찰코아틀루스는 두 다리로만 달려서 날아오른 것이 아니었습니다",
  "생체역학 연구에서는 사족도약과 이족도약을 비롯한 서로 다른 이륙 방식을 검토하며, 어느 한 가지가 실제 행동이었다고 확정할 수 없습니다"),
 ("앞다리와 뒷다리, 즉 네 다리로 땅을 강하게 차올라 공중으로 약 2.4미터 높이까지 순간적으로 솟구쳐 오른 후 날개짓을 시작하여 비상했습니다",
  "사족 이륙 모형에서는 앞다리와 뒷다리를 활용하는 강한 도약을 가정하지만, 정확히 2.4m 도약했다는 수치는 직접 관찰이 아니라 복원 시나리오에 의존합니다"),
 ("내부가 비어 있어 무게를 극소화한 함기골이 없었다면 2.4미터 높이까지 솟구치는 도약이 불가능했을 것이며, 네 다리로 땅을 차는 강력한 도약 이륙이 없었다면 그 거대한 날개를 공중에서 젓기 시작할 고도를 확보하지 못했을 것입니다",
  "함기골과 강한 사지의 구조는 비행 가능성을 검토하는 중요한 제약조건입니다. 하지만 2.4m 도약이나 사족 이륙만이 가능한 유일한 방법이라는 주장은 화석으로 확정되지 않았습니다"),
 ],
"note":f'''<section class="{MARK}"><h2>이륙 장면을 본 사람이 없는 익룡의 비행은 어떻게 연구할까요?</h2>
<p>{a("quetz","2021년 케찰코아틀루스 기능형태학 연구")}는 사족도약에 필요한 팔꿈치 관절의 힘과 뼈 강도가 충분했는지 확실하지 않다고 설명하며, 이족도약 역시 가능한 가설로 검토합니다. {a("quetz_news","UC 버클리 연구 소개")}에서도 도약 후 날갯짓이라는 가설을 재구성했지만, 이륙 장면이 관찰된 것은 아닙니다.</p>
<p><strong>비교의 핵심:</strong> 날개뼈·사지 길이와 관절의 운동 범위는 화석 자료입니다. 구체적인 도약 고도와 이륙 방식은 이를 바탕으로 계산한 모델의 해석입니다. 한쪽 모델을 ‘입증된 동작’으로 소개하지 않습니다.</p></section>'''
},
807:{
"edits":[
 ("modern skeletal reconstructions have established a verified wingspan of 10 to 11 meters",
  "modern skeletal reconstructions generally estimate a 10-to-11-meter wingspan from incomplete remains and comparisons with smaller relatives"),
 ("Rather than running on two hind legs like modern birds, ",
  "In one proposed reconstruction, "),
 ("used all four limbs to leap into the air",
  "might use all four limbs to leap, although functional-anatomy research also regards bipedal jumps as plausible"),
 ("it vaulted roughly 2.4 meters (8 feet) into the air before beginning its very first wingbeat",
  "modeled launch sequences explore the clearance needed for an effective first wingbeat, but a 2.4-meter leap was not directly measured from a fossil"),
 ],
"note":f'''<section class="{MARK}"><h2>What wing fossils show versus what takeoff models assume</h2>
<p>The {a("quetz","2021 functional-morphology study")} discusses quadrupedal and bipedal takeoff scenarios, noting uncertain forelimb strength in proposed launch mechanics. {a("quetz_news","UC Berkeley's research account")} explains a jumping first stroke, but this is reconstructed behavior, not a video or a measurable prehistoric leap.</p>
<p><strong>Useful distinction:</strong> fossil geometry and joint movement are anatomical evidence; the launch trajectory, precise vertical leap and flight style depend on biomechanical assumptions. Published estimates need not be settled on one mechanism.</p></section>'''
},
141:{
"edits":[
 ("사람이 잎 위에 안전하게 올라앉거나 서기 위해서는",
  "식물원에서 잎의 하중을 통제된 조건으로 시연할 때에는"),
 ],
"note":f'''<section class="{MARK}"><h2>수련 잎의 하중 지지 기록을 실제 안전 기준으로 오해하면 안 됩니다</h2>
<p>{a("lily_spec","큐 왕립식물원은 아마존빅토리아수련")}의 성숙 잎이 하중을 분산했을 때 어린아이의 무게를 지탱할 수 있다고 설명합니다. {a("lily_102","2026년 102kg 시연")}은 다른 종인 <em>Victoria boliviana</em>의 잎으로 진행했으며 시연 조건이 달랐습니다.</p>
<p>{a("lily","큐 왕립식물원의 방문자 안내")}는 성인의 체중을 지탱할 수 있는 잎도 있지만 실제로 올라서려 시도하지 말라고 명시합니다. <strong>하중 시연은 일반 방문자에게 안전한 발판이라는 뜻이 아닙니다.</strong></p></section>'''
},
775:{
"edits":[
 ("the leaf's natural engineering can easily hold an adult floating above the stream",
  "the leaf may support a carefully distributed demonstration load under controlled garden conditions, but is not a safe surface for visitors to stand on"),
 ],
"note":f'''<section class="{MARK}"><h2>Structural demonstration versus public safety</h2>
<p>{a("lily_spec","Kew's Victoria amazonica profile")} describes a leaf that can support a child with suitable weight distribution. The famous {a("lily_102","2026 102 kg demonstration")} used a <em>Victoria boliviana</em> leaf and specialized preparations, not an uncovered human foot.</p>
<p>Kew's {a("lily","Waterlily House visitor guidance")} explicitly warns people not to try standing on leaves. A demonstrated weight under load-spreading conditions cannot be treated as a certified safe capacity or transferred between species.</p></section>'''
},
178:{
"edits":[
 ("더욱 특이한 점은 번식을 진행할 때 산불의 열기나 특정 동물 매개체에 절대적으로 의존한다는 사실입니다",
  "거대 세쿼이아는 산불이 종자 방출과 어린 묘목의 정착을 크게 돕지만, 솔방울에서 씨앗을 방출하는 경로는 산불 외에도 더글러스다람쥐와 딱정벌레 등에 의해 나타납니다"),
 ],
"note":f'''<section class="{MARK}"><h2>제너럴 셔먼의 부피 기록과 산불의 역할, 측정 항목을 구분해 보기</h2>
<p>{a("sequoia_nps","미국 국립공원관리청")}이 발표하는 제너럴 셔먼의 약 1,487m³는 주로 <strong>줄기 부피</strong> 기준입니다. {a("sequoia_guinness","기네스의 2013년 1,591m³")}는 나무의 목재와 수피를 포함하는 다른 계산 범위이므로 같은 수치가 틀렸다는 뜻은 아닙니다.</p>
<p>{a("sequoia_usfs","미국 산림청의 자이언트 세쿼이아 생태 연구")}는 뜨거운 공기에 의한 솔방울 건조·개방 외에도 더글러스다람쥐와 딱정벌레가 종자를 방출할 수 있다고 설명합니다. 다만 대량 실생 정착에는 불이 만들어낸 수관 틈·맨땅이 중요합니다. 씨앗이 ‘나오는 것’과 어린나무가 ‘살아남는 것’은 다른 단계입니다.</p></section>'''
},
667:{
"edits":[
 ("the species relies directly on heat to complete its life cycle",
  "fire helps release seeds en masse and creates conditions for seedlings to establish, although squirrels, beetles and cone drying can also disperse seeds"),
 ],
"note":f'''<section class="{MARK}"><h2>Giant sequoia record methodology and how seeds actually escape cones</h2>
<p>The {a("sequoia_nps","US National Park Service")} lists General Sherman at about 1,487 m³ by primary trunk volume. {a("sequoia_guinness","Guinness' 2013 figure")} of 1,591 m³ refers to a differently defined wood-and-bark calculation. These cannot be compared as if they measured precisely the same part of the tree.</p>
<p>The {a("sequoia_usfs","US Forest Service species review")} identifies fire, Douglas squirrels and cone-boring insects as seed-release routes. Fire is especially effective because it releases many seeds into well-lit, exposed mineral soils, but individual seeds can be liberated without a fire. Seed dispersal and successful regeneration are distinct outcomes.</p></section>'''
},
221:{
"edits":[
 ("단 하나의 유전자 클론으로 연결된 단일 개체(Genet)가 9.65km²의 토양을 가득 메우고 있다는",
  "유전적으로 동일한 균류 표본들이 약 9.65km² 범위에서 발견됐다는"),
 ],
"note":f'''<section class="{MARK}"><h2>2003년 원논문은 9.65km²의 균류를 어떻게 확인했을까요?</h2>
<p>{a("fungus","Ferguson 외(2003), Canadian Journal of Forest Research")}는 오리건 숲에서 112개 균류 분리주를 조사했고, 종·체세포 불화합성 검사를 통해 여러 유전 개체(genet)를 구별했습니다. 그중 가장 넓은 개체의 추정 분포 범위는 <strong>965헥타르(9.65km²)</strong>, 가장 먼 표본 간 거리는 약 3,810m였습니다.</p>
<p>{a("fungus_gt","기네스의 가장 큰 균류 기록")}도 이를 인용합니다. 그러나 이 면적은 균사체로 토양 전체가 빈틈없이 채워졌다는 측정이 아닙니다. 유전학적 표본과 지도상의 개체 경계로 <strong>추정한 분포 영역</strong>입니다. 연령과 무게 역시 생장 속도 및 생물량 모델에 따른 추정치입니다.</p></section>'''
},
434:{
"edits":[
 ("allow a single genetic individual to spread across miles without breaking connection",
  "allow genetically matching fungal individuals to be identified across sampled forest sites; the mapped area does not mean every cubic metre of soil is filled with hyphae"),
 ],
"note":f'''<section class="{MARK}"><h2>How researchers actually mapped the 9.65 km² Armillaria individual</h2>
<p>{a("fungus","Ferguson et al. (2003)")} identified 112 fungal isolates and discriminated multiple genetic individuals using diagnostic and compatibility tests. Their largest mapped genet occupied about 965 hectares, with the farthest positive samples about 3,810 m apart.</p>
<p>The {a("fungus_gt","Guinness record")} describes the largest known fungus by area, not an excavation proving the entire 9.65 km² contains solid fungal tissue. The mapped boundary comes from tested sampling points, while total mass and lifespan are estimated from other assumptions. <strong>Measured genetic identity, inferred occupied area and modeled biomass are different facts.</strong></p></section>'''
},
227:{
"edits":[
 ("그러나 학계의 연구 결과, 푸야 라이몬디는 동물을 소화하는 효소나 능동적인 포획 기작을 전혀 가지고 있지 않습니다",
  "하지만 2024년 생태학 검토에서는 새가 가시에 걸려 죽는 현상과 이를 통해 양분을 얻을 수 있다는 가설을 소개하면서도, 해당 영양 흡수 과정에 대한 추가 연구가 필요하다고 밝혔습니다"),
 ("잎의 가시는 식물체를 뜯어먹으려는 초식동물로부터 스스로를 지키기 위한 물리적 방어 장치일 뿐이며, 동물이 걸려 죽는 것은 단순한 우발적 사고로 결론지어졌습니다",
  "갈고리 가시는 초식동물 방어와 새의 둥지 지지에 기여할 수 있지만, 그 구조가 동물 유래 영양분을 얻는 적응이기도 한지는 아직 충분히 검증되지 않았습니다"),
 ],
"note":f'''<section class="{MARK}"><h2>푸야 라이몬디는 육식식물일까요? ‘반증됨’보다 정확한 표현</h2>
<p>{a("puya","2024년 Frontiers in Conservation Science 검토")}는 잎 사이에서 죽은 새가 발견된 사례와 원시 육식성(protocarnivory) 가설을 설명합니다. 이 가설은 실험으로 확정된 결과도, 과학적으로 완전히 반박된 결론도 아닙니다. 실제로 동물의 영양분이 식물에 흡수돼 생장 이익을 주는지를 확인하는 연구가 더 필요하다고 명시합니다.</p>
<p>따라서 '동물이 걸린다'는 관찰, '가시가 초식동물을 막는다'는 기능, '죽은 동물의 영양을 이용한다'는 가설을 각각 구분해야 합니다.</p></section>'''
},
449:{
"edits":[
 ("Scientific evaluation has thoroughly disproved this notion",
  "A 2024 ecological review instead treats possible nutrient gain from trapped animals as an untested hypothesis needing further study"),
 ("Botanists have confirmed that the hooked leaf spines serve exclusively as a physical defense mechanism",
  "The hooked spines can deter grazing and also support nesting birds, but exclusive defense as their sole function is not established"),
 ("Any nutrients absorbed from animals that accidentally die nearby represent incidental ecological recycling rather than a specialized carnivorous strategy",
  "Whether nutrients from trapped animals enter the plant and yield a biological advantage has not yet been adequately tested"),
 ],
"note":f'''<section class="{MARK}"><h2>Protocarnivory is a hypothesis, not an established or disproven fact</h2>
<p>The {a("puya","2024 Frontiers review")} documents birds entangled in recurved leaf spines and discusses whether their decay could provide nutrients. It explicitly calls for further research into this possible strategy. This is not evidence that the plant actively hunts or digests birds, but neither does it prove that the nutrient-gain hypothesis has been fully falsified.</p>
<p>Distinguish three claims: observed trapped birds, the known protective and nesting roles of spines, and the still-untested benefit of animal-derived nutrients to the plant.</p></section>'''
},
254:{
"edits":[
 ("수정난풀은 자라는 토양의 특성에 따라 중금속을 농축할 가능성이 있으며, 식물 자체의 독성 위험도 배제할 수 없기 때문입니다",
  "2025년 화학 분석에서 50개 표본의 그라야노톡신류가 검출되지 않았지만, 그 연구는 모든 독성 물질이나 중금속을 전수 검사한 결과가 아니며 사람에게 복용 안전성을 입증하지도 않았기 때문입니다"),
 ],
"note":f'''<section class="{MARK}"><h2>50개 표본에서 독소가 검출되지 않았다는 결과의 의미</h2>
<p>{a("ghost","Anez 외(2025), Journal of Natural Products")}는 수정난풀 50개 표본을 대상으로 특정 그라야난형 독소 및 유사체를 정밀 분석해 검출하지 못했습니다. 이는 1889년 보고를 다시 검토한 중요한 자료입니다. 그러나 <strong>모든 유해 성분이 없다는 판정이나 섭취 안전성 검사는 아니었습니다.</strong></p>
<p>{a("ghost_uses","2025년 민속식물학 조사")}는 사람들의 사용 경험을 기록한 것이지 진통 효과·용량·안전성을 검증한 임상시험이 아닙니다. 성분 연구의 미검출과 실제 치료 효능을 하나로 이어서 해석해서는 안 됩니다.</p></section>'''
},
518:{
"edits":[
 ("Because mycoheterotrophic plants bioaccumulate substances directly from soil fungal networks, there are significant toxicity concerns, including the potential uptake and concentration of heavy metals from the soil environment",
  "A 2025 mass-spectrometry study did not detect grayanane-type toxins in 50 ghost-pipe samples; it did not test every possible contaminant or establish the complete safety of ingesting this plant"),
 ],
"note":f'''<section class="{MARK}"><h2>What a 50-sample negative toxin test actually excludes</h2>
<p>{a("ghost","Anez et al., Journal of Natural Products (2025)")} did not detect grayanane-type compounds in 50 <em>Monotropa uniflora</em> samples, re-examining an old disputed toxicity report. The study did not conduct broad human safety testing or a controlled clinical trial.</p>
<p>A separate {a("ghost_uses","2025 ethnobotanical survey")} describes reported use but cannot measure analgesic efficacy. This distinction matters because a negative test for one toxin family is not a general certificate for self-medication, and speculative claims about heavy-metal bioaccumulation should not be stated as proven without direct measurements.</p></section>'''
}
}
def api(method,route,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+route,timeout=85,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {route}: HTTP {r.status_code}: {r.text[:140]}")
 return r.json()

def main():
 planned={}
 for pid,spec in DATA.items():
  p=api("GET",f"posts/{pid}",params={"context":"edit"})
  if p["status"]!="publish":raise RuntimeError(f"{pid}: not published")
  old=p["content"].get("raw") or p["content"].get("rendered") or ""
  if MARK in old:
   print("FINAL12_ALREADY_PRESENT",pid,flush=True);continue
  new=old
  for before,after in spec["edits"]:
   hits=new.count(before)
   if hits!=1:raise RuntimeError(f"{pid}: exact phrase match {hits} for {before[:78]}")
   new=new.replace(before,after,1)
  # H2 introduction preserves the remainder including all existing citations.
  h=re.search(r"<h2\b",new,re.I)
  if not h:raise RuntimeError(f"{pid}: no safe heading insertion point")
  new=new[:h.start()]+spec["note"]+new[h.start():]
  refs=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',old))
  if not refs or refs!=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',new)):
   raise RuntimeError(f"{pid}: prior citation numbers changed")
  imgs=len(re.findall(r"<img\b",old,re.I))
  if imgs!=len(re.findall(r"<img\b",new,re.I)):raise RuntimeError(f"{pid}: media count changed")
  if len(new)<len(old)*.9:raise RuntimeError(f"{pid}: article shrank unexpectedly")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False),encoding="utf8")
  planned[pid]={"old":old,"new":new,"refs":refs,"images":imgs,"link":p.get("link")}
 print("FINAL12_PREFLIGHT",len(planned),"ALL original WP backups made",flush=True)
 results=[]
 for pid,item in planned.items():
  if APPLY:
   api("POST",f"posts/{pid}",json={"content":item["new"]})
   check=api("GET",f"posts/{pid}",params={"context":"edit"})
   new=check["content"].get("raw") or ""
   if check["status"]!="publish" or new.count(MARK)!=1:
    raise RuntimeError(f"{pid}: verified content/status mismatch")
   if set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',new))!=item["refs"]:
    raise RuntimeError(f"{pid}: prior citations lost")
   if len(re.findall(r"<img\b",new,re.I))!=item["images"]:
    raise RuntimeError(f"{pid}: image count changed")
  result={"id":pid,"state":"UPDATED" if APPLY else "DRY_RUN",
          "chars_added":len(item["new"])-len(item["old"]),"url":item["link"]}
  results.append(result)
  print("FINAL12_ITEM="+json.dumps(result,ensure_ascii=False),flush=True)
 (OUT/"report.json").write_text(json.dumps({"apply":APPLY,"results":results,
      "checked_at_utc":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("FINAL12_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(x["state"]=="UPDATED" for x in results),
      "preview":sum(x["state"]=="DRY_RUN" for x in results)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
