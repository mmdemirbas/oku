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
  `oku-annotated-code`, `oku-chart-grid`, `oku-timeline`, `oku-info-tip`,
  `oku-diagram`, `oku-copy` — plus plain `mermaid` (GitHub renders it
  natively).
  `oku spec` prints this list from the code, and
  `test_content_regression.py` holds this sentence against it. The list
  named a fence that had been removed and omitted one that exists, which
  is what a hand-copied list does.

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
| `chrome.js` | Custom Elements (chart with 53 render modes, diagram, live-snippet, annotated-code, glossary-term, ext-ref, page-chrome / page-nav / page-toc), init-time DOM enhancement (table chrome, code fold, line numbers, sidebar wiring, bar-chart hover/click-pin/legend toggle), Prism + Mermaid lazy loaders, glossary tooltip controller, lightbox with pan/zoom/pinch fullscreen, the top rail (progress + landmark minimap), the markdown viewer. ~13k LoC. |
| `chrome.css` | All visual tokens (light/dark, --series-1..--series-10, --prose-width), layout grid (asymmetric bleed, three-mode content width), every primitive's styling. ~6.5k LoC. |
| `renderer.js` | page JSON → DOM mapping. Walks `b[]`; strings parsed by the GFM block parser (headings → sections, paragraphs, lists, GFM tables, fences — `oku-*`/`mermaid` fences lift to typed blocks, def-lists, task-lists, HTML islands w/ executing scripts, admonitions); typed objects dispatched to typed renderers. v1→v2 shim keeps older pages rendering. ~2.6k LoC. |
| `kit/schema/page.schema.json` | JSON-schema for page payloads. Every page (converted from .md) validates against it; the optional `jsonschema` dep makes the check active. Chart `type` enum here is the single source of truth for known chart types. |
| `kit/{glossary,extrefs}/<domain>.json` | Central glossary + ext-ref registries by domain; fetched at runtime by chrome.js. |
| `src/oku/cli.py` | `oku init / build / clean / check / spec / vendor / verify / migrate / serve` plus the v3 converter pair (`md_to_v2_page` / `page_to_md`), the strict-GFM + island lint (`_lint_md_string`), and the v1→v2 page shim (`_v1_to_v2`). |
| `src/oku/templates/` | `starter.{md,html}` — pair to copy when starting a new page. |
| `bin/oku` | PEP 723 shim — run without install via `uv run bin/oku …`. Points at `oku.cli:main`. |
| `docs/` | The kit's own documentation, authored via the kit. Use these as canonical examples. `docs/roadmap.md` tracks open phases. |

## Installing the tool globally

Other projects reach the kit through a globally installed `oku`, which
carries its OWN COPY of `kit/` inside the wheel. Editing this repo does
not change what those projects build with until the tool is reinstalled:

```bash
./run install    # the whole procedure, and it verifies itself
```

**Use `./run install`. Do not hand anyone the raw `uv tool install`
line** — it has a trap in it, and a command with a trap is one nobody
should be retyping from memory. `--force` alone is NOT enough: uv reuses
the cached wheel when the version string in `pyproject.toml` has not
changed, so the tool silently stays on the old kit while reporting a
successful install. `./run install` passes `--no-cache`, then compares
the repo's kit stamp against the one the installed tool reports and
exits non-zero when they differ. That comparison is the point — a stale
global tool reports success and then builds other projects with the old
kit, so the symptom arrives later, somewhere else, as "the kit
regressed".

`./run version` answers the same question without reinstalling.
`oku --version` prints the kit build stamp (`__okuKitBuild` in
chrome.js); standalone HTML files carry it inlined, so when a project
reports a kit bug, check the stamp in the artifact first.

The wheel's copy of `kit/` is assembled from a hand-maintained
`force-include` list in `pyproject.toml`. `test_packaging.py` checks
that list against the directory in both directions, because a kit file
nobody remembered to add ships as a silent absence — this repo renders
it, the tests pass, and every other project builds without it.

## Develop / verify

