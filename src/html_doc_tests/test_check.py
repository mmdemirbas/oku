"""Tests for the `html-doc check` doctree linter.

Each test builds a small in-memory page-JSON fixture, feeds it through
check_pages(), and asserts on the resulting issue list. This isolates
the linter's behaviour from the rest of the build pipeline and from
the project's own docs/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from html_doc import cli


# ---------- helpers ----------

def _issues_of(issues: list[dict], *, code: str | None = None,
               severity: str | None = None) -> list[dict]:
    """Filter issues by code and/or severity."""
    out = issues
    if code is not None:
        out = [i for i in out if i["code"] == code]
    if severity is not None:
        out = [i for i in out if i["severity"] == severity]
    return out


def _run(page_dict: dict, *, filename: str = "page.json",
         tmp_path: Path | None = None) -> list[dict]:
    """Run check_pages against a single in-memory page dict and return
    the issue list."""
    p = (tmp_path or Path("/tmp")) / filename
    return cli.check_pages([(p, page_dict)], tmp_path or Path("/tmp"))


# ---------- clean baseline ----------

def test_clean_minimal_page(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "Minimal page",
        "meta": {"summary": "A trivial page."},
        "blocks": [
            {
                "kind": "section",
                "id": "intro",
                "title": "Intro",
                "blocks": [
                    {"kind": "paragraph", "content": "Hello world."},
                ],
            },
        ],
    }
    issues = _run(page, tmp_path=tmp_path)
    errors = _issues_of(issues, severity="error")
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------- deprecated kinds ----------

def test_flags_deprecated_bar_chart(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {"kind": "bar-chart", "rows": [{"label": "x", "value": 1}]},
                ],
            },
        ],
    }
    issues = _run(page, tmp_path=tmp_path)
    deprecated = _issues_of(issues, code="deprecated-kind")
    assert len(deprecated) == 1
    assert "type:bar" in deprecated[0]["message"]
    assert deprecated[0]["severity"] == "error"


def test_flags_deprecated_scope_grid(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "scope-grid",
                        "columns": [
                            {"status": "in", "title": "A", "items": ["x"]},
                            {"status": "out", "title": "B", "items": ["y"]},
                        ],
                    },
                ],
            },
        ],
    }
    deprecated = _issues_of(_run(page, tmp_path=tmp_path), code="deprecated-kind")
    assert len(deprecated) == 1
    assert "compare-grid" in deprecated[0]["message"]


# ---------- chart shape ----------

def test_chart_bar_without_rows_errors(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [{"kind": "chart", "type": "bar"}],
            },
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-bar-missing-rows")
    assert len(issues) == 1


def test_chart_scatter_without_series_errors(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [{"kind": "chart", "type": "scatter"}],
            },
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-cartesian-missing-series")
    assert len(issues) == 1


def test_chart_unknown_type_errors(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [{"kind": "chart", "type": "pie", "rows": []}],
            },
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-unknown-type")
    assert len(issues) == 1
    assert "scatter, line, area, bubble, quadrant" in issues[0]["message"]


# ---------- Tier-1 / Tier-3 chart shape sanity ----------

@pytest.mark.parametrize(
    "ctype, code",
    [
        ("heatmap",  "chart-heatmap-missing-cells"),
        ("sparkline", "chart-sparkline-missing-values"),
        ("waffle",   "chart-waffle-missing-segments"),
        ("gauge",    "chart-gauge-missing-fields"),
        ("radar",    "chart-radar-missing-fields"),
        ("box-plot", "chart-boxplot-missing-boxes"),
        ("bullet",   "chart-bullet-missing-tracks"),
        ("slope",    "chart-slope-missing-items"),
    ],
)
def test_chart_extension_missing_payload_flagged(tmp_path: Path, ctype: str, code: str) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [{"kind": "chart", "type": ctype}],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code=code)
    assert len(issues) == 1


def test_chart_heatmap_with_cells_passes(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "chart",
                        "type": "heatmap",
                        "cells": [[1, 2], [3, 4]],
                    }
                ],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-heatmap-missing-cells")
    assert len(issues) == 0


def test_chart_gauge_with_value_and_max_passes(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {"kind": "chart", "type": "gauge", "value": 62, "max": 100}
                ],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-gauge-missing-fields")
    assert len(issues) == 0


# ---------- duplicate anchors ----------

def test_duplicate_section_ids_flagged(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {"kind": "section", "id": "dup", "title": "A", "blocks": []},
            {"kind": "section", "id": "dup", "title": "B", "blocks": []},
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="duplicate-anchor")
    assert len(issues) == 1


# ---------- forbidden prose ----------

def test_round_breadcrumb_in_lead_flagged(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "lead": "Fixed in round 3 — see prior notes.",
                "blocks": [],
            },
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="process-breadcrumb")
    assert len(issues) == 1
    assert issues[0]["severity"] == "warning"


def test_round_breadcrumb_in_inline_text_flagged(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "content": [
                            "See ",
                            {"kind": "code", "text": "round-5"},
                            " for context.",
                        ],
                    },
                ],
            },
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="process-breadcrumb")
    assert len(issues) == 1


# ---------- glossary / extref resolution ----------

def test_unresolved_glossary_term_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point KIT_DIR to an empty fixture dir so no term resolves.
    fixture = tmp_path / "kit_empty"
    (fixture / "glossary").mkdir(parents=True)
    (fixture / "extrefs").mkdir(parents=True)
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "content": [{"kind": "glossary-term", "term": "Nonexistent"}],
                    },
                ],
            },
        ],
    }
    issues = cli.check_pages([(tmp_path / "page.json", page)], tmp_path, kit_dir=fixture)
    unresolved = _issues_of(issues, code="unresolved-glossary")
    assert len(unresolved) == 1


def test_known_glossary_term_passes(tmp_path: Path) -> None:
    fixture = tmp_path / "kit"
    (fixture / "glossary").mkdir(parents=True)
    (fixture / "extrefs").mkdir(parents=True)
    (fixture / "glossary" / "test.json").write_text(json.dumps({
        "domain": "test",
        "version": 1,
        "entries": {"Iceberg": {"en": {"summary": "..."}}},
    }))
    page = {
        "kind": "page",
        "title": "T",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "content": [{"kind": "glossary-term", "term": "iceberg"}],
                    },
                ],
            },
        ],
    }
    issues = cli.check_pages([(tmp_path / "page.json", page)], tmp_path, kit_dir=fixture)
    assert _issues_of(issues, code="unresolved-glossary") == []


# ---------- stray demo pages ----------

def test_stray_demo_filename_flagged(tmp_path: Path) -> None:
    page = {"kind": "page", "title": "T", "blocks": []}
    issues = cli.check_pages([(tmp_path / "table-demo.json", page)], tmp_path)
    stray = _issues_of(issues, code="stray-demo")
    assert len(stray) == 1
    assert stray[0]["severity"] == "error"


def test_markdown_demo_filename_is_allowed(tmp_path: Path) -> None:
    page = {"kind": "page", "title": "T", "blocks": []}
    issues = cli.check_pages([(tmp_path / "markdown-demo.json", page)], tmp_path)
    assert _issues_of(issues, code="stray-demo") == []


# ---------- metadata nudges ----------

def test_missing_summary_is_info(tmp_path: Path) -> None:
    page = {"kind": "page", "title": "T", "blocks": []}
    issues = cli.check_pages([(tmp_path / "p.json", page)], tmp_path)
    summary = _issues_of(issues, code="no-summary")
    assert len(summary) == 1
    assert summary[0]["severity"] == "info"


def test_code_block_without_language_is_info(tmp_path: Path) -> None:
    page = {
        "kind": "page",
        "title": "T",
        "meta": {"summary": "..."},
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [{"kind": "code", "source": "foo"}],
            },
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="code-no-language")
    assert len(issues) == 1


# ---------- end-to-end against the live repo ----------

def test_project_docs_pass_check_strict(repo_root: Path) -> None:
    """The kit's own docs must pass `html-doc check --strict`.

    This is the canonical regression net for the html-doc skill's
    auto-verify step: the kit's own dogfooding must remain clean."""
    import importlib
    importlib.reload(cli)  # ensure fresh schema cache for the run
    pages = cli.find_json_pages(repo_root)
    assert pages, "Expected to find at least one page-JSON under repo_root"
    issues = cli.check_pages(pages, repo_root)
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    assert errors == [], f"Doctree has errors: {errors}"
    assert warnings == [], f"Doctree has warnings (run `html-doc check`): {warnings}"
