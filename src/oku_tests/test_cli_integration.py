"""End-to-end test of the oku CLI as a subprocess.

Most of the suite tests pure-function units; this file drives the actual
``bin/oku`` shim against a synthetic project and asserts on the
file-system output. It catches plumbing regressions that unit tests
can't see — argparse wiring, the chdir flow, build orchestration order.

Only ``init`` and ``build`` are covered here; ``serve`` opens a long-
running socket and a browser tab, which would make CI flaky.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(cwd: Path, *args: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Run bin/oku as a subprocess. We use the in-tree shim rather
    than an installed binary so the test stays portable — works against
    any clone, no pre-install step required."""
    proc = subprocess.run(
        [sys.executable, str(repo_root / "bin" / "oku"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc


@pytest.fixture
def sample_project(tmp_path: Path, repo_root: Path) -> Path:
    """Lay out a minimal project under tmp_path: docs/ with two pages and
    a _kit symlink back to the repo root. Returns the project root."""
    docs = tmp_path / "docs"
    docs.mkdir()
    # _kit symlink — what `oku init` would have created.
    (docs / "_oku").symlink_to(repo_root)
    # Source is JSON-only; build synthesizes the .html stub into dist.
    for stem, title in (("index", "Index"), ("about", "About")):
        (docs / f"{stem}.json").write_text(
            json.dumps(
                {
                    "kind": "page",
                    "title": title,
                    "meta": {"summary": f"{title} page"},
                    "blocks": [
                        {
                            "kind": "section",
                            "id": "s",
                            "title": "S",
                            "blocks": [{"kind": "paragraph", "content": f"Body of {title}"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    return tmp_path


class TestCLIBuild:
    def test_build_emits_all_artifacts(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        proc = _run_cli(docs, "build", repo_root=repo_root)
        assert proc.returncode == 0, f"build failed:\n{proc.stderr}\n{proc.stdout}"
        # Source dir stays clean — manifest / llms.txt / page.md twins
        # / .html stubs all live under dist/ only.
        for offender in (
            "site-manifest.json",
            "site-manifest.js",
            "llms.txt",
            "index.md",
            "about.md",
            "index.html",
            "about.html",
        ):
            assert not (docs / offender).exists(), f"{offender} leaked into source: must live under dist/"
        # dist/ trees carry the actual artifacts the runtime needs.
        assert (docs / "dist" / "standalone" / "index.html").exists()
        assert (docs / "dist" / "site" / "index.html").exists()
        assert (docs / "dist" / "site" / "_oku" / "chrome.css").exists()
        # site-manifest.json lives under dist/site/ only — chrome.js
        # fetches it at runtime when serving over HTTP. Standalone HTMLs
        # inline window.__okuManifest directly, so they don't need
        # a sidecar.
        assert (docs / "dist" / "site" / "site-manifest.json").exists()
        assert not (docs / "dist" / "standalone" / "site-manifest.json").exists()
        # The historical .js companion (set window.__okuManifest
        # via <script src>) is no longer emitted in either tree.
        assert not (docs / "dist" / "site" / "site-manifest.js").exists()
        assert not (docs / "dist" / "standalone" / "site-manifest.js").exists()
        # llms.txt lives at the site docs root; the .md SOURCES are the
        # canonical AI surface — no dist/markdown twin tree.
        assert (docs / "dist" / "site" / "llms.txt").exists()
        assert not (docs / "dist" / "markdown").exists()
        assert not (docs / "dist" / "standalone" / "llms.txt").exists()

    def test_manifest_sits_where_the_kit_does_when_building_from_the_root(
        self, sample_project: Path, repo_root: Path
    ) -> None:
        """Built from the PROJECT root with every page under docs/ — the
        standard layout. build_site copies the kit to dist/site/_oku/ and
        chrome.js derives the docs root from wherever _oku/ sits, so the
        manifest has to be at the site root with root-relative page paths.
        Writing it under dist/site/docs/ left every built page fetching a
        manifest that was not there, and the site tree came up empty."""
        proc = _run_cli(sample_project, "build", repo_root=repo_root)
        assert proc.returncode == 0, proc.stderr
        site = sample_project / "dist" / "site"
        assert (site / "site-manifest.json").exists()
        assert not (site / "docs" / "site-manifest.json").exists()
        assert (site / "llms.txt").exists()
        assert (site / "_oku" / "chrome.js").exists()
        manifest = json.loads((site / "site-manifest.json").read_text(encoding="utf-8"))
        paths = sorted(entry["path"] for entry in manifest["pages"])
        assert paths == ["docs/about.html", "docs/index.html"], paths
        # …and each of those paths resolves against the site root.
        for rel in paths:
            assert (site / rel).exists(), rel

    def test_manifest_lists_both_pages(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        manifest = json.loads((docs / "dist" / "site" / "site-manifest.json").read_text(encoding="utf-8"))
        titles = {entry["title"] for entry in manifest["pages"]}
        assert titles == {"Index", "About"}

    def test_standalone_is_self_contained(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        body = (docs / "dist" / "standalone" / "index.html").read_text(encoding="utf-8")
        # No external _kit references — everything inlined.
        assert 'href="_oku/chrome.css"' not in body
        assert 'src="_oku/chrome.js"' not in body
        # JSON content inlined for autoBoot.
        assert 'id="__oku_page__"' in body
        # The page body text shows up in the inlined JSON.
        assert "Body of Index" in body

    def test_site_html_has_pagefind_body_injection(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        body = (docs / "dist" / "site" / "index.html").read_text(encoding="utf-8")
        assert "data-pagefind-body" in body
        assert "Body of Index" in body

    def test_llms_txt_has_pages_section(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        text = (docs / "dist" / "site" / "llms.txt").read_text(encoding="utf-8")
        assert "## Pages" in text
        assert "Index" in text
        assert "About" in text


class TestCLIClean:
    def test_clean_removes_dist(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        assert (docs / "dist").exists()
        proc = _run_cli(docs, "clean", repo_root=repo_root)
        assert proc.returncode == 0, f"clean failed:\n{proc.stderr}\n{proc.stdout}"
        assert not (docs / "dist").exists()

    def test_clean_is_idempotent(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        # First run: nothing to clean — should succeed and print a friendly note.
        proc1 = _run_cli(docs, "clean", repo_root=repo_root)
        assert proc1.returncode == 0
        assert "Nothing to clean" in proc1.stdout

    def test_clean_does_not_touch_source(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        _run_cli(docs, "clean", repo_root=repo_root)
        # Source pages must survive.
        assert (docs / "index.json").exists()
        assert (docs / "about.json").exists()
        # _kit symlink must survive — it's not under dist/.
        assert (docs / "_oku").exists()


class TestCLIInit:
    # cmd_init operates on cwd directly — never on a "docs/" subdir.
    # Tests run init from tmp_path and assert outputs live there.

    def test_init_creates_kit_symlink_in_cwd(self, tmp_path: Path, repo_root: Path) -> None:
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        link = tmp_path / "_oku"
        assert link.is_symlink()
        # The symlink target is the resolver's choice — dev layout points
        # at <repo>/kit (chrome.css + schema/ both live there).
        target = Path(os.readlink(link))
        assert (target / "chrome.css").exists()
        # init does NOT create a docs/ subdir.
        assert not (tmp_path / "docs").exists()

    def test_init_is_idempotent(self, tmp_path: Path, repo_root: Path) -> None:
        # Running init twice in the same dir should succeed both times.
        proc1 = _run_cli(tmp_path, "init", repo_root=repo_root)
        proc2 = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc1.returncode == 0
        assert proc2.returncode == 0

    def test_init_creates_index_html_in_cwd(self, tmp_path: Path, repo_root: Path) -> None:
        # The on-disk stub at cwd/index.html is what makes IDE-served
        # workflows work (IntelliJ's HTTP server, Live Server, etc.)
        # — without it, only `oku serve` can render pages.
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        index = tmp_path / "index.html"
        assert index.exists()
        body = index.read_text(encoding="utf-8")
        # Stub must reference the kit (boot, css, main, renderer).
        # autoBoot is self-triggered by renderer.js — the stub no longer
        # carries an inline script.
        assert "_oku/chrome-boot.js" in body
        assert "_oku/chrome.css" in body
        assert "_oku/chrome.js" in body
        assert "_oku/renderer.js" in body

    def test_init_picks_title_from_existing_index_json(self, tmp_path: Path, repo_root: Path) -> None:
        # If cwd/index.json already exists, init should use its title
        # for the stub's <title> — otherwise the tab shows the generic
        # fallback until the renderer overwrites it.
        (tmp_path / "index.json").write_text(
            json.dumps({"kind": "page", "title": "My Project Docs", "blocks": []}),
            encoding="utf-8",
        )
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        body = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "<title>My Project Docs</title>" in body

    def test_init_does_not_overwrite_existing_index_html(self, tmp_path: Path, repo_root: Path) -> None:
        # Idempotency for index.html: a user-edited stub must survive
        # a re-run of `oku init`. "User-edited" = anything inside
        # <body> (the default stub leaves it empty).
        custom = "<!doctype html><html><body>HANDS OFF</body></html>"
        (tmp_path / "index.html").write_text(custom, encoding="utf-8")
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        assert (tmp_path / "index.html").read_text(encoding="utf-8") == custom

    def test_init_stamps_cache_buster_on_kit_urls(self, tmp_path: Path, repo_root: Path) -> None:
        # Static file servers (IntelliJ :63342, plain http.server) don't
        # send revalidation headers we control; without a query-string
        # buster, chrome.js / chrome.css / renderer.js sit in the
        # browser cache indefinitely. The stub stamps the latest kit
        # mtime so every kit change forces a fresh fetch.
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        body = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert re.search(r"_oku/chrome\.css\?v=\d+", body), body
        assert re.search(r"_oku/chrome\.js\?v=\d+", body), body
        assert re.search(r"_oku/chrome-boot\.js\?v=\d+", body), body
        assert re.search(r"_oku/renderer\.js\?v=\d+", body), body

    def test_init_refreshes_default_stub_with_new_cache_buster(self, tmp_path: Path, repo_root: Path) -> None:
        # An on-disk stub generated long ago has a stale ?v=N. Re-running
        # init must rewrite the URLs so the new kit mtime takes effect —
        # provided the stub is still default-shaped (empty body).
        stale = (
            "<!DOCTYPE html>\n<html><head>"
            '<script src="_oku/chrome-boot.js?v=1"></script>'
            '<link rel="stylesheet" href="_oku/chrome.css?v=1">'
            '<script src="_oku/chrome.js?v=1" defer></script>'
            '<script src="_oku/renderer.js?v=1" defer></script>'
            "</head><body></body></html>\n"
        )
        (tmp_path / "index.html").write_text(stale, encoding="utf-8")
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        refreshed = (tmp_path / "index.html").read_text(encoding="utf-8")
        # The stale ?v=1 must be gone; whichever fresh mtime got stamped,
        # it's almost certainly > 1.
        assert '?v=1"' not in refreshed
        m = re.search(r"_oku/chrome\.js\?v=(\d+)", refreshed)
        assert m is not None
        assert int(m.group(1)) > 1

    def test_init_refreshes_stale_kit_symlink(self, tmp_path: Path, repo_root: Path) -> None:
        # Stale symlink (left over from a moved kit checkout) should be
        # transparently refreshed to the resolver's current KIT_DIR.
        elsewhere = tmp_path / "stale-target"
        elsewhere.mkdir()
        (tmp_path / "_oku").symlink_to(elsewhere)
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        # The symlink now points at the kit, not the stale target.
        new_target = Path(os.readlink(tmp_path / "_oku"))
        assert (new_target / "chrome.css").exists()
        assert "Refreshed" in proc.stdout

    def test_init_refuses_to_overwrite_non_symlink_kit(self, tmp_path: Path, repo_root: Path) -> None:
        # A regular file or directory at cwd/_kit is user data; init
        # must not clobber it.
        (tmp_path / "_oku").mkdir()
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode != 0
        assert "_oku" in proc.stderr

    def test_init_does_not_create_json_twins(self, tmp_path: Path, repo_root: Path) -> None:
        # init must NOT write .json siblings next to .md / .html files —
        # source of truth stays the .md (or hand-authored .json). The
        # dev server synthesises the .json view in memory; the build
        # emits dist/ artifacts. Duplicating on disk is unacceptable.
        (tmp_path / "guide.md").write_text("# Guide\n\n## Setup\n\nbody\n", encoding="utf-8")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "deep.md").write_text("# Deep\n\n## X\n\nbody\n", encoding="utf-8")
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        assert not (tmp_path / "guide.json").exists(), "init must not generate a .json twin"
        assert not (tmp_path / "nested" / "deep.json").exists(), "init must not generate a .json twin"

    def test_init_does_not_overwrite_hand_authored_json(self, tmp_path: Path, repo_root: Path) -> None:
        # A hand-authored .json sibling of an .md takes precedence — init
        # must not clobber it.
        (tmp_path / "guide.md").write_text("# From MD", encoding="utf-8")
        hand = {"k": "page", "t": "Hand-authored", "b": []}
        (tmp_path / "guide.json").write_text(json.dumps(hand), encoding="utf-8")
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        # Hand-authored content must survive.
        kept = json.loads((tmp_path / "guide.json").read_text(encoding="utf-8"))
        assert kept.get("t") == "Hand-authored"

    def test_init_minimal_output(self, tmp_path: Path, repo_root: Path) -> None:
        # init's only side effects: create _oku symlink and write
        # index.html. No JSON twins, no other files.
        for name in ("README.md", "real.md"):
            (tmp_path / name).write_text(f"# {name}", encoding="utf-8")
        before = set(tmp_path.iterdir())
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        after = set(tmp_path.iterdir())
        new = after - before
        # Allowed new entries: _oku symlink + index.html.
        new_names = {p.name for p in new}
        assert new_names <= {"_oku", "index.html"}, f"init produced unexpected files: {new_names}"


class TestCLIHelp:
    def test_no_args_prints_help(self, tmp_path: Path, repo_root: Path) -> None:
        proc = _run_cli(tmp_path, repo_root=repo_root)
        assert proc.returncode == 0
        assert "usage:" in proc.stdout.lower() or "usage:" in proc.stderr.lower()

    def test_serve_help_lists_new_flags(self, tmp_path: Path, repo_root: Path) -> None:
        proc = _run_cli(tmp_path, "serve", "--help", repo_root=repo_root)
        assert proc.returncode == 0
        out = proc.stdout
        assert "--no-watch" in out
        assert "--no-search" in out


# ---------- migrate ----------


def test_migrate_converts_and_removes_the_json(tmp_path: Path, repo_root: Path) -> None:
    page = {"k": "page", "t": "Sayfa", "b": ["## Bölüm {#b}\n\nMetin.\n"]}
    (tmp_path / "p.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    proc = _run_cli(tmp_path, "migrate", repo_root=repo_root)
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "p.json").exists()
    assert "## Bölüm {#b}" in (tmp_path / "p.md").read_text(encoding="utf-8")


def test_migrate_keeps_json_when_asked(tmp_path: Path, repo_root: Path) -> None:
    page = {"k": "page", "t": "T", "b": ["## S {#s}\n\nx\n"]}
    (tmp_path / "p.json").write_text(json.dumps(page), encoding="utf-8")
    assert _run_cli(tmp_path, "migrate", "--keep-json", repo_root=repo_root).returncode == 0
    assert (tmp_path / "p.json").exists()
    assert (tmp_path / "p.md").exists()


def test_migrate_dry_run_writes_nothing(tmp_path: Path, repo_root: Path) -> None:
    page = {"k": "page", "t": "T", "b": ["## S {#s}\n\nx\n"]}
    (tmp_path / "p.json").write_text(json.dumps(page), encoding="utf-8")
    assert _run_cli(tmp_path, "migrate", "--dry-run", repo_root=repo_root).returncode == 0
    assert (tmp_path / "p.json").exists()
    assert not (tmp_path / "p.md").exists()


def test_migrate_refuses_to_delete_a_page_it_cannot_reproduce(tmp_path: Path, repo_root: Path) -> None:
    """The JSON is deleted after conversion, so a page carrying something
    the markdown emitter cannot express must keep its source instead of
    losing it silently."""
    page = {"k": "page", "t": "T", "b": ["## S {#s}\n\nx\n", {"k": "weird-kind", "x": 1}]}
    (tmp_path / "p.json").write_text(json.dumps(page), encoding="utf-8")
    proc = _run_cli(tmp_path, "migrate", repo_root=repo_root)
    assert proc.returncode == 0
    assert (tmp_path / "p.json").exists(), "source must survive a lossy conversion"
    assert not (tmp_path / "p.md").exists()
    assert "not lossless" in proc.stderr


# ---------- init starter page ----------


def test_init_seeds_a_starter_page_in_an_empty_docs_root(tmp_path: Path, repo_root: Path) -> None:
    """An empty docs root that renders nothing is a bad first minute.
    init drops a front-matter skeleton the author can type into."""
    proc = _run_cli(tmp_path, "init", repo_root=repo_root)
    assert proc.returncode == 0, proc.stderr
    md = tmp_path / "index.md"
    assert md.exists()
    body = md.read_text(encoding="utf-8")
    assert body.startswith("---\ntitle:")
    assert "[!TLDR]" in body
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "_oku").is_symlink()


def test_init_does_not_add_a_starter_next_to_existing_pages(tmp_path: Path, repo_root: Path) -> None:
    """init is idempotent and gets re-run constantly; it must never drop
    a stray index.md into a docs tree that already has pages."""
    (tmp_path / "guide.md").write_text("---\ntitle: G\n---\n\n## S\n\nx\n", encoding="utf-8")
    assert _run_cli(tmp_path, "init", repo_root=repo_root).returncode == 0
    assert not (tmp_path / "index.md").exists()


def test_init_keeps_an_existing_starter(tmp_path: Path, repo_root: Path) -> None:
    (tmp_path / "index.md").write_text("---\ntitle: Mine\n---\n\n## S\n\nmine\n", encoding="utf-8")
    assert _run_cli(tmp_path, "init", repo_root=repo_root).returncode == 0
    assert "mine" in (tmp_path / "index.md").read_text(encoding="utf-8")


def test_version_reports_the_kit_build_stamp(tmp_path: Path, repo_root: Path) -> None:
    """An installed tool carries its own COPY of the kit, and
    `uv tool install --force` reuses the cached wheel when the version
    string has not changed — so a stale tool looks freshly installed.
    `oku --version` is the one-command answer to "which kit is this
    tool actually building with?"."""
    proc = _run_cli(tmp_path, "--version", repo_root=repo_root)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip()
    assert out.startswith("oku ")
    # One line, whatever the terminal width. `./run install` reads the
    # `kit` and `src` fields back out of this with sed to decide whether
    # the global tool is stale; argparse's built-in version action wraps
    # at terminal width, and a wrap landing mid-field breaks that gate
    # silently. Adding `src` moved the wrap onto the space before the
    # assets path, which is how it was found.
    assert "\n" not in out, out
    assert " · kit " in out and " · src " in out and " · assets " in out
    stamp = (repo_root / "kit" / "chrome.js").read_text(encoding="utf-8")
    expected = re.search(r"__okuKitBuild\s*=\s*'([^']+)'", stamp).group(1)
    assert expected in out, out
