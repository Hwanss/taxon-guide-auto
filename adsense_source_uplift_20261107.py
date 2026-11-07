"""Careful bibliography uplift for 6 published articles / 12 exact reference slots.

Replaces generic Wikipedia and ResearchGate copies with the source academic
journal or research institution, preserving citation ID, pictures and full text.
Always backs up all 6 original WordPress posts BEFORE any write. Preview first.
Does NOT bulk-replace 84 links without verifying their subjects.
"""
from __future__ import annotations
import os,re,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("BIBLIO_UPLIFT_APPLY","false").lower()=="true"
OUT=Path("audit_output/bibliography_uplift");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
# Ref number -> (expected old URL, verified original primary/institution URL, citation label)
REFS={
 227:{
  1:("https://en.wikipedia.org/wiki/Puya_raimondii","https://doi.org/10.3389/fcosc.2024.1349553","Frontiers in Conservation Science (2024): Puya raimondii ecology"),
  3:("https://www.researchgate.net/publication/235343738_Historical_biogeography_and_life-history_evolution_of_AndeanPuyaBromeliaceae_Biogeography_ofPuya","https://doi.org/10.1111/j.1095-8339.2012.01307.x","Botanical Journal of the Linnean Society: Puya biogeography"),
 },
 449:{
  1:("https://en.wikipedia.org/wiki/Puya_raimondii","https://doi.org/10.3389/fcosc.2024.1349553","Frontiers in Conservation Science (2024): Puya raimondii ecology"),
  3:("https://www.researchgate.net/publication/235343738_Historical_biogeography_and_life-history_evolution_of_AndeanPuyaBromeliaceae_Biogeography_ofPuya","https://doi.org/10.1111/j.1095-8339.2012.01307.x","Botanical Journal of the Linnean Society: Puya biogeography"),
 },
 154:{
  1:("https://en.wikipedia.org/wiki/Echiniscus_testudo","https://pmc.ncbi.nlm.nih.gov/articles/PMC8582207/","Multiomics study of Echiniscus testudo (2021)"),
  3:("https://www.researchgate.net/publication/385176101_Distribution_of_tardigrade_cryptobiotic_abilities_across_a_fine-scale_habitat_gradient","https://doi.org/10.1007/s13127-024-00660-z","Organisms Diversity & Evolution (2025): habitat cryptobiosis"),
 },
 739:{
  1:("https://en.wikipedia.org/wiki/Echiniscus_testudo","https://pmc.ncbi.nlm.nih.gov/articles/PMC8582207/","Multiomics study of Echiniscus testudo (2021)"),
  3:("https://www.researchgate.net/publication/385176101_Distribution_of_tardigrade_cryptobiotic_abilities_across_a_fine-scale_habitat_gradient","https://doi.org/10.1007/s13127-024-00660-z","Organisms Diversity & Evolution (2025): habitat cryptobiosis"),
 },
 123:{
  1:("https://en.wikipedia.org/wiki/Quetzalcoatlus","https://doi.org/10.1080/02724634.2020.1780247","Journal of Vertebrate Paleontology (2021): Quetzalcoatlus"),
  5:("http://markwitton-com.blogspot.com/2016/05/","https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/","UC Berkeley (2021): reconstructed Quetzalcoatlus locomotion"),
 },
 807:{
  1:("https://en.wikipedia.org/wiki/Quetzalcoatlus","https://doi.org/10.1080/02724634.2020.1780247","Journal of Vertebrate Paleontology (2021): Quetzalcoatlus"),
  5:("http://markwitton-com.blogspot.com/2016/05/","https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/","UC Berkeley (2021): reconstructed Quetzalcoatlus locomotion"),
 }
}
def req(method,route,**kwargs):
 r=S.request(method,SITE+"/wp-json/wp/v2/"+route,timeout=80,**kwargs)
 if r.status_code>=400:raise RuntimeError(f"{method} {route} HTTP {r.status_code}: {r.text[:200]}")
 return r.json()
