"""Insert source-backed, reader-useful comparison notes into four existing biology articles.

Only add researched comparisons using Kew and Guinness records; preserves original
content, citations, images, URLs and publication status. Dry run by default.
"""
import os,re,json
from pathlib import Path
from datetime import datetime,timezone
import requests

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("FACTCHECK_APPLY","false").lower()=="true"
SESSION=requests.Session()
SESSION.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
OUT=Path("audit_output/factcheck_additions");OUT.mkdir(parents=True,exist_ok=True)

FACTS={
221:'''<section class="taxonguru-source-comparison">
<h2>기록 비교: 세계 최대 균류와 세계 최대 단일 생명체는 다릅니다</h2>
<p>‘가장 크다’는 말은 측정 기준을 함께 확인해야 의미가 분명해집니다. 면적 기준에서 균류와 전체 생명체의 공식 기록 보유자는 서로 다릅니다.</p>
<figure class="wp-block-table"><table><thead><tr><th>구분</th><th>해당 생물</th><th>확인된 면적</th><th>기록의 의미</th></tr></thead><tbody>
<tr><td>균류</td><td><em>Armillaria ostoyae</em>, 미국 오리건</td><td>약 9.65km²</td><td>면적 기준 세계 최대 규모의 균류 개체</td></tr>
<tr><td>해초</td><td><em>Posidonia australis</em>, 호주 샤크베이</td><td>약 200km²</td><td>면적 기준 세계 최대 단일 생명체</td></tr>
</tbody></table></figure>
<p>두 수치는 개체 또는 클론의 분포 면적에 관한 기록으로, 지상에서 보이는 버섯 갓의 크기나 정확한 생물량(무게)을 의미하지 않습니다. 균류의 무게 추정치는 별도 기록으로 비교해야 합니다.</p>
<p>자료: <a href="https://www.guinnessworldrecords.com/world-records/606952-largest-living-organism" target="_blank" rel="noopener noreferrer">기네스: 최대 단일 생명체</a> · <a href="https://www.guinnessworldrecords.com/world-records/106978-heaviest-organism" target="_blank" rel="noopener noreferrer">기네스: 가장 무거운 생명체</a></p>
</section>''',
434:'''<section class="taxonguru-source-comparison">
<h2>Record comparison: the largest fungus is not the largest organism by area</h2>
<p>The word “largest” depends on what is measured. The two records below refer to different groups of organisms and both use the area occupied by a genetic individual or clone.</p>
<figure class="wp-block-table"><table><thead><tr><th>Group</th><th>Organism and location</th><th>Area</th><th>Record</th></tr></thead><tbody>
<tr><td>Fungus</td><td><em>Armillaria ostoyae</em>, Oregon, USA</td><td>About 9.65 km²</td><td>Largest known fungus by area</td></tr>
<tr><td>Seagrass</td><td><em>Posidonia australis</em>, Shark Bay, Australia</td><td>About 200 km²</td><td>Largest known single organism by area</td></tr>
</tbody></table></figure>
<p>These areas represent the spread of a single genetic individual or clone—not the visible size of a mushroom cap, and not a measurement of biomass. Weight records must be considered separately.</p>
<p>Sources: <a href="https://www.guinnessworldrecords.com/world-records/606952-largest-living-organism" target="_blank" rel="noopener noreferrer">Guinness: largest organism</a> · <a href="https://www.guinnessworldrecords.com/world-records/106978-heaviest-organism" target="_blank" rel="noopener noreferrer">Guinness: heaviest organism</a></p>
</section>''',
141:'''<section class="taxonguru-source-comparison">
<h2>자료 비교: 아마존빅토리아수련과 볼리비아빅토리아수련의 기록</h2>
<p>거대한 수련 잎의 크기와 하중 지지 기록은 <em>Victoria amazonica</em>와 <em>Victoria boliviana</em>를 구별해야 정확하게 이해할 수 있습니다.</p>
<figure class="wp-block-table"><table><thead><tr><th>종</th><th>확인된 사실</th><th>주의할 점</th></tr></thead><tbody>
<tr><td><em>Victoria amazonica</em></td><td>오랫동안 세계 최대 수련으로 알려졌으며, 하중을 고르게 분산했을 때 어린아이의 체중을 지탱하는 사례가 소개됩니다.</td><td>다른 종의 하중 시험 기록을 이 종의 결과로 사용하면 안 됩니다.</td></tr>
<tr><td><em>Victoria boliviana</em></td><td>2022년 독립된 종으로 확인되었고, 볼리비아에서 지름 3.2m의 잎이 기록됐습니다. 영국 큐 왕립식물원의 2026년 시연에서는 잎 한 장에 총 102kg의 하중을 가했습니다.</td><td>102kg에는 사람뿐 아니라 장화·장비와 하중 분산용 받침대도 포함됩니다. 일반적인 안전 허용하중은 아닙니다.</td></tr>
</tbody></table></figure>
<p>확인 자료: <a href="https://www.kew.org/plants/victoria-boliviana" target="_blank" rel="noopener noreferrer">큐 왕립식물원 종 정보</a> · <a href="https://www.kew.org/about-us/press-media/waterlily-weigh-off-2026" target="_blank" rel="noopener noreferrer">2026년 하중 시연 보도자료</a> · <a href="https://www.kew.org/read-and-watch/new-giant-waterlily-victoria-boliviana-discovered-at-kew" target="_blank" rel="noopener noreferrer">종 분류 연구 배경</a></p>
</section>''',
775:'''<section class="taxonguru-source-comparison">
<h2>Evidence comparison: Victoria amazonica versus Victoria boliviana</h2>
<p>Claims about giant waterlily leaf diameter and weight-bearing demonstrations must distinguish two different species, <em>Victoria amazonica</em> and <em>Victoria boliviana</em>.</p>
<figure class="wp-block-table"><table><thead><tr><th>Species</th><th>Documented finding</th><th>Interpretation</th></tr></thead><tbody>
<tr><td><em>Victoria amazonica</em></td><td>Historically considered the largest waterlily. Kew describes a leaf supporting a small child when the load is spread evenly.</td><td>Weight records for other Victoria species must not be presented as results for V. amazonica.</td></tr>
<tr><td><em>Victoria boliviana</em></td><td>Recognised as a distinct species in 2022. A 3.2 m leaf was recorded in Bolivia, and a Kew demonstration in 2026 supported a total load of 102 kg.</td><td>The 102 kg included the person, gear, waders and a plastic base. It is a specific demonstration, not a general safe-load rating.</td></tr>
</tbody></table></figure>
<p>Sources: <a href="https://www.kew.org/plants/victoria-boliviana" target="_blank" rel="noopener noreferrer">Kew species profile</a> · <a href="https://www.kew.org/about-us/press-media/waterlily-weigh-off-2026" target="_blank" rel="noopener noreferrer">Kew 2026 weight demonstration</a> · <a href="https://www.kew.org/read-and-watch/new-giant-waterlily-victoria-boliviana-discovered-at-kew" target="_blank" rel="noopener noreferrer">Kew taxonomic history</a></p>
</section>'''
}

