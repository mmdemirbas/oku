"""A failure names the file that exists, and the line inside it.

Two things were wrong with where `oku check` pointed, and both cost a
round trip before any fixing could start.

**The path did not exist.** A markdown page is carried through the
pipeline under a `.json` path that `_synth_json_path` invents so
downstream `with_suffix(".html")` keeps working. That is an internal
detail, and it was being printed: an author told `notes/plan.json` has an
error opens it and finds no such file. The page they wrote is
`notes/plan.md`.

**The locator was an index.** `b[5]` is a position in the converted
block list, not in the source. Finding it means counting typed fences
through the page — and the count is not even the same, because prose
between fences occupies indices too.

So the report now leads with `file:line`, the shape every editor already
knows how to jump to.
"""

from __future__ import annotations

from pathlib import Path

from oku import cli


SOURCE = """---
title: Deep probe
summary: Errors at known source lines.
---

## One {#one}

Lead paragraph.

```oku-chart
{"type":"sankey","nodes":[{"id":"a","label":"A"}],"edges":[]}
```

## Two {#two}

Lead paragraph.

```oku-kpi-grid
{"tiles":[]}
```
"""

# Counted from the source above, 1-based, as an editor shows them.
CHART_FENCE_LINE = 10
KPI_FENCE_LINE = 18


def _check(tmp_path: Path, text: str = SOURCE) -> list[dict]:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "p.md").write_text(text, encoding="utf-8")
    return cli.check_pages(cli.find_json_pages(docs), docs)


def test_the_reported_path_is_a_file_that_exists(tmp_path: Path) -> None:
    issues = [i for i in _check(tmp_path) if i["severity"] == "error"]

    assert issues, "the fixture is meant to produce errors"
    for issue in issues:
        assert issue["path"].suffix == ".md", f"reported a synthesized path: {issue['path']}"
        assert issue["path"].exists(), f"reported a path that does not exist: {issue['path']}"


def test_a_typed_block_failure_carries_its_source_line(tmp_path: Path) -> None:
    issues = _check(tmp_path)

    chart = [i for i in issues if i["code"] == "chart-graph-missing-payload"]
    kpi = [i for i in issues if i["code"] == "empty-kpi-grid"]
    assert chart and kpi, [i["code"] for i in issues]

    assert chart[0]["line"] == CHART_FENCE_LINE, chart[0]
    assert kpi[0]["line"] == KPI_FENCE_LINE, kpi[0]


def test_a_schema_failure_carries_it_too(tmp_path: Path) -> None:
    """Schema errors locate a block as `b.1` rather than `b[1]`, and are
    reported with a `(root)` locator, so they need the index pulled out
    of the message rather than the locator."""
    schema = [i for i in _check(tmp_path) if i["code"] == "schema"]

    assert schema, "the fixture is meant to fail the schema"
    assert schema[0]["line"] == CHART_FENCE_LINE, schema[0]


def test_the_line_is_the_line_in_the_file_not_in_the_body(tmp_path: Path) -> None:
    """Front-matter is stripped before the walk, so a line index into the
    remaining text is short by its length. Growing the front-matter must
    move every reported line by the same amount."""
    padded = SOURCE.replace(
        "summary: Errors at known source lines.",
        "summary: Errors at known source lines.\nauthors: [a]\ndate: 2026-08-11",
    )
    issues = _check(tmp_path, padded)

    kpi = [i for i in issues if i["code"] == "empty-kpi-grid"]
    assert kpi and kpi[0]["line"] == KPI_FENCE_LINE + 2, kpi[0]


def test_the_human_line_reads_as_file_colon_line(tmp_path: Path) -> None:
    issues = [i for i in _check(tmp_path) if i["code"] == "empty-kpi-grid"]
    rendered = cli._format_issue(issues[0], tmp_path / "docs")

    assert rendered.lstrip().startswith(f"✗ p.md:{KPI_FENCE_LINE}:"), rendered


FAR = (
    "---\ntitle: Line probe\nsummary: References far from the block start.\n---\n\n"
    "## Overview {#overview}\n\nLead paragraph.\n\n"
    + "\n".join(f"Filler paragraph {i}." for i in range(1, 40))
    + "\n\nA [bad anchor](#overvieww) here.\n\n```oku-nope\n{}\n```\n"
)
FAR_LINK_LINE = 50
FAR_FENCE_LINE = 52


def test_a_string_pass_reports_the_file_line_not_the_block_line(tmp_path: Path) -> None:
    """`_lint_md_string` counts from the start of its own string, and a
    block boundary is invisible in the source — the author sees one file.
    Printed raw, that number looks precise and points elsewhere: the
    probe that found this had a fence on file line 10 reported as line 5.
    """
    issues = [i for i in _check(tmp_path, FAR) if i["code"] == "fence-not-lifted"]

    assert issues, "the fixture is meant to have an unlifted fence"
    assert issues[0]["line"] == FAR_FENCE_LINE, issues[0]
    assert f"line {FAR_FENCE_LINE}" in issues[0]["where"], issues[0]["where"]


def test_a_reference_deep_in_a_prose_block_points_at_itself(tmp_path: Path) -> None:
    """A prose block runs from one typed fence to the next, so on a page
    with few fences it is most of the document. The block's own line
    would be 40+ lines from the link that is actually wrong."""
    issues = [i for i in _check(tmp_path, FAR) if i["code"] == "unresolved-anchor"]

    assert issues, "the fixture is meant to have a broken anchor"
    assert issues[0]["line"] == FAR_LINK_LINE, issues[0]


def test_a_near_miss_reference_is_offered_the_real_one(tmp_path: Path) -> None:
    """The checker holds the valid set at the point it rejects a value.
    Printing the rejection without it leaves the author to recover the
    string by opening the page."""
    issues = [i for i in _check(tmp_path, FAR) if i["code"] == "unresolved-anchor"]

    assert "Did you mean: overview?" in issues[0]["message"], issues[0]["message"]


def test_nothing_is_suggested_when_nothing_is_close(tmp_path: Path) -> None:
    """A wrong suggestion is worse than none, because it gets applied."""
    text = FAR.replace("#overvieww", "#zzzzzzzzzzzz")
    issues = [i for i in _check(tmp_path, text) if i["code"] == "unresolved-anchor"]

    assert issues, "the fixture is meant to have a broken anchor"
    assert "Did you mean" not in issues[0]["message"], issues[0]["message"]


def test_a_real_json_page_is_left_alone(tmp_path: Path) -> None:
    """The mapping is for synthesized paths. A page genuinely authored as
    JSON must still be reported under its own name, with no line."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "q.json").write_text(
        '{"k":"page","t":"Q","m":{"summary":"s"},'
        '"b":["## S {#s}\\n\\nLead.\\n",{"k":"kpi-grid","tiles":[]}]}',
        encoding="utf-8",
    )
    issues = [i for i in cli.check_pages(cli.find_json_pages(docs), docs) if i["code"] == "empty-kpi-grid"]

    assert issues, "the fixture is meant to produce an error"
    assert issues[0]["path"].name == "q.json"
    assert "line" not in issues[0], issues[0]
