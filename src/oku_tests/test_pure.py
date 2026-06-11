"""Tests for pure functions in oku.cli.

These don't touch the filesystem at all — fast, deterministic, and the
right surface to catch markdown-twin / target-picker / docs-dir regressions
before they ship.
"""

from __future__ import annotations

from pathlib import Path


from oku import cli


# ---------- _flatten_inline ----------


class TestFlattenInline:
    def test_string_passthrough(self) -> None:
        assert cli._flatten_inline("hello") == "hello"

    def test_none_returns_empty(self) -> None:
        assert cli._flatten_inline(None) == ""

    def test_list_joins(self) -> None:
        assert cli._flatten_inline(["a", " ", "b"]) == "a b"

    def test_em_wraps_in_asterisks(self) -> None:
        assert cli._flatten_inline({"kind": "em", "text": "x"}) == "*x*"

    def test_strong_wraps_in_double_asterisks(self) -> None:
        assert cli._flatten_inline({"kind": "strong", "text": "x"}) == "**x**"

    def test_code_wraps_in_backticks(self) -> None:
        assert cli._flatten_inline({"kind": "code", "text": "x"}) == "`x`"

    def test_link_formats_md(self) -> None:
        node = {"kind": "link", "text": "x", "href": "https://e.com"}
        assert cli._flatten_inline(node) == "[x](https://e.com)"

    def test_link_without_href_falls_back_to_plain_text(self) -> None:
        assert cli._flatten_inline({"kind": "link", "text": "x"}) == "x"

    def test_nested_mix(self) -> None:
        node = [
            "Run ",
            {"kind": "code", "text": "ls"},
            " and see ",
            {"kind": "strong", "text": "output"},
        ]
        assert cli._flatten_inline(node) == "Run `ls` and see **output**"

    def test_glossary_term_strips_to_text(self) -> None:
        # glossary terms are inline-readable but carry no markdown anchor;
        # the twin keeps the text bare.
        node = {"kind": "glossary-term", "text": "Iceberg"}
        assert cli._flatten_inline(node) == "Iceberg"


# ---------- _md_block ----------


