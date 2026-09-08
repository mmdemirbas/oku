"""Moving around inside a standalone page must not reach the network.

The hash router is shared with the served modes, where a hash names a
PAGE and fetching its JSON is the whole job. A standalone file has its
page inline and is the only page it can render — but the router did not
know that, so every hash change went to __okuFetchAndRender for
`<page>.json` and file:// refused it. Clicking a row of the on-page
contents put "Fetch API cannot load … URL scheme "file" is not
supported" on the reader's console. The scroll still worked, which is
how it survived: nothing broke, it just said it did.
"""

from __future__ import annotations

from ._wait import page_quiet, scroll_stable, settled

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

PAGE_MD = """---
title: Navigation
summary: Anchors, a contents list, and no network.
---

> [!TLDR]
> Clicking around must stay inside the file.

## First section {#first}

Text with a [link to the second](#second).

## Second section {#second}

More text.

## Third section {#third}

Still more.
"""


@pytest.fixture(scope="module")
def standalone_page(tmp_path_factory):
    docs = tmp_path_factory.mktemp("nav") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Navigation"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    return docs / "dist" / "standalone" / "page.html"


def _errors_during(page, url, action):
    errs: list[str] = []
    page.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"[:160]))
    page.goto(url, wait_until="load")
    page_quiet(page)
    errs.clear()
    action()
    # The list this returns is built by Playwright handlers in PYTHON, so
    # the page cannot be asked about it — what is waited for is the list
    # itself holding still. An error that arrives late still lands in it;
    # a fixed delay only decides how late is too late, without saying so.
    settled(lambda: len(errs), what="the console stopped reporting")
    cdn = ("jsdelivr", "googleapis", "gstatic", "fonts.")
    return [e for e in errs if not any(k in e for k in cdn)]


def test_clicking_a_contents_row_reaches_no_network(page, standalone_page):
    url = standalone_page.as_uri()
    errs = _errors_during(
        page, url, lambda: page.evaluate("document.querySelector('page-nav page-toc a')?.click()")
    )
    assert errs == [], f"clicking the contents produced: {errs}"
    assert page.evaluate("location.hash"), "the click did not move to an anchor at all"


def test_an_in_page_link_reaches_no_network(page, standalone_page):
    url = standalone_page.as_uri()
    errs = _errors_during(
        page, url, lambda: page.evaluate("document.querySelector('main a[href^=\"#\"]')?.click()")
    )
    assert errs == [], f"following an in-page link produced: {errs}"


def test_the_anchor_still_scrolls(page, standalone_page):
    """The fix must not turn the error into a dead link."""
    page.goto(standalone_page.as_uri(), wait_until="load")
    page_quiet(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.evaluate("location.hash = '#third'")
    # The kit scrolls smoothly, so the position right after the hash is
    # set is the start of the animation and not the answer.
    scroll_stable(page)
    assert page.evaluate("window.scrollY") > 100, "the anchor did not scroll anywhere"
