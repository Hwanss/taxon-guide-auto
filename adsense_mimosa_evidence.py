"""Bilingual Mimosa literature comparison, safe published-content improvement.

Evidence: Gagliano et al. 2014 Oecologia PMID 24390479; Biegler 2018 Oecologia
PMID 29214474; review published in Learning & Behavior 2026.
The reference citations are real but none establish plant consciousness.
No republishing from draft; original full HTML always archived. Default preview.
"""
import json,os,re
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("MIMOSA_APPLY","false").lower()=="true"
OUT=Path("audit_output/mimosa_evidence");OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
EXPLANATIONS={
 139:'''<section class="taxonguru-mimosa-study-comparison">
<h2>미모사가 배웠다는 결론, 왜 아직 논쟁 중일까요?</h2>
<p>식물의 접힘 반응이 반복 자극 후 줄었다는 사실과, 그 변화가 <strong>피로가 아닌 학습</strong>이었다는 해석은 다릅니다. 미모사 연구를 판단하려면 최초 실험과 비판 논문을 함께 읽어야 합니다.</p>
<table><thead><tr><th>연구</th><th>실제로 확인한 내용</th><th>해석에서 주의할 점</th></tr></thead><tbody>
<tr><td>Gagliano 외, 2014, <em>Oecologia</em></td><td>화분을 반복해서 떨어뜨렸을 때 잎을 접는 반응이 감소했으며, 환경 조건에 따른 반응 차이를 보고했습니다.</td><td>연구진은 이를 습관화(habituation)로 해석했지만 이것만으로 인간과 같은 의식이나 기억이 있다는 뜻은 아닙니다.</td></tr>
<tr><td>Biegler, 2018, <em>Oecologia</em></td><td>원래 실험의 탈습관화·자극 구별 증거와 대조 조건을 재평가했습니다.</td><td>상당 부분은 운동기관의 피로로 설명할 가능성을 제시했으며, 학습 해석이 최종적으로 입증됐다고 보기 어렵다고 논평했습니다.</td></tr>
<tr><td>2026년 학습 연구 방법론 검토</td><td>식물의 습관화 연구에서 적절한 대조군과 감각 적응·피로 배제가 중요함을 설명했습니다.</td><td>식물의 학습 가능성은 연구 대상이지만, 논쟁 중인 해석을 확정적 사실로 표현해서는 안 됩니다.</td></tr>
</tbody></table>
<p><strong>이 글의 편집 판단:</strong> ‘반복 자극 후 접힘이 줄어든다’는 관찰은 설명할 수 있지만, ‘미모사가 사람처럼 배운다’는 결론은 현재 근거만으로 단정하지 않습니다. 운동기관의 에너지 소모와 실험 대조 조건을 함께 고려해야 합니다.</p>
<p>직접 확인할 자료: <a href="https://pubmed.ncbi.nlm.nih.gov/24390479/" target="_blank" rel="noopener noreferrer">Gagliano 외(2014) 원연구</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/29214474/" target="_blank" rel="noopener noreferrer">Biegler(2018) 비판 논문</a> · <a href="https://link.springer.com/article/10.3758/s13420-026-00727-1" target="_blank" rel="noopener noreferrer">2026년 연구 방법론 검토</a>.</p>
</section>''',
 781:'''<section class="taxonguru-mimosa-study-comparison">
<h2>Does Mimosa learn, or do its leaves simply tire? Three research perspectives</h2>
<p>A reduced leaf-closing response following repeated stimulation is an observation. Explaining that response as <strong>learning rather than fatigue</strong> requires stronger controls. Comparing the original experiment with the scientific critique makes the limits explicit.</p>
<table><thead><tr><th>Source</th><th>What it examined</th><th>What it does not establish</th></tr></thead><tbody>
<tr><td>Gagliano et al., 2014, <em>Oecologia</em></td><td>Repeatedly dropping potted <em>Mimosa pudica</em> plants and measuring reduced leaf folding under different environments.</td><td>The authors interpreted their results as habituation, not evidence of human-like intelligence or conscious memory.</td></tr>
<tr><td>Biegler, 2018, <em>Oecologia</em></td><td>Critically reviewed the interpretation of dishabituation and stimulus specificity and the experimental controls.</td><td>Motor fatigue could account for much of the reported result; this critique concluded that habituation remained uncertain.</td></tr>
<tr><td>2026 review of learning methodology</td><td>Examined why controlling for fatigue, sensory adaptation and recovery matters in plant-behavior studies.</td><td>Mixed evidence should not be recast as proof that all plants learn or that a plant has a brain-like memory.</td></tr>
</tbody></table>
<p><strong>Editorial interpretation:</strong> It is reasonable to report changes in leaf movements across repeated trials, but not to claim that learning has been conclusively proved. Future controlled replications should distinguish physiological fatigue from experience-dependent behavioral change.</p>
<p>Read the sources: <a href="https://pubmed.ncbi.nlm.nih.gov/24390479/" target="_blank" rel="noopener noreferrer">Gagliano et al. (2014)</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/29214474/" target="_blank" rel="noopener noreferrer">Biegler (2018) critique</a> · <a href="https://link.springer.com/article/10.3758/s13420-026-00727-1" target="_blank" rel="noopener noreferrer">2026 methodological review</a>.</p>
</section>'''
}
def api(method,route,**kw):
 r=s.request(method,BASE+"/wp-json/wp/v2/"+route,timeout=70,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {route}: HTTP {r.status_code} {r.text[:220]}")
 return r.json()
def main():
 planned={}
 for pid,note in EXPLANATIONS.items():
  p=api("GET",f"posts/{pid}",params={"context":"edit"})
  if p.get("status")!="publish":raise RuntimeError(f"{pid} not published; no changes")
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  marker="taxonguru-mimosa-study-comparison"
  if marker in raw:
   print("MIMOSA_ALREADY_PRESENT",pid,flush=True);continue
  m=re.search(r"<h2\b",raw,re.I)
  if not m:raise RuntimeError(f"{pid} has no safe H2 insertion point")
  updated=raw[:m.start()]+note+raw[m.start():]
  if len(updated)-len(raw)!=len(note):raise RuntimeError("Unexpected string difference")
  (OUT/f"before_{pid}.json").write_text(json.dumps({
   "id":pid,"content":raw,"title":p["title"],"status":p["status"],
   "excerpt":p["excerpt"],"modified":p["modified"]
  },ensure_ascii=False,indent=2),encoding="utf8")
  planned[pid]=updated
 print("MIMOSA_PREFLIGHT",len(planned),flush=True)
 res=[]
 for pid,html in planned.items():
  if APPLY:
   api("POST",f"posts/{pid}",json={"content":html})
   new=api("GET",f"posts/{pid}",params={"context":"edit"})
   if new.get("status")!="publish" or (new["content"].get("raw") or "").count("taxonguru-mimosa-study-comparison")!=1:
    raise RuntimeError(f"{pid} verify failed")
  res.append({"id":pid,"result":"UPDATED" if APPLY else "PREVIEW"})
  print("MIMOSA_ITEM="+json.dumps(res[-1]),flush=True)
 (OUT/"results.json").write_text(json.dumps(res,indent=2),encoding="utf8")
if __name__=="__main__": main()
