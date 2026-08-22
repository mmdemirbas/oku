"""A heading's id is the same answer in all three places that compute it.

Three implementations decided what a heading's id is, and they disagreed
the moment a heading was not written in English:

- `_md_slug` in src/oku/cli.py strips `[^\\w\\s-]`, and Python's `\\w` is
  Unicode-aware — so `## Özet` is `özet` and `## 概述` is `概述`.
- `slugify` in kit/renderer.js stripped `[^a-z0-9\\s-]` — `Özet` became
  `zet`, `概述` became the empty string, and the caller fell back to a
  positional `sec-3` that MOVES when a section is inserted above it.
- `slugify` in kit/chrome.js, which names the h3s under a section, named
  six Turkish letters explicitly and dropped every other script. That is
  what patching one language at a time looks like: two Chinese h3s under
  one section got the same id.

The consequence is not a broken-looking page, which is why it survived.
`oku check` validates a page's `#fragment` links against the Python
answer, so `[Özet](#özet)` passed the check — and in the browser none of
the four links on the probe page landed. In the other direction the
check reported a `duplicate-anchor` between an h2 and an h3 that had
different ids in the DOM, and refused to build a page that was fine.

The explicit escape hatch was the same defect one layer up. CLAUDE.md
tells an author to pin `{#id}` on a translated page, and the renderer's
pattern was `\\{#([\\w-]+)\\}` with JavaScript's ASCII `\\w` — so
`## Explicit {#a-özet}` missed the optional group and rendered with the
literal `{#a-özet}` inside the heading text.

The assertion is end to end rather than a comparison of two sources: the
id Python predicts is read off the rendered DOM, and every authored link
is required to land.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

# One heading per script, plus the shapes that decide a rule: an explicit
# id carrying a non-ASCII letter, a title whose punctuation is dropped,
# and two headings that differ only outside ASCII.
HEADINGS = [
    ("Overview", None),
    ("Özet", None),
    ("Gözden geçirme", None),
    ("İşlem sırası", None),
    ("概述", None),
    ("日本語の見出し", None),
    ("Обзор", None),
    ("Résumé", None),
    ("Ελληνικά", None),
    ("한국어 제목", None),
    ("Punctuation: dropped, mostly!", None),
    ("Explicit", "a-özet"),
    # Decomposed: `e` + U+0301, which is what a macOS-typed title can be.
    ("Cafe\u0301 note", None),
]


def _md() -> str:
    lines = [
        "---",
        "title: Diller",
        "summary: A heading in every script the kit might meet.",
        "---",
        "",
        "Links: " + " · ".join(f"[{title}](#{pinned or cli._md_slug(title)})" for title, pinned in HEADINGS),
        "",
    ]
    for title, pinned in HEADINGS:
        lines.append(f"## {title}" + (f" {{#{pinned}}}" if pinned else ""))
        lines.append("")
        lines.append(f"Body for {title}.")
        lines.append("")
    # Two subheads under one section, distinguishable only outside ASCII.
    lines += ["## Subheads {#subs}", "", "### 数据说明", "", "one", "", "### 説明", "", "two", ""]
    return "\n".join(lines)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("slug") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(_md(), encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Diller"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    # `oku build` refuses to ship a page with an error, so a non-zero rc
    # is itself the check disagreeing with the renderer — that is how the
    # h2-vs-h3 `duplicate-anchor` presented.
    assert rc == 0, "the check rejected a page the renderer draws correctly"
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def rendered(browser, built) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    console: list[str] = []
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console.append(str(e)))
    try:
        page.goto(built.as_uri(), wait_until="load")
        page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        page_quiet(page)
        data = page.evaluate(
            """() => ({
              headings: [...document.querySelectorAll('main h2, main h3')].map(h => ({
                id: h.closest('section[id]') && h.tagName === 'H2'
                      ? h.closest('section[id]').id : h.id,
                text: (h.textContent || '').replace(/\\u00b6|#/g, '').trim(),
              })),
              links: [...document.querySelectorAll('main a[href^="#"]')].map(a => {
                const frag = decodeURIComponent(a.getAttribute('href').slice(1));
                return {frag: frag, lands: !!document.getElementById(frag)};
              }),
              duplicates: (() => {
                const seen = new Set(), dup = [];
                document.querySelectorAll('[id]').forEach(e => {
                  if (seen.has(e.id)) dup.push(e.id);
                  seen.add(e.id);
                });
                return dup;
              })(),
            })"""
        )
        return {**data, "console": console}
    finally:
        page.close()


class TestTheIdIsWhatPythonPredicts:
    def test_the_page_rendered_every_heading(self, rendered) -> None:
        """Every assertion below is satisfied by a page with no headings
        on it, so this one says the page has them."""
        texts = {h["text"] for h in rendered["headings"]}
        missing = [t for t, _ in HEADINGS if t not in texts]
        assert missing == [], missing
        assert rendered["console"] == [], rendered["console"]

    @pytest.mark.parametrize("title,pinned", HEADINGS, ids=[h[0] for h in HEADINGS])
    def test_the_dom_id_is_the_python_slug(self, rendered, title, pinned) -> None:
        want = pinned or cli._md_slug(title)
        got = [h["id"] for h in rendered["headings"] if h["text"] == title]
        assert got == [want], f"{title!r}: DOM {got}, `oku check` expects {want!r}"

    def test_a_pinned_id_is_not_left_in_the_heading_text(self, rendered) -> None:
        left = [h["text"] for h in rendered["headings"] if "{#" in h["text"]]
        assert left == [], left

    def test_every_authored_link_lands(self, rendered) -> None:
        lost = [link["frag"] for link in rendered["links"] if not link["lands"]]
        assert lost == [], lost

    def test_two_subheads_that_differ_outside_ascii_are_two_ids(self, rendered) -> None:
        subs = [h["id"] for h in rendered["headings"] if h["text"] in ("数据说明", "説明")]
        assert len(subs) == 2 and len(set(subs)) == 2, subs

    def test_no_id_is_used_twice(self, rendered) -> None:
        assert rendered["duplicates"] == [], rendered["duplicates"]


class TestThePythonSlugKeepsTheLetters:
    """The Python half on its own, so a failure says which side moved."""

    @pytest.mark.parametrize(
        "text,want",
        [
            ("Overview", "overview"),
            ("Özet", "özet"),
            ("概述", "概述"),
            ("Обзор", "обзор"),
            ("Résumé", "résumé"),
            ("Punctuation: dropped, mostly!", "punctuation-dropped-mostly"),
            ("  spaced  out  ", "spaced-out"),
            ("İşlem sırası", "işlem-sırası"),
            ("Cafe\u0301", "café"),
            ("café", "café"),
            ("---", ""),
            ("", ""),
        ],
    )
    def test_slug(self, text, want) -> None:
        assert cli._md_slug(text) == want
