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


KIT_URL = "/k/"


@pytest.fixture()
def fake_vendor(tmp_path: Path, monkeypatch) -> Path:
    """A complete vendor copy and grammar cache of placeholder bytes, so
    the export runs without a network."""
    vendor = tmp_path / "vendor"
    for rel, _url in cli._vendor_files():
        (vendor / rel).parent.mkdir(parents=True, exist_ok=True)
        (vendor / rel).write_bytes(f"/* {rel} */\n".encode())
    grammars = tmp_path / "grammars"
    grammars.mkdir()
    for g in pack._all_grammars():
        (grammars / f"prism-{g}.min.js").write_bytes(f"/* {g} */\n".encode())
    monkeypatch.setattr(cli, "vendor_dir", lambda: vendor)
    monkeypatch.setattr(pack, "_grammar_dir", lambda: grammars)
    return tmp_path


def _layers(out: Path) -> dict[str, str]:
    """The export's layers by name: {"core": "core-<hex>", ...}."""
    return {d.name.split("-", 1)[0]: d.name for d in out.iterdir()}


@pytest.fixture()
def exported(fake_vendor: Path) -> Path:
    out = fake_vendor / "kit"
    assert pack.export_kit(str(out)) == 0
    return out


class TestASharedKit:
    """`--kit` and `--kit-url`: the package names the host's one copy of the
    kit, in its layers, instead of carrying `_oku/`. The browser half, which
    proves every lazy load follows, is `browser/test_pack_shared_kit.py`."""

    def _pack(self, project: Path, kit: Path | None, kit_url: str | None = KIT_URL) -> tuple[int, Path]:
        out = project.parent / "out"
        rc = pack.run(
            [str(project / "docs" / "entry.md")], str(out), kit_url=kit_url, kit_dir=kit and str(kit)
        )
        return rc, out

    def test_no_kit_is_written(self, project: Path, exported: Path) -> None:
        rc, out = self._pack(project, exported)
        assert rc == 0
        assert not (out / "_oku").exists()
        index = json.loads((out / "_pack.json").read_text(encoding="utf-8"))
        assert not [f["path"] for f in index["files"] if f["path"].startswith("_oku/")]

    def test_every_kit_tag_names_the_core_layer_and_no_stamp(self, project: Path, exported: Path) -> None:
        """The layer's name is its content; a `?v=` that differs between two
        machines would make one file two addresses."""
        rc, out = self._pack(project, exported)
        assert rc == 0
        stub = (out / "docs" / "entry.html").read_text(encoding="utf-8")
        core = _layers(exported)["core"]
        for name in cli.KIT_FILES:
            assert f'="{KIT_URL}{core}/{name}"' in stub, (name, stub)
        assert "_oku/" not in stub and "?v=" not in stub, stub

    def test_the_stub_names_every_root(self, project: Path, exported: Path) -> None:
        """chrome.js finds the root, the kit and the vendored files by the
        `_oku/` in its tags; without one, the stub has to say where each is."""
        rc, out = self._pack(project, exported)
        assert rc == 0
        stub = (out / "docs" / "entry.html").read_text(encoding="utf-8")
        layers = _layers(exported)
        assert '<meta name="oku-docs-root" content="../">' in stub, stub
        assert f'<meta name="oku-kit-base" content="{KIT_URL}{layers["core"]}/">' in stub, stub
        for name in ("fonts", "mermaid", "prism"):
            assert f'<meta name="oku-vendor-{name}" content="{KIT_URL}{layers[name]}/">' in stub, stub

    def test_the_index_names_the_kit_and_its_layers(self, project: Path, exported: Path) -> None:
        rc, out = self._pack(project, exported)
        assert rc == 0
        index = json.loads((out / "_pack.json").read_text(encoding="utf-8"))
        assert index["kit"] == {"url": KIT_URL, "layers": sorted(_layers(exported).values())}
        assert list(index) == ["pack", "entry", "title", "summary", "kit", "pages", "files"]

    def test_without_a_kit_the_package_is_as_before(self, project: Path) -> None:
        rc, out = _pack(project)
        assert rc == 0
        assert (out / "_oku" / "chrome.js").is_file()
        assert "kit" not in json.loads((out / "_pack.json").read_text(encoding="utf-8"))
        stub = (out / "docs" / "entry.html").read_text(encoding="utf-8")
        assert 'src="../_oku/chrome.js?v=' in stub
        assert "oku-kit-base" not in stub and "oku-docs-root" not in stub

    @pytest.mark.parametrize(
        "url",
        [
            "k/x/",  # relative
            "/k/x",  # no trailing slash
            "//cdn.example.com/k/",  # protocol-relative: another origin
            "https://host/k/x/",
            "/k/../x/",
            "/k/./x/",
            "/k//x/",
            "/k/x/?v=1",
            "/k/x/#a",
            "/k/x y/",
            '/k/"x/',
            "",
        ],
    )
    def test_a_url_that_is_not_a_root_relative_directory_is_a_usage_error(
        self, project, exported, url
    ) -> None:
        rc, out = self._pack(project, exported, url)
        assert rc == 2
        assert not out.exists()

    @pytest.mark.parametrize("which", ["kit", "kit_url"])
    def test_one_without_the_other_is_a_usage_error(self, project, exported, which) -> None:
        rc, out = self._pack(
            project, None if which == "kit" else exported, None if which == "kit_url" else KIT_URL
        )
        assert rc == 2
        assert not out.exists()

    def test_an_export_of_another_oku_is_refused(self, project, exported, capsys) -> None:
        core = exported / _layers(exported)["core"]
        (core / "renderer.js").write_text("/* another release */\n", encoding="utf-8")
        rc, out = self._pack(project, exported)
        assert rc == 2
        assert "renderer.js is not this oku's" in capsys.readouterr().err
        assert not out.exists()

    def test_a_directory_that_is_not_an_export_is_refused(self, project, exported) -> None:
        (exported / "notes.txt").write_text("mine\n", encoding="utf-8")
        rc, out = self._pack(project, exported)
        assert rc == 2
        assert not out.exists()

    def test_the_leak_check_still_runs(self, project, exported, capsys) -> None:
        (project / "files" / "notes.md").write_text("# Notes\n\n/Users/alice/secret.txt\n", encoding="utf-8")
        rc, out = self._pack(project, exported)
        assert rc == 1
        assert "[home-path] /Users/alice/secret.txt" in capsys.readouterr().out
        assert not out.exists()

    def test_a_kit_reference_the_export_does_not_carry_is_a_finding(self, project, exported, capsys) -> None:
        core = _layers(exported)["core"]
        (exported / core / "chrome.css").unlink()
        rc, out = self._pack(project, exported)
        assert rc == 1
        assert f"{KIT_URL}{core}/chrome.css" in capsys.readouterr().out
        assert not out.exists()

    def test_main_routes_the_kit(self, project, exported, monkeypatch) -> None:
        out = project.parent / "via-main"
        entry = str(project / "docs" / "entry.md")
        argv = ["oku", "pack", entry, "--out", str(out), "--kit", str(exported), "--kit-url", KIT_URL]
        monkeypatch.setattr("sys.argv", argv)
        assert cli.main() == 0
        assert json.loads((out / "_pack.json").read_text(encoding="utf-8"))["kit"]["url"] == KIT_URL


