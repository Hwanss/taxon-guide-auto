from __future__ import annotations

import re
import sys

import adsense_auto_publish_v64 as v64


def extract_article_html(html_text: str) -> str:
    """Return the main post body, excluding global navigation/footer where possible."""
    candidates: list[str] = []
    for pattern in (
        r"<article\b[^>]*>.*?</article>",
        r"<main\b[^>]*>.*?</main>",
        r"<div\b[^>]*(?:class|id)=[\"'][^\"']*(?:entry-content|post-content|site-main)[^\"']*[\"'][^>]*>.*?</div>",
    ):
        candidates.extend(re.findall(pattern, html_text or "", flags=re.I | re.S))
    return max(candidates, key=len) if candidates else (html_text or "")


def english_render_has_language_mix(text: str) -> bool:
    """Ignore tiny theme/meta labels while still rejecting meaningful KO/JP contamination."""
    hangul_count = len(re.findall(r"[가-힣]", text))
    kana_count = len(re.findall(r"[\u3040-\u30FF]", text))
    # The draft itself is already checked strictly before publish. This render-stage
    # threshold exists only to avoid false positives from bilingual theme chrome/meta.
    hangul_limit = max(80, int(max(1, len(text)) * 0.02))
    return hangul_count > hangul_limit or kana_count > 12


def public_render_ok(url: str, *, is_english: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    try:
        response = v64.session.get(url, timeout=v64.REQUEST_TIMEOUT, allow_redirects=True)
    except Exception as exc:
        return False, [f"공개 페이지 접속 실패: {type(exc).__name__}"]
    if response.status_code != 200:
        return False, [f"공개 페이지 HTTP {response.status_code}"]

    content_html = extract_article_html(response.text)
    text = v64.text_only(content_html)
    if len(text) < 1500:
        reasons.append("공개 페이지 렌더링 본문이 비정상적으로 짧음")
    if (
        v64.FIXED_TEMPLATE_RE.search(text)
        or v64.BILINGUAL_RE.search(content_html)
        or v64.FAKE_EXPERT_RE.search(text)
    ):
        reasons.append("공개 렌더링에서 금지 패턴 재검출")

    if is_english and english_render_has_language_mix(text):
        reasons.append("공개 영문 본문에 의미 있는 언어 혼입")
    if not is_english and re.search(r"[\u3040-\u30FF]", text):
        reasons.append("공개 한국어 본문에 일본어 혼입")
    return not reasons, reasons


def run_patch_self_test() -> int:
    # Korean site chrome around an English article must not fail the render language gate.
    english_body = "<article><h1>Bee hummingbird</h1><p>" + ("English biology text. " * 140) + "</p></article>"
    shell = "<html><nav>홈 소개 문의</nav>" + english_body + "<footer>개인정보처리방침</footer></html>"
    scoped = v64.text_only(extract_article_html(shell))
    if english_render_has_language_mix(scoped):
        raise SystemExit("SELF_TEST_FAIL_THEME_CHROME")

    mixed_body = (
        "<article><p>" + ("English biology text. " * 80) + "</p><p>"
        + ("한국어 본문 혼입 문장입니다. " * 30) + "</p></article>"
    )
    if not english_render_has_language_mix(v64.text_only(extract_article_html(mixed_body))):
        raise SystemExit("SELF_TEST_FAIL_REAL_MIX")

    if v64.run_self_test() != 0:
        raise SystemExit("SELF_TEST_FAIL_BASE")
    print("V641_RENDER_SCOPE_SELF_TEST_OK")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return run_patch_self_test()
    v64.public_render_ok = public_render_ok
    print("🩹 v6.4.1 렌더링 검증 보정 활성화: 글 본문 범위만 언어 혼입 검사", flush=True)
    return v64.main()


if __name__ == "__main__":
    raise SystemExit(main())
