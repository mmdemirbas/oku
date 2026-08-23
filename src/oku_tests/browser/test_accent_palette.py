"""Every accent the schema documents has to be a colour by the time a
diagram asks for one.

`oku spec front-matter` lists seven tokens — teal, amber, indigo, rose,
violet, green, slate. The palette map in `_applyAccent` held three, and
the other four fell through to a fallback that wrote the raw token into
`--accent`. That splits by whether the word happens to be a CSS named
colour:

- `violet` and `green` are, so `--accent` took the browser's hue while
  `--accent-soft` and `--accent-strong` stayed on the indigo defaults —
  one hue on a callout's rule, another on the surface behind it.
- `rose` and `slate` are not, so `--accent` held an invalid declaration
  and computed to the literal string. `chrome.js::buildConfig` hands
  `--accent` to Mermaid's `themeVariables`, which requires a concrete
  colour, so EVERY diagram on the page became an "Unsupported color
  format" card — measured at 0px against 155px for the control — while
  `oku check --strict` called the page clean.

The assertions below are the distinctness of the seven families rather
than their hex values: a suite pinned to hexes fails on a retune, and
what was broken was two tokens sharing indigo's soft and two producing
no colour at all.
"""

from __future__ import annotations

from ._wait import diagram_drawn, page_quiet

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

# The seven `oku spec front-matter` documents, plus the two shapes the
# fallback has to tell apart.
TOKENS = ("teal", "amber", "indigo", "rose", "violet", "green", "slate")
DERIVED = "rebeccapurple"  # a CSS name the map does not carry
NONSENSE = "notacolour"  # neither a token nor a colour


def _page_md(accent: str | None) -> str:
    front = f"accent: {accent}\n" if accent else ""
    return f"""---
title: Accent {accent or "default"}
summary: One diagram and one callout, so both halves of the family show.
{front}---

> [!NOTE]
> A callout, which paints `--accent-soft` behind `--accent-strong` text.

## One diagram {{#d}}

```mermaid
flowchart LR
    A[one] --> B[two]
```
"""


