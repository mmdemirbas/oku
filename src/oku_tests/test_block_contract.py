"""A page that cannot render must not pass `oku check`.

A real page shipped with two bands of white space where a table should
have been, a step flow showing the numerals 1-4 and nothing else, and a
KPI grid printing the literal string "undefined" three times. `oku check`
had called it clean.

Three separate failures had to line up, and each one is pinned here:

1. **`jsonschema` was an optional dependency.** The installed tool did
   not have it, so `validate_page_schema` returned `[]` and only the
   structural checks ran — while the report still printed a tick. It is
   a hard dependency now, and the check refuses to print success if the
   pass did not run.

2. **The check stopped at the first schema error per page.** The page
   had eight bad blocks; one was named. An author fixes it, re-runs,
   and learns about the next.

3. **The renderer degraded instead of failing.** It read fields that
   were not there and rendered whatever came back, so a malformed block
   produced blank space or the word "undefined" rather than saying what
   was wrong. It now checks a contract mirroring the schema first.

The contract is a copy of the schema's `required` arrays, because the
renderer cannot fetch the schema at runtime. A copy drifts, so the first
test regenerates it and fails on any difference.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from oku import cli

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "kit" / "schema" / "page.schema.json"
RENDERER = REPO / "kit" / "renderer.js"


def _contract_from_schema() -> dict[str, dict]:
    defs = json.loads(SCHEMA.read_text(encoding="utf-8"))["$defs"]
    out: dict[str, dict] = {}
    for value in defs.values():
        if not isinstance(value, dict) or "properties" not in value:
            continue
        k = value["properties"].get("k")
        if not (isinstance(k, dict) and "const" in k):
            continue
        required = [r for r in value.get("required", []) if r != "k"]
        items: dict[str, list[str]] = {}
        for prop, spec in value["properties"].items():
            if isinstance(spec, dict) and spec.get("type") == "array" and isinstance(spec.get("items"), dict):
                item_required = list(spec["items"].get("required", []))
                if item_required:
                    items[prop] = item_required
        if required or items:
            entry: dict = {}
            if required:
                entry["required"] = required
            if items:
                entry["items"] = items
            out[k["const"]] = entry
    return out


def _contract_from_renderer() -> dict[str, dict]:
    """Parse `OkuRenderer.BLOCK_CONTRACT = { … };` out of renderer.js.

    A JS object literal with bare keys is not JSON, so the keys and the
    single quotes are normalised before parsing. Deliberately dumb: the
    failure mode should be "the table moved, fix the test", never "the
    parser silently matched nothing".
    """
    src = RENDERER.read_text(encoding="utf-8")
    m = re.search(r"OkuRenderer\.BLOCK_CONTRACT\s*=\s*\{(.*?)\n  \};", src, re.S)
    assert m, "BLOCK_CONTRACT literal not found in renderer.js"
    body = m.group(1)
    body = re.sub(r"([{,]\s*)([A-Za-z_][\w-]*)\s*:", r'\1"\2":', body)  # bare keys
    body = body.replace("'", '"')
    text = "{" + body + "}"
    # After wrapping, not before — the literal's last entry has a
    # trailing comma with nothing after it until the closing brace is
    # added, so stripping first misses exactly that one.
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def test_the_renderer_contract_matches_the_schema():
    """The renderer must demand exactly what the schema demands. If the
    schema gains a required field and this copy does not, the renderer
    goes back to rendering a broken block as blank space."""
    assert _contract_from_renderer() == _contract_from_schema(), (
        "BLOCK_CONTRACT in kit/renderer.js has drifted from page.schema.json — "
        "regenerate it from the schema rather than hand-editing"
    )


# ---------- every bad block is reported, not the first ----------

BAD_PAGE = """---
title: Broken
summary: Three blocks the renderer cannot read.
---

## One {#one}

```oku-table
{"columns":[{"key":"a","label":"A"}],"rows":[{"a":"1"}]}
```

```oku-kpi-grid
{"tiles":[{"label":"WER","value":"0.18"}]}
```

