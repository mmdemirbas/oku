"""Front-matter is discoverable, and a typo in it is not silent.

Every page has front-matter and it is the one part an author cannot
infer from the body they are writing. Measured before this: the schema
knew 10 keys, the skill briefing named 3 of them, and `parent` — used by
this repo's own pages — was in neither.

`$defs/meta` is `additionalProperties: true` on purpose, so a project can
carry its own keys. The cost was that a misspelling was accepted in
silence: `sumary:` produced nothing but the info-level no-summary nudge,
which is hidden at default verbosity, so the page shipped without a
summary and `oku check` said it was clean.

The rule that resolves both: permissive about unknown keys, loud about
one that looks like a known key spelled wrong.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from oku import cli


def _check(tmp_path: Path, front: str) -> list[dict]:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "p.md").write_text(
        f"---\ntitle: T\n{front}\n---\n\n## S {{#s}}\n\nLead paragraph.\n", encoding="utf-8"
    )
    return cli.check_pages(cli.find_json_pages(docs), docs)


@pytest.mark.parametrize(
    ("typo", "meant"),
    [("sumary", "summary"), ("ordering", "order"), ("acent", "accent"), ("parnet", "parent")],
)
def test_a_misspelled_key_is_flagged_with_the_real_one(typo: str, meant: str, tmp_path: Path) -> None:
    issues = [i for i in _check(tmp_path, f"summary: s\n{typo}: x") if i["code"] == "unknown-meta-key"]

    assert issues, f"{typo!r} was accepted in silence"
    assert meant in issues[0]["message"], issues[0]["message"]
    assert issues[0]["severity"] == "warning", "info is hidden at default verbosity"


def test_a_key_resembling_nothing_is_left_alone(tmp_path: Path) -> None:
    """`additionalProperties: true` is deliberate — a project may carry
    its own keys, and warning on those would train authors to ignore the
    check."""
    issues = [i for i in _check(tmp_path, "summary: s\nticket_id: ABC-1") if i["code"] == "unknown-meta-key"]

    assert issues == [], issues


def test_every_key_this_repo_uses_is_known(tmp_path: Path) -> None:
    """`parent` was used by these pages and absent from the schema, so
    the schema could not have caught a typo of it either."""
    import re

    known = set(cli._known_meta_keys())
    for page in Path("docs").glob("*.md"):
        m = re.match(r"---\n(.*?)\n---", page.read_text(encoding="utf-8"), re.S)
        if not m:
            continue
        used = {ln.split(":")[0].strip() for ln in m.group(1).splitlines() if ":" in ln and ln[:1].strip()}
        unknown = sorted(used - known)
        assert unknown == [], f"{page.name} uses {unknown}, which the schema does not define"


# ---------- discoverability ----------


def test_spec_prints_every_key_with_what_it_does(capsys) -> None:
    cli.cmd_spec(argparse.Namespace(name="front-matter", json=False))
    out = capsys.readouterr().out

    for key in cli._known_meta_keys():
        assert f"{key}:" in out, f"{key} is not in `oku spec front-matter`"
    # A key without an explanation is a key an author still has to guess.
    body = [ln for ln in out.splitlines() if ln.endswith(">") and ":" in ln]
    assert body == [], f"keys printed with no description: {body}"


def test_the_listing_mentions_it(capsys) -> None:
    """A discoverability feature nobody can discover is the failure the
    command exists to fix."""
    cli.cmd_spec(argparse.Namespace(name=None, json=False))
    out = capsys.readouterr().out

    assert "front-matter" in out, out


def test_the_derived_keys_are_marked_as_derived(capsys) -> None:
    """Hand-setting one freezes a value the build would keep current,
    and `hand-set-derivable` only says so after the fact."""
    cli.cmd_spec(argparse.Namespace(name="front-matter", json=False))
    out = capsys.readouterr().out

    for key in cli._DERIVABLE_META:
        line = next(ln for ln in out.splitlines() if ln.startswith(f"{key}:"))
        assert "DERIVED" in line and "do not hand-set" in line, line


def test_a_placeholder_left_in_prose_is_flagged(tmp_path: Path) -> None:
    """ "Word-search for placeholders before delivering" was a step in the
    skill's manual checklist. A checklist step is skipped in silence; a
    check is not."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "p.md").write_text(
        "---\ntitle: T\nsummary: s\n---\n\n## S {#s}\n\n"
        "Revenue rose to {{ figure }} last quarter.\n\nTODO: check this.\n\n"
        "We keep a todo list, which is ordinary prose.\n\n"
        "```python\n# TODO: inside code, not prose\npass\n```\n",
        encoding="utf-8",
    )
    issues = [i for i in cli.check_pages(cli.find_json_pages(docs), docs) if i["code"] == "placeholder-text"]
    found = {i["message"].split("placeholder ")[1].split(".")[0] for i in issues}

    assert len(issues) == 2, [i["message"] for i in issues]
    assert found == {"'{{ figure }}'", "'TODO'"}, found
