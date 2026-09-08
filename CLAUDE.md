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
| `chrome.js` | Custom Elements (chart with 53 render modes, diagram, live-snippet, annotated-code, glossary-term, ext-ref, page-chrome / page-nav / page-toc), init-time DOM enhancement (table chrome, code fold, line numbers, sidebar wiring, bar-chart hover/click-pin/legend toggle), Prism + Mermaid lazy loaders, glossary tooltip controller, lightbox with pan/zoom/pinch fullscreen, the top rail (progress + landmark minimap), the presentation menu (text scale, width, theme, language, placeholders), the markdown viewer. ~13k LoC. |
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
./ctl deploy    # the whole procedure, and it verifies itself
```

**Use `./ctl deploy`. Do not hand anyone the raw `uv tool install`
line** — it has a trap in it, and a command with a trap is one nobody
should be retyping from memory. `--force` alone is NOT enough: uv reuses
the cached wheel when the version string in `pyproject.toml` has not
changed, so the tool silently stays on the old kit while reporting a
successful install. `./ctl deploy` passes `--no-cache`, then compares
the repo's kit stamp against the one the installed tool reports and
exits non-zero when they differ. That comparison is the point — a stale
global tool reports success and then builds other projects with the old
kit, so the symptom arrives later, somewhere else, as "the kit
regressed".

`./ctl status` answers the same question without reinstalling.
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
- **One button holds every presentation choice.** Text size, column
  width, theme, language and placeholders are rows in the menu behind
  `.menu-toggle`; the corner keeps search and the warning indicator.
  Held by `test_chrome_menu.py`. → [why](PRESENTATION-RULES.md#one-button-holds-every-presentation-choice)
- **The reader can make the document bigger, and the document is all of
  it.** `zoom` on the reading column, so charts and diagrams grow with
  the prose. Held by `test_text_scale.py`. → [why](PRESENTATION-RULES.md#the-reader-can-make-the-document-bigger)
- **The width control has three stops, and you can see which one you are in.** Held by `test_reader_can_cycle_content_width`. → [why](PRESENTATION-RULES.md#the-width-control-has-three-stops-and-the-icon-h)
- **The theme control has three stops, and System is the only auto there is.** Held by `test_theme_modes.py`. → [why](PRESENTATION-RULES.md#the-theme-control-has-three-stops-and-system-is-o)
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

**A manifest path is in URL space, and `source` is not.** Every `path`
becomes an href and is compared against `location.pathname`, which the
browser hands back percent-encoded. Left raw, `notes#1.md` built into
`notes#1.html` and the href pointed at `notes` with the fragment `1`:
the page was written, indexed and listed, and the row that named it went
somewhere else. `?` did the same with a query string, and a space ended
the target of the markdown link in llms.txt so the rest of the filename
became a link title. Nothing failed anywhere.

`_url_path` encodes per SEGMENT, so the separators survive, and it runs
on every path rather than only the awkward ones — a name with no special
character encodes to itself. It runs on `parent` too, because a path and
the parent it groups under are compared as strings, and encoding one of
them loses the row. It runs ONCE: `path_parent` is already in URL space
and an author's own `parent:` is not, and putting both through the
encoder turned `sub#dir` into `sub%2523dir`. `source` stays raw — it is
for a human with an editor, and an encoded path there is one the reader
decodes by hand. Held by `test_url_safe_paths.py` and
`browser/test_awkward_filenames.py`, the second one because the chain
that matters is href → request → the server's `unquote` → the file, and
only a browser walks all of it.

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
original's** — `{#id}` is copied verbatim, and a heading whose title
differs between the two languages needs the id pinned on both sides.
Pinning is no longer forced by the slugifier: it keeps the letters now
(see the slug rule below), so a Turkish heading gets a Turkish id and a
translated page that reuses the original's headings needs nothing.

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
The fixed 44px boxes float over the top of the reading column at every
scroll position. They sit at a 0.32 floor and rise to full on a cosine
falloff over 190px of pointer distance, measured **to the button's box**
(point-to-rect, zero inside) so a button you are about to click is not
still dim. Per button, not per region: approaching the presentation
menu does not light the Contents button. Three things keep it from becoming
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

