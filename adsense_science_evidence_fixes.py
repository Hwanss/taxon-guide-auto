"""Targeted evidence-backed fixes after independent 58-article editorial review.

Dry-run by default. All six article originals and metadata are backed up before
any writes. Changes are fixed exact-substring replacements with strict preflight.
No article is set to READY or marked human-signed-off by this script.
"""
from __future__ import annotations
import json,os,re,hashlib
from pathlib import Path
from datetime import datetime,timezone
import requests

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("SCIENCE_EDIT_APPLY","false").lower()=="true"
OUT=Path("audit_output/science_editorial");OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])

POSTS={
 178:{
  "title":"부피 기준 세계 최대 나무, 자이언트 세쿼이아의 생존 전략과 위기",
  "excerpt":"자이언트 세쿼이아의 제너럴 셔먼은 줄기 부피 약 1,487m³로 세계 최대 규모의 현존 나무입니다. 하지만 세계에서 질량이 가장 큰 생명체라는 뜻은 아닙니다. 산불과 생태·보전 문제를 미국 국립공원관리청 자료를 바탕으로 살펴봅니다.",
  "replacement":[
    ["지구상에서 단일 생명체로서 가장 커다란 부피와 질량을 자랑하는 식물",
     "세계 최대 줄기 부피 기록을 보유한 나무를 포함하는 식물 종"],
    ["단순한 수직 높이보다 줄기의 굵기와 전체 부피, 그리고 질량 면에서 지구상 단일 생명체 중 1위를 차지합니다",
     "줄기 부피 측면에서 세계 최대 기록을 보유하지만, 모든 생명체 가운데 질량까지 가장 크다는 뜻은 아닙니다"],
    ["단일 줄기 부피 기준으로 세계 최대 규모의 단일 생명체로 공식 인정받고 있습니다",
     "단일 줄기 부피 기준으로 세계 최대 규모의 현존 나무로 기록되어 있습니다"],
  ],
  "note":'<p><strong>기록 구분:</strong> 미국 국립공원관리청은 제너럴 셔먼을 <a href="https://www.nps.gov/seki/learn/nature/sherman.htm" target="_blank" rel="noopener noreferrer">줄기 부피 기준 세계 최대 나무</a>로 소개합니다. 생명체 전체의 질량 기록은 별개로, 기네스는 <a href="https://www.guinnessworldrecords.com/world-records/106978-heaviest-organism" target="_blank" rel="noopener noreferrer">오리건의 거대 꿀버섯</a>을 가장 무거운 생명체로 기록합니다.</p>',
 },
 667:{
  "excerpt":"General Sherman, a giant sequoia, holds the record for the largest measured trunk volume of any living tree. This is a tree-volume record, not a claim that it is the heaviest organism. Explore giant sequoia fire ecology, reproduction and conservation through park-service evidence.",
  "replacement":[
    ["single largest living organism on Earth by trunk volume and overall mass",
     "world's largest recorded tree by trunk volume, although not the heaviest living organism"],
    ["largest individual living organism currently recorded on Earth",
     "largest known living tree by measured trunk volume"],
  ],
  "note":'<p><strong>Record clarification:</strong> The <a href="https://www.nps.gov/seki/learn/nature/sherman.htm" target="_blank" rel="noopener noreferrer">US National Park Service</a> identifies General Sherman as the largest tree by trunk volume. The <a href="https://www.guinnessworldrecords.com/world-records/106978-heaviest-organism" target="_blank" rel="noopener noreferrer">Guinness record for the heaviest organism</a> instead describes an Armillaria fungal individual in Oregon. The two rankings must not be conflated.</p>',
 },
 123:{
  "excerpt":"케찰코아틀루스는 날개 폭 약 10~11미터의 거대 익룡으로, 복원된 어깨높이는 약 2.5미터입니다. 긴 목과 머리를 포함한 전체 높이와 어깨높이를 혼동하지 않으면서, 제한된 화석으로 추정한 비행 방식과 생태를 살펴봅니다.",
  "replacement":[
    ["네 다리로 지면을 딛고 사족 보행으로 서 있을 때의 어깨 높이는 4~5미터에 이릅니다",
     "골격 복원 연구에서 어깨 높이는 약 2.5미터로 추정됩니다"],
    ["우리가 동물원에서 목을 한참 올려다보는 기린의 키와 유사합니다",
     "이는 성체 기린의 어깨높이 약 2.75미터에 가깝지만, 긴 목과 머리를 포함한 전체 높이와는 구별해야 합니다"],
    ["어깨 높이가 기린만 한 생물이 네 다리로 땅을 강하게 차올라 2.4미터 위로 솟구친 뒤",
     "기린의 어깨높이에 가까운 익룡이 지면에서 이륙한 뒤"],
  ],
  "reference":{7:"https://doi.org/10.1080/02724634.2021.1907587",
               8:"https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/"},
  "note":'<p><strong>복원 수치 안내:</strong> <a href="https://www.nhm.ac.uk/discover/the-truth-about-pterosaurs.html" target="_blank" rel="noopener noreferrer">영국 자연사박물관</a>은 케찰코아틀루스 어깨높이를 약 2.5m, 성체 기린 어깨높이를 약 2.75m로 제시합니다. 긴 목·머리를 포함한 전체 높이나 상상도에 표시된 수치와 구분해 해석해야 합니다.</p>',
 },
 807:{
  "excerpt":"Quetzalcoatlus northropi had an estimated 10–11-meter wingspan and a reconstructed shoulder height of roughly 2.5 meters, close to a giraffe's 2.75-meter shoulder height. Explore the fossil evidence behind its walking, feeding and proposed takeoff mechanisms.",
  "replacement":[
    ["its shoulder height alone measured between 4 and 5 meters (13 to 16 feet)",
     "its reconstructed shoulder height was about 2.5 meters (8 feet)"],
    ["That stature matches an adult giraffe, allowing the animal to stand shoulder-to-shoulder with the tallest living land mammal without even extending its long neck",
     "This is close to the approximately 2.75-meter shoulder height of an adult giraffe; total height including the neck and head is a separate measurement"],
  ],
  "reference":{7:"https://doi.org/10.1080/02724634.2021.1907587",
               8:"https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/"},
  "note":'<p><strong>Scale correction:</strong> The <a href="https://www.nhm.ac.uk/discover/the-truth-about-pterosaurs.html" target="_blank" rel="noopener noreferrer">Natural History Museum, London</a>, gives an estimated shoulder height of about 2.5 m for Quetzalcoatlus, compared with approximately 2.75 m for an adult giraffe. Full standing height and shoulder height are different quantities.</p>',
 },
 35:{
  "excerpt":"흉내문어는 가자미류·쏠배감펭·바다뱀 등을 닮은 자세와 무늬를 보이는 동적 모방으로 알려져 있습니다. 하지만 모방 대상이 정확히 세 종 또는 열다섯 종으로 확정된 것은 아닙니다. 초기 현장 관찰 연구를 통해 실제 모방 행동을 살펴봅니다.",
  "replacement":[
    ["과학자들이 촬영된 영상 자치 자료와 동적 모방 행동을 엄격하게 분석한 결과, 정밀하게 검증된 흉내문어의 모방 대상은 3종으로 확인되었습니다",
     "연구자들이 현장에서 촬영한 영상과 행동을 분석한 결과, 흉내문어가 가자미류·쏠배감펭·바다뱀 등의 모습을 모방하는 사례가 보고되었습니다. 다만 모방 대상이 정확히 세 종뿐이라고 확정된 것은 아닙니다"],
    ["15가지 동물로 변신하는 사기캐? 오해와 진실을 파헤치다",
     "흉내문어는 정말 15가지 동물을 흉내 낼까? 관찰 기록과 주장의 차이"],
    ["단 3가지 생물만을 엄격하게 모방하더라도",
     "몇 가지 대표적인 모방 행동만 살펴보더라도"],
  ],
  "reference":{4:"https://pmc.ncbi.nlm.nih.gov/articles/PMC1088805/"},
  "note":'<p><strong>근거 범위:</strong> Norman·Finn·Tregenza(2001)의 <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC1088805/" target="_blank" rel="noopener noreferrer">현장 연구 논문</a>은 여러 동물의 모습을 연상시키는 동적 모방 행동을 기록했습니다. 널리 알려진 세 가지 사례를 소개하는 것과 이 종의 모방 레퍼토리가 세 종뿐이라고 확정하는 것은 다릅니다.</p>',
 },
 829:{
  "excerpt":"Field studies describe dynamic mimicry by Thaumoctopus mimicus, with flatfish, lionfish and banded sea snakes among the familiar examples. The evidence does not establish a repertoire of exactly three or fifteen species.",
  "replacement":[
    ["for exactly three high-threat organisms",
     "with prominent examples including several animals"],
    ["centered on three specific models",
     "illustrated by several well-described model animals"],
    ["the octopus thrives because its three models represent widespread, well-recognized threats in its environment",
     "these familiar mimicry forms may offer defensive advantages in its habitat"],
    ["Anatomy of an Illusion: Three Verified Performances",
     "Anatomy of an Illusion: Three Well-Known Examples"],
  ],
  "reference":{4:"https://pmc.ncbi.nlm.nih.gov/articles/PMC1088805/"},
  "note":'<p><strong>Evidence qualification:</strong> <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC1088805/" target="_blank" rel="noopener noreferrer">Norman, Finn &amp; Tregenza (2001)</a> documented dynamic mimicry and several model-like postures in observed octopuses. The well-known flatfish, lionfish and sea-snake examples should not be mistaken for a conclusive upper limit of three possible mimicked species.</p>',
 }
}

