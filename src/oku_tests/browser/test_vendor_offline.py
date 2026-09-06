"""A built page draws its diagrams and colours its code with no network.

mermaid and Prism were fetched from a CDN at runtime. Measured on the
built docs/architecture.html with the CDN blocked: every diagram failed
and the syntax highlighting disappeared entirely. Line numbers survived,
having been made independent of the CDN earlier.

Inlining them per page is the obvious repair and the wrong one — mermaid
alone is 3.3 MB against a 1.1 MB page, and a tree pays that for every
page that draws anything. The bytes are identical across documents, so
they are fetched once and shared from `_oku/vendor/`. Offline does not
require a single file; it requires the bytes to be reachable.

The CDN remains as the fallback, which is why these tests block the
network outright rather than trusting that it was not used: a page that
quietly reached the CDN would pass every assertion about what it drew.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from . import _wait

from oku import cli


PAGE_MD = """---
title: Vendored
summary: Diagrams and highlighting with no network at all.
---

## Figure and code {#surfaces}

Lead paragraph.

```mermaid
flowchart LR
  A["write"] --> B["read"]
```

```python
def f(x):
    return x + 1
```
"""


@pytest.fixture(scope="module")
def vendored_page(tmp_path_factory):
    if not cli.vendor_is_complete():
        pytest.skip("vendor cache absent — run `oku vendor`")
    docs = tmp_path_factory.mktemp("vendored") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Vendored"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    out = docs / "dist" / "standalone" / "page.html"
    assert out.exists()
    return out


STATE = """() => ({
  diagrams: document.querySelectorAll('oku-diagram').length,
  drawn: document.querySelectorAll('oku-diagram svg .node').length,
  broken: [...document.querySelectorAll('oku-diagram')]
            .filter(d => /Parse error|loading/i.test(d.textContent)).length,
  tokens: document.querySelectorAll('pre code .token').length,
  lineNumbers: document.querySelectorAll('.okt-code-line').length,
})"""


@pytest.fixture(scope="module")
def offline_state(browser, vendored_page):
    """Load the page with every network origin refused."""
    pg = browser.new_page()
    reached = []
    calls = [0]

    def refuse(route, request):
        calls[0] += 1
        if not request.url.startswith(("http://", "https://")):
            route.continue_()
            return
        reached.append(request.url)
        route.abort()

    # `**/*`, not `https://**`. The scheme-prefixed glob matches NOTHING
    # in this Playwright version — measured: route fires 0 times and the
    # CDN answers 200 — so this fixture blocked nothing at all, and the
    # assertion that nothing reached a CDN was true only because the
    # callback that records the reaching never ran. Every test in this
    # file passed against a live CDN, which is how a dist/site tree that
    # shipped without its vendored copy at all got past them.
    pg.route("**/*", refuse)
    pg.goto(vendored_page.as_uri())
    pg.wait_for_selector("main section")
    pg.wait_for_function(
        "() => { const d = document.querySelectorAll('oku-diagram');"
        "        return [...d].every((x) => x._rendered || /Parse error/.test(x.textContent)); }",
        timeout=30000,
    )
    state = pg.evaluate(STATE)
    pg.close()
    return state, reached, calls[0]


def test_the_diagram_draws_with_no_network(offline_state) -> None:
    state, _, _ = offline_state
    assert state["diagrams"] == 1, state
    assert state["broken"] == 0, f"the diagram did not render offline: {state}"
    assert state["drawn"] == 2, f"the diagram drew no nodes: {state}"


def test_the_code_is_highlighted_with_no_network(offline_state) -> None:
    state, _, _ = offline_state
    assert state["tokens"] > 0, f"no syntax highlighting offline: {state}"
    assert state["lineNumbers"] == 2, state


def test_nothing_reaches_for_a_cdn(offline_state) -> None:
    """The fallback makes silence the only proof. A page that quietly
    fetched mermaid would satisfy every assertion above."""
    _, reached, calls = offline_state
    # The route has to have RUN. `page.route("https://**", …)` matched
    # nothing here and made this assertion true by never recording a
    # thing — for months, against a live CDN.
    assert calls > 0, "the route never fired — this test proves nothing"
    cdn = [u for u in reached if "jsdelivr" in u or "unpkg" in u]
    assert cdn == [], f"the page went to a CDN despite a local copy: {cdn}"


def test_the_dependencies_are_shared_not_inlined(vendored_page) -> None:
    """The point of vendoring rather than inlining. mermaid is 3.3 MB;
    a page that swallowed it would be unopenable as mail and the tree
    would carry one copy per page."""
    tree = vendored_page.parent
    shared = tree / "_oku" / "vendor" / "mermaid.min.js"

    assert shared.is_file(), "no shared copy beside the pages"
    assert shared.stat().st_size > 1_000_000, shared.stat().st_size
    assert vendored_page.stat().st_size < 2_000_000, (
        f"the page is {vendored_page.stat().st_size} bytes — a dependency got inlined"
    )


# ---------- the same promise, in the other built tree ----------
#
# Everything above drives dist/standalone/. dist/site/ is the tree that
# gets DEPLOYED — to an intranet, a shared drive, a laptop with no
# route out — and it was built from a different recipe: build_site never
# copied vendor/ at all, and the loader was told there was no local Prism
# because the flag saying so was injected by build_standalone alone.
# Measured on this repo's own site build with the CDNs blocked: 0 of 6
# diagrams drawn, 0 highlight tokens, against 6 and 598 for the same
# pages built standalone. Both failures are invisible with a network,
# which is the whole reason the copy exists.


@pytest.fixture(scope="module")
def site_tree(tmp_path_factory):
    if not cli.vendor_is_complete():
        pytest.skip("vendor cache absent — run `oku vendor`")
    docs = tmp_path_factory.mktemp("vendored-site") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Vendored"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    site = docs / "dist" / "site"
    assert (site / "page.html").exists()
    return site


@pytest.fixture(scope="module")
def site_offline_state(browser, site_tree):
    """dist/site over HTTP with every non-local origin refused."""
    import functools
    import http.server
    import threading

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_tree))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/page.html"

    pg = browser.new_page()
    reached = []
    calls = [0]

    def route(r, request):
        calls[0] += 1
        if "127.0.0.1" in request.url or not request.url.startswith(("http://", "https://")):
            r.continue_()
            return
        reached.append(request.url)
        r.abort()

    pg.route("**/*", route)  # see the note on the standalone fixture above
    pg.goto(url)
    pg.wait_for_selector("main section")
    pg.wait_for_function(
        "() => { const d = document.querySelectorAll('oku-diagram');"
        "        return [...d].every((x) => x._rendered || /Parse error/.test(x.textContent)); }",
        timeout=30000,
    )
    # The diagram wait above says Mermaid is done; STATE also counts
    # Prism's tokens and the line-number spans, which land on their own
    # schedule when the grammar arrives. Waiting for the whole tuple to
    # stop moving is the condition — a fixed 1.5 s was a guess at how
    # long the slowest of the three takes.
    _wait.stable(pg, STATE, what="the offline page finished drawing and highlighting")
    state = pg.evaluate(STATE)
    pg.close()
    httpd.shutdown()
    return state, reached, calls[0]


def test_the_site_build_carries_the_shared_copy(site_tree) -> None:
    shared = site_tree / "_oku" / "vendor" / "mermaid.min.js"
    assert shared.is_file(), "dist/site ships without the dependencies it needs offline"


def test_the_site_build_draws_and_highlights_with_no_internet(site_offline_state) -> None:
    state, _, _ = site_offline_state
    assert state["broken"] == 0, f"the diagram did not render: {state}"
    assert state["drawn"] == 2, f"the diagram drew no nodes: {state}"
    # python is an autoloader COMPONENT, not part of prism core — this is
    # the assertion that fails when languages_path points at the CDN.
    assert state["tokens"] > 0, f"no syntax highlighting: {state}"


def test_the_site_build_reaches_no_cdn_either(site_offline_state) -> None:
    _, reached, calls = site_offline_state
    assert calls > 0, "the route never fired — this test proves nothing"
    cdn = [u for u in reached if "jsdelivr" in u or "unpkg" in u]
    assert cdn == [], f"dist/site went to a CDN despite a local copy: {cdn}"
