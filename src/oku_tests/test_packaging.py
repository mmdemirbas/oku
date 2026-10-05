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

import ast
import re
import shutil
import tomllib
from pathlib import Path

import pytest

# Not kit content: editor and OS droppings that would never be assets.
IGNORED = {".DS_Store"}

# Deliberately NOT packed, which is a different thing from forgotten —
# and the distinction is the whole point of the test above, so it is
# spelled out rather than added to IGNORED.
#
# `kit/vendor/` holds mermaid and Prism, fetched once per installation by
# `oku vendor`. Shipping them would put 3.3 MB into the wheel and the
# same 3.3 MB into git history on every upstream release, to deliver
# bytes that a single fetch already delivers once per machine. A missing
# vendor directory degrades to the CDN, which is what happens today.
UNPACKED = {"kit/vendor"}


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
    missing = sorted(on_disk - set(force_include) - UNPACKED)

    assert missing == [], (
        f"{missing} exist under kit/ but are not in "
        "[tool.hatch.build.targets.wheel.force-include]. Other projects would "
        "install an oku missing them."
    )


def test_the_unpacked_entries_are_a_cache_and_not_tracked(repo_root: Path):
    """An entry excused from the wheel must be one that is REGENERATED,
    never one someone forgot. `kit/vendor/` qualifies because `oku
    vendor` refetches it; the proof it is not authored content is that
    git does not track it. Without this, `UNPACKED` becomes a place to
    silence the check above."""
    import subprocess

    for entry in sorted(UNPACKED):
        proc = subprocess.run(
            ["git", "check-ignore", entry],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"{entry} is excused from the wheel but IS tracked by git — "
            "so it is authored content that simply is not shipped, which is "
            "the exact failure the packing check exists to catch."
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


# ---------- the source distribution ----------
#
# The list above is checked against the directory, and both agreed while
# `uv build` was failing outright: the sdist held nine files and not one
# kit asset, so the wheel built FROM it died on the first force-include.
# A test that reads configuration cannot see that — only one that builds
# can.


def _sdist_names(repo_root: Path, tmp_path: Path) -> list[str]:
    import subprocess
    import tarfile

    out = tmp_path / "dist"
    proc = subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(out)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    tarballs = sorted(out.glob("*.tar.gz"))
    assert tarballs, f"uv build wrote no sdist: {proc.stdout[-500:]}"
    with tarfile.open(tarballs[0]) as tf:
        return tf.getnames()


def test_the_sdist_carries_every_file_the_wheel_force_includes(
    repo_root: Path, tmp_path: Path, force_include: dict[str, str]
) -> None:
    """`uv build` builds the wheel from the sdist, so a source path
    missing there is a release that cannot be built at all — and the
    error names one file, which reads like a typo rather than an empty
    tree.

    The cause was symlinks: every `_oku` beside a page directory points
    at `../kit`, hatchling dedupes directories by inode as it walks, and
    `docs` and `examples` both sort before `kit`. The kit's inode was
    consumed under a name no include pattern matched, and `kit/` was
    skipped as already seen.
    """
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH")
    names = _sdist_names(repo_root, tmp_path)
    prefix = next((n.split("/")[0] for n in names if "/" in n), "")
    present = {n[len(prefix) + 1 :] for n in names}

    missing = []
    for source in force_include:
        src_path = repo_root / source
        if src_path.is_dir():
            wanted = {
                str(f.relative_to(repo_root))
                for f in src_path.rglob("*")
                if f.is_file() and f.name not in IGNORED
            }
        else:
            wanted = {source}
        missing.extend(sorted(w for w in wanted if w not in present))

    assert missing == [], f"the sdist is missing {len(missing)} kit file(s): {missing[:5]}"


def test_a_new_oku_symlink_cannot_reintroduce_it(repo_root: Path) -> None:
    """The exclusion is a glob, not the two paths that happened to exist:
    a fourth page directory gets an `_oku` the day someone runs
    `oku init` in it."""
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    sdist = data["tool"]["hatch"]["build"]["targets"]["sdist"]

    assert "**/_oku" in sdist.get("exclude", [])
    assert sdist.get("skip-excluded-dirs") is True


# The other half of "other projects read the installed tool": its
# CAPABILITIES. `oku verify` printed `uv tool install 'oku[verify]'` while
# no such extra existed, and `./ctl deploy` installed with no extras at
# all — so every session outside this repo found the browser check "not
# installed" and skipped it, and every dist/site shipped no search index.
_EXTRA_HINT = re.compile(r"oku\[([a-z,]+)\]")


def test_every_extra_a_hint_names_is_declared(repo_root: Path) -> None:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(data["project"]["optional-dependencies"])
    sources = [
        repo_root / "src" / "oku" / "cli.py",
        repo_root / "ctl",
        *sorted((repo_root / "docs").glob("*.md")),
    ]
    named = {
        (src.name, extra)
        for src in sources
        for m in _EXTRA_HINT.finditer(src.read_text(encoding="utf-8"))
        for extra in m.group(1).split(",")
    }
    assert named, "no oku[...] hint found; the scan is not reading what it should"
    assert {pair for pair in named if pair[1] not in declared} == set()


def test_deploy_installs_the_tool_with_its_capabilities(repo_root: Path) -> None:
    ctl = (repo_root / "ctl").read_text(encoding="utf-8")
    installs = [m.group(1).split(",") for m in _EXTRA_HINT.finditer(ctl)]
    assert any({"verify", "search"} <= set(extras) for extras in installs), installs


def _printed_strings(path: Path) -> list[tuple[int, str]]:
    """String constants in a module that are not docstrings: what the
    tool can print, as opposed to what it says about itself."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


# The fix that started this file's second half, applied to every hint.
# Measured before: the jsonschema hint said `uv tool install --force
# --no-cache --from . oku` (no extras, so following it removed playwright
# and pagefind again, and `.` is the reader's own project); both pagefind
# hints said `uv pip install 'pagefind[bin]'`, which installs into
# whatever venv is active and never into the tool the hint came from.
_FOREIGN_INSTALL = re.compile(r"\b(?:uv pip install|pip install|uv tool install)\b")


def test_every_install_hint_the_tool_prints_is_ctl_deploy(repo_root: Path) -> None:
    offenders = [
        (line, text.strip()[:90])
        for line, text in _printed_strings(repo_root / "src" / "oku" / "cli.py")
        if _FOREIGN_INSTALL.search(text)
    ]
    assert offenders == []


def test_the_docs_hand_no_one_the_bare_install(repo_root: Path) -> None:
    offenders = [
        f"{md.name}:{n}"
        for md in sorted((repo_root / "docs").glob("*.md"))
        for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"uv tool install \.", line)
    ]
    assert offenders == []
