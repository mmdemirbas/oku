"""What the build actually writes into the two trees it ships.

Both bugs here were invisible from inside: the build succeeded, every
page rendered, and the missing thing was only missing where nobody
looked — in the search index, and on the one page of a tree that has no
markdown behind it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from oku import cli

PAGE_MD = """---
title: Compaction
summary: How compaction rewrites small files.
---

> [!TLDR]
> Small files cost more than the rows in them.

## What compaction does {#does}

Compaction rewrites many small data files into fewer large ones, so a
scan opens fewer handles and reads longer runs.

```oku-chart
{"type":"bar","rows":[{"label":"before","value":60},{"label":"after","value":12}]}
```

## When to run it {#when}

After a burst of streaming writes, or when the manifest count climbs.
"""


def _build(tmp_path: Path, sources: dict[str, str], stub_manifest: dict | None = None) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    for rel, text in sources.items():
        (docs / rel).write_text(text, encoding="utf-8")
    (docs / "index.html").write_text(
        cli._stub_for("Home", inline_manifest=stub_manifest) if stub_manifest else cli._stub_for("Home"),
        encoding="utf-8",
    )
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    return docs / "dist"


# ---------- the search index ----------


def test_a_page_indexes_its_body_not_just_its_title(tmp_path: Path) -> None:
    """extract_page_text walked `blocks`, the v1 key. Every page written
    since the format changed keeps them under `b`, so the walker got an
    empty list and Pagefind indexed a title. docs/charts.md: 118 blocks,
    182 characters extracted."""
    page = cli.md_to_v2_page(PAGE_MD, Path("compaction.md"))
    text = cli.extract_page_text(page)

    assert "rewrites many small data files" in text, text[:200]
    assert "manifest count climbs" in text, text[:200]
    assert len(text) > 300, f"only {len(text)} characters came out: {text!r}"


def test_the_index_skips_the_json_payload_of_a_typed_fence(tmp_path: Path) -> None:
    """A reader searching for `rows` wants the word, not the key of a
    chart payload."""
    text = cli.extract_page_text(cli.md_to_v2_page(PAGE_MD, Path("compaction.md")))
    assert '"type"' not in text and '"rows"' not in text, text


def test_the_built_site_page_carries_that_text_for_pagefind(tmp_path: Path) -> None:
    dist = _build(tmp_path, {"compaction.md": PAGE_MD})
    html = (dist / "site" / "compaction.html").read_text(encoding="utf-8")
    m = re.search(r"data-pagefind-body[^>]*>(.*?)</div>", html, re.S)
    assert m, "no pagefind body in the built page"
    body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
    assert "rewrites many small data files" in body, body[:200]


# ---------- the entry stub ----------
#
# `oku init` writes docs/index.html with a manifest inlined AT THAT
# MOMENT. Every injection in build_standalone sat behind `if data_text:`,
# and an entry stub has no .md behind it — so the front page of a
# delivered tree kept whatever tree `oku init` last saw and got none of
# the rest either. Measured on a delivered tree: index.html listed three
# pages, every other page in the same build listed four.

STALE = {
    "schema_version": 1,
    "root": ".",
    "pages": [{"path": "compaction.html", "source": "compaction.md", "title": "Compaction", "parent": None}],
}


def _last_inline_manifest(html: str) -> dict:
    blobs = re.findall(r"window\.__okuManifest\s*=\s*(\{.*?\});", html, re.S)
    assert blobs, "no inline manifest in the built page"
    return json.loads(blobs[-1])


def test_the_entry_stub_gets_the_manifest_of_this_build(tmp_path: Path) -> None:
    dist = _build(
        tmp_path,
        {"compaction.md": PAGE_MD, "deletes.md": PAGE_MD.replace("Compaction", "Deletes")},
        stub_manifest=STALE,
    )
    manifest = _last_inline_manifest((dist / "standalone" / "index.html").read_text(encoding="utf-8"))
    paths = sorted(p["path"] for p in manifest["pages"])

    assert "deletes.html" in paths, f"the entry page still carries the manifest `oku init` wrote: {paths}"
    assert "compaction.html" in paths, paths


def test_the_entry_stub_gets_the_rest_of_the_standalone_injections(tmp_path: Path) -> None:
    """The manifest was the visible half. The stub was skipping the whole
    block: vendor base, kit bundle, string table, inlined .md sources."""
    dist = _build(tmp_path, {"compaction.md": PAGE_MD}, stub_manifest=STALE)
    html = (dist / "standalone" / "index.html").read_text(encoding="utf-8")

    # The ASSIGNMENT, not the name: chrome.js is inlined into this file
    # and reads `window.__okuVendorBase` itself, so a substring test for
    # the name passes on a page that was given nothing.
    assert re.search(r'window\.__okuVendorBase\s*=\s*"', html), (
        "no vendor base assigned — mermaid and Prism resolve nowhere"
    )


def test_a_page_with_a_source_still_gets_them(tmp_path: Path) -> None:
    dist = _build(tmp_path, {"compaction.md": PAGE_MD}, stub_manifest=STALE)
    html = (dist / "standalone" / "compaction.html").read_text(encoding="utf-8")

    assert "__oku_page__" in html, "the page data stopped being inlined"
    assert "__okuVendorBase" in html
    assert "compaction.html" in json.dumps(_last_inline_manifest(html))
