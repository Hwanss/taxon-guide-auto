"""Read-only network reachability scan for citations in all 58 published articles.

Status codes 403/429 and transport failures are flagged for MANUAL checking, not
called dead sources. Confirm HTTP 404/410 with GET and track all results.
No WordPress writes. Source content claims are NOT validated by this network scan.
"""
import csv,json,os,collections,urllib.parse,concurrent.futures
from pathlib import Path
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
AUTH=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
OUT=Path("audit_output/source_health");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=AUTH
S.headers["User-Agent"]="TaxonGuruReadOnlySourceVerification/1.0"
def fetch_posts():
 posts=[]
 for n in range(1,4):
  r=S.get(BASE+"/wp-json/wp/v2/posts",params={"status":"publish","per_page":100,"page":n,"context":"edit"},timeout=55)
  if r.status_code==400:break
  r.raise_for_status()
  posts.extend(r.json())
  if n>=int(r.headers.get("X-WP-TotalPages","1")):break
 return posts
def check_one(item):
 url,ids=item
 try:
  s=requests.Session()
  s.headers["User-Agent"]="Mozilla/5.0 (compatible; AcademicReferencesAudit/1.0)"
  r=s.get(url,timeout=(7,13),allow_redirects=True,stream=True)
  code=r.status_code;dest=r.url;r.close()
  if code in (404,410):
   status="HTTP_NOT_FOUND"
  elif 200<=code<400:
   status="REACHABLE"
  elif code in (401,403,406,429,451):
   status="ACCESS_RESTRICTED"
  else:status="HTTP_OTHER"
  return {"url":url,"post_ids":ids,"status":status,"http":code,"final_url":dest}
 except requests.exceptions.RequestException as e:
  return {"url":url,"post_ids":ids,"status":"REQUEST_ERROR","http":None,
          "error":type(e).__name__}
def main():
 posts=fetch_posts()
 sources=collections.defaultdict(set)
 counts=collections.Counter()
 for p in posts:
  soup=BeautifulSoup(p["content"].get("raw") or p["content"].get("rendered") or "",'html.parser')
  for li in soup.select('li[id^="ref-"]'):
   a=li.select_one('a[href]')
   if not a:continue
   u=a["href"].strip()
   if urllib.parse.urlparse(u).scheme in ("http","https"):
    sources[u].add(p["id"]);counts[p["id"]]+=1
  # Detect missing citation IDs from the markup, never treat visible link number as proof
  refs={li.get("id") for li in soup.select('li[id^="ref-"]')}
  intext={a.get('href','').removeprefix('#') for a in soup.select('sup a[href^="#ref-"]')}
  bad=intext-refs
  if bad:print("BROKEN_CITATION_ANCHOR",p["id"],sorted(bad),flush=True)
 print("URL_SCAN_START",len(posts),"posts",len(sources),"unique URLS",flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
  results=list(ex.map(check_one,((u,sorted(ids)) for u,ids in sources.items())))
 summary=collections.Counter(x["status"] for x in results)
 report={"checked_utc":datetime.now(timezone.utc).isoformat(),"published_posts":len(posts),
         "citation_urls":sum(counts.values()),"unique_urls":len(sources),
         "status_counts":dict(summary),"results":sorted(results,key=lambda x:(x["status"],x["url"]))}
 (OUT/"source_status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 with (OUT/"source_status.csv").open("w",newline="",encoding="utf-8-sig") as f:
  writer=csv.writer(f)
  writer.writerow(["status","http","post_ids","url","final_url","error"])
  for z in sorted(results,key=lambda x:(x["status"],x["url"])):
   writer.writerow([z["status"],z.get("http"),",".join(map(str,z["post_ids"])),z["url"],z.get("final_url",""),z.get("error","")])
 print("URL_SCAN_SUMMARY="+json.dumps({"published_posts":len(posts),"unique_urls":len(sources),"status":dict(summary)},ensure_ascii=False),flush=True)
 for z in results:
  if z["status"]=="HTTP_NOT_FOUND":
   print("CONFIRMED_NOT_FOUND="+json.dumps({k:z[k] for k in ("url","post_ids","http")},ensure_ascii=False),flush=True)

if __name__=="__main__": main()
