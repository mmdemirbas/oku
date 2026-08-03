"""Numeric UI invariants — see CLAUDE.md §"UI invariants".

Every assertion here is a boundingBox / computed-value check, never an
eyeball. Diagram assertions count host elements, not rendered SVG —
Mermaid loads from CDN and these tests must pass offline. Charts are
kit-native SVG, so chart assertions DO require rendered <svg>.
"""

from __future__ import annotations

import math

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


def test_chart_axis_ticks_are_nice_numbers(page, site_url):
    """Linear axes label human-friendly values, not the raw even-split.
    Before the nice-tick pass the 7-day latency line read its X axis as
    0.78 · 2.3 · 3.9 · 5.6 · 7.3; it must now read whole days on a nice,
    uniform step."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_selector('oku-chart[title="P50 latency over 7 days"] svg')
    xticks = page.evaluate(
        """() => {
            const c = document.querySelector('oku-chart[title="P50 latency over 7 days"]');
            return [...c.querySelectorAll('text.okc-tick[text-anchor="middle"]')]
                .map(t => parseFloat(t.textContent))
                .filter(v => !Number.isNaN(v));
        }"""
    )
    assert len(xticks) >= 3, f"expected x-axis ticks, got {xticks}"
    # Whole-day labels: no 0.78 / 2.3 fractional noise.
    assert all(abs(v - round(v)) < 1e-9 for v in xticks), f"x ticks not whole numbers: {xticks}"
    # Uniform spacing on a nice step (1 / 2 / 2.5 / 5 / 10 × 10ᵏ).
    steps = [round(xticks[i + 1] - xticks[i], 6) for i in range(len(xticks) - 1)]
    assert len(set(steps)) == 1, f"non-uniform tick spacing: {steps}"
    mant = steps[0] / 10 ** math.floor(math.log10(steps[0]))
    assert round(mant, 6) in (1.0, 2.0, 2.5, 5.0), f"tick step not nice: {steps[0]}"


def test_example_output_outweighs_code(page, site_url):
    """In a CODE/OUTPUT demo pair the rendered output is the point; it
    must be the wider column (was a 50/50 split that let source out-shout
    its own result)."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/reference.html")
    page.wait_for_selector(".example-pair .example-output")
    boxes = page.evaluate(
        """() => {
            for (const p of document.querySelectorAll('.example-pair')) {
                const c = p.querySelector('.example-code');
                const o = p.querySelector('.example-output');
                if (!c || !o) continue;
                const cb = c.getBoundingClientRect(), ob = o.getBoundingClientRect();
                if (cb.width > 0 && ob.width > 0) return {code: cb.width, output: ob.width};
            }
            return null;
        }"""
    )
    assert boxes is not None, "no two-column example-pair found at desktop width"
    # 2fr:3fr → output ≈ 1.5× code. Pin the dominance with margin.
    assert boxes["output"] >= boxes["code"] * 1.3, f"output column must dominate code: {boxes}"


def test_nav_cards_are_unordered_two_column_grid(page, site_url):
    """The index Documentation menu is a set of parallel destinations, not
    a numbered sequence: render it as an unordered 2-up card grid with no
    step numerals (numerals imply an order the menu doesn't have)."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/index.html")
    page.wait_for_selector(".step-cards-grid .step-card")
    info = page.evaluate(
        """() => {
            const cards = [...document.querySelectorAll('.step-cards-grid .step-card')];
            return {
                count: cards.length,
                numerals: document.querySelectorAll('.step-cards-grid .step-num').length,
                columns: new Set(cards.map(c => Math.round(c.getBoundingClientRect().x))).size,
            };
        }"""
    )
    assert info["count"] >= 6, f"nav menu lost its cards: {info}"
    assert info["numerals"] == 0, "nav cards must not carry sequence numerals"
    assert info["columns"] == 2, f"nav cards must tile two-up at desktop, got {info['columns']}"


def test_hero_keeps_gradient_wash_at_desktop(page, site_url):
    """The hero cover must read as a branded block on a wide desktop, not
    flat white: it carries a diagonal accent wash (visible at any width)
    on top of the two corner glows. Gradient legibility itself needs the
    eye (see commit screenshots); this guards the layers from silently
    being dropped."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/index.html")
    bg = page.evaluate("() => getComputedStyle(document.querySelector('header.cover')).backgroundImage")
    assert bg.count("linear-gradient") >= 1, f"hero lost its diagonal wash: {bg}"
    assert bg.count("radial-gradient") >= 2, f"hero lost its corner glows: {bg}"


