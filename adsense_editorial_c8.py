"""Targeted eight-page editorial: titan arum, Tyrannosaurus, bristlecone, Rafflesia.

Dry run by default, strict original phrase matches, backup all eight originals
before WordPress writes, keep posts published, original refs and media intact.
No AdSense signoff or automated publication. November 2026 evidence sources.
"""
from __future__ import annotations
import json,os,re
from pathlib import Path
from datetime import datetime,timezone
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("EDITORIAL_C8_APPLY","false").lower()=="true"
OUT=Path("audit_output/editorial_c8");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
MARKER="taxonguru-c8-evidence-nov2026"
U={
"kew_arum":"https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:84456-1/general-information",
"kew_arum_status":"https://www.kew.org/plants/titan-arum",
"trexwalk":"https://pubmed.ncbi.nlm.nih.gov/33996115/",
"trexrun":"https://pubmed.ncbi.nlm.nih.gov/28740745/",
"trexmass":"https://onlinelibrary.wiley.com/doi/10.1002/ece3.11658",
"nps_old":"https://www.nps.gov/grba/learn/historyculture/the-prometheus-story.htm",
"usfs_old":"https://research.fs.usda.gov/feis/species-reviews/pinlon",
"genome_old":"https://pmc.ncbi.nlm.nih.gov/articles/PMC13233319/",
"guinness_old":"https://www.guinnessworldrecords.com/world-records/oldest-living-individual-tree",
"kew_raf":"https://www.kew.org/plants/rafflesia-arnoldi",
"guinness_raf":"https://www.guinnessworldrecords.com/world-records/66511-largest-single-flower",
}
def a(key,label):
 return '<a href="'+U[key]+'" target="_blank" rel="noopener noreferrer">'+label+'</a>'

