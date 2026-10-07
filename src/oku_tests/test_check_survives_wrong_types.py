"""`oku check` reports a field of the wrong type; it never crashes on one.

A table fence holding `"rows": 3` ended `oku check` with a TypeError and a
traceback, saying nothing about the page — the schema finding that would
have named the field never printed. The rules after schema validation
iterated fields as though validation had already passed. An editor checks a
fence while it is being typed, which is when a field has the wrong type
most often, and lost every finding on the page with it.

The cases are derived from `kit/schema/examples.json`, not listed: every
shipped example with each field, and each field of its first row, replaced
by a value of every other JSON type. A block kind or chart type added
tomorrow is covered on the day it lands.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from oku import cli

WRONG = [3, "s", {"a": 1}, None, [1, 2], [{"x": 1}], True]


def _payloads() -> list[tuple[str, dict]]:
    examples = json.loads((cli.KIT_DIR / "schema" / "examples.json").read_text(encoding="utf-8"))
    found = [(kind, p) for kind, p in examples["blocks"].items() if isinstance(p, dict)]
    found += [("chart", p) for p in examples["charts"].values()]
    return found


def _mutants(payload: dict):
    for key in payload:
        if key == "type":  # a chart's type picks the rules; a wrong one is its own case
            continue
        for wrong in WRONG:
            yield key, {**payload, key: wrong}
        value = payload[key]
        if isinstance(value, list) and value and isinstance(value[0], dict):
            for sub in value[0]:
                for wrong in WRONG:
                    mutant = copy.deepcopy(payload)
                    mutant[key][0][sub] = wrong
                    yield f"{key}[0].{sub}", mutant


@pytest.mark.parametrize(
    ("kind", "payload"),
    _payloads(),
    ids=[f"{k}-{p.get('type', '')}".rstrip("-") for k, p in _payloads()],
)
def test_no_field_of_the_wrong_type_crashes_the_check(tmp_path: Path, kind: str, payload: dict) -> None:
    (tmp_path / ".git").mkdir()
    virtual = tmp_path / "p.json"
    crashed = []
    for where, mutant in _mutants(payload):
        page = {"k": "page", "t": "x", "m": {}, "b": [{"k": kind, **mutant}]}
        try:
            cli.check_pages([(virtual, page)], tmp_path)
        except Exception as e:  # the test is the census of these
            crashed.append(f"{where}: {type(e).__name__}: {e}")
    assert not crashed, crashed


def test_the_wrong_type_is_reported_where_it_used_to_crash(tmp_path: Path) -> None:
    pytest.importorskip("jsonschema")
    (tmp_path / ".git").mkdir()
    page = {"k": "page", "t": "x", "m": {}, "b": [{"k": "table", "headers": ["x"], "rows": 3}]}
    issues = cli.check_pages([(tmp_path / "p.json", page)], tmp_path)
    assert any(i["code"] == "schema" and "rows" in i["message"] for i in issues), issues
