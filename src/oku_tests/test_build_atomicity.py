"""A failed build costs the new pages, never the old ones.

`cmd_build` used to remove every output tree and then write the new
pages into the hole. Anything failing in between left the reader's copy
deleted and the replacement half-written — measured on a 12 MB disk
image: `dist/standalone` ended holding one 0-byte page, and the build it
replaced was gone.

The order is now write-beside-then-swap. Everything lands in
`dist/.build-<pid>/`, and the first statement that touches the previous
output is a pair of renames after the last byte is written.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from oku import cli

PAGE = """---
title: {title}
summary: A page for the atomicity tests.
---

## Body {{#body}}

Text for {title}.
"""


def _args(**kw):
    base = {"no_search": True, "no_vendor": True, "allow_errors": False}
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    root = (tmp_path / "proj").resolve()
    root.mkdir()
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    for stem in ("alpha", "beta"):
        (root / f"{stem}.md").write_text(PAGE.format(title=stem.title()), encoding="utf-8")
    cli._project_root_cache.clear()
    monkeypatch.chdir(root)
    return root


def _built_state(root: Path) -> dict:
    """Everything a reader would notice about the output tree."""
    dist = root / "dist"
    return {
        str(p.relative_to(dist)): p.stat().st_size
        for p in sorted(dist.rglob("*"))
        if p.is_file() and not p.name.startswith(".")
    }


def test_a_clean_build_leaves_no_staging_directory(project: Path) -> None:
    assert cli.cmd_build(_args()) == 0
    dist = project / "dist"
    assert (dist / "standalone" / "alpha.html").is_file()
    assert (dist / "site" / "alpha.html").is_file()
    assert [p.name for p in dist.iterdir() if p.name.startswith(".build-")] == []
    assert [p.name for p in dist.iterdir() if p.name.startswith(".old-")] == []


def test_a_build_that_fails_leaves_the_previous_one_standing(project: Path, monkeypatch, capsys) -> None:
    assert cli.cmd_build(_args()) == 0
    before = _built_state(project)
    assert before, "nothing was built, so nothing is being protected"
    capsys.readouterr()

    real = cli.build_site

    def explode(*a, **kw):
        real(*a, **kw)  # write most of it, then fail like a full disk
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cli, "build_site", explode)
    assert cli.cmd_build(_args()) == 1
    err = capsys.readouterr().err
    assert "No space left on device" in err
    assert "previous build still stands" in err
    assert _built_state(project) == before


def test_a_build_that_fails_early_leaves_the_previous_one_standing(project: Path, monkeypatch) -> None:
    """The other half of the window: failing before a single page of the
    new build is written used to be just as destructive, because the old
    trees were already gone."""
    assert cli.cmd_build(_args()) == 0
    before = _built_state(project)

    def explode(*a, **kw):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(cli, "build_standalone", explode)
    assert cli.cmd_build(_args()) == 1
    assert _built_state(project) == before


def test_a_failed_build_cleans_up_after_itself(project: Path, monkeypatch) -> None:
    """Staging is named after the process, so a leftover would silently
    accumulate one directory per failed build."""
    real = cli.build_standalone

    def explode(*a, **kw):
        real(*a, **kw)  # staging exists by the time this raises
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cli, "build_standalone", explode)
    assert cli.cmd_build(_args()) == 1
    dist = project / "dist"
    # Failing before the first write leaves no dist/ at all, which is the
    # same promise stated more strongly.
    leftovers = [p.name for p in dist.iterdir() if p.name.startswith(".")] if dist.is_dir() else []
    assert leftovers == [], leftovers


def test_a_file_of_yours_under_dist_survives_a_build(project: Path) -> None:
    """The swap moves the trees the build owns. `dist/` is a conventional
    name, not one this tool owns — the same reasoning `oku clean` runs
    on."""
    dist = project / "dist"
    dist.mkdir()
    keep = dist / "deploy-notes.md"
    keep.write_text("mine", encoding="utf-8")
    assert cli.cmd_build(_args()) == 0
    assert keep.read_text(encoding="utf-8") == "mine"


def test_a_tree_this_build_did_not_write_is_still_swept(project: Path) -> None:
    """`dist/_search` outliving the pages it indexed was a real defect —
    the sweep moved to swap time, it did not go away."""
    stale = project / "dist" / "_search"
    stale.mkdir(parents=True)
    (stale / "index.json").write_text("[]", encoding="utf-8")
    assert cli.cmd_build(_args()) == 0
    assert not stale.exists()


def test_the_first_build_needs_no_previous_one(project: Path) -> None:
    assert not (project / "dist").exists()
    assert cli.cmd_build(_args()) == 0
    assert (project / "dist" / "standalone" / "beta.html").is_file()
