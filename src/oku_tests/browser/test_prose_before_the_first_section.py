"""Prose before the first `##` is prose, in the page and in the viewer.

The reading face, its size and the justify rule are scoped by selector
list, and every list said `main > section > p`. A paragraph written
before the first `##` is a child of `main` itself — a lead under the
cover, or the opening of a README — so it was set in the interface face
at 16px directly above section prose in the reading face at 18px.
Measured on a built page: `Inter 16px` for the intro, `Literata 18px` for
the paragraph under it. In the viewer it was the same, plus the file's
own `# title`, which opened a delivered spec in Inter above a body in
Literata.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from oku import cli

from ._wait import page_quiet

pytestmark = pytest.mark.browser

PAGE = """---
title: Faces
summary: Which face prose gets.
lang: en
---

An opening paragraph before any section, long enough to wrap onto a second line so that its alignment means something at this width.

- an opening list item

## First {#first}

A paragraph inside a section, long enough to wrap onto a second line so that its alignment means something at this width.

- a list item inside a section

See [`spec.md`](#f/../src/spec.md).
"""

SPEC = """# Spec title

An opening paragraph of a viewed file, long enough to wrap onto a second line so that its alignment means something here.

- an opening list item

## First

A paragraph inside a section of a viewed file, long enough to wrap onto a second line so that its alignment means something.
"""

FACE = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const c = getComputedStyle(e);
  return { family: c.fontFamily.split(',')[0].replace(/"/g, ''), size: c.fontSize, align: c.textAlign }; }"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("faces") / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "spec.md").write_text(SPEC, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(PAGE, encoding="utf-8")
    (docs / "kit.json").write_text('{"rebuild_command": false}', encoding="utf-8")
    (docs / "index.html").write_text(cli._stub_for("index"), encoding="utf-8")
    cwd = Path.cwd()
    os.chdir(docs)
    try:
        assert cli.cmd_build(argparse.Namespace(no_search=True, no_vendor=False)) == 0
    finally:
        os.chdir(cwd)
    return root


@pytest.fixture(scope="module")
def faces(built, browser):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.goto((built / "docs" / "dist" / "standalone" / "index.html").as_uri(), wait_until="load")
    page_quiet(pg)
    got = {
        "intro": pg.evaluate(FACE, "main > p"),
        "introLi": pg.evaluate(FACE, "main > ul > li"),
        "body": pg.evaluate(FACE, "main > section > p"),
        "bodyLi": pg.evaluate(FACE, "main > section > ul > li"),
    }
    pg.locator("main .okt-fp .okt-fp-label").first.click()
    pg.wait_for_selector(".okt-mdview-rendered section p", state="attached")
    got.update(
        {
            "vTitle": pg.evaluate(FACE, ".okt-mdview-rendered > h1"),
            "vIntro": pg.evaluate(FACE, ".okt-mdview-rendered > p"),
            "vIntroLi": pg.evaluate(FACE, ".okt-mdview-rendered > ul > li"),
            "vBody": pg.evaluate(FACE, ".okt-mdview-rendered > section > p"),
            "vH2": pg.evaluate(FACE, ".okt-mdview-rendered > section > h2"),
        }
    )
    pg.close()
    return got


def test_the_measurement_found_its_elements(faces) -> None:
    assert all(faces.values()), faces
    # The section paragraph IS in the reading face; otherwise the
    # comparisons below would pass by agreeing on the wrong face.
    assert faces["body"]["family"] == "Literata", faces


def test_a_pages_opening_prose_is_set_like_its_section_prose(faces) -> None:
    assert faces["intro"] == faces["body"], faces
    assert faces["introLi"]["family"] == faces["bodyLi"]["family"], faces
    assert faces["introLi"]["size"] == faces["bodyLi"]["size"], faces


def test_a_viewed_files_opening_prose_and_title_are_in_the_reading_face(faces) -> None:
    assert faces["vIntro"]["family"] == faces["vBody"]["family"] == "Literata", faces
    assert faces["vIntro"]["size"] == faces["vBody"]["size"], faces
    assert faces["vIntroLi"]["family"] == "Literata", faces
    assert faces["vTitle"]["family"] == faces["vH2"]["family"], faces
