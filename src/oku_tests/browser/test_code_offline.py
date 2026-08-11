"""Line numbers and folds do not depend on a third-party CDN.

Numbering a line needs no grammar. The pass that does it was reachable
only through Prism's `complete` hook, so every block that declared a
language lost its gutter whenever the CDN was unreachable — measured on
the built `docs/charts.html` with the network blocked: 51 code blocks,
0 gutters, and a standalone file is the artifact that exists FOR
reading offline.

Both states are asserted here. Restoring the offline case is worth
nothing if it changes what an online reader gets.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# Two blocks that declare a language (so Prism owns them) and one that
# does not (so the local pass owns it) — the bug was in the first kind
# only, and a test that used the second would have passed unfixed.
MD = """---
title: Code
summary: Blocks with and without a language.
---

## Blocks {#blocks}

```python
def render(page):
    for block in page:
        emit(block)
    return True
```

```json
{"type": "bar", "rows": [{"label": "a", "value": 1}]}
```

```
plain text, no language declared
```
"""

PROBE = """() => ({
  codeBlocks: document.querySelectorAll('pre code').length,
  numbered: document.querySelectorAll('pre.okt-line-numbered').length,
  lineNumbers: document.querySelectorAll('.okt-code-ln').length,
  highlighted: document.querySelectorAll('pre code .token').length,
})"""


@pytest.fixture(scope="module")
def code_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("code")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "page.md").write_text(MD, encoding="utf-8")
    (d / "page.html").write_text(cli._stub_for("Code"), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _measure(browser, code_url, *, offline: bool):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    if offline:
        # Prism now has a same-origin vendored copy, so blocking the CDN
        # alone no longer produces the state this file is about — the
        # highlighter simply loads locally. What is being asserted is
        # that the GUTTER does not depend on the highlighter arriving at
        # all, so both sources are cut.
        ctx.route("**cdn.jsdelivr.net**", lambda route: route.abort())
        ctx.route("**/_oku/vendor/**", lambda route: route.abort())
    pg = ctx.new_page()
    try:
        pg.goto(f"{code_url}/page.html")
        # Longer than PRISM_FALLBACK_MS so the timer path is covered too.
        pg.wait_for_timeout(5000)
        return pg.evaluate(PROBE)
    finally:
        pg.close()
        ctx.close()


def test_line_numbers_survive_without_the_cdn(browser, code_url):
    got = _measure(browser, code_url, offline=True)
    assert got["codeBlocks"] == 3, got
    assert got["numbered"] == 3, got
    # 4 + 1 + 1 source lines across the three blocks.
    assert got["lineNumbers"] == 6, f"blocks lost their gutter with no highlighter: {got}"
    assert got["highlighted"] == 0, f"tokens appeared with every Prism source blocked: {got}"


def test_the_vendored_copy_highlights_when_the_cdn_is_gone(browser, code_url):
    """The capability the vendored copy adds. Blocking only the CDN used
    to mean no highlighting at all; now it means the local copy answers,
    and this is what distinguishes the two from each other."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.route("**cdn.jsdelivr.net**", lambda route: route.abort())
    pg = ctx.new_page()
    try:
        pg.goto(f"{code_url}/page.html")
        pg.wait_for_timeout(5000)
        got = pg.evaluate(PROBE)
    finally:
        pg.close()
        ctx.close()

    if not cli.vendor_is_complete():
        pytest.skip("vendor cache absent — run `oku vendor`")
    assert got["lineNumbers"] == 6, got
    assert got["highlighted"] > 0, f"the vendored Prism did not highlight: {got}"


def test_the_online_result_is_unchanged(browser, code_url):
    """The fallback must not cost the reader who does have the CDN: same
    gutter, and the highlighting still arrives."""
    got = _measure(browser, code_url, offline=False)
    assert got["lineNumbers"] == 6, got
    assert got["highlighted"] > 0, f"Prism did not highlight: {got}"
