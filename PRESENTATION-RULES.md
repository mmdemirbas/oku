# Presentation rules — the long form

Every rule the user has set down whose reasoning runs longer than the
rule itself. `CLAUDE.md` states each one and points here; this file
carries what broke, why the fix is shaped the way it is, and which
test holds it.

Read the entry before changing anything in `chrome.js`, `chrome.css`
or `renderer.js` that touches its subject. The rules are enforced by
tests — the prose is here so a future session does not "fix" a test
by reverting the decision it was protecting.

## Contents drawer: one button, three states. {#contents-drawer-one-button-three-states}

**Contents drawer: one button, three states.** `page-nav` adopts
`page-toc` as a child at boot so site-tree + on-page TOC stack in one
panel. NO dual-pane, NO right-side TOC.

The panel parks off-canvas at `left: -100%` and is slid in by
`body.drawer-open`, which is set in all three states. The other three
classes carry the differences:

| State | `body` class | Entered by | Leaves on | Moves content |
|---|---|---|---|---|
| peek | `drawer-peek` | hovering the Contents button (mouse/pen) | clicking a link in it, pointer crossing its right edge + 24px, Escape, outside click | no |
| pinned | `drawer-pinned` | **clicking** the button, ≥900px | clicking the button again | yes, insets once |
| modal | `drawer-modal` | clicking the button, <900px | link click, outside click, Escape | no |

- **Peek** is the old behaviour reached without a click: look, jump,
  gone, nothing on the page moves. It is what a reader lands in without
  deciding anything, so it must stay free.
- **Pinned** is the state that answers "I want to see the contents while
  I read". `.layout` gets `padding-left: var(--oku-drawer-w)` and `main`
  re-centres in the remainder; the scroll-spy highlight tracks the
  reading position and the panel scrolls itself to keep that highlight
  in view. **A heading click does not close it** — that auto-close is
  the exact complaint it exists to answer. No scrim, no scroll lock:
  the page behind it is what the reader is reading. Persisted under
  `oku-drawer-pinned`.
- **Modal** is the narrow case. There is no pinned state below 900px
  because the remainder would be narrower than the narrow measure; a
  window that shrinks past the threshold unpins, and one that grows back
  re-pins from the stored flag. The flag is only written when the READER
  changes state, never when the window forces it.

Escape does not dismiss a pinned panel. It is not a dialog — no scrim,
no focus trap, the page behind it live — so there is nothing to rescue
the reader from, and losing the state to a stray keypress costs more.

The pinned inset is the ONE place the kit moves the measure, and it is
a deliberate reversal of the removed edge handle. What CLAUDE.md removed was
an edge handle that both resized and collapsed, always present, moving
text as a side effect of a control nobody asked for. This moves it only
when the reader asks for a panel that has to live somewhere, once, and
moves it back on unpin. Peek — the state you reach without deciding —
still moves nothing at all. `test_a_peek_moves_nothing` and
`test_pinning_insets_the_column_rather_than_covering_it` pin both
halves; do not collapse them back into one rule.

`--oku-drawer-w` is the single source for the panel's width AND the
inset. Two numbers that had to agree would drift on the first tuning.

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
reflows the text every time it is used is what this replaced — the
handle was the problem, not the column: it was always on the page's
edge, it did two jobs at once, and using either one moved the text.
The pinned state above is not a route back to it. There is no handle,
no resize, one button, and the reader gets the same measure back the
moment they unpin.

## The default has to render finished. {#the-default-has-to-render-finished}

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
- Every table ships the whole toolbar — filter, count, both copy
  buttons, gear, expand, sortable columns — whatever its row count. A
  threshold once stripped the first four below seven rows, on the
  reasoning that a reader who can see every row has nothing to filter.
  The toolbar is revealed by hover, so on a small table there was
  nothing to reveal: one table answered the pointer with nothing while
  every larger one answered with six controls, and that reads as the
  kit having lost them. Sorting and column configuration are useful at
  three rows besides. The resting `opacity: 0` is NOT the defect and
  has been reviewed once since — chrome that appears when it is reached
  for is the wanted behaviour, and touch keeps it visible because there
  is no hover to reveal with.
