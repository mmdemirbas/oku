"""`oku serve` re-reads the tree's configuration when the tree changes.

The page dict is synthesized per request, but what it is built FROM —
the nearest kit.json, the project root, the skip list, git's dates —
was cached for the life of the process and nothing cleared it. Measured
in one process, which is how serve runs: kit.json's accent changed from
teal to rose, the watcher broadcast a reload, and the next page still
came back teal. The same held for `lang`, `audience`, `skip_dirs` and the
project fence, so the preview stopped agreeing with the build it
previews until the server was restarted.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from oku import cli


def test_a_kit_json_edit_reaches_the_next_page_served(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "kit.json").write_text('{"name":"p","accent":"teal"}', encoding="utf-8")
    page = tmp_path / "p.md"
    page.write_text("---\ntitle: P\n---\n\n## A {#a}\n\nx\n", encoding="utf-8")
    assert cli._page_from_source_file(page)["m"]["accent"] == "teal"

    reloaded = threading.Event()
    monkeypatch.setattr(cli, "_sse_broadcast", lambda _msg: reloaded.set())
    stop = threading.Event()
    watcher = threading.Thread(target=cli._watcher_loop, args=(tmp_path, stop), daemon=True)
    watcher.start()
    try:
        time.sleep(0.6)  # the watcher takes its first snapshot
        (tmp_path / "kit.json").write_text('{"name":"p","accent":"rose"}', encoding="utf-8")
        assert reloaded.wait(10), "the watcher never noticed kit.json change"
    finally:
        stop.set()
        watcher.join(5)

    assert cli._page_from_source_file(page)["m"]["accent"] == "rose"
