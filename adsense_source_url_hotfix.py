"""Repair one confirmed broken bibliography URL on two Quetzalcoatlus posts."""
import os,json
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("DOI_HOTFIX_APPLY","false").lower()=="true"
AUTH=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
s=requests.Session();s.auth=AUTH
out=Path("audit_output/doi_url_hotfix");out.mkdir(parents=True,exist_ok=True)
bad="https://doi.org/10.1080/02724634.2021.19075872724634.2019.1593184/Habitat-of-the-Giant-Pterosaur-Quetzalcoatlus-Lawson-1975-Pterodactyloidea/10.1080/02724634.2019.1593184.full"
correct="https://doi.org/10.1080/02724634.2021.1907587"
def req(method,path,**kwargs):
 r=s.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=70,**kwargs)
 r.raise_for_status()
 return r.json()
def main():
 planned={}
 for pid in (123,807):
  p=req("GET",f"posts/{pid}",params={"context":"edit"})
  if p["status"]!="publish":raise RuntimeError(f"{pid}: not published")
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  if raw.count(bad)!=1:
   raise RuntimeError(f"{pid}: broken URL not found exactly once, count {raw.count(bad)}")
  planned[pid]=raw
  (out/f"original_{pid}.json").write_text(json.dumps({"id":pid,"content":raw,"modified":p["modified"]},ensure_ascii=False),encoding="utf8")
 print("DOI_PREFLIGHT_OK",len(planned),"backups",flush=True)
 results=[]
 for pid,raw in planned.items():
  new=raw.replace(bad,correct,1)
  if APPLY:
   req("POST",f"posts/{pid}",json={"content":new})
   p=req("GET",f"posts/{pid}",params={"context":"edit"})
   final=p["content"].get("raw") or ""
   if p["status"]!="publish" or bad in final or correct not in final:
    raise RuntimeError(f"{pid}: DOI verification failed")
  results.append({"id":pid,"status":"UPDATED" if APPLY else "DRY_RUN","old_url_removed":bad not in new})
 print("DOI_HOTFIX_RESULT="+json.dumps(results),flush=True)
 (out/"result.json").write_text(json.dumps(results,indent=2),encoding="utf8")
if __name__=="__main__":main()
