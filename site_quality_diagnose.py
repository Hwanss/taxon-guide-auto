"""Read-only diagnosis of WordPress theme date markup and outdated post excerpts."""
import requests,os,re,json,html
from pathlib import Path
from bs4 import BeautifulSoup
base=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
s.headers["User-Agent"]="TaxonGuruThemeUXDiagnosis/1.0"
def get(route,**kw):
 r=s.get(base+route,timeout=50,**kw)
 print("FETCH",route,"HTTP",r.status_code,"length",len(r.content),flush=True)
 return r
r=get("/")
txt=r.text
for needle in ["entry-meta","posted-on","updated","time","11월 5","11월 6"]:
 idx=txt.find(needle)
 if idx>=0:print("HTML_NEAR",needle,repr(txt[max(0,idx-220):idx+620]),flush=True)
soup=BeautifulSoup(txt,"html.parser")
for meta in soup.select(".entry-meta, .posted-on, .post-date, .entry-date, .updated"):
 val=meta.get_text(" ",strip=True)
 if "2026" in val:
  print("DATE_ELEMENT",meta.name,meta.get("class"),repr(str(meta)[:1450]),flush=True)
  if len([x for x in soup.select(".entry-meta")])>4:break
for pid in (221,434,141,775):
 r=get("/wp-json/wp/v2/posts/"+str(pid),params={"context":"edit"})
 if r.status_code!=200:continue
 p=r.json()
 title=p["title"].get("raw") or p["title"]["rendered"]
 excerpt=p["excerpt"].get("raw") or p["excerpt"].get("rendered")
 content=p["content"].get("raw") or p["content"].get("rendered") or ""
 print("ARTICLE",pid,"TITLE",title,"EXCERPT",excerpt[:900],"MODIFIED",p.get("modified"),flush=True)
 for pat in ("largest living organism","largest known living organism","지상 최대의","지구상에서 가장 큰","9.65"):
  x=re.search(re.escape(pat),content,re.I)
  if x:print("ARTICLE_CLAIM",pid,pat,repr(html.unescape(re.sub("<[^>]*>"," ",content[max(0,x.start()-170):x.end()+270]))[:650]),flush=True)
r=get("/wp-json/wp/v2/themes",params={"status":"active"})
if r.status_code==200:
 for x in r.json():print("THEME",json.dumps({k:x.get(k) for k in ("stylesheet","template","name","version","status")},ensure_ascii=False),flush=True)
r=get("/wp-json/")
if r.status_code==200:
 obj=r.json()
 print("NAMESPACES",json.dumps([x for x in obj.get("namespaces",[]) if re.search("jetpack|custom|theme|code|widget|snippet|plugin|wp/v2",x,re.I)],ensure_ascii=False),flush=True)
for endpoint in ("/wp-json/wp/v2/types/custom_css","/wp-json/wp/v2/widgets","/wp-json/wp/v2/widget-types","/wp-json/wp/v2/plugins"):
 r=get(endpoint)
 if r.status_code==200:
  data=r.json()
  if isinstance(data,dict): print("ENDPOINT_OBJECT",endpoint,list(data.keys())[:12],flush=True)
  elif isinstance(data,list):print("ENDPOINT_LIST",endpoint,len(data),[x.get("id",x.get("plugin",x.get("name"))) for x in data[:15]],flush=True)

# Preflight of safe no-theme-file WordPress UX repairs
r=get("/wp-json/wp/v2/sidebars",params={"context":"edit"})
if r.status_code==200:
 for x in r.json():
  print("SIDEBAR",json.dumps({k:x.get(k) for k in ("id","name","status","widgets","class","description")},ensure_ascii=False)[:1000],flush=True)
r=get("/wp-json/wp/v2/widgets",params={"context":"edit","per_page":100})
if r.status_code==200:
 for x in r.json():
  print("WIDGET",json.dumps({k:x.get(k) for k in ("id","id_base","sidebar","rendered","instance")},ensure_ascii=False)[:650],flush=True)
r=get("/wp-json/wp/v2/users/me",params={"context":"edit"})
if r.status_code==200:
 x=r.json()
 print("AUTHOR_PROFILE",json.dumps({k:x.get(k) for k in ("id","name","slug","nickname","display_name","url")},ensure_ascii=False),flush=True)

