"""Exact-phrase science editorial corrections, eight active WordPress posts.

Topics: Otodus megalodon, Antarctic icefish, vampire squid, mimic octopus.
Research-linked comparative sections are ORIGINAL editorial synthesis.
All 8 originals backed up before any WP changes. Dry run by default.
Preserves post slug/status/excerpt/images/citations and references.
"""
import os,re,json
from pathlib import Path
from datetime import datetime,timezone
import requests

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("BATCH5_APPLY","false").lower()=="true"
OUT=Path("audit_output/science_batch5");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
MARK="taxonguru-research-comparison-batch5"
SRC={
 "mega25":"https://pmc.ncbi.nlm.nih.gov/articles/PMC7617484/",
 "mega26":"https://palaeo-electronica.org/content/2026/5872-otodus-megalodon-vertebrae-from-denmark",
 "bite":"https://doi.org/10.1111/j.1469-7998.2008.00494.x",
 "ice25":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12527291/",
 "ice24":"https://pmc.ncbi.nlm.nih.gov/articles/PMC11575085/",
 "icecomp":"https://pubmed.ncbi.nlm.nih.gov/40920645/",
 "vamp":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3479720/",
 "vampnews":"https://royalsociety.org/news/2012/vampire-squid-eating-habits/",
 "mimic":"https://pmc.ncbi.nlm.nih.gov/articles/PMC1088805/",
 "mimictax":"https://www.mapress.com/mrs/article/view/mr.25.2.1",
 "mimicg":"https://www.guinnessworldrecords.com/world-records/398858-greatest-octopus-mimic",
}
def link(k,label):return '<a href="'+SRC[k]+'" target="_blank" rel="noopener noreferrer">'+label+'</a>'
DATA={
164:{"edits":[
 ("추정한 성체 메갈로돈의 몸길이는 약 15m에서 20m에 달합니다",
 "과거 모델에서는 성체 메갈로돈의 몸길이를 주로 약 15~20m로 추정했지만, 2025년 척추·체형 비교 모델에서는 최대 약 24.3m 가능성까지 제시했습니다. 이는 발견된 완전한 개체의 실측이 아닙니다"),
 ],
 "note":f'''<section class="{MARK}"><h2>2025~2026년 화석 연구: 메갈로돈은 실제로 24m였을까요?</h2>
<table><thead><tr><th>분석 방법</th><th>연구 결과</th><th>주의할 점</th></tr></thead><tbody>
<tr><td>{link("mega25","2025년 체형 복원 논문")}</td><td>척추 화석과 165종의 상어 체형비를 비교하여 최대 약 <strong>24.3m</strong>와 약 94t의 가상 대형 개체를 제안했습니다.</td><td>완전한 24.3m 골격이 발견된 것이 아니며, 표본의 머리·꼬리 길이를 모델로 복원한 추정치입니다.</td></tr>
<tr><td>{link("mega26","2026년 덴마크 척추 화석 재발견 연구")}</td><td>기존 사진에만 남았던 척추 표본을 재확인하고 약 23cm 지름을 검증했습니다.</td><td>척추 지름의 실측이 곧 몸 전체 길이의 직접 측정은 아닙니다.</td></tr>
<tr><td>{link("bite","2008년 백상아리 유한요소 모델")}</td><td>메갈로돈의 최대 턱힘 약 108,514~182,201N은 살아있는 개체의 측정이 아니라 체중과 턱 구조를 가정한 모델 추정입니다.</td><td>새로운 체형 복원은 체중 가정 자체를 바꿀 수 있어 모든 치악력 모델이 완전히 확정됐다고 말할 수 없습니다.</td></tr>
</tbody></table><p>독자는 <strong>화석에서 실제로 잰 값</strong>과 <strong>사라진 연조직을 복원한 값</strong>을 구분해야 합니다.</p></section>'''},
709:{"edits":[
 ("While tooth size and bite force are firmly established by fossil data",
  "While fossil tooth dimensions can be measured directly, bite forces are estimates from biomechanical models"),
 ],
 "note":f'''<section class="{MARK}"><h2>2025–2026 reassessment: is a 24.3-m megalodon established fact?</h2>
<table><thead><tr><th>Source</th><th>Evidence</th><th>Uncertainty</th></tr></thead><tbody>
<tr><td>{link("mega25","2025 comparative shark study")}</td><td>Compared fossil vertebrae with proportions of 165 living and extinct sharks to propose a slenderer animal possibly up to <strong>24.3 m</strong> and about 94 tonnes.</td><td>The full length was reconstructed from comparative anatomy, not directly measured on a complete fossil skeleton.</td></tr>
<tr><td>{link("mega26","2026 rediscovered Danish vertebrae")}</td><td>Researchers re-examined associated vertebrae and confirmed a reported maximum vertebral diameter of about 23 cm.</td><td>Vertebral size is a real fossil observation; full-body length depends on the model used.</td></tr>
<tr><td>{link("bite","2008 finite-element bite model")}</td><td>The commonly repeated 108,514–182,201 N bite-force estimate came from simulated jaw mechanics and body-size assumptions.</td><td>It was never an instrumented bite test on a living megalodon. A change in assumed mass or body shape can change estimates.</td></tr>
</tbody></table><p>The scientifically useful distinction is fossil measurement versus modeled size versus modeled jaw mechanics.</p></section>'''},
170:{"edits":[
 ("지구상에 존재하는 척추동물 중 유일하게 적혈구와 헤모글로빈이 전혀 없는 매우 특별한 혈액 구조",
 "큰지느러미빙어과(Channichthyidae) 계통이 공통으로 보여주는 헤모글로빈 결핍과 성숙 적혈구 부재라는 특별한 혈액 구조"),
 ],
 "note":f'''<section class="{MARK}"><h2>유전자 손실을 바로 이해하기: 혈액이 없는 것이 아니라 헤모글로빈이 없습니다</h2>
<table><thead><tr><th>논문</th><th>확인된 사실</th><th>구분해야 할 해석</th></tr></thead><tbody>
<tr><td>{link("ice25","2025년 두 헤모글로빈 유전자 군집 비교 연구")}</td><td>여러 남극어류의 염색체 영역을 대조해 헤모글로빈 유전자 두 군집의 상실 흔적과 전이인자 관여 가능성을 확인했습니다.</td><td>이 현상을 이 종 한 마리에게만 발생한 변이로 보거나, 낮은 수온 덕분에 불이익이 전혀 없다고 단정하지 않습니다.</td></tr>
<tr><td>{link("ice24","2024년 한국극지연구소 참여 유전체 비교")}</td><td>빙어류에서 FAAP20 및 SOAT1 유전자 부위의 차이를 조사하고 낮은 적혈구 용적률과 연관된 분자적 실마리를 제시했습니다.</td><td>사람의 빈혈 원인과 동일한 메커니즘이라는 결론도, 특정 유전자 하나가 모든 생리적 적응을 설명한다는 결론도 아닙니다.</td></tr>
<tr><td>{link("icecomp","2025년 물고기 계통 간 비교연구")}</td><td>남극 빙어류와 아시아 국수물고기류의 산소운반 단백질 유전자 퇴화가 독립적으로 일어났음을 분석했습니다.</td><td>다른 계통의 유사한 모습은 정확히 같은 유전자 손실 경로를 뜻하지 않습니다.</td></tr>
</tbody></table><p>극저온의 용존산소와 큰 심장·많은 혈액량은 상실된 혈색소의 기능을 <strong>부분적으로 보완</strong>하지만, 산소 수송 능력의 제약을 완전히 없애지는 않습니다.</p></section>'''},
691:{"edits":[
 ("a genetic mutation disrupted hemoglobin synthesis",
  "genetic changes eliminated the hemoglobin gene clusters"),
 ],
 "note":f'''<section class="{MARK}"><h2>Three genetic studies: what does white blood really reveal?</h2>
<table><thead><tr><th>Evidence</th><th>What was found</th><th>What remains uncertain</th></tr></thead><tbody>
<tr><td>{link("ice25","2025 hemoglobin-cluster study")}</td><td>Compared two hemoglobin gene clusters in red-blooded relatives with corresponding regions of icefish genomes; transposable-element-associated changes help explain the losses.</td><td>The mechanism is a reconstructed evolutionary scenario, not a directly observed single mutation in today's fish.</td></tr>
<tr><td>{link("ice24","2024 genome comparison")}</td><td>Examined FAAP20 and SOAT1 loss patterns that may relate to their unusual low-hematocrit physiology.</td><td>Gene association alone does not demonstrate a full one-gene explanation for enlarged hearts and oxygen delivery.</td></tr>
<tr><td>{link("icecomp","2025 fish-lineage comparison")}</td><td>Independent hemoprotein gene deterioration in Antarctic icefish and Asian noodlefishes provides a case of different routes to analogous phenotypes.</td><td>Neither group is a proof that hemoglobin is dispensable in all waters or all vertebrates.</td></tr>
</tbody></table><p>White blood is shared across the icefish family, not a property unique to one named species. Plasma transports dissolved oxygen, but reduced capacity still requires cardiovascular compensations.</p></section>'''},
180:{"edits":[
 ("흡반과 유두상 돌기를 통해 경질화 과정을 거친 뒤",
  "흡반과 유두상 돌기, 점액을 이용해 작은 덩어리로 모은 뒤"),
 ],
 "note":f'''<section class="{MARK}"><h2>심해 영상과 수조 실험은 뱀파이어오징어의 먹이를 어떻게 확인했을까요?</h2>
<table><thead><tr><th>관찰 방법</th><th>실제 확인 내용</th><th>추정의 한계</th></tr></thead><tbody>
<tr><td>{link("vamp","Hoving·Robison, Proceedings B (2012)")}</td><td>MBARI 원격무인잠수정 영상·위 내용물 분석에서 유기물 쇄설입자, 버려진 유생피낭집, 갑각류 잔해, 규조류 및 배설물 펠릿을 확인했습니다.</td><td>주된 식단이 부유 유기물이라는 사실은 확인되지만 모든 먹이가 반드시 죽은 동물 한 종류라는 뜻은 아닙니다.</td></tr>
<tr><td>{link("vampnews","영국 왕립학회 연구 소개")}</td><td>사육 수조에서 필라멘트에 부착된 입자를 팔 사이로 모으고 점액 덩어리로 만든 뒤 섭취하는 행동을 관찰했습니다.</td><td>실 모양 기관이 ‘먹이를 굳게 경질화한다’고 설명하기보다 포획·응집·이동이라는 동작을 구분하는 것이 정확합니다.</td></tr>
</tbody></table><p><strong>독창적 해석:</strong> 낮은 산소·낮은 먹이 밀도라는 생태환경에서 필라멘트 수집과 낮은 대사율은 연결되는 적응이지만, 모든 지역에서 먹이 조성 비율이 동일하다고 말할 수는 없습니다.</p></section>'''},
661:{"edits":[
 ("it does not hunt live prey or pierce the flesh of other ocean dwellers",
  "its best-documented feeding strategy is collecting detritus rather than active pursuit of live prey; observations do not justify absolute claims about every possible feeding event"),
 ],
 "note":f'''<section class="{MARK}"><h2>Research compared: deep-sea video, gut contents and live feeding experiments</h2>
<table><thead><tr><th>Method</th><th>What was directly observed</th><th>What should not be generalized</th></tr></thead><tbody>
<tr><td>{link("vamp","2012 Proceedings of the Royal Society B study")}</td><td>ROV video, gut contents and aquarium trials identified detrital materials including zooplankton remains, larvacean houses, crustacean fragments, diatoms and faecal pellets.</td><td>“Marine snow” is a diverse mixture, not a uniform dead-prey item. It is not a measured universal diet percentage.</td></tr>
<tr><td>{link("vampnews","Royal Society account of the experiment")}</td><td>Filaments trapped drifting material, which was drawn toward the arms and gathered with mucus before ingestion.</td><td>The filaments' food-collecting role was demonstrated. Any additional sensory function requires separate testing.</td></tr>
</tbody></table><p>Evidence of a primarily detritivorous diet is stronger than an absolute statement that the animal could never interact with live material.</p></section>'''},
35:{"edits":[
 ("15가지 이상의 동물로 변신한다는 주장은 관찰자의 주관적인 해석이나 단순 일화에 가까우며, 아직 과학적인 증거가 부족한 미확증 상태입니다",
  "여러 동물에 대한 모방 주장은 관찰 및 자료마다 분류 기준이 다릅니다. 2001년 학술논문은 9개 개체의 모방 자세를 촬영했고, 기네스 자료는 최대 16가지 형태의 모방 목록을 소개합니다. 따라서 정확히 3종 또는 15종만 모방한다고 단정하기보다 각 행동의 영상·관찰 근거를 구분해야 합니다"),
 ],
 "note":f'''<section class="{MARK}"><h2>모방 대상은 3종, 15종, 16종? 논문과 기록의 차이를 직접 비교</h2>
<table><thead><tr><th>출처</th><th>기록한 내용</th><th>정확한 해석</th></tr></thead><tbody>
<tr><td>{link("mimic","2001년 Proceedings B 원논문")}</td><td>인도네시아 술라웨시·발리 현장에서 <strong>9개체</strong>의 자세와 체색 변화를 촬영하고 여러 위험 동물과 닮은 행동을 설명했습니다.</td><td>9는 관찰된 문어 개체 수이지 모방 종 수가 아닙니다. 모든 포식자가 실제로 속았다는 실험 결과도 아닙니다.</td></tr>
<tr><td>{link("mimictax","2005년 공식 종 기술 논문")}</td><td>흉내문어를 <em>Thaumoctopus mimicus</em>로 정식 기술하고 분포·형태적 특징을 정리했습니다.</td><td>종을 정식으로 기술한 논문이 모든 모방 대상과 성공률을 따로 입증했다는 의미는 아닙니다.</td></tr>
<tr><td>{link("mimicg","기네스 세계기록의 16종 목록")}</td><td>가자미·바다뱀·쏠배감펭 등을 포함해 <strong>16가지 모방 형태</strong>를 소개합니다.</td><td>기네스가 소개한 목록과 논문에서 독립 검증된 각각의 행동을 동일 수준의 증거라고 취급해서는 안 됩니다.</td></tr>
</tbody></table><p>따라서 횟수나 종류만 세기보다 <strong>누가, 어떤 환경에서, 어떤 행동을 관찰했는지</strong>와 다른 생물의 반응을 함께 살펴보는 것이 중요합니다.</p></section>'''},
829:{"edits":[
 ("effortlessly transforms into fifteen distinct marine species",
  "has a fixed repertoire of precisely fifteen proven model species"),
 ],
 "note":f'''<section class="{MARK}"><h2>Three, fifteen or sixteen disguises? Distinguishing papers from record lists</h2>
<table><thead><tr><th>Source</th><th>What it actually documented</th><th>What cannot be inferred</th></tr></thead><tbody>
<tr><td>{link("mimic","Norman, Finn & Tregenza (2001)")}</td><td>Researchers filmed <strong>nine individual octopuses</strong> in Indonesia and observed several posture and pattern changes resembling dangerous animals.</td><td>Nine is the number of study individuals, not a count of confirmed model species or a proven success rate with predators.</td></tr>
<tr><td>{link("mimictax","Formal species description (2005)")}</td><td>Described the morphology, distribution and taxonomy of <em>Thaumoctopus mimicus</em>.</td><td>Taxonomic description does not validate every animal name proposed in popular mimicry lists.</td></tr>
<tr><td>{link("mimicg","Guinness World Records list")}</td><td>Lists <strong>16 different imitated animals</strong> including flatfish, sea snakes and lionfish.</td><td>A compiled list and controlled evidence of successful predator deception are different kinds of claim.</td></tr>
</tbody></table><p>For readers, the useful question is not “how many exact disguises?” but which behaviors were filmed, how models were identified, and whether a predator's response was measured.</p></section>'''}
}
def api(method,path,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=85,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {path}: {r.status_code}: {r.text[:140]}")
 return r.json()
def main():
 batch={}
 for pid,sp in DATA.items():
  p=api("GET",f"posts/{pid}",params={"context":"edit"})
  if p["status"]!="publish":raise RuntimeError(f"{pid}: post not published")
  old=p["content"].get("raw") or p["content"].get("rendered") or ""
  if MARK in old:
   print("B5_ALREADY_EXISTS",pid,flush=True);continue
  new=old
  for before,after in sp["edits"]:
   count=new.count(before)
   if count!=1:raise RuntimeError(f"{pid}: exact phrase count {count} for {before[:70]}")
   new=new.replace(before,after,1)
  h=re.search(r"<h2\b",new,re.I)
  if not h:raise RuntimeError(f"{pid}: no H2 insertion point")
  new=new[:h.start()]+sp["note"]+new[h.start():]
  if len(new)<len(old)*.9:raise RuntimeError(f"{pid}: unexpected shrinkage")
  before_refs=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',old))
  if not before_refs or before_refs!=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',new)):
   raise RuntimeError(f"{pid}: reference IDs changed")
  imgnum=len(re.findall(r"<img\b",old,re.I))
  if imgnum!=len(re.findall(r"<img\b",new,re.I)):raise RuntimeError(f"{pid}: images changed")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False),encoding="utf8")
  batch[pid]={"before":old,"after":new,"refs":before_refs,"images":imgnum,"link":p.get("link")}
 print("B5_PREFLIGHT_OK",len(batch),"all original snapshots saved",flush=True)
 results=[]
 for pid,x in batch.items():
  if APPLY:
   api("POST",f"posts/{pid}",json={"content":x["after"]})
   post=api("GET",f"posts/{pid}",params={"context":"edit"})
   content=post["content"].get("raw") or ""
   if post["status"]!="publish" or content.count(MARK)!=1:
    raise RuntimeError(f"{pid}: post-update status/content failed")
   if set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',content))!=x["refs"]:
    raise RuntimeError(f"{pid}: ref anchors changed")
   if len(re.findall(r"<img\b",content,re.I))!=x["images"]:
    raise RuntimeError(f"{pid}: image count changed")
  res={"id":pid,"action":"UPDATED" if APPLY else "DRY_RUN","new_chars":len(x["after"])-len(x["before"]),"url":x["link"]}
  results.append(res);print("B5_ITEM="+json.dumps(res,ensure_ascii=False),flush=True)
 (OUT/"report.json").write_text(json.dumps({"apply":APPLY,"results":results,
    "timestamp_utc":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("B5_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(r["action"]=="UPDATED" for r in results),"preview":sum(r["action"]=="DRY_RUN" for r in results)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