@pytest.fixture(scope="module")
def accent_pages(tmp_path_factory) -> dict[str, Path]:
    docs = tmp_path_factory.mktemp("accents") / "docs"
    docs.mkdir()
    names = {t: t for t in TOKENS}
    names[DERIVED] = "named"
    names[NONSENSE] = "bogus"
    names[""] = "plain"
    for accent, stem in names.items():
        (docs / f"{stem}.md").write_text(_page_md(accent or None), encoding="utf-8")
        (docs / f"{stem}.html").write_text(cli._stub_for(stem), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return {a: docs / "dist" / "standalone" / f"{s}.html" for a, s in names.items()}


READ = """() => {
  const cs = getComputedStyle(document.documentElement);
  const svg = document.querySelector('oku-diagram svg');
  return {
    accent: cs.getPropertyValue('--accent').trim(),
    soft: cs.getPropertyValue('--accent-soft').trim(),
    strong: cs.getPropertyValue('--accent-strong').trim(),
    diagramWidth: svg ? Math.round(svg.getBoundingClientRect().width) : 0,
    errorCards: document.querySelectorAll('.okd-error-card').length,
  };
}"""


def _read(page, path: Path, *, dark: bool = False) -> dict:
    page.set_viewport_size({"width": 1200, "height": 900})
    # The kit follows the OS unless a reader pins a mode, so emulating
    # the media is the same path a reader takes and needs no stored key.
    page.emulate_media(color_scheme="dark" if dark else "light")
    page.goto(path.as_uri(), wait_until="load")
    diagram_drawn(page)
    page_quiet(page)
    return page.evaluate(READ)


@pytest.fixture(scope="module")
def measured(browser, accent_pages) -> dict[str, dict]:
    pg = browser.new_page(viewport={"width": 1200, "height": 900})
    try:
        return {a: _read(pg, p) for a, p in accent_pages.items()}
    finally:
        pg.close()


@pytest.mark.parametrize("token", TOKENS)
def test_a_documented_token_resolves_to_a_colour(token, measured) -> None:
    """The literal `rose` computed as the string `rose`, which is what
    reached Mermaid."""
    got = measured[token]
    for field in ("accent", "soft", "strong"):
        assert got[field].startswith("#"), f"--accent-{field} for {token} is {got[field]!r}"
    assert got["accent"] != got["soft"] != got["strong"], got


@pytest.mark.parametrize("token", TOKENS)
def test_a_documented_token_still_draws_its_diagrams(token, measured) -> None:
    got = measured[token]
    assert got["errorCards"] == 0, f"{token} produced {got['errorCards']} error card(s)"
    assert got["diagramWidth"] > 50, f"{token} drew a {got['diagramWidth']}px diagram"


def test_the_seven_families_are_seven_families(measured) -> None:
    """`violet` and `green` carried indigo's soft and strong, so the page
    rendered one hue on a callout's rule and indigo on the surface behind
    it. Distinctness is the assertion because a hex pin fails on a
    retune and would not have caught the sharing either."""
    for field in ("accent", "soft", "strong"):
        values = {t: measured[t][field] for t in TOKENS}
        assert len(set(values.values())) == len(TOKENS), f"--accent-{field} is shared: {values}"


def test_a_css_colour_outside_the_map_gets_a_whole_family(measured) -> None:
    """The fallback used to write `--accent` and stop, leaving soft and
    strong on the indigo defaults."""
    got = measured[DERIVED]
    assert got["accent"].startswith("#"), got
    assert got["soft"] != measured["indigo"]["soft"], got
    assert got["strong"] != measured["indigo"]["strong"], got
    assert got["errorCards"] == 0 and got["diagramWidth"] > 50, got


def test_a_word_that_is_not_a_colour_keeps_the_default(measured) -> None:
    """A wrong colour is recoverable; a page of error cards is not."""
    got = measured[NONSENSE]
    plain = measured[""]
    assert got["accent"] == plain["accent"], (got, plain)
    assert got["soft"] == plain["soft"], (got, plain)
    assert got["errorCards"] == 0 and got["diagramWidth"] > 50, got


def test_a_word_that_is_not_a_colour_says_so(page, accent_pages) -> None:
    """Silently keeping the default is the same class of defect one step
    quieter — the author picked a colour and got another one."""
    seen: list[str] = []
    page.on("console", lambda m: seen.append(m.text))
    _read(page, accent_pages[NONSENSE])

    assert [m for m in seen if "accent-unresolved" in m], seen[:12]


@pytest.fixture(scope="module")
def measured_dark(browser, accent_pages) -> dict[str, dict]:
    pg = browser.new_page(viewport={"width": 1200, "height": 900})
    try:
        return {t: _read(pg, accent_pages[t], dark=True) for t in TOKENS}
    finally:
        pg.close()


def test_the_dark_half_is_seven_families_too(measured_dark, measured) -> None:
    """The fallback derived no dark half at all, so the four tokens
    outside the map kept indigo's dark surface — and a reader in dark
    mode got the same page whichever of the four they picked."""
    assert len({measured_dark[t]["soft"] for t in TOKENS}) == len(TOKENS), {
        t: measured_dark[t]["soft"] for t in TOKENS
    }
    for token in TOKENS:
        assert measured_dark[token]["soft"] != measured[token]["soft"], (
            f"{token} paints the same surface in both themes"
        )
        assert measured_dark[token]["errorCards"] == 0, measured_dark[token]
        assert measured_dark[token]["diagramWidth"] > 50, measured_dark[token]


def test_the_dark_pages_really_were_dark(page, accent_pages) -> None:
    """The guard: every assertion above is about a page in dark mode, and
    all of them hold trivially on a page that stayed light."""
    _read(page, accent_pages["rose"], dark=True)

    assert page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
