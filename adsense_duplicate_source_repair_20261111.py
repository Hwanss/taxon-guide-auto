"""Claim-matched reference repair for 4 published TaxonGuru posts.

Targets: Puya raimondii ref-5 from duplicated 2024 secondary review to
Rees & Roe (1980) primary field observations and explicit nutrient hypothesis.
Nautilus pompilius ref-4 from duplicated NOAA summary to Dunstan et al. (2011)
wild mark-recapture life-history research. NEVER infer certainty from hypothesis.
Safe workflow: authenticated backups -> preview -> exact timestamp gate -> write
-> readback and public link status, with non-writing default.
"""
from __future__ import annotations
import datetime,html,json,os,re
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("DUPLICATE_SOURCE_APPLY","false").lower()=="true"
EXPECTED=json.loads(os.getenv("DUPLICATE_SOURCE_EXPECTED","{}"))
OUT=Path("audit_output/duplicate_source_repair")
OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
S.headers["User-Agent"]="TaxonGuruBackupFirstClaimSourceRepair/2026-11-11"
SECONDARY="https://www.frontiersin.org/journals/conservation-science/articles/10.3389/fcosc.2024.1349553/full"
NOAA="https://www.fisheries.noaa.gov/species/chambered-nautilus"
TARGETS={
 227:{"ref":5,"expected_old":SECONDARY,"new":"https://doi.org/10.1139/b80-157",
      "label":"Rees & Roe (1980), Canadian Journal of Botany: Puya raimondii와 새의 현장 관찰·영양 획득 가설",
      "context_word":"육식"},
 449:{"ref":5,"expected_old":SECONDARY,"new":"https://doi.org/10.1139/b80-157",
      "label":"Rees & Roe (1980), Canadian Journal of Botany: field observations and proposed nutrient hypothesis",
      "context_word":"protocarnivorous"},
 209:{"ref":4,"expected_old":NOAA,"new":"https://doi.org/10.1371/journal.pone.0016312",
      "label":"Dunstan et al. (2011), PLOS ONE: 앵무조개 야생 표지·재포획 수명 연구",
      "context_word":"15"},
 401:{"ref":4,"expected_old":NOAA,"new":"https://doi.org/10.1371/journal.pone.0016312",
      "label":"Dunstan et al. (2011), PLOS ONE: wild mark-recapture, maturity and longevity",
      "context_word":"maturity"}
}

def wp(method,endpoint,**kwargs):
 r=S.request(method,SITE+"/wp-json/wp/v2/"+endpoint,timeout=75,**kwargs)
 r.raise_for_status()
 return r.json()

def extract_refs(raw):
 refs={}
 for m in re.finditer(r'<li\s+id=["\x27]ref-(\d+)["\x27][^>]*>.*?</li>',raw,re.I|re.S):
  n=int(m.group(1))
  if n in refs:raise ValueError(f"duplicate reference ID {n}")
  refs[n]=m.group(0)
 return refs

def patch(pid,raw):
 t=TARGETS[pid]; r=int(t["ref"])
 refs=extract_refs(raw)
 if r not in refs:raise ValueError(f"{pid} missing reference {r}")
 old=refs[r]
 anchors=re.findall(r'<a\b[^>]*href=["\x27]([^"\x27]+)',old,re.I)
 if len(anchors)!=1 or html.unescape(anchors[0])!=t["expected_old"]:
  raise ValueError(f"{pid} source URL changed: {anchors}")
 # Ensure other numbered slot still keeps the identical original URL.
 other=2 if pid in (227,449) else 5
 if other not in refs or t["expected_old"] not in html.unescape(refs[other]):
  raise ValueError(f"{pid} duplicate source slot {other} no longer matches")
 text=" ".join(BeautifulSoup(raw,"html.parser").get_text(" ",strip=True).split())
 if t["context_word"].lower() not in text.lower():
  raise ValueError(f"{pid} expected claim context missing")
 if not re.search(r'(?:(?:href=["\x27]#ref-'
                 +str(r)+r'["\x27])|(?:\['+str(r)+r'\]))',raw,re.I):
  raise ValueError(f"{pid} source {r} is not cited")
 updated_ref=(f'<li id="ref-{r}"><a href="{html.escape(t["new"],quote=True)}" '
              f'target="_blank" rel="noopener noreferrer">{html.escape(t["label"])}</a> '
              f'— {"확인일" if pid in (227,209) else "reviewed"} 2026-11-11</li>')
 if raw.count(old)!=1:raise ValueError("Source snippet not unique")
 changed=raw.replace(old,updated_ref,1)
 if sorted(extract_refs(changed))!=sorted(refs):
  raise ValueError("Reference numbering changed")
 if t["new"] not in extract_refs(changed)[r]:
  raise ValueError("New source not in targeted reference")
 if len(re.findall(r"<img\b",raw,re.I))!=len(re.findall(r"<img\b",changed,re.I)):
  raise ValueError("Image count changed")
 if len(re.findall(r"<h[123]\b",raw,re.I))!=len(re.findall(r"<h[123]\b",changed,re.I)):
  raise ValueError("Heading structure changed")
 if len(changed)<len(raw)*.98:raise ValueError("Suspicious content reduction")
 # A reference replacement is not a body rewrite; this source describes a
 # scientific hypothesis or site-specific sampling, never definitive proof.
 return changed

def main():
 posts={}
 pending={}
 for pid in TARGETS:
  p=wp("GET",f"posts/{pid}",params={"context":"edit"})
  if p.get("status")!="publish":raise ValueError(f"{pid} is no longer public")
  raw=p.get("content",{}).get("raw")
  if not raw:raise ValueError(f"{pid}: no editable raw HTML")
  # Copy full original post record before editing anything.
  (OUT/f"original_{pid}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")
  changed=patch(pid,raw)
  (OUT/f"proposed_{pid}.html").write_text(changed,encoding="utf-8")
  posts[pid]=p
  pending[pid]=changed
 timestamps={str(pid):posts[pid]["modified"] for pid in TARGETS}
 result={"apply":APPLY,"original_backups":len(posts),"modified_timestamps":timestamps,
         "targets":[{"id":pid,"ref_id":t["ref"],"source":t["new"]} for pid,t in TARGETS.items()],
         "result":"PREVIEW_OK"}
 print("SOURCE_REPAIR_PREFLIGHT="+json.dumps(result,ensure_ascii=False),flush=True)
 if APPLY:
  if EXPECTED!=timestamps:
   raise ValueError(f"Exact prior-preview timestamps required: expected={EXPECTED}, current={timestamps}")
  done=[]
  for pid,prepared in pending.items():
   wp("POST",f"posts/{pid}",json={"content":prepared})
   p=wp("GET",f"posts/{pid}",params={"context":"edit"})
   if p["status"]!="publish" or p["content"].get("raw")!=prepared:
    raise RuntimeError(f"{pid}: saved content readback mismatch; restore from backup")
   public=requests.get(posts[pid]["link"],timeout=50,headers={"Cache-Control":"no-cache"})
   rest=requests.get(SITE+f"/wp-json/wp/v2/posts/{pid}",timeout=50)
   if public.status_code!=200 or rest.status_code!=200:
    raise RuntimeError(f"{pid}: published page/REST not 200")
   body=rest.json().get("content",{}).get("rendered","")
   if TARGETS[pid]["new"] not in html.unescape(body):
    raise RuntimeError(f"{pid}: published new reference not visible")
   done.append(pid)
  result["result"]="LIVE_UPDATED_AND_VERIFIED"
  result["public_verified_ids"]=done
 (OUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print("SOURCE_REPAIR_RESULT="+json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
 main()
