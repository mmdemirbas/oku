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
    yield
    cli._tree_defaults_cache.clear()
    cli._git_date_cache.clear()


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
