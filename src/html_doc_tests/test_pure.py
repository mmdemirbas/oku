"""Tests for pure functions in html_doc.cli.

These don't touch the filesystem at all — fast, deterministic, and the
right surface to catch markdown-twin / target-picker / docs-dir regressions
before they ship.
"""

from __future__ import annotations

from pathlib import Path


from html_doc import cli


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


# ---------- Markdown link-href rewriting ----------


class TestMdLinkHref:
    """`[text](other.md)` style links must point at the rendered .html
    page; absolute URLs and fragments must pass through untouched."""

    def test_relative_md_link_rewritten(self) -> None:
        assert cli._md_link_href("other.md") == "other.html"

    def test_relative_md_link_with_fragment(self) -> None:
        assert cli._md_link_href("notes/details.md#thing") == "notes/details.html#thing"

    def test_parent_relative_md_link(self) -> None:
        assert cli._md_link_href("../sibling.md") == "../sibling.html"

    def test_absolute_url_passthrough(self) -> None:
        for href in (
            "https://example.com/x.md",
            "http://example.com/x.md",
            "mailto:foo@bar.md",
            "//cdn.example.com/x.md",
        ):
            assert cli._md_link_href(href) == href, f"absolute URL {href!r} should pass through"

    def test_fragment_only_passthrough(self) -> None:
        assert cli._md_link_href("#section") == "#section"

    def test_root_absolute_path_passthrough(self) -> None:
        # /a/b.md is a server-relative absolute path; leave it alone —
        # the kit can't know whether that maps to a rendered .html.
        assert cli._md_link_href("/docs/foo.md") == "/docs/foo.md"

    def test_non_md_passthrough(self) -> None:
        assert cli._md_link_href("other.html") == "other.html"
        assert cli._md_link_href("data.json") == "data.json"


# ---------- md_to_page integration ----------


class TestMdToPage:
    """End-to-end checks on md_to_page output shape."""

    def test_h1_becomes_title(self) -> None:
        page = cli.md_to_page("# Hello\n\nbody")
        assert page["kind"] == "page"
        assert page["title"] == "Hello"

    def test_h2_starts_a_section(self) -> None:
        page = cli.md_to_page("# X\n\nintro\n\n## First\n\nbody")
        ids = [b.get("id") for b in page["blocks"] if b.get("kind") == "section"]
        assert "intro" in ids, "implicit intro section missing"
        assert "first" in ids, "h2 'First' did not become a section with id='first'"

    def test_hr_is_dropped_not_emitted(self) -> None:
        """Markdown `---` produced `{"kind": "hr"}` which the schema
        rejects (no `hr` kind) and the renderer ignores. Drop it."""
        page = cli.md_to_page("## H\n\nbefore\n\n---\n\nafter\n")
        section = page["blocks"][0]
        kinds = [b["kind"] for b in section["blocks"]]
        assert "hr" not in kinds, "hr block leaked into output"
        # Surrounding paragraphs still present.
        assert kinds.count("paragraph") == 2

    def test_indented_blockquote_does_not_hang(self) -> None:
        """Regression: a `>` line indented (e.g., inside a list item)
        used to make the main loop never advance, because the dispatcher
        stripped whitespace before checking for ">" but ``take_blockquote``
        compared the raw line. Bisected from a real HANDOFF.md in 2026-05.
        Cap the parse with a soft time budget so a future regression
        surfaces as a test timeout, not a hung CI run."""
        import threading

        md = "## H\n- item:\n  > indented quote line\n"
        result: dict[str, object] = {}

        def go() -> None:
            result["page"] = cli.md_to_page(md)

        t = threading.Thread(target=go, daemon=True)
        t.start()
        t.join(timeout=2.0)
        assert not t.is_alive(), "md_to_page hung on indented blockquote"
        page = result["page"]
        assert isinstance(page, dict)
        assert page.get("kind") == "page"

    def test_md_link_in_paragraph_rewritten_to_html(self) -> None:
        """Live integration — the link rewriter must actually run on
        paragraph content emitted by md_to_page."""
        page = cli.md_to_page("# X\n\n## Sec\n\nSee [details](notes/details.md#thing).")
        # Walk to the link node.
        found = None
        def walk(node):
            nonlocal found
            if isinstance(node, dict):
                if node.get("kind") == "link":
                    found = node
                    return
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for it in node:
                    walk(it)
        walk(page)
        assert found is not None, "no link node emitted"
        assert found["href"] == "notes/details.html#thing"


# ---------- find_json_pages / project-meta exclusion ----------


class TestFindJsonPagesMd:
    """Markdown files anywhere under the docs root become first-class
    pages, except a small set of well-known project-meta filenames."""

    def test_md_under_root_included(self, tmp_path: Path) -> None:
        (tmp_path / "overview.md").write_text("# Overview\n\nbody", encoding="utf-8")
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "details.md").write_text("# Details", encoding="utf-8")
        pages = cli.find_json_pages(tmp_path)
        paths = sorted(str(p.relative_to(tmp_path)) for p, _ in pages)
        assert "overview.json" in paths, "top-level overview.md was not surfaced as a page"
        assert "notes/details.json" in paths

    def test_well_known_project_meta_excluded(self, tmp_path: Path) -> None:
        for name in ("README.md", "CLAUDE.md", "CHANGELOG.md", "LICENSE.md"):
            (tmp_path / name).write_text(f"# {name}", encoding="utf-8")
        (tmp_path / "real.md").write_text("# Real", encoding="utf-8")
        pages = cli.find_json_pages(tmp_path)
        paths = {str(p.relative_to(tmp_path)) for p, _ in pages}
        for name in ("README.md", "CLAUDE.md", "CHANGELOG.md", "LICENSE.md"):
            assert name.replace(".md", ".json") not in paths, (
                f"{name} should be excluded as project meta"
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
