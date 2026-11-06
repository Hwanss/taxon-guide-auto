"""Evidence-led editorial triage: hold 2 scientifically weak bilingual topics.

Only four explicit WordPress post IDs. No deletion; status -> draft and backups.
Default PREVIEW mode. Restore from saved original WordPress editor if needed.
Never mark AdSense ready or pretend posts have independent expert approval.
"""
from __future__ import annotations
import json,os,re,html
from pathlib import Path
from datetime import datetime,timezone
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("EDITORIAL_TRIAGE_APPLY","false").lower()=="true"
OUT=Path("audit_output/originality_triage");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
S.headers["User-Agent"]="TaxonGuruEditorialQualityTriage/1.0"
TARGETS={
34:{"subject":"Ambystoma mexicanum","language":"ko","reason":"The article makes an unsupported causal claim that neoteny is a necessary condition for full regeneration; reference list lacks matching regeneration primary research.","must_contain":"필수적인 생리적 조건"},
834:{"subject":"Ambystoma mexicanum","language":"en","reason":"Statements about brain and heart regeneration depend mainly on broad secondary sites and do not demonstrate independent source verification.","must_contain":"Blastema"},
260:{"subject":"Hydnellum peckii","language":"ko","reason":"Unqualified human safety/toxicity and drug-like anticoagulation claims are not substantiated by the supplied popular mycology reference set.","must_contain":"치명적인"},
535:{"subject":"Hydnellum peckii","language":"en","reason":"The claim that laboratory evaluations exclude ALL lethal toxins is unsupported by the listed reference set; potentially unsafe or misleading.","must_contain":"no lethal toxins whatsoever"},
}
def wp(method,path,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=70,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {path} HTTP {r.status_code} {r.text[:200]}")
 return r.json()
def main():
 originals={}
 for pid,spec in TARGETS.items():
  p=wp("GET",f"posts/{pid}",params={"context":"edit"})
  if p["status"] not in ("publish","draft"):raise RuntimeError(f"{pid}: unexpected status {p['status']}")
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  title=p["title"].get("raw") or p["title"].get("rendered") or ""
  body=html.unescape(re.sub(r"<[^>]+>"," ",raw))
  if spec["must_contain"].lower() not in body.lower():
   raise RuntimeError(f"{pid}: targeted quality issue absent; manual reassessment required")
  originals[pid]=p
  # Back up the entire original editable WP object plus clear reason. Never log private auth.
  (OUT/f"original_{pid}.json").write_text(
   json.dumps({"reviewed_utc":datetime.now(timezone.utc).isoformat(),
      "id":pid,"reason":spec["reason"],"post":p},ensure_ascii=False,indent=2),encoding="utf8")
 print("ORIGINALITY_TRIAGE_PREFLIGHT_OK",len(originals),flush=True)
 report=[]
 for pid,p in originals.items():
  spec=TARGETS[pid]
  result={"id":pid,"subject":spec["subject"],"language":spec["language"],
          "old_status":p["status"],"reason":spec["reason"],
          "action":"WOULD_HOLD_IN_DRAFT"}
  if p["status"]=="draft":
   result["action"]="ALREADY_DRAFT"
  elif APPLY:
   after=wp("POST",f"posts/{pid}",json={"status":"draft"})
   verify=wp("GET",f"posts/{pid}",params={"context":"edit"})
   if after.get("status")!="draft" or verify.get("status")!="draft":
    raise RuntimeError(f"{pid}: WordPress status update not verified")
   # Public anonymous REST endpoint must no longer expose the post.
   anon=requests.get(BASE+f"/wp-json/wp/v2/posts/{pid}",timeout=30)
   result["public_rest_http"]=anon.status_code
   if anon.status_code==200:
    raise RuntimeError(f"{pid}: draft is accessible through public WordPress REST API")
   result["action"]="MOVED_TO_DRAFT"
  report.append(result)
  print("ORIGINALITY_TRIAGE_ITEM="+json.dumps(result,ensure_ascii=False),flush=True)
 (OUT/"triage_summary.json").write_text(json.dumps({
 "apply":APPLY,"evaluated":58,"on_hold":len(TARGETS),
 "criteria":"Qualified source checks and evidence-led editor decision, NOT Google scoring",
 "original_articles_preserved":True,"items":report
 },ensure_ascii=False,indent=2),encoding="utf8")
 print("ORIGINALITY_TRIAGE_RESULT="+json.dumps({
  "apply":APPLY,"moved_to_draft":sum(x["action"]=="MOVED_TO_DRAFT" for x in report),
  "already_draft":sum(x["action"]=="ALREADY_DRAFT" for x in report)
 },ensure_ascii=False),flush=True)
if __name__=="__main__":main()