A layout is still something the page hands to everyone it reaches, so a
project that ships pages off the machine sets `"rebuild_command": false`
in `kit.json` and the command goes, taking the button with it — the
footer already draws nothing when `cmd` is absent, so there is no
disabled state to explain. Everything that is about the ARTIFACT rather
than about where it was made stays: version, kit stamp, build age, drift
warning. On by default, and that is the load-bearing half — the defect
this whole mechanism exists for is a page that could not say how old it
was, and `cmd` is the only field that names a machine.

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

**A tag the kit calls inline is a tag the kit draws.** `INLINE_HTML_TAGS`
answers one question, so it has to answer both halves of it: a tag on
that list never opens an island — a paragraph starting `<kbd>` stays
prose — AND parseInline builds an element for it where it stands. The
pattern is spliced from the list at `__TAGS__` rather than repeating it,
because a repeat is what happened: the island rule listed fourteen tags,
the parser drew nine, and `a` / `code` / `em` / `strong` sat in the gap
as prose nobody drew. A delivered page read
`<code>ilimler→ilimleri</code>` with the angle brackets showing, inside
a compare-grid card, past a clean `oku check --strict`. `b` and `i` were
on neither list, so one tag meant two things — an island at the start of
a paragraph, literal text one word later. The pass-through REBUILDS: the
element is made by name, the body parsed as markdown (CommonMark's rule
between raw tags), and only `title` survives from the attributes, plus
`href` on an `<a>` through renderLink and therefore through `safeUrl`.
Held by `test_inline_html.py`, whose case list is read out of
INLINE_HTML_TAGS at collection time, and by `test_authority_agreement`.

There is no check for a tag OUTSIDE the list, deliberately. Prose here
writes `<name>`, `<rel-path>` and `<docs>` as metavariables, and a check
cannot tell those from a typo'd tag without guessing.

**A viewed document is read, not run.** An island in a PAGE keeps full
capability — the author wrote it into their own page and `oku check`
lints it as page content. The markdown viewer renders something else: a
file the page merely LINKS to, into the page's own document. Measured
from a linked `.md`: its `<script>` set a global on the host page,
rewrote `document.title`, and wrote the kit's own `oku-theme-mode` key
in localStorage — a setting the reader cannot see change and would not
think to undo. An `<img onerror>` fired in the same pass. `makeInert`
in renderer.js drops what could run (an executable `<script>`, an `on*`
attribute, a URL `safeUrl` refuses, `iframe` / `frame` / `object` /
`embed` / `link`) and the viewer says how many went, because a silent
removal reads as a rendering bug to the author whose island stopped
working.

**A `<style>` is confined rather than dropped.** It does not run, which
is why it survived the first pass, and it still reaches the whole
document it is inserted into — which is the reader's page. `body {
display: none }` in a linked file blanked the page that opened it, and
the control that would close the viewer went with everything else; the
module's own fixture cannot even reach the viewer without the fix, so
all fifteen of its tests error rather than fail. Dropping the sheet is
the opposite failure, so the sheet is wrapped in ONE CSS nesting block
keyed to a `data-oku-inert` mark on the host — the browser's own parser
takes the comma lists, the `:not()`, the `@media` and the nested rules
that a rule-by-rule CSSOM rewrite would silently drop. A selector naming
`:root`, `html` or `body` becomes a descendant selector matching
nothing, which is the answer and not a limitation: those three ARE the
page that opened the file. `<link>` cannot be confined — a cross-origin
sheet has no readable rules — and every `rel` is a request made on
behalf of a reader who only opened a file, so it goes with the framing
elements.

Two things about it are load-bearing. **Only executable scripts go**: a
typed block carries its payload in a `text/x-mermaid`, `text/x-code`,
`application/json` or `text/plain` holder, so a rule taking every
script would gut every diagram and chart in the document. **It runs
before the rebase**, not after — `safeUrl` refuses `file:`, and
rebasing turns every relative href in a viewed document into a `file:`
URL on a standalone page, so the later placement strips every link on
the one delivery mode with no other way to reach the sibling. Held by
`test_viewed_document_is_inert.py`, whose served and standalone halves
each pin one of those.

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

**A typed fence inside an island splits the island's own block.**
`md_to_v2_page` lifts an `oku-*` fence into its own `b[]` entry, so the
prose around it becomes two strings with a typed object between them —
and both the renderer's stack and the lint's were per-string, so the
`</details>` was scanned in a later block than the `<details>` that
opened it. One cause, two failures, and only one of them was reported.
The lint said `island-unclosed` at error severity and refused every page
in the tree, on a page whose tags are balanced at column 0. The renderer,
measured before the fix, had already put the figure and every paragraph
after it OUTSIDE the island — an island the author wrote a chart into
rendered with the chart beside it, styled as though it had never
belonged, which is the same silent loss the blank-line rule above exists
to prevent. The stacks now outlive one block: the renderer carries
`openIsland` across the page's blocks and appends a typed block into
whatever is open, and `_lint_md_string` takes an `open_els` the caller
owns and reports leftovers at the page end. Both reset at `##`, which is
the boundary the renderer already resets on. Held by
`test_check.py::TestATypedFenceInsideAnIsland` and by the `typed` case in
`test_html_island_spans_blank_lines.py`.

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