DATA={
24:{"replacements":[
 ("식물원이나 온실 등 통제된 재배 환경에서는 송장벌레와 쉬파리류가 시체꽃의 주요 수분 매개 곤충이라는 사실이 명확하게 확인되었습니다",
 "온실에서 관찰된 곤충 방문과 야생에서 꽃가루를 실제로 옮기는 곤충 종을 확정하는 것은 다릅니다. 큐 왕립식물원은 이 종의 수분 과정에 관한 체계적인 정식 연구가 아직 부족하다고 설명합니다"),
 ("시체꽃은 이들 곤충의 몸에 꽃가루를 묻혀 다른 개체로 이동시키는 수분 매개자로 활용할 뿐, 곤충에게 해를 입히지 않습니다",
 "곤충은 냄새를 따라 꽃차례 안으로 들어와 꽃가루를 옮길 수 있습니다. 다만 방문 곤충의 행동과 실제 수분 성공률에 관한 연구가 충분하지 않아, 모든 방문자가 안전하게 나오거나 수분에 기여한다고 단정할 수 없습니다")
 ],
 "note":f'''<section class="{MARKER}"><h2>검증 비교: 거대한 한 송이 꽃일까요, 수백 송이의 꽃차례일까요?</h2>
<table><thead><tr><th>질문</th><th>기관 자료가 확인하는 사실</th><th>판단에 필요한 주의사항</th></tr></thead><tbody>
<tr><td>꽃의 구조</td><td>{a("kew_arum","큐 왕립식물원 식물종 자료")}는 중앙 육수꽃차례(spadix)에 작은 수꽃·암꽃이 모여 있고 이를 포엽(spathe)이 둘러싼다고 설명합니다.</td><td>라플레시아의 단일 꽃 크기 기록과 직접 비교할 수 없습니다.</td></tr>
<tr><td>곤충 수분</td><td>암꽃의 수분 가능 시기와 수꽃의 꽃가루 방출 시기가 달라 곤충 매개 이동이 추정됩니다.</td><td>큐 왕립식물원 자료에는 아직 제대로 된 수분 연구가 없다고 명시되어 있습니다. 특정 파리·딱정벌레가 ‘확정된 주요 야생 수분자’라고 표현하면 과장입니다.</td></tr>
<tr><td>보전 상태</td><td>{a("kew_arum_status","큐 왕립식물원은 IUCN 위기(EN) 등급")}으로 소개합니다.</td><td>온실 재배 기술이 실제 야생 개체 수 증가로 이어졌는지는 별도 실증이 필요합니다.</td></tr>
</tbody></table><p>꽃차례의 크기·냄새·발열은 관찰 가능한 사실이며, 어떤 곤충이 자연상태에서 수분에 성공하는지는 추가 연구 과제입니다.</p></section>'''},
864:{"replacements":[
 ("While carrion beetles and flesh flies are confirmed functional pollinators in cultivation, field researchers acknowledge that additional wild insect interactions require ongoing ecological study",
 "Carrion beetles and flesh flies are plausible visitors attracted by the plant's odor, but Kew's botanical account cautions that proper formal pollination research is still lacking; neither greenhouse visits nor odor attraction alone establish confirmed functional pollinators in the wild"),
 ("In controlled botanical garden settings, entomologists have observed carrion beetles and flesh flies responding enthusiastically to the heat and stench",
 "In botanical accounts, carrion beetles and flesh flies are proposed as likely visitors drawn by heat and odor, but direct pollen transfer and pollination success have not been systematically established for all settings"),
 ],
 "note":f'''<section class="{MARKER}"><h2>What is established about titan arum—and what remains unknown?</h2>
<table><thead><tr><th>Question</th><th>Supported evidence</th><th>Limit</th></tr></thead><tbody>
<tr><td>One flower or inflorescence?</td><td>{a("kew_arum","Royal Botanic Gardens, Kew")} describes a central spadix bearing separate tiny male and female flowers, enclosed by a large spathe.</td><td>Its enormous unbranched inflorescence must not be mistaken for the largest individual flower.</td></tr>
<tr><td>Which insects pollinate in the wild?</td><td>The odor and heat suggest carrion-associated flies and beetles, and male and female stages mature at different times.</td><td>Kew notes the lack of a proper scientific pollination study; insect visits do not automatically prove fertilization.</td></tr>
<tr><td>How threatened is the species?</td><td>{a("kew_arum_status","Kew lists titan arum as Endangered (EN)")} under the IUCN Red List.</td><td>Successful greenhouse propagation is different from a demonstrated recovery of natural populations.</td></tr>
</tbody></table><p>The useful distinction is between a known botanical structure, plausible pollinator attraction and experimentally demonstrated wild pollination.</p></section>'''},
30:{"replacements":[
 ("성체 티라노사우루스 렉스의 실제 최대 이동 속도는 시속 16~40km(10~25mph) 수준으로 제한되었습니다",
 "성체 티라노사우루스의 최고속도는 화석 자체로 실측할 수 없으며, 근육·골격 부하·꼬리의 운동을 어떻게 모델링하는지에 따라 서로 다른 추정치가 나옵니다"),
 ("뛰어난 입체 시각과 후각, 그리고 효율적인 주행 기법을 통해 먹잇감을 추적하고 제압하기에는 충분했습니다",
 "뛰어난 감각과 강한 치악력으로 포식 활동을 했을 가능성이 크지만, 계산된 이동속도만으로 특정 먹잇감을 어떤 속도로 추격했는지 확정할 수는 없습니다")
 ],
 "note":f'''<section class="{MARKER}"><h2>티라노사우루스의 속도: 걸음걸이와 최고속도를 혼동하면 안 되는 이유</h2>
<table><thead><tr><th>연구</th><th>실제로 계산한 값</th><th>해석의 범위</th></tr></thead><tbody>
<tr><td>{a("trexwalk","2021년 꼬리 고유진동수 연구")}</td><td>에너지 효율이 높은 선호 <strong>보행속도</strong>를 초속 1.28m(약 시속 4.6km)로 추정했습니다. 민감도 범위는 초속 0.80~1.64m입니다.</td><td>이 수치는 최고 달리기 속도가 아니므로 최고속도 추정치와 직접 비교하면 안 됩니다.</td></tr>
<tr><td>{a("trexrun","2017년 골격 응력 시뮬레이션")}</td><td>성체가 공중에 떠오르는 본격적인 달리기 자세를 취하면 다리뼈 하중이 과도해질 가능성을 제시했습니다.</td><td>근육·연부조직 복원과 모델의 가정에 따라 결과가 달라질 수 있습니다.</td></tr>
<tr><td>{a("trexmass","2024년 최대 체중 모델")}</td><td>현존 최대급 화석 약 8.8t을 기준으로, 더 큰 개체가 존재했을 가능성을 통계적으로 추정했습니다.</td><td>최대 약 15t은 <strong>발견된 표본의 실측치가 아니라 가상 모집단 모델</strong>의 결과입니다.</td></tr>
</tbody></table><p>따라서 특정 시속 수치를 모든 티라노사우루스 성체의 ‘확정 최고속도’라고 표시하기보다, 어떤 표본과 가정이 사용됐는지를 명시하는 것이 정확합니다.</p></section>'''},
849:{"replacements":[
 ("a mature adult reached a maximum movement speed of 16 to 40 kilometers per hour (10 to 25 miles per hour)",
 "there is no directly measured top speed: biomechanical estimates vary depending on assumptions about muscle forces, skeletal stress and body mass"),
 ("This movement speed was still more than adequate to capture the heavy armored herbivores inhabiting its ecosystem",
 "No single speed estimate can establish which prey animals an adult T. rex could catch in a particular encounter"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Comparing evidence: preferred walking speed is not maximum running speed</h2>
<table><thead><tr><th>Research</th><th>What the model estimated</th><th>What it cannot prove</th></tr></thead><tbody>
<tr><td>{a("trexwalk","2021 tail-frequency method")}</td><td>Energetically preferred <strong>walking</strong> speed: 1.28 m/s (about 4.6 km/h), with model bounds 0.80–1.64 m/s.</td><td>A preferred walk is not a measurement of the animal's peak speed.</td></tr>
<tr><td>{a("trexrun","2017 bone-stress simulation")}</td><td>Running gaits with an aerial phase may have imposed excessive loads on a large adult T. rex skeleton.</td><td>Reconstructed joint loads depend on modeled muscles and soft tissues that were not fossilized.</td></tr>
<tr><td>{a("trexmass","2024 body-mass population model")}</td><td>Known extremely large individuals approach 8.8–9 metric tons; a hypothetical upper extreme near 15 tons was predicted.</td><td>The proposed giant is a statistical extrapolation, not a discovered 15-ton fossil.</td></tr>
</tbody></table><p>Neither bite marks nor mathematical movement estimates can tell us exactly how fast a particular hunt unfolded. Speed claims need model definitions and uncertainty, not one authoritative-looking range.</p></section>'''},
111:{"replacements":[
 ("현재 세계에서 가장 오래된 단일 비클론 나무로 공식 확인된 개체는 캘리포니아 화이트 산맥에 서 있는 '므두셀라(Methuselah)'입니다",
 "캘리포니아 화이트 산맥의 '므두셀라(Methuselah)'는 나이테 교차연대측정으로 확인된 가장 오래된 <strong>이름 붙은</strong> 살아 있는 나무 중 하나입니다. 다만 이름 없는 약 5천 년 수령 개체의 검증 상태에 대해서는 출처별 차이가 있어 단독 최고령이라고 단정하기 어렵습니다"),
 ("2010년 톰 하란(Tom Harlan) 연구원이 5,060년 이상 된 샘플을 측정했다고 보고했으나, 2013년 사망 후 물리적 코어 표본을 찾을 수 없었고 피어리뷰 논문으로 검증되지 않았습니다",
 "톰 하란(Tom Harlan)이 연대를 측정한 익명의 5,000년 넘는 개체는 미 국립공원관리청·산림청과 기네스 등에서 인용되지만, 2026년 유전체 논문은 이를 별도 확인이 필요한 사례로 설명합니다. 따라서 자료 간 검증 기준과 원시 코어의 재현 가능성을 함께 살펴야 합니다"),
 ],
 "note":f'''<section class="{MARKER}"><h2>최고령 나무 기록은 왜 자료마다 다를까요?</h2>
<table><thead><tr><th>자료</th><th>무엇을 기록했나요?</th><th>해석할 때 구분할 점</th></tr></thead><tbody>
<tr><td>{a("nps_old","미 국립공원관리청, 프로메테우스 이야기")}</td><td>1964년 벌목된 프로메테우스의 나이테 약 4,862개를 설명하고, 2012년에 약 5,065년으로 연대가 산정된 더 오래된 개체를 소개합니다.</td><td>죽은 나무의 나이테 수와 현재 살아 있는 나무의 연령은 서로 다른 범주입니다.</td></tr>
<tr><td>{a("guinness_old","기네스 최고령 개체 기록")}</td><td>므두셀라 외에 이름 없는 더 오래된 가시소나무의 연대 자료도 소개합니다.</td><td>각 수치의 조사 연도 및 측정·보정 연도를 같이 확인해야 합니다.</td></tr>
<tr><td>{a("genome_old","2026년 가시소나무 유전체 논문")}</td><td>므두셀라의 2025년 기준 연령을 4,857년으로 제시하며, 2012년에 주장된 5,065년 개체는 잠정적·추가 확인이 필요한 사례로 표현합니다.</td><td>연구기관이 같은 자료를 인용해도 연대 검증의 강도에 대한 판단은 다를 수 있습니다.</td></tr>
</tbody></table><p><strong>핵심:</strong> ‘최고령으로 이름이 붙은 나무’, ‘익명의 고령 나무’, ‘죽은 표본’, ‘뿌리 군락 클론’은 별도로 비교해야 합니다. 고령 개체의 정확한 위치는 보호를 위해 공개하지 않습니다.</p></section>'''},
792:{"replacements":[
 ("the record for the oldest officially verified living non-clonal tree belongs to Methuselah, located in the White Mountains of California",
 "Methuselah in California's White Mountains is among the oldest named, tree-ring-dated living non-clonal trees. Older anonymous bristlecone age records are described differently by institutions, so calling Methuselah the undisputed overall record holder is misleading"),
 ("However, following Harlan's death in 2013, the physical core could not be recovered, and no peer-reviewed paper was published to validate the claim",
 "The National Park Service, U.S. Forest Service and Guinness cite an unnamed 5,000-plus-year-old bristlecone dated by Harlan, while a 2026 genome paper refers to the approximately 5,065-year-old record as provisional. Access to original samples and crossdating documentation matters when judging how strongly a record is established"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Why 'oldest tree' records disagree: three evidence standards</h2>
<table><thead><tr><th>Institution</th><th>Record discussed</th><th>Important qualification</th></tr></thead><tbody>
<tr><td>{a("nps_old","US National Park Service")}</td><td>Describes the Prometheus tree cut in 1964, with approximately 4,862 counted rings, and a different tree aged to around 5,065 years in 2012.</td><td>Dead specimens and currently living, named or unnamed trees should not share a single undifferentiated ranking.</td></tr>
<tr><td>{a("guinness_old","Guinness World Records")}</td><td>Lists Methuselah and also reports an older unnamed living tree dated by dendrochronologists.</td><td>The age cited depends on the reference year and access to documentation.</td></tr>
<tr><td>{a("genome_old","2026 Pinus longaeva genome research")}</td><td>Gives Methuselah's age as 4,857 years in 2025, but explicitly describes the ~5,065-year unnamed specimen as provisional.</td><td>Different institutions apply different evidence standards; the strongest public claim should acknowledge this disagreement.</td></tr>
</tbody></table><p>Ages for clonal aspen colonies refer to recurring genetically identical stems and roots rather than one uninterrupted bristlecone trunk. Exact coordinates of protected old trees are deliberately omitted.</p></section>'''},
137:{"replacements":[
 ("일반적으로 잘 자란 꽃의 지름은 90cm에서 100cm에 달합니다",
 "일부 큰 꽃은 지름 약 1m에 이르지만, 모든 개체의 평균 지름이 90~100cm라고 일반화할 근거는 부족합니다"),
 ("기네스 세계 기록으로 측정된 가장 큰 개체는 지름이 무려 111cm에 이르렀고, 무게는 11kg에 달했습니다",
 "기네스의 <strong>실측 단일 꽃 지름</strong> 기록은 2020년 서수마트라에서 확인된 111cm입니다. 꽃 무게 최대 약 11kg이라는 수치는 별도로 소개되지만, 해당 111cm 개체의 무게를 함께 실측했다는 의미는 아닙니다"),
 ],
 "note":f'''<section class="{MARKER}"><h2>111cm 지름과 11kg 무게는 같은 꽃의 측정일까요?</h2>
<table><thead><tr><th>구분</th><th>확인되는 기록</th><th>자료가 말하지 않는 것</th></tr></thead><tbody>
<tr><td>{a("guinness_raf","기네스 세계기록, 최대 단일 꽃")}</td><td>2020년 1월 인도네시아 서수마트라에서 <em>Rafflesia arnoldii</em> 꽃의 지름 111cm가 기록됐습니다.</td><td>‘최대 11kg’이라는 종의 일반적 무게 상한을 해당 기록 개체에서 측정했다는 뜻은 아닙니다.</td></tr>
<tr><td>{a("kew_raf","큐 왕립식물원 종 프로필")}</td><td>잎·줄기·뿌리를 갖지 않는 완전 기생식물로, 테트라스티그마속 덩굴에 의존하며 단일 꽃을 만듭니다.</td><td>‘시체꽃’으로 불리는 타이탄 아룸의 수많은 작은 꽃으로 이루어진 꽃차례와 같은 구조가 아닙니다.</td></tr>
<tr><td>IUCN 등재</td><td>큐 자료는 이 종을 IUCN 적색목록의 <strong>미평가(NE)</strong>로 표시합니다.</td><td>미평가는 안전하다는 등급이 아니며, 과학자들의 멸종 우려와 공식 등재 상태를 구별해야 합니다.</td></tr>
</tbody></table><p>이 글의 기록 비교는 공식 기관의 현재 공개자료에 근거한 편집 분석이며, 자체 현장 측정 결과가 아닙니다.</p></section>'''},
787:{"replacements":[
 ("On average, these blooms expand to a massive diameter of 90 to 100 centimeters",
 "Some exceptional blooms approach a meter in diameter, but a species-wide average of 90–100 cm cannot be established from the cited record"),
 ("The absolute record holder, documented by Guinness World Records, measured an extraordinary 111 centimeters across and weighed 11 kilograms",
 "Guinness documents a 111 cm diameter measured in West Sumatra in January 2020. The often cited weight of up to 11 kg is a separate upper-size figure for the species; it is not documented as the weight of that same 111 cm bloom"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Evidence comparison: one 111 cm flower, not a 111 cm and 11 kg measurement</h2>
<table><thead><tr><th>Source</th><th>What is documented</th><th>Interpretive limit</th></tr></thead><tbody>
<tr><td>{a("guinness_raf","Guinness largest single flower record")}</td><td>A <em>Rafflesia arnoldii</em> flower measuring 111 cm across was discovered in West Sumatra in January 2020.</td><td>The general estimate of flowers weighing up to 11 kg is not presented as the measured mass of that exact flower.</td></tr>
<tr><td>{a("kew_raf","Royal Botanic Gardens, Kew profile")}</td><td>The plant has no ordinary leaves, roots or stems and depends entirely on <em>Tetrastigma</em> vines.</td><td>Unlike the titan arum, it produces a single flower rather than an unbranched cluster of many flowers.</td></tr>
<tr><td>Conservation status</td><td>Kew lists the species as Not Evaluated (NE) on the IUCN Red List.</td><td>NE is not a conclusion that wild populations are safe. Scientific warnings about habitat loss are not the same as a formal IUCN threat category.</td></tr>
</tbody></table><p>These distinctions help readers separate primary measurements, typical sizes, specimen records and conservation assessments.</p></section>'''}
}
def api(method,route,**kwargs):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+route,timeout=70,**kwargs)
 if r.status_code>=400:raise RuntimeError(f"{method} {route} HTTP {r.status_code} {r.text[:150]}")
 return r.json()
def main():
 changes={}
 for pid,spec in DATA.items():
  post=api("GET",f"posts/{pid}",params={"context":"edit"})
  if post.get("status")!="publish":raise RuntimeError(f"{pid}: no longer published")
  original=post["content"].get("raw") or post["content"].get("rendered") or ""
  if MARKER in original:
   print("C8_ALREADY_PRESENT",pid,flush=True)
   continue
  new=original
  for old,repl in spec["replacements"]:
   if new.count(old)!=1:
    raise RuntimeError(f"{pid}: exact phrase match count={new.count(old)} for {old[:76]}")
   new=new.replace(old,repl,1)
  m=re.search(r"<h2\b",new,re.I)
  if not m:raise RuntimeError(f"{pid}: no heading for safe source note")
  new=new[:m.start()]+spec["note"]+new[m.start():]
  if len(new)<len(original)*.95:raise RuntimeError(f"{pid}: unexpected content loss")
  refs=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',original))
  if not refs or refs!=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',new)):raise RuntimeError(f"{pid}: reference list changed")
  imgs=len(re.findall(r"<img\b",original,re.I))
  if imgs!=len(re.findall(r"<img\b",new,re.I)):raise RuntimeError(f"{pid}: image count changed")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"id":pid,"status":post["status"],
     "title":post["title"],"slug":post["slug"],"content":original,
     "excerpt":post["excerpt"],"modified":post["modified"]},ensure_ascii=False),encoding="utf8")
  changes[pid]={"content":new,"old":original,"refs":refs,"imgs":imgs,
                "url":post.get("link")}
 print("C8_PREFLIGHT_OK",len(changes),"all original HTML backed up",flush=True)
 rows=[]
 for pid,row in changes.items():
  if APPLY:
   api("POST",f"posts/{pid}",json={"content":row["content"]})
   check=api("GET",f"posts/{pid}",params={"context":"edit"})
   html=check["content"].get("raw") or ""
   if check["status"]!="publish" or html.count(MARKER)!=1 or row["imgs"]!=len(re.findall(r"<img\b",html,re.I)):
    raise RuntimeError(f"{pid}: updated publication/content/images mismatch")
   if row["refs"]!=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',html)):
    raise RuntimeError(f"{pid}: original reference identifiers changed")
  z={"id":pid,"result":"UPDATED" if APPLY else "PREVIEW","url":row["url"],
     "original_chars":len(row["old"]),"edited_chars":len(row["content"])}
  rows.append(z);print("C8_ITEM="+json.dumps(z,ensure_ascii=False),flush=True)
 (OUT/"summary.json").write_text(json.dumps({"apply":APPLY,"items":rows,
     "time_utc":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("C8_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(x["result"]=="UPDATED" for x in rows),"preview":sum(x["result"]=="PREVIEW" for x in rows)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
