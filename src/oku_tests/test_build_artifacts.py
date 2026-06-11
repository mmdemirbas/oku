"""Tests for the heavier build helpers: build_site, build_standalone,
build_kit_bundle, and the kit-assets resolver.

These touch real kit files (chrome.css etc.) under the repo's KIT_ROOT,
so the tests assert on the wiring (right files copied, JSON inlined,
pagefind body injected) rather than the content of the kit itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oku import cli


# Sample HTML stub matching src/oku/templates/starter.html in shape.
SAMPLE_STUB = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<link rel="stylesheet" href="_oku/chrome.css">
<script src="_oku/chrome-boot.js"></script>
<script src="_oku/chrome.js" defer></script>
<script src="_oku/renderer.js" defer></script>
</head>
<body>
<page-chrome></page-chrome>
<div class="layout"><main id="main-content"></main></div>
</body>
</html>
"""


def _scaffold_project(
    root: Path, *, with_kit_json: bool = True
) -> list[tuple[Path, str, dict | None]]:
    """Lay out a minimal site under root: two HTML + sibling JSON pages,
    optional kit.json. Returns the iter_page_stubs-shaped tuple list
    (path, html_text, page_data | None) that build_site / build_standalone
    consume.
    """
    docs = root
    pages: list[tuple[Path, str, dict | None]] = []
    for stem, title in (("index", "Index"), ("about", "About")):
        html_path = docs / f"{stem}.html"
        html_text = SAMPLE_STUB.format(title=title)
        html_path.write_text(html_text, encoding="utf-8")
        (docs / f"{stem}.json").write_text(
            json.dumps(
                {
                    "kind": "page",
                    "title": title,
                    "blocks": [
                        {"kind": "section", "id": "x", "title": "X",
                         "blocks": [{"kind": "paragraph", "content": f"Body of {title}"}]}
                    ],
                }
            ),
            encoding="utf-8",
        )
        pages.append((html_path, html_text, None))
    if with_kit_json:
        (docs / "kit.json").write_text(
            json.dumps({"name": "Test kit", "domains": []}), encoding="utf-8"
        )
    return pages


# ---------- build_site ----------