```oku-step-flow
{"steps":[{"title":"Decode","detail":"31 hours"}]}
```
"""


def test_every_malformed_block_is_reported(tmp_path):
    src = tmp_path / "broken.md"
    src.write_text(BAD_PAGE, encoding="utf-8")
    page = cli._page_from_source_file(src)
    assert page is not None
    errors = cli.validate_pages([(src, page)])
    blocks = {e[1].split(":", 1)[0] for e in errors}
    assert len(blocks) == 3, f"expected all three bad blocks, got {sorted(blocks)}"


def test_one_error_per_block_not_per_anyof_branch(tmp_path):
    """A block that fails `anyOf` emits a sub-error for every branch it
    did not match. Printing forty of those for one bad table buries the
    page it is trying to describe."""
    src = tmp_path / "broken.md"
    src.write_text(BAD_PAGE, encoding="utf-8")
    page = cli._page_from_source_file(src)
    errors = cli.validate_pages([(src, page)])
    assert len(errors) == 3, f"{len(errors)} errors for 3 bad blocks: {[e[1][:60] for e in errors]}"


def test_a_good_page_still_validates_clean(tmp_path):
    src = tmp_path / "fine.md"
    src.write_text(
        "---\ntitle: Fine\nsummary: Correct payloads.\n---\n\n## One {#one}\n\n"
        '```oku-kpi-grid\n{"tiles":[{"num":"0.18","label":"WER"}]}\n```\n\n'
        '```oku-step-flow\n{"steps":[{"t":"Decode","b":"31 hours"}]}\n```\n\n'
        "| A | B |\n|---|---|\n| 1 | 2 |\n",
        encoding="utf-8",
    )
    page = cli._page_from_source_file(src)
    assert cli.validate_pages([(src, page)]) == []


# ---------- the check cannot report success it did not earn ----------


def test_jsonschema_is_a_hard_dependency():
    """It was optional, and every `uv tool install` produced a copy of
    the tool whose schema pass silently did nothing."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies = \[(.*?)\]", pyproject, re.S | re.M)
    assert block, "no [project] dependencies array"
    assert "jsonschema" in block.group(1), (
        "jsonschema is not a runtime dependency — the schema check will no-op "
        "in every installed copy of the tool"
    )
    assert cli._HAS_JSONSCHEMA, "jsonschema is not importable in this environment"


def test_check_refuses_to_print_clean_when_the_schema_pass_did_not_run(tmp_path, monkeypatch, capsys):
    """Belt and braces for a broken install: without jsonschema the run
    must fail loudly rather than print a tick for a pass that never
    happened."""
    (tmp_path / "ok.md").write_text(
        "---\ntitle: Ok\nsummary: S.\n---\n\n## One {#one}\n\nText.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_HAS_JSONSCHEMA", False)
    args = type(
        "A", (), {"errors_only": False, "verbose": False, "strict": False, "quiet": False, "json": False}
    )()
    rc = cli.cmd_check(args)
    out = capsys.readouterr()
    assert rc == 1, "a run without schema validation exited 0"
    assert "did not run" in (out.err + out.out)
    assert "clean" not in out.out


@pytest.mark.parametrize(
    ("kind", "payload", "missing"),
    [
        ("kpi-grid", {"k": "kpi-grid", "tiles": [{"label": "WER", "value": "0.18"}]}, "num"),
        ("step-flow", {"k": "step-flow", "steps": [{"title": "Decode"}]}, "t"),
        ("compare-grid", {"k": "compare-grid", "cards": [{"title": "A"}]}, "t"),
        ("chart", {"k": "chart", "rows": [{"label": "a", "value": 1}]}, "type"),
    ],
)
def test_the_shapes_that_shipped_are_all_rejected(kind, payload, missing, tmp_path):
    """The exact payloads from the page that shipped broken, each named
    by the field the renderer needed and did not get."""
    page = {"k": "page", "t": "T", "b": [payload]}
    errors = cli.validate_pages([(tmp_path / "p.json", page)])
    assert errors, f"{kind} with a missing `{missing}` validated clean"