- The cover subtitle falls back to `summary`; a cover holding only an
  h1 gets `.cover-bare`; `updated` is suppressed when it equals `date`.

## One column, one right edge. {#one-column-one-right-edge}

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

## The rail does not move — and opening it is not moving. {#the-rail-does-not-move-and-opening-it-is-not-mov}

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

## Shape says what kind of thing it is. {#shape-says-what-kind-of-thing-it-is}

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

## The top-right corner is one flex row, not five offsets. {#the-top-right-corner-is-one-flex-row-not-five-of}

**The top-right corner is one flex row, not five offsets.** Every button
that belongs there — search, warning, and the presentation menu — is a
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

Within that row, **the menu sits hard right**. It is the one button that
changes what the reader is looking at rather than how it is lit, so it
gets the corner they can hit without aiming — the position the width
cycler used to hold, for the same reason. The order is `order:` values in
one block — read them there, never re-derive.

The flex row fixed the corner's arithmetic. It did not fix the **count**,
and the count is the second failure. Six buttons wanted this corner
(personalize, search, language, warning, theme, width) and text size was
the seventh; six 44px boxes floating over the top of the reading column
is a toolbar the reader has to read before every click, and five sixths
of it is set once and never touched again. So the corner now splits by
FREQUENCY: what a reader uses **while reading** stays out — search, and
the warning indicator, which is not a control at all but an alarm and
must never hide itself — and everything they set once moves into the
menu. See "One button holds every presentation choice" below.

## The width control has three stops, and you can see which one you are in. {#the-width-control-has-three-stops-and-the-icon-h}

**The width control has three stops, and you can see which one you are
in.** `narrow` (860px, a prose measure) · `comfortable` (the default,
1100 → 1240 → 1400 as the screen grows) · `max` (the full width of what
is available, for wide tables and matrices). One stop per thing a reader
wants.

It was a cycler with a three-segment icon, filled left-to-right, because
a 44px box in the corner has no room for words. That icon had to be
hovered to be read and it announced its stops in a `title` nobody opens.
In the presentation menu there is room for one labelled button per stop,
so the state is **visible** rather than announced and the reader picks a
stop instead of cycling to it. The segments are built from `WIDTH_MODES`
rather than written out again — a hand-written list is the second copy
that goes stale, and it already did once: the label named a `wide` stop
that had been removed, so the button announced four stops and cycled
three until the first click replaced the label.

`max` is `--content-width: 100%`, not `100vw`. A viewport unit resolves
against the initial containing block, which the reader's text scale does
not touch, so at 1.25x it asked for 125% of the viewport and the page
scrolled sideways in the one mode meant for wide tables.

There were four. `wide` (1400 → 1560 → 1760) sat between comfortable and
max and answered the same want as max — more room — so a reader cycling
through could not say which of the two they had landed in without
reading the icon, and the icon had to represent the extra level by
filling a segment at 50% opacity, which reads as a rendering fault
rather than as a state. Four labelled stops would not have that
particular defect — but they answer the same want, and a control with
two stops that mean nearly the same thing is one the reader has to think
about. A stored `wide` migrates through
`WIDTH_ALIASES` to comfortable, the nearest surviving band at every
breakpoint; dropping a mode without that would silently reset the
reader's choice. `test_reader_can_cycle_content_width` asserts the mode
set is exactly the three, so adding a fourth fails rather than merely
crowding the row.

## The theme control has three stops, and System is the only auto there is. {#the-theme-control-has-three-stops-and-system-is-o}

**The theme control has three stops, and System is the only auto there
is.** System, Light, Dark, in that order — System first because it is
where a reader starts and the other two are the departures from it. Each
carries its own glyph and the one in force is pressed.

