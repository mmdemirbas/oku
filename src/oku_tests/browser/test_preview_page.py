"""A page `oku preview` wrote, opened the way an editor's panel opens it.

The panel loads the file over file:// and reloads it after every edit, so
two things have to hold in a browser and nowhere else: the editor's theme
is the first paint, and the reader is put back where they were. The second
broke once already — the kit sets `scroll-behavior: smooth` on <html>, and
a plain scrollTo animated the page down from the top on every keystroke
(1938 of 2400 px after 300 ms), so the read is taken early on purpose.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._wait import page_quiet

SECTIONS = 40


@pytest.fixture(scope="module")
def previewed(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("preview")
    (root / ".git").mkdir()
    docs = root / "docs"
    docs.mkdir()
    (docs / "kit.json").write_text('{"name": "p"}', encoding="utf-8")
    body = "".join(
        f"## Section {i} {{#s{i}}}\n\n" + ("A paragraph of text. " * 40) + "\n\n" for i in range(SECTIONS)
    )
    (docs / "long.md").write_text(f"---\ntitle: Long\n---\n\n{body}", encoding="utf-8")
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "oku.cli",
            "preview",
            str(docs / "long.md"),
            "--out",
            str(root / "out"),
            "--theme",
            "dark",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return Path(json.loads(done.stdout)["html"])


def test_the_page_renders_in_the_editors_theme(previewed: Path, browser) -> None:
    context = browser.new_context(color_scheme="light")
    page = context.new_page()
    try:
        page.goto(previewed.as_uri(), wait_until="load")
        page_quiet(page)
        # The reader's system says light; the editor asked for dark.
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        assert page.evaluate("() => document.querySelectorAll('main section[id]').length") == SECTIONS
    finally:
        context.close()


def test_a_reload_puts_the_reader_back_without_animating(previewed: Path, browser) -> None:
    context = browser.new_context(viewport={"width": 1100, "height": 900})
    page = context.new_page()
    try:
        page.goto(previewed.as_uri(), wait_until="load")
        page_quiet(page)
        page.evaluate("() => window.scrollTo({top: 2400, behavior: 'instant'})")
        page.wait_for_timeout(300)  # the position is saved 80 ms after scrolling stops
        page.reload(wait_until="load")
        page.wait_for_function("() => window.__okuRendered === true")
        page.wait_for_timeout(120)
        assert page.evaluate("() => window.scrollY") == 2400
    finally:
        context.close()
