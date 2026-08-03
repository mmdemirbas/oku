---
name: oku
description: >
  Produce a standalone, **visual-first** HTML artifact for long-form
  replies — reviews, feedback rounds, study guides, briefs, design docs.
  Use when the user has 5+ distinct points/questions, asks for "visually
  rich" or "well-designed" output, needs ~1500+ words, or wants a
  document to read alongside another file. Diagrams (SVG topology,
  HTML/CSS bar charts, timelines, scatter matrices, step-flow chevrons,
  comparison cards, status icons) are the primary communication
  medium; prose is caption. The output is a single self-contained HTML
  file with consistent chrome (top-left TOC toggle, top-right theme
  toggle), light/dark theme that respects prefers-color-scheme,
  auto-built scroll-spy TOC, and a reusable kit of visual components.
  Companion repo: https://github.com/mmdemirbas/html-doc (remote URL
  still on the legacy name).
---

# oku Skill

A pattern for producing standalone, readable HTML artifacts when an
inline reply would be either too long or too flat.

## When to fire this skill

- 5+ distinct feedback points or questions in one message.
- Response would naturally span multiple categories
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

This skill is governed by the four design principles in
`~/.claude/rules/design-principles.md` (proximity, hierarchy, schema,
grouping). They apply at three layers — visual, content, code — and
the **content layer** is the load-bearing one for this skill.

**Before structuring the page, decide catalog or teaching** — see
`~/.claude/rules/teaching-order.md`. A reference the user returns to
for lookup is organised by topic; anything meant to be read start to
finish is organised by the reader's next question, with one spine
visual that grows through the document. Getting this backwards
produces a page that is complete and unusable. When both are needed,
build two pages and link them.

When generating any artifact via this skill, route the content design
through the four:

- **Proximity** — the caveat sits next to the claim. The example
  follows the paragraph it illustrates. The link is beside the term
  it documents. Cross-references do not leave the reader hunting.
- **Hierarchy** — top-level conclusion before nested reasoning. The
  most important sentence of a paragraph is first or last, never
  buried. Visual emphasis matches semantic importance — not the other
  way around.
- **Schema** — every kind of artifact has predictable parts. A review
  has subject / criteria / findings / recommendations. A study doc
  has overview / key concepts / examples / pitfalls / further reading.
  A plan has goal / scope / approach / risks / asks. Stick to the
  schema for the kind; the reader's mental model carries between
  documents.
- **Grouping** — bullets for parallel items; numbered lists for ordered
  steps. Related facts cluster into themed cards or visual regions.
  Sub-points indented under their parents. One idea per paragraph.

These apply identically whether the artifact is a study guide, a plan
review, a team-facing brief, or a personal learning note. Same vocabulary,
same routing. The visual richness this skill describes elsewhere sits
*on top of* this content discipline, not in place of it.

## Verify after every page edit — non-negotiable

After ANY edit to a `docs/*.md` page source (or any kit schema), run:

```bash
oku check
```

— from the repo root (the local directory name happens to be
`html-doc/` because the GitHub remote is still on that URL; the
project, CLI, and skill itself all read `oku`). `oku check`
validates every
page against `kit/schema/page.schema.json` and runs the structural /
content lint. Exit code is the only signal that matters; parse the
output for the offending file + path when non-zero.

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
  a property name that belongs on a different block kind. Read the
  schema's `$defs/<kind>` first; don't guess.
- `"is not of type 'array'"` on a `content` field means the caller
  passed a string where a richString was expected, or vice-versa. The
  error message is sometimes misleading — investigate the nearest
  enclosing block, not just the literal pointer.
- Chip-filter columns require BOTH the header object's `values: [...]`
  AND each cell's `{ values: [...], value: "display text" }`. The
  pipe-separated-string shape is invalid.
- `engine` is NOT a valid key on `diagram` blocks — Mermaid is the
  only engine; just pass `source: "..."`.
- `info-tip.content` must be a **block array**, never a bare string.
  A string passes `oku check` and then renders as a `<details>` with
  ONLY the `<summary>` — the body silently disappears. Same silent-drop
  risk for any `content` field documented as a block list. After adding
  an `info-tip`, open the page and assert the `<details>` has more than
  one child element; the linter will not catch this.

**Never declare a page edit done if `oku check` exits non-zero.**

