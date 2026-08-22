"""How many times a build asks git for a date.

`updated` is derived from the file's last commit date — never the
mtime, because a fresh clone stamps every file with the checkout time
and the whole tree would render as "updated today". It cost one
`git log` subprocess per page: profiled on a 100-page tree,
`_git_last_modified` was 9.0s of a 12.9s build, and the newest pages
were the most expensive, because `git log -1 -- <file>` walks the whole
history before returning empty for a file git has never seen.

One `git log --name-only` per directory answers for every file in it.
"""

from __future__ import annotations

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
