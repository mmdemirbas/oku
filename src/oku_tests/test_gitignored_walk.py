"""`skip_gitignored`: a project may declare .gitignore its skip list.

Opt-in, and off by default. Gitignore is a VERSION-CONTROL policy and
this is a PUBLICATION policy; they are not the same question. Plenty of
projects gitignore generated pages they fully intend to publish, and
with this on, editing `.gitignore` silently changes what the site
contains — action at a distance from a file nobody thinks of as build
configuration. So the default path below is the one that asserts the
most: a project that says nothing gets exactly the old walk.

Where the two policies do coincide the flag says so, and then the answer
is worth having. `SKIP_DIRS` can only list the names somebody
remembered, and the names that matter differ per project — `tmp`,
`build`, `out`, `target`, a recovered dataset, a scratch copy of the
file being edited.

The failure the flag introduces is a page that should build going
silently missing, so even switched on the mechanism has to be inert
where it cannot know better, and has to name itself where it acts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

PAGE = """---
title: {title}
summary: A page.
---

## Body {{#body}}

Text.
"""


def _repo(root: Path, ignore: str, *, opt_in: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text(ignore, encoding="utf-8")
    kit = {"name": "probe"}
    if opt_in:
        kit["skip_gitignored"] = True
    (root / "kit.json").write_text(json.dumps(kit), encoding="utf-8")
    return root


def _write(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.format(title=title), encoding="utf-8")


def _titles(root: Path) -> set[str]:
    cli._git_ignored_cache.clear()
    cli._project_skip_cache.clear()
    return {str(data.get("t") or data.get("title")) for _p, data in cli.find_json_pages(root)}


def test_a_project_that_says_nothing_gets_the_old_walk(tmp_path):
    """The default, and the whole reason the flag exists. A gitignored
    page still builds unless the project asked otherwise — what it keeps
    out of version control is its own business."""
    root = _repo(tmp_path / "r", "tmp/\n", opt_in=False)
    _write(root / "docs" / "real.md", "Real")
    _write(root / "tmp" / "scratch.md", "Scratch")

    assert _titles(root) == {"Real", "Scratch"}
    assert cli.git_ignored_paths(root) == frozenset()
    assert cli.ignored_paths_note(root) is None


def test_a_flag_that_is_not_true_is_not_opting_in(tmp_path):
    """`"skip_gitignored": "yes"` is a typo, not a yes. A truthy-string
    check would turn the feature on for a project that never asked."""
    root = _repo(tmp_path / "r", "tmp/\n", opt_in=False)
    (root / "kit.json").write_text('{"name": "probe", "skip_gitignored": "yes"}', encoding="utf-8")
    _write(root / "docs" / "real.md", "Real")
    _write(root / "tmp" / "scratch.md", "Scratch")

    assert _titles(root) == {"Real", "Scratch"}


def test_a_page_under_an_ignored_directory_is_not_a_page(tmp_path):
    root = _repo(tmp_path / "r", "tmp/\n")
    _write(root / "docs" / "real.md", "Real")
    _write(root / "tmp" / "scratch.md", "Scratch")

    assert _titles(root) == {"Real"}


def test_an_ignored_file_beside_a_real_one_is_not_a_page(tmp_path):
    """`--directory` collapses a wholly-ignored directory to one entry,
    but a single ignored file inside a live directory is listed on its
    own — and has to be dropped just the same."""
    root = _repo(tmp_path / "r", "docs/draft-*.md\n")
    _write(root / "docs" / "real.md", "Real")
    _write(root / "docs" / "draft-idea.md", "Draft")

    assert _titles(root) == {"Real"}


def test_a_tree_with_no_git_is_walked_exactly_as_before(tmp_path):
    """No repository means no opinion, not "nothing is ignored". A
    directory that was never a git repo has to keep building even with
    the flag set."""
    root = tmp_path / "plain"
    (root).mkdir(parents=True, exist_ok=True)
    (root / "kit.json").write_text('{"name": "probe", "skip_gitignored": true}', encoding="utf-8")
    _write(root / "docs" / "real.md", "Real")
    _write(root / "tmp" / "scratch.md", "Scratch")

    assert _titles(root) == {"Real", "Scratch"}


def test_a_root_that_is_itself_ignored_still_builds(tmp_path):
    """Run from inside an ignored directory git answers `./`, and every
    file under it looks like junk. A project that gitignores its own
    docs output would then build nothing at all, so the mechanism stands
    down instead."""
    root = _repo(tmp_path / "r", "generated/\n")
    _write(root / "generated" / "one.md", "One")
    _write(root / "generated" / "two.md", "Two")

    assert cli.git_ignored_paths(root / "generated") == frozenset()
    assert _titles(root / "generated") == {"One", "Two"}


def test_the_answer_is_the_same_on_a_second_call(tmp_path):
    """One subprocess per root. The walk asks for every suffix pass, and
    `oku build` walks four times."""
    root = _repo(tmp_path / "r", "tmp/\n")
    _write(root / "docs" / "real.md", "Real")
    cli._git_ignored_cache.clear()

    first = cli.git_ignored_paths(root)
    (root / ".gitignore").write_text("docs/\n", encoding="utf-8")
    assert cli.git_ignored_paths(root) == first, "the second call re-ran git"


def test_the_pruning_says_so_rather_than_going_quiet(tmp_path):
    """A page that stops building is the failure mode this introduces.
    One line naming the mechanism turns it from a mystery into a
    one-second diagnosis."""
    root = _repo(tmp_path / "r", "tmp/\nHANDOFF.md\n")
    _write(root / "docs" / "real.md", "Real")
    _write(root / "tmp" / "scratch.md", "Scratch")
    (root / "HANDOFF.md").write_text("notes", encoding="utf-8")
    cli._git_ignored_cache.clear()
    cli._project_skip_cache.clear()

    note = cli.ignored_paths_note(root)
    assert note and "git ignores them" in note, note
    assert "HANDOFF.md" in note or "tmp" in note, note


def test_the_line_names_only_what_git_contributed(tmp_path):
    """`dist`, `.idea` and `node_modules` were already skipped by
    SKIP_DIRS and the dot-prefix rule. Listing them says nothing about
    why a page is missing, and a line that is mostly noise is one nobody
    reads when it finally matters."""
    root = _repo(tmp_path / "r", "dist/\n.idea/\nnode_modules/\n")
    _write(root / "docs" / "real.md", "Real")
    for junk in ("dist", ".idea", "node_modules"):
        _write(root / junk / "x.md", junk)
    cli._git_ignored_cache.clear()
    cli._project_skip_cache.clear()

    assert cli.ignored_paths_note(root) is None
    assert _titles(root) == {"Real"}


def test_kit_json_skip_dirs_still_applies_without_git(tmp_path):
    """The two mechanisms are additive, not alternatives: a project can
    keep a directory out of the site while keeping it in git."""
    root = tmp_path / "plain"
    _write(root / "docs" / "real.md", "Real")
    _write(root / "logs" / "dump.md", "Dump")
    (root / "kit.json").write_text('{"name": "x", "skip_dirs": ["logs"]}', encoding="utf-8")
    # No git, no flag — `skip_dirs` is the direct way to say it and the
    # one that works everywhere.

    assert _titles(root) == {"Real"}
