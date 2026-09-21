---
name: oku
description: >
  Produce a standalone, **visual-first** HTML artifact for long-form
  replies — reviews, feedback rounds, study guides, briefs, design docs.
  Use when the user has 5+ distinct points/questions, asks for "visually
  rich" or "well-designed" output, needs ~1500+ words, or wants a
  document to read alongside another file. Figures are the primary
  communication medium and prose is the caption. You write one markdown
  file — charts, tables, diagrams, comparison grids and step flows are
  typed fences — and the kit renders all the chrome, so there is no CSS
  to write.
  Companion repo: https://github.com/mmdemirbas/html-doc (remote URL
  still on the legacy name).
---

# oku Skill

A pattern for producing standalone, readable HTML artifacts when an
inline reply would be too long or too flat.

## When to fire this skill

- 5+ distinct feedback points or questions in one message.
- Response would span multiple categories
  (corrections + explanations + proposals).
- ~1500+ words of useful depth.
- User is reading a long document and the reply needs to live alongside
  it as a second pane.
- User says "visually rich", "well-designed", "easy to read", "to study",
  or asks for an HTML directly.
- The content needs diagrams, code blocks, comparison tables, or
  progressive disclosure that markdown handles awkwardly.

If the task is a one-off question, a small code change, or a quick
clarification, **skip this skill** — HTML is overkill and slows the user
down.

## Design principles — apply to content, not just visual style

`~/.claude/rules/design-principles.md` and `teaching-order.md` are
loaded every session and carry the four principles, the three layers and
the catalog-vs-teaching decision in full; restating them here costs
tokens on every invocation for what is already in context.

Two things are specific to this skill and are NOT in those files:

- The **content layer** is the load-bearing one here. A page can respect
  every visual principle and still be organised so the reader cannot use
  it — hierarchy means the conclusion precedes its reasoning, not that
  the heading is bigger.
- **Decide catalog or teaching before the first section**, and say which
  in the opening. A guide written in catalog order is complete and
  unusable; that is the single most common failure of a generated
  document. When both are wanted, build two pages and link them.

## Verify after every page edit — non-negotiable

After ANY edit to a `docs/*.md` page source (or any kit schema), run:

```bash
oku check
```

— from the repo root (the local directory is `html-doc/` because the
GitHub remote is still on that URL; the project, CLI and skill all read
`oku`). `oku check` validates every page against
`kit/schema/page.schema.json` and runs the structural / content lint.
Exit code is the only signal that matters; parse the output for the
offending file + path when non-zero.

This applies to:

- Every individual page edit during a multi-edit session — not just
  the last one. Schema errors compound and the path-pointer messages
  get less precise the more invalid blocks coexist.
- Page sources under `docs/*.md` and any starter / template. Typed
  fence payloads all validate against the same schema; the strict-GFM
  subset and HTML-island audit run in the same pass.
- Skill-file authoring (this file): not subject to the check, but if
  you touch the kit's schema itself, ALSO re-run check across the
  repo's existing pages.

Failure recovery rules:

- `additionalProperties: false` failures usually mean a typo'd key or
  a property name that belongs on a different block kind. The message
  names the offending key and the missing one — read it before doing
  anything else. `oku spec <kind>` prints a correct payload to compare
  against; never re-derive the shape from the schema.
- `"is not of type 'array'"` on a `content` field means the caller
  passed a string where a richString was expected, or vice-versa. The
  error message is sometimes misleading — investigate the nearest
  enclosing block, not just the literal pointer.
- Chip-filter columns require BOTH the header object's `values: [...]`
  AND each cell's `{ values: [...], value: "display text" }`. The
  pipe-separated-string shape is invalid.
- `engine` is NOT a valid key on `diagram` blocks — Mermaid is the
  only engine; just pass `source: "..."`.
- `info-tip.content` must be a **block array**, never a bare string —
  the linter says so (`'…' is not of type 'array'`). The schema covers
  the shape and cannot cover the render: a disclosure that drops its
  whole body still paints its summary, so it reads as a healthy figure
  from the outside. That is `oku verify`'s job, and it now fails a
  disclosure that opens onto nothing.

**Never declare a page edit done if `oku check` exits non-zero.**

