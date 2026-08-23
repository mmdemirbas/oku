"""Presentation rules in `oku check`.

Style advice written as prose in a briefing decays, because nothing
fails when it is ignored. The half of it a tool can decide without
judgement lives in the linter instead, so the briefing can be about
content.

Each rule here is decidable. Anything that needs a reader — whether the
diagram carries the point, whether the prose is any good — stays out on
purpose: a check that guesses trains authors to ignore checks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oku import cli


@pytest.fixture(autouse=True)
def _clear_caches():
    cli._tree_defaults_cache.clear()
    cli._git_date_cache.clear()
    cli._kit_token_cache.clear()
    yield
    cli._tree_defaults_cache.clear()
    cli._git_date_cache.clear()
    cli._kit_token_cache.clear()


def _issues(tmp_path: Path, md: str, *, kit: dict | None = None, name: str = "page.md") -> list[dict]:
    if kit is not None:
        (tmp_path / "kit.json").write_text(json.dumps(kit), encoding="utf-8")
    src = tmp_path / name
    src.write_text(md, encoding="utf-8")
    page = cli._page_from_source_file(src)
    assert page is not None
    return cli.check_pages([(src, page)], tmp_path)


def _codes(issues: list[dict]) -> set[str]:
    return {i["code"] for i in issues}


PARA = "A sentence that carries a little weight and then stops there.\n"


# ---------- duplicated metadata ----------


class TestRedundantMeta:
    def test_subtitle_repeating_summary_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\nsummary: One line.\nsubtitle: One line.\n---\n\n## S {#s}\n\nText.\n",
        )
        hit = [i for i in issues if i["code"] == "redundant-meta"]
        assert hit and hit[0]["where"] == "meta.subtitle", issues
        assert hit[0]["severity"] == "warning"

    def test_a_different_subtitle_is_not_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\nsummary: One line.\nsubtitle: Another line entirely.\n---\n\n## S {#s}\n\nText.\n",
        )
        assert "redundant-meta" not in _codes(issues), issues

    def test_updated_repeating_date_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\ndate: 2026-05-18\nupdated: 2026-05-18\n---\n\n## S {#s}\n\nText.\n",
        )
        hit = [i for i in issues if i["where"] == "meta.updated" and i["code"] == "redundant-meta"]
        assert hit, issues

    def test_a_page_repeating_the_tree_accent_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\naccent: teal\n---\n\n## S {#s}\n\nText.\n",
            kit={"name": "x", "accent": "teal"},
        )
        hit = [i for i in issues if i["where"] == "meta.accent"]
        assert hit and hit[0]["code"] == "redundant-meta", issues

    def test_a_genuine_override_is_not_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\naccent: amber\n---\n\n## S {#s}\n\nText.\n",
            kit={"name": "x", "accent": "teal"},
        )
        assert "redundant-meta" not in _codes(issues), issues

    def test_a_derived_value_is_never_reported_as_authored(self, tmp_path):
        """The tree default lands in `m` too. Flagging it would tell the
        author to delete a line they never wrote."""
        issues = _issues(
            tmp_path,
            "---\ntitle: T\n---\n\n## S {#s}\n\nText.\n",
            kit={"name": "x", "accent": "teal", "audience": "Author"},
        )
        assert "redundant-meta" not in _codes(issues), issues


class TestHandSetDerivable:
    def test_a_hand_counted_read_time_is_noted(self, tmp_path):
        issues = _issues(tmp_path, "---\ntitle: T\nread_time: ~5 min read\n---\n\n## S {#s}\n\nText.\n")
        hit = [i for i in issues if i["code"] == "hand-set-derivable"]
        assert hit and hit[0]["severity"] == "info", issues

    def test_a_page_that_writes_neither_is_quiet(self, tmp_path):
        issues = _issues(tmp_path, "---\ntitle: T\n---\n\n## S {#s}\n\nText.\n")
        assert "hand-set-derivable" not in _codes(issues), issues


# ---------- density ----------


class TestProseOnlySection:
    def test_three_paragraphs_with_nothing_for_the_eye(self, tmp_path):
        issues = _issues(tmp_path, f"---\ntitle: T\n---\n\n## S {{#s}}\n\n{PARA}\n{PARA}\n{PARA}")
        hit = [i for i in issues if i["code"] == "prose-only-section"]
        assert hit, issues
        assert "S" in hit[0]["where"], hit[0]

    def test_two_paragraphs_are_fine(self, tmp_path):
        issues = _issues(tmp_path, f"---\ntitle: T\n---\n\n## S {{#s}}\n\n{PARA}\n{PARA}")
        assert "prose-only-section" not in _codes(issues), issues

    @pytest.mark.parametrize(
        "visual",
        [
            "| a | b |\n|---|---|\n| 1 | 2 |",
            "```python\nx = 1\n```",
            '```oku-kpi-grid\n{"tiles":[{"num":"1","label":"x"}]}\n```',
            "```mermaid\nflowchart TB\n  A --> B\n```",
            '<div class="okt-thing">island</div>',
        ],
    )
    def test_one_visual_clears_the_section(self, tmp_path, visual):
        issues = _issues(tmp_path, f"---\ntitle: T\n---\n\n## S {{#s}}\n\n{PARA}\n{PARA}\n{PARA}\n{visual}\n")
        assert "prose-only-section" not in _codes(issues), issues

    def test_a_callout_does_not_count_as_a_visual(self, tmp_path):
        """A coloured box around a paragraph reads as decorated text.
        Counting it would let any page pass by adding one."""
        issues = _issues(
            tmp_path,
            f"---\ntitle: T\n---\n\n## S {{#s}}\n\n{PARA}\n{PARA}\n{PARA}\n> [!NOTE] N\n> Body.\n",
        )
        assert "prose-only-section" in _codes(issues), issues

    def test_each_section_is_judged_on_its_own(self, tmp_path):
        md = (
            "---\ntitle: T\n---\n\n"
            f"## Thin {{#thin}}\n\n{PARA}\n{PARA}\n{PARA}\n"
            f"## Fat {{#fat}}\n\n{PARA}\n{PARA}\n{PARA}\n| a |\n|---|\n| 1 |\n"
        )
        hits = [i for i in _issues(tmp_path, md) if i["code"] == "prose-only-section"]
        assert len(hits) == 1, hits
        assert "Thin" in hits[0]["where"], hits


# ---------- HTML islands ----------


class TestIslandStyling:
    def test_an_island_with_hardcoded_colour_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            '---\ntitle: T\n---\n\n## S {#s}\n\n<div style="background:#ff0055">x</div>\n',
        )
        hit = [i for i in issues if i["code"] == "island-hand-styled"]
        assert hit and hit[0]["severity"] == "warning", issues

    def test_an_island_with_its_own_stylesheet_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\n---\n\n## S {#s}\n\n<style>.x { color: red }</style>\n",
        )
        assert "island-hand-styled" in _codes(issues), issues

    def test_an_island_built_on_kit_tokens_is_not_flagged(self, tmp_path):
        """This is the shape the kit wants: full HTML capability, colours
        from the page's own palette, so the island follows the accent and
        the light/dark theme."""
        issues = _issues(
            tmp_path,
            "---\ntitle: T\n---\n\n## S {#s}\n\n"
            '<div class="okt-card" style="background:var(--surface); color:var(--text)">x</div>\n',
        )
        assert "island-hand-styled" not in _codes(issues), issues

    def test_a_custom_element_island_is_not_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\n---\n\n## S {#s}\n\n<oku-chart></oku-chart>\n",
        )
        assert "island-hand-styled" not in _codes(issues), issues


# ---------- mermaid ----------


def _diagram(body: str) -> str:
    return "---\ntitle: T\n---\n\n## S {#s}\n\n```mermaid\n" + body + "\n```\n"


class TestDiagramTokens:
    """A `var(--token)` the kit does not define is a diagram that does
    not draw at all.

    `__okuResolveCssVars` substitutes a token's computed value before
    Mermaid sees the source, and leaves an unresolvable one exactly as
    written — deliberately, so the parse error names the token rather
    than a silent substitution rendering the wrong colour. What reaches
    Mermaid is then `var(`, and its grammar has no production for `(`:
    the whole figure becomes a parse-error card.

    The usual cause is not a typo. It is a page written against a newer
    kit than the installed tool carries — reported from another project
    as "the kit documents `--series-N-soft` and does not ship it", with
    `oku --version` reading `kit 2026-08-20-r50` against a repo three
    weeks ahead. So the check reads the kit being CHECKED rather than
    this repo's, and says which one it read the tokens from.
    """

    def test_a_token_the_kit_defines_is_not_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            _diagram(
                "flowchart TB\n  A --> B\n"
                "  classDef x fill:var(--series-3-soft),stroke:var(--series-3),color:var(--text)\n"
                "  class A x"
            ),
        )
        assert "diagram-unknown-token" not in _codes(issues), issues

    def test_a_token_the_kit_does_not_define_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            _diagram(
                "flowchart TB\n  A --> B\n"
                "  classDef x fill:var(--series-3-shoft),stroke:var(--nope)\n  class A x"
            ),
        )
        hit = [i for i in issues if i["code"] == "diagram-unknown-token"]
        assert hit and hit[0]["severity"] == "warning", issues
        assert "--series-3-shoft" in hit[0]["message"], hit
        assert "--nope" in hit[0]["message"], hit

    def test_the_message_points_at_the_version_mismatch(self, tmp_path):
        """The token is usually spelled correctly and the tool is old,
        so a message that only says "unknown token" sends the author
        looking for a typo that is not there."""
        issues = _issues(tmp_path, _diagram("flowchart TB\n  A --> B\n  style A fill:var(--nope)"))
        msg = [i for i in issues if i["code"] == "diagram-unknown-token"][0]["message"]
        assert "oku --version" in msg, msg

    def test_a_stale_kit_is_what_this_reports(self, tmp_path):
        """The reproduction of the report: the SAME page, checked once
        against a kit that defines the token and once against one that
        does not."""
        src = tmp_path / "page.md"
        src.write_text(
            _diagram(
                "flowchart TB\n  A --> B\n"
                "  classDef x fill:var(--series-3-soft),stroke:var(--series-3)\n  class A x"
            ),
            encoding="utf-8",
        )
        page = cli._page_from_source_file(src)
        assert page is not None

        stale = tmp_path / "stale-kit"
        stale.mkdir()
        (stale / "chrome.css").write_text(
            ":root { --series-3: #b45309; --text: #1e1b29; }\n", encoding="utf-8"
        )

        current = {i["code"] for i in cli.check_pages([(src, page)], tmp_path, kit_dir=cli.KIT_DIR)}
        old = {i["code"] for i in cli.check_pages([(src, page)], tmp_path, kit_dir=stale)}

        assert "diagram-unknown-token" not in current, current
        assert "diagram-unknown-token" in old, old

    def test_a_kit_with_no_stylesheet_says_nothing(self, tmp_path):
        """A check that cannot read the kit knows nothing about its
        tokens, and reporting every one of them as unknown is a warning
        nobody reads."""
        src = tmp_path / "page.md"
        src.write_text(_diagram("flowchart TB\n  A --> B\n  style A fill:var(--anything)"), encoding="utf-8")
        page = cli._page_from_source_file(src)
        empty = tmp_path / "no-kit"
        empty.mkdir()

        codes = {i["code"] for i in cli.check_pages([(src, page)], tmp_path, kit_dir=empty)}

        assert "diagram-unknown-token" not in codes, codes

    def test_a_var_outside_a_style_line_is_not_read(self, tmp_path):
        """Only the lines that carry colour are walked, for the same
        reason `#3` in a node label is left alone."""
        issues = _issues(tmp_path, _diagram('flowchart TB\n  A["var(--nope) in prose"] --> B'))
        assert "diagram-unknown-token" not in _codes(issues), issues


class TestMermaidStyling:
    """A `classDef` with a hex literal is the same defect as an inline
    style on an island, so it carries the same code. It went unnoticed
    longer because the lint only ever walked string blocks, and a
    mermaid fence lifts to a typed `diagram` block before it gets
    there — this repo's own architecture page had nine of them.
    """

    def test_a_classdef_with_a_hex_fill_is_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            _diagram("flowchart TB\n  A --> B\n  classDef x fill:#dbeafe,stroke:#1d4ed8\n  class A x"),
        )
        hit = [i for i in issues if i["code"] == "island-hand-styled"]
        assert hit and hit[0]["severity"] == "warning", issues
        assert "diagram" in hit[0]["where"], hit

    def test_the_message_names_the_tokens_to_use_instead(self, tmp_path):
        """A check that says "do not do that" without naming the
        replacement is one authors work around."""
        issues = _issues(
            tmp_path, _diagram("flowchart TB\n  A --> B\n  classDef x fill:#dbeafe\n  class A x")
        )
        msg = [i for i in issues if i["code"] == "island-hand-styled"][0]["message"]
        assert "--series-N-soft" in msg and "--text" in msg, msg

    def test_a_style_statement_is_flagged_too(self, tmp_path):
        issues = _issues(tmp_path, _diagram("flowchart TB\n  A --> B\n  style A fill:#fff"))
        assert "island-hand-styled" in _codes(issues), issues

    def test_a_theme_directive_is_flagged_too(self, tmp_path):
        issues = _issues(
            tmp_path,
            _diagram("%%{init: {'themeVariables': {'primaryColor': '#ff0000'}}}%%\nflowchart TB\n  A --> B"),
        )
        assert "island-hand-styled" in _codes(issues), issues

    def test_an_rgb_call_is_flagged_too(self, tmp_path):
        issues = _issues(
            tmp_path, _diagram("flowchart TB\n  A --> B\n  classDef x fill:rgb(255,0,0)\n  class A x")
        )
        assert "island-hand-styled" in _codes(issues), issues

    def test_a_classdef_on_kit_tokens_is_not_flagged(self, tmp_path):
        issues = _issues(
            tmp_path,
            _diagram(
                "flowchart TB\n  A --> B\n"
                "  classDef x fill:var(--series-1-soft),stroke:var(--series-1),color:var(--text)\n"
                "  class A x"
            ),
        )
        assert "island-hand-styled" not in _codes(issues), issues

    def test_a_hex_in_a_node_label_is_not_flagged(self, tmp_path):
        """Only the lines that carry colour are read. `#3` in a label is
        a number, and a check that guesses is one authors ignore."""
        issues = _issues(tmp_path, _diagram('flowchart TB\n  A["#3 pick"] --> B["ticket #42"]'))
        assert "island-hand-styled" not in _codes(issues), issues

    def test_an_uncoloured_diagram_is_not_flagged(self, tmp_path):
        issues = _issues(
            tmp_path, _diagram("flowchart TB\n  A --> B\n  classDef x stroke-width:2px\n  class A x")
        )
        assert "island-hand-styled" not in _codes(issues), issues


# ---------- accent divergence ----------


class TestAccentDivergence:
    def _tree(self, tmp_path, accents: list[str]) -> list[dict]:
        pages = []
        for i, a in enumerate(accents):
            src = tmp_path / f"p{i}.md"
            src.write_text(
                f"---\ntitle: P{i}\naccent: {a}\n---\n\n## S {{#s{i}}}\n\nText.\n", encoding="utf-8"
            )
            page = cli._page_from_source_file(src)
            pages.append((src, page))
        return cli.check_pages(pages, tmp_path)

    def test_a_tree_with_no_convention_is_noted(self, tmp_path):
        issues = self._tree(tmp_path, ["teal", "amber", "indigo"])
        assert "accent-divergence" in _codes(issues), issues

    def test_two_pages_are_not_enough_to_call_it_a_convention(self, tmp_path):
        issues = self._tree(tmp_path, ["teal", "amber"])
        assert "accent-divergence" not in _codes(issues), issues

    def test_a_tree_that_agrees_is_quiet(self, tmp_path):
        issues = self._tree(tmp_path, ["teal", "teal", "teal"])
        assert "accent-divergence" not in _codes(issues), issues

    def test_a_kit_json_default_settles_it(self, tmp_path):
        (tmp_path / "kit.json").write_text(json.dumps({"name": "x", "accent": "teal"}), encoding="utf-8")
        issues = self._tree(tmp_path, ["teal", "amber", "indigo"])
        assert "accent-divergence" not in _codes(issues), issues


class TestTheReposOwnTree:
    def test_check_still_exits_clean_on_the_docs_tree(self):
        """The rules have to be quiet on real, finished pages or authors
        learn to ignore them."""
        root = Path(__file__).resolve().parents[2]
        pages = [
            (p, page)
            for p in sorted((root / "docs").glob("*.md"))
            if (page := cli._page_from_source_file(p)) is not None
        ]
        assert pages
        errors = [i for i in cli.check_pages(pages, root) if i["severity"] == "error"]
        assert errors == [], errors


# ---------- visualizations that encode nothing ----------


class TestGroupOfOne:
    """A compare-grid, step flow, KPI grid or chart grid draws the
    relationship BETWEEN its members. With one member there is no
    relationship left — what remains is a titled box with an accent on
    it, which is the shape that reads as a visualization without being
    one."""

    @pytest.mark.parametrize(
        ("fence", "payload", "word"),
        [
            ("oku-compare-grid", '{"cards":[{"t":"Only","b":"One card."}]}', "cards"),
            ("oku-step-flow", '{"steps":[{"t":"Only","b":"One step."}]}', "steps"),
            ("oku-kpi-grid", '{"tiles":[{"label":"Rows","value":"12"}]}', "tiles"),
        ],
    )
    def test_a_single_member_is_flagged(self, tmp_path, fence, payload, word):
        issues = _issues(
            tmp_path,
            f"---\ntitle: T\nsummary: S.\n---\n\n## S {{#s}}\n\n```{fence}\n{payload}\n```\n",
        )
        hit = [i for i in issues if i["code"] == "group-of-one"]
        assert hit, _codes(issues)
        assert hit[0]["severity"] == "warning"
        assert word in hit[0]["message"], hit[0]["message"]

    def test_two_members_are_fine(self, tmp_path):
        issues = _issues(
            tmp_path,
            "---\ntitle: T\nsummary: S.\n---\n\n## S {#s}\n\n"
            '```oku-compare-grid\n{"cards":[{"t":"A","b":"x"},{"t":"B","b":"y"}]}\n```\n',
        )
        assert "group-of-one" not in _codes(issues)

    def test_a_repeated_index_is_exempt(self, tmp_path):
        """docs/charts.md indexes nine chart families as nine grids, and
        one family has a single member. There the relationship the
        reader is reading lives between the grids, so a lone card in one
        of them is not the defect this rule is about. Three or more
        instances of the same primitive on a page means a series."""
        cards = '{"cards":[{"t":"only","b":"","href":"#x"}]}'
        body = "\n\n".join(f"```oku-compare-grid\n{cards}\n```" for _ in range(3))
        issues = _issues(tmp_path, f"---\ntitle: T\nsummary: S.\n---\n\n## S {{#s}}\n\n{body}\n")
        assert "group-of-one" not in _codes(issues)


class TestFigureRestatesHeadings:
    """A flowchart whose boxes are the page's own section titles is the
    table of contents, drawn. It adds no relationship the headings do
    not already carry."""

    def test_a_diagram_of_the_headings_is_flagged(self, tmp_path):
        md = (
            "---\ntitle: T\nsummary: S.\n---\n\n"
            "## Plan {#plan}\n\nText.\n\n"
            "## Execute {#execute}\n\nText.\n\n"
            "## Commit {#commit}\n\nText.\n\n"
            "```mermaid\nflowchart LR\n  A[Plan] --> B[Execute]\n  B --> C[Commit]\n```\n"
        )
        issues = _issues(tmp_path, md)
        hit = [i for i in issues if i["code"] == "figure-restates-headings"]
        assert hit, _codes(issues)
        assert hit[0]["severity"] == "warning"
        assert "3 of 3" in hit[0]["message"], hit[0]["message"]

    def test_a_diagram_that_adds_structure_is_not(self, tmp_path):
        """Same three headings, but the figure names the artifacts that
        move between them — which is the relationship the headings do
        not show."""
        md = (
            "---\ntitle: T\nsummary: S.\n---\n\n"
            "## Plan {#plan}\n\nText.\n\n"
            "## Execute {#execute}\n\nText.\n\n"
            "## Commit {#commit}\n\nText.\n\n"
            "```mermaid\nflowchart LR\n"
            "  A[manifest list] --> B[rewrite groups]\n"
            "  B --> C[merged files]\n  C --> D[new snapshot]\n```\n"
        )
        assert "figure-restates-headings" not in _codes(_issues(tmp_path, md))

    def test_a_two_node_diagram_is_left_alone(self, tmp_path):
        """Two boxes is below the floor where the overlap means
        anything — the rule would be guessing."""
        md = (
            "---\ntitle: T\nsummary: S.\n---\n\n"
            "## Plan {#plan}\n\nText.\n\n"
            "## Execute {#execute}\n\nText.\n\n"
            "```mermaid\nflowchart LR\n  A[Plan] --> B[Execute]\n```\n"
        )
        assert "figure-restates-headings" not in _codes(_issues(tmp_path, md))
