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
    assert re.fullmatch(r"sha256:[0-9a-f]{12}", first), first


def test_the_digest_cannot_be_mistaken_for_a_commit() -> None:
    """Twelve bare hex characters in a version line is what an
    abbreviated git commit looks like. A reader holding a rendering
    defect ran `git cat-file -t` on one, got "Not a valid object name",
    and still could not tell whether their build predated the fix."""
    assert cli._tool_digest().startswith("sha256:"), cli._tool_digest()


def test_the_version_line_carries_a_date_that_orders() -> None:
    """A digest answers "same or different", never "older or newer".
    Ordering is the question a reader in another project is actually
    asking — "does this build have the fix that landed on the 22nd" —
    and it is the half that was missing."""
    before = cli._tool_dated()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", before), before

    out = subprocess.run(
        [sys.executable, "-c", "from oku.cli import main; main()", "--version"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    printed = out.stdout + out.stderr
    # Read after, too: the date is derived from file mtimes, so an edit
    # landing between the two reads is a real difference and not a bug
    # in either. Accepting both is what keeps this from failing on a
    # working tree someone is still typing into.
    assert any(f"as of {d}" in printed for d in (before, cli._tool_dated())), (before, printed)


def test_the_date_and_the_digest_read_the_same_files() -> None:
    """Two file lists is a version line whose halves can describe
    different builds."""
    files = cli._tool_files()
    assert files, "the digest covers nothing"
    assert cli.Path(cli.__file__) in files
    assert not [f for f in files if "vendor" in f.parts], "vendor is a cache and does not ship"


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


def test_the_vendor_cache_does_not_move_the_digest(tmp_path, monkeypatch) -> None:
    """`vendor/` is fetched, not authored, and deliberately absent from
    the wheel. Counting it made the repo's digest differ from the
    installed tool's permanently — a staleness gate that always fires,
    which is the failure this digest exists to prevent wearing the
    opposite sign. It reported drift on a tool that was current.
    """
    fake = tmp_path / "assets"
    (fake / "vendor" / "prism").mkdir(parents=True)
    (fake / "chrome.js").write_text("var __okuKitBuild = '2026-01-01';\n")
    monkeypatch.setattr(cli, "_kit_assets_dir", lambda: fake)
    before = cli._tool_digest()

    (fake / "vendor" / "mermaid.min.js").write_text("// 3.3 MB in real life\n")
    (fake / "vendor" / "prism" / "prism.min.js").write_text("// also fetched\n")

    assert cli._tool_digest() == before, "vendoring changed the digest"
