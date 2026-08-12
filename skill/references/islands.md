---
title: HTML islands and hand-drawn SVG
summary: The escape hatch when no primitive fits, and how a hand-drawn figure gets its colour.
---

> [!TLDR]
> Read this before writing an island or a hand-drawn SVG. It is kept
> out of the skill briefing because the briefing is paid on every
> invocation and an island is the rare path — the rule that matters
> (colours come from kit variables) stays inline there, and
> `island-hand-styled` fails the build if it is ignored.

## When a primitive does not fit {#islands}

A block-level HTML tag at column 0 passes through to the DOM untouched
— custom elements, `<script>` and `<style>` included. Full capability,
no restrictions. This is the intended escape hatch, and reaching for it
is not a failure.

**Build on the kit, not beside it.** An island that carries its own
colours ignores the page accent and breaks in the theme the author
wasn't looking at:

```html
<!-- yes: follows the accent, follows light/dark -->
<div class="okt-card" style="background: var(--surface); color: var(--text);
     border: 1px solid var(--border); border-radius: 12px; padding: 16px;">
  <strong style="color: var(--accent-strong)">Heading</strong>
</div>

<!-- no: hardcoded, breaks in dark mode, ignores the accent -->
<div style="background: #f5f3ff; color: #1e1b29;">…</div>
```

`oku check` reports `island-hand-styled` for the second shape. The
variables to build on: `--bg`, `--surface`, `--surface-2`, `--text`,
`--text-soft`, `--text-faint`, `--border`, `--accent`, `--accent-soft`,
`--accent-strong`, `--warning`, `--danger`, `--success`, and
`--series-1` … `--series-10` for categorical data.

### Hand-drawn SVG inside an island

Sometimes the figure genuinely has no primitive — a topology, an
annotated screenshot, a custom geometry. Then:

- **Inline only**, no external URLs. The artifact has to open offline.
- **Colours from variables:** `fill="var(--surface)"`,
  `stroke="var(--text-soft)"`. The theme toggle then needs no JS.
- **`viewBox` + `width="100%"`** so it scales instead of clipping.
- `role="img"` + `aria-label`, or a `<title>` first child.
- Keep it under ~150 lines. Past that the diagram is doing two jobs.

**The hand-positioned-text trap.** Any label placed at a coordinate you
picked by eye will collide at some content density or viewport width.
CSS does not compute label collision; you do, and you will get it
wrong. Two passes before shipping any hand-drawn figure:

1. **Density:** add 50% more items mentally. Do labels overlap?
2. **Viewport:** open it at 360px. Are any two text elements within 4px?

If either fails, the pattern cannot survive a content or viewport
change. Switch to a shape where overlap is structurally impossible — a
row per item, a numbered marker with the text in a table below, a
flex-wrap row of self-contained boxes — or use Mermaid, which solves
collision for you. **Reach for Mermaid whenever a custom diagram would
need four or more hand-positioned labels.**

