"""What a page looks like when the author writes only content.

The kit's job is to make `title` + `summary` + prose render as a
finished page. Each test here pins one default that did not, measured
rather than eyeballed:

  * an untitled `> [!TLDR]` printed the words "TL;DR" twice
  * the TL;DR gradient faded to a violet-leaning neutral, so it read
    teal-to-lavender under any accent that was not the default indigo
  * a cover with nothing but a title sat in a 156px tinted panel
  * body prose ran 77-83 characters per line at the default width
  * a three-row table shipped a filter box, a row counter and a gear

The page below sets exactly two front-matter fields. That is the
point — anything an author has to add to get a decent result is the
formatting work this suite exists to remove.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# Long enough to wrap several times at every content width, so the
# characters-per-line measurement has lines to average over.
PARA = (
    "Every checkpoint flushes whatever the writer has buffered, and a five-second "
    "checkpoint interval on a modestly sized topic produces twelve files per minute "
    "per bucket, none of them anywhere near the target size. The table stays correct "
    "throughout; what degrades is planning, because the planner has to open every "
    "footer before it can prune anything at all."
)

PAGE_MD = f"""---
title: Compaction on primary-key tables
summary: Why small files pile up and what the compaction job does about them.
---

> [!TLDR]
> Streaming writes leave thousands of small files.

## Why small files appear {{#why}}

{PARA}

{PARA}

## What the job does {{#what}}

| Stage | Input | Output |
|---|---|---|
| Plan | manifest list | rewrite groups |
| Execute | small files | merged files |
| Commit | merged files | new snapshot |

## A table worth filtering {{#big}}

| Stage | Input | Output |
|---|---|---|
| a | 1 | x |
| b | 2 | x |
| c | 3 | x |
| d | 4 | x |
| e | 5 | x |
| f | 6 | x |
| g | 7 | x |
| h | 8 | x |
"""

# A second page carrying only a title — no summary — so the cover has
# nothing but the h1 to hold.
TITLE_ONLY_MD = """---
title: Bare
---

## Body {#body}

Text.
"""

TITLED_TLDR_MD = """---
title: Titled
summary: The TL;DR carries a real title.
---

> [!TLDR] Where we are
> Body line.

## Body {#body}

Text.
"""

SOURCES = {
    "page": ("Compaction on primary-key tables", PAGE_MD),
    "bare": ("Bare", TITLE_ONLY_MD),
    "titled": ("Titled", TITLED_TLDR_MD),
}


@pytest.fixture(scope="module")
def defaults_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("defaults")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [
            {"path": f"{stem}.html", "source": f"{stem}.md", "title": title, "parent": None}
            for stem, (title, _md) in SOURCES.items()
        ],
    }
    for stem, (title, md) in SOURCES.items():
        (d / f"{stem}.md").write_text(md, encoding="utf-8")
        (d / f"{stem}.html").write_text(cli._stub_for(title, inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def rendered(defaults_url, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{defaults_url}/page.html")
    page.wait_for_timeout(1500)
    yield page
    page.close()


# ---------- TL;DR ----------


def test_untitled_tldr_does_not_print_its_own_name_twice(rendered):
    """`> [!TLDR]` with no title rendered the pill AND an h2 reading
    "TL;DR". The starter template emits exactly that shape, so it was
    the default state of the block that opens most pages."""
    visible = rendered.evaluate(
        """() => {
        const t = document.querySelector('.tldr');
        return [...t.querySelectorAll('*')]
          .filter(e => e.offsetParent !== null || getComputedStyle(e).position === 'static')
          .filter(e => /^tl;dr$/i.test((e.textContent || '').trim()))
          .filter(e => e.getBoundingClientRect().width > 1)
          .map(e => e.tagName + '.' + e.className);
    }"""
    )
    assert len(visible) == 1, f"the words TL;DR are rendered {len(visible)} times: {visible}"
    assert visible[0].startswith("SPAN"), visible


def test_the_tldr_heading_survives_for_the_outline(rendered):
    """buildTOC() skips a section with no h2 and the search index reads
    the section heading, so hiding the duplicate must not delete it."""
    got = rendered.evaluate(
        """() => {
        const h = document.querySelector('.tldr h2');
        if (!h) return null;
        const r = h.getBoundingClientRect();
        return { text: h.textContent.replace('#','').trim(), cls: h.className,
                 w: Math.round(r.width), h: Math.round(r.height) };
    }"""
    )
    assert got is not None, "the TL;DR heading was removed, not hidden"
    assert got["text"] == "TL;DR", got
    assert got["cls"] == "okt-sr-only", got
    assert got["w"] <= 1 and got["h"] <= 1, f"the hidden heading still occupies space: {got}"


def test_a_titled_tldr_still_shows_its_title(defaults_url, browser):
    """The suppression is scoped to the duplicate. A real title has to
    render as a real, visible heading."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        page.goto(f"{defaults_url}/titled.html")
        page.wait_for_timeout(1200)
        got = page.evaluate(
            """() => {
            const h = document.querySelector('.tldr h2');
            const r = h.getBoundingClientRect();
            return { text: h.textContent.replace('#','').trim(), cls: h.className,
                     w: Math.round(r.width), h: Math.round(r.height) };
        }"""
        )
        assert got["text"] == "Where we are", got
        assert got["cls"] == "", got
        assert got["w"] > 50 and got["h"] > 10, f"the titled heading is not visible: {got}"
    finally:
        page.close()


