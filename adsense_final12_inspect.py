"""Read-only targeted review of 8 active posts before source-based changes.

Only prints titled paragraphs with numeric/source claims and reference domains;
never modifies WordPress. Saves original eight post payloads as a private artifact.
"""
import os,re,json,html
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
OUT=Path("audit_output/final12_inspection");OUT.mkdir(parents=True,exist_ok=True)
TARGET={
 123:(r"케찰|목|높이|날개|기린|비행|km|kg|등뼈|지상|착륙|거대", "Quetzalcoatlus ko"),
 807:(r"Quetzal|m|kg|wingspan|height|takeoff|flight|giraffe|landing|giant", "Quetzalcoatlus en"),
 141:(r"빅토리아|수련|amazonica|boliviana|kg|잎|102|하중|3.2|부력|강도", "Victoria ko"),
 775:(r"victoria|amazonica|boliviana|kg|leaf|102|weight|load|3.2|float|rib", "Victoria en"),
 178:(r"세쿼이아|부피|높이|몸무게|질량|셔먼|m³|2000|2500|나이|탄소", "Sequoiadendron ko"),
 667:(r"sequoia|volume|weight|mass|sherman|m3|m³|ton|age|2,000|carbon", "Sequoiadendron en"),
 221:(r"균|꿀버섯|아르밀|ostoyae|km|무게|해초|largest|largest|사망", "Armillaria ko"),
 434:(r"fungus|Armillaria|ostoyae|km|mass|weight|organism|seagrass|largest", "Armillaria en"),
 227:(r"puya|라이몬디|100년|28년|80년|꽃|한번|번식|보전", "Puya ko"),
 449:(r"puya|century|28|flower|once|100|80|pollination|endangered", "Puya en"),
 254:(r"수정난풀|약|복용|안전|독|치료|그라야|민속|암|효능|2025", "Ghost pipe ko"),
 518:(r"ghost pipe|toxic|medical|pain|safety|grayan|clinical|traditional|2025", "Ghost pipe en"),
}
def text(x): return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",x))).strip()
def main():
 for pid,(regex,label) in TARGET.items():
  r=S.get(BASE+"/wp-json/wp/v2/posts/"+str(pid),params={"context":"edit"},timeout=75)
  r.raise_for_status();p=r.json();c=p["content"].get("raw") or p["content"].get("rendered") or ""
  title=p["title"].get("raw") or p["title"].get("rendered") or ""
  excerpt=p["excerpt"].get("raw") or p["excerpt"].get("rendered") or ""
  (OUT/f"original_{pid}.json").write_text(json.dumps({"post":p},ensure_ascii=False),encoding="utf8")
  print("INSPECT_POST",pid,label,"STATUS",p.get("status"),"URL",p.get("link"),"TITLE",title, "EXCERPT",text(excerpt)[:250],flush=True)
  pars=re.findall(r"<(?:p|h[2-4])\b[^>]*>.*?</(?:p|h[2-4])>",c,re.I|re.S)
  candidates=[]
  for para in pars:
   t=text(para)
   if len(t)<65 or len(t)>1250:continue
   if re.search(regex,t,re.I):candidates.append((para,t))
  for i,(raw,t) in enumerate(candidates[:25]):
   print("EVIDENCE_PARA",pid,i,"TEXT",t[:950],"HTML",raw[:450].replace("\n"," "),flush=True)
  print("EXISTING_MARKERS",pid, "source_comparison", c.count("taxonguru-source-comparison"), "puya_growth",c.count("puya-growth-evidence"),"ghost_pipe",c.count("taxonguru-ghost-pipe-research-2025"),flush=True)
  print("INSPECT_COUNTS",pid,"PARA",len(pars),"MATCHED",len(candidates),
     "REFS",re.findall(r'<li\s+id=["\\x27]ref-(\d+)',c,re.I)[:15],flush=True)
if __name__=="__main__":main()
