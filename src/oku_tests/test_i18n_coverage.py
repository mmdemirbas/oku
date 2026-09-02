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
DYNAMIC: set[str] = set()

# Emitted from a lookup keyed by something else — a copy format, a
# region role — so the literal sits in a map declaration and never in
# the assignment a pattern above could match. Unlike DYNAMIC the string
# IS in the source; what is missing is a use site shaped like a string.
# Named here so the table still has to carry them.
FROM_LOOKUP = {
    # kit/renderer.js, _renderCopy: LABEL and FULL, keyed by format.
    "Rich",
    "Plain",
    "Copy as rich text",
    "Copy as Markdown",
    "Copy as plain text",
    # The two region roles, passed to region() as an argument.
    "Replace",
    "With",
}

# Strings that are deliberately the same in every language. Each needs a
# reason; "we did not get to it" is not one.
UNTRANSLATED = {
    "TL;DR": "an established abbreviation, used as-is in Turkish technical writing",
    "Markdown": "the name of the format, written the same way in Turkish",
    "Esc": "the key cap, which is printed on the keyboard in English",
}


def _rail_kinds(source: str) -> set[str]:
    """The rail's landmark words, under the keys the kit looks them up by.

    They are common nouns — "Chart", "Table", "Section" — so they cannot
    be plain table keys: the localize walk would apply them to any leaf
    that matched, and on this repo's own docs "Charts" alone matches 18.
    `railKind` prefixes them, and because the prefix is built from a
    variable no pattern above can see the literal at the call site.

    Derived from the source rather than listed here. A new row in
    RAIL_FIGURES ships a word a reader sees on hover, and it should fail
    this test the day it is written, not the day someone remembers.
    """
    kinds = set(re.findall(r"railKind\('([^']+)'\)", source))
    block = re.search(r"var RAIL_FIGURES = \[(.*?)\n\];", source, re.S)
    if block:
        kinds |= set(re.findall(r"\[\s*'[^']*'\s*,\s*'([^']+)'\s*,", block.group(1)))
    return {"rail:" + k for k in kinds}


def _menu_words(source: str) -> set[str]:
    """The presentation menu's vocabulary, under the keys it looks them up by.

    Same hazard as the rail's, same answer. `Theme`, `Language`, `Light`,
    `Dark`, `Narrow` and `Max` are words an author writes — this repo's
    own docs write most of them in a table cell or a card title — and a
    bare table key is matched against the leaf text of author content.
    `menuWord` prefixes them with `menu:` and builds the key from a
    variable, so the literal never appears at a call site.

    Derived from the source, so a row added to the menu ships a word a
    reader sees and fails here the day it is written. The width stops are
    capitalised from WIDTH_MODES rather than written out, which is why
    they are listed here: `menuWord(m.charAt(0)...)` carries no literal.
    """
    words = set(re.findall(r"menuWord\('([^']+)'\)", source))
    if "menuWord(m.charAt(0).toUpperCase() + m.slice(1))" in source:
        block = re.search(r"var WIDTH_MODES = \[(.*?)\];", source, re.S)
        if block:
            words |= {w.capitalize() for w in re.findall(r"'([^']+)'", block.group(1))}
    return {"menu:" + w for w in words}


def _file_kinds(source: str) -> set[str]:
    """The path chip's kind words, under the keys the kit looks them up by.

    Same hazard as the rail's, same answer: `Text`, `Image` and `Video`
    are common nouns, and a bare key is matched against the leaf text of
    author content. `__okuFileKindWord` prefixes them with `file:` and
    builds the key from a variable, so the literal never appears at a
    call site for the patterns above to find.
    """
    block = re.search(r"var __OKU_FILE_LABEL = \{(.*?)\n\};", source, re.S)
    if not block:
        return set()
    return {"file:" + w for w in re.findall(r":\s*'([^']+)'", block.group(1))}


@pytest.fixture(scope="module")
def kit_source(repo_root: Path) -> str:
    return "\n".join(
        (repo_root / "kit" / name).read_text(encoding="utf-8") for name in ("chrome.js", "renderer.js")
    )


@pytest.fixture(scope="module")
def kit_strings(kit_source: str) -> set[str]:
    source = kit_source
    found: set[str] = set()
    for pattern in PATTERNS:
        for hit in pattern.findall(source):
            text = hit.strip()
            if not text or text.startswith(("http", "M ", "L ", "#", ".")):
                continue
            if text in NOT_STRINGS:
                continue
            found.add(text)
    return found | _rail_kinds(source) | _file_kinds(source) | _menu_words(source)


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
        wanted = kit_strings | DYNAMIC | FROM_LOOKUP
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
        known = kit_strings | DYNAMIC | FROM_LOOKUP
        stale = sorted(k for k in table if k not in known)
        assert stale == [], f"{code} table has entries the kit no longer emits: {stale}"


def test_no_namespaced_word_is_a_key_in_its_own_right(kit_source, tables):
    """The safety property behind the `rail:` and `file:` prefixes.

    The localize walk matches a table key against the leaf text of every
    descendant of an `.okt-*` host, and author content lives there. A
    rail word is a common noun — `Charts` matches 18 places in this
    repo's own docs, among them a page title in the tree, an `<h2>` and
    a `<tspan>` inside a diagram. Adding one as a bare key would rewrite
    all of them. The presentation menu's `Theme` / `Language` / `Light` /
    `Dark` are the same class of word and take the same prefix. Held on the runtime side by
    `browser/test_i18n_runtime.py::test_a_rail_word_in_author_content_survives_the_pass`."""
    namespaced = _rail_kinds(kit_source) | _file_kinds(kit_source) | _menu_words(kit_source)
    bare = {k.split(":", 1)[1] for k in namespaced}
    assert bare, "no namespaced words were derived, so this asserts nothing"
    for code, table in tables.items():
        clash = sorted(w for w in bare if w in table)
        assert clash == [], (
            f"{code} table keys {clash} are rail, file-kind or menu words. A key is "
            "matched against author content, so these must stay under their prefix."
        )


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
