"""Edge cases for the pure helpers: unicode, deep nesting, malformed
inputs, empty data.

These don't add coverage by themselves — the happy-path tests in
test_pure.py already exercise the code. They harden against regressions
in the value/error boundaries that aren't obvious from the prose
contracts.
"""

from __future__ import annotations

import json
from pathlib import Path

from html_doc import cli


# ---------- Unicode ----------


def test_flatten_inline_passes_unicode_unchanged() -> None:
    # The kit ships TR + EN content; non-ASCII must round-trip cleanly.
    assert cli._flatten_inline("İstanbul · 京都") == "İstanbul · 京都"
    assert cli._flatten_inline({"kind": "strong", "text": "ölçü"}) == "**ölçü**"


def test_render_page_markdown_unicode_title() -> None:
    page = {"kind": "page", "title": "Yöneylem 中文", "blocks": []}
    md = cli.render_page_markdown(page)
    assert md.startswith("# Yöneylem 中文")


def test_inject_pagefind_body_preserves_unicode() -> None:
    out = cli.inject_pagefind_body("<body></body>", "İstanbul", "Başlık")
    assert "İstanbul" in out
    assert "Başlık" in out


def test_build_manifest_with_unicode_titles(tmp_path: Path) -> None:
    (tmp_path / "p1.json").write_text(
        json.dumps({"kind": "page", "title": "Şehir", "blocks": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    path = cli.build_manifest(tmp_path)
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["pages"][0]["title"] == "Şehir"
    # The .js companion preserves Unicode too (no ensure_ascii=True hack).
    js = (tmp_path / "site-manifest.js").read_text(encoding="utf-8")
    assert "Şehir" in js


# ---------- Deep nesting ----------


def test_flatten_inline_deep_list_does_not_overflow() -> None:
    # 200 levels of nested lists. _flatten_inline recurses — verify it
    # doesn't hit Python's default recursion limit.
    node: list = ["leaf"]
    for _ in range(200):
        node = [node]
    assert cli._flatten_inline(node) == "leaf"


def test_md_block_section_with_deep_nested_sections() -> None:
    # Nested sections (used in long-form pages). The recursive emitter
    # walks every level.
    inner: dict = {"kind": "section", "id": "deep", "title": "Deep", "blocks": [
        {"kind": "paragraph", "content": "Innermost"}
    ]}
    for i in range(5):
        inner = {"kind": "section", "id": f"s{i}", "title": f"S{i}", "blocks": [inner]}
    out = "\n".join(cli._md_block(inner))
    assert "Innermost" in out
    # Each level emits its own ## header.
    assert out.count("## ") >= 5


# ---------- Empty / minimal inputs ----------


def test_flatten_inline_empty_string() -> None:
    assert cli._flatten_inline("") == ""


def test_flatten_inline_empty_list() -> None:
    assert cli._flatten_inline([]) == ""


def test_md_block_empty_dict_returns_placeholder() -> None:
    # Defensive: a {} block (no kind) shouldn't crash; falls through to
    # the "_[block]_" placeholder branch.
    out = cli._md_block({})
    assert out == ["_[block]_"]


def test_render_page_markdown_empty_blocks() -> None:
    md = cli.render_page_markdown({"kind": "page", "title": "T", "blocks": []})
    assert md.strip() == "# T"


def test_build_manifest_no_pages_writes_empty_manifest(tmp_path: Path) -> None:
    # An empty docs dir still produces a parseable manifest with no
    # pages, so the runtime <page-nav> shows "no entries" rather than
    # 404'ing.
    out = cli.build_manifest(tmp_path)
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["pages"] == []
    assert body["schema_version"] == 1


def test_build_llms_txt_no_pages_still_has_header(tmp_path: Path) -> None:
    text = cli.build_llms_txt(tmp_path).read_text(encoding="utf-8")
    # The "# <project>" header lives in the output even with no pages.
    assert text.startswith("# ")
    assert "## Pages" in text


# ---------- Malformed / invalid inputs ----------


def test_find_json_pages_skips_malformed_json(tmp_path: Path) -> None:
    (tmp_path / "ok.json").write_text(
        json.dumps({"kind": "page", "title": "OK", "blocks": []}), encoding="utf-8"
    )
    (tmp_path / "broken.json").write_text("{not valid", encoding="utf-8")
    pages = cli.find_json_pages(tmp_path)
    names = {p.name for p, _ in pages}
    assert names == {"ok.json"}


def test_build_markdown_twins_handles_unparseable_sibling(tmp_path: Path) -> None:
    # find_json_pages skips bad files, so the twin generator only sees
    # parseable ones. The bad one shouldn't crash the run.
    (tmp_path / "ok.json").write_text(
        json.dumps({"kind": "page", "title": "OK", "blocks": []}), encoding="utf-8"
    )
    (tmp_path / "broken.json").write_text("{not valid", encoding="utf-8")
    count = cli.build_markdown_twins(tmp_path)
    assert count == 1
    assert (tmp_path / "ok.md").exists()
    assert not (tmp_path / "broken.md").exists()


def test_extract_page_text_handles_non_dict_blocks() -> None:
    # Some authored pages have stray strings or None in a blocks list;
    # the walker should not crash.
    page = {
        "kind": "page",
        "title": "T",
        "blocks": ["stray string", None, {"kind": "paragraph", "content": "real"}],
    }
    text = cli.extract_page_text(page)
    assert "real" in text


def test_md_block_chart_without_title_uses_kind_fallback() -> None:
    out = cli._md_block({"kind": "chart"})
    # No explicit title — emit a placeholder that names the kind.
    assert out == ["_[chart: chart]_"]


# ---------- Group/iv preservation ----------


def test_md_block_table_with_pipe_in_cell_escapes_correctly() -> None:
    out = cli._md_block({
        "kind": "table",
        "headers": ["A"],
        "rows": [["x | y"]],
    })
    # A literal | inside a cell would break the markdown table — must escape.
    cell_row = next(line for line in out if line.startswith("| x"))
    assert "\\|" in cell_row


def test_md_block_table_with_newline_in_cell_collapses_to_space() -> None:
    out = cli._md_block({
        "kind": "table",
        "headers": ["A"],
        "rows": [["line1\nline2"]],
    })
    cell_row = next(line for line in out if line.startswith("| line"))
    assert "\n" not in cell_row
    assert "line1 line2" in cell_row
