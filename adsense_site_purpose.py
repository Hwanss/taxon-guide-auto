"""Safe one-time site purpose tagline update. Does not modify site URL or search visibility."""
import os,json,requests
from pathlib import Path
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("SITE_PURPOSE_APPLY","false").lower()=="true"
TAGLINE="생물의 진화·생태·생존 전략을 과학적 근거와 함께 읽는 가이드 | Evidence-based biology"
out=Path("audit_output/site_purpose");out.mkdir(parents=True,exist_ok=True)
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
def settings(method,**kw):
 r=s.request(method,BASE+"/wp-json/wp/v2/settings",timeout=65,**kw);r.raise_for_status();return r.json()
before=settings("GET",params={"context":"edit"})
old=before.get("description") or ""
if old.strip() and old.strip()!=TAGLINE:
 raise RuntimeError("Existing non-empty site tagline should not be overwritten")
(out/"before.json").write_text(json.dumps({"title":before.get("title"),"description":old,"url":before.get("url")},ensure_ascii=False,indent=2),encoding="utf8")
if APPLY and old.strip()!=TAGLINE:
 settings("POST",json={"description":TAGLINE})
after=settings("GET",params={"context":"edit"})
if APPLY and after.get("description")!=TAGLINE:raise RuntimeError("Tagline update did not persist")
homepage=s.get(BASE+"/",timeout=55,headers={"Cache-Control":"no-cache"})
result={"apply":APPLY,"old":old,"new":TAGLINE,"updated":APPLY and old!=TAGLINE,"settings_verified":after.get("description")==TAGLINE,"homepage_http":homepage.status_code,"homepage_contains_tagline":"Evidence-based biology" in homepage.text,"site_url_unchanged":before.get("url")==after.get("url")}
(out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
print("SITE_PURPOSE_RESULT="+json.dumps(result,ensure_ascii=False),flush=True)
