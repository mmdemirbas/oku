"""A page and its translation are one page in two languages.

Authoring is `<page>.md` + `<page>.<lang>.md` side by side — no new
syntax, each file a complete markdown document that still renders on
GitHub. `kit.json` declares which codes count; without that key none of
this runs and a monolingual site pays nothing.

The manifest carries the pairing, because it is the one thing that
already reaches every page in all three modes: fetched under `oku serve`
and `dist/site`, inlined in a standalone file.
"""

from __future__ import annotations

from pathlib import Path

from oku import cli

KIT = '{"domains":[],"languages":[{"code":"en","label":"English"},{"code":"tr","label":"Türkçe"}],"defaultLanguage":"en"}'


def _page(path: Path, title: str, order: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {title}\nsummary: s\norder: {order}\n---\n\n## S {{#s}}\n\nBody.\n",
        encoding="utf-8",
    )


def _bilingual(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir(parents=True)
    (root / "kit.json").write_text(KIT, encoding="utf-8")
    _page(root / "index.md", "Home")
    _page(root / "index.tr.md", "Ana sayfa")
    _page(root / "only-english.md", "Only English", order=20)
    return root


class TestSuffixSplitting:
    def test_a_declared_code_splits(self):
        assert cli.split_language_suffix("index.tr", ["en", "tr"]) == ("index", "tr")

    def test_an_undeclared_suffix_is_part_of_the_name(self):
        """Without this check `format-comparison` is fine but `api.v2`
        would split into base `api` with language `v2`, and a page would
        vanish from the tree the day a language code collided with the
        last dotted part of a filename."""
        assert cli.split_language_suffix("api.v2", ["en", "tr"]) == ("api.v2", None)
        assert cli.split_language_suffix("format-comparison", ["en", "tr"]) == (
            "format-comparison",
            None,
        )

    def test_a_name_with_no_dot_is_left_alone(self):
        assert cli.split_language_suffix("index", ["en", "tr"]) == ("index", None)


class TestDeclaredLanguages:
    def test_a_site_that_declares_none_is_monolingual(self, tmp_path: Path):
        root = tmp_path / "docs"
        root.mkdir()
        (root / "kit.json").write_text('{"domains":[]}', encoding="utf-8")

        assert cli.declared_languages(root) == ([], "")

    def test_one_declared_language_is_still_monolingual(self, tmp_path: Path):
        """A switch with one stop is not a switch."""
        root = tmp_path / "docs"
        root.mkdir()
        (root / "kit.json").write_text('{"languages":["en"]}', encoding="utf-8")

        assert cli.declared_languages(root) == ([], "")

    def test_bare_codes_and_labelled_objects_both_work(self, tmp_path: Path):
        root = tmp_path / "docs"
        root.mkdir()
        (root / "kit.json").write_text('{"languages":["en","tr"]}', encoding="utf-8")
        assert cli.declared_languages(root) == (["en", "tr"], "en")

        (root / "kit.json").write_text(KIT, encoding="utf-8")
        assert cli.declared_languages(root) == (["en", "tr"], "en")

    def test_a_default_outside_the_list_falls_back_to_the_first(self, tmp_path: Path):
        root = tmp_path / "docs"
        root.mkdir()
        (root / "kit.json").write_text('{"languages":["en","tr"],"defaultLanguage":"de"}', encoding="utf-8")

        assert cli.declared_languages(root) == (["en", "tr"], "en")


class TestManifestFolding:
    def test_a_translation_is_not_a_second_tree_entry(self, tmp_path: Path):
        """Left as its own entry, a ten-page site in two languages reads
        as twenty pages and every reader sees both halves of a tree they
        can only read half of."""
        root = _bilingual(tmp_path)

        pages = cli.compute_manifest(root)["pages"]

        assert [p["path"] for p in pages] == ["index.html", "only-english.html"]

    def test_the_base_entry_knows_where_its_translation_is(self, tmp_path: Path):
        root = _bilingual(tmp_path)

        entry = next(p for p in cli.compute_manifest(root)["pages"] if p["path"] == "index.html")

        assert entry["lang"] == "en"
        assert entry["variants"] == {"en": "index.html", "tr": "index.tr.html"}
        # The map includes the base itself, so the switch has no special
        # case for "where do I go back to".
        assert entry["variants"]["en"] == entry["path"]

    def test_a_page_with_no_translation_carries_no_variants(self, tmp_path: Path):
        """The switch is a property of the page: no counterpart, no
        button, nothing to explain."""
        root = _bilingual(tmp_path)

        entry = next(p for p in cli.compute_manifest(root)["pages"] if p["path"] == "only-english.html")

        assert "variants" not in entry
        assert entry["lang"] == "en"

    def test_a_monolingual_site_gains_no_language_keys(self, tmp_path: Path):
        """The feature has to cost nothing until it is asked for."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        (root / "kit.json").write_text('{"domains":[]}', encoding="utf-8")
        _page(root / "index.md", "Home")
        _page(root / "index.tr.md", "Ana sayfa")

        pages = cli.compute_manifest(root)["pages"]

        assert sorted(p["path"] for p in pages) == ["index.html", "index.tr.html"]
        assert all("variants" not in p and "lang" not in p for p in pages)

    def test_a_translation_whose_base_is_missing_keeps_its_entry(self, tmp_path: Path):
        """`notes.tr.md` with no `notes.md` is not a translation — it is
        a page. Dropping it would delete it from the tree with no way to
        reach it."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        (root / "kit.json").write_text(KIT, encoding="utf-8")
        _page(root / "orphan.tr.md", "Yetim")

        pages = cli.compute_manifest(root)["pages"]

        assert [p["path"] for p in pages] == ["orphan.tr.html"]
        assert pages[0]["lang"] == "tr"


class TestDottedNamesDoNotCollide:
    def test_a_dotted_name_gets_its_own_page(self, tmp_path: Path):
        """`with_suffix` replaces the LAST dotted part, so the stem
        `index.tr` became `index.json` — the same virtual path `index.md`
        produces — and the walker's dedupe silently dropped one of the
        two. True of any `a.b.md` long before a language entered the
        picture: `api.v2.md` collided with `api.md`."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        _page(root / "api.md", "API")
        _page(root / "api.v2.md", "API v2")

        found = {p.name for p, _ in cli.find_json_pages(root)}

        assert found == {"api.json", "api.v2.json"}, found

    def test_each_dotted_page_keeps_its_own_content(self, tmp_path: Path):
        """The collision did not only lose a page — it served the wrong
        one, because the survivor answered for both paths."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        _page(root / "api.md", "API")
        _page(root / "api.v2.md", "API v2")

        titles = {p.name: cli._page_title(d) for p, d in cli.find_json_pages(root)}

        assert titles == {"api.json": "API", "api.v2.json": "API v2"}

    def test_the_source_sibling_of_a_dotted_page_resolves_back(self, tmp_path: Path):
        assert cli._source_sibling(Path("docs/index.tr.json")) == Path("docs/index.tr.md")
        assert cli._source_sibling(Path("docs/index.html")) == Path("docs/index.md")
