"""A file opened from a page can be handed to the reader's editor.

The viewer showed a file, copied its full path and opened it in a new
tab, but not in the tool that edits it — the reader copied the path,
switched to the editor and pasted it into a file dialog. Each editor
registers a URL scheme on install, so the viewer offers a link in that
scheme with the file's full path in it.

Held here:

  - nothing guesses the editor: before a choice the control is a menu,
    and a choice is remembered and becomes a one-click link;
  - every editor's link carries the full path, percent-encoded per
    segment, so a space, a `#` and a Turkish letter in a folder name
    arrive as the folder name;
  - Escape closes the menu and leaves the viewer open — the menu is what
    is in front — and the menu works from the keyboard;
  - where the full path is not known the control is absent, not broken:
    a page moved out of its build tree cannot say where the file is;
  - an editor is offered only where its own source says the link opens
    a file: IntelliJ's `idea://open` is handled by the macOS launcher
    alone, so a Linux reader is not shown it.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from urllib.parse import quote

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

# The navigation itself would leave the page for an app headless Chromium
# does not have. The choice is recorded by the link's own click handler,
# which still runs: preventDefault stops the navigation, not the event.
NO_LAUNCH = """
  window.__launched = [];
  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a[href]');
    if (a && /^(vscode|idea|zed):/.test(a.getAttribute('href'))) {
      e.preventDefault(); window.__launched.push(a.getAttribute('href'));
    }
  }, true);
"""

# The runner's own platform must not decide what the assertions expect.
PLATFORM = """
  Object.defineProperty(Navigator.prototype, 'platform', { get: () => '%s' });
  Object.defineProperty(Navigator.prototype, 'userAgentData', { get: () => undefined });
