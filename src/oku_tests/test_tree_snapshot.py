"""The tree snapshot reads the directories it watches and no others.

`oku preview --serve` snapshots a page's tree on every request, to tell
whether its cached manifest still holds. The walk used to enter every
directory and drop skipped paths afterwards, so a tree holding `.git`,
`.venv` or a build output paid for walking all of them on every render:
for a README at this repository's root, 605 ms of a 1.3 s render.
"""

from __future__ import annotations

import os
from pathlib import Path

from oku import cli


def _tree(root: Path) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
    (root / "README.md").write_text("# R\n", encoding="utf-8")
    for skipped in (".git", "node_modules", "build"):
        for i in range(20):
            d = root / skipped / f"d{i}"
            d.mkdir(parents=True)
            (d / "x.md").write_text("# X\n", encoding="utf-8")


def test_a_skipped_directory_is_never_listed(tmp_path, monkeypatch):
    _tree(tmp_path)
    listed: list[str] = []
    real = os.scandir

    def counting(path=".", *args, **kwargs):
        listed.append(os.fspath(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", counting)
    snapshot = cli._snapshot_tree(tmp_path)
    monkeypatch.undo()
    assert listed, "the walk listed nothing, so this test would hold for any walk"
    entered = sorted(Path(p).relative_to(tmp_path).as_posix() for p in listed)
    assert entered == [".", "docs"]
    assert sorted(Path(p).relative_to(tmp_path).as_posix() for p in snapshot) == ["README.md", "docs/a.md"]


def test_a_tree_under_a_directory_named_like_a_skipped_one_is_still_watched(tmp_path):
    root = tmp_path / "build" / "site"
    root.mkdir(parents=True)
    (root / "a.md").write_text("# A\n", encoding="utf-8")
    assert list(cli._snapshot_tree(root)) == [str(root / "a.md")]
