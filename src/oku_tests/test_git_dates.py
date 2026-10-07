"""How many times a build asks git for a date.

`updated` is derived from the file's last commit date — never the
mtime, because a fresh clone stamps every file with the checkout time
and the whole tree would render as "updated today". It cost one
`git log` subprocess per page: profiled on a 100-page tree,
`_git_last_modified` was 9.0s of a 12.9s build, and the newest pages
were the most expensive, because `git log -1 -- <file>` walks the whole
history before returning empty for a file git has never seen.

One `git log --name-only` per directory answers for every file in it —
and one at the tree's root answers for every directory under it: per
directory, a 126-directory tree ran 126 walks of the whole history at
~0.1 s each, 12.9 s of a 15.6 s manifest. A served tree drops its caches
on every save, which cannot change a date; the tree's answers are kept
while HEAD holds.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from oku import cli


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    (d / "docs").mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q")
    run("config", "user.email", "probe@example.com")
    run("config", "user.name", "Probe")
    for i in range(4):
        (d / "docs" / f"p{i}.md").write_text(f"page {i}\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-q", "-m", f"add p{i}", "--date", f"2026-0{i + 1}-15T12:00:00")
    cli._git_date_cache.clear()
    cli._git_dir_dates.clear()
    cli._git_tree_dates.clear()
    return d


def test_one_subprocess_answers_for_every_page_in_a_directory(repo: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    real = subprocess.run

    def counted(cmd, *a, **kw):
        if cmd and cmd[0] == "git":
            calls.append(list(cmd))
        return real(cmd, *a, **kw)

    monkeypatch.setattr(cli.subprocess, "run", counted)
    dates = [cli._git_last_modified(repo / "docs" / f"p{i}.md") for i in range(4)]

    assert all(dates), dates
    assert len(calls) == 1, f"{len(calls)} git invocations for 4 pages: {calls}"


def test_the_batched_answer_is_the_per_file_answer(repo: Path) -> None:
    """The speedup is worth nothing if it changes what the page says."""
    for i in range(4):
        f = repo / "docs" / f"p{i}.md"
        one = cli._git_date_one(f)
        cli._git_date_cache.clear()
        cli._git_dir_dates.clear()
        batched = cli._git_last_modified(f)
        assert one == batched, f"{f.name}: per-file {one}, batched {batched}"


def test_a_file_git_has_never_seen_costs_nothing_extra(repo: Path, monkeypatch) -> None:
    """The old worst case: `git log -1` on an unknown path walks the
    entire history to return empty, so the newest page was the slowest."""
    (repo / "docs" / "fresh.md").write_text("not committed\n", encoding="utf-8")
    cli._git_last_modified(repo / "docs" / "p0.md")  # warms the directory

    calls: list[list[str]] = []
    real = subprocess.run
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda cmd, *a, **kw: (calls.append(list(cmd)), real(cmd, *a, **kw))[1],
    )
    assert cli._git_last_modified(repo / "docs" / "fresh.md") is None
    assert calls == [], f"asked git again for a file it does not know: {calls}"


def test_a_directory_outside_a_repository_still_answers_none(tmp_path: Path) -> None:
    """git cannot answer here at all; the caller must get None rather
    than a traceback or a wrong date."""
    d = tmp_path / "loose"
    d.mkdir()
    f = d / "page.md"
    f.write_text("x\n", encoding="utf-8")
    cli._git_date_cache.clear()
    cli._git_dir_dates.clear()

    assert cli._git_last_modified(f) is None


# VIII.5 / XII.3: git quotes a non-ASCII path by default
# (core.quotePath), so `ölçüm.md` came back as
# "\303\266l\303\247\303\274m.md" and matched no file name. The directory
# answer had succeeded, so the per-file fallback never ran either: every
# page whose name is not ASCII lost `updated`, which in a Turkish tree is
# most of them.
@pytest.mark.parametrize("name", ["ölçüm.md", "İçerik notları.md", "概述.md"])
def test_a_page_named_in_any_script_gets_its_date(repo: Path, name: str) -> None:
    f = repo / "docs" / name
    f.write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "n", "--date", "2026-07-04T12:00:00"],
        cwd=repo,
        check=True,
        env={**os.environ, "GIT_COMMITTER_DATE": "2026-07-04T12:00:00"},
    )
    cli._git_dir_dates.clear()
    cli._git_date_cache.clear()
    assert cli._git_last_modified(f) == "2026-07-04"


# XII.2: git exports GIT_DIR into hooks, often relative (`.git`). The
# kit's git calls run with cwd set to the page's directory, where that
# relative path names nothing, so a build run from a pre-commit hook
# stamped no page with a date.
def test_a_build_run_from_a_git_hook_still_dates_its_pages(repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GIT_DIR", ".git")
    monkeypatch.setenv("GIT_WORK_TREE", ".")
    assert cli._git_last_modified(repo / "docs" / "p0.md") is not None


def _counting(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []
    real = subprocess.run

    def counted(cmd, *a, **kw):
        if cmd and cmd[0] == "git":
            calls.append(list(cmd))
        return real(cmd, *a, **kw)

    monkeypatch.setattr(cli.subprocess, "run", counted)
    return calls


def _nest(repo: Path) -> list[Path]:
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    files = [repo / "docs" / "a" / "x.md", repo / "docs" / "b" / "c" / "y.md"]
    for i, f in enumerate(files):
        f.parent.mkdir(parents=True)
        f.write_text(f"{f.name}\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-q", "-m", f"add {f.name}", "--date", f"2026-0{i + 6}-15T12:00:00")
    return files + [repo / "docs" / "p0.md"]


def test_one_log_answers_for_every_directory_of_a_tree(repo: Path, monkeypatch) -> None:
    files = _nest(repo)
    per_file = [cli._git_date_one(f) for f in files]
    calls = _counting(monkeypatch)
    cli._prime_git_dates(repo / "docs")
    assert [c[3] for c in calls] == ["rev-parse", "log"], calls
    assert [cli._git_last_modified(f) for f in files] == per_file
    assert len(calls) == 2, f"asked git again after the tree's one log: {calls[2:]}"


def test_a_save_asks_git_only_whether_head_moved(repo: Path, monkeypatch) -> None:
    files = _nest(repo)
    cli._prime_git_dates(repo / "docs")
    calls = _counting(monkeypatch)
    cli._forget_tree_state()  # what a served tree does on any save
    cli._prime_git_dates(repo / "docs")
    assert [c[3] for c in calls] == ["rev-parse"], calls
    # A commit moves HEAD, and the tree is read again.
    monkeypatch.undo()
    files[0].write_text("changed\n", encoding="utf-8")
    # %cs is the committer's date, which --date does not set.
    when = {**os.environ, "GIT_COMMITTER_DATE": "2026-09-15T12:00:00"}
    subprocess.run(["git", "commit", "-qam", "edit"], cwd=repo, env=when, check=True)
    cli._forget_tree_state()
    cli._prime_git_dates(repo / "docs")
    assert cli._git_last_modified(files[0]) == cli._git_date_one(files[0]) == "2026-09-15"
