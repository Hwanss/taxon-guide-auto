"""Read-only bilingual integrity audit of all 27 active content topic pairs."""
from __future__ import annotations
import os,json,datetime,concurrent.futures
from pathlib import Path
import requests
from bs4 import BeautifulSoup
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/bilingual_seo");OUT.mkdir(parents=True,exist_ok=True)
PAIRS=[(24,864),(26,859),(27,854),(30,849),(32,839),(35,829),(111,792),(116,797),(123,807),(137,787),(139,781),(141,775),(146,763),(150,751),(154,739),(162,715),(164,709),(170,691),(176,673),(178,667),(180,661),(201,386),(209,401),(221,434),(227,449),(231,460),(254,518)]
def fetchlist():
 r=requests.get(BASE+"/wp-json/wp/v2/posts",params={"per_page":100,"status":"publish"},timeout=55);r.raise_for_status()
 return r.json()
def inspect(x):
 pid,url,expected_lang=x
 try:
  r=requests.get(url,timeout=50)
  soup=BeautifulSoup(r.text,"html.parser")
  alternate={a.get("hreflang"):a.get("href","") for a in soup.select("link[hreflang]")}
  canon=soup.select_one('link[rel="canonical"]')
  desc=soup.select_one('meta[name="description"]')
  return {"id":pid,"url":url,"http":r.status_code,"html_lang":soup.html.get("lang") if soup.html else "",
   "has_desc":bool(desc and len(desc.get("content",""))>40),
   "canonical":canon.get("href","") if canon else None,
   "alternates":alternate,"h1":len(soup.select("h1")),"expected_language":expected_lang}
 except requests.RequestException as err:
  return {"id":pid,"url":url,"http":0,"error":type(err).__name__}
def main():
 posts=fetchlist()
 by_id={x["id"]:x for x in posts}
 if len(posts)!=54:raise RuntimeError(f"Expected 54 public posts, got {len(posts)}")
 jobs=[]
 for ko,en in PAIRS:
  if ko not in by_id or en not in by_id:raise RuntimeError(f"missing public pair {ko}/{en}")
  jobs.extend([(ko,by_id[ko]["link"],"ko"),(en,by_id[en]["link"],"en")])
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
  results=list(ex.map(inspect,jobs))
 by={x["id"]:x for x in results}
 faults=[]
 for ko,en in PAIRS:
  x,y=by[ko],by[en]
  for q in (x,y):
   if q.get("http")!=200:faults.append({"id":q["id"],"issue":"HTTP not 200"})
   if not q.get("has_desc"):faults.append({"id":q["id"],"issue":"missing meta description"})
   if q.get("h1")!=1:faults.append({"id":q["id"],"issue":"missing/duplicate h1"})
   if (q.get("canonical") or "").rstrip("/")!=q["url"].rstrip("/"):
    faults.append({"id":q["id"],"issue":"canonical mismatch"})
   expected=q["expected_language"]
   if expected not in q.get("html_lang","").lower():
    faults.append({"id":q["id"],"issue":"page html language mismatch"})
   alt=q.get("alternates",{})
   if alt.get("ko","").rstrip("/")!=x["url"].rstrip("/") or alt.get("en","").rstrip("/")!=y["url"].rstrip("/"):
    faults.append({"id":q["id"],"issue":"nonreciprocal/missing ko/en hreflang"})
 summary={"count_public":len(posts),"checked":len(results),"pairs":len(PAIRS),
 "correct_bidirectional_pairs":sum(not any(z["id"] in (ko,en) for z in faults) for ko,en in PAIRS),
 "faults":faults,"time":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (OUT/"bilingual_audit.json").write_text(json.dumps({"summary":summary,"pages":results},ensure_ascii=False,indent=2),encoding="utf8")
 print("BILINGUAL_SEO_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
