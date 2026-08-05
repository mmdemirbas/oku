# CLAUDE.md — oku

Onboarding notes for a fresh Claude Code session in this repo.
Read this before touching code. Skip nothing — every rule below was
the answer to a real bug the user pointed out.

The project is **oku** (Turkish imperative "read!"). Every layer
reads `oku`: the Python package (src/oku/), the CSS prefixes
(okt- / okc- / okd-), the JS globals (__oku*), the custom-event
names (oku:*), the data-attrs (data-oku-*), and the custom-element
tag names (oku-chart, oku-snippet, oku-diagram, oku-annotated-code,
oku-cite).

The only remaining mention of the legacy name "html-doc" is the
GitHub remote URL itself (`github.com/mmdemirbas/html-doc`) — used
by the schema `$id`, the `git clone` example, and the jsdelivr CDN
URL. Rename the GitHub repo and flip those when convenient; this
file is the catalog of the one exception.

## What this repo is

A shared HTML chrome kit + a Python CLI (`oku`) that authors
single-source **markdown pages** and renders them in the browser via
Custom Elements. No build step for content; the CLI converts each
`.md` source into a v2 page dict (`md_to_v2_page`) on the fly and
`renderer.js` walks it at page load.

Authoring shape: `docs/<page>.md` (source) + `docs/<page>.html` (thin
stub that loads the kit; it fetches `<page>.json`, which `oku serve` /
`oku build` synthesize from the .md).

### Page format (v3 — markdown-first)

A page is a `.md` file: YAML front-matter + a GFM body. The body is
**plain markdown**; kit primitives live in typed fences whose body is
ONE compact JSON object (same payload shapes as the schema `$defs`):

````markdown
---
title: Architecture
accent: teal
date: 2026-06-11
order: 40
summary: Runtime mental model + build pipeline.
---

> [!TLDR]
> Short summary.
>
> - bullet 1
> - bullet 2

## Section title {#anchor-id}

Lead paragraph with *emphasis* and `code`.

```oku-chart
{"type":"bar","rows":[{"label":"a","value":60},{"label":"b","value":80}]}
```

```mermaid
flowchart TB
  A --> B
```

*An italic line right after a mermaid fence becomes the caption.*
````

- Fence tags: `oku-chart`, `oku-table`, `oku-kpi-grid`, `oku-step-flow`,
  `oku-compare-grid`, `oku-example`, `oku-insight`, `oku-live-snippet`,
  `oku-annotated-code`, `oku-chart-grid`, `oku-tldr`, `oku-diagram` —
  plus plain `mermaid` (GitHub renders it natively).
- `##` opens a `<section>`, `###` is a sub-heading inside it. `{#id}`
  overrides the auto-slug. Glossary / ext-refs: `[label](#g/term-id)`,
  `[label](#x/source-id)`.
- Admonitions are GFM blockquotes: `NOTE`, `TIP`, `IMPORTANT`,
  `WARNING`, `CAUTION` + the kit's `TLDR`. `> [!NOTE] Title` carries
  an optional title.
- **Strict-GFM subset** (linted): no indented code blocks, no setext
  (`===`) headings, no lazy blockquote continuation. The subset is
  valid GFM, so GitHub/Obsidian render every page.
- **HTML islands**: a block-level HTML tag at column 0 (custom
  elements and `<script>`/`<style>` included) passes through to the
  DOM untouched — full capability, no restrictions. `oku check` lists
  every island as an info-level audit line; external markdown viewers
  strip islands. Inline HTML in prose stays literal text.
- Definition lists (`Term` / `: def`), task lists (`- [x]`), footnotes
  (`[^id]` + `[^id]: …`) and reference-style links (`[text][label]`,
  `[label][]`, `[label]` + `[label]: url "title"`) are supported.
  Both reference forms resolve **page-wide**, not per b[] string —
  `md_to_v2_page` splits a page at every typed fence, so a definition
  routinely lands in a different string than its reference. Footnotes
  render as numbered superscripts plus one "Footnotes" section at the
  end of the page. `oku check` warns on a reference with no definition
  (it would otherwise render as literal text with no other signal).

