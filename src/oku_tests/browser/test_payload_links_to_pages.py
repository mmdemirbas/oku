"""A link written in a block's payload goes where a prose link goes.

A prose link `[x](other.md)` is rewritten to `other.html`, because the
built tree holds the rendered page and not its source. A step-flow card,
a compare-grid card and a table row carry their link as a payload string,
and each set it on the element raw — so in both built trees the card
pointed at `other.md`, which is not there, and clicking it was a dead
link. `oku check` resolves `other.md` against the source tree and reports
`other.html` as unresolved, so the author had no spelling that was both
clean and working. Found on a five-page delivered report whose index was
a grid of step-flow cards.

The two cards also skipped `safeUrl`, which every other link in the kit
goes through: a `javascript:` destination in a card ran on click.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser


def _fence(tag: str, payload: dict) -> str:
    return f"```{tag}\n{json.dumps(payload)}\n```\n"


INDEX = (
    "---\ntitle: Index\n---\n\n## Links {#links}\n\nProse to [the other page](other.md).\n\n"
    + _fence(
        "oku-step-flow",
        {
            "ordered": False,
            "steps": [
                {"t": "Step", "b": "To a page.", "href": "other.md"},
                {"t": "Step frag", "b": "To a section.", "href": "other.md#part"},
                {"t": "Script", "b": "Must not run.", "href": "javascript:alert(1)"},
            ],
        },
    )
    + "\n"
    + _fence(
        "oku-compare-grid",
        {
            "cards": [
                {"t": "Card", "b": "To a page.", "href": "other.md"},
                {"t": "Script", "b": "Must not run.", "href": "javascript:alert(1)"},
            ]
        },
    )
    + "\n"
    + _fence(
        "oku-table",
        {"headers": ["Page"], "rows": [{"cells": ["other"], "href": "other.md"}]},
    )
)
OTHER = "---\ntitle: Other\n---\n\n## Part {#part}\n\nThe other page.\n"


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    docs = tmp_path_factory.mktemp("payloadlinks") / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(INDEX, encoding="utf-8")
    (docs / "other.md").write_text(OTHER, encoding="utf-8")
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "_oku").symlink_to(Path(cli.__file__).resolve().parents[2] / "kit", target_is_directory=True)
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs


LINKS = """() => ({
  prose: document.querySelector('main p a[href]')?.getAttribute('href'),
  steps: [...document.querySelectorAll('main .step-card')].map(c => c.getAttribute('href')),
  cards: [...document.querySelectorAll('main .compare-card')].map(c => c.getAttribute('href')),
  row: document.querySelector('main tr[data-href]')?.getAttribute('data-href') || null,
})"""

EXPECT = {
    "prose": "other.html",
    "steps": ["other.html", "other.html#part", None],
    "cards": ["other.html", None],
    "row": "other.html",
}


def _links(browser, url: str) -> dict:
    pg = browser.new_page()
    try:
        pg.goto(url, wait_until="load")
        page_quiet(pg)
        return pg.evaluate(LINKS)
    finally:
        pg.close()


def test_standalone(browser, tree) -> None:
    assert _links(browser, (tree / "dist" / "standalone" / "index.html").as_uri()) == EXPECT


def test_site(browser, tree) -> None:
    site = tree / "dist" / "site"
    handler = functools.partial(cli._VerifySiteHandler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        got = _links(browser, f"http://127.0.0.1:{httpd.server_address[1]}/index.html")
    finally:
        httpd.shutdown()
    assert got == EXPECT


def test_the_target_exists_in_both_trees(tree) -> None:
    """The rewrite is only right if the page it names was written."""
    for sub in ("standalone", "site"):
        assert (tree / "dist" / sub / "other.html").is_file(), sub
