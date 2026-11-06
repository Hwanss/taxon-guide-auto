"""Read-only targeted review of 8 active posts before source-based changes.

Only prints titled paragraphs with numeric/source claims and reference domains;
never modifies WordPress. Saves original eight post payloads as a private artifact.
"""
import os,re,json,html
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
OUT=Path("audit_output/science_batch5_inspection");OUT.mkdir(parents=True,exist_ok=True)
TARGET={
 164:(r"물|힘|교합|치|메갈|이빨|24|18|20|무게|멸종|고래","megalodon ko"),
 709:(r"bite|force|newton|ton|length|24|20|15|mass|weight|megalodon|extinct","megalodon en"),
 170:(r"혈액|적혈구|헤모글로빈|온도|심장|산소|남극|진화|빙어|손실","icefish ko"),
 691:(r"hemoglobin|oxygen|heart|blood|icefish|red cell|temperature|gene","icefish en"),
 180:(r"먹이|사냥|뱀파이어|필라멘트|산소|점액|심해|marine snow|포식","vampire squid ko"),
 661:(r"food|prey|feed|marine snow|filament|oxygen|vampire|predator","vampire squid en"),
 35:(r"15종|3종|16종|모방|포식자|흉내|바다뱀|문어|관찰","mimic octopus ko"),
 829:(r"15|16|3 |mimic|study|snake|flounder|lionfish|octopus","mimic octopus en"),
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
  for i,(raw,t) in enumerate(candidates[:18]):
   print("EVIDENCE_PARA",pid,i,"TEXT",t[:560],"HTML",raw[:750].replace("\n"," "),flush=True)
  print("INSPECT_COUNTS",pid,"PARA",len(pars),"MATCHED",len(candidates),
     "REFS",re.findall(r'<li\s+id=["\\x27]ref-(\d+)',c,re.I)[:15],flush=True)
if __name__=="__main__":main()
