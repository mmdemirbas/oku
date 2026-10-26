"""A `.md` link inside a viewed file goes where that file means it to go.

A note the page carries for a chip is shown in the viewer, and its own
`[sib](sib.md)` was drawn as `sib.html`, resolved against the PAGE's URL.
Measured on a note outside the docs tree: a click took the reader off the
page, to Chrome's error page in a standalone file and a 404 in dist/site
and under oku serve. Where the page had a `sib.md` of its own, the click
went to that page instead, which is a different file.

A link in a viewed file is resolved from the file's own place: a page of
the tree opens as that page, anything else opens in the viewer, and the
build carries those files by place, as it carries what the file's chips
name. This half holds the build; `browser/test_md_links_in_viewed_files.py`
holds the reader's side in all three delivery modes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli

NOTE = (
    "---\ntitle: Note\n---\n\n## Note {#note}\n\n"
    "Its sibling: [sib](sib.md)\n\n"
    "A page of the tree: [guide](../docs/guide.md#part)\n\n"
    '<p>Island links: <a href="island.md">island</a> and <a href="only-note.md">only</a></p>\n\n'
    "Nothing there: [gone](missing.md)\n\n"
    "A sample, not a link: `[x](sample.md)`\n"
)
NOTE_SIB = "---\ntitle: Note sibling\n---\n\n## S {#s}\n\nBeside the note.\n"
NOTE_ISLAND = "---\ntitle: Note island\n---\n\n## I {#i}\n\nBeside the note too.\n"
ONLY_NOTE = "---\ntitle: Only the note\n---\n\n## O {#o}\n\nNo page names this.\n"


def make_project(tmp_path: Path) -> Path:
    """The tree both halves read: the browser half builds it too."""
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    docs = root / "docs"
    notes = root / "notes"
    docs.mkdir()
    notes.mkdir()
    (docs / "index.md").write_text(
        "---\ntitle: Index\n---\n\n## One {#one}\n\n"
        "A note: [`note.md`](#f/../notes/note.md)\n\n"
        "The page's own: [sib](sib.md)\n\n"
        '<p>The page\'s island: <a href="island.md">island</a></p>\n',
        encoding="utf-8",
    )
    pages = {
        "sib": "---\ntitle: Page sibling\n---\n\n## P {#p}\n\nBeside the page.\n",
        "island": "---\ntitle: Page island\n---\n\n## PI {#pi}\n\nBeside the page too.\n",
        "guide": "---\ntitle: Guide\n---\n\n## Intro {#intro}\n\nText.\n\n## Part {#part}\n\nThe part.\n",
    }
    for stem, text in pages.items():
        (docs / f"{stem}.md").write_text(text, encoding="utf-8")
    for stem in ("index", *pages):
        (docs / f"{stem}.html").write_text(cli._stub_for(stem), encoding="utf-8")
    (notes / "note.md").write_text(NOTE, encoding="utf-8")
    (notes / "sib.md").write_text(NOTE_SIB, encoding="utf-8")
    (notes / "island.md").write_text(NOTE_ISLAND, encoding="utf-8")
    (notes / "only-note.md").write_text(ONLY_NOTE, encoding="utf-8")
    (notes / "sample.md").write_text("never carried\n", encoding="utf-8")
    return root


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    return make_project(tmp_path)


def _more(project: Path) -> dict[str, dict]:
    return cli._page_from_source_file(project / "docs" / "index.md")["m"].get("_files_more", {})


def test_a_viewed_files_md_links_travel_by_its_place(project: Path) -> None:
    """A prose link and an island link, each carried under the note's
    sibling's place, which is what the viewer looks the file up by."""
    more = _more(project)
    assert more["notes/sib.md"]["text"] == NOTE_SIB
    assert more["notes/island.md"]["text"] == NOTE_ISLAND
    assert more["notes/only-note.md"]["text"] == ONLY_NOTE


def test_a_link_in_code_or_to_nothing_is_not_carried(project: Path) -> None:
    more = _more(project)
    assert "notes/sample.md" not in more
    assert "notes/missing.md" not in more


def test_the_pages_linked_docs_are_only_the_pages_own(project: Path, capsys: pytest.CaptureFixture) -> None:
    """`__oku_local_docs__` is keyed by the PAGE's hrefs. It read the
    note's island links as the page's too, resolved them against the
    page's directory, and warned that `only-note.md` could not be
    inlined, about a file nobody asked it to inline."""
    docs = project / "docs"
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    assert "only-note.md" not in capsys.readouterr().out
    html = (docs / "dist" / "standalone" / "index.html").read_text(encoding="utf-8")
    body = html.split('id="__oku_local_docs__">', 1)[1].split("</script>", 1)[0]
    local = json.loads(body.replace("<\\/script", "</script"))
    assert local == {"island.md": (docs / "island.md").read_text(encoding="utf-8")}