```bash
uv sync --extra dev           # pulls pytest, ruff, jsonschema
oku check                     # schema + structural lint (the fast verify gate)
oku check --strict            # exit 1 on warnings too
oku build                     # writes dist/{standalone,site}/
oku verify                    # opens BOTH built trees in a browser
oku serve --no-watch          # local server (live-reload on by default)
uv run pytest -q              # 1500+ tests; should all pass
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

Each was the answer to a real bug. The ones whose reasoning runs long
are stated here and explained in full in `PRESENTATION-RULES.md` —
read that entry before changing anything it covers. The rest are short
enough that a pointer would cost what the rule costs, so they stay
whole below.

- **Contents drawer: one button, three states.** Held by `test_a_peek_moves_nothing`. → [why](PRESENTATION-RULES.md#contents-drawer-one-button-three-states)
- **The default has to render finished.** Held by `test_presentation_defaults`. → [why](PRESENTATION-RULES.md#the-default-has-to-render-finished)
- **One column, one right edge.** Held by `test_presentation_measure`. → [why](PRESENTATION-RULES.md#one-column-one-right-edge)
- **The rail does not move — and opening it is not moving.** Held by `test_page_rail`. → [why](PRESENTATION-RULES.md#the-rail-does-not-move-and-opening-it-is-not-mov)
- **Shape says what kind of thing it is.** Four rail-mark silhouettes,
  not eleven — bar for a heading, square/circle/diamond for
  table/chart/diagram, hollow square for every other figure. → [why](PRESENTATION-RULES.md#shape-says-what-kind-of-thing-it-is)
- **The top-right corner is one flex row, not five offsets.** Held by `test_invariants`. → [why](PRESENTATION-RULES.md#the-top-right-corner-is-one-flex-row-not-five-of)
- **The width control has three stops, and the icon has three segments.** Held by `test_reader_can_cycle_content_width`. → [why](PRESENTATION-RULES.md#the-width-control-has-three-stops-and-the-icon-h)
- **The theme button has two stops, and following the OS is not one of them.** Held by `test_the_auto_dot_marks_following_and_goes_out_when_pinned`. → [why](PRESENTATION-RULES.md#the-theme-button-has-two-stops-and-following-the)
- **A link to a .md file opens the kit's viewer, not the browser's raw text.** Held by `test_a_relative_prose_link_is_not_carried`. → [why](PRESENTATION-RULES.md#a-link-to-a-md-file-opens-the-kit-s-viewer-not-t)
- **The kit's own strings follow the page's language.** Held by `test_i18n_coverage.py`. → [why](PRESENTATION-RULES.md#the-kit-s-own-strings-follow-the-page-s-language)
- **Anything the kit hangs off content must never become content.** → [why](PRESENTATION-RULES.md#anything-the-kit-hangs-off-content-must-never-be)
- **A card answers the pointer with light, never with position.** Held by `test_hovering_a_card_does_not_move_what_is_written_on_it`. → [why](PRESENTATION-RULES.md#a-card-answers-the-pointer-with-light-never-with)
- **A card that promises a picture shows the picture, and the picture is a clone.** Held by `test_compare_previews`. → [why](PRESENTATION-RULES.md#a-card-that-promises-a-picture-shows-the-picture)
- **A label is fitted to the space it has, and measured after the font
  lands.** A chart's gutter is sized from its own labels, never from a
  constant; anything still too wide is shortened after paint with the
  whole string kept in a `<title>`. Held by `test_chart_label_fit`. → [why](PRESENTATION-RULES.md#a-label-is-fitted-to-the-space-it-has)

**Running prose is justified, and the hyphenation is part of it.**
`text-align: justify` + `hyphens: auto` on paragraphs, list items,
callout and TL;DR bodies. Justify without hyphenation computes the same
and renders rivers — the browser can only stretch word spaces, so one
long word at the end of a line drags the whole line apart. The scope is
a selector list, not `main`: a justified table cell, axis label or chip
is a short string pulled to a box edge. Single-line blocks need no
exception — `justify` leaves a block's LAST line ragged, and a one-line
paragraph is all last line.

**The swell is a transform, and that is the whole safety argument.**
Marks within 46px of the pointer scale on a cosine falloff, like a
dock. A dock that reflows makes you chase the thing you were aiming
at; this one scales the mark's `::before`, so no layout is computed
and no button box moves. It multiplies with the rail's open scale, and
the pair is bounded by the rail's open height (see
[the rail rule](PRESENTATION-RULES.md#the-rail-does-not-move-and-opening-it-is-not-mov)).
Touch pointers are
ignored — there is no hover to respond to, and a swell on tap moves the
target out from under the finger.

**A translation is the same page, not another page.** Authoring is
`<page>.md` + `<page>.<lang>.md` side by side — no new syntax, each file
a complete markdown document that still renders on GitHub. `kit.json`
declares which codes count (`languages`, `defaultLanguage`); without
that key none of it runs and a monolingual site pays nothing. Not a
mirrored `docs/tr/` tree: that duplicates the structure, breaks every
relative link inside a page, and hides the counterpart from anyone
reading a directory listing.

The **manifest** carries the pairing — each base entry gains `lang` and
a `variants` map, and the translations leave the tree. It is the carrier
because it is the one thing that already reaches every page in all three
modes: fetched under `oku serve` and `dist/site`, inlined in a
standalone file. Left in the tree, a ten-page site in two languages
reads as twenty pages. `variants` includes the base itself, so the
switch has no special case for "where do I go back to".

**Match the manifest path by SUFFIX, never by equality.** Manifest paths
are relative to the root the manifest was built from, and that root is
not the same thing in every mode — `reference.html` under `oku serve`,
`docs/reference.html` in `dist/site` and in the standalone inline — while
`location.pathname` is `/docs/reference.html` in the first two and an
absolute filesystem path in the third. Equality against a bare filename
matched under `oku serve` and nowhere else, so the button worked in
development and was missing from both things a reader receives.
Resolving against `__okuDocsRoot` is not the fix either: it doubles the
prefix in the two modes that already carry it. The suffix match also
yields the navigation target — strip it off the pathname and the
remainder is the prefix every variant hangs from.

**Every standalone page inlines the manifest**, not just the entry stub.
`build_standalone` injects a freshly computed one; before that only the
stub `oku init` wrote had any, so every other page opened over file://
with no site tree and no switch. `page-nav`'s standalone branch reads it
for the switch AND for the tree, because a variant and a sibling page are
the same relation: the file sitting next to this one.

**"Standalone" is how the file carries the kit, not how many files there
are.** `oku build` writes one self-contained HTML per page side by side
in `dist/standalone/`, so a reader who opens one does have a tree to
navigate — every row points at a file in the same directory. The branch
used to drop the tree on the reasoning that a single file has no site,
which holds only for a one-page build; for every tree the reader lost the
navigation the served modes give them, with the data to rebuild it
inlined in the same file. It now draws the tree unless the manifest lists
one page, or this file's own path is not in it (no suffix match, so no
root for the rows to hang from). A page forwarded ALONE out of a
multi-page build keeps rows that will not resolve — the same bet the
language switch already makes, against the cost of every reader of a
whole tree losing navigation. Held by `test_standalone_site_tree.py`.

The base is the one part that cannot be shared with the served modes:
`__okuDocsRoot` falls back to the page's OWN directory when the kit is
inlined, which is right at the tree root and wrong by one level in every
subfolder. Both the row hrefs and the active-row marking come from
`__okuLangSwitch.locate` — the suffix match above — so there is one
implementation of that rule rather than two that drift. The SPA click
interceptor sits out standalone entirely: each file is self-contained, so
the browser's own navigation is already right, and SPA-rendering would
fetch a JSON `file://` refuses.

