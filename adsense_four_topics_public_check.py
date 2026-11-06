"""Anonymous, non-writing visibility check for eight scientific content changes."""
import os,json,requests,concurrent.futures
from datetime import datetime,timezone
from pathlib import Path
SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/four_topic_public");OUT.mkdir(parents=True,exist_ok=True)
MARK="taxonguru-verified-20261106-topic-review"
PATHS={
162:"/architeuthis-dux-giant-squid/",
715:"/en/science-of-the-giant-squid-architeuthis-dux/",
176:"/dragons-blood-tree-red-sap/",
673:"/en/socotra-dragon-blood-tree-survival-adaptation/",
231:"/goblin-shark-deep-sea-alien/",
460:"/en/goblin-shark-mitsukurina-owstoni-facts/",
209:"/nautilus-pompilius-living-fossil/",
401:"/en/chambered-nautilus-myths-vs-reality/",
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
for row in results:print("FOUR_PUBLIC_ITEM="+json.dumps(row,ensure_ascii=False),flush=True)
excerpt={"ok":False}
try:
 x=requests.get(SITE+"/wp-json/wp/v2/posts/231",timeout=45)
 if x.status_code==200:
  raw=x.json()["excerpt"]["rendered"]
  excerpt={"http_status":x.status_code,"ok":"3.14" in raw and "1억 2,500만 년 동안 심해 환경에 완벽히 적응" not in raw}
 else: excerpt={"http_status":x.status_code,"ok":False}
except requests.RequestException as exc:excerpt={"exception":type(exc).__name__,"ok":False}
report={"checked_utc":datetime.now(timezone.utc).isoformat(),"posts":results,"goblin_excerpt":excerpt,
        "all_ok":all(z["ok"] for z in results) and excerpt["ok"]}
(OUT/"public_verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
print("FOUR_PUBLIC_SUMMARY="+json.dumps({"count":len(results),"ok":sum(x["ok"] for x in results),
    "excerpt_ok":excerpt["ok"],"all_ok":report["all_ok"]},ensure_ascii=False),flush=True)
if not report["all_ok"]:raise SystemExit(1)
