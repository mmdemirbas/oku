"""Colour arithmetic shared by the browser tests.

`getComputedStyle` hands back `rgb(...)` / `rgba(...)` strings, and the
questions the tests ask of them are always the same two: what does this
look like once it is composited over what is behind it, and is the pair
far enough apart to read. Both were written out by hand in the first
test that needed them; this is the second use.
"""

from __future__ import annotations

import re


_NUM = re.compile(r"-?\d*\.?\d+%?")


def parse_rgb(css: str) -> tuple[float, float, float, float]:
    """A computed colour string → channels 0-255 plus alpha 0-1.

    Chromium hands back three spellings and the tests hit all of them:
    `rgb(r, g, b)`, `rgba(r, g, b, a)`, and — for anything that went
    through `color-mix()` — `color(srgb 0.19 0.19 0.3 / 1)`, whose
    channels are 0-1. Anything else, including `transparent` and a bare
    keyword, is returned as fully transparent black, which `composite`
    then treats as "shows whatever is behind it".
    """
    if "(" not in css:
        return (0.0, 0.0, 0.0, 0.0)
    scale = 255.0 if css.strip().startswith("color(") else 1.0
    nums = _NUM.findall(css[css.index("(") + 1 :])
    if len(nums) < 3:
        return (0.0, 0.0, 0.0, 0.0)

    def val(raw: str, unit: float) -> float:
        return float(raw[:-1]) / 100 * unit if raw.endswith("%") else float(raw)

    r, g, b = (val(n, 255.0) * scale for n in nums[:3])
    alpha = val(nums[3], 1.0) if len(nums) > 3 else 1.0
    return (r, g, b, alpha)


def composite(front: str, back: str) -> tuple[float, float, float]:
    """Source-over: what the eye actually receives."""
    fr, fg, fb, fa = parse_rgb(front)
    br, bg, bb, _ = parse_rgb(back)
    return (
        fr * fa + br * (1 - fa),
        fg * fa + bg * (1 - fa),
        fb * fa + bb * (1 - fa),
    )


def _luminance(rgb: tuple[float, float, float]) -> float:
    def chan(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(a: str | tuple[float, float, float], b: str | tuple[float, float, float]) -> float:
    """WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white).

    Either side may be a CSS string or an already-composited triple. A
    translucent CSS string is composited over the other side first,
    because that is what the reader sees.
    """
    back = b if isinstance(b, tuple) else composite(b, "rgb(255, 255, 255)")
    front = a if isinstance(a, tuple) else composite(a, f"rgb({back[0]}, {back[1]}, {back[2]})")
    hi, lo = sorted((_luminance(front), _luminance(back)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
