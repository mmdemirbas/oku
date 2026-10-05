"""A search a Turkish reader types finds what a Turkish author wrote.

The table filter and the in-page search matched `x.toLowerCase()`
against the lowercased query. That is not how Turkish case works:
`'İzmir'.toLowerCase()` is `i̇zmir` — an `i` plus a combining dot — so
`izmir` is not a substring of it, and `'IRMAK'.toLowerCase()` is
`irmak`, which `ırmak` is not. Measured on a `lang: tr` page, in an
en-US and a tr-TR browser alike: the filter emptied the table for
`izmir` and `ırmak`, and the search said "No matches" for both, while
the sidebar filter beside them, which folds through `__okuFuzzy`, found
all of them.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, until

pytestmark = pytest.mark.browser

PAGE_MD = """---
title: Şehirler
lang: tr
summary: Türkçe büyük harfle yazılmış adlar.
---

## Kıyı {#kiyi}

Ege kıyısında İzmir büyük bir liman kentidir.

## Akarsu {#akarsu}

Bu bölümde adı büyük harfle yazılmış bir IRMAK geçiyor.

## Tablo {#tablo}

| Ad | Tür |
|:---|:---|
| İzmir | kent |
| IRMAK | akarsu |
| ılıca | kaynak |
| Ankara | kent |
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("turkish") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Şehirler"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture
def opened(browser, built):
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(built.as_uri(), wait_until="load")
    page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page_quiet(page)
    yield page
    page.close()


VISIBLE_ROWS = """() => [...document.querySelectorAll('.okt-table-wrap tbody tr')]
  .filter((tr) => tr.offsetParent !== null).map((tr) => tr.cells[0].textContent.trim())"""


@pytest.mark.parametrize(("query", "row"), [("izmir", "İzmir"), ("ırmak", "IRMAK"), ("ILICA", "ılıca")])
def test_the_table_filter_folds_turkish_case(opened, query: str, row: str) -> None:
    opened.hover(".okt-table-wrap")
    opened.fill(".okt-table-wrap .okt-filter input", query)
    until(opened, f"() => ({VISIBLE_ROWS})().length === 1", what=f"one row left for {query!r}")
    assert opened.evaluate(VISIBLE_ROWS) == [row]


@pytest.mark.parametrize(("query", "word"), [("izmir", "İzmir"), ("ırmak", "IRMAK")])
def test_the_in_page_search_folds_turkish_case(opened, query: str, word: str) -> None:
    opened.keyboard.press("Control+k")
    until(
        opened,
        "() => document.activeElement === document.querySelector('.search-input')",
        what="the search box has the caret",
    )
    opened.keyboard.type(query)
    until(
        opened,
        "() => document.querySelectorAll('.search-results mark').length > 0",
        what=f"a marked result for {query!r}",
    )
    marked = opened.evaluate(
        "() => [...document.querySelectorAll('.search-results mark')].map((m) => m.textContent)"
    )
    assert word in marked, marked