The button appears **only where there is somewhere to go**, so there is
no disabled state to explain. Two letters, never a flag (which names a
country) and never a word (which would have to be written in the
language the reader has not chosen). It carries the `#fragment` across,
which is why **a translation's anchors must be identical to its
original's** — `{#id}` is copied verbatim, and a heading the English
side leaves to the slugifier gets its id pinned explicitly on the
translated side, because `slugify` strips non-ASCII.

**No auto-redirect on load.** A reader who opens a URL gets the page at
that URL; sending them elsewhere breaks the back button and makes a
shared link mean different things to different people. `oku-lang` stores
the choice and nothing reads it back yet — the tree still lists base
pages under base titles. That is the honest state, not a missing step.

Derived values follow the page's language where they are words:
`read_time` is `~17 dakikalık okuma` on a `.tr` page. A declared
language with no phrase of its own falls back to English rather than
guessing. The kit's own chrome (search, viewer, Contents) is still
English on every page — localizing it is separate work.

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

**A built page says what it was built from.** The sidebar footer carries
`oku v0.6.5 · kit 2026-08-14-r37` / `built 3 days ago` / a Rebuild button
that copies `cd <source> && oku build`. It exists because a delivered
report was opened, a rendering defect was reported against it, and the
defect had been fixed three stamps earlier — nothing on the file said it
was old. The facts ride in the manifest's `build` block, which is the one
thing that already reaches every page in all three modes.

