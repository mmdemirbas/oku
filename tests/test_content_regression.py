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
import re
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

    def test_chrome_css_has_code_lang_pill_top_left(self, repo_root: Path) -> None:
        """Language pill is a top-left label tab — above the block boundary.

        Regression history:
        - First, pill was at top-right next to copy button (user asked
          for top-left).
        - Then, pill was at top:8px inside the pre's padding, which
          visually overlapped the first character of the first code line.
        - Now, pill floats half above the pre's top border (top: -8px)
          so it never overlaps any code regardless of gutter width or
          first-line content.

        Verify the base rule positions with `left:` AND a negative `top:`
        so the pill sits as a label tab on the corner, not inside the
        code area.
        """
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        assert ".hdt-code-lang" in css, "code-block language pill rule missing"
        m = re.search(r"pre\s*>\s*\.hdt-code-lang\s*\{([^}]+)\}", css)
        assert m, "base `pre > .hdt-code-lang` rule missing"
        block = m.group(1)
        assert "left:" in block, "lang pill must use left: (top-left)"
        assert "right:" not in block, (
            "lang pill must not use right: — top-right belongs to the chrome bar"
        )
        # Pill must straddle the top edge (negative `top:`) so it never
        # overlaps code horizontally regardless of gutter or line length.
        top_match = re.search(r"top:\s*(-?\d+)px", block)
        assert top_match, "lang pill must declare a top: value"
        top_px = int(top_match.group(1))
        assert top_px <= 0, (
            f"lang pill top: {top_px}px sits INSIDE the pre's padding — "
            "it overlaps code on the first line. Use a negative value so "
            "the pill floats above the block boundary like a label tab."
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
        js = (repo_root / "chrome.js").read_text(encoding="utf-8")
        boot = (repo_root / "chrome-boot.js").read_text(encoding="utf-8")
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

    def test_lightbox_module_exists(self, repo_root: Path) -> None:
        """Shared lightbox overlay must exist + be wired to charts + diagrams.

        Regression: user asked for a full-screen expand on images, charts,
        diagrams (and later Mermaid). One shared overlay so the affordance
        is identical everywhere.
        """
        js = (repo_root / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        assert "__htmldocLightbox" in js, "lightbox module missing"
        assert ".hdt-lightbox" in css, "lightbox CSS missing"
        assert "ICON_EXPAND" in js, "expand icon constant missing"
        # Chart + diagram custom elements get the expand action in their
        # toolbars; both call into __htmldocLightbox.open.
        chart_expand = re.search(
            r"makeToolbar\(this,\s*\[[\s\S]*?Expand to fullscreen[\s\S]*?\]\)",
            js,
        )
        assert chart_expand, "Expand action missing from a custom element toolbar"
        # Backdrop + Escape close paths.
        assert "hdt-lightbox-backdrop" in js, "backdrop close target missing"
        assert "e.key === 'Escape'" in js, "Escape close path missing"

    def test_annotated_code_markers_in_left_gutter(self, repo_root: Path) -> None:
        """Annotation markers must sit in a per-line LEFT gutter, not inline.

        Regression: the original `<html-doc-annotated-code>` placed `(1)`,
        `(2)` markers inline within the code text. The reader had to scan
        each line to find them. User asked for markers BEFORE the line,
        vertically aligned, so the eye can find every annotated line at a
        glance.

        Enforce by checking:
        - chrome.js builds the per-line slot (`hdc-anno-line-marker`) AND
          moves markers from inline into those slots.
        - chrome.css positions the slot as a left gutter via absolute
          positioning + reserved padding on the pre.
        """
        js = (repo_root / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        # JS marker construction + extraction.
        assert "hdc-anno-line-marker" in js, "per-line marker slot missing"
        assert "prepareLineSlots" in js or "hdc-anno-gutter-on" in js, (
            "slot prep step missing — annotated lines won't get gutter slots"
        )
        assert "moveMarkersToSlots" in js or "slot.appendChild(btn)" in js, (
            "marker-move-to-slot step missing — markers will stay inline"
        )
        # CSS positions the slot to the LEFT of code (negative left:) and
        # reserves padding on the pre to make room.
        assert ".hdc-anno-line-marker" in css, "marker slot styling missing"
        slot_rule = re.search(
            r"\.hdc-anno-wrap\.hdc-anno-gutter-on\s+\.hdc-anno-line-marker\s*\{([^}]+)\}",
            css,
        )
        assert slot_rule, "scoped slot rule missing"
        assert "position: absolute" in slot_rule.group(1), (
            "marker slot must be absolutely positioned so it doesn't break the "
            "inline flow of Prism token spans on each line"
        )

    def test_list_view_items_visually_separated(self, repo_root: Path) -> None:
        """List-view items must have clear visual separation.

        Regression: user reported "I cannot tell where the first list item
        ends and second starts" when tables were in list view. The fix
        triples the gap and swaps the outer border from --border-soft to
        --line, with a box-shadow to lift each card off the page.

        Enforce by checking the .hdt-table-list / .hdt-list-card block
        carries (a) a meaningful gap (≥16px), (b) a non-soft outer border
        token, and (c) a box-shadow declaration.
        """
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        # Match the BASE list rule (the data-view variants are display:none
        # and don't carry layout). Anchor on the unique `display: flex` shape.
        list_rule = re.search(
            r"\.hdt-table-list\s*\{[^}]*display:\s*flex[^}]*\}", css
        )
        card_rule = re.search(r"\.hdt-list-card\s*\{([^}]*)\}", css)
        assert list_rule, ".hdt-table-list base rule (display:flex) missing"
        assert card_rule, ".hdt-list-card rule missing"
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
        js = (repo_root / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        assert "ICON_WRAP" in js, "wrap button needs a dedicated icon constant"
        assert "hdt-wrap-btn" in js, "wrap button must be created in chrome.js"
        assert ".hdt-wrap-btn" in css, "wrap button styling missing"
        # Toggled state must flip white-space on the inner <code>.
        assert "pre.hdt-wrap" in css, "wrap state class missing"
        assert "white-space: pre-wrap" in css, (
            "wrap state must flip white-space to pre-wrap so long lines wrap"
        )

    def test_fold_markers_separate_from_line_numbers(self, repo_root: Path) -> None:
        """Fold handles must be their own gutter column, IDE-style.

        Regression: an earlier implementation put fold chevrons inline with
        line numbers via `pre .hdt-code-ln.hdt-foldable::after`, making
        foldable line numbers a different colour and weight, breaking
        gutter alignment. The user asked for IDE-style: numbers uniform,
        fold handle as a separate dim column.

        Enforce by checking:
        - chrome.js emits a `.hdt-code-row` per line with both a
          `.hdt-fold-marker` and a `.hdt-code-ln` child.
        - chrome.css styles `.hdt-fold-marker` as its own gutter element.
        - chrome.css does NOT carry the old `pre .hdt-code-ln.hdt-foldable`
          override that re-coloured the line number.
        """
        js = (repo_root / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "chrome.css").read_text(encoding="utf-8")
        assert "hdt-code-row" in js, "gutter must emit per-line rows"
        assert "hdt-fold-marker" in js, "gutter must emit a fold-marker span per row"
        assert ".hdt-fold-marker" in css, "fold-marker styling missing"
        assert ".hdt-fold-marker.hdt-foldable" in css, (
            "fold-marker foldable variant missing"
        )
        # Negative: the old line-number override must be gone.
        assert ".hdt-code-ln.hdt-foldable" not in css, (
            "stale `.hdt-code-ln.hdt-foldable` override resurfaced — fold "
            "handles must live on `.hdt-fold-marker`, not on the line number"
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
        js = (repo_root / "chrome.js").read_text(encoding="utf-8")
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
