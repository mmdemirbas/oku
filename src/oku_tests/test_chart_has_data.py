"""A chart with no data is caught, whatever its type.

The kit has 53 chart types and only 22 of them had a shape check. The
cost was measured rather than guessed: take each shipped example, empty
its main data array, and see what the gates say. Twelve types passed
clean. Drop the key entirely and seventeen did. Every one of those
renders a box with nothing in it — the wrong-but-valid failure the
briefing warns about, which no linter was catching.

Writing 53 per-type rules is how the first 22 were arrived at, and the
gap is what that approach produces. One rule covers every type instead:
a chart whose collections are all empty or absent cannot draw. Scalars
alone are never enough — even a gauge carries `zones`.

Three types needed a rule of their own on top. `bump`, `stream` and
`marimekko` read `categories` and their renderers return without drawing
when it is missing (chrome.js: `if (!categories.length || !series.length)
return;`), exactly like the two types the schema already covered.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from oku import cli


EXAMPLES = cli._load_examples()["charts"]


def _page(block: dict) -> dict:
    return {"k": "page", "t": "P", "m": {"summary": "s"}, "b": ["## S {#s}\n\nLead.\n", block]}


def _errors(block: dict, tmp_path: Path) -> list[str]:
    p = tmp_path / "p.json"
    schema = [msg for _p, msg in cli.validate_pages([(p, _page(block))])]
    structural = [
        i["code"] for i in cli.check_pages([(p, _page(block))], tmp_path) if i["severity"] == "error"
    ]
    return schema + structural


# `col_labels` and `marks` have renderer defaults, so a chart without
# them still draws. They are the only two, and naming them keeps the
# sweep below honest rather than loosening it.
OPTIONAL = {("heatmap", "col_labels"), ("plot", "marks")}


def _main_data_key(payload: dict) -> str | None:
    arrays = [k for k, v in payload.items() if isinstance(v, list) and v]
    return max(arrays, key=lambda k: len(payload[k])) if arrays else None


@pytest.mark.parametrize("ctype", sorted(EXAMPLES))
def test_an_emptied_chart_is_rejected(ctype: str, tmp_path: Path) -> None:
    payload = EXAMPLES[ctype]
    key = _main_data_key(payload)
    if key is None:
        # Its data is a dict, not an array — sunburst's `tree`,
        # calendar-heatmap's `date_values`. The general rule already
        # counts a non-empty dict, so there is nothing to mutate here.
        pytest.skip(f"{ctype} carries its data as an object, not an array")
    if (ctype, key) in OPTIONAL:
        pytest.skip(f"{ctype}.{key} has a renderer default")
    broken = {**copy.deepcopy(payload), key: [], "k": "chart"}

    assert _errors(broken, tmp_path), f"type:{ctype} with an empty `{key}` passed every gate"


@pytest.mark.parametrize("ctype", sorted(EXAMPLES))
def test_a_chart_missing_its_data_is_rejected(ctype: str, tmp_path: Path) -> None:
    payload = EXAMPLES[ctype]
    key = _main_data_key(payload)
    if key is None:
        # Its data is a dict, not an array — sunburst's `tree`,
        # calendar-heatmap's `date_values`. The general rule already
        # counts a non-empty dict, so there is nothing to mutate here.
        pytest.skip(f"{ctype} carries its data as an object, not an array")
    if (ctype, key) in OPTIONAL:
        pytest.skip(f"{ctype}.{key} has a renderer default")
    broken = {k: v for k, v in payload.items() if k != key} | {"k": "chart"}

    assert _errors(broken, tmp_path), f"type:{ctype} with no `{key}` passed every gate"


def test_a_chart_with_only_scalars_is_rejected(tmp_path: Path) -> None:
    """The general rule, stated directly: a title is not data."""
    errs = _errors({"k": "chart", "type": "bar", "title": "Nothing to see"}, tmp_path)

    assert any("chart-no-data" in e or "rows" in e for e in errs), errs


def test_the_message_names_the_command_that_fixes_it(tmp_path: Path) -> None:
    issues = cli.check_pages(
        [(tmp_path / "p.json", _page({"k": "chart", "type": "sankey", "title": "t"}))], tmp_path
    )
    msg = " ".join(i["message"] for i in issues)

    assert "oku spec sankey" in msg, msg


@pytest.mark.parametrize("ctype", sorted(EXAMPLES))
def test_no_shipped_example_is_caught_by_this(ctype: str, tmp_path: Path) -> None:
    """The rule has to be exactly as strict as reality: every payload
    that renders must pass. `test_spec_examples_render` proves all 53
    draw, so any rejection here is the rule being wrong."""
    assert _errors({**EXAMPLES[ctype], "k": "chart"}, tmp_path) == []
