"""Everything in kit/ reaches the installed wheel.

Other projects do not read this repo — they read the copy of `kit/` that
`uv tool install` packs into the wheel under `oku/assets/`. That copy is
assembled from a HAND-MAINTAINED list in pyproject.toml, one line per
top-level entry. A new kit file is therefore shipped only if someone
remembers to add it, and forgetting produces no error anywhere: the repo
renders it, the tests pass, and every other project silently builds
against a kit that is missing the file.

So the list is checked against the directory rather than trusted.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

# Not kit content: editor and OS droppings that would never be assets.
IGNORED = {".DS_Store"}


@pytest.fixture(scope="module")
def force_include(repo_root: Path) -> dict[str, str]:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]


def test_every_kit_entry_is_packed_into_the_wheel(repo_root: Path, force_include: dict[str, str]):
    on_disk = {
        f"kit/{p.name}"
        for p in sorted((repo_root / "kit").iterdir())
        if p.name not in IGNORED and not p.name.startswith(".")
    }
    missing = sorted(on_disk - set(force_include))

    assert missing == [], (
        f"{missing} exist under kit/ but are not in "
        "[tool.hatch.build.targets.wheel.force-include]. Other projects would "
        "install an oku missing them."
    )


def test_the_wheel_list_names_nothing_that_is_gone(repo_root: Path, force_include: dict[str, str]):
    """The mirror failure: a kit file is renamed or removed and the
    packaging line outlives it. Hatch fails the build on a missing
    force-include source, so this turns a broken `uv tool install` into a
    failing test here."""
    stale = sorted(src for src in force_include if not (repo_root / src).exists())

    assert stale == [], f"{stale} are listed in pyproject.toml but not on disk"


def test_every_kit_entry_lands_under_the_assets_root(force_include: dict[str, str]):
    """`_kit_assets_dir()` in cli.py looks for `oku/assets/` beside the
    package. A destination outside it would be packed and never found."""
    astray = sorted(
        f"{src} -> {dest}" for src, dest in force_include.items() if not dest.startswith("oku/assets/")
    )

    assert astray == [], astray
