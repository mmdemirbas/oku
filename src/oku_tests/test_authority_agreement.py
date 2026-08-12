"""The sources that decide what a block kind IS must agree.

Six places encode that answer, and none of them can see the others:

| source | answers |
|---|---|
| `_FENCE_KINDS` (cli) | which ```oku-… fences the converter lifts |
| `FENCE_KINDS` (renderer.js) | the same question, in the browser |
| `$defs` (page.schema.json) | which typed blocks validate |
| the `case` dispatch (renderer.js) | which typed blocks draw |
| `_KNOWN_BLOCK_KINDS` (cli) | which the structural lint accepts |
| `examples.json` | which `oku spec` can answer for |
| the `required` map (renderer.js) | which fields each must carry |

The last one has its own guard in `test_block_contract.py` — it caught
this file's author adding `info-tip` to the schema and not to it.

A kind present in some and absent from others is not a crash. It is a
fence that lifts into a block nothing validates, or a kind the linter
rejects that the renderer draws — and both have shipped here:

- `oku-chart-grid` was a documented fence, drawn by the renderer and
  blessed by the schema, that `oku check` rejected as an unknown kind.
- `oku-tldr` was a documented fence that lifted into a block with no
  `$defs` entry and no renderer case, so it failed validation and could
  never have drawn. Nothing in this repo used it, so nothing failed.

Both were found by hand. This is the check that finds the next one.

The rule enforced: **anything an author can write must validate, draw,
and be printable by `oku spec`.** Kinds reachable only from a v1/JSON
page are held to less — they are legacy, and the shim converts most of
them to markdown before the schema ever sees them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from oku import cli


KIT = Path(__file__).resolve().parents[2] / "kit"
RENDERER = (KIT / "renderer.js").read_text(encoding="utf-8")
SCHEMA = json.loads((KIT / "schema" / "page.schema.json").read_text(encoding="utf-8"))

SCHEMA_KINDS = {
    ref.split("/")[-1] for ref in (x.get("$ref", "") for x in SCHEMA["$defs"]["block"]["oneOf"]) if ref
}
DISPATCH_KINDS = set(re.findall(r"case '([a-z-]+)':\s*el = this\._render", RENDERER))
EXAMPLE_KINDS = set(cli._load_examples()["blocks"])


def _renderer_fence_kinds() -> set[str]:
    m = re.search(r"const FENCE_KINDS = \[(.*?)\];", RENDERER, re.S)
    assert m, "FENCE_KINDS moved in renderer.js — this test cannot see it any more"
    return set(re.findall(r"'([a-z-]+)'", m.group(1)))


def test_both_lifters_agree_on_what_a_fence_is() -> None:
    """The CLI lifts fences at build time and renderer.js lifts them in
    the browser. A kind in one and not the other renders differently
    depending on how the page was opened."""
    assert cli._FENCE_KINDS == _renderer_fence_kinds()


@pytest.mark.parametrize("kind", sorted(cli._FENCE_KINDS))
def test_every_fence_kind_validates(kind: str) -> None:
    """`oku-tldr` lifted into a block the schema had no entry for, so a
    page using the documented fence failed `oku check`."""
    assert kind in SCHEMA_KINDS, (
        f"```oku-{kind} lifts to a typed block with no $defs entry — authoring it produces a schema error"
    )


@pytest.mark.parametrize("kind", sorted(cli._FENCE_KINDS))
def test_every_fence_kind_draws(kind: str) -> None:
    """The other half of the same bug: a block that validates and then
    reaches a renderer with no case for it."""
    assert kind in DISPATCH_KINDS, f"```oku-{kind} lifts to a typed block renderer.js does not draw"


@pytest.mark.parametrize("kind", sorted(cli._FENCE_KINDS))
def test_every_fence_kind_is_accepted_by_the_lint(kind: str) -> None:
    """`oku-chart-grid` was rejected as `unknown-kind` while the renderer
    drew it — the linter refusing a page the kit renders."""
    assert kind in cli._KNOWN_BLOCK_KINDS


@pytest.mark.parametrize("kind", sorted(cli._FENCE_KINDS))
def test_every_fence_kind_is_printable(kind: str) -> None:
    """An author who cannot get the payload from `oku spec` reads the
    schema instead, which is the cost the command exists to remove."""
    assert kind in EXAMPLE_KINDS
    entry = cli._spec_entry(kind)
    assert entry and entry["fence"] == f"oku-{kind}", entry


def test_a_kind_the_schema_validates_can_also_be_drawn() -> None:
    """Direction reversed: a `$defs` entry nothing renders is a payload
    the linter blesses and the reader never sees."""
    undrawn = sorted(SCHEMA_KINDS - DISPATCH_KINDS)
    assert undrawn == [], f"schema validates {undrawn}, renderer draws none of them"


def test_a_kind_with_no_fence_says_how_to_write_it() -> None:
    """The kinds that exist but are not fences are the ones an author
    guesses at. Each must have a stated markdown form, or the guess has
    no answer — `code`, `image` and `svg` are all real `$defs` entries
    with no fence, and `oku spec` printed an ```oku-code fence for one
    of them before this was noticed."""
    fenceless = (SCHEMA_KINDS | DISPATCH_KINDS) - cli._FENCE_KINDS
    missing = sorted(k for k in fenceless if k not in cli._MARKDOWN_FORM_OF)
    assert missing == [], f"no stated markdown form for {missing}"
