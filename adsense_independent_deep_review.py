"""Independent AdSense quality risk review of the live TaxonGuru public site.

Different from past 'hard blocker=0' scripts: specifically audits provenance,
repeated boilerplate, source quality, mobile-language structure, weak homepage
navigation, links to draft/404 pages, and image licensing credits.
READ-ONLY: no changes to WordPress, no editorial signoff.
"""
from __future__ import annotations
import collections,concurrent.futures,datetime,html,json,os,re,statistics,urllib.parse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/independent_review");OUT.mkdir(parents=True,exist_ok=True)
HEAD={"User-Agent":"Mozilla/5.0 (compatible; TaxonGuruIndependentQualityReview/1.0)","Cache-Control":"no-cache"}
HOST=urllib.parse.urlsplit(BASE).netloc
sess=requests.Session();sess.headers.update(HEAD)
def get(path,params=None,timeout=50):
 return sess.get(path if path.startswith("http") else BASE+path,params=params,timeout=timeout,allow_redirects=True)
def norm(x):
 if not x:return ""
 soup=BeautifulSoup(x,"html.parser")
 for s in soup(["style","script","noscript"]):s.decompose()
 return re.sub(r"\s+"," ",html.unescape(soup.get_text(" ",strip=True))).strip()
def text_p(x):
 return re.sub(r"\s+"," ",norm(x))
def host(u):
 try:return urllib.parse.urlsplit(urllib.parse.urljoin(BASE,u)).hostname or ""
 except:return ""
def fetch_articles():
 r=get("/wp-json/wp/v2/posts",params={"per_page":100,"status":"publish"})
 r.raise_for_status()
 return r.json()
def fetch_page(url):
 try:
  x=get(url,timeout=38)
  return {"url":url,"status":x.status_code,"final":x.url,"cache":{k:v for k,v in x.headers.items() if k.lower() in ("age","x-cache","cf-cache-status","cache-control")}}
 except requests.RequestException as e:
  return {"url":url,"status":0,"error":type(e).__name__}
def article_source(post):
 content=post["content"]["rendered"];soup=BeautifulSoup(content,"html.parser")
 title=norm(post["title"]["rendered"])
 refs=soup.select('[id^="ref-"]')
 links=[a.get("href") for li in refs for a in li.select("a[href]") if a.get("href")]
 domains=[host(x) for x in links]
 # Exact duplicate URLs across distinct numbered references matter to reader trust.
 ref_url_to_ids=collections.defaultdict(list)
 for li in refs:
  number=re.search(r'ref-(\d+)',li.get("id",""))
  if not number:continue
  for a in li.select("a[href]"):
   full=urllib.parse.urljoin(BASE,html.unescape(a.get("href","")))
   full=full.split("#",1)[0]
   ref_url_to_ids[full].append(int(number.group(1)))
 duplicate_ref_urls=[{"url":u,"ref_ids":sorted(set(nums))}
   for u,nums in ref_url_to_ids.items() if len(set(nums))>1]
 sections=[x.get_text(" ",strip=True) for x in soup.find_all("h2")]
 pars=[text_p(str(x)) for x in soup.find_all("p") if len(text_p(str(x)))>80]
 # Only article body refs, not theme footer or image credits
 internal=[a.get("href") for a in soup.select("a[href]") if host(a.get("href",""))==HOST and not re.search(r"/wp-(?:content|json|includes)/",a.get("href",""))]
 weak=[d for d in domains if any(y in d for y in ("wikipedia.org","researchgate.net","youtube.com","reddit.com","quora.com","indiatimes.com","pinterest.com","facebook.com","encyclopedia.pub","plantnimals.com","medium.com","blogspot.","wikihow.com"))]
 # References may be cited as a link OR as literal [1, 3, 7] in prose.
 # The old link-only test overstated the count of 'uncited' references.
 cited=set(re.findall(r'href=["\x27]#ref-(\d+)["\x27]',content))
 plain_body=BeautifulSoup(content,"html.parser")
 for node in plain_body.select('[id^="ref-"]'):node.decompose()
 for cluster in re.findall(r'\[\s*\d+(?:\s*,\s*\d+)*\s*\]',plain_body.get_text(" ",strip=True)):
  cited.update(re.findall(r'\d+',cluster))
 existing_refs=set(re.findall(r'id=["\x27]ref-(\d+)["\x27]',content))
 uncited=[n for n in existing_refs if n not in cited]
 dangling=sorted(n for n in cited if n not in existing_refs)
 images=soup.find_all("img")
 lic=[x.get_text(" ",strip=True) for x in soup.find_all(string=re.compile(r"CC BY|Wikimedia Commons|AI-generated",re.I))]
 return {
  "id":post["id"],"title":title,"url":post["link"],
  "lang":"en" if "/en/" in post["link"] else "ko",
  "ref_count":len(refs),"source_domains":domains,"weak_domains":weak,
  "reference_links":links,"uncited_ref_ids":sorted(uncited),
  "duplicate_reference_urls":duplicate_ref_urls,"dangling_citation_ref_ids":dangling,
  "internal_body_links":internal,"img_count":len(images),
  "img_alts_missing":sum(not im.get("alt") for im in images),
  "credit_text_count":len(lic),"text_length":len(norm(content)),
  "paragraphs":pars,"section_titles":sections,
  "disclosure_in_body":("AI-generated" in content or "AI 활용" in content or "AI use" in content),
 }