**`oku check` passing is not proof the content rendered.** Blocks with
a wrong-but-valid payload shape (see `info-tip` above) validate clean and
vanish in the browser. For any block kind you have not used before,
verify in a real browser that its body is present, not just that the
build succeeded.

For the strict gate before delivery, use `oku check --strict`
(exits 1 on warnings too). For partial passes during iteration, plain
`oku check` is enough.

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
   tell the user "run init"; just run it yourself from the directory
   that contains (or will contain) the new page. Init is idempotent:
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

   ```markdown
   ---
   title: Storage engines
   eyebrow: Reference
   subtitle: One line under the H1.
   accent: teal
   order: 20
   summary: One line for nav tooltips, search and llms.txt.
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
   ```

   - `##` opens a section (the TOC is built from these); `###` is a
     sub-heading inside it. `{#id}` overrides the auto-slug.
   - Every kit primitive is a typed fence whose body is ONE compact
     JSON object: `oku-chart`, `oku-table`, `oku-kpi-grid`,
     `oku-step-flow`, `oku-compare-grid`, `oku-example`, `oku-insight`,
     `oku-live-snippet`, `oku-annotated-code`, `oku-chart-grid`,
     `oku-tldr`, `oku-diagram` — plus plain `mermaid`.
   - Admonitions are GFM alerts: `NOTE`, `TIP`, `IMPORTANT`, `WARNING`,
     `CAUTION` and the kit's `TLDR`.
   - Glossary and external references are links:
     `[label](#g/term-id)` and `[label](#x/source-id)`. Registry ids
     may contain spaces.
   - A block-level HTML tag at column 0 is an escape hatch (custom
     elements and `<script>` included) when a primitive genuinely does
     not exist for what you need. `oku check` lists each one.
   - `docs/reference.md` in the kit repo is the canonical example of
     every primitive with its payload shape beside the rendered output.

   Hand-authored `.json` pages (v1 and v2) still render, and
   `oku migrate` converts one to markdown, but new pages are markdown.

5. **Keep the chrome out of it.** Do not write `<page-chrome>`,
   `<page-toc>`, `<main>`, a cover header or a `<style>` block — the
   renderer emits all of it from the front-matter. Per-page accent is
   the `accent:` key (named token or CSS colour), not a stylesheet.
   The kit gives you three-mode theming, the sticky TOC with
   scroll-spy, the progress bar, back-to-top, section permalinks,
   copy-to-clipboard and line folding on code, glossary tooltips, the
   lightbox, search and the print stylesheet. Don't re-implement any
   of it.

6. **Run sanity checks** (see below).

7. **Run `oku build`, then report the standalone file by absolute path** —
   e.g. `/Users/md/dev/proj/docs/reports/dist/standalone/foo.html`. No
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

## Page chrome — never moves

Two fixed-position icon-only buttons, persistent across the document:

- **Top-left:** TOC toggle (☰)
- **Top-right:** Theme toggle (🌙 / ☀️)

**Same corners at every viewport.** Resist the urge to drop a
"☰ Contents" pill at bottom-right on mobile. The single TOC button
branches its behaviour by viewport width:

- Desktop (> 920px): collapses the sticky sidebar to zero width
  (`body.toc-collapsed`), persisted via `localStorage`.
- Mobile (≤ 920px): toggles an off-canvas drawer (`nav.toc.open`).

Same icon for both states; the meaning is the action, not the glyph.

### Fixed-positioning pitfalls

Make sure no ancestor breaks `position: fixed`:

- Ancestor with `transform`, `filter`, `perspective`,
  `will-change: transform`, or `contain: paint` establishes a new
  containing block. Buttons must be direct children of `<body>`.
- `overflow: hidden` on a near-ancestor sometimes clips the button.
- Stacking contexts from `opacity < 1`, `mix-blend-mode`, or
  `isolation: isolate` on ancestors can hide the button behind
  otherwise-lower-z elements. Use z-index ≥ 100.

## Theme switcher — three modes

The kit ships a **three-mode** cycler: `system → light → dark → system`.
System is the default and follows `prefers-color-scheme` live; if the
user changes their OS theme while in system mode, the page updates
without a click.

- Stored in `localStorage` under key `theme-pref`. Values: `light`,
  `dark`, or absent (= system).
- `chrome-boot.js` (synchronous, in `<head>`) reads the pref and sets
  `data-theme` (the rendered theme) and `data-theme-mode` (which of
  the three modes is active) on `<html>` before paint. No FOUC.
