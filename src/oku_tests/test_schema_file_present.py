"""A schema the tool cannot read is a broken install, never an empty schema.

`_load_schema` turned a missing or unparseable `page.schema.json` into
`{}`, and an empty schema accepts everything. Measured with a copy of
the installed package minus that one file: a page holding
`{"steps": 5}` and `{"rows": "nope"}` came back `✓ 1 page(s) clean
(schema + structural + content)`, exit 0. The same family as the
missing-jsonschema case CLAUDE.md records: a check reporting success
when it did not run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oku import cli

BAD_PAGE = {"k": "page", "t": "T", "b": [{"k": "step-flow", "steps": 5}]}


@pytest.fixture
def kit_without(tmp_path: Path, monkeypatch):
    def make(missing: str, *, garbage: bool = False) -> None:
        (tmp_path / "schema").mkdir()
        real = cli.KIT_DIR / "schema"
        for f in real.iterdir():
            if f.name != missing:
                (tmp_path / "schema" / f.name).write_bytes(f.read_bytes())
        if garbage:
            (tmp_path / "schema" / missing).write_text("{ not json", encoding="utf-8")
        monkeypatch.setattr(cli, "KIT_DIR", tmp_path)
        monkeypatch.setattr(cli, "_schema_cache", None)
        monkeypatch.setattr(cli, "_validator_cache", None)
        monkeypatch.setattr(cli, "_kit_schema_cache", None)

    return make


@pytest.mark.parametrize("garbage", [False, True], ids=["missing", "unparseable"])
def test_a_page_schema_the_tool_cannot_read_stops_the_check(kit_without, garbage: bool) -> None:
    kit_without("page.schema.json", garbage=garbage)
    with pytest.raises(SystemExit) as exc:
        cli.validate_pages([(Path("p.json"), BAD_PAGE)])
    assert "page.schema.json" in str(exc.value)


@pytest.mark.parametrize("garbage", [False, True], ids=["missing", "unparseable"])
def test_a_kit_schema_the_tool_cannot_read_stops_the_check(kit_without, garbage: bool) -> None:
    kit_without("project-kit.schema.json", garbage=garbage)
    with pytest.raises(SystemExit) as exc:
        cli._known_kit_keys()
    assert "project-kit.schema.json" in str(exc.value)


def test_the_shipped_schemas_still_load() -> None:
    # The control: the refusal must not fire on a healthy install.
    assert cli._load_schema().get("$defs")
    assert cli._known_kit_keys()
