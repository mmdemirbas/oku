"""Reader state that persisted yesterday must not kill the chrome today.

A standalone page INLINES chrome.js. The stub loads the same file with
`defer`, but an inline script ignores `defer` — so in `dist/standalone/`
every top-level statement in the kit runs mid-`<head>`, with
`document.body` still null. The two modes therefore execute the same
file against two different DOMs, and only one of them is covered by a
test that opens a served page.

That is how the drawer-pin restore shipped broken. `setDrawerState`
writes classes onto `<body>`; restoring the pin at parse time threw, and
because the throw was in top-level code the rest of the kit never ran —
no chrome cluster, no sidebar, not one control. It fired only for a
reader who had pinned the drawer, on every standalone page they opened
afterwards (file:// shares one localStorage across the whole tree), and
it was self-locking: unpinning needs the button that was lost with the
rest.

So the invariant is not "the pin restores". It is that NO persisted
value the kit writes can stop the chrome from being built. The second
test derives the key list from the kit source, so a new persisted key
arrives here as a failure rather than as an untested path.
"""

from __future__ import annotations

from ._wait import page_quiet

import argparse
import os
import re
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PAGE_MD = """---
title: Stored state
summary: Opened with a reader's preferences already in storage.
---

> [!TLDR]
> The chrome has to survive whatever is in localStorage.

## A section {#one}

Prose.

## Another {#two}

More prose.
"""

# A plausible stored value per key the kit persists. Keys are discovered
# from the source below; anything new lands here as a KeyError, which is
# the point — the author picks a realistic value rather than the test
# guessing one.
SEED = {
    "theme-pref": "dark@light",
    "oku-drawer-pinned": "1",
    "htmldoc-content-width": "narrow",
    "oku-personalization": '{"env":"prod"}',
}

CHROME = """() => ({
    errors:  window.__testErrors || [],
    drawer:  !!document.querySelector('.ctrl-btn.drawer-toggle'),
    theme:   !!document.querySelector('.ctrl-btn.theme-toggle'),
    width:   !!document.querySelector('.ctrl-btn.width-toggle'),
    search:  !!document.querySelector('.ctrl-btn[class*=search]'),
    nav:     !!document.querySelector('page-nav'),
    pinned:  document.body.classList.contains('drawer-pinned'),
    sections: document.querySelectorAll('main section').length,
})"""


def _persisted_keys() -> set[str]:
    """Every localStorage key the kit reads or writes, from the source.

    Identifiers are resolved against their `var NAME = '...'` line, so
    DRAWER_PIN_KEY counts as the key it holds.
    """
    keys: set[str] = set()
    for name in ("chrome.js", "chrome-boot.js", "renderer.js"):
        src = (KIT / name).read_text(encoding="utf-8")
        consts = dict(re.findall(r"var\s+([A-Z_][A-Z0-9_]*)\s*=\s*'([^']+)'", src))
        for arg in re.findall(r"localStorage\.(?:get|set)Item\(\s*([^,)]+)", src):
            arg = arg.strip()
            if arg.startswith(("'", '"')):
                keys.add(arg[1:-1])
            elif arg in consts:
                keys.add(consts[arg])
    return keys


@pytest.fixture(scope="module")
def standalone_file(tmp_path_factory):
    docs = tmp_path_factory.mktemp("stored") / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Stored state"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        rc = cli.cmd_build(argparse.Namespace(no_search=True))
    finally:
        os.chdir(cwd)
    assert rc == 0, "build failed"
    out = docs / "dist" / "standalone" / "page.html"
    assert out.exists(), "standalone build produced no page"
    return out


def _load_with_storage(page, url, values: dict[str, str]):
    """Open the page once to own the origin, seed storage, open it again.

    Errors are collected on `window` rather than through a Playwright
    listener because the reload replaces the listener's execution
    context; a hook installed on `init` script survives it.
    """
    page.add_init_script(
        "window.__testErrors = []; addEventListener('error', e => window.__testErrors.push(String(e.message)));"
    )
    page.goto(url, wait_until="load")
    page.evaluate(
        "vals => { for (const [k, v] of Object.entries(vals)) localStorage.setItem(k, v); }", values
    )
    page.goto(url, wait_until="load")
    page_quiet(page)
    return page.evaluate(CHROME)


def test_a_pinned_drawer_does_not_take_the_chrome_with_it(page, standalone_file):
    got = _load_with_storage(page, standalone_file.as_uri(), {"oku-drawer-pinned": "1"})
    assert got["errors"] == [], f"the page threw on load: {got['errors']}"
    assert got["drawer"] and got["theme"] and got["width"] and got["search"], got
    assert got["nav"], "the sidebar never got built"
    # And the state is honoured, not merely survived: a reader who pinned
    # the drawer gets it back.
    assert got["pinned"], "the pinned drawer was dropped instead of restored"


def test_no_persisted_value_can_stop_the_chrome_from_being_built(page, standalone_file):
    got = _load_with_storage(page, standalone_file.as_uri(), SEED)
    assert got["errors"] == [], f"the page threw on load: {got['errors']}"
    assert got["drawer"] and got["theme"] and got["width"] and got["search"], got
    assert got["nav"], "the sidebar never got built"
    assert got["sections"] >= 2, got


def test_every_key_the_kit_persists_is_covered_here():
    """A key the kit stores but this file never seeds is an untested
    load path, and the failure it hides is invisible until a reader
    happens to have set it."""
    missing = _persisted_keys() - set(SEED)
    assert not missing, f"persisted keys with no seeded value in SEED: {sorted(missing)}"
