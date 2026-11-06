"""Read-only targeted review of 8 active posts before source-based changes.

Only prints titled paragraphs with numeric/source claims and reference domains;
never modifies WordPress. Saves original eight post payloads as a private artifact.
"""
import os,re,json,html
from pathlib import Path
import requests
BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
S=requests.Session();S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
OUT=Path("audit_output/next8_inspection");OUT.mkdir(parents=True,exist_ok=True)
TARGET={
 162:(r"13|12|20m|대왕|암모니|오징어|향유고래|길이|눈", "giant squid ko"),
 715:(r"13|12|20.m|giant|squid|ammon|length|sperm|eyes|ball", "giant squid en"),
 176:(r"용혈|안개|수분|약|항균|치료|임상|수지|효능|보전", "dragon blood tree ko"),
 673:(r"resin|medicine|heal|antimicrob|antibiot|fog|drip|pharmac|treat|sap", "dragon blood tree en"),
 231:(r"입|턱|3.14|3\.1|고블린|속도|심해|포식|돌출|사냥", "goblin shark ko"),
 460:(r"jaw|3.14|3\.1|sling|speed|protrus|feeding|prey|2008|2011", "goblin shark en"),
 209:(r"황금|피보나치|나선|부력|껍데기|기체|방|앵무조개|20년", "nautilus ko"),
 401:(r"golden|fibonacci|spiral|chamber|float|buoyan|nautilus|30|20.year", "nautilus en"),
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
  for i,(raw,t) in enumerate(candidates[:16]):
   print("EVIDENCE_PARA",pid,i,"TEXT",t[:560],"HTML",raw[:750].replace("\n"," "),flush=True)
  print("INSPECT_COUNTS",pid,"PARA",len(pars),"MATCHED",len(candidates),
     "REFS",re.findall(r'<li\s+id=["\\x27]ref-(\d+)',c,re.I)[:15],flush=True)
if __name__=="__main__":main()
