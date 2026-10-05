"""Wiring a table twice is wiring it once.

`initReadingAids` runs again on `oku:rendered`, when the file viewer
opens, and when page-chrome connects — and its table pass collects every
`table:not([data-okt-bound])`. The List view builds each row as its own
`<table class="okt-list-card">`, created after the first collection and
never marked, so the next pass wrapped every card in a full table
toolbar of its own. Measured on the reference tables page: expand
buttons went from 5 to 29, and a List view row drew a copy / copy-md /
expand bar over an empty pill.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

ROWS = "\n".join(f"| row{i} | {i} | note {i} |" for i in range(4))
PAGE_MD = f"""---
title: Tables
summary: One table, wired more than once.
---

## Data {{#data}}

| Name | Count | Note |
|:---|---:|:---|
{ROWS}
"""

COUNTS = """() => ({
  wraps: document.querySelectorAll('.okt-table-wrap').length,
  bound: document.querySelectorAll('table[data-okt-bound]').length,
  expand: document.querySelectorAll('.okt-table-wrap [data-action="expand"], .okt-table-wrap .okt-expand, .okt-table-wrap button[aria-label*="xpand"]').length,
})"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("tablewire") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Tables"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


def test_a_second_render_pass_adds_no_table_controls(built, page):
    page.goto(built.as_uri(), wait_until="load")
    page_quiet(page)
    first = page.evaluate(COUNTS)
    assert first["wraps"] == 1, first
    for _ in range(2):
        page.evaluate("() => window.dispatchEvent(new Event('oku:rendered'))")
        page_quiet(page)
    again = page.evaluate(COUNTS)
    assert again == first, f"a re-run of the wiring changed the table chrome: {first} -> {again}"
