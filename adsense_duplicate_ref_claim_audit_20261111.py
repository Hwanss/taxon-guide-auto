"""Read-only citation-slot and claim-context audit for TaxonGuru duplicate URLs.

No mutations, no credentials, no automatic replacement. Saves 4 target articles' exact
reference URLs and citation snippets to an Actions artifact for claim/source comparison.
"""
from __future__ import annotations
import datetime
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup

ROOT=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/duplicate_ref_claim_review")
OUT.mkdir(parents=True,exist_ok=True)
TARGETS={227:(2,5),449:(2,5),209:(4,5),401:(4,5)}
S=requests.Session()
S.headers["User-Agent"]="TaxonGuruReadOnlyClaimAudit/2026-11-11"

def plain(text):
 return " ".join(BeautifulSoup(text, "html.parser").get_text(" ",strip=True).split())

def get_post(pid):
 res=S.get(f"{ROOT}/wp-json/wp/v2/posts/{pid}",timeout=60,params={"_": "20261111claimreview"})
 res.raise_for_status()
 p=res.json()
 if p.get("id")!=pid or p.get("status")!="publish":raise ValueError(f"{pid}: not currently published")
 return p

def inspect(pid,nums):
 p=get_post(pid)
 raw=p["content"]["rendered"]
 soup=BeautifulSoup(raw,"html.parser")
 refs={}
 for n in nums:
  li=soup.find(id=f"ref-{n}")
  if li is None:raise ValueError(f"{pid} missing ref-{n}")
  refs[n]={"text":plain(str(li)),"links":[a["href"] for a in li.select("a[href]")]}
 # Exclude bibliography first so references aren't counted as body mentions
 for node in soup.select('[id^="ref-"]'):node.decompose()
 # HTML-based citation-link context, plus literal [2,5] plain citations
 alltext=plain(str(soup))
 snippets=[]
 for n in nums:
  expressions=[rf"\[{n}\]",rf"(?<!\d){n}(?!\d)"]
  matches=list(re.finditer(expressions[0],alltext))
  # For some sources [2,5] bracket clusters, inspect all bracket numbers instead
  for x in re.finditer(r"\[\s*\d+(?:\s*[,;]\s*\d+)*\s*\]",alltext):
   numbers=[int(z) for z in re.findall(r"\d+",x.group())]
   if n in numbers and all(abs(x.start()-m.start())>2 for m in matches):matches.append(x)
  contexts=[]
  for m in matches[:18]:
   a=max(0,m.start()-190);b=min(len(alltext),m.end()+120)
   contexts.append(alltext[a:b])
  snippets.append({"ref_id":n,"mentions":len(matches),"samples":contexts[:12]})
 result={
  "id":pid,"url":p["link"],"modified":p.get("modified"),
  "title":plain(p["title"]["rendered"]),
  "references":refs,"citations":snippets,
  "duplicate_urls":len(set(u for r in refs.values() for u in r["links"]))<sum(len(r["links"]) for r in refs.values())
 }
 (OUT/f"claim_context_{pid}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 return result

def main():
 results=[inspect(pid,nums) for pid,nums in TARGETS.items()]
 report={"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"items":results,"read_only":True,
         "limits":"This is literal citation-context extraction, not scholarly source verification. No link changes are safe until a claim-level original study is reviewed."}
 (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print("TARGET_DUPLICATE_REF_SUMMARY="+json.dumps({"items":[{
    "id":r["id"],"title":r["title"],"modified":r["modified"],"references":r["references"],
    "citation_contexts":r["citations"]} for r in results]},ensure_ascii=False),flush=True)
if __name__=="__main__":
 main()
