"""Guarded claim-level fix of published Korean Victoria amazonica article (ID 141).

Preview is mandatory. Applied run requires exact modified time from previous preview.
No changes to images, headings, author, slug, status, publish settings, or AdSense.
"""
from __future__ import annotations
import datetime, html, json, os, re
from pathlib import Path
from urllib.parse import urlsplit
import requests

SITE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("VICTORIA_KO_APPLY","false").lower()=="true"
EXPECTED=os.getenv("VICTORIA_KO_EXPECTED_MODIFIED","").strip()
POST_ID=141
OUT=Path("audit_output/victoria_ko_20261111")
OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
S.headers["User-Agent"]="TaxonGuru-ClaimEvidencePreflight/1.0"

# Revised reference slots: distinct sources that support taxonomy, morphology,
# spines, leaf engineering, and actual floral thermogenesis measurements.
REFS={
 1:("wikipedia.org","https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:605776-1/general-information","Kew Science: Victoria amazonica 종 정보·서식·형태"),
 4:("amazonriverlodge.com","https://www.nparks.gov.sg/florafaunaweb/flora/2/5/2545","싱가포르 국립공원청: 잎 뒷면 가시와 담수 서식 형태"),
 6:("wikipedia.org","https://www.kew.org/about-us/press-media/new-giant-waterlily","큐 왕립식물원: Victoria boliviana 신종 식별"),
 7:("kew.org","https://pmc.ncbi.nlm.nih.gov/articles/PMC8827653/","Science Advances (2022): 빅토리아수련 잎 지지 구조 원논문"),
 9:("kew.org","https://pmc.ncbi.nlm.nih.gov/articles/PMC2803590/","Annals of Botany (2006): 빅토리아수련 꽃의 실제 발열 측정"),
}

def api(method,route,**kwargs):
 r=S.request(method,SITE+"/wp-json/wp/v2/"+route,timeout=75,**kwargs)
 r.raise_for_status()
 return r.json()

def refs(raw):
 results={}
 for m in re.finditer(r'<li\s+id=["\x27]ref-(\d+)["\x27][^>]*>.*?</li>',raw,re.I|re.S):
  n=int(m.group(1))
  if n in results:raise ValueError(f"Duplicate reference marker: {n}")
  results[n]=m.group(0)
 return results

def section(raw,needle):
 headings=list(re.finditer(r"<h2\b[^>]*>.*?</h2>",raw,re.I|re.S))
 matched=[i for i,h in enumerate(headings) if needle in html.unescape(re.sub("<[^>]+>","",h.group()))]
 if len(matched)!=1:raise ValueError(f"Expected exactly one heading '{needle}', got {len(matched)}")
 idx=matched[0]
 start=headings[idx].start()
 end=headings[idx+1].start() if idx+1<len(headings) else len(raw)
 return start,end,headings[idx].end()

