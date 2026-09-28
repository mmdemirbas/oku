"""The shipped examples, and the long-token variant of them.

`kit/schema/examples.json` is the one place that holds a payload for
every primitive the kit draws, which is why several suites derive their
pages from it rather than listing cases: a chart type added tomorrow is
covered on the day it lands.

The lengthened variant lives here too, because more than one reader
needs it and two copies of "which keys are enums" is a list that stops
matching the schema on the second edit. `test_narrow_no_sideways_scroll`
uses it to ask whether a long word widens the page; `tools/
text_fit_audit.py` uses it to ask whether a long label can still be
read.
"""

from __future__ import annotations

import json
from pathlib import Path

KIT = Path(__file__).resolve().parents[2] / "kit"

# One unbreakable run, in the shape author text actually holds: a class
# name, a config key, a path. Long enough to overflow any column.
LONG = "BatchDataScanGroupReaderDeduplicateMergeFunctionFactory"

# A label a reader would really write: ordinary words, spaces to break
# at, and longer than the gutter any chart reserves by default. The
# unbreakable token above answers a different question — it asks
# whether the box can shrink; this one asks whether the text can be
# read once it fits.
WORDY = "Kullanıcı oturum açma gecikmesi p99 (ms, bölge başına)"

def _schema_enum_keys() -> set[str]:
    """Every property the page schema pins to a fixed set of values.

    Derived, not listed. The hand list this replaces was missing
    `marks`, `from_color` and `to_color`, so lengthening the shipped
    plot and dumbbell examples produced pages the build refuses — and
    the list could only ever be as current as the last person who
    remembered it. The schema is the authority for what an enum is;
    ask it.
    """
    schema = json.loads((KIT / "schema" / "page.schema.json").read_text(encoding="utf-8"))
    out: set[str] = set()

    def walk(node, key=None):
        if isinstance(node, dict):
            if key and ("enum" in node or "const" in node):
                out.add(key)
            for k, v in (node.get("properties") or {}).items():
                walk(v, k)
            for nested in ("items", "additionalProperties", "contains", "not"):
                if isinstance(node.get(nested), dict):
                    walk(node[nested], key)
            for branch in ("anyOf", "oneOf", "allOf"):
                for v in node.get(branch) or []:
                    walk(v, key)
            for group in ("$defs", "definitions"):
                for v in (node.get(group) or {}).values():
                    walk(v, None)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)

    walk(schema)
    return out


# Keys that are not enums and still must not grow: a path, an id, a
# pre-split list of values, an ordering. Appending to one produces a
# page that is broken rather than long, which measures nothing.
_NOT_TEXT = {"src", "id", "values", "boardOrder", "align", "position", "severity", "mode"}

ENUM_KEYS = _schema_enum_keys() | _NOT_TEXT

FENCE_OF = {
    "chart": "oku-chart",
    "chart-grid": "oku-chart-grid",
    "compare-grid": "oku-compare-grid",
    "copy": "oku-copy",
    "diagram": "oku-diagram",
    "example": "oku-example",
    "info-tip": "oku-info-tip",
    "insight": "oku-insight",
    "kpi-grid": "oku-kpi-grid",
    "live-snippet": "oku-live-snippet",
    "step-flow": "oku-step-flow",
    "table": "oku-table",
    "timeline": "oku-timeline",
    "annotated-code": "oku-annotated-code",
}


def examples() -> dict:
    return json.loads((KIT / "schema" / "examples.json").read_text(encoding="utf-8"))


def longify(obj, token: str = LONG):
    """The token appended to every string the example carries."""
    if isinstance(obj, str):
        return f"{obj} {token}" if obj else obj
    if isinstance(obj, list):
        return [longify(v, token) for v in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ENUM_KEYS else longify(v, token)) for k, v in obj.items()}
    return obj