class TestTheKitExport:
    """`oku kit export`: what a page loads from the kit, in layers named for
    their content, the same bytes on every run."""

    def test_two_runs_write_the_same_bytes(self, fake_vendor: Path) -> None:
        a, b = fake_vendor / "a", fake_vendor / "b"
        assert pack.export_kit(str(a)) == 0
        assert pack.export_kit(str(b)) == 0
        assert _files(a) == _files(b)

    def test_it_holds_what_a_page_loads_and_no_schema(self, exported: Path) -> None:
        layers = _layers(exported)
        assert sorted(layers) == ["core", "fonts", "mermaid", "prism"]
        files = _files(exported)
        core = layers["core"]
        for name in ("chrome.js", "renderer.js", "chrome-boot.js"):
            assert files[f"{core}/{name}"] == cli.kit_file_text(name).encode("utf-8"), name
        for rel in ("i18n/tr.json", "glossary/web.json", "extrefs/web.json"):
            assert f"{core}/{rel}" in files, rel
        for rel, _url in cli._vendor_files():
            name, inner = pack._layer_of(f"vendor/{rel}")
            assert f"{layers[name]}/{inner}" in files, rel
        assert not [p for p in files if "/schema/" in p or p.endswith("examples.json")]

    def test_the_stylesheet_names_the_fonts_layer(self, exported: Path) -> None:
        layers = _layers(exported)
        css = (exported / layers["core"] / "chrome.css").read_text(encoding="utf-8")
        assert f'url("../{layers["fonts"]}/fonts/' in css
        assert 'url("vendor/fonts/' not in css

    def test_each_layer_is_named_for_its_content(self, exported: Path) -> None:
        """The rule pano checks every layer against."""
        for d in exported.iterdir():
            files = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
            assert d.name.endswith("-" + pack.layer_id(files)), d.name

    def test_a_release_that_changes_only_oku_changes_only_the_core(
        self, fake_vendor, exported, monkeypatch
    ) -> None:
        """What the layers are for: mermaid, the fonts and the grammars keep
        their addresses, so a reader downloads only the new core."""
        before = _layers(exported)
        shipped = cli.kit_file_text
        monkeypatch.setattr(
            cli, "kit_file_text", lambda n: shipped(n) + ("\n;0;" if n == "chrome.js" else "")
        )
        after_dir = fake_vendor / "after"
        assert pack.export_kit(str(after_dir)) == 0
        after = _layers(after_dir)
        assert {n for n in before if before[n] != after[n]} == {"core"}

    def test_new_fonts_are_a_new_core_too(self, fake_vendor, exported) -> None:
        """The core's stylesheet names the fonts layer."""
        before = _layers(exported)
        font = next(rel for rel, _url in cli._vendor_files() if rel.startswith("fonts/"))
        (fake_vendor / "vendor" / font).write_bytes(b"another face")
        after_dir = fake_vendor / "after"
        assert pack.export_kit(str(after_dir)) == 0
        after = _layers(after_dir)
        assert {n for n in before if before[n] != after[n]} == {"core", "fonts"}

    def test_it_carries_every_grammar_and_says_so(self, exported: Path) -> None:
        """Not the grammars this machine's builds happened to fetch: those
        grow, and every new one would change the prism layer's name."""
        prism = exported / _layers(exported)["prism"] / "prism"
        grammars = pack._all_grammars()
        components = sorted(p.name for p in (prism / "components").iterdir())
        assert components == sorted(f"prism-{g}.min.js" for g in grammars)
        carried = (prism / "carried.js").read_text(encoding="utf-8")
        ids = json.loads(carried.removeprefix("window.__okuPrismCarried=").removesuffix(";\n"))["ids"]
        assert set(grammars) <= set(ids)

    def test_a_directory_it_did_not_write_is_refused(self, fake_vendor: Path) -> None:
        out = fake_vendor / "kit"
        out.mkdir()
        (out / "keep.txt").write_text("mine\n", encoding="utf-8")
        assert pack.export_kit(str(out)) == 2
        assert sorted(p.name for p in out.iterdir()) == ["keep.txt"]

    def test_an_earlier_export_is_replaced(self, exported: Path) -> None:
        stale = exported / "core-0123456789abcdef"
        stale.mkdir()
        (stale / "chrome.js").write_text("old\n", encoding="utf-8")
        assert pack.export_kit(str(exported)) == 0
        assert not stale.exists()

    def test_a_grammar_that_cannot_be_fetched_stops_it(self, fake_vendor: Path, monkeypatch) -> None:
        missing = fake_vendor / "grammars" / f"prism-{pack._all_grammars()[0]}.min.js"
        missing.unlink()
        monkeypatch.setattr(pack, "_fetch_grammar", lambda ident: False)
        out = fake_vendor / "kit"
        assert pack.export_kit(str(out)) == 1
        assert not out.exists()

    def test_main_routes_the_export(self, fake_vendor: Path, monkeypatch) -> None:
        out = fake_vendor / "via-main"
        monkeypatch.setattr("sys.argv", ["oku", "kit", "export", "--out", str(out)])
        assert cli.main() == 0
        assert (out / _layers(out)["core"] / "chrome.js").is_file()


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
