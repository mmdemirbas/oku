"""Front-matter is discoverable, and a typo in it is not silent.

Every page has front-matter and it is the one part an author cannot
infer from the body they are writing. Measured before this: the schema
knew 10 keys, the skill briefing named 3 of them, and `parent` — used by
this repo's own pages — was in neither.

`$defs/meta` is `additionalProperties: true` on purpose, so a project can
carry its own keys. The cost was that a misspelling was accepted in
silence: `sumary:` produced nothing but the info-level no-summary nudge,
which is hidden at default verbosity, so the page shipped without a
summary and `oku check` said it was clean.

The rule that resolves both: permissive about unknown keys, loud about
one that looks like a known key spelled wrong.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from oku import cli


def _check(tmp_path: Path, front: str) -> list[dict]:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "p.md").write_text(
        f"---\ntitle: T\n{front}\n---\n\n## S {{#s}}\n\nLead paragraph.\n", encoding="utf-8"
    )
    return cli.check_pages(cli.find_json_pages(docs), docs)


@pytest.mark.parametrize(
    ("typo", "meant"),
    [("sumary", "summary"), ("ordering", "order"), ("acent", "accent"), ("parnet", "parent")],
)
def test_a_misspelled_key_is_flagged_with_the_real_one(typo: str, meant: str, tmp_path: Path) -> None:
    issues = [i for i in _check(tmp_path, f"summary: s\n{typo}: x") if i["code"] == "unknown-meta-key"]

    assert issues, f"{typo!r} was accepted in silence"
    assert meant in issues[0]["message"], issues[0]["message"]
    assert issues[0]["severity"] == "warning", "info is hidden at default verbosity"


def test_a_key_resembling_nothing_is_left_alone(tmp_path: Path) -> None:
    """`additionalProperties: true` is deliberate — a project may carry
    its own keys, and warning on those would train authors to ignore the
    check."""
    issues = [i for i in _check(tmp_path, "summary: s\nticket_id: ABC-1") if i["code"] == "unknown-meta-key"]

    assert issues == [], issues


def test_every_key_this_repo_uses_is_known(tmp_path: Path) -> None:
    """`parent` was used by these pages and absent from the schema, so
    the schema could not have caught a typo of it either."""
    import re

    known = set(cli._known_meta_keys())
    for page in Path("docs").glob("*.md"):
        m = re.match(r"---\n(.*?)\n---", page.read_text(encoding="utf-8"), re.S)
        if not m:
            continue
        used = {ln.split(":")[0].strip() for ln in m.group(1).splitlines() if ":" in ln and ln[:1].strip()}
        unknown = sorted(used - known)
        assert unknown == [], f"{page.name} uses {unknown}, which the schema does not define"


# ---------- discoverability ----------


def test_spec_prints_every_key_with_what_it_does(capsys) -> None:
    cli.cmd_spec(argparse.Namespace(name="front-matter", json=False))
    out = capsys.readouterr().out

    for key in cli._known_meta_keys():
        assert f"{key}:" in out, f"{key} is not in `oku spec front-matter`"
    # A key without an explanation is a key an author still has to guess.
    body = [ln for ln in out.splitlines() if ln.endswith(">") and ":" in ln]
    assert body == [], f"keys printed with no description: {body}"


def test_the_listing_mentions_it(capsys) -> None:
    """A discoverability feature nobody can discover is the failure the
    command exists to fix."""
    cli.cmd_spec(argparse.Namespace(name=None, json=False))
    out = capsys.readouterr().out

    assert "front-matter" in out, out


def test_the_derived_keys_are_marked_as_derived(capsys) -> None:
    """Hand-setting one freezes a value the build would keep current,
    and `hand-set-derivable` only says so after the fact."""
    cli.cmd_spec(argparse.Namespace(name="front-matter", json=False))
    out = capsys.readouterr().out

    for key in cli._DERIVABLE_META:
        line = next(ln for ln in out.splitlines() if ln.startswith(f"{key}:"))
        assert "DERIVED" in line and "do not hand-set" in line, line


def test_a_placeholder_left_in_prose_is_flagged(tmp_path: Path) -> None:
    """ "Word-search for placeholders before delivering" was a step in the
    skill's manual checklist. A checklist step is skipped in silence; a
    check is not."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
    (docs / "p.md").write_text(
        "---\ntitle: T\nsummary: s\n---\n\n## S {#s}\n\n"
        "Revenue rose to {{ figure }} last quarter.\n\nTODO: check this.\n\n"
        "We keep a todo list, which is ordinary prose.\n\n"
        "```python\n# TODO: inside code, not prose\npass\n```\n",
        encoding="utf-8",
    )
    issues = [i for i in cli.check_pages(cli.find_json_pages(docs), docs) if i["code"] == "placeholder-text"]
    found = {i["message"].split("placeholder ")[1].split(".")[0] for i in issues}

    assert len(issues) == 2, [i["message"] for i in issues]
    assert found == {"'{{ figure }}'", "'TODO'"}, found


