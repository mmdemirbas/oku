"""A reader fills a placeholder once and every page swaps to their value.

`kit.json` declares the keys, the presentation menu grows a Placeholders
row, and `{{key}}` is substituted at read time — into `<pre>`, `<code>`
and `<kbd>` on its own, and into running prose wrapped in an island
carrying `okc-personalize-target`.

The feature shipped and had never run. Three defects, each hiding the
next:

1. `init` read `if (!btn) buildButton();` and no `btn` was ever declared
   — a leftover from when the control was a corner button rather than a
   row this module registers with the menu. It threw a ReferenceError on
   its first statement, before any substitution.
2. The served modes DID call `init`, inside `catch (e) { /* ignore */ }`.
   A silent catch over a throw that happens every time is why nobody saw
   it: no row, no substitution, `{{key}}` left on the page as written,
   and nothing anywhere saying so.
3. The standalone branch of the kit loader never called `init` at all.
   It hydrated `kit.personalization` from the inlined bundle, marked the
   kit loaded and notified its waiters — so even with (1) and (2) fixed,
   the delivery mode a reader is most often handed a file of would still
   have done nothing. `load()` has one exit now.

Both trees are covered here, because "two recipes and only one of them
was covered" is the standing lesson in this repo and this feature is a
fresh instance of it.
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

from ._wait import page_quiet, until

pytestmark = pytest.mark.browser

KEYS = [
    {"key": "apiKey", "label": "API Key", "default": "sk_test_demo", "type": "password"},
    {"key": "projectId", "label": "Project ID", "default": "proj_demo"},
]

PAGE = """---
title: Placeholders
summary: A page carrying placeholders.
---

## s {#s}

```bash
curl -H "key: {{apiKey}}" https://api.example.com/v1/{{projectId}}
```

<div class="okc-personalize-target">

Prose naming the project `{{projectId}}` inline.

</div>
"""


def _build(tmp_path_factory, name: str, keys: list | None):
    docs = tmp_path_factory.mktemp(name) / "docs"
    docs.mkdir()
    kit = {"name": name}
    if keys is not None:
        kit["personalization"] = keys
    (docs / "kit.json").write_text(json.dumps(kit), encoding="utf-8")
    (docs / "page.md").write_text(PAGE, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Placeholders"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


@pytest.fixture(scope="module")
def declared(tmp_path_factory):
    return _build(tmp_path_factory, "placeholders", KEYS)


@pytest.fixture(scope="module")
def undeclared(tmp_path_factory):
    return _build(tmp_path_factory, "noplaceholders", None)


@pytest.fixture(scope="module")
def served(declared):
    """The site tree over loopback HTTP, because that tree FETCHES its
    kit.json where the standalone one carries it inlined — two different
    branches of the loader, and the bug was in the branch nobody
    served."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(declared / "site"))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


SWAPPED = """() => ({
  code: document.querySelector('pre code').textContent.trim(),
  prose: document.querySelector('.okc-personalize-target').textContent.trim(),
  spans: [...document.querySelectorAll('.okc-personalized')].map((e) => e.getAttribute('data-key')),
  literals: (document.body.innerText.match(/\\{\\{\\w+\\}\\}/g) || []),
})"""


def _opened(browser, url: str):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    pg.goto(url, wait_until="load")
    page_quiet(pg)
    # The swap is hung off the kit loading, which is a promise on both
    # branches — so the condition is the substitution, not a clock.
    until(
        pg,
        "() => !/\\{\\{\\w+\\}\\}/.test(document.body.innerText)",
        what="every placeholder was substituted",
    )
    return pg


def test_a_standalone_page_swaps_the_readers_values(browser, declared):
    """The branch that never ran. A standalone page carries the keys in
    its inlined bundle and hands nothing to the personalization module,
    so this is the case that was dead in the mode readers are handed."""
    pg = _opened(browser, (declared / "standalone" / "page.html").as_uri())
    try:
        got = pg.evaluate(SWAPPED)
        assert got["literals"] == [], got
        assert "sk_test_demo" in got["code"] and "proj_demo" in got["code"], got
        assert "proj_demo" in got["prose"], got
        # Prose keeps the span that names the key on hover. A code block
        # does not: Prism rewrites a block from its own text, so nothing
        # that is not code survives inside it — the VALUE is there and
        # the wrapper is gone, which is why both are asserted separately.
        assert "projectId" in got["spans"], got
    finally:
        pg.close()


def test_a_served_page_swaps_them_too(browser, served):
    """The other recipe. This tree fetches `kit.json` at runtime rather
    than carrying it inlined, so it exercises the loader's other
    branch — the one that did call `init`, into a silent catch."""
    pg = _opened(browser, f"{served}/page.html")
    try:
        got = pg.evaluate(SWAPPED)
        assert got["literals"] == [], got
        assert "sk_test_demo" in got["code"] and "proj_demo" in got["code"], got
        assert "proj_demo" in got["prose"], got
    finally:
        pg.close()


def test_a_project_declaring_nothing_leaves_the_braces_alone(browser, undeclared):
    """The other direction, and the one that would make this feature
    dangerous: `{{...}}` is ordinary text in a document about templating,
    and a project that declared no keys must get it back unchanged. The
    substitution is keyed to the DECLARED list, not to the braces."""
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        pg.goto((undeclared / "standalone" / "page.html").as_uri(), wait_until="load")
        page_quiet(pg)
        got = pg.evaluate(SWAPPED)
        assert sorted(set(got["literals"])) == ["{{apiKey}}", "{{projectId}}"], got
        assert got["spans"] == [], got
        assert not pg.evaluate("() => !!document.querySelector('.personalize-toggle')")
    finally:
        pg.close()


def test_the_reader_can_reach_the_control(browser, declared):
    """A substitution the reader cannot change is a typo with extra
    steps. The row registers rather than being listed, so it appears
    only where a project declared keys — and the menu builds its rows
    when it opens, which is why this clicks first."""
    pg = _opened(browser, (declared / "standalone" / "page.html").as_uri())
    try:
        pg.click(".menu-toggle")
        until(
            pg,
            "() => !!document.querySelector('.personalize-toggle')",
            what="the Placeholders row appeared in the presentation menu",
        )
        rows = pg.evaluate("() => [...document.querySelectorAll('[data-row]')].map((e) => e.dataset.row)")
        assert "personalize" in rows, rows
    finally:
        pg.close()


def test_changing_a_value_updates_every_place_it_appears(browser, declared):
    """One value, two renderings, and they must not drift. The prose span
    and the code block are written by different passes."""
    pg = _opened(browser, (declared / "standalone" / "page.html").as_uri())
    try:
        pg.evaluate("() => __okuPersonalization.set('projectId', 'proj_live')")
        until(
            pg,
            "() => document.querySelector('.okc-personalize-target').textContent.includes('proj_live')",
            what="the prose took the new value",
        )
        got = pg.evaluate(SWAPPED)
        assert "proj_live" in got["prose"], got
        assert "proj_demo" not in got["prose"], got
    finally:
        pg.close()
