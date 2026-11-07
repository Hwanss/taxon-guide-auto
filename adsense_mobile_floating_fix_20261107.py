"""Mobile readability improvement: remove ONLY overlapping sticky social icons.

Site currently uses STSSM: <ul class="stssm-social-icons stssm-sticky-social-icons">
as confirmed on live 390px Chromium. Inline non-sticky share icons remain.
No plugin deletion or article edits. Preview first and back up all widgets.
"""
from __future__ import annotations
import json,os
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("MOBILE_FIX_APPLY","false").lower()=="true"
OUT=Path("audit_output/mobile_floating_fix");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
STYLE='''<style id="taxonguru-mobile-reader-ux-20261107">
@media screen and (max-width: 767px) {
  /* Only the fixed overlay; in-article STSSM sharing remains enabled */
  ul.stssm-social-icons.stssm-sticky-social-icons { display: none !important; }
  /* Improve continuous reading without altering headings or captions */
  .entry-content p, .entry-content li { font-size: 16px; line-height: 1.75; }
}
</style>'''
def api(method,path,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=75,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {path} HTTP {r.status_code}: {r.text[:220]}")
 return r.json()
def widget_source(w):
 raw=(w.get("instance") or {}).get("raw") or {}
 return (raw.get("content") or "")+" "+(w.get("rendered") or "")
def main():
 widgets=api("GET","widgets",params={"context":"edit","per_page":100})
 sidebars=api("GET","sidebars",params={"context":"edit"})
 footer=next((x for x in sidebars if x.get("id")=="footer-1" and x.get("status")=="active"),None)
 if footer is None:raise RuntimeError("Expected footer-1 active; refuse to touch site settings")
 matched=[w for w in widgets if "taxonguru-mobile-reader-ux-20261107" in widget_source(w)]
 if len(matched)>1:raise RuntimeError("Duplicate mobile repair widgets; refuse to add")
 original={"widgets":widgets,"sidebars":sidebars,"new_css":STYLE}
 (OUT/"original_widget_metadata.json").write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding="utf8")
 if matched:
  current=matched[0]
  wid=current["id"]
  if "stssm-sticky-social-icons" not in widget_source(current):
   raise RuntimeError("Existing mobile CSS not matching expected selector; stop")
  if current.get("sidebar")=="footer-1":
   result={"status":"ALREADY_APPLIED","widget_id":wid}
  elif APPLY:
   # Creation produced inactive WP widget; assign existing, never create duplicate.
   now=api("GET","sidebars/footer-1",params={"context":"edit"})
   original_ids=list(now.get("widgets",[]))
   if wid not in original_ids:
    api("POST","sidebars/footer-1",json={"widgets":original_ids+[wid]})
   revised=api("GET","widgets/"+wid,params={"context":"edit"})
   if revised.get("sidebar")!="footer-1":
    raise RuntimeError("Reassignment did not persist; refuse duplicate widget")
   result={"status":"ASSIGNED_EXISTING_WIDGET","widget_id":wid}
  else:
   result={"status":"WOULD_ASSIGN_EXISTING_WIDGET","widget_id":wid}
 elif APPLY:
  w=api("POST","widgets",json={"id_base":"custom_html","sidebar":"footer-1","instance":{"raw":{"title":"","content":STYLE}}})
  check=api("GET","widgets/"+w["id"],params={"context":"edit"})
  if check.get("sidebar")!="footer-1" or "taxonguru-mobile-reader-ux-20261107" not in widget_source(check):
   raise RuntimeError("Created CSS but it did not persist in the active footer")
  result={"status":"UPDATED","widget_id":w["id"]}
 else: result={"status":"PREVIEW","widget_id":None}
 home=S.get(BASE+"/",timeout=55,headers={"Cache-Control":"no-cache"})
 result.update({"apply":APPLY,"public_home_status":home.status_code,
   "css_visible_in_home":'taxonguru-mobile-reader-ux-20261107' in home.text,
   "mobile_fixed_selector":"ul.stssm-social-icons.stssm-sticky-social-icons",
   "in_article_share_selector_untouched":"ul.stssm-social-icons.stssm-content-social-icons"})
 (OUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
 print("MOBILE_FIX_RESULT="+json.dumps(result,ensure_ascii=False),flush=True)
 if APPLY and not result["css_visible_in_home"]:raise RuntimeError("CSS not visible on public homepage after widget modification")
if __name__=="__main__":main()
