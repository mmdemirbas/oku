"""Tests for the `oku check` doctree linter.

Each test builds a small in-memory page-JSON fixture, feeds it through
check_pages(), and asserts on the resulting issue list. This isolates
the linter's behaviour from the rest of the build pipeline and from
the project's own docs/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oku import cli


# ---------- helpers ----------


def _issues_of(issues: list[dict], *, code: str | None = None, severity: str | None = None) -> list[dict]:
    """Filter issues by code and/or severity."""
    out = issues
    if code is not None:
        out = [i for i in out if i["code"] == code]
    if severity is not None:
        out = [i for i in out if i["severity"] == severity]
    return out


def _run(page_dict: dict, *, filename: str = "page.json", tmp_path: Path | None = None) -> list[dict]:
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
                "blocks": [{"kind": "chart", "type": "spirograph", "rows": []}],
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
        ("heatmap", "chart-heatmap-missing-cells"),
        ("sparkline", "chart-sparkline-missing-values"),
        ("waffle", "chart-waffle-missing-segments"),
        ("gauge", "chart-gauge-missing-fields"),
        ("radar", "chart-radar-missing-fields"),
        ("box-plot", "chart-boxplot-missing-boxes"),
        ("bullet", "chart-bullet-missing-tracks"),
        ("slope", "chart-slope-missing-items"),
        ("histogram", "chart-histogram-missing-bins"),
        ("calendar-heatmap", "chart-calendar-missing-date-values"),
        ("treemap", "chart-treemap-missing-tree"),
        ("ridgeline", "chart-ridgeline-missing-distributions"),
        ("funnel", "chart-funnel-missing-stages"),
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
                "blocks": [{"kind": "chart", "type": "gauge", "value": 62, "max": 100}],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-gauge-missing-fields")
    assert len(issues) == 0


def test_chart_histogram_with_bins_passes(tmp_path: Path) -> None:
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
                        "type": "histogram",
                        "bins": [{"lo": 0, "hi": 10, "count": 3}, {"lo": 10, "hi": 20, "count": 7}],
                    }
                ],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-histogram-missing-bins")
    assert len(issues) == 0


def test_chart_treemap_with_tree_passes(tmp_path: Path) -> None:
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
                        "type": "treemap",
                        "tree": [
                            {"label": "A", "value": 40},
                            {"label": "B", "value": 30},
                        ],
                    }
                ],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-treemap-missing-tree")
    assert len(issues) == 0


def test_chart_calendar_heatmap_with_date_values_passes(tmp_path: Path) -> None:
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
                        "type": "calendar-heatmap",
                        "year": 2026,
                        "date_values": {"2026-01-01": 4, "2026-06-15": 9},
                    }
                ],
            }
        ],
    }
    issues = _issues_of(_run(page, tmp_path=tmp_path), code="chart-calendar-missing-date-values")
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
    (fixture / "glossary" / "test.json").write_text(
        json.dumps(
            {
                "domain": "test",
                "version": 1,
                "entries": {"Iceberg": {"en": {"summary": "..."}}},
            }
        )
    )
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


def test_multi_word_markdown_refs_are_collected(tmp_path: Path) -> None:
    """Registry ids carry spaces ("Iceberg paper", "Time travel"). The
    reference scanner used to match `[\\w-]+` only, so a multi-word
    reference was never collected — an unresolved one passed check in
    silence, and that is most of the registry."""
    fixture = tmp_path / "kit_empty"
    (fixture / "glossary").mkdir(parents=True)
    (fixture / "extrefs").mkdir(parents=True)
    page = {
        "k": "page",
        "t": "T",
        "b": ["## S {#s}\n\nSee [the paper](#x/Iceberg paper) and [travel](#g/Time travel).\n"],
    }
    issues = cli.check_pages([(tmp_path / "page.json", page)], tmp_path, kit_dir=fixture)
    x = _issues_of(issues, code="unresolved-extref")
    assert len(x) == 1 and "Iceberg paper" in x[0]["where"], x
    g = _issues_of(issues, code="unresolved-glossary")
    assert len(g) == 1 and "Time travel" in g[0]["where"], g


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


def test_no_summary_skipped_for_materialised_pages(tmp_path: Path) -> None:
    """Materialised repo markdown (README & friends — no front-matter)
    can't carry meta.summary; the nudge applies to authored pages only."""
    materialised = {
        "k": "page",
        "t": "README",
        "m": {"_materialised_by": "oku-init"},
        "b": ["intro prose"],
    }
    authored = {"k": "page", "t": "T", "b": ["intro prose"]}
    issues = _run(materialised, tmp_path=tmp_path)
    assert _issues_of(issues, code="no-summary") == []
    issues = _run(authored, tmp_path=tmp_path)
    assert len(_issues_of(issues, code="no-summary")) == 1


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
    """The kit's own docs must pass `oku check --strict`.

    This is the canonical regression net for the oku skill's
    auto-verify step: the kit's own dogfooding must remain clean."""
    import importlib

    importlib.reload(cli)  # ensure fresh schema cache for the run
    pages = cli.find_json_pages(repo_root)
    assert pages, "Expected to find at least one page-JSON under repo_root"
    issues = cli.check_pages(pages, repo_root)
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    assert errors == [], f"Doctree has errors: {errors}"
    assert warnings == [], f"Doctree has warnings (run `oku check`): {warnings}"