- Cycler button icon shows the *current mode* (monitor, sun, moon),
  not the rendered theme. So if the user is in system mode and OS is
  dark, the button still shows the monitor icon.
- Two complete CSS variable sets in `chrome.css`: `:root` (light) and
  `:root[data-theme="dark"]` (dark). Every rule reads `var(--bg)`,
  `var(--text)`, etc. No hardcoded hex outside these two blocks.
- Concept colours (engine palette, status pills) need both light- and
  dark-mode values. Saturated dark colours often look garish on white;
  desaturate and darken for light.

## TOC behaviour

- Sidebar default open on desktop.
- Top-left toggle collapses to zero width and reopens.
- Off-canvas drawer on mobile: backdrop click, toggle click, `Escape`,
  and clicking any TOC link all close it.
- Scroll-spy highlights the active section in the TOC; sub-items expand
  for the active section, collapse for others.
- Auto-generated from `<main> <section>` `<h2>` and `<h3>` elements —
  add `id` attributes if you want stable anchors, otherwise the script
  slugifies titles.

## CSS token system

The kit's `chrome.css` provides two complete sets. Don't introduce
hardcoded colours outside `:root` and `:root[data-theme="dark"]`. If
the topic has parallel concepts (engines, states, tracks), add one
variable per concept in **both** blocks. Same colour = same concept
everywhere.

Don't reuse a colour for two distinct concepts.

### Accent — pick per artifact