def home_inspect():
 x=get("/?fresh=quality-check-nov6")
 soup=BeautifulSoup(x.text,"html.parser")
 all_a=[{"title":a.get_text(" ",strip=True)[:80],"url":urllib.parse.urljoin(BASE,a["href"])} for a in soup.select("a[href]") if host(a.get("href",""))==HOST]
 # known draft article urls referenced in last cached homepage
 draft_urls=[BASE+"/axolotl-neotenic-amphibian/",BASE+"/en/axolotl-facts-neoteny-regeneration-conservation/",
 BASE+"/hydnellum-peckii-bleeding-tooth-fungus/",BASE+"/en/hydnellum-peckii-bleeding-tooth-mushroom/"]
 found=[a for a in all_a if any("axolotl" in a["url"] or "hydnellum" in a["url"] for _ in [1])]
 home_post_links=[a for a in all_a if "axolotl" in a["url"] or "hydnellum" in a["url"]]
 return {"status":x.status_code,"lang":soup.html.get("lang") if soup.html else None,
   "title":soup.title.get_text(" ",strip=True) if soup.title else None,
   "found_links_to_held_topics":home_post_links,
   "homepage_internal_anchors":len(all_a),"recent_comments_visible":"Recent Comments" in soup.get_text(" ",strip=True),
   "featured_urls":list(dict.fromkeys(a["url"] for a in all_a))[:30],
   "body_excerpt":norm(str(soup))[:850],
   "meta_description":bool(soup.select_one('meta[name="description"]'))}
def sample_page(url):
 r=get(url,timeout=50)
 soup=BeautifulSoup(r.text,"html.parser")
 meta=soup.select_one("meta[name=description]")
 og=soup.select_one("meta[property='og:description']")
 canonical=soup.select_one('link[rel="canonical"]')
 hrels=[{"lang":a.get("hreflang"),"url":a.get("href")} for a in soup.select("link[hreflang]")]
 a=soup.select_one("article")
 return {"status":r.status_code,"html_lang":soup.html.get("lang") if soup.html else None,
   "description":meta.get("content")[:160] if meta and meta.get("content") else None,
   "og_description":bool(og),
   "canonical":canonical.get("href") if canonical else None,
   "hreflangs":hrels[:8],
   "h1_count":len(soup.select("h1")),
   "h2_count":len(soup.select("h2")),
   "featured_image_credit":len(soup.find_all(string=re.compile("AI-generated featured",re.I))),
   "byline":norm(str(soup.select_one(".author")))[:100] if soup.select_one(".author") else None,
   "published_date_markers":len(soup.select(".posted-on time, .entry-date, .updated")),
   "html_bytes":len(r.content),
  }
def nav_sources(posts):
 counts=collections.Counter(d for p in posts for d in p["source_domains"])
 weakcounts=collections.Counter(d for p in posts for d in p["weak_domains"])
 return counts,weakcounts