**`oku check` passing is not proof the content rendered.** Blocks with
a wrong-but-valid payload shape (see `info-tip` above) validate clean and
vanish in the browser. For any block kind you have not used before,
start from `oku spec <kind>` rather than from memory — a shape that came
from the shipped examples is asserted valid against both the schema and
the structural checks, which is the one class of error the linter cannot
catch on its own. Then verify in a real browser that the body is
present, not just that the build succeeded.

For the strict gate before delivery, use `oku check --strict`
(exits 1 on warnings too). For partial passes during iteration, plain
`oku check` is enough.

### Checking a figure in the browser: query the figure, not `svg`

The kit paints its own inline SVGs as chrome - copy buttons, wrap
toggles, table view switches, the filter icon - and they are typically
14x14. `container.querySelector('svg')` therefore returns a **button
icon**, not your figure, whenever the container holds a code block or a
table first. Concluding "the figure did not render" from that is a
measurement that answered a different question, and it costs a page
restructure to fix nothing.

Query the figure's own host and assert on content, not on presence:

```js
// mermaid: the kit wraps the rendered SVG in .okd-render
const svgs = [...el.querySelectorAll('.okd-render svg')];
svgs.map(s => ({ w: s.getBoundingClientRect().width,
                 nodes: s.querySelectorAll('.nodeLabel').length,
                 label: s.textContent.includes('SomeNodeLabel') }));
```

Rules of thumb: filter by `getBoundingClientRect().width > 100`; assert a
node/label count above zero, not just that an element exists; open every
`<details>` (`d.forEach(x => x.open = true)`) and wait ~2.5s before
measuring, because mermaid renders lazily; and check for a **marker
string you put in the source**, so a stale render cannot pass.

Established by running it (2026-08-18, oku 0.6.5, kit 2026-08-17-r43):
`code`, `table`, `chart` and `diagram` blocks **all render correctly**
inside `oku-info-tip.content`. A figure that looks missing there is a
measurement error until a minimal reproduction says otherwise.

### Reporting an oku defect

Confirmed defects go to `~/dev/mmdemirbas/html-doc/BUGS.md`, newest
first, in the schema its header states: symptom, minimal reproduction,
expected vs actual, where the failure was localised, and - kept separate
- what was *observed* versus what was *inferred from reading source*.

Build the minimal reproduction inside `html-doc` first and confirm the
failure there. A defect that only appears in a large page is not
localised yet, and an entry written from a large page usually describes
the wrong thing. If the reproduction renders correctly, there is no
entry to write.

## Workflow

1. **Clarify scope if ambiguous** (skip if user has been explicit).
   Useful axes:
   - Depth — zero knowledge / project knowledge / domain knowledge?
   - Output path — alongside source artifact, or somewhere else?
   - Visual aids — Mermaid, SVG, tables, code callouts?
   - Density — progressive disclosure vs. everything inline.

   Use `AskUserQuestion` with concrete options when in doubt.

2. **Pick the narrative shape:**
   - **Engineering-review shape:** Foundations → problem → solution
     shape → components → mechanism → decisions → verification →
     future/FAQ/cheatsheet.
   - **Domain-brief shape:** TL;DR → context/landscape → findings →
     open questions → next steps.

3. **Run `oku init` from the docs root.** Do this silently — don't
   tell the user "run init"; run it yourself from the directory that
   contains (or will contain) the new page. Init is idempotent:
   it confirms or refreshes the `_oku` symlink and refreshes
   `index.html` so the inline `window.__okuManifest` includes every
   page currently in the tree (including the one you just added). Run
   it once before authoring AND once after adding or updating a page
   — the second run is what makes the new entry visible in the site-
   tree sidebar when the user opens the file directly from their IDE.

   In an otherwise empty directory init also drops a starter
   `index.md`: front-matter skeleton plus a TL;DR block, ready to type
   into. It never adds one next to pages that already exist.

   Important: run `oku init` in the same directory the page lives
   under (typically `docs/`). Running from the project root when
   pages live under `docs/` creates a stray `_oku` symlink and
   `index.html` at the project root — neither is wanted.

