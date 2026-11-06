"""Non-destructive UX cleanup: WordPress date CSS, accurate excerpts, author label.

Dry-run is default. Production runs require SITE_UX_APPLY=true.
Backup current widget/user/post metadata as Actions artifact before writing.
Do not touch content, title, slug, dates, SEO settings, or image metadata.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

SITE=os.environ.get("WP_SITE_URL","https://taxonguru.com").rstrip("/")
AUTH=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
APPLY=os.environ.get("SITE_UX_APPLY","false").lower()=="true"
OUT=Path(os.environ.get("AUDIT_OUTPUT_DIR","audit_output"))/"ux_improvement"
OUT.mkdir(parents=True,exist_ok=True)
session=requests.Session()
session.auth=AUTH
session.headers["User-Agent"]="TaxonGuruQualityUX/1.0"

TARGET={
 221:{
  "title":"면적 기준 세계 최대 균류, 어두운뽕나무버섯(Armillaria ostoyae)의 생태",
  "excerpt":"미국 오리건주 말허어 국유림에는 약 9.65km²의 땅속에 걸쳐 자라는 어두운뽕나무버섯(Armillaria ostoyae) 균류 개체가 있습니다. 이는 알려진 세계 최대 규모의 균류 기록이며, 지구상에서 가장 큰 단일 생명체 기록과는 다릅니다. 균사체의 성장과 숲 생태계에 미치는 영향을 과학적 자료와 함께 살펴봅니다."
 },
 434:{
  "title":"Oregon's Humongous Fungus: The World's Largest Known Fungus",
  "excerpt":"An Armillaria ostoyae fungal individual in Oregon's Malheur National Forest spans roughly 2,385 acres (about 9.65 km²). It is the largest known fungus by area, not the largest single organism on Earth. Explore how its underground mycelium grows and interacts with the forest ecosystem."
 }
}
STYLE='<style id="taxonguru-date-display-fix">.posted-on time.updated{display:none!important}</style>'
PROFILE_NAME="TaxonGuru 운영자"

def req(method,route,**kwargs):
    r=session.request(method,f"{SITE}/wp-json/wp/v2/{route}",timeout=70,**kwargs)
    if r.status_code>=400:
        raise RuntimeError(f"{method} {route}: HTTP {r.status_code}, detail={r.text[:280]}")
    return r.json()

def read_context():
    posts={}
    for pid,details in TARGET.items():
        post=req("GET",f"posts/{pid}",params={"context":"edit"})
        title=post["title"].get("raw") or post["title"].get("rendered")
        if title!=details["title"] or post.get("status")!="publish":
            raise RuntimeError(f"{pid}: title or published status changed since inspection")
        posts[pid]={
            "title":title,
            "excerpt":post["excerpt"].get("raw") or post["excerpt"].get("rendered") or "",
            "modified":post.get("modified"),
            "status":post.get("status"),
        }
    author=req("GET","users/me",params={"context":"edit"})
    sidebars=req("GET","sidebars",params={"context":"edit"})
    footer=[x for x in sidebars if x.get("id")=="footer-1" and x.get("status")=="active"]
    if not footer:raise RuntimeError("Footer-1 widget sidebar is not active; do not alter theme")
    widgets=req("GET","widgets",params={"context":"edit","per_page":100})
    matching=[x for x in widgets if "taxonguru-date-display-fix" in (x.get("rendered") or "")]
    return posts,author,widgets,matching

def main():
    posts,author,widgets,existing=read_context()
    backup={
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "site":SITE,
        "post_metadata":posts,
        "public_author":{"id":author.get("id"),"name":author.get("name"),"nickname":author.get("nickname")},
        "widgets":[{"id":w.get("id"),"id_base":w.get("id_base"),"sidebar":w.get("sidebar")} for w in widgets],
        "existing_fix_widget_ids":[w.get("id") for w in existing]
    }
    (OUT/"before.json").write_text(json.dumps(backup,ensure_ascii=False,indent=2),encoding="utf-8")
    result={"apply":APPLY,"posts":{},"author":"SKIP","css_widget":"SKIP","errors":[]}
    print("BACKUP_OK",len(posts),"posts",len(widgets),"existing widgets",flush=True)
    for pid,details in TARGET.items():
        if posts[pid]["excerpt"].strip()==details["excerpt"]:
            result["posts"][str(pid)]="ALREADY_FIXED"
            continue
        if APPLY:
            req("POST",f"posts/{pid}",json={"excerpt":details["excerpt"]})
            updated=req("GET",f"posts/{pid}",params={"context":"edit"})
            final=updated["excerpt"].get("raw") or ""
            if final.strip()!=details["excerpt"]:
                raise RuntimeError(f"Excerpt verification failed for post {pid}")
            result["posts"][str(pid)]="UPDATED"
        else:result["posts"][str(pid)]="WOULD_UPDATE"

    if author.get("name")==PROFILE_NAME:
        result["author"]="ALREADY_FIXED"
    elif APPLY:
        req("POST","users/me",json={"name":PROFILE_NAME})
        final=req("GET","users/me",params={"context":"edit"})
        if final.get("name")!=PROFILE_NAME:
            raise RuntimeError("Author display name did not change")
        result["author"]="UPDATED"
    else: result["author"]="WOULD_UPDATE"

    if len(existing)>1:raise RuntimeError("Multiple existing date-style widgets found; no further changes")
    if existing:result["css_widget"]="ALREADY_FIXED"
    elif APPLY:
        response=req("POST","widgets",json={
            "id_base":"custom_html","sidebar":"footer-1",
            "instance":{"raw":{"title":"","content":STYLE}}
        })
        wid=response["id"]
        actual=req("GET",f"widgets/{wid}",params={"context":"edit"})
        if "taxonguru-date-display-fix" not in actual.get("rendered",""):
            raise RuntimeError(f"Widget {wid} created but CSS is not rendered")
        result["css_widget"]="CREATED:"+wid
    else:result["css_widget"]="WOULD_CREATE"

    home=session.get(SITE+"/",timeout=60,headers={"Cache-Control":"no-cache"})
    result["homepage_http"]=home.status_code
    result["homepage_css_marker"]=bool("taxonguru-date-display-fix" in home.text)
    result["homepage_updated_excerpt"]=TARGET[434]["excerpt"][:55] in home.text
    result["homepage_author_label"]=PROFILE_NAME in home.text
    (OUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("UX_RESULT="+json.dumps(result,ensure_ascii=False),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