def test_table_status_cells_render_semantic_pills(page, site_url):
    """A table column with a `status` value→verdict map renders coloured
    status pills (not bare text), and the pill is purely visual — the cell
    text stays the raw value so sort / filter / group still read it."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/tables.html")
    page.wait_for_selector(".okt-status")
    info = page.evaluate(
        """() => {
            const out = {};
            for (const c of document.querySelectorAll('td .okt-status')) {
                out[c.textContent.trim()] = {
                    cls: c.className,
                    tdText: c.closest('td').textContent.trim(),
                };
            }
            return out;
        }"""
    )
    assert "okt-status-good" in info.get("done", {}).get("cls", ""), info
    assert "okt-status-warn" in info.get("in-progress", {}).get("cls", ""), info
    assert "okt-status-neutral" in info.get("queued", {}).get("cls", ""), info
    # Pill is visual only — underlying cell value preserved for sort/filter.
    assert info["done"]["tdText"] == "done", "status pill must not alter the cell value"


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


def test_diagram_fits_container(page, site_url):
    """Rendered mermaid diagrams FIT their column: never overflow (the
    old clip / horizontal-scroll regression) and never up-scale beyond
    their authored size (no cartoonish labels). Detail on a wide diagram
    is reachable via the fullscreen lightbox, not an inline scrollbar."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/architecture.html")
    page.wait_for_selector("oku-diagram .okd-render svg")
    page.wait_for_timeout(1500)
    data = page.evaluate(
        """() => [...document.querySelectorAll('oku-diagram')].map(d => {
            const s = d.querySelector('.okd-render svg');
            const host = d.querySelector('.okd-render');
            const vb = s.viewBox.baseVal;
            const w = s.getBoundingClientRect().width;
            return { fits: w <= host.getBoundingClientRect().width + 1,
                     notUpscaled: vb.width > 0 ? w <= vb.width + 1 : true };
        })"""
    )
    assert data, "no rendered diagrams"
    assert all(d["fits"] for d in data), f"diagram overflows its column (clips): {data}"
    assert all(d["notUpscaled"] for d in data), f"diagram up-scaled beyond authored size: {data}"


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


def test_lightbox_uses_full_viewport_and_keeps_live_content(page, site_url):
    """Expanded views must (a) fill the whole browser area and (b) move
    the LIVE element in — clones lose tooltips and hover wiring. Close
    must return the element to its inline slot."""
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/architecture.html")
    page.wait_for_selector("oku-diagram .okd-render svg")

    page.evaluate("document.querySelector('oku-diagram').__live = 1")
    page.hover("oku-diagram")
    page.click('oku-diagram [title="Expand to fullscreen"]')
    page.wait_for_selector(".okt-lightbox.open")

    frame = page.locator(".okt-lightbox-frame").bounding_box()
    vw, vh = page.evaluate("[innerWidth, innerHeight]")
    assert abs(frame["width"] - vw) <= 1 and abs(frame["height"] - vh) <= 1, (
        f"lightbox frame {frame['width']}x{frame['height']} must fill viewport {vw}x{vh}"
    )
    close = page.locator(".okt-lightbox-close").bounding_box()
    assert close["y"] >= 0 and close["x"] + close["width"] <= vw, "close button must sit inside the viewport"
    assert page.evaluate("document.querySelector('.okt-lightbox oku-diagram')?.__live") == 1, (
        "lightbox must contain the LIVE diagram host, not a clone"
    )

    page.click(".okt-lightbox-close")
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('main oku-diagram')?.__live") == 1, (
        "close must return the live host to its inline slot"
    )
    assert page.evaluate("!document.querySelector('.okt-lightbox oku-diagram')")


