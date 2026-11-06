"""Add a genuinely useful, sourced TaxonGuru reading guide and visible navigation.

Default: read-only preview. On APPLY, creates one editorial page and links it to
the existing footer and homepage sidebar. Moves the empty recent-comments widget
out of sidebar-1 without deletion; keeps backups of full original sidebar/menu.
No AdSense requests or automated editorial sign-off.
"""
from __future__ import annotations
import os,json,re
from pathlib import Path
from datetime import datetime,timezone
import requests
from bs4 import BeautifulSoup

BASE=os.getenv("WP_SITE_URL","https://taxonguru.com").rstrip("/")
APPLY=os.getenv("READER_GUIDE_APPLY","false").lower()=="true"
USER=os.environ["WP_USER"]; PASS=os.environ["WP_APP_PASSWORD"]
OUT=Path("audit_output/reader_guide");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.auth=(USER,PASS);S.headers["User-Agent"]="TaxonGuruReaderGuide/1.0"
SLUG="reading-guide"
PAGE_TITLE="TaxonGuru 주제별 읽기 길잡이 | Start Here"
MARKER="taxonguru-reader-guide-v1"
NAV_TITLE="주제별 읽기 안내 / Start Here"
LINK=BASE+"/"+SLUG+"/"
def a(path,label,lang="ko"):
 return '<a href="'+BASE+path+'" lang="'+lang+'">'+label+'</a>'

