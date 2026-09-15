from __future__ import annotations

import re
import sys

import adsense_public_guard as _guard
from adsense_public_guard import *  # noqa: F401,F403

# The v6.2 audit regex contained the generic word "Hook", which can occur in
# legitimate biological prose. For production gating, use only distinctive
# template headings to avoid drafting a valid article on a false positive.
FIXED_TEMPLATE_RE = re.compile(
    r"Scientific Backbone|Deep Anatomy|Evolutionary Context|Verdict\s*&\s*Trivia|"
    r"핵심\s*요약.{0,120}분류학적\s*위치",
    re.I | re.S,
)
BILINGUAL_RE = re.compile(
    r"Global Readers|English Version|\[2부|Part\s*2\s*:\s*English",
    re.I,
)

_guard.FIXED_TEMPLATE_RE = FIXED_TEMPLATE_RE
_guard.BILINGUAL_RE = BILINGUAL_RE


def main() -> int:
    return _guard.main()


if __name__ == "__main__":
    sys.exit(main())
