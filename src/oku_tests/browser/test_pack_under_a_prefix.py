"""A package renders from any path prefix, under a host's strict CSP.

`oku pack` writes a directory that a host serves somewhere it chooses —
`https://host/d/<slug>/` — behind a policy the host sets. Every URL in
the package therefore has to be relative, and everything the kit loads
has to come from the package itself: a page that reached a CDN for
mermaid, or asked for `/site-manifest.json` at the origin root, works on
the author's machine and nowhere it is sent.

So the package is served here the way a host would serve it: under
`/d/x/` and nowhere else (anything outside the prefix is a 404), with
the CSP below on every response, `connect-src` narrowed to the prefix.
Then the door is opened and the page is walked: no failed request, no
console error, no CSP violation, a diagram that really drew (nodes in
`.okd-render svg`, not just an svg — the kit's own button icons are
svgs), a link that renders the next page, a PDF chip that opens the PDF.
"""

from __future__ import annotations

import base64
import functools
import http.server
import threading
from pathlib import Path

import pytest

from oku import cli, pack

from . import _wait

pytestmark = pytest.mark.browser

PREFIX = "/d/x/"

CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
    "connect-src {origin}/d/x/; frame-src 'none'; worker-src 'none'; form-action 'none'; "
    "base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
)

ENTRY_MD = """---
title: Packed entry
summary: A diagram, code, a figure, a PDF and a link to another page.
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

| Name | Value |
|---|---|
| alpha | 1 |
"""

SECOND_MD = """---
title: Second packed page
summary: Reached by a link.
---

## Second {#second}

Back to [the entry](entry.md).
"""

# A one-page PDF, enough for a browser to call it one.
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
def package(tmp_path_factory) -> Path:
    if not cli.vendor_is_complete():
        pytest.skip("vendor cache absent — run `oku vendor`")
    proj = tmp_path_factory.mktemp("packsrc")
    (proj / ".git").mkdir()
    (proj / "docs" / "img").mkdir(parents=True)
    (proj / "files").mkdir()
    (proj / "docs" / "entry.md").write_text(ENTRY_MD, encoding="utf-8")
    (proj / "docs" / "second.md").write_text(SECOND_MD, encoding="utf-8")
    (proj / "docs" / "img" / "pixel.png").write_bytes(PNG)
    (proj / "files" / "manual.pdf").write_bytes(PDF)
    out = tmp_path_factory.mktemp("packout") / "pkg"
    assert pack.run([str(proj / "docs" / "entry.md")], str(out)) == 0
    return out


@pytest.fixture(scope="module")
def served(package: Path):
    """The package under /d/x/ only, every response carrying the CSP."""
    origin: list[str] = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — the stdlib's name
            if not self.path.startswith(PREFIX):
                self.send_error(404)
                return
            self.path = "/" + self.path[len(PREFIX) :]
            super().do_GET()

        def end_headers(self):
            self.send_header("Content-Security-Policy", CSP.format(origin=origin[0]))
            super().end_headers()

        def log_message(self, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(package))
    )
    origin.append(f"http://127.0.0.1:{httpd.server_address[1]}")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield origin[0]
    httpd.shutdown()


@pytest.fixture(scope="module")
def walk(browser, served: str) -> dict:
    """Open the door, then follow the page's link and its PDF chip."""
    ctx = browser.new_context()
    requests: list[str] = []
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

    def on_response(r):
        if r.status >= 400:
            bad.append(f"{r.status} {r.url}")

    ctx.on("response", on_response)
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(f"({WATCH})()")

    pg.goto(served + PREFIX)
    pg.wait_for_url("**" + PREFIX + "docs/entry.html")
    _wait.until(
        pg, "() => document.querySelectorAll('.okd-render svg .node').length > 0", what="mermaid drew nodes"
    )
    _wait.until(
        pg, "() => document.querySelectorAll('pre code .token').length > 0", what="Prism coloured the code"
    )
    state = pg.evaluate(
        """() => ({
          nodes: document.querySelectorAll('.okd-render svg .node').length,
          image: (document.querySelector('main img[alt="A pixel"]') || {}).naturalWidth || 0,
          tree: [...document.querySelectorAll('page-nav a')].map((a) => a.textContent.trim()),
          csp: window.__csp.slice(),
        })"""
    )
    # A headless browser may hand a PDF to its viewer or to a download,
    # and fires no `load` for either; the response is what both share.
    is_pdf = lambda r: r.url.endswith("manual.pdf")  # noqa: E731
    with ctx.expect_event("response", is_pdf) as got, ctx.expect_page() as popup:
        pg.click('oku-filepath[path$="manual.pdf"] .okt-fp-label')
    pdf.append((got.value.status, got.value.headers.get("content-type", "")))
    opened = got.value.url
    popup.value.close()
    pg.click('main a[href="second.html"]')
    pg.wait_for_url("**" + PREFIX + "docs/second.html")
    _wait.until(
        pg,
        "() => /Second packed page/.test(document.querySelector('h1')?.textContent || '')",
        what="page two",
    )
    state["csp"] += pg.evaluate("() => window.__csp")
    state.update(requests=requests, bad=bad, errors=errors, pdf=pdf, popup=opened)
    ctx.close()
    return state


def test_the_diagram_draws_from_the_package(walk) -> None:
    assert walk["nodes"] >= 2, walk


def test_nothing_fails_and_nothing_is_refused(walk) -> None:
    assert walk["bad"] == [], walk["bad"]
    assert walk["errors"] == [], walk["errors"]
    assert walk["csp"] == [], walk["csp"]


def test_every_request_stays_under_the_prefix(walk, served: str) -> None:
    """The package is relative throughout: nothing reaches for the origin
    root, and nothing reaches past the origin at all."""
    outside = [
        u
        for u in walk["requests"]
        if not u.startswith(served + PREFIX) and not u.startswith(("data:", "blob:"))
    ]
    assert outside == [], outside


def test_the_figure_loads(walk) -> None:
    assert walk["image"] == 1, walk


def test_the_pdf_chip_opens_the_pdf(walk) -> None:
    assert walk["popup"].endswith(PREFIX + "files/manual.pdf"), walk["popup"]
    assert walk["pdf"] and walk["pdf"][0][0] == 200 and "pdf" in walk["pdf"][0][1], walk["pdf"]


def test_the_site_tree_lists_the_packed_pages(walk) -> None:
    assert "Packed entry" in " ".join(walk["tree"]) and "Second packed page" in " ".join(walk["tree"]), walk[
        "tree"
    ]