Three things about it that are decisions, not oversights. **The button
copies rather than rebuilds**: a `file://` page has no channel to a
shell, and the one surface with a live server (`oku serve`) symlinks the
kit, so a served page is never the stale one — a real rebuild button
would work only where nothing needs it. **The page never says how far
behind the installed kit it is**: that needs the network, and a document
that calls home when a colleague opens it is worse than the bug it would
report. `oku build` prints `kit <old> → <new>` instead, at the one moment
both numbers are in the same process. **The command is kept out of the
committed stub** — `_init_time_manifest` pops `build` because
`docs/index.html` is a source file and the command holds a path from the
author's machine (collapsed to `~`, so it names a layout and not an
account). Held by `test_build_provenance.py`, both halves.

The footer's `KIT_VERSION` constant is gone with it. It was told to track
`pyproject.toml` "in lockstep" and read `v0.4.0` against a `0.6.5`
package for however long nobody put the two side by side — a second copy
of a fact with no authority rule. The version now comes from the manifest
and the stamp is read out of chrome.js by the build, so neither is
hand-maintained.

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

**A blank line ends an island's BLOCK, never its element.** That is
CommonMark, and it is the whole reason an author can write markdown
inside a `<div>` — the `<div>` / blank / `**bold**` / blank / `</div>`
idiom GitHub documents. The kit rendered each block as its own fragment
and `createContextualFragment` auto-closed the element, so everything
after the blank line became a sibling of the island instead of a child:
an island holding an 82-line block rendered with 403 characters in it,
the rest on the page styled as though it had never belonged, and
`oku check --strict` clean. `emitMarkdown` carries a stack of what is
still open; an island's source is cut at every tag closing something an
earlier island opened, and whatever it leaves open takes the blocks that
follow. Held by `test_html_island_spans_blank_lines.py`.

The opposite failure is the one this creates, so it is a check. An
island that never closes now takes the rest of the section with it, and
`island-unclosed` names the tag and the line that opened it — at the page
end and at every `##`, because a section boundary ends the run of blocks
the renderer emits in one pass. The lint walks tags the way the renderer
does, and `test_authority_agreement` holds the void and raw-text tag
tables against each other: a tag in one and not the other is a lint
reporting an island the renderer closed, or the reverse.

**Multi-line code inside an island is a `<pre>`, never `<br>`.** A `<br>`
renders three lines and copies as one — it carries no newline character,
so a SQL block pasted into another system arrives on one line. A `<pre>`
at column 0 always ran to its own `</pre>`; what was broken was a `<pre>`
nested in a `<div>`, cut at the first blank line, which left `<br>` as
the only spelling. The kit's copy button reaches an island's `<pre>` and
reads the newlines that are there.

**A file the page points at travels with the page.** `![tiny](tiny.png)`
beside its `.md` built clean and shipped broken: the reference survived,
the file was copied nowhere, `oku check` passed and `oku build` printed
nothing. A preview served from the source directory resolves the image,
so only the handed-over artifact is missing it — a delivered page carried
a screenshot with `naturalWidth` 0. `collect_page_assets` finds all three
spellings (markdown `![alt]()`, an island attribute, an `image` block's
`src`), keyed by the href AS AUTHORED. `dist/site` copies the file at the
path the href names; a standalone page inlines it as a `data:` URI up to
`MAX_INLINE_ASSET_BYTES` (2 MB) and past that copies it beside the page
and says so, because the page has stopped being one file. Rewriting skips
code spans and fences — a page documenting figures shows the markdown for
one — and a missing file is left to `unresolved-link` rather than reported
twice. Held by `test_build_carries_assets.py` and
`browser/test_image_delivery.py`.

**A Mermaid diagram gets its colour from the kit too, and the kit has
to do the work.** Mermaid's `classDef` / `style` grammar takes CSS
*values*, not CSS *functions* — there is no production for `(`, so
`classDef fmt fill:var(--surface-2)` dies with `got '(-'` and the whole
diagram becomes a parse-error card. `__okuResolveCssVars` substitutes
the computed value before Mermaid sees the source, at EVERY hand-off
(parse, first render, and the re-render on `oku:theme-changed`) — not in
the source cleaning, because `_src` must keep the token the author
wrote. Resolving at hand-off is what makes the colour track the theme
instead of freezing at first paint. A token that resolves to nothing is
left as written: the parse error then names the token, which is more use
than a silent substitution rendering the wrong colour.

