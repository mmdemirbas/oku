"""What the front-matter scanner keeps, and what it used to delete.

The sibling file `test_front_matter.py` covers the other half — which
keys the kit knows and what it says about a typo of one.

The scanner walked from the opening `---` to the NEXT `---` wherever it
was, keeping only lines that matched `key: value` and silently dropping
everything else. Two shapes lost the author's text with nothing to
report it:

* a block whose closing `---` is missing — the scanner runs on into the
  body and stops at the first thematic break, deleting every paragraph
  above it;
* a value too long for one line — the continuation is not a `key:`, so
  it is passed over and the value ships truncated mid-sentence.

The second one was live in this repo: `docs/format-comparison.md`'s
summary reached `site-manifest.json`, `llms.txt` and the page cover cut
after "converter weight and".
"""

from __future__ import annotations

from pathlib import Path

from oku import cli

REPO = Path(__file__).resolve().parents[2]


def _check(tmp_path: Path, body: str) -> list[dict]:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "kit.json").write_text('{"name": "probe"}', encoding="utf-8")
    src = root / "docs" / "page.md"
    src.write_text(body, encoding="utf-8")
    cli._project_root_cache.clear()
    page = cli._page_from_source_file(src)
    assert page is not None
    return cli.check_pages([(src, page)], root)


# ---------- continuation lines ----------


def test_a_value_too_long_for_one_line_keeps_its_second_line() -> None:
    text, meta = cli._strip_md_front_matter("---\ntitle: T\nsummary: line one\n  line two\n---\n\nBody.\n")
    assert meta["summary"] == "line one line two"
    assert text.strip() == "Body."


def test_a_value_spread_over_three_lines_joins_with_single_spaces() -> None:
    _, meta = cli._strip_md_front_matter("---\nsummary: one\n  two\n     three\n---\n")
    assert meta["summary"] == "one two three"


def test_a_continuation_is_joined_before_the_value_is_coerced() -> None:
    # `42` alone coerces to an int; with a continuation it is a sentence.
    _, meta = cli._strip_md_front_matter("---\nsummary: 42\n  reasons why\n---\n")
    assert meta["summary"] == "42 reasons why"
    _, plain = cli._strip_md_front_matter("---\norder: 42\n---\n")
    assert plain["order"] == 42


def test_the_repos_own_summary_is_a_whole_sentence() -> None:
    # The live damage. A truncated value is not a crash anywhere, so the
    # guard has to be on the shipped text itself.
    page = cli._page_from_source_file(REPO / "docs" / "format-comparison.md")
    assert page is not None
    summary = page["m"]["summary"]
    assert summary.endswith(".")
    assert "converter weight and ecosystem fit" in summary


# ---------- a block that is not front-matter ----------


def test_a_missing_closing_delimiter_does_not_eat_the_body(tmp_path: Path) -> None:
    body = (
        "---\ntitle: My page\nsummary: Something\n\n"
        "Intro text that must not vanish.\n\n---\n\n## Section {#sec}\n\nMore.\n"
    )
    text, meta = cli._strip_md_front_matter(body)
    assert text == body
    assert "Intro text that must not vanish." in text
    issues = _check(tmp_path, body)
    codes = [i["code"] for i in issues]
    assert "front-matter-malformed" in codes
    bad = next(i for i in issues if i["code"] == "front-matter-malformed")
    assert bad["severity"] == "error"
    assert "Intro text that must not vanish." in bad["message"]
    assert bad["where"] == "line 5"


def test_prose_between_the_delimiters_is_reported_not_deleted(tmp_path: Path) -> None:
    body = "---\n\nIntro paragraph.\n\n---\n\n## S {#s}\n\nTail.\n"
    text, meta = cli._strip_md_front_matter(body)
    assert text == body
    assert "_front_matter_error" in meta
    assert "front-matter-malformed" in [i["code"] for i in _check(tmp_path, body)]


def test_an_unterminated_block_of_keys_alone_is_left_alone() -> None:
    # Nothing is lost — the text comes back whole and the author sees
    # their own front-matter rendered as body on the page.
    body = "---\ntitle: T\norder: 3\n"
    text, meta = cli._strip_md_front_matter(body)
    assert text == body
    assert meta == {}


def test_a_well_formed_page_reports_nothing(tmp_path: Path) -> None:
    body = "---\ntitle: Fine\nsummary: A page\n  with a folded summary.\n---\n\n## S {#s}\n\nText.\n"
    assert "front-matter-malformed" not in [i["code"] for i in _check(tmp_path, body)]


# ---------- tolerated shapes ----------


def test_comments_and_blank_lines_inside_the_block_are_tolerated() -> None:
    _, meta = cli._strip_md_front_matter("---\n# a note about the page\ntitle: T\n\norder: 3\n---\n")
    assert meta == {"title": "T", "order": 3}


def test_a_byte_order_mark_does_not_hide_the_front_matter() -> None:
    # A BOM is not whitespace to `str.strip()`, so the opening `---` did
    # not match, the front-matter rendered as body text, and the page —
    # now titleless — was tagged as materialised repo markdown.
    text, meta = cli._strip_md_front_matter("﻿---\ntitle: BOM Page\n---\n\nBody.\n")
    assert meta["title"] == "BOM Page"
    assert text.strip() == "Body."


def test_quotes_and_booleans_still_coerce() -> None:
    _, meta = cli._strip_md_front_matter('---\ntitle: "Quoted"\ndraft: true\norder: 10\nratio: 1.5\n---\n')
    assert meta == {"title": "Quoted", "draft": True, "order": 10, "ratio": 1.5}


# ---------- the error never travels ----------


def test_the_error_marker_never_reaches_a_written_source(tmp_path: Path) -> None:
    page = {
        "k": "page",
        "t": "T",
        "m": {"summary": "s", "_front_matter_error": (5, "junk")},
        "b": ["Text."],
    }
    assert "_front_matter_error" not in cli.page_to_md(page)
