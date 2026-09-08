"""An artifact says what it was built from, and how to build it again.

A reader opening a built page has no way to tell whether they are
looking at something current. That is not a hypothetical: a report was
opened, a rendering defect was reported against it, and the defect had
been fixed three kit stamps earlier — the file was simply old, and
nothing on it said so. The rebuild took ten seconds; finding out that a
rebuild was the answer took considerably longer.

Three facts close that gap, and all three live in the sidebar footer
next to the version that was already there:

- the kit stamp the artifact carries. `v0.4.0` is the same string for
  months, so it cannot answer "how old is this"; `2026-08-11-r33`
  carries its own date and can.
- how long ago it was built.
- the exact command that rebuilds it, `cd` included — an artifact says
  nothing about where its source sits, and the reader is by definition
  somewhere else.

The command is copied rather than run because no page can run it. A
file:// page has no channel to a shell, and the one surface that has a
live server — `oku serve` — symlinks the kit, so a served page is never
the stale one. A rebuild button would work only where it is not needed.

What this file pins is that each fact arrives, in every mode a reader
receives a page in, and that the footer stays a footer while doing it.
"""

from __future__ import annotations

import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

from ._wait import box_stable, measured

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

PAGE = """---
title: Provenance
summary: Whether this page can say what it is.
---

## A section {#a}

A paragraph, so the page has a body and a landmark.
"""


def _serve(directory: Path) -> tuple[str, http.server.ThreadingHTTPServer]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", httpd