The accent colour is **not fixed**. Each artifact picks its own (matching
the project's product palette, the topic, or the contrast of the team).
Examples in the repo: amber (`#f0b429` dark / `#b45309` light) for the
Flink studies; indigo for a strategy brief; teal for an infrastructure
review. Define the accent and `--accent-soft` in both `:root` and
`[data-theme="dark"]` (or `[data-theme="light"]`) blocks. Everything
else — chrome buttons, focus halos, scroll-spy active TOC, anchor
flash, progress bar, hero glow — derives from those two tokens.

## Visual language — modern, layered, frosted

The kit ships a modern, ai-2025-era look. Don't strip it down to
"plain HTML"; that feels mechanical and dated. The defining touches:

- **Typography:** Inter (body, 400/500/600/700/800) and JetBrains Mono
  (code, 400/500/600). Both via Google Fonts with `display=swap`.
  Body at 16px, line-height 1.65, letter-spacing 0.005em. H1 ≈ 44px
  with -0.025em letter-spacing. Eyebrow letter-spacing 0.2em.
- **Chrome buttons** (`.ctrl-btn`): 44×44, border-radius 12px. Layered
  shadow `0 6px 18px var(--shadow-strong), 0 0 0 1px var(--shadow-soft)`,
  frosted via `backdrop-filter: blur(12px) saturate(140%)`, isolation
  `isolation: isolate`, and a subtle `:active { transform: scale(0.96) }`
  press feedback. Hover lifts to `--ctrl-bg-hover` with `--line-strong`
  border.
- **SVG icons** (Feather-style stroke): menu `☰`, sun, moon, up-arrow.
  Use inline `<svg viewBox="0 0 24 24" stroke="currentColor" ...>` at
  20×20 inside `.ctrl-btn` rather than emoji glyphs. Theme switcher
  shows sun XOR moon via `display: none/flex` based on
  `[data-theme="..."]`.
- **Hero radial glow:** `header.cover::before` is a radial gradient
  using `--accent-soft` positioned at `60% 80% at 20% 0%`, behind the
  hero content via `z-index: -1` and parent `isolation: isolate`. Gives
  the page a focal point without a hard banner.
- **Content centering:** `main { max-width: var(--max-width); margin:
  0 auto; }` keeps body width stable when the sticky sidebar collapses,
  so the eye doesn't jump.

These are **defaults**, not laws. A project with a different visual
identity can override — but if you find yourself reaching for plainer
chrome, default back to this kit before shipping. "Mechanical" is the
failure mode.

## Diagram patterns — the primary vocabulary

These are the actual visuals. Reach for one of these before writing
the third paragraph in a section. All implementable in inline SVG or
HTML+CSS — no external libraries needed.

| Pattern | When to reach for it |
|---|---|
| **Topology / architecture diagram** (inline SVG: nodes + edges, color-coded paths, arrowheads) | "Where does X sit relative to Y" — any system with 3+ components and at least one path between them. The single highest-leverage diagram for orientation. |
| **Horizontal bar chart** (HTML/CSS, log-scaled if range is wide) | Comparing magnitudes across categories — recovery times, costs, byte counts, latencies, sizes. Add overlay rows in a different color for before/after comparisons. |
| **Timeline** (HTML/CSS, axis + event dots + colored bands) | "What happens when X event fires" — sequence of events with relative timing. Colored bands show state regions (working / degraded / broken). Use side-by-side timelines for before/after. |
| **2-D scatter / ROI matrix** (HTML positioned dots in a 2×2 grid) | Multi-attribute comparison of a small set (3–6 items). Cost vs impact, risk vs payoff, effort vs value. The position carries the message. |
| **Step-flow chevrons** (boxes + arrows in a horizontal row) | Pipeline order, dependency chain, ship sequence. ≤6 steps. Highlight the current/recommended step. |
| **Verdict tile** (icon + headline + status pills, framed) | Top-of-doc summary instead of a prose TL;DR. The icon does most of the work; the headline is one sentence; the pills are the conclusions. |
| **Numbered card list** (badge + title + meta row + body) | Proposals, action items, ranked recommendations. Each card scannable as a unit — cost / risk / files line as meta, ≤2 short paragraphs in the body. |
| **Comparison cards** (side-by-side bad/good with status colors) | Today-vs-proposed, A/B alternatives, before/after of a single decision. |
| **Inline status icons** (single-color SVG, currentColor-aware) | Replace pill text where the meaning is binary. Checkmark, cross, warning triangle, arrow. |

## Static text-shaped components — supporting cast

Use these to dress and frame the diagrams above, not as standalone
"visuals". A section made entirely of these is a markdown document
in HTML clothing.

| Component | Use for |
|---|---|
| `.callout` (+ `.warning` / `.danger` / `.success` / `.neutral`) | A piece of prose that needs scannable attention — pitfall, key takeaway, optional reading. |
| `.pill` (+ `.ok` / `.warn` / `.fail` / `.info` / `.muted`) | Status badges. Best paired with an inline SVG icon. |
| `.kpi-grid` + `.kpi` | Headline numbers at the start of a section. Useful but easy to overuse — replace with a bar chart whenever you have 4+ values that share a unit. |
| `<table>` | Matrices (engine × column, rule × trigger). Use any time prose lists more than three parallel things — but ask first if a chart or grid would carry it better. |
| `details.card` (or `details.defer`) | Optional depth that doesn't disrupt linear reading. Default-collapsed for skim-readers; expand for the full account. |
| `.g-wrap` + `.g` + `.g-tip` | Inline glossary tooltip; dotted underline indicator. |

## SVG conventions

- **Inline only.** No external CDNs, no `<img src="…">`. The artifact
  must be a self-contained file the user can open offline.
- **Reference CSS variables for colors.** `fill="var(--surface)"`,
  `stroke="var(--text-soft)"`. Theme toggle then works automatically
  with no JS re-render needed.
- **Use `viewBox` + `width="100%"`.** Diagrams scale on mobile without
  per-viewport code. Set `class="full"` (or equivalent) on the SVG
  element so it fills its container.
- **Cap diagram complexity.** One SVG should be ≤ ~150 lines. If it's
  growing past that, the diagram is doing too much — split into
  two diagrams or simplify the system being shown.
- **Define markers (arrowheads) once in `<defs>`.** Color them via
  class so theme variables propagate.
- **Accessibility.** Add `role="img"` + `aria-label="..."` on the
  outer SVG, or a `<title>` first child. Screen-reader users should
  get the gist without seeing the geometry.
- **Honour reduced-motion.** No CSS animations on SVG that aren't
  decorative; if any are present, gate them behind
  `@media (prefers-reduced-motion: no-preference)`.

## Layout discipline — overlap is structural, not stylistic

The single most common way a "visual" turns unreadable is hand-positioned
text that overlaps when content is dense or the viewport is narrow.
The fix is never "make the font smaller" or "shorten the labels" —
it's **pick a layout pattern where overlaps are structurally impossible**.

**The hand-positioned-text trap:** any time a label, dot, or annotation
gets an `style="left:X%"` / `top:Y%` / SVG `x="..." y="..."` that you
chose by eye, the layout will collide for SOME content density or
viewport width. CSS doesn't compute label-collision; you do, and you
will get it wrong.

### Safe patterns — use these

| Pattern | Why overlap is impossible |
|---|---|
| **Bar chart row-per-item** (each row is its own track) | Labels and bars share a row; a row is only one thing tall. Adding more items adds more rows; never collides. |
| **Table-driven legend below the visual** (numbered marker on visual, numbered row in table below) | The visual carries position/shape; the table carries text. Tables can't overlap themselves. |
| **Step-flow chevrons in a flexbox row with `flex-wrap: wrap`** | Each step is a self-contained box; wrap kicks in when narrow. No fixed-position math. |
| **Comparison cards in a CSS grid** (`grid-template-columns: 1fr 1fr`) | Each card is its own cell; collapses to 1fr on narrow viewports. |
| **Mermaid diagrams** (sequence, gantt, flow, state) | Mermaid computes positions and avoids label overlap automatically. Worth the runtime dependency for any diagram that would otherwise need ≥4 hand-positioned labels. |

### Risky patterns — use only with strong constraints

| Pattern | Risk | Constraint that makes it safe |
|---|---|---|
| **Timeline with event labels on the bar** | Labels collide when events are <10% apart on the time axis | Cap to 3 events on the bar; put detail in a numbered table BELOW the bar (the visual is bands + axis ticks only). |
| **Scatter / 2-D matrix with labels next to dots** | Labels collide when dots are close OR viewport is narrow | Number the dots only; put the legend in a keyed table below. |
| **Topology with edge labels** | Labels overlap when edges cross or are close | Place labels on the edge midpoint with `text-anchor="middle"` and a `<rect>` background; if you have ≥3 edges through a region, split into two diagrams. |
| **Hand-positioned annotations on any SVG** | Will fail at SOME viewport. | Use `viewBox` so geometry scales together; never mix `viewBox` (relative) with `style="left:X%"` (absolute) on the same diagram. |

### The two-pass test (run on every diagram)

After laying out a diagram:

1. **Density pass:** add 50% more items mentally — would labels overlap? If yes, the pattern can't survive a content change. Switch to a row-per-item or table-below pattern.
2. **Viewport pass:** view at the narrowest planned viewport (typically 360px). Are any two text elements within 4px of each other? If yes, the pattern can't survive a viewport change.

A diagram that passes both is robust. A diagram that fails either will produce the bug "labels are unreadable" the moment content shifts or someone opens it on a phone.

### When in doubt, use Mermaid

Reach for Mermaid (sequence, gantt, flowchart, state) any time a custom
diagram would need ≥4 hand-positioned labels. The runtime dependency
(~80 KB inlined) is worth more than any custom design — Mermaid solves
label collision automatically and the diagrams age well.

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
- Don't ship a "diagram" that's just a fancier list. If your diagram
  looks like the bullet list it replaced but with boxes, it isn't
  pulling its weight. Cut it or replace with a real chart.
- Don't dump deep-dive content inline. Use `<details>` accordions so
  the skim-reader sees the structure and the depth-reader can expand.
- Don't ship a section with three or more paragraphs of prose without
  at least one visual. Either find the diagram, or rewrite as a table,
  card grid, or comparison block.

**Mechanical / structural don'ts:**

- Don't apply structural changes the user hasn't approved. Propose first.
- Don't cram multiple rounds into one HTML file. Each reply is its own round.
- Don't claim "fixed" when you've only added a comment.
- Don't reuse a colour for two distinct concepts.
- Don't over-nest headings — cap at H4.
- Don't auto-play, auto-scroll, or hijack the reader's pace.
- Don't include images or fonts that need network unless the page
  degrades cleanly without them.
- Don't write a "design decisions" section that's just rationalising
  what you did. List the rejected alternatives.
- Don't ship a second mobile-only button (no bottom-right "Contents"
  pill). One button, top-left, every viewport.

