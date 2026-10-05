"""A file that is not UTF-8 is reported, never a traceback.

Every reader caught `JSONDecodeError` and `OSError`, and a decoding
failure is neither — `UnicodeDecodeError` is a `ValueError`. So one
Latin-1 file anywhere in a tree (a saved note, a data dump, a file an
older editor wrote) ended `oku check` and `oku build` with a traceback
and no report. Measured: `printf '{"a":"\\xe7"}' > data.json` beside a
good page, and `oku check` died in `codecs.decode`.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

GOOD = "---\ntitle: Good\n---\n\n## A {#a}\n\nText.\n"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "good.md").write_text(GOOD, encoding="utf-8")
    (tmp_path / "data.json").write_bytes(b'{"a":"\xe7"}')
    (tmp_path / "notes.md").write_bytes(b"---\ntitle: Notes\n---\n\nG\xfcl\n")
    return tmp_path


def test_check_reports_both_files_instead_of_crashing(tree: Path, capsys) -> None:
    cwd = Path.cwd()
    os.chdir(tree)
    try:
        cli.cmd_check(argparse.Namespace(path=None, strict=False, fix=False, json=False))
    finally:
        os.chdir(cwd)
    out = capsys.readouterr()
    text = out.out + out.err
    assert "data.json" in text
    assert "notes.md" in text


def test_build_still_ships_the_page_that_reads(tree: Path) -> None:
    cwd = Path.cwd()
    os.chdir(tree)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True))
    finally:
        os.chdir(cwd)
    assert rc == 0
    assert (tree / "dist" / "standalone" / "good.html").is_file()


def test_migrate_skips_a_json_it_cannot_decode(tree: Path) -> None:
    assert cli.cmd_migrate(argparse.Namespace(path=str(tree), dry_run=True, keep_json=False)) == 0
