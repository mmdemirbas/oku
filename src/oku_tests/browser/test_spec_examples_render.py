"""Every payload `oku spec` prints actually draws something.

The rest of the suite asserts the shipped examples are *valid* — against
the schema and against the structural checks. Validity is the wrong
question to stop on. The kit's own briefing warns that a wrong-but-valid
payload "validates clean and renders empty", and that is the one failure
class no linter can catch, because an empty box is well-formed.

It is also not hypothetical for this file. Rendering the seven examples
that had never been rendered turned up two defects at once: `oku check`
rejected `oku-chart-grid`, a fence the renderer draws, and `oku spec`
printed an ```oku-code fence for three kinds that no fence lifts. Both
were invisible to every gate that only asked "is this valid?".

So the payload is put on a page and the page is opened. A figure that
paints nothing fails here.
"""

from __future__ import annotations

import argparse
import contextlib
import http.server
import io
import json
import threading

import pytest

from oku import cli


KIT = cli.KIT_DIR
EXAMPLES = cli._load_examples()

# One page per group keeps any single page from carrying 68 figures —
# a diagram waits on a CDN, and a page that times out reports as a
# rendering failure when it is a network one.
GROUPS = {
    "blocks": sorted(EXAMPLES["blocks"]),
    "charts": sorted(EXAMPLES["charts"]),
}


def _page_source(names: list[str], group: str) -> str:
    """Build the page out of what `oku spec` prints, not out of the
    examples file directly. What the author pastes is what gets tested."""
    out = [
        "---",
        f"title: {group} probe",
        f"summary: Every shipped {group} example, rendered.",
        "---",
        "",
    ]
    for name in names:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.cmd_spec(argparse.Namespace(name=name, json=False))
        out += [f"## {name} {{#x-{name}}}", "", "Lead paragraph.", "", buf.getvalue().rstrip(), ""]
    return "\n".join(out)


def _png(w: int, h: int, rgb: tuple[int, int, int] = (90, 140, 160)) -> bytes:
    """A real PNG of a real size, built in-process so the fixture needs no
    binary asset checked into the repo."""
    import struct
    import zlib

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture(scope="module")
def examples_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("spec-examples")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    # `image`'s example points at a neighbouring file. Without it the page
    # renders a broken image and the failure reads as a kit defect; at 1x1
    # it renders a real image with no area, which fails the same
    # assertion for a reason that has nothing to do with the kit.
    (d / "diagram.png").write_bytes(_png(240, 140))
    manifest = {"schema_version": 1, "root": ".", "pages": []}
    for group, names in GROUPS.items():
        (d / f"{group}.md").write_text(_page_source(names, group), encoding="utf-8")
        (d / f"{group}.html").write_text(
            cli._stub_for(f"{group} probe", inline_manifest=manifest), encoding="utf-8"
        )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


# Ink, per section: the painted geometry a figure is supposed to leave
# behind. Text alone does not count — a chart that renders its title and
# no bars is the exact defect this is looking for.
IN_SECTIONS = """() => {
  const out = [];
  document.querySelectorAll('main section').forEach((s) => {
    const id = s.id || '';
    if (!id.startsWith('x-')) return;
    const painted = s.querySelectorAll(
      'svg rect, svg path, svg circle, svg line, svg polygon, svg polyline, svg image,' +
      ' canvas, img, .bar-track, .kpi, .step-card, .compare-card,' +
      // A closed <details> paints its summary and nothing else — that IS
      // its rendered state, so the box counts rather than its contents.
      // A copy region's figure IS its two boxes. Without the box in
      // this list the only thing matching is the clipboard glyph on
      // its buttons, and a 12px icon reads as a degenerate figure.
      ' .okt-tl-item, aside.insight, details.info-tip, .okt-copy-region,'  +
      ' td, th, pre code, .okt-diag-node'
    );
    let widest = 0;
    painted.forEach((el) => {
      const b = el.getBoundingClientRect();
      if (b.width * b.height > widest) widest = b.width * b.height;
    });
    const box = s.getBoundingClientRect();
    out.push({ id: id.slice(2), marks: painted.length, area: Math.round(widest),
               height: Math.round(box.height) });
  });
  return out;
}"""


def _render(page, url: str, group: str) -> dict:
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{url}/{group}.html")
    page.wait_for_selector("main section")
    # Wait on the work, not the clock: charts render synchronously off
    # `oku:rendered`, diagrams wait on a CDN fetch for mermaid.
    page.wait_for_function(
        "() => { const d = document.querySelectorAll('oku-diagram');"
        "        return [...d].every((x) => x._rendered || /Parse error/.test(x.textContent)); }",
        timeout=45000,
    )
    # The kit marks images `loading="lazy"`, so one below the fold has
    # never been fetched and measures 0x0 — indistinguishable from the
    # figure-that-drew-nothing this test is looking for. Scrolling each
    # section into view is the obvious fix and an unreliable one: the
    # fetch is not guaranteed to have started by the time the next scroll
    # moves on. Flipping the attribute starts the load synchronously.
    page.evaluate(
        "() => document.querySelectorAll('img[loading=\"lazy\"]').forEach((i) => { i.loading = 'eager'; })"
    )
    page.wait_for_function(
        "() => [...document.images].every((i) => i.complete && i.naturalWidth > 0)",
        timeout=15000,
    )
    return {row["id"]: row for row in page.evaluate(IN_SECTIONS)}


@pytest.fixture(scope="module")
def page_module(browser):
    """One page for all 68 cases: the plugin's `page` is function-scoped,
    and opening a browser per case would dominate the suite's runtime for
    no extra coverage.

    It takes the plugin's session-scoped `browser` rather than starting
    its own. Calling `sync_playwright()` here instead passed in isolation
    and errored all 68 cases inside the full suite, because by then the
    plugin holds a live sync instance on this thread and a second one
    cannot be nested — a failure that only appears once some other test
    has already used a browser.
    """
    pg = browser.new_page()
    yield pg
    pg.close()


@pytest.fixture(scope="module")
def block_ink(page_module, examples_url):
    return _render(page_module, examples_url, "blocks")


@pytest.fixture(scope="module")
def chart_ink(page_module, examples_url):
    return _render(page_module, examples_url, "charts")


@pytest.mark.parametrize("name", GROUPS["blocks"])
def test_every_block_example_paints(name: str, block_ink) -> None:
    row = block_ink.get(name)
    assert row, f"{name} produced no section at all: {sorted(block_ink)}"
    assert row["marks"] > 0, f"`oku spec {name}` renders an empty box: {row}"
    assert row["area"] > 100, f"`oku spec {name}` paints a degenerate figure: {row}"


@pytest.mark.parametrize("name", GROUPS["charts"])
def test_every_chart_example_paints(name: str, chart_ink) -> None:
    row = chart_ink.get(name)
    assert row, f"{name} produced no section at all"
    assert row["marks"] > 0, f"`oku spec {name}` renders an empty chart: {row}"
    assert row["area"] > 100, f"`oku spec {name}` paints a degenerate chart: {row}"