**Hand-drawn figures get their colour from the kit.** An author who
draws their own SVG — in an HTML island; there is no `svg` fence, the
`svg` block kind is reachable only from a JSON page — reaches
for `.okt-diag-node` / `-edge` / `-arrow` / `-label` / `-group` (each
with `ok` / `warn` / `fail` / `accent` / `plain` / `soft` / `mono`
modifiers) and `.okt-diag-fill-1..10` for the chart ramp. Every one is
driven by a token, so the figure follows the page accent and both
themes. A hex literal is how a figure ends up invisible in the theme
nobody was looking at; `island-hand-styled` says so and the message
names these classes. Both halves are pinned by
`test_the_kit_gives_a_hand_drawn_svg_somewhere_to_get_colour` — a
vocabulary nothing points at goes unused, and a check that says "use
the classes" without naming them is one authors ignore.

**Timeline is not step-flow, and the difference is the point.** A
step-flow is a procedure the reader is meant to follow, so every step
is equally true. A timeline is a record of what happened, and an entry
on it can be a claim that was later dropped — which is why its dot
carries a status (`note` / `done` / `open` / `dropped`) and a step
numeral does not. The status carries the colour, the author's `label`
carries the word ("claim #1", "2026-03-04", "v0.4.0"), so a new kind of
entry never needs a new colour. The rail and the dots are positioned by
two independent rules; `test_every_timeline_dot_sits_on_the_rail` and
its narrow-width twin measure them onto the same axis, because tuning
the list padding without the dot offset is the failure and it only
shows below 560px.

**A copy region hands over the source, not the DOM.** All three formats
come from re-rendering the author's markdown into a detached host.
Reading the visible region would hand over the line-number gutter, the
fold markers, the kit's own copy button and, in a diffed pair, the
`<del>` / `<ins>` marks — rendering from source is what makes those
marks safe to draw at all. **Markdown is the source verbatim**:
re-serialising the DOM gives back *a* markdown, not *the* one, and the
round trip is the whole reason that format is offered. Rich is a
`ClipboardItem` carrying `text/html` AND `text/plain` so a paste into a
plain field still lands, with every attribute stripped but a per-tag
keep-list — the target applies its own styles, and `class="okt-card"`
arriving in a wiki looks pasted in and follows no theme. The `before`
half offers plain text alone, because its job is to be *found* in the
target document and no search box takes rich text. Held by
`test_copy_region.py`.

The diff is word-level and on by default; `"diff": false` is for a
rewrite rather than an edit. Contiguous changed words become ONE mark,
not one per word — three abutting boxes read as three separate edits and
the reader then looks for three. Text inside `<pre>` is deliberately
skipped: Prism rewrites a block from its own text and the line-wrap pass
rebuilds its innerHTML, so a mark there would vanish on the next pass.
Inline `<code>` is diffed.

**Quoted content is not the kit's words.** A copy region's body carries
`data-oku-verbatim`, and `localize()` returns early inside it. Without
that, a translated page rewrites a paragraph the reader is about to
paste somewhere else, because it happened to match a string-table key.

**A table copies to two destinations, and one attribute names which.**
TSV goes to a spreadsheet; GFM goes to a pull request, an issue or
another markdown document — and that second one had no button, so the
only way out of the page was to retype the table. Both come off ONE
reading of the live table, so a filtered table copies the rows on screen
in either format and the two never disagree about which rows those are.
The buttons are `data-copy="tsv"` and `data-copy="md"`, not a second
attribute name: the toolbar sizes and orders its icons through
`[data-copy]`, and a button called `data-copy-md` fell out of every rule
in that list — a 22x10 box around a 0x0 icon. Held by
`test_table_copy_formats.py`.