# Investigate custom HTML widget rendering/sanitization safely
r=get("/wp-json/wp/v2/widgets",params={"context":"edit","per_page":100})
if r.status_code==200:
 for w in r.json():
  if w.get("id_base")!="custom_html":continue
  instance=w.get("instance",{})
  print("CUSTOM_HTML_WIDGET",json.dumps({"id":w.get("id"),"sidebar":w.get("sidebar"),"rendered":w.get("rendered"),"instance":instance},ensure_ascii=False)[:1800],flush=True)
print("PUBLIC_DATE_CSS_MARKER", "taxonguru-date-display-fix" in txt,flush=True)

# Inspect authoritative generated frontend cards after WordPress REST updates
for article in soup.select("article"):
 cardtext=article.get_text(" ",strip=True)
 if ("Oregon" in cardtext and "Humongous" in cardtext) or ("어두운뽕나무버섯" in cardtext):
  print("FRONT_CARD",repr(cardtext[:1000]),flush=True)
style=soup.select_one("style#taxonguru-date-display-fix")
print("DATE_CSS_TAG",bool(style),"DATE_CSS_TEXT",repr(style.get_text() if style else ""),flush=True)
print("FRONT_AUTHOR_BRAND", "TaxonGuru 운영자" in soup.get_text(" ",strip=True),flush=True)

# Pre-application public site readiness (read only)
def probe_public(path):
 try:
  response=requests.get(base+path,headers={"User-Agent":"TaxonGuruPreAdSenseCheck/1.0","Cache-Control":"no-cache"},timeout=40)
  return response.status_code, response.text[:600000]
 except requests.RequestException as error:
  print("SITE_PROBE_ERROR",path,type(error).__name__,flush=True)
  return 0,""

settings=get("/wp-json/wp/v2/settings",params={"context":"edit"})
if settings.status_code==200:
 cfg=settings.json()
 print("READINESS_SETTINGS",json.dumps({k:cfg.get(k) for k in ("title","description","url","timezone","show_on_front","posts_per_page","blog_public")},ensure_ascii=False),flush=True)
for route in ("/robots.txt","/sitemap_index.xml","/wp-sitemap.xml","/ads.txt","/reading-guide/","/editorial-policy/","/privacy-policy/","/contact-and-corrections/"):
 status,body=probe_public(route)
 x={"path":route,"status":status,"length":len(body)}
 if route=="/robots.txt":
  x["no_global_disallow"]=not bool(re.search(r"(?im)^Disallow:\s*/\s*$",body))
 if route=="/ads.txt":
  x["google_direct"]=bool(re.search(r"(?im)^google\.com\s*,\s*pub-\d+\s*,\s*DIRECT",body))
 if route=="/reading-guide/":
  x["guide_present"]="taxonguru-reader-guide-v1" in body
 print("PUBLIC_HEALTH",json.dumps(x,ensure_ascii=False),flush=True)
homepage=BeautifulSoup(txt,"html.parser")
get_attr=lambda selector,attr: [x.get(attr) for x in homepage.select(selector)]
print("SEO_SNIPPET",json.dumps({
 "title":homepage.title.get_text(" ",strip=True) if homepage.title else None,
 "meta_description":get_attr('meta[name="description"]',"content")[:2],
 "canonical":get_attr('link[rel="canonical"]',"href")[:2],
 "robots_meta":get_attr('meta[name="robots"]',"content")[:2],
 "adsense_script_present":"pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in txt,
 "adsense_client_present":bool(re.search(r"ca-pub-\d+",txt)),
 "reading_guide_homepage":"/reading-guide/" in txt,
 "date_css_present":bool(homepage.select_one("style#taxonguru-date-display-fix")),
},ensure_ascii=False),flush=True)

# Extra risk: all internal links on the newly curated reading guide must resolve.
from concurrent.futures import ThreadPoolExecutor
guide_response=get("/reading-guide/")
guide_soup=BeautifulSoup(guide_response.text,"html.parser")
guide_main=guide_soup.find(id="taxonguru-reader-guide-v1")
if not guide_main:
 print("GUIDE_LINKS_MISSING_CONTENT",flush=True)