**And it travels only as far as the project owns it.** "Above the tree
being built" and "outside the project" are two questions, and the build
only ever asked the first — so `![x](../../other-repo/shot.png)` was
base64'd into a standalone page in silence, past a clean `oku check`. A
standalone page carries BYTES, which is what makes an image above the
docs root legitimate (`../shots/x.png` in a repo that keeps screenshots
beside its docs) and what makes one past the project fence a file handed
to whoever the page is sent to. `asset_within_project` is the same fence
`#f/` answers to — nearest `.git`, else `kit.json` — asked through the
same `_asset_hrefs` scanner the build carries with, so the check reports
exactly what the build would publish rather than approximating it with a
second set of regexes. `oku check` says `image-outside`; the build says
so on the line where it declines; and the reference stays in the page,
because losing what the author wrote is never the better failure. Held
by the fence section of `test_build_carries_assets.py`.

**And a code the check emits is a code `docs/cli.md` explains.** The
severity table is the eighth source of the kind
`test_authority_agreement.py` exists for — three copies of one list
(the CLI, `cli.md`, `cli.tr.md`), none able to see the others. Both
directions are held: a code missing from the table is a warning whose
only explanation is the message that fired, and a code in the table that
nothing emits is a reader looking for behaviour that was renamed out
from under them. Four call shapes reach an issue list (`add(...)`, a
`(severity, code, ...)` tuple, the chart rule's local `bad(...)`, and a
dict literal), and the reverse direction is what found the last two —
a scan seeing only the first two reported `chart-*`, `json-parse-failed`
and `shadowed-source` as documented-but-dead.

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

The kit had the substitution and no way to notice its absence:
`island-hand-styled` walked only string blocks, and a mermaid fence lifts
to a typed `diagram` block before the lint gets there — so this repo's
own architecture page carried nine hardcoded `classDef` fills past
`oku check --strict`, pale plates that stayed pale on a dark page under a
label that inverted without them. The lint reads a diagram's `classDef` /
`style` / `linkStyle` lines and its `%%{init}%%` directive, and only
those: a `#3` in a node label is a number, and a check that guesses is
one authors ignore. The vocabulary it names is
`fill:var(--series-N-soft),stroke:var(--series-N),color:var(--text)`.
**The ramp is for marks, and the plates are a second set** — a node is
something with a label written on it, and `--series-3` under `--text` is
dark-on-dark in one theme and light-on-light in the other. Ten
`--series-N-soft` per theme, pale in light and deep in dark; tokens
rather than a `color-mix()` at the call site, because Mermaid's grammar
has no `(`. Held by `test_check_presentation.py::TestMermaidStyling`,
by `test_colour_contrast.py` (the label clears 4.5:1 on every plate in
both themes, the stroke 3:1 on its own fill) and by
`browser/test_diagram_tokens.py`.

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

**A heading's id is one rule, computed in three places.** `_md_slug` in
cli.py, `slugify` in renderer.js and `slugify` in chrome.js must give
the same answer, because `oku check` validates a page's `#fragment`
links against the first, the second is the id the reader lands on, and
the third names the h3s under a section. They disagreed for anything not
written in English: Python's `\w` is Unicode-aware, renderer.js stripped
`[^a-z0-9\s-]`, and chrome.js named six Turkish letters explicitly —
which is what patching one language at a time looks like.