def test_lightbox_chart_tooltip_still_fires(page, site_url):
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_selector('oku-chart[type="line"] svg')
    page.hover('oku-chart[type="line"]')
    page.click('oku-chart[type="line"] [title*="ullscreen"]')
    page.wait_for_selector(".okt-lightbox.open")
    page.locator(".okt-lightbox oku-chart svg").first.hover(position={"x": 150, "y": 100})
    page.wait_for_selector(".okc-tooltip.visible", timeout=3000)
    page.keyboard.press("Escape")


def test_format_corpus_renders_identically(page, site_url):
    """The same page through three different source formats must
    produce the same rendered structure — sections, charts, KPI tiles,
    step cards all equal."""
    counts = {}
    for fmt in ("markdown", "html", "asciidoc"):
        _goto(page, f"{site_url}/examples/format-comparison/{fmt}/sample-viz.html")
        page.wait_for_selector("oku-chart svg")
        counts[fmt] = page.evaluate(
            """() => ({
                sections: document.querySelectorAll('main section').length,
                charts: document.querySelectorAll('oku-chart').length,
                diagrams: document.querySelectorAll('oku-diagram').length,
                title: document.title,
            })"""
        )
    assert counts["markdown"] == counts["html"] == counts["asciidoc"], counts


def test_comparison_page_rendered_links_all_work(page, site_url):
    """Every 'See them rendered' link on the comparison page navigates
    to a rendering page — cross-docs-root links navigate natively (no
    SPA 404), json-backed stubs retarget kit assets at any depth."""
    _goto(page, f"{site_url}/docs/format-comparison.html")
    hrefs = page.evaluate(
        """() => [...document.querySelectorAll('main a[href*="examples/format-comparison"]')]
                .map(a => a.getAttribute('href'))"""
    )
    assert len(hrefs) == 10, f"expected 10 rendered links, got {len(hrefs)}"
    for href in hrefs:
        _goto(page, f"{site_url}/docs/format-comparison.html")
        page.click(f'main a[href="{href}"]')
        page.wait_for_selector("main section", timeout=8000)
        assert page.locator("main section").count() >= 3, f"{href} rendered empty"
        assert page.title().startswith("Sample"), f"{href} landed on wrong page: {page.title()}"