def req(method,path,**kwargs):
 r=s.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=70,**kwargs)
 if r.status_code>=400:raise RuntimeError(f"{method} {path} HTTP {r.status_code} {r.text[:120]}")
 return r.json()

def patch_li(raw,num,url):
 pat=rf'(<li\s+id=["\\x27]ref-{num}["\\x27][^>]*>.*?<a\s+href=["\\x27])([^"\\x27]+)(["\\x27])'
 matched=re.search(pat,raw,re.I|re.S)
 if not matched:raise RuntimeError(f"Reference {num} not located")
 original=matched.group(2)
 if not original.startswith("http"):raise RuntimeError(f"Reference {num} url unexpected")
 def change(m):return m.group(1)+url+m.group(3)
 return re.sub(pat,change,raw,count=1,flags=re.I|re.S)

def preflight():
 changes={}
 for pid,spec in POSTS.items():
  post=req("GET",f"posts/{pid}",params={"context":"edit"})
  if post["status"]!="publish":raise RuntimeError(f"{pid} no longer published")
  raw=post["content"].get("raw") or post["content"].get("rendered") or ""
  title=post["title"].get("raw") or post["title"].get("rendered") or ""
  old_excerpt=post["excerpt"].get("raw") or post["excerpt"].get("rendered") or ""
  marker="taxonguru-final-evidence-correction"
  if marker in raw:
   print(json.dumps({"id":pid,"status":"ALREADY_PRESENT"},ensure_ascii=False),flush=True)
   continue
  new=raw
  for old,repl in spec["replacement"]:
   if new.count(old)!=1:raise RuntimeError(f"{pid}: strict phrase match failed: {old[:45]}")
   new=new.replace(old,repl,1)
  for n,u in spec.get("reference",{}).items():
   new=patch_li(new,n,u)
  note='<div class="'+marker+'">'+spec["note"]+'</div>'
  if "<h2" not in new:raise RuntimeError(f"{pid}: missing section heading")
  new=new.replace("<h2",note+"<h2",1)
  if len(new)<len(raw)*.95:raise RuntimeError(f"{pid}: excessive content change")
  changes[pid]={"post":post,"before":raw,"after":new,
                "old_title":title,"old_excerpt":old_excerpt,"spec":spec}
  (OUT/f"original_{pid}.json").write_text(
     json.dumps({"id":pid,"content":raw,"title":title,"excerpt":old_excerpt,
                 "modified":post["modified"]},ensure_ascii=False,indent=2),encoding="utf8")
 return changes

