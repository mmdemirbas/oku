"""Content the kit renders into markup, and where it stops being text.

Three values reached `innerHTML` unescaped while their neighbours on the
same card were escaped — which is the tell that each was an omission
rather than a design:

* a heading's text in the sidebar TOC, taken from
  `_okuHeadingText` → `clone.textContent`, so it UN-escapes exactly what
  the renderer escaped for display;
* a glossary entry's `link`, interpolated straight into `href="…"`;
* an ext-ref's `summary`, beside five fields that go through escapeXml.

The first is a correctness bug before it is anything else: this repo's
own docs are ABOUT markup, and a heading naming a tag lost that word
from the sidebar. The registries are project files, but they travel
between projects — a glossary domain is meant to be shared — so a
`javascript:` link in one is a stored payload with a long reach.
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

HOSTILE_TERM = "Probe Term"
HOSTILE_REF = "Probe Ref"

KIT_JSON = {
    "name": "probe",
    "domains": ["web"],
    "glossary": {
        "web": {
            HOSTILE_TERM: {
                "en": {
                    "def": "A term whose link tries to leave its attribute.",
                    "link": 'https://example.com/" onmouseover="window.__PWNED_LINK=1" data-x="',
                }
            }
        }
    },
    "extrefs": {
        "web": {
            HOSTILE_REF: {
                "en": {
                    "name": HOSTILE_REF,
                    "summary": '<img src=x onerror="window.__PWNED_SUMMARY=1"> and a < b & c',
                    "link": "https://example.com",
                }
            }
        }
    },
}

PAGE = (
    "---\ntitle: Probe\nsummary: Registry values that try to become markup.\n---\n\n"
    '## A heading with <img src=x onerror="window.__PWNED_TOC=1"> in it {#h-raw}\n\n'
    f"Prose naming [{HOSTILE_TERM}](#g/{HOSTILE_TERM}) and [{HOSTILE_REF}](#x/{HOSTILE_REF}).\n\n"
    "### A subheading {#sub}\n\nMore prose so the TOC has two levels.\n"
)


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("registryescape").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps(KIT_JSON), encoding="utf-8")
    (d / "page.md").write_text(PAGE, encoding="utf-8")
    (d / "page.html").write_text(
        cli._stub_for("page", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def measured(browser, served):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        pg.goto(f"{served}/page.html")
        pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
        pg.wait_for_timeout(600)
        # Hovering is what builds both cards; without it the tooltip
        # HTML is never constructed and every assertion below passes for
        # the wrong reason.
        for sel in ("glossary-term", "ext-ref"):
            el = pg.query_selector(sel)
            if el:
                box = el.bounding_box()
                if box:
                    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    pg.wait_for_timeout(700)
        return pg.evaluate("""() => {
          const toc = document.querySelector('.toc-head');
          const tip = document.querySelector('.oku-tooltip');
          return {
            pwnedToc: !!window.__PWNED_TOC,
            pwnedLink: !!window.__PWNED_LINK,
            pwnedSummary: !!window.__PWNED_SUMMARY,
            imgsInToc: document.querySelectorAll('.toc-head img, nav.toc img, page-toc img').length,
            tocText: toc ? toc.querySelector('a').textContent : null,
            handlers: document.querySelectorAll('[onmouseover], [onerror], [onclick]').length,
            builtACard: !!tip,
            tipText: tip ? tip.textContent : '',
          };
        }""")
    finally:
        pg.close()


def test_a_heading_that_names_a_tag_keeps_the_word_in_the_sidebar(measured) -> None:
    assert measured["tocText"] == 'A heading with <img src=x onerror="window.__PWNED_TOC=1"> in it'
    assert measured["imgsInToc"] == 0


def test_no_registry_or_heading_value_becomes_a_live_element(measured) -> None:
    assert measured["pwnedToc"] is False
    assert measured["pwnedLink"] is False
    assert measured["pwnedSummary"] is False
    assert measured["handlers"] == 0, "a value broke out of its attribute into an event handler"


def test_the_cards_were_actually_built(measured) -> None:
    """The guard against passing on an empty page: every assertion above
    is trivially true if no tooltip was ever constructed."""
    assert measured["builtACard"], "no tooltip was built — the assertions above proved nothing"


def test_a_url_that_is_not_a_url_is_dropped_rather_than_rendered() -> None:
    """`javascript:` in a registry entry runs on click, and a glossary
    domain is meant to be shared between projects."""
    js = (KIT / "chrome.js").read_text(encoding="utf-8")
    assert "function __okuSafeUrl(" in js
    assert "'<div class=\"okt-link\"><a href=\"' + link +" not in js