"""
MAC = PLATFORM % "MacIntel"
LINUX = PLATFORM % "Linux x86_64"


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = tmp_path_factory.mktemp("editor") / "Proje Ş #1"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "tool.py").write_text("x = 1\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "---\ntitle: Editor\nsummary: A file to edit.\n---\n\n## Files {#files}\n\nThe program [`tool.py`](#f/../src/tool.py).\n",
        encoding="utf-8",
    )
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("index"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return root


def _open(browser, url, platform=MAC, width=1440):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_init_script(NO_LAUNCH)
    context.add_init_script(platform)
    page = context.new_page()
    page.goto(url, wait_until="load")
    page_quiet(page)
    page.locator("main .okt-fp[data-status='ok'] .okt-fp-label").first.click()
    page.wait_for_selector(".okt-mdview .okt-viewer-file", state="attached")
    return context, page


@pytest.fixture()
def page(project, browser):
    context, pg = _open(browser, (project / "docs" / "dist" / "standalone" / "index.html").as_uri())
    yield pg
    context.close()


CONTROL = """() => { const box = document.querySelector('.okt-mdview .okt-mdview-editor');
  if (!box) return null;
  const go = box.querySelector('.okt-mdview-editor-go');
  const pick = box.querySelector('.okt-mdview-editor-pick');
  const menu = box.querySelector('.okt-mdview-editor-menu');
  return { go: go ? [go.textContent.trim(), go.getAttribute('href')] : null,
           pick: pick.textContent.trim(), expanded: pick.getAttribute('aria-expanded'),
           menuShown: !menu.hidden && menu.getBoundingClientRect().height > 0,
           items: [...menu.querySelectorAll('a')].map(a => [a.textContent.trim(), a.getAttribute('href'),
                                                             a.getAttribute('aria-checked')]),
           focused: document.activeElement && document.activeElement.textContent.trim() }; }"""


def _expected(project):
    abs_path = str((project / "src" / "tool.py").resolve())
    url_path = "/".join(quote(seg, safe="-_.!~*'()") for seg in abs_path.split("/"))
    return {
        "VS Code": "vscode://file" + url_path,
        "IntelliJ IDEA": "idea://open?file=" + quote(abs_path, safe="-_.!~*'()") + "&line=1",
        "Zed": "zed://file" + url_path,
    }


def test_nothing_is_guessed_before_the_reader_chooses(page):
    c = page.evaluate(CONTROL)
    assert c is not None, "a file whose full path is known offers no editor control"
    assert c["go"] is None, f"an editor was chosen for the reader: {c['go']}"
    assert c["pick"] == "Open in editor", c
    assert not c["menuShown"], c


def test_every_editor_link_carries_the_encoded_full_path(page, project):
    page.click(".okt-mdview-editor-pick")
    c = page.evaluate(CONTROL)
    assert c["menuShown"] and c["expanded"] == "true", c
    want = _expected(project)
    assert {name: href for name, href, _ in c["items"]} == want, c["items"]
    # Nothing in the path survived unencoded that would end it early.
    assert all(" " not in href and "#" not in href for _, href, _ in c["items"]), c["items"]


def test_intellij_is_offered_only_where_its_link_opens_a_file(project, browser):
    context, pg = _open(browser, (project / "docs" / "dist" / "standalone" / "index.html").as_uri(), LINUX)
    try:
        pg.evaluate("() => localStorage.setItem('oku-editor', 'idea')")
        pg.keyboard.press("Escape")
        pg.locator("main .okt-fp[data-status='ok'] .okt-fp-label").first.click()
        pg.wait_for_selector(".okt-mdview .okt-viewer-file", state="attached")
        c = pg.evaluate(CONTROL)
        assert [name for name, _, _ in c["items"]] == ["VS Code", "Zed"], c["items"]
        assert c["go"] is None, f"a choice that cannot open here was offered as the link: {c['go']}"
    finally:
        context.close()


def test_a_choice_is_remembered_and_becomes_one_link(page, project, browser):
    page.click(".okt-mdview-editor-pick")
    page.click(".okt-mdview-editor-item[data-editor='zed']")
    want = _expected(project)["Zed"]
    assert page.evaluate("() => window.__launched") == [want]
    assert page.evaluate("() => localStorage.getItem('oku-editor')") == "zed"
    page.wait_for_function("() => document.querySelector('.okt-mdview-editor-go')")
    c = page.evaluate(CONTROL)
    assert c["go"] == ["Zed", want], c
    assert [i[2] for i in c["items"]] == ["false", "false", "true"], c["items"]
    assert c["pick"] == "", "with a choice made the caret carries no words of its own"


def test_escape_closes_the_menu_and_not_the_viewer(page):
    page.focus(".okt-mdview-editor-pick")
    page.keyboard.press("Enter")
    c = page.evaluate(CONTROL)
    assert c["menuShown"], c
    assert c["focused"] == "VS Code", f"opening from the keyboard left focus on {c['focused']!r}"
    page.keyboard.press("ArrowDown")
    assert page.evaluate(CONTROL)["focused"] == "IntelliJ IDEA"
    page.keyboard.press("Escape")
    c = page.evaluate(CONTROL)
    assert c is not None, "Escape closed the viewer under the menu"
    assert not c["menuShown"], c
    assert c["focused"] == "Open in editor", "focus did not return to the control that opened the menu"
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('.okt-mdview')?.isConnected")


def test_a_click_elsewhere_closes_the_menu(page):
    page.click(".okt-mdview-editor-pick")
    assert page.evaluate(CONTROL)["menuShown"]
    page.click(".okt-mdview-body")
    assert not page.evaluate(CONTROL)["menuShown"]


def test_no_full_path_no_control(project, browser, tmp_path):
    """Moved out of `dist/standalone/`, the page cannot work out where
    the project is, so it cannot say where the file is either."""
    moved = tmp_path / "index.html"
    shutil.copy(project / "docs" / "dist" / "standalone" / "index.html", moved)
    context, pg = _open(browser, moved.as_uri())
    try:
        assert pg.evaluate(CONTROL) is None
    finally:
        context.close()


@pytest.mark.parametrize("width", [360, 1440])
def test_the_list_opens_on_screen(project, browser, width):
    """Hung from the control's right edge, the list began at x=-58 at
    360px, where a code file's bar holds only Open file and this control
    and both sit at the left."""
    context, pg = _open(
        browser, (project / "docs" / "dist" / "standalone" / "index.html").as_uri(), width=width
    )
    try:
        pg.click(".okt-mdview-editor-pick")
        got = pg.evaluate("""() => { const m = document.querySelector('.okt-mdview-editor-menu').getBoundingClientRect();
          const reach = [...document.querySelectorAll('.okt-mdview-editor-item')].every(a => {
            const b = a.getBoundingClientRect(); return document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2) === a; });
          return { left: m.left, right: m.right, w: innerWidth, reach }; }""")
        assert got["left"] >= 0 and got["right"] <= got["w"], got
        assert got["reach"], "an editor in the list is covered by something else"
    finally:
        context.close()