# ---------- find_unparseable_json + cmd_check JSON-parse hard-fail ----------
#
# Regression net for an actual incident: design-review.json silently
# disappeared from the site nav for a session because a single missing
# comma made json.loads raise — find_json_pages caught it and dropped
# the page without surfacing the error. We now scan separately and
# fold parse failures into the issue stream as `json-parse-failed`
# errors. The tests below pin that behaviour.


def test_find_unparseable_json_returns_bad_file(tmp_path: Path) -> None:
    """A page-shaped .json with a syntax error must surface from
    find_unparseable_json so cmd_check can promote it to a hard error."""
    bad = tmp_path / "page-broken.json"
    # Missing comma between two object literals — same shape as the
    # incident that hid design-review.html.
    bad.write_text(
        '{"kind": "page", "title": "T", "blocks": [{"kind": "paragraph"} {"kind": "paragraph"}]}',
        encoding="utf-8",
    )
    out = cli.find_unparseable_json(tmp_path)
    paths = [str(p) for p, _ in out]
    assert str(bad) in paths
    # Error message should be specific, not generic.
    err_for_bad = next(err for p, err in out if p == bad)
    assert "line" in err_for_bad.lower()


def test_find_unparseable_json_skips_sidecars(tmp_path: Path) -> None:
    """kit.json / site-manifest.json / package.json / tsconfig.json
    are NOT page sources; the scanner must not surface parse errors
    in those well-known sidecars — find_json_pages already skips them,
    so they never reach the check pipeline. (User-authored pages
    fail loud; framework sidecars stay quiet.)"""
    (tmp_path / "kit.json").write_text("{ bad json", encoding="utf-8")
    (tmp_path / "package.json").write_text("{ bad", encoding="utf-8")
    (tmp_path / "real-page.json").write_text(
        '{"kind": "page", "title": "ok", "blocks": []}', encoding="utf-8"
    )
    out = cli.find_unparseable_json(tmp_path)
    assert out == [], f"Expected no findings for sidecars, got: {out}"


def test_find_unparseable_json_returns_empty_when_clean(tmp_path: Path) -> None:
    (tmp_path / "page.json").write_text('{"kind": "page", "title": "T", "blocks": []}', encoding="utf-8")
    assert cli.find_unparseable_json(tmp_path) == []


