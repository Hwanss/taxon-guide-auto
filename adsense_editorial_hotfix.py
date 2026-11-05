"""Verified editorial hotfix for 2 inaccurate fungus headlines and 2 corrupted image credits."""
import os,re,json
from pathlib import Path
import requests

base=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
apply=os.getenv("ADSENSE_HOTFIX_APPLY","false").lower()=="true"
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
out=Path("audit_output/content_hotfix");out.mkdir(parents=True,exist_ok=True)
titles={
 221:"면적 기준 세계 최대 균류, 어두운뽕나무버섯(Armillaria ostoyae)의 생태",
 434:"Oregon's Humongous Fungus: The World's Largest Known Fungus",
}
replacements={
 221:[
 ("면적 기준 지구상에서 가장 거대한 단일 생명체라는 공식 타이틀","면적 기준 세계 최대 규모의 균류 개체라는 기록"),
 ("지구상 가장 거대한 단일 생명체","세계 최대 규모의 균류 개체"),
 ("지상 최대의 생명체","세계 최대 규모의 균류"),
 ],
 434:[
 ("largest single living organism on Earth","largest known fungus by area"),
 ("largest single organism confirmed on Earth by surface area","largest known fungus by area"),
 ("world’s largest living creature","world’s largest known fungus"),
 ],
}
source="https://www.guinnessworldrecords.com/world-records/606952-largest-living-organism"
ko_note='<p><strong>면적 기준 기록 정정:</strong> 현재 알려진 최대 단일 생명체는 호주 샤크베이의 해초 Posidonia australis(약 200km²)입니다. 오리건의 Armillaria ostoyae(약 9.65km²)는 면적 기준 최대 균류 기록을 보유합니다. <a href="'+source+'" target="_blank" rel="noopener noreferrer">기네스 세계기록</a>에서 두 기록을 구분해 확인할 수 있습니다.</p>'
en_note='<p><strong>Area record clarification:</strong> The largest known single organism by area is the Posidonia australis seagrass clone in Shark Bay, Australia (about 200 km²). Oregon’s Armillaria ostoyae (about 9.65 km²) remains the largest known fungus by area. <a href="'+source+'" target="_blank" rel="noopener noreferrer">Guinness World Records</a> documents this distinction.</p>'
def call(method,path,**kw):
 r=s.request(method,base+"/wp-json/wp/v2/"+path,timeout=80,**kw);r.raise_for_status();return r.json()
results=[]
for pid in (141,775,221,434):
 try:
  p=call("GET",f"posts/{pid}",params={"context":"edit"})
  if p["status"]!="publish":raise ValueError("post status not publish")
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  (out/f"original_{pid}.json").write_text(json.dumps({"id":pid,"title":p["title"],"content":raw,"modified":p["modified"]},ensure_ascii=False),encoding="utf8")
  new=raw
  if pid in (141,775):
   new,n=re.subn(r'(?<=Sèrgio Valle Duarte) \.mw-parser-output.*?(?= · Wikimedia Commons)',"",new,count=1,flags=re.S)
   if n!=1 or ".mw-parser-output" in new:raise ValueError("CSS credit markup not found or remains")
  else:
   for old,replace in replacements[pid]:
    if old not in new:raise ValueError("Fact claim text missing: "+old)
    new=new.replace(old,replace)
   marker="<h2>"
   if marker not in new:raise ValueError("No first heading")
   note=ko_note if pid==221 else en_note
   new=new.replace(marker,note+marker,1)
  if len(new)<len(raw)*0.65:raise ValueError("Potential content loss")
  payload={"content":new}
  if pid in titles:payload["title"]=titles[pid]
  if apply:
   call("POST",f"posts/{pid}",json=payload)
   v=call("GET",f"posts/{pid}",params={"context":"edit"})
   if v["status"]!="publish":raise ValueError("No longer public")
   actual=v["content"].get("raw") or ""
   if pid in titles and titles[pid] not in v["title"].get("raw",""):raise ValueError("Title verification failed")
   if pid in (141,775) and ".mw-parser-output" in actual:raise ValueError("CSS verification failed")
  row={"id":pid,"result":"APPLIED" if apply else "DRY_RUN","html_before":len(raw),"html_after":len(new)}
 except Exception as e:
  row={"id":pid,"result":"ERROR","reason":str(e)}
 print(json.dumps(row,ensure_ascii=False),flush=True);results.append(row)
(out/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf8")
if any(r["result"]=="ERROR" for r in results):raise SystemExit(1)
print("HOTFIX_SUCCESS",len(results),"APPLIED",apply)