class TestMdBlock:
    def test_paragraph(self) -> None:
        assert cli._md_block({"kind": "paragraph", "content": "hi"}) == ["hi"]

    def test_heading_level_clamped_to_min_two(self) -> None:
        # The renderer accepts level 3 or 4; the twin clamps to >= 2 so the
        # # count never overshoots H2 vs the page H1.
        out = cli._md_block({"kind": "heading", "level": 3, "title": "x"})
        assert out == ["### x"]

    def test_heading_uses_text_fallback(self) -> None:
        # Some pages legacy-emit `text`; the twin emitter reads `text` too.
        out = cli._md_block({"kind": "heading", "level": 3, "text": "y"})
        assert out == ["### y"]

    def test_callout_emits_blockquote(self) -> None:
        out = cli._md_block({"kind": "callout", "type": "note", "title": "T", "content": "body"})
        assert out == ["> **NOTE: T**", "> body"]

    def test_callout_without_title(self) -> None:
        out = cli._md_block({"kind": "callout", "type": "tip", "content": "x"})
        assert out == ["> **TIP**", "> x"]

    def test_list_unordered(self) -> None:
        out = cli._md_block({"kind": "list", "items": ["a", "b"]})
        assert out == ["- a", "- b"]

    def test_list_ordered(self) -> None:
        out = cli._md_block({"kind": "list", "ordered": True, "items": ["a", "b"]})
        assert out == ["1. a", "2. b"]

    def test_code_block_uses_source(self) -> None:
        out = cli._md_block({"kind": "code", "language": "python", "source": "print(1)"})
        assert out == ["```python", "print(1)", "```"]

    def test_annotated_code_with_inline_html_stripped(self) -> None:
        out = cli._md_block(
            {
                "kind": "annotated-code",
                "language": "js",
                "source": "x // (1)",
                "annotations": [{"id": 1, "content": "<code>x</code> is one."}],
            }
        )
        # Inline HTML tags get stripped so the twin is plain markdown.
        assert out[0] == "```js"
        assert "x // (1)" in out[1]
        assert "```" in out
        assert any("1. x is one." in line for line in out)

    def test_table_flat(self) -> None:
        out = cli._md_block(
            {
                "kind": "table",
                "headers": ["A", "B"],
                "rows": [["1", "2"], ["3", "4"]],
            }
        )
        assert out[0] == "| A | B |"
        assert out[1] == "| --- | --- |"
        assert out[2] == "| 1 | 2 |"
        assert out[3] == "| 3 | 4 |"

    def test_table_grouped_emits_subhead(self) -> None:
        out = cli._md_block(
            {
                "kind": "table",
                "headers": ["A"],
                "groups": [
                    {"title": "G1", "rows": [["x"]]},
                    {"title": "G2", "rows": [["y"]]},
                ],
            }
        )
        joined = "\n".join(out)
        assert "### G1" in joined
        assert "### G2" in joined
        assert "| x |" in joined
        assert "| y |" in joined

    def test_table_chip_headers_use_label(self) -> None:
        """Object-form headers `{label, filter, values}` collapse to the
        bare label in the markdown twin; the chip metadata is discarded
        because LLM consumers don't need the interactive layer."""
        out = cli._md_block(
            {
                "kind": "table",
                "headers": [
                    "Engine",
                    {"label": "Tags", "filter": "chips", "values": ["a", "b"]},
                ],
                "rows": [["Iceberg", {"values": ["a", "b"]}]],
            }
        )
        assert out[0] == "| Engine | Tags |"
        assert out[2] == "| Iceberg | a, b |"

    def test_table_chip_cell_value_overrides_join(self) -> None:
        """Object-form cells render their explicit `value` when present
        rather than the auto-joined chip values."""
        out = cli._md_block(
            {
                "kind": "table",
                "headers": ["Engine", "Maturity"],
                "rows": [["Paimon", {"value": "Incubating", "values": ["incubating"]}]],
            }
        )
        assert "| Paimon | Incubating |" in out

    def test_chart_emits_placeholder(self) -> None:
        out = cli._md_block({"kind": "chart", "title": "T"})
        assert out == ["_[chart: T]_"]

    def test_unknown_kind_emits_placeholder(self) -> None:
        # Doesn't silently swallow — emits a marker so the LLM consumer
        # sees structure even when the kind isn't recognised.
        out = cli._md_block({"kind": "exotic-block"})
        assert out == ["_[exotic-block]_"]


# ---------- render_page_markdown ----------


class TestRenderPageMarkdown:
    def test_emits_h1_title_and_meta_blockquote(self, sample_page: dict) -> None:
        md = cli.render_page_markdown(sample_page)
        lines = md.splitlines()
        assert lines[0] == "# Sample page"
        assert any(line.startswith("*A page for tests*") for line in lines)
        # Meta blockquote contains date + audience + read_time + Updated:
        meta_line = next(line for line in lines if line.startswith("> "))
        assert "2026-05-19" in meta_line
        assert "internal" in meta_line
        assert "~2 min" in meta_line
        assert "Updated:" in meta_line

    def test_handles_page_without_meta(self) -> None:
        # Bare-minimum page: title only. Doesn't crash, no meta line.
        md = cli.render_page_markdown({"kind": "page", "title": "Bare", "blocks": []})
        assert md.startswith("# Bare\n")

    def test_includes_section_heading(self, sample_page: dict) -> None:
        md = cli.render_page_markdown(sample_page)
        assert "## Intro" in md

    def test_ends_with_single_trailing_newline(self, sample_page: dict) -> None:
        md = cli.render_page_markdown(sample_page)
        # The function rstrips then appends one \n.
        assert md.endswith("\n")
        assert not md.endswith("\n\n")


# ---------- _common_docs_dir ----------