def test_tldr_gradient_does_not_fade_to_an_unrelated_hue(rendered):
    """The far stop was --surface-2 (#f5f3ff), a violet-leaning neutral.
    Under the default indigo accent that reads as intentional; under any
    other accent the card fades to lavender."""
    stops = rendered.evaluate("""() => getComputedStyle(document.querySelector('.tldr')).backgroundImage""")
    assert "245, 243, 255" not in stops, f"the violet stop is still in the gradient: {stops}"
    surface = rendered.evaluate(
        """() => getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()"""
    )
    assert surface == "#ffffff", surface
    assert "255, 255, 255" in stops, f"the gradient does not fade to --surface: {stops}"


# ---------- cover ----------


def test_the_cover_subtitle_falls_back_to_summary(rendered):
    """`summary` is the line the author always writes. Authors were
    copying it verbatim into `subtitle` to fill the cover."""
    got = rendered.evaluate(
        """() => {
        const s = document.querySelector('header.cover .subtitle');
        return s ? s.textContent.trim() : null;
    }"""
    )
    assert got == "Why small files pile up and what the compaction job does about them.", got


def test_a_title_only_cover_shrinks_to_fit(defaults_url, browser):
    """With no eyebrow, subtitle or meta line the full panel padding
    left the h1 stranded in the top third of an empty rectangle."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{defaults_url}/bare.html")
        page.wait_for_timeout(1200)
        got = page.evaluate(
            """() => {
            const c = document.querySelector('header.cover');
            const h = c.querySelector('h1');
            const cb = c.getBoundingClientRect(), hb = h.getBoundingClientRect();
            return { bare: c.classList.contains('cover-bare'),
                     cover: Math.round(cb.height), h1: Math.round(hb.height),
                     slack: Math.round(cb.height - hb.height) };
        }"""
        )
        assert got["bare"] is True, got
        # The panel is padding plus the heading, nothing else. Before the
        # fix the same cover measured 156px around a 48px heading.
        assert got["slack"] <= 70, f"the bare cover still has {got['slack']}px of empty panel: {got}"
    finally:
        page.close()


# ---------- prose measure ----------


CPL = """() => {
  const out = [];
  for (const p of document.querySelectorAll('main > section > p')) {
    const lh = parseFloat(getComputedStyle(p).lineHeight);
    const lines = Math.round(p.getBoundingClientRect().height / lh);
    if (lines >= 3) out.push(Math.round(p.textContent.trim().length / lines));
  }
  out.sort((a, b) => a - b);
  return { n: out.length, median: out[Math.floor(out.length / 2)], max: out[out.length - 1] };
}"""


def test_default_prose_measure_is_inside_the_readable_range(rendered):
    """At the default content width, body paragraphs ran 77-83
    characters per line. The readable range is 45-75."""
    got = rendered.evaluate(CPL)
    assert got["n"] >= 2, f"not enough wrapped paragraphs to measure: {got}"
    assert 45 <= got["median"] <= 75, f"default measure outside the readable range: {got}"


def test_the_width_toggle_still_moves_prose(rendered):
    """The symmetric model was adopted because authors expect the
    toggle to act on every block kind. It still does — on a curve
    suited to reading."""
    seen = {}
    for mode in ("narrow", "comfortable", "wide", "max"):
        rendered.evaluate(f"document.body.setAttribute('data-content-width','{mode}')")
        rendered.wait_for_timeout(200)
        seen[mode] = rendered.evaluate(CPL)["median"]
    rendered.evaluate("document.body.setAttribute('data-content-width','comfortable')")
    rendered.wait_for_timeout(200)
    assert seen["narrow"] < seen["comfortable"] < seen["wide"] < seen["max"], seen
    assert seen["narrow"] >= 45, f"narrow is too tight to read: {seen}"


def test_visual_primitives_are_not_clamped_to_the_prose_measure(rendered):
    """Only running prose is capped. A table still fills the content
    width — that was the whole objection to the asymmetric model. (A
    SMALL table is the stated exception: it sizes to its content, so
    this measures one past the threshold.)"""
    got = rendered.evaluate(
        """() => {
        const t = document.querySelector('#big .okt-table-wrap');
        const p = document.querySelector('main > section > p');
        return { table: Math.round(t.getBoundingClientRect().width),
                 para: Math.round(p.getBoundingClientRect().width) };
    }"""
    )
    assert got["table"] > got["para"] + 100, got


# ---------- small tables ----------


def test_a_small_table_ships_no_filter_counter_or_gear(rendered):
    """Three rows, all on screen. A filter box and a row counter above
    them answer a question nobody has at that size."""
    got = rendered.evaluate(
        """() => {
        const w = document.querySelector('#what .okt-table-wrap');
        const vis = s => { const e = w.querySelector(s); if (!e) return false;
                           const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        return { scale: w.dataset.scale, filter: vis('.okt-filter'), stats: vis('.okt-stats'),
                 gear: vis('[data-cfg]'), views: vis('.okt-view-group'),
                 copy: vis('[data-copy]'), expand: vis('[data-expand]') };
    }"""
    )
    assert got["scale"] == "small", got
    assert got["filter"] is False and got["stats"] is False, got
    assert got["gear"] is False and got["views"] is False, got
    # Copy and expand are useful at any size and must survive.
    assert got["copy"] is True and got["expand"] is True, got


def test_a_small_table_does_not_offer_to_sort_three_rows(rendered):
    """Same non-answer as filtering them."""
    got = rendered.evaluate(
        """() => {
        const th = document.querySelector('#what .okt-table-wrap th');
        return { cursor: getComputedStyle(th).cursor,
                 arrow: getComputedStyle(th, '::after').content };
    }"""
    )
    assert got["cursor"] == "default", got
    assert got["arrow"] in ("none", "normal"), got


def test_a_small_table_sizes_to_its_content(rendered):
    """Three short cells stretched across the full content width read as
    a layout accident. The cap at 100% still holds."""
    got = rendered.evaluate(
        """() => {
        const w = document.querySelector('#what .okt-table-wrap');
        const t = w.querySelector('table');
        return { table: Math.round(t.getBoundingClientRect().width),
                 wrap: Math.round(w.getBoundingClientRect().width) };
    }"""
    )
    assert got["table"] < got["wrap"], got
    assert got["table"] <= got["wrap"], got


def test_a_table_past_the_threshold_keeps_its_controls(rendered):
    """The threshold is a size rule, not a removal. Eight rows is past
    it and the full toolbar comes back."""
    got = rendered.evaluate(
        """() => {
        const w = document.querySelector('#big .okt-table-wrap');
        const vis = s => { const e = w.querySelector(s); if (!e) return false;
                           const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        return { scale: w.dataset.scale || null, filter: vis('.okt-filter'), gear: vis('[data-cfg]') };
    }"""
    )
    assert got["scale"] is None, got
    assert got["filter"] is True and got["gear"] is True, got


def test_the_quiet_surface_has_no_hue_of_its_own(rendered):
    """--surface-2 backs 38 rules — table header band, chart tracks, code
    background, TOC hover. At #f5f3ff it carried 12 points of blue over
    red, which reads as intentional beside the default indigo accent and
    as an unrelated lavender everywhere else."""
    rgb = rendered.evaluate(
        """() => {
        const v = getComputedStyle(document.documentElement)
                    .getPropertyValue('--surface-2').trim();
        const d = document.createElement('div');
        d.style.color = v; document.body.appendChild(d);
        const c = getComputedStyle(d).color; d.remove();
        return c.match(/\\d+/g).slice(0, 3).map(Number);
    }"""
    )
    spread = max(rgb) - min(rgb)
    assert spread <= 5, f"--surface-2 is {rgb}, a spread of {spread} — it reads as a hue, not a neutral"
