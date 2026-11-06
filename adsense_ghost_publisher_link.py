"""Change only an intermittent-access ghost-pipe study link to publisher DOI article.

Cites same 2025 Anez et al. peer reviewed study. Preflight original two
published articles; preserve all other HTML, refs/images, status.
Read-only unless GHOST_SOURCE_APPLY=true.
"""
import os,json,re
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("GHOST_SOURCE_APPLY","false").lower()=="true"
OLD="https://pmc.ncbi.nlm.nih.gov/articles/PMC12900251/"
NEW="https://link.springer.com/article/10.1007/s12231-025-09637-1"
OUT=Path("audit_output/ghost_publisher_link");OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
def api(method,p,**k):
 r=s.request(method,f"{BASE}/wp-json/wp/v2/posts/{p}",timeout=75,**k);r.raise_for_status()
 return r.json()
def main():
 changed={}
 for pid in (254,518):
  p=api("GET",pid,params={"context":"edit"})
  if p["status"]!="publish":raise RuntimeError(f"{pid}: unexpectedly unpublished")
  html=p["content"].get("raw") or ""
  count=html.count(OLD)
  if NEW in html and count==0:
   print("GHOST_PUBLISHER_ALREADY",pid,flush=True);continue
  if count not in (1,2):raise RuntimeError(f"{pid}: old link phrase match={count}, stop")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False),encoding="utf8")
  changed[pid]={"old":html,"new":html.replace(OLD,NEW)}
 print("GHOST_PUBLISHER_PREFLIGHT",len(changed),flush=True)
 for pid,x in changed.items():
  if APPLY:
   api("POST",pid,json={"content":x["new"]})
   z=api("GET",pid,params={"context":"edit"})
   content=z["content"].get("raw") or ""
   if z["status"]!="publish" or content!=x["new"]:raise RuntimeError(f"{pid}: nonexact persistence")
  print("GHOST_PUBLISHER_RESULT="+json.dumps({"post_id":pid,"state":"UPDATED" if APPLY else "PREVIEW"},ensure_ascii=False),flush=True)
 (OUT/"status.json").write_text(json.dumps({"apply":APPLY,"posts":list(changed),"old":OLD,"new":NEW},indent=2),encoding="utf8")
if __name__=="__main__":main()
