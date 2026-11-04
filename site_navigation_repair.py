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

    # Primary menu is deliberately preferred: trust links must be visible in main navigation.
    target_slug = next(
        (slug for slug, loc in items_by_slug.items()
         if "primary" in str(loc.get("description", "")).lower()
         or "primary" in slug.lower() or "menu-1" == slug.lower()), None
    )
    target_slug = target_slug or next((k for k in items_by_slug if "footer" in k.lower()), None)
    if not target_slug:
        report["issues"].append("WordPress 테마에서 footer/primary 메뉴 위치를 확인하지 못했습니다.")
    else:
        report["target_location"] = target_slug
        target = items_by_slug[target_slug]
        menu_id = int(target.get("menu") or 0)
        needs_assignment = False
        if menu_id <= 0 and len(menus) == 1:
            candidate = menus[0]
            if not candidate.get("locations"):
                # Reuse the only existing unassigned menu. Never replace an active menu.
                menu_id = int(candidate["id"])
                needs_assignment = True
        if menu_id <= 0:
            report["issues"].append(
                "기존 메뉴가 없거나 여러 개여서 자동 할당할 수 없습니다. 기존 메뉴를 보존합니다.")
        else:
            report["target_menu_id"] = menu_id
            report["needs_assignment"] = needs_assignment
            existing = []
            page = 1
            while True:
                batch = req("GET", "menu-items", params={"menus": menu_id, "context": "edit", "per_page": 100, "page": page})
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
                if APPLY:
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
            # Only assign the menu after all five links have been successfully created.
            if needs_assignment:
                if APPLY:
                    req("POST", f"menus/{menu_id}", json={"locations": [target_slug]})
                    report["assigned_location"] = target_slug
                else:
                    report["assignment_preview"] = f"Would assign existing menu {menu_id} to {target_slug}"
    output = OUTPUT / "site_navigation_repair.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