def main():
 posts=fetch_articles()
 if len(posts)!=54:raise RuntimeError(f"Unexpected published {len(posts)}, stop to avoid false review")
 data=[article_source(p) for p in posts]
 home=home_inspect()
 sampled=[{"url":p["url"], **sample_page(p["url"])} for p in [data[0],data[27]]]
 links=home["found_links_to_held_topics"]
 # Verify public access for links advertised on the home page + four held URLs
 checked=list({u:None for u in [a["url"] for a in links]+[
 BASE+"/axolotl-neotenic-amphibian/",
 BASE+"/en/axolotl-facts-neoteny-regeneration-conservation/",
 BASE+"/hydnellum-peckii-bleeding-tooth-fungus/"]}.keys())
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  checked=list(pool.map(fetch_page,checked))
 counts,weak=nav_sources(data)
 repeated=collections.defaultdict(list)
 for p in data:
  for para in p["paragraphs"]:
   if len(para)<100:continue
   q=re.sub(r"\s+"," ",para.strip().lower())
   repeated[q].append(p["id"])
 repeats=[{"count":len(set(v)),"ids":sorted(set(v)),"text_sample":k[:350]} for k,v in repeated.items() if len(set(v))>=3]
 repeats=sorted(repeats,key=lambda x:-x["count"])[:18]
 patterns=collections.Counter((len(p["paragraphs"]),len(p["section_titles"]),p["img_count"],p["ref_count"]) for p in data)
 source_dist=collections.Counter(p["ref_count"] for p in data)
 weak_by_post=sorted([{"id":p["id"],"title":p["title"],"domains":p["weak_domains"],"ref_count":p["ref_count"],"chars":p["text_length"]} for p in data if p["weak_domains"]],key=lambda x:-len(x["domains"]))
 no_credits=[{"id":p["id"],"title":p["title"]} for p in data if p["img_count"] and not p["credit_text_count"]]
 report={
  "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "posts":len(data),"ko":sum(p["lang"]=="ko" for p in data),
  "source_ref_total":sum(p["ref_count"] for p in data),
  "source_domains_ranked":counts.most_common(35),
  "weak_domains_ranked":weak.most_common(25),
  "posts_with_weak_reference_sources":len(weak_by_post),
  "examples_weak_posts":weak_by_post[:25],
  "weak_sources_total":sum(len(p["weak_domains"]) for p in data),
  "uncited_references":sum(len(p["uncited_ref_ids"]) for p in data),
  "duplicate_reference_post_count":sum(bool(p["duplicate_reference_urls"]) for p in data),
  "duplicate_reference_extra_slots":sum(sum(len(d["ref_ids"])-1 for d in p["duplicate_reference_urls"]) for p in data),
  "duplicate_reference_examples":[{"id":p["id"],"url":p["url"],"duplicates":p["duplicate_reference_urls"]} for p in data if p["duplicate_reference_urls"]][:20],
  "dangling_citation_refs":[{"id":p["id"],"ids":p["dangling_citation_ref_ids"]} for p in data if p["dangling_citation_ref_ids"]],
  "ref_count_distribution":source_dist.most_common(),
  "p_structure_common":patterns.most_common(15),
  "repeated_paragraphs":repeats,
  "intro_length_median":statistics.median(len(p["paragraphs"][0]) if p["paragraphs"] else 0 for p in data),
  "images_without_credit_text":no_credits[:20],
  "home":home,
  "held_post_public_checks":checked,
  "page_metadata_samples":sampled,
  "disclosed_AI_in_article_count":sum(p["disclosure_in_body"] for p in data),
  "all_articles_summary":[{"id":p["id"],"title":p["title"],"chars":p["text_length"],"source_domains":p["source_domains"],
    "internal_body_links":len(p["internal_body_links"]),"ref_count":p["ref_count"],"img_count":p["img_count"],"alt_missing":p["img_alts_missing"],
    "duplicate_reference_urls":p["duplicate_reference_urls"],"uncited_ref_ids":p["uncited_ref_ids"],"dangling_citation_ref_ids":p["dangling_citation_ref_ids"]} for p in data],
  "limitations":"Source host names are risk signals, not verified accuracy; paragraphs may differ despite templated concepts; individual human review of primary studies and paid proprietary AdSense algorithm remains unavailable."
 }
 (OUT/"deep_review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 summary={k:v for k,v in report.items() if k not in ("all_articles_summary","page_metadata_samples","home","held_post_public_checks")}
 print("DEEP_REVIEW_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
 print("DEEP_REVIEW_HOMEPAGE="+json.dumps(home,ensure_ascii=False),flush=True)
 print("DEEP_REVIEW_HELD_CHECKS="+json.dumps(checked,ensure_ascii=False),flush=True)
 print("DEEP_REVIEW_PAGE_META="+json.dumps(sampled,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