Pressed is keyed off `data-theme-mode`, never `data-theme`. Those answer
different questions: the first is the stop the reader chose, the second
is what the page is painted in, and on System with a dark OS they are
`system` and `dark`. A control keyed off the second lights Dark while the
reader is on System, and looks correct in every light-OS test.

### What it replaced, and why the replacement is smaller

Two stops, Light and Dark, with following the OS surviving as a **policy**
rather than a stop. Three mechanisms held that up:

- you re-entered auto by picking whichever theme the OS was already
  showing, since that is not an override of anything;
- a 4px accent dot on the pressed segment said you were in it;
- an explicit choice **expired** at the next OS flip, and `theme-pref`
  stored `"<chosen>@<os-at-choice>"` so a flip that happened with the tab
  closed expired it too.

All three existed to fit the rule into one corner button that could show
one of two icons. Before that there had been three stops on a cycler, and
two of them rendered identically — with the OS on dark, `system` and
`dark` are the same pixels, so the only way to know which one you were in
was to read the icon. That is a real defect and it is what the cut was
for; what fixes it is **drawing the stops**, not removing one. A
segmented control shows all three at once with the chosen one pressed, so
`system` and `dark` are two visibly different states even when the page
is the same colour.

Both mechanisms cost the reader something, and neither cost is worth
paying once there is room:

- **The expiry meant "always dark" could not be pinned.** A reader whose
  OS runs on a schedule re-picked it once a day. The trade was stated
  when it was made and it was the right trade for a two-icon button.
- **The hand-back gesture had to be known.** The way to auto was to
  understand that clicking a theme you were already in did something
  other than nothing. A drawn stop can be aimed at.
- **The dot was the state, and a dot is not a name.** The stops carry
  their own names, which is what a screen reader reads; the dot carried
  the one distinction that had no name at all.

So a choice holds until the reader changes it, `theme-pref` stores the
bare mode, and the dot is gone with the policy it marked.

### The absence of a key is System

Not a stored `"system"`. A reader who has never touched the control and
one who chose System back are then the same state rather than two that
can drift, and there is no third value for a later branch to forget.
Anything stored that does not name a theme falls back to System, so a junk
value cannot pin a reader to a theme they did not choose and cannot get
out of.

A kit under the old rule stored `"dark@light"`. Under this rule there is
nothing to expire that against, so the first field is simply that
reader's pin: it is honoured, and rewritten to the bare form so the
migration happens once rather than on every load.

`chrome-boot.js` applies all of this pre-paint — the theme has to be on
the element before the first paint or the page flashes the other one —
and `chrome.js` writes it.

### The OS listener moves a following page and only that

`matchMedia`'s `change` handler returns early unless the mode is
`system`. That early return IS the difference between the three stops and
the two they replaced; without it the listener would spend the reader's
pin exactly as the old rule did.

Every path that changes the theme goes through `announceTheme()`,
including the OS flip. A diagram left on the previous theme's palette is
the same bug whether the reader or the clock caused it — the old OS
listener set `data-theme` directly and skipped the event, so Mermaid
diagrams kept the outgoing palette until something else re-rendered them.
The panel syncs off that event too, never off the click handler that
happened to fire it, and the OS flip is the case that proves the
difference: the page moves under an open panel with no click involved.

`test_theme_modes.py` pins the whole rule, including both reversals — a
theme the OS already shows is now a real pin, and an OS flip no longer
spends a choice — and `test_chrome_menu.py` pins that the row is drawn
and operable where the reader now finds it.

## One button holds every presentation choice. {#one-button-holds-every-presentation-choice}

**One button holds every presentation choice.** Text size, column width,
theme, language and snippet placeholders are rows in the panel behind
`.menu-toggle`. The corner keeps search and the warning indicator, and
nothing else.

The split is by **frequency**, not by kind. Search is a thing a reader
reaches for while reading; the warning indicator is not a control at all
but an alarm, and an alarm that hides itself is a bug (it is also the one
button the proximity dimming skips, for the same reason). Everything else
here is set once and then read past for the rest of the session, and a
44px box that is used once per session is a box the reader has to look at
on every click that is not it.