**A word a reader might also write cannot be a string-table key.** The
localize walk matches a key against the leaf text of every descendant of
an `.okt-*` host, and author content lives there too. The comment used to
say author prose was "unreachable twice over"; it is not. Measured on
this repo's own docs, the single word `Charts` as a key would rewrite 18
places — a page title in the tree, an `<h2>`, a `<tspan>` inside a
diagram. So the rail's landmark words (`Chart`, `Table`, `Section`,
`Figure`, …) go in under a `rail:` prefix that no author writes, reached
through `railKind()`, which falls back to the English word rather than to
the key. `test_i18n_coverage.py` derives the required set from
`RAIL_FIGURES` itself — a new rail figure fails on the day it is added,
not the day someone remembers — and asserts no bare rail word is a key;
`test_i18n_runtime.py` injects those words into author content, runs the
pass by hand, and requires them to come through unchanged.

Until then the rail was English on every page: `tipKind` was interpolated
raw into `Jump to {0} in {1}`, so a Turkish page read `Chart` inside a
Turkish sentence, and the tooltip is built on hover — after the one-shot
localize pass has already run, which is why the DOM walk was never going
to reach it.

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

**mermaid and Prism are fetched once, not per page.** Both were loaded
from a CDN at runtime, so a built page with no network drew no diagrams
and highlighted no code. `oku vendor` fetches them into
`kit/vendor/` (gitignored, not in the wheel — it is a cache), `oku build`
does it automatically the first time, and the build copies one shared
`_oku/vendor/` beside the output. Every loader tries that copy and falls
back to the CDN, so a page that travels away from its vendor directory
still works with a network.

**They are deliberately NOT inlined.** mermaid is 3.3 MB against a 1.1 MB
standalone page, and a tree would carry one copy per page that draws
anything. Offline does not require a single file — it requires the bytes
to be reachable, which one shared directory achieves at 1/38th the cost
here. `test_vendor_offline.py` blocks every origin and asserts the
diagram draws, the code is coloured, and nothing reached a CDN; the last
one matters because the fallback would otherwise mask a broken local
copy. It also asserts the page did NOT grow, which is what catches
someone "fixing" offline support by inlining.

**`__okuVendorPath()` is a function; `window.__okuVendorBase` is a
string.** The names differ deliberately. A top-level
`function __okuVendorBase()` and the injected
`window.__okuVendorBase = "../_oku/vendor/"` share one global binding,
and whichever loads second wins — which presented as every dependency
failing to load, including the line numbers that had nothing to do with
the change.

**Seven sources decide what a block kind is, and they cannot see each
other.** `_FENCE_KINDS` (cli) and `FENCE_KINDS` (renderer.js) say what
lifts; `$defs` says what validates; the `case` dispatch says what draws;
`_KNOWN_BLOCK_KINDS` says what the lint accepts; `examples.json` says
what `oku spec` can answer for; and the `required` map at the foot of
renderer.js mirrors the schema's own `required` arrays. A kind in some
and not the others is never a crash — it is a fence that lifts into a
block nothing validates, or a linter rejecting a page the kit draws.
Both have shipped: `oku-chart-grid` (rejected by the lint, drawn by the
renderer) and `oku-tldr` (documented fence, validated by nothing).

`test_authority_agreement.py` holds them against each other, and
`test_block_contract.py` covers the required-field mirror. The rule:
**anything an author can write must validate, draw, and be printable by
`oku spec`.** Adding a primitive means adding it in all of them — the
tests name which one you missed.

**`info-tip` is a fence now.** It was drawn by the renderer, documented
in the briefing as the canonical wrong-but-valid example, and reachable
from nowhere: no fence, no `$defs`, and the v1 shim turns legacy ones
into markdown. `docs/reference.md` demonstrated it with a `> [!TIP]`
admonition standing in for the real thing. It has a schema entry and a
fence, so the primitive the renderer implements is one an author can
actually write.

## Common pitfalls

- **`page.route("https://**", …)` matches NOTHING.** Measured: the
  callback fires 0 times and the CDN answers 200. `**/*` and
  `https://*/**` both work; filter inside the handler. This is why
  `test_vendor_offline.py` — the file CLAUDE.md cited as proof that a
  built page works with no network — passed for months against a live
  CDN, with its "nothing reached a CDN" assertion true only because the
  callback that records the reaching never ran. **A test that blocks,
  denies or intercepts must assert that it actually did**: count the
  interceptions and require the count, or the test degrades into a test
  of the happy path without anyone editing it.

