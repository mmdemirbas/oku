"""Inline HTML an author writes in prose must render, not be typed out.

Two lists decided what "inline HTML" means and they disagreed.
`INLINE_HTML_TAGS` said which tags never open an island — `a`, `code`,
`em`, `strong` among them — so a paragraph carrying one stayed prose.
The inline parser then rendered a SHORTER set (kbd, sub, sup, mark,
abbr, del, ins, samp, span) and left everything else as literal text.

The overlap gap is what shipped: a delivered page showed
`<code>yıldızları→yıldızların</code>` and `<b>aynı kök</b>` as visible
angle brackets inside a compare-grid card, and `oku check --strict` was
clean on it.

`b` and `i` were in neither list, which made the same tag behave two
ways: at the start of a paragraph it opened an island and rendered
bold; one word later it was typed out.

One list now drives both rules. These cases cover prose, a typed
block's string field (where it was found), and the boundary — a tag
outside the set still stays literal, and it must stay inert.
"""

from __future__ import annotations

from ._wait import page_quiet

import http.server
import json
import re
import threading
from functools import partial
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

HREF = "https://example.com/inline"

# Derived from the source, not copied: a tag added to INLINE_HTML_TAGS
# and not to the render path fails here on the day it is added, which is
# the only day anyone is looking. `br` carries no body and gets its own
# case below; `a` needs a destination and gets one.
_TAGS = sorted(
    set(
        re.findall(
            r"'([a-z]+)'",
            re.search(
                r"const INLINE_HTML_TAGS = \[(.*?)\];",
                (KIT / "renderer.js").read_text(encoding="utf-8"),
                re.S,
            ).group(1),
        )
    )
    - {"br"}
)
_ATTRS = {"a": ' href="https://example.com/sweep"'}

PAGE = {
    "k": "page",
    "t": "Satır içi HTML",
    "b": [
        "## Prose {#prose}\n\n"
        "Bold: <b>aynı kök, farklı ek</b> ve italik: <i>eğik</i>.\n\n"
        "Kod: <code>yıldızları→yıldızların</code> tam olarak böyle.\n\n"
        f'Bağlantı: <a href="{HREF}">bir bağlantı</a> burada.\n\n'
        "Vurgu: <strong>kalın</strong> ve <em>vurgu</em>.\n\n"
        "Bilinmeyen: <blooper>bu düz metin</blooper> kalmalı.\n\n"
        "Kod aralığı korunur: `<b>literal</b>` aynen.\n",
        {
            "k": "compare-grid",
            "cards": [
                {
                    "t": "Sese yakın",
                    "accent": "accent",
                    "b": "30'u tam olarak <b>aynı kök, farklı ek</b>: "
                    "<code>ilimler→ilimleri</code>, <code>kudret→kudüret</code>.",
                }
            ],
        },
        "## Sonra {#sonra}\n\nBu paragraf kartın dışında kalmalı.\n",
        "## Her etiket {#hepsi}\n\n"
        + "\n\n".join(f"Etiket {t}: <{t}{_ATTRS.get(t, '')}>gövde-{t}</{t}> sonrası." for t in _TAGS)
        + "\n\nSatır sonu: bir<br>iki.\n",
    ],
}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("inlinehtml")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [{"path": "page.html", "source": "page.json", "title": PAGE["t"], "parent": None}],
    }
    (d / "page.html").write_text(cli._stub_for(PAGE["t"], inline_manifest=manifest), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    httpd.shutdown()


def _text(page):
    return page.eval_on_selector("main", "el => el.innerText")


def test_no_tag_is_typed_out_anywhere_on_the_page(page, served):
    """The reported symptom, stated as the reader sees it: a tag the kit
    accepts must never appear as characters. The one deliberate literal
    is inside a code span, which is excluded by construction."""
    page.goto(served)
    page_quiet(page)
    leaked = page.eval_on_selector_all(
        "main p, main .compare-card",
        "els => els.map(e => { const c = e.cloneNode(true);"
        " c.querySelectorAll('code').forEach(n => n.remove());"
        " return c.innerText; })"
        ".filter(t => /<\\/?(b|i|code|a|strong|em)\\b[^>]*>/.test(t))",
    )
    assert leaked == [], leaked


def test_bold_and_italic_render_mid_paragraph(page, served):
    page.goto(served)
    page_quiet(page)
    assert page.locator("main p > b").count() >= 1
    assert page.locator("main p > b").first.inner_text().strip() == "aynı kök, farklı ek"
    assert page.locator("main p > i").first.inner_text().strip() == "eğik"


def test_code_renders_mid_paragraph(page, served):
    """`code` was already declared inline by the island rule, so it never
    opened an island — and the inline parser did not render it either."""
    page.goto(served)
    page_quiet(page)
    texts = page.eval_on_selector_all("main p > code", "els => els.map(e => e.textContent)")
    assert "yıldızları→yıldızların" in texts


def test_anchor_renders_with_its_href(page, served):
    page.goto(served)
    page_quiet(page)
    a = page.locator(f'main p > a[href="{HREF}"]')
    assert a.count() == 1
    assert a.inner_text().strip() == "bir bağlantı"


def test_strong_and_em_render(page, served):
    page.goto(served)
    page_quiet(page)
    assert page.locator("main p > strong").first.inner_text().strip() == "kalın"
    assert page.locator("main p > em").first.inner_text().strip() == "vurgu"


def test_a_typed_block_string_field_renders_the_same_html(page, served):
    """Where it was found: a compare-grid card body, not a prose line.
    Every typed renderer that takes markdown runs the same parser, so the
    card is the case that proves the fix reaches them."""
    page.goto(served)
    page_quiet(page)
    card = page.locator(".compare-card").first
    assert card.locator("b").count() == 1
    codes = card.locator("code")
    assert codes.count() == 2
    assert codes.first.inner_text().strip() == "ilimler→ilimleri"


def test_a_tag_outside_the_set_stays_literal(page, served):
    """The pass-through is an allow-list, not a parser. An unknown tag
    keeps the old behaviour — visible text, nothing constructed."""
    page.goto(served)
    page_quiet(page)
    assert "<blooper>" in _text(page)
    assert page.locator("blooper").count() == 0


def test_a_code_span_still_protects_its_body(page, served):
    page.goto(served)
    page_quiet(page)
    codes = page.eval_on_selector_all("main code", "els => els.map(e => e.textContent)")
    assert "<b>literal</b>" in codes
    assert page.locator("main code b").count() == 0


@pytest.mark.parametrize("tag", _TAGS)
def test_every_declared_inline_tag_renders_as_that_element(page, served, tag):
    """Declaring a tag inline and not drawing it is the defect this file
    exists for, so the case list comes from the declaration itself."""
    page.goto(served)
    page_quiet(page)
    el = page.locator(f"main p > {tag}").filter(has_text=f"gövde-{tag}")
    assert el.count() == 1, f"<{tag}> did not render as an element"
    assert el.inner_text().strip() == f"gövde-{tag}"


def test_br_renders_as_a_line_break(page, served):
    """The one inline tag held out of the pass-through, because a void
    element has no body to parse. Held out is not unsupported."""
    page.goto(served)
    page_quiet(page)
    assert page.locator("main p > br").count() == 1


def test_inline_html_does_not_swallow_the_rest_of_the_page(page, served):
    """A tag rendered mid-paragraph must not be mistaken for an island
    opening — the section after the compare-grid still stands alone."""
    page.goto(served)
    page_quiet(page)
    assert page.locator("#sonra").count() == 1
    assert "Bu paragraf kartın dışında kalmalı." in _text(page)
