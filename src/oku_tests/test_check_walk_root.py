"""The walk root decides scope, not which links exist.

`oku check --strict` from the repo root reported this project's own
documentation clean. The same command from `docs/` reported nine
`unresolved-link` warnings — on links that build fine and open fine,
because `../examples/…/sample-guide.html` is what `oku build` writes
beside a source the docs-only walk never reached.

An author who runs the check from the directory they are editing in
gets a different answer than CI does, and the difference is all false.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from oku import cli

PAGE = """---
title: Guide
summary: A page linking to a page in a sibling tree.
---

## Links {#links}

- [built sibling](../examples/sample.html)
- [source sibling](../examples/sample.md)
- [nothing there](../examples/gone.html)
"""

SIBLING = """---
title: Sample
summary: The page the link names.
---

## Body {#body}

Text.
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "examples").mkdir()
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    (root / "docs" / "guide.md").write_text(PAGE, encoding="utf-8")
    (root / "examples" / "sample.md").write_text(SIBLING, encoding="utf-8")
    cli._project_root_cache.clear()
    return root


def _codes(root: Path, walk: Path) -> list[str]:
    cwd = Path.cwd()
    os.chdir(walk)
    try:
        pages = [(p, cli._page_from_source_file(p)) for p in sorted(walk.rglob("*.md"))]
        return [i["code"] for i in cli.check_pages(pages, root) if i["code"] == "unresolved-link"]
    finally:
        os.chdir(cwd)


def test_a_narrow_walk_reports_the_same_broken_links_as_a_wide_one(project: Path) -> None:
    wide = _codes(project, project)
    narrow = _codes(project, project / "docs")
    assert narrow == wide == ["unresolved-link"], (narrow, wide)


def test_the_link_that_is_really_broken_is_still_reported(project: Path) -> None:
    """The failure this fix could introduce: a `.html` with no source of
    any kind beside it has to stay a warning, or the check stops
    covering the case it exists for."""
    src = project / "docs" / "guide.md"
    issues = cli.check_pages([(src, cli._page_from_source_file(src))], project)
    broken = [i for i in issues if i["code"] == "unresolved-link"]
    assert len(broken) == 1, broken
    assert "gone.html" in broken[0]["message"], broken[0]


def test_a_json_source_counts_too(project: Path) -> None:
    """`.json` pages still render, so a link naming one that has not
    been built yet is not broken either."""
    (project / "examples" / "legacy.json").write_text(
        '{"schema_version": 2, "k": "page", "t": "Legacy", "b": []}', encoding="utf-8"
    )
    page = project / "docs" / "legacy-link.md"
    page.write_text(
        "---\ntitle: L\nsummary: One link.\n---\n\n## X {#x}\n\n[a](../examples/legacy.html)\n",
        encoding="utf-8",
    )
    issues = cli.check_pages([(page, cli._page_from_source_file(page))], project)
    assert [i for i in issues if i["code"] == "unresolved-link"] == []
