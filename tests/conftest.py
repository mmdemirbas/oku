"""Shared fixtures.

The src/html_doc/ package layout is picked up via pythonpath in
pyproject.toml ([tool.pytest.ini_options]). No sys.path mangling needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Path to the html-doc repo root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def page_schema() -> dict:
    """Loaded schema/page.schema.json — every docs/*.json must validate."""
    return json.loads((REPO_ROOT / "schema" / "page.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_page() -> dict:
    """A minimal valid JSON page exercising every block kind the tests care about.

    Used by the markdown-twin tests so the asserted output stays compact and
    readable. Real docs/*.json are tested separately in test_schema.
    """
    return {
        "kind": "page",
        "title": "Sample page",
        "meta": {
            "subtitle": "A page for tests",
            "date": "2026-05-19",
            "updated": "2026-05-19",
            "audience": "internal",
            "read_time": "~2 min",
        },
        "blocks": [
            {
                "kind": "section",
                "id": "intro",
                "title": "Intro",
                "blocks": [
                    {"kind": "paragraph", "content": "Hello world."},
                    {
                        "kind": "callout",
                        "type": "note",
                        "title": "Heads up",
                        "content": "Note body.",
                    },
                    {
                        "kind": "list",
                        "items": ["one", "two", "three"],
                    },
                    {
                        "kind": "code",
                        "language": "python",
                        "source": "print('hi')",
                    },
                    {
                        "kind": "annotated-code",
                        "language": "javascript",
                        "source": "const x = 1; // (1)",
                        "annotations": [{"id": 1, "content": "Constant binding."}],
                    },
                    {
                        "kind": "table",
                        "headers": ["Name", "Value"],
                        "rows": [["alpha", "1"], ["beta", "2"]],
                    },
                ],
            },
        ],
    }
