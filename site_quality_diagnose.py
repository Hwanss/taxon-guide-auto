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
