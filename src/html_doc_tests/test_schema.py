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
    "cli.json",
    "glossary.json",
    "index.json",
    "reference.json",
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
    """src/html_doc/templates/starter.json — emitted to fresh projects
    via `html-doc init`. A starter that doesn't pass schema would
    mislead every new author."""
    data = json.loads(
        (repo_root / "src" / "html_doc" / "templates" / "starter.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(data, page_schema)


def test_table_chip_columns_validate(page_schema: dict) -> None:
    """Object-form table headers and cells (chip filters, multi-valued
    cells) are accepted by the schema. Locked here so a future schema
    refactor that drops the alternatives is caught immediately."""
    page = {
        "kind": "page",
        "title": "Chip table",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "table",
                        "headers": [
                            "Engine",
                            {
                                "label": "Tags",
                                "filter": "chips",
                                "values": ["a", "b"],
                            },
                        ],
                        "rows": [
                            ["Iceberg", {"value": "a, b", "values": ["a", "b"]}],
                            ["Hudi", {"values": ["a"]}],
                        ],
                    }
                ],
            }
        ],
    }
    jsonschema.validate(page, page_schema)


def test_table_chip_header_requires_values(page_schema: dict) -> None:
    """A chip header without a values list is rejected — every chip
    column must declare its enumeration up front."""
    page = {
        "kind": "page",
        "title": "X",
        "blocks": [
            {
                "kind": "section",
                "id": "s",
                "title": "S",
                "blocks": [
                    {
                        "kind": "table",
                        "headers": [
                            {"label": "Tags", "filter": "chips"},
                        ],
                        "rows": [["x"]],
                    }
                ],
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(page, page_schema)
