"""A callout's type class is one the stylesheet knows.

`.callout` takes its icon, its rule colour and its tint from a bare
type class — `.callout.warning`, not `.callout.callout-warning`. The
hyphenated spelling parses, applies nothing, and leaves the callout
looking like the accent-coloured default with a solid square where the
icon belongs: `--callout-icon` unset makes `::before` render its own
background with no mask.

The markdown viewer's "could not be read" notice shipped that way. It
is checked here rather than in the browser because the failure is a
class name in a string, and the sibling that gets it wrong next will be
a string too.
"""

from __future__ import annotations

import re
from pathlib import Path

KIT = Path(__file__).resolve().parents[2] / "kit"

# `class="callout …"` in an HTML string, `className = 'callout …'` in JS.
CALLOUT_CLASS = re.compile(r"""(?:class=|className\s*=\s*)['"]callout ([a-z0-9 _-]*)['"]""")


def _defined_types() -> set[str]:
    css = (KIT / "chrome.css").read_text(encoding="utf-8")
    return set(re.findall(r"\.callout\.([a-z0-9-]+)", css))


def test_the_stylesheet_defines_types_to_check_against() -> None:
    """The guard: an empty set would make every assertion below vacuous
    in the direction that matters."""
    types = _defined_types()
    assert {"warning", "info", "tip", "danger"} <= types, sorted(types)


def test_every_callout_the_kit_builds_names_a_type_the_stylesheet_has() -> None:
    types = _defined_types()
    offenders = []
    for name in ("chrome.js", "renderer.js"):
        src = (KIT / name).read_text(encoding="utf-8")
        for line_no, line in enumerate(src.splitlines(), 1):
            m = CALLOUT_CLASS.search(line)
            if not m:
                continue
            for token in m.group(1).split():
                # A layout hook (`okt-mdview-fail`) is not a type; a type
                # is a bare word the stylesheet keys on.
                if token.startswith("okt-") or token.startswith("oku-"):
                    continue
                if token not in types:
                    offenders.append(f"{name}:{line_no} — .callout.{token} is styled nowhere")
    assert offenders == [], offenders
