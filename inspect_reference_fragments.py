import os,re,requests,html
s=requests.Session()
s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
base=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
for pid in (141,164,170,180,209,227,401,449,661,691,709,775):
 r=s.get(f"{base}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=60)
 r.raise_for_status()
 p=r.json();raw=p["content"].get("raw") or p["content"]["rendered"]
 m=re.search(r"<h[2-6][^>]*>\\s*(참고자료|References).*?</h[2-6]>",raw,re.I|re.S)
 ref=raw[m.end():] if m else ""
 print("POST",pid,"STATUS",p["status"],"REF_SAMPLE",ref[:2500].replace("\\n"," "))
