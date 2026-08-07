"""Both published builds can reach the .md files their pages link to.

The markdown viewer renders a linked .md in place of the browser's
plain-text rendering, and it has two supply lines.

Over HTTP it fetches the file — so `build_site` copies each .md source
next to its .html. Without that, a published site is the one place the
viewer cannot read its own tree, while `oku serve` and the standalone
build both can.

Over file:// it cannot fetch at all: the origin is opaque, so a page
cannot read the file sitting next to it, and a standalone HTML is
exactly the artifact people open over file://. So `build_standalone`
inlines what the viewer will be asked for.

The inline keys are hrefs AS AUTHORED, because that is what the viewer
looks up (`a.getAttribute('href')`). Anything else would need both
sides to normalise a path the same way forever.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from oku import cli

LOCAL_DOCS_RE = re.compile(r'id="__oku_local_docs__">(.*?)</script>', re.S)


def _page(body: str) -> dict:
    return {"k": "page", "t": "Host", "m": {"summary": "s"}, "b": [body]}


def _local_docs(html: str) -> dict:
    """The inlined map, read the way a browser reads it: the block ends at
    the first real `</script>`, and `<\\/script>` is not one — so unescape
    AFTER slicing the block out, never before."""
    m = LOCAL_DOCS_RE.search(html)
    return json.loads(m.group(1).replace("<\\/script", "</script")) if m else {}


class TestCollectLocalDocs:
    def test_an_island_href_is_carried(self, tmp_path: Path) -> None:
        """The shape the reader actually hits. A link written inside an
        HTML island never passes through renderLink, so it reaches the
        DOM still saying `.md` — and opens the viewer."""
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "plan.md").write_text("# Plan\n\nBody.\n", encoding="utf-8")
        page = _page('<p><a href="notes/plan.md">plan</a></p>')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {"notes/plan.md": "# Plan\n\nBody.\n"}, docs
        assert skipped == []

    def test_a_root_absolute_markdown_link_is_carried(self, tmp_path: Path) -> None:
        """The other shape renderLink leaves alone: `](/x.md)` is not a
        relative href, so it is not rewritten to `.html`."""
        (tmp_path / "readme.md").write_text("# R\n", encoding="utf-8")
        page = _page("See [the readme](/readme.md) for context.\n")

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {"/readme.md": "# R\n"}, docs
        assert skipped == []

    def test_a_relative_prose_link_is_not_carried(self, tmp_path: Path) -> None:
        """renderLink rewrites `[x](notes/plan.md)` to `notes/plan.html`
        because that file is a page in this tree, and the whole page beats
        a file viewer. The viewer is never asked for it, so inlining it
        would be bytes in a mailed artifact that nothing can reach.

        This is the one rule the two sides have to agree on. If renderLink
        ever stops rewriting, this test is what fails."""
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "plan.md").write_text("# Plan\n", encoding="utf-8")
        page = _page("See [the plan](notes/plan.md).\n")

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {}, docs
        assert skipped == []

    def test_a_fragment_is_not_part_of_the_file(self, tmp_path: Path) -> None:
        """`plan.md#risks` names a heading inside the file. The key is the
        file; the viewer strips the fragment before looking up and scrolls
        to it after rendering."""
        (tmp_path / "plan.md").write_text("## Risks {#risks}\n", encoding="utf-8")
        page = _page('<p><a href="plan.md#risks">risks</a></p>')

        docs, _ = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert list(docs) == ["plan.md"], docs

    def test_a_link_inside_a_typed_block_is_found(self, tmp_path: Path) -> None:
        """Prose lives in typed blocks too — an insight body, a table
        cell, a callout. Walking only the top-level b[] strings would miss
        every one of them."""
        (tmp_path / "plan.md").write_text("# P\n", encoding="utf-8")
        page = {
            "k": "page",
            "t": "Host",
            "b": [{"k": "insight", "b": "Read [the plan](/plan.md) first."}],
        }

        docs, _ = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert list(docs) == ["/plan.md"], docs

    def test_a_file_outside_the_tree_is_reported_not_shipped(self, tmp_path: Path) -> None:
        """Escaping the tree is how a build ends up embedding something
        the author never meant to publish."""
        root = tmp_path / "docs"
        root.mkdir()
        (tmp_path / "secret.md").write_text("# Secret\n", encoding="utf-8")
        page = _page('<p><a href="../secret.md">x</a></p>')

        docs, skipped = cli.collect_local_docs(page, root / "index.html", root)

        assert docs == {}
        assert skipped == ["../secret.md"]

    def test_a_missing_file_is_reported_not_silent(self, tmp_path: Path) -> None:
        """A standalone that quietly cannot open one of its own links is
        the kind of gap that gets reported as a kit bug."""
        page = _page('<p><a href="gone.md">x</a></p>')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {}
        assert skipped == ["gone.md"]

    def test_an_oversize_file_is_reported_not_shipped(self, tmp_path: Path) -> None:
        """The artifact is meant to be sent as a file."""
        big = tmp_path / "big.md"
        big.write_text("x" * (cli.MAX_INLINE_DOC_BYTES + 1), encoding="utf-8")
        page = _page('<p><a href="big.md">x</a></p>')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {}
        assert skipped == ["big.md"]

    def test_an_href_inside_backticks_is_a_quotation_not_a_link(self, tmp_path: Path) -> None:
        """Documenting the viewer made the build warn about the examples
        that explain it: a table cell reading `<a href="notes/plan.md">`
        was collected as a link to a file nobody had written. The
        renderer never turns a code span into an anchor, so the build
        has nothing to inline for one."""
        page = _page('Write `<a href="notes/plan.md">` in an island, or `[plan](/notes/plan.md)` in prose.\n')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {}
        assert skipped == []

    def test_an_href_inside_a_fenced_sample_is_not_collected(self, tmp_path: Path) -> None:
        page = _page('Example:\n\n```html\n<a href="/notes/plan.md">plan</a>\n```\n')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {}
        assert skipped == []

    def test_a_real_link_beside_a_quoted_one_is_still_collected(self, tmp_path: Path) -> None:
        """Stripping code must not swallow the prose around it."""
        (tmp_path / "plan.md").write_text("# P\n", encoding="utf-8")
        page = _page('Shown as `<a href="other.md">`, and live here: <a href="plan.md">plan</a>\n')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert list(docs) == ["plan.md"], docs
        assert skipped == []

    def test_a_remote_url_is_left_alone(self, tmp_path: Path) -> None:
        page = _page('<p><a href="https://example.com/README.md">x</a></p>')

        docs, skipped = cli.collect_local_docs(page, tmp_path / "index.html", tmp_path)

        assert docs == {}
        assert skipped == []


class TestStandaloneCarriesThem:
    def test_the_built_html_inlines_the_linked_file(self, tmp_path: Path) -> None:
        root = tmp_path / "docs"
        (root / "notes").mkdir(parents=True)
        (root / "notes" / "plan.md").write_text("# Plan\n\nBody.\n", encoding="utf-8")
        page = _page('<p><a href="notes/plan.md">plan</a></p>')
        html = cli._stub_for("Host")
        out = tmp_path / "out"

        cli.build_standalone([(root / "index.html", html, page)], out, root)

        built = (out / "index.html").read_text(encoding="utf-8")
        assert _local_docs(built) == {"notes/plan.md": "# Plan\n\nBody.\n"}

    def test_a_page_linking_no_markdown_carries_no_map(self, tmp_path: Path) -> None:
        """Most pages link to no .md at all and must not pay for it."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        page = _page("Just prose.\n")

        cli.build_standalone([(root / "index.html", cli._stub_for("Host"), page)], tmp_path / "out", root)

        built = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        assert 'id="__oku_local_docs__"' not in built

    def test_a_closing_script_tag_in_the_file_cannot_end_the_block(self, tmp_path: Path) -> None:
        """The inlined file is author text inside a <script> element. A
        markdown file that documents a <script> tag would otherwise close
        the block early and dump the rest of itself into the document —
        the same escape the page JSON and the kit bundle already carry."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        (root / "html.md").write_text("Write `</script>` to close it.\n", encoding="utf-8")
        page = _page('<p><a href="html.md">x</a></p>')

        cli.build_standalone([(root / "index.html", cli._stub_for("H"), page)], tmp_path / "out", root)

        built = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        assert "<\\/script>" in built, "the closing tag was inlined unescaped"
        assert _local_docs(built) == {"html.md": "Write `</script>` to close it.\n"}


class TestSiteCarriesTheSource:
    def test_the_site_build_copies_the_md_next_to_the_html(self, tmp_path: Path) -> None:
        """The viewer fetches over HTTP, so the file has to be there. A
        site that ships only .html is a site where every markdown link
        opens the viewer's failure card."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        (root / "index.md").write_text(
            "---\ntitle: Home\nsummary: s\n---\n\n## S {#s}\n\nBody.\n", encoding="utf-8"
        )
        page = _page("Body.\n")
        out = tmp_path / "site"

        cli.build_site([(root / "index.html", cli._stub_for("Home"), page)], out, root)

        assert (out / "index.md").exists(), sorted(p.name for p in out.iterdir())
        assert (out / "index.md").read_text(encoding="utf-8") == (root / "index.md").read_text(
            encoding="utf-8"
        )

    def test_a_page_with_no_md_source_is_not_invented(self, tmp_path: Path) -> None:
        """A hand-authored .html + .json page has no markdown source, and
        the build must not conjure one."""
        root = tmp_path / "docs"
        root.mkdir(parents=True)
        out = tmp_path / "site"

        cli.build_site([(root / "page.html", cli._stub_for("P"), _page("Body.\n"))], out, root)

        assert not (out / "page.md").exists()

    def test_the_copy_keeps_the_directory_structure(self, tmp_path: Path) -> None:
        """A nested page's source has to land beside its own .html, not
        at the site root, or the relative href the viewer resolves goes
        somewhere else."""
        root = tmp_path / "docs"
        (root / "guides").mkdir(parents=True)
        (root / "guides" / "intro.md").write_text(
            "---\ntitle: Intro\nsummary: s\n---\n\n## S {#s}\n\nB.\n", encoding="utf-8"
        )
        out = tmp_path / "site"

        cli.build_site([(root / "guides" / "intro.html", cli._stub_for("Intro"), _page("B.\n"))], out, root)

        assert (out / "guides" / "intro.md").exists()
