"""Repair two stale public excerpt snippets after factual article corrections.

Strict preflight of both originals, backups, safe idempotence,
update only excerpt and reread status. No other WordPress changes.
"""
import json,os
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("B5_EXCERPT_APPLY","false").lower()=="true"
OUT=Path("audit_output/batch5_excerpt");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
TARGET={
164:{"old":"최대 20m 크기와 18톤의 치악력을 지닌","new":"메갈로돈의 크기는 화석과 복원 모델에 따라 달리 추정됩니다. 기존 15~20m 추정과 2025년 최대 약 24.3m 가능성, 치악력 모델의 한계와 멸종 근거를 실제 연구로 비교합니다."},
170:{"old":"척추동물 중 유일하게 적혈구와 헤모글로빈이 없는","new":"눈표범빙어가 속한 큰지느러미빙어과는 성숙 적혈구와 헤모글로빈이 없는 독특한 척추동물 계통입니다. 2024~2025년 유전체 연구를 바탕으로 혈장 산소 운반, 큰 심장, 결빙 방지 적응을 설명합니다."}
}
def api(method,p,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/posts/"+str(p),timeout=65,**kw)
 r.raise_for_status()
 return r.json()
def main():
 planned={}
 for pid,item in TARGET.items():
  p=api("GET",pid,params={"context":"edit"})
  if p["status"]!="publish":raise RuntimeError(f"{pid}: status changed")
  ex=p["excerpt"].get("raw") or ""
  if ex==item["new"]:
   print("B5_EXCERPT_ALREADY",pid,flush=True)
   continue
  if item["old"] not in ex:raise RuntimeError(f"{pid}: unexpected original excerpt {ex[:100]}")
  (OUT/f"original_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False),encoding="utf8")
  planned[pid]=item["new"]
 print("B5_EXCERPT_PREFLIGHT",len(planned),flush=True)
 for pid,new in planned.items():
  if APPLY:
   api("POST",pid,json={"excerpt":new})
   check=api("GET",pid,params={"context":"edit"})
   if check["status"]!="publish" or check["excerpt"].get("raw")!=new:
    raise RuntimeError(f"{pid}: verification failed")
  print("B5_EXCERPT_RESULT="+json.dumps({"id":pid,"result":"UPDATED" if APPLY else "PREVIEW"},ensure_ascii=False),flush=True)
 (OUT/"report.json").write_text(json.dumps({"applied":APPLY,"ids":list(planned)},ensure_ascii=False),encoding="utf8")
if __name__=="__main__":main()
