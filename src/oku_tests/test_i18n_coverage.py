"""Every string the kit shows a reader has a translation.

The kit writes ~90 strings of its own onto a page — button labels,
tooltips, aria-labels, placeholders. They are keyed by the ENGLISH
STRING, so a missing entry does not crash: it silently leaves that one
control in English on a translated page. Silent and per-string is
exactly the shape that accumulates, so the coverage is asserted rather
than remembered.

A new string added to chrome.js without a Turkish entry fails here, on
the day it is written.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# Patterns that only ever match a string a reader can see. Deliberately
# narrower than "every literal": a heuristic that also catches selectors
# and class names produces failures nobody can act on, and a test people
# learn to override is worse than no test.
PATTERNS = [
    # aria-label="…" / title="…" / placeholder="…" inside a markup string
    re.compile(r"""(?:aria-label|title|placeholder)=["']([A-Z][^"'<>{}]{1,70})["']"""),
    # el.setAttribute('aria-label', '…')
    re.compile(
        r"""setAttribute\(\s*['"](?:aria-label|title|placeholder)['"]\s*,\s*['"]([A-Z][^'"]{1,70})['"]"""
    ),
    # el.textContent = '…'  /  el.title = '…'
    re.compile(r"""\.(?:textContent|title|placeholder|ariaLabel)\s*=\s*['"]([A-Z][^'"]{1,70})['"]"""),
    # okuT('…') — an explicit request for a translation
    re.compile(r"""okuT\(\s*'([^']{2,140})'"""),
    # getAttribute('x-label') || 'Default'
    re.compile(r"""getAttribute\(['"][a-z-]+['"]\)\s*\|\|\s*'([A-Z][^']{2,70})'"""),
    # >Visible text< inside a markup string the kit assembles
    re.compile(r""">([A-Z][a-zA-Z][a-zA-Z ;/'…&-]{1,45})<"""),
]

# Matches of the patterns above that are not strings at all. Each is a
# false positive with a named cause, not a string we chose to skip.
NOT_STRINGS = {
    # A prose example inside the i18n design comment in chrome.js.
    "btn.close",
    # `'Toggle ' + label` survives only in a comment describing why that
    # concatenation was replaced by a template.
    "Toggle",
}

# Passed to okuT() as a VARIABLE, so the literal never appears in the
# source and no pattern can find it. Named here so the coverage test
# still guards them instead of quietly losing them.
DYNAMIC = {
    # `okuT(mode)` inside _widthLabelFor — the three WIDTH_MODES.
    "narrow",
    "comfortable",
    "max",
}

# Strings that are deliberately the same in every language. Each needs a
# reason; "we did not get to it" is not one.
UNTRANSLATED = {
    "TL;DR": "an established abbreviation, used as-is in Turkish technical writing",
    "Esc": "the key cap, which is printed on the keyboard in English",
}


@pytest.fixture(scope="module")
def kit_strings(repo_root: Path) -> set[str]:
    source = "\n".join(
        (repo_root / "kit" / name).read_text(encoding="utf-8") for name in ("chrome.js", "renderer.js")
    )
    found: set[str] = set()
    for pattern in PATTERNS:
        for hit in pattern.findall(source):
            text = hit.strip()
            if not text or text.startswith(("http", "M ", "L ", "#", ".")):
                continue
            if text in NOT_STRINGS:
                continue
            found.add(text)
    return found


@pytest.fixture(scope="module")
def tables(repo_root: Path) -> dict[str, dict]:
    out = {}
    for path in sorted((repo_root / "kit" / "i18n").glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out


def test_a_language_table_exists(tables):
    assert tables, "kit/i18n/ carries no table, so nothing can be translated"
    assert "tr" in tables


def test_every_reader_facing_string_is_translated(kit_strings, tables):
    for code, table in tables.items():
        wanted = kit_strings | DYNAMIC
        missing = sorted(s for s in wanted if s not in table and s not in UNTRANSLATED)
        assert missing == [], (
            f"{len(missing)} kit string(s) have no {code} translation and will render "
            f"in English on a {code} page: {missing}"
        )


def test_the_table_names_nothing_the_kit_stopped_saying(kit_strings, tables):
    """The mirror failure: a string is reworded in chrome.js and the old
    key survives in the table, so the entry silently stops applying and
    the new wording ships untranslated."""
    for code, table in tables.items():
        stale = sorted(k for k in table if k not in kit_strings and k not in DYNAMIC)
        assert stale == [], f"{code} table has entries the kit no longer emits: {stale}"


def test_a_placeholder_template_keeps_its_slots(tables):
    """`{0}` is substituted at runtime. A translation that drops the slot
    loses the value — a filename, a line number, a series name."""
    for code, table in tables.items():
        for english, translated in table.items():
            slots = set(re.findall(r"\{\d\}", english))
            assert set(re.findall(r"\{\d\}", translated)) == slots, (
                f"{code}: {english!r} -> {translated!r} does not carry the same placeholders"
            )


def test_no_translation_is_left_as_the_english(tables):
    """An entry equal to its key is either an oversight or belongs in
    UNTRANSLATED with a reason."""
    for code, table in tables.items():
        same = sorted(k for k, v in table.items() if k == v and k not in UNTRANSLATED)
        assert same == [], f"{code}: untranslated entries with no recorded reason: {same}"


def test_the_table_ships_to_other_projects(repo_root: Path):
    """Other projects read the copy of kit/ packed into the wheel."""
    import tomllib

    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    force = data["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

    assert "kit/i18n" in force, "the language tables are not packed into the wheel"
    assert force["kit/i18n"] == "oku/assets/i18n"