def test_gantt_labels_never_clip_at_svg_edge(page, site_url):
    """Gantt row labels stay INSIDE the chart's own box at every
    viewport. The left gutter used to be a fixed 160 units, so any
    label wider than that ran off the SVG's left edge and was clipped
    mid-word — silently, and worse as the viewport narrowed.

    Long, real-world labels are injected here because the docs' gantt
    sample uses short ones ("Design", "Build") that cannot expose the
    bug. Assertion is numeric: every label's bounding box must sit at
    or inside the SVG's left edge, and each label's text must be
    non-empty (a zero-width gutter would "pass" a bounds check while
    rendering nothing).
    """
    labels = [
        "Ankara rehberi: Telegram verisi → yapısal liste",
        "Hukuki hazırlık (belgeler, avukat, yazılı cevap)",
        "Mülakat hazırlığı (Spark boşluğu + anlatılar)",
        "QA",
    ]
    for viewport in (DESKTOP, NARROW):
        page.set_viewport_size(viewport)
        _goto(page, f"{site_url}/docs/charts.html")
        page.wait_for_selector("oku-chart svg")
        data = page.evaluate(
            """(labels) => {
                const host = document.createElement('oku-chart');
                host.setAttribute('type', 'gantt');
                host.setAttribute('title', 'clip probe');
                const s = document.createElement('script');
                s.type = 'application/json';
                s.textContent = '[]';
                host.appendChild(s);
                const ex = document.createElement('script');
                ex.type = 'application/json';
                ex.setAttribute('data-extras', 'gantt');
                ex.textContent = JSON.stringify({
                    tasks: labels.map((l, i) => ({label: l, start: i, end: i + 2}))
                });
                host.appendChild(ex);
                document.querySelector('main section').appendChild(host);
                const svg = host.querySelector('svg');
                if (!svg) return {rendered: false};
                const sr = svg.getBoundingClientRect();
                const rows = [...svg.querySelectorAll('.okc-gantt-label')].map(t => {
                    const r = t.getBoundingClientRect();
                    // Direct text nodes only — textContent would also
                    // splice in the nested <title> tooltip string.
                    const visible = [...t.childNodes]
                        .filter(n => n.nodeType === Node.TEXT_NODE)
                        .map(n => n.nodeValue).join('');
                    return {
                        text: visible.trim(),
                        title: (t.querySelector('title') || {}).textContent || '',
                        overflowLeft: +(sr.left - r.left).toFixed(2),
                        overflowRight: +(r.right - sr.right).toFixed(2),
                    };
                });
                host.remove();
                return {rendered: true, rows, count: rows.length};
            }""",
            labels,
        )
        assert data["rendered"], "gantt did not render"
        assert data["count"] == len(labels), f"expected {len(labels)} labels, got {data['count']}"
        for row in data["rows"]:
            assert row["text"], f"empty gantt label at {viewport}: {row}"
            assert row["overflowLeft"] <= 1, (
                f"gantt label clipped at left edge ({viewport['width']}px): "
                f"{row['overflowLeft']}px over — {row!r}"
            )
            assert row["overflowRight"] <= 1, (
                f"gantt label overruns the plot ({viewport['width']}px): {row!r}"
            )
        # Truncated labels must keep the full string reachable in <title>.
        for row, original in zip(data["rows"], labels):
            if row["text"] != original:
                assert row["text"].endswith("…"), f"silent truncation: {row!r}"
                assert row["title"] == original, f"tooltip lost the full label: {row!r}"


def test_gutter_charts_keep_long_labels_inside_the_svg(page, site_url):
    """Charts that park labels in a side gutter (gantt row labels,
    funnel stage labels, waffle legend) sized that gutter with a
    constant, so a long label overflowed the SVG box and got clipped.
    Same defect, three renderers — assert the class, not one instance.

    Labels here are deliberately longer than every fixed gutter the kit
    used to hardcode (160 / 168 / 160 units).
    """
    long_label = "Ankara rehberi: Telegram verisi yapısal listeye dönüştürülür"
    specs = [
        (
            "gantt",
            "gantt",
            ".okc-gantt-label",
            {"tasks": [{"label": long_label, "start": 0, "end": 3}, {"label": "QA", "start": 2, "end": 4}]},
        ),
        (
            "funnel",
            "funnel",
            ".okc-funnel-label",
            {"stages": [{"label": long_label, "value": 200}, {"label": "Kısa", "value": 30}]},
        ),
        (
            "waffle",
            "waffle",
            ".okc-waffle-legend-label",
            {"segments": [{"label": long_label, "count": 60}, {"label": "Kısa", "count": 40}], "total": 100},
        ),
    ]
    for viewport in (DESKTOP, NARROW):
        page.set_viewport_size(viewport)
        _goto(page, f"{site_url}/docs/charts.html")
        page.wait_for_selector("oku-chart svg")
        for chart_type, extras_key, selector, payload in specs:
            data = page.evaluate(
                """([type, extrasKey, selector, payload]) => {
                    const host = document.createElement('oku-chart');
                    host.setAttribute('type', type);
                    const s = document.createElement('script');
                    s.type = 'application/json'; s.textContent = '[]';
                    host.appendChild(s);
                    const ex = document.createElement('script');
                    ex.type = 'application/json';
                    ex.setAttribute('data-extras', extrasKey);
                    ex.textContent = JSON.stringify(payload);
                    host.appendChild(ex);
                    document.querySelector('main section').appendChild(host);
                    const svg = host.querySelector('svg');
                    if (!svg) { host.remove(); return {rendered: false}; }
                    const sr = svg.getBoundingClientRect();
                    const rows = [...svg.querySelectorAll(selector)].map(t => {
                        const r = t.getBoundingClientRect();
                        const visible = [...t.childNodes]
                            .filter(n => n.nodeType === Node.TEXT_NODE)
                            .map(n => n.nodeValue).join('').trim();
                        return {text: visible,
                                left: +(sr.left - r.left).toFixed(2),
                                right: +(r.right - sr.right).toFixed(2)};
                    });
                    host.remove();
                    return {rendered: true, rows};
                }""",
                [chart_type, extras_key, selector, payload],
            )
            assert data["rendered"], f"{chart_type} did not render"
            assert data["rows"], f"{chart_type} rendered no labels"
            for row in data["rows"]:
                assert row["text"], f"{chart_type}: empty label at {viewport}"
                assert row["left"] <= 1, (
                    f"{chart_type} label clipped left at {viewport['width']}px: "
                    f"{row['left']}px over — {row!r}"
                )
                assert row["right"] <= 1, (
                    f"{chart_type} label clipped right at {viewport['width']}px: "
                    f"{row['right']}px over — {row!r}"
                )


