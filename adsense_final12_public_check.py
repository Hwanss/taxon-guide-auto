"""Anonymous, non-writing visibility check for eight scientific content changes."""
import os,json,requests,concurrent.futures
from datetime import datetime,timezone
from pathlib import Path
SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/final12_public");OUT.mkdir(parents=True,exist_ok=True)
MARK="taxonguru-final12-editorial-2026"
PATHS={
123:"/quetzalcoatlus-giant-pterosaur/",
807:"/en/quetzalcoatlus-northropi-giant-flying-pterosaur/",
141:"/victoria-amazonica-giant-lily/",
775:"/en/victoria-amazonica-giant-water-lily-facts/",
178:"/giant-sequoia-largest-tree/",
667:"/en/giant-sequoia-mass-fire-ecology-and-survival/",
221:"/armillaria-ostoyae-honey-mushroom-giant/",
434:"/en/largest-living-organism-armillaria-ostoyae-fungus/",
227:"/puya-raimondii-century-bloom-andes-giant/",
449:"/en/puya-raimondii-queen-of-the-andes/",
254:"/monotropa-uniflora-ghost-plant/",
518:"/en/monotropa-uniflora-ghost-pipe-biology/",
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
for row in results:print("FINAL12_PUBLIC_ITEM="+json.dumps(row,ensure_ascii=False),flush=True)
report={"checked_utc":datetime.now(timezone.utc).isoformat(),"posts":results,"all_ok":all(z["ok"] for z in results)}
(OUT/"public_verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
print("FINAL12_PUBLIC_SUMMARY="+json.dumps({"count":len(results),"ok":sum(x["ok"] for x in results),
    "all_ok":report["all_ok"]},ensure_ascii=False),flush=True)
if not report["all_ok"]:raise SystemExit(1)
