"""Regression tests for the image / svg / collapsible-info-tip / danger
callout kit features.

- `image` and `svg` are typed blocks: the schema accepts them and the
  v1→v2 shim converts the legacy `{kind: …}` shape into `{k: …}`.
- A v1 `callout` with `type: danger` must survive the shim as a
  `[!DANGER]` admonition string so the renderer's ADM_CLASS can colour
  it red (it previously fell back to neutral 'note').
- A v1 `info-tip` still converts on the CLI side (the collapsible
  `<details>` rendering is a renderer.js concern, verified in the
  browser suite).

The render-side behaviour (danger = red, info-tip = <details>, image /
svg = <figure>) is pinned in src/oku_tests/browser/test_new_blocks.py.
"""

from __future__ import annotations

import pytest

jsonschema = pytest.importorskip("jsonschema")

from oku.cli import _v1_to_v2, _v1_to_v2_block  # noqa: E402

TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_schema_accepts_image_and_svg(page_schema: dict) -> None:
    page = {
        "k": "page",
        "t": "Görsel testi",
        "b": [
            {"k": "image", "src": TINY_PNG, "alt": "tek piksel", "caption": "alt yazı", "width": 320},
            {"k": "svg", "src": "<svg viewBox='0 0 10 10'></svg>", "caption": "çizim", "label": "şema"},
        ],
    }
    jsonschema.validate(page, page_schema)


def test_schema_rejects_image_without_src(page_schema: dict) -> None:
    page = {"k": "page", "t": "T", "b": [{"k": "image", "alt": "yok"}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(page, page_schema)


def test_v1_image_converts_to_typed() -> None:
    out = _v1_to_v2_block({"kind": "image", "src": TINY_PNG, "alt": "a", "caption": "c", "width": 200})
    assert out == {"k": "image", "src": TINY_PNG, "alt": "a", "caption": "c", "width": 200}


def test_v1_svg_converts_to_typed() -> None:
    out = _v1_to_v2_block({"kind": "svg", "source": "<svg></svg>", "caption": "c", "label": "l"})
    assert out == {"k": "svg", "src": "<svg></svg>", "caption": "c", "label": "l"}


def test_v1_danger_callout_survives_as_admonition() -> None:
    out = _v1_to_v2_block({"kind": "callout", "type": "danger", "title": "Dikkat", "content": "metin"})
    assert isinstance(out, str)
    assert out.startswith("> [!DANGER] Dikkat")


def test_v1_page_with_new_blocks_validates(page_schema: dict) -> None:
    """A whole v1 page mixing image / svg / info-tip / danger callout
    shims to v2 and still validates."""
    v1 = {
        "kind": "page",
        "title": "Karışık",
        "blocks": [
            {
                "kind": "section",
                "id": "s1",
                "title": "Bölüm",
                "blocks": [
                    {"kind": "image", "src": TINY_PNG, "alt": "a"},
                    {"kind": "svg", "source": "<svg viewBox='0 0 4 4'></svg>", "label": "şema"},
                    {"kind": "callout", "type": "danger", "title": "Kritik", "content": "uyarı"},
                    {
                        "kind": "info-tip",
                        "summary": "Kendini sına",
                        "content": [{"kind": "paragraph", "content": "cevap"}],
                    },
                ],
            }
        ],
    }
    v2 = _v1_to_v2(v1)
    jsonschema.validate(v2, page_schema)