## Sanity checks before delivery

**Density gate (run BEFORE the mechanical checks):**

0a. **Visual presence.** Walk through every section. For each one, ask:
   - Does it have at least one visual element that isn't a callout / pill / table?
   - Could I cover the prose and still get the point from the visual?
   - If I removed the visual, would the section still "feel like HTML" or read as a markdown paragraph in disguise?

   If a section fails any of these, find the diagram (topology, bar
   chart, timeline, scatter, flow, comparison cards) before shipping.

0b. **Layout robustness.** For every diagram in the document, run the
   two-pass test from the Layout discipline section:
   - **Density pass:** would labels overlap if I added 50% more items?
   - **Viewport pass:** at 360px width, are any two text elements within 4px of each other?

   Open the file in a browser and resize to ~360px (devtools "Responsive"
   mode is fastest). If anything overlaps, the diagram uses a hand-
   positioned pattern that needs to be replaced with a row-per-item bar,
   a table-below-visual legend, or a Mermaid diagram. **Never ship a
   diagram you haven't actually viewed at narrow width.**

These two are the checks most likely to be skipped — don't.

**Automated (every artifact — run this first):**

Run `oku check --strict` from the project root after you finish
authoring. The linter validates every page (typed fence payloads
against the schema) and flags structural / content issues that the
browser-side checks below can't see:

