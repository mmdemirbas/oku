"""Numeric UI invariants — see CLAUDE.md §"UI invariants".

Every assertion here is a boundingBox / computed-value check, never an
eyeball. Diagram assertions count host elements, not rendered SVG —
Mermaid loads from CDN and these tests must pass offline. Charts are
kit-native SVG, so chart assertions DO require rendered <svg>.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser

DESKTOP = {"width": 1280, "height": 900}
NARROW = {"width": 360, "height": 800}


def _goto(page, url: str) -> None:
    page.goto(url)
    page.wait_for_selector("main section")


def _literal_tag_text_nodes(page) -> int:
    """Count visible text nodes containing a raw '<code>' tag — the
    regression class where inline HTML in prose renders as literal
    text instead of a code span."""
    return page.evaluate(
        """() => {
            const w = document.createTreeWalker(
                document.querySelector('main'), NodeFilter.SHOW_TEXT);
            let n, hits = 0;
            while ((n = w.nextNode()))
                if (n.textContent.includes('<code>')) hits++;
            return hits;
        }"""
    )


def test_sidebar_spans_viewport(page, site_url):
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/architecture.html")
    box = page.locator("page-nav").bounding_box()
    assert box is not None, "page-nav missing"
    assert abs(box["y"]) <= 1, f"sidebar must start at y=0, got {box['y']}"
    assert abs(box["height"] - DESKTOP["height"]) <= 1, (
        f"sidebar surface must span the viewport: height {box['height']} != {DESKTOP['height']}"
    )


def test_architecture_renders_fence_lifted_blocks(page, site_url):
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/architecture.html")
    assert page.locator("oku-diagram").count() == 6, "mermaid fences must lift to oku-diagram hosts"
    assert page.locator("main section").count() >= 10
    assert page.locator("pre code").count() >= 5
    assert _literal_tag_text_nodes(page) == 0, "raw <code> tags visible in prose"


def test_charts_render_kit_native_svg(page, site_url):
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_selector("oku-chart svg")
    assert page.locator("oku-chart").count() >= 40, "charts page lost its fence-lifted charts"
    assert page.locator("oku-chart svg").count() >= 40, "charts must render kit-native SVG"
    assert _literal_tag_text_nodes(page) == 0


def test_drawer_geometry_at_narrow_viewport(page, site_url):
    page.set_viewport_size(NARROW)
    _goto(page, f"{site_url}/docs/architecture.html")

    toggle = page.locator(".ctrl-btn.drawer-toggle").bounding_box()
    assert toggle is not None, "drawer toggle missing at 360px"
    assert toggle["width"] >= 24 and toggle["height"] >= 24, "touch target below 24px minimum"

    nav = page.locator("page-nav").bounding_box()
    assert nav["x"] + nav["width"] <= 0 or nav["x"] >= NARROW["width"], (
        f"sidebar must be off-canvas at 360px, got x={nav['x']}"
    )
    no_hscroll = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert no_hscroll, "horizontal scroll at 360px"

    page.click(".ctrl-btn.drawer-toggle")
    # The slide-in is a CSS transition — wait on the geometry, not the
    # class, so the assertion never reads a mid-animation frame.
    page.wait_for_function("document.querySelector('page-nav').getBoundingClientRect().left > -1")
    nav = page.locator("page-nav").bounding_box()
    assert abs(nav["x"]) <= 1, f"open drawer must sit at x=0, got {nav['x']}"
    assert abs(nav["height"] - NARROW["height"]) <= 1, "open drawer must span the viewport"

    page.keyboard.press("Escape")
    page.wait_for_function("!document.body.classList.contains('drawer-open')")


def test_html_island_script_executes(page, site_url):
    _goto(page, f"{site_url}/examples/markdown-demo.html")
    out = page.locator("#md-demo-out")
    assert out.text_content() == "8.00 ms per GB"
    page.fill("#md-demo-bw", "2000")
    page.dispatch_event("#md-demo-bw", "input")
    assert out.text_content() == "4.00 ms per GB", (
        "island <script> did not execute — createContextualFragment path broken"
    )


def test_task_list_and_definition_list_render(page, site_url):
    _goto(page, f"{site_url}/examples/markdown-demo.html")
    boxes = page.locator("li.task-item input[type=checkbox]")
    assert boxes.count() == 3
    assert page.locator("li.task-item input:checked").count() == 2
    assert page.locator("dl.md-dl dt").count() == 2


def test_path_router_keeps_url_and_content_in_sync(page, site_url):
    """The nav bug class: URL path and rendered page must never
    diverge. Tree-click routes via pushState (no reload), reload keeps
    the page, Back restores the previous one."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/charts.html")
    assert page.title() == "Charts"
    assert page.locator("oku-chart").count() >= 40

    page.evaluate("window.__navMarker = 42")
    page.click('page-nav a[href$="diagrams.html"]')
    page.wait_for_function("document.title === 'Diagrams'")
    assert page.evaluate("location.pathname").endswith("/docs/diagrams.html")
    assert page.evaluate("window.__navMarker === 42"), "tree click must not full-reload"
    assert page.locator("oku-diagram").count() >= 5

    page.reload()
    page.wait_for_selector("main section")
    assert page.title() == "Diagrams", "reload must keep the routed page"

    page.go_back()
    page.wait_for_function("document.title === 'Charts'")
    assert page.evaluate("location.pathname").endswith("/docs/charts.html")


def test_legacy_hash_urls_normalize_to_real_page(page, site_url):
    _goto(page, f"{site_url}/docs/charts.html#diagrams.html:mermaid-journey")
    page.wait_for_function("document.title === 'Diagrams'")
    assert page.evaluate("location.pathname").endswith("/docs/diagrams.html")
    assert page.evaluate("location.hash") == "#mermaid-journey"


def test_diagram_legibility_floor(page, site_url):
    """Wide mermaid diagrams render at ≥90% of authored width inside a
    horizontal scroll context — never shrunk to illegible label sizes."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/architecture.html")
    page.wait_for_selector("oku-diagram .okd-render svg")
    page.wait_for_timeout(1500)
    ratios = page.evaluate(
        """() => [...document.querySelectorAll('oku-diagram .okd-render svg')].map(s => {
            const vb = s.viewBox.baseVal;
            return vb.width > 0 ? s.getBoundingClientRect().width / vb.width : 1;
        })"""
    )
    assert ratios, "no rendered diagrams"
    assert all(r >= 0.89 for r in ratios), f"diagram shrunk below legibility floor: {ratios}"


def test_sunburst_has_legend_chips(page, site_url):
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_selector('oku-chart[type="sunburst"] svg')
    chips = page.locator('oku-chart[type="sunburst"] .okc-legend-chip')
    assert chips.count() >= 2, "sunburst must identify its top-level ring via legend chips"


def test_inline_html_allowlist_renders(page, site_url):
    """Allow-listed inline tags (<kbd>, <sub>, …) render as elements;
    nothing in prose shows a raw tag."""
    _goto(page, f"{site_url}/docs/reference.html")
    page.wait_for_timeout(1500)
    assert page.locator("main kbd").count() >= 2
    literal = page.evaluate(
        """() => {
            const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
            let n, hits = 0;
            while ((n = w.nextNode()))
                if (/<\\/?(kbd|sub|sup|code)>/.test(n.textContent) && !n.parentElement.closest('code, pre')) hits++;
            return hits;
        }"""
    )
    assert literal == 0, "raw inline tags visible in prose"
