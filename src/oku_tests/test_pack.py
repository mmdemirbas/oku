"""`oku pack`: the pages named, the pages they link, the files they name.

Built because sharing one page out of a tree leaked the tree. The site
manifest, llms.txt and the search index listed the titles of every page
beside it (fifty unrelated reports, for one shared one); a carried
markdown file kept the absolute paths it was written with; and a PDF a
`#f/` chip named was never carried, so the chip opened nothing.

Each test builds a small project and packs from it. The vendor fetch is
stubbed so these run without a network; the browser half, which needs
the real vendored kit, is `browser/test_pack_under_a_prefix.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from oku import cli, pack

ENTRY = """---
title: Entry page
summary: Where the package opens.
---

## The start {#start}

Read [the second page](second.md), the [manual](#f/../files/manual.pdf)
and the [notes](#f/../files/notes.md).

![A pixel](img/pixel.png)

- first **item**
- second item

| Name | Value |
|---|---|
| alpha | `one` |

```python
def hidden_from_text():
    pass
```
"""

SECOND = """---
title: Second page
summary: Reached by a link.
---

## Two {#two}

Back to [the entry](entry.md).
"""

SIBLING = """---
title: Zebra sibling that nobody links
summary: Must not appear anywhere in the package.
---

## Z {#z}

Alone.
"""

NOTES = "# Notes\n\nOrdinary notes.\n"
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
PNG = bytes.fromhex("89504e470d0a1a0a")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """The kit's vendor copy is the browser test's business; here a
    missing cache must not turn into a fetch, or into a finding."""
    monkeypatch.setattr(cli, "vendor_is_complete", lambda: True)
    monkeypatch.setattr(cli, "fetch_prism_langs", lambda names, quiet=False: ([], []))


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / "docs" / "img").mkdir(parents=True)
    (proj / "files").mkdir()
    (proj / "docs" / "entry.md").write_text(ENTRY, encoding="utf-8")
    (proj / "docs" / "second.md").write_text(SECOND, encoding="utf-8")
    (proj / "docs" / "sibling.md").write_text(SIBLING, encoding="utf-8")
    (proj / "docs" / "img" / "pixel.png").write_bytes(PNG)
    (proj / "files" / "manual.pdf").write_bytes(PDF)
    (proj / "files" / "notes.md").write_text(NOTES, encoding="utf-8")
    return proj


def _pack(project: Path, *pages: str, out: Path | None = None) -> tuple[int, Path]:
    out = out or project.parent / "out"
    rc = pack.run([str(project / "docs" / p) for p in (pages or ("entry.md",))], str(out))
    return rc, out


def _files(out: Path) -> dict[str, bytes]:
    return {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}


class TestTheClosure:
    def test_a_linked_page_is_packed(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        assert (out / "docs" / "second.html").is_file()
        assert (out / "docs" / "second.json").is_file()
        manifest = json.loads((out / "site-manifest.json").read_text(encoding="utf-8"))
        assert [e["title"] for e in manifest["pages"]] == ["Entry page", "Second page"]

    def test_an_unlinked_sibling_appears_in_no_output_file(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        leaked = [
            rel for rel, data in _files(out).items() if b"Zebra sibling" in data or b"sibling.md" in data
        ]
        assert leaked == []
        assert not any("sibling" in rel for rel in _files(out))

    def test_index_html_forwards_to_the_first_entry(self, project: Path) -> None:
        rc, out = _pack(project, "second.md", "entry.md")
        assert rc == 0
        door = (out / "index.html").read_text(encoding="utf-8")
        assert 'http-equiv="refresh" content="0; url=docs/second.html"' in door
        assert "<script" not in door
        assert json.loads((out / "_pack.json").read_text(encoding="utf-8"))["entry"] == "docs/second.html"


class TestCarriedFiles:
    def test_a_linked_pdf_is_carried_and_its_chip_resolves(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        page = json.loads((out / "docs" / "entry.json").read_text(encoding="utf-8"))
        ref = page["m"]["_files"]["../files/manual.pdf"]
        assert ref["kind"] == "pdf"
        target = (out / "docs" / ref["url"]).resolve()
        assert target == (out / "files" / "manual.pdf").resolve()
        assert target.read_bytes() == PDF

    def test_an_image_is_a_file_beside_the_page(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        assert (out / "docs" / "img" / "pixel.png").read_bytes() == PNG

    def test_no_payload_names_a_path_on_this_machine(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        home = str(Path.home()).encode()
        tmp = str(project.parent).encode()
        assert [rel for rel, data in _files(out).items() if home in data or tmp in data] == []

    def test_the_rebuild_command_stays_home(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        manifest = json.loads((out / "site-manifest.json").read_text(encoding="utf-8"))
        assert "cmd" not in manifest["build"]
        assert json.loads((out / "kit.json").read_text(encoding="utf-8"))["rebuild_command"] is False


class TestThePackIndex:
    def test_shape(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        index = json.loads((out / "_pack.json").read_text(encoding="utf-8"))
        assert index["pack"] == 1
        assert index["entry"] == "docs/entry.html"
        assert (index["title"], index["summary"]) == ("Entry page", "Where the package opens.")
        assert [p["path"] for p in index["pages"]] == ["docs/entry.html", "docs/second.html"]
        first = index["pages"][0]
        assert set(first) == {"path", "title", "summary", "lang", "text"}
        assert first["lang"] == "en"

    def test_text_is_the_words_without_the_markup(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        text = json.loads((out / "_pack.json").read_text(encoding="utf-8"))["pages"][0]["text"]
        for words in ("The start", "Read the second page, the manual", "first item", "alpha\tone"):
            assert words in text, text
        for markup in ("**", "](", "|", "##", "{#", "hidden_from_text"):
            assert markup not in text, (markup, text)

    def test_files_lists_the_directory_exactly(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        index = json.loads((out / "_pack.json").read_text(encoding="utf-8"))
        on_disk = _files(out)
        del on_disk["_pack.json"]
        assert [f["path"] for f in index["files"]] == sorted(on_disk)
        for f in index["files"]:
            data = on_disk[f["path"]]
            assert f["bytes"] == len(data)
            assert f["sha256"] == hashlib.sha256(data).hexdigest()
        types = {f["path"]: f["type"] for f in index["files"]}
        assert types["files/manual.pdf"] == "application/pdf"
        assert types["docs/entry.html"] == "text/html"
        assert types["docs/entry.md"] == "text/markdown"


class TestTheLeakCheck:
    @pytest.mark.parametrize("path", ["/Users/alice/projects/secret.txt", "/home/bob/work/x.py"])
    def test_a_home_path_in_a_carried_file_names_that_file_and_line(self, project, capsys, path) -> None:
        (project / "files" / "notes.md").write_text(
            f"# Notes\n\nSee\n{path} for the rest.\n", encoding="utf-8"
        )
        rc, out = _pack(project)
        assert rc == 1
        printed = capsys.readouterr().out
        assert f"notes.md:4 [home-path] {path}" in printed, printed
        assert not out.exists()
        assert [p.name for p in out.parent.iterdir() if p.name.startswith(".")] == []

    def test_a_url_with_home_in_its_path_is_not_a_home_path(self, project, capsys) -> None:
        (project / "files" / "notes.md").write_text(
            "See [it](https://example.com/home/news/x).\n", encoding="utf-8"
        )
        rc, _out = _pack(project)
        assert rc == 0, capsys.readouterr().out

    def test_an_external_script_island_stops_the_pack(self, project, capsys) -> None:
        text = ENTRY.replace(
            "- second item", '- second item\n\n<script src="https://cdn.example.com/x.js"></script>'
        )
        (project / "docs" / "entry.md").write_text(text, encoding="utf-8")
        rc, out = _pack(project)
        assert rc == 1
        line = text.splitlines().index('<script src="https://cdn.example.com/x.js"></script>') + 1
        printed = capsys.readouterr().out
        assert f"entry.md:{line} [external-load] https://cdn.example.com/x.js" in printed, printed
        assert not out.exists()

    def test_an_external_image_stops_the_pack(self, project, capsys) -> None:
        (project / "docs" / "second.md").write_text(
            SECOND + "\n![x](https://img.example.com/a.png)\n", encoding="utf-8"
        )
        rc, _out = _pack(project)
        assert rc == 1
        assert "[external-load] https://img.example.com/a.png" in capsys.readouterr().out

    def test_a_plain_external_link_is_a_note(self, project, capsys) -> None:
        (project / "docs" / "second.md").write_text(
            SECOND + "\nSee [the site](https://example.org/).\n", encoding="utf-8"
        )
        rc, _out = _pack(project)
        assert rc == 0
        assert "· " in capsys.readouterr().out

    def test_a_chip_past_the_project_stops_the_pack(self, project, capsys) -> None:
        (project.parent / "elsewhere.txt").write_text("not ours\n", encoding="utf-8")
        (project / "docs" / "second.md").write_text(
            SECOND + "\nThe [other](#f/../../elsewhere.txt).\n", encoding="utf-8"
        )
        rc, _out = _pack(project)
        assert rc == 1
        printed = capsys.readouterr().out
        assert "[outside-package] #f/../../elsewhere.txt names a file outside the project" in printed, printed
        assert str(project.parent) + os.sep + "elsewhere.txt" not in printed.split("[outside-package]")[1]

    def test_a_root_absolute_reference_stops_the_pack(self, project, capsys) -> None:
        (project / "docs" / "second.md").write_text(SECOND + "\n![x](/img/pixel.png)\n", encoding="utf-8")
        rc, _out = _pack(project)
        assert rc == 1
        assert "/img/pixel.png is root-absolute" in capsys.readouterr().out

    def test_a_link_to_a_missing_page_stops_the_pack(self, project, capsys) -> None:
        (project / "docs" / "second.md").write_text(SECOND + "\nSee [gone](gone.md).\n", encoding="utf-8")
        rc, _out = _pack(project)
        assert rc == 1
        assert "gone.md names nothing at the source" in capsys.readouterr().out

    def test_an_incomplete_kit_stops_the_pack(self, project, capsys, monkeypatch) -> None:
        monkeypatch.setattr(cli, "vendor_is_complete", lambda: False)
        monkeypatch.setattr(cli, "fetch_vendor", lambda **kw: (0, 0))
        rc, _out = _pack(project)
        assert rc == 1
        assert "[kit-incomplete]" in capsys.readouterr().out


def test_a_carried_file_at_a_name_the_package_writes_is_refused(tmp_path: Path, capsys) -> None:
    proj = tmp_path / "flat"
    (proj / ".git").mkdir(parents=True)
    (proj / "llms.txt").write_text("the author's own\n", encoding="utf-8")
    (proj / "a.md").write_text(
        "---\ntitle: A\n---\n\n## A {#a}\n\nSee [it](#f/llms.txt).\n", encoding="utf-8"
    )
    rc = pack.run([str(proj / "a.md")], str(tmp_path / "out"))
    assert rc == 1
    assert "[path-collision] llms.txt is carried" in capsys.readouterr().out


class TestTheCommandLine:
    def test_a_missing_page_is_a_usage_error(self, project) -> None:
        assert pack.run([str(project / "docs" / "nope.md")], str(project.parent / "out")) == 2

    def test_a_page_must_be_markdown(self, project) -> None:
        assert pack.run([str(project / "files" / "manual.pdf")], str(project.parent / "out")) == 2

    def test_a_directory_oku_did_not_pack_is_refused(self, project) -> None:
        out = project.parent / "out"
        out.mkdir()
        (out / "keep.txt").write_text("mine\n", encoding="utf-8")
        assert _pack(project, out=out)[0] == 2
        assert (out / "keep.txt").read_text(encoding="utf-8") == "mine\n"

    def test_an_earlier_pack_is_replaced(self, project) -> None:
        rc, out = _pack(project)
        assert rc == 0
        (out / "stale.txt").write_text("old\n", encoding="utf-8")
        assert _pack(project)[0] == 0
        assert not (out / "stale.txt").exists()

    def test_main_routes_pack(self, project, monkeypatch) -> None:
        out = project.parent / "via-main"
        monkeypatch.setattr(
            "sys.argv", ["oku", "pack", str(project / "docs" / "entry.md"), "--out", str(out)]
        )
        assert cli.main() == 0
        assert (out / "_pack.json").is_file()

    def test_main_without_out_is_a_usage_error(self, project, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["oku", "pack", str(project / "docs" / "entry.md")])
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
        assert exit_info.value.code == 2


def test_plain_text_drops_code_scripts_and_markup() -> None:
    page = cli.md_to_v2_page(
        "## Head {#h}\n\nA *soft* and __strong__ [link](x.md) with `code`.\n\n"
        "> [!NOTE]\n> Quoted line.\n\n<div><script>var no = 1;</script>island words</div>\n\n"
        "```oku-table\n"
        '{"columns":["C"],"rows":[["cell words"]]}\n'
        "```\n",
        default_title="t",
    )
    text = pack.page_plain_text(page)
    lines = text.splitlines()
    assert lines[:4] == ["Head", "A soft and strong link with code.", "Quoted line.", "island words"]
    # A typed table speaks through the search index's own walk, which
    # reads rows before columns; the words are what matter here.
    assert set(lines[4].split()) == {"C", "cell", "words"}
    assert len(lines) == 5


@pytest.mark.parametrize(
    "data, found",
    [
        (b"see /Users/alice/x/y.md here", b"/Users/alice/x/y.md"),
        (b'{"text": "line\\n/home/bob/notes/"}', b"/home/bob/notes/"),
        (b"file:///Users/alice/doc.pdf", b"/Users/alice/doc.pdf"),
        (b"https://example.com/home/news/x", None),
        (b"https://github.com/Users/x/", None),
    ],
)
def test_what_counts_as_a_home_path(data: bytes, found: bytes | None) -> None:
    """A JSON string escapes its newline, so the path after one follows an
    `n`; a URL's path segment called `home` follows its host."""
    m = pack._HOME_RE.search(data)
    assert (m.group(0) if m else None) == found