4. **Author the page as markdown.** A page is ONE `.md` file:
   YAML front-matter + a GFM body. There is no HTML to write and no
   JSON to hand-assemble — `oku serve` and `oku build` convert the
   source on the fly.

   ````markdown
   ---
   title: Storage engines
   summary: One line for the nav tooltip, search, llms.txt and the cover.
   ---

   > [!TLDR]
   > The one sentence a reader keeps.
   >
   > - point one
   > - point two

   ## Section title {#anchor-id}

   Lead paragraph. Full GFM: **bold**, *italic*, ~~strike~~, `code`,
   [links](https://example.com), ![images](path.png), footnotes[^1],
   tables with alignment, task lists, definition lists.

   ```oku-chart
   {"type":"bar","rows":[{"label":"a","value":60}]}
   ```

   [^1]: Definitions resolve page-wide — put them wherever you like.
   ````

   - `##` opens a section (the TOC is built from these); `###` is a
     sub-heading inside it. `{#id}` overrides the auto-slug.
   - Every kit primitive is a typed fence whose body is ONE compact
     JSON object. **`oku spec` lists every one and prints a
     ready-to-paste payload; `oku spec front-matter` does the same for
     the page keys.** Both print from the code, so neither can go stale
     — the enumeration that used to sit here named a fence that had
     been removed and omitted two that exist.
   - Admonitions are GFM alerts: `NOTE`, `TIP`, `IMPORTANT`, `WARNING`,
     `CAUTION` and the kit's `TLDR`.
   - Glossary and external references are links:
     `[label](#g/term-id)` and `[label](#x/source-id)`. Registry ids
     may contain spaces.
   - A file the page talks about is a link too: `[label](#f/path)`
     renders a chip the reader can hover for a preview, click to open
     (markdown in the kit's viewer, images and video inline, anything
     else as highlighted source) and copy the path from. **Use it
     wherever you would have put a path in a code span** — that is the
     whole decision rule, and it holds *inside a table cell*, which is
     where a path most often ends up as a bare span and where the dead
     end costs the reader most: a table of files is a list of things to
     go and find. `oku check` says `path-in-code-span` at **warning**
     when it finds a span naming a file that is really there, and **`oku
     check --fix` rewrites every one of them** — in prose, in GFM cells
     and inside `oku-*` payloads alike. Reach for the chip while
     writing; run `--fix` over a page you have converted from somewhere
     else. The path resolves against the page's directory first, then
     the project root, so the root-relative spelling prose already uses
     works. The bytes travel inside the page, so the file must be inside
     the project and under the size cap; `oku check` reports both.
   - `oku spec` lists the three inline kinds (`filepath`,
     `glossary-term`, `ext-ref`) beside the fences, and `oku spec
     filepath` prints the syntax with a note on when to reach for it.
   - A block-level HTML tag at column 0 is an escape hatch (custom
     elements and `<script>` included) when a primitive genuinely does
     not exist for what you need. `oku check` lists each one.
   - `oku spec <name>` prints a ready-to-paste payload for any block
     kind, chart type or inline kind. `oku spec` alone lists every name
     it can answer for, grouped, with its own counts — do not carry a
     total in prose, it goes stale the day a primitive lands.

   Hand-authored `.json` pages (v1 and v2) still render, and
   `oku migrate` converts one to markdown, but new pages are markdown.

5. **Keep the chrome out of it.** Do not write `<page-chrome>`,
   `<page-toc>`, `<main>`, a cover header or a `<style>` block — the
   renderer emits all of it. The tree's accent lives in `kit.json`,
   once, not in each page's front-matter and never in a stylesheet.
   See "What the kit owns" below for the full list of what you get for
   free; re-implementing any of it is the most common way an artifact
   ends up worse than the default.

6. **Run sanity checks** (see below).

7. **Run `oku build`, then report the standalone file by absolute path** —
   e.g. `/Users/you/dev/proj/docs/reports/dist/standalone/foo.html`. No
   `file://` prefix; the bare absolute path is clickable.

   `dist/standalone/` inlines its assets, so it opens in a browser tab
   with no server. `dist/site/` and the source directory both depend on
   sibling assets — never hand those over.

## Visual-first communication — the load-bearing principle

Markdown rendered as colored HTML is **not** visual communication. A
reader who needs to read a paragraph to absorb your point hasn't been
helped by adding a green pill at the end of it. The whole reason to
ship an HTML artifact instead of a markdown reply is that the medium
supports **diagrams that the eye parses geometrically** — size,
position, direction, color regions, sequence — and absorbs in
fractions of the time it takes to read prose.

**Default position:** every section header should be answerable by
glancing at one visual. Prose is the caption underneath, not the
delivery mechanism.

### Visuals are not equal — rank them before you pick one

Three properties separate a figure that does the work from one that
merely occupies the space. Aim for all three; accept two.

1. **It shows the whole at a glance.** The reader sees the shape of
   the answer before reading a single label — which bar is tallest,
   where the line turns, which box everything flows into. A figure
   that has to be read left-to-right like a sentence has not bought
   anything over the sentence.
2. **It packs information into a small space, meaningfully.** Density
   is only a virtue when every mark is carrying a value: position,
   length, angle, colour scale, containment. Twelve numbers in one
   sparkline beats twelve tiles. Twelve *labels* in one diagram is
   just a list drawn sideways.
3. **It tells the story without stopping the reader.** No legend to
   decode before the point lands, no mental arithmetic, no "compare
   the third row against the seventh". If the reader has to *work* the
   figure out, the figure is the work, not the answer.

Ranked by what they typically achieve:

| Tier | Shapes | Why |
|---|---|---|
| **Reach for first** | charts with a real axis, small multiples, mermaid flow / state / sequence / ER, annotated code, before-and-after pairs on one scale | Position and length encode magnitude; arrows encode direction; containment encodes scope. Measurable with a ruler. |
| **Legitimate, lower ceiling** | tables with a filter, step flows, compare grids | Structure the reader can *scan*, but every cell still has to be read. Worth it when the content genuinely is N things × M attributes. |
| **Almost never a visual** | KPI tiles, status pills, coloured callouts, icon rows, "key concepts" cards, a flowchart whose boxes are the section headings | Nothing is encoded. Colour is decoration, adjacency is not comparison, and the box restates prose already on the page. |

**The rule that follows:** when a section's content is numeric, it
gets a chart, not tiles. When it is a process, it gets a diagram, not
a step-flow of paragraph summaries. Drop to the lower tiers only when
the content really has no encodable dimension — and then say so in
one sentence rather than dressing the prose.

**The covering test:** put your hand over a section's prose. Can you
still get the point from the diagram alone? If not, the diagram is
either missing or too small to carry the point. Add it; don't paste
more text.

**The repetition test:** are you producing the same shape (table,
KPI grid, callout) for every section? Vary the visual vocabulary so
each section gives the eye fresh information. A document that's "just
tables" is not visually richer than one that's "just paragraphs".

**The pretty-prose trap:** colored callouts, status pills, and KPI
tiles dressed around paragraphs are the most common failure mode.
They feel visual to the writer (because adding them was an extra
step) and read as decorated text to the reader. Test by removing
the prose around them — is the surviving thing self-explanatory? If
not, you've decorated text, not built a visual.

**Two of these are decidable, so `oku check` enforces them:**
`figure-restates-headings` fires when a diagram's boxes are the page's
own section titles, and `group-of-one` fires on a compare-grid, step
flow, KPI grid or chart grid carrying a single member — a primitive
whose entire job is the relationship between members, used where there
is no second member. The rest of this section needs your judgement and
no linter will do it for you.

## File conventions

- Path: `docs/<area>/review-YYYY-MM-DD.html`, `<task-dir>/REVIEW.html`,
  or `<task-dir>/notes/<topic>.html`. Place alongside the source artifact
  so the user can read both side-by-side.
- Multiple replies in one day: suffix `-01`, `-02`.
- Commit policy depends on what the artifact IS — don't assume:
  - **One-off / throwaway** (a single-reply review HTML, a postmortem
    or audit doc generated alongside one answer): don't commit by
    default; it's a personal aid, not project history. User opts in.
  - **An ongoing project or knowledge base** the user is actively
    building with the kit (a multi-session study guide, a docs site,
    a living reference): this IS real project work. Version-control it
    like any code — follow the repo's commit conventions and the
    user's `commit.md` cadence. Do NOT label it a "study aid" and skip
    committing; that mislabels real work. If unsure which kind it is,
    ask — the difference is "wrote it once to answer a question" vs.
    "we keep coming back to grow it."

## What the kit owns — don't rebuild any of it

None of the chrome is yours to write, style or position. The renderer
emits it from the source: the cover, the Contents drawer carrying the
site tree and the on-page TOC, the presentation menu (text size, column
width, light/dark theming that follows the OS until the reader overrides
it, language, placeholders), search,
scroll-spy, section permalinks, the top rail, back-to-top, code
line numbers with a language pill and brace folds, glossary tooltips,
the lightbox with pan and zoom, and the print stylesheet.

The rail changes what a heading costs you. It is the hairline strip
across the top: read progress, plus
a tick for every heading — thicker the higher its level — and a mark for
every figure, shaped by kind: a square is a table, a circle is a chart,
a diamond is a diagram, a hollow square is any other figure. Each one
is a button that jumps there, and hovering the strip opens it so the
shapes resolve. So a page with clear section titles and real figures
gets a usable map for free, and a page that is one long undivided
section gets a rail with nothing on it. That is a reason to break a
page into sections, not a reason to write anything extra.

There is no stylesheet to write and no `:root` block to define. Two
complete CSS variable sets ship in the kit, light and dark, and every
component reads them. The accent comes from `kit.json` for the whole
tree.

**If you are writing CSS, stop and check the vocabulary below.** You
are almost certainly rebuilding something that already exists, and the
hand-rolled copy will not follow the accent or the theme.

## The primitive vocabulary — pick by the relationship

Each primitive is a typed fence whose body is ONE compact JSON object.
Pick by what the content *is*, not by
what looks good — and within that, by what the primitive **encodes**
(see the tier table above; the first three rows here are the ones to
reach for first):

| Fence | The relationship it carries | Reach for it when |
|---|---|---|
| `oku-chart` | magnitude, distribution, change over time, part-to-whole, correlation | Any set of numbers that share a unit. ~50 types; `bar` and `plot` cover most cases. |
| `oku-chart-grid` | the same shape repeated across N groups | Small multiples — one chart per region, per engine, per week. |
| `oku-table` | a matrix — N things × M attributes | More than three parallel things with the same fields. Gains filter, sort, group-by and card/board views past a size threshold. |
| `oku-compare-grid` | two or more options weighed side by side | A decision with alternatives. `verdict` marks the winner; `accent` colours the card. `preview: true` turns a grid of in-page links into a picker — each card shows a silhouette of the figure it points at, cloned from the render so it cannot drift. |
| `oku-step-flow` | ordered stages, or unordered parallel options | A pipeline, a procedure, a migration. `ordered: false` for a 2-up grid of links with no implied sequence. |
| `oku-kpi-grid` | headline numbers, no shared axis | Two to four figures that open a section — and know that this is a tier-three shape: nothing is encoded, adjacency is not comparison. Values that share a unit belong in a chart. |
| `mermaid` | topology, sequence, state, containment, timing | Any diagram. Mermaid computes positions and avoids label collision; prefer it over hand-drawn SVG. |
| `oku-info-tip` | detail the curious 5% want and the rest do not | A `<details>` disclosure. Keeps a long aside off the main line. |
| `oku-diagram` | the same, with a caption | When the figure needs a caption line. A plain `mermaid` fence with an italic line under it produces the same thing. |
| `oku-annotated-code` | a line of code and the reason for it | Walking through an implementation. Numbered markers in the source pair with a side panel. |
| `oku-example` | input beside its rendered output | Documenting a format. This is how `docs/reference.md` shows every primitive. |
| `oku-copy` | text the reader will paste elsewhere, and what it replaces | Pointed edits to a document someone else owns. Three clipboard formats off one source — markdown verbatim, plain, rich — and `before` adds a word-level diff so the edit is visible rather than inferred. |
| `oku-live-snippet` | code the reader can edit and re-run | Teaching a syntax where trying it beats reading about it. |
| `oku-insight` | one sentence that must not be skipped | Sparingly. It is text-shaped, and three of them in a row is a bullet list. |
| `> [!TLDR]` | the page in one line plus three points | The opener. A blockquote alert, not a fence — there is no `oku-tldr`. |

Admonitions (`NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`, `TLDR`)
are GFM blockquotes. **They are not visuals.** A coloured box around a
paragraph is decorated text — `oku check`'s density rule does not count
one, and neither should you.

**Never guess a payload shape — `oku spec <name>` prints it.**

```
oku spec                # every name: 14 block kinds, 53 chart types
oku spec sankey         # the fence, ready to paste
oku spec table --json   # the payload alone
```

Median output is ~100 tokens. The alternatives are worse in both
directions: reading `page.schema.json` costs 11.6k tokens, and guessing
risks a payload that validates clean and renders empty (see `info-tip`
above) — the one failure the linter cannot catch for you.

`docs/reference.md` and `docs/charts.md` show every primitive beside its
rendered output, but they live in the kit repo and are **not** in the
installed wheel. From any other project, `oku spec` is the source.

## When a primitive does not fit: HTML islands

A block-level HTML tag at column 0 passes through to the DOM untouched —
custom elements, `<script>` and `<style>` included. Full capability, no
restrictions. Reach for it only after checking that no primitive covers
the relationship you are showing; `oku spec` lists all 68.

**Colours come from the kit, never from a hex literal.** `var(--accent)`,
`var(--surface)`, `--series-1..10` for an island; `.okt-diag-node` /
`-edge` / `-arrow` / `-label` / `-group` and `.okt-diag-fill-1..10` for a
hand-drawn SVG; `fill:var(--series-N-soft),stroke:var(--series-N),color:var(--text)`
for a mermaid `classDef`, where the `-soft` plate is what makes the node
label readable in both themes. A hardcoded colour is how a figure ends up
invisible in the theme nobody was looking at, and `island-hand-styled`
fails on it — in an island and in a mermaid fence alike.

**A blank line inside an island does not end it.** It ends the HTML
block, which is what lets you write markdown between the tags, and the
element stays open until its closing tag. Multi-line code inside one is
a real `<pre>`, never `<br>` — a `<br>` renders three lines and copies
as one. An island that never closes takes the rest of the section with
it, and `oku check` says so as `island-unclosed`.

Everything else — what goes inside an island, images and other files
beside the page, the two-pass layout test, the full class vocabulary,
why `<style>` blocks are refused — is in
`references/islands.md` beside this file. Read it before writing one.

## Tone

- **Detailed**, not summary-skim. The reader wants depth.
- **Plain language**, not cryptic shorthand. Complete sentences.
- **"Points toward"**, not "decided". The user makes decisions; the
  artifact surfaces considerations.
- **Honest about limitations.** If knowledge is dated or based on one
  source, say so. If a decision is uncertain, list the open questions.
- **Answer with background AND solution.** A reader who only gets the
  solution can't generalise it.
- **Predict follow-up questions** and answer them in an FAQ section
  rather than waiting for a second round.

## Don'ts

**Visual anti-patterns** (the ones that turn an HTML artifact into
disguised markdown):

- Don't conflate "added a pill" with "added a visual". A pill is a
  colored word. A visual is a thing the eye parses geometrically —
  size, position, direction, color regions, sequence.
- Don't write a paragraph then drop a status pill at the end. The
  pill should *replace* the sentence, not adorn it.
- Don't repeat the same shape (table, KPI grid, comparison card) for
  every section. Vary the visual vocabulary so the reader's eye gets
  fresh information each scroll.
- Don't ship a "diagram" that's just the bullet list it replaced with
  boxes around it — it isn't pulling its weight. Cut it or replace with
  a real chart.
- Don't dump deep-dive content inline. A `<details>` island keeps the
  structure visible to a skim-reader and the depth available on click.
- Don't ship a section with three or more paragraphs of prose without
  at least one visual. Either find the figure, or rewrite as a table,
  card grid, or comparison block. `oku check` names the section.

**Mechanical / structural don'ts:**

- Don't apply structural changes the user hasn't approved. Propose first.
- Don't cram multiple rounds into one HTML file. Each reply is its own round.
- Don't claim "fixed" when you've only added a comment.
- Don't reuse a colour for two distinct concepts.
- Don't over-nest headings — cap at H4.
- Don't auto-play, auto-scroll, or hijack the reader's pace.
- Don't include images or fonts that need network unless the page
  degrades cleanly without them. A file beside the page is fine — the
  build carries it, and a standalone page inlines it — but a rendered
  figure beats a picture of one at every width and in both themes.
- Don't write a "design decisions" section that's just rationalising
  what you did. List the rejected alternatives.
- Don't hand-write chrome, a stylesheet, a `:root` block or a per-page
  accent. The kit owns all four, and a hand-rolled copy stops following
  the theme the moment the reader toggles it.
- Don't fill front-matter fields the build supplies. A hand-counted
  reading time is wrong after the next edit and nothing says so.

## Sanity checks before delivery

**The density gate is now the linter's job, not yours.**

`oku check` reports `prose-only-section` for any section with three or
more paragraphs and nothing for the eye — a callout does not count. It
also reports `redundant-meta` for a field that repeats another,
`island-hand-styled` for an island carrying hardcoded colour,
`accent-divergence` for a tree with no colour convention,
`group-of-one` for a compare-grid / step flow / KPI grid / chart grid
holding a single member, and `figure-restates-headings` for a diagram
whose boxes are the page's own section titles. Run it and fix what it
names; that removes the whole class of judgement calls that used to sit
here as a checklist.

What the linter cannot decide, and you still have to:

- **Does the figure carry the point?** Cover the prose. Can you still
  get the section from the visual alone? A chart that restates the
  sentence above it passes every automated check and earns nothing.
- **Is the visual vocabulary varied?** A page that is nine tables is
  not visually richer than a page that is nine paragraphs.
- **Layout robustness of any hand-drawn figure.** Run the two-pass test
  from the islands section — density, then 360px — in a real browser.
  Never ship a hand-positioned diagram you have not viewed narrow.

**Automated (every artifact — run this first):**

Run `oku check --strict` from the project root. It validates every typed
fence payload against the schema and runs 65 structural and content
checks, and it names each finding with `file:line`, the offending value
and — for anything it can compute — the fix. Read what it prints rather
than working from a list here: a catalogue in this file goes stale
against the tool independently, and the tool is the one that is right.

`--json` for machine-parseable output, `--verbose` to include
info-level nudges, `--errors-only` to hide warnings. Zero exit under
`--strict` means the doctree is clean.

One finding a correct document can earn: `process-breadcrumb`. This
skill's own vocabulary is rounds, and a report that corrects an earlier
round has to cite it by name. A page whose SUBJECT is a history — that
report, an audit, a changelog — sets `documents_history: true` in its
front-matter. It exempts that one rule on that one page; every other
check, `placeholder-text` included, still applies. Do not reach for it
to silence a breadcrumb in a page that documents current behaviour —
there the warning is right and the sentence is the thing to fix.

**Rendered (every artifact):**

```bash
oku build && oku verify
```

`oku verify` opens every built page at 1440px and 360px and reports what
reading the source cannot: a diagram that failed to draw, a figure that
rendered an empty box, sideways scroll, a console or page error. That
last class is the one that matters most — a wrong-but-valid payload
validates clean and draws nothing, and no source check reaches it.

What is left for your eyes, because it needs judgement:

1. Toggle the theme; nothing strobes, and any island or hand-drawn SVG
   stays legible — confirm its fills and strokes read CSS variables
   rather than hardcoded hex.
2. Does the figure carry the point when you cover the prose?

Anchors and placeholders were on this list and are checks now
(`unresolved-anchor`, `placeholder-text`); opening the page, narrow
width and empty figures are `oku verify`. A step you have to remember is
a step that gets skipped.

**Heavier (long reference documents):**

4. Mermaid blocks re-render correctly after a theme toggle.
5. Take screenshots in both modes for the user.

Not on this list any more: blocking the CDN (mermaid and Prism are
vendored — `test_vendor_offline.py` asserts a built page draws with
every origin refused), and "disable JavaScript; the body is still
readable". The second was never true: renderer.js builds the DOM, so a
no-JS page measures 0 characters of body text. Asking for a check that
cannot pass teaches you to report passes you did not get.

After the checks, announce the file with a 1-3 sentence pointer plus
the top 1-3 takeaways.

## Mermaid and Prism are already handled

The kit lazy-loads both and re-renders Mermaid on a theme toggle,
caching the source so a re-render never reads an emptied node. Write a
`mermaid` fence or a fenced code block with a language; there is
nothing to wire.

## After the round

- Persistent principles learned in this round → global rules or the
  project's `CLAUDE.md`.
- Project-specific preferences (regulatory framework, language, tone)
  → project `CLAUDE.md`.
- Ephemeral context (current hypothesis, pending decision) → memory.

The artifact itself is the round's deliverable; the rule updates are
the round's compound interest.
