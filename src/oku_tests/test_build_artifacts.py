"""Tests for the heavier build helpers: build_site, build_standalone,
build_kit_bundle, and the kit-assets resolver.

These touch real kit files (chrome.css etc.) under the repo's KIT_ROOT,
so the tests assert on the wiring (right files copied, JSON inlined,
pagefind body injected) rather than the content of the kit itself.
"""

from __future__ import annotations

import json
import re
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


_SCRIPT_OPEN_RE = re.compile(r"<script\b[^>]*>", re.I)


def _script_bodies(html: str) -> list[str]:
    """Split html into script bodies the way an HTML parser would.

    A parser ends a script element at the first `</script` in the raw text,
    regardless of JS syntax — which is exactly the failure mode this file
    guards against. Mirroring that rule here (rather than counting tags)
    keeps the assertions honest.
    """
    bodies: list[str] = []
    pos = 0
    while (m := _SCRIPT_OPEN_RE.search(html, pos)) is not None:
        end = html.lower().find("</script", m.end())
        if end == -1:
            bodies.append(html[m.end() :])
            break
        bodies.append(html[m.end() : end])
        pos = end + len("</script")
    return bodies


def _scaffold_project(root: Path, *, with_kit_json: bool = True) -> list[tuple[Path, str, dict | None]]:
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
                        {
                            "kind": "section",
                            "id": "x",
                            "title": "X",
                            "blocks": [{"kind": "paragraph", "content": f"Body of {title}"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        pages.append((html_path, html_text, None))
    if with_kit_json:
        (docs / "kit.json").write_text(json.dumps({"name": "Test kit", "domains": []}), encoding="utf-8")
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
        (docs / "kit.json").write_text(json.dumps({"name": "from-docs", "domains": []}), encoding="utf-8")
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
        assert "_oku/chrome.css" in body

    def test_preserves_nested_directory_structure(self, tmp_path: Path) -> None:
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        (src_root / "guides").mkdir(parents=True)
        html_text = SAMPLE_STUB.format(title="Intro")
        (src_root / "guides" / "intro.html").write_text(html_text, encoding="utf-8")
        (src_root / "guides" / "intro.json").write_text(
            json.dumps({"kind": "page", "title": "Intro", "blocks": []}), encoding="utf-8"
        )
        cli.build_site([(src_root / "guides" / "intro.html", html_text, None)], out_dir, src_root)
        assert (out_dir / "guides" / "intro.html").exists()
        assert (out_dir / "guides" / "intro.json").exists()


# ---------- build_kit_bundle ----------


class TestBuildKitBundle:
    def test_returns_none_without_kit_json(self, tmp_path: Path) -> None:
        assert cli.build_kit_bundle(tmp_path) is None

    def test_returns_json_blob_with_kit_block(self, tmp_path: Path) -> None:
        (tmp_path / "kit.json").write_text(json.dumps({"name": "X", "domains": []}), encoding="utf-8")
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
        (tmp_path / "kit.json").write_text(json.dumps({"name": "X", "domains": ["web"]}), encoding="utf-8")
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

    def test_inlined_kit_scripts_are_not_split_by_the_page_data(self, tmp_path: Path) -> None:
        """The page-data tag must not land inside an inlined kit script.

        chrome.js documents the layout skeleton with a comment containing the
        literal text "<body></body>". Injecting the page data after the kit
        was inlined matched that comment first, so the JSON landed mid-script
        and its </script> terminated chrome.js early — the remaining ~11k
        lines rendered as visible page text.
        """
        src_root = tmp_path / "src"
        out_dir = tmp_path / "out"
        src_root.mkdir()
        pages = _scaffold_project(src_root)
        cli.build_standalone(pages, out_dir, src_root)
        body = (out_dir / "index.html").read_text(encoding="utf-8")

        bodies = _script_bodies(body)
        # Exactly one script body is the page data, and it parses as JSON —
        # a truncated one would not.
        page_blobs = [b for b in bodies if '"k"' in b or '"kind"' in b]
        assert len(page_blobs) == 1
        json.loads(page_blobs[0])

        # chrome.js arrives whole: the body that opens it also carries its
        # tail. A split leaves the tail outside every script body.
        chrome_src = (cli.KIT_DIR / "chrome.js").read_text(encoding="utf-8")
        head_marker = chrome_src[:200].strip().splitlines()[1].strip()
        tail_marker = chrome_src.strip().splitlines()[-1].strip()
        hosting = [b for b in bodies if head_marker in b]
        assert len(hosting) == 1, "chrome.js should occupy exactly one script element"
        assert tail_marker in hosting[0], "chrome.js was cut off mid-script"

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
                            "kind": "section",
                            "id": "x",
                            "title": "X",
                            "blocks": [
                                {"kind": "code", "language": "html", "source": "<script>alert(1)</script>"}
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        cli.build_standalone([(src_root / "tricky.html", tricky_html, None)], out_dir, src_root)
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
        cli.build_standalone([(src_root / "guides" / "intro.html", intro_html, None)], out_dir, src_root)
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
        good.write_text(json.dumps({"kind": "page", "title": "Good", "blocks": []}), encoding="utf-8")
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


# ---------- authored stubs must keep their page data ----------


class TestAuthoredStubKeepsItsPage:
    """`docs/<page>.md` + a thin `docs/<page>.html` is the documented
    authoring shape. When the stub exists on disk the build must use the
    author's HTML *and* the parsed page — dropping the page left the
    standalone build with nothing to inline, so the artifact fetched
    `<page>.json` at runtime and rendered blank from a file:// origin.
    """

    MD = "---\ntitle: Authored\n---\n\n## Body {#body}\n\nText.\n"

    def _tree(self, tmp_path: Path) -> Path:
        (tmp_path / "page.md").write_text(self.MD, encoding="utf-8")
        (tmp_path / "page.html").write_text(cli._stub_for("Authored"), encoding="utf-8")
        return tmp_path

    def test_iter_page_stubs_attaches_the_page(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        srcs = cli.iter_page_stubs(root)
        entry = [s for s in srcs if s[0].name == "page.html"]
        assert len(entry) == 1, srcs
        path, html, page = entry[0]
        assert page is not None, "authored stub lost its page data"
        assert "_oku/chrome.js" in html, "the author's own stub was replaced"

    def test_standalone_inlines_the_page(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        out = tmp_path / "out"
        cli.build_standalone(cli.iter_page_stubs(root), out, root)
        built = (out / "page.html").read_text(encoding="utf-8")
        assert 'id="__oku_page__"' in built, "standalone build inlined no page data"
        assert '"Body"' in built or "Body" in built

    def test_site_build_indexes_the_page(self, tmp_path: Path) -> None:
        """Same omission kept authored-stub pages out of Pagefind."""
        root = self._tree(tmp_path)
        out = tmp_path / "site"
        cli.build_site(cli.iter_page_stubs(root), out, root)
        built = (out / "page.html").read_text(encoding="utf-8")
        assert "data-pagefind-body" in built, "page missing from the search index"


class TestKitSniffWindow:
    def test_stub_with_a_large_inline_manifest_is_recognised(self, tmp_path: Path) -> None:
        """`oku init` writes the entry stub with an inline manifest. On a
        site of any size that pushes the kit <script> well past the first
        couple of KB; a short sniff window made the build treat the stub
        as foreign HTML and ignore it."""
        manifest = {"pages": [{"path": f"p{i}.html", "title": f"Page {i}"} for i in range(200)]}
        stub = cli._stub_for("Big", inline_manifest=manifest)
        assert stub.index("_oku/chrome-boot.js") > 4096, "fixture is not exercising the window"
        (tmp_path / "big.html").write_text(stub, encoding="utf-8")
        found = [p.name for p in cli.find_html_files(tmp_path)]
        assert "big.html" in found, found


class TestBuiltMarker:
    def test_site_pages_are_stamped_as_build_output(self, tmp_path: Path) -> None:
        """A built stub and a dev-server stub are otherwise identical, so
        a site previewed from a local static server opened an EventSource
        against the dev server's /__reload and logged a 404 per page."""
        (tmp_path / "page.md").write_text("---\ntitle: T\n---\n\n## S {#s}\n\nx.\n", encoding="utf-8")
        out = tmp_path / "site"
        cli.build_site(cli.iter_page_stubs(tmp_path), out, tmp_path)
        built = (out / "page.html").read_text(encoding="utf-8")
        assert "window.__okuBuilt=1" in built
        assert built.index("window.__okuBuilt=1") < built.index("_oku/chrome-boot.js")

    def test_marker_is_not_doubled(self) -> None:
        once = cli._mark_built("<html><head><title>t</title></head><body></body></html>")
        assert once.count("window.__okuBuilt=1") == 1
        assert cli._mark_built(once) == once


class TestPayloadBudget:
    """The kit's own weight, asserted rather than assumed.

    Every reader downloads chrome.js + chrome.css + renderer.js, and a
    standalone page carries all three inline, so this is the one number
    that scales with nothing the author writes. It had no ceiling: the
    repo's stated rule is that a rule which is not a numeric assertion is
    not a rule yet, and page weight was carrying no assertion at all.

    These budgets are not targets. They sit close above today so that
    ordinary work never trips them and a step change does. Raising one is
    a decision — make it deliberately, in a commit that says what was
    bought with the bytes.
    """

    # 1,162 KB today. Raised from 1,150,000 by the copy-region
    # primitive (the three clipboard serialisers, the word diff, and
    # the styling for both), then from 1,190,000 by the theme-tracking
    # pass on Mermaid: five cScale entries and the crit colours read
    # from tokens instead of literals, plus `darkMode`, plus the
    # navigation token and the scroll-behaviour helper. 1.6 KB, most
    # of it the comments that say why. The gap is headroom for a
    # feature, not for drift.
    KIT_BUDGET_BYTES = 1_200_000
    # A standalone page is the kit plus its own content; this page's
    # content is 45 KB of it. The ceiling is what the kit costs plus a
    # generous page.
    STANDALONE_BUDGET_BYTES = 1_400_000

    KIT_FILES = ("chrome.js", "chrome.css", "renderer.js", "chrome-boot.js")

    def test_the_kit_payload_stays_under_budget(self) -> None:
        kit = Path(__file__).resolve().parents[2] / "kit"
        sizes = {n: (kit / n).stat().st_size for n in self.KIT_FILES}
        total = sum(sizes.values())
        assert total <= self.KIT_BUDGET_BYTES, (
            f"kit payload is {total:,} bytes, over the {self.KIT_BUDGET_BYTES:,} budget. "
            f"Per file: { {k: f'{v:,}' for k, v in sizes.items()} }. "
            "Raise the budget deliberately, or find the weight."
        )

    def test_a_standalone_page_stays_under_budget(self, tmp_path: Path) -> None:
        """A standalone file is what a reader is handed for offline
        reading, and it inlines the whole kit. Nothing measured its
        size, so a doubling would have shipped silently."""
        (tmp_path / "page.md").write_text(
            "---\ntitle: T\nsummary: S\n---\n\n## S {#s}\n\nBody text.\n", encoding="utf-8"
        )
        out = tmp_path / "standalone"
        cli.build_standalone(cli.iter_page_stubs(tmp_path), out, tmp_path)
        built = out / "page.html"
        size = built.stat().st_size
        assert size <= self.STANDALONE_BUDGET_BYTES, (
            f"a standalone page is {size:,} bytes, over the {self.STANDALONE_BUDGET_BYTES:,} budget."
        )

    def test_the_budget_is_not_slack(self) -> None:
        """A ceiling far above the thing it measures reports success
        forever. This fails if the kit ever shrinks enough to make the
        budget meaningless — at which point lower it and keep the gate
        working."""
        kit = Path(__file__).resolve().parents[2] / "kit"
        total = sum((kit / n).stat().st_size for n in self.KIT_FILES)
        assert total >= self.KIT_BUDGET_BYTES * 0.6, (
            f"kit payload is {total:,} bytes against a {self.KIT_BUDGET_BYTES:,} budget — "
            "the ceiling is now so far above the floor that it can never fail. Lower it."
        )