### Older pages (v1/v2 JSON)

JSON pages keep rendering indefinitely: v2 (`k/t/m/b`) natively,
v1 (`kind/title/blocks`) via the in-memory shim. Run
`oku migrate [path]` to convert any page-JSON to a v3 `.md` source
(deterministic, round-trips; the .json is removed).

### Two source formats. HTML is the output, not a source.

Worth stating plainly, because the phrase "markdown-first" reads like
a claim about the deliverable and is not one. **Every page ships as
HTML** — that is what `oku build` writes and what a reader opens.
The source format is a separate question: what the author types.

- **`.md`** — what an author writes. Front-matter + strict-GFM body.
- **`.json`** — v1/v2 pages written before the markdown format
  existed. They keep rendering forever; `oku migrate` converts one to
  `.md` when you want it converted.

Three more once existed for a measured comparison — `.src.html`
(authoring the *source* in HTML), `.adoc`, `.dj` — and were deleted
once markdown won. An author who wants raw HTML inside a page uses an
HTML island, which has no restrictions; that is a different thing from
writing the whole page in HTML, and it is the thing people actually
want. `_PAGE_SOURCE_PARSERS` / `_PAGE_SOURCE_EMITTERS` in cli.py stay
as a registry because `.json` is still a second entry.

### Build outputs

