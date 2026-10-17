"""A package that loads the kit from one shared address renders fully.

A host serving many packages keeps one copy of the kit (`oku kit export`)
at `/k/<id>/`, cached by readers' browsers across every package, and
packs with `oku pack --kit-url /k/<id>/`, which writes no `_oku/`. Every
reference a page makes to the kit has to reach that address: the four
tags in the stub, the fonts through chrome.css, and everything chrome.js
loads later on its own — mermaid, Prism's core, carried.js and a grammar,
the i18n table of a Turkish page, the glossary and ext-ref registries a
kit.json names. Any one of them left relative asks for
`/d/s/@v1/_oku/…`, which this host does not have: a failed request.

So the export is served at `/k/test/` and the package at `/d/s/@v1/`,
every other path a 404, with the CSP a host would send. Both pages are
walked; nothing may fail, log an error or be refused, nothing may ask
for the package's own `_oku/`, and each lazy load must be seen arriving
from the kit — a page that skipped one would pass the first three.
"""

from __future__ import annotations

import base64
import http.server
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from oku import cli, pack

from . import _wait

pytestmark = pytest.mark.browser

KIT = "/k/test/"
PKG = "/d/s/@v1/"

CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
    "media-src 'self'; connect-src {origin}/d/s/ {origin}/k/; frame-src 'none'; worker-src 'none'; "
    "form-action 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
)

ENTRY_MD = """---
title: Shared-kit entry
summary: A diagram, code, a figure, a PDF and a link to a Turkish page.
---

## The figure {#figure}

Read [the second page](second.md) or open the [manual](#f/../files/manual.pdf).

![A pixel](img/pixel.png)

```mermaid
flowchart LR
  A["write"] --> B["read"]
```

```python
def f(x):
    return x + 1
```
"""

# Turkish, so the page asks the kit for its i18n table.
SECOND_MD = """---
title: İkinci sayfa
summary: Bir bağlantıyla ulaşılan sayfa.
lang: tr
---

## İkinci {#ikinci}

[Girişe](entry.md) dön.
"""

PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
)

WATCH = """() => {
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', (e) => {
    window.__csp.push(e.violatedDirective + ' ' + e.blockedURI);
  });
}"""


@pytest.fixture(scope="module")
def trees(tmp_path_factory) -> dict[str, Path]:
    if not cli.vendor_is_complete():
        pytest.skip("vendor cache absent — run `oku vendor`")
    proj = tmp_path_factory.mktemp("kitsrc")
    (proj / ".git").mkdir()
    (proj / "docs" / "img").mkdir(parents=True)
    (proj / "files").mkdir()
    # A domain the kit ships both registries for, so both are fetched.
    (proj / "kit.json").write_text('{"name": "p", "domains": ["web"]}\n', encoding="utf-8")
    (proj / "docs" / "entry.md").write_text(ENTRY_MD, encoding="utf-8")
    (proj / "docs" / "second.md").write_text(SECOND_MD, encoding="utf-8")
    (proj / "docs" / "img" / "pixel.png").write_bytes(PNG)
    (proj / "files" / "manual.pdf").write_bytes(PDF)
    out = tmp_path_factory.mktemp("kitout")
    assert pack.export_kit(str(out / "kit")) == 0
    assert pack.run([str(proj / "docs" / "entry.md")], str(out / "pkg"), kit_url=KIT) == 0
    assert not (out / "pkg" / "_oku").exists()
    return {KIT: out / "kit", PKG: out / "pkg"}


