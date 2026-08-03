"""Render-side regression for NESTED inline markdown.

The inline parser used to emit each construct's body as literal text, so
anything wrapped in emphasis lost its markup: `**[a](b)**` rendered as
the characters `[a](b)` in bold, and `[**a**](b)` as `**a**` inside a
link. Authors worked around it by moving links out of the bold run.

Bodies now parse recursively, so emphasis, links, code and the kit's
`#g/` glossary links compose in either nesting order. Only a code span
keeps a literal body — that is the rule that protects it.

Served as a v2 page from a tmp dir with an `_oku` symlink to the live
kit/; the package auto-skips when chromium isn't installed.
"""

from __future__ import annotations

import http.server
import json
import threading
from functools import partial
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

X = "https://example.com/x"
Y = "https://example.com/y"

PAGE = {
    "k": "page",
    "t": "Iç içe satır içi biçimler",
    "b": [
        "## Test {#t}\n\n"
        f"Bold sarmalı: **[bir bağlantı]({X}) kalın içinde**.\n\n"
        f"Ters yön: [**kalın** bir bağlantı içinde]({Y}).\n\n"
        "Kod: **`kalın kod`** ve vurgu: **kalın içinde *vurgu* var**.\n\n"
        "Sözlük: **[terim](#g/iceberg)**.\n\n"
        "Boşluklu kimlik: [makale](#x/Iceberg paper) ve [zaman](#g/Time travel).\n\n"
        "Normal bağlantı boşluk kabul etmez: [kırık](http://a b) düz metin kalır.\n\n"
        "Literal kod: `**[a](b)**` aynen kalmalı.\n"
    ],
}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("inlinemd")
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


def test_link_inside_bold_is_a_link(page, served):
    page.goto(served)
    page.wait_for_timeout(800)
    a = page.locator(f'strong > a[href="{X}"]')
    assert a.count() == 1, "a link inside ** ** must render as <a>, not literal text"
    assert a.inner_text().strip() == "bir bağlantı"


def test_bold_inside_link_keeps_its_markup(page, served):
    page.goto(served)
    page.wait_for_timeout(800)
    assert page.locator(f'a[href="{Y}"] > strong').count() == 1


def test_code_and_em_nest_inside_bold(page, served):
    page.goto(served)
    page.wait_for_timeout(800)
    assert page.locator("strong > code").count() == 1
    assert page.locator("strong > em").count() == 1
    assert page.locator("strong > em").inner_text().strip() == "vurgu"


def test_glossary_link_inside_bold_stays_a_glossary_term(page, served):
    page.goto(served)
    page.wait_for_timeout(800)
    gt = page.locator("strong > glossary-term")
    assert gt.count() == 1
    assert gt.get_attribute("term") == "iceberg"


def test_multi_word_registry_ids_resolve(page, served):
    """`#g/` and `#x/` ids are human-readable registry keys and most of
    them contain spaces ("Iceberg paper", "Time travel"). GFM forbids
    whitespace in a link destination, so those references rendered as
    literal text — the kit prefixes are the documented exception."""
    page.goto(served)
    page.wait_for_timeout(800)
    assert page.locator('ext-ref[name="Iceberg paper"]').count() == 1
    assert page.locator('glossary-term[term="Time travel"]').count() == 1


def test_plain_link_still_rejects_whitespace(page, served):
    """The exception is scoped to the kit prefixes — an ordinary
    destination with a space stays literal, as GFM specifies."""
    page.goto(served)
    page.wait_for_timeout(800)
    assert page.locator('a[href="http://a b"]').count() == 0
    body = page.eval_on_selector("main", "el => el.innerText")
    assert "[kırık](http://a b)" in body


def test_code_span_body_stays_literal(page, served):
    """Recursion must not reach inside a code span — the one construct
    whose body is by definition literal."""
    page.goto(served)
    page.wait_for_timeout(800)
    codes = page.eval_on_selector_all("code", "els => els.map(e => e.textContent)")
    assert "**[a](b)**" in codes
    assert page.locator("code strong").count() == 0


def test_no_literal_markdown_leaks_into_prose(page, served):
    """Nothing in the rendered prose still reads as markdown source —
    except the one paragraph that deliberately carries an invalid
    destination (see test_plain_link_still_rejects_whitespace)."""
    page.goto(served)
    page.wait_for_timeout(800)
    leaks = page.eval_on_selector_all(
        "main p",
        "els => els.filter(e => !e.querySelector('code'))"
        ".map(e => e.innerText).filter(t => t.includes('](') || t.includes('**'))",
    )
    assert leaks == ["Normal bağlantı boşluk kabul etmez: [kırık](http://a b) düz metin kalır."], leaks
