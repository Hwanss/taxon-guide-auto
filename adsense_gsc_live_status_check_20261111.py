"""Read-only current-status comparison for Search Console index discrepancies."""
import json,os,requests
from pathlib import Path
SITE="https://taxonguru.com"
PAIRS={
 "colossal_squid_ko":"colossal-squid-giant-cephalopod",
 "colossal_squid_en":"colossal-squid-facts-and-adaptations",
 "hydnellum_ko":"hydnellum-peckii-devils-tooth",
 "hydnellum_en":"bleeding-tooth-fungus-hydnellum-peckii-guide",
 "rafflesia_en":"rafflesia-arnoldii-worlds-largest-single-flower"
}
def main():
 s=requests.Session()
 s.auth=(os.environ["WP_USER"],os.environ["WP_APP_PASSWORD"])
 out=[]
 for name,slug in PAIRS.items():
  path=('/en/' if name.endswith("_en") else '/')+slug+'/'
  url=SITE+path
  obj={"name":name,"url":url}
  for head,ua in [("normal","Mozilla/5.0 (compatible; TaxonGuru-QA/1.0)"),("google_like","Googlebot/2.1 (+http://www.google.com/bot.html)")]:
   # Simulated UA is only a comparison, not actual Google verification.
   try:
    resp=requests.get(url,headers={"User-Agent":ua},timeout=25,allow_redirects=True)
    obj[head]={"status":resp.status_code,"final_url":resp.url,"bytes":len(resp.content)}
   except requests.RequestException as e:
    obj[head]={"error":type(e).__name__}
  try:
   v=s.get(SITE+"/wp-json/wp/v2/posts",params={"slug":slug,"context":"edit","status":"any"},timeout=30)
   obj["admin_rest_status"]=v.status_code
   if v.status_code==200:
    obj["wordpress"]=[{"id":x.get("id"),"status":x.get("status"),"slug":x.get("slug"),"modified":x.get("modified"),"link":x.get("link")} for x in v.json()]
   else:
    obj["wordpress_response_note"]=v.text[:130].replace("\n"," ")
  except requests.RequestException as e:
   obj["wordpress_error"]=type(e).__name__
  out.append(obj)
 from datetime import datetime,timezone
 report={"audit_time_utc":datetime.now(timezone.utc).isoformat(),"no_write":True,"results":out}
 Path("audit_output/gsc_status_check").mkdir(parents=True,exist_ok=True)
 Path("audit_output/gsc_status_check/current_public_and_post_status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 print("GSC_STATUS_COMPARISON="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
