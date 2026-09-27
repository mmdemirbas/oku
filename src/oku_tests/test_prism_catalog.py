"""The kit knows which names are Prism grammars, and which it carries.

Three facts decide whether a ```<lang> fence highlights, and the vendor
directory answers none of them on its own: whether the name is a grammar
at all, which grammar an alias resolves to, and what that grammar
requires. `src/oku/prism_catalog.json` carries them, generated from
Prism's own components.json by `tools/prism_catalog.py`.

Held here against the version the CLI pins and against the vendored copy
when one is on disk — a catalog from a different release would resolve
an alias the shipped autoloader does not have.
"""

from __future__ import annotations

import json
from pathlib import Path

from oku import cli

CATALOG = Path(cli.__file__).resolve().parent / "prism_catalog.json"


def test_the_catalog_names_the_version_the_cli_pins() -> None:
    assert json.loads(CATALOG.read_text(encoding="utf-8"))["prism"] == cli._PRISM_VERSION


def test_a_grammar_is_told_from_a_word() -> None:
    # `hcl` is a grammar and asks for a file; `text` and `pseudocode` are
    # words an author writes over a block, and nothing can be fetched for
    # them. Reporting the second kind would fire on correct prose.
    assert cli.prism_components_needed(["hcl"]) == ["hcl"]
    assert cli.prism_components_needed(["text", "pseudocode", "oku-chart", ""]) == []


def test_an_alias_resolves_the_way_the_autoloader_resolves_it() -> None:
    # Measured in a browser before this existed: a ```adoc fence fetches
    # prism-asciidoc.min.js, and ```rb loads ruby. A rule reading the
    # component directory alone calls both of them missing.
    assert cli.prism_components_needed(["adoc"]) == ["asciidoc"]
    assert cli.prism_components_needed(["rb"]) == ["ruby"]


def test_a_grammar_in_the_core_bundle_needs_no_file() -> None:
    # markup / css / clike / javascript and their aliases are compiled
    # into prism.min.js; the autoloader never asks for a component.
    assert cli.prism_components_needed(["js", "html", "css", "javascript", "xml"]) == []


def test_dependencies_come_first_and_only_once() -> None:
    # A component without its dependencies is a file that still cannot
    # highlight. Order matters to the fetch; the dedupe matters because a
    # tree naming both cpp and c must not fetch c twice.
    assert cli.prism_components_needed(["cpp"]) == ["c", "cpp"]
    assert cli.prism_components_needed(["tsx"]) == ["jsx", "typescript", "tsx"]
    assert cli.prism_components_needed(["c", "cpp", "c"]) == ["c", "cpp"]


def test_every_baseline_language_is_a_real_grammar() -> None:
    """`_PRISM_LANGS` is hand-maintained, so a typo in it is a file that
    404s at the CDN every time the vendor directory is rebuilt."""
    cat = cli.prism_catalog()
    unknown = [lang for lang in cli._PRISM_LANGS if lang not in cat["ids"] and lang not in cat["bundled"]]
    assert unknown == [], f"not Prism grammars: {unknown}"


def test_the_vendor_list_carries_what_the_baseline_depends_on() -> None:
    """The hand-written baseline was dependency-incomplete: it named
    `php` and not `markup-templating`, which php requires — so an
    offline page with a PHP block loaded neither. The FETCH list is
    resolved through the catalog, which is what this holds; the hand
    list stays a statement of intent and cannot break this again."""
    files = {rel for rel, _url in cli._vendor_files()}
    for ident in cli.prism_components_needed(cli._PRISM_LANGS):
        assert f"prism/components/prism-{ident}.min.js" in files, f"{ident} is required and not fetched"
    assert "prism/components/prism-markup-templating.min.js" in files


def test_the_catalog_matches_the_vendored_autoloader() -> None:
    """The vendored autoloader has its own copy of this list baked in.
    When it is on disk, the two must be the same release — an alias the
    catalog knows and the autoloader does not is a refusal that loses
    highlighting."""
    auto = cli.vendor_dir() / "prism" / "plugins" / "autoloader" / "prism-autoloader.min.js"
    if not auto.exists():
        return  # nothing vendored here; the catalog stands on its pin
    text = auto.read_text(encoding="utf-8", errors="replace")
    cat = cli.prism_catalog()
    # The autoloader bakes in exactly two of the three facts — the alias
    # map and the dependency map — and every name in both appears in its
    # source. Plain containment rather than a parser for minified JS:
    # the question is whether the two files are the same release, and a
    # name absent from the blob answers it. (Its map holds no bare ids,
    # which is why `hcl` is not in there and is still a grammar.)
    missing = [a for a in cat["aliases"] if a not in text]
    assert missing == [], f"aliases the vendored autoloader does not know: {missing}"
    missing = [k for k in cat["requires"] if k not in text]
    assert missing == [], f"dependencies the vendored autoloader does not know: {missing}"
