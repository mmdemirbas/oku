"""Metadata the author should not have to write.

The front-matter block used to ask for ten fields before the first
sentence, and this repo's own eleven pages showed most of them being
answered the same way every time. What is derivable is derived, what is
constant across a tree comes from kit.json, and an authored value always
wins.

The load-bearing property is that derivation never leaks back into the
source: `page_to_md` must not write a derived key into front-matter, or
one `oku migrate` would re-introduce every field this removes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from oku import cli


@pytest.fixture(autouse=True)
def _clear_caches():
    cli._tree_defaults_cache.clear()
    cli._git_date_cache.clear()
    yield
    cli._tree_defaults_cache.clear()
    cli._git_date_cache.clear()


def _page(tmp_path: Path, front: str, body: str = "Prose.\n", *, kit: dict | None = None) -> dict:
    if kit is not None:
        (tmp_path / "kit.json").write_text(json.dumps(kit), encoding="utf-8")
    src = tmp_path / "page.md"
    src.write_text(f"---\n{front}\n---\n\n## S {{#s}}\n\n{body}", encoding="utf-8")
    page = cli._page_from_source_file(src)
    assert page is not None
    return page


# ---------- tree defaults ----------


class TestTreeDefaults:
    def test_accent_and_audience_come_from_kit_json(self, tmp_path):
        page = _page(
            tmp_path, "title: T\nsummary: S", kit={"name": "x", "accent": "teal", "audience": "Author"}
        )
        assert page["m"]["accent"] == "teal"
        assert page["m"]["audience"] == "Author"
        assert set(page["m"]["_derived"]) >= {"accent", "audience"}

    def test_an_authored_value_wins(self, tmp_path):
        page = _page(tmp_path, "title: T\naccent: amber", kit={"name": "x", "accent": "teal"})
        assert page["m"]["accent"] == "amber"
        assert "accent" not in page["m"].get("_derived", [])

    def test_no_kit_json_means_no_defaults(self, tmp_path):
        page = _page(tmp_path, "title: T\nsummary: S")
        assert "accent" not in page["m"]
        assert "audience" not in page["m"]

    def test_kit_json_is_found_from_a_nested_page(self, tmp_path):
        (tmp_path / "kit.json").write_text(json.dumps({"name": "x", "accent": "rose"}), encoding="utf-8")
        nested = tmp_path / "guides" / "deep"
        nested.mkdir(parents=True)
        src = nested / "page.md"
        src.write_text("---\ntitle: T\n---\n\n## S {#s}\n\nText.\n", encoding="utf-8")
        page = cli._page_from_source_file(src)
        assert page["m"]["accent"] == "rose"

    def test_unparseable_kit_json_does_not_break_the_page(self, tmp_path):
        (tmp_path / "kit.json").write_text("{ not json", encoding="utf-8")
        page = _page(tmp_path, "title: T")
        assert page["t"] == "T"
        assert "accent" not in page.get("m", {})


# ---------- read time ----------


class TestReadTime:
    def test_a_short_page_gets_no_estimate(self, tmp_path):
        page = _page(tmp_path, "title: T", "Three words here.\n")
        assert "read_time" not in page.get("m", {})

    def test_a_long_page_gets_one(self, tmp_path):
        body = ("word " * 1200) + "\n"
        page = _page(tmp_path, "title: T", body)
        assert page["m"]["read_time"] == "~5 min read", page["m"]
        assert "read_time" in page["m"]["_derived"]

    def test_an_authored_estimate_wins(self, tmp_path):
        body = ("word " * 1200) + "\n"
        page = _page(tmp_path, "title: T\nread_time: ~99 min read", body)
        assert page["m"]["read_time"] == "~99 min read"
        assert "read_time" not in page["m"].get("_derived", [])

    def test_the_estimate_tracks_the_body(self, tmp_path):
        short = _page(tmp_path, "title: T", ("word " * 500) + "\n")["m"]["read_time"]
        long = _page(tmp_path, "title: T", ("word " * 2000) + "\n")["m"]["read_time"]
        assert short != long, (short, long)


# ---------- updated ----------


class TestUpdated:
    def test_untracked_files_get_no_date(self, tmp_path):
        """Better nothing than a wrong date."""
        page = _page(tmp_path, "title: T")
        assert "updated" not in page.get("m", {})

    def test_the_commit_date_is_used_not_the_mtime(self, tmp_path):
        """A fresh clone stamps every file with the checkout time, which
        would render a whole tree as updated today."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
        src = tmp_path / "page.md"
        src.write_text("---\ntitle: T\n---\n\n## S {#s}\n\nText.\n", encoding="utf-8")
        subprocess.run(["git", "add", "page.md"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "add", "--date", "2020-03-04T00:00:00"],
            cwd=tmp_path,
            check=True,
            env={"GIT_COMMITTER_DATE": "2020-03-04T00:00:00", "PATH": "/usr/bin:/bin"},
        )
        page = cli._page_from_source_file(src)
        assert page["m"]["updated"] == "2020-03-04", page["m"]
        assert "updated" in page["m"]["_derived"]

    def test_an_authored_date_wins(self, tmp_path):
        page = _page(tmp_path, "title: T\nupdated: 2019-01-01")
        assert page["m"]["updated"] == "2019-01-01"
        assert "updated" not in page["m"].get("_derived", [])


