"""Filesystem-touching tests for the build helpers.

All work happens inside pytest's tmp_path, so these stay fast and don't
collide with the real repo's docs/ directory. The tests cover the three
artifact emitters and the page-text extraction used by Pagefind.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


from oku import cli


# ---------- find_json_pages / find_html_files ----------


def _write_page(path: Path, *, title: str = "A page", extra: dict | None = None) -> None:
    payload: dict = {"kind": "page", "title": title, "blocks": []}
    if extra:
        payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_html(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<!doctype html>\n", encoding="utf-8")


class TestFindHelpers:
    def test_find_json_pages_skips_kit_json(self, tmp_path: Path) -> None:
        # kit.json is a project-config file, not a page; the walker must skip it.
        _write_page(tmp_path / "docs" / "p1.json")
        (tmp_path / "kit.json").write_text('{"name": "X"}')
        pages = cli.find_json_pages(tmp_path)
        sources = {p.name for p, _ in pages}
        assert sources == {"p1.json"}

    def test_find_json_pages_skips_non_page_json(self, tmp_path: Path) -> None:
        # JSON that isn't kind: "page" — config blobs, data files — is skipped.
        _write_page(tmp_path / "docs" / "p1.json")
        (tmp_path / "docs" / "data.json").write_text('{"foo": "bar"}')
        pages = cli.find_json_pages(tmp_path)
        assert len(pages) == 1
        assert pages[0][0].name == "p1.json"

    def test_find_json_pages_skips_dist_and_kit_dirs(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "docs" / "p1.json")
        _write_page(tmp_path / "dist" / "site" / "p1.json")
        (tmp_path / "_oku").mkdir()
        _write_page(tmp_path / "_oku" / "schema-example.json")
        pages = cli.find_json_pages(tmp_path)
        assert {p.relative_to(tmp_path).as_posix() for p, _ in pages} == {"docs/p1.json"}

    def test_find_html_files_sorted(self, tmp_path: Path) -> None:
        for rel in ("b.html", "a.html", "sub/c.html"):
            _write_html(tmp_path / rel)
        out = cli.find_html_files(tmp_path)
        names = [p.name for p in out]
        assert names == sorted(names, key=str.lower)


# ---------- build_manifest ----------


class TestBuildManifest:
    def test_emits_only_json(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "a.json", title="Alpha")
        _write_page(tmp_path / "b.json", title="Beta")
        manifest = cli.build_manifest(tmp_path)
        assert manifest == tmp_path / "site-manifest.json"
        body = json.loads(manifest.read_text(encoding="utf-8"))
        assert body["schema_version"] == 1
        titles = {entry["title"] for entry in body["pages"]}
        assert titles == {"Alpha", "Beta"}
        # No .js companion — the runtime falls back to inline
        # window.__okuManifest (shipped in every standalone HTML)
        # or to a fresh fetch on each request.
        assert not (tmp_path / "site-manifest.js").exists()

    def test_entries_include_meta_fields_when_present(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path / "a.json",
            title="Alpha",
            extra={"meta": {"order": 1, "summary": "The first page"}},
        )
        manifest = cli.build_manifest(tmp_path)
        body = json.loads(manifest.read_text(encoding="utf-8"))
        entry = body["pages"][0]
        assert entry["order"] == 1
        assert entry["summary"] == "The first page"

    def test_parent_is_null_for_root_pages(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "a.json")
        body = json.loads(cli.build_manifest(tmp_path).read_text(encoding="utf-8"))
        assert body["pages"][0]["parent"] is None

    def test_parent_is_dirname_for_nested(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "guide" / "intro.json")
        body = json.loads(cli.build_manifest(tmp_path).read_text(encoding="utf-8"))
        assert body["pages"][0]["parent"] == "guide"


# ---------- build_llms_txt ----------


class TestBuildLlmsTxt:
    def test_emits_pages_section_with_links(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "a.json", title="Alpha")
        _write_page(tmp_path / "b.json", title="Beta")
        out = cli.build_llms_txt(tmp_path)
        text = out.read_text(encoding="utf-8")
        assert "## Pages" in text
        assert "- [Alpha](a.html)" in text
        assert "- [Beta](b.html)" in text

    def test_includes_summary_when_present(self, tmp_path: Path) -> None:
        _write_page(
            tmp_path / "a.json",
            title="Alpha",
            extra={"meta": {"summary": "First page"}},
        )
        text = cli.build_llms_txt(tmp_path).read_text(encoding="utf-8")
        assert "- [Alpha](a.html): First page" in text

    def test_uses_kit_json_name_and_description(self, tmp_path: Path) -> None:
        (tmp_path / "kit.json").write_text(
            json.dumps({"name": "MyDocs", "description": "A test kit"})
        )
        _write_page(tmp_path / "a.json")
        text = cli.build_llms_txt(tmp_path).read_text(encoding="utf-8")
        assert text.startswith("# MyDocs")
        assert "> A test kit" in text


# ---------- build_markdown_twins ----------


class TestBuildMarkdownTwins:
    def test_writes_md_alongside_each_page(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "a.json", title="Alpha")
        _write_page(tmp_path / "sub" / "b.json", title="Beta")
        count = cli.build_markdown_twins(tmp_path)
        assert count == 2
        assert (tmp_path / "a.md").exists()
        assert (tmp_path / "sub" / "b.md").exists()

    def test_md_starts_with_h1_title(self, tmp_path: Path) -> None:
        _write_page(tmp_path / "a.json", title="Alpha")
        cli.build_markdown_twins(tmp_path)
        text = (tmp_path / "a.md").read_text(encoding="utf-8")
        assert text.startswith("# Alpha\n")

    def test_returns_zero_when_no_pages(self, tmp_path: Path) -> None:
        assert cli.build_markdown_twins(tmp_path) == 0


# ---------- extract_page_text ----------


class TestExtractPageText:
    def test_pulls_title_subtitle_summary(self) -> None:
        page = {
            "kind": "page",
            "title": "Alpha",
            "meta": {"subtitle": "Sub", "summary": "Sum"},
            "blocks": [],
        }
        text = cli.extract_page_text(page)
        assert "Alpha" in text
        assert "Sub" in text
        assert "Sum" in text

    def test_strips_inline_html(self) -> None:
        page = {
            "kind": "page",
            "title": "Alpha",
            "blocks": [
                {"kind": "paragraph", "content": "Hello <strong>world</strong>"},
            ],
        }
        text = cli.extract_page_text(page)
        assert "<strong>" not in text
        assert "world" in text

    def test_collapses_whitespace(self) -> None:
        page = {
            "kind": "page",
            "title": "Alpha",
            "blocks": [{"kind": "paragraph", "content": "foo\n\n   bar"}],
        }
        text = cli.extract_page_text(page)
        assert re.search(r"\s{2,}", text) is None


# ---------- inject_pagefind_body ----------


class TestInjectPagefindBody:
    def test_inserts_before_body_close(self) -> None:
        html = "<html><body><h1>Hi</h1></body></html>"
        out = cli.inject_pagefind_body(html, "indexable text", "Title")
        assert "data-pagefind-body" in out
        assert "indexable text" in out
        # The block lands before </body>, not after.
        idx_block = out.index("data-pagefind-body")
        idx_close = out.index("</body>")
        assert idx_block < idx_close

    def test_escapes_lt_in_text(self) -> None:
        out = cli.inject_pagefind_body("<body></body>", "1 < 2", "T")
        # The unescaped "<" would close the hidden div or worse.
        assert "1 &lt; 2" in out
        assert "1 < 2" not in out.replace("&lt;", "")

    def test_appends_when_no_body_close(self) -> None:
        # Defensive: a malformed input (no </body>) still gets the body
        # appended at the end rather than silently dropping it.
        original = "<div>only</div>"
        out = cli.inject_pagefind_body(original, "x", "T")
        assert "data-pagefind-body" in out
        # Original content is preserved and the indexable block lands after it.
        assert out.startswith(original)
