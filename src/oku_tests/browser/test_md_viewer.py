"""A link to a .md file opens the kit's viewer, not the browser's raw text.

Before this, clicking such a link handed the reader to the browser's
plain-text rendering of markdown: no typography, no theme, no way back
but the back button. The kit renders markdown already, so it renders it
here — in the shared lightbox frame, over the page they came from.

The links exercised here are the shapes that survive to the DOM still
saying `.md`. A relative link written in PROSE is deliberately not one of
them: renderLink rewrites `foo.md` to `foo.html` because that file is a
page in this tree, and the whole page beats a file viewer. What is left
is a root-absolute destination and anything inside an HTML island —
tested in both shapes here, and pinned on the build side by
`test_standalone_local_docs.py`.
"""

from __future__ import annotations

import pytest

# A real file in this repo's docs tree, served raw by the dev handler.
TARGET = "/docs/reference.md"


def _open_page(page, site_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/index.html")
    page.wait_for_selector("main section")
    page.wait_for_function("() => window.__okuRendered === true", timeout=15000)


# Islands are how an author writes a link the renderer must not touch, so
# building one in the DOM is the same shape a real page ships.
INJECT = """(href) => {
  const p = document.createElement('p');
  p.innerHTML = '<a id="probe" href="' + href + '">the file</a>';
  document.querySelector('main').appendChild(p);
}"""

STATE = """() => {
  const w = document.querySelector('.okt-mdview');
  if (!w) return { open: false, href: location.href };
  const r = w.querySelector('.okt-mdview-rendered');
  return {
    open: true,
    // The PATH, not the href: opening the overlay locks body scroll,
    // which moves the scroll-spy and rewrites the hash. That is the
    // lightbox's existing behaviour on every fullscreen figure, and it
    // is not navigation.
    path: location.pathname,
    file: w.querySelector('.okt-mdview-file').textContent,
    dir: w.querySelector('.okt-mdview-dir').textContent,
    view: w.getAttribute('data-view'),
    headings: [...r.querySelectorAll('h1, h2, h3')].map(h => h.textContent),
    ids: [...r.querySelectorAll('[id]')].map(n => n.id),
    renderedText: r.textContent,
    // Prose only. A page that documents the markdown format shows
    // `## Overview {#overview}` inside a fence, and that syntax
    // reaching the reader as text is the whole point of a code block.
    proseText: (() => {
      const clone = r.cloneNode(true);
      clone.querySelectorAll('pre, code').forEach((n) => n.remove());
      return clone.textContent;
    })(),
    source: w.querySelector('.okt-mdview-source code').textContent,
    failed: !!r.querySelector('.okt-mdview-fail'),
  };
}"""


def _open_viewer(page, site_url, href=TARGET):
    _open_page(page, site_url)
    page.evaluate(INJECT, href)
    page.click("#probe")
    page.wait_for_selector(".okt-mdview .okt-mdview-rendered *", timeout=15000)
    # The viewer fetches the file, so the first child appearing is not the
    # pass finishing. Wait for what the tests actually read — the prefixed
    # ids the second render assigns — rather than for a fixed 400ms that
    # only holds while the machine is idle.
    page.wait_for_function(
        "() => { const h = document.querySelector('.okt-mdview .okt-mdview-rendered');"
        "        return !!h && h.querySelectorAll('[id]').length > 0; }",
        timeout=15000,
    )
    return page.evaluate(STATE)


def test_a_markdown_link_opens_the_viewer_instead_of_navigating(page, site_url):
    """The whole point: the reader stays on the page they were reading."""
    state = _open_viewer(page, site_url)

    assert state["open"], "the click navigated away instead of opening the viewer"
    assert state["path"] == "/docs/index.html", state["path"]
    assert not state["failed"], state["renderedText"][:200]


def test_the_file_is_rendered_not_printed(page, site_url):
    """Headings become headings. The regression this replaces showed the
    reader `## Prose primitives {#prose}` as literal text."""
    state = _open_viewer(page, site_url)

    assert len(state["headings"]) > 3, state["headings"]
    assert "{#" not in state["proseText"], "anchor syntax reached the reader as text"
    assert "\n## " not in state["proseText"], "heading syntax reached the reader as text"
    # The exclusion has to be narrow, or the assertion above passes on a
    # page whose whole body failed to parse into one code block.
    assert len(state["proseText"]) > len(state["renderedText"]) / 2, "almost nothing rendered as prose"


def test_the_source_view_is_the_bytes(page, site_url):
    """Two views of the same file. The source pane is what the reader came
    for when they wanted to copy it or check exact whitespace, so it holds
    the file verbatim — front-matter included, which the rendered view
    consumes."""
    state = _open_viewer(page, site_url)
    raw = page.request.get(f"{site_url}{TARGET}").text()

    assert state["source"] == raw, "the source pane is not the file"
    assert state["source"].startswith("---"), "fixture has no front-matter to consume"
    assert not state["renderedText"].startswith("---")


def test_switching_views_swaps_exactly_one_pane(page, site_url):
    _open_viewer(page, site_url)
    page.click(".okt-mdview-view[data-view='source']")
    page.wait_for_timeout(200)
    after = page.evaluate("""() => {
      const w = document.querySelector('.okt-mdview');
      return {
        view: w.getAttribute('data-view'),
        rendered: getComputedStyle(w.querySelector('.okt-mdview-rendered')).display,
        source: getComputedStyle(w.querySelector('.okt-mdview-source')).display,
      };
    }""")

    assert after == {"view": "source", "rendered": "none", "source": "block"}, after


def test_the_viewed_file_cannot_shadow_the_page_ids(page, site_url):
    """Ids are document-global. The viewed file's headings slugify exactly
    as the page's do, so an unprefixed id would make getElementById reach
    into the overlay for the rest of the session — deep links, the TOC and
    scroll-spy all following it. Every emitted id carries the prefix."""
    state = _open_viewer(page, site_url)

    assert state["ids"], "the fixture emitted no ids to check"
    unprefixed = [i for i in state["ids"] if not i.startswith("okv-")]
    assert unprefixed == [], unprefixed

    # And the page's own anchors still resolve to the page.
    leaked = page.evaluate("""() => {
      const ids = [...document.querySelectorAll('main section[id]')].map(s => s.id);
      return ids.filter(id => !document.getElementById(id).closest('main'));
    }""")
    assert leaked == [], leaked


def test_a_fragment_scrolls_within_the_viewed_file(page, site_url):
    """`plan.md#risks` names a heading inside the file, so the viewer
    honours it rather than dropping the reader at the top."""
    _open_page(page, site_url)
    page.evaluate(INJECT, f"{TARGET}#prose")
    page.click("#probe")
    page.wait_for_selector(".okt-mdview .okt-mdview-rendered *", timeout=5000)
    page.wait_for_timeout(500)
    out = page.evaluate("""() => {
      const w = document.querySelector('.okt-mdview');
      const body = w.querySelector('.okt-mdview-body');
      const target = document.getElementById(w._idPrefix + 'prose');
      return { found: !!target, scrolled: body.scrollTop };
    }""")

    assert out["found"], "the fragment names no heading in the fixture"
    assert out["scrolled"] > 0, "the viewer stayed at the top"


def test_the_path_names_the_file_the_author_typed(page, site_url):
    """The resolved URL is a machine's answer. `/docs/reference.md` is the
    reader's — and the filename is the half that identifies it, so it is
    the half that never truncates."""
    state = _open_viewer(page, site_url)

    assert state["file"] == "reference.md", state["file"]
    assert state["dir"] == "/docs/", state["dir"]


def test_an_island_href_reaches_the_viewer_too(page, site_url):
    """A relative href inside an island is not rewritten by the renderer,
    so it arrives here saying `.md`. This is the shape that sent readers
    to plain text."""
    _open_page(page, site_url)
    state = page.evaluate(INJECT, "reference.md") or None
    page.click("#probe")
    page.wait_for_selector(".okt-mdview .okt-mdview-rendered *", timeout=5000)
    page.wait_for_timeout(300)
    state = page.evaluate(STATE)

    assert state["open"] and not state["failed"], state
    assert state["file"] == "reference.md", state["file"]


@pytest.mark.parametrize("href", ["https://example.com/README.md", "#section"])
def test_links_that_are_not_a_local_markdown_file_are_left_alone(page, site_url, href):
    """A .md on someone else's origin is their page to serve — fetching it
    would fail on CORS anyway. A fragment was never this feature's
    business.

    A `.html` link is deliberately absent from this list: the kit's own
    cross-page handler claims those and converts them to hash navigation,
    so `defaultPrevented` is true for a reason that has nothing to do
    with this viewer."""
    _open_page(page, site_url)
    page.evaluate(INJECT, href)
    claimed = page.evaluate("""() => new Promise(r => {
      const a = document.getElementById('probe');
      // Runs after the kit's document-level handler, so defaultPrevented
      // reports whether the kit claimed the click — and preventing here
      // stops the navigation the assertion does not need.
      document.addEventListener('click', (e) => { r(e.defaultPrevented); e.preventDefault(); }, { once: true });
      a.click();
    })""")

    assert claimed is False, f"the viewer claimed {href}"
    assert page.evaluate("() => !!document.querySelector('.okt-mdview')") is False


def test_a_modified_click_is_left_to_the_browser(page, site_url):
    """Cmd / Ctrl / Shift / middle-click all mean "give me the file, not
    your reading of it"."""
    _open_page(page, site_url)
    page.evaluate(INJECT, TARGET)
    claimed = page.evaluate("""() => new Promise(r => {
      const a = document.getElementById('probe');
      document.addEventListener('click', (e) => { r(e.defaultPrevented); e.preventDefault(); }, { once: true });
      a.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, metaKey: true }));
    })""")

    assert claimed is False, "a Cmd-click was swallowed by the viewer"


def test_the_bar_never_hides_behind_the_close_button(page, site_url):
    """The lightbox close button is absolutely positioned over this bar's
    right end. At 1280 the row has slack; at 380 it does not, and the
    actions have to move rather than slide underneath."""
    for width in (1280, 380):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(f"{site_url}/docs/index.html")
        page.wait_for_selector("main section")
        page.wait_for_timeout(300)
        page.evaluate(INJECT, TARGET)
        page.click("#probe")
        page.wait_for_selector(".okt-mdview .okt-mdview-rendered *", timeout=5000)
        page.wait_for_timeout(300)
        boxes = page.evaluate("""() => {
          const r = (s) => document.querySelector(s).getBoundingClientRect().toJSON();
          return {
            actions: r('.okt-mdview-actions'),
            close: r('.okt-lightbox-close'),
            pageScrollsSideways:
              document.documentElement.scrollWidth > document.documentElement.clientWidth,
          };
        }""")
        a, c = boxes["actions"], boxes["close"]
        overlap = not (
            a["right"] <= c["left"]
            or c["right"] <= a["left"]
            or a["bottom"] <= c["top"]
            or c["bottom"] <= a["top"]
        )
        assert not overlap, (width, a, c)
        assert not boxes["pageScrollsSideways"], width


def test_a_file_that_cannot_be_read_says_so_in_the_failure_colour(page, site_url):
    """The notice shipped as `class="callout callout-warning"`, which the
    stylesheet keys nothing off — so a file that could not be read
    announced itself in the accent colour, under a solid square where the
    icon belongs (an unset `--callout-icon` leaves `::before` unmasked).
    Measured against a callout that IS a warning, in the same page."""
    _open_page(page, site_url)
    page.evaluate(INJECT, "nope-there-is-no-such-file.md")
    page.click("#probe")
    page.wait_for_selector(".okt-mdview-fail", timeout=15000)
    measured = page.evaluate("""() => {
      const fail = document.querySelector('.okt-mdview-fail');
      const probe = document.createElement('div');
      probe.style.cssText = 'position:absolute;left:-4000px;top:0';
      probe.innerHTML = '<div class="callout warning"></div><div class="callout"></div>';
      document.body.appendChild(probe);
      const read = (el) => ({
        border: getComputedStyle(el).borderLeftColor,
        glyph: getComputedStyle(el, '::before').backgroundColor,
        icon: getComputedStyle(el, '::before').maskImage,
      });
      const out = {
        fail: read(fail),
        warning: read(probe.children[0]),
        plain: read(probe.children[1]),
      };
      probe.remove();
      return out;
    }""")
    assert measured["warning"] != measured["plain"], (
        "the two controls are identical — nothing is being compared"
    )
    assert measured["fail"]["border"] == measured["warning"]["border"], measured
    assert measured["fail"]["glyph"] == measured["warning"]["glyph"], measured
    assert measured["fail"]["icon"] not in ("none", ""), measured["fail"]["icon"]
