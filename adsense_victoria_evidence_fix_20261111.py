"""Evidence-aligned, reversible fix for TaxonGuru Victoria amazonica English article (775).

Default: preview. No new publishing, no AdSense submission, no editorial signoff.
Preconditions protect site from overwriting concurrent edits. Original saved to Actions artifact.
"""
from __future__ import annotations
import datetime
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests

SITE = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
APPLY = os.getenv("VICTORIA_EVIDENCE_APPLY", "false").lower() == "true"
POST_ID = 775
EXPECTED_MODIFIED = "2026-11-06T22:07:56"
OUT = Path("audit_output/victoria_evidence_20261111")
OUT.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "TaxonGuruEvidenceRepair/2026-11-11"}

# Every destination was checked against its substantive claims.
# Original reference numbering is kept even when the linked source changes.
REPAIRS = {
    1: ("wikipedia.org", "https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:605776-1/general-information", "Kew Science: Victoria amazonica taxonomy, ecology and morphology"),
    4: ("amazonriverlodge.com", "https://www.nparks.gov.sg/florafaunaweb/flora/2/5/2545", "Singapore NParks: Victoria amazonica leaf features"),
    6: ("wikipedia.org", "https://www.kew.org/about-us/press-media/new-giant-waterlily", "Kew: discovery of Victoria boliviana (2022)"),
    7: ("kew.org", "https://www.kew.org/kew-gardens/whats-in-the-gardens/waterlily-house", "Kew: Waterlily House visitor safety and structural history"),
    9: ("kew.org", "https://pmc.ncbi.nlm.nih.gov/articles/PMC2803590/", "Seymour & Matthews (2006), Annals of Botany: floral thermogenesis field study"),
}
S = requests.Session()
S.headers.update(HEADERS)
S.auth = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])

def wp(method, route, **kwargs):
    r = S.request(method, SITE + "/wp-json/wp/v2/" + route, timeout=65, **kwargs)
    r.raise_for_status()
    return r.json()

def extract_refs(raw):
    result = {}
    for m in re.finditer(r'<li\s+id=["\x27]ref-(\d+)["\x27][^>]*>.*?</li>', raw, flags=re.I | re.S):
        n = int(m.group(1))
        if n in result:
            raise ValueError(f"Duplicate ID ref-{n}")
        result[n] = m.group(0)
    return result

def replace_section(raw, start_h2, end_h2, f):
    i = raw.find(start_h2)
    if i < 0 or raw.find(start_h2, i+1) >= 0:
        raise ValueError(f"Missing or repeated section: {start_h2}")
    j = raw.find(end_h2, i + len(start_h2))
    if j < 0:
        raise ValueError(f"Missing end boundary: {end_h2}")
    return raw[:i] + f(raw[i:j]) + raw[j:]

