"""A document the reader opened is read, not run.

An HTML island in a PAGE is full-capability by design — the author
wrote it into their own page and `oku check` lints it as page content.
The markdown viewer renders something else: a file the page merely
links to, into the page's own document. `../README.md`, a filepath
chip's preview, any `.md` a reader can reach.

Measured before the fix, from a linked file: the script set a global on
the host page, rewrote `document.title`, and wrote the kit's own
`oku-theme-mode` key in localStorage — a setting the reader cannot see
change and would not think to undo. An `<img onerror>` fired in the
same pass.

Both halves are pinned here, because the fix could overreach as easily
as the defect underreached: the viewed file goes inert AND the page's
own island still runs, its diagrams and charts still draw, and its
links still resolve. That last one is the standalone case: `safeUrl`
refuses `file:`, so an inert pass running after the rebase would strip
every link in a viewed document on exactly the delivery mode that has
no other way to show it.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import subprocess
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

CHART = json.dumps({"type": "bar", "rows": [{"label": "a", "value": 3}, {"label": "b", "value": 8}]})

# What a linked document could do to the page that opened it. The
# localStorage key is the kit's own, chosen deliberately: the reader
# would see the theme change and have no idea why.
NOTE_MD = f"""---
title: The Note
summary: A document that tries to run.
---

## Body {{#body}}

Prose with [a sibling](other.md).

<div class="okt-card">

<script>window.__RAN_SCRIPT = 1; document.title = 'TAKEN OVER'; try {{ localStorage.setItem('oku-theme-mode', 'written-by-a-viewed-file'); }} catch (e) {{}}</script>

Text after the script.

</div>

<img src="x" onerror="window.__RAN_ONERROR = 1">

<iframe srcdoc="&lt;script&gt;parent.__RAN_FRAME = 1&lt;/script&gt;"></iframe>

<base href="https://example.com/">

<meta http-equiv="refresh" content="0;url=https://example.com/">

```mermaid
flowchart LR
  A --> B
```

```oku-chart
{CHART}
```
"""

PAGE_MD = """---
title: Host
summary: A page that links to a document.
---

## Link {#link}

