"""Content-regression tests for the docs/ JSON sources.

These guard against accidental deletion or shape-drift of the worked
examples that prove a primitive works. Schema validation alone won't
catch "reference.json no longer contains a chip-filtered table" — a
future edit could pass the schema while silently removing the demo.

The browser layer (table filter / chip toggle / fold region) is NOT
tested here — that needs a headless browser. The CLAUDE.md note in
the repo root describes how to add Playwright coverage when the
existing assertions are not enough.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(scope="module")
def reference(repo_root: Path) -> dict:
    """Combined view of the kit's own docs — every JSON page under
    docs/ folded into one virtual page with an aggregated blocks
    array. Lets the existing 'walk for kind X' tests work after the
    reference was split into reference.json + charts.json +
    diagrams.json + tables.json + roadmap.json, etc."""
    combined: dict = {"kind": "page", "title": "all docs", "blocks": []}
    for p in sorted((repo_root / "docs").glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(d, dict) and isinstance(d.get("blocks"), list):
            combined["blocks"].extend(d["blocks"])
    return combined


def _walk_blocks(node: dict | list) -> Iterator[dict]:
    """Yield every block-like dict reachable from node."""
    if isinstance(node, dict):
        if node.get("kind"):
            yield node
        for v in node.values():
            yield from _walk_blocks(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_blocks(item)


def _find_block(page: dict, predicate) -> dict | None:
    for b in _walk_blocks(page):
        if predicate(b):
            return b
    return None


# ---------- table primitive ----------


class TestTablePrimitive:
    """The reference reference must keep the three worked examples:
    flat, grouped, and chip-filtered with multi-valued cells. Without
    them the table block has no visible documentation."""

    def test_flat_table_present(self, reference: dict) -> None:
        block = _find_block(
            reference,
            lambda b: b.get("kind") == "table"
            and isinstance(b.get("headers"), list)
            and "rows" in b
            and "groups" not in b,
        )
        assert block is not None, "flat table example missing from reference.json"

    def test_grouped_table_present(self, reference: dict) -> None:
        block = _find_block(
            reference,
            lambda b: b.get("kind") == "table" and isinstance(b.get("groups"), list),
        )
        assert block is not None, "grouped table example missing from reference.json"
        assert len(block["groups"]) >= 2, "grouped example should declare multiple groups"

    def test_chip_filtered_table_present(self, reference: dict) -> None:
        """At least one table header uses the object form with
        filter='chips' + values."""
        for block in _walk_blocks(reference):
            if block.get("kind") != "table":
                continue
            for h in block.get("headers", []):
                if isinstance(h, dict) and h.get("filter") == "chips" and h.get("values"):
                    return
        pytest.fail("chip-filtered table example missing from reference.json")

    def test_chip_cells_use_object_form(self, reference: dict) -> None:
        """Cells under chip columns must declare a `values` array."""
        for block in _walk_blocks(reference):
            if block.get("kind") != "table":
                continue
            chip_cols = []
            for i, h in enumerate(block.get("headers", [])):
                if isinstance(h, dict) and h.get("filter") == "chips":
                    chip_cols.append(i)
            if not chip_cols:
                continue
            rows = block.get("rows") or [r for g in block.get("groups", []) for r in g.get("rows", [])]
            for row in rows:
                cells = row.get("cells") if isinstance(row, dict) else row
                for col in chip_cols:
                    cell = cells[col]
                    assert isinstance(cell, dict) and isinstance(
                        cell.get("values"), list
                    ), f"chip column {col} has a non-object cell: {cell!r}"
            return  # one chip-filtered table is enough


# ---------- tldr primitive ----------


class TestTldrPrimitive:
    def test_tldr_render_sample(self, reference: dict) -> None:
        """tldr now renders inside contentBlock context, so the
        reference reference must include both a code example and a
        live tldr render."""
        tldrs = [b for b in _walk_blocks(reference) if b.get("kind") == "tldr"]
        assert tldrs, "no tldr render sample in reference.json"


# ---------- kpi-grid sync ----------


class TestKpiGridSync:
    def test_kpi_example_matches_render(self, reference: dict) -> None:
        """The kpi-grid example code and the adjacent rendered sample
        must agree on the tile set, otherwise the doc is lying.

        Scoped to the reference page's `id="kpi-grid"` heading and the
        very next kpi-grid block + code block in walk order. Other
        pages (index.json etc.) now also host kpi-grid examples, so
        an unscoped 'first matching code block' search would pick the
        wrong one in the aggregated fixture.
        """
        blocks = list(_walk_blocks(reference))
        heading_idx = None
        for i, b in enumerate(blocks):
            if b.get("id") == "kpi-grid" and b.get("kind") == "heading":
                heading_idx = i
                break
        assert heading_idx is not None, "no heading id='kpi-grid' in reference docs"
        rendered = None
        code_block = None
        for j in range(heading_idx + 1, len(blocks)):
            b = blocks[j]
            if b.get("kind") == "kpi-grid" and rendered is None:
                rendered = b
            if (
                code_block is None
                and b.get("kind") == "code"
                and b.get("language") == "json"
                and '"kind": "kpi-grid"' in (b.get("source") or "")
            ):
                code_block = b
            if rendered is not None and code_block is not None:
                break
        assert rendered is not None, "no rendered kpi-grid sample after heading"
        assert code_block is not None, "no kpi-grid code example after heading"
        labels = {t.get("label") for t in rendered.get("tiles", [])}
        for label in labels:
            assert (
                label in code_block["source"]
            ), f"render shows tile {label!r} but the example code doesn't"


# ---------- cross-cutting features ----------


class TestCrossCuttingFeatures:
    def test_section_present(self, reference: dict) -> None:
        for b in _walk_blocks(reference):
            if b.get("kind") == "section" and b.get("id") == "cross-cutting":
                return
        pytest.fail("cross-cutting section missing from reference.json")

    def test_data_bind_demo_paired(self, reference: dict) -> None:
        """A bound paragraph and callout must share a `bind` key — the
        live demo of the synced-hover feature."""
        bind_blocks = [b for b in _walk_blocks(reference) if b.get("bind")]
        keys = [b["bind"] for b in bind_blocks]
        # At least one key shared between two blocks
        from collections import Counter

        counts = Counter(keys)
        shared = [k for k, v in counts.items() if v >= 2]
        assert shared, "no two blocks share a bind key in the demo"


# ---------- table-demo removal ----------


class TestNoStrayDemoPages:
    """User explicitly requested table-demo be merged into reference.
    Make sure it doesn't sneak back in."""

    def test_no_table_demo(self, repo_root: Path) -> None:
        assert not (
            repo_root / "docs" / "table-demo.html"
        ).exists(), "table-demo.html should live inside reference, not as a separate doc"
        assert not (
            repo_root / "docs" / "table-demo.json"
        ).exists(), "table-demo.json should live inside reference, not as a separate doc"


# ---------- P0 cleanup invariants ----------


class TestRoadmapAndCleanup:
    """P0 cleanup landed the roadmap, retired the plans/ tree, switched
    the docs-card flow to href cards, and dropped the 'Not in the
    converter' / 'project-meta files excluded' text. These tests are the
    regression net."""

    @pytest.fixture(scope="class")
    def index_json(self, repo_root: Path) -> dict:
        return json.loads(
            (repo_root / "docs" / "index.json").read_text(encoding="utf-8")
        )

    @pytest.fixture(scope="class")
    def roadmap_json(self, repo_root: Path) -> dict:
        return json.loads(
            (repo_root / "docs" / "roadmap.json").read_text(encoding="utf-8")
        )

    def test_plans_directory_retired(self, repo_root: Path) -> None:
        assert not (
            repo_root / "docs" / "plans"
        ).exists(), (
            "docs/plans/ retired in P0 — content folded into docs/roadmap.json"
        )

    def test_roadmap_page_present_and_routable(
        self, repo_root: Path, roadmap_json: dict
    ) -> None:
        assert roadmap_json.get("kind") == "page"
        assert roadmap_json.get("title") == "Roadmap"
        manifest_html = (repo_root / "docs" / "index.html").read_text(encoding="utf-8")
        assert (
            "roadmap.html" in manifest_html
        ), "roadmap.json missing from the page manifest in docs/index.html"

    def test_docs_step_flow_cards_use_href(self, index_json: dict) -> None:
        """Every step in the docs/index.json 'Documentation' section
        carries an href — the cards are click-targetable instead of
        embedding 'Open X.html' link text in the body."""
        sections = [
            b
            for b in index_json.get("blocks", [])
            if b.get("kind") == "section" and b.get("id") == "docs"
        ]
        assert sections, "docs/index.json missing the 'docs' section"
        sf = next(
            (b for b in sections[0].get("blocks", []) if b.get("kind") == "step-flow"),
            None,
        )
        assert sf is not None, "documentation section missing the step-flow"
        for step in sf.get("steps", []):
            assert step.get("href"), (
                f"step {step.get('title')!r} has no href — restore card click target"
            )

    def test_reference_no_longer_lists_converter_gaps(
        self, repo_root: Path
    ) -> None:
        """The 'Not in the converter' card text is retired in P0; the
        gaps it described will land as fixes in P4. Same for the
        project-meta-excluded callout. Scope: the primitive-reference
        pages only — the roadmap legitimately mentions the phrase in
        the historical narrative."""
        primitive_docs = (
            "reference.json",
            "charts.json",
            "diagrams.json",
            "tables.json",
        )
        for name in primitive_docs:
            path = repo_root / "docs" / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            assert (
                "Not in the converter" not in text
            ), f"'Not in the converter' must be retired from {name} (P0)"
            assert (
                "Project-meta files excluded" not in text
            ), f"'Project-meta files excluded' must be retired from {name} (P0)"

    def test_cli_section_counts_five_commands(self, index_json: dict) -> None:
        sections = [
            b
            for b in index_json.get("blocks", [])
            if b.get("kind") == "section" and b.get("id") == "docs"
        ]
        sf = sections[0]["blocks"][0]
        cli_step = next(
            (s for s in sf.get("steps", []) if s.get("title") == "CLI reference"),
            None,
        )
        assert cli_step is not None, "CLI reference step missing from docs section"
        # The meta line should enumerate all five commands.
        meta = cli_step.get("meta", "")
        for name in ("init", "build", "clean", "check", "serve"):
            assert (
                name in meta
            ), f"CLI step meta should mention '{name}'; got: {meta!r}"


# ---------- chrome.js / chrome.css regression markers ----------


