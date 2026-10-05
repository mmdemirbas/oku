"""A page that writes its own HTML and uses the kit for the chrome alone.

Such a page has its content in the document before chrome.js runs. Served
(`oku serve`, `dist/site`), chrome.js is a deferred script, so the body is
already parsed when it executes, and every `customElements.define` upgrades
the matching element on the spot — running its `connectedCallback` in the
middle of the file, before the top-level state declared further down has
been initialised. `page-chrome` wired the tables and threw on
`OKU_URL_SHAPED`, which leaves the rest of the table wiring undone; a chart
read the label-width constant as undefined and cut its axis titles to an
ellipsis, then threw on its toolbar controller.

Standalone did not show it: there the kit is inlined mid-<head>, the body
is not parsed yet, and every element upgrades after the file has finished.
Found on a delivered report (solo, a 37 KB hand-written page) in dist/site.
"""

from __future__ import annotations

import argparse
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Chrome only</title>
<script src="_oku/chrome-boot.js"></script>
<link rel="stylesheet" href="_oku/chrome.css">
<script src="_oku/chrome.js" defer></script>
</head><body>
<page-chrome></page-chrome>
<div class="layout"><page-toc title="Contents"></page-toc>
<main id="main-content">
<section id="s"><h2>Section</h2>
<table><thead><tr><th>Where</th><th>What</th></tr></thead>
<tbody><tr><td>https://example.org/one/two/three/four</td><td><code>a b c</code></td></tr></tbody></table>
<oku-chart type="line" x-label="Day" y-label="ms"><script type="application/json">
[{"label":"api","data":[{"x":1,"y":142},{"x":2,"y":155},{"x":3,"y":138}]},
 {"label":"auth","data":[{"x":1,"y":88},{"x":2,"y":92},{"x":3,"y":110}]}]
</script></oku-chart>
</section>
</main></div>
</body></html>
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("chromeonly")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.html").write_text(PAGE, encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def loaded(browser, served):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(e.message))
    pg.goto(f"{served}/page.html")
    pg.wait_for_function("() => !!document.querySelector('oku-chart svg')", timeout=20000)
    pg.wait_for_timeout(300)
    yield pg, errors
    pg.close()


def test_the_kit_starts_without_an_error(loaded) -> None:
    _, errors = loaded
    assert errors == [], errors


def test_the_table_wiring_runs_to_the_end(loaded) -> None:
    """The URL breaks at its separators — the last step of the pass that threw."""
    pg, _ = loaded
    assert pg.evaluate("() => document.querySelectorAll('td wbr').length") > 0


def test_a_chart_reads_its_axis_titles_whole(loaded) -> None:
    pg, _ = loaded
    texts = pg.evaluate(
        "() => [...document.querySelectorAll('oku-chart svg text')].map((t) => t.textContent)"
    )
    assert "Day" in texts and "ms" in texts, texts


# The other half. Everything the kit does AFTER content is in place —
# the reading aids that wrap and wire tables, the contents list, the
# rail, the string table — runs on `oku:rendered`, which only the
# renderer fires. A page with its own HTML has no renderer, so nothing
# announced it. Served, the element upgrades above happened to cover the
# tables; standalone, where the kit runs before the body is parsed,
# `page-chrome` upgraded as the parser met it, before any table existed,
# and the delivered file shipped bare tables that pushed a 360px page to
# 630px (solo, found once `oku verify` began checking such pages).


@pytest.fixture(scope="module")
def standalone(tmp_path_factory) -> str:
    d = tmp_path_factory.mktemp("chromeonly-standalone").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.html").write_text(PAGE, encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(d)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return (d / "dist" / "standalone" / "page.html").as_uri()


AFTER_CONTENT = """() => ({
  wrapped: [...document.querySelectorAll('main th')].some(
    (th) => th.textContent === 'Where' && !!th.closest('.okt-table-scroll')),
  toc: [...document.querySelectorAll('page-toc a')].map((a) => a.getAttribute('href')),
  rendered: window.__okuRendered === true,
})"""


@pytest.mark.parametrize("mode", ["served", "standalone"])
def test_the_passes_that_wait_for_content_run(browser, served, standalone, mode) -> None:
    url = f"{served}/page.html" if mode == "served" else standalone
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(e.message))
    try:
        pg.goto(url)
        pg.wait_for_timeout(1500)
        got = pg.evaluate(AFTER_CONTENT)
    finally:
        pg.close()
    assert errors == [], errors
    assert got["wrapped"], got
    assert "#s" in got["toc"], got
    assert got["rendered"], got
