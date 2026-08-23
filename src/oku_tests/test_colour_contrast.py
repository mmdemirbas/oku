"""Contrast of the chart ramp, computed rather than eyeballed.

Ten series colours, two themes, three surfaces they can be drawn on —
and until this file, not one ratio had ever been calculated. The ramp
was picked by looking at it, which is exactly the method the repo
rejects everywhere else: a rule that cannot be phrased as a numeric
assertion is not a rule yet.

The threshold is WCAG 2.1 SC 1.4.11 Non-text Contrast, 3:1. That is the
right one here: a bar, a slice or a line is a **graphical object**
essential to understanding the figure, not text. Chart LABELS are text
and live on the ordinary text tokens, which this file does not cover.

No browser is involved. The tokens are plain hex in one stylesheet and
the formula is arithmetic, so this runs in milliseconds and fails on the
day a colour is changed rather than on the day someone opens the page in
sunlight.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parents[2] / "kit" / "chrome.css"

# SC 1.4.11 — graphical objects and UI components.
MIN_RATIO = 3.0

# A chart can sit directly on the page, inside a card, or on the
# secondary surface a nested panel uses. All three are backgrounds a
# series colour is drawn against, so all three are checked.
SURFACE_TOKENS = ("--bg", "--surface", "--surface-2")


def _hex_tokens(css: str, name: str) -> list[str]:
    """Every hex value declared for a token, in document order.

    The light theme is declared first and the dark theme second, which
    is the only ordering this file depends on — asserted below rather
    than assumed, so a reordering fails here instead of silently
    comparing a colour against the wrong theme's surface.
    """
    return re.findall(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})\s*;", css)


def _relative_luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.fixture(scope="module")
def css() -> str:
    return CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ramps(css: str) -> dict[str, list[str]]:
    """The ten series colours per theme, light first."""
    out: dict[str, list[str]] = {"light": [], "dark": []}
    for i in range(1, 11):
        values = _hex_tokens(css, f"--series-{i}")
        assert len(values) == 2, f"--series-{i} is declared {len(values)} times, expected light + dark"
        out["light"].append(values[0])
        out["dark"].append(values[1])
    return out


@pytest.fixture(scope="module")
def surfaces(css: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {"light": {}, "dark": {}}
    for token in SURFACE_TOKENS:
        values = _hex_tokens(css, token)
        assert len(values) == 2, f"{token} is declared {len(values)} times, expected light + dark"
        out["light"][token], out["dark"][token] = values
    return out


def test_the_formula_agrees_with_the_known_extremes() -> None:
    """A contrast function that returns plausible numbers for everything
    proves nothing. Black on white is exactly 21, and a colour against
    itself is exactly 1."""
    assert round(contrast_ratio("#000000", "#ffffff"), 2) == 21.0
    assert round(contrast_ratio("#4d7c0f", "#4d7c0f"), 2) == 1.0


def test_light_is_declared_before_dark(surfaces: dict[str, dict[str, str]]) -> None:
    """Everything above reads the ramps positionally. If the themes are
    ever reordered, every ratio below would be computed against the
    wrong background and still pass."""
    assert _relative_luminance(surfaces["light"]["--bg"]) > 0.5, surfaces["light"]
    assert _relative_luminance(surfaces["dark"]["--bg"]) < 0.2, surfaces["dark"]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("index", range(1, 11))
def test_every_series_colour_clears_three_to_one(
    ramps: dict[str, list[str]],
    surfaces: dict[str, dict[str, str]],
    theme: str,
    index: int,
) -> None:
    colour = ramps[theme][index - 1]
    worst_token, worst = min(
        ((t, contrast_ratio(colour, s)) for t, s in surfaces[theme].items()),
        key=lambda pair: pair[1],
    )
    assert worst >= MIN_RATIO, (
        f"--series-{index} ({colour}) in the {theme} theme is {worst:.2f}:1 against "
        f"{worst_token} ({surfaces[theme][worst_token]}), under the {MIN_RATIO}:1 that "
        "WCAG 2.1 SC 1.4.11 asks of a graphical object."
    )


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_ramp_has_ten_distinct_colours(ramps: dict[str, list[str]], theme: str) -> None:
    """Ten tokens that resolve to nine colours means two series are
    indistinguishable, and the legend is the only thing telling them
    apart."""
    ramp = ramps[theme]
    assert len(set(ramp)) == 10, f"{theme} ramp repeats a colour: {ramp}"


# ---------- the soft plates ----------
#
# A figure that groups nodes by category needs a plate to write a label
# on, and the ramp above is for marks: `fill:var(--series-3)` under
# `color:var(--text)` is dark-on-dark in one theme and light-on-light in
# the other. --series-N-soft is the tint of the same hue, so the pair
# fill/stroke/text reads in both themes. Mermaid `classDef` is the
# caller that forced them to be tokens rather than a color-mix(): its
# grammar takes CSS values, not CSS functions.
#
# The threshold changes with the job. A label ON the plate is text, so
# 4.5:1 (SC 1.4.3). The stroke around it is a graphical object, so 3:1.

MIN_TEXT_RATIO = 4.5


@pytest.fixture(scope="module")
def softs(css: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"light": [], "dark": []}
    for i in range(1, 11):
        values = _hex_tokens(css, f"--series-{i}-soft")
        assert len(values) == 2, f"--series-{i}-soft is declared {len(values)} times, expected light + dark"
        out["light"].append(values[0])
        out["dark"].append(values[1])
    return out


@pytest.fixture(scope="module")
def texts(css: str) -> dict[str, str]:
    values = _hex_tokens(css, "--text")
    assert len(values) == 2, f"--text is declared {len(values)} times, expected light + dark"
    return {"light": values[0], "dark": values[1]}


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("index", range(1, 11))
def test_a_label_on_a_soft_plate_clears_four_and_a_half(
    softs: dict[str, list[str]], texts: dict[str, str], theme: str, index: int
) -> None:
    """The whole reason the tokens exist. A hardcoded pale fill kept its
    pale on a dark page, so the label sat light-on-light and the node
    read as empty."""
    plate = softs[theme][index - 1]
    ratio = contrast_ratio(texts[theme], plate)
    assert ratio >= MIN_TEXT_RATIO, (
        f"--text ({texts[theme]}) on --series-{index}-soft ({plate}) in the {theme} "
        f"theme is {ratio:.2f}:1, under the {MIN_TEXT_RATIO}:1 WCAG 2.1 SC 1.4.3 asks "
        "of body text."
    )


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("index", range(1, 11))
def test_a_series_stroke_is_visible_on_its_own_plate(
    ramps: dict[str, list[str]], softs: dict[str, list[str]], theme: str, index: int
) -> None:
    """The pair is used together — `fill:var(--series-N-soft),
    stroke:var(--series-N)` — so the border has to be visible against
    the fill it encloses, not only against the page."""
    ratio = contrast_ratio(ramps[theme][index - 1], softs[theme][index - 1])
    assert ratio >= MIN_RATIO, (
        f"--series-{index} on --series-{index}-soft in the {theme} theme is "
        f"{ratio:.2f}:1, under {MIN_RATIO}:1."
    )


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_soft_ramp_has_ten_distinct_plates(softs: dict[str, list[str]], theme: str) -> None:
    ramp = softs[theme]
    assert len(set(ramp)) == 10, f"{theme} soft ramp repeats a colour: {ramp}"


@pytest.mark.parametrize("index", range(1, 11))
def test_a_soft_plate_is_pale_in_light_and_deep_in_dark(softs: dict[str, list[str]], index: int) -> None:
    """A plate that did not flip with the theme would pass both contrast
    tests above by being mid-grey, and defeat the point."""
    light = _relative_luminance(softs["light"][index - 1])
    dark = _relative_luminance(softs["dark"][index - 1])
    assert light > 0.5, f"--series-{index}-soft light ({softs['light'][index - 1]}) is not a pale plate"
    assert dark < 0.2, f"--series-{index}-soft dark ({softs['dark'][index - 1]}) is not a deep plate"


# ---------- the accent families ----------
#
# These live in renderer.js rather than chrome.css: the accent is
# written as a stylesheet at render time, because a page picks it in its
# own front-matter. The map held three families and was extended to the
# seven `oku spec front-matter` documents — four palettes that had never
# been drawn, let alone measured, and that had been reaching pages as an
# unresolvable literal in `--accent`.
#
# The threshold here is 4.5:1, not the 3:1 the ramp above uses. The ramp
# colours bars and slices, which are graphical objects; `--accent` and
# `--accent-strong` are the link colour and the text on a callout, which
# are TEXT and take SC 1.4.3.

RENDERER = Path(__file__).resolve().parents[2] / "kit" / "renderer.js"

MIN_TEXT_RATIO = 4.5

ACCENT_THEMES = {
    # theme → (accent key, plate key, strong key, index into the token lists)
    "light": ("light", "soft", "strong", 0),
    "dark": ("dark", "darkSoft", "darkStrong", 1),
}


@pytest.fixture(scope="module")
def palettes() -> dict[str, dict[str, str]]:
    """The `palettes` map, read out of renderer.js rather than copied.

    A copy is what let the schema document seven tokens while the
    renderer carried three.
    """
    js = RENDERER.read_text(encoding="utf-8")
    block = re.search(r"const palettes = \{(.*?)\n      \};", js, re.S)
    assert block, "the palettes map moved — this file reads it by shape"
    out = {}
    for name, body in re.findall(r"(\w+):\s*\{([^}]*)\}", block.group(1)):
        out[name] = dict(re.findall(r"(\w+):\s*'(#[0-9a-fA-F]{6})'", body))
    return out


def test_the_map_carries_every_token_the_schema_documents(palettes) -> None:
    """The guard: every assertion below is per-token, so a missing
    family is measured as nothing rather than as a failure."""
    documented = {"teal", "amber", "indigo", "rose", "violet", "green", "slate"}

    assert set(palettes) == documented, set(palettes) ^ documented
    for name, p in palettes.items():
        assert set(p) == {"light", "soft", "strong", "dark", "darkSoft", "darkStrong"}, (name, p)


@pytest.mark.parametrize("theme", list(ACCENT_THEMES))
@pytest.mark.parametrize("token", ["teal", "amber", "indigo", "rose", "violet", "green", "slate"])
def test_an_accent_is_readable_on_the_page(palettes, surfaces, theme, token) -> None:
    """`--accent` is the link colour, so it is text."""
    accent = palettes[token][ACCENT_THEMES[theme][0]]
    ratio = contrast_ratio(accent, surfaces[theme]["--bg"])

    assert ratio >= MIN_TEXT_RATIO, f"{token} {theme} accent on --bg is {ratio:.2f}:1"


@pytest.mark.parametrize("theme", list(ACCENT_THEMES))
@pytest.mark.parametrize("token", ["teal", "amber", "indigo", "rose", "violet", "green", "slate"])
def test_accent_text_is_readable_on_its_own_plate(palettes, texts, theme, token) -> None:
    """A callout paints `--accent-soft` behind `--accent-strong` and
    behind ordinary body text, so both have to clear the plate. The
    tightest measured is amber's strong-on-soft at 4.51:1 — it clears,
    with nothing to spare, and a retune of amber will fail here."""
    _, plate_key, strong_key, _ = ACCENT_THEMES[theme]
    plate = palettes[token][plate_key]

    strong = contrast_ratio(palettes[token][strong_key], plate)
    body = contrast_ratio(texts[theme], plate)

    assert strong >= MIN_TEXT_RATIO, f"{token} {theme} accent-strong on accent-soft is {strong:.2f}:1"
    assert body >= MIN_TEXT_RATIO, f"{token} {theme} body text on accent-soft is {body:.2f}:1"


@pytest.mark.parametrize("field", ["light", "soft", "strong", "dark", "darkSoft", "darkStrong"])
def test_the_seven_families_share_no_colour(palettes, field) -> None:
    """`violet` and `green` used to fall through to the fallback and
    carry indigo's soft and strong, which is how a page rendered one hue
    on a callout's rule and another on the surface behind it."""
    values = {name: p[field] for name, p in palettes.items()}

    assert len(set(values.values())) == len(values), f"{field} is shared: {values}"