def api(method,path,**kw):
 r=SESSION.request(method,f"{BASE}/wp-json/wp/v2/{path}",timeout=75,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {path}: HTTP {r.status_code}, {r.text[:200]}")
 return r.json()

def main():
 results=[]
 for pid,addition in FACTS.items():
  try:
   post=api("GET",f"posts/{pid}",params={"context":"edit"})
   if post.get("status")!="publish":raise ValueError("Published status changed")
   original=post["content"].get("raw") or post["content"].get("rendered") or ""
   if not original:raise ValueError("No body HTML")
   marker='<section class="taxonguru-source-comparison">'
   if marker in original:
    results.append({"id":pid,"result":"ALREADY_PRESENT"});continue
   first=re.search(r"<h2\b",original,re.I)
   if not first:raise ValueError("No section heading for safe insertion")
   img_before=len(re.findall(r"<img\b",original,re.I))
   refs_before=len(re.findall(r"<li\b[^>]*\bid=['\"]ref-",original,re.I))
   revised=original[:first.start()]+addition+original[first.start():]
   if len(revised)-len(original)!=len(addition):raise ValueError("Unexpected content diff")
   (OUT/f"original_{pid}.json").write_text(json.dumps({
       "id":pid,"title":post.get("title"),"content":original,"modified":post.get("modified"),
   },ensure_ascii=False),encoding="utf-8")
   if APPLY:
    api("POST",f"posts/{pid}",json={"content":revised})
    verified=api("GET",f"posts/{pid}",params={"context":"edit"})
    actual=verified["content"].get("raw") or ""
    if verified["status"]!="publish" or actual.count(marker)!=1:
     raise ValueError("Updated article verification failed")
    if img_before!=len(re.findall(r"<img\b",actual,re.I)):raise ValueError("Image count changed unexpectedly")
    if refs_before!=len(re.findall(r"<li\b[^>]*\bid=['\"]ref-",actual,re.I)):
     raise ValueError("Original reference IDs changed")
   result={"id":pid,"result":"UPDATED" if APPLY else "DRY_RUN","added_chars":len(addition)}
  except Exception as exc:result={"id":pid,"result":"ERROR","error":str(exc)}
  results.append(result)
  print("FACTCHECK_ITEM="+json.dumps(result,ensure_ascii=False),flush=True)
 (OUT/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
 print("FACTCHECK_SUMMARY="+json.dumps({"apply":APPLY,"updated":sum(x["result"]=="UPDATED" for x in results),"errors":sum(x["result"]=="ERROR" for x in results)},ensure_ascii=False),flush=True)
 return 1 if any(x["result"]=="ERROR" for x in results) else 0

if __name__=="__main__":
 raise SystemExit(main())
