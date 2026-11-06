"""Evidence-first targeted revision of eight B-priority bilingual articles.

Covers Venus flytrap (26/859), Echiniscus testudo (154/739),
Atlantic horseshoe crab (146/763), and Tiktaalik (150/751).
Only replaces exact verified wording and appends original fact interpretation
with hyperlinks to primary academic or official institutional sources.
All originals saved BEFORE first WordPress write. Dry-run by default.
"""
import os,re,json
from pathlib import Path
from datetime import datetime,timezone
import requests

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("EDITORIAL_B8_APPLY","false").lower()=="true"
OUT=Path("audit_output/editorial_b8");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
MARKER="taxonguru-b8-evidence-2026"
SOURCES={
"venus_actions":"https://pubmed.ncbi.nlm.nih.gov/26804557/",
"venus_pollination":"https://pubmed.ncbi.nlm.nih.gov/29570403/",
"tardigrade_species":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9833599/",
"tardigrade_protein":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8582207/",
"usp":"https://doi.usp.org/USPNF/USPNF_M16015_02_01.html",
"fda":"https://www.fda.gov/drugs/drug-alerts-and-statements/international-collaboration-advance-new-testing-methods-reduce-reliance-horseshoe-crab-blood",
"iucn":"https://iucn.org/our-union/commissions/group/iucn-ssc-horseshoe-crab-specialist-group",
"tik_fin":"https://www.nature.com/articles/nature04637",
"tik_spine":"https://pmc.ncbi.nlm.nih.gov/articles/PMC11009633/"
}
def src(k,label):
 return f'<a href="{SOURCES[k]}" target="_blank" rel="noopener noreferrer">{label}</a>'