Moving them pays for itself twice, and the second time is the one worth
stating. An icon-only cycler exists **because** the corner has no room
for words — the width control's three-segment icon had to be hovered to
be read, and it announced its stops in a `title` nobody opens. A menu row
has room for a label and for one button per stop, so the state is visible
instead of announced, and the reader picks a stop rather than cycling to
it. The controls did not merely move; they stopped being ciphers.

Three properties hold it together, and each is a decision:

- **Rows register, they are not listed.** Language appears only where the
  manifest offers a variant; personalize only where a snippet declared
  placeholders. Neither knows what else is on the page, which is the same
  problem the flex row solved for the corner and takes the same answer. A
  row that never registers costs nothing and leaves no gap.
  `unregister` exists for the other direction: a row is a claim about the
  page ("there is somewhere to go"), and a manifest replaced at runtime
  that no longer supports the claim must retract it rather than leave the
  previous one pointing nowhere.
- **The panel does not close when a control inside it is used.** Stepping
  the text size is the one thing here a reader does repeatedly — three
  clicks to find the size that suits them — and a menu that closed on the
  first click would make that nine. It closes on Escape (focus returns to
  the button), on a click outside, and on the button again.
- **The button is created lazily and never at module scope.** The rows
  register while the file is being evaluated, and a standalone page
  inlines chrome.js into `<head>`, where `defer` means nothing and
  `<body>` does not exist yet. `ensureButton` returns null rather than
  reaching for a body that is not there; a readyState guard calls it
  again. This is the trap CLAUDE.md already names, and it caught this
  change on the first run of `test_standalone_stored_state.py` — a
  top-level throw there takes the whole kit with it, and the reader who
  sees it has no control left to undo it with.

The panel is a `<body>` child, not a child of the cluster: the cluster is
a flex row of 44px boxes and a 300px panel inside it would size the row.
Each row is a two-track grid — label, control — so the controls line up
down one right edge whatever the labels say in whatever language.

`test_chrome_menu.py` pins the corner's contents, the three ways it
closes, the way it does not, and that a row with nowhere to go is absent.

## The reader can make the document bigger, and the document is all of it. {#the-reader-can-make-the-document-bigger}

**The reader can make the document bigger, and the document is all of
it.** A ladder of eight stops from 80% to 200%, stepped from the
presentation menu, persisted in `oku-text-scale`, restored before first
paint by chrome-boot.js.

"The font size feels too small" is not a request about the body font. A
reader who cannot read the prose cannot read a chart's axis labels
either, so a control that grew the paragraphs and left every figure where
it was would answer the easy half of the complaint and ship looking
finished. The mechanism is therefore **`zoom` on the reading column**,
not a font-size: `zoom` takes text, inline SVG (every chart the kit
draws), Mermaid's output, images and rules together, and unlike
`transform: scale` it reflows — a paragraph at 1.5 wraps at 1.5, it is
not a stretched picture of a paragraph.

Four things follow from that choice, and each is a decision:

