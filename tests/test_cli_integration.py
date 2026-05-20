"""End-to-end test of the html-doc CLI as a subprocess.

Most of the suite tests pure-function units; this file drives the actual
``bin/html-doc`` shim against a synthetic project and asserts on the
file-system output. It catches plumbing regressions that unit tests
can't see — argparse wiring, the chdir flow, build orchestration order.

Only ``init`` and ``build`` are covered here; ``serve`` opens a long-
running socket and a browser tab, which would make CI flaky.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(cwd: Path, *args: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Run bin/html-doc as a subprocess. We use the in-tree shim rather
    than an installed binary so the test stays portable — works against
    any clone, no pre-install step required."""
    proc = subprocess.run(
        [sys.executable, str(repo_root / "bin" / "html-doc"), *args],
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
    # _kit symlink — what `html-doc init` would have created.
    (docs / "_kit").symlink_to(repo_root)
    # Source is JSON-only; build synthesizes the .html stub into dist.
    for stem, title in (("index", "Index"), ("about", "About")):
        (docs / f"{stem}.json").write_text(
            json.dumps(
                {
                    "kind": "page",
                    "title": title,
                    "meta": {"summary": f"{title} page"},
                    "blocks": [
                        {"kind": "section", "id": "s", "title": "S",
                         "blocks": [{"kind": "paragraph", "content": f"Body of {title}"}]}
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
        for offender in ("site-manifest.json", "site-manifest.js", "llms.txt",
                         "index.md", "about.md", "index.html", "about.html"):
            assert not (docs / offender).exists(), (
                f"{offender} leaked into source: must live under dist/"
            )
        # dist/ trees carry the actual artifacts the runtime needs.
        assert (docs / "dist" / "standalone" / "index.html").exists()
        assert (docs / "dist" / "site" / "index.html").exists()
        assert (docs / "dist" / "site" / "_kit" / "chrome.css").exists()
        # Manifest + llms.txt land alongside the JSON pages in each dist
        # tree (the runtime fetches them via `__htmldocDocsRoot + ...`).
        assert (docs / "dist" / "site" / "site-manifest.json").exists()
        assert (docs / "dist" / "site" / "site-manifest.js").exists()
        assert (docs / "dist" / "site" / "llms.txt").exists()
        assert (docs / "dist" / "standalone" / "site-manifest.json").exists()
        # Twins ARE in dist (both flavors).
        assert (docs / "dist" / "site" / "index.md").exists()
        assert (docs / "dist" / "standalone" / "index.md").exists()

    def test_manifest_lists_both_pages(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        manifest = json.loads(
            (docs / "dist" / "site" / "site-manifest.json").read_text(encoding="utf-8")
        )
        titles = {entry["title"] for entry in manifest["pages"]}
        assert titles == {"Index", "About"}

    def test_standalone_is_self_contained(self, sample_project: Path, repo_root: Path) -> None:
        docs = sample_project / "docs"
        _run_cli(docs, "build", repo_root=repo_root)
        body = (docs / "dist" / "standalone" / "index.html").read_text(encoding="utf-8")
        # No external _kit references — everything inlined.
        assert 'href="_kit/chrome.css"' not in body
        assert 'src="_kit/chrome.js"' not in body
        # JSON content inlined for autoBoot.
        assert 'id="__htmldoc_page__"' in body
        # The page body text shows up in the inlined JSON.
        assert "Body of Index" in body

    def test_site_html_has_pagefind_body_injection(
        self, sample_project: Path, repo_root: Path
    ) -> None:
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


class TestCLIInit:
    def test_init_creates_kit_symlink(self, tmp_path: Path, repo_root: Path) -> None:
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        link = tmp_path / "docs" / "_kit"
        assert link.is_symlink()
        # The symlink target is the resolver's choice — dev layout points
        # at the repo root (where chrome.css lives next to schema/).
        target = Path(os.readlink(link))
        assert (target / "chrome.css").exists()

    def test_init_is_idempotent(self, tmp_path: Path, repo_root: Path) -> None:
        # Running init twice on the same project should succeed both times
        # — first creates, second sees the existing link and reports OK.
        proc1 = _run_cli(tmp_path, "init", repo_root=repo_root)
        proc2 = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc1.returncode == 0
        assert proc2.returncode == 0

    def test_init_creates_docs_index_html(self, tmp_path: Path, repo_root: Path) -> None:
        # The single on-disk stub at docs/index.html is what makes the
        # IDE-served workflow work — IntelliJ's HTTP server can serve it
        # without `html-doc serve` running.
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0, f"init failed:\n{proc.stderr}\n{proc.stdout}"
        index = tmp_path / "docs" / "index.html"
        assert index.exists()
        body = index.read_text(encoding="utf-8")
        # Stub must reference the kit (boot, css, main, renderer) so the
        # page actually renders when opened in a browser.
        assert "_kit/chrome-boot.js" in body
        assert "_kit/chrome.css" in body
        assert "_kit/chrome.js" in body
        assert "_kit/renderer.js" in body
        # autoBoot is what fetches the sibling JSON at load time.
        assert "autoBoot" in body

    def test_init_picks_title_from_existing_index_json(self, tmp_path: Path, repo_root: Path) -> None:
        # If docs/index.json already exists, init should use its title
        # for the stub's <title> element — otherwise the browser tab
        # shows "Documentation" until the renderer overwrites it.
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.json").write_text(
            json.dumps({"kind": "page", "title": "My Project Docs", "blocks": []}),
            encoding="utf-8",
        )
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        body = (docs / "index.html").read_text(encoding="utf-8")
        assert "<title>My Project Docs</title>" in body

    def test_init_does_not_overwrite_existing_index_html(self, tmp_path: Path, repo_root: Path) -> None:
        # Idempotency for index.html: a user-edited stub must survive
        # a re-run of `html-doc init`.
        docs = tmp_path / "docs"
        docs.mkdir()
        custom = "<!doctype html><html><body>HANDS OFF</body></html>"
        (docs / "index.html").write_text(custom, encoding="utf-8")
        proc = _run_cli(tmp_path, "init", repo_root=repo_root)
        assert proc.returncode == 0
        assert (docs / "index.html").read_text(encoding="utf-8") == custom


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