def test_every_chart_clips_to_its_own_plot_rect(page, site_url):
    """SVG url(#id) references resolve against the DOCUMENT, so a
    clipPath id shared by every chart made all of them clip to the FIRST
    chart's plot rectangle — series cut off or spilling over depending on
    page order. Ids must be unique, and each chart's clip must point at a
    rect inside that same chart."""
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_timeout(1500)
    result = page.evaluate(
        """() => {
            const ids = [...document.querySelectorAll('clipPath[id]')].map(c => c.id);
            const refs = [...document.querySelectorAll('[clip-path^="url(#"]')].map(g => {
                const id = g.getAttribute('clip-path').slice(5, -1);  // strip url(# and )
                const target = document.getElementById(id);
                return { id, sameChart: !!target && target.closest('oku-chart') === g.closest('oku-chart') };
            });
            return { ids, refs };
        }"""
    )
    assert len(result["ids"]) > 1, "expected several charts on this page"
    assert len(set(result["ids"])) == len(result["ids"]), result["ids"]
    assert result["refs"], "expected clipped plot groups"
    assert all(r["sameChart"] for r in result["refs"]), result["refs"]


def test_no_duplicate_element_ids_on_a_chart_heavy_page(page, site_url):
    """Duplicate ids break getElementById for everything after the first
    one — deep links, the TOC and SVG references alike."""
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_timeout(1500)
    dups = page.evaluate(
        """() => {
            const seen = new Set(), dup = [];
            document.querySelectorAll('[id]').forEach(e => {
                if (seen.has(e.id)) dup.push(e.id); else seen.add(e.id);
            });
            return dup;
        }"""
    )
    assert dups == [], dups


@pytest.mark.parametrize(
    "rel",
    [
        "docs/index.html",
        "docs/reference.html",
        "docs/charts.html",
        "docs/tables.html",
        "notes/audit-2026-08-03.html",
    ],
)
def test_no_horizontal_page_scroll_at_360(page, site_url, rel):
    """Wide content scrolls inside its own container; the page body never
    does. A grid item defaults to min-width:auto, so one long path or
    URL inside a card refuses to shrink and drags the whole document
    wider than the viewport — which is what an audit page full of file
    paths did at 360px."""
    page.set_viewport_size(NARROW)
    _goto(page, f"{site_url}/{rel}")
    page.wait_for_timeout(600)
    doc_w, win_w = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    assert doc_w <= win_w, f"{rel}: document {doc_w}px wider than viewport {win_w}px"