# Curated scientific synthesis is not a regenerated variant of any single article.
# Each reading path explains what two or more related articles teach together.
BODY=f'''
<div id="{MARKER}">
<p><strong>처음 오셨나요?</strong> TaxonGuru는 생물의 크기, 진화, 극한 환경 적응, 번식과 행동을 다룹니다. 이 페이지는 글을 단순 나열하지 않고, 자주 혼동되는 개념을 비교한 다음 적절한 글로 안내합니다. 각 글에는 원자료를 찾을 수 있는 참고문헌이 있습니다.</p>
<p><a href="#read-korean">한국어로 읽기</a> · <a href="#read-english" lang="en">Read in English</a> · {a("/editorial-policy/","편집 및 팩트체크 정책")}</p>
<h2 id="read-korean">어디부터 읽을까요? 다섯 가지 과학 질문</h2>
<h3>1. ‘가장 크다’는 어떤 기준일까요?</h3>
<p>크기 기록을 비교할 때는 <strong>면적·높이·줄기 부피·질량</strong>을 구분해야 합니다. 오리건의 거대 버섯은 균류의 넓이 기록, 제너럴 셔먼은 나무의 줄기 부피 기록에 해당합니다. 아마존빅토리아수련은 2022년 새 종으로 구분된 볼리비아빅토리아수련과 혼동하지 않아야 합니다. 같은 ‘세계 최대’라도 기록이 서로 다른 이유입니다.</p>
<ul><li>{a("/armillaria-ostoyae-honey-mushroom-giant/","거대 꿀버섯 — 면적과 개체의 기준")}</li>
<li>{a("/giant-sequoia-largest-tree/","자이언트 세쿼이아 — 줄기 부피의 기준")}</li>
<li>{a("/victoria-amazonica-giant-lily/","빅토리아수련 — 종 구분과 잎의 하중 기록")}</li></ul>
<h3>2. ‘살아있는 화석’은 진화가 멈췄다는 뜻일까요?</h3>
<p>실러캔스의 오래된 계통이 현대 개체까지 이어진다고 해서 그 종이 수억 년 동안 전혀 변하지 않았다는 뜻은 아닙니다. 틱타알릭은 물고기와 사지동물의 특징을 함께 보여주지만 오늘날 육상동물의 직접 조상이라고 단정할 수 없습니다. 시조새의 깃털과 골격 역시 <strong>진화의 가지와 형질 변화</strong>를 읽는 근거입니다.</p>
<ul><li>{a("/coelacanth-living-fossil/","실러캔스 — ‘살아있는 화석’의 의미")}</li>
<li>{a("/tiktaalik-fishapod-evolution/","틱타알릭 — 수중에서 육상으로의 형질 변화")}</li>
<li>{a("/archaeopteryx-dinosaur-bird-transition/","시조새 — 공룡·조류의 형질 비교")}</li></ul>
<h3>3. 극한 환경에서 산다는 것이 모든 위험에 강하다는 뜻일까요?</h3>
<p>남극의 아이스피시는 헤모글로빈이 없는 혈액과 저온 환경에 적응했고, 열수분출구의 거대 튜브벌레는 공생 미생물의 화학합성을 이용합니다. 거북곰벌레의 건조 내성은 특정 상태와 조건에서 작동합니다. <strong>극한 적응은 특정 환경에 대한 생물학적 해법</strong>이지, 모든 열·냉기·방사선에서 무제한 생존한다는 뜻은 아닙니다.</p>
<ul><li>{a("/antarctic-icefish-transparent-blood/","남극 아이스피시 — 산소 운반")}</li>
<li>{a("/giant-tube-worm-chemosynthesis/","열수분출구 튜브벌레 — 화학합성과 공생")}</li>
<li>{a("/echiniscus-testudo-tardigrade/","거북곰벌레 — 건조 내성의 조건")}</li></ul>
<h3>4. ‘세계 최대 꽃’과 ‘거대한 꽃차례’는 같은 것일까요?</h3>
<p>라플레시아는 하나의 큰 꽃을 만들지만, 타이탄 아룸(시체꽃)의 거대한 구조는 수많은 작은 꽃이 모인 <strong>꽃차례</strong>입니다. 푸야 라이몬디의 수십 년에 걸친 성장은 일생에 한 번 일어나는 개화와 연결됩니다. 기록을 확인할 때는 꽃 한 송이인지 꽃차례인지, 개화 시기와 수명 중 어느 값을 비교하는지 살펴보세요.</p>
<ul><li>{a("/rafflesia-arnoldii-largest-flower/","라플레시아 — 단일 꽃")}</li>
<li>{a("/corpse-flower-giant-stinker/","타이탄 아룸 — 꽃차례와 악취")}</li>
<li>{a("/puya-raimondii-century-bloom-andes-giant/","푸야 라이몬디 — 일생에 한 번의 개화")}</li></ul>
<h3>5. 동물의 놀라운 행동은 어디까지 관찰로 입증됐을까요?</h3>
<p>흉내문어는 여러 동물의 모습을 연상시키는 행동을 보이지만, 정확히 3종 또는 15종만 흉내 낸다고 결론내리는 것은 무리입니다. 뱀파이어오징어의 먹이·방어 행동 역시 실제 심해 관찰과 논문을 중심으로 해석해야 합니다. <strong>관찰된 사실과 생물학적 기능을 추정한 가설을 구분</strong>하며 읽어보세요.</p>
<ul><li>{a("/mimic-octopus-master-disguise/","흉내문어 — 관찰된 모방과 속설")}</li>
<li>{a("/vampire-squid-deep-sea-mystery/","뱀파이어오징어 — 심해 먹이와 방어")}</li></ul>
<h2>과학 기사를 검증하면서 읽는 방법</h2>
<ol><li>정확한 <strong>학명</strong>이 등장하는지 확인합니다. 이름이 비슷한 생물도 서로 다른 종일 수 있습니다.</li>
<li>‘최대·최초·유일’ 같은 표현 뒤의 <strong>측정 기준과 연도</strong>를 봅니다.</li>
<li>기사의 참고문헌이 실제로 그 주장을 뒷받침하는지 원문에서 대조합니다.</li>
<li><strong>관찰, 실험 결과, 추정, 아직 논쟁 중인 가설</strong>을 구분합니다.</li>
<li>오류를 찾으시면 {a("/contact-and-corrections/","문의 및 정정")} 페이지로 글 주소와 근거를 보내 주세요.</li></ol>
<h2>확인 가능한 대표 원자료</h2>
<p><a href="https://www.nps.gov/seki/learn/nature/largest-trees-in-world.htm" target="_blank" rel="noopener noreferrer">미국 국립공원관리청: 세계 최대 나무</a> · <a href="https://www.kew.org/plants/victoria-boliviana" target="_blank" rel="noopener noreferrer">큐 왕립식물원: 볼리비아빅토리아수련</a> · <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC1088805/" target="_blank" rel="noopener noreferrer">흉내문어 현장 관찰 논문</a></p>
<hr>
<h2 id="read-english" lang="en">Start here: five science questions</h2>
<p lang="en">Browse the Korean and English articles by scientific question rather than by popularity. Each path links related topics and clarifies a distinction that can be overlooked when reading only one article.</p>
<h3 lang="en">1. What does 'the largest' actually measure?</h3>
<p lang="en">Area, height, trunk volume and mass measure different things. Oregon's giant fungus, the General Sherman tree and Victoria waterlilies hold distinct types of records. Never transfer a size or leaf-load result from one species to another.</p>
<ul><li>{a("/en/largest-living-organism-armillaria-ostoyae-fungus/","Humongous fungus","en")}</li><li>{a("/en/giant-sequoia-mass-fire-ecology-and-survival/","Giant sequoia","en")}</li><li>{a("/en/victoria-amazonica-giant-water-lily-facts/","Victoria amazonica","en")}</li></ul>
<h3 lang="en">2. Does 'living fossil' mean evolution stopped?</h3>
<p lang="en">Coelacanth lineages, Tiktaalik fossils and Archaeopteryx traits illuminate different branches of evolutionary history. Shared characteristics do not prove that a fossil species was the direct ancestor of every living descendant.</p>
<ul><li>{a("/en/west-indian-ocean-coelacanth-biology-evolution/","Coelacanth","en")}</li><li>{a("/en/tiktaalik-roseae-devonian-fishapod-evolution/","Tiktaalik","en")}</li><li>{a("/en/archaeopteryx-lithographica-avian-evolution-flight/","Archaeopteryx","en")}</li></ul>
<h3 lang="en">3. Are extremophiles indestructible?</h3>
<p lang="en">Icefish, hydrothermal vent tubeworms and tardigrades demonstrate different adaptations to cold, chemical energy and drying. Each adaptation works under particular physiological and environmental conditions.</p>
<ul><li>{a("/en/ocellated-icefish-antarctic-adaptation-chionodraco-rastrospinosus/","Ocellated icefish","en")}</li><li>{a("/en/giant-tubeworm-riftia-pachyptila-hydrothermal-vents/","Giant tubeworm","en")}</li><li>{a("/en/echiniscus-testudo-armored-turtle-water-bear/","Turtle tardigrade","en")}</li></ul>
<h3 lang="en">4. Is a giant flower the same as a giant inflorescence?</h3>
<p lang="en">Rafflesia's single flower and the titan arum's inflorescence are not the same botanical structure. Puya raimondii illustrates yet another life-history strategy: a long-lived plant that typically flowers only once.</p>
<ul><li>{a("/en/rafflesia-arnoldii-worlds-largest-single-flower/","Rafflesia","en")}</li><li>{a("/en/understanding-amorphophallus-titanum-titan-arum/","Titan arum","en")}</li><li>{a("/en/puya-raimondii-queen-of-the-andes/","Puya raimondii","en")}</li></ul>
<h3 lang="en">5. What was observed, and what remains a hypothesis?</h3>
<p lang="en">Mimic-octopus forms have been documented in field studies, but a fixed number of mimicked species is not established. Vampire-squid feeding claims should likewise be compared with observations rather than repeated myths.</p>
<ul><li>{a("/en/mimic-octopus-disguise-facts-and-myth/","Mimic octopus","en")}</li><li>{a("/en/vampyroteuthis-infernalis-vampire-squid-facts/","Vampire squid","en")}</li></ul>
<p lang="en">For sources and corrections, see our {a("/editorial-policy/","editorial policy","en")} and {a("/contact-and-corrections/","corrections page","en")}. This is an editorial reading guide based on cited published research and institutional material, not firsthand field research.</p>
<p><small>자료 검증 및 구성 업데이트: 2026-11-06 / Editorial guide updated: 6 Nov 2026.</small></p>
</div>
'''
SIDEBAR_HTML=(
 '<nav class="taxonguru-reading-guide" aria-label="TaxonGuru 주제별 안내">'
 '<h2>처음 오셨나요? / Start Here</h2>'
 '<p>생물의 크기·진화·극한 생존·번식·행동을 비교해 읽는 길잡이입니다.</p>'
 '<p><a href="'+LINK+'">주제별 읽기 안내 · Reading Guide</a></p>'
 '</nav>'
)

