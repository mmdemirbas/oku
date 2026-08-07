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
