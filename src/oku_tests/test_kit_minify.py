"""Every build ships the kit minified, and minifying changes no token.

`kit_file_text` runs rjsmin and rcssmin, which take out whitespace and
comments and touch nothing else. rjsmin has one documented gap: it knows
only unnested template literals, and inside a nested one it collapses the
whitespace of the template's text, so a string the page shows or injects
changes with no error anywhere. The kit has no nested template today.
These tests compare the program before and after through a real parser,
so the first nested template fails here rather than in a reader's page.

The stylesheet's counterpart, compared by the browser's own parse, is
browser/test_kit_minify_css.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oku import cli

ts = pytest.importorskip("tree_sitter")
tsjs = pytest.importorskip("tree_sitter_javascript")

_PARSER = ts.Parser(ts.Language(tsjs.language()))
_JS = [n for n in cli.KIT_FILES if n.endswith(".js")]


def _tokens(src: bytes) -> tuple[list[bytes], bool]:
    """The program's leaf tokens, comments left out, and whether it parsed.

    A template string's own text is one token per run between
    substitutions: tree-sitter gives the substitutions as children but not
    the text around them, and that text is what rjsmin can damage."""
    tree = _PARSER.parse(src)
    out: list[bytes] = []
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        if n.type == "comment":
            continue
        if n.type == "template_string":
            subs = [c for c in n.children if c.type == "template_substitution"]
            pos, text = n.start_byte, []
            for c in subs:
                text.append(src[pos : c.start_byte])
                pos = c.end_byte
            text.append(src[pos : n.end_byte])
            out.append(b"template:" + b"\x00".join(text))
            stack.extend(reversed(subs))
        elif n.child_count == 0 or n.type in ("string_fragment", "regex_pattern"):
            out.append(src[n.start_byte : n.end_byte])
        else:
            stack.extend(reversed(n.children))
    return out, tree.root_node.has_error


@pytest.mark.parametrize("name", _JS)
def test_minifying_leaves_every_token_of_the_program(name: str) -> None:
    source, source_broken = _tokens((cli.KIT_DIR / name).read_bytes())
    shipped, shipped_broken = _tokens(cli.kit_file_text(name).encode("utf-8"))
    assert not source_broken, f"{name}: the source does not parse"
    assert not shipped_broken, f"{name}: the minified file does not parse"
    first = next((i for i, (a, b) in enumerate(zip(source, shipped, strict=False)) if a != b), None)
    assert first is None and len(source) == len(shipped), (
        f"{name}: minifying changed the program at token {first}: "
        f"{source[first : first + 3] if first is not None else len(source)} became "
        f"{shipped[first : first + 3] if first is not None else len(shipped)}. A nested template "
        "literal is the known cause (rjsmin's documented limit): build the inner string first."
    )


def test_the_comparison_sees_what_rjsmin_gets_wrong() -> None:
    """The control. Without it the test above could pass by seeing nothing."""
    import rjsmin

    src = b"var a = `p ${ `  q  ` } s`;"
    assert _tokens(src) != _tokens(rjsmin.jsmin(src.decode()).encode())


@pytest.mark.parametrize("name", cli.KIT_FILES)
def test_every_build_ships_the_file_minified(name: str) -> None:
    source = (cli.KIT_DIR / name).stat().st_size
    assert len(cli.kit_file_text(name).encode("utf-8")) < source * 0.7, name


def test_the_build_still_reads_its_stamp_out_of_a_built_tree(tmp_path: Path) -> None:
    kit = tmp_path / "site" / "_oku"
    kit.mkdir(parents=True)
    (kit / "chrome.js").write_text(cli.kit_file_text("chrome.js"), encoding="utf-8")
    assert cli._artifact_kit_stamp(tmp_path) == cli._kit_build_stamp() != "unknown"


def test_the_font_rewrites_still_find_every_face() -> None:
    source = (cli.KIT_DIR / "chrome.css").read_text(encoding="utf-8")
    shipped = cli.kit_file_text("chrome.css")
    assert len(cli._FONT_URL_RE.findall(shipped)) == len(cli._FONT_URL_RE.findall(source)) > 0
    assert len(cli._FONT_FACE_RE.findall(shipped)) == len(cli._FONT_FACE_RE.findall(source)) > 0
