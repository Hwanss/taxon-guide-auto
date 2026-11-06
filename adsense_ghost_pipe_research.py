"""Improve ghost pipe biology articles with two primary-source studies (2025).

Not a medical efficacy claim. Show what each study DID and DID NOT establish.
No claiming first-hand research, no sign-off. Backup both WordPress originals.
"""
from __future__ import annotations
import os,json,re
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("GHOST_PIPE_APPLY","false").lower()=="true"
OUT=Path("audit_output/ghost_pipe_evidence");OUT.mkdir(parents=True,exist_ok=True)
AUTH=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
S=requests.Session();S.auth=AUTH
SCHEMAS={
254:{
 "heading":"<h2>민간전승과 현대 과학의 경계: 약용에 관한 오해와 주의점</h2>",
 "note":'''<section class="taxonguru-ghost-pipe-research-2025"><h2>2025년 연구 비교: 유효성·독성·사용 실태는 서로 다릅니다</h2>
<p>수정난풀(<em>Monotropa uniflora</em>)에 관한 인터넷의 약용 주장을 검토할 때는 세 가지 질문을 구분해야 합니다. 실제로 누가 사용했는가, 특정 독성 성분이 검출됐는가, 사람에게 치료 효과가 입증됐는가는 각각 다른 문제입니다.</p>
<table><thead><tr><th>자료</th><th>검사 또는 조사 대상</th><th>확인된 결과</th><th>결론의 한계</th></tr></thead><tbody>
<tr><td>2025년 성분 분석</td><td>수정난풀 표본 50개, 질량분석 및 분자 네트워킹</td><td>시료에서 그라야노톡신류가 검출되지 않았습니다.</td><td>특정 물질의 미검출이 식물 전체의 안전성, 섭취 가능성이나 치료 효과를 증명하지는 않습니다.</td></tr>
<tr><td>2025년 민속식물학 조사</td><td>미국에서 수정난풀을 사용하는 사람들의 디지털 설문</td><td>통증 관리 등을 목적으로 한 사용 경험과 인터넷을 통한 지식 확산이 보고됐습니다.</td><td>자기보고식 사용 실태이며 임상 시험이나 진통 효과 입증 연구가 아닙니다.</td></tr>
</tbody></table>
<p><strong>검증 결론:</strong> 민간 사용 기록과 현대 성분 분석을 연결해 읽을 수는 있지만, 현재 자료만으로 수정난풀의 약용 효과나 자가 복용의 안전성을 보장해서는 안 됩니다. 아래 내용은 의학적 사용 권고가 아니라 자료 간 차이를 설명하는 과학적 비교입니다.</p>
<p><strong>원자료:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/40982630/" target="_blank" rel="noopener noreferrer">Anez et al., Journal of Natural Products (2025), 분석 표본 50건</a> · <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC12900251/" target="_blank" rel="noopener noreferrer">Ghost Pipe Then and Now, 2025 민속식물학 조사</a>.</p>
</section>'''
},
518:{
 "heading":"<h2>Folk Remedies and Scientific Caution</h2>",
 "note":'''<section class="taxonguru-ghost-pipe-research-2025"><h2>Two 2025 studies: chemical detection is not clinical effectiveness</h2>
<p>Traditional use, chemical safety testing and proven clinical effectiveness answer different questions. Comparing two recent studies helps avoid misleading medical conclusions about <em>Monotropa uniflora</em>.</p>
<table><thead><tr><th>Evidence</th><th>What researchers studied</th><th>What the study found</th><th>What it did not establish</th></tr></thead><tbody>
<tr><td>2025 phytochemical analysis</td><td>50 plant samples, targeted and untargeted mass spectrometry</td><td>Grayanane-type toxins were not detected in the samples analyzed.</td><td>Non-detection of these compounds does not prove the plant is completely safe to consume or medically effective.</td></tr>
<tr><td>2025 ethnobotany survey</td><td>Self-reported practices of people using ghost pipe in the United States</td><td>The survey documented traditional and emerging uses, including pain management, and the role of online communities.</td><td>Reported use is not a controlled clinical trial and does not demonstrate pain relief or treatment efficacy.</td></tr>
</tbody></table>
<p><strong>Evidence-based interpretation:</strong> Neither study establishes that consuming ghost pipe is safe or that it treats medical conditions. This is an editorial analysis of published research, not first-hand field research or medical advice.</p>
<p><strong>Primary sources:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/40982630/" target="_blank" rel="noopener noreferrer">Anez et al., Journal of Natural Products (2025): 50 samples</a> · <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC12900251/" target="_blank" rel="noopener noreferrer">Ghost Pipe Then and Now: 2025 ethnobotanical survey</a>.</p>
</section>'''
}
}
def req(method,path,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+path,timeout=75,**kw);r.raise_for_status();return r.json()
def main():
 changes={}
 for id,spec in SCHEMAS.items():
  post=req("GET",f"posts/{id}",params={"context":"edit"})
  if post["status"]!="publish":raise RuntimeError(f"{id}: status changed")
  raw=post["content"].get("raw") or post["content"].get("rendered") or ""
  if "taxonguru-ghost-pipe-research-2025" in raw:
   print("EVIDENCE_ALREADY_PRESENT",id,flush=True);continue
  if raw.count(spec["heading"])!=1:raise RuntimeError(f"{id}: expected heading does not match actual")
  new=raw.replace(spec["heading"],spec["note"]+spec["heading"],1)
  changes[id]=(raw,new)
  (OUT/f"original_{id}.json").write_text(json.dumps({"id":id,"content":raw,"modified":post.get("modified"),"status":post["status"]},ensure_ascii=False,indent=2),encoding="utf8")
 print("GHOST_PIPE_PREFLIGHT_OK",len(changes),flush=True)
 for id,(old,new) in changes.items():
  if APPLY:
   req("POST",f"posts/{id}",json={"content":new})
   p=req("GET",f"posts/{id}",params={"context":"edit"})
   actual=p["content"].get("raw") or ""
   if p["status"]!="publish" or actual.count("taxonguru-ghost-pipe-research-2025")!=1:raise RuntimeError(f"{id}: write check failed")
  print("GHOST_PIPE_ITEM="+json.dumps({"id":id,"action":"UPDATED" if APPLY else "PREVIEW","added_chars":len(new)-len(old)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
