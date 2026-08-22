"""What `oku migrate` proves before it deletes the source.

The command converts a page-JSON to a `.md` and unlinks the JSON. The
guard is a fingerprint comparison: convert, convert back, and refuse
unless the two match. It compared title, typed blocks and prose — and
not `m`, so every front-matter value the emitter could not write came
back missing or changed, the round trip was declared lossless, and the
only copy was removed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from oku import cli


def _round_trip(meta: dict) -> tuple[bool, dict]:
    page = {"k": "page", "t": "T", "m": dict(meta), "b": ["Body."]}
    back = cli.md_to_v2_page(cli.page_to_md(page), default_title="T")
    same = cli._page_content_fingerprint(page) == cli._page_content_fingerprint(back)
    return same, back.get("m") or {}


@pytest.mark.parametrize(
    ("meta", "note"),
    [
        ({"summary": "one\ntwo"}, "a multi-line value is not written at all"),
        ({"tags": ["a", "b"]}, "a list comes back as the string \"['a', 'b']\""),
    ],
)
def test_a_value_that_cannot_survive_stops_the_migration(meta: dict, note: str) -> None:
    same, _ = _round_trip(meta)
    assert not same, note


@pytest.mark.parametrize(
    "meta",
    [
        {"summary": "one line", "order": 3, "parent": "guide"},
        {"order": "007"},  # a zero-padded string, not the int 7
        {"flag": "true"},  # the word, not the boolean
        {"ver": "1.10"},  # a version, not the float 1.1
        {"empty": ""},
        {"pad": " x "},
        {"ratio": 1.5, "draft": True},
    ],
)
def test_an_ordinary_value_round_trips_unchanged(meta: dict) -> None:
    same, back = _round_trip(meta)
    assert same, back
    for key, value in meta.items():
        assert back[key] == value, f"{key}: {back[key]!r} != {value!r}"


def test_the_refusal_names_the_key_that_would_be_lost() -> None:
    """ "Report this page" gives the author nothing to look at; the answer
    is usually one key they can rewrite in ten seconds."""
    page = {"k": "page", "t": "T", "m": {"summary": "one\ntwo", "keep": "fine"}, "b": ["Body."]}
    back = cli.md_to_v2_page(cli.page_to_md(page), default_title="T")
    detail = cli._lossy_detail(cli._page_content_fingerprint(page), cli._page_content_fingerprint(back))
    assert "summary" in detail
    assert "keep" not in detail


def test_derived_values_are_not_expected_to_survive() -> None:
    """`_derived` names what the build works out again; re-emitting them
    into a source is what freezes them stale, so their absence from the
    markdown is correct, not a loss."""
    meta = {"summary": "s", "read_time": "~3 min read", "_derived": ["read_time"]}
    same, back = _round_trip(meta)
    assert same
    assert "read_time" not in back


def test_migrate_keeps_the_json_when_the_front_matter_would_not_survive(tmp_path: Path, capsys) -> None:
    """End to end, because the guard's whole job is deciding whether
    `p.unlink()` runs."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    src = docs / "p.json"
    src.write_text(
        json.dumps({"k": "page", "t": "T", "m": {"summary": "one\ntwo"}, "b": ["## S {#s}\n\nBody."]}),
        encoding="utf-8",
    )
    rc = cli.cmd_migrate(argparse.Namespace(path=str(src), dry_run=False, keep_json=False))
    err = capsys.readouterr().err

    assert src.exists(), "the source was deleted despite a lossy round trip"
    assert not (docs / "p.md").exists()
    assert "summary" in err
    assert rc == 0


def test_migrate_still_converts_a_page_it_can_carry(tmp_path: Path) -> None:
    """The control: the guard must not refuse everything."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    src = docs / "p.json"
    src.write_text(
        json.dumps(
            {"k": "page", "t": "T", "m": {"summary": "one line", "order": 2}, "b": ["## S {#s}\n\nBody."]}
        ),
        encoding="utf-8",
    )
    cli.cmd_migrate(argparse.Namespace(path=str(src), dry_run=False, keep_json=False))

    assert not src.exists()
    md = (docs / "p.md").read_text(encoding="utf-8")
    assert "summary: one line" in md
    assert "order: 2" in md
