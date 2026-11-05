import os,re,json,html
from pathlib import Path
from urllib.parse import urlsplit
import requests

root=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
apply=os.getenv("ADSENSE_CITATION_APPLY","false").lower()=="true"
s=requests.Session()
s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
plan=json.loads(Path("adsense_reference_repair_manifest.json").read_text())
out=Path("audit_output/citation_repair");out.mkdir(parents=True,exist_ok=True)
bad={"facebook.com","reddit.com"}
def host(url): return (urlsplit(html.unescape(url)).hostname or "").lower().removeprefix("www.")
def api(method,path,**kw):
 r=s.request(method,f"{root}/wp-json/wp/v2/{path}",timeout=80,**kw)
 r.raise_for_status()
 return r.json()
def fix_li(match,refs):
 li=match.group(0)
 num=match.group(1)
 if num not in refs:return li
 old=re.search(r'href="([^"]+)"',li)
 if not old or host(old.group(1)) not in bad: raise ValueError(f"Reference {num} no longer points to an audited social site")
 url=refs[num];dom=host(url)
 li=li.replace(old.group(1),html.escape(url,quote=True),1)
 li=re.sub(r'(<a\b[^>]*>)[^<]*(</a>)',lambda m:m.group(1)+dom+m.group(2),li,count=1)
 li=re.sub(r'(?:www\.)?(?:facebook\.com|reddit\.com)',dom,li,flags=re.I)
 li=re.sub(r'((?:확인일|accessed)\s+)\d{4}-\d{2}-\d{2}',r'\g<1>2026-11-05',li)
 return li
ko_old="따라서 판을 활용해 무게가 넓게 분산되기만 한다면, 아이는 물론 성인의 체중까지 가뿐하게 견뎌내는 놀라운 지지력을 발휘할 수 있습니다"
ko_new="잎의 지지력은 종과 개별 잎의 상태, 하중 분산 방식에 따라 달라집니다. 큐 왕립식물원은 아마존빅토리아수련(Victoria amazonica)이 고르게 분산된 어린아이의 체중을 지탱할 수 있다고 설명합니다. 한편 2026년 102kg을 지탱한 시연은 다른 종인 Victoria boliviana로 이루어진 시험이므로 두 종의 기록을 혼동해서는 안 됩니다"
en_old="When load is properly spread using a board, a single leaf can readily support the full weight of a child or an adult weighing over 100 kilograms"
en_new="Weight capacity depends on species, leaf condition, and even distribution of the load. Kew describes Victoria amazonica as able to support a small child when weight is spread evenly. Its 2026 demonstration of a leaf supporting 102 kg involved a different species, Victoria boliviana, and should not be attributed to Victoria amazonica"
results=[]
for sid,refs in plan.items():
 try:
  post=api("GET",f"posts/{sid}",params={"context":"edit"})
  if post["status"]!="publish":raise ValueError("Post is no longer published")
  raw=post["content"].get("raw") or post["content"].get("rendered") or ""
  if not raw:raise ValueError("No original HTML")
  Path(out/f"original_{sid}.json").write_text(json.dumps({"id":sid,"content":raw,"status":post["status"],"modified":post["modified"]},ensure_ascii=False),encoding="utf8")
  count=[0]
  def patch(m):
   if m.group(1) in refs:count[0]+=1
   return fix_li(m,refs)
  updated=re.sub(r'<li\s+id="ref-(\d+)"[^>]*>.*?</li>',patch,raw,flags=re.I|re.S)
  if count[0]!=len(refs):raise ValueError(f"Ref mismatch: {count[0]}/{len(refs)}")
  if sid in ("141","775"):
   old,new=(ko_old,ko_new) if sid=="141" else (en_old,en_new)
   if old not in updated:raise ValueError("Exact species-specific claim not found")
   updated=updated.replace(old,new,1)
  if len(updated)<len(raw)*0.95:raise ValueError("Unexpected HTML size loss")
  if apply:
   api("POST",f"posts/{sid}",json={"content":updated})
   after=api("GET",f"posts/{sid}",params={"context":"edit"})
   actual=after["content"].get("raw") or ""
   if after["status"]!="publish" or not all(url in html.unescape(actual) for url in refs.values()):
    raise ValueError("Post-update verification failed")
  result={"id":sid,"status":"UPDATED" if apply else "DRY_RUN","ref_count":count[0],"updated_html_chars":len(updated)}
 except Exception as e:
  result={"id":sid,"status":"ERROR","reason":str(e)}
 results.append(result)
 print(json.dumps(result,ensure_ascii=False),flush=True)
(out/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf8")
if any(x["status"]=="ERROR" for x in results):raise SystemExit(1)
print("ALL_CITATION_REPAIRS_VERIFIED",len(results),"APPLIED",apply)
