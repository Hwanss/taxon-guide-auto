"""Inspect and safely add five TaxonGuru trust links to an existing WordPress navigation menu.

Never delete an item or replace an assigned menu. Dry-run by default.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE = os.getenv("WP_SITE_URL", "https://taxonguru.com").rstrip("/")
API = f"{BASE}/wp-json/wp/v2"
USER = os.getenv("WP_USER", "")
PASSWORD = os.getenv("WP_APP_PASSWORD", "")
APPLY = os.getenv("NAV_APPLY", "false").lower() == "true"
OUTPUT = Path(os.getenv("AUDIT_OUTPUT_DIR", "audit_output"))
LINKS = [
    ("소개", "about-taxonguru"),
    ("편집 및 팩트체크", "editorial-policy"),
    ("AI 활용 정책", "ai-use-policy"),
    ("문의 및 정정", "contact-and-corrections"),
    ("개인정보처리방침", "privacy-policy"),
]

session = requests.Session()
session.auth = (USER, PASSWORD)
session.headers.update({"User-Agent": "TaxonGuruSafeNavigationRepair/1.0"})


def req(method: str, path: str, **kwargs):
    res = session.request(method, f"{API}/{path}", timeout=45, **kwargs)
    if res.status_code >= 400:
        raise RuntimeError(f"{method} {path} HTTP {res.status_code}: {res.text[:300]}")
    return res.json()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {"site": BASE, "apply": APPLY, "changed": [], "issues": []}
    if not USER or not PASSWORD:
        raise RuntimeError("WordPress app credentials missing")

    try:
        locations = req("GET", "menu-locations", params={"context": "edit"})
        menus = req("GET", "menus", params={"context": "edit", "per_page": 100})
    except Exception as exc:
        report["issues"].append("REST 메뉴 API 접근 실패: " + str(exc))
        (OUTPUT / "site_navigation_repair.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0  # an unsupported theme still gets an actionable report

    report["menu_locations"] = locations
    report["menus"] = [
        {"id": item.get("id"), "name": item.get("name"), "locations": item.get("locations")}
        for item in menus
    ]
    items_by_slug = {}
    if isinstance(locations, dict):
        items_by_slug = {
            slug: loc for slug, loc in locations.items() if isinstance(loc, dict)
        }
    else:
        items_by_slug = {
            str(loc.get("slug", "")): loc
            for loc in locations
            if isinstance(loc, dict) and loc.get("slug")
        }

    # Use the footer location: do NOT activate the old 15-category menu on top.
    target_slug = next((k for k in items_by_slug if "footer" in k.lower()), None)
    if not target_slug:
        report["issues"].append("테마 footer 메뉴 위치가 없어 자동 작업을 건너뜁니다.")
    else:
        report["target_location"] = target_slug
        target = items_by_slug[target_slug]
        menu_id = int(target.get("menu") or 0)
        needs_assignment = menu_id <= 0
        if needs_assignment:
            matching = [m for m in menus if m.get("name") == "TaxonGuru 정책 및 안내"]
            if len(matching) == 1 and not matching[0].get("locations"):
                menu_id = int(matching[0]["id"])
            elif not matching and APPLY:
                created = req("POST", "menus", json={
                    "name": "TaxonGuru 정책 및 안내",
                    "description": "AdSense transparency links; existing navigation preserved",
                })
                menu_id = int(created["id"])
                report["created_menu_id"] = menu_id
            else:
                report["new_menu_preview"] = "Would create a dedicated footer menu; existing category menu remains untouched"

        report["target_menu_id"] = menu_id or None
        existing = []
        if menu_id > 0:
            page = 1
            while True:
                batch = req("GET", "menu-items", params={
                    "menus": menu_id, "context": "edit", "per_page": 100, "page": page
                })
                existing.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
                if page > 10:
                    raise RuntimeError("메뉴 항목 조회 페이지 제한 초과")
        report["existing_items"] = [
            {"id": item.get("id"), "url": item.get("url"), "title": item.get("title")}
            for item in existing
        ]
        existing_urls = {str(item.get("url", "")).rstrip("/").lower() for item in existing}
        for title, slug in LINKS:
            url = f"{BASE}/{slug}/"
            if url.rstrip("/").lower() in existing_urls:
                continue
            if APPLY and menu_id > 0:
                posted = req("POST", "menu-items", json={
                    "menus": menu_id,
                    "title": title,
                    "url": url,
                    "type": "custom",
                    "status": "publish",
                })
                report["changed"].append({"title": title, "url": url, "item_id": posted.get("id")})
            else:
                report["changed"].append({"title": title, "url": url, "action": "would_add"})

        # Assign the new footer menu only after all links have been safely created.
        if needs_assignment:
            if APPLY and menu_id > 0:
                req("POST", f"menus/{menu_id}", json={"locations": [target_slug]})
                report["assigned_location"] = target_slug
            else:
                report["assignment_preview"] = f"Would assign dedicated footer menu to {target_slug}"
    output = OUTPUT / "site_navigation_repair.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
