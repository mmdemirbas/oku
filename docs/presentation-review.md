---
title: Presentation defaults
audience: Maintainer
order: 998
summary: What a page looked like when the author wrote only content, what was wrong with it, and what shipped.
---

> [!TLDR] The short version
> The visual language was not the problem. A page whose author wrote only
> content rendered cleanly; what stood between it and a finished page was
> a handful of small defaults, a metadata block asking for ten fields
> before the first sentence, and a briefing that spent more space on
> chrome the author cannot touch than on the blocks they type.
>
> - Seven defects measured on a page with two front-matter fields. All fixed.
> - Front-matter is now `title` + `summary`; the rest is inherited from `kit.json` or derived at build time.
> - The decidable half of the style advice moved into `oku check`, where ignoring it fails.

> [!IMPORTANT] Status
> Everything below shipped. The findings are kept in the past tense with
> their measurements so the numbers stay checkable, and each section ends
> with what changed. The kit build is `2026-08-04-r19`.

## What does a page look like when the author writes only content? {#plain-page}

Two versions of the same page were built and measured in Chromium at
1440px and 390px. One carries the full front-matter block the starter
template asks for. The other carries `title` and `summary` only — what an
author writes when they are thinking about the subject rather than the
page.

The plain version renders cleanly. There is no broken layout, no
horizontal overflow at 390px, no unstyled block. What it has instead is a
set of small defaults that each cost the reader a little.

```oku-kpi-grid
{"tiles":[{"num":"83","label":"characters per line at the default width"},{"num":"2×","label":"the words \"TL;DR\" printed in one card"},{"num":"156px","label":"cover panel height holding one line of title"},{"num":"7","label":"table controls shipped above a three-row table"}]}
```

The measurements behind those tiles, taken from the plain page:

```oku-table
{"headers":["Surface","Measured","Reference point"],"rows":[["Body paragraph","972px wide, 77–83 characters per line, 16px/26.4px","The readable range is 45–75 characters; 66 is the usual target"],["Cover panel","972 × 156px, title at y=101, first section at y=260","With eyebrow + subtitle the same panel is 284px and reads as composed"],["TL;DR card","`<span class=\"tldr-label\">TL;DR</span>` followed by `<h2>TL;DR</h2>`","The label is duplicated whenever the author gives no title"],["TL;DR background","`linear-gradient(135deg, var(--accent-soft), var(--surface-2))`","`--surface-2` was `#f5f3ff` — 12 points of blue over red. It backs 38 rules, so the lavender was everywhere, not just here"],["Table chrome","Filter input, count badge, gear, expand — 7 buttons, 27px strip","The table has three rows and three columns"],["390px width","No horizontal overflow, h1 30px, table fits its wrapper","Narrow rendering is sound; nothing to fix here"]]}
```

## Which of those are defects, and which are trade-offs? {#findings}

Two of them were decided deliberately and are recorded as such in the
source. The rest are unowned.

```oku-table
{"headers":["#","Finding","Kind","What shipped"],"rows":[["1","`> [!TLDR]` with no title rendered the words TL;DR twice — once as the pill, once as the heading. The shipped starter template produced exactly that shape, so it was the default state of the block that opens nearly every page.","Defect","The heading carries `.okt-sr-only` when it would only repeat the pill. It has to stay in the DOM: `buildTOC` skips a section without an `h2`, and the search index reads it."],["2","The TL;DR gradient faded to `--surface-2`, a violet-leaning neutral. Under the default indigo accent that reads as intentional; on a teal page the card faded teal → lavender. Fixing only the gradient left the same lavender on the table header band and the chart tracks — the token backs 38 rules.","Defect, twice","The gradient ends on `--surface`, which has no hue of its own. Then `--surface-2` itself went from `#f5f3ff` to `#f5f4f8` — same family, a quarter of the saturation — so the whole quiet-surface layer stops reading as a colour. A test pins its channel spread at 5."],["3","Body prose ran 77–83 characters per line. `--prose-width` was declared and applied to nothing.","Recorded trade-off, reopened","`--prose-width` is now a `ch` value re-declared per content-width mode. Measured medians 63 / 67 / 78. Visual primitives are untouched."],["4","With no `eyebrow` and no `subtitle` the cover was a 972×156 tinted panel holding one line of text in its top third.","Defect","The subtitle falls back to `summary`; a cover holding only an `h1` gets `.cover-bare` and shrinks to fit."],["5","A three-row table shipped a filter input, a count badge, a gear popover and an expand button, then stretched three short cells across the full content width.","Defect","At or below `SMALL_TABLE_ROWS` the table sizes to its content and keeps copy + expand. The controls stay in the DOM with their listeners bound; CSS hides them."],["6","`date` and `updated` were separate hand-maintained fields and the cover printed both. On `architecture.md` they were the same date in two styles.","Design","`updated` is derived from the file's last commit date, and suppressed when it equals `date`."],["7","`read_time` was hand-written prose on four pages — and `architecture.md`'s was already a minute off the body it described.","Design","Derived at 220 wpm, omitted below two minutes. Setting it by hand still wins and earns an info note."]]}
```

Finding 3 is the one worth arguing about, because it was decided on
purpose. `chrome.css` carries the reasoning: the asymmetric model — prose
clamped to `--prose-width`, visuals bleeding to `--content-width` — was
retired because authors expect the width toggle to act uniformly across
every block kind. That is a real objection and the note is right that the
asymmetric model surprised people.

The cost of the resolution landed on the default reading experience,
which is the surface this page is about. What shipped is a middle
position that keeps the toggle uniform: prose has a `ch`-based cap that
scales with the same toggle rather than ignoring it.

```oku-table
{"headers":["Toggle setting","Content width","Prose cap","Measured median"],"rows":[["narrow","860px","54ch","63 characters"],["comfortable (default)","1100px","62ch","67 characters"],["wide","1400px","72ch","78 characters"],["max","100vw","none","uncapped (142)"]]}
```

Prose still responds to the toggle in the same direction, so the control
keeps its meaning; it responds on a curve suited to reading rather than
to a chart. The `ch` values are calibrated rather than chosen — `ch` is
the width of "0", wider than the average character in running prose, so
the rendered line runs about 1.1× the nominal figure. A reader who wants
full-bleed prose still has `max`.

## Why does the author fill in ten metadata fields? {#front-matter}

The `meta` schema carries ten fields: `accent`, `eyebrow`, `subtitle`,
`audience`, `date`, `updated`, `read_time`, `lang`, `order`, `summary`.
The starter template asks for seven of them as placeholders before the
first heading. Every one is a presentation decision, and the eleven pages
in this tree show what authors actually do with them.

```oku-table
{"headers":["Field","What the eleven pages show","Reading"],"rows":[["`subtitle`","Identical to `summary`, verbatim, on `charts.md`, `diagrams.md`, `tables.md`","Two fields, one sentence, written twice"],["`accent`","teal on 8 pages, amber on 2, indigo on 1","A per-page knob used as a per-tree setting"],["`audience`","`Author` on 7 pages, `Maintainer` on 2, absent on 2","Near-constant within a tree"],["`eyebrow`","`Reference`, `Reference · charts`, `Reference · tables`","Restates the tree position the nav already shows"],["`date` + `updated`","Both present on 4 pages; identical on `architecture.md`","Two hand-maintained dates; one is derivable"],["`read_time`","`~7 min read`, `~4 min read`, `~6 min read`, `~15 min read`","Hand-counted, and silently wrong after the next edit"]]}
```

`kit.json` already exists as the tree-level configuration — it carries
`name`, `description`, `domains`, `lang`, `lang_fallback`. It carries no
accent. The right home for a tree-wide colour is already built and is not
wired to the one field that most wants to live there.

> [!IMPORTANT] The kit already states the test this surface fails
> `docs/design-review.md` records the contract for adding any primitive:
> *"Can AI emit this in one obvious shape, with no per-page judgement
> calls?"* The front-matter block asks for seven judgement calls before
> the first sentence, and the pages show six of them being answered the
> same way every time.

**What shipped.** The authored set is `title` and `summary`, plus
`order` / `parent` where a page has siblings. `accent` and `audience` are
tree defaults in `kit.json`. `read_time` is derived at 220 words per
minute and omitted below two minutes; `updated` is the file's last commit
date — deliberately not the mtime, since a fresh clone would stamp the
whole tree as updated today, which is worse than showing nothing because
it looks like information. An authored value always wins, and every
derived key is recorded in `m._derived` so `page_to_md` can skip it. That
last part is load-bearing: without it one `oku migrate` would write every
derived value back into the source and freeze it stale. A test drove the
leak out.

The eight docs pages dropped what they no longer needed to say. The
overrides that carry real information stayed — `Maintainer` on two pages,
amber and indigo accents on three.

## Why did the briefing teach CSS the author cannot touch? {#briefing}

The authoring surface is a markdown file with typed fences. The briefing
an agent read before writing one was 681 lines, and the balance inside it
ran against that surface.

```oku-table
{"headers":["What the briefing spends space on","Lines","Applies to a `.md` page?"],"rows":[["Page chrome, theme switcher, TOC behaviour","63","No — the kit owns all three"],["CSS token system, accent in `:root` blocks, visual language","54","No — a `.md` page has no stylesheet"],["SVG conventions, layout discipline, hand-positioned label traps","70","Rarely — only inside an HTML island"],["Mermaid and Prism loading","12","No — the kit lazy-loads both"],["Everything else — workflow, verification, content principles, tone","482","Yes"]]}
```

Roughly two hundred lines instructed on chrome the kit owns — and parts
of it had gone stale: the TOC section still described `body.toc-collapsed`
and an off-canvas `nav.toc.open`, both replaced by the Contents drawer.
Against that, the five layout primitives an author actually types —
`oku-chart`, `oku-table`, `oku-kpi-grid`, `oku-step-flow`,
`oku-compare-grid` — had seven mentions in total. The section titled
"Diagram patterns — the primary vocabulary" described them as *"all
implementable in inline SVG or HTML+CSS — no external libraries
needed"*, which was true before the kit shipped its chart renderers and
its Mermaid loader.

An agent reading that came away primed to hand-position SVG labels and
define `:root` accent variables — the opposite of the aim.

**What shipped.** Those sections are gone, replaced by three: what the
kit owns and must not be rebuilt; the primitive vocabulary as a
pick-by-relationship table; and HTML islands, which keep full capability
but build on the kit's classes and CSS variables so they follow the
accent and the theme. The compressed layout-discipline material — the
hand-positioned-text trap and the two-pass test — moved inside the
islands section, which is the only place it still applies. The same five
primitives now have fifteen mentions and the raw-CSS instruction is at
zero.

## What changed, by side of the boundary {#proposals}

```oku-compare-grid
{"cards":[{"t":"Kit — the default renders finished","b":"TL;DR label printed once, heading kept for the outline. Gradient fades to `--surface`. Cover subtitle from `summary`, bare cover shrinks to fit, `updated` suppressed when it equals `date`. Prose capped on a `ch` scale that still tracks the width toggle. Small tables size to content and drop the controls that had nothing to act on.","accent":"success"},{"t":"Author — the decisions are gone","b":"Front-matter is `title` + `summary`. `accent` and `audience` live once in `kit.json`. `read_time` and `updated` are derived, and never written back into a source. The starter template asks for two fields instead of nine.","accent":"accent"},{"t":"Briefing — rebalanced toward content","b":"Chrome, CSS-token, theme and SVG-convention sections deleted; the kit owns them. In their place: the primitive vocabulary, and how to build an HTML island on the kit's variables. Layout discipline survives where it still applies.","accent":"warn"},{"t":"Not changed","b":"No new primitive, no new chart type, no new schema surface. Every item above removes a decision or fixes a default. The catalog was not the problem the reader was having.","accent":"muted"}]}
```

## How does it stay fixed? {#enforcement}

Style advice written in prose decays, because nothing fails when it is
ignored. The briefing currently asks the agent to run a subjective visual
audit before delivery — a density gate, a covering test, a two-pass
overlap check. Those are good instructions and they are unenforceable.

`oku check` runs on every build and refuses to ship on error. Its issue
codes were structural and correctness-shaped: schema violations,
unparseable JSON, shadowed sources, deprecated kinds, duplicate anchors,
unresolved glossary terms, chart payload sanity. It carried nothing about
presentation.

Five rules moved there:

```oku-step-flow
{"ordered":false,"steps":[{"t":"redundant-meta","b":"`subtitle` verbatim from `summary`, `updated` from `date`, or a field repeating the `kit.json` default. Two fields, one sentence.","meta":"warning"},{"t":"hand-set-derivable","b":"`read_time` or `updated` written by hand where the build works it out. The override is legitimate; going stale silently is not.","meta":"info"},{"t":"prose-only-section","b":"Three or more paragraphs with nothing for the eye. A callout does not count — a coloured box around a paragraph is decorated text, and counting it would let any page pass by adding one.","meta":"warning"},{"t":"island-hand-styled","b":"An HTML island carrying hardcoded colour or its own `<style>`. Built on `var(--accent)` and the `.okt-*` classes it follows the page; hand-rolled it does not.","meta":"warning"},{"t":"accent-divergence","b":"Three or more pages in a directory picking different accents with no default in `kit.json`. Two pages disagreeing is a coincidence.","meta":"info"}]}
```

Each is decidable without judgement. What needs a reader — whether the
figure carries the point, whether the visual vocabulary is varied — stays
out on purpose: a check that guesses trains authors to ignore checks.
That part is what the briefing now asks for, and nothing else.

The rules found one real prose-only section on their first run, in this
repo's own `design-review`, where the two failure modes and the two
questions were carried by three paragraphs. They are a compare-grid and a
step-flow now, which is what the section was describing anyway.

## What was not checked {#limits}

Stated so the findings are not read as wider than the evidence.

- Measurements come from two pages in Chromium at two widths. No other
  browser, no other viewport, no print stylesheet.
- Dark theme was not measured. The TL;DR gradient finding is from the
  light theme; the dark-theme value may differ.
- The line-length figure is from one page's prose. It follows from the
  container width, so it will hold across pages at the same setting, but
  it was measured once.
- The briefing line counts are section spans, not a semantic
  classification of every line. Treat them as proportions, not exact
  figures.
- Dark theme is still unmeasured. The gradient now fades to `--surface`,
  which is defined in both themes, but no dark-theme measurement was
  taken.
- The reading-time constant (220 wpm) is a convention, not a measurement
  of this corpus's readers.
- `updated` derives from `git log`, so a page in an untracked directory
  gets no date at all. That is the intended failure mode, not an
  oversight, but it means the field is absent more often than it is
  wrong.
