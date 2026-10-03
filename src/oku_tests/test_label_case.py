"""The kit draws text in the case it was written in.

Twenty-two rules set labels in tracked-out capitals and one forced card
titles to lower case. Most of what they recased was the AUTHOR's: column
names in the card, list and board views, group values, chart axis and
series names, example titles. A column called `createdAt` read
`CREATEDAT`, which is not the key a reader would type; a Turkish one
read in dotted capitals nobody wrote. The reading look already put the
table header and the headings in sentence case; these were the rest.

A language code is the one exception: it is a code, and codes are
written in capitals.

The browser half — that the drawn text keeps its case in every view —
is `browser/test_labels_keep_their_case.py`. This half is the rule's
source, so a new rule that recases fails here before anything renders.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "kit" / "chrome.css"

# selector -> the one transform it may apply
ALLOWED = {".oku-tooltip .okt-lang": "uppercase"}


def _rules(css: str):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # Innermost blocks only, so a rule inside @media is read with its own
    # selector rather than with the at-rule's prelude.
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield " ".join(m.group(1).split()), m.group(2)


def test_no_rule_changes_the_case_of_text():
    bad = []
    for sel, body in _rules(CSS.read_text(encoding="utf-8")):
        for value in re.findall(r"text-transform\s*:\s*([a-z-]+)", body):
            if value != "none" and ALLOWED.get(sel) != value:
                bad.append(f"{sel} {{ text-transform: {value} }}")
        if re.search(r"font-variant(?:-caps)?\s*:[^;]*small-caps", body):
            bad.append(f"{sel} {{ small-caps }}")
    assert bad == [], "rules that recase text:\n" + "\n".join(bad)


def test_the_exception_is_still_there():
    """Vacuity guard: the parser has to find the one rule it allows, or
    an empty list above means the parser stopped reading the file."""
    found = {
        sel
        for sel, body in _rules(CSS.read_text(encoding="utf-8"))
        if re.search(r"text-transform\s*:\s*uppercase", body)
    }
    assert found == set(ALLOWED), found
