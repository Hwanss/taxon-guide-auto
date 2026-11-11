"""Four curated, verified topic comparison links: Rafflesia vs titan arum, KO and EN.
Backup and preview before any edit; inspect published state and exact edited content.
"""
import os,re,html,json,requests
from pathlib import Path
ROOT=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("RELATED_LINKS_APPLY","false").lower()=="true"
EXPECTED=json.loads(os.getenv("RELATED_LINKS_EXPECTED","{}"))
DIR=Path("audit_output/corpse_flower_crosslinks")
DIR.mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
PAIR={
137:(24,"ko","라플레시아는 하나의 거대한 꽃입니다. 반면 비슷한 악취로 시체꽃이라 불리는 {a}은 작은 꽃 여러 개가 모인 꽃차례입니다. 같은 크기 기록으로 비교하면 안 됩니다."),
24:(137,"ko","타이탄 아룸은 여러 작은 꽃이 모인 꽃차례인 반면 {a}는 하나의 단일 꽃으로서 최대 크기 기록을 갖습니다. 악취의 공통점보다 식물학적 구조의 차이가 중요합니다."),
787:(864,"en","Rafflesia is a single enormous flower, whereas the similarly smelly {a} is an inflorescence containing many small flowers. Their size records measure fundamentally different structures."),
864:(787,"en","Titan arum has a giant unbranched inflorescence, not a single flower. By contrast, {a} holds the record for the largest individual flower. Their distinctive records should not be conflated.")
}
SOURCE={
137:"https://www.kew.org/plants/titan-arum",
24:"https://www.loc.gov/everyday-mysteries/categories/botany/item/what-is-the-largest-flower-in-the-world/",
787:"https://www.kew.org/plants/titan-arum",
864:"https://www.loc.gov/everyday-mysteries/categories/botany/item/what-is-the-largest-flower-in-the-world/"
}
LABEL={137:"타이탄 아룸의 꽃차례",24:"라플레시아 아르놀디",787:"titan arum",864:"Rafflesia arnoldii"}
def wp(method,path,**kw):
 r=S.request(method,ROOT+"/wp-json/wp/v2/"+path,timeout=75,**kw)
 r.raise_for_status()
 return r.json()
def insert(raw,para,lang):
 headings=list(re.finditer(r"<h2\b[^>]*>.*?</h2>",raw,re.I|re.S))
 labels=[html.unescape(re.sub(r"<[^>]*>","",h.group())).strip().lower() for h in headings]
 if lang=="ko":
  indices=[i for i,t in enumerate(labels) if "자료와 편집 원칙" in t]
 else:
  indices=[i for i,t in enumerate(labels) if "editorial" in t and "source" in t]
 if len(indices)!=1:
  indices=[i for i,t in enumerate(labels) if t in ("참고자료","references","sources")]
 if len(indices)!=1:raise ValueError("No safe unique heading to insert before: "+str(labels))
 pos=headings[indices[0]].start()
 return raw[:pos]+para+"\n"+raw[pos:]
def main():
 posts={id:wp("GET",f"posts/{id}",params={"context":"edit"}) for id in PAIR}
 changes={}
 for id,(peer,lang,fmt) in PAIR.items():
  p,q=posts[id],posts[peer]
  if p["status"]!="publish" or q["status"]!="publish":
   raise ValueError("Only already-published articles are eligible")
  if ("/en/" in p["link"])!=(lang=="en") or ("/en/" in q["link"])!=(lang=="en"):
   raise ValueError("Cross-language link refused")
  src=p["content"].get("raw")
  if not src:raise ValueError("Authenticated original missing")
  (DIR/f"original_{id}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8")
  if "tg-context-compare" in src or q["link"] in src:
   raise ValueError(f"Duplicate contextual link risk: {id}")
  a='<a href="'+html.escape(q["link"],quote=True)+'">'+html.escape(LABEL[id])+'</a>'
  body=fmt.format(a=a)
  anchor='<p class="tg-context-compare"><strong>'+("추가 비교: " if lang=="ko" else "Related comparison: ")+'</strong>'+body+' '+('<a href="'+SOURCE[id]+'" target="_blank" rel="noopener noreferrer">'+("식물원·기관 근거" if lang=="ko" else "botanical source")+'</a>')+'</p>'
  changed=insert(src,anchor,lang)
  if len(re.findall(r"<img\b",src,re.I))!=len(re.findall(r"<img\b",changed,re.I)):raise ValueError("Images changed")
  if len(re.findall(r"<h2\b",src,re.I))!=len(re.findall(r"<h2\b",changed,re.I)):raise ValueError("Headings changed")
  if changed.count('class="tg-context-compare"')!=1:raise ValueError("Duplicate insertion")
  (DIR/f"proposal_{id}.html").write_text(changed,encoding="utf-8")
  changes[id]={"modified":p["modified"],"original":src,"new":changed,"link":p["link"],"peer":q["link"]}
 result={"apply":APPLY,"backups":len(changes),"modified":{str(id):d["modified"] for id,d in changes.items()},"result":"PREVIEW_OK"}
 if APPLY:
  if EXPECTED!={str(id):d["modified"] for id,d in changes.items()}:
   raise ValueError("Exact prior modified timestamp map required before writing")
  done=[]
  for id,d in changes.items():
   wp("POST",f"posts/{id}",json={"content":d["new"]})
   actual=wp("GET",f"posts/{id}",params={"context":"edit"})
   if actual["status"]!="publish" or actual["content"].get("raw")!=d["new"]:
    raise RuntimeError(f"Post {id}: exact WordPress readback failure")
   public=requests.get(d["link"],timeout=40)
   rest=requests.get(ROOT+f"/wp-json/wp/v2/posts/{id}",timeout=40)
   if public.status_code!=200 or rest.status_code!=200 or d["peer"] not in rest.json()["content"]["rendered"]:
    raise RuntimeError(f"Post {id}: public validation failed")
   done.append(id)
  result["result"]="LIVE_UPDATED_AND_VERIFIED"
  result["public_validated"]=done
 (DIR/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print("CROSS_LINK_RESULT="+json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
