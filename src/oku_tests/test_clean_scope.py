"""What `oku clean` is allowed to delete.

It was `shutil.rmtree(dist)`. `dist/` is a conventional name, not one
this tool owns — a project can keep a deploy script, a client's notes or
a checked-in data file in there — and the command removed all of it with
a one-line success message and no way back.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from oku import cli


def _project(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "standalone").mkdir(parents=True)
    (dist / "standalone" / "index.html").write_text("<p>built</p>", encoding="utf-8")
    (dist / "site" / "_oku").mkdir(parents=True)
    (dist / "site" / "index.html").write_text("<p>built</p>", encoding="utf-8")
    (dist / "_search" / "site").mkdir(parents=True)
    (dist / "_search" / "site" / "ghost.json").write_text("{}", encoding="utf-8")
    return tmp_path


def _clean(cwd: Path):
    old = Path.cwd()
    os.chdir(cwd)
    try:
        return cli.cmd_clean(argparse.Namespace())
    finally:
        os.chdir(old)


def test_a_file_the_project_put_there_survives(tmp_path: Path, capsys) -> None:
    root = _project(tmp_path)
    keep = root / "dist" / "NOTES-FROM-THE-CLIENT.md"
    keep.write_text("do not delete me", encoding="utf-8")
    (root / "dist" / "keepme").mkdir()
    (root / "dist" / "keepme" / "data.csv").write_text("a,b\n", encoding="utf-8")

    assert _clean(root) == 0
    out = capsys.readouterr().out

    assert keep.read_text(encoding="utf-8") == "do not delete me"
    assert (root / "dist" / "keepme" / "data.csv").exists()
    assert not (root / "dist" / "standalone").exists()
    assert not (root / "dist" / "site").exists()
    assert "NOTES-FROM-THE-CLIENT.md" in out, "the survivors are named, or nobody knows they are there"


def test_the_built_trees_all_go_including_the_serve_index(tmp_path: Path) -> None:
    """`dist/_search` was in neither the build's cleanup list nor the
    clean command's, so an index kept answering for pages the source no
    longer had."""
    root = _project(tmp_path)
    assert _clean(root) == 0
    assert not (root / "dist").exists()


def test_an_empty_dist_is_removed_with_it(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _clean(root)
    assert not (root / "dist").exists()


def test_a_symlinked_dist_is_reported_not_crashed(tmp_path: Path, capsys) -> None:
    """rmtree refuses a symlink with a raw OSError, which reads as a
    crash rather than as the safe outcome it is."""
    real = tmp_path / "elsewhere"
    (real / "standalone").mkdir(parents=True)
    root = tmp_path / "proj"
    root.mkdir()
    (root / "dist").symlink_to(real, target_is_directory=True)

    assert _clean(root) == 0
    assert "symlink" in capsys.readouterr().out
    assert (real / "standalone").exists()


def test_the_two_commands_agree_on_what_the_build_owns() -> None:
    """One list, because a tree in the build's cleanup and not in
    clean's (or the reverse) is how `dist/_search` went stale."""
    src = Path(cli.__file__).read_text(encoding="utf-8")
    assert src.count("for name in BUILD_TREES:") == 2
