"""`kit.json` is the one file in a tree that nothing read back.

It is not a page, so the schema pass never reached it, and it sat on the
exclusion list `find_json_pages` keeps so a stray `package.json` beside a
docs tree cannot break a build. Every reader of it in `cli.py` and in
`chrome.js` is a `get` with a default behind it, which is the right shape
for a file whose keys are all optional and the wrong shape for a file
nobody validates: a misspelling is not an error anywhere, it is the
setting silently not applying.

Measured before the fix, on this repo's own `docs/kit.json`: three of its
eleven keys — `languages`, `defaultLanguage`, `skip_gitignored` — were
not in the schema its first line points an editor at, and that schema
says `additionalProperties: false`. So the kit refused, in its published
contract, three keys the kit itself implements and CLAUDE.md documents,
and the file that named the contract was invalid against it.

Two directions, and both are held below: a key the tool reads must be in
the schema, and a key in the schema must be one the tool reads.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import pytest

from oku import cli

REPO = Path(__file__).resolve().parents[2]
CLI_SRC = REPO / "src" / "oku" / "cli.py"


def _page(title: str = "Probe") -> dict:
    """The smallest thing `check_pages` accepts, so a case about
    `kit.json` is not also a case about page shape."""
    return {
        "k": "page",
        "t": title,
        "m": {"summary": "One page, so the tree has something to walk."},
        "b": ["## Body {#body}", "A line of prose."],
    }


def _keys_read_from_a_kit_json() -> dict[str, str]:
    """Every `<var>.get("key")` where `<var>` was loaded out of a
    kit.json, mapped to the function that reads it.

    Derived rather than listed. A hand-written list is the failure this
    file exists for one layer up: the schema WAS the list, it fell five
    keys behind the tool, and nothing could see the gap because the two
    live in different files and neither reads the other.

    Anchored on the ASSIGNMENT — `data = json.loads(kit_json.read_text(
    …))` — rather than on the enclosing function mentioning kit.json,
    which was the first shape tried and reported `cmd_init` reading a
    `title`: that function writes a kit.json and reads a page dict, and
    a scan keyed on the word cannot tell those apart.

    `_tree_defaults` is invisible to this on purpose: it reads `accent`
    and `audience` through a loop variable, so there is no literal to
    find. Both are declared, and a scan that guessed at loop bodies
    would report keys nobody wrote.
    """
    source = CLI_SRC.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        holders = set()
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
                continue
            target = node.targets[0]
            call = node.value
            if not (isinstance(target, ast.Name) and isinstance(call, ast.Call)):
                continue
            loaded = ast.unparse(call)
            if loaded.startswith("json.loads(") and "kit" in loaded and ".read_text(" in loaded:
                holders.add(target.id)
        if not holders:
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in holders
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.setdefault(node.args[0].value, fn.name)
    return found


def test_the_schema_declares_every_key_the_tool_reads() -> None:
    """The direction that was broken. A key the tool honours and the
    schema refuses is a red squiggle in the author's editor on a setting
    that works — which trains them to stop believing the squiggles."""
    read = _keys_read_from_a_kit_json()
    # Vacuity guard: this scan is a regex-shaped thing wearing an AST,
    # and a scan that finds nothing agrees with every schema.
    assert len(read) >= 5, read
    known = set(cli._known_kit_keys())
    missing = {k: fn for k, fn in read.items() if k not in known}
    assert missing == {}, f"read by the tool, absent from project-kit.schema.json: {missing}"


def test_the_tool_reads_every_key_the_schema_declares() -> None:
    """And the reverse, which is an author configuring behaviour that
    left the tool. Checked against both source files, because the JS
    half of this config (`lang`, `lang_fallback`, `domains`, `glossary`,
    `extrefs`, `personalization`) is read in the browser and never by
    the CLI — and read there as a property access, `kit.lang_fallback`,
    with no quotes to look for.

    Loose on purpose: a bare `.key` match means a key whose name is a
    prefix of another would pass on its neighbour. The job here is to
    catch a WHOLLY dead key — one an author can set and nothing will
    ever look at — and a tighter rule that has to be told about each
    reading style is one that reports the next style as dead."""
    sources = (CLI_SRC.read_text(encoding="utf-8"), (REPO / "kit" / "chrome.js").read_text(encoding="utf-8"))
    dead = [
        key
        for key in cli._known_kit_keys()
        if key != "$schema"
        and not any(f'"{key}"' in src or f"'{key}'" in src or f".{key}" in src for src in sources)
    ]
    assert dead == [], f"declared in the schema, read by nothing: {dead}"


@pytest.mark.parametrize("name", ["docs/kit.json", "examples/kit.json"])
def test_this_project_s_own_config_validates(name: str) -> None:
    """The end this was found from. Both files carry the schema's URL in
    their first line, and `docs/kit.json` did not validate against it."""
    assert cli._kit_json_issues(REPO / name) == []


def _kit(tmp_path: Path, payload: str) -> Path:
    (tmp_path / "kit.json").write_text(payload, encoding="utf-8")
    return tmp_path / "kit.json"


def test_a_misspelled_key_is_named_with_the_spelling_that_would_have_worked(tmp_path: Path) -> None:
    """The concrete defect. `personalisation` costs the reader every
    `{{placeholder}}` in the tree and says nothing anywhere — and a
    report naming the typo without naming the fix leaves the author
    where they started, since the keys are printed in no other place."""
    path = _kit(tmp_path, json.dumps({"name": "p", "personalisation": []}))
    issues = cli._kit_json_issues(path)
    assert len(issues) == 1, issues
    where, message = issues[0]
    assert where == "personalisation"
    assert "personalization" in message


def test_a_value_of_the_wrong_shape_is_reported(tmp_path: Path) -> None:
    """The other half a typo takes. `"languages": "en,tr"` reads as a
    string, `declared_languages` iterates it into per-character codes,
    fewer than two survive `isinstance(c, str) and c`… and the site is
    monolingual with nothing said."""
    path = _kit(tmp_path, json.dumps({"languages": "en,tr"}))
    issues = cli._kit_json_issues(path)
    assert [w for w, _ in issues] == ["languages"], issues
    assert "array" in issues[0][1]


def test_a_nested_shape_is_reported_where_it_sits(tmp_path: Path) -> None:
    """`personalization` is a list of objects with two required fields,
    and an entry missing `label` renders a menu row with no name on it.
    The locator has to point INTO the file, not at it: a tree-wide
    config is long enough that "somewhere in kit.json" is a search."""
    path = _kit(tmp_path, json.dumps({"personalization": [{"key": "host"}]}))
    issues = cli._kit_json_issues(path)
    assert [w for w, _ in issues] == ["personalization.0"], issues


def test_a_malformed_kit_json_is_reported_once(tmp_path: Path) -> None:
    """A trailing comma reverts the accent, the domains, the languages
    and the reader placeholders for the whole tree, because every reader
    catches JSONDecodeError and returns its default. It is an error
    rather than a warning, and it belongs to the parse scan — reporting
    it here as well would put one file on two lines under two codes."""
    (tmp_path / "page.md").write_text("x", encoding="utf-8")
    path = _kit(tmp_path, '{"name": "p",}')
    assert cli._kit_json_issues(path) == []
    bad = cli.find_unparseable_json(tmp_path)
    assert [p.name for p, _ in bad] == ["kit.json"], bad


def test_the_check_reads_the_config_beside_the_pages_it_walks(tmp_path: Path) -> None:
    """The wiring, which is the half a helper with no caller passes
    without. Also the de-duplication: a tree of many pages shares one
    config, and reporting the same typo once per page is a report
    nobody reads to the end."""
    docs = tmp_path / "docs"
    docs.mkdir()
    _kit(docs, json.dumps({"skip_gitignore": True}))
    pages = [(docs / f"p{i}.md", _page(f"Page {i}")) for i in range(4)]
    issues = [i for i in cli.check_pages(pages, tmp_path) if i["code"] == "kit-invalid"]
    assert len(issues) == 1, issues
    assert issues[0]["severity"] == "warning"
    assert issues[0]["path"] == docs / "kit.json"
    assert "skip_gitignored" in issues[0]["message"]


def test_a_config_above_the_checked_tree_is_left_alone(tmp_path: Path) -> None:
    """`_tree_defaults` walks to the filesystem root because a page has
    to build wherever it sits. A check that did the same would report a
    file above the tree it was pointed at — on a machine where the home
    directory happens to carry one, a file the author has never seen."""
    (tmp_path / "kit.json").write_text(json.dumps({"nonsense": 1}), encoding="utf-8")
    inner = tmp_path / "docs"
    inner.mkdir()
    issues = cli.check_pages([(inner / "p.md", _page())], inner)
    assert [i for i in issues if i["code"] == "kit-invalid"] == []


def test_oku_spec_prints_every_key_the_schema_declares(capsys) -> None:
    """The other end of the same gap: `oku check` can now say a key is
    wrong, and until this branch existed there was nowhere to look up
    the right one. `oku spec` answered for 14 block kinds, 53 chart
    types and 3 inline kinds, and for the tree's own config it exited 1
    with `unknown name 'kit'`."""
    assert cli.cmd_spec(argparse.Namespace(name="kit", json=False)) == 0
    out = capsys.readouterr().out
    for key in cli._known_kit_keys():
        assert key in out, key
    # The message the check prints points here, so the pointer has to
    # resolve: a command named in a warning and answering nothing is the
    # same dead end one layer along.
    assert "kit-invalid" in out
