"""A page whose filename is awkward is still a page you can reach.

Every manifest `path` becomes an href, and every href is compared
against `location.pathname`, which the browser hands back
percent-encoded. Left raw:

- `notes#1.md` built into `notes#1.html`, and the href pointed at
  `notes` with the fragment `1`. The page existed, was written, was
  indexed, and no row in the tree could reach it.
- `what?.md` did the same with a query string.
- `a b.md` ended the target of the markdown link in llms.txt at the
  space, so the rest of the filename was read as a link title.

None of it failed. `oku build` printed the files, `oku check` passed,
and the tree drew a row per page — the rows just went nowhere.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

import pytest

from oku import cli

PAGE = "---\ntitle: {title}\nsummary: A page with an awkward name.\n---\n\n## X {{#x}}\n\nBody.\n"

AWKWARD = ["notes#1.md", "what?.md", "a b.md", "100%.md", "one&two.md"]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    cli._project_root_cache.clear()
    cli._tree_defaults_cache.clear()
    docs = tmp_path / "docs"
    (docs / "sub#dir").mkdir(parents=True)
    (docs / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (docs / "index.md").write_text(PAGE.format(title="Index"), encoding="utf-8")
    for name in AWKWARD:
        (docs / name).write_text(PAGE.format(title=Path(name).stem), encoding="utf-8")
    (docs / "sub#dir" / "deep.md").write_text(PAGE.format(title="Deep"), encoding="utf-8")
    return docs


def _manifest(docs: Path) -> dict:
    cwd = Path.cwd()
    os.chdir(docs)
    real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        sys.stdout = real
        os.chdir(cwd)
    return json.loads((docs / "dist" / "site" / "site-manifest.json").read_text(encoding="utf-8"))


def test_no_manifest_path_carries_a_url_delimiter(tree: Path) -> None:
    """`#` starts a fragment and `?` starts a query. Either one in a
    path means the href names a different resource than the file."""
    bad = [p["path"] for p in _manifest(tree)["pages"] if set("#? ") & set(p["path"])]
    assert bad == [], bad


def test_the_encoded_path_decodes_back_to_the_file_on_disk(tree: Path) -> None:
    """The server unquotes what the browser sends, so the round trip is
    the whole contract — an encoding that does not come back is a 404
    with extra steps."""
    from urllib.parse import unquote

    site = tree / "dist" / "site"
    for page in _manifest(tree)["pages"]:
        assert (site / unquote(page["path"])).is_file(), page["path"]


def test_a_directory_and_the_rows_under_it_are_spelled_the_same(tree: Path) -> None:
    """A path and the parent it groups under are compared as strings.
    Encode one and not the other and the row keeps its href and loses
    its place in the tree."""
    pages = {p["path"]: p for p in _manifest(tree)["pages"]}
    deep = pages["sub%23dir/deep.html"]
    assert deep["parent"] == "sub%23dir", deep


def test_an_author_pinned_parent_is_encoded_once(tmp_path: Path) -> None:
    """`path_parent` is already in URL space and an author's own
    `parent` is not. Running both through the encoder is how `sub#dir`
    became `sub%2523dir` and took every row under it out of the tree."""
    cli._project_root_cache.clear()
    cli._tree_defaults_cache.clear()
    docs = tmp_path / "docs"
    (docs / "sub#dir").mkdir(parents=True)
    (docs / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (docs / "sub#dir" / "deep.md").write_text(PAGE.format(title="Deep"), encoding="utf-8")
    (docs / "pinned.md").write_text(
        "---\ntitle: Pinned\nsummary: s\nparent: sub#dir\n---\n\n## X {#x}\n\nBody.\n", encoding="utf-8"
    )
    parents = {p["path"]: p.get("parent") for p in _manifest(docs)["pages"]}
    assert parents["pinned.html"] == "sub%23dir", parents
    assert parents["sub%23dir/deep.html"] == "sub%23dir", parents


def test_an_ordinary_name_is_left_exactly_as_it_was(tree: Path) -> None:
    """The encoder runs on every path, not only the awkward ones, so
    the thing that must not change is every existing project."""
    paths = [p["path"] for p in _manifest(tree)["pages"]]
    assert "index.html" in paths, paths


def test_llms_txt_links_survive_a_space(tree: Path) -> None:
    """A bare markdown target ends at the first space, so `(a b.html)`
    is a link to `a` with the title `b.html`."""
    _manifest(tree)
    text = (tree / "dist" / "site" / "llms.txt").read_text(encoding="utf-8")
    targets = [line.split("](", 1)[1].split(")", 1)[0] for line in text.split("\n") if line.startswith("- [")]
    assert targets, text
    assert not any(" " in t for t in targets), targets


def test_the_source_field_still_names_the_file_you_would_open(tree: Path) -> None:
    """`source` is for a human with an editor, not for a browser. An
    encoded path there is one the reader has to decode by hand."""
    sources = [p.get("source") for p in _manifest(tree)["pages"]]
    assert "notes#1.md" in sources, sources
