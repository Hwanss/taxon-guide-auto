"""Titan arum claim-scope correction: backup-first, read-only by default."""
import os,json,re,html
from pathlib import Path
import requests
from bs4 import BeautifulSoup
SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
OUT=Path("audit_output/titan_claim");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
S.headers["User-Agent"]="TaxonGuruClaimCorrection/2026-11-23"
APPLY=os.getenv("TITAN_CLAIM_APPLY","false").lower()=="true"
EXPECTED=json.loads(os.getenv("TITAN_EXPECTED","{}"))
OLD="종의 유전 자원을 안전하게 보존하고 개체수를 복원할 수 있는 핵심적인 기술적 보루"
NEW="실험실에서 조직배양과 식물체 증식 가능성을 보여 주는 연구 단계이며, 야생 서식지 재도입과 개체군 회복 효과는 별도로 검증해야 하는 보전 기술 후보"
def wp(pid,method="GET",**kw):
 r=S.request(method,f"{SITE}/wp-json/wp/v2/posts/{pid}",timeout=60,**kw);r.raise_for_status();return r.json()
def refs(raw):
 return re.findall(r'<li\s+id=["\']ref-(\d+)["\']',raw,re.I)
def imgs(raw):
 return re.findall(r'<img\b[^>]*>',raw,re.I)
def main():
 p=wp(24,params={"context":"edit"})
 raw=p.get("content",{}).get("raw")
 if p.get("status")!="publish" or not raw:raise RuntimeError("post 24 not editable published raw")
 (OUT/"original_24.json").write_text(json.dumps(p,ensure_ascii=False,indent=2))
 if raw.count(OLD)!=1:raise RuntimeError(f"exact Korean claim not unique: {raw.count(OLD)}")
 if not all(x in raw for x in ('ref-4','ref-5')):raise RuntimeError("source anchors changed")
 if not all(x in raw for x in ("10.29244/jhi.15.3.133-139","10.17660/actahortic.1988.226.5")):
  raise RuntimeError("primary research links changed")
 changed=raw.replace(OLD,NEW,1)
 if refs(raw)!=refs(changed) or imgs(raw)!=imgs(changed):raise RuntimeError("refs/images changed")
 if re.findall(r'<h[1-6]\b',raw,re.I)!=re.findall(r'<h[1-6]\b',changed,re.I):raise RuntimeError("headings changed")
 (OUT/"proposed_24.html").write_text(changed)
 preview={"result":"PREVIEW_OK","apply":APPLY,"id":24,"modified":p["modified"],"slug":p["slug"],"status":p["status"],"old_count":1,"refs":len(refs(raw)),"images":len(imgs(raw))}
 (OUT/"preview.json").write_text(json.dumps(preview,ensure_ascii=False,indent=2))
 print("TITAN_PREVIEW="+json.dumps(preview,ensure_ascii=False),flush=True)
 if not APPLY:return
 if EXPECTED!={"24":p["modified"]}:raise RuntimeError("prior preview timestamp mismatch")
 updated=wp(24,"POST",json={"content":changed})
 after=wp(24,params={"context":"edit"})
 if after.get("content",{}).get("raw")!=changed or after["slug"]!=p["slug"] or after["status"]!="publish":
  raise RuntimeError("readback/slug/status mismatch")
 pub=requests.get(p["link"],timeout=50)
 if pub.status_code!=200 or NEW not in BeautifulSoup(pub.text,"html.parser").get_text(" ",strip=True):
  raise RuntimeError("public 200 or new text missing")
 preview["result"]="LIVE_UPDATED_AND_VERIFIED"
 (OUT/"result.json").write_text(json.dumps(preview,ensure_ascii=False,indent=2))
 print("TITAN_RESULT="+json.dumps(preview,ensure_ascii=False),flush=True)
if __name__=="__main__":
 try:
  main()
 except Exception as exc:
  # Preserve a non-secret failure reason in the artifact for diagnosing
  # authentication or exact-match failures; never retry a write.
  message=str(exc)
  if any(token in message.lower() for token in ("password", "authorization", "token", "secret")):
   message="redacted authentication or secret-related error"
  failure={"result":"BLOCKED_NO_WRITE","error_type":type(exc).__name__,"reason":message[:500]}
  (OUT/"failure.json").write_text(json.dumps(failure,ensure_ascii=False,indent=2))
  print("TITAN_BLOCKED="+json.dumps(failure,ensure_ascii=False),flush=True)
  raise SystemExit(1)

