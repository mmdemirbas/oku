"""`oku spec` prints a payload the author can paste, for every shape.

The file it prints from is hand-maintainable, which is exactly why it
needs a gate in both directions:

- a chart type added to the schema enum with no example is a name
  `oku spec` cannot answer, and the author falls back to reading the
  schema — the cost this command exists to remove;
- an example that stops validating is worse than no example, because it
  is pasted before it is checked.

So every entry is put through the same two gates a real page passes:
the schema, and the structural chart-shape checks. An example that
would fail `oku check` fails here first.
"""

from __future__ import annotations

import json

import pytest

from oku import cli


EXAMPLES = cli._load_examples()
SCHEMA = cli._load_schema()
CHART_TYPES = sorted(SCHEMA["$defs"]["chart"]["properties"]["type"]["enum"])
BLOCK_KINDS = sorted(
    k for k in SCHEMA["$defs"] if k not in ("block", "meta", "tableCell", "tableHeader", "tableRow")
)


def test_the_examples_file_ships_with_the_kit() -> None:
    """`kit/schema` is force-included wholesale, so a file added there
    reaches the wheel. If that ever changes, this is the first failure."""
    assert (cli.KIT_DIR / "schema" / "examples.json").exists()
    assert EXAMPLES.get("blocks") and EXAMPLES.get("charts")


# ---------- coverage, both directions ----------


@pytest.mark.parametrize("ctype", CHART_TYPES)
def test_every_chart_type_in_the_schema_has_an_example(ctype: str) -> None:
    assert ctype in EXAMPLES["charts"], (
        f"chart type {ctype!r} is in the schema enum with no `oku spec` entry — "
        "an author asking for it gets sent to the schema instead"
    )


@pytest.mark.parametrize("kind", BLOCK_KINDS)
def test_every_block_kind_in_the_schema_has_an_example(kind: str) -> None:
    assert kind in EXAMPLES["blocks"], f"block kind {kind!r} has no `oku spec` entry"


def test_no_example_names_a_shape_the_schema_does_not_have() -> None:
    """The other direction: an entry left behind after a type was renamed
    prints a payload nothing will accept."""
    assert set(EXAMPLES["charts"]) - set(CHART_TYPES) == set()
    assert set(EXAMPLES["blocks"]) - set(BLOCK_KINDS) == set()


def test_a_name_resolves_to_exactly_one_shape() -> None:
    """`_spec_entry` prefers a block kind on a collision. Nothing should
    ever depend on that preference."""
    assert set(EXAMPLES["blocks"]) & set(EXAMPLES["charts"]) == set()


# ---------- validity, through the gates a real page passes ----------


def _page_with(block: dict) -> dict:
    return {
        "k": "page",
        "t": "Spec probe",
        "m": {"summary": "One shipped example."},
        "b": ["## A section\n\nLead paragraph.\n", block],
    }


@pytest.mark.parametrize("kind", BLOCK_KINDS)
def test_every_block_example_validates(kind: str, tmp_path) -> None:
    block = {**EXAMPLES["blocks"][kind], "k": kind}
    errors = cli.validate_pages([(tmp_path / "p.json", _page_with(block))])
    assert errors == [], f"the shipped {kind} example does not validate: {errors}"


@pytest.mark.parametrize("kind", BLOCK_KINDS)
def test_every_block_example_passes_the_structural_checks(kind: str, tmp_path) -> None:
    """The schema and the structural checks disagree more often than they
    look like they would — `chart-grid` validated against `$defs` while
    `oku check` called it an unknown kind. Validating against one gate
    only is how that survived.
    """
    block = {**EXAMPLES["blocks"][kind], "k": kind}
    issues = cli.check_pages([(tmp_path / "p.json", _page_with(block))], tmp_path)
    hard = [i for i in issues if i["severity"] == "error"]
    assert hard == [], f"the shipped {kind} example fails `oku check`: {hard}"


# ---------- the authoring form is the one that works ----------


@pytest.mark.parametrize("kind", BLOCK_KINDS)
def test_a_kind_prints_a_form_that_exists(kind: str) -> None:
    """Three block kinds are real `$defs` entries that no `oku-` fence
    lifts: `code`, `image` and `svg`. A page written with ```oku-code
    keeps it as literal text — so those kinds must print their markdown
    form, and every other kind must have a fence."""
    entry = cli._spec_entry(kind)
    assert entry is not None
    if kind in cli._FENCE_KINDS:
        assert entry["fence"] == f"oku-{kind}", entry
    else:
        assert entry["fence"] is None, entry
        assert entry["markdown"], f"{kind} has no fence and no markdown form"


_MARKDOWN_MARKER = {
    "code": "```python",
    "image": "![What the pipeline does](diagram.png)",
    "svg": "<svg",
}


@pytest.mark.parametrize("kind", sorted(set(BLOCK_KINDS) - set(cli._FENCE_KINDS)))
def test_the_markdown_form_survives_into_the_page(kind: str, tmp_path) -> None:
    """Round-trip: paste what `oku spec` prints into a page, and the
    converter must carry it through without complaint.

    These three stay inside the `b[]` markdown string rather than
    becoming typed blocks — only a typed fence lifts, and renderer.js
    parses the rest at load time. So the invariant here is that the text
    survives and the linter accepts it. An `oku-code` fence would fail
    both halves: it would not lift, and `fence-not-lifted` would fire.
    """
    body = EXAMPLES["markdown"][kind]
    src = f"---\ntitle: Probe\nsummary: A probe.\n---\n\n## S {{#s}}\n\nLead.\n\n{body}\n"
    page = cli.md_to_v2_page(src, "p")
    text = "".join(b for b in page["b"] if isinstance(b, str))

    assert _MARKDOWN_MARKER[kind] in text, f"{kind} did not survive: {page['b']}"
    issues = cli.check_pages([(tmp_path / "p.json", page)], tmp_path)
    hard = [i for i in issues if i["severity"] == "error"]
    assert hard == [], f"what `oku spec {kind}` prints does not pass `oku check`: {hard}"