What that cost: `## Özet` got the id `zet`; `## 概述` got the empty string
and fell back to a positional `sec-3` that MOVES when a section is
inserted above it; two Chinese h3s under one section got the same id;
`[Özet](#özet)` passed `oku check` and landed nowhere; and in the other
direction the check reported a `duplicate-anchor` between an h2 and an
h3 whose DOM ids differ, refusing to build a page that was fine. The
escape hatch had the same defect one layer up — the renderer's explicit
`\{#([\w-]+)\}` used JavaScript's ASCII `\w`, so `{#a-özet}` missed the
group and rendered as literal text inside the heading.

The rule now: lowercase, **compose to NFC**, drop everything that is not
a letter, number, space, `_` or `-`, whitespace runs to `-`, hyphen runs
to `-`, trim. NFC is what makes one title give one id whichever
normalisation form it was typed in; dropping what survives composition
is what turns a lowercased `İ` — `i` plus a combining dot — into the
plain `i` a Turkish author would type into a link. An empty result is
the caller's to name: `"section"` for the check, a positional id for the
renderer, which cannot collide. Not GitHub's slugger, which keeps runs
of hyphens (`A - B` is `a-b` here, `a---b` there); that predates this and
changing it would move every existing id. Held end to end by
`test_heading_slug.py` — the id Python predicts is read off the rendered
DOM for a heading in nine scripts, and every authored link must land.

**Never do index arithmetic on a case-folded copy.** Neither
`str.lower()` nor `String.prototype.toLowerCase()` preserves length — a
Turkish `İ` lowercases to `i` plus a combining dot — so an index found
in the lowered copy is not an index into the text, and every position
past the first one is off by one. Two sites had it. A test helper
searched `html.lower().find("</script")` and sliced the original, which
had been correct for as long as no kit file contained an `İ` and
presented as the page JSON failing to parse. And the in-page search
found the query in the lowered body, sliced the body for the excerpt,
then searched the excerpt's own lowered copy to place `<mark>` — so the
window drifted one character per expanding character before the match
and the mark drifted with it, reading `ayıt ` for a search of `kayıt`.
`__okuLowerWithMap` builds the lowered text and the map back in one
pass, and only when lowercasing actually changed the length, so the
English path pays nothing. Where the mark sits in the excerpt is now
arithmetic rather than a second search: a second `indexOf` is a second
chance to land on the wrong character. Held by `test_search_excerpt.py`,
which pins the mark's text AND the 40 characters of lead — the drift
stated as a number, because an assertion about what the excerpt contains
cannot see a window that is two characters out.

**Every kit box that holds author text may be narrower than its longest
word.** A grid or flex item defaults to `min-width: auto`, so it refuses
to shrink below the widest unbreakable run inside it — and author text
holds those constantly: a class name, a config key, a path, a URL, a
percent-encoded string. One of them in a card and the whole PAGE scrolls
sideways. The fix is two declarations that go together: `min-width: 0`
on the item so it can track its column, and `overflow-wrap: anywhere` on
the text so the word breaks. `break-word` does not save it — that wraps
a word only once the box is narrow, and the box is sized FROM the word;
only `anywhere` lowers the min-content size the parent measures. An
inline-block is the same defect wearing a different hat: it sizes to
max-content, so it needs `max-width: 100%` beside the wrap. And
`white-space: nowrap` cannot be rescued by either — with wrapping
switched off there is no break opportunity to take, so a chip that must
survive a long label gives up `nowrap` and relies on being `flex: none`
to keep short labels on one line.

Held by `test_narrow_no_sideways_scroll.py`, whose second page is
derived from `kit/schema/examples.json` — every shipped example with the
long token appended to every string it carries — and measured at 1440px
as well as 360px and 320px. Desktop matters: a KPI numeral put the
page's scrollWidth at 1818 against a 1440px viewport, and a suite that
only measured narrow viewports would have stayed green while a desktop
reader scrolled sideways.

**A mark the kit draws never gets a negative extent.** Chrome refuses a
negative `width` outright — the rect is not drawn at all, and the console
says `<rect> attribute width: A negative value is not valid`, which names
the attribute and not the chart, so the report that arrives says the kit
broke. One page of adversarial payloads produced 904 of those lines. Two
families reach it and both come from ordinary work: a gap subtracted from
a cell thinner than the gap — 900 bins across a 576px plot give each bin
0.64px, and the 1px inter-bar gap takes the width to -0.36 — and a pair
written the wrong way round (`q3` below `q1`, `high` below `low`, `end`
before `start`), where the span is the difference of two scaled
coordinates. `markSpan(a, b, gap)` orders the pair, never lets the gap
eat more than half the span, and floors the result at `MIN_MARK_PX`;
`markSize` is the one-sided half. Ten call sites use them. The floor is
sub-pixel (0.5) deliberately — at 900 bins the honest picture IS a dense
band and a 1px floor would make every bar overlap its neighbour — but
zero is not an option either, because a rect of width 0 draws nothing and
cannot be hovered.

