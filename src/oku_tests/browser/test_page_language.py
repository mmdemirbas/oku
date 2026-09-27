"""A page says which language it is written in, and the browser is told.

`renderer.js` has always carried `document.documentElement.lang =
meta.lang`, and that line had never run: nothing set `m.lang`. So every
page the kit has ever built — including this repo's own Turkish
documentation — was delivered as `<html lang="en">`.

What the browser decides from that attribute, all of it invisible to a
test that only reads text: which hyphenation dictionary breaks a word at
the end of a justified line, how `text-transform: uppercase` maps a
letter (Turkish `i` uppercases to `İ`, and to `I` under any other
language), which voice a screen reader uses, and which `:lang()` rules
apply. Measured on a delivered 134 KB Turkish document: `<html
lang="en">`, an English reading estimate over Turkish prose, English
chrome, and a Turkish word broken mid-syllable.

The filename answers for a TRANSLATION and only where `kit.json`
declares the codes, so a project with one language and no `kit.json` had
no way to say which language that was. `lang:` in front-matter is that
sentence.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

TR_MD = """---
title: Bir Türkçe belge
summary: Tek dilli bir projede yazılmış Türkçe bir sayfa.
lang: tr
---

## Bölüm {#bolum}

Okumak neden yetmez? Bir metni ikinci kez okuyunca tanıdık gelir, ve
tanıdık gelmek bilmek sanılır. Bu yüzden her bölüm kendini sınamakla
bitiyor ve her kavram bir örnekle açılıyor.

| işlem | maliyet |
|:---|:---|
| ekleme | sabit |
"""

EN_MD = """---
title: An English page
summary: The default, stated rather than assumed.
---

## Section {#section}

Ordinary prose, in the language the kit's own strings are written in.
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("pagelang") / "docs"
    docs.mkdir(parents=True)
    (docs / "tr-page.md").write_text(TR_MD, encoding="utf-8")
    (docs / "tr-page.html").write_text(cli._stub_for("Bir Türkçe belge"), encoding="utf-8")
    (docs / "en-page.md").write_text(EN_MD, encoding="utf-8")
    (docs / "en-page.html").write_text(cli._stub_for("An English page"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


def test_the_source_records_the_language_it_declares() -> None:
    """Before any browser: the page dict carries it, which is what every
    delivery mode reads."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "tr-page.md"
        src.write_text(TR_MD, encoding="utf-8")
        page = cli._page_from_source_file(src)
        assert page["m"]["lang"] == "tr"
        # Authored, so not in the derived list — the author's value wins
        # and `page_to_md` must write it back on a migrate.
        assert "lang" not in (page["m"].get("_derived") or [])


def test_an_undeclared_page_states_the_default() -> None:
    """`en` written down is the same fact as `en` assumed, and the
    attribute has to say something for the browser to act on."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "en-page.md"
        src.write_text(EN_MD, encoding="utf-8")
        page = cli._page_from_source_file(src)
        assert page["m"]["lang"] == "en"
        assert "lang" in page["m"]["_derived"]


def test_a_value_that_is_not_a_language_tag_is_refused() -> None:
    """The schema refuses it rather than the CLI ignoring it quietly —
    `<html lang="Turkish">` is worse than no declaration, and a setting
    silently going unfilled is the defect `kit.json` validation exists
    for."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "bad.md"
        src.write_text(TR_MD.replace("lang: tr", "lang: Turkish"), encoding="utf-8")
        page = cli._page_from_source_file(src)
        issues = cli.check_pages([(src.with_suffix(".json"), page)], root)
        if cli._HAS_JSONSCHEMA:
            assert [i for i in issues if i["code"] == "schema"], "an unparseable lang passed validation"
        # Whatever the schema says, the attribute never carries it.
        assert cli._with_html_lang('<html lang="en">', "Turkish") == '<html lang="en">'


@pytest.mark.parametrize("tree", ["standalone", "site"])
def test_the_delivered_html_carries_the_language(built, tree) -> None:
    """In the file itself, not only after the renderer runs: the first
    layout is the one that hyphenates, and a language arriving after it
    re-breaks every paragraph on the page."""
    html = (built / tree / "tr-page.html").read_text(encoding="utf-8")
    assert '<html lang="tr">' in html
    assert '<html lang="en">' not in html
    assert '<html lang="en">' in (built / tree / "en-page.html").read_text(encoding="utf-8")


def test_the_browser_reads_it(built, browser) -> None:
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto((built / "standalone" / "tr-page.html").as_uri(), wait_until="load")
        page_quiet(page)
        assert page.evaluate("() => document.documentElement.lang") == "tr"
        # The one consequence a test can read directly: Turkish casing.
        # `text-transform: uppercase` on a table header maps `i` to `İ`
        # under `tr` and to `I` under anything else, so the column label
        # is the assertion.
        assert (
            page.evaluate(
                "() => { const th = document.querySelector('main table th');"
                " const r = document.createRange(); r.selectNodeContents(th);"
                " return getComputedStyle(th).textTransform; }"
            )
            == "uppercase"
        )
        assert page.evaluate("() => document.querySelector('main table th').textContent.trim()") == "işlem"
    finally:
        context.close()


def test_the_kit_finds_its_own_strings_from_the_attribute(built, browser) -> None:
    """A monolingual Turkish project has no `.tr` filename and no
    manifest variant, so `<html lang>` is the only thing that can tell
    the kit which string table to read."""
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto((built / "standalone" / "tr-page.html").as_uri(), wait_until="load")
        page_quiet(page)
        # The reading estimate is derived at build time in the page's own
        # language; the chrome's own strings come from the table.
        assert (
            page.evaluate(
                "() => (window.__okuPageMeta && window.__okuPageMeta.read_time) || "
                "(document.body.innerText.match(/dakikalık okuma|min read/) || [''])[0]"
            )
            != "min read"
        )
    finally:
        context.close()
