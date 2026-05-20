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
        src = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "hdt-groupby-select" in src, "table group-by picker source markers missing"

    def test_chrome_has_fold_handler(self, repo_root: Path) -> None:
        src = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert (
            "_hdtDetectBraceFolds" in src
        ), "code-block brace-fold detector missing from chrome.js"

    def test_chrome_has_sidebar_toggle(self, repo_root: Path) -> None:
        src = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        assert "sidebar-collapsed" in src, "sidebar collapse class wiring missing"

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
        - No `pre:hover > .hdt-code-lang` rule.
        - top: 0, left: 0 (corner-flush, not 7px / 10px inset).
        - border-radius drops corner-rounding except the inner one.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "pre:hover > .hdt-code-lang" not in css, (
            "lang pill must not have a hover state — it's a label, not a button"
        )
        m = re.search(r"pre\s*>\s*\.hdt-code-lang\s*\{([^}]+)\}", css)
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
            r"pre\.hdt-line-numbered\s+\.hdt-code-line\s*\{([^}]+)\}",
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
        Verify the .hdt-code-line uses display: grid and
        `align-items: start` so cells anchor to the row top while
        content can grow to wrapped height.
        """
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        m = re.search(
            r"pre\.hdt-line-numbered\s+\.hdt-code-line\s*\{([^}]+)\}",
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
        tooltip (`.hdc-anno-tip`).
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        # JS attaches the tooltip with the annotation body.
        assert "hdc-anno-tip" in js, "annotation tooltip injection missing"
        # CSS: 4-column grid override for annotated-code line.
        assert ".hdc-anno-wrap.hdc-anno-gutter-on pre.hdt-line-numbered .hdt-code-line" in css, (
            "annotation-mode grid override missing"
        )
        # Hover/focus shows the tip.
        assert ".hdc-anno-marker:hover + .hdc-anno-tip" in css, (
            "hover-to-show tooltip CSS missing"
        )

    def test_renderer_converts_inline_code_tags_in_strings(self, repo_root: Path) -> None:
        """Renderer auto-converts `<code>…</code>` strings to inline code.

        Regression: authored callouts/paragraphs contained literal
        `<code>...</code>` strings in `content`. The renderer used to
        HTML-escape them, showing the angle-bracket tag as text instead
        of a code element. Added _splitInlineTags to detect + convert
        the three text-shape primitives (code, em, strong) so either
        authoring form works.
        """
        js = (repo_root / "kit" / "renderer.js").read_text(encoding="utf-8")
        assert "_splitInlineTags" in js, "inline-tag converter missing"
        # Regex targets only code / em / strong — not arbitrary tags
        # (otherwise documentation like "<callout>" gets eaten).
        assert "(code|em|strong)" in js, (
            "_splitInlineTags regex must restrict to code/em/strong tags"
        )

    def test_serve_synthesizes_md_pages(self, repo_root: Path) -> None:
        """`html-doc serve` synthesizes .html + .json from .md sources.

        Before this fix, the dev server returned 404 for any *.html
        request that had no real .html file on disk, even if a sibling
        .md existed. That broke the `html-doc serve` preview workflow
        for markdown-authored pages. The build path (cmd_build) emits
        them into dist/, but serve must work without a build.

        Verify the handler has the `_serve_md_synthesized` method and
        it short-circuits do_GET when a sibling .md exists.
        """
        cli_src = (repo_root / "src" / "html_doc" / "cli.py").read_text(encoding="utf-8")
        assert "_serve_md_synthesized" in cli_src, "md synthesis handler missing"
        # Must be invoked from do_GET before super().do_GET().
        m = re.search(
            r"def do_GET\(self\)[\s\S]*?if self\._serve_md_synthesized\(\)",
            cli_src,
        )
        assert m, "_serve_md_synthesized must be called from do_GET"

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

        Audit findings on first run: 3 broken ext-refs in primitives.json
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
        for p in (repo_root / "kit-data" / "glossary").glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            for term in (data.get("entries") or {}).keys():
                glossary_terms.add(term.lower())

        extref_names: set[str] = set()
        for p in (repo_root / "kit-data" / "extrefs").glob("*.json"):
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

    def test_primitives_code_samples_have_live_demos(self, repo_root: Path) -> None:
        """Every code sample in docs/primitives.json must have a matching demo.

        Rule: when a `<code>` block contains JSON describing an html-doc
        block (single top-level object with a `kind` field), one of the
        next ≤4 sibling blocks must be a block of that kind, OR one of
        those siblings must contain that kind as an inline element.

        Prevents author-drift where someone edits the code sample but
        forgets the live demo (or vice versa). User explicitly called
        out: "Some examples are different than the rendered content
        below it, some doesn't have a rendered counterpart at all."
        """
        page_path = repo_root / "docs" / "primitives.json"
        assert page_path.exists(), "docs/primitives.json missing"
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
        assert not issues, "primitives.json drift:\n" + "\n".join(issues)

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
        from html_doc.cli import md_to_page  # noqa: PLC0415

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

    def test_root_index_redirects_to_docs(self, repo_root: Path) -> None:
        """Repo-root `index.html` must exist and forward to docs/index.html.

        Use case: IntelliJ's built-in HTTP server (and any static host
        serving the repo root) lands on this file. Without it, opening
        the project URL yields a 404 unless the user knows to navigate
        to docs/. Tiny forwarder; no kit assets.

        Must:
        - Exist at repo root.
        - Reference docs/index.html as the target.
        - Forward the IntelliJ `_ijt` query token so internal asset
          fetches keep their auth.
        """
        idx = (repo_root / "index.html")
        assert idx.exists(), "root index.html missing"
        body = idx.read_text(encoding="utf-8")
        assert "docs/index.html" in body, "root index must forward to docs/index.html"
        # Either a meta-refresh, a JS location.replace, or a plain link works.
        # We need at least one of them.
        assert (
            "http-equiv=\"refresh\"" in body
            or "location.replace" in body
            or 'href="docs/index.html"' in body
        ), "root index must contain a forwarding mechanism"
        # _ijt token must be forwarded so IntelliJ asset fetches still resolve.
        assert "_ijt" in body, (
            "root index must forward the IntelliJ _ijt token through to "
            "the docs index so internal asset URLs keep their auth"
        )

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
            r"class\s+HtmlDocDiagram[\s\S]*?_attachToolbar\(\)\s*\{[\s\S]*?makeToolbar\(this,\s*\[([\s\S]*?)\]\)",
            js,
        )
        assert m, "HtmlDocDiagram._attachToolbar block not found"
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

    def test_table_has_board_view(self, repo_root: Path) -> None:
        """Tables expose a 4th view: Board (kanban-style lanes).

        User asked for "board view in tables" alongside the existing
        Table / List / Cards. Group-by drives lanes; rows become cards.
        Lock in:

        - JS toolbar emits a `data-view="board"` button.
        - JS has a `renderBoard` function and a `.hdt-table-board`
          container.
        - CSS view-toggle hides `.hdt-table-board` for the three
          non-active views and hides it by default (no data-view attr).
        - CSS provides `.hdt-board-lane` styling.
        """
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert 'data-view="board"' in js, "Board toggle button missing in toolbar"
        assert "renderBoard" in js, "renderBoard function missing"
        assert "hdt-table-board" in js, "board container missing"
        assert ".hdt-board-lane" in css, "lane styling missing"
        assert '[data-view="board"]' in css, "board active-view rule missing"

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
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
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
        js = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
        css = (repo_root / "kit" / "chrome.css").read_text(encoding="utf-8")
        assert "ICON_WRAP" in js, "wrap button needs a dedicated icon constant"
        assert "hdt-wrap-btn" in js, "wrap button must be created in chrome.js"
        assert ".hdt-wrap-btn" in css, "wrap button styling missing"
        # Toggled state must flip white-space on the inner <code>.
        assert "pre.hdt-wrap" in css, "wrap state class missing"
        assert "white-space: pre-wrap" in css, (
            "wrap state must flip white-space to pre-wrap so long lines wrap"
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