- **`dist/site` and `dist/standalone` are two recipes, and only one of
  them was covered.** `build_standalone` copied `kit/vendor/`, injected
  the manifest, the vendor base, the kit bundle and the string table;
  `build_site` copied none of it and `oku verify` never opened that tree
  at all. A deployed site therefore drew no diagrams and highlighted no
  code without internet, and its search index held titles only. `oku
  verify` walks BOTH trees now (site over a local HTTP server, because
  those pages fetch), and `test_delivery_parity.py` diffs the two —
  primitive tally, text length, controls, tree, TOC, rail — so a block
  that renders in one tree and not the other fails a test rather than
  being reported by a reader.

- **A standalone page runs chrome.js with `document.body` still null,
  because an inline script ignores `defer`.** The stub loads the kit as
  `<script src="_oku/chrome.js" defer>`, so under `oku serve` and in
  `dist/site` every top-level statement runs against a parsed document.
  `build_standalone` replaces that tag with the file's contents, and
  `defer` means nothing on an inline script — the same statements now run
  mid-`<head>`. Top-level code that touches the DOM must go through the
  `document.readyState === 'loading'` check the file uses everywhere
  else; one line that didn't (the drawer-pin restore) threw, and because
  the throw was top-level the rest of the kit never ran: no chrome
  cluster, no sidebar, not one control. It reached only readers who had
  pinned the drawer — file:// shares one localStorage across a whole
  tree, so after that every standalone page they opened was bare — and
  they could not undo it, since unpinning needs the button that was lost
  with the rest. Held by `test_standalone_stored_state.py`, which seeds
  every key the kit persists (the list is derived from the source, so a
  new key arrives as a failure) and requires the chrome to be built
  anyway.

- **Stale chrome.js in the browser.** The CDN-loaded Prism autoloader
  fires `complete` twice per block (once before the language module
  arrives, once after). The line-wrap / fold pass guards against the
  second pass via `code.querySelector('.okt-code-line')` — DO NOT
  guard with a one-shot `data-` attribute; the second Prism pass
  wipes the spans, and a one-shot guard then refuses to re-apply.

- **Prism rewrites a block from its own text, so nothing that is not
  code may be inside `pre code` when it runs.** `highlightElement`
  reads `element.textContent` and writes `element.innerHTML`. Any
  decoration living inside the code element is read back as program
  text on the next pass: `<oku-annotated-code>` puts its marker chips
  and hover tooltips there, and a second pass highlighted the
  commentary as source and wiped the chips — reported from another
  project as a page inflated by 25,000px, reproduced here at 3366px
  for a three-line program.

  Two rules, and they are separate because they fix different halves:

  1. **A caller that decorates the result uses
     `__prismLoader.highlightOnce(root, lang)`, never `highlightAll`.**
     highlightAll hands the block to the autoloader, whose promise
     resolves when the highlight was *requested* — inside the window
     before the grammar lands and the block is read again. highlightOnce
     loads the grammar first, so one pass runs and there is no second
     read to lose the race to.
  2. **A block that has finished decorating sets `_okuMarkersBuilt`,
     and the `before-sanity-check` hook in `__prismLoader` blanks
     `env.code` for it.** More than one driver highlights a given block
     — the element does its own, the page-level sweep runs on
     `oku:rendered` — and neither sees the other's timing, so the guard
     cannot live at a call site. Blanking `env.code` makes Prism fire
     `complete` and return without touching innerHTML, which is the
     same suppression the autoloader itself uses.

  Every annotated block in this repo's docs is **javascript**, whose
  grammar the loader preloads, so it takes one pass and the defect was
  invisible here for as long as it existed. `test_annotated_code_
  highlighting.py` uses python deliberately.

  The related trap: a `(1)` marker in live code is split by Prism into
  `(`, `1` and `)` in three token elements, so a per-text-node regex
  matched nothing and silently left `(1)` in the program. `injectMarkers`
  matches the flattened text and splices with a Range — the same shape
  `markNeedleInScope` already used next to it.

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

- **There is exactly one way to write a TL;DR: `> [!TLDR]`.** A
  ```oku-tldr fence used to lift into a typed block that no `$defs`
  entry validated and no renderer case drew — so the documented fence
  could not work, and nothing failed because nothing in this repo used
  it. The fence is gone; `_MARKDOWN_FORM_OF` names the survivor, so an
  author who reaches for it is told what to write instead of reading a
  list that lacks what they typed.

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
