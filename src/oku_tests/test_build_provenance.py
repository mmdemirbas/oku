"""What the build writes down about itself.

The browser half of this lives in `browser/test_build_provenance.py` —
whether the facts reach a reader. This half is the two decisions made
in Python: what the manifest carries, and which artifacts are allowed
to carry it.

The second one is the sharp edge. The rebuild command holds a path on
the author's machine, and one of the manifest's consumers is a SOURCE
file that gets committed.
"""

from __future__ import annotations

import json
from pathlib import Path

from oku import cli


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "kit.json").write_text(json.dumps({"name": "t"}), encoding="utf-8")
    (tmp_path / "p.md").write_text(
        "---\ntitle: P\nsummary: S.\n---\n\n## A {#a}\n\nBody.\n", encoding="utf-8"
    )
    return tmp_path


def test_the_manifest_carries_the_stamp_and_the_command(tmp_path):
    """The manifest is the carrier because it is the one thing that
    already reaches every page in all three modes — fetched under
    `oku serve` and in dist/site, inlined in a standalone file."""
    manifest = cli.compute_manifest(_tree(tmp_path))
    assert manifest["build"]["kit"] == cli._kit_build_stamp()
    assert manifest["build"]["cmd"].endswith("&& oku build")
    assert str(tmp_path.resolve()) in manifest["build"]["cmd"]


def test_the_init_stub_is_not_given_a_path_from_this_machine(tmp_path):
    """`docs/index.html` is a source file. It gets committed, and it
    gets committed by people whose home directory is not a thing they
    intend to publish. The build metadata belongs in `dist/`, which is
    ignored, and in the standalone files, which are deliberately sent."""
    stub = cli._init_time_manifest(_tree(tmp_path))
    assert "build" not in stub, "the committed stub must not carry a machine path"
    assert "generated_at" not in stub


def test_a_home_relative_command_does_not_name_the_account(tmp_path, monkeypatch):
    """A standalone file is made to be sent to other people. `~` says
    the whole thing to the one reader who can act on it, and says
    nothing about who they are to everyone else."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    inside = tmp_path / "work" / "notes"
    inside.mkdir(parents=True)
    assert cli._rebuild_command(inside) == "cd ~/work/notes && oku build"


def test_a_path_outside_home_stays_absolute(tmp_path, monkeypatch):
    """Nothing to collapse against, and a wrong-but-shorter path is
    worse than a long one: the command has to actually run."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "elsewhere"))
    assert cli._rebuild_command(tmp_path) == f"cd {tmp_path.resolve()} && oku build"


def test_a_directory_with_a_space_is_quoted_without_killing_the_tilde(tmp_path, monkeypatch):
    """`cd '~/my notes'` is a directory literally named `~`. The tilde
    has to stay outside the quotes for the shell to expand it, which is
    the one thing shlex.quote on the whole string would get wrong."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    spaced = tmp_path / "my notes"
    spaced.mkdir()
    assert cli._rebuild_command(spaced) == "cd ~/'my notes' && oku build"


def test_the_outgoing_stamp_is_read_before_it_is_overwritten(tmp_path):
    """`oku build` is the only place both stamps exist at once: the
    artifact cannot learn the installed one without reaching the
    network, and the tool does not know an artifact exists until it is
    asked to replace one. Reading it is what lets the build print the
    version-against-version line a page cannot."""
    dist = tmp_path / "dist"
    assert cli._artifact_kit_stamp(dist) is None, "nothing built yet is not a stamp"

    shared = dist / "site" / "_oku"
    shared.mkdir(parents=True)
    (shared / "chrome.js").write_text("var __okuKitBuild = '2019-01-01-r1';\n", encoding="utf-8")
    assert cli._artifact_kit_stamp(dist) == "2019-01-01-r1"


def test_a_tree_built_without_a_site_still_answers(tmp_path):
    """`dist/site/_oku/chrome.js` settles it in one read when it is
    there. A standalone page is the fallback, and it is 1 MB — which is
    why exactly one of them is opened, not all of them."""
    alone = tmp_path / "dist" / "standalone"
    alone.mkdir(parents=True)
    (alone / "a.html").write_text("<script>var __okuKitBuild = '2020-02-02-r9';</script>", encoding="utf-8")
    assert cli._artifact_kit_stamp(tmp_path / "dist") == "2020-02-02-r9"
