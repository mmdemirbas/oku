"""Finding a page's code samples costs what the samples cost, not their square.

`_rewrite_assets` cuts every string of a page at its code samples, so a
carried image's href is rewritten in prose and left alone in a quotation.
`_code_spans` found those cuts by testing each inline code span against
every span found before it, inline ones included: a string with k spans
paid k²/2 comparisons. `docs/reference.md` reached 590,587 of them in one
render, more than half of what `oku preview` spent on the page, once per
keystroke in an editor's preview.

The test states the scaling rather than a time, so a busy machine moves
both sides: four times the spans may cost up to eight times as long,
where a square costs sixteen.
"""

from __future__ import annotations

import time

from oku import cli


def _page(spans: int) -> str:
    fence = "```js\nconst a = `x`;\n```\n"
    return "".join(f"word `code{i}` word\n" + (fence if i % 50 == 0 else "") for i in range(spans))


def _best_cost(text: str) -> float:
    best = float("inf")
    for _ in range(5):
        start = time.perf_counter()
        cli._code_spans(text)
        best = min(best, time.perf_counter() - start)
    return best


def test_four_times_the_spans_cost_less_than_sixteen_times_as_much() -> None:
    small, large = _page(1500), _page(6000)
    ratio = _best_cost(large) / _best_cost(small)
    assert ratio < 8, f"4x the code spans cost {ratio:.1f}x as long: the search is quadratic"


def test_the_spans_are_the_ones_a_reader_sees() -> None:
    text = "a `one` b\n```\nx `not a span` y\n```\nc `two` d"
    spans = [text[s:e] for s, e in cli._code_spans(text)]
    # A fence's span opens on the newline before it (_FENCE_RE).
    assert spans == ["`one`", "\n```\nx `not a span` y\n```", "`two`"]