class TestBuildSite:
    def test_copies_kit_chrome_files(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root)
        cli.build_site(pages, out_dir, src_root)
        for f in cli.KIT_FILES:
            assert (out_dir / "_oku" / f).exists(), f"missing kit asset: {f}"

    def test_copies_kit_registry_dirs_when_present(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root)
        cli.build_site(pages, out_dir, src_root)
        # Runtime JS/CSS and shared registries (schema/glossary/extrefs)
        # both live under _oku/. schema/ is always shipped.
        assert (out_dir / "_oku" / "schema").is_dir()

    def test_copies_kit_json_when_present(self, tmp_path: Path) -> None:
        # build_site copies the user-authored kit.json. site-manifest /
        # llms.txt are NO LONGER copied from source — cmd_build writes
        # them directly into each dist tree to keep source clean.
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root)
        cli.build_site(pages, out_dir, src_root)
        assert (out_dir / "kit.json").exists()
        # Manifest / llms NOT here — written by cmd_build into the dist
        # tree's docs_dir, not by build_site from source files.
        assert not (out_dir / "site-manifest.json").exists()
        assert not (out_dir / "site-manifest.js").exists()
        assert not (out_dir / "llms.txt").exists()

    def test_copies_kit_json_from_docs_subdir(self, tmp_path: Path) -> None:
        """Canonical kit.json home is docs/kit.json (per the schema's
        own description). build_site must find it via find_kit_json
        and copy it to the dist root, sibling of _oku/. Earlier
        regression: build looked only at root/kit.json, so authoring
        at docs/ silently shipped no kit.json — runtime then 404'd on
        /docs/kit.json (dev server) or /kit.json (dist site)."""
        src_root = tmp_path / "src"
        docs = src_root / "docs"
        docs.mkdir(parents=True)
        # Pages laid out under docs/.
        pages: list[tuple[Path, str, dict | None]] = []
        for stem, title in (("index", "Index"), ("about", "About")):
            html_path = docs / f"{stem}.html"
            html_text = SAMPLE_STUB.format(title=title)
            html_path.write_text(html_text, encoding="utf-8")
            (docs / f"{stem}.json").write_text(
                json.dumps({"kind": "page", "title": title, "blocks": []}), encoding="utf-8"
            )
            pages.append((html_path, html_text, None))
        # Authored kit.json under docs/, NOT at src_root.
        (docs / "kit.json").write_text(
            json.dumps({"name": "from-docs", "domains": []}), encoding="utf-8"
        )
        out_dir = tmp_path / "out"
        cli.build_site(pages, out_dir, src_root)
        # The copied kit.json lands at the dist root (sibling of _oku/),
        # regardless of whether it was authored at docs/ or root/.
        assert (out_dir / "kit.json").exists()
        contents = json.loads((out_dir / "kit.json").read_text(encoding="utf-8"))
        assert contents["name"] == "from-docs"

    def test_copies_html_and_json_pages(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root, with_kit_json=False)
        cli.build_site(pages, out_dir, src_root)
        assert (out_dir / "index.html").exists()
        assert (out_dir / "index.json").exists()
        assert (out_dir / "about.html").exists()
        assert (out_dir / "about.json").exists()

    def test_injects_pagefind_body_into_each_html(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root, with_kit_json=False)
        cli.build_site(pages, out_dir, src_root)
        body = (out_dir / "index.html").read_text(encoding="utf-8")
        # The pagefind block uses data-pagefind-body and carries the page title
        # plus extracted text.
        assert "data-pagefind-body" in body
        assert "Body of Index" in body
        assert 'data-pagefind-meta="title"' in body
        # The original kit references remain untouched (no inlining at this
        # step — that's build_standalone's job).
        assert '_oku/chrome.css' in body

    def test_preserves_nested_directory_structure(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        (src_root / "guides").mkdir(parents=True)
        html_text = SAMPLE_STUB.format(title="Intro")
        (src_root / "guides" / "intro.html").write_text(html_text, encoding="utf-8")
        (src_root / "guides" / "intro.json").write_text(
            json.dumps({"kind": "page", "title": "Intro", "blocks": []}), encoding="utf-8"
        )
        cli.build_site(
            [(src_root / "guides" / "intro.html", html_text, None)], out_dir, src_root
        )
        assert (out_dir / "guides" / "intro.html").exists()
        assert (out_dir / "guides" / "intro.json").exists()


# ---------- build_kit_bundle ----------


class TestBuildKitBundle:
    def test_returns_none_without_kit_json(self, tmp_path: Path) -> None:
        assert cli.build_kit_bundle(tmp_path) is None

    def test_returns_json_blob_with_kit_block(self, tmp_path: Path) -> None:
        (tmp_path / "kit.json").write_text(
            json.dumps({"name": "X", "domains": []}), encoding="utf-8"
        )
        blob = cli.build_kit_bundle(tmp_path)
        assert isinstance(blob, str)
        parsed = json.loads(blob)
        assert parsed["kit"]["name"] == "X"
        assert "glossary" in parsed
        assert "extrefs" in parsed

    def test_skips_unknown_domains_gracefully(self, tmp_path: Path) -> None:
        # Reference a domain that doesn't exist in the kit — bundle skips
        # silently rather than raising.
        (tmp_path / "kit.json").write_text(
            json.dumps({"name": "X", "domains": ["nonexistent-domain"]}),
            encoding="utf-8",
        )
        blob = cli.build_kit_bundle(tmp_path)
        parsed = json.loads(blob)
        assert parsed["glossary"] == {}
        assert parsed["extrefs"] == {}

    def test_includes_real_domain_entries(self, tmp_path: Path) -> None:
        # web/ is one of the kit's bundled glossary domains; assert its
        # entries surface when declared.
        (tmp_path / "kit.json").write_text(
            json.dumps({"name": "X", "domains": ["web"]}), encoding="utf-8"
        )
        blob = cli.build_kit_bundle(tmp_path)
        parsed = json.loads(blob)
        assert "web" in parsed["glossary"]
        assert parsed["glossary"]["web"]  # non-empty


# ---------- build_standalone ----------


class TestBuildStandalone:
    def test_inlines_css_and_scripts(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root)
        cli.build_standalone(pages, out_dir, src_root)
        body = (out_dir / "index.html").read_text(encoding="utf-8")
        # External kit references gone — replaced with inline <style>/<script>.
        assert 'href="_oku/chrome.css"' not in body
        assert 'src="_oku/chrome.js"' not in body
        assert "<style>" in body
        # Each kit script tag becomes <script>...</script> (count covers boot,
        # main, renderer, plus the inlined JSON tags).
        assert body.count("<script>") >= 3

    def test_inlines_page_json(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root)
        cli.build_standalone(pages, out_dir, src_root)
        body = (out_dir / "index.html").read_text(encoding="utf-8")
        # autoBoot looks for this id; missing → standalone is dead on arrival.
        assert 'id="__oku_page__"' in body
        assert "Body of Index" in body

    def test_escapes_closing_script_tag_in_json(self, tmp_path: Path) -> None:
        # JSON content that literally contains "</script" would close the
        # inline tag early; the build must escape it.
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        tricky_html = SAMPLE_STUB.format(title="T")
        (src_root / "tricky.html").write_text(tricky_html, encoding="utf-8")
        (src_root / "tricky.json").write_text(
            json.dumps(
                {
                    "kind": "page",
                    "title": "T",
                    "blocks": [
                        {
                            "kind": "section", "id": "x", "title": "X",
                            "blocks": [
                                {"kind": "code", "language": "html",
                                 "source": "<script>alert(1)</script>"}
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        cli.build_standalone(
            [(src_root / "tricky.html", tricky_html, None)], out_dir, src_root
        )
        body = (out_dir / "tricky.html").read_text(encoding="utf-8")
        # The inlined JSON block should NOT contain a raw </script that
        # would terminate the surrounding inline script tag.
        json_block_start = body.index('id="__oku_page__"')
        json_block_end = body.index("</script>", json_block_start)
        json_segment = body[json_block_start:json_block_end]
        assert "</script" not in json_segment

    def test_inlines_kit_bundle_when_kit_json_present(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root, with_kit_json=True)
        cli.build_standalone(pages, out_dir, src_root)
        body = (out_dir / "index.html").read_text(encoding="utf-8")
        # __oku_kit_bundle__ surfaces when kit.json exists and the
        # bundle has at least the kit block.
        assert 'id="__oku_kit_bundle__"' in body

    def test_preserves_nested_directory_structure(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        (src_root / "guides").mkdir(parents=True)
        intro_html = SAMPLE_STUB.format(title="Intro")
        (src_root / "guides" / "intro.html").write_text(intro_html, encoding="utf-8")
        (src_root / "guides" / "intro.json").write_text(
            json.dumps({"kind": "page", "title": "Intro", "blocks": []}), encoding="utf-8"
        )
        cli.build_standalone(
            [(src_root / "guides" / "intro.html", intro_html, None)], out_dir, src_root
        )
        assert (out_dir / "guides" / "intro.html").exists()


# ---------- _kit_assets_dir ----------


class TestKitAssetsResolver:
    def test_resolver_walks_up_through_src(self, repo_root: Path) -> None:
        # The cli module lives at src/oku/cli.py; the resolver
        # must walk up to the repo root to find <repo>/kit/ (not stop
        # at src/ or oku/).
        kit_dir = cli._kit_assets_dir()
        assert (kit_dir / "chrome.css").exists()
        assert (kit_dir / "chrome.js").exists()
        assert (kit_dir / "chrome-boot.js").exists()
        assert (kit_dir / "renderer.js").exists()
        assert (kit_dir / "schema" / "page.schema.json").exists()
        assert (kit_dir / "glossary").is_dir()
        assert (kit_dir / "extrefs").is_dir()


# ---------- validate_pages (soft-import jsonschema gate) ----------


jsonschema = pytest.importorskip("jsonschema")


class TestValidatePages:
    def test_clean_pages_return_empty_errors(self, tmp_path: Path) -> None:
        good = tmp_path / "good.json"
        good.write_text(
            json.dumps({"kind": "page", "title": "Good", "blocks": []}), encoding="utf-8"
        )
        pages = [(good, json.loads(good.read_text(encoding="utf-8")))]
        # When jsonschema is installed, validate_pages walks each page;
        # the empty list means no errors.
        assert cli.validate_pages(pages) == []

    def test_returns_errors_for_invalid_page(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        # Missing required "title" on the root page schema.
        bad.write_text(json.dumps({"kind": "page", "blocks": []}), encoding="utf-8")
        pages = [(bad, json.loads(bad.read_text(encoding="utf-8")))]
        errors = cli.validate_pages(pages)
        assert errors  # at least one issue surfaced
        path, msg = errors[0]
        assert path == bad
        assert isinstance(msg, str) and msg
