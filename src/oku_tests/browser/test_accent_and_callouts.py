"""One accent, one hue family — and every callout type gets its glyph.

Both defects here surfaced on the same block of one real page: an
`> [!IMPORTANT]` callout rendered a solid coloured square where its
icon belongs, sitting in a body tinted a completely different hue from
its own left rule.

They have separate causes.

  * **The square.** `.callout.important` had no `--callout-icon`, so
    the ::before fell back to `mask-image: none` — and a 20x20 box
    painted `--accent-strong` with no mask is a filled block. IMPORTANT
    is one of the five standard GFM admonition types, so this was the
    default rendering of a type authors reach for.

  * **The two hues.** `_applyAccent` derived `--accent-soft` and
    `--accent-strong` only for the three named palettes. Any other
    colour set `--accent` and stopped, leaving both companions on the
    indigo defaults and dark mode underived. Invisible while the accent
    is indigo, which is the default — it appears the moment an author
    picks a colour.
"""

from __future__ import annotations

import http.server
import re
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# Every GFM type the kit maps, so a future type added without an icon
# fails here rather than shipping as a square.
TYPES = ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"]

CALLOUTS = "\n\n".join(f"> [!{t}]\n> Body line for {t}." for t in TYPES)

# An orange the kit does not know. The reporting page used exactly this.
CUSTOM = "#c2410c"

PAGES = {
    "hex": f'---\ntitle: Hex\nsummary: A colour the kit has no palette for.\naccent: "{CUSTOM}"\n---\n\n'
    f"## Callouts {{#callouts}}\n\n{CALLOUTS}\n",
    "named": "---\ntitle: Named\nsummary: One of the three hand-tuned palettes.\naccent: teal\n---\n\n"
    f"## Callouts {{#callouts}}\n\n{CALLOUTS}\n",
}


