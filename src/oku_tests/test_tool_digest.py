"""The installed tool can be told apart from this repo's code.

`./run install` used to verify one thing: the kit build stamp. That stamp
is hand-bumped and lives in chrome.js, so it answers "did the kit change"
and nothing else. A change to cli.py moves neither the stamp nor the
version string, and `uv tool install` reuses its cached wheel when the
version has not changed — so a CLI-only change could leave the global
tool on old code while every signal said it was current.

That is not hypothetical. The global tool reported the same version and
the same kit stamp as the repo while running a cli.py without a check
that had been added to it, so `oku check --strict` reported a tree clean
that the repo source warns about. The verify gate returned success from
stale code, which is worse than returning it slowly.

The digest is derived from the bytes that ship, so unlike a stamp it
cannot be forgotten on the day it matters.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from oku import cli


def test_the_digest_is_stable_and_short() -> None:
    first = cli._tool_digest()
    assert first == cli._tool_digest(), "digest is not deterministic"
    assert re.fullmatch(r"[0-9a-f]{12}", first), first


def test_the_version_string_carries_it() -> None:
    """`./run install` reads it back out of `oku --version`, so the shape
    of that line is load-bearing."""
    out = subprocess.run(
        [sys.executable, "-c", "from oku.cli import main; main()", "--version"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    printed = out.stdout + out.stderr
    assert f"src {cli._tool_digest()}" in printed, printed


def test_an_asset_change_moves_the_digest(tmp_path, monkeypatch) -> None:
    """The half the kit stamp already covered — kept because the digest
    now carries it, and a digest blind to assets would silently narrow
    what install verifies."""
    fake = tmp_path / "assets"
    fake.mkdir()
    (fake / "chrome.js").write_text("var __okuKitBuild = '2026-01-01';\n")
    monkeypatch.setattr(cli, "_kit_assets_dir", lambda: fake)
    before = cli._tool_digest()

    (fake / "chrome.js").write_text("var __okuKitBuild = '2026-01-02';\n")
    after = cli._tool_digest()

    assert before != after, "an edited asset left the digest unchanged"


def test_a_cli_change_moves_the_digest(tmp_path) -> None:
    """The half that was missing, and the reason this exists. Two copies
    of the package differing only in cli.py must not report the same
    digest."""
    pkg_root = Path(cli.__file__).resolve().parent
    assets = cli._kit_assets_dir()

    def digest_of(where: Path) -> str:
        out = subprocess.run(
            [sys.executable, "-c", "from oku.cli import _tool_digest; print(_tool_digest())"],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(where.parent), "PATH": ""},
            cwd=str(where.parent),
        )
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()

    for name in ("a", "b"):
        dest = tmp_path / name / "oku"
        dest.parent.mkdir()
        shutil.copytree(pkg_root, dest, ignore=shutil.ignore_patterns("__pycache__", "assets"))
        # Same assets for both, so only cli.py can differ.
        (dest / "assets").symlink_to(assets, target_is_directory=True)

    unchanged = digest_of(tmp_path / "a" / "oku")
    edited_path = tmp_path / "b" / "oku" / "cli.py"
    edited_path.write_text(edited_path.read_text() + "\n# one more line\n")
    edited = digest_of(tmp_path / "b" / "oku")

    assert unchanged and edited
    assert unchanged != edited, "a cli.py edit left the digest unchanged — the gap is still open"
