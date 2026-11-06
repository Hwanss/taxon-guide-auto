"""Correct misleading century-bloom wording in bilingual Puya raimondii articles.

Published titles, excerpts and 3 exact scientific phrases; add records from
Botanic Gardens of Sydney, the 2024 review and Guinness's historic cultivated
28-year exception. Changes require preflight and are backed up. Dry-run default.
"""
import os,json
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("PUYA_EDIT_APPLY","false").lower()=="true"
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
out=Path("audit_output/puya_evidence_corrections");out.mkdir(parents=True,exist_ok=True)
SOURCES=[
"https://www.botanicgardens.org.au/our-science/our-collections/plant-names-and-classifications/bromeliads",
"https://www.frontiersin.org/journals/conservation-science/articles/10.3389/fcosc.2024.1349553/full",
"https://www.guinnessworldrecords.com/world-records/slowest-flowering-plant",
]
SPEC={
227:{"original_title":"100년에 한 번 꽃을 피우는 안데스의 거탑 '푸야 라이몬디'의 생태와 생존 전략",
 "title":"평생 단 한 번 꽃피는 안데스의 거탑, 푸야 라이몬디의 생존 전략",
 "excerpt":"안데스의 푸야 라이몬디(Puya raimondii)는 수십 년에 걸쳐 성장한 뒤 일생에 한 번 개화하고 생을 마감합니다. 자료마다 개화 연령 추정이 다르며, 28년 만에 개화한 재배 기록도 있습니다. 꽃차례의 크기, 번식 전략과 보전 문제를 함께 살펴봅니다.",
 "replacements":[
 ("평생 단 한 번, 100년 만에 꽃을 피우고 장렬히 전사하는 이 거탑은",
  "정확한 개화 연령은 개체와 환경에 따라 다르지만, 생애 마지막에 한 번 개화한 뒤 수명을 마치는 이 식물은"),
 ("야생에서는 미세기후에 따라 개화까지 40년에서 150년이라는 긴 세월이 걸립니다",
  "학술 자료마다 개화까지 걸리는 기간이 약 60~100년 또는 80~150년 등으로 다르게 제시됩니다. 따라서 모든 개체가 정확히 100년에 개화한다고 말할 수는 없습니다"),
 ("반면 적절한 온도와 영양이 공급되는 식물원 같은 재배 환경에서는 약 28~30년 만에 꽃을 피우기도 합니다",
  "기네스 기록에는 캘리포니아대 버클리 식물원에서 재배한 개체가 약 28년 만에 개화한 예외 사례도 소개되어 있습니다"),
 ],
 "extra":'<p><strong>개화 연령의 근거 비교:</strong> <a href="'+SOURCES[0]+'" target="_blank" rel="noopener noreferrer">시드니 식물원</a>은 약 80~100년, <a href="'+SOURCES[1]+'" target="_blank" rel="noopener noreferrer">2024년 생태학 리뷰</a>는 약 60~100년을 소개합니다. <a href="'+SOURCES[2]+'" target="_blank" rel="noopener noreferrer">기네스의 기록</a>은 야생 추정치와 약 28년 만의 재배 개화 사례를 함께 설명합니다. 이는 개화 시점이 일정한 주기가 아니라 생애 한 번의 사건임을 보여줍니다.</p>'},
449:{"original_title":"Puya raimondii: The Queen of the Andes That Waits a Century to Bloom",
 "title":"Puya raimondii: The Queen of the Andes That Flowers Once",
 "excerpt":"Puya raimondii is a giant Andean bromeliad that flowers once before dying. Published estimates for its age at flowering vary, and a cultivated specimen reportedly flowered after 28 years. Compare the life-history evidence, inflorescence and conservation challenges.",
 "replacements":[
 ("Rather than producing flowers every spring, the plant acts as a massive energy reservoir, storing carbohydrates over a span of 40 to 150 years in the wild",
  "Rather than flowering every spring, the plant grows for decades before a single reproductive episode. Published estimates vary: some reviews describe roughly 60–100 years, while Guinness records a wider historical range of 80–150 years"),
 ("Under ideal cultivated conditions in botanical gardens, where warmth and water are consistently managed, this growth period can shorten significantly to about 28 to 30 years",
  "An exceptional plant grown at the University of California Botanical Garden was recorded flowering after about 28 years, according to Guinness World Records"),
 ],
 "extra":'<p><strong>What the evidence supports:</strong> The <a href="'+SOURCES[0]+'" target="_blank" rel="noopener noreferrer">Botanic Gardens of Sydney</a> describes a roughly 80–100-year life history. A <a href="'+SOURCES[1]+'" target="_blank" rel="noopener noreferrer">2024 ecology review</a> gives a roughly 60–100-year range, while <a href="'+SOURCES[2]+'" target="_blank" rel="noopener noreferrer">Guinness World Records</a> includes a cultivated example flowering after about 28 years. These estimates differ, but all agree that the plant flowers only once, not once every 100 years.</p>"}
}
def call(method,route,**kw):
 r=s.request(method,BASE+"/wp-json/wp/v2/"+route,timeout=75,**kw);r.raise_for_status();return r.json()
def main():
  entries={}
  for pid,sp in SPEC.items():
    p=call("GET",f"posts/{pid}",params={"context":"edit"})
    title=p["title"].get("raw") or p["title"].get("rendered")
    body=p["content"].get("raw") or p["content"].get("rendered") or ""
    if p.get("status")!="publish":raise RuntimeError(f"{pid}: not public")
    if title==sp["title"] and "puya-growth-evidence" in body:
      print("PUYA_ALREADY_FIXED",pid,flush=True);continue
    if title!=sp["original_title"]:raise RuntimeError(f"{pid}: unexpected old title {title}")
    edited=body
    for old,new in sp["replacements"]:
      if edited.count(old)!=1:raise RuntimeError(f"{pid}: source phrase not found uniquely: {old[:60]}")
      edited=edited.replace(old,new,1)
    if "<h2" not in edited:raise RuntimeError("No section to attach evidence")
    edited=edited.replace("<h2",'<div class="puya-growth-evidence">'+sp["extra"]+"</div><h2",1)
    (out/f"original_{pid}.json").write_text(json.dumps({"id":pid,"title":title,"content":body,"excerpt":p["excerpt"],"modified":p["modified"]},ensure_ascii=False,indent=2),encoding="utf8")
    entries[pid]={"new_content":edited,"old_content":body,"payload":{"title":sp["title"],"excerpt":sp["excerpt"],"content":edited}}
  print("PUYA_PREFLIGHT_OK",len(entries),flush=True)
  final=[]
  for pid,x in entries.items():
    if APPLY:
      call("POST",f"posts/{pid}",json=x["payload"])
      p=call("GET",f"posts/{pid}",params={"context":"edit"})
      raw=p["content"].get("raw") or ""
      if p.get("status")!="publish" or p["title"].get("raw")!=x["payload"]["title"] or "puya-growth-evidence" not in raw:raise RuntimeError(f"{pid}: content validation failed")
      status="UPDATED"
    else:status="PREVIEW"
    result={"id":pid,"status":status,"before_chars":len(x["old_content"]),"after_chars":len(x["new_content"])}
    final.append(result);print("PUYA_ITEM="+json.dumps(result),flush=True)
  (out/"result.json").write_text(json.dumps(final,indent=2),encoding="utf8")
if __name__=="__main__":main()