def main():
 changes=preflight() # do not write anything until all originals are validated
 summary={"apply":APPLY,"checked":len(POSTS),"planned":len(changes),"results":[]}
 print("PREFLIGHT_SUCCESS",len(changes),"backups",flush=True)
 for pid,obj in changes.items():
  try:
   payload={"content":obj["after"],"excerpt":obj["spec"]["excerpt"]}
   if obj["spec"].get("title"):payload["title"]=obj["spec"]["title"]
   if APPLY:
    req("POST",f"posts/{pid}",json=payload)
    v=req("GET",f"posts/{pid}",params={"context":"edit"})
    actual=v["content"].get("raw") or ""
    if "taxonguru-final-evidence-correction" not in actual or v["status"]!="publish":
     raise RuntimeError("post-update content status check failed")
    if v["excerpt"].get("raw")!=obj["spec"]["excerpt"]:raise RuntimeError("excerpt mismatch")
    if obj["spec"].get("title") and v["title"].get("raw")!=obj["spec"]["title"]:
     raise RuntimeError("title mismatch")
   row={"id":pid,"status":"UPDATED" if APPLY else "PREVIEW",
        "html_before":len(obj["before"]),"html_after":len(obj["after"])}
  except Exception as exc:
   row={"id":pid,"status":"ERROR","reason":str(exc)}
  summary["results"].append(row)
  print("EVIDENCE_EDIT_ITEM="+json.dumps(row,ensure_ascii=False),flush=True)
 (OUT/"results.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
 print("EVIDENCE_EDIT_SUMMARY="+json.dumps({"apply":APPLY,"posts":len(POSTS),"errors":sum(x["status"]=="ERROR" for x in summary["results"])},ensure_ascii=False),flush=True)
 return int(any(x["status"]=="ERROR" for x in summary["results"]))

if __name__=="__main__":raise SystemExit(main())