@pytest.fixture(scope="module")
def accent_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("accent")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    manifest = {
        "schema_version": 1,
        "root": ".",
        "pages": [
            {"path": f"{stem}.html", "source": f"{stem}.md", "title": stem, "parent": None} for stem in PAGES
        ],
    }
    for stem, md in PAGES.items():
        (d / f"{stem}.md").write_text(md, encoding="utf-8")
        (d / f"{stem}.html").write_text(cli._stub_for(stem, inline_manifest=manifest), encoding="utf-8")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def hexpage(accent_url, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(f"{accent_url}/hex.html")
    page.wait_for_timeout(1200)
    yield page
    page.close()


def _rgb(value: str) -> tuple[int, int, int]:
    nums = re.findall(r"[\d.]+", value)
    return tuple(round(float(n)) for n in nums[:3])


def _hue(rgb: tuple[int, int, int]) -> float:
    """Hue in degrees. The comparison that matters here: two surfaces on
    one object must come from the same family."""
    r, g, b = (c / 255 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return -1.0  # achromatic — no hue to disagree about
    if mx == r:
        h = 60 * (((g - b) / d) % 6)
    elif mx == g:
        h = 60 * ((b - r) / d + 2)
    else:
        h = 60 * ((r - g) / d + 4)
    return h % 360


def _hue_gap(a: float, b: float) -> float:
    if a < 0 or b < 0:
        return 0.0
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ---------- every type gets a glyph ----------


@pytest.mark.parametrize("kind", [t.lower() for t in TYPES])
def test_every_callout_type_renders_a_glyph_not_a_block(hexpage, kind):
    """`mask-image: none` on a filled 20x20 box is a solid square. The
    mask is what makes the box a glyph."""
    got = hexpage.evaluate(
        """(k) => {
        const el = document.querySelector('.callout.' + k);
        if (!el) return null;
        const cs = getComputedStyle(el, '::before');
        return { icon: getComputedStyle(el).getPropertyValue('--callout-icon').trim(),
                 mask: cs.maskImage || cs.webkitMaskImage,
                 w: cs.width, h: cs.height };
    }""",
        kind,
    )
    assert got is not None, f"no .callout.{kind} rendered"
    assert got["icon"], f"{kind} declares no --callout-icon — its ::before paints as a square"
    assert got["mask"] not in ("none", "", None), got


# ---------- one hue family ----------

# Two colours read as one family well inside this; the defect was 180
# degrees apart (orange rule, indigo body).
HUE_TOLERANCE_DEG = 40


def test_a_custom_accent_carries_its_soft_and_strong_surfaces(hexpage):
    """The authored hex stays verbatim on --accent; the two companions
    are derived from it rather than left on the previous palette."""
    got = hexpage.evaluate(
        """() => {
        const s = getComputedStyle(document.documentElement);
        const rgbOf = v => { const d = document.createElement('div');
                             d.style.color = v; document.body.appendChild(d);
                             const c = getComputedStyle(d).color; d.remove(); return c; };
        return { accent: rgbOf(s.getPropertyValue('--accent')),
                 soft: rgbOf(s.getPropertyValue('--accent-soft')),
                 strong: rgbOf(s.getPropertyValue('--accent-strong')) };
    }"""
    )
    hues = {k: _hue(_rgb(v)) for k, v in got.items()}
    assert _hue_gap(hues["accent"], hues["soft"]) <= HUE_TOLERANCE_DEG, (got, hues)
    assert _hue_gap(hues["accent"], hues["strong"]) <= HUE_TOLERANCE_DEG, (got, hues)
    # The authored value survives untouched — an author who wrote a hex
    # expects to see that hex.
    assert _rgb(got["accent"]) == (194, 65, 12), got


def test_a_callout_body_and_its_rule_are_one_hue(hexpage):
    """The reported symptom, as a number: an orange left rule around an
    indigo-tinted body, with an indigo glyph inside it."""
    got = hexpage.evaluate(
        """() => {
        const el = document.querySelector('.callout.important');
        const before = getComputedStyle(el, '::before');
        return { rule: getComputedStyle(el).borderLeftColor,
                 body: getComputedStyle(el).backgroundColor,
                 glyph: before.backgroundColor };
    }"""
    )
    hues = {k: _hue(_rgb(v)) for k, v in got.items()}
    assert _hue_gap(hues["rule"], hues["body"]) <= HUE_TOLERANCE_DEG, (got, hues)
    assert _hue_gap(hues["rule"], hues["glyph"]) <= HUE_TOLERANCE_DEG, (got, hues)


def test_a_custom_accent_reaches_the_dark_theme_too(hexpage):
    """The hex branch emitted no dark-theme rule at all, so a page with
    a custom accent fell back to indigo the moment the reader switched
    themes."""
    got = hexpage.evaluate(
        """() => {
        document.documentElement.setAttribute('data-theme', 'dark');
        const s = getComputedStyle(document.documentElement);
        const rgbOf = v => { const d = document.createElement('div');
                             d.style.color = v; document.body.appendChild(d);
                             const c = getComputedStyle(d).color; d.remove(); return c; };
        const out = { accent: rgbOf(s.getPropertyValue('--accent')),
                      soft: rgbOf(s.getPropertyValue('--accent-soft')),
                      strong: rgbOf(s.getPropertyValue('--accent-strong')) };
        document.documentElement.removeAttribute('data-theme');
        return out;
    }"""
    )
    hues = {k: _hue(_rgb(v)) for k, v in got.items()}
    for key in ("soft", "strong"):
        assert _hue_gap(hues["accent"], hues[key]) <= HUE_TOLERANCE_DEG, (got, hues)
    # Dark-theme soft is a deep tint, not the pale one from light mode.
    assert sum(_rgb(got["soft"])) < sum(_rgb(got["accent"])), got


def test_a_named_palette_is_untouched(accent_url, browser):
    """The three hand-tuned palettes are better than anything derived
    from a single hex. The derivation is the fallback, not a
    replacement."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        page.goto(f"{accent_url}/named.html")
        page.wait_for_timeout(1200)
        got = page.evaluate(
            """() => {
            const s = getComputedStyle(document.documentElement);
            return { accent: s.getPropertyValue('--accent').trim(),
                     soft: s.getPropertyValue('--accent-soft').trim(),
                     strong: s.getPropertyValue('--accent-strong').trim() };
        }"""
        )
        assert got["accent"] == "#0f766e", got
        assert got["soft"] == "#ccfbf1", got
        assert got["strong"] == "#115e59", got
    finally:
        page.close()
