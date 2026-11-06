"""Clean up misleading public-card excerpt after corrections to goblin shark.

Dry-run unless EXCERPT_APPLY is true. Preserve entire original post and verify.
"""
import os,json
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("EXCERPT_APPLY","false").lower()=="true"
OUT=Path("audit_output/excerpt_cleanup");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
pid=231
r=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=60)
r.raise_for_status();p=r.json()
old=p["excerpt"].get("raw") or ""
if p.get("status")!="publish":raise RuntimeError("post is no longer published")
NEW="고블린상어는 오래된 상어 계통에 속하지만 진화가 멈춘 생물은 아닙니다. 실제 해양 촬영 연구에서 측정한 턱 돌출 속도 약 3.14m/s와 분홍빛 피부, 전기 감지 주둥이의 역할을 원자료에 근거해 설명합니다."
if old==NEW:
 print("EXCERPT_STATUS ALREADY_UPDATED",flush=True)
else:
 if "1억 2,500만 년" not in old:
  raise RuntimeError("old excerpt changed; re-review necessary")
 (OUT/"before.json").write_text(json.dumps({"id":pid,"old_excerpt":old,"post":p},ensure_ascii=False),encoding="utf8")
 if APPLY:
  x=S.post(f"{BASE}/wp-json/wp/v2/posts/{pid}",json={"excerpt":NEW},timeout=65);x.raise_for_status()
  check=S.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=65);check.raise_for_status()
  if check.json()["excerpt"].get("raw")!=NEW or check.json()["status"]!="publish":
   raise RuntimeError("excerpt did not persist in published article")
 print("EXCERPT_STATUS",("UPDATED" if APPLY else "PREVIEW"),"ID",pid,flush=True)
(OUT/"result.json").write_text(json.dumps({"apply":APPLY,"id":pid,"new_excerpt":NEW},ensure_ascii=False,indent=2),encoding="utf8")