@pytest.mark.parametrize("ctype", CHART_TYPES)
def test_every_chart_example_validates(ctype: str, tmp_path) -> None:
    block = {**EXAMPLES["charts"][ctype], "k": "chart"}
    errors = cli.validate_pages([(tmp_path / "p.json", _page_with(block))])
    assert errors == [], f"the shipped {ctype} example does not validate: {errors}"


@pytest.mark.parametrize("ctype", CHART_TYPES)
def test_every_chart_example_passes_the_structural_checks(ctype: str, tmp_path) -> None:
    """The schema and the chart-shape checks catch different things — a
    payload can satisfy one and fail the other, which is the wrong-but-valid
    case `oku spec` exists to prevent."""
    block = {**EXAMPLES["charts"][ctype], "k": "chart"}
    issues = cli.check_pages([(tmp_path / "p.json", _page_with(block))], tmp_path)
    hard = [i for i in issues if i["severity"] == "error"]
    assert hard == [], f"the shipped {ctype} example fails `oku check`: {hard}"


@pytest.mark.parametrize("ctype", CHART_TYPES)
def test_a_chart_example_declares_its_own_type(ctype: str) -> None:
    """The payload is pasted into a bare ```oku-chart fence, which carries
    no type of its own."""
    assert EXAMPLES["charts"][ctype].get("type") == ctype


# ---------- what the command prints ----------


def test_the_printed_fence_round_trips_into_a_page(tmp_path, capsys) -> None:
    """The end-to-end claim: what `oku spec` prints is what an author
    pastes, and a page holding it passes `oku check`."""
    import argparse

    cli.cmd_spec(argparse.Namespace(name="sankey", json=False))
    out = capsys.readouterr().out

    assert out.startswith("```oku-chart\n") and out.rstrip().endswith("```")
    body = out.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    payload = json.loads(body)

    page = tmp_path / "docs"
    page.mkdir()
    (page / "kit.json").write_text('{"title":"probe"}')
    (page / "p.md").write_text(
        "---\ntitle: Probe\nsummary: A probe.\n---\n\n## Flows {#flows}\n\nLead.\n\n"
        f"```oku-chart\n{json.dumps(payload, separators=(',', ':'))}\n```\n"
    )
    converted = cli.md_to_v2_page((page / "p.md").read_text(), "p")
    issues = cli.check_pages([(page / "p.json", converted)], page)
    assert [i for i in issues if i["severity"] == "error"] == [], issues


def test_an_unknown_name_suggests_a_real_one(capsys) -> None:
    """A typo costs one line, not a schema read."""
    import argparse

    rc = cli.cmd_spec(argparse.Namespace(name="sankee", json=False))
    err = capsys.readouterr().err

    assert rc == 1
    assert "sankey" in err


def test_the_listing_never_breaks_a_name_across_lines(capsys) -> None:
    """Every name is hyphenated and meant to be copied; a wrapped
    `calendar-heatmap` is not a name."""
    import argparse

    cli.cmd_spec(argparse.Namespace(name=None, json=False))
    out = capsys.readouterr().out

    for line in out.splitlines():
        assert not line.rstrip().endswith("-"), f"a name was split: {line!r}"
    for name in list(EXAMPLES["charts"]) + list(EXAMPLES["blocks"]):
        assert name in out, f"{name} is missing from the listing"


# ---------- the kinds written as a link, not as a fence ----------


@pytest.mark.parametrize("name", sorted(cli._INLINE_KINDS))
def test_an_inline_kind_prints_its_syntax_and_when_to_use_it(name: str, capsys) -> None:
    """`oku spec` is the one surface that ships in the wheel, so it is
    where an author working from another project finds out what they
    can write. It listed 14 block kinds and 53 chart types and did not
    know the inline kinds existed — filepath was reachable from the
    skill briefing and from docs/reference.md, neither of which travels
    with the tool.

    The note is half the entry. Syntax answers "how"; an author
    choosing between a code span and a chip is asking "when"."""
    import argparse

    rc = cli.cmd_spec(argparse.Namespace(name=name, json=False))
    out = capsys.readouterr().out
    assert rc == 0
    assert cli._INLINE_KINDS[name] in out, out
    # Syntax line, blank line, note.
    assert len(out.strip().splitlines()) >= 3, out


def test_the_listing_names_every_inline_kind_with_its_prefix(capsys) -> None:
    """A name alone would send the reader back to the reference page to
    learn it is a link and not a fence."""
    import argparse

    cli.cmd_spec(argparse.Namespace(name=None, json=False))
    out = capsys.readouterr().out
    assert "inline (3)" in out, out
    for name, prefix in cli._INLINE_KINDS.items():
        assert f"{name} {prefix}" in out, (name, out)


def test_an_inline_kind_prints_json_that_parses(capsys) -> None:
    """--json exists for callers that compose rather than paste."""
    import argparse

    cli.cmd_spec(argparse.Namespace(name="filepath", json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["markdown"].startswith("The resolver lives in")
    assert payload["note"]