def test_cmd_check_promotes_parse_failure_to_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """cmd_check must surface json-parse-failed as an error so the
    user sees the file in the report instead of having it silently
    drop from the page list. Before the fix this test would run with
    one valid page, report '1 page(s) clean', and exit 0 — hiding the
    broken sibling."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "good.json").write_text('{"kind": "page", "title": "T", "blocks": []}', encoding="utf-8")
    (tmp_path / "design-review.json").write_text(
        '{"kind": "page", "title": "T", "blocks": [] "extra": "bad"}',
        encoding="utf-8",
    )

    class _Args:
        json = False
        strict = False
        verbose = False
        errors_only = False

    rc = cli.cmd_check(_Args())
    out = capsys.readouterr().out
    assert rc == 1, "cmd_check must exit non-zero when a page-shaped JSON fails to parse"
    assert "design-review.json" in out
    assert "json-parse-failed" in out


# ---------- find_kit_json placement priority ----------
#
# kit.json belongs next to the docs root per the schema description.
# A prior fix accidentally moved it to the project root; that worked
# for `oku build` but broke `oku serve` against the source tree
# because chrome.js resolves kit.json from /docs/ (the parent of
# _oku/). find_kit_json probes docs/ first, falls back to root, so
# both authoring locations work and both serve paths succeed.


def test_find_kit_json_prefers_docs_subdir(tmp_path: Path) -> None:
    """When kit.json sits at docs/kit.json AND root/kit.json, the
    docs/ copy wins. This is the canonical home per the schema."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "docs-copy"}', encoding="utf-8")
    (tmp_path / "kit.json").write_text('{"name": "root-copy"}', encoding="utf-8")
    p = cli.find_kit_json(tmp_path)
    assert p is not None
    assert p == docs / "kit.json"
    # And the contents reflect the docs/ copy, not the root one.
    import json as _json

    assert _json.loads(p.read_text(encoding="utf-8"))["name"] == "docs-copy"


def test_find_kit_json_falls_back_to_root(tmp_path: Path) -> None:
    """When only root/kit.json exists (legacy authoring location,
    or a project where root IS the docs root), the helper returns
    that path."""
    (tmp_path / "kit.json").write_text('{"name": "root-only"}', encoding="utf-8")
    p = cli.find_kit_json(tmp_path)
    assert p == tmp_path / "kit.json"


def test_find_kit_json_returns_none_when_absent(tmp_path: Path) -> None:
    assert cli.find_kit_json(tmp_path) is None


def test_shadowed_source_flagged(tmp_path: Path, repo_root: Path) -> None:
    """A real .json page sitting next to a .md source must be flagged —
    it silently wins discovery and the rendered page stops following
    the source (the stale-global-init incident class)."""
    import subprocess
    import sys

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("---\ntitle: P\n---\n\nbody\n", encoding="utf-8")
    (docs / "page.json").write_text(
        '{"k":"page","t":"P","m":{"summary":"s"},"b":["## S {#s}\\n\\nstale shadow"]}',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(repo_root / "bin" / "oku"), "check", "--json"],
        cwd=docs,
        capture_output=True,
        text=True,
    )
    assert '"shadowed-source"' in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 1, "shadowed-source must be an error"


# ---------- reference forms (footnotes, reference links) ----------


def test_undefined_footnote_and_link_reference_are_flagged(tmp_path: Path) -> None:
    """Both forms resolve page-wide at render time; an undefined one is
    invisible in the output (it renders as its own source text), so the
    linter is where the author has to hear about it."""
    page = {
        "k": "page",
        "t": "T",
        "b": [
            "## S {#s}\n\nA note[^ok] and a bad one[^missing].\n\n"
            "A [good][site] and a [bad][nope] link.\n\n"
            "[^ok]: defined\n[site]: https://example.com\n"
        ],
    }
    issues = cli.check_pages([(tmp_path / "page.json", page)], tmp_path)
    fn = _issues_of(issues, code="undefined-footnote")
    ln = _issues_of(issues, code="undefined-link-reference")
    assert len(fn) == 1 and "missing" in fn[0]["message"], fn
    assert len(ln) == 1 and "nope" in ln[0]["message"], ln