CONTAINMENT_PROBE = """() => {
  const main = document.querySelector('main');
  const mb = main.getBoundingClientRect();
  const out = [];
  main.querySelectorAll('*').forEach(e => {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') return;
    if (r.width === 0 && r.height === 0) return;
    if (r.right <= mb.right + 1.5 && r.left >= mb.left - 1.5) return;
    // Wide content MAY overflow inside a scroll container — that is the
    // documented pattern for tables, boards and code. What it may not do
    // is overflow with nowhere to scroll.
    let a = e.parentElement;
    while (a && a !== main.parentElement) {
      const ov = getComputedStyle(a).overflowX;
      if ((ov === 'auto' || ov === 'scroll') && a.scrollWidth > a.clientWidth + 1) return;
      a = a.parentElement;
    }
    const cls = (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className) || '';
    out.push(e.tagName + '.' + cls + ' +' + Math.round(Math.max(r.right - mb.right, mb.left - r.left)) + 'px');
  });
  return [...new Set(out)].slice(0, 8);
}"""


@pytest.mark.parametrize("width", [1440, 768, 360])
@pytest.mark.parametrize("rel", ["docs/charts.html", "docs/tables.html", "docs/reference.html"])
def test_nothing_escapes_its_container(page, site_url, rel, width):
    """Every rendered element stays inside <main>, unless it sits in a
    container that actually scrolls. This is the one assertion that
    covers the whole primitive set at once — 48 charts, boards, wide
    tables, code blocks — at every breakpoint."""
    page.set_viewport_size({"width": width, "height": 900})
    _goto(page, f"{site_url}/{rel}")
    page.wait_for_timeout(1500)
    escapes = page.evaluate(CONTAINMENT_PROBE)
    assert escapes == [], f"{rel} @{width}px: {escapes}"


def test_containment_holds_in_dark_theme(page, site_url):
    """Dark theme swaps tokens, and a token change can change a border
    or padding — so containment is asserted in both themes, not one."""
    page.add_init_script("try{localStorage.setItem('theme-pref','dark')}catch(e){}")
    page.set_viewport_size(DESKTOP)
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_timeout(1500)
    assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
    assert page.evaluate(CONTAINMENT_PROBE) == []


def test_every_chart_on_the_charts_page_renders_a_visual(page, site_url):
    """A chart that fails to render leaves an empty host — visible as a
    gap, invisible to a schema check. Every <oku-chart> must carry a
    non-trivial rendered surface (SVG or the DIV-based bar family)."""
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_timeout(1800)
    empty = page.evaluate(
        """() => [...document.querySelectorAll('oku-chart')]
             .filter(c => {
               const v = c.querySelector('svg, .bar-chart, .bar-chart-multi, .waffle, .kpi-grid');
               if (!v) return true;
               const r = v.getBoundingClientRect();
               return r.width < 8 || r.height < 8;
             })
             .map(c => c.getAttribute('type') || c.textContent.slice(0, 30))"""
    )
    assert empty == [], empty


# ---------- accessibility baseline ----------


A11Y_PROBE = """() => {
  const vis = e => {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const name = e =>
    (e.getAttribute('aria-label') || '').trim() ||
    (e.getAttribute('title') || '').trim() ||
    (e.textContent || '').trim() ||
    (e.labels && e.labels.length ? [...e.labels].map(l => l.textContent.trim()).join(' ') : '');
  const controls = [...document.querySelectorAll(
    'button, [role="button"], input, select, a[href]')].filter(vis);
  return {
    unnamed: [...new Set(controls.filter(e => !name(e))
      .map(e => e.tagName + '.' + (e.className || '')))],
    focusableButHidden: [...new Set([...document.querySelectorAll(
      '[aria-hidden="true"]')].filter(e => e.tabIndex >= 0 && vis(e))
      .map(e => e.tagName + '.' + (e.className || '')))],
    unnamedCharts: [...document.querySelectorAll('oku-chart svg.okc-svg')]
      .filter(vis).filter(s => !s.getAttribute('aria-label') && !s.querySelector('title')).length,
    landmarks: {
      main: document.querySelectorAll('main').length,
      h1: document.querySelectorAll('main h1').length,
      lang: document.documentElement.lang || '',
    },
  };
}"""


