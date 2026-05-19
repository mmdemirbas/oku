"""Every published page validates against the page schema.

If this fails, the runtime renderer's strict schema-validation path will
warn at load — and a future authoring round may break in less obvious
ways. Pin the contract here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")


DOC_FILES = [
    "architecture.json",
    "authoring.json",
    "cli.json",
    "glossary.json",
    "index.json",
    "primitives.json",
]


@pytest.mark.parametrize("doc_name", DOC_FILES)
def test_docs_page_validates(doc_name: str, page_schema: dict, repo_root: Path) -> None:
    """Each docs/*.json conforms to schema/page.schema.json.

    The repo's CI / build-time validator runs the same check via the
    optional jsonschema dependency; this test makes it explicit and
    fail-fast when running pytest.
    """
    data = json.loads((repo_root / "docs" / doc_name).read_text(encoding="utf-8"))
    jsonschema.validate(data, page_schema)


def test_starter_template_validates(page_schema: dict, repo_root: Path) -> None:
    """templates/starter.json — emitted to fresh projects via `html-doc init`.
    A starter that doesn't pass schema would mislead every new author."""
    data = json.loads((repo_root / "templates" / "starter.json").read_text(encoding="utf-8"))
    jsonschema.validate(data, page_schema)