def request(method,route,**kw):
 r=S.request(method,BASE+"/wp-json/wp/v2/"+route,timeout=65,**kw)
 if r.status_code>=400:raise RuntimeError(f"{method} {route} failed HTTP {r.status_code}: {r.text[:230]}")
 return r.json()
def pages(slug):
 r=request("GET","pages",params={"slug":slug,"status":"publish,draft,pending,private","context":"edit","per_page":100})
 return r
def main():
 report={"apply":APPLY,"created_at":datetime.now(timezone.utc).isoformat(),"actions":[],"live_verification":{}}
 found=pages(SLUG)
 if len(found)>1:raise RuntimeError("Multiple pages use reading-guide slug; no mutation")
 pre=found[0] if found else None
 if pre and MARKER not in (pre["content"].get("raw") or pre["content"].get("rendered") or ""):
  raise RuntimeError("Existing non-TaxonGuru page would be overwritten")
 report["existing_page_id"]=pre["id"] if pre else None
 locs=request("GET","menu-locations",params={"context":"edit"})
 footer=locs.get("footer") if isinstance(locs,dict) else next((x for x in locs if x.get("slug")=="footer"),None)
 menu_id=int((footer or {}).get("menu") or 0)
 if menu_id<=0:raise RuntimeError("Existing footer menu missing, no alternate menu created")
 items=request("GET","menu-items",params={"menus":menu_id,"context":"edit","per_page":100})
 report["footer_menu_id"]=menu_id
 sidebar=request("GET","sidebars/sidebar-1",params={"context":"edit"})
 oldids=list(sidebar.get("widgets") or [])
 widgets=request("GET","widgets",params={"context":"edit","per_page":100})
 existing_widget=[w for w in widgets if "taxonguru-reading-guide" in (
  w.get("rendered","") or ((w.get("instance") or {}).get("raw") or {}).get("content","")
 )]
 if len(existing_widget)>1:raise RuntimeError("Multiple reading guide widgets detected")
 widget=existing_widget[0] if existing_widget else None
 report["old_sidebar_widget_ids"]=oldids
 report["removed_empty_recent_comments_widget"]="block-4" in oldids
 report["existing_widget_id"]=widget.get("id") if widget else None
 report["old_footer_items"]=[{"id":x.get("id"),"title":x.get("title"),"url":x.get("url")} for x in items]
 (OUT/"before.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 if APPLY:
  if pre:
   if pre.get("status")!="publish":page=request("POST",f"pages/{pre['id']}",json={"status":"publish"})
   else:page=pre
  else:
   page=request("POST","pages",json={"title":PAGE_TITLE,"slug":SLUG,
      "content":BODY,"status":"publish","comment_status":"closed"})
  if page.get("status")!="publish":raise RuntimeError("Reading guide page not published")
  report["page_id"]=page["id"];report["actions"].append("page_published")
  if LINK.rstrip("/") not in {str(item.get("url","")).rstrip("/") for item in items}:
   newitem=request("POST","menu-items",json={"menus":menu_id,"title":NAV_TITLE,
        "url":LINK,"type":"custom","status":"publish"})
   report["new_menu_item_id"]=newitem.get("id");report["actions"].append("footer_menu_link_added")
  if not widget:
   widget=request("POST","widgets",json={"id_base":"custom_html",
       "sidebar":"wp_inactive_widgets",
       "instance":{"raw":{"title":"","content":SIDEBAR_HTML}}})
   report["actions"].append("sidebar_widget_created")
  widgetid=widget["id"]
  updated=[wid for wid in oldids if wid!="block-4" and wid!=widgetid]
  insertat=1 if updated and updated[0]=="block-2" else 0
  updated.insert(insertat,widgetid)
  if updated!=oldids:
   request("POST","sidebars/sidebar-1",json={"widgets":updated})
   report["actions"].append("sidebar_guide_positioned_and_empty_comment_widget_unassigned")
  report["new_sidebar_widget_ids"]=updated
 else:
  report["actions"]=["would_create_reading_guide_page" if not pre else "reading_guide_page_exists",
                      "would_ensure_footer_menu_link","would_add_sidebar_guide_and_unassign_empty_recent_comments"]
 # Verify content on the public site and do not assume WP REST write means page is visible.
 a=S.get(LINK,timeout=60,headers={"Cache-Control":"no-cache"})
 b=S.get(BASE+"/",timeout=60,headers={"Cache-Control":"no-cache"})
 public=BeautifulSoup(a.text,"html.parser")
 report["live_verification"]={
   "reading_page_http":a.status_code,
   "has_marker":MARKER in a.text,
   "reading_h2_count":len(public.select("h2")),
   "has_verified_primary_source":'kew.org/plants/victoria-boliviana' in a.text,
   "homepage_http":b.status_code,
   "homepage_has_guide_link":"/reading-guide/" in b.text,
   "homepage_guide_sidebar":'taxonguru-reading-guide' in b.text,
 }
 (OUT/"after.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 print("READER_GUIDE_REPORT="+json.dumps(report,ensure_ascii=False),flush=True)
 if APPLY and (report["live_verification"]["reading_page_http"]!=200 or not report["live_verification"]["has_marker"] or not report["live_verification"]["homepage_guide_sidebar"]):
  raise RuntimeError("Guide creation completed but public rendering is incomplete")
if __name__=="__main__":main()
