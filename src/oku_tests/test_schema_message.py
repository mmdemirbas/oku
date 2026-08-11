"""A schema failure names the fix; it does not read the payload back.

`$defs/block` is an `anyOf`, so every malformed block fails it the same
way — jsonschema words that rejection as "<the entire instance> is not
valid under any of the given schemas". Three things were wrong with
that, and they compound:

- the echo is the author's own JSON, which they already have;
- it says nothing about what to change;
- it grows with the payload. Measured on a 14-node sankey written with
  `edges` where the schema wants `links`, the run printed 1372 bytes and
  1235 of them were the echo.

A block declares which shape it means (`k`), so the fix is to validate it
against that one `$defs` entry and report those messages instead. The
size assertions below are the point of the test, not decoration: a
message that degrades back to echoing passes every "is it accurate?"
check and silently costs the reader the page.
"""

from __future__ import annotations

import json

from oku import cli


def _sankey_with_the_wrong_key(n_nodes: int) -> dict:
    """A chart an author would plausibly write: correct data, one key
    named from the wrong vocabulary (`edges` is graph-speak, the schema
    says `links`)."""
    return {
        "k": "chart",
        "type": "sankey",
        "nodes": [{"id": f"n{i}", "label": f"Stage {i}"} for i in range(n_nodes)],
        "edges": [
            {"source": f"n{i}", "target": f"n{i + 1}", "value": 10 + i} for i in range(n_nodes - 1)
        ],
    }


def _page(block: dict) -> dict:
    return {
        "k": "page",
        "t": "Probe",
        "m": {"summary": "A probe page."},
        "b": ["## A section\n\nLead paragraph.\n", block],
    }


def _messages(block: dict) -> list[str]:
    from pathlib import Path

    return [msg for _p, msg in cli.validate_pages([(Path("p.json"), _page(block))])]


def test_the_message_names_the_missing_and_the_unexpected_key() -> None:
    msgs = _messages(_sankey_with_the_wrong_key(14))

    assert len(msgs) == 1, msgs
    assert "'links' is a required property" in msgs[0], msgs
    assert "'edges' was unexpected" in msgs[0], msgs


def test_the_message_does_not_grow_with_the_payload() -> None:
    """The defect this replaces scaled linearly with the data. A 4-node
    chart and a 60-node one are the same mistake and deserve the same
    sentence."""
    small = _messages(_sankey_with_the_wrong_key(4))[0]
    large = _messages(_sankey_with_the_wrong_key(60))[0]

    assert small == large, f"the message tracked the payload:\n{small}\n{large}"
    assert len(large) < 200, f"message is {len(large)} chars: {large}"


def test_the_payload_is_not_read_back_to_the_author() -> None:
    block = _sankey_with_the_wrong_key(14)
    msg = _messages(block)[0]

    # Any run of the author's own data appearing verbatim is the defect.
    assert "Stage 7" not in msg, msg
    assert json.dumps(block["nodes"][:2]) not in msg, msg


def test_an_unknown_kind_is_named_rather_than_echoed() -> None:
    msgs = _messages({"k": "bar-chart", "rows": [{"label": "a", "value": 1}]})

    assert len(msgs) == 1, msgs
    assert "'bar-chart' is not a known block kind" in msgs[0], msgs


def test_a_block_with_no_kind_says_so() -> None:
    msgs = _messages({"rows": [{"label": "a", "value": 1}]})

    assert len(msgs) == 1, msgs
    assert "no `k` field" in msgs[0], msgs


def test_a_specific_error_is_still_reported_verbatim() -> None:
    """The compaction only replaces the blanket `anyOf` rejection. An
    error that already names its own field must survive untouched."""
    msgs = _messages({"k": "chart", "type": "not-a-chart-type", "rows": []})

    assert len(msgs) == 1, msgs
    assert "not-a-chart-type" in msgs[0], msgs