The inverted pair is ALSO a data error the author can fix, and the
renderer drawing it ordered is exactly what hides it: the figure looks
right and reads wrong. So `oku check` reports `chart-inverted-range`
naming the row and the two fields, for box-plot, range-bar, histogram,
gantt and candlestick. Equality passes throughout — a zero-width bin is
degenerate, not backwards, and a check that guesses at intent is one
authors learn to ignore. Held by `test_chart_degenerate_payloads.py`,
whose cases are derived from `kit/schema/examples.json` rather than
listed: every shipped example mutated four ways, so a chart type added
tomorrow is covered on the day it lands.

**A figure that takes the pointer answers it, and the answer describes
the picture.** Every chart type must produce a reading for a reader who
points at it — from the mark if it draws marks, and from the cursor if
it does not. `browser/test_hover_shows_a_reading.py` is a sweep derived
from `kit/schema/examples.json` and it no longer skips: a chart with no
mark falls through to its own cursor and must read out there. Two shapes
had neither. A violin drew a median line and an IQR box and named
neither, in two renderers that share nothing — the value runs along x in
one and up y in the other, and the vertical one wired no cursor at all,
so it answered with nothing. A density plot is one curve with no mark to
hover, and its cursor swept the plot reporting silence.

**What the reading contains is the other half.** It says what the reader
is looking at, in the units the picture is drawn in. Density reports its
height as a share of its own peak, because the plotted height IS
`d / maxDensity` — a raw KDE density in units of 1/x answers a question
nobody asked, and `fmtNum` renders 0.0043 as `0.00`, so the honest
number is also the unformattable one. Where two renderers give the same
reading it is built ONCE (`okuDistributionPayload`): two copies of a
chart's reading is how two orientations stop agreeing about what the
chart says.

A chart may legitimately have both paths — marks that read and a cursor
that only aligns. Beeswarm is the pattern: the dots carry the payload
and the line is an alignment aid. That only works because the tooltip
has an owner (see the single-owner pitfall below); before that, wiring
both meant the cursor deleted the mark's reading.

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

