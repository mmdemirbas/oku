"""Content-regression tests for the docs/ JSON sources.

These guard against accidental deletion or shape-drift of the worked
examples that prove a primitive works. Schema validation alone won't
catch "primitives.json no longer contains a chip-filtered table" — a
future edit could pass the schema while silently removing the demo.

The browser layer (table filter / chip toggle / fold region) is NOT
tested here — that needs a headless browser. The CLAUDE.md note in
the repo root describes how to add Playwright coverage when the
existing assertions are not enough.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(scope="module")
def primitives(repo_root: Path) -> dict:
    return json.loads((repo_root / "docs" / "primitives.json").read_text(encoding="utf-8"))


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
    """The primitives reference must keep the three worked examples:
    flat, grouped, and chip-filtered with multi-valued cells. Without
    them the table block has no visible documentation."""

    def test_flat_table_present(self, primitives: dict) -> None:
        block = _find_block(
            primitives,
            lambda b: b.get("kind") == "table"
            and isinstance(b.get("headers"), list)
            and "rows" in b
            and "groups" not in b,
        )
        assert block is not None, "flat table example missing from primitives.json"

    def test_grouped_table_present(self, primitives: dict) -> None:
        block = _find_block(
            primitives,
            lambda b: b.get("kind") == "table" and isinstance(b.get("groups"), list),
        )
        assert block is not None, "grouped table example missing from primitives.json"
        assert len(block["groups"]) >= 2, "grouped example should declare multiple groups"

    def test_chip_filtered_table_present(self, primitives: dict) -> None:
        """At least one table header uses the object form with
        filter='chips' + values."""
        for block in _walk_blocks(primitives):
            if block.get("kind") != "table":
                continue
            for h in block.get("headers", []):
                if isinstance(h, dict) and h.get("filter") == "chips" and h.get("values"):
                    return
        pytest.fail("chip-filtered table example missing from primitives.json")

    def test_chip_cells_use_object_form(self, primitives: dict) -> None:
        """Cells under chip columns must declare a `values` array."""
        for block in _walk_blocks(primitives):
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
    def test_tldr_render_sample(self, primitives: dict) -> None:
        """tldr now renders inside contentBlock context, so the
        primitives reference must include both a code example and a
        live tldr render."""
        tldrs = [b for b in _walk_blocks(primitives) if b.get("kind") == "tldr"]
        assert tldrs, "no tldr render sample in primitives.json"


# ---------- kpi-grid sync ----------


class TestKpiGridSync:
    def test_kpi_example_matches_render(self, primitives: dict) -> None:
        """The kpi-grid example code and the adjacent rendered sample
        must agree on the tile set, otherwise the doc is lying."""
        blocks = list(_walk_blocks(primitives))
        # Find the rendered kpi-grid that immediately follows the
        # heading id="kpi-grid".
        rendered = None
        for i, b in enumerate(blocks):
            if b.get("id") == "kpi-grid" and b.get("kind") == "heading":
                for j in range(i + 1, len(blocks)):
                    if blocks[j].get("kind") == "kpi-grid":
                        rendered = blocks[j]
                        break
                break
        assert rendered is not None, "no rendered kpi-grid sample"
        labels = {t.get("label") for t in rendered.get("tiles", [])}
        # Find the code block immediately before the render (the example).
        # Look up siblings via blocks list — pragmatic; not airtight.
        code_blocks = [
            b
            for b in blocks
            if b.get("kind") == "code"
            and b.get("language") == "json"
            and '"kind": "kpi-grid"' in (b.get("source") or "")
        ]
        assert code_blocks, "no kpi-grid code example next to the render"
        example_source = code_blocks[0]["source"]
        for label in labels:
            assert (
                label in example_source
            ), f"render shows tile {label!r} but the example code doesn't"


# ---------- cross-cutting features ----------


class TestCrossCuttingFeatures:
    def test_section_present(self, primitives: dict) -> None:
        for b in _walk_blocks(primitives):
            if b.get("kind") == "section" and b.get("id") == "cross-cutting":
                return
        pytest.fail("cross-cutting section missing from primitives.json")

    def test_data_bind_demo_paired(self, primitives: dict) -> None:
        """A bound paragraph and callout must share a `bind` key — the
        live demo of the synced-hover feature."""
        bind_blocks = [b for b in _walk_blocks(primitives) if b.get("bind")]
        keys = [b["bind"] for b in bind_blocks]
        # At least one key shared between two blocks
        from collections import Counter

        counts = Counter(keys)
        shared = [k for k, v in counts.items() if v >= 2]
        assert shared, "no two blocks share a bind key in the demo"


# ---------- table-demo removal ----------


class TestNoStrayDemoPages:
    """User explicitly requested table-demo be merged into primitives.
    Make sure it doesn't sneak back in."""

    def test_no_table_demo(self, repo_root: Path) -> None:
        assert not (
            repo_root / "docs" / "table-demo.html"
        ).exists(), "table-demo.html should live inside primitives, not as a separate doc"
        assert not (
            repo_root / "docs" / "table-demo.json"
        ).exists(), "table-demo.json should live inside primitives, not as a separate doc"


# ---------- chrome.js / chrome.css regression markers ----------


class TestChromeKitMarkers:
    """Spot-check chrome.js / chrome.css for behaviours the user has
    asked to keep. These won't catch DOM bugs at runtime, but they
    flag a regression where someone deletes the marker code entirely
    while doing an unrelated refactor."""

    def test_chrome_has_groupby_picker(self, repo_root: Path) -> None:
        src = (repo_root / "chrome.js").read_text(encoding="utf-8")
        assert "hdt-groupby-select" in src, "table group-by picker source markers missing"

    def test_chrome_has_fold_handler(self, repo_root: Path) -> None:
        src = (repo_root / "chrome.js").read_text(encoding="utf-8")
        assert (
            "_hdtDetectBraceFolds" in src
        ), "code-block brace-fold detector missing from chrome.js"

    def test_chrome_has_sidebar_toggle(self, repo_root: Path) -> None:
        src = (repo_root / "chrome.js").read_text(encoding="utf-8")
        assert "sidebar-collapsed" in src, "sidebar collapse class wiring missing"

    def test_chrome_css_has_sticky_sidebar(self, repo_root: Path) -> None:
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
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
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
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

    def test_chrome_css_has_code_lang_pill(self, repo_root: Path) -> None:
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        assert ".hdt-code-lang" in css, "code-block language pill rule missing"
