"""Read-only preflight to identify exact floating share bar class and high-risk references.

No WordPress writes. Avoids credential/PII output; prints only page selectors,
article reference list entries and CSS widget IDs relevant to public design.
"""
import os,re,json
from bs4 import BeautifulSoup
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
s=requests.Session();s.headers["User-Agent"]="TaxonGuruReadOnlyPreflight/1.0"
def api(route):
 r=s.get(BASE+"/wp-json/wp/v2/"+route,auth=auth,timeout=65)
 r.raise_for_status();return r.json()
def main():
 r=s.get(BASE+"/victoria-amazonica-giant-lily/",timeout=65);r.raise_for_status()
 d=BeautifulSoup(r.text,"html.parser")
 for el in d.find_all(True):
  classes=" ".join(el.get("class",[]))
  identifier=el.get("id","")
  if any(w in (classes+" "+identifier).lower() for w in ("a2a","sharethis","heateor","social-share","sticky-share","addtoany","floating-share","share-bar")):
   print("MOBILE_DOM_SHARE="+json.dumps({"tag":el.name,"classes":classes[:210],"id":identifier[:120],"html":str(el)[:260]},ensure_ascii=False),flush=True)
 widgets=api("widgets?context=edit&per_page=100")
 for w in widgets:
  if w.get("id_base")=="custom_html":
   instance=w.get("instance") or {}
   raw=instance.get("raw") if isinstance(instance,dict) else None
   raw_content=(raw or {}).get("content","") if isinstance(raw,dict) else ""
   rendered=w.get("rendered") or ""
   print("WIDGET_DEBUG="+json.dumps({"id":w.get("id"),"sidebar":w.get("sidebar"),"raw_content_length":len(raw_content),"rendered_length":len(rendered),"has_marker_in_raw":"taxonguru-mobile-reader-ux-20261107" in raw_content,"has_marker_in_rendered":"taxonguru-mobile-reader-ux-20261107" in rendered,"content_head":raw_content[:220]},ensure_ascii=False),flush=True)
 footer=api("sidebars/footer-1?context=edit")
 print("FOOTER_DEBUG="+json.dumps({"widget_count":len(footer.get("widgets",[])),"widget_ids":footer.get("widgets",[])},ensure_ascii=False),flush=True)
 print("PUBLIC_CSS_DEBUG="+json.dumps({"home_contains_mobile_css":"taxonguru-mobile-reader-ux-20261107" in s.get(BASE+"/",timeout=60).text},ensure_ascii=False),flush=True)

 for w in widgets:
  data=w.get("instance",{})
  content=((data.get("raw") or {}).get("content") or "") if isinstance(data,dict) else ""
  if any(x in content for x in ("taxonguru-date-display-fix","@media","a2a_","sharethis","font-size")):
   print("MOBILE_CSS_WIDGET="+json.dumps({"id":w.get("id"),"id_base":w.get("id_base"),"sidebar":w.get("sidebar"),"content_excerpt":content[:1300]},ensure_ascii=False),flush=True)
 for pid in [227,449,154,739,123,807,146,763]:
  post=api("posts/"+str(pid)+"?context=edit")
  src=post["content"].get("raw") or post["content"].get("rendered") or ""
  soup=BeautifulSoup(src,"html.parser")
  out=[]
  for li in soup.select('li[id^="ref-"]'):
   a=li.select_one("a[href]")
   if not a:continue
   url=a.get("href","")
   if any(x in url.lower() for x in ("wikipedia.org","researchgate.net","blogspot.","medium.com","wikia.")):
    out.append({"ref":li.get("id"),"url":url,"label":a.get_text(" ",strip=True)[:145],"li_text":li.get_text(" ",strip=True)[:240],"li_html":str(li)[:670]})
  print("WEAK_REFERENCE_POST="+json.dumps({"id":pid,"status":post["status"],"title":post["title"].get("raw") or "", "weak_refs":out},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
