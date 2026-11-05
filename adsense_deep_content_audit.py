"""Evidence-first audit of ALL published TaxonGuru WordPress posts.

Read only. Never publishes, drafts, or rewrites. Creates private Action artifact backups
and review worksheets. No claims that internal scores equal Google approval.
"""
from __future__ import annotations
import csv
import html
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit
import requests

BASE = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
AUTH = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])
OUT = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output")) / "deep_content_audit"
OUT.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.auth = AUTH
SESSION.headers.update({"User-Agent": "TaxonGuruEvidenceAudit/1.0"})
SOCIAL = {"facebook.com", "instagram.com", "reddit.com", "tiktok.com", "pinterest.com", "youtube.com", "x.com", "twitter.com"}
BAD_HOST = {"vertexaisearch.cloud.google.com", "googleusercontent.com", "www.googleusercontent.com"}
REF_HEADERS = re.compile(r"<h[2-6][^>]*>\s*(?:References|Sources|참고자료|참고문헌|출처)\s*</h[2-6]>", re.I)
URL_RE = re.compile(r"""href\s*=\s*["'](https?://[^"']+)""", re.I)
HEADER_RE = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
TEMPLATE_RE = re.compile(r"Scientific Backbone|Deep Anatomy|Evolutionary Context|Verdict\s*&\s*Trivia|Hook", re.I)
UNVERIFIED_RE = re.compile(r"world.s (?:only|first|largest|smallest)|the only species|최초로|유일한|가장 큰|세계 최대", re.I)

def plain(s):
    return " ".join(html.unescape(TAG_RE.sub(" ", s or "")).split())

def ref_host(url):
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")

def get_posts():
    all_posts = []
    p = 1
    while True:
        response = SESSION.get(f"{BASE}/wp-json/wp/v2/posts", params={
            "status": "publish", "context": "edit", "per_page": 100,
            "page": p, "orderby": "id", "order": "asc",
        }, timeout=75)
        response.raise_for_status()
        batch = response.json()
        all_posts.extend(batch)
        if p >= int(response.headers.get("X-WP-TotalPages", "1")): break
        p += 1
    return all_posts

def shingle_set(s, n=8):
    words = re.findall(r"[a-z]{2,}|[가-힣]{2,}", s.lower())
    return set(tuple(words[i:i+n]) for i in range(max(0,len(words)-n+1)))

def main():
    posts = get_posts()
    backups = []
    records = []
    text_by_id = {}
    shingles = {}
    paragraph_counts = Counter()
    repeated_paragraphs = defaultdict(list)
    for post in posts:
        pid = int(post["id"])
        title = plain(str(post.get("title",{}).get("raw") or post.get("title",{}).get("rendered") or ""))
        content_obj = post.get("content", {})
        content = content_obj.get("raw") or content_obj.get("rendered") or ""
        text = plain(content)
        text_by_id[pid] = text
        shingles[pid] = shingle_set(text)
        all_links = URL_RE.findall(content)
        reference_match = REF_HEADERS.search(content)
        refhtml = content[reference_match.end():] if reference_match else ""
        # Stop at the next heading to avoid footers, translations, and unrelated sections.
        end_heading = re.search(r"<h[2-6]\b", refhtml, re.I)
        if end_heading: refhtml = refhtml[:end_heading.start()]
        ref_links = URL_RE.findall(refhtml)
        social_links = [u for u in ref_links if ref_host(u) in SOCIAL]
        raw_paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", content, re.I | re.S)
        for para in raw_paragraphs:
            ptxt=plain(para)
            if len(ptxt)>=110:
                paragraph_counts[ptxt]+=1
                repeated_paragraphs[ptxt].append(pid)
        direct_domains = Counter(ref_host(u) for u in ref_links)
        short_claims = [plain(m.group(0)) for m in list(UNVERIFIED_RE.finditer(text))[:6]]
        row = {
            "id":pid,"title":title,"url":post.get("link",""),"status":post.get("status"),
            "modified":post.get("modified"),"chars":len(text),
            "english_words":len(re.findall(r"\b[a-zA-Z][a-zA-Z'-]*\b",text)),
            "paragraphs":len(raw_paragraphs),"images":len(re.findall(r"<img\b",content,re.I)),
            "links":len(all_links),"reference_links":len(ref_links),
            "reference_hosts":dict(direct_domains),
            "social_references":social_links,
            "has_reference_section":bool(reference_match),
            "template_traces":bool(TEMPLATE_RE.search(text)),
            "claims_to_verify":short_claims,
            "headings":[plain(x) for x in HEADER_RE.findall(content)],
            "excerpt":text[:850],
        }
        records.append(row)
        backups.append({"id":pid,"title":title,"url":post.get("link"),"content":content,"modified":post.get("modified"),"excerpt":post.get("excerpt")})
    similarities=[]
    for i,a in enumerate(records):
        for b in records[i+1:]:
            xs=shingles[a["id"]]; ys=shingles[b["id"]]
            if not xs or not ys: continue
            common = len(xs&ys); union=len(xs|ys)
            sim=round(common/union,3) if union else 0
            if sim>=0.1: similarities.append({"id_a":a["id"],"id_b":b["id"],"jaccard_8":sim,"title_a":a["title"],"title_b":b["title"]})
    similarities.sort(key=lambda p:-p["jaccard_8"])
    recurring=[{"count":c,"post_ids":list(dict.fromkeys(repeated_paragraphs[p])),"sample":p[:250]} for p,c in paragraph_counts.items() if c>=3]
    recurring.sort(key=lambda x:-x["count"])
    summaries={
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "public_posts":len(records),
        "social_reference_posts":sum(bool(p["social_references"]) for p in records),
        "no_reference_section":sum(not p["has_reference_section"] for p in records),
        "no_reference_links":sum(not p["reference_links"] for p in records),
        "image_free_posts":sum(not p["images"] for p in records),
        "template_trace_posts":sum(p["template_traces"] for p in records),
        "repeated_paragraphs_3plus":len(recurring),
        "pair_similarity_top":similarities[:20],
        "length_min":min((p["chars"] for p in records),default=0),
        "length_max":max((p["chars"] for p in records),default=0),
    }
    (OUT/"backup_public_posts.json").write_text(json.dumps(backups,ensure_ascii=False,indent=2),encoding="utf8")
    (OUT/"post_audit_full.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf8")
    (OUT/"summary.json").write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding="utf8")
    (OUT/"repeated_paragraphs.json").write_text(json.dumps(recurring[:120],ensure_ascii=False,indent=2),encoding="utf8")
    with (OUT/"review_queue.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(["id","title","url","chars","EN words","reference links","social links","images","reference domains","review status","review note"])
        for p in records:w.writerow([p["id"],p["title"],p["url"],p["chars"],p["english_words"],p["reference_links"]," | ".join(p["social_references"]),p["images"]," | ".join(p["reference_hosts"]),"필요",""])
    print("DEEP_AUDIT_SUMMARY="+json.dumps(summaries,ensure_ascii=False))
    print("SOCIAL_REFERENCES_START")
    for p in records:
        if p["social_references"]:
            print(json.dumps({"id":p["id"],"title":p["title"],"url":p["url"],"social_urls":p["social_references"],"other_ref_domains":p["reference_hosts"],"headings":p["headings"][-7:]},ensure_ascii=False))
    print("SOCIAL_REFERENCES_END")
    print("REPEATED_PARAGRAPHS_TOP="+json.dumps(recurring[:8],ensure_ascii=False))
    print("AUDIT_COMPLETED_READ_ONLY")

if __name__ == "__main__":
    main()
