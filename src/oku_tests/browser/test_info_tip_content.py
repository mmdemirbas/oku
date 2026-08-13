"""A disclosure shows what it was given, whatever shape it arrived in.

`_renderInfoTip` ran every content item through `convertV1Block`, which
returns null for anything without a v1 `.kind` key. The markdown pipeline
produces bare strings for prose and `k`-keyed objects for typed blocks —
neither has `.kind` — so every item was discarded by the `continue` and
the reader got a `<details>` holding only its `<summary>`.

Nothing failed. The schema accepts the payload, `oku check --strict`
reports the page clean, and the block-contract guard passes because
`summary` and `content` are both present. `_hasVisibleContent` passes too:
the summary is visible content. The payload `oku spec info-tip` prints is
one of the affected ones, so the kit's own documented example could not
render, and a delivered document (mesh, network-security report, `#faq`)
shipped four empty disclosures.

The old test asserted the box, not the body — `count() == 1`, tag name,
`open === false`, one `<summary>` — and it fed the one input shape that
still worked. This asserts the body, over every shape an author can
produce: v2 strings, v2 typed blocks, and legacy v1 blocks.
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from oku import cli

pytestmark = pytest.mark.browser

KIT = Path(__file__).resolve().parents[3] / "kit"

# One fence per shape, each keyed by the anchor its section carries so a
# failure names the shape rather than an index.
FENCES = {
    "prose": {
        "summary": "Prose only",
        "content": ["A single prose item.", "And a second paragraph."],
    },
    "typed": {
        "summary": "Typed block only",
        "content": [{"k": "code", "src": "echo prose-free", "lang": "bash"}],
    },
    "mixed": {
        "summary": "Prose and a typed block",
        "content": ["Before.", {"k": "code", "src": "echo between", "lang": "bash"}, "After."],
    },
    "markdown": {
        "summary": "Markdown inside the prose",
        "content": ["A list follows:\n\n- first item\n- second item"],
    },
    # Not hand-written: the payload the tool hands the author.
    "shipped": cli._load_examples()["blocks"]["info-tip"],
}

# What must be readable in the expanded body. A shape whose text is
# present but whose element never appeared would pass a text-only check.
EXPECTED = {
    "prose": ("A single prose item.", "p"),
    "typed": ("echo prose-free", "pre"),
    "mixed": ("echo between", "pre"),
    "markdown": ("second item", "li"),
}

V1_PAGE = {
    "kind": "page",
    "title": "Legacy disclosure",
    "blocks": [
        {
            "kind": "section",
            "id": "legacy",
            "title": "Legacy",
            "blocks": [
                {
                    "kind": "info-tip",
                    "summary": "Written before the v2 migration",
                    "content": [
                        {"kind": "paragraph", "content": "the legacy body"},
                        {"kind": "code", "language": "bash", "source": "echo legacy"},
                    ],
                }
            ],
        }
    ],
}


def _md_source() -> str:
    out = ["---", "title: Disclosure bodies", "summary: Every content shape a disclosure accepts.", "---", ""]
    for anchor, payload in FENCES.items():
        out += [
            f"## {anchor} {{#{anchor}}}",
            "",
            "Lead paragraph.",
            "",
            "```oku-info-tip",
            json.dumps(payload),
            "```",
            "",
        ]
    return "\n".join(out)


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    d = tmp_path_factory.mktemp("infotip")
    (d / "_oku").symlink_to(KIT, target_is_directory=True)
    (d / "kit.json").write_text(json.dumps({"name": "probe", "accent": "teal"}), encoding="utf-8")
    (d / "tips.md").write_text(_md_source(), encoding="utf-8")
    (d / "legacy.json").write_text(json.dumps(V1_PAGE), encoding="utf-8")
    manifest = {"schema_version": 1, "root": ".", "pages": []}
    (d / "tips.html").write_text(
        cli._stub_for("Disclosure bodies", inline_manifest=manifest), encoding="utf-8"
    )
    (d / "legacy.html").write_text(
        cli._stub_for("Legacy disclosure", inline_manifest=manifest), encoding="utf-8"
    )
    # The real serve handler, so the markdown page goes through the same
    # md -> page-dict synthesis `oku serve` and `oku build` use.
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cli._make_serve_handler(d))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


# Everything in the disclosure except the summary. A closed <details> has
# zero-height children, so this reads the DOM rather than geometry —
# `open` is forced first so the text is reachable either way.
BODY = """({ sel, tag }) => {
  const det = document.querySelector(sel);
  if (!det) return null;
  det.open = true;
  const kids = [...det.children].filter((el) => el.tagName !== 'SUMMARY');
  return {
    count: kids.length,
    tags: kids.map((el) => el.tagName.toLowerCase()),
    text: kids.map((el) => el.textContent).join(' ').replace(/\\s+/g, ' ').trim(),
    // Nested, not direct-child: a list item sits inside its <ul> and a
    // code block inside the wrapper the kit puts round every <pre>.
    has: tag ? kids.some((el) => el.matches(tag) || el.querySelector(tag)) : true,
  };
}"""


@pytest.fixture(scope="module")
def md_page(browser, served):
    pg = browser.new_page()
    pg.set_viewport_size({"width": 1280, "height": 900})
    pg.goto(f"{served}/tips.html")
    pg.wait_for_function("() => window.__okuRendered === true", timeout=20000)
    yield pg
    pg.close()


@pytest.mark.parametrize("anchor", sorted(EXPECTED))
def test_a_markdown_disclosure_renders_its_body(anchor: str, md_page) -> None:
    needle, tag = EXPECTED[anchor]
    body = md_page.evaluate(BODY, {"sel": f"#{anchor} details.info-tip", "tag": tag})
    assert body, f"no disclosure rendered under #{anchor}"
    assert body["count"] > 0, (
        f"#{anchor}: the disclosure holds nothing but its summary — "
        f"content was dropped between the payload and the DOM"
    )
    assert needle in body["text"], f"#{anchor}: expected {needle!r} in the body, got {body['text']!r}"
    assert body["has"], f"#{anchor}: expected a <{tag}> in the body, got {body['tags']}"


def test_a_legacy_disclosure_still_renders_its_body(page, served) -> None:
    """The shape that always worked, now asserted past the summary. It is
    the reason the defect survived: the only test feeding info-tip fed
    this, and stopped at the box."""
    page.goto(f"{served}/legacy.html")
    page.wait_for_function("() => window.__okuRendered === true", timeout=20000)
    body = page.evaluate(BODY, {"sel": "details.info-tip", "tag": "pre"})
    assert body, "no disclosure rendered on the v1 page"
    assert body["count"] > 0, "a v1 disclosure lost its body"
    assert "the legacy body" in body["text"], body["text"]
    assert "echo legacy" in body["text"], body["text"]


def test_the_shipped_example_renders_its_body(md_page) -> None:
    """The payload `oku spec info-tip` prints, on the page. An author who
    pastes what the tool prints has to get a working block, and this one
    was among those rendering empty.

    `test_spec_examples_render.py` already puts it on a page, and passes:
    it counts `details.info-tip` as a painted mark, which is right for a
    closed disclosure and blind to whether it has anything to open."""
    body = md_page.evaluate(BODY, {"sel": "#shipped details.info-tip", "tag": "pre"})
    assert body, "the shipped example produced no disclosure"
    assert body["count"] > 0, "`oku spec info-tip` prints a payload that renders empty"
    for word in ("lost with no error", "mutate(state)"):
        assert word in body["text"], f"expected {word!r} in the body, got {body['text']!r}"
