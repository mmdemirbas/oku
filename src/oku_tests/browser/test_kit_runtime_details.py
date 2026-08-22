"""Four small runtime rules, each measured rather than argued.

* A mindmap or timeline takes its palette from the kit's series ramp,
  so it inverts with the theme like everything around it.
* A scripted scroll respects `prefers-reduced-motion`. CSS alone cannot
  do it: per CSSOM-View an explicit `behavior: 'smooth'` on the call
  overrides `scroll-behavior` from the stylesheet.
* Two quick navigations render the page that was clicked last, which is
  also the one the address bar names.
* Collapsing a table group with the keyboard leaves the focus on the
  control that did it.
"""

from __future__ import annotations

from ._wait import page_quiet

import http.server
import json
import re
import threading
from pathlib import Path

import pytest

from oku import cli
from oku_tests.browser._colour import contrast

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

MINDMAP = "mindmap\n  root((kit))\n    charts\n      bar\n      line\n    diagrams\n      mermaid\n"
TABLE = {
    "k": "table",
    "headers": ["Engine", "Note"],
    "groups": [
        {"t": "Batch", "rows": [["Spark", "one"], ["Flink", "two"]]},
        {"t": "Stream", "rows": [["Kafka", "three"]]},
    ],
}

PAGE_A = (
    "---\ntitle: Alpha\nsummary: A page with a mindmap and a grouped table.\n---\n\n"
    "## Map {#map}\n\n```mermaid\n" + MINDMAP + "```\n\n"
    "## Table {#table}\n\n```oku-table\n" + json.dumps(TABLE) + "\n```\n\n"
    "## Long {#long}\n\n" + ("Filler paragraph so the page can scroll. " * 60) + "\n"
)
PAGE_B = "---\ntitle: Beta\nsummary: The second page.\n---\n\n## Beta {#beta}\n\nShort.\n"


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("kitruntime").resolve()
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    for stem, body in (("alpha", PAGE_A), ("beta", PAGE_B)):
        (d / f"{stem}.md").write_text(body, encoding="utf-8")
        (d / f"{stem}.html").write_text(
            cli._stub_for(stem, inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
            encoding="utf-8",
        )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _page(browser, served, stem="alpha", **kw):
    pg = browser.new_page(viewport={"width": 1280, "height": 900}, **kw)
    pg.goto(f"{served}/{stem}.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=60000)
    page_quiet(pg)
    return pg


def _mindmap_fills(pg) -> dict:
    return pg.evaluate("""() => {
      const svg = document.querySelector('oku-diagram .okd-render svg');
      if (!svg) return null;
      const circle = svg.querySelector('circle.node-bkg');
      const branch = svg.querySelector('path.node-bkg');
      if (!circle || !branch) return null;
      return { root: getComputedStyle(circle).fill, branch: getComputedStyle(branch).fill,
               page: getComputedStyle(document.body).backgroundColor };
    }""")


def test_a_mindmap_changes_colour_with_the_theme(browser, served) -> None:
    """Every other Mermaid theme value is resolved from a token; the six
    cScale entries were light-theme literals, so a mindmap branch stayed
    #b45309 on a page that had otherwise inverted."""
    pg = _page(browser, served)
    try:
        light = _mindmap_fills(pg)
        if light is None:
            pytest.skip("this mermaid build did not draw a mindmap node to measure")
        # Through the kit's own cycler: `applyTheme` sets the attribute,
        # `announceTheme` is what tells the diagram to re-render, and
        # only the cycler does both.
        pg.evaluate("() => cycleTheme()")
        pg.wait_for_timeout(1500)
        assert pg.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
        dark = _mindmap_fills(pg)
        assert dark["branch"] != light["branch"], f"branch node is {light['branch']} in both themes"
    finally:
        pg.close()


def test_a_mindmap_root_node_is_not_black_on_a_dark_page(browser, served) -> None:
    """Mermaid derives the root node's fill rather than reading it from
    `cScale0`, and it derives by lightening or darkening according to
    `darkMode` — a flag the kit never set. Measured rgb(0, 0, 0) on a
    #1e1b29 page: the one node in the figure that had disappeared."""
    pg = _page(browser, served)
    try:
        pg.evaluate("() => cycleTheme()")
        pg.wait_for_timeout(1500)
        fills = _mindmap_fills(pg)
        if fills is None:
            pytest.skip("this mermaid build did not draw a mindmap node to measure")
        assert fills["root"] != "rgb(0, 0, 0)", "the root node is painted black on a dark page"
        assert contrast(fills["root"], fills["page"]) >= 1.6, f"root {fills['root']} on page {fills['page']}"
    finally:
        pg.close()


def test_a_rail_jump_does_not_animate_under_reduced_motion(browser, served) -> None:
    pg = _page(browser, served, reduced_motion="reduce")
    try:
        assert pg.evaluate("() => matchMedia('(prefers-reduced-motion: reduce)').matches")
        positions = pg.evaluate("""async () => {
          const el = document.getElementById('long');
          const before = window.scrollY;
          el.scrollIntoView({ behavior: window.__okuScrollBehavior ? window.__okuScrollBehavior() : 'smooth' });
          const seen = new Set();
          for (let i = 0; i < 20; i++) {
            seen.add(Math.round(window.scrollY));
            await new Promise(r => requestAnimationFrame(r));
          }
          return { distinct: seen.size, moved: window.scrollY !== before };
        }""")
        assert positions["moved"], "the scroll never happened, so nothing was measured"
        assert positions["distinct"] <= 2, f"scrolled through {positions['distinct']} positions under reduce"
    finally:
        pg.close()


def _without_comments(js: str) -> str:
    """Comments explain the rule; only code can break it."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", js)


def test_the_kit_asks_for_the_behaviour_rather_than_hardcoding_it() -> None:
    """The CSS half was already right; the JS call sites overrode it."""
    js = (KIT / "chrome.js").read_text(encoding="utf-8")
    assert "function __okuScrollBehavior()" in js
    code = _without_comments(js)
    pinned = [m for m in re.findall(r"behavior:\s*'smooth'", code)]
    assert pinned == [], f"{len(pinned)} scripted scroll(s) still pin smooth"


def test_two_quick_clicks_render_the_page_in_the_address_bar(browser, served) -> None:
    pg = _page(browser, served)
    try:
        state = pg.evaluate("""async () => {
          // Both navigations are started in the same tick, the second
          // last. Whichever response lands last used to win the DOM.
          window.history.pushState({}, '', 'beta.html');
          const a = __okuFetchAndRender('alpha.html', '');
          const b = __okuFetchAndRender('beta.html', '');
          await Promise.all([a, b]);
          return { url: location.pathname, h1: document.querySelector('h1').textContent.trim(),
                   current: window.__okuCurrentPage };
        }""")
        assert state["url"].endswith("beta.html")
        assert state["h1"] == "Beta", f"address bar says beta, page says {state['h1']}"
        assert state["current"] == "beta.html"
    finally:
        pg.close()


def test_collapsing_a_group_keeps_the_focus_on_the_chevron(browser, served) -> None:
    """`renderTable` detaches every row, and removing the ancestor of the
    focused element blurs it to <body> — so the follow-up Space reached
    the document and scrolled the page instead of reopening the group."""
    pg = _page(browser, served)
    try:
        result = pg.evaluate("""() => {
          const chev = document.querySelector('.okt-group-chevron');
          if (!chev) return null;
          chev.focus();
          const before = document.activeElement.className;
          chev.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
          return { before, after: document.activeElement.className,
                   tag: document.activeElement.tagName };
        }""")
        assert result is not None, "no grouped table rendered to test"
        assert "okt-group-chevron" in result["before"]
        assert "okt-group-chevron" in result["after"], f"focus fell to {result['tag']}"
    finally:
        pg.close()