**A project may declare .gitignore its skip list, and must ask for
it.** `kit.json`'s `skip_gitignored: true` adds everything git ignores to
the walk's prune set — one `git ls-files -o -i --exclude-standard
--directory` per root, cached, `--directory` collapsing a wholly-ignored
subtree to one entry so the walk prunes instead of stat-ing it. It exists
because `SKIP_DIRS` can only list the names somebody remembered, and the
names that matter differ per project: `tmp`, `build`, `out`, `target`, a
recovered dataset, a scratch copy of the file being edited. One of those
is how it was found — a backup of `CLAUDE.md` under `tmp/` was walked,
turned into a page, and reported as fifteen `unresolved-link` warnings
against links that are correct where the original sits.

**Off by default, and that is the load-bearing part.** Gitignore is a
version-control policy; this is a publication policy. Plenty of projects
gitignore generated pages they fully intend to publish, and with the flag
on, editing `.gitignore` silently changes what the site contains — action
at a distance from a file nobody thinks of as build configuration. A
project that says nothing gets exactly the old walk, and `skip_dirs`
remains the direct way to say it, needing no git at all.

Switched on, the failure it introduces is a page that should build going
missing in silence, so: it stands down where it cannot know better (no
git, no repository, or a root that is ITSELF ignored — git answers `./`
there and everything below would look like junk), and it names itself
where it acts, one line counting what git pruned and listing only paths
the other rules would have walked. `dist` and `.idea` in that line would
be noise, and a line that is mostly noise is one nobody reads when it
finally matters. Held by `test_gitignored_walk.py`, whose first two cases
are the default path.

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

**A path in a document is a thing the reader can look inside.**
`[label](#f/<path>)` renders a chip: hover for a preview, click for the
whole file, copy button for the path. It exists because a path in a code
span is a dead end — the reader leaves the page, finds the file, comes
back — and that is what every document does with the paths it mentions.

**Two bases, page first then the project root.** A relative path in a
markdown file means "beside this file" everywhere else, so that is tried
first and an existing reference cannot change meaning because a file of
the same name appeared at the root. But prose does not write paths that
way: a sentence about `src/oku/cli.py` says it from the root, which is
how the reader would type it into an editor, and from `docs/reference.md`
that resolved nowhere — the chip rendered and its preview never opened.
The fallback only runs where the answer was already `missing`, and a
failure still reports the page-relative attempt, because that is what the
author wrote.

**A primitive nobody can discover is not a primitive, and telling an
author about one is only half of discovery.** Four surfaces now: the
skill briefing carries the decision rule (use it wherever you would have
put a path in a code span), `oku spec` lists the three inline kinds
beside the fences and `oku spec filepath` prints the syntax WITH a note
on when to reach for it, `oku check` says `path-in-code-span` when a code
span names a file that is really there, and **`oku check --fix` does the
rewrite**.

That last one is what changed the third. The nudge was an `info`, on the
reasoning that the check cannot tell "this file" from "a file of that
name" — but the gate had already answered that: `_looks_like_a_path`
requires a SEPARATOR, so a page telling a reader to create a `kit.json`
is not judged at all, and the file must additionally resolve inside the
project. What info bought instead was invisibility. An info note is one
summary line naming the code, so the rule reached nobody: measured, this
repo's own reference page named `src/oku/cli.py` in prose and five other
pages did the same, ten spans that had survived every build. It is a
`warning` now, printed by default and answerable by `--strict`.

Raising a severity without a mechanical remedy is just nagging, which is
why the two shipped together. `--fix` is defined as APPLYING WHAT THE
REPORT SAID — it takes the issue list rather than walking the tree again,
because which pages qualify has several answers already baked into the
check (a materialised README is exempt, a reference outside the project
does not resolve, a page behind `skip_gitignored` was never walked) and a
second walk is a second set of answers waiting to diverge. It rewrites
prose, GFM cells and `oku-*` payloads, leaves front matter, plain fences,
island raw-text regions and existing links alone, re-parses any fence it
touched, and is idempotent because a chip's label is a code span inside a
link construct. Held by `test_filepath_refs.py`.

**A materialised page is never nudged.** A README or a CLAUDE.md renders
through the kit and is also read on GitHub, where `#f/…` is a link to an
anchor that does not exist — the one place this rule would make the file
worse.

`_INLINE_KINDS` in cli.py is the authority for the set, held against
renderer.js's own prefix dispatch by `test_authority_agreement`.

**The bytes travel inside the page, and that is what shapes the rest.**
No delivery mode can fetch the file when the reader clicks: `oku serve`
and `dist/site` serve the docs tree while the references worth making
point outside it (`../src/oku/cli.py`), and a standalone page is opened
over `file://`, where fetch is refused before a request is made. So
`_page_from_source_file` resolves every reference once and puts the
result in `m._files`, keyed by the path AS AUTHORED — the same key the
element carries and the runtime looks up, so the two cannot drift by
disagreeing about how to normalise a path. `m._files` rides in the page
dict, which is the one thing all three modes already carry, and it is
computed at the ONE point a page dict is made, so serve, check and both
build trees get it without three call sites to keep in step.

Two consequences are decisions. **The project root is the fence**:
nearest ancestor with `.git`, else with `kit.json`. Not the docs root —
this repo has `docs/kit.json`, and a docs-rooted fence would refuse
`../src/oku/cli.py`, the reference an author most wants. The fence is
not about trusting the author, who typed the path; it is about what the
page PUBLISHES, since the build copies those bytes into an artifact that
gets sent to people. **A reference that does not resolve still renders a
chip that still copies** — the failure mode has to be "the preview does
not open", never "the page lost the reference the author wrote".
`filepath-missing`, `filepath-outside` and `filepath-not-carried` say so
at build time instead. Held by `test_filepath.py`, which runs against the
standalone build because it is the mode with the least to work with.

**A card appears when the pointer arrives, not when the page moves under
it.** `mouseenter` fires when a layer above an element goes away, so
closing the popup a chip opened put that chip's card back under a cursor
that never moved — a dismissed popup returning as a tooltip. The
controller ignores an enter with no `mousemove` behind it. The same pass
made the focus branch `:focus-visible` only (a mouse click focuses too)
and gave every `role="button"` chip a keydown handler, because Enter and
Space fire click on a real `<button>` and on nothing else.

**Focus is a promise, and the kit has broken it three times.** Anything
the kit makes focusable — `tabindex="0"`, `role="button"`, a real
`<button>` it draws — has told the reader there is something to do once
they get there. Three elements took focus and did nothing with it, and
none of the failures is visible to anyone using a pointer:

- the filepath chip carried `role="button"`, was reachable by Tab, and
  could not be opened, because Enter and Space fire click on a real
  `<button>` and on nothing else;
- every network node group carries `tabindex="0"`, so Tab reaches each
  node in the graph, and every key did nothing. Worse than the chip's
  version: dragging a node apart was the whole point of that figure and
  there was no other way to do it, so a reader on a keyboard could look
  at the tangle and nothing else.
- every legend chip on a marimekko, a stream and a sunburst carried
  `tabindex="0"` AND was handed `aria-pressed="false"` by the wiring
  pass, so it announced itself as a toggle button with a state — and
  moved nothing. The three use the shared `_renderSeriesLegend` row,
  whose chips carry `data-series-idx`, and the wiring toggles
  `.okc-series[data-series-idx]`, which none of the three emitted. The
  fix is DOM shape rather than a fourth copy of the toggle: each
  renderer wraps its shapes in the group and the existing wiring, CSS
  and solo behaviour apply unchanged. Two consequences are decisions —
  marimekko paints cells column-first, so its cells are collected per
  series (a group built per column hides a third of a series), and its
  category ticks stay OUTSIDE the groups, because a chart whose axis
  labels fade as you mute is unreadable exactly when the reader is
  comparing what is left.

Two near neighbours, from the lightbox, where the promise is broken
without any element lying about itself. **A control's keys must be bound
where focus actually lands**: the pan/zoom stage listens for `+`, `-`,
`0` and the arrows, and `open()` focused the holder AROUND it, so every
keydown bubbled up and away from the listener — expand a figure, press
`+`, nothing. And **a dialog that says `aria-modal="true"` has to keep
focus**: the close button is drawn before the content, so tabbing
forward left the overlay for the page behind at 39 presses. Both are
invisible to anyone using a pointer, and neither shows up as a control
that does nothing when you press it. Held by
`browser/test_lightbox_navigation.py`.

The check is mechanical and belongs in the browser suite: focus it, press
the keys it implies, assert the same thing the pointer path asserts. Where
both paths exist they go through ONE function — the network's drag and
its arrow-key nudge share a mover, because two copies of "write the
transform, the two data attributes and every touching edge" is one rule
that the second edit stops matching. Held by
`browser/test_filepath.py::test_the_chip_opens_from_the_keyboard`,
`browser/test_network_untangle.py` and
`browser/test_legend_is_a_control.py` — the last one a sweep derived
from `kit/schema/examples.json`, so a chart type added tomorrow is
covered on the day it lands. Measuring first is half the rule: the same
sweep found that donut, pie, waffle and radar — the four the roadmap
asked for — had shipped, and that box-plot has no legend to wire.

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

**The typefaces are vendored too, and they have no CDN behind them.**
`chrome.css` used to open with an `@import` of fonts.googleapis.com, so
every page of every built tree fetched two families from a third party
on load — measured on a standalone page opened over `file://`: three
requests, one to fonts.googleapis.com and two to fonts.gstatic.com. That
is the kit telling Google who is reading a document it was handed, which
is the exact thing the rebuild button refuses to do for its own build
stamp. `oku vendor` fetches four variable woff2 (Inter + JetBrains Mono,
latin + latin-ext) into `vendor/fonts/`, and the `@font-face` rules name
them relative to chrome.css — so serve and `dist/site` resolve them with
nothing injected, and `build_standalone` repoints them at its own
`_oku/vendor/` copy through `_retarget_font_urls`.

Three parts of that are decisions. **latin-ext is not optional**: `ş` and
`ğ` live there, so shipping only latin changes typeface in the middle of
a Turkish word. **No file, no rule** — when the fonts were never fetched
both builds DROP the `@font-face` blocks rather than shipping a URL to a
file they did not carry, because a failed request per page buys nothing
the font-family fallbacks do not already give. And **a missing face
counts as none at all** (`vendor_fonts_present` is all-or-nothing), since
half a set renders one alphabet in Inter and the other in the system
stack, which reads as a rendering bug. Held by
`test_fonts_are_local.py`, which loads both delivered trees with every
non-local origin refused, asserts the route actually fired, and asserts
Turkish letters resolve to a loaded face.

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

- **A Prism grammar asks for a language out of the DOCUMENT's content,
  not out of what the author tagged.** Two 404s per page came from that,
  and neither name is written anywhere in the source. Prism's markdown
  grammar reads a fence's info string inside a markdown SAMPLE and calls
  `autoloader.loadLanguages()` itself, from a `wrap` hook — so a page
  documenting this kit fetched `prism-oku-chart.min.js`, which can never
  exist. And Prism's JavaScript grammar gives a regex literal's source
  the alias `language-regex`, so any page with a regex in a JS block
  asked for a component the kit had not vendored. The page renders and
  most code still highlights, so the only thing that says anything is
  wrong is the reader's console.

  The two get opposite fixes, and the asymmetry is the rule: a name the
  kit CAN serve is served (`regex` is in `_PRISM_LANGS` now), and only a
  name that never could is refused. The refusal wraps
  `autoloader.loadLanguages`, because that is the property the markdown
  grammar calls — neither the autoloader's `complete` hook nor the kit's
  nested-language pass is on that path, and both were written and thrown
  away before a `createElement` stack trace said so. It refuses the
  `oku-` prefix only: that prefix can never be a Prism language, so
  refusing it cannot lose highlighting, where an allow-list would
  silently stop highlighting every alias nobody remembered to add. Held
  by `browser/test_prism_asks_only_for_what_it_has.py`.

  How that measurement went wrong first is worth as much as the fix.
  Three "still 404" readings came from opening
  `docs/dist/standalone/reference.html` while running `oku build` from
  the REPO ROOT, which writes `./dist/` — so the artifact under the
  microscope predated every fix being tested against it. That is the
  defect the build-provenance footer exists for, arriving from the other
  side. Build in the directory you are about to read from.

- **The line splitter rebuilds a block, so it has to rebuild the whole
  tree.** Prism highlights a nested language by itself: its markdown
  grammar puts `token code-block language-bash` inside the single
  `token code` that spans a fenced block, and its markup grammar hands a
  `<script>` / `<style>` body to JavaScript and CSS. The kit's per-line
  pass then threw it away — an element straddling a newline was cloned
  per line with `clone.textContent = seg`, which drops every descendant,
  under a comment calling nested tokens across newlines "very rare". A
  fenced block inside a markdown sample is exactly that, and this repo's
  docs are made of them, so nested highlighting read as a missing
  feature and was a deletion. `emit` recurses now and `newline()` closes
  and reopens the open stack per line. An element whose content ENDS on
  a break prunes at its own close the clone it reopened and never used:
  the per-break pruning only reaches a clone a LATER break arrives at,
  and Prism's `<script>` body span starts and ends with a newline every
  time. Held by `browser/test_nested_code_highlighting.py`.

- **One element with several writers needs a single-owner rule, and the
  hide is where it bites.** A chart has ONE `.okc-tooltip` and three
  things write it: the Cartesian `.okc-dot` path's `showTip`, the
  per-mark anchors' `showRich`, and the vertical cursor's
  `_showCursorTip`. Each hide cleared it unconditionally, so the last
  writer to hide won regardless of who had shown. The cursor's guard
  calls `_hideCursorTip()` on every mousemove landing outside its plot
  band — and a data mark can sit outside the band its own chart
  declares, which is not an edge case: beeswarm's leftmost dot is at
  viewBox x=22 against a band starting at `pad.left`, and bump's top dot
  at y=34 against a band top of 36. Hovering those marks built the right
  tooltip and deleted it in the same gesture. Whoever showed it owns it;
  only the owner may hide it. **All the writers must claim, not the two
  that showed up in the bug** — a rule covering two of three is the same
  defect with a smaller blast radius. The symptom gives nothing away:
  the content is correct, the anchor's events all fire, and the only
  thing missing is a class. Held by
  `browser/test_hover_shows_a_reading.py`.

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
