"""A kit word drawn when the reader acts is in the page's language too.

The localize pass walks the page once the string table has arrived, and
anything built AFTER that is never visited. Several surfaces are built on
demand and wrote their words as English literals, so on a Turkish page
they stayed English with the translation sitting in the table unused:

  - the chart configuration panel (title, every row label, every chip),
    built when the gear is pressed;
  - the "click to pin" line in every chart reading, built on hover;
  - the glossary card's "Learn more" and its pin hint, built on hover;
  - the board view's "All" lane, built when the view is chosen;
  - the lightbox and the chart reading's close button, built on first
    use;
  - the donut's "total" caption, drawn when the chart renders — which on
    a served page can be before the table has arrived at all.

`test_i18n_runtime.py` sweeps the page as it loads, which is exactly the
state none of these exist in. This one acts first and sweeps after each
step, in both delivery modes: standalone inlines the table, the site
fetches it, and the race is different in each.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet
from .test_i18n_runtime import _KEYS, _TABLE, SURVIVORS

pytestmark = pytest.mark.browser

LINE = {
    "type": "line",
    "title": "Gecikme",
    "series": [{"label": "api", "data": [{"x": 1, "y": 142}, {"x": 2, "y": 155}, {"x": 3, "y": 138}]}],
}
DONUT = {
    "type": "donut",
    "title": "Sayfa yükü",
    "slices": [{"label": "HTML", "value": 12}, {"label": "CSS", "value": 28}, {"label": "JS", "value": 44}],
}

PAGE_MD = f"""---
title: Sonradan çizilenler
summary: Okuyucu bir şey yapınca çizilen kit sözcükleri.
lang: tr
---

## Grafikler {{#grafikler}}

Bir terim: [ACID](#g/ACID).

```oku-chart
{json.dumps(LINE, ensure_ascii=False)}
```

```oku-chart
{json.dumps(DONUT, ensure_ascii=False)}
```

## Tablo {{#tablo}}

| Ad | Durum |
|---|---|
| a | açık |
| b | kapalı |
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    docs = tmp_path_factory.mktemp("ondemand") / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text(PAGE_MD, encoding="utf-8")
    (docs / "page.html").write_text(cli._stub_for("Page"), encoding="utf-8")
    (docs / "kit.json").write_text(
        '{"domains": ["data-platforms"], "rebuild_command": false}', encoding="utf-8"
    )
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=True)) == 0
    finally:
        os.chdir(cwd)
    return docs / "dist"


@pytest.fixture(scope="module")
def served(built):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(built / "site"))

    class Quiet(handler.func):  # type: ignore[misc,valid-type]
        def log_message(self, *a):  # noqa: D401
            pass

    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(built / "site"))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


TEXT = """(sel) => { const e = document.querySelector(sel); return e ? e.textContent.trim() : null; }"""


def _act(browser, url):
    """Open the page, do each thing a reader does, and sweep after each.
    Returns every English survivor and the words the steps produced."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        page.goto(url, wait_until="load")
        page_quiet(page)
        page.evaluate("() => window.__okuI18n.load()")
        page_quiet(page)
        out, seen = [], {}

        def sweep(step):
            out.extend(f"{step}: {s}" for s in page.evaluate(SURVIVORS, _KEYS))

        sweep("load")
        seen["caption"] = page.evaluate(TEXT, ".okc-donut-caption")

        # A chart reading, from the line chart's cursor.
        svg = page.locator("oku-chart").nth(0).locator(".okc-svg")
        box = svg.bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5)
        page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5, steps=6)
        page.wait_for_selector(".okc-tooltip .okc-tt-pin-hint", state="attached", timeout=4000)
        seen["chartPin"] = page.evaluate(TEXT, ".okc-tooltip .okc-tt-pin-hint")
        sweep("chart reading")

        # The configuration panel, from the gear.
        page.locator("oku-chart").nth(0).hover()
        page.locator("oku-chart").nth(0).locator(
            "[title='Grafiği ayarla'], [title='Configure chart']"
        ).first.click(force=True)
        page.wait_for_selector(".okc-config-popover:not([hidden]) .okc-cfg-title")
        seen["cfgTitle"] = page.evaluate(TEXT, ".okc-config-popover .okc-cfg-title")
        seen["cfgLabels"] = page.evaluate(
            "() => [...document.querySelectorAll('.okc-config-popover .okc-cfg-label, .okc-config-popover .okc-cfg-chip')].map(e => e.textContent.trim())"
        )
        sweep("chart panel")
        page.keyboard.press("Escape")
        page.mouse.move(2, 2)

        # The glossary card.
        term = page.locator("main glossary-term").first
        term.hover()
        page.wait_for_selector(".oku-tooltip .okt-pin-hint", timeout=4000)
        seen["glossPin"] = page.evaluate(TEXT, ".oku-tooltip .okt-pin-hint")
        seen["glossLink"] = page.evaluate(TEXT, ".oku-tooltip .okt-link a")
        sweep("glossary card")
        page.mouse.move(2, 2)

        # The board view.
        page.evaluate("() => document.querySelector('.okt-view-btn[data-view=\"board\"]').click()")
        page.wait_for_selector(".okt-board-lane-title", state="attached")
        seen["lanes"] = page.evaluate(
            "() => [...document.querySelectorAll('.okt-board-lane-title')].map(e => e.textContent.trim())"
        )
        sweep("board")

        # The lightbox, built on its first open.
        donut = page.locator("oku-chart").nth(1)
        donut.hover()
        donut.locator(
            "[title='Expand to fullscreen'], [title='" + _TABLE["Expand to fullscreen"] + "']"
        ).first.click(force=True)
        page.wait_for_selector(".okt-lightbox .okt-lightbox-close")
        seen["lightbox"] = page.evaluate(
            "() => document.querySelector('.okt-lightbox .okt-lightbox-close').getAttribute('aria-label')"
        )
        sweep("lightbox")
        return out, seen
    finally:
        context.close()


@pytest.mark.parametrize("mode", ["standalone", "site"])
def test_a_word_built_on_demand_is_in_the_page_language(mode, built, served, browser):
    url = (built / "standalone" / "page.html").as_uri() if mode == "standalone" else served
    survivors, seen = _act(browser, url)
    assert survivors == [], f"{mode}:\n" + "\n".join(survivors[:40])
    assert seen["caption"] == "Toplam", (mode, seen)
    assert seen["chartPin"] == _TABLE["click to pin"], (mode, seen)
    assert seen["cfgTitle"] == _TABLE["Configure chart"], (mode, seen)
    # The line chart's panel: its type row (or the hint that it has no
    # alternatives) and the three marks chips — all kit words.
    assert {"İşaretler", "Noktalar", "Çizgi", "Alan"} <= set(seen["cfgLabels"]), (mode, seen)
    assert seen["glossPin"] == _TABLE["click to pin"], (mode, seen)
    assert seen["glossLink"] == _TABLE["Learn more"] + " →", (mode, seen)
    assert seen["lanes"] and "All" not in seen["lanes"], (mode, seen)
    assert seen["lightbox"] == _TABLE["Close"], (mode, seen)
