"""Find exact runtime selector of mobile floating sharing controls. READ-ONLY."""
import json,os
from playwright.sync_api import sync_playwright
SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=["--no-sandbox"])
 ctx=b.new_context(viewport={"width":390,"height":844},device_scale_factor=1,is_mobile=True,has_touch=True)
 pg=ctx.new_page()
 pg.goto(SITE+"/victoria-amazonica-giant-lily/",wait_until="domcontentloaded",timeout=60000)
 pg.wait_for_timeout(3500)
 r=pg.evaluate("""() => [...document.querySelectorAll('body *')].filter(el=>{
  const c=getComputedStyle(el),r=el.getBoundingClientRect();
  const tags=(String(el.className||'')+' '+String(el.id||'')).toLowerCase();
  return (c.position==='fixed'&&r.width>10&&r.height>10&&r.right>=innerWidth-90)||(tags.match(/share|a2a|heateor|sticky|social/)&&r.width>10&&r.height>10);
 }).slice(0,40).map(el=>{const r=el.getBoundingClientRect(),c=getComputedStyle(el);
 return {tag:el.tagName,id:el.id,cls:String(el.className||'').slice(0,210),pos:c.position,display:c.display,right:Math.round(r.right),left:Math.round(r.left),w:Math.round(r.width),h:Math.round(r.height),outer:el.outerHTML.slice(0,210)};})""")
 print("OVERLAY_FOUND="+json.dumps(r,ensure_ascii=False),flush=True)
 b.close()
