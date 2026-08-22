"""What `oku build` does when the check it runs finds an error.

The documented contract — CLAUDE.md, and the reason the build runs
`check_pages` at all — is that it "refuses to ship if it errors". It
printed the errors and shipped anyway, exit code 0, so a CI job went
green on a tree carrying a page the linter had rejected and the reader
got that page.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from oku import cli


def _project(tmp_path: Path, body: str) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "_oku").symlink_to(Path(cli.KIT_DIR), target_is_directory=True)
    (docs / "p.md").write_text(body, encoding="utf-8")
    (docs / "p.html").write_text(
        cli._stub_for("p", inline_manifest={"schema_version": 1, "root": ".", "pages": []}),
        encoding="utf-8",
    )
    cli._project_root_cache.clear()
    return tmp_path


def _build(cwd: Path, **kw) -> int:
    old = Path.cwd()
    os.chdir(cwd)
    try:
        return cli.cmd_build(argparse.Namespace(no_vendor=True, allow_errors=kw.get("allow_errors", False)))
    finally:
        os.chdir(old)


BROKEN = (
    "---\ntitle: Broken\nsummary: A chart whose payload the schema rejects.\n---\n\n"
    "## S {#s}\n\n```oku-chart\n"
    + json.dumps({"type": "bar", "rows": [{"label": "a", "value": "not-a-number"}]})
    + "\n```\n"
)
FINE = "---\ntitle: Fine\nsummary: An ordinary page.\n---\n\n## S {#s}\n\nProse.\n"


@pytest.mark.skipif(not cli._HAS_JSONSCHEMA, reason="schema validation needs jsonschema")
def test_a_page_the_check_rejects_stops_the_build(tmp_path: Path, capsys) -> None:
    root = _project(tmp_path, BROKEN)
    rc = _build(root)
    out = capsys.readouterr()

    assert rc == 1, "the build shipped a tree its own check had rejected"
    assert "Not building" in out.err
    assert not (root / "dist" / "standalone").exists()


@pytest.mark.skipif(not cli._HAS_JSONSCHEMA, reason="schema validation needs jsonschema")
def test_the_escape_hatch_still_ships(tmp_path: Path, capsys) -> None:
    """Nobody should be stuck: a consumer with one bad legacy page needs
    a way through, and it says so on the console when it takes it."""
    root = _project(tmp_path, BROKEN)
    rc = _build(root, allow_errors=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert "--allow-errors" in out
    assert (root / "dist" / "standalone" / "docs" / "p.html").exists()


def test_a_clean_tree_builds(tmp_path: Path) -> None:
    """The control — the refusal must be about errors, not about the
    check running at all."""
    root = _project(tmp_path, FINE)
    assert _build(root) == 0
    assert (root / "dist" / "standalone" / "docs" / "p.html").exists()
