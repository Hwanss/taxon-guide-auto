"""Non-destructive AdSense preapplication technical and content-similarity QA.

Reads 54 published WordPress articles and their public pages, finds broken
internal editorial links and clear HTML issues; does not simulate Google's
nonpublic approval model or approve content. Saves machine-readable evidence.
"""
import os,re,json,html,collections,concurrent.futures,urllib.parse
from pathlib import Path
from datetime import datetime,timezone
import requests
from bs4 import BeautifulSoup

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
HOST=urllib.parse.urlsplit(BASE).hostname
OUT=Path("audit_output/final54_quality");OUT.mkdir(parents=True,exist_ok=True)
HEADERS={"User-Agent":"TaxonGuruEditorialReadiness/2026.11","Cache-Control":"no-cache"}
def get(url,timeout=60):
 r=requests.get(url,timeout=timeout,headers=HEADERS,allow_redirects=True)
 return r
def retrieve_posts():
 url=f"{BASE}/wp-json/wp/v2/posts?per_page=100&status=publish"
 r=get(url);r.raise_for_status()
 return r.json()
def normalized_text(body):
 soup=BeautifulSoup(body,"html.parser")
 for x in soup(["script","style","noscript"]):x.decompose()
 return re.sub(r"\s+"," ",soup.get_text(" ",strip=True)).strip()
def shingles(text,size=6):
 words=re.findall(r"[\w가-힣]+",text.lower())
 return {" ".join(words[i:i+size]) for i in range(max(0,len(words)-size+1))}
def locate(u):
 try:
  p=urllib.parse.urlsplit(urllib.parse.urljoin(BASE,u))
  if p.scheme not in ("http","https") or p.hostname!=HOST:return None
  if p.path.startswith(("/wp-content/","/wp-includes/","/wp-json/")):return None
  if not p.path or p.path=="/":return None
  if re.search(r"\.(?:jpe?g|png|webp|gif|svg|zip|mp4|css|js|xml|json)$",p.path,re.I):return None
  return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,"",""))
 except Exception:return None
def inspect_one(post):
 pid=post["id"]
 title=html.unescape(BeautifulSoup(post["title"]["rendered"],"html.parser").get_text())
 raw=post["content"]["rendered"]
 text=normalized_text(raw)
 soup=BeautifulSoup(raw,"html.parser")
 refs=soup.select('li[id^="ref-"]')
 links=[a.get("href","") for a in soup.select("a[href]")]
 external=[u for u in links if (urllib.parse.urlsplit(urllib.parse.urljoin(BASE,u)).hostname not in (HOST,None))]
 internal=[x for x in (locate(u) for u in links) if x]
 imgs=soup.find_all("img")
 source_links=[]
 for li in refs:
  source_links += [a.get("href","") for a in li.select("a[href]")]
 sns=[u for u in source_links if re.search(r"(?:reddit\.com|facebook\.com|instagram\.com|tiktok\.com|pinterest\.com)",u,re.I)]
 return {
  "id":pid,"title":title,"url":post["link"],
  "locale":"en" if "/en/" in post["link"] else "ko",
  "characters":len(text),"image_count":len(imgs),
  "images_without_alt":sum(not im.get("alt") for im in imgs),
  "citation_anchors":len(refs),"external_links":len(external),
  "sns_reference_urls":sns,"internal_links":sorted(set(internal)),
  "_text":text
 }
def check_public(rec):
 url=rec["url"]
 try:
  r=get(url,timeout=55)
  if r.status_code!=200:
   return {"id":rec["id"],"http":r.status_code,"ok":False}
  doc=BeautifulSoup(r.text,"html.parser")
  meta_robots=doc.select_one('meta[name="robots"]')
  noindex=bool(meta_robots and "noindex" in str(meta_robots.get("content","")).lower())
  canon=doc.select_one('link[rel="canonical"]')
  canonical=canon.get("href","") if canon else ""
  canonical_ok=(canonical.rstrip("/") == url.rstrip("/")) if canonical else None
  viewport=bool(doc.select_one('meta[name="viewport"]'))
  title=bool(doc.title and doc.title.get_text(" ",strip=True))
  return {"id":rec["id"],"http":200,"ok":not noindex and title,
       "noindex":noindex,"canonical":canonical,"canonical_matches":canonical_ok,"viewport":viewport}
 except requests.RequestException as err:
  return {"id":rec["id"],"http":0,"ok":False,"error":type(err).__name__}
def check_internal(url):
 try:
  r=get(url,timeout=40)
  return {"url":url,"status":r.status_code,"ok":r.status_code==200}
 except requests.RequestException as err:
  return {"url":url,"status":0,"ok":False,"error":type(err).__name__}
