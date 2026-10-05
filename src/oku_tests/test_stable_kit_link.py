"""A project's `_oku` link survives a reinstall of the tool.

`oku init` pointed `_oku` straight at the installed wheel's assets,
`…/uv/tools/oku/lib/python3.13/site-packages/oku/assets`. A reinstall
under another Python moves that directory, and every project's link
dangles at once: a stub opened from the editor renders an empty page
until someone thinks to run `oku init` in each project again.

Projects now point at ONE stable link (`$XDG_DATA_HOME/oku/kit`, by
default `~/.local/share/oku/kit`), and the installed tool keeps that
link pointing at its own assets every time it runs — so the first `oku`
command after a reinstall repairs every project together. A checkout
(`uv run`, `bin/oku`) never touches the stable link: it would otherwise
point every project on the machine at an uncommitted working copy.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import pytest

from oku import cli


@pytest.fixture
def installed(tmp_path: Path, monkeypatch) -> Path:
    stable = tmp_path / "share" / "oku" / "kit"
    monkeypatch.setattr(cli, "_stable_kit_link", lambda: stable)
    monkeypatch.setattr(cli, "_running_installed", lambda: True)
    return stable


def _init(docs: Path, monkeypatch) -> None:
    docs.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(docs)
    assert cli.cmd_init(argparse.Namespace()) == 0


def test_init_points_a_project_at_the_stable_link(tmp_path: Path, installed: Path, monkeypatch) -> None:
    docs = tmp_path / "proj" / "docs"
    _init(docs, monkeypatch)
    assert os.readlink(docs / "_oku") == str(installed)
    assert (docs / "_oku" / "chrome.css").is_file()


def test_a_reinstall_elsewhere_repairs_every_project_without_init(
    tmp_path: Path, installed: Path, monkeypatch
) -> None:
    docs = tmp_path / "proj" / "docs"
    _init(docs, monkeypatch)
    moved = tmp_path / "python3.14" / "assets"
    shutil.copytree(cli.KIT_DIR, moved, ignore=shutil.ignore_patterns("vendor"))
    monkeypatch.setattr(cli, "KIT_DIR", moved)
    cli._refresh_stable_kit_link()
    assert (docs / "_oku" / "chrome.css").resolve() == (moved / "chrome.css").resolve()


def test_init_moves_an_old_direct_link_onto_the_stable_one(
    tmp_path: Path, installed: Path, monkeypatch
) -> None:
    docs = tmp_path / "proj" / "docs"
    docs.mkdir(parents=True)
    (docs / "_oku").symlink_to(cli.KIT_DIR, target_is_directory=True)
    _init(docs, monkeypatch)
    assert os.readlink(docs / "_oku") == str(installed)


def test_a_checkout_links_directly_and_leaves_the_stable_link_alone(tmp_path: Path, monkeypatch) -> None:
    stable = tmp_path / "share" / "oku" / "kit"
    monkeypatch.setattr(cli, "_stable_kit_link", lambda: stable)
    monkeypatch.setattr(cli, "_running_installed", lambda: False)
    docs = tmp_path / "proj" / "docs"
    _init(docs, monkeypatch)
    assert (docs / "_oku").resolve() == cli.KIT_DIR.resolve()
    assert not stable.exists() and not stable.is_symlink()
