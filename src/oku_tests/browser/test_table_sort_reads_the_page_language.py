"""A table sorts numbers and words the way the page's language writes them.

The comparator called `parseFloat` on the cell, so `4,400,000` was 4,
and an ascending sort put 4,400,000 before 5, 7 and 12,000. Words were
compared with `toLowerCase().localeCompare()` and no locale, so a
Turkish column sorted in the BROWSER's order: on an en-US browser
`ılıca` came after `İzmir`, and the dotless `I` of `IRMAK` landed among
the i-words. The page says which language it is in (`<html lang>`), so
that is the language to sort in — including which character separates
thousands, which is `,` in English and `.` in Turkish.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet, until

pytestmark = pytest.mark.browser


def _page(lang: str, numbers: list[str], words: list[str]) -> str:
    rows = "\n".join(f"| {w} | {n} |" for w, n in zip(words, numbers, strict=True))
    return f"""---
title: Sort
lang: {lang}
summary: One table to sort.
---

## Table {{#table}}

| Name | Amount |
|:---|---:|
{rows}
"""


CASES = {
    "en": (
        ["4,400,000", "5", "12,000", "900", "2.5"],
        ["Delta", "alpha", "Charlie", "bravo", "echo"],
        ["2.5", "5", "900", "12,000", "4,400,000"],
        ["alpha", "bravo", "Charlie", "Delta", "echo"],
    ),
    "tr": (
        ["4.400.000", "5", "12.000", "900", "2,5"],
        ["İzmir", "ılıca", "Ankara", "IRMAK", "iğne"],
        ["2,5", "5", "900", "12.000", "4.400.000"],
        ["Ankara", "ılıca", "IRMAK", "iğne", "İzmir"],
    ),
}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tablesort") / "docs"
    docs.mkdir()
    for lang, (numbers, words, _, _) in CASES.items():
        (docs / f"{lang}.md").write_text(_page(lang, numbers, words), encoding="utf-8")
        (docs / f"{lang}.html").write_text(cli._stub_for("Sort"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone"


COLUMN = """(i) => [...document.querySelectorAll('.okt-table-wrap tbody tr')]
  .filter((tr) => tr.offsetParent !== null).map((tr) => tr.cells[i].textContent.trim())"""


def _sorted_by(page, col: int) -> list[str]:
    before = page.evaluate(COLUMN, col)
    page.locator(".okt-table-wrap thead th").nth(col).click()
    until(
        page, f"() => JSON.stringify(({COLUMN})({col})) !== {before!r}".replace("'", '"'), what="the sort ran"
    )
    return page.evaluate(COLUMN, col)


@pytest.mark.parametrize("lang", sorted(CASES))
def test_numbers_sort_by_value_in_the_page_language(browser, built, lang: str) -> None:
    page = browser.new_page()
    page.goto((built / f"{lang}.html").as_uri(), wait_until="load")
    page_quiet(page)
    assert _sorted_by(page, 1) == CASES[lang][2]
    page.close()


@pytest.mark.parametrize("lang", sorted(CASES))
def test_words_sort_in_the_page_language(browser, built, lang: str) -> None:
    page = browser.new_page(locale="en-US")
    page.goto((built / f"{lang}.html").as_uri(), wait_until="load")
    page_quiet(page)
    assert _sorted_by(page, 0) == CASES[lang][3]
    page.close()