def public_resource(route):
 try:
  r=get(BASE+route,timeout=35)
  return {"url":route,"http":r.status_code,"body":r.text[:60000]}
 except requests.RequestException as e:
  return {"url":route,"http":0,"error":type(e).__name__,"body":""}
def main():
 posts=retrieve_posts()
 print("FINAL54_FETCHED",len(posts),flush=True)
 if len(posts)!=54:raise RuntimeError("expected exactly 54 published posts, got "+str(len(posts)))
 items=[inspect_one(x) for x in posts]
 pageinfo=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
  pageinfo=list(pool.map(check_public,items))
 urls=sorted({u for r in items for u in r["internal_links"]})
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
  internal=list(pool.map(check_internal,urls))
 resources=[public_resource(u) for u in ["/robots.txt","/ads.txt","/sitemap_index.xml","/wp-sitemap.xml","/reading-guide/","/privacy-policy/","/editorial-policy/","/contact-and-corrections/"]]
 robots=next(x for x in resources if x["url"]=="/robots.txt")["body"]
 ads=next(x for x in resources if x["url"]=="/ads.txt")["body"]
 no_global_disallow=not bool(re.search(r"(?im)^Disallow:\s*/\s*$",robots))
 ads_record=bool(re.search(r"(?im)^google\.com\s*,\s*pub-\d+\s*,\s*DIRECT",ads))
 duplicate_exact=[]
 repeats=collections.defaultdict(list)
 for x in items:
  repeats[re.sub(r"\s+","",x["_text"][:1200])].append(x["id"])
 duplicate_exact=[ids for ids in repeats.values() if len(ids)>1]
 pairs=[]
 for i,a in enumerate(items):
  sha=shingles(a["_text"])
  if not sha:continue
  for b in items[i+1:]:
   if a["locale"]!=b["locale"]:continue
   shb=shingles(b["_text"])
   if not shb:continue
   sim=len(sha & shb)/len(sha | shb)
   if sim>0.38:pairs.append({"ids":[a["id"],b["id"]],"similarity":round(sim,3)})
 anomalies=[]
 for rec in items:
  if rec["citation_anchors"]<1:anomalies.append({"id":rec["id"],"issue":"no numbered references"})
  if rec["image_count"]<1:anomalies.append({"id":rec["id"],"issue":"no article image"})
  if rec["characters"]<900:anomalies.append({"id":rec["id"],"issue":"short rendered text"})
  if rec["images_without_alt"]:anomalies.append({"id":rec["id"],"issue":"missing image alt","count":rec["images_without_alt"]})
 blocked=[x for x in pageinfo if not x["ok"]]
 canonical=[x for x in pageinfo if x.get("canonical_matches") is False]
 broken=[x for x in internal if not x["ok"]]
 summary={
  "generated_utc":datetime.now(timezone.utc).isoformat(),
  "published_count":len(posts),"ko":sum(x["locale"]=="ko" for x in items),
  "en":sum(x["locale"]=="en" for x in items),
  "public_pages_ok":sum(x["ok"] for x in pageinfo),
  "public_pages_bad":blocked,"canonical_mismatches":canonical,
  "visible_reference_items":sum(x["citation_anchors"] for x in items),
  "sns_citation_count":sum(len(x["sns_reference_urls"]) for x in items),
  "total_post_images":sum(x["image_count"] for x in items),
  "metadata_warnings":anomalies,
  "internal_unique_checked":len(internal),"broken_internal_links":broken,
  "site_resources":[{"path":x["url"],"http":x["http"]} for x in resources],
  "ads_txt_valid_publisher_record":ads_record,
  "robots_allows_crawl":no_global_disallow,
  "duplicate_full_intros":duplicate_exact,
  "high_shingle_overlap_same_locale":pairs,
  "limitations":"Automated SEO and duplicate-string signals cannot establish editorial originality or replicate Google's AdSense approval; no live mobile layout screenshots tested",
 }
 (OUT/"final54_report.json").write_text(json.dumps({
   "summary":summary,
   "articles":[{k:v for k,v in x.items() if k not in ("_text","internal_links")} for x in items],
   "public_page_checks":pageinfo,
   "internal_link_checks":internal,
 },ensure_ascii=False,indent=2),encoding="utf8")
 import pprint
 print("FINAL54_QA_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
 if blocked or broken or not ads_record or not no_global_disallow:
  print("FINAL54_QA_REVIEW_NEEDED",len(blocked),"page blockers",len(broken),"broken internal",flush=True)
 # Report issues but do not auto-approve any status, never write WordPress.
if __name__=="__main__":main()
