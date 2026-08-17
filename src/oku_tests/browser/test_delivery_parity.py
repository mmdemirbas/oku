"""The same page, in both trees the build ships, has to come out the same.

This is the test that exists because of a pattern rather than a bug.
`oku serve`, `dist/site` and `dist/standalone` run ONE kit against three
different DOMs, origins and fetch capabilities, and almost every browser
test in this repo drives the first of them. Four defects reached a reader
that way — a crash before <body> existed, a sidebar that dropped its site
tree, a hash click that fetched a JSON file:// refuses, and a site tree
shipped without the dependencies it needs offline. Each was found by
opening a delivered file, one at a time.

So instead of another test per symptom: render every page in both built
trees and diff them. Anything that renders in one and not the other is a
finding, whatever its cause. The tally is derived from the DOM rather
than declared here, so a primitive added later is compared without this
file being touched.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

CDN = ("jsdelivr", "googleapis", "gstatic", "fonts.")

PAGES = {
    "index.md": """---
title: Home
order: 10
summary: The front page of a small tree.
---

## Welcome {#welcome}

Prose with `code`, *emphasis* and a [link](sub/deep.html).

| col | val |
|---|---|
| a | 1 |
| b | 2 |
""",
    "charts.md": """---
title: Charts
order: 20
summary: A page carrying figures.
---

## Figures {#figures}

```oku-chart
{"type":"bar","rows":[{"label":"one","value":60},{"label":"two","value":80}]}
```

```mermaid
flowchart LR
  A["in"] --> B["out"]
```

```python
def f(x):
    return x + 1
```
""",
    "sub/deep.md": """---
title: Deep
order: 30
summary: A page one level down.
---

> [!TLDR]
> Depth is where the base of every relative path goes wrong.

## Body {#body}

Text.
""",
}

# Everything the DOM says about itself, so a primitive added to the kit
# later is compared here without anyone remembering to add it.
TALLY = """() => {
  const t = {};
  const bump = k => { t[k] = (t[k] || 0) + 1; };
  document.querySelectorAll('main *').forEach(e => {
    const cls = typeof e.className === 'string' ? e.className : '';
    cls.split(/\\s+/).forEach(c => { if (/^ok[tcd]-/.test(c)) bump(c); });
    const tag = e.tagName.toLowerCase();
    if (tag.startsWith('oku-') || tag === 'svg' || tag === 'table' || tag === 'pre') bump(tag);
  });
  const main = document.querySelector('main');
  return {
    tally: t,
    text: main ? main.innerText.replace(/\\s+/g, ' ').trim().length : 0,
    ctrls: [...document.querySelectorAll('.ctrl-btn')].map(b => b.className.replace('ctrl-btn ', '')).sort(),
    tree: document.querySelectorAll('page-nav .page-nav-tree a').length,
    toc: document.querySelectorAll('page-nav page-toc a').length,
    rail: document.querySelectorAll('.okt-rail-mark').length,
    errors: window.__e || [],
  };
}"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("parity") / "docs"
    docs.mkdir()
    for rel, text in PAGES.items():
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("Home"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    return docs / "dist"


@pytest.fixture(scope="module")
def site_url(built):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(built / "site"))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def snapshots(browser, built, site_url):
    """{page: {mode: snapshot}} for every page in both built trees."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(
        "window.__e=[];addEventListener('error',e=>window.__e.push(String(e.message)));"
        "addEventListener('unhandledrejection',e=>window.__e.push('rejection: '+String(e.reason)))"
    )
    page = ctx.new_page()
    console: list[str] = []
    page.on("console", lambda m: console.append(m.text[:160]) if m.type == "error" else None)
    out: dict[str, dict[str, dict]] = {}
    for rel in ("index.html", "charts.html", "sub/deep.html"):
        for mode, url in (
            ("site", f"{site_url}/{rel}"),
            ("standalone", (built / "standalone" / rel).as_uri()),
        ):
            console.clear()
            page.goto(url, wait_until="load")
            page.wait_for_timeout(2500)
            snap = page.evaluate(TALLY)
            snap["console"] = [c for c in console if not any(k in c for k in CDN)]
            out.setdefault(rel, {})[mode] = snap
    ctx.close()
    return out


def test_neither_tree_throws_on_any_page(snapshots):
    noisy = {
        f"{page} [{mode}]": snap["errors"] + snap["console"]
        for page, modes in snapshots.items()
        for mode, snap in modes.items()
        if snap["errors"] or snap["console"]
    }
    assert not noisy, f"errors while loading a built page: {noisy}"


def test_both_trees_render_the_same_primitives(snapshots):
    """A block that draws in one tree and not the other is the shape of
    every standalone defect found so far."""
    diffs = {}
    for page, modes in snapshots.items():
        keys = set(modes["site"]["tally"]) | set(modes["standalone"]["tally"])
        for k in sorted(keys):
            a = modes["site"]["tally"].get(k, 0)
            b = modes["standalone"]["tally"].get(k, 0)
            if a != b:
                diffs[f"{page}:{k}"] = f"site={a} standalone={b}"
    assert not diffs, f"the two built trees disagree: {diffs}"


def test_both_trees_carry_the_same_words(snapshots):
    for page, modes in snapshots.items():
        a, b = modes["site"]["text"], modes["standalone"]["text"]
        assert a and b, f"{page}: empty main (site={a} standalone={b})"
        assert abs(a - b) <= max(a, b) * 0.02, f"{page}: site={a} chars, standalone={b}"


def test_both_trees_give_the_reader_the_same_chrome(snapshots):
    """Controls, site tree, on-page contents, rail. The sidebar dropping
    its tree in one tree only is exactly this assertion."""
    for page, modes in snapshots.items():
        for field in ("ctrls", "tree", "toc", "rail"):
            a, b = modes["site"][field], modes["standalone"][field]
            assert a == b, f"{page}: {field} site={a} standalone={b}"


def test_the_tree_is_actually_there_to_compare(snapshots):
    """Guard against the comparison above passing because both sides are
    empty — a parity test that compares nothing is the failure mode this
    whole file exists to catch."""
    for page, modes in snapshots.items():
        assert modes["standalone"]["tree"] == len(PAGES), (
            f"{page}: site tree has {modes['standalone']['tree']} rows for {len(PAGES)} pages"
        )
        assert modes["standalone"]["toc"] > 0, f"{page}: no on-page contents"
        assert len(modes["standalone"]["ctrls"]) >= 4, modes["standalone"]["ctrls"]
