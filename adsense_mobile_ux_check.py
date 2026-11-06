"""Headless Chromium responsive and accessibility smoke check; READ-ONLY.

Creates screenshots as artifacts for real human inspection. Calculates
document overflow, table clipping, viewport, links, nav, and console errors;
metrics are not a substitute for visual expert review.
"""
from pathlib import Path
import json,os,datetime
from playwright.sync_api import sync_playwright
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/mobile_ux");OUT.mkdir(parents=True,exist_ok=True)
PAGES={
 "home":"/",
 "ko_waterlily":"/victoria-amazonica-giant-lily/",
 "en_mimic":"/en/mimic-octopus-disguise-facts-and-myth/",
 "ko_ghost":"/monotropa-uniflora-ghost-plant/",
 "reading_guide":"/reading-guide/",
 "privacy":"/privacy-policy/",
}
def inspect(page,tag):
 errors=[]
 def err(x):
  if len(errors)<10:errors.append(str(x)[:220])
 page.on("pageerror",err)
 try:
  r=page.goto(BASE+PAGES[tag],wait_until="domcontentloaded",timeout=55000)
  page.wait_for_timeout(1500)
  res=page.evaluate("""() => {
    const d=document,root=d.documentElement;
    const ww=window.innerWidth, sh=root.scrollHeight;
    const all=[...d.querySelectorAll("body *")].filter(el=> {
      const s=getComputedStyle(el);
      if(s.display==="none"||s.visibility==="hidden")return false;
      const b=el.getBoundingClientRect();
      return b.width>1&&b.height>1&&b.right>ww+8&&b.left<ww+25&&!el.closest("svg")&&s.position!=="fixed";
    });
    const tables=[...d.querySelectorAll("table")].map(t=>{
      const tr=t.getBoundingClientRect(), cs=getComputedStyle(t);
      const anc=t.closest(".wp-block-table,.entry-content,figure");
      return {width:Math.round(tr.width),left:Math.round(tr.left),viewport:ww,
          container_scroll:!!(anc&&(anc.scrollWidth>anc.clientWidth+5)),
          wrapper_overflow:anc?getComputedStyle(anc).overflowX:null,
          own_scroll:t.scrollWidth>t.clientWidth+5};
    });
    const nav=d.querySelector("nav");
    const art=d.querySelector("article");
    const body=d.body;
    const css=art?getComputedStyle(art).fontSize:null;
    const main=d.querySelector("main");
    return {
       viewport:ww,device_pixel_ratio:window.devicePixelRatio,
       document_width:root.scrollWidth,body_width:body.scrollWidth,
       horizontal_overflow:root.scrollWidth>ww+6,
       overflowing_elements:all.slice(0,9).map(el=>({
         tag:el.tagName,cls:String(el.className||"").slice(0,65),
         width:Math.round(el.getBoundingClientRect().width),
         right:Math.round(el.getBoundingClientRect().right)
       })),tables,
       article_font_size:css,main_present:!!main,nav_present:!!nav,
       h1_count:d.querySelectorAll("h1").length,
       link_empty_text:[...d.querySelectorAll("a")].filter(a=>!a.getAttribute("aria-label")&&!a.innerText.trim()&& !a.querySelector("img[alt]")).length,
       images_missing_alt:[...d.images].filter(img=>!img.hasAttribute("alt")).length,
       content_height:sh,
       horizontal_scrollable_table_count:tables.filter(t=>t.container_scroll).length,
       tables_clipped_without_scroll:tables.filter(t=>t.width>ww&&t.wrapper_overflow!=="auto"&&t.wrapper_overflow!=="scroll").length
    };
  }""")
  res.update({"name":tag,"http_status":r.status if r else 0,"url":page.url,"console_errors":errors})
  filename=OUT/(tag+"_mobile.png" if res["viewport"]<500 else tag+"_desktop.png")
  page.screenshot(path=str(filename),full_page=False)
  return res
 except Exception as e:
  return {"name":tag,"http_status":0,"error":str(e)[:250],"console_errors":errors}
def main():
 results=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox"])
  for width,height,ismobile in [(390,844,True),(1366,768,False)]:
   context=browser.new_context(viewport={"width":width,"height":height},is_mobile=ismobile,has_touch=ismobile,device_scale_factor=1)
   for tag in PAGES:
    page=context.new_page()
    x=inspect(page,tag)
    results.append(x)
    print("BROWSER_CHECK="+json.dumps(x,ensure_ascii=False),flush=True)
    page.close()
   context.close()
  browser.close()
 summary={"page_count":len(results),"mobile_horizontal_overflow":[x["name"] for x in results if x.get("viewport",999)<500 and x.get("horizontal_overflow")],
  "mobile_tables_clipped":[{"page":x["name"],"tables":x.get("tables")} for x in results if x.get("viewport",999)<500 and x.get("tables_clipped_without_scroll")],
  "broken_pages":[x for x in results if x.get("http_status")!=200],
  "browser_errors":sum(len(x.get("console_errors",[])) for x in results),
  "limitations":"Chromium is an emulator of common screen widths, not a human inspection of physical mobile devices. Screenshots are provided in Actions artifacts."}
 (OUT/"responsive_report.json").write_text(json.dumps({"summary":summary,"pages":results,"timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat()},ensure_ascii=False,indent=2),encoding="utf8")
 print("BROWSER_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