else:
 urls=sorted(set(a.get("href") for a in guide_main.select("a[href]") if (a.get("href") or "").startswith(base+"/")))
 def validate_guide(u):
  try:
   r=requests.get(u,timeout=22,allow_redirects=True,headers={"User-Agent":"TaxonGuruInternalLinkCheck/1.0"})
   return {"url":u,"http":r.status_code,"final_url":r.url}
  except requests.RequestException as exc:
   return {"url":u,"http":0,"error":type(exc).__name__}
 with ThreadPoolExecutor(max_workers=8) as workers:
  results=list(workers.map(validate_guide,urls))
 broken=[r for r in results if r["http"]!=200]
 print("GUIDE_LINK_HEALTH",json.dumps({"total":len(urls),"broken":len(broken),"errors":broken},ensure_ascii=False),flush=True)

# Priority 8 updated pages: anonymous reader-visible verification after editorial writes.
priority8_paths={
 27:"/welwitschia-desert-ancient/",
 854:"/en/welwitschia-mirabilis-namib-desert-two-leaf-plant/",
 32:"/coelacanth-living-fossil/",
 839:"/en/west-indian-ocean-coelacanth-biology-evolution/",
 116:"/giant-tube-worm-chemosynthesis/",
 797:"/en/giant-tubeworm-riftia-pachyptila-hydrothermal-vents/",
 201:"/archaeopteryx-dinosaur-bird-transition/",
 386:"/en/archaeopteryx-lithographica-avian-evolution-flight/",
}
priority8_public=[]
for pid,p in priority8_paths.items():
 status,body=probe_public(p)
 markers=body.count("taxonguru-priority8-source-review")
 ok=(status==200 and markers==1)
 res={"id":pid,"http":status,"research_note_present":markers==1,"ok":ok}
 priority8_public.append(res)
 print("PRIORITY8_PUBLIC_CHECK="+json.dumps(res,ensure_ascii=False),flush=True)
print("PRIORITY8_PUBLIC_SUMMARY="+json.dumps({"checked":len(priority8_public),"ok":sum(x["ok"] for x in priority8_public)},ensure_ascii=False),flush=True)

# B-priority eight changed posts, anonymous reader-facing verification
b8_pages={
26:"/venus-flytrap-carnivorous-plant/",
859:"/en/venus-flytrap-dionaea-muscipula-guide/",
154:"/echiniscus-testudo-tardigrade/",
739:"/en/echiniscus-testudo-armored-turtle-water-bear/",
146:"/limulus-polyphemus-horseshoe-crab/",
763:"/en/atlantic-horseshoe-crab-myths-blue-blood-medicine/",
150:"/tiktaalik-fishapod-evolution/",
751:"/en/tiktaalik-roseae-devonian-fishapod-evolution/",
}
b8_checks=[]
for pid,path in b8_pages.items():
 st,body=probe_public(path)
 marker="taxonguru-b8-evidence-2026"
 has_note=body.count(marker)==1
 result={"id":pid,"status":st,"evidence_panel_visible":has_note,"ok":st==200 and has_note}
 b8_checks.append(result)
 print("B8_PUBLIC_CHECK="+json.dumps(result,ensure_ascii=False),flush=True)
print("B8_PUBLIC_SUMMARY="+json.dumps({"checked":len(b8_checks),
 "ok":sum(p["ok"] for p in b8_checks),"failures":[p for p in b8_checks if not p["ok"]]},
 ensure_ascii=False),flush=True)

# C8: verify each evidence-corrected live page as a non-logged-in visitor.
c8_paths={
 24:"/corpse-flower-giant-stinker/",
 864:"/en/understanding-amorphophallus-titanum-titan-arum/",
 30:"/tyrannosaurus-rex/",
 849:"/en/how-tyrannosaurus-rex-survived-and-dominated-late-cretaceous/",
 111:"/bristlecone-pine-oldest-tree/",
 792:"/en/great-basin-bristlecone-pine-longevity-survival/",
 137:"/rafflesia-arnoldii-largest-flower/",
 787:"/en/rafflesia-arnoldii-worlds-largest-single-flower/",
}
c8_results=[]
for pid,path in c8_paths.items():
 code,page=probe_public(path)
 marker_count=page.count("taxonguru-c8-evidence-nov2026")
 row={"id":pid,"http":code,"evidence_panel":marker_count==1,"ok":code==200 and marker_count==1}
 c8_results.append(row)
 print("C8_PUBLIC_ITEM="+json.dumps(row,ensure_ascii=False),flush=True)
print("C8_PUBLIC_SUMMARY="+json.dumps({
 "count":len(c8_results),"ok":sum(x["ok"] for x in c8_results),
 "failed":[x for x in c8_results if not x["ok"]]
},ensure_ascii=False),flush=True)