def original_ref_count(src):
 return len(re.findall(r'<li\s+id=["\x27]ref-\d+["\x27]',src,re.I))
def new_list_item(pid,number,old,new,label,match):
 ko=pid in (227,154,123)
 src=match.group(0)
 if src.count(old)!=1:raise RuntimeError(f"{pid}: ref {number} contains {src.count(old)} matches of old URL")
 if "wikipedia.org" not in old and "researchgate.net" not in old and "blogspot.com" not in old:raise RuntimeError("source list invalid")
 tail="검토일 2026-11-07" if ko else "reviewed 2026-11-07"
 return f'<li id="ref-{number}"><a href="{new}" target="_blank" rel="noopener noreferrer">{label}</a> — {tail}</li>'
def main():
 pending={}
 for pid,refmap in REFS.items():
  p=req("GET",f"posts/{pid}",params={"context":"edit"})
  if p.get("status")!="publish":raise RuntimeError(f"{pid}: not currently public")
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  changed=raw
  applied=[]
  for rid,(old,new,label) in refmap.items():
   pat=rf'<li\s+id=["\x27]ref-{rid}["\x27][^>]*>.*?</li>'
   found=list(re.finditer(pat,changed,re.I|re.S))
   if len(found)!=1:raise RuntimeError(f"{pid}: ref-{rid} not unique")
   if new in found[0].group() and old not in found[0].group():
    print("BIBLIO_ALREADY",pid,rid,flush=True);continue
   replacement=new_list_item(pid,rid,old,new,label,found[0])
   changed=changed[:found[0].start()]+replacement+changed[found[0].end():]
   applied.append(rid)
  if original_ref_count(raw)!=original_ref_count(changed):raise RuntimeError(f"{pid}: reference count changed")
  if len(re.findall(r"<img\b",raw,re.I))!=len(re.findall(r"<img\b",changed,re.I)):
   raise RuntimeError(f"{pid}: image count changed")
  if len(changed)<len(raw)*.96:raise RuntimeError(f"{pid}: unusual content shrinkage")
  (OUT/f"before_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False,indent=2),encoding="utf8")
  pending[pid]={"before":raw,"after":changed,"updated_ref_ids":applied,"url":p["link"]}
 print("BIBLIO_PREFLIGHT="+json.dumps({"posts":len(pending),"references":sum(len(x["updated_ref_ids"]) for x in pending.values()),"all_originals_backed_up":True},ensure_ascii=False),flush=True)
 results=[]
 for pid,data in pending.items():
  if data["before"]!=data["after"] and APPLY:
   req("POST",f"posts/{pid}",json={"content":data["after"]})
   v=req("GET",f"posts/{pid}",params={"context":"edit"})
   page=v["content"].get("raw") or ""
   if v["status"]!="publish" or page!=data["after"]:raise RuntimeError(f"{pid}: WordPress exact readback mismatch")
   for rid in data["updated_ref_ids"]:
    new=REFS[pid][rid][1]
    if f'<li id="ref-{rid}"><a href="{new}"' not in page:raise RuntimeError(f"{pid}: updated ref {rid} missing")
  line={"post":pid,"status":"UPDATED" if APPLY and data["before"]!=data["after"] else "PREVIEW" if not APPLY else "ALREADY","ref_ids":data["updated_ref_ids"],"url":data["url"]}
  results.append(line);print("BIBLIO_ITEM="+json.dumps(line,ensure_ascii=False),flush=True)
 (OUT/"report.json").write_text(json.dumps({"apply":APPLY,"results":results,"utc":datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("BIBLIO_SUMMARY="+json.dumps({"apply":APPLY,"updated_ref_count":sum(len(x["updated_ref_ids"]) for x in results) if APPLY else 0,"preflight_refs":sum(len(x["updated_ref_ids"]) for x in results),"posts":len(results)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
