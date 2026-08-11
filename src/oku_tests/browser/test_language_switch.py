"""The language button has to find the current page in the manifest.

Manifest paths are relative to the root the manifest was BUILT from, and
that root is not the same thing in every mode:

    oku serve      reference.html        (docs root is the tree root)
    dist/site      docs/reference.html   (built from the repo root)
    standalone     docs/reference.html   (inlined, same root)

while `location.pathname` is `/docs/reference.html` in the first two and
an absolute filesystem path in the third. Comparing the manifest path to
a bare filename matched under `oku serve` and nowhere else, so the button
appeared in development and was missing from both things a reader
receives. These pin the match itself, in both path shapes.
"""

from __future__ import annotations

import pytest

# Drive the switch with a manifest of each shape, against the real page
# at /docs/reference.html. Faster and far more direct than building two
# dist trees, and it targets the exact thing that broke.
BUILD = """(manifest) => {
  const old = document.querySelector('.ctrl-btn.lang-toggle');
  if (old) old.remove();
  __okuLangSwitch.build(manifest);
  const b = document.querySelector('.ctrl-btn.lang-toggle');
  return b ? { code: b.textContent.trim(), label: b.getAttribute('aria-label') } : null;
}"""


def _manifest(prefix):
    def path(name):
        return f"{prefix}{name}"

    return {
        "pages": [
            {
                "path": path("reference.html"),
                "title": "Reference",
                "lang": "en",
                "variants": {"en": path("reference.html"), "tr": path("reference.tr.html")},
            },
            {"path": path("charts.html"), "title": "Charts", "lang": "en"},
        ]
    }


@pytest.mark.parametrize(
    "prefix,shape",
    [("", "bare, as oku serve builds it"), ("docs/", "prefixed, as dist/site builds it")],
)
def test_the_button_finds_the_page_whatever_root_the_manifest_used(page, site_url, prefix, shape):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/reference.html")
    page.wait_for_selector("main section")
    # The first section is not the walk finishing, and this test writes
    # `location.hash` — which a still-settling page overwrites, losing the
    # reader position the switch is supposed to carry across.
    page.wait_for_function("() => window.__okuRendered === true", timeout=15000)

    got = page.evaluate(BUILD, _manifest(prefix))

    assert got is not None, f"no button for a {shape} manifest"
    assert got["code"] == "EN", got
    assert "TR" in got["label"], got


@pytest.mark.parametrize("prefix", ["", "docs/"])
def test_the_target_is_built_from_the_matched_prefix(page, site_url, prefix):
    """Navigating to the variant path verbatim would give
    /docs/docs/reference.tr.html for a prefixed manifest. The prefix
    comes from the suffix match, so the target is right either way."""
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/reference.html")
    page.wait_for_selector("main section")
    # The first section is not the walk finishing, and this test writes
    # `location.hash` — which a still-settling page overwrites, losing the
    # reader position the switch is supposed to carry across.
    page.wait_for_function("() => window.__okuRendered === true", timeout=15000)
    page.evaluate("() => { location.hash = '#prose'; }")
    # Setting the hash starts an ASYNCHRONOUS scroll to the anchor, and the
    # scroll spy clears the hash entirely while `scrollY < 80` — at the top
    # of the page no section is current, which is deliberate. Clicking
    # before the scroll lands therefore tests a page whose fragment the kit
    # has already dropped, and the switch is blamed for losing it.
    page.wait_for_function("() => window.scrollY >= 80 && location.hash === '#prose'", timeout=10000)

    page.evaluate(BUILD, _manifest(prefix))
    page.click(".ctrl-btn.lang-toggle")
    page.wait_for_load_state()

    from urllib.parse import urlparse

    parsed = urlparse(page.url)
    assert parsed.path == "/docs/reference.tr.html", page.url
    assert parsed.fragment == "prose", page.url


def test_a_page_with_no_counterpart_gets_no_button(page, site_url):
    """The switch is a property of the page: no counterpart, no button,
    no disabled state to explain."""
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{site_url}/docs/reference.html")
    page.wait_for_selector("main section")
    # The first section is not the walk finishing, and this test writes
    # `location.hash` — which a still-settling page overwrites, losing the
    # reader position the switch is supposed to carry across.
    page.wait_for_function("() => window.__okuRendered === true", timeout=15000)

    got = page.evaluate(
        BUILD,
        {"pages": [{"path": "docs/reference.html", "title": "Reference", "lang": "en"}]},
    )

    assert got is None, got