@pytest.mark.parametrize("rel", ["docs/charts.html", "docs/tables.html", "docs/reference.html"])
def test_accessibility_baseline(page, site_url, rel):
    """Every visible control has an accessible name, nothing is both
    focusable and aria-hidden (a control a keyboard reaches and a screen
    reader cannot see), every chart SVG is named, and the page has one
    main, one h1 and a language."""
    _goto(page, f"{site_url}/{rel}")
    page.wait_for_timeout(1500)
    r = page.evaluate(A11Y_PROBE)
    assert r["unnamed"] == [], f"{rel}: unnamed controls {r['unnamed']}"
    assert r["focusableButHidden"] == [], f"{rel}: {r['focusableButHidden']}"
    assert r["unnamedCharts"] == 0, f"{rel}: {r['unnamedCharts']} chart SVGs without a name"
    assert r["landmarks"] == {"main": 1, "h1": 1, "lang": "en"}, r["landmarks"]


def test_pointer_targets_meet_the_minimum(page, site_url):
    """Chip rack, group chevrons and toolbar buttons are the surfaces a
    reader actually clicks; they must be at least 24px in both axes.
    Inline affordances inside prose or a code gutter are exempt — that
    is the documented exception, not an oversight."""
    _goto(page, f"{site_url}/docs/tables.html")
    page.wait_for_timeout(1500)
    small = page.evaluate(
        """() => [...document.querySelectorAll(
             '.okt-chip, .okt-group-chevron, .okt-table-controls button, .copy-btn, .okt-wrap-btn')]
           .map(e => ({ n: e.className, r: e.getBoundingClientRect() }))
           .filter(o => o.r.width > 0 && (o.r.width < 24 || o.r.height < 24))
           .map(o => o.n + ' ' + Math.round(o.r.width) + 'x' + Math.round(o.r.height))"""
    )
    assert small == [], small


def test_code_fold_marker_is_a_named_button_when_active(page, site_url):
    """The marker starts as decoration (aria-hidden) and becomes a real
    button once a fold is attached. It used to keep aria-hidden while
    gaining tabindex — reachable by keyboard, invisible to a reader."""
    _goto(page, f"{site_url}/docs/reference.html")
    page.wait_for_timeout(1500)
    state = page.evaluate(
        """() => [...document.querySelectorAll('.okt-fold-marker.okt-foldable')].slice(0, 3)
             .map(m => ({ hidden: m.getAttribute('aria-hidden'), label: m.getAttribute('aria-label'),
                          role: m.getAttribute('role'), expanded: m.getAttribute('aria-expanded') }))"""
    )
    assert state, "expected at least one foldable marker on the reference page"
    for m in state:
        assert m["hidden"] is None, m
        assert m["label"], m
        assert m["role"] == "button" and m["expanded"] in ("true", "false"), m


def test_theme_toggle_leaves_the_dom_where_it_started(page, site_url):
    """Charts, code blocks and tables all re-render on a theme change.
    If any of them appends instead of replacing, a page grows every time
    the reader flips the theme — invisible until a long document turns
    sluggish. Six round trips must land on the counts it started with."""
    snapshot = """() => ({
      elements: document.querySelectorAll('main *').length,
      chartSvgs: document.querySelectorAll('oku-chart svg').length,
      copyBtns: document.querySelectorAll('main .copy-btn').length,
      wrapBtns: document.querySelectorAll('main .okt-wrap-btn').length,
      tableWraps: document.querySelectorAll('main .okt-table-wrap').length,
      theme: document.documentElement.dataset.theme,
    })"""
    _goto(page, f"{site_url}/docs/charts.html")
    page.wait_for_timeout(1800)
    before = page.evaluate(snapshot)
    for _ in range(6):
        page.click(".theme-toggle, [data-theme-toggle], .ctrl-btn[title*='theme' i]")
        page.wait_for_timeout(320)
    page.wait_for_timeout(900)
    after = page.evaluate(snapshot)
    assert after == before, {k: (before[k], after[k]) for k in before if before[k] != after[k]}
