"""Every SVG element the kit draws gets a colour from somewhere.

Two files decide what a chart looks like and neither can see the other:
`chrome.js` writes the markup, `chrome.css` styles it. An element whose
class the stylesheet never mentions is not a broken element — SVG has
defaults, and the defaults are the trap:

| element | with no colour set | how it presents |
|---|---|---|
| `text`, `circle`, `rect`, `path` | `fill: black` | fine in light, invisible in dark |
| `line`, `polyline` | `stroke: none` | never paints, in either theme |

Eight label classes and two guide lines shipped this way. The eight were
reported from a delivered document, in dark mode, months after they were
written — because black on white looks like a decision, so nothing about
the light theme said the fill was missing rather than chosen.

The browser test that pins their contrast, `browser/test_chart_label_
legibility.py`, names the classes it checks. This one does not need to:
it re-derives the list from the source, so a chart family added next
year with the same omission fails here without anyone remembering to
extend a list.

Kept static on purpose. The rendering question — is this readable — is
a browser measurement and lives there. The question here is narrower and
decidable from the source: does this element get a colour AT ALL.

Scope, stated so the green is not read as more than it is: this covers
elements that carry a class, which is every element a renderer draws and
every one of the ten that were wrong. It does not cover the icon
fragments, which are class-less strings spliced into a wrapper `<svg>`
declared elsewhere — no class rule could reach them, and their colour
cannot be resolved from the line they are written on.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[2] / "kit"

SHAPES = ("circle", "rect", "path", "polygon", "ellipse", "text", "line", "polyline")
# Which property has to be set for the element to be seen at all.
NEEDS_FILL = {"circle", "rect", "path", "polygon", "ellipse", "text"}

TAG_RE = re.compile(r"<(" + "|".join(SHAPES) + r")\b[^>]*?>")
CLASS_RE = re.compile(r'class="([^"]*)"')
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DECL_RE = re.compile(r"(?:^|[;{\s])(fill|stroke|color)\s*:")
SELECTOR_CLASS_RE = re.compile(r"\.([A-Za-z][\w-]*)")
# A wrapper <svg> that sets fill or stroke colours everything inside it,
# so nothing on that line needs its own.
SVG_WITH_COLOUR_RE = re.compile(r"<svg\b[^>]*\b(?:fill|stroke)=")


def _classes_with_colour(css: str) -> dict[str, set[str]]:
    """class name -> the colour properties any rule sets on it."""
    found: dict[str, set[str]] = {}
    for selector, body in RULE_RE.findall(css):
        props = set(DECL_RE.findall(body))
        if not props:
            continue
        for name in SELECTOR_CLASS_RE.findall(selector):
            found.setdefault(name, set()).update(props)
    return found


def _unresolved(js: str, coloured: dict[str, set[str]]) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(js.split("\n"), 1):
        if SVG_WITH_COLOUR_RE.search(line):
            continue
        for match in TAG_RE.finditer(line):
            tag, element = match.group(0), match.group(1)
            classes = CLASS_RE.search(tag)
            # Names are stripped of a trailing quote: several are built
            # by concatenation (`class="okc-x' + (flag ? ' on' : '') + '"`).
            names = [c.rstrip("'\"") for c in (classes.group(1).split() if classes else [])]
            # No class and no inline colour: an icon fragment, spliced
            # into a wrapper <svg> defined somewhere else. Its colour is
            # not decidable from this line, and no CSS class rule could
            # have reached it anyway — which is the scope limit stated
            # in the module docstring.
            if not names and "fill=" not in tag and "stroke=" not in tag:
                continue
            from_css: set[str] = set()
            for name in names:
                from_css |= coloured.get(name, set())
            if element in NEEDS_FILL:
                ok = "fill=" in tag or bool(re.search(r'style="[^"]*fill\s*:', tag))
                ok = ok or "fill" in from_css or "color" in from_css
                want = "fill (defaults to black)"
            else:
                ok = "stroke=" in tag or bool(re.search(r'style="[^"]*stroke\s*:', tag))
                ok = ok or "stroke" in from_css
                want = "stroke (defaults to none — never paints)"
            if not ok:
                out.append((lineno, f"<{element} class={' '.join(names) or '(none)'}>", want))
    return out


@pytest.mark.parametrize("source", ["chrome.js", "renderer.js"])
def test_every_svg_element_the_kit_draws_is_given_a_colour(source):
    js = (KIT / source).read_text(encoding="utf-8")
    coloured = _classes_with_colour((KIT / "chrome.css").read_text(encoding="utf-8"))
    unresolved = _unresolved(js, coloured)
    assert not unresolved, "\n".join(
        [f"{source}: {len(unresolved)} SVG element(s) with no colour from markup or CSS:"]
        + [f"  line {n}: {tag} needs {want}" for n, tag, want in unresolved]
    )


def test_no_svg_colour_is_written_as_a_hex_literal():
    """A hex does not follow the accent and does not flip with the
    theme, so it is the other way to end up invisible in the theme
    nobody was looking at — the same rule `island-hand-styled` enforces
    for an author's own markup."""
    offenders = []
    for source in ("chrome.js", "renderer.js"):
        js = (KIT / source).read_text(encoding="utf-8")
        for lineno, line in enumerate(js.split("\n"), 1):
            if re.search(r'(fill|stroke)\s*[=:]\s*["\']?#[0-9a-fA-F]{3,8}', line):
                offenders.append(f"  {source}:{lineno}: {line.strip()[:90]}")
    assert not offenders, "hardcoded SVG colours:\n" + "\n".join(offenders)