def patch(raw):
 initial=refs(raw)
 if sorted(initial)!=list(range(1,10)):raise ValueError(f"Unexpected original ref IDs: {sorted(initial)}")
 out=raw
 for num,(old_host,dest,label) in REFS.items():
  old=initial[num]
  url=re.findall(r'<a\b[^>]*href=["\x27]([^"\x27]+)',old,re.I)
  if len(url)!=1 or old_host not in (urlsplit(html.unescape(url[0])).hostname or "").lower():
   raise ValueError(f"ref-{num} changed from expected host; investigate, do not override")
  new=(f'<li id="ref-{num}"><a href="{html.escape(dest,quote=True)}" target="_blank" '
       f'rel="noopener noreferrer">{html.escape(label)}</a> — 근거 검증 2026-11-11</li>')
  if out.count(old)!=1:raise ValueError(f"ref-{num}: original fragment not unique")
  out=out.replace(old,new,1)

 # Remove classification-only reference [2] from unrelated mechanical history.
 # Record exactly how many cited markers were removed, refusing if none.
 removed={}
 for key in ("자연이 만든 공학적 구조","발열 작용과 딱정벌레"):
  a,b,_=section(out,key)
  fragment=out[a:b]
  # Link is always associated with a numbered marker; only remove that marker.
  def drop_ref_two(match):
   removed[key]=removed.get(key,0)+1
   return ""
  revised=re.sub(
    r'\s*,?\s*<sup\b[^>]*>\s*<a\b[^>]*href=["\x27]#ref-2["\x27][^>]*>\s*\[2\]\s*</a>\s*</sup>',
    drop_ref_two,fragment,flags=re.I|re.S)
  out=out[:a]+revised+out[b:]
  if not removed.get(key):
   raise ValueError(f"No protected ref-2 marker found in {key}; inspect actual markup")

 # Add a claim-specific primary-data explanation rather than repeating source links.
 start,end,after_heading=section(out,"발열 작용과 딱정벌레")
 study=(
  '<p><strong>원논문 수치와 해석:</strong> Seymour와 Matthews(2006)는 가이아나 현장의 '
  '아마존빅토리아수련 꽃 20개에서 온도를, 꽃 5개에서 호흡을 관찰했습니다. '
  '첫째 날 밤 꽃 내부 온도는 29.3~34.7°C, 주변 공기 온도는 23.5~25.2°C로 측정됐습니다. '
  '이는 모든 꽃이 언제나 주변보다 정확히 10°C 뜨거워진다는 뜻이 아닙니다. '
  '연구진은 꽃의 열이 향기 발산을 돕는 것 외에도 방문 딱정벌레의 활동 에너지 부담을 '
  '줄일 수 있다는 해석을 제안했습니다. '
  '<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC2803590/" target="_blank" '
  'rel="noopener noreferrer">Annals of Botany 원논문(2006)</a>을 참고했습니다.</p>')
 out=out[:after_heading]+"\n"+study+out[after_heading:]
 # Softened protection claim based on source's "possibly defence" phrasing.
 old="아마존빅토리아수련은 전신을 감싸고 있는 날카로운 가시를 이용해 초식동물의 접근이나 포식 행위를 효과적으로 차단합니다"
 new="아마존빅토리아수련의 날카로운 가시는 수생 초식동물의 섭식을 방해하는 방어 구조로 해석됩니다. 다만 모든 포식 행위를 완전히 차단하는 것은 아닙니다"
 if out.count(old)!=1:raise ValueError("Protected spines description missing or repeated")
 out=out.replace(old,new,1)
 # Avoid implying all of species V. amazonica are always three metres across.
 old2="지름이 3m에 이르는 거대한 잎이 수면 위에서"
 if out.count(old2)!=1:raise ValueError("Protected leaf-diameter phrasing missing or repeated")
 out=out.replace(old2,"지름이 2.5m 이상 자라기도 하는 거대한 잎이 수면 위에서",1)
 if sorted(refs(out))!=sorted(initial):raise ValueError("Numbered reference IDs changed")
 if len(re.findall(r"<img\b",out,re.I))!=len(re.findall(r"<img\b",raw,re.I)):raise ValueError("Image count changed")
 if len(re.findall(r"<h2\b",out,re.I))!=len(re.findall(r"<h2\b",raw,re.I)):raise ValueError("H2 structure changed")
 if len(out)<len(raw)*.97:raise ValueError("Suspicious content shrinkage")
 if "원논문 수치와 해석" not in out:raise ValueError("Evidence paragraph missing")
 if any(dest not in refs(out)[num] for num,(_,dest,_) in REFS.items()):
  raise ValueError("A rewritten source was not retained")
 return out,removed

def main():
 p=api("GET",f"posts/{POST_ID}",params={"context":"edit"})
 if p.get("status")!="publish":raise ValueError("Article status changed; refuse write")
 raw=p.get("content",{}).get("raw")
 if not raw:raise ValueError("Raw edit article not accessible")
 pre={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "id":POST_ID,"status":p["status"],"modified":p["modified"],
      "link":p["link"],"title":p.get("title"),"excerpt":p.get("excerpt"),
      "featured_media":p.get("featured_media"),"content":raw}
 (OUT/"original_post_141.json").write_text(json.dumps(pre,ensure_ascii=False,indent=2),encoding="utf8")
 corrected,removed=patch(raw)
 (OUT/"proposed_article_141.html").write_text(corrected,encoding="utf8")
 result={"id":POST_ID,"apply":APPLY,"modified_before":p["modified"],
         "preview_reference_ids":sorted(REFS),"removed_mislinked_citations":removed,
         "backed_up":True,"original_chars":len(raw),"new_chars":len(corrected),
         "result":"PREVIEW_OK"}
 if APPLY:
  if not EXPECTED or p["modified"]!=EXPECTED:
   raise ValueError(f"Refuse write: expected modified={EXPECTED}, live={p['modified']}")
  api("POST",f"posts/{POST_ID}",json={"content":corrected})
  verify=api("GET",f"posts/{POST_ID}",params={"context":"edit"})
  if verify["status"]!="publish" or verify["content"].get("raw")!=corrected:
   raise ValueError("WordPress content readback differs or article unpublished")
  public=requests.get(p["link"],timeout=45,headers={"Cache-Control":"no-cache"})
  rest=requests.get(SITE+f"/wp-json/wp/v2/posts/{POST_ID}",timeout=45)
  if public.status_code!=200 or rest.status_code!=200:
   raise ValueError(f"Public page / REST status mismatch: {public.status_code}/{rest.status_code}")
  rendered=rest.json()["content"]["rendered"]
  for _,url,_ in REFS.values():
   if url not in rendered:raise ValueError(f"Reference not visible publicly: {url}")
  result["result"]="LIVE_UPDATED_AND_VERIFIED"
  result["public_http"]=public.status_code
 (OUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
 print("VICTORIA_KO_RESULT="+json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
 main()