def patch(raw):
    before_refs = extract_refs(raw)
    if set(before_refs) != set(range(1, 10)):
        raise ValueError(f"Reference IDs changed unexpectedly: {sorted(before_refs)}")
    updated = raw
    for n, (expected_host, dest, label) in REPAIRS.items():
        current = before_refs[n]
        anchors = re.findall(r'<a\b[^>]*\bhref=["\x27]([^"\x27]+)', current, flags=re.I)
        if len(anchors) != 1 or expected_host not in (urlsplit(html.unescape(anchors[0])).hostname or "").lower():
            raise ValueError(f"Reference {n} original host/anchor changed; refuse overwrite")
        new = (f'<li id="ref-{n}"><a href="{html.escape(dest, quote=True)}" target="_blank" '
               f'rel="noopener noreferrer">{html.escape(label)}</a> — verified 2026-11-11</li>')
        if updated.count(current) != 1:
            raise ValueError(f"Reference {n} not unique in article")
        updated = updated.replace(current, new, 1)

    # Remove classification paper [2] as purported support for floral thermogenesis.
    h2_bloom = "<h2>A Two-Night Trap: Heat, Fragrance, and Beetles</h2>"
    h2_arch = "<h2>Architectural Inspiration and the Great Size Reassessment</h2>"
    def bloom_change(fragment):
        fragment = fragment.replace("[2, 3, 9]", "[3, 9]")
        fragment = fragment.replace("[1, 2, 3]", "[1, 3, 9]")
        fragment = re.sub(
            r'<sup>\s*<a\s+href=["\x27]#ref-2["\x27]>\[2\]</a>\s*</sup>', "",
            fragment, flags=re.I)
        evidence = (
            '<p><strong>What the field experiment actually measured:</strong> '
            'Seymour and Matthews (2006) recorded flower temperatures in 20 <em>V. amazonica</em> '
            'flowers in Guyana and respiration in five. During the first night, floral chamber '
            'temperatures were 29.3–34.7°C while ambient air was 23.5–25.2°C. The authors '
            'proposed that warmth may also save visiting beetles energy, beyond helping spread '
            'scent; this was not a controlled demonstration of the plant producing a fixed '
            '10°C temperature increase in every setting '
            '(<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC2803590/" '
            'target="_blank" rel="noopener noreferrer">Annals of Botany field study, 2006</a>).</p>')
        return fragment.replace(h2_bloom, h2_bloom + "\n" + evidence, 1)
    updated = replace_section(updated, h2_bloom, h2_arch, bloom_change)

    # The 2022 species-description paper is not an architectural history study.
    h2_follow = "<h2>Linking Architecture, Defense, and Survival</h2>"
    def architecture_change(fragment):
        return fragment.replace("[1, 2, 3]", "[3, 8]")
    updated = replace_section(updated, h2_arch, h2_follow, architecture_change)

    # Defensive spines are described as a possible deterrent, not experimentally proven protection.
    updated = updated.replace(
        "These formidable hard spines prevent underwater herbivorous animals",
        "These spines may help deter underwater herbivorous animals", 1)

    after_refs = extract_refs(updated)
    if sorted(before_refs) != sorted(after_refs):
        raise ValueError("Reference numbering changed")
    if len(re.findall(r"<img\b", raw, re.I)) != len(re.findall(r"<img\b", updated, re.I)):
        raise ValueError("Image count changed")
    if len(re.findall(r"<h2\b", raw, re.I)) != len(re.findall(r"<h2\b", updated, re.I)):
        raise ValueError("Headings count changed")
    if len(updated) < len(raw)*0.98:
        raise ValueError("Unusual content shrinkage")
    for n, (_, dest, _) in REPAIRS.items():
        if dest not in after_refs[n]:
            raise ValueError(f"Replacement reference {n} did not persist")
    if "What the field experiment actually measured:" not in updated:
        raise ValueError("Evidence explanatory paragraph missing")
    return updated

def main():
    post = wp("GET", f"posts/{POST_ID}", params={"context": "edit"})
    if post["status"] != "publish":
        raise ValueError("Target not currently published; refuse change")
    if post["modified"] != EXPECTED_MODIFIED:
        raise ValueError(f"Concurrent edit: modified={post['modified']}; manual review required")
    raw = post["content"].get("raw")
    if not raw:
        raise ValueError("Authenticated editable HTML unavailable")
    orig = {"id": POST_ID, "modified": post["modified"], "status": post["status"],
            "title": post["title"], "content": raw, "excerpt": post.get("excerpt"),
            "featured_media": post.get("featured_media"), "link": post["link"]}
    (OUT/"original_post_775.json").write_text(json.dumps(orig, ensure_ascii=False, indent=2), encoding="utf-8")
    changed = patch(raw)
    (OUT/"preview_patch.html").write_text(changed, encoding="utf-8")
    result = {"id": POST_ID, "apply": APPLY, "reference_ids": sorted(REPAIRS),
              "original_chars": len(raw), "updated_chars": len(changed),
              "backup_saved": True, "result": "PREVIEW_OK"}
    if APPLY:
        # Save only content: never change status, permalink, author, categories, media or ads settings.
        wp("POST", f"posts/{POST_ID}", json={"content": changed})
        after = wp("GET", f"posts/{POST_ID}", params={"context": "edit"})
        actual = after["content"].get("raw", "")
        if after["status"] != "publish" or actual != changed:
            raise RuntimeError("Live WordPress read-back differed from prepared HTML")
        public = requests.get(post["link"], headers=HEADERS, timeout=45)
        if public.status_code != 200:
            raise RuntimeError(f"Public article failed after update: HTTP {public.status_code}")
        public_rest = requests.get(SITE+f"/wp-json/wp/v2/posts/{POST_ID}", headers=HEADERS, timeout=45)
        if public_rest.status_code != 200:
            raise RuntimeError(f"Public WordPress REST failed: HTTP {public_rest.status_code}")
        html_public = public_rest.json()["content"]["rendered"]
        if not all(u in html_public for _, u, _ in REPAIRS.values()):
            raise RuntimeError("New scholarly/institutional references not all public")
        result["result"] = "LIVE_UPDATED_AND_VERIFIED"
        result["public_status"] = public.status_code
    (OUT/"result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("VICTORIA_EVIDENCE_RESULT="+json.dumps(result), flush=True)

if __name__ == "__main__":
    main()