class TestWherePlaceholdersAreLookedFor:
    """The rule read paragraphs and nothing else.

    `process-breadcrumb` walks prose nested inside typed payloads — a
    step body, a card, a KPI label, a table cell — because that is prose
    an author writes and a reader reads. `placeholder-text` sat beside
    it in the same function and did not. Measured on one page carrying
    the same `TODO` in a paragraph and in a step body: one warning, from
    the paragraph. This repo's own `examples/iceberg.md` had carried
    "still TODO in build sequence step 11" in a compare-grid card,
    past `oku check --strict`, long enough for all three things the card
    listed as future work to have shipped.

    The other half is where it must NOT look. Naming the token is not
    leaving one behind, and the kit's own severity table has to spell
    the four it catches — which is how the gap surfaced: closing it made
    `docs/cli.md` fail its own check.
    """

    def _check(self, tmp_path: Path, body: str) -> list[dict]:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
        (docs / "p.md").write_text(
            f"---\ntitle: T\nsummary: s\n---\n\n## S {{#s}}\n\n{body}\n", encoding="utf-8"
        )
        return [
            i for i in cli.check_pages(cli.find_json_pages(docs), docs) if i["code"] == "placeholder-text"
        ]

    def test_a_step_body_is_prose_too(self, tmp_path: Path) -> None:
        issues = self._check(
            tmp_path,
            '```oku-step-flow\n{"steps":[{"t":"First","b":"A step body carrying TODO."},'
            '{"t":"Second","b":"Another step."}]}\n```',
        )

        assert len(issues) == 1, [i["message"] for i in issues]
        assert issues[0]["where"].endswith("k=step-flow"), issues[0]

    def test_a_compare_card_is_prose_too(self, tmp_path: Path) -> None:
        """The shape the repo's own example page carried."""
        issues = self._check(
            tmp_path,
            '```oku-compare-grid\n{"cards":[{"t":"In","b":"- one\\n- two"},'
            '{"t":"Out","b":"- Mermaid diagrams (still TODO in step 11)"}]}\n```',
        )

        assert len(issues) == 1, [i["message"] for i in issues]

    def test_a_table_cell_is_prose_too(self, tmp_path: Path) -> None:
        issues = self._check(
            tmp_path,
            '```oku-table\n{"headers":["name","note"],"rows":[["a","fine"],["b","TBD"]]}\n```',
        )

        assert len(issues) == 1, [i["message"] for i in issues]

    def test_an_island_is_markup_the_reader_sees_through(self, tmp_path: Path) -> None:
        """The content rules sat past three `continue`s, so a line inside
        an island reached none of them.

        No blank line inside the island, deliberately: a blank line ends
        the html BLOCK, which is what lets an author write markdown
        between the tags — and those lines were already reaching the
        rules as ordinary prose. The gap was the lines the walker still
        considers island markup."""
        issues = self._check(
            tmp_path,
            '<div class="okt-card">\n  <p>A card built by hand, carrying TODO.</p>\n</div>',
        )

        assert len(issues) == 1, [i["message"] for i in issues]

    def test_markdown_between_the_tags_was_never_the_gap(self, tmp_path: Path) -> None:
        """The control for the case above. A blank line ends the block,
        so this line is ordinary prose and always was."""
        issues = self._check(
            tmp_path,
            '<div class="okt-card">\n\nA card built by hand, carrying TODO.\n\n</div>',
        )

        assert len(issues) == 1, [i["message"] for i in issues]

    def test_the_breadcrumb_rule_moved_with_it(self, tmp_path: Path) -> None:
        """Both content rules sat behind the same three `continue`s and
        both now run ahead of them, so an island cannot be the one place
        either of them stops looking."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "kit.json").write_text('{"name":"probe"}', encoding="utf-8")
        (docs / "p.md").write_text(
            "---\ntitle: T\nsummary: s\n---\n\n## S {#s}\n\n"
            '<div class="okt-card">\n  <p>Fixed in round 3, see the prior notes.</p>\n</div>\n',
            encoding="utf-8",
        )
        codes = [
            i["code"]
            for i in cli.check_pages(cli.find_json_pages(docs), docs)
            if i["code"] == "process-breadcrumb"
        ]

        assert codes == ["process-breadcrumb"], codes

    def test_a_pre_body_is_code_and_stays_code(self, tmp_path: Path) -> None:
        """A raw-text element holds a program. `// TODO` in a sample is
        the sample, and flagging it would make the rule unusable in any
        page that shows real code."""
        issues = self._check(
            tmp_path,
            "<div>\n<pre><code>function f() {\n  // TODO: implement\n}\n</code></pre>\n</div>",
        )

        assert issues == [], [i["message"] for i in issues]

    def test_a_token_in_a_code_span_is_being_named(self, tmp_path: Path) -> None:
        """`TODO` in backticks is a citation of the token. Without this
        the rule cannot be documented in a page the rule checks."""
        issues = self._check(
            tmp_path,
            "The check catches `TODO`, `TBD`, `FIXME`, `XXX` and an unfilled `{{ }}` template.",
        )

        assert issues == [], [i["message"] for i in issues]

    def test_a_token_in_a_payload_code_span_is_being_named_too(self, tmp_path: Path) -> None:
        """Both paths, or the severity table fails in one spelling and
        passes in the other."""
        issues = self._check(
            tmp_path,
            '```oku-table\n{"headers":["Code","Catches"],'
            '"rows":[["`placeholder-text`","A leftover `TODO` or `TBD`."]]}\n```',
        )

        assert issues == [], [i["message"] for i in issues]

    def test_a_bare_token_beside_a_code_span_still_fires(self, tmp_path: Path) -> None:
        """The guard: a rule that ignored the whole line whenever it held
        any code span would pass every test above by measuring nothing."""
        issues = self._check(tmp_path, "The `TODO` check exists. TODO: wire it up.")

        assert len(issues) == 1, [i["message"] for i in issues]

    def test_the_line_number_survives_the_masking(self, tmp_path: Path) -> None:
        """Masked to spaces rather than deleted. Stripping a span moves
        everything after it, so `file:line` would name a line the author
        has to count to find — and every locator in the checker is a
        line number into the source as written."""
        body = "A first line with `code` in it.\n\nA second line.\n\nTODO: the fourth."
        issues = self._check(tmp_path, body)

        assert len(issues) == 1, [i["message"] for i in issues]
        # front-matter is 4 lines, blank, `## S`, blank, then the body.
        assert issues[0]["line"] == 12, issues[0]


class TestAccentValue:
    """A key spelled right whose VALUE the browser cannot parse.

    `accent: rose` was documented, absent from the renderer's palette,
    and not a CSS named colour — so the fallback wrote an invalid
    declaration and `--accent` computed to the literal string `rose`.
    `buildConfig` hands `--accent` to Mermaid's `themeVariables`, which
    requires a concrete colour, so every diagram on the page became an
    "Unsupported color format" card while `oku check --strict` called
    the page clean.

    The renderer keeps the default now rather than writing a token it
    could not resolve, which turns a page of error cards into a page in
    the wrong colour. That is the recoverable failure, and this check is
    what makes it visible instead of silent.
    """

    @pytest.mark.parametrize("token", ["teal", "amber", "indigo", "rose", "violet", "green", "slate"])
    def test_every_documented_token_is_accepted(self, token: str, tmp_path: Path) -> None:
        issues = [
            i for i in _check(tmp_path, f"summary: s\naccent: {token}") if i["code"] == "accent-unknown"
        ]

        assert issues == [], issues

    @pytest.mark.parametrize("value", ["#b45309", "rgb(180 83 9)", "hsl(28 91% 37%)", "rebeccapurple"])
    def test_a_colour_the_browser_can_read_is_accepted(self, value: str, tmp_path: Path) -> None:
        """Only bare words are judged. A hex or a function form is the
        browser's to parse, and a check that guesses at those is one
        authors learn to ignore."""
        issues = [
            i for i in _check(tmp_path, f"summary: s\naccent: {value}") if i["code"] == "accent-unknown"
        ]

        assert issues == [], issues

    def test_a_bare_word_that_is_no_colour_is_flagged(self, tmp_path: Path) -> None:
        issues = [
            i for i in _check(tmp_path, "summary: s\naccent: notacolour") if i["code"] == "accent-unknown"
        ]

        assert issues, "the value was accepted in silence"
        assert issues[0]["severity"] == "warning", "info is hidden at default verbosity"
        assert issues[0]["where"] == "meta.accent", issues[0]

    def test_a_near_miss_names_the_token_meant(self, tmp_path: Path) -> None:
        issues = [i for i in _check(tmp_path, "summary: s\naccent: rosé") if i["code"] == "accent-unknown"]

        assert issues, "the value was accepted in silence"
        assert "rose" in issues[0]["message"], issues[0]["message"]