`oku build` produces two single-purpose trees under `dist/`:
- `dist/standalone/` — self-contained single files (humans, file://).
  Each HTML inlines kit + page JSON + `window.__okuManifest`.
- `dist/site/` — shared-assets multi-page site with Pagefind search
  (humans, HTTP). Holds the one `site-manifest.json` chrome.js fetches
  + `llms.txt` at the docs root.

There is no `dist/markdown/` tree: the `.md` sources ARE the canonical
AI/LLM surface.

## Top-level files

| File | Owns |
|---|---|
| `chrome.js` | Custom Elements (chart with 28 render modes, diagram, live-snippet, annotated-code, glossary-term, ext-ref, page-chrome / page-nav / page-toc), init-time DOM enhancement (table chrome, code fold, line numbers, sidebar wiring, bar-chart hover/click-pin/legend toggle), Prism + Mermaid lazy loaders, glossary tooltip controller, lightbox with pan/zoom/pinch fullscreen, the top rail (progress + landmark minimap). ~7k LoC. |
| `chrome.css` | All visual tokens (light/dark, --series-1..--series-10, --prose-width), layout grid (asymmetric bleed, four-mode content width), every primitive's styling. ~3k LoC. |
| `renderer.js` | page JSON → DOM mapping. Walks `b[]`; strings parsed by the GFM block parser (headings → sections, paragraphs, lists, GFM tables, fences — `oku-*`/`mermaid` fences lift to typed blocks, def-lists, task-lists, HTML islands w/ executing scripts, admonitions); typed objects dispatched to typed renderers. v1→v2 shim keeps older pages rendering. ~1.6k LoC. |
| `kit/schema/page.schema.json` | JSON-schema for page payloads. Every page (converted from .md) validates against it; the optional `jsonschema` dep makes the check active. Chart `type` enum here is the single source of truth for known chart types. |
| `kit/{glossary,extrefs}/<domain>.json` | Central glossary + ext-ref registries by domain; fetched at runtime by chrome.js. |
| `src/oku/cli.py` | `oku init / build / clean / check / migrate / serve` plus the v3 converter pair (`md_to_v2_page` / `page_to_md`), the strict-GFM + island lint (`_lint_md_string`), and the v1→v2 page shim (`_v1_to_v2`). |
| `src/oku/templates/` | `starter.{md,html}` — pair to copy when starting a new page. |
| `bin/oku` | PEP 723 shim — run without install via `uv run bin/oku …`. Points at `oku.cli:main`. |
| `docs/` | The kit's own documentation, authored via the kit. Use these as canonical examples. `docs/roadmap.md` tracks open phases. |

## Installing the tool globally

Other projects reach the kit through a globally installed `oku`, which
carries its OWN COPY of `kit/` inside the wheel. Editing this repo does
not change what those projects build with until the tool is reinstalled:

```bash
uv tool install --force --no-cache --from . oku   # --no-cache is load-bearing
oku --version    # oku 0.4.0 · kit 2026-08-03-r13 · assets /…/site-packages/oku/assets
```

`--force` alone is NOT enough: uv reuses the cached wheel when the
version string in `pyproject.toml` has not changed, so the tool silently
stays on the old kit while reporting a successful install. Either bump
the version on a kit change, or pass `--no-cache`. `oku --version`
prints the kit build stamp (`__okuKitBuild` in chrome.js) — compare it
against the repo's to see whether a project is building with the current
kit. A page rendered by a stale tool is the usual cause of a "the kit
regressed" report; check the stamp inlined in the artifact first
(standalone HTML files carry it).

## Develop / verify

```bash
uv sync --extra dev           # pulls pytest, ruff, jsonschema
oku check                     # schema + structural lint (the fast verify gate)
oku check --strict            # exit 1 on warnings too
oku build                     # writes dist/{standalone,site}/
oku serve --no-watch          # local server (live-reload on by default)
uv run pytest -q              # 300+ tests; should all pass
uv run ruff check . && uv run ruff format --check .
```

`oku check` is the canonical verify step for any doc-content
change — it runs the schema + a suite of structural checks (deprecated
kinds, duplicate anchors, unresolved glossary terms / ext-refs,
forbidden process language, chart shape sanity per type — including
the Tier 3 chord / geo / sankey / network / scatter-matrix /
parallel-coordinates payload shapes). Run it before calling a doc
change done. `oku build` invokes the same checks internally and
refuses to ship if it errors.

After ANY change to chrome.js / chrome.css: hard-reload the browser
(`location.reload(true)` from the page console, or close the tab and
re-open). The dev server doesn't cache aggressively, but Chrome
itself often holds the prior script in memory and the symptom looks
like "my change didn't take effect" — it did; the runtime is stale.

## Rules the user has set down

**Contents drawer, centred content.** `page-nav` adopts `page-toc` as
a child at boot so site-tree + on-page TOC stack in one panel. NO
dual-pane, NO right-side TOC.

The panel is an **overlay drawer at every width** — parked off-canvas
at `left: -100%`, slid in by `body.drawer-open`, with a scrim, Escape
and outside-click to close. `main` is `margin-inline: auto`, so the
measure is centred and **never moves when the drawer opens**. On a wide
window the drawer lands in the empty gutter beside the column.

One affordance: the **`.ctrl-btn.drawer-toggle` in the top-left chrome
strip** — icon only, in the same 44px box every other chrome button
uses, with the name carried by `aria-label` + `title` (plus
`aria-expanded` / `aria-controls`). It is present at every width. The
visible word "Contents" was removed: it made the one control that wears
text the heaviest thing above the cover, and `test_invariants.py`
now asserts the button's `inner_text` is empty and both name attributes
are there.

Removed, do not bring back: the permanent sidebar grid column, the
full-height right-edge handle (`.page-nav-edge`) that doubled as
resize + collapse, the 24px collapsed rail, and the persisted
`sidebarCollapsed` / `sidebarWidth` state. A line down the page that
reflows the text every time it is used is what this replaced.

**The default has to render finished.** A page whose author wrote
`title`, `summary` and content — nothing else — is the case the kit is
judged on. Concretely, and each pinned by a test in
`src/oku_tests/browser/test_presentation_defaults.py`:

- An untitled `> [!TLDR]` shows the words TL;DR **once**. The `<h2>`
  still exists (`buildTOC` skips a section without one, and search
  reads it) carrying `.okt-sr-only`.
- Every block in a section ends at the same x — paragraph, list,
  blockquote, callout, TL;DR, code, diagram, table. See "One column,
  one right edge" below; nothing caps a block below `--content-width`.
- A table at or below `SMALL_TABLE_ROWS` (chrome.js) keeps only copy +
  expand. That threshold is a rule about its CONTROLS, not about its
  box: the card spans the column like every other block. The controls
  stay in the DOM with their listeners bound; CSS hides them, so a
  table that grows past the threshold needs no re-init.
- The cover subtitle falls back to `summary`; a cover holding only an
  h1 gets `.cover-bare`; `updated` is suppressed when it equals `date`.

**One column, one right edge.** Every block in a section ends at the
same x. Nothing caps a block below `--content-width` — not prose, not
a callout, not the TL;DR panel. The reader shortens the measure with
the width toggle, which moves the whole column together.

This has been reopened once and must not be a third time. Body prose
runs long at the comfortable width (a 77–83 character median when it
was measured), so `--prose-width` was applied to running prose. Better
for the paragraph, wrong for the page: the text stopped ~200px short
of the cover, the code blocks and the diagrams around it, and the
verdict was "the text is still narrower than the other elements". A
right edge that steps in and out down the page reads as a rendering
fault. `--prose-width` stays declared and unapplied for a caller that
wants a per-block cap. `test_presentation_measure.py` pins the rule at
every width, including the computed `max-width: none`, so re-applying
the cap fails rather than merely looking different.

A small table was the one block exempt from this, sizing to its content
so three short cells were not stretched over 970px. The card then ended
short of the paragraph above and the code block below, which is the
same stepped right edge in a different guise, and the exemption is
gone. Columns distribute the slack; `table-layout: auto` gives each its
content share.

**Running prose is justified, and the hyphenation is part of it.**
`text-align: justify` + `hyphens: auto` on paragraphs, list items,
callout and TL;DR bodies. Justify without hyphenation computes the same
and renders rivers — the browser can only stretch word spaces, so one
long word at the end of a line drags the whole line apart. The scope is
a selector list, not `main`: a justified table cell, axis label or chip
is a short string pulled to a box edge. Single-line blocks need no
exception — `justify` leaves a block's LAST line ragged, and a one-line
paragraph is all last line.

**The rail does not move — and opening it is not moving.** The strip at
the top carries read progress plus a tick per heading and a dot per
figure, each a button that jumps there. Hover and focus OPEN it: 12px
of hairline becomes a 32px map, marks scale x2, and the swell still
applies on top of that. Nothing drifts, because the strip is `fixed`
with a fixed top edge and can therefore only grow **downward** — every
mark keeps its x, its width and its top, `main` does not move, and
`test_page_rail.py` compares all of it across states. The three numbers
(32px open height, x2 open scale, `RAIL_MAG_MAX` 1.6) are one
constraint against the 9px title bar: 9 x 2 x 1.6 = 28.8 has to fit
inside 32. Change one, re-check the other two. The label is absolutely
positioned and `pointer-events: none`, so revealing it cannot push
anything.

Three decisions inside it are load-bearing. Marks and the fill share one
scale (`elementTop / maxScroll`), so the fill edge reaches a mark
exactly when that landmark hits the top of the viewport — a second
scale would let the highlight contradict the bar beside it. Marks are
**thinned** in hierarchy order: sections first because they are the
shape of the page, then the title, then sub-headings, then figures,
each placed only where it clears everything already down by 6px, and
figures not at all below a 560px rail. Unthinned, `docs/reference.md`
put 49 marks 0px apart at phone width. Plain `<pre>` is not a landmark
kind — marking every code block turns the rail into a dotted line.

And **`RAIL_FIGURES` order is priority**: overlapping figures are
rejected in BOTH nesting directions, so whichever selector is listed
first claims the position. Named kinds are listed before generic
containers for a reason — every chart on `docs/charts.md` sits inside
an `.example-pair`, the pair starts a few pixels above the chart it
wraps, and with both claiming a mark the thinner kept the pair. 48
charts, no chart shape on the rail, and a tooltip reading "Example"
where the reader was looking for "Chart".

**The swell is a transform, and that is the whole safety argument.**
Marks within 46px of the pointer scale on a cosine falloff, like a
dock. A dock that reflows makes you chase the thing you were aiming
at; this one scales the mark's `::before`, so no layout is computed
and no button box moves. It multiplies with the rail's open scale, and
the pair is bounded by the open height (see above). Touch pointers are
ignored — there is no hover to respond to, and a swell on tap moves the
target out from under the finger.

**Shape says what kind of thing it is.** A bar for a heading, thicker
and taller the higher its level — h1 (the cover title) 3x9, `##` 2x7,
`###` 1.5x4. Depth alone says "there is a hierarchy"; depth plus weight
says which level, without measuring one bar against its neighbour. For
figures, the three kinds a reader hunts for by name get a silhouette
each and share it with nothing: a filled square is a **table**, a
filled circle is a **chart**, a diamond is a **diagram**. Every other
figure — KPI grid, comparison grid, step flow, snippet, annotated code,
example pair — is a hollow square: recognisably a figure, recognisably
not one of the three. Four figure shapes, not eleven; 4px carries a
silhouette, not an alphabet, which is why the rail opens on hover. The
tooltip carries the name, and for a chart or a diagram a thumbnail
cloned from the rendered SVG. The clone's ids are rewritten;
`page-chrome` precedes `<main>`, so a duplicate id would make
`getElementById` return the thumbnail instead of the real figure.

**The top-right corner is one flex row, not five offsets.** Every button
that belongs there — personalize, search, warning, width, theme — is a
child of `.okt-chrome-cluster` and is positioned by it. Visual order is
`order:`, so it does not depend on which subsystem initialised first.
The cluster lives on `<body>`, deliberately **not** inside `page-chrome`:
that element rewrites its own `innerHTML` in `connectedCallback`, which
fires again on reparent, and would take a late-arriving search button
with it. Use `okuChromeCluster()` to get it; never `document.body.
appendChild` a chrome button and never give one a `right:` of its own.

The version this replaced had each button computing `right:` by hand
plus `:has()` rules to close the gap when a neighbour was absent, and
`.width-toggle` and `.search-toggle` both landed on right: 76px — same
44px square, width toggle unreachable, on every page with search and no
warning. Neither declaration was wrong alone; the offset table was
never re-derived when search was added, which is what offset tables do.
A `display: none` child now takes no space and the row closes up on its
own. `test_invariants.py::test_the_top_right_chrome_never_overlaps`
asserts no two visible `.ctrl-btn` rects intersect, at four widths.

**The chrome buttons quiet down when nothing is reaching for them.**
Four fixed 44px boxes float over the top of the reading column at every
scroll position. They sit at a 0.32 floor and rise to full on a cosine
falloff over 190px of pointer distance, measured **to the button's box**
(point-to-rect, zero inside) so a button you are about to click is not
still dim. Per button, not per region: approaching the theme cycler
does not light the Contents button. Three things keep it from becoming
a hidden control — the floor is not zero, hover / focus-visible /
`aria-expanded="true"` pin it to full, and the whole mechanism only
arms once a non-touch pointer has actually moved
(`body[data-ctrl-proximity="1"]`), so touch, screen readers and a
no-script page see full opacity. The warning indicator is excluded: an
alert that dims itself is a bug. Opacity only — no box changes.

**Front-matter is `title` + `summary`.** Plus `order` / `parent` for
tree placement. `accent` and `audience` are tree-wide in `docs/kit.json`;
`read_time` and `updated` are derived at build time (220 wpm; the git
commit date, never the mtime — a fresh clone would stamp the whole tree
as updated today). An authored value always wins and every derived key
is listed in `m._derived`. **`page_to_md` must skip that set** — without
it, one `oku migrate` writes every derived value back into the source
and freezes it stale.

**Presentation rules live in `oku check`, not in prose.** A style rule
written in the skill briefing decays because nothing fails when it is
ignored. `redundant-meta`, `hand-set-derivable`, `prose-only-section`,
`island-hand-styled`, `accent-divergence`, `group-of-one` and
`figure-restates-headings` are the decidable half. Anything needing a
reader's judgement stays out — a check that guesses trains authors to
ignore checks. The repo's own tree must stay clean under
`oku check --strict`; `test_check.py::test_project_docs_pass_check_strict`
enforces it.

**Visuals are ranked, and the ranking is in the briefing.** Prefer the
figure that shows the whole at a glance, encodes values into a small
space, and lands without the reader stopping to work it out: charts
with a real axis, small multiples, mermaid topology, before/after on
one scale. Tables, step flows and compare grids are legitimate with a
lower ceiling — the reader still has to read every cell. KPI tiles,
status pills, coloured callouts and icon rows encode nothing; they are
decoration wearing a chart's clothes. Only two parts of this are
decidable, and those two are checks: `group-of-one` (a primitive whose
job is the relationship between members, used with one member) and
`figure-restates-headings` (a diagram whose boxes are the page's own
section titles). The rest is the author's judgement, and belongs in
`skill/SKILL.md`.

**HTML islands build on the kit.** An island is the escape hatch and
keeps full capability, but its colours come from the kit's CSS
variables (`var(--accent)`, `var(--surface)`, `--series-1..10`) and its
structure from the `.okt-*` classes. Hardcoded hex or an inline
`<style>` earns `island-hand-styled`, because the hand-rolled copy stops
following the accent and breaks in the theme nobody was looking at.

**Neutral count visual language.** Stats counter / chip badges /
group count badges render bare numerals ("5" or "3/5"), never
English words. The page can flip to TR or EN without touching kit
code.

**No demo sibling pages.** Every example for a primitive lives
inside `docs/reference.md` next to the primitive's heading: code
sample + rendered block. Don't create `docs/<thing>-demo.{html,json}`
— `src/oku_tests/test_content_regression.py::TestNoStrayDemoPages` enforces.

**No process/round/historical references in docs.** "Round-N",
"v2 review", "fixed in round 5" etc. are forbidden in `docs/*.md`.
Refer to current behaviour, not how it got here. Past sessions left
this kind of breadcrumb in many places; `git grep -i round docs/`
should return nothing relevant.

**Tables read as one card.** `.okt-table-wrap` carries a border +
padding so two consecutive tables don't bleed into each other. The
filter input + stats counter sit together on the left; chip rack is
a two-column grid (label, chips) directly under the controls bar.
Group count badges go FIRST in the group header (before the title)
so the numbers line up at a consistent x.

**Code blocks: line numbers + language pill + brace folds.** Every
`<pre><code>` gets a gray gutter with line numbers (`.okt-code-gutter`,
`user-select: none` so copy excludes them). When a language class is
present, a small label appears at top-right of the pre. JS / TS /
JSON / CSS code blocks gain a fold marker on every line ending with
`{`, `(`, or `[`; click hides lines until the matching closer at
the same indent. The fold pass is hooked into Prism's `complete`
event because the autoloader replaces innerHTML asynchronously per
block — a `.then()` chain after `highlightAll()` races and loses.

**Add a regression test with every fix.** The user has explicitly
called out that bugs keep recurring because tests don't cover the
surface. For Python CLI behaviour use pytest under
`src/oku_tests/`. For doc-content regressions use
`src/oku_tests/test_content_regression.py` (walk the doc tree,
assert on shape). For runtime browser behaviour add Playwright tests
under `src/oku_tests/browser/` — wired and running in the default
suite against the real serve handler in headless chromium
(`test_invariants.py` pins the numeric UI invariants below; the
package auto-skips where chromium isn't installed, enable with
`uv run playwright install chromium`). Whatever the layer, the rule
is: a bug found by the user must have a test that fails before the
fix and passes after.

## UI invariants — numeric, enforced

Four rules that prevent the regression class the user has had to
correct repeatedly. Each is phrased as a binary numeric invariant so
a test can assert it. "Looks right" is not an acceptable
formulation — if you can't state the rule as a `boundingBox` /
computed-style assertion, the rule isn't found yet.

1. **Sidebar surface always spans the visible viewport.** If a sidebar
   exists, its background+border extends from `y=0` to `y=innerHeight`
   at every scroll position and on every page. Content inside may
   overflow with its own scrollbar, but the surface never ends
   mid-page. Numeric: `page-nav.boundingBox.height === innerHeight`
   (±1px). Set `height: 100vh` AND `height: 100dvh` — `max-height`
   alone lets content shrink the element.

2. **Hidden modes have a visible reveal.** Collapsed sidebars, closed
   drawers, hidden details — every hidden state keeps a clickable
   affordance visible. No invisible-toggle states. Numeric: the rail
   (collapsed sidebar) is ≥ 18px wide and click-targetable; the
   reveal control's `boundingBox` is non-zero and inside the
   viewport.

3. **Layout invariants are numeric, not eyeball.** Anything you would
   state as "X should look right" can be phrased as a numeric
   assertion: bounding-box position, dimension, or computed style.
   If you can't phrase it numerically, you haven't found the rule
   yet. Don't ship a "fix" backed only by a screenshot — the
   screenshot is evidence, not the rule.

4. **Browser-verify before claiming "fixed".** Pytest is necessary,
   not sufficient. UI changes get opened in a real browser via
   Playwright at desktop AND ~360px width; the relevant
   `boundingBox` figures land in the commit message body as the
   verification record. The record is the proof — no record means
   no verification.

## Common pitfalls

- **Stale chrome.js in the browser.** The CDN-loaded Prism autoloader
  fires `complete` twice per block (once before the language module
  arrives, once after). The line-wrap / fold pass guards against the
  second pass via `code.querySelector('.okt-code-line')` — DO NOT
  guard with a one-shot `data-` attribute; the second Prism pass
  wipes the spans, and a one-shot guard then refuses to re-apply.

- **CSS rules silently dropped by Chrome.** A multi-line comment
  inside a rule body, containing certain Unicode punctuation, has
  been observed to make Chrome's parser drop the trailing
  declaration. If a rule that should win according to specificity
  ISN'T winning, move the comment outside the braces.

- **page-toc adoption is async.** `PageNav.connectedCallback` queues
  a microtask to adopt the sibling `page-toc`. If you query the
  sidebar shape during init you'll see them as separate elements
  until the microtask runs.

- **`connectedCallback` fires on every reparent.** "Expand to
  fullscreen" moves the LIVE host into the lightbox and back on
  close. Every custom element that consumes its own source
  (`<script type="text/x-mermaid">`, `text/x-code`, `text/plain`)
  and then overwrites `innerHTML` MUST carry the
  `if (this._initialized) return;` guard, or the second pass reads
  an empty source and blanks the block. Chart, diagram, snippet and
  annotated-code all have it; a new element of that shape needs it
  too. `test_reparent_safety.py` pins it.

- **Inline styles beat the lightbox stylesheet.** The diagram render
  pass pins the authored width as an inline `max-width`, so the
  `max-width: none` rule for `.okt-lightbox-*` loses. Anything that
  should change inside the lightbox and was set inline must be
  stashed and restored by the expand handler, not fought in CSS.

- **`tldr` is allowed inside contentBlock** (recent schema change).
  Don't refactor the schema to remove this — the primitives reference
  embeds a live tldr sample alongside its code example.

## Browser verification flow

1. `oku build` (validates schema + emits artifacts).
2. `oku serve --no-watch --no-search`.
3. Open the changed surface in a browser.
4. Force a hard reload (`Cmd+Shift+R` / `Ctrl+Shift+R`) — soft reloads
   keep the prior chrome.js in memory.
5. Walk the user-facing path (filter, group-by, chip toggle, fold,
   collapse, etc.) and verify; not just look at the screenshot.
6. Encode the verification as a content-regression test (or a future
   Playwright test).

## What NOT to do

- Don't introduce a `docs/<thing>-demo.{html,json}` page. Fold demos
  into `docs/reference.md`.
- Don't reintroduce the dual-pane sidebar / right-side TOC / mid-edge
  collapse tab. They were explicitly removed.
- Don't add English words to count badges or stats text. Numbers only.
- Don't say "since round N" / "fixed in round N" in docs.
- Don't claim a fix is done after only running pytest. The Python
  test surface doesn't cover the browser behaviour where most bugs
  hide.
- Don't add an `!important` to win a cascade fight before checking
  whether a sibling rule is dropping a declaration silently (see
  pitfalls above).