ROWS={
26:{"changes":[
 ("실제 야생 파리지옥이 포획하는 먹이의 70~80% 이상은 날아다니는 파리가 아니라, 지면을 기어다니는 개미, 거미, 딱정벌레 등입니다",
  "2018년 야생 개체 조사에서는 포획된 먹이 중 거미·딱정벌레·개미가 특히 흔했습니다. 하지만 종별 포획 비율을 모든 자생지에 동일한 70~80% 수치로 일반화할 근거는 부족합니다"),
 ("약 20~30초 내에 두 번째 자극이 연속해서 가해졌을 때",
  "대표적인 실험에서 약 15~20초 내에 두 번째 활동전위가 발생했을 때"),
 ("파리지옥은 이 문제를 '공간적 분리'라는 지혜로운 전략으로 해결했습니다",
  "현장 연구는 꽃가루받이를 하는 절지동물과 덫에 잡히는 먹이의 종류가 상당히 다르다는 사실을 확인했습니다. 꽃과 덫의 공간 분리는 그 차이를 만드는 여러 요인 중 하나일 수 있습니다"),
 ],
 "note":f'''<section class="{MARKER}"><h2>원연구 비교: 덫을 닫는 신호와 꽃가루받이 곤충은 어떻게 다를까요?</h2>
<table><thead><tr><th>실험·조사</th><th>직접 확인한 사실</th><th>주의할 해석</th></tr></thead><tbody>
<tr><td>{src("venus_actions","2016년 전기신호 실험")}</td><td>감각모 자극으로 두 활동전위가 발생하면 덫이 닫히며, 추가 전기신호가 소화 효소·이온 흡수 관련 유전자 발현을 조절했습니다.</td><td>비유적인 ‘숫자 세기’는 신경계나 의식적 계산의 증거가 아니라 전기적 신호의 누적 반응입니다.</td></tr>
<tr><td>{src("venus_pollination","2018년 야생 먹이·수분매개체 조사")}</td><td>먹이에서는 거미·딱정벌레·개미 등이 흔했고, 꽃에서는 여러 벌·딱정벌레가 꽃가루를 옮겼습니다. 두 집단의 종 수준 겹침은 매우 낮았습니다.</td><td>꽃줄기 높이만이 이 분리를 일으켰다는 인과관계까지 검증된 것은 아닙니다.</td></tr>
</tbody></table><p><strong>독자가 구분할 점:</strong> 트랩의 전기신호 제어는 실험실의 생리학적 측정이고, 곤충 집단 분리는 자연 서식지의 생태 조사입니다. 서로 다른 연구를 연결해 설명하되 수치와 원인을 혼동하면 안 됩니다.</p></section>'''
},
859:{"changes":[
 ("Field research reveals that over 70 to 80 percent of the wild prey captured by <em>Dionaea muscipula</em> consists of crawling ground arthropods, such as ants, spiders, and beetles",
  "A 2018 field survey found spiders, beetles and ants among the most common prey; a universal estimate of 70–80 percent crawling prey should not be inferred from this survey alone"),
 ("within approximately 20 to 30 seconds of the first",
  "within approximately 15 to 20 seconds of the first in a representative experiment"),
 ("By separating its reproductive flowers from its feeding traps by such a substantial distance, flying pollinators like bees and butterflies can safely visit the flowers without risking an untimely death in the hungry leaves below",
  "Research found very little overlap between the arthropod species visiting the flowers and those caught in the traps. Elevating the flowers may contribute, but the study did not establish flower height as the sole cause"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Two field and laboratory studies: electrical signals versus pollinator ecology</h2>
<table><thead><tr><th>Source</th><th>What researchers measured</th><th>What remains uncertain</th></tr></thead><tbody>
<tr><td>{src("venus_actions","2016 action-potential experiments")}</td><td>Two rapid electrical impulses close the trap. Continued prey movements control downstream jasmonate signaling and digestive/enzyme activity.</td><td>Calling this 'counting' describes electrical integration; it does not demonstrate a brain or awareness.</td></tr>
<tr><td>{src("venus_pollination","2018 pollinator-versus-prey field survey")}</td><td>Spiders, beetles and ants were common prey, while the major flower visitors included bees and beetles. Species overlap between flowers and traps was near zero.</td><td>Separating flowers and traps spatially is a plausible contributing factor, not a uniquely demonstrated causal mechanism.</td></tr>
</tbody></table><p><strong>Interpretation:</strong> Mechanistic laboratory measurements and field community comparisons answer different questions; neither should be reduced to a universal feeding percentage or a statement of intentional plant behavior.</p></section>'''
},
154:{"changes":[
 ("이들이 극저온, 강한 방사선, 극단적 건조 환경을 견뎌내는 능력은 수분이 완전히 마르고 신체 수분을 극도로 배출한 '툰(tun)' 상태에 진입했을 때만 발휘됩니다",
  "극단적 건조를 버티는 능력은 주로 수분을 잃고 '툰(tun)' 상태에 들어가는 건면 과정과 관련이 있습니다. 방사선·온도·진공에 대한 내성은 종, 수분 상태, 노출 강도와 시간에 따라 달라져 모든 조건에서 반드시 생존하는 것은 아닙니다"),
 ("거북곰벌레가 속한 이질곰벌레강 생물들에게는 진곰벌레강(Eutardigrada)에서 관찰되는 CAHS나 Dsup 단백질이 전혀 존재하지 않는 것으로 밝혀졌습니다",
  "거북곰벌레의 다중옴믹스 연구에서는 기존 진곰벌레 연구에서 알려진 일부 AHS 유전자 계열이 보존되지 않은 것으로 나타났습니다. 이 결과를 이질곰벌레강 전체에 특정 보호 단백질이 완전히 없다는 뜻으로 확대해서는 안 됩니다"),
 ],
 "note":f'''<section class="{MARKER}"><h2>내성의 실험 조건을 비교하면 ‘무적 생물’이라는 말이 달라집니다</h2>
<table><thead><tr><th>직접 연구</th><th>관찰한 사실</th><th>일반화하면 안 되는 내용</th></tr></thead><tbody>
<tr><td>{src("tardigrade_species","2023년 네 종의 건면 생존 실험")}</td><td><em>Echiniscus testudo</em>를 포함한 네 종에서 건면 기간에 따른 생존 능력과 복귀 시간을 비교했습니다. 같은 환경에 있는 종 사이에도 차이가 나타났습니다.</td><td>곰벌레가 모두 같은 시간 동안 건조나 냉기·방사선을 견딘다는 뜻이 아닙니다.</td></tr>
<tr><td>{src("tardigrade_protein","거북곰벌레 다중옴믹스 원연구")}</td><td>153.7Mb 유전체와 단백질을 분석해 새로운 EtAHS 단백질 계열을 보고했습니다. 시험관 내에서는 수분 감소 시 일부 단백질의 구조 전환을 관찰했습니다.</td><td>시험관 안의 구조 변화가 살아있는 개체의 모든 내성 기작을 단독으로 증명하는 것은 아닙니다.</td></tr>
</tbody></table><p><strong>독자가 얻을 결론:</strong> 생존할 수 있는 환경을 논할 때는 종명, 건조 여부, 온도·방사선 수준과 노출 시간, 복귀 후 활동 여부까지 함께 확인해야 합니다.</p></section>'''
},
739:{"changes":[
 ("Only when locked in this dehydrated tun state can the animal withstand extreme radiation, severe freezing, and vacuum conditions",
  "Desiccation tolerance is closely tied to the dehydrated tun state, but survival under radiation, freezing or vacuum also depends on the species, stress intensity and exposure time; no state guarantees survival"),
 ("it lacks CAHS and Dsup proteins entirely",
  "its studied genome did not conserve several previously identified abundant heat-soluble gene families from eutardigrade model species; this finding should not be generalized to all heterotardigrades or all possible protective mechanisms"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Comparing experiments: how long can this tardigrade survive dry conditions?</h2>
<table><thead><tr><th>Study</th><th>Evidence</th><th>Important limit</th></tr></thead><tbody>
<tr><td>{src("tardigrade_species","2023 four-species desiccation experiment")}</td><td>Compared the survival and recovery of four tardigrade species including <em>E. testudo</em>. Species and habitats differed in their anhydrobiotic performance; longer dry periods required longer recovery.</td><td>These results cannot be used as a universal limit for all tardigrades or extreme space environments.</td></tr>
<tr><td>{src("tardigrade_protein","Multiomics study of E. testudo")}</td><td>Sequenced a 153.7 Mb genome and identified EtAHS protein families. Purified proteins adopted different structures in vitro as water content fell.</td><td>In-vitro protein measurements are mechanistic clues, not proof that one protein protects a whole animal from every stress.</td></tr>
</tbody></table><p><strong>Evidence rule:</strong> distinguish survival during a particular exposure from indefinite 'invincibility,' and species-specific observations from claims about all water bears.</p></section>'''
},
146:{"changes":[
 ("규제 기관의 승인을 받아 의약품 내독소 검사에 도입되고 있습니다",
  "미국약전(USP) 제86장은 재조합 내독소 검사를 기존 LAL 검사에 대한 대안으로 제시하며, 2026년 FDA는 여러 생물학적 제제의 검사 방법을 바꾸는 절차를 승인했습니다. 다만 모든 제품에서 자동으로 동일하게 허용된다는 뜻은 아닙니다"),
 ("의약품과 의료용품의 오염 여부를 측정하는 정밀 시약인 LAL",
  "의약품과 의료용품의 그람음성균 유래 내독소를 검출하는 시약인 LAL"),
 ],
 "note":f'''<section class="{MARKER}"><h2>검사법 비교: 투구게의 피에서 재조합 시약으로</h2>
<table><thead><tr><th>방식</th><th>원리·근거</th><th>어디까지 확인된 것인가?</th></tr></thead><tbody>
<tr><td>LAL</td><td>투구게 변형세포 유래 추출액의 반응으로 그람음성균의 내독소를 검출합니다.</td><td>모든 감염 원인균이나 모든 미생물 오염을 검사하는 일반적인 무균시험과 같지 않습니다.</td></tr>
<tr><td>{src("usp","미국약전 USP &lt;86&gt;")}</td><td>재조합 C인자(rFC) 및 재조합 반응계(rCR)를 이용한 내독소 검사법을 기술합니다.</td><td>적용되는 제품과 검증 요건에 따라 대체시험법 절차를 따라야 합니다.</td></tr>
<tr><td>{src("fda","2026년 미국 FDA 국제 공동평가")}</td><td>특정 제조업체의 여러 생물학적 제제에 대해 LAL 방식에서 재조합 방식으로 전환하는 승인 절차를 지원했습니다.</td><td>전 세계 모든 의약품이 자동 전환됐다는 의미는 아닙니다.</td></tr>
</tbody></table><p>{src("iucn","IUCN 투구게 전문위원회")}는 아메리카투구게를 취약(VU) 종으로 평가합니다. 대체 검사의 확산은 야생 채혈 의존을 줄일 수 있지만, 실제 보전 성과는 도입 규모와 지역별 개체군 변화로 따로 평가해야 합니다.</p></section>'''
},
763:{"changes":[
 ("Regulatory acceptance of rFC now allows pharmaceutical manufacturers to conduct endotoxin testing without harvesting wild animals, offering a sustainable path forward for marine ecosystems",
  "The United States Pharmacopeia describes validated recombinant endotoxin assays, and a 2026 FDA-led collaboration reviewed a manufacturer's transition protocol for several biologic products. This supports a pathway away from animal-derived reagents, but does not constitute blanket approval for every drug"),
 ("to test vaccines, intravenous drugs, and medical equipment for dangerous bacterial contamination",
  "to test pharmaceuticals and medical products for endotoxins from Gram-negative bacteria, which is different from a general sterility test"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Evidence comparison: what rFC testing replaces—and what it does not</h2>
<table><thead><tr><th>Method</th><th>Scientific basis</th><th>Regulatory interpretation</th></tr></thead><tbody>
<tr><td>Horseshoe-crab LAL</td><td>Animal-derived lysate detects Gram-negative bacterial endotoxins.</td><td>It does not replace every microbiological contamination or sterility test.</td></tr>
<tr><td>{src("usp","USP chapter &lt;86&gt;")}</td><td>Introduces recombinant Factor C (rFC) and recombinant cascade reagent (rCR) assay techniques.</td><td>Alternative procedures must meet applicable validation and compendial requirements.</td></tr>
<tr><td>{src("fda","FDA international collaboration, 2026")}</td><td>Approved a post-approval change-management protocol enabling a manufacturer's test transition across several biologic products.</td><td>This is not universal automatic authorization for all pharmaceutical products.</td></tr>
</tbody></table><p>{src("iucn","The IUCN specialist group")} lists the American horseshoe crab as Vulnerable. Replacing animal-derived reagents may reduce bleeding pressure, but benefits should be measured rather than assumed.</p></section>'''
},
150:{"changes":[
 ("골반과 척추를 단단하게 연결해 주는 천골 갈비뼈(sacral rib)가 없었기 때문에 지상에서 자신의 체중을 온전히 견디며 걸어 다니는 것은 불가능했습니다",
  "2024년 CT 연구에서는 틱타알릭의 천골 영역에 특화된 갈비뼈가 있고 골반과 인대로 연결됐을 가능성이 제시됐습니다. 그러나 실제로 마른 땅에서 체중을 지탱하며 걸었는지는 화석만으로 확정할 수 없습니다"),
 ],
 "note":f'''<section class="{MARKER}"><h2>2006년 지느러미 연구와 2024년 척추 CT 연구가 바꾼 그림</h2>
<table><thead><tr><th>연구</th><th>화석에서 확인한 구조</th><th>가능한 해석</th></tr></thead><tbody>
<tr><td>{src("tik_fin","Shubin 외, Nature (2006)")}</td><td>가슴지느러미 내부의 뼈·관절이 바닥에 몸을 지지할 수 있는 자세를 허용했습니다.</td><td>육지 보행의 직접 관찰 증거가 아니라 물속 바닥에서 몸을 받치는 가능성도 포함됩니다.</td></tr>
<tr><td>{src("tik_spine","2024년 PNAS 축골격 CT 연구")}</td><td>갈비뼈가 천골 영역에서 넓고 아래로 휘어진 형태를 보이며 골반 장골에 인대로 연결됐을 가능성이 제시됐습니다.</td><td>'천골 부위가 아예 없었다'는 옛 서술을 수정해야 하지만, 현대 사지동물처럼 단단한 골반-척추 결합을 증명한 것은 아닙니다.</td></tr>
</tbody></table><p><strong>진화 해석:</strong> 물속에서 바닥을 버티는 해부학적 특징이 먼저 나타나고, 육상 동작은 점진적으로 진화했을 수 있습니다. 틱타알릭이 현생 사지동물 전체의 직접 조상이라는 뜻도 아닙니다.</p></section>'''
},
751:{"changes":[
 ("The animal lacked sacral ribs—the specialized ribs that physically link the pelvic girdle directly to the spine",
  "A 2024 CT study identified a specialized sacral region with ribs that may have connected to the pelvis through ligaments, although this is not equivalent to the fully rigid attachment seen in many later tetrapods"),
 ("Without this crucial rigid attachment, the spinal column could not support the full weight of the body against gravity outside of water",
  "These structures support hypotheses of increased pelvic support in shallow water, but fossils cannot by themselves establish the animal's full capacity for walking on dry land"),
 ],
 "note":f'''<section class="{MARKER}"><h2>Fins, ribs and pelvis: what the 2006 and 2024 fossils show</h2>
<table><thead><tr><th>Source</th><th>Direct anatomical evidence</th><th>Scientific interpretation</th></tr></thead><tbody>
<tr><td>{src("tik_fin","Nature 2006: pectoral fin")}</td><td>Expanded fin bones and joints permitted a substrate-supported posture, comparable in certain respects to later limb architecture.</td><td>Supporting a body on the bottom of shallow water is not proof of full terrestrial walking.</td></tr>
<tr><td>{src("tik_spine","PNAS 2024: axial skeleton CT")}</td><td>Ribs in a specialized sacral domain have shapes compatible with ligamentous attachment to an enlarged pelvic bone.</td><td>This revises an old 'no sacral-rib region' claim, but the reconstructed attachment is not identical to a rigid land-tetrapod sacrum.</td></tr>
</tbody></table><p><strong>New insight:</strong> partial integration between pelvic support and the spine likely began before true digits and land locomotion evolved; fossils document the structure rather than an observed walk.</p></section>'''
}
}
def api(method,path,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=75,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {path} HTTP {r.status_code} {r.text[:150]}")
 return r.json()
def main():
 changes={}
 for pid,spec in ROWS.items():
  post=api("GET",f"posts/{pid}",params={"context":"edit"})
  if post.get("status")!="publish":raise RuntimeError(f"{pid}: post is not publicly published")
  original=post["content"].get("raw") or post["content"].get("rendered") or ""
  if MARKER in original:
   print("B8_ALREADY_APPLIED",pid,flush=True);continue
  after=original
  for old,new in spec["changes"]:
   if after.count(old)!=1:
    raise RuntimeError(f"{pid}: unsafe phrase match {after.count(old)} for {old[:80]}")
   after=after.replace(old,new,1)
  h=re.search(r"<h2\b",after,re.I)
  if not h:raise RuntimeError(f"{pid}: no heading; cannot insert without disruption")
  after=after[:h.start()]+spec["note"]+after[h.start():]
  original_refs=set(re.findall(r'id=["\\x27]ref-(\d+)["\\x27]',original))
  if not original_refs:raise RuntimeError(f"{pid}: no original references")
  if original_refs!=set(re.findall(r'id=["\\x27]ref-(\d+)["\\x27]',after)):
   raise RuntimeError(f"{pid}: numbered reference list changed")
  if len(re.findall(r"<img\b",original,re.I))!=len(re.findall(r"<img\b",after,re.I)):
   raise RuntimeError(f"{pid}: image count changed")
  (OUT/f"original_{pid}.json").write_text(json.dumps({
   "id":pid,"title":post["title"],"slug":post["slug"],"status":post["status"],
   "modified":post["modified"],"content":original,"excerpt":post["excerpt"]
  },ensure_ascii=False),encoding="utf-8")
  changes[pid]={"before":original,"after":after,"url":post.get("link"),
                "reference_ids":sorted(original_refs)}
 print("B8_PREFLIGHT_OK",len(changes),"all originals safely backed up",flush=True)
 report=[]
 for pid,change in changes.items():
  if APPLY:
   api("POST",f"posts/{pid}",json={"content":change["after"]})
   check=api("GET",f"posts/{pid}",params={"context":"edit"})
   actual=check["content"].get("raw") or ""
   if check["status"]!="publish" or actual.count(MARKER)!=1:
    raise RuntimeError(f"{pid}: WordPress content or publish status verification failed")
   if set(re.findall(r'id=["\\x27]ref-(\d+)["\\x27]',actual))!=set(change["reference_ids"]):
    raise RuntimeError(f"{pid}: reference IDs changed in WordPress")
   if len(re.findall(r"<img\b",actual,re.I))!=len(re.findall(r"<img\b",change["before"],re.I)):
    raise RuntimeError(f"{pid}: image count changed")
  result={"id":pid,"status":"UPDATED" if APPLY else "PREVIEW",
          "old_length":len(change["before"]),"new_length":len(change["after"]),
          "url":change["url"]}
  report.append(result)
  print("B8_ITEM="+json.dumps(result,ensure_ascii=False),flush=True)
 (OUT/"results.json").write_text(json.dumps({"apply":APPLY,"items":report,
     "checked_at":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf-8")
 print("B8_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(x["status"]=="UPDATED" for x in report),
     "preview":sum(x["status"]=="PREVIEW" for x in report)},ensure_ascii=False),flush=True)
if __name__=="__main__":
 main()