class TestCommonDocsDir:
    def test_pages_in_single_subdir(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.json").write_text('{"kind": "page", "title": "A"}')
        (docs / "b.json").write_text('{"kind": "page", "title": "B"}')
        pages = cli.find_json_pages(tmp_path)
        assert cli._common_docs_dir(tmp_path, pages) == docs

    def test_no_pages_returns_root(self, tmp_path: Path) -> None:
        assert cli._common_docs_dir(tmp_path, []) == tmp_path

    def test_pages_in_nested_subdirs_finds_common(self, tmp_path: Path) -> None:
        d1 = tmp_path / "site" / "guide"
        d2 = tmp_path / "site" / "ref"
        d1.mkdir(parents=True)
        d2.mkdir(parents=True)
        (d1 / "a.json").write_text('{"kind": "page", "title": "A"}')
        (d2 / "b.json").write_text('{"kind": "page", "title": "B"}')
        pages = cli.find_json_pages(tmp_path)
        assert cli._common_docs_dir(tmp_path, pages) == tmp_path / "site"


# ---------- _pick_open_target ----------


class TestPickOpenTarget:
    @staticmethod
    def _setup(tmp_path: Path) -> tuple[list[Path], Path]:
        """Minimal repo: docs/index.html, docs/architecture.html, _internal/iceberg.html."""
        for rel in (
            "docs/index.html",
            "docs/architecture.html",
            "_internal/iceberg.html",
        ):
            full = tmp_path / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("<!doctype html>")
        # Return sorted alphabetically — matches cmd_serve's input shape.
        htmls = sorted(p for p in tmp_path.rglob("*.html"))
        return htmls, tmp_path

    def test_prefers_user_cwd_index_html(self, tmp_path: Path) -> None:
        htmls, root = self._setup(tmp_path)
        picked = cli._pick_open_target(htmls, root / "docs", root)
        assert picked == root / "docs/index.html"

    def test_falls_back_to_first_html_under_user_cwd(self, tmp_path: Path) -> None:
        # No index.html under user_cwd, but other HTMLs exist.
        for rel in ("examples/foo.html", "examples/bar.html"):
            full = tmp_path / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("<!doctype html>")
        htmls = sorted(p for p in tmp_path.rglob("*.html"))
        picked = cli._pick_open_target(htmls, tmp_path / "examples", tmp_path)
        assert picked is not None
        assert picked.parent == tmp_path / "examples"

    def test_repo_root_cwd_picks_docs_index_over_internal(self, tmp_path: Path) -> None:
        # If the user starts serve from repo root and docs/index.html exists,
        # that wins over alphabetically-first _internal/iceberg.html.
        htmls, root = self._setup(tmp_path)
        picked = cli._pick_open_target(htmls, root, root)
        # Public docs (docs/) beat _internal/ and examples/.
        assert picked == root / "docs/index.html"

    def test_empty_htmls_returns_none(self, tmp_path: Path) -> None:
        assert cli._pick_open_target([], tmp_path, tmp_path) is None


# ---------- markdown → v2 page conversion ----------


class TestMdToV2Page:
    """md_to_v2_page keeps body markdown VERBATIM and lifts only typed
    fences (```oku-<kind> JSON, ```mermaid) into typed blocks."""

    def test_front_matter_hoists_title_and_meta(self) -> None:
        md = "---\ntitle: Hello\naccent: teal\norder: 7\n---\n\n## S\n\nbody\n"
        page = cli.md_to_v2_page(md)
        assert page["k"] == "page"
        assert page["t"] == "Hello"
        assert page["m"]["accent"] == "teal"
        assert "title" not in page["m"]

    def test_h1_hoisted_when_no_front_matter_title(self) -> None:
        page = cli.md_to_v2_page("# Hello\n\nbody")
        assert page["t"] == "Hello"
        assert page["b"] == ["body"]

    def test_body_stays_verbatim(self) -> None:
        body = "## Sec {#sec}\n\nA *paragraph* with [a ref](#g/iceberg).\n\n- one\n- two"
        page = cli.md_to_v2_page("---\ntitle: T\n---\n" + body)
        assert page["b"] == [body]

    def test_oku_chart_fence_lifts_to_typed_block(self) -> None:
        md = '## S\n\n```oku-chart\n{"type":"bar","rows":[{"label":"a","value":1}]}\n```\n\nafter'
        page = cli.md_to_v2_page(md)
        assert page["b"][0] == "## S"
        assert page["b"][1] == {"k": "chart", "type": "bar", "rows": [{"label": "a", "value": 1}]}
        assert page["b"][2] == "after"

    def test_mermaid_fence_lifts_to_diagram(self) -> None:
        page = cli.md_to_v2_page("```mermaid\nflowchart TB\n  A --> B\n```")
        assert page["b"] == [{"k": "diagram", "src": "flowchart TB\n  A --> B"}]

    def test_italic_caption_folds_into_diagram(self) -> None:
        page = cli.md_to_v2_page("```mermaid\nA --> B\n```\n\n*The caption.*\n\nprose")
        assert page["b"][0] == {"k": "diagram", "src": "A --> B", "caption": "The caption."}
        assert page["b"][1] == "prose"

    def test_italic_line_in_running_prose_is_not_a_caption(self) -> None:
        page = cli.md_to_v2_page("```mermaid\nA\n```\n\n*emphasis* opener\nmore prose")
        assert page["b"][0] == {"k": "diagram", "src": "A"}
        assert "*emphasis* opener" in page["b"][1]

    def test_bad_json_fence_stays_verbatim(self) -> None:
        md = "```oku-chart\n{not json}\n```"
        assert cli.md_to_v2_page(md)["b"] == [md]

    def test_unknown_oku_kind_stays_verbatim(self) -> None:
        md = "```oku-bogus\n{}\n```"
        assert cli.md_to_v2_page(md)["b"] == [md]

    def test_fence_inside_plain_fence_not_lifted(self) -> None:
        """A 3-tick typed fence nested in a 4-tick plain fence is a code
        SAMPLE, not a primitive — it must stay verbatim. Same
        variable-length close rule as CommonMark."""
        md = '````markdown\n```oku-chart\n{"type":"bar","rows":[]}\n```\n````'
        assert cli.md_to_v2_page(md)["b"] == [md]

    def test_mermaid_inside_plain_fence_not_lifted(self) -> None:
        md = "````markdown\n```mermaid\nA --> B\n```\n````"
        assert cli.md_to_v2_page(md)["b"] == [md]

    def test_html_island_stays_verbatim(self) -> None:
        body = (
            '<div class="demo">\n'
            '  <button id="go">Click</button>\n'
            "</div>\n"
            "<script>\n"
            'console.log("island");\n'
            "</script>"
        )
        page = cli.md_to_v2_page("---\ntitle: T\n---\n## S\n\n" + body)
        assert page["b"] == ["## S\n\n" + body], "island must survive byte-for-byte"

    def test_k_in_payload_cannot_spoof_kind(self) -> None:
        md = '```oku-chart\n{"k":"diagram","type":"bar","rows":[]}\n```'
        assert cli.md_to_v2_page(md)["b"][0]["k"] == "chart"

    def test_unclosed_typed_fence_does_not_hang(self) -> None:
        page = cli.md_to_v2_page('```oku-chart\n{"type":"bar"')
        assert page["b"], "unclosed typed fence must still produce output"


# ---------- markdown string lint ----------


class TestMdStringLint:
    """_lint_md_string enforces the strict-GFM subset and audits HTML
    islands; glossary / ext-ref ids are collected for resolution."""

    def _codes(self, text: str, skip_prose: bool = False) -> list:
        issues, _, _, _ = cli._lint_md_string(text, skip_prose=skip_prose)
        return [c for _, c, _, _ in issues]

    def test_setext_heading_flagged(self) -> None:
        assert "setext-heading" in self._codes("Title\n=====")

    def test_ambiguous_hr_flagged(self) -> None:
        assert "ambiguous-hr" in self._codes("some text\n---")

    def test_hr_after_blank_ok(self) -> None:
        assert "ambiguous-hr" not in self._codes("text\n\n---")

    def test_lazy_continuation_flagged(self) -> None:
        assert "lazy-continuation" in self._codes("> quoted\nlazy line")

    def test_marked_blockquote_ok(self) -> None:
        assert "lazy-continuation" not in self._codes("> quoted\n> second line")

    def test_indented_code_flagged(self) -> None:
        assert "indented-code" in self._codes("para\n\n    indented code")

    def test_indented_list_marker_not_flagged(self) -> None:
        assert "indented-code" not in self._codes("- item\n\n    - nested")

    def test_html_island_audited_once_per_island(self) -> None:
        codes = self._codes("<div>\nhello\n</div>")
        assert codes.count("html-island") == 1

    def test_unlifted_fence_flagged(self) -> None:
        assert "fence-not-lifted" in self._codes("```oku-chart\n{bad\n```")

    def test_bare_fence_is_code_no_language_info(self) -> None:
        assert "code-no-language" in self._codes("```\nplain\n```")

    def test_glossary_and_extref_collected(self) -> None:
        _, _, gloss, xrefs = cli._lint_md_string("see [x](#g/iceberg) and [y](#x/spec)", skip_prose=False)
        assert gloss == ["iceberg"]
        assert xrefs == ["spec"]

    def test_refs_inside_fences_ignored(self) -> None:
        _, _, gloss, _ = cli._lint_md_string("```md\n[x](#g/iceberg)\n```", skip_prose=False)
        assert gloss == []

    def test_heading_ids_explicit_and_slugged(self) -> None:
        _, ids, _, _ = cli._lint_md_string("## A {#aa}\n\n### B C", skip_prose=False)
        assert [h for _, h in ids] == ["aa", "b-c"]

    def test_skip_prose_suppresses_breadcrumb(self) -> None:
        text = "fixed in round 5"
        assert "process-breadcrumb" in self._codes(text)
        assert "process-breadcrumb" not in self._codes(text, skip_prose=True)


# ---------- find_json_pages / .md walk ----------


class TestFindJsonPagesMd:
    """Markdown files anywhere under the docs root become first-class
    pages — including README / CHANGELOG / CLAUDE / LICENSE. Earlier
    revisions filtered those out; the policy is now include-by-default."""

    def test_md_under_root_included(self, tmp_path: Path) -> None:
        (tmp_path / "overview.md").write_text("# Overview\n\nbody", encoding="utf-8")
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "details.md").write_text("# Details", encoding="utf-8")
        pages = cli.find_json_pages(tmp_path)
        paths = sorted(str(p.relative_to(tmp_path)) for p, _ in pages)
        assert "overview.json" in paths, "top-level overview.md was not surfaced as a page"
        assert "notes/details.json" in paths

    def test_repo_meta_md_included(self, tmp_path: Path) -> None:
        """README / CLAUDE / CHANGELOG / LICENSE are surfaced as pages
        just like any other Markdown file. Authors who want them
        hidden should put them under a SKIP_DIRS subdir."""
        for name in ("README.md", "CLAUDE.md", "CHANGELOG.md", "LICENSE.md"):
            (tmp_path / name).write_text(f"# {name}", encoding="utf-8")
        (tmp_path / "real.md").write_text("# Real", encoding="utf-8")
        pages = cli.find_json_pages(tmp_path)
        paths = {str(p.relative_to(tmp_path)) for p, _ in pages}
        for name in ("README.md", "CLAUDE.md", "CHANGELOG.md", "LICENSE.md"):
            assert name.replace(".md", ".json") in paths, (
                f"{name} should now be surfaced as a page (include-by-default)"
            )
        assert "real.json" in paths

    def test_manifest_source_points_at_real_md(self, tmp_path: Path) -> None:
        """For md-derived pages, compute_manifest must report the .md
        file as the source (not the virtual .json path)."""
        (tmp_path / "overview.md").write_text("# Overview\n\nx", encoding="utf-8")
        manifest = cli.compute_manifest(tmp_path)
        entry = next((e for e in manifest["pages"] if e["path"] == "overview.html"), None)
        assert entry is not None
        assert entry["source"] == "overview.md"
