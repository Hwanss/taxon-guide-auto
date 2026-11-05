import os,re,requests,json,html
s=requests.Session();s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
b=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
for page in (1,2):
 r=s.get(b+"/wp-json/wp/v2/posts",params={"context":"edit","status":"publish","per_page":100,"page":page},timeout=80)
 if r.status_code==400:break
 r.raise_for_status()
 for p in r.json():
  raw=p["content"].get("raw") or p["content"].get("rendered") or ""
  title=html.unescape(re.sub("<[^>]+>","",p["title"].get("raw") or p["title"].get("rendered") or ""))
  if re.search("Armillaria|뽕나무|fungus|largest living organism|지상 최대",title,re.I) or ".mw-parser-output" in raw:
   print("ISSUE_POST",p["id"],"TITLE",title,"URL",p["link"],"CSS",raw.count(".mw-parser-output"))
   for pat in ("largest living organism","지상 최대","세계 최대","가장 큰 단일 생명체",".mw-parser-output"):
    m=re.search(re.escape(pat),raw,re.I)
    if m: print("MATCH",pat,raw[max(0,m.start()-130):m.start()+300].replace("\n"," "))