Open [the note](/note.md), or preview [`note.md`](#f/note.md).

<div class="okt-card">

<script>window.__PAGE_ISLAND_RAN = 1;</script>

The page's own island, which is content the author wrote.

</div>
"""


def _write(d: Path) -> None:
    (d / "note.md").write_text(NOTE_MD, encoding="utf-8")
    (d / "other.md").write_text(
        "---\ntitle: Other\nsummary: A sibling.\n---\n\n## Other {#other}\n\nHere.\n", encoding="utf-8"
    )
    (d / "page.md").write_text(PAGE_MD, encoding="utf-8")


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("inertserved").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    _write(d)
    for stem in ("page", "note", "other"):
        (d / f"{stem}.html").write_text(
            cli._stub_for(stem, inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
            encoding="utf-8",
        )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


PROBE = """() => {
  const view = document.querySelector('.okt-mdview-rendered');
  const src = document.querySelector('.okt-mdview-source code');
  return {
    ranScript: !!window.__RAN_SCRIPT,
    ranOnerror: !!window.__RAN_ONERROR,
    ranFrame: !!window.__RAN_FRAME,
    pageIslandRan: !!window.__PAGE_ISLAND_RAN,
    title: document.title,
    themeKey: localStorage.getItem('oku-theme-mode'),
    scripts: [...view.querySelectorAll('script')].map(s => (s.getAttribute('type') || '(none)')),
    frames: view.querySelectorAll('iframe, frame, object, embed').length,
    reaching: document.querySelectorAll('.okt-mdview base, .okt-mdview meta').length,
    handlers: view.querySelectorAll('[onerror], [onload], [onclick], [onmouseover]').length,
    notice: view.querySelector('.okt-mdview-inert') ? view.querySelector('.okt-mdview-inert').textContent.trim() : null,
    diagramDrew: !!view.querySelector('oku-diagram svg'),
    barsDrew: view.querySelectorAll('.okt-bar, .okt-bar-row, [class*="okt-bar"]').length,
    links: [...view.querySelectorAll('a[href]')].map(a => a.getAttribute('href')),
    cardText: view.querySelector('.okt-card') ? view.querySelector('.okt-card').textContent.replace(/\\s+/g, ' ').trim() : null,
    sourceHasScript: !!src && src.textContent.indexOf('__RAN_SCRIPT') >= 0,
  };
}"""


@pytest.fixture(scope="module")
def opened(browser, served):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        pg.goto(f"{served}/page.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.click("a[href='/note.md']")
        pg.wait_for_selector(".okt-mdview-rendered", timeout=20000)
        pg.wait_for_selector(".okt-mdview-rendered oku-diagram svg", timeout=30000)
        yield pg.evaluate(PROBE)
    finally:
        pg.close()


def test_a_viewed_document_does_not_run(opened) -> None:
    assert opened["ranScript"] is False, "a linked file's script executed in the page"
    assert opened["ranOnerror"] is False, "a linked file's onerror handler fired"
    assert opened["ranFrame"] is False, "a linked file's iframe reached its parent"


def test_a_viewed_document_leaves_the_page_alone(opened) -> None:
    """What the script tried to take: the page's identity and the
    reader's stored settings."""
    assert opened["title"] == "Host"
    assert opened["themeKey"] != "written-by-a-viewed-file"


def test_nothing_executable_survives_in_the_rendered_pane(opened) -> None:
    assert opened["frames"] == 0
    assert opened["handlers"] == 0
    # `base` and `meta` run nothing themselves; they redirect the whole
    # page, which is the same reach by another route.
    assert opened["reaching"] == 0
    assert "(none)" not in opened["scripts"], opened["scripts"]
    # An empty list satisfies the line above for the wrong reason, so
    # require the count the viewer reported: the script, the iframe and
    # the handler are three separate removals.
    assert re.search(r"\b(\d+) items? (?:was|were) left out", opened["notice"] or ""), opened["notice"]
    assert int(re.search(r"\b(\d+) items? (?:was|were) left out", opened["notice"]).group(1)) >= 5


def test_the_reader_is_told_something_was_left_out(opened) -> None:
    """A silent removal reads as a rendering bug to the author whose
    island stopped working."""
    assert opened["notice"], "nothing said a piece of the document was removed"
    assert "not run" in opened["notice"], opened["notice"]


def test_the_source_view_still_holds_what_was_removed(opened) -> None:
    """The removal is a rendering rule, not a redaction — Source is
    where the reader goes to see what it was."""
    assert opened["sourceHasScript"]


def test_the_document_still_renders(opened) -> None:
    """The failure this fix could introduce. Diagrams and charts carry
    their payload in `text/x-mermaid` and `application/json` holders,
    which are data — a rule that took every script would take those
    too, and the document would arrive gutted. Neither holder is in
    `scripts` by the time this reads: each element consumes its own
    source at connect. Drawing IS the evidence they survived."""
    assert opened["diagramDrew"], "the mermaid diagram did not draw"
    assert opened["barsDrew"] > 0, "the bar chart did not draw"
    assert opened["cardText"] and "Text after the script." in opened["cardText"]


def test_the_page_s_own_island_still_runs(opened) -> None:
    """The scope of the rule. An island in the page is the author's own
    content and keeps full capability; only the viewer goes inert."""
    assert opened["pageIslandRan"] is True


def test_links_in_a_viewed_document_still_resolve(opened) -> None:
    assert opened["links"], "the viewed document lost every link"
    assert any("other" in h for h in opened["links"]), opened["links"]


# ---------------------------------------------------------------- standalone


@pytest.fixture(scope="module")
def standalone(tmp_path_factory):
    root = tmp_path_factory.mktemp("inertstandalone")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    docs = root / "docs"
    docs.mkdir()
    _write(docs)
    for stem in ("page", "note", "other"):
        (docs / f"{stem}.html").write_text(cli._stub_for(stem), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True, allow_errors=False)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist" / "standalone" / "page.html"


@pytest.fixture(scope="module")
def opened_standalone(browser, standalone):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        pg.goto(standalone.as_uri(), wait_until="load")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        # The chip, not a link: over file:// the viewer reads the bytes
        # the build inlined rather than fetching them.
        pg.click("oku-filepath")
        pg.wait_for_selector(".okt-mdview-rendered", timeout=20000)
        pg.wait_for_timeout(1200)
        yield pg.evaluate(PROBE)
    finally:
        pg.close()


def test_a_viewed_document_is_inert_over_file_too(opened_standalone) -> None:
    assert opened_standalone["ranScript"] is False
    assert opened_standalone["ranOnerror"] is False
    assert opened_standalone["title"] == "Host"


def test_a_viewed_document_keeps_its_links_over_file(opened_standalone) -> None:
    """`safeUrl` refuses `file:`. Rebasing turns every relative href in
    a viewed document into a `file:` URL, so an inert pass placed after
    the rebase strips them all — on the one delivery mode with no other
    way to reach the sibling."""
    assert opened_standalone["links"], "every link in the viewed document was stripped"
    assert any("other" in h for h in opened_standalone["links"]), opened_standalone["links"]