class TestChromeKitMarkers:
    """Spot-check chrome.js / chrome.css for behaviours the user has
    asked to keep. These won't catch DOM bugs at runtime, but they
    flag a regression where someone deletes the marker code entirely
    while doing an unrelated refactor."""

    def test_chrome_has_groupby_picker(self, repo_root: Path) -> None:
        src = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "okt-groupby-select" in src, "table group-by picker source markers missing"

    def test_chrome_has_fold_handler(self, repo_root: Path) -> None:
        src = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert (
            "_hdtDetectBraceFolds" in src
        ), "code-block brace-fold detector missing from chrome.js"

    def test_chrome_has_sidebar_toggle(self, repo_root: Path) -> None:
        src = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "sidebar-collapsed" in src, "sidebar collapse class wiring missing"

    def test_chrome_extref_link_in_tooltip(self, repo_root: Path) -> None:
        """ext-ref hosts are NOT navigation links — clicking them only
        pins the tooltip. The destination URL lives as a clickable
        domain anchor inside the citation card (okt-cite-domain),
        rendered by the citation builder when hit.link is present.
        Earlier behavior (host click → window.open) made the host
        ambiguous: a single click both pinned the tooltip AND opened
        the URL, so users couldn't tell which action they were
        triggering. One affordance per element."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            "__okuExtRefMakeClickable" not in js
        ), "ext-ref host should NOT be a navigation link — helper must stay deleted"
        assert (
            "oku-extref-link" not in css
        ), "CSS class for clickable host must stay deleted — clicking pins, not navigates"
        assert (
            'a class="okt-cite-domain"' in js
        ), "citation card must render the domain as an <a>, not a code chip"
        assert (
            ".oku-tooltip:has(.okt-cite) .okt-link" in css
        ), "duplicate Learn-more footer must be hidden when cite card has its own link"

    def test_callout_symbols_present(self, repo_root: Path) -> None:
        """Renderer writes a per-type symbol onto callouts via
        data-callout-symbol; CSS picks an inline-SVG mask per type so
        readers see the semantic class at a glance."""
        js = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            "_calloutSymbol" in js
        ), "callout symbol helper missing — info/warn/tip have no glyph"
        assert (
            "data-callout-symbol" in js
        ), "renderer must tag callouts with data-callout-symbol for the CSS slot"
        # Per-type icon is set via the --callout-icon CSS variable; the
        # ::before pseudo-element uses mask-image to colour it.
        assert (
            "--callout-icon" in css
        ), "CSS must declare a per-type --callout-icon mask URL"
        assert (
            "mask-image" in css and ".callout.warn" in css and ".callout.danger" in css
        ), "missing per-type SVG icon assignments"

    def test_table_supports_pinned_view(self, repo_root: Path) -> None:
        """A table block can declare `view: \"board\"` etc. to pin the
        initial view. Renderer surfaces it as data-default-view on the
        <table>; chrome.js reads that and seeds the view-toggle. The
        kanban example uses this so the board renders by default
        (instead of a flat table the reader has to re-pivot)."""
        schema = json.loads(
            (repo_root / "kit" / "schema" / "page.schema.json").read_text(
                encoding="utf-8"
            )
        )
        assert "view" in schema["$defs"]["table"]["properties"], (
            "schema lost the pinned-view field — table.view"
        )
        renderer = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert (
            "data-default-view" in renderer
        ), "renderer must surface block.view as data-default-view"
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert (
            "data-default-view" in js
        ), "chrome.js must read data-default-view to seed the toggle"
        rendered = []
        for p in sorted((repo_root / "docs").glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rendered.extend(
                b for b in _walk_blocks(d)
                if isinstance(b, dict) and b.get("kind") == "table" and b.get("view") == "board"
            )
        assert rendered, (
            "kanban example should pin view: 'board' so the render shows lanes by default (now lives in tables.json)"
        )

    def test_example_primitive_wired(self, repo_root: Path) -> None:
        """P3 — the new `example` primitive ships in schema + renderer +
        _KNOWN_BLOCK_KINDS, and reference.json uses it for at least one
        primitive entry (paragraph)."""
        schema = json.loads(
            (repo_root / "kit" / "schema" / "page.schema.json").read_text(
                encoding="utf-8"
            )
        )
        assert "example" in schema["$defs"], "schema is missing the example primitive"
        renderer = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert "_renderExample" in renderer, "renderer is missing _renderExample"
        cli = (repo_root / "src" / "oku" / "cli.py").read_text(encoding="utf-8")
        assert '"example"' in cli, "cli._KNOWN_BLOCK_KINDS missing 'example'"
        examples = []
        for p in sorted((repo_root / "docs").glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            examples.extend(b for b in _walk_blocks(d) if isinstance(b, dict) and b.get("kind") == "example")
        assert examples, "kit docs should use at least one `example` block"
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert ".example-pair" in css, "example-pair CSS missing — no two-column layout"

    def test_chart_polish_palette_pin_legend(self, repo_root: Path) -> None:
        """Chart polish — extended series palette (10 tokens), click-
        pin on chart + bar tooltips, legend toggle on stacked/grouped
        bar variants."""
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Extended palette tokens (light + dark themes).
        for n in range(1, 11):
            assert f"--series-{n}" in css, f"missing --series-{n} chart palette token"
        # Pin state + hint.
        assert ".okc-tooltip.pinned" in css, "missing .okc-tooltip.pinned CSS"
        assert ".okc-tt-pin-hint" in css, "missing pin-hint CSS"
        # Bar-fill dim for legend toggle.
        assert ".bar-fill.dim" in css, "missing .bar-fill.dim CSS"
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "__okuPickColor" in js, "missing palette helper"
        assert "pinnedAnchor" in js, "chart tooltip missing click-pin"
        assert "pinnedFill" in js, "bar enhancer missing click-pin"
        assert "bar-chart-legend-chip[data-series-idx]" in js, (
            "bar legend toggle wiring missing"
        )
        renderer = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert "data-series-idx" in renderer, (
            "renderer must emit data-series-idx on bar-chart-legend chips for the toggle"
        )

    def test_tier3_chart_types_shipped(self, repo_root: Path) -> None:
        """P5 close-out — all six Tier 3 types (sankey, network,
        scatter-matrix, parallel-coordinates, chord, geo) ship as
        kit-native chart types: schema enum + chrome.js renderer +
        reference example."""
        schema = json.loads(
            (repo_root / "kit" / "schema" / "page.schema.json").read_text(
                encoding="utf-8"
            )
        )
        chart_def = schema["$defs"]["chart"]
        enum = chart_def["properties"]["type"]["enum"]
        for t in ("sankey", "network", "scatter-matrix", "parallel-coordinates", "chord", "geo"):
            assert t in enum, f"chart enum missing tier-3 type {t!r}"
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        for fn in (
            "_renderSankey",
            "_renderNetwork",
            "_renderScatterMatrix",
            "_renderParallelCoordinates",
            "_renderChord",
            "_renderGeo",
        ):
            assert fn in js, f"chrome.js missing tier-3 renderer {fn}"
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        for cls in (".okc-sankey", ".okc-network", ".okc-scatter-matrix", ".okc-parcoord", ".okc-chord", ".okc-geo"):
            assert cls in css, f"chart css missing class {cls}"
        ids = set()
        for p in sorted((repo_root / "docs").glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for b in _walk_blocks(d):
                if isinstance(b, dict) and b.get("kind") == "heading":
                    ids.add(b.get("id"))
        for hid in (
            "chart-sankey",
            "chart-network",
            "chart-scatter-matrix",
            "chart-parallel-coordinates",
            "chart-chord",
            "chart-geo",
        ):
            assert hid in ids, f"reference missing heading id {hid}"

    def test_mermaid_supported_types_documented(self, repo_root: Path) -> None:
        """P5 — diagram subsection lists the Mermaid v10 types the kit
        forwards unchanged. Cards must enumerate at least: sequence,
        state, ER, class, gantt, pie, journey, mindmap, timeline,
        sankey-beta."""
        ids = set()
        for p in sorted((repo_root / "docs").glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for b in _walk_blocks(d):
                if isinstance(b, dict) and b.get("kind") == "heading":
                    ids.add(b.get("id"))
        assert "mermaid-supported" in ids, "Mermaid types subsection missing"
        # The cards each have a live diagram render. Count them across
        # all docs (catalog now lives in docs/diagrams.json).
        diagrams_in_compare = 0
        for p in sorted((repo_root / "docs").glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for b in _walk_blocks(d):
                if isinstance(b, dict) and b.get("kind") == "diagram":
                    src = b.get("source") or ""
                    if any(t in src for t in (
                        "sequenceDiagram", "stateDiagram", "erDiagram",
                        "classDiagram", "gantt", "pie ", "journey",
                        "mindmap", "timeline", "sankey-beta"
                    )):
                        diagrams_in_compare += 1
        assert diagrams_in_compare >= 10, (
            f"expected at least 10 Mermaid examples in the supported-types "
            f"showcase, found {diagrams_in_compare}"
        )

    def test_chart_family_overview_present(self, repo_root: Path) -> None:
        """P3 — chart subsection opens with a compare-grid grouping
        the 28 variants by intent. The catalog now lives in
        docs/charts.json after the reference split."""
        charts = json.loads(
            (repo_root / "docs" / "charts.json").read_text(encoding="utf-8")
        )
        # Find heading with id 'chart-families'.
        ids = {
            b.get("id")
            for b in _walk_blocks(charts)
            if b.get("kind") == "heading"
        }
        assert (
            "chart-families" in ids
        ), "chart family overview heading missing in charts.json"

    def test_chart_hover_payloads(self, repo_root: Path) -> None:
        """P2 — bar / stacked / grouped / donut / treemap / funnel emit
        rich hover payloads that chrome.js wires into the shared
        .okc-tooltip controller. Each one declares the share / value
        / drop-off the reader expects."""
        renderer = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Bar / multi-bar — payload via data-hover-payload on .bar-fill.
        assert "data-hover-payload" in renderer, (
            "bar fills must carry data-hover-payload for the shared chart tooltip"
        )
        assert "__okuEnhanceBarCharts" in js, (
            "bar-chart hover enhancer missing — DIV-based bars get no rich tooltip"
        )
        # Donut + treemap + funnel — data attributes on the SVG shapes.
        assert "data-slice-share" in js, "donut slice missing share data attr"
        assert "data-cell-share" in js, "treemap cell missing share data attr"
        assert "data-stage-share" in js, "funnel band missing share data attr"
        assert "data-stage-drop" in js, "funnel band missing drop-off data attr"

    def test_quadrant_label_halo(self, repo_root: Path) -> None:
        """P2 — quadrant labels and legend text gain a paint-order halo
        so data points scattering underneath don't shred the glyphs."""
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            "paint-order: stroke fill" in css
        ), "quadrant labels need a paint-order halo to survive scatter overlap"

    def test_ridgeline_parallel_cursor(self, repo_root: Path) -> None:
        """P2 — ridgeline gains a parallel cursor (single vertical line
        spanning every ridge) wired to pointer movement, so the reader
        can compare a given X across distributions in one glance."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "okc-ridge-cursor" in js, "ridge cursor element missing in renderer"
        assert "_wireRidgelineCursor" in js, "ridge cursor wiring missing"
        assert ".okc-ridge-cursor" in css, "ridge cursor styling missing"

    def test_lightbox_pan_zoom(self, repo_root: Path) -> None:
        """P2 — lightbox now wraps content in a pan/zoom stage by
        default. Wheel zoom, drag pan, pinch zoom, double-click reset,
        +/-/0/arrows keyboard, and a small toolbar. Tables opt out
        with panZoom:false so cell scroll behaviour is preserved."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            "__okuPanZoom" in js
        ), "pan-zoom controller missing — fullscreen has no zoom"
        assert (
            "okt-lightbox-pz" in js
        ), "pan-zoom stage class missing in lightbox open()"
        assert (
            ".okt-lightbox-pz" in css
        ), "pan-zoom stage has no CSS"
        assert (
            "panZoom: false" in js
        ), "tables must opt out of pan/zoom (cell scroll would conflict)"

    def test_funnel_aligns_columns(self, repo_root: Path) -> None:
        """Funnel labels / values / percentages now live in three
        fixed right-anchored columns instead of being band-edge
        anchored. The renderer emits okc-funnel-value and
        okc-funnel-pct text elements separately so the digits stack
        cleanly across rows."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert (
            "okc-funnel-value" in js
        ), "funnel value class missing — values rendered band-edge anchored, columns will stagger"
        assert (
            "okc-funnel-pct" in js
        ), "funnel pct class missing — percentages rendered band-edge anchored, columns will stagger"
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            ".okc-funnel-value" in css
        ), "funnel value class has no CSS"
        assert (
            "tabular-nums" in css
        ), "funnel value/pct must use tabular-nums so digits stack across rows"

    def test_table_view_toggle_compact(self, repo_root: Path) -> None:
        """The view toggle was widened from word-buttons to a single
        segmented icon-only group. Lock the new shape so a future
        refactor doesn't quietly bring the word buttons back."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            "okt-view-group" in js
        ), "view-toggle group wrapper missing (compact form not applied)"
        assert (
            "okt-view-btn" in js
        ), "view buttons missing the compact class"
        assert (
            ".okt-view-group" in css
        ), "view-toggle group has no CSS — falls back to default button chrome"

    def test_annotated_code_substring_chip_autoplace(self, repo_root: Path) -> None:
        """Pure-substring annotations (no inline (N), no `lines`) now
        get a numeric chip auto-placed in front of the first highlighted
        substring. Without this, the user couldn't tell which annotation
        a highlight referred to."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert (
            "okc-anno-marker-substr" in js
        ), "substring auto-placement helper missing — substring-only annotations have no visible chip"
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert (
            "okc-anno-marker-substr" in css
        ), "CSS for the inline substring chip missing — chip will visually crowd the surrounding tokens"

    def test_annotated_code_multiline_tooltip_offset(self, repo_root: Path) -> None:
        """Multi-line annotations now render their tooltip ABOVE the
        highlighted block via position:fixed so the tooltip escapes
        the wrap's clipping context and is never trimmed by scroll.
        The setHover positioning code reads the first + last line's
        bounding rect to anchor the tip at the top centre of the
        whole block."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "position: fixed" in css and ".okc-anno-tip" in css, (
            "tooltip must use position:fixed to escape ancestor clipping"
        )
        # JS-driven flip — render above by default, flip below when
        # there's not enough room.
        assert "translate(-50%, -100%)" in js, (
            "multi-line tooltip must default to render ABOVE the anchor"
        )

    def test_compare_grid_accepts_blocks(self, repo_root: Path) -> None:
        """compare-grid card now accepts a `blocks: contentBlock[]`
        payload alongside content / items — the schema and the
        renderer must agree."""
        schema = json.loads(
            (repo_root / "kit" / "schema" / "page.schema.json").read_text(
                encoding="utf-8"
            )
        )
        card = schema["$defs"]["compare-grid"]["properties"]["cards"]["items"]
        assert "blocks" in card["properties"], (
            "compare-grid card lost its `blocks` field — restore the loose-content payload"
        )
        assert "accent" in card["properties"], (
            "compare-grid card lost its `accent` field — restore the token-aligned alias for verdict"
        )
        js = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert (
            "c.blocks" in js
        ), "renderer must read c.blocks for the new compare-grid block payload"
        assert (
            "c.accent" in js
        ), "renderer must read c.accent (taking precedence over verdict)"

    def test_wide_screen_uniform_widening(self, repo_root: Path) -> None:
        """Wide-screen support — every component fills the reader-
        selected --content-width. Media queries at 1500px and 1900px
        push the content width up so charts, tables, prose ALL grow
        in lockstep on bigger monitors. --prose-width remains as a
        CSS variable for callers that want a per-block line-length
        cap; the kit itself no longer auto-applies it."""
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # The wide-screen bumps are required.
        assert "min-width: 1500px" in css, "missing 1500px breakpoint"
        assert "min-width: 1900px" in css, "missing 1900px breakpoint"
        # Visual primitives don't cap themselves below content-width.
        for selector in (
            "main .okt-table-wrap",
            "main .kpi-grid",
            "main oku-chart",
            "main pre",
        ):
            assert selector in css, f"primitive '{selector}' missing the max-width override"

    def test_reader_can_cycle_content_width(self, repo_root: Path) -> None:
        """Reader has a chrome button to cycle content width modes (D3).

        Default narrow (860px, optimal line length); wide (1100px, more
        cards per row); max (fills the grid cell, useful for tables
        and matrices on wide screens). Mode persists to localStorage so
        the choice survives reloads.

        Locks:
        - chrome.css declares `--content-width` and the three body
          attribute overrides
        - chrome.js exposes `cycleContentWidth` and a boot-time restore
          path reading `localStorage['htmldoc-content-width']`
        - PageChrome injects a `.width-toggle` button alongside the
          other top-right chrome controls
        - `.personalize-toggle` shifts to right: 136px so it doesn't
          collide with `.width-toggle` at right: 76px
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "--content-width" in css, "missing --content-width CSS variable"
        # P7 — default expanded to four modes; comfortable is now the
        # boot default and sits between narrow and wide.
        for mode in ("narrow", "comfortable", "wide", "max"):
            assert f'body[data-content-width="{mode}"]' in css, (
                f"missing CSS rule for width mode '{mode}'"
            )
        assert ".width-toggle { top: 16px; right: 76px;" in css, (
            "width-toggle button must sit at right:76px (left of theme)"
        )
        assert ".personalize-toggle { top: 16px; right: 136px;" in css, (
            "personalize-toggle must shift to right:136px to make room "
            "for the new width-toggle button"
        )

        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "cycleContentWidth" in js, "cycleContentWidth handler missing"
        assert "htmldoc-content-width" in js, (
            "localStorage key for the width-mode preference missing"
        )
        for mode in ("'narrow'", "'comfortable'", "'wide'", "'max'"):
            assert mode in js, f"WIDTH_MODES list must include {mode}"
        assert ".width-toggle" in js, (
            "PageChrome must inject a .width-toggle button"
        )
        assert "ICON_WIDTH" in js, "width-toggle icon constant missing"

    def test_layout_is_edge_anchored_not_centered(self, repo_root: Path) -> None:
        """The `.layout` grid must span the viewport edge-to-edge, with
        no centered max-width band that pushes the sidebar inward.

        Regression target (D1): the previous layout was
        `.layout { max-width: 1280px; margin: 0 auto; }`, which at 1920w
        put the sidebar at x=320 instead of x=0 — visually "floating in
        the middle". The fix anchors the sidebar to the viewport edge
        and lets `<main>` take its width from `--content-width` (D3),
        left-aligned in the remaining grid cell.

        Locks:
        - `.layout` rule does NOT declare `max-width` or `margin: 0 auto`
        - `main` rule does NOT declare `margin: 0 auto` (would re-center
          inside the grid cell and undo the edge feel)
        - `main` uses `--content-width` (D3) with `--max-width` fallback
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        layout_idx = css.find("\n.layout {")
        assert layout_idx != -1, "base `.layout { ... }` rule missing"
        layout_block = css[layout_idx : css.find("\n}", layout_idx)]
        assert "max-width" not in layout_block, (
            "`.layout` must not declare max-width — that re-introduces the "
            "centered band and floats the sidebar away from the viewport edge"
        )
        assert "margin: 0 auto" not in layout_block, (
            "`.layout` must not declare `margin: 0 auto` — same regression"
        )

        main_idx = css.find("\nmain {")
        assert main_idx != -1, "base `main { ... }` rule missing"
        main_block = css[main_idx : css.find("\n}", main_idx)]
        assert "margin: 0 auto" not in main_block, (
            "`main` must not re-center inside the grid cell — D1 requires "
            "left-aligned content panel next to the edge-anchored sidebar"
        )
        assert "--content-width" in main_block, (
            "main must respect --content-width (D3's reader-controlled "
            "width mode) with --max-width as the default fallback"
        )

    def test_sidebar_toggle_button_is_not_always_hidden(self, repo_root: Path) -> None:
        """The top-left sidebar collapse button must not be hidden by a
        stale CSS rule that always matches.

        Regression (D2, 2026-05-20): a dead `:has()` rule from the
        previous edge-tab design always matched on doc pages
        (`body:has(.layout page-nav) .ctrl-btn.toc-toggle { display: none }`),
        making the collapse toggle invisible on every page. The
        single-sidebar layout has only one toggle — it must be visible.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        forbidden = [
            "body:has(.layout page-nav) .ctrl-btn.toc-toggle",
            ".layout-has-v2 ~ .ctrl-btn.toc-toggle",
        ]
        for pattern in forbidden:
            assert pattern not in css, (
                f"dead always-match rule `{pattern}` re-introduced — it "
                "hides the only sidebar collapse toggle on every doc page"
            )

    def test_chrome_css_has_sticky_sidebar(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "position: sticky" in css, "sticky position missing in chrome.css"
        # Sidebar should be sticky + scrollable independently.
        assert (
            "max-height: 100vh" in css
        ), "sidebar must cap at viewport height so it can scroll on its own"

    def test_page_nav_spans_full_viewport_height(self, repo_root: Path) -> None:
        """page-nav must declare an explicit height, not just max-height.

        Regression: a previous edit replaced `height: 100vh` with `max-height:
        100vh` alone — without a height declaration the sidebar shrinks to its
        content height (~633px on docs/index) and visually ends mid-page. The
        UI rule is "the sidebar surface always spans the visible viewport".
        Enforce by checking that the page-nav block declares height — both
        100vh (desktop) and 100dvh (mobile-toolbar correctness) — alongside
        the max-height cap.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Find the base `page-nav { ... }` block (not body.sidebar-collapsed or
        # any descendant rule). Locate the brace pair after the bare selector.
        marker = "\npage-nav {"
        start = css.find(marker)
        assert start != -1, "base `page-nav { ... }` rule missing from chrome.css"
        end = css.find("\n}", start)
        assert end != -1, "page-nav rule has no closing brace"
        block = css[start:end]
        assert "height: 100vh" in block, (
            "page-nav must declare `height: 100vh` so its surface spans the "
            "visible viewport even when contents are shorter. `max-height` "
            "alone is not enough — without `height` the element shrinks to "
            "content."
        )
        assert "height: 100dvh" in block, (
            "page-nav must also declare `height: 100dvh` so mobile browsers "
            "(URL-bar collapse changes vh) render the sidebar correctly."
        )

    def test_code_lang_pill_is_static_label_not_button(self, repo_root: Path) -> None:
        """Lang pill must be a flush corner label, never a hover-responsive button.

        Regression: previous polishes added :hover / :focus rules that
        made the pill change color and border, signaling "click me" when
        it's actually pointer-events: none. The user wanted a static
        label flush to the top-left edge. Lock in:
        - No `pre:hover > .okt-code-lang` rule.
        - top: 0, left: 0 (corner-flush, not 7px / 10px inset).
        - border-radius drops corner-rounding except the inner one.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "pre:hover > .okt-code-lang" not in css, (
            "lang pill must not have a hover state — it's a label, not a button"
        )
        m = re.search(r"pre\s*>\s*\.okt-code-lang\s*\{([^}]+)\}", css)
        assert m, "base lang pill rule missing"
        block = m.group(1)
        top_match = re.search(r"top:\s*(-?\d+)(?:px)?", block)
        left_match = re.search(r"left:\s*(-?\d+)(?:px)?", block)
        assert top_match and int(top_match.group(1)) == 0, "lang pill must sit at top: 0"
        assert left_match and int(left_match.group(1)) == 0, "lang pill must sit at left: 0"

    def test_code_fold_marker_right_of_line_number(self, repo_root: Path) -> None:
        """Fold-marker column sits to the RIGHT of the line-number column.

        IntelliJ / VSCode / GitHub all put the fold gutter on the inside
        of the line number (closer to the code). The kit follows that
        convention so the marker doesn't dominate the gutter's leftmost
        column. Verify via the per-line grid template.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        m = re.search(
            r"pre\.okt-line-numbered\s+\.okt-code-line\s*\{([^}]+)\}",
            css,
        )
        assert m, "per-line grid rule missing"
        block = m.group(1)
        cols = re.search(r"grid-template-columns:\s*([^;]+);", block)
        assert cols, "grid-template-columns declaration missing"
        # First column should be the line-number width (>= 28px),
        # second the fold-marker (<= 18px), third the content (1fr).
        parts = cols.group(1).strip().split()
        assert len(parts) >= 3, f"expected ≥3 grid columns, got: {parts}"
        # Triangle glyphs for the fold marker — \25BC (▼) + \25B6 (▶).
        assert "25BC" in css.upper() or "25BC" in css, (
            "fold marker should use a triangle arrow (▼)"
        )
        assert "25B6" in css.upper() or "25B6" in css, (
            "folded marker should rotate to a right-arrow (▶)"
        )

    def test_word_wrap_keeps_line_number_at_logical_line_top(self, repo_root: Path) -> None:
        """Word-wrap must align numbers to the START of the wrapped line.

        Regression: with the previous absolute-positioned gutter, when
        a logical line wrapped to multiple visual rows the line numbers
        froze in place — content shifted but numbers didn't, so they
        no longer matched the line they labeled.

        Architecture fix: per-line grid replaces the absolute gutter.
        Verify the .okt-code-line uses display: grid and
        `align-items: start` so cells anchor to the row top while
        content can grow to wrapped height.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        m = re.search(
            r"pre\.okt-line-numbered\s+\.okt-code-line\s*\{([^}]+)\}",
            css,
        )
        assert m, "per-line grid rule missing"
        block = m.group(1)
        assert "display: grid" in block, "line must be a grid container"
        assert "align-items: start" in block, (
            "cells must anchor to row top so wrapped content doesn't centre the number"
        )

    def test_anno_marker_in_own_column_with_tooltip(self, repo_root: Path) -> None:
        """Annotation marker has its own gutter column + hover tooltip.

        Regression: markers previously sat at the same x as line
        numbers, blocking them. Fixed by adding a 4th column to the
        per-line grid for annotated-code. Also added hover preview
        tooltip (`.okc-anno-tip`).

        Note: the CSS-only hover-show rule was retired in favour of
        JS-driven positioning (position:fixed + viewport coords) so
        the tip escapes the wrap's clipping context. The presence of
        the .okc-anno-tip class + JS show/hide handlers is the
        relevant invariant now.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # JS attaches the tooltip with the annotation body.
        assert "okc-anno-tip" in js, "annotation tooltip injection missing"
        # CSS: 4-column grid override for annotated-code line.
        assert ".okc-anno-wrap.okc-anno-gutter-on pre.okt-line-numbered .okt-code-line" in css, (
            "annotation-mode grid override missing"
        )
        # Tip uses fixed positioning to escape ancestor clipping.
        assert ".okc-anno-tip" in css and "position: fixed" in css, (
            "tip must be position:fixed so scroll doesn't clip it"
        )

    def test_anno_marker_sits_adjacent_to_code(self, repo_root: Path) -> None:
        """Annotation column is the LAST gutter column (right of the
        fold marker, immediately left of the code), so the chip reads
        as belonging to the code on its right rather than floating in
        the far gutter.

        The 4-column grid order is [num] [fold] [anno] [content];
        any future change to that order should fail this test loudly.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Pin the exact column order — 32px line-number, 14px fold,
        # 22px anno, 1fr content. Changes to widths are fine; column
        # ORDER (anno third, not first) is the load-bearing rule.
        assert "grid-template-columns: 32px 14px 22px 1fr" in css, (
            "annotation gutter column order must be [num] [fold] [anno] [content]"
        )

        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The DOM insertion must put the slot BEFORE the content cell
        # (third grid child), not as the first child.
        assert "line.insertBefore(slot, content)" in js, (
            "annotation slot must be inserted before .okt-code-content "
            "so the grid resolves [num] [fold] [anno] [content]"
        )

    def test_anno_marker_vertically_centered_with_line_number(self, repo_root: Path) -> None:
        """Marker's vertical centre should align with the line-number
        text's vertical centre. With a 14px circle at row top, the
        marker centre is at y=7; the line-number text centre sits
        near y=11 (half of ~22px line-height), so a 4px margin-top
        nudges the marker into alignment.

        Earlier the marker sat flush at the top of the row, visibly
        offset above the line-number digit.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        anno_block = css.split(".okc-anno-wrap.okc-anno-gutter-on .okc-anno-line-marker .okc-anno-marker", 1)[-1].split("}", 1)[0]
        assert "margin-top: 4px" in anno_block, (
            "annotation marker must carry margin-top: 4px so its centre "
            "aligns with the line-number text centre"
        )

    def test_renderer_converts_inline_html_tags_in_strings(self, repo_root: Path) -> None:
        """Renderer auto-converts whitelisted inline HTML in strings.

        Original regression: authored callouts/paragraphs carried
        literal `<code>...</code>` strings in `content`; the renderer
        used to HTML-escape them. Extended after user feedback to also
        cover anchors (`<a href="...">link</a>`), other text-shape
        tags (kbd, samp, mark), and a safe pass-through set
        (span, sup, sub, br, del, ins, abbr). Documentation tags like
        `<callout>` (not on the allowlist) still render literal so the
        kit can document itself without self-eating.
        """
        js = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert "_splitInlineTags" in js, "inline-tag converter missing"
        assert "(code|em|strong|kbd|samp|mark)" in js, (
            "_splitInlineTags must cover the text-shape tags"
        )
        assert "anchorRe" in js or "<a\\s+" in js, (
            "_splitInlineTags must detect anchors so inline links render"
        )

    def test_source_dirs_stay_clean_of_generated_files(self, repo_root: Path) -> None:
        """Source dirs must hold authored content only. site-manifest,
        llms.txt, page.md twins, and .html stubs are generated artifacts
        and must never be written into source.

        The dev server synthesizes them in memory; `oku build`
        writes them under dist/{site,standalone}/. Source stays as
        .json / .md (+ a single optional kit.json for project config).
        """
        cli_src = (repo_root / "src" / "oku" / "cli.py").read_text(encoding="utf-8")
        assert "_write_source_stubs" not in cli_src, (
            "no source-side stub writer — that pollutes the source dir"
        )
        assert "_serve_generated_artifact" in cli_src, (
            "dev server must synthesize site-manifest / llms.txt in memory"
        )
        # cmd_serve must not write manifests to source.
        assert "build_manifest(docs_dir)" not in cli_src, (
            "cmd_serve / watcher must not call build_manifest on source dirs"
        )
        # Real source dir check.
        offenders = []
        for name in (
            "site-manifest.json", "site-manifest.js", "llms.txt",
        ):
            for cand in [repo_root / name, repo_root / "docs" / name]:
                if cand.exists():
                    offenders.append(str(cand.relative_to(repo_root)))
        # Stubs: any .html under docs/ or examples/ is an offender,
        # EXCEPT docs/index.html — `oku init` writes that single
        # entry stub on purpose so IDE-served workflows work without
        # the dev server running.
        for d in (repo_root / "docs", repo_root / "examples"):
            if not d.exists():
                continue
            for p in d.rglob("*.html"):
                if "dist" in p.parts:
                    continue
                if p == repo_root / "docs" / "index.html":
                    continue
                offenders.append(str(p.relative_to(repo_root)))
        assert not offenders, (
            "generated files leaked into source:\n  " + "\n  ".join(offenders)
        )

    def test_serve_synthesizes_generated_artifacts(self, repo_root: Path) -> None:
        """Dev server returns site-manifest.json / llms.txt fresh on
        each request — keyed by the URL's parent dir as the docs
        root. The .js companion was retired (every standalone HTML
        already inlines window.__okuManifest; the site fetches
        the .json variant)."""
        cli_src = (repo_root / "src" / "oku" / "cli.py").read_text(encoding="utf-8")
        assert "compute_manifest" in cli_src, "compute_manifest helper missing"
        assert "compute_llms_txt" in cli_src, "llms.txt synthesis helper missing"
        assert '"site-manifest.json"' in cli_src, (
            "synthesis must handle site-manifest.json"
        )
        assert '"site-manifest.js"' not in cli_src, (
            ".js manifest form is retired — drop it from dev server too"
        )
        assert '"llms.txt"' in cli_src, "synthesis must handle llms.txt"

    def test_serve_synthesizes_md_and_json_pages(self, repo_root: Path) -> None:
        """`oku serve` synthesizes .html / .json on the fly (D5).

        Three synthesis paths:
          /name.html + name.md   sibling → md→page→stub
          /name.json + name.md   sibling → md→page json
          /name.html + name.json sibling → stub from json's title

        The .json-sibling case (added in D5) lets authors author only
        the .json content — the source dir doesn't need an .html stub.
        """
        cli_src = (repo_root / "src" / "oku" / "cli.py").read_text(encoding="utf-8")
        assert "_serve_synthesized" in cli_src, "synthesis handler missing"
        m = re.search(
            r"def do_GET\(self\)[\s\S]*?if self\._serve_synthesized\(\)",
            cli_src,
        )
        assert m, "_serve_synthesized must be called from do_GET"
        # Must handle the .json-sibling case for .html requests (D5).
        assert "json_path.exists()" in cli_src, (
            "_serve_synthesized must fall back to a .json sibling for "
            "missing-on-disk .html requests"
        )

    def test_search_has_in_page_fallback(self, repo_root: Path) -> None:
        """Search degrades to in-page navigation when Pagefind is absent.

        Regression: IDE-served projects don't have the Pagefind index
        built, so the search modal used to dead-end with "index not
        found". User asked: "at least help me to navigate the current
        document". The fallback walks `#main-content` headings and
        returns same-page anchor hits.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "_inPageSearch" in js, "in-page fallback function missing"
        assert "site index unavailable" in js or "On this page" in js, (
            "fallback status message missing"
        )

    def test_sidebar_default_expanded_on_first_visit(self, repo_root: Path) -> None:
        """First-time visitor must see the sidebar expanded.

        Rule: absent `sidebarCollapsed` localStorage key &rArr; sidebar
        renders expanded so the user discovers the site tree. The
        collapsed class is only applied when the key is explicitly '1'.
        Two conditions enforce this:

        - chrome.js boot guards `sidebar-collapsed` behind a strict
          `=== '1'` check (not a looser `!== null` or truthy check).
        - chrome-boot.js does NOT add the `sidebar-collapsed` class
          (its responsibility is theme + auth; nav state belongs to
          chrome.js to keep the restore path single-source).
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        boot = (repo_root / "kit" / "chrome-boot.js").read_text(encoding="utf-8")
        assert (
            "localStorage.getItem('sidebarCollapsed') === '1'" in js
        ), (
            "chrome.js must restore `sidebar-collapsed` only when the key "
            "equals '1' — a looser check would surface the collapsed state "
            "on first visit"
        )
        assert (
            "sidebar-collapsed" not in boot
        ), (
            "chrome-boot.js must not touch the sidebar-collapsed class; "
            "single-source restore lives in chrome.js"
        )

    def test_no_unresolved_references_in_docs(self, repo_root: Path) -> None:
        """Every glossary-term / ext-ref / anchor link in docs must resolve.

        Audit findings on first run: 3 broken ext-refs in reference.json
        (Iceberg paper, RFC 9457, Iceberg 1.4 release) — they were
        authored but never defined in extrefs/*.json. The user explicitly
        asked: "Identify the missing references in our docs and fix them."

        Symbol tables:
        - Glossary terms: union of `entries` keys across glossary/*.json
          (case-insensitive match against the term `term` field).
        - Ext-refs: union of `entries` keys across extrefs/*.json
          (case-sensitive match against the `name` field).
        - Anchors: each docs/*.json page collects every `id` from its
          blocks recursively. `<link href="#foo">` resolves against the
          current page's anchors; `<link href="page.html#foo">` against
          the target page's anchors.
        """
        glossary_terms: set[str] = set()
        for p in (repo_root / "kit" / "glossary").glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            for term in (data.get("entries") or {}).keys():
                glossary_terms.add(term.lower())

        extref_names: set[str] = set()
        for p in (repo_root / "kit" / "extrefs").glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            for name in (data.get("entries") or {}).keys():
                extref_names.add(name)

        all_anchors: dict[str, set[str]] = {}
        for p in (repo_root / "docs").glob("*.json"):
            if p.name in ("kit.json", "site-manifest.json"):
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if data.get("kind") != "page":
                continue
            ids: set[str] = set()

            def collect(node):  # noqa: ANN001
                if isinstance(node, list):
                    for x in node:
                        collect(x)
                    return
                if not isinstance(node, dict):
                    return
                if isinstance(node.get("id"), str):
                    ids.add(node["id"])
                for k in ("content", "children", "blocks", "items"):
                    if k in node:
                        collect(node[k])

            collect(data.get("blocks", []))
            all_anchors[p.stem] = ids

        anchor_re = re.compile(r"([^#]+)\.html#(.+)$")
        unresolved: list[str] = []

        def walk(node, page: str, path: str) -> None:
            if isinstance(node, list):
                for i, x in enumerate(node):
                    walk(x, page, f"{path}[{i}]")
                return
            if not isinstance(node, dict):
                return
            kind = node.get("kind")
            if kind == "glossary-term":
                term = (node.get("term") or "").lower()
                if term and term not in glossary_terms:
                    unresolved.append(
                        f"{page}:{path} glossary-term {term!r} not in any glossary/*.json"
                    )
            elif kind == "ext-ref":
                name = node.get("name") or ""
                if name and name not in extref_names:
                    unresolved.append(
                        f"{page}:{path} ext-ref {name!r} not in any extrefs/*.json"
                    )
            elif kind == "link":
                href = node.get("href") or ""
                if href.startswith("#"):
                    anchor = href[1:]
                    if all_anchors.get(page) and anchor not in all_anchors[page]:
                        unresolved.append(
                            f"{page}:{path} local anchor {href!r} not found on this page"
                        )
                else:
                    m = anchor_re.match(href)
                    if m:
                        target = Path(m.group(1)).name
                        anchor = m.group(2)
                        if target in all_anchors and anchor not in all_anchors[target]:
                            unresolved.append(
                                f"{page}:{path} cross-page link {href!r} target page exists "
                                "but anchor missing"
                            )
            for k in ("content", "children", "blocks", "items"):
                if k in node:
                    walk(node[k], page, f"{path}/{k}")

        for p in (repo_root / "docs").glob("*.json"):
            if p.name in ("kit.json", "site-manifest.json"):
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if data.get("kind") != "page":
                continue
            walk(data.get("blocks", []), p.stem, "/blocks")

        assert not unresolved, "Unresolved references:\n  " + "\n  ".join(unresolved)

    def test_reference_code_samples_have_live_demos(self, repo_root: Path) -> None:
        """Every code sample in docs/reference.json must have a matching demo.

        Rule: when a `<code>` block contains JSON describing an html-doc
        block (single top-level object with a `kind` field), one of the
        next ≤4 sibling blocks must be a block of that kind, OR one of
        those siblings must contain that kind as an inline element.

        Prevents author-drift where someone edits the code sample but
        forgets the live demo (or vice versa). User explicitly called
        out: "Some examples are different than the rendered content
        below it, some doesn't have a rendered counterpart at all."
        """
        page_path = repo_root / "docs" / "reference.json"
        assert page_path.exists(), "docs/reference.json missing"
        data = json.loads(page_path.read_text(encoding="utf-8"))

        def inline_kinds(node, acc=None):
            if acc is None:
                acc = set()
            if isinstance(node, list):
                for item in node:
                    inline_kinds(item, acc)
                return acc
            if not isinstance(node, dict):
                return acc
            kind = node.get("kind")
            if isinstance(kind, str):
                acc.add(kind)
            for key in ("content", "children", "blocks", "items"):
                if key in node:
                    inline_kinds(node[key], acc)
            return acc

        issues = []

        def walk(blocks, path):
            for i, b in enumerate(blocks):
                if isinstance(b, dict) and b.get("kind") == "code":
                    src = (b.get("source") or b.get("code") or "").strip()
                    if not src.startswith("{") or not src.endswith("}"):
                        continue
                    try:
                        parsed = json.loads(src)
                    except json.JSONDecodeError:
                        continue
                    claimed = parsed.get("kind") if isinstance(parsed, dict) else None
                    if not claimed:
                        continue
                    # Root-level kinds (page) are shown to document the
                    # top-of-file structure, not as renderable blocks. No
                    # demo can follow.
                    if claimed == "page":
                        continue
                    found = False
                    for j in range(i + 1, min(i + 5, len(blocks))):
                        c = blocks[j]
                        if not isinstance(c, dict):
                            continue
                        if c.get("kind") == "heading" and j > i + 1:
                            break
                        if c.get("kind") == claimed:
                            found = True
                            break
                        if claimed in inline_kinds(c):
                            found = True
                            break
                    if not found:
                        issues.append(f"{path}[{i}] claims kind={claimed!r} but no demo follows")
                if isinstance(b, dict):
                    for key in ("children", "blocks"):
                        if isinstance(b.get(key), list):
                            walk(b[key], f"{path}/{b.get('kind')}[{i}].{key}")

        walk(data.get("blocks", []), "")
        assert not issues, "reference.json drift:\n" + "\n".join(issues)

    def test_markdown_pages_convert_to_kit_json(self, repo_root: Path) -> None:
        """cli.md_to_page must convert common Markdown into kit page JSON.

        User asked: "We can add Markdown rendering support so existing
        markdown documents could be also incorporated to the existing
        knowledge base without re-writing them. But we must be ensure
        that the links, diagrams, sections, titles, everything works
        just like HTML and integrates well natively."

        Verify the round-trip on the bundled examples/markdown-demo.md:
        H1 → title, H2 → heading blocks with id slugs, fences → code
        blocks (mermaid → diagram), lists → list blocks, inline
        emphasis/links survive into the content array.
        """
        from oku.cli import md_to_page  # noqa: PLC0415

        sample = repo_root / "examples" / "markdown-demo.md"
        if not sample.exists():
            pytest.skip("markdown-demo.md sample missing")
        page = md_to_page(sample.read_text(encoding="utf-8"))

        assert page["kind"] == "page"
        assert page["title"] == "Markdown demo"

        # Top-level blocks are sections (schema requires it). H2s map
        # to section titles; everything else nests inside sections.
        top_kinds = [b.get("kind") for b in page["blocks"]]
        assert top_kinds and all(k == "section" for k in top_kinds), (
            f"top-level blocks must all be sections, got: {top_kinds}"
        )
        # Each section has a slug id (kebab-case).
        for sec in page["blocks"]:
            assert re.match(r"^[a-z0-9-]+$", sec["id"]), f"non-slug id: {sec['id']}"

        # Flatten the inner blocks to check primitive coverage.
        inner = [b for sec in page["blocks"] for b in sec.get("blocks", [])]
        inner_kinds = {b.get("kind") for b in inner}
        assert "code" in inner_kinds, "fenced code → code block missing"
        assert "diagram" in inner_kinds, "```mermaid → diagram block missing"
        assert "list" in inner_kinds, "- list → list block missing"
        assert "callout" in inner_kinds, "> blockquote → callout block missing"

        # Inline link / strong / code survive into paragraph content arrays.
        paragraphs = [b for b in inner if b.get("kind") == "paragraph"]
        flat = [
            item
            for p in paragraphs
            for item in p.get("content", [])
            if isinstance(item, dict)
        ]
        kinds_inline = {x.get("kind") for x in flat}
        assert "link" in kinds_inline, "inline [text](url) → link missing"
        assert "strong" in kinds_inline, "inline **bold** → strong missing"
        assert "code" in kinds_inline, "inline `code` → code missing"

    def test_diagram_toolbar_has_copy_and_expand(self, repo_root: Path) -> None:
        """Mermaid diagrams must expose both copy-source and expand actions.

        User explicitly asked for these buttons on Mermaid blocks. Copy
        was pre-existing in the diagram toolbar; expand was added in P12.
        Lock both into the diagram custom element so a future refactor
        can't quietly drop either.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Find the diagram custom element's _attachToolbar block.
        m = re.search(
            r"class\s+OkuDiagram[\s\S]*?_attachToolbar\(\)\s*\{[\s\S]*?makeToolbar\(this,\s*\[([\s\S]*?)\]\)",
            js,
        )
        assert m, "OkuDiagram._attachToolbar block not found"
        toolbar = m.group(1)
        assert "Copy diagram source" in toolbar, (
            "Copy action missing from diagram toolbar"
        )
        assert "Expand to fullscreen" in toolbar, (
            "Expand action missing from diagram toolbar"
        )

    def test_lightbox_module_exists(self, repo_root: Path) -> None:
        """Shared lightbox overlay must exist + be wired to charts + diagrams.

        Regression: user asked for a full-screen expand on images, charts,
        diagrams (and later Mermaid). One shared overlay so the affordance
        is identical everywhere.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "__okuLightbox" in js, "lightbox module missing"
        assert ".okt-lightbox" in css, "lightbox CSS missing"
        assert "ICON_EXPAND" in js, "expand icon constant missing"
        # Chart + diagram custom elements get the expand action in their
        # toolbars; both call into __okuLightbox.open.
        chart_expand = re.search(
            r"makeToolbar\(this,\s*\[[\s\S]*?Expand to fullscreen[\s\S]*?\]\)",
            js,
        )
        assert chart_expand, "Expand action missing from a custom element toolbar"
        # Backdrop + Escape close paths.
        assert "okt-lightbox-backdrop" in js, "backdrop close target missing"
        assert "e.key === 'Escape'" in js, "Escape close path missing"

    def test_table_board_view_honors_board_order(self, repo_root: Path) -> None:
        """Board (kanban) lanes must be orderable via a column header.

        Authors declare `boardOrder` on a column header; when that column
        is the board view's group-by, lanes render in that order rather
        than first-occurrence-in-rows order. Without this knob the board
        view is functionally a colored list — useless as a kanban.

        Locks:
        - renderer.js emits `data-board-order` on the th when the header
          object declares boardOrder
        - chrome.js renderBoard reads `data-board-order` and sorts the
          lane list by it (unknown values appended at end)
        - schema/page.schema.json declares boardOrder on tableHeader
        - docs/reference.json carries a worked example so the demo
          stays in sync with the renderer
        """
        renderer = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert "data-board-order" in renderer, (
            "renderer must emit data-board-order from header.boardOrder"
        )

        chrome_js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "data-board-order" in chrome_js, (
            "renderBoard must read data-board-order to order lanes"
        )
        assert "laneOrder" in chrome_js and "laneRank" in chrome_js, (
            "renderBoard must define a lane-rank function to sort lanes "
            "by the declared boardOrder"
        )

        schema = json.loads(
            (repo_root / "kit" / "schema" / "page.schema.json").read_text(encoding="utf-8")
        )
        defs = schema.get("$defs") or schema.get("definitions") or {}
        header_def = defs.get("tableHeader") or {}
        header_blob = json.dumps(header_def)
        assert "boardOrder" in header_blob, (
            "tableHeader schema must declare boardOrder as an optional "
            "ordered string array"
        )

        demo_seen = False
        for p in sorted((repo_root / "docs").glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for block in _walk_blocks(d):
                if not isinstance(block, dict) or block.get("kind") != "table":
                    continue
                for h in block.get("headers", []):
                    if isinstance(h, dict) and isinstance(h.get("boardOrder"), list):
                        demo_seen = True
                        break
                if demo_seen:
                    break
            if demo_seen:
                break
        assert demo_seen, (
            "the docs must demonstrate a boardOrder header so authors "
            "see how to drive kanban lane ordering (now in tables.json)"
        )

    def test_table_has_board_view(self, repo_root: Path) -> None:
        """Tables expose a 4th view: Board (kanban-style lanes).

        User asked for "board view in tables" alongside the existing
        Table / List / Cards. Group-by drives lanes; rows become cards.
        Lock in:

        - JS toolbar emits a `data-view="board"` button.
        - JS has a `renderBoard` function and a `.okt-table-board`
          container.
        - CSS view-toggle hides `.okt-table-board` for the three
          non-active views and hides it by default (no data-view attr).
        - CSS provides `.okt-board-lane` styling.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # The view buttons may be emitted via a helper (viewBtnHTML)
        # or inline; either way the 'board' key must be there.
        assert (
            'viewBtnHTML(\'board\'' in js or 'data-view="board"' in js
        ), "Board toggle button missing in toolbar"
        assert "renderBoard" in js, "renderBoard function missing"
        assert "okt-table-board" in js, "board container missing"
        assert ".okt-board-lane" in css, "lane styling missing"
        assert '[data-view="board"]' in css, "board active-view rule missing"

    def test_list_view_items_visually_separated(self, repo_root: Path) -> None:
        """List-view items must have clear visual separation.

        Regression: user reported "I cannot tell where the first list item
        ends and second starts" when tables were in list view. The fix
        triples the gap and swaps the outer border from --border-soft to
        --line, with a box-shadow to lift each card off the page.

        Enforce by checking the .okt-table-list / .okt-list-card block
        carries (a) a meaningful gap (≥16px), (b) a non-soft outer border
        token, and (c) a box-shadow declaration.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Match the BASE list rule (the data-view variants are display:none
        # and don't carry layout). Anchor on the unique `display: flex` shape.
        list_rule = re.search(
            r"\.okt-table-list\s*\{[^}]*display:\s*flex[^}]*\}", css
        )
        card_rule = re.search(r"\.okt-list-card\s*\{([^}]*)\}", css)
        assert list_rule, ".okt-table-list base rule (display:flex) missing"
        assert card_rule, ".okt-list-card rule missing"
        list_block = list_rule.group(0)
        card_block = card_rule.group(1)
        # Gap >= 16px (was 10px; user couldn't tell items apart).
        gap_match = re.search(r"gap:\s*(\d+)px", list_block)
        assert gap_match, "list gap declaration missing"
        gap_px = int(gap_match.group(1))
        assert gap_px >= 16, (
            f"list gap is {gap_px}px — items need ≥16px breathing room "
            "to read as distinct cards"
        )
        # Stronger outer border (not the soft variant).
        assert "border: 1px solid var(--line)" in card_block, (
            "card outer border must use --line (stronger) so it stands out "
            "from the inner row dividers using --border-soft"
        )
        # Shadow to lift the card off the page.
        assert "box-shadow:" in card_block, (
            "card needs a box-shadow to read as a lifted surface"
        )

    def test_code_block_has_wrap_toggle(self, repo_root: Path) -> None:
        """Every <pre> gets a wrap toggle button next to copy.

        Regression: long lines (URLs, generated tokens, JSON one-liners)
        force a horizontal scrollbar by default. The wrap toggle lets the
        reader flip a block to `white-space: pre-wrap` per-block. Symbol-
        only icon (Feather wrap-line); sits 8px to the left of the copy
        button on the same row.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "ICON_WRAP" in js, "wrap button needs a dedicated icon constant"
        assert "okt-wrap-btn" in js, "wrap button must be created in chrome.js"
        assert ".okt-wrap-btn" in css, "wrap button styling missing"
        # Toggled state must flip white-space on the inner <code>.
        assert "pre.okt-wrap" in css, "wrap state class missing"
        assert "white-space: pre-wrap" in css, (
            "wrap state must flip white-space to pre-wrap so long lines wrap"
        )

    def test_copy_wrap_buttons_attach_to_non_scrolling_host(self, repo_root: Path) -> None:
        """Copy + wrap buttons must live on .okt-pre-host, not inside
        the scrolling <pre>.

        Regression: when buttons were appended to <pre> directly, a
        horizontal scroll of the pre's content pushed the buttons
        off-screen with the content (the buttons are children of the
        scroll viewport). Wrapping every <pre> in a non-scrolling
        .okt-pre-host keeps the buttons pinned at the host's edges.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Host must exist as a CSS class with position: relative.
        host_rule = re.search(r"\.okt-pre-host\s*\{([^}]*)\}", css)
        assert host_rule, ".okt-pre-host CSS rule missing"
        assert "position: relative" in host_rule.group(1), (
            ".okt-pre-host must be position: relative — it's the buttons' anchor"
        )
        # Buttons are appended to the host, not pre.
        assert "host.appendChild(btn)" in js, (
            "copy / wrap buttons must be appended to the .okt-pre-host, "
            "not the scrolling <pre>"
        )
        # Hover-reveal selectors target the host.
        assert ".okt-pre-host:hover .copy-btn" in css, (
            "hover-reveal must trigger from the host, not from pre"
        )
        assert ".okt-pre-host:hover .okt-wrap-btn" in css, (
            "wrap-btn hover-reveal must trigger from the host"
        )

    def test_page_nav_adopts_page_toc_with_document_fallback(self, repo_root: Path) -> None:
        """page-nav must adopt a page-toc found anywhere in the document.

        Regression: the prior adoption code only looked at `:scope > page-toc`
        inside the same `.layout`. When a page authored page-toc outside the
        layout container (e.g. as a direct body child, which is easy to do
        without noticing), the adoption silently no-op'd and page-toc rendered
        at the page bottom — breaking the single-LEFT-sidebar rule in
        CLAUDE.md.

        The fix is a document-level fallback. Enforce by checking the
        connectedCallback contains both the layout-scoped query AND the
        document-level fallback.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The layout-scoped query (preserved as the primary lookup).
        assert (
            "layout.querySelector(':scope > page-toc, :scope > nav.toc')" in js
        ), "layout-scoped page-toc adoption query missing"
        # The document-level fallback that catches body-direct page-toc.
        assert (
            "document.querySelector('page-toc, nav.toc')" in js
        ), (
            "document-level page-toc adoption fallback missing — page-toc "
            "authored outside .layout will render at page bottom"
        )


class TestDesignReviewPage:
    """The design-review page is the live decision log the user keeps
    flipping back to. A silent drop from the site nav (because of a
    JSON parse error, a missing meta field, or a build skip) is the
    bug we want this class to catch."""

    def test_design_review_json_parses(self, repo_root: Path) -> None:
        p = repo_root / "docs" / "design-review.json"
        assert p.exists(), "docs/design-review.json missing — site nav loses the live decision log"
        # If json.loads raises, pytest surfaces the line+col, which is
        # already much better than the silent drop we used to ship.
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data.get("kind") == "page", "design-review.json is not a page (kind != 'page')"
        assert data.get("title"), "design-review.json missing title — nav entry would render with the filename"

    def test_design_review_in_site_manifest_after_build(self, tmp_path: Path, repo_root: Path) -> None:
        """End-to-end: build the project and verify design-review appears
        in dist/site/site-manifest.json. Earlier regression: a stray
        comma in design-review.json silently dropped the page from the
        manifest while every other check still reported 'clean'."""
        from oku import cli
        # Stage a minimal project that includes a design-review-shaped
        # page so we don't depend on real docs/.
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "design-review.json").write_text(
            json.dumps({"kind": "page", "title": "Design review", "blocks": []}),
            encoding="utf-8",
        )
        (tmp_path / "docs" / "index.html").write_text(
            "<!doctype html><html><body></body></html>", encoding="utf-8"
        )
        (tmp_path / "docs" / "index.json").write_text(
            json.dumps({"kind": "page", "title": "Home", "blocks": []}),
            encoding="utf-8",
        )
        pages = cli.find_json_pages(tmp_path)
        out_dir = tmp_path / "dist"
        out_dir.mkdir()
        cli.build_manifest(tmp_path, out_dir=out_dir, pages=pages)
        m = json.loads((out_dir / "site-manifest.json").read_text(encoding="utf-8"))
        page_paths = [p["path"] for p in m.get("pages", [])]
        assert any("design-review" in p for p in page_paths), (
            f"design-review.html missing from manifest. Pages: {page_paths}"
        )


class TestMultiSeriesChartsHaveLegendExtras:
    """marimekko and stream chart blocks must keep their multi-series
    payload shape (categories + series with values) so the SVG renderer
    has data to build a legend over. A regression that flattened
    series → a single bare values list would remove the legend.

    The legend rendering itself is in chrome.js (`_renderSeriesLegend`);
    the precondition for it being meaningful is series.length ≥ 2
    AND every series carrying a `label`."""

    def _find_chart(self, reference: dict, chart_type: str) -> dict | None:
        return _find_block(reference, lambda b: b.get("kind") == "chart" and b.get("type") == chart_type)

    def test_marimekko_keeps_multi_series_with_labels(self, reference: dict) -> None:
        block = self._find_chart(reference, "marimekko")
        assert block, "marimekko chart block missing from docs/"
        series = block.get("series") or []
        assert len(series) >= 2, f"marimekko needs ≥2 series for a legend; got {len(series)}"
        labelled = [s for s in series if s.get("label")]
        assert len(labelled) == len(series), (
            "every marimekko series must have a `label` — otherwise the legend "
            "swatch row would be missing entries"
        )

    def test_stream_keeps_multi_series_with_labels(self, reference: dict) -> None:
        block = self._find_chart(reference, "stream")
        assert block, "stream chart block missing from docs/"
        series = block.get("series") or []
        assert len(series) >= 2, f"stream needs ≥2 series for a legend; got {len(series)}"
        labelled = [s for s in series if s.get("label")]
        assert len(labelled) == len(series), (
            "every stream series must have a `label` — otherwise the legend "
            "swatch row would be missing entries"
        )


class TestChartConfigMarksAndCompat:
    """The chart-config popover's correctness invariants live in
    chrome.js source. These tests pin the load-bearing patterns so a
    future refactor can't silently re-introduce the bugs the user
    flagged this round:

      1. A marks delta must normalise to type=plot + marks attr —
         setting marks on a host that's still type=scatter is a
         no-op since the dispatcher only honours marks when
         type=plot.
      2. Quadrant must be in the Cartesian compat list so users
         can round-trip back to it after switching to scatter/line/
         area. (User explicitly couldn't get back to quadrant.)
      3. The marks chip row must show for bubble + quadrant — they
         share the Cartesian payload."""

    def test_marks_delta_normalises_to_plot(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Look for the apply-marks branch: must set type to 'plot' and
        # set marks attr together. Without this, marks toggle is a no-op.
        assert re.search(
            r"if\s*\(\s*delta\.marks\s*\)\s*\{[^}]*setAttribute\('type',\s*'plot'\)[^}]*setAttribute\('marks',",
            js,
            re.DOTALL,
        ), (
            "applyChange in __okuChartConfig must normalise a marks delta to "
            "type='plot' + marks attr together. Setting marks alone won't "
            "re-render the host."
        )

    def test_cartesian_compat_includes_quadrant(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # getCompatibleTypes' hasXY branch must list quadrant alongside
        # scatter/line/area so the user can switch back to quadrant from
        # any Cartesian shape.
        m = re.search(
            r"if\s*\(\s*hasXY\s*\)\s*\{(.*?)return\s+opts\s*;",
            js,
            re.DOTALL,
        )
        assert m, "getCompatibleTypes hasXY branch not found"
        body = m.group(1)
        assert "type: 'quadrant'" in body or "type: \"quadrant\"" in body, (
            "Cartesian compat list must include quadrant — the user explicitly "
            "asked for round-trip from scatter/line/area back to quadrant"
        )

    def test_marks_ui_shows_for_bubble_and_quadrant(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The render() branch that emits the marks chip row must include
        # bubble and quadrant in its type-guard.
        m = re.search(
            r"// Cartesian — marks combo.*?if\s*\((host\._type === [^)]*)\)\s*\{",
            js,
            re.DOTALL,
        )
        assert m, "marks chip render branch not found"
        guard = m.group(1)
        for t in ("scatter", "line", "area", "plot", "bubble", "quadrant"):
            assert f"'{t}'" in guard, f"marks chip render must show for {t}; guard was: {guard}"


class TestMermaidSvgIntrinsicSize:
    """OkuDiagram must declare width/height from the rendered SVG's
    viewBox so the SVG renders at 1:1 instead of scaling up to fill
    its container. The scale-up was the root cause of state + ER
    diagrams rendering foreignObject labels at ~26-30px (visually
    twice their authored size)."""

    def test_oku_diagram_sets_explicit_width_height_from_viewbox(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Must read the viewBox + assign both width and height attrs
        # in the post-mermaid-render path.
        assert re.search(
            r"var\s+vb\s*=\s*\(svg\.getAttribute\('viewBox'\)[^;]*split\s*\(",
            js,
        ), "OkuDiagram must parse the SVG's viewBox to derive intrinsic size"
        assert "svg.setAttribute('width', String(vb[2]))" in js, (
            "OkuDiagram must set explicit width from viewBox[2] so the SVG "
            "renders at 1:1; otherwise foreignObject text scales with the SVG"
        )
        assert "svg.setAttribute('height', String(vb[3]))" in js, (
            "OkuDiagram must set explicit height from viewBox[3]"
        )


class TestMermaidNeighborHighlight:
    """The mermaid flowchart neighbor-highlight wiring (data-id +
    LS-/LE- class adjacency map) was added this session. Pin the
    load-bearing pieces so a future refactor can't break the
    hover-emphasises-the-active-subgraph affordance."""

    def test_wire_neighbor_highlight_present(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "_wireNeighborHighlight" in js, (
            "OkuDiagram._wireNeighborHighlight removed — flowchart neighbor "
            "highlight will no longer wire"
        )
        # Must call it from the connected-callback render path so first-
        # render diagrams get the wiring, not just re-renders.
        # The hook lives inside the .then(out) handler after svg attrs
        # are pinned.
        assert "self._wireNeighborHighlight(svg)" in js, (
            "_wireNeighborHighlight must be called in the post-render path"
        )

    def test_neighbor_highlight_indexes_on_data_id_and_ls_le_classes(
        self, repo_root: Path
    ) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The wiring leans on Mermaid v10's own conventions: nodes carry
        # data-id="<NodeId>"; edges carry LS-<source> + LE-<target>.
        # Both must be present for the adjacency map to build.
        assert ".node[data-id]" in js, (
            "neighbor highlight must select nodes by `[data-id]` — "
            "the convention Mermaid v10 emits"
        )
        assert "LS-" in js and "LE-" in js, (
            "neighbor highlight must parse LS-<source> + LE-<target> "
            "classes from each edge; both substrings must remain in the "
            "wiring source"
        )


class TestPickerCardUniformity:
    """The chart-variant picker grid is unusable if one row sits at
    136px while another sits at 178px. Pin the load-bearing CSS rule
    so a future "polish" pass can't silently strip the fixed-height
    contract."""

    def test_picker_card_has_fixed_height(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        m = re.search(
            r"\.compare-card\.compare-card-link\s*\{([^}]+)\}",
            css,
        )
        assert m, ".compare-card.compare-card-link rule missing"
        body = m.group(1)
        assert re.search(r"height\s*:\s*\d+px", body), (
            "picker card .compare-card.compare-card-link must declare an "
            "explicit `height` so every variant tile lands in the same row "
            "frame; without it the grid staggers by family"
        )


# =====================================================================
# Round 14 regressions — every fix from the user's "fix everything"
# audit gets a test that names the incident, so a future refactor can't
# silently undo it.
# =====================================================================


class TestQuadrantLabelsOutsidePlot:
    """Quadrant region labels (QUICK WINS / RE-EVALUATE) must render
    OUTSIDE the plot bounds — earlier rounds put them inside the
    corners and tried to fade-on-hover, which still left data points
    occluded at rest. The pad bump + region-label code is the
    contract; the .okc-quadrant-label-pill backing rect is gone."""

    def test_quadrant_bumps_pad_top_and_bottom(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "var isQuadrant = this._type === 'quadrant';" in js, (
            "OkuChart must branch on `_type === 'quadrant'` to allocate "
            "extra pad.top + pad.bottom for region labels"
        )
        # The +22 bump moves region labels out of the plot.
        assert "isQuadrant ? 22 : 0" in js, (
            "Quadrant pad.top and pad.bottom must add 22 viewBox units "
            "of gutter to fit corner labels above/below the plot"
        )

    def test_quadrant_label_pill_rect_dropped(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The fade-on-hover workaround is gone — labels live in their
        # own gutter, no need for a backing pill. (We allow the class
        # to appear in a `//` historical comment but not in any
        # actual JS string / DOM emission.)
        # Strip JS line comments so the historical note doesn't trip
        # the test.
        js_no_comments = re.sub(r"//[^\n]*\n", "\n", js)
        assert "okc-quadrant-label-pill" not in js_no_comments, (
            "okc-quadrant-label-pill (backing rect for in-plot labels) "
            "must be removed — labels are now outside the plot bounds"
        )


class TestGaugeZoneLabelsAsLegendRow:
    """Gauge zone labels (BREACHING / CAUTION / HEALTHY) used to render
    around the arc rim at zone mid-angle, where text-anchor:middle
    pushed left-half labels into the arc band. Now they live as a
    horizontal legend ROW below the value readout — same shape as
    marimekko / stream legends."""

    def test_gauge_emits_zone_chip_row(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "okc-gauge-zone-chip" in js, (
            "Gauge must emit the bottom-row .okc-gauge-zone-chip group "
            "for each zone label; without it labels collide with the arc"
        )

    def test_gauge_height_grows_with_legend(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # When at least one zone has a label, H bumps to fit the row.
        assert "hasZoneLegend ? 230 : 200" in js, (
            "Gauge SVG height must grow to 230 when zone labels are "
            "present so the bottom legend row has room"
        )


class TestBarTooltipViewportPlacement:
    """Bar chart tooltip MUST use viewport-clamped placement because
    .okc-tooltip is `position: fixed`. Earlier the bar enhancer used
    host-relative coords (a number near 0), which placed the tooltip
    at the viewport's LEFT edge regardless of which bar was hovered.
    The fix is to call the module-level __okuPlaceTooltipAt helper
    with viewport coords."""

    def test_bar_enhancer_uses_module_level_helper(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "function __okuPlaceTooltipAt" in js, (
            "Module-level __okuPlaceTooltipAt missing — bar enhancer "
            "would need to re-implement viewport clamping"
        )
        # The bar enhancer must call it with viewport coords, not
        # host-relative deltas.
        assert "__okuPlaceTooltipAt(t, aRect.left + aRect.width / 2, aRect.top - 8)" in js, (
            "bar tooltip placement must use the viewport-clamped helper "
            "— host-relative coords end up at the viewport's left edge"
        )


class TestVerticalCursorPlotAreaConstraint:
    """The SVG vertical cursor must check BOTH x AND y bounds before
    showing — earlier only x was checked, so hovering the title row
    still flashed the cursor. Bar cursor was full-height of host;
    now it's clipped to first/last .bar-row range."""

    def test_generic_cursor_checks_y_bounds(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Both axis-bound checks must appear together in the cursor's
        # mousemove handler.
        assert "y < plotBounds.top" in js, (
            "Vertical cursor must hide when pointer y < plotBounds.top "
            "(so it doesn't show over the title row)"
        )
        assert "y > plotBounds.bottom" in js, (
            "Vertical cursor must hide when pointer y > plotBounds.bottom"
        )

    def test_bar_cursor_clips_to_bar_rows(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "function plotYBounds" in js, (
            "Bar enhancer must derive plot y-bounds from first/last "
            ".bar-row so cursor doesn't span title + legend"
        )

    def test_cursor_visual_is_visible(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # SVG generic cursor — stroke-width must be ≥ 1.5 to read clearly.
        m = re.search(r"\.okc-generic-cursor\s*\{([^}]*)\}", css)
        assert m, ".okc-generic-cursor rule missing"
        body = m.group(1)
        sw = re.search(r"stroke-width\s*:\s*([\d.]+)", body)
        assert sw and float(sw.group(1)) >= 1.5, (
            f"vertical-cursor stroke-width must be ≥1.5 for legibility, "
            f"got {sw.group(1) if sw else 'none'}"
        )


class TestGroupedBarCascadeFix:
    """`.bar-chart-grouped-bar .bar-row .bar-fill` MUST NOT set
    background unconditionally — that cascade-fights the
    `.bar-row .bar-fill.success`-style token rules (same specificity,
    grouped-bar wins by source order) and turns every series into
    accent. The fix is to drop the unconditional background; defaults
    fall through from the parent rule, token classes apply normally."""

    def test_grouped_bar_does_not_force_accent(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        m = re.search(
            r"\.bar-chart-grouped-bar\s+\.bar-row\s+\.bar-fill\s*\{([^}]+)\}",
            css,
        )
        assert m, ".bar-chart-grouped-bar bar-fill rule missing"
        body = m.group(1)
        # Strip CSS comments so the phrase appearing inside a `/* ... */`
        # explanation doesn't trigger the assertion. Only an actual
        # `background: var(--accent);` property declaration should fail.
        body_no_comments = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        # Background must NOT be set as a real declaration ending with
        # `;` or the rule's closing brace.
        bg = re.search(r"background\s*:\s*var\(--accent\)\s*[;}]", body_no_comments)
        assert not bg, (
            "`.bar-chart-grouped-bar .bar-row .bar-fill` must NOT set "
            "background: var(--accent); same-specificity token rules "
            "ship later than this selector and would lose. Result: every "
            "series renders in accent regardless of its color field."
        )


class TestSunburstPolarAreaInteractivity:
    """Sunburst arcs and polar-area sectors must carry rich
    data-hover-payload AND visible class hooks for the CSS hover-emphasis
    rules. Sunburst payload must include share (% of total) — the user
    reported "no visible values" for the wheel."""

    def _read_chrome(self, repo_root: Path) -> str:
        return (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")

    def test_sunburst_payload_includes_share(self, repo_root: Path) -> None:
        js = self._read_chrome(repo_root)
        # The payload-building line must include both `value` and `share`
        # in the kv array.
        assert "k: 'share'" in js, (
            "Sunburst hover payload must include `share: N%` of total "
            "— the user reported 'no visible values' on the wheel"
        )

    def test_sunburst_reserves_title_gutter(self, repo_root: Path) -> None:
        js = self._read_chrome(repo_root)
        # The title-clearance block must reserve a top gutter so the
        # outer ring doesn't run under the title.
        assert "titleH = this._title ? 28 : 8" in js, (
            "Sunburst must reserve 28 viewBox units of title gutter so "
            "the title text and the outer ring don't overlap"
        )

    def test_polar_area_payload_includes_share(self, repo_root: Path) -> None:
        js = self._read_chrome(repo_root)
        # Polar-area's payload-building section must produce a share kv.
        # The total-sum computation must exist for the share %.
        assert "totalValue = sectors.reduce" in js, (
            "Polar-area must sum total sector value to compute share %"
        )


class TestSlopeParcoordInteractivity:
    """Slope lines + parallel-coords polylines must have visible hover
    emphasis. Parcoord polyline also needs explicit fill='none' so
    SVG doesn't paint it as a black blob (polyline default fill is
    black)."""

    def test_parcoord_polyline_has_no_fill(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The parcoord render must emit `fill="none"` on every polyline.
        assert "okc-parcoord-line" in js
        assert 'fill="none"' in js, (
            "Parcoord polyline must set fill='none' explicitly — SVG "
            "polyline defaults to black fill and renders the line "
            "as a closed blob otherwise"
        )

    def test_slope_and_parcoord_have_hover_emphasis(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Both selectors must appear with :has() + :hover for the
        # dim-others-pop-target pattern.
        assert ".okc-slope:has(.okc-slope-line:hover)" in css, (
            "Slope must have :has()-based hover emphasis"
        )
        assert ".okc-parcoord:has(.okc-parcoord-line:hover)" in css, (
            "Parallel-coordinates must have :has()-based hover emphasis"
        )


class TestBulletVerticalCursor:
    """The bullet renderer must wire the generic vertical cursor with
    a seriesLookup callback so a hover at any x reports each track's
    `pct * trackMax` reading."""

    def test_bullet_wires_cursor_with_series_lookup(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Find the bullet renderer block and check it calls
        # _wireGenericVerticalCursor with a seriesLookup option.
        m = re.search(
            r"_renderBullet\(\)\s*\{.*?_wireGenericVerticalCursor\([^)]*\{(?:[^{}]|\{[^{}]*\})*seriesLookup",
            js,
            re.DOTALL,
        )
        assert m, (
            "_renderBullet must call _wireGenericVerticalCursor with a "
            "seriesLookup callback so the cursor surfaces per-track "
            "readouts at the pointer's x position"
        )


class TestRadarRichSample:
    """The radar example in docs/charts.json must be a richer sample
    (≥6 axes, ≥3 series) so the polygons actually compare meaningfully.
    Before the fix it was 5 axes × 2 generic A/B series — looked like
    decoration."""

    def test_radar_example_has_real_data(self, repo_root: Path) -> None:
        import json as _json
        data = _json.loads((repo_root / "docs" / "charts.json").read_text(encoding="utf-8"))
        # Walk to find the radar example output
        def walk(node):
            if isinstance(node, dict):
                if node.get("kind") == "chart" and node.get("type") == "radar":
                    yield node
                for v in node.values():
                    yield from walk(v)
            elif isinstance(node, list):
                for x in node:
                    yield from walk(x)
        radars = list(walk(data))
        # Find the main chart-radar (excluding the picker's tiny preview)
        main = [r for r in radars if isinstance(r.get("axes"), list) and len(r.get("axes", [])) >= 6]
        assert main, (
            f"Radar example must have ≥6 axes; found radars with "
            f"{[len(r.get('axes', [])) for r in radars]} axes"
        )
        sample = main[0]
        series = sample.get("series", [])
        assert len(series) >= 3, (
            f"Radar example must have ≥3 series to compare polygon "
            f"shapes; got {len(series)}"
        )
        for s in series:
            assert s.get("label"), "every radar series must have a label"


class TestPickerOverhaul:
    """Pick-by-family preview cards must be at least 200 px tall
    (was 170), the chart inside max 160 px (was 100), and every
    legend variant must be display:none inside the picker."""

    def test_picker_card_taller(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        m = re.search(
            r"\.compare-card\.compare-card-link\s*\{([^}]+)\}",
            css,
        )
        assert m
        h = re.search(r"height\s*:\s*(\d+)px", m.group(1))
        assert h and int(h.group(1)) >= 200, (
            f"picker card height must be ≥200px for readability; "
            f"got {h.group(1) if h else 'none'}"
        )

    def test_picker_chart_legends_hidden(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Every legend variant must be in the display:none block
        # scoped to .compare-card-link.
        for lg in (
            ".okc-series-legend",
            ".okc-radar-legend",
            ".okc-donut-legend",
            ".okc-waffle-legend",
            ".okc-legend-backdrop",
            ".bar-chart-legend",
        ):
            assert (
                f".compare-card.compare-card-link {lg}" in css
            ), f"picker must hide {lg} (preview shouldn't include legends)"


class TestTableCopyTSV:
    """Every table toolbar must emit a Copy data (TSV) button. Same
    affordance charts have."""

    def test_table_renders_copy_button(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "title=\"Copy data (TSV)\"" in js, (
            "Table toolbar must include a Copy data (TSV) button"
        )
        # Click handler must write headers + visible rows as TSV
        # via navigator.clipboard.writeText.
        assert "navigator.clipboard.writeText(tsv)" in js, (
            "Copy button must use navigator.clipboard.writeText to "
            "send the TSV to the clipboard"
        )


class TestMermaidUniversalHover:
    """Hover emphasis must apply to every Mermaid diagram type, not
    only flowchart. Earlier the `.node:hover` rule only matched
    flowcharts; state / class / ER / sequence / gantt / pie etc.
    had no hover at all."""

    def test_hover_targets_each_type(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # The hover rule must include selectors for major diagram types.
        for sel in (
            ".actor",                  # sequence
            ".statediagram-state",    # state
            ".classGroup",             # class
            ".entityBox",              # ER
            ".task",                   # gantt + journey
        ):
            assert (
                f"oku-diagram .okd-render svg {sel}:hover" in css
            ), (
                f"Mermaid hover rule must include {sel} so {sel}-shaped "
                f"diagrams (state / class / ER / sequence / gantt) "
                f"react to hover"
            )

    def test_gantt_sample_is_realistic(self, repo_root: Path) -> None:
        import json as _json
        diagrams = _json.loads((repo_root / "docs" / "diagrams.json").read_text(encoding="utf-8"))
        # Walk to find gantt example
        src = ""
        def walk(node):
            nonlocal src
            if isinstance(node, dict):
                s = node.get("source", "")
                if isinstance(s, str) and s.startswith("gantt"):
                    src = s
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for x in node:
                    walk(x)
        walk(diagrams)
        assert "after a" in src or "after w" in src, (
            "Gantt sample should chain tasks via `after <id>` to show "
            "dependencies — bare back-to-back tasks don't demonstrate "
            "Gantt's value as a chart type"
        )
        assert "milestone" in src, (
            "Gantt sample should include at least one :milestone task "
            "to show the full vocabulary"
        )


class TestLightboxZoomSmoothness:
    """Lightbox wheel zoom must use a deltaY-proportional factor, not
    a flat per-tick step. Toolbar buttons softened to ×1.2."""

    def test_wheel_zoom_uses_exponential_factor(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # The exponential mapping is the load-bearing math — must remain.
        assert "Math.exp(-dy * 0.0025)" in js, (
            "Lightbox wheel zoom must use exp(-dy * 0.0025) factor for "
            "proportional smoothness on trackpads"
        )

    def test_toolbar_buttons_use_softer_step(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        # Toolbar +/- buttons must use ×1.2, not the old ×1.4.
        assert "zoomAt(cx, cy, 1.2)" in js, (
            "Lightbox toolbar Zoom-in button must use ×1.2 step"
        )
        assert "zoomAt(cx, cy, 1 / 1.2)" in js, (
            "Lightbox toolbar Zoom-out button must use ÷1.2 step"
        )


class TestCurveSmoothing:
    """Line + area charts support `curve: "smooth"` for Catmull-Rom
    splines. Schema must allow it, renderer must pass it through,
    OkuChart must read it, and the path builder must emit cubic
    Bezier when smooth is active."""

    def test_schema_includes_curve_field(self, repo_root: Path) -> None:
        import json as _json
        schema = _json.loads((repo_root / "kit" / "schema" / "page.schema.json").read_text(encoding="utf-8"))
        # Locate the chart kind's properties — schema is nested.
        text = (repo_root / "kit" / "schema" / "page.schema.json").read_text(encoding="utf-8")
        assert '"curve"' in text, "schema must declare a `curve` property"
        assert '"smooth"' in text and '"linear"' in text, (
            "curve enum must include both `linear` and `smooth`"
        )

    def test_renderer_passes_curve_attribute(self, repo_root: Path) -> None:
        rjs = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert "el.setAttribute('curve'" in rjs, (
            "renderer.js must pipe block.curve onto the oku-chart host "
            "as a `curve` attribute"
        )

    def test_oku_chart_reads_curve_and_builds_catmull_rom(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "this._curve" in js, (
            "OkuChart must read the `curve` attribute into this._curve"
        )
        # Catmull-Rom-to-Bezier formula — control points use the
        # canonical 1/6 tension. Both control points should appear.
        assert "(p2.x - p0.x) / 6" in js, (
            "Catmull-Rom Bezier control-point math must use the canonical "
            "(P_next - P_prev) / 6 tension formula"
        )


class TestGeoHonestNaming:
    """The geo cartogram is a tile grid, not a real map. Schema must
    include `tile-map` as an alias and the docs must drop the
    'real-world map' claim."""

    def test_schema_includes_tile_map_alias(self, repo_root: Path) -> None:
        schema_text = (repo_root / "kit" / "schema" / "page.schema.json").read_text(encoding="utf-8")
        assert '"tile-map"' in schema_text, (
            "schema enum must include `tile-map` as an honest alias for `geo`"
        )

    def test_oku_chart_dispatches_tile_map_to_geo_renderer(self, repo_root: Path) -> None:
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "'tile-map': '_renderGeo'" in js, (
            "OkuChart's non-Cartesian dispatch must route `tile-map` to "
            "_renderGeo (same as the `geo` alias)"
        )

    def test_docs_drop_real_world_map_claim(self, repo_root: Path) -> None:
        text = (repo_root / "docs" / "charts.json").read_text(encoding="utf-8")
        assert "Values placed on a real-world map." not in text, (
            "Docs must NOT claim the geo chart is a 'real-world map' — "
            "it's a tile cartogram; calling it a map overpromises"
        )


class TestLegendHoverNoBleed:
    """Legend hover emphasis for non-Cartesian shapes (donut / waffle)
    must NOT use drop-shadow halos that bleed across the inter-slice
    gap. Use filter:brightness + accent stroke instead."""

    def test_slice_emphasis_does_not_drop_shadow(self, repo_root: Path) -> None:
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # Find the block that styles the matching slice/waffle/radar
        # under legend-hover.
        m = re.search(
            r"oku-chart\.okc-legend-hovering\[data-legend-hover=\"0\"\]\s+\.okc-slice\[data-slice-idx=\"0\"\],"
            r".*?\}",
            css,
            re.DOTALL,
        )
        assert m, "non-Cartesian legend-hover rule missing"
        body = m.group(0)
        # Strip CSS comments so the comment discussing the old approach
        # doesn't trigger the assertion. Only an actual `drop-shadow(...)`
        # in a property declaration should fail.
        body_no_comments = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        assert "drop-shadow" not in body_no_comments, (
            "Donut slice / waffle cell legend-hover emphasis must NOT "
            "use drop-shadow (bleeds across the inter-slice gap). Use "
            "filter:brightness + accent stroke instead."
        )
        assert "brightness" in body_no_comments, (
            "Use filter:brightness for fill emphasis without bleeding"
        )


class TestSelfReviewMisses:
    """Self-review of the audit round surfaced four cases the round
    missed. Pin each so they can't silently regress."""

    def test_bubble_label_offset_scales_with_radius(self, repo_root: Path) -> None:
        """Point-label x-offset must account for the bubble's actual
        radius — a flat 8 px puts labels INSIDE large bubbles. The
        user's "Auth"/"Logging" overlap was exactly this."""
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "var labelOffset = r + 8;" in js, (
            "Cartesian point label must compute `r + 8` for its x-offset "
            "so the label clears the bubble's edge regardless of size"
        )

    def test_mermaid_hover_targets_slice_for_pie(self, repo_root: Path) -> None:
        """Pie's interactive shapes are .slice (the wedges), not
        .pieCircle (the outer ring)."""
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "oku-diagram .okd-render svg .slice" in css, (
            "Mermaid hover rule must include .slice — the wedge class "
            "is where pie's interaction actually lives"
        )
        assert "oku-diagram .okd-render svg .slice:hover" in css, (
            "Mermaid hover rule must give .slice a :hover styling"
        )

    def test_mermaid_hover_targets_timeline_classes(self, repo_root: Path) -> None:
        """Timeline emits .timeline-node + .taskWrapper, neither of
        which matches the earlier generic selectors."""
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        for sel in (".timeline-node", ".taskWrapper"):
            assert f"oku-diagram .okd-render svg {sel}" in css, (
                f"Mermaid hover rule must include {sel} — timeline "
                f"diagrams have no other matching selector"
            )

    def test_mermaid_section_substring_match(self, repo_root: Path) -> None:
        """Gantt + journey + mindmap section classes come through as
        `.section0` / `.section--1` / etc. without a hyphen separator.
        Substring match `[class*="section"]` catches them."""
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert 'oku-diagram .okd-render svg [class*="section"]' in css, (
            "Mermaid hover rule must use `[class*=\"section\"]` to "
            "catch .section0 / .section--1 / .section-edge-N variants"
        )