@pytest.fixture(scope="module")
def served(trees: dict[str, Path]):
    """The export under /k/test/, the package under /d/s/@v1/, nothing else."""
    origin: list[str] = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            p = unquote(urlsplit(path).path)
            for prefix, root in trees.items():
                if p.startswith(prefix) and ".." not in p.split("/"):
                    return str(root / p[len(prefix) :])
            return str(Path(trees[KIT]).parent / "no-such-path")

        def end_headers(self):
            self.send_header("Content-Security-Policy", CSP.format(origin=origin[0]))
            super().end_headers()

        def log_message(self, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    origin.append(f"http://127.0.0.1:{httpd.server_address[1]}")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield origin[0]
    httpd.shutdown()


@pytest.fixture(scope="module")
def walk(browser, served: str) -> dict:
    """Open the door, check the entry drew, open the PDF chip, follow the
    link to the Turkish page."""
    ctx = browser.new_context()
    requests: list[str] = []
    ok: list[str] = []
    bad: list[str] = []
    pdf: list[tuple[int, str]] = []
    ctx.on("request", lambda r: requests.append(r.url))

    def on_failed(r):
        # Headless chromium has no PDF viewer: it turns the navigation into
        # a download and reports the document request as aborted, AFTER a
        # 200 for it arrived. That one abort is the browser, not the page.
        if not (r.url.endswith("manual.pdf") and "ERR_ABORTED" in (r.failure or "")):
            bad.append(f"failed {r.url} {r.failure}")

    ctx.on("requestfailed", on_failed)
    ctx.on("response", lambda r: (bad if r.status >= 400 else ok).append(f"{r.status} {r.url}"))
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(f"({WATCH})()")

    pg.goto(served + PKG)
    pg.wait_for_url("**" + PKG + "docs/entry.html")
    _wait.until(
        pg, "() => document.querySelectorAll('.okd-render svg .node').length > 0", what="mermaid drew nodes"
    )
    _wait.until(
        pg, "() => document.querySelectorAll('pre code .token').length > 0", what="Prism coloured the code"
    )
    pg.evaluate("() => document.fonts.ready.then(() => true)")
    state = pg.evaluate(
        """() => ({
          nodes: document.querySelectorAll('.okd-render svg .node').length,
          tokens: document.querySelectorAll('pre code .token').length,
          image: (document.querySelector('main img[alt="A pixel"]') || {}).naturalWidth || 0,
          fonts: [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/["']/g, '')),
          csp: window.__csp.slice(),
        })"""
    )
    is_pdf = lambda r: r.url.endswith("manual.pdf")  # noqa: E731
    with ctx.expect_event("response", is_pdf) as got, ctx.expect_page() as popup:
        pg.click('oku-filepath[path$="manual.pdf"] .okt-fp-label')
    pdf.append((got.value.status, got.value.headers.get("content-type", "")))
    opened = got.value.url
    popup.value.close()
    with pg.expect_response(lambda r: r.url.endswith("/i18n/tr.json")):
        pg.click('main a[href="second.html"]')
    pg.wait_for_url("**" + PKG + "docs/second.html")
    _wait.until(
        pg, "() => /İkinci sayfa/.test(document.querySelector('h1')?.textContent || '')", what="page two"
    )
    state["csp"] += pg.evaluate("() => window.__csp")
    state.update(requests=requests, ok=ok, bad=bad, errors=errors, pdf=pdf, popup=opened)
    ctx.close()
    return state


def test_the_page_renders_fully(walk) -> None:
    assert walk["nodes"] >= 2, walk
    assert walk["tokens"] > 0, walk
    assert walk["image"] == 1, walk
    assert {"Literata", "JetBrains Mono"} <= set(walk["fonts"]), walk["fonts"]


def test_nothing_fails_and_nothing_is_refused(walk) -> None:
    assert walk["bad"] == [], walk["bad"]
    assert walk["errors"] == [], walk["errors"]
    assert walk["csp"] == [], walk["csp"]


def test_nothing_asks_for_a_kit_inside_the_package(walk, served: str) -> None:
    inside = [u for u in walk["requests"] if u.startswith(served + PKG + "_oku/") or "/_oku/" in u]
    assert inside == [], inside


def test_every_request_is_the_package_or_the_kit(walk, served: str) -> None:
    outside = [
        u
        for u in walk["requests"]
        if not u.startswith((served + PKG, served + KIT)) and not u.startswith(("data:", "blob:"))
    ]
    assert outside == [], outside


@pytest.mark.parametrize(
    "path",
    [
        "chrome-boot.js?v=",
        "chrome.css?v=",
        "chrome.js?v=",
        "renderer.js?v=",
        "vendor/fonts/literata-",
        "vendor/mermaid.min.js",
        "vendor/prism/prism.min.js",
        "vendor/prism/carried.js",
        "vendor/prism/components/prism-python.min.js",
        "i18n/tr.json",
        "glossary/web.json",
        "extrefs/web.json",
    ],
)
def test_each_kind_of_kit_load_arrives_from_the_kit(walk, served: str, path: str) -> None:
    """Without this, a load that silently never happened would pass the
    tests above: nothing failed because nothing was asked for."""
    assert any(r.startswith(f"200 {served}{KIT}{path}") for r in walk["ok"]), [
        r for r in walk["ok"] if KIT in r
    ]


def test_no_page_loads_a_schema(walk) -> None:
    """What lets `oku kit export` leave schema/ out."""
    asked = [u for u in walk["requests"] if "schema" in u or "examples.json" in u]
    assert asked == [], asked


def test_the_pdf_chip_opens_the_pdf(walk) -> None:
    assert walk["popup"].endswith(PKG + "files/manual.pdf"), walk["popup"]
    assert walk["pdf"] and walk["pdf"][0][0] == 200 and "pdf" in walk["pdf"][0][1], walk["pdf"]
