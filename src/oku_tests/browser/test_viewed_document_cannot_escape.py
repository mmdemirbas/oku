"""Five more ways a viewed document reached the page that opened it.

`test_viewed_document_is_inert.py` holds the first pass: `makeInert`
drops executable scripts, `on*` handlers, frames, `<link>`, and confines
a `<style>`. A second look found routes it did not see, every one run in
Chromium against the shipped kit before the fix:

- a script whose type is executable but not on the deny-list
  (`text/jscript`, `text/x-javascript`) ran;
- a stray `}` in a viewed `<style>` closed the confinement block, and the
  rules after it styled the host page;
- an unknown `<glossary-term>` put its own text into the tooltip as HTML,
  built on hover, after the inert pass had run;
- an `oku-table` row's `href` is kept in `data-href` and followed by a
  click listener, neither of which the inert pass inspects;
- a group-by value from a cell's `data-values` went into the card-view
  group header through `innerHTML`.

And one on the page itself: `__okuSafeUrl`, which guards glossary and
ext-ref links from a registry, let `javascript:` through behind a tab or
a leading control character — the browser strips both before parsing.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

NOTE = """---
title: Note
summary: A document that tries to escape.
---

## Body {#body}

<div class="okt-card">

<script type="text/jscript">window.__ESC_JSCRIPT = 1</script>

<script type="text/x-javascript">window.__ESC_XJS = 1</script>

</div>

<style>
} body { outline: 7px solid rgb(1, 2, 3) } x {
</style>

<p><glossary-term id="gl">&lt;img src=x onerror="window.__ESC_GLOSS=1"&gt;</glossary-term></p>

```oku-table
{"headers":["A","B"],"rows":[{"cells":["rowclick","1"],"href":"javascript:window.__ESC_ROW=1"},["two","2"]]}
```

<table id="grp"><thead><tr><th>A</th><th>B</th></tr></thead><tbody>
<tr><td data-values="&lt;img src=x onerror=window.__ESC_GROUP=1&gt;">one</td><td>1</td></tr>
<tr><td>two</td><td>2</td></tr>
</tbody></table>
"""

PAGE = """---
title: Host
summary: Links a document and two registry terms.
---

## Link {#link}

Open [the note](/note.md). Terms: [T](#g/T), [U](#g/U) and [V](#g/V).
"""

KIT_JSON = {
    "name": "probe",
    "domains": ["web"],
    "glossary": {
        "web": {
            "T": {"en": {"def": "tab", "link": "java\tscript:window.__ESC_TAB=1"}},
            "U": {"en": {"def": "ctl", "link": "\u0001javascript:window.__ESC_CTL=1"}},
            # No language level: the any-language fallback picked the
            # STRING under `def` as the entry, and `.link` on a string is
            # String.prototype.link — a function, rendered as the href.
            "V": {"def": "flat"},
        }
    },
}


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("escape").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps(KIT_JSON), encoding="utf-8")
    (d / "note.md").write_text(NOTE, encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    for stem in ("page", "note"):
        (d / f"{stem}.html").write_text(
            cli._stub_for(stem, inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
            encoding="utf-8",
        )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def page(browser, served):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    yield pg
    pg.close()


def _flag(pg, name: str) -> bool:
    return pg.evaluate(f"() => !!window.{name}")


@pytest.mark.parametrize(("term", "flag"), [("T", "__ESC_TAB"), ("U", "__ESC_CTL")])
def test_a_registry_link_cannot_smuggle_a_script_scheme(page, served, term: str, flag: str) -> None:
    page.goto(f"{served}/page.html")
    page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page.hover(f"glossary-term[term='{term}']")
    page.wait_for_timeout(900)
    href = page.evaluate(
        "() => { const a = document.querySelector('.oku-tooltip .okt-link a'); return a && a.getAttribute('href'); }"
    )
    if href:
        page.evaluate("() => document.querySelector('.oku-tooltip .okt-link a').removeAttribute('target')")
        page.click(".oku-tooltip .okt-link a", timeout=3000)
        page.wait_for_timeout(300)
    assert not _flag(page, flag), f"Learn more ran {href!r}"


def test_an_entry_without_a_language_level_offers_no_function_as_a_link(page, served) -> None:
    page.goto(f"{served}/page.html")
    page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page.hover("glossary-term[term='V']")
    page.wait_for_timeout(900)
    href = page.evaluate(
        "() => { const a = document.querySelector('.oku-tooltip .okt-link a'); return a && a.getAttribute('href'); }"
    )
    assert not href or "function" not in href, href
    page.mouse.move(5, 5)


@pytest.fixture(scope="module")
def viewed(page, served):
    page.goto(f"{served}/page.html")
    page.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page.click("a[href='/note.md']")
    page.wait_for_selector(".okt-mdview-rendered", timeout=20000)
    page.wait_for_timeout(1200)
    return page


def test_no_executable_script_type_runs(viewed) -> None:
    assert not _flag(viewed, "__ESC_JSCRIPT")
    assert not _flag(viewed, "__ESC_XJS")


def test_a_stray_brace_cannot_close_the_confinement(viewed) -> None:
    # The style, not the width: an unset outline computes to `medium`
    # (3px) with style `none`. The escaped rule made it `7px solid`.
    outline = viewed.evaluate("() => getComputedStyle(document.body).outlineStyle")
    assert outline == "none", f"the viewed sheet styled the host page: outline-style {outline}"


def test_an_unknown_term_is_text_in_its_tooltip(viewed) -> None:
    viewed.hover(".okt-mdview-rendered [id$=gl]")
    viewed.wait_for_timeout(900)
    assert not _flag(viewed, "__ESC_GLOSS")


def test_a_row_link_cannot_be_a_script(viewed) -> None:
    viewed.click(".okt-mdview-rendered tr:has-text('rowclick') td", timeout=3000)
    viewed.wait_for_timeout(400)
    assert not _flag(viewed, "__ESC_ROW")


def test_a_group_value_is_text_in_its_header(viewed) -> None:
    state = viewed.evaluate(
        """() => {
          const t = document.querySelector('.okt-mdview-rendered [id$=grp]');
          const wrap = t && t.closest('.okt-table-wrap');
          if (!wrap) return 'no wrap';
          const sel = wrap.querySelector('.okt-groupby-select');
          if (!sel) return 'no select';
          sel.value = '0'; sel.dispatchEvent(new Event('change', {bubbles: true}));
          const btn = wrap.querySelector('[data-view="cards"]') || wrap.querySelector('[data-view="list"]');
          if (btn) btn.click();
          return 'ok';
        }"""
    )
    assert state == "ok", state
    viewed.wait_for_timeout(500)
    assert not _flag(viewed, "__ESC_GROUP")
