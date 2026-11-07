"""Live 390px/1366px Chromium + six-post public bibliography verification.

READ ONLY. Confirms mobile STSSM fixed overlay is hidden while in-article
sharing remains present. Checks the exact publicly rendered scholarly URLs.
"""
import json,os,datetime,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/mobile_verified");OUT.mkdir(parents=True,exist_ok=True)
REF={
 227:["https://doi.org/10.3389/fcosc.2024.1349553","https://doi.org/10.1111/j.1095-8339.2012.01307.x"],
 449:["https://doi.org/10.3389/fcosc.2024.1349553","https://doi.org/10.1111/j.1095-8339.2012.01307.x"],
 154:["https://pmc.ncbi.nlm.nih.gov/articles/PMC8582207/","https://doi.org/10.1007/s13127-024-00660-z"],
 739:["https://pmc.ncbi.nlm.nih.gov/articles/PMC8582207/","https://doi.org/10.1007/s13127-024-00660-z"],
 123:["https://doi.org/10.1080/02724634.2020.1780247","https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/"],
 807:["https://doi.org/10.1080/02724634.2020.1780247","https://news.berkeley.edu/2021/12/07/fleshing-out-the-bones-of-quetzalcoatlus-earths-largest-flier-ever/"],
}
def check_refs():
 out=[]
 for pid,urls in REF.items():
  req=urllib.request.Request(BASE+"/wp-json/wp/v2/posts/"+str(pid),headers={"User-Agent":"TaxonGuruPublicCitationCheck/1.0"})
  with urllib.request.urlopen(req,timeout=55) as response:
   obj=json.load(response)
  html=obj.get("content",{}).get("rendered","")
  matched=[u for u in urls if u in html]
  result={"id":pid,"status":obj.get("status"),"verified_links":len(matched),"expected_links":len(urls),"ok":obj.get("status")=="publish" and len(matched)==len(urls)}
  out.append(result);print("PUBLIC_BIBLIO_ITEM="+json.dumps(result,ensure_ascii=False),flush=True)
 return out
def browser_check(p):
 b=p.chromium.launch(headless=True,args=["--no-sandbox"])
 checks=[]
 for width,height in [(390,844),(1366,768)]:
  ctx=b.new_context(viewport={"width":width,"height":height},is_mobile=width<500,has_touch=width<500,device_scale_factor=1)
  pg=ctx.new_page()
  resp=pg.goto(BASE+"/victoria-amazonica-giant-lily/",wait_until="domcontentloaded",timeout=65000)
  pg.wait_for_timeout(3000)
  x=pg.evaluate("""() => {
   const el=document.querySelector('ul.stssm-social-icons.stssm-sticky-social-icons');
   const inline=document.querySelectorAll('ul.stssm-social-icons.stssm-content-social-icons');
   const p=document.querySelector('.entry-content p');
   return {width:innerWidth,media_applies:matchMedia('(max-width: 767px)').matches,
    sticky_found:!!el,sticky_display:el?getComputedStyle(el).display:null,
    inline_share_count:inline.length,inline_share_visible:[...inline].some(n=>getComputedStyle(n).display!=='none'),
    paragraph_font_size:p?getComputedStyle(p).fontSize:null,
    css_widget_present:!!document.getElementById('taxonguru-mobile-reader-ux-20261107'),
    doc_width:document.documentElement.scrollWidth};
  }""")
  x.update({"http":resp.status if resp else 0,"mobile_ok":not(width<500) or
    (x["sticky_found"] and x["sticky_display"]=="none" and x["inline_share_count"]>=1
     and x["css_widget_present"] and x["paragraph_font_size"]=="16px" and x["doc_width"]<=width+6)})
  checks.append(x)
  pg.screenshot(path=str(OUT/("post_mobile_after.png" if width<500 else "post_desktop_after.png")),full_page=False)
  print("MOBILE_LIVE_CHECK="+json.dumps(x,ensure_ascii=False),flush=True)
  ctx.close()
 b.close()
 return checks
def main():
 citations=check_refs()
 with sync_playwright() as p: browsers=browser_check(p)
 ok=all(a["ok"] for a in citations) and all(b["http"]==200 and b["mobile_ok"] for b in browsers)
 data={"ok":ok,"citations":citations,"browsers":browsers,"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (OUT/"verified.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
 print("MOBILE_AND_SOURCES_SUMMARY="+json.dumps({"ok":ok,"citation_posts_verified":sum(x["ok"] for x in citations),"public_refs":sum(x["verified_links"] for x in citations),"mobile_no_overlay":browsers[0].get("sticky_display")=="none","inline_share_retained":browsers[0].get("inline_share_count",0)>=1,"mobile_font":browsers[0].get("paragraph_font_size")},ensure_ascii=False),flush=True)
 if not ok:raise SystemExit(1)
if __name__=="__main__":main()
