"""A file the viewer shows carries its own images, by its own place.

A page carries the files its `#f/` chips name (`m._files`) and the files
those name (`m._files_more`), so the viewer can show them where nothing
can be fetched. Their images were never carried by their own place: the
build walked the whole page dict, carried text included, and resolved an
image a note names against the PAGE's directory. Two failures came of
it, measured on a two-file tree:

  - the note's text was rewritten: `(img/dot.svg)` became the data: URI
    of the page's own `img/dot.svg`, so the viewer's source view showed a
    file that is not on disk, and its rendered view showed the page's
    picture wherever the two directories hold a file of the same name;
  - an image beside the note and nowhere else was carried by nothing.

Now a carried file's text is the file, byte for byte, and its images go
in `m._file_assets`, keyed by their place in the project, which is what
the viewer looks them up by.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

import pytest

from oku import cli

PAGE_DOT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
)
NOTE_DOT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30"><rect width="30" height="30"/></svg>'
)
DEEP = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"><rect width="50" height="50"/></svg>'

NOTE = (
    "---\ntitle: Note\n---\n\n## Note {#note}\n\n"
    "Its own dot: ![note dot](img/dot.svg)\n\n"
    "And further: [`deeper.md`](#f/deeper.md)\n\n"
    "Outside the project: ![far](../../../outside.svg)\n\n"
    "A sample, not a reference: `![x](img/dot.svg)`\n"
)
DEEPER = "---\ntitle: Deeper\n---\n\n## Deeper {#deeper}\n\n![deep](../../shots/deep.svg)\n"


def make_project(tmp_path: Path) -> Path:
    """The tree both halves read: the browser half builds it too."""
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    docs = root / "docs"
    (docs / "img").mkdir(parents=True)
    (docs / "notes" / "img").mkdir(parents=True)
    (root / "shots").mkdir()
    (docs / "img" / "dot.svg").write_text(PAGE_DOT, encoding="utf-8")
    (docs / "notes" / "img" / "dot.svg").write_text(NOTE_DOT, encoding="utf-8")
    (root / "shots" / "deep.svg").write_text(DEEP, encoding="utf-8")
    (tmp_path / "outside.svg").write_text(DEEP, encoding="utf-8")
    (docs / "notes" / "note.md").write_text(NOTE, encoding="utf-8")
    (docs / "notes" / "deeper.md").write_text(DEEPER, encoding="utf-8")
    (docs / "index.md").write_text(
        "---\ntitle: Index\n---\n\n## One {#one}\n\n"
        "The page's own dot: ![page dot](img/dot.svg)\n\n"
        "A note: [`note.md`](#f/notes/note.md)\n",
        encoding="utf-8",
    )
    (docs / "index.html").write_text(cli._stub_for("Index"), encoding="utf-8")
    return root


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    return make_project(tmp_path)


def _build(project: Path) -> Path:
    docs = project / "docs"
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


def _built_page(dist: Path, tree: str) -> dict:
    if tree == "site":
        return json.loads((dist / "site" / "index.json").read_text(encoding="utf-8"))
    html = (dist / "standalone" / "index.html").read_text(encoding="utf-8")
    body = html.split('id="__oku_page__">', 1)[1].split("</script>", 1)[0]
    return json.loads(body.replace("<\\/script", "</script"))


def _svg(uri: str) -> str:
    head, _, data = uri.partition(",")
    assert head == "data:image/svg+xml;base64", head
    return base64.b64decode(data).decode("utf-8")


@pytest.mark.parametrize("tree", ["standalone", "site"])
def test_a_carried_files_text_is_the_file(project: Path, tree: str) -> None:
    """The viewer's source view shows `text`, so it has to be what is on
    disk. The page shows an image of the same relative name, which is
    what the page-wide rewrite matched the note's reference against."""
    m = _built_page(_build(project), tree)["m"]
    assert m["_files"]["notes/note.md"]["text"] == NOTE
    assert m["_files_more"]["docs/notes/deeper.md"]["text"] == DEEPER


def test_the_pages_own_image_is_still_carried(project: Path) -> None:
    """The other half of the rewrite, which must keep working."""
    blocks = json.dumps(_built_page(_build(project), "standalone")["b"])
    assert "img/dot.svg" not in blocks
    assert base64.b64encode(PAGE_DOT.encode()).decode() in blocks


def _assets(project: Path) -> dict[str, str]:
    return cli._page_from_source_file(project / "docs" / "index.md")["m"].get("_file_assets", {})


def test_an_image_is_carried_by_the_place_of_the_file_that_names_it(project: Path) -> None:
    """The note's `img/dot.svg` is the one beside the note, not the one
    beside the page. Keyed by place, as `_files_more` is, because the
    same string names a different file from each directory."""
    assets = _assets(project)
    assert _svg(assets["docs/notes/img/dot.svg"]) == NOTE_DOT
    assert "docs/img/dot.svg" not in assets


def test_a_file_a_carried_file_names_carries_its_images_too(project: Path) -> None:
    """deeper.md is in `_files_more`; its image sits above the docs tree
    and inside the project, which is the fence a carried file answers to."""
    assert _svg(_assets(project)["shots/deep.svg"]) == DEEP


def test_an_image_outside_the_project_is_not_carried(project: Path) -> None:
    assets = _assets(project)
    assert not [k for k in assets if k.startswith("..")], sorted(assets)
    assert set(assets) == {"docs/notes/img/dot.svg", "shots/deep.svg"}, sorted(assets)


def test_the_budget_drops_the_furthest_first(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "MAX_FILE_ASSET_BYTES", len(NOTE_DOT))
    assert set(_assets(project)) == {"docs/notes/img/dot.svg"}


def test_an_image_over_the_inline_cap_is_not_carried(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "MAX_INLINE_ASSET_BYTES", len(NOTE_DOT))
    assert set(_assets(project)) == {"docs/notes/img/dot.svg"}