# ---------- the round-trip guard ----------


class TestDerivedValuesNeverReachTheSource:
    def test_page_to_md_omits_derived_keys(self, tmp_path):
        page = _page(
            tmp_path,
            "title: T\nsummary: S",
            ("word " * 1200) + "\n",
            kit={"name": "x", "accent": "teal", "audience": "Author"},
        )
        assert set(page["m"]["_derived"]) >= {"accent", "audience", "read_time"}
        md = cli.page_to_md(page)
        front = md.split("---")[1]
        for key in ("accent:", "audience:", "read_time:", "_derived:"):
            assert key not in front, f"{key} leaked into the source front-matter:\n{front}"
        assert "title: T" in front and "summary: S" in front

    def test_a_migrate_round_trip_does_not_grow_the_front_matter(self, tmp_path):
        page = _page(tmp_path, "title: T\nsummary: S", kit={"name": "x", "accent": "teal"})
        once = cli.page_to_md(page)
        twice = cli.page_to_md(cli.md_to_v2_page(once))
        assert once == twice


# ---------- the starter ----------


class TestStarterAsksForLess:
    def test_the_starter_front_matter_is_title_and_summary(self):
        text = cli._kit_starter_md()
        assert text is not None
        front = text.split("---")[1]
        keys = {ln.split(":")[0].strip() for ln in front.strip().splitlines() if ":" in ln}
        assert keys == {"title", "summary"}, keys


class TestTheReposOwnPagesUseTheDefaults:
    """The proof the defaults cover the real cases: the docs tree no
    longer repeats what kit.json and the build already know."""

    def test_no_page_repeats_the_tree_accent_or_audience(self):
        root = Path(__file__).resolve().parents[2] / "docs"
        kit = json.loads((root / "kit.json").read_text(encoding="utf-8"))
        offenders = []
        for f in sorted(root.glob("*.md")):
            _, front = cli._strip_md_front_matter(f.read_text(encoding="utf-8"))
            for key in ("accent", "audience"):
                if front.get(key) == kit.get(key):
                    offenders.append(f"{f.name}:{key}")
        assert offenders == [], offenders

    def test_no_page_hand_counts_its_reading_time(self):
        root = Path(__file__).resolve().parents[2] / "docs"
        offenders = [
            f.name
            for f in sorted(root.glob("*.md"))
            if "read_time" in cli._strip_md_front_matter(f.read_text(encoding="utf-8"))[1]
        ]
        assert offenders == [], offenders

    def test_no_page_carries_a_subtitle_identical_to_its_summary(self):
        root = Path(__file__).resolve().parents[2] / "docs"
        offenders = []
        for f in sorted(root.glob("*.md")):
            _, front = cli._strip_md_front_matter(f.read_text(encoding="utf-8"))
            sub, summ = front.get("subtitle"), front.get("summary")
            if sub and summ and str(sub).strip() == str(summ).strip():
                offenders.append(f.name)
        assert offenders == [], offenders
