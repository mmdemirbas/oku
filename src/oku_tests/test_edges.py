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

from oku import cli


# ---------- Unicode ----------


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


# ---------- Markdown twin link rewriting ----------


# ---------- Deep nesting ----------


# ---------- Empty / minimal inputs ----------


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


# ---------- Group/iv preservation ----------
