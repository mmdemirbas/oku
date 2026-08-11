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

    def refuse(route, request):
        reached.append(request.url)
        route.abort()

    pg.route("http://**", refuse)
    pg.route("https://**", refuse)
    pg.goto(vendored_page.as_uri())
    pg.wait_for_selector("main section")
    pg.wait_for_function(
        "() => { const d = document.querySelectorAll('oku-diagram');"
        "        return [...d].every((x) => x._rendered || /Parse error/.test(x.textContent)); }",
        timeout=30000,
    )
    state = pg.evaluate(STATE)
    pg.close()
    return state, reached


def test_the_diagram_draws_with_no_network(offline_state) -> None:
    state, _ = offline_state
    assert state["diagrams"] == 1, state
    assert state["broken"] == 0, f"the diagram did not render offline: {state}"
    assert state["drawn"] == 2, f"the diagram drew no nodes: {state}"


def test_the_code_is_highlighted_with_no_network(offline_state) -> None:
    state, _ = offline_state
    assert state["tokens"] > 0, f"no syntax highlighting offline: {state}"
    assert state["lineNumbers"] == 2, state


def test_nothing_reaches_for_a_cdn(offline_state) -> None:
    """The fallback makes silence the only proof. A page that quietly
    fetched mermaid would satisfy every assertion above."""
    _, reached = offline_state
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