- Schema violations (missing required fields, unknown kinds).
- Deprecated primitives (`bar-chart`, `scope-grid`) — both fold into
  unified primitives (`chart` with `type:"bar"`, `compare-grid` with
  `verdict:"in"`/`"out"` + `items[]`); the linter names the migration.
- Duplicate section / heading anchors within a page.
- Unresolved glossary terms / ext-refs (the kit drops these silently
  in the browser; the linter is the only catch).
- Forbidden process language: `round-N`, `v2 review`, `fixed in round`
  in any prose. The kit documents current behaviour, not history.
- Chart shape errors: `type:bar` without `rows`, `type:scatter|line`
  without `series`, unknown chart types.
- Layout primitives with an empty collection (`kpi-grid` with no
  tiles, `step-flow` with no steps, `compare-grid` with no cards,
  `chart-grid` with no charts) — these render as a zero-height gap
  with no other signal.
- Footnote and reference-link labels with no definition anywhere on
  the page; both render as literal source text otherwise.
- Headings that skip a level (`##` → `####`), which breaks the
  outline a screen reader announces and the TOC nests by.
- Strict-GFM subset violations (setext headings, indented code
  blocks, lazy blockquote continuation, ambiguous `---`) and
  ```oku-* fences that failed to lift (bad JSON / unknown kind).
- HTML islands (info-level audit — each island is a deliberate,
  visible decision).
- Stray demo pages (`*-demo.html|md`) outside the one historical
  exception (`markdown-demo.md`).

Use `--json` for machine-parseable output, `--verbose` to also see
info-level nudges (missing `meta.summary`, code blocks without a
declared language). A zero exit code under `--strict` means the
doctree is clean.

**Lightweight (every artifact):**

1. Page opens in a browser; no console errors.
2. Every TOC link resolves to a section.
3. Toggle the theme; nothing strobes, all callouts/pills/tooltips/SVGs
   remain legible (especially confirm SVG fills/strokes use CSS
   variables, not hardcoded hex).
4. Resize to a narrow viewport; chrome stays in corners, drawer
   behaves correctly, SVGs scale via `viewBox`.
5. Word-search for placeholders (`{{ }}`, `TODO`, `TBD`, `XXX`) —
   none should remain.

**Heavier (long reference documents):**

6. Block the CDN domain in devtools; the page is still readable.
7. Disable JavaScript; the body is still readable.
8. Mermaid blocks re-render correctly after a theme toggle.
9. Take screenshots in both modes for the user.

After the checks, announce the file with a 1-3 sentence pointer plus
the top 1-3 takeaways.

## Optional: Mermaid and Prism

The kit doesn't ship with Mermaid or Prism. If the artifact needs
them:

- **Mermaid** bakes theme into rendered SVG at init. On theme toggle,
  re-initialise with new variables and re-render every `.mermaid`
  block. Cache original source in `data-mermaid-src`.
- **Prism** themes are CSS. Ship `prism-tomorrow` (dark) and `prism`
  (light), toggle `disabled` on the `<link>` tags. Or write Prism token
  rules using the page's own CSS variables.

## After the round

- Persistent principles learned in this round → global rules or the
  project's `CLAUDE.md`.
- Project-specific preferences (regulatory framework, language, tone)
  → project `CLAUDE.md`.
- Ephemeral context (current hypothesis, pending decision) → memory.

The artifact itself is the round's deliverable; the rule updates are
the round's compound interest.