@pytest.fixture(scope="module")
def built(tmp_path_factory, monkeypatch_session):
    """A real `oku build` of a two-page tree, served both ways.

    The full command rather than `build_standalone` directly: the
    provenance is computed in `compute_manifest` and reaches the two
    output trees by different routes (inlined in one, a fetched file in
    the other). Calling one builder would test one route.
    """
    from oku import cli

    src = tmp_path_factory.mktemp("prov-src")
    (src / "_oku").symlink_to(KIT, target_is_directory=True)
    (src / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (src / "p.md").write_text(PAGE, encoding="utf-8")
    (src / "index.md").write_text(PAGE.replace("Provenance", "Home"), encoding="utf-8")

    monkeypatch_session.chdir(src)
    args = type("A", (), {"no_vendor": True, "strict": False, "no_search": True})()
    assert cli.cmd_build(args) == 0

    site_url, site_httpd = _serve(src / "dist" / "site")
    alone_url, alone_httpd = _serve(src / "dist" / "standalone")
    yield {
        "root": src,
        "site": f"{site_url}/p.html",
        "standalone": f"{alone_url}/p.html",
        "kit": cli._kit_build_stamp(),
        "pkg": cli._PKG_VERSION,
    }
    site_httpd.shutdown()
    alone_httpd.shutdown()


@pytest.fixture(scope="module")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


def _open(page, url: str):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(url)
    page.wait_for_function("() => window.__okuRendered === true", timeout=30000)
    # The footer's second line is filled after the manifest resolves,
    # which is a fetch in site mode. Waiting for the element rather than
    # a duration is what keeps this off the flaky list.
    page.wait_for_selector("page-nav .page-nav-age", state="attached", timeout=15000)


FOOTER = """() => {
  const f = document.querySelector('page-nav .page-nav-footer');
  if (!f) return null;
  const q = s => f.querySelector(s);
  const cmd = q('.page-nav-cmd');
  return {
    stamp: q('.page-nav-stamp')?.textContent || null,
    version: q('.page-nav-version')?.textContent ?? null,
    age: q('.page-nav-age')?.textContent || null,
    button: q('.page-nav-rebuild')?.textContent || null,
    cmd: cmd?.textContent || null,
    cmdShown: cmd ? cmd.getClientRects().length > 0 : null,
    cmdSelectable: cmd ? getComputedStyle(cmd).userSelect : null,
    drift: q('.page-nav-drift')?.textContent || null,
    height: f.getBoundingClientRect().height,
  };
}"""


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_a_built_page_carries_the_stamp_it_was_built_with(built, page, mode):
    """The fact whose absence started this. Both modes, because the
    standalone branch of PageNav returns early — it drops the site tree,
    and dropping the build block with it is exactly the shape of bug
    that made the language switch miss the artifact people are sent."""
    _open(page, built[mode])
    foot = page.evaluate(FOOTER)
    assert foot is not None, f"{mode}: no sidebar footer at all"
    # `kit <stamp>`, spelled the way `oku --version` spells it, so the
    # footer and the terminal can be compared without translating.
    assert foot["stamp"] == f"kit {built['kit']}", (
        f"{mode}: footer says {foot['stamp']!r}, built with {built['kit']!r}"
    )
    assert foot["version"] == f" v{built['pkg']}", (
        f"{mode}: footer says oku {foot['version']!r}, the tool is {built['pkg']!r}. "
        "A hand-kept constant here read v0.4.0 against a 0.6.5 package for as long "
        "as nobody put the two side by side"
    )


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_a_built_page_says_how_old_it_is(built, page, mode):
    """Age is the half of the drift a page can answer alone. The other
    half — how far behind the installed kit it is — needs a number the
    page could only get by reaching the network, so `oku build` prints
    that one instead."""
    _open(page, built[mode])
    assert page.evaluate(FOOTER)["age"] == "built today"


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_the_command_is_hidden_until_it_is_asked_for(built, page, mode):
    """Two reasons, and the first is the regression this caught: `code`
    is inline, so showing it needs `display: block` — and an author rule
    setting `display` outranks the UA stylesheet's `[hidden]`, which
    shipped the command permanently open and took the footer from 61px
    to 140px. The second is that the command carries a path from the
    author's machine, and an artifact travels."""
    _open(page, built[mode])
    foot = page.evaluate(FOOTER)
    assert foot["cmdShown"] is False, f"{mode}: the command is showing before anyone asked"
    assert foot["height"] <= 70, (
        f"{mode}: the footer is {foot['height']:.0f}px — it is eating the sidebar, "
        "which is what an unhidden command block does"
    )


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_the_rebuild_button_hands_over_a_command_that_names_the_source(built, page, mode):
    """The click reveals AND copies. Revealing is the half that cannot
    fail, and it is the fallback for every browser that refuses the
    clipboard — so it is the half asserted here."""
    _open(page, built[mode])
    page.click(".ctrl-btn.drawer-toggle")  # pin the drawer; the footer lives in it
    # `drawer-open` is on the body the moment the handler runs; the panel
    # is still sliding, and everything read below lives inside it.
    box_stable(page, "page-nav")
    page.click(".page-nav-rebuild")
    foot = measured(page, FOOTER)
    assert foot["cmdShown"] is True, f"{mode}: clicking Rebuild revealed nothing"
    assert foot["cmd"] == f"cd {built['root']} && oku build", (
        f"{mode}: the command is {foot['cmd']!r} — it must name the source tree, "
        "because the reader is not standing in it"
    )
    assert foot["cmdSelectable"] != "none", (
        f"{mode}: the command cannot be selected — the footer is user-select:none and "
        "hand-selecting it is the fallback when the clipboard is refused"
    )
    assert page.get_attribute(".page-nav-rebuild", "aria-expanded") == "true"


CONTRAST = """(selectors) => {
  const srgb = c => { c/=255; return c<=0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = p => 0.2126*srgb(p[0]) + 0.7152*srgb(p[1]) + 0.0722*srgb(p[2]);
  const parse = s => (s.match(/[\\d.]+/g) || []).slice(0,3).map(Number);
  const bgOf = el => { let n = el;
    while (n && n !== document.documentElement) {
      const b = getComputedStyle(n).backgroundColor;
      if (!/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) return parse(b);
      n = n.parentElement; }
    return parse(getComputedStyle(document.body).backgroundColor); };
  // Every ancestor's opacity multiplies in. Measuring the declared
  // colour alone reports a contrast nobody is looking at.
  const opacityOf = el => { let n = el, o = 1;
    while (n && n !== document.documentElement) { o *= parseFloat(getComputedStyle(n).opacity); n = n.parentElement; }
    return o; };
  const out = {};
  for (const sel of selectors) {
    const el = document.querySelector('page-nav ' + sel);
    if (!el) { out[sel] = null; continue; }
    const bg = bgOf(el.parentElement), a = opacityOf(el);
    const fg = parse(getComputedStyle(el).color).map((c, i) => c*a + bg[i]*(1-a));
    const [hi, lo] = [lum(fg), lum(bg)].sort((p,q)=>q-p);
    out[sel] = +(((hi+0.05)/(lo+0.05)).toFixed(2));
  }
  return out;
}"""

READABLE = [".page-nav-stamp", ".page-nav-age", ".page-nav-rebuild", ".page-nav-cmd", ".page-nav-drift"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_fact_in_the_build_block_clears_the_contrast_floor(built, page, theme):
    """The footer used to be decoration — a version number nobody had to
    read — at `--text-faint` under a blanket `opacity: 0.85`, measuring
    2.8:1. Facts moved in, and a fact under the floor is not a fact the
    reader has. The drift line is why the container opacity had to go
    rather than just the token: a child cannot raise an ancestor's
    opacity, and that line was stuck at 3.86:1 in light."""
    _open(page, built["site"])
    page.evaluate(f"() => document.documentElement.setAttribute('data-theme','{theme}')")
    page.click(".ctrl-btn.drawer-toggle")
    box_stable(page, "page-nav")
    page.click(".page-nav-rebuild")
    # The drift line only exists on a real mismatch; put one in the DOM
    # so its colour is measured on the same surface as the rest.
    page.evaluate("""() => { const d = document.createElement('div');
      d.className = 'page-nav-drift'; d.textContent = 'x';
      document.querySelector('.page-nav-freshness').appendChild(d); }""")
    # The theme was flipped above and every colour here is mid-transition
    # until it lands, so the wait and the assertion read one expression.
    ratios = measured(page, CONTRAST, READABLE)
    under = {k: v for k, v in ratios.items() if v is None or v < 4.5}
    assert not under, f"{theme}: below the 4.5:1 floor — {under} (all: {ratios})"


def test_a_half_updated_tree_says_so(built, page):
    """The one version-against-version comparison a page CAN make: the
    kit the pages were built with, against the kit now running. They
    agree by construction in a standalone file, which inlines both.
    They part company when a dist/site tree has had its shared `_oku/`
    replaced without the pages being rebuilt, or the reverse — which is
    a tree that renders with one kit and was laid out by another."""
    manifest = built["root"] / "dist" / "site" / "site-manifest.json"
    original = manifest.read_text(encoding="utf-8")
    data = json.loads(original)
    assert data["build"]["kit"] == built["kit"], "the site manifest must carry the build stamp"
    data["build"]["kit"] = "2019-01-01-r1"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    try:
        _open(page, built["site"])
        drift = page.evaluate(FOOTER)["drift"]
        assert drift and "2019-01-01-r1" in drift and built["kit"] in drift, (
            f"a tree built by another kit reported {drift!r} — it must name both stamps"
        )
    finally:
        manifest.write_text(original, encoding="utf-8")


def test_a_tree_that_agrees_with_itself_says_nothing(built, page):
    """The other half, and the reason it is a separate test: a drift
    line that shows on a healthy page is how a reader learns to skip
    the line that matters."""
    _open(page, built["site"])
    assert page.evaluate(FOOTER)["drift"] is None


def test_the_footer_never_leaves_the_sidebar(built, page):
    """UI invariant 1 from CLAUDE.md, restated for this change: the
    sidebar surface spans the viewport, and the footer sits at its
    bottom edge. Growing the footer is the way this change could break
    it, so the measurement is taken with the command revealed."""
    _open(page, built["standalone"])
    page.click(".ctrl-btn.drawer-toggle")
    box_stable(page, "page-nav")
    page.click(".page-nav-rebuild")
    box = measured(
        page,
        """() => {
      const nav = document.querySelector('page-nav');
      const foot = nav.querySelector('.page-nav-footer');
      return {nav: nav.getBoundingClientRect(), foot: foot.getBoundingClientRect(),
              vh: window.innerHeight};
    }""",
    )
    assert abs(box["nav"]["height"] - box["vh"]) <= 1, (
        f"sidebar is {box['nav']['height']:.0f}px against a {box['vh']}px viewport"
    )
    assert box["foot"]["bottom"] <= box["nav"]["bottom"] + 1, (
        f"the footer's bottom ({box['foot']['bottom']:.0f}) is past the sidebar's "
        f"({box['nav']['bottom']:.0f}) — the command block pushed it out"
    )


# The build block's own strings are covered by
# `test_i18n_coverage.py`, which extracts every `okuT('…')` in chrome.js
# and requires a Turkish entry for each. Verified by removing one and
# watching it fail, rather than assumed — a second copy of that check
# here would be a copy that can rot out of step with the first.
