"""The minified stylesheet is the same stylesheet to the browser.

Compared by Chrome's own parse of each (the CSSOM), not by bytes. One
normalisation: a custom property's value, and a declaration holding a
var(), keep their text as written, so `rgba(0, 0, 0, 0.5)` in the source
and `rgba(0,0,0,0.5)` in the output differ there and nowhere else
(57 of 1,316 rules on 2026-10-18). Whitespace beside a comma, a slash or
a parenthesis is taken out of both sides before comparing.
"""

from __future__ import annotations

import re

from oku import cli

_RULES = "css => { const s = new CSSStyleSheet(); s.replaceSync(css); return [...s.cssRules].map(r => r.cssText); }"


def _same(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*([,(/)])\s*", r"\1", text))


def _rules(page, css: str) -> list[str]:
    return [_same(r) for r in page.evaluate(_RULES, css)]


def test_the_minified_stylesheet_parses_to_the_same_rules(page) -> None:
    source = _rules(page, (cli.KIT_DIR / "chrome.css").read_text(encoding="utf-8"))
    shipped = _rules(page, cli.kit_file_text("chrome.css"))
    assert len(source) > 1000
    differ = [(a, b) for a, b in zip(source, shipped, strict=False) if a != b]
    assert len(source) == len(shipped) and not differ, differ[:3]


def test_the_comparison_sees_a_broken_declaration(page) -> None:
    """The control: calc() without spaces round `+` is invalid and dropped."""
    assert _rules(page, ".a { width: calc(1px + 2px) }") != _rules(page, ".a{width:calc(1px+2px)}")
