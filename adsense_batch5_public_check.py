"""Anonymous, non-writing visibility check for eight scientific content changes."""
import os,json,requests,concurrent.futures
from datetime import datetime,timezone
from pathlib import Path
SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/batch5_public");OUT.mkdir(parents=True,exist_ok=True)
MARK="taxonguru-research-comparison-batch5"
PATHS={
164:"/megalodon-largest-shark/",
709:"/en/otodus-megalodon-science-and-facts/",
170:"/antarctic-icefish-transparent-blood/",
691:"/en/ocellated-icefish-antarctic-adaptation-chionodraco-rastrospinosus/",
180:"/vampire-squid-deep-sea-mystery/",
661:"/en/vampyroteuthis-infernalis-vampire-squid-facts/",
35:"/mimic-octopus-master-disguise/",
829:"/en/mimic-octopus-disguise-facts-and-myth/",
}
def check(item):
 pid,path=item
 try:
  r=requests.get(SITE+path,timeout=60,headers={"User-Agent":"TaxonGuruPublicVerify/1.0","Cache-Control":"no-cache"})
  return {"post_id":pid,"http_status":r.status_code,"research_section_visible":r.text.count(MARK)==1,
   "ok":r.status_code==200 and r.text.count(MARK)==1,"url":r.url}
 except requests.RequestException as e:
  return {"post_id":pid,"ok":False,"exception":type(e).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 results=list(ex.map(check,PATHS.items()))
for row in results:print("B5_PUBLIC_ITEM="+json.dumps(row,ensure_ascii=False),flush=True)
snippet_checks=[]
for pid,required in [(164,"24.3"),(170,"큰지느러미빙어과")]:
 try:
  rr=requests.get(SITE+f"/wp-json/wp/v2/posts/{pid}",timeout=45)
  snippet=rr.json().get("excerpt",{}).get("rendered","") if rr.status_code==200 else ""
  item={"post_id":pid,"http_status":rr.status_code,"updated_excerpt":rr.status_code==200 and required in snippet}
 except requests.RequestException as error:
  item={"post_id":pid,"updated_excerpt":False,"error":type(error).__name__}
 snippet_checks.append(item)
 print("B5_SNIPPET_CHECK="+json.dumps(item,ensure_ascii=False),flush=True)
report={"checked_utc":datetime.now(timezone.utc).isoformat(),"posts":results,"snippets":snippet_checks,"all_ok":all(z["ok"] for z in results) and all(z["updated_excerpt"] for z in snippet_checks)}
(OUT/"public_verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
print("B5_PUBLIC_SUMMARY="+json.dumps({"count":len(results),"ok":sum(x["ok"] for x in results), "excerpt_ok":sum(x["updated_excerpt"] for x in snippet_checks),
    "all_ok":report["all_ok"]},ensure_ascii=False),flush=True)
if not report["all_ok"]:raise SystemExit(1)
