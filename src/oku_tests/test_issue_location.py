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