- **No chart is re-typeset.** A chart's label gutter is fitted to its own
  labels at render time and shortened after paint (see "A label is fitted
  to the space it has"). `zoom` scales the fitted result whole, so a
  gutter measured at 1.0 is still right at 2.0. A font-size-based scale
  would have invalidated every fit on the page at every step, and the
  charts would have needed a re-render path that does not exist.
- **`100vw` does not scale.** Viewport units resolve against the initial
  containing block, which zoom does not touch. `max` mode is `100%`.
- **A `position: fixed` descendant takes the zoom with it.** The viewport
  coordinate written into `left` is multiplied before it lands, and the
  coordinate came out of `getBoundingClientRect()`, which reports client
  space. Measured before the fix: at 1.25x a chart tooltip landed 189px
  from its bar, at 1.5x 360px. Three of the kit's tooltips live inside
  `main` — chart, bar-chart enhancer, annotated-code — and they go
  through `__okuSetFixedPos`, which divides by `currentCSSZoom`. Every
  other overlay the kit builds is appended to `<body>` and is outside the
  zoomed subtree by construction, which is what made `zoom` viable here.
- **A grid floor must yield.** `minmax(200px, 1fr)` is a width the track
  refuses to go below, and the container is now narrower than it looks —
  the scale divides the available width, so at 2x on a 360px phone a grid
  has 136px to lay out in. Measured: eight compare cards 400px wide in a
  360px viewport. Every auto-fill floor is `minmax(min(Npx, 100%), 1fr)`.
  The same pass found a sparkline row — an `inline-flex` with a fixed
  120px chart in it — sizing to max-content with no `max-width: 100%`,
  which is the defect CLAUDE.md's "every kit box that holds author text"
  rule already names. It overflows at 1x too, given a long enough end
  label; the scale is what made it show up.

**The chrome is not in it, and the sidebar's text is.** The 44px buttons,
the rail's 12px strip and the sidebar's own width are the frame the
document sits in, and their geometry is asserted numerically across four
test files. The sidebar's SCROLL region is in it, because the tree and
the table of contents are text a reader reads; the build footer is not,
so the surface's height contract (invariant 1) is untouched.

**`main`'s padding is divided by the scale**, so the frame around the
column is the same number of physical pixels at every stop. Magnifying
the padding with the text is what a browser's own zoom does, and on a
phone it is the part that hurts: the column is already clamped to the
viewport, so every pixel the padding gains comes off the figure. Measured
at 360px, uncompensated: a chart went from 286px wide to 256px when the
reader stepped the text up one notch — they asked for more and the
picture got smaller.

The ladder has ends and says so. At 80% and 200% the stepper carries
`aria-disabled="true"`, keeps its box and stays where it is; a step that
silently does nothing reads as a broken control. The readout in the
middle is the reset — a fourth box would crowd a three-wide row, and at
100% a separate Reset is a control that does nothing, which is the
disabled state this kit does not ship.

Print resets it to 1. Paper has a fixed page width and its own scale
control in the print dialog, and a page printed at 200% is four times the
sheets for the same words.

`test_text_scale.py` pins all of it: the factor, a chart growing, the
chrome not moving, the sidebar's text scaling and its width not, no
sideways scroll in any width mode at 1440px or 360px, the tooltip landing
on the pointer at four scales, the ends of the ladder, and the choice
surviving a reload.

## A link to a .md file opens the kit's viewer, not the browser's raw text. {#a-link-to-a-md-file-opens-the-kit-s-viewer-not-t}

**A link to a .md file opens the kit's viewer, not the browser's raw
text.** The kit renders markdown for a living; handing the reader to
Chrome's plain-text rendering of a linked file — no typography, no
theme, no way back but the back button — was the kit declining to do the
one thing it does. `__okuMdViewer` renders it in the shared lightbox
frame, over the page they came from: path in the bar, the file's
front-matter title and summary, the rendered document, a **Source** pane
with the exact bytes plus copy, and **Open file** as the escape hatch.
Read-only, deliberately.

Which links reach it is the load-bearing part, and it is a rule about
what the renderer already does. `renderLink` rewrites a *relative* prose
`foo.md` to `foo.html`, because that file is a page in this tree and the
whole page beats a file viewer. What that rewrite deliberately leaves
alone is what the viewer gets: a root-absolute `/notes/plan.md`, any
href inside an HTML island, any `.md` that is not a page here. The click
handler mirrors the kit's existing cross-page handler exactly —
`defaultPrevented`, modifier keys, `button !== 0`, `target`, `download`
all mean "the browser's job, not ours".

The `file://` half is why this touches the CLI at all. A page on a
`file://` origin cannot read the file sitting next to it — the same wall
`renderFromUrl` documents — so `build_standalone` inlines every such
file as `__oku_local_docs__`, **keyed by the href as authored**, which is
exactly what the viewer looks up (`a.getAttribute('href')`). Two sides
normalising a path independently is how they drift; one key, taken from
the source, cannot. `collect_local_docs` therefore collects the same two
shapes the runtime will ask for and no others —
`test_a_relative_prose_link_is_not_carried` is the test that fails on the
day the rewrite rule changes on either side. Anything missing, oversize
or outside the tree is printed at build time, because a standalone that
quietly cannot open its own link reads as a kit bug.

Two things keep a second render pass safe inside a live document, both
in `OkuRenderer.renderMarkdownInto`. Ids are prefixed `okv-N-`: a viewed
file's headings slugify exactly as the page's do, and an unprefixed
collision would send `getElementById` into the overlay for the rest of
the session — the same defect the rail's thumbnail clone rewrites its
ids to avoid. And relative hrefs and image srcs are re-resolved against
the viewed file's own URL, so a link inside it means on screen what it
means on disk. The module-level parser state (anchor ids, link and
footnote definitions, the typed-block hook) is saved and restored around
the pass.

`test_md_viewer.py` and `test_standalone_local_docs.py` pin both halves.

## The kit's own strings follow the page's language. {#the-kit-s-own-strings-follow-the-page-s-language}

**The kit's own strings follow the page's language.** `kit/i18n/<code>.json`
maps the ENGLISH STRING to its translation — not an invented id. The call
sites keep reading as English, so nothing had to be rewritten to
`okuT('btn.close')` and re-verified, and a key with no entry falls back
to itself: a missing translation degrades to what shipped before rather
than to a blank or a raw key. `test_i18n_coverage.py` is what keeps that
from rotting — a new reader-facing string with no entry fails on the day
it is written, and a table entry the kit stopped emitting fails too.

Three shapes, and mixing them up is the defect:

- a **whole literal** is matched exactly by `__okuI18n.localize`, scoped
  to kit-owned elements so author prose is unreachable;
- a **concatenated fragment** (`'Toggle ' + label + ' series'`) must
  become a `{0}` template. Turkish puts the verb last, so a translated
  fragment is broken Turkish however good the fragment is;
- a string **composed at runtime** (`Last updated 2026-08-07`) is not a
  table key at all, so the element carries `data-oku-t` plus its
  arguments and the pass rebuilds it. It replaces the leading text node
  when the element has children — writing `textContent` would take the
  permalink `buildTOC` appended with it.

Load the table lazily, never at module scope: `__okuDocsRoot` is a `var`
assigned thousands of lines below, so an early `load()` fetches
`undefined_oku/i18n/…`, 404s, and memoises the failure for the page.

## Anything the kit hangs off content must never become content. {#anything-the-kit-hangs-off-content-must-never-be}

**Anything the kit hangs off content must never become content.** Three
defects of one shape, each of which rendered as a plausible wrong answer
rather than an error:

- Prism re-highlighting a block that now holds annotation chips and
  tooltips (see the pitfall below);
- the shared copy button reading `code.textContent` at click time, so
  pasting an annotated block gave commentary interleaved with source —
  `<oku-annotated-code>` publishes `_okuCopyText` behind
  `data-oku-copy-source` and the copy pass prefers it;
- table headers cloned into the Cards / List / Board views *after*
  `wireColResize` had injected `.okt-col-resize` into every `th`, which
  is `position: absolute` with a `static` parent there and painted a
  dead full-height resize bar down a view with no columns.

Before reading an element to hand its text to a reader, ask what else
has been put inside it since it was built. `_okuHeadingText` exists for
the same reason: six places need a heading's own words, five had grown
their own copy of the same two removals, search had none (every result
read `Prose primitives#`) and the TOC's h3 entry patched the symptom
with a trailing-hash regex.

## A card answers the pointer with light, never with position. {#a-card-answers-the-pointer-with-light-never-with}

**A card answers the pointer with light, never with position.** Every
card kind used to hover with `transform: translateY(-2px)` and the
Contents tree grew its left padding 8px → 12px. Both take the text with
them. Two to four pixels is too small to read as an effect and exactly
the right size to read as a rendering fault, and it fires on everything
the pointer crosses on its way somewhere else — which is most of the
page, most of the time.

The raise is box-shadow now: a ring grows out of the card's edge
(`--okt-ring-off` → `--okt-ring-on`) and the shadow deepens under it.
Paint only, no layout, so the box a reader is reading from does not
move. The **resting state carries the same layer count as the hover
state**, collapsed to zero blur and zero spread so it paints nothing —
box-shadow interpolates layer-for-layer, and a rule that omits the ring
at rest snaps it on instead of growing it.

Anything that changes a card's box on hover — transform, padding,
border-*width*, font-size — is the defect, not the effect. Border
*colour* is free, and so is opacity.
`test_no_hover_rule_moves_the_content_under_the_pointer` reads every
`:hover` rule in the stylesheet, so a new primitive reaching for
translateY fails on the day it is written; `_NOT_CONTENT` there is the
list of genuine exceptions (a marker dot growing about its own centre,
a `::after` arrow, the sidebar tab thumbs, a donut slice responding
under the pointer that put it there). The geometry itself is pinned in
`test_hovering_a_card_does_not_move_what_is_written_on_it`, to the
pixel — a tolerance is what a 2px nudge hides in.

## A card that promises a picture shows the picture, and the picture is a clone. {#a-card-that-promises-a-picture-shows-the-picture}

**A card that promises a picture shows the picture, and the picture is a
clone.** `compare-grid` takes `preview: true`; every card whose `href` is
an in-page anchor gets a silhouette of the figure after that anchor,
built by `wireComparePreviews` on `oku:rendered`.

The picture is **cloned from the rendered figure**, never authored beside
it. A miniature payload next to the real one is a copy, and a copy drifts
silently — the card keeps previewing a shape its own section stopped
drawing, and nothing fails.

Four things the clone has to survive, each of which broke first:

- **It leaves the host, so the host's CSS stops applying.** 197 rules are
  written `oku-chart .okc-…`; a chart lifted out matches none of them and
  every fill falls back to the initial value, which is BLACK. The clone
  is re-parented into an inert `<oku-chart>` shell — inert by the kit's
  own `_initialized` reparent guard. Copying resolved colours instead
  would freeze them and break on a theme flip.
- **The writing has to go, and it takes two mechanisms because there are
  two media.** SVG `text` is deleted outright — a class list has to be
  extended by whoever adds the next chart type, and the enumeration
  already missed the gauge readout and three row-label sets. The HTML bar
  family is the opposite: its label and value ARE the first and third
  columns of the grid the track spans, so they are hidden with
  `visibility`, never `display`.
- **It must not become a landmark.** `oku-chart` and `.bar-chart` outrank
  `.compare-grid` in `RAIL_FIGURES` and the rail rejects overlap in both
  nesting directions, so a clone claimed the position and the grid lost
  its mark. The rail skips anything inside `.okt-compare-preview`.
- **It must re-fit when its box changes.** The bar family has no viewBox
  and is fitted by transform, so a `ResizeObserver` — not a window
  listener, because the width control and the pinned drawer both change
  the column without resizing the window.

The reason this is written down at length: **the styling half already
existed.** A `.compare-card.compare-card-link` block hid legends and
thickened strokes, `.bar-row` carried a comment about "compare-card
mini-renders", and `docs/charts.md` had told the reader since before the
markdown migration that "each card has a tiny live preview". Nothing ever
drew one, and no check could tell — the schema validates, the structural
lint passes, the tests were green. **An empty box is well-formed.** It
took opening the page. `test_compare_previews.py` now asserts ink, in
pixels, so the next empty box fails instead of rendering.

## A label is fitted to the space it has, and measured after the font lands. {#a-label-is-fitted-to-the-space-it-has}

**A label is fitted to the space it has, and measured after the font
lands.** Reported against a delivered document: a bullet chart's track
names arrived as `.0 tests, as configured` and `lent, spark-extensions`
— the front of every long name gone, no ellipsis, no scrollbar, nothing
to hover. An `<svg>` clips at its viewBox, so a label wider than the
gutter its renderer guessed is not shortened, it is simply absent, and
the reader has no way to know.

The guess was `pad.left = 140`, written when track names were words.
Five renderers had the same constant in them (bullet, box-plot,
ridgeline, range-bar, and bump with the same name at BOTH ends), the
gauge laid its zone chips end to end on one row whatever the width, and
the treemap wrote a name across whatever sat to the right of its cell.
A sweep over every chart type in `kit/schema/examples.json`, each
rendered twice — as authored, then with every label 40 characters
longer — found the whole class: **100 labels outside their viewBox
across 30 of the 53 types**, and three of them (`Mon`, `v5`, `Markdown`)
were clipped on the reference payloads, with nothing long involved.

Three mechanisms, in the order they run:

1. **The gutter is sized from the labels** — `okuFitLabelGutter`, which
   the row-label family already used and these five did not. It caps at
   a fraction of the chart width so the plot cannot vanish, and the
   bullet and box-plot pass `maxLines: 2` because a 42px row has space
   for two lines of an 12px label. **Pass the size the CSS actually
   renders**: the bullet's labels are 12px and its gutter was computed
   for 11px, which is how `Revenue ($M)` — the kit's own example — came
   out as `Revenue ($…`. The estimate errs HIGH on purpose (0.66em per
   character), because too wide costs a few pixels of plot and too
   narrow costs the end of a name.
2. **Labels that sit on an edge anchor inward** — `okuTickAnchor` for
   the first and last category tick, which are centred on a tick that
   sits ON the plot edge, and the connected scatter's point labels,
   which hang off the right of their dot until the dot is past halfway.
3. **Then everything is measured** — `__okuFitSvgTextToViewBox` walks
   every `<text>` after paint, shortens only what still leaves the box,
   and moves the whole string into a `<title>`. It is the backstop for
   what no gutter can fix: a name inside a treemap cell, a node in a
   network, a radial label on a polar chart.

Two things about that measurement are load-bearing and neither is
obvious:

- **Screen rects, not `getBBox()`.** getBBox ignores the element's own
  transform, so every rotated label — heatmap columns, pareto
  categories — measures as if it were horizontal. Measured that way,
  19 labels read as overflowing that were fine.
- **Nothing is measured until `document.fonts.ready`.** The kit loads
  Inter from a CDN, and the same string measures about 5% narrower in
  the fallback face — 271px against 284px on a donut legend label, with
  identical computed style at both readings. A pass that runs before the
  font lands agrees with itself about a width the reader never sees, and
  every label it "fitted" ends up one glyph over the edge. This cost the
  session hours: the fit ran, the labels were trimmed, and they still
  overflowed, while re-running the identical function from a debugger
  converged every time. A `ResizeObserver` per chart re-fits when the
  box changes — the width control has three stops and the lightbox is a
  fourth — and the pass restores the full string before re-deciding, so
  running it again can only improve the answer.

Held by `browser/test_chart_label_fit.py`, which is the sweep itself:
every type in the example set, both variants, plus the reported bullet
payload and a gauge whose legend needs two rows. Four of its seven
assertions fail on the code before this rule.

The sweep also found a chart type that drew nothing at all. `tile-map`
is the name `CLAUDE.md` tells new pages to use and `geo` is the alias
kept for old ones, but `renderer.js` keys the payload by the type the
author wrote and `_renderGeo` only ever looked in `extras.geo` — so the
preferred name produced an empty element. It is the seven-sources
problem again, and the same lesson: **a name an author is told to write
has to be rendered, validated and printable, and only rendering it
proves the first one.**
