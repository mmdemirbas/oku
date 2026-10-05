"""Every custom element goes through `__okuDefine`, which queues it to the
foot of chrome.js. A direct `customElements.define` mid-file upgrades the
already-parsed elements of a served page before the state below it is
initialised — see browser/test_chrome_only_page.py for what that broke."""

from __future__ import annotations

import re
from pathlib import Path

CHROME = Path(__file__).resolve().parents[2] / "kit" / "chrome.js"


def test_no_element_is_defined_outside_the_queue() -> None:
    src = CHROME.read_text(encoding="utf-8")
    direct = [m.start() for m in re.finditer(r"customElements\.define\(", src)]
    # Two legitimate sites: the helper (after the queue has flushed) and
    # the flush itself at the foot of the file.
    assert len(direct) == 2, f"{len(direct)} direct customElements.define calls; use __okuDefine"
    # The flush comes after the last class is queued.
    assert src.rfind("customElements.define(") > src.rfind("__okuDefine('"), (
        "the flush must follow every queued define"
    )
