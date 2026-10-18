"""A `.md` link to a note outside the tree being built opens the note.

The renderer makes every relative `.md` link `.html`, because a page of
the tree sits beside it as `.html`. A note outside the tree is built by
nobody, so a report in `raporlar/` linking `../arastirma/not.md` sent
the reader to a page that does not exist, in both built trees, and
`oku check` said nothing. Built or served, such a link is a `#f/` file:
the note opens in the viewer with its bytes carried in the page. `oku
pack` keeps making it a page of the package, scans and all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oku import cli, pack

REPORT = """---
title: Rapor
---

Notlar: [not](../arastirma/not.md), [başlığı](../arastirma/not.md#kanit), [alt sayfa](alt.md).

Kodda olan link değildir: `[kod](../arastirma/not.md)`.

```md
[blok](../arastirma/not.md)
```
"""


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / "arastirma").mkdir()
    (proj / "arastirma" / "not.md").write_text(
        "# Not\n\nKanıt burada.\n\n![tarama](tara.png)\n", encoding="utf-8"
    )
    (proj / "arastirma" / "tara.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    docs = proj / "raporlar"
    docs.mkdir()
    (docs / "rapor.md").write_text(REPORT, encoding="utf-8")
    (docs / "alt.md").write_text("# Alt\n", encoding="utf-8")
    return docs


def _built(docs: Path, name: str = "rapor") -> dict:
    return next(page for path, page in cli.find_json_pages(docs) if path.stem == name)


def test_a_link_out_of_the_tree_becomes_the_note_in_the_viewer(tree: Path) -> None:
    page = _built(tree)
    prose = "\n".join(cli._iter_strings(page["b"]))
    assert "[not](#f/../arastirma/not.md)" in prose
    # The viewer opens a file at its top; the heading is not a place in a file.
    assert "[başlığı](#f/../arastirma/not.md)" in prose
    assert "Kanıt burada." in page["m"]["_files"]["../arastirma/not.md"]["text"]


def test_a_link_inside_the_tree_and_code_are_left_alone(tree: Path) -> None:
    prose = "\n".join(cli._iter_strings(_built(tree)["b"]))
    assert "[alt sayfa](alt.md)" in prose
    assert "`[kod](../arastirma/not.md)`" in prose
    assert "[blok](../arastirma/not.md)\n```" in prose


@pytest.mark.parametrize(
    "link, why",
    [("../arastirma/yok.md", "missing"), ("../../../dis.md", "past the project")],
)
def test_a_link_with_nothing_to_carry_is_left_as_written(tree: Path, link: str, why: str) -> None:
    (tree.parent.parent / "dis.md").write_text("# Dış\n", encoding="utf-8")
    (tree / "rapor.md").write_text(f"---\ntitle: R\n---\n\n[x]({link})\n", encoding="utf-8")
    assert f"[x]({link})" in "\n".join(cli._iter_strings(_built(tree)["b"])), why


def test_a_link_to_a_page_of_the_tree_stays_a_page_link(tree: Path) -> None:
    """Built from the project root, the note IS a page of the tree."""
    prose = "\n".join(cli._iter_strings(_built(tree.parent)["b"]))
    assert "[not](../arastirma/not.md)" in prose


def test_pack_still_makes_the_note_a_page_with_its_scan(tree: Path) -> None:
    (tree / "rapor.md").write_text("---\ntitle: R\n---\n\n[not](../arastirma/not.md)\n", encoding="utf-8")
    out = tree.parent.parent / "paket"
    assert pack.run([str(tree / "rapor.md")], str(out)) == 0
    index = json.loads((out / "_pack.json").read_text(encoding="utf-8"))
    assert "arastirma/not.html" in [p["path"] for p in index["pages"]]
    assert (out / "arastirma" / "tara.png").is_file()
