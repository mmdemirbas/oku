---
title: Roadmap
subtitle: What just shipped, what's still open, and the locked decisions that shape the kit.
audience: Maintainer
order: 999
summary: Open work, recent landings, and locked design decisions for oku.
accent: amber
---

> [!TLDR]
> Most of the chart kit is interactive now — tooltips, click-pin, cursor sweep, fullscreen-preserving lightbox, deconflicted labels, family-grouped catalog with clickable mini-cards. Open work concentrates on legend interactivity for the long tail, draggable network nodes, lightbox scrollbar + minimap, and nested-language code highlighting.
>
> - Interactivity coverage: 29 / 29 chart variants now fire contextual tooltips on hover with real per-anchor data. Cartesian + ridgeline + sparkline + gauge carry a synced cursor that updates the tooltip per-position.
> - Visual polish: quadrant + bubble label deconfliction is no-fly-zone aware. Parallel-coordinates line stroke 3.6 → 5px with fade-others on hover. Donut/pie pinned slices scale + accent-stroke. Mermaid fonts clamped to 13px, aspect-fit caps tall portrait diagrams.
> - Layout: source / render columns universally box-top aligned (zero pixel delta across 21 / 29 / 5 example-pairs on reference / charts / tables).
> - Tooltip: width-stable across pin states; explicit × close button when pinned; `_tipPinned` flag stops cursor-driven charts from overwriting pinned content.
> - Pick-by-family: 29 clickable mini-cards (one per variant) each with a tiny live render — readers scan the shape they want and click straight into the variant's full example.
> - `oku` is on PATH as a system command (uv tool install).

## Snapshot {#snapshot}

Where the kit sits today, in numbers.

```oku-kpi-grid
{"tiles":[{"num":"29","label":"Chart variants in the kit"},{"num":"29","label":"Variants with rich tooltip + click-pin"},{"num":"19","label":"Mermaid diagram types catalogued"},{"num":"10","label":"Intent families on the charts page"},{"num":"17","label":"Documentation pages clean under oku check --strict"},{"num":"309","label":"Pytest assertions — green"},{"num":"2","label":"Build trees per oku build (standalone / site)"},{"num":"10","label":"Series colour ramp (--series-1..10)"}]}
```

## Chart interactivity by feature {#interactivity}

Which chart types carry which interaction primitive today. Filled cells are shipped; empty cells are queued.

```oku-table
{"headers":["Variant",{"label":"Family","filter":"chips","values":["cartesian","categorical","distribution","part-to-whole","flow","hierarchy","matrix","trend","goal","geo"]},"Tooltip","Click-pin","Hover-highlight","Synced cursor","Fullscreen"],"rows":[["scatter",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["line",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["area",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["bubble",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["quadrant",{"value":"cartesian","values":["cartesian"]},"●","●","●","—","●"],["bar",{"value":"categorical","values":["categorical"]},"●","●","●","—","—"],["stacked-bar",{"value":"categorical","values":["categorical"]},"●","●","●","—","—"],["grouped-bar",{"value":"categorical","values":["categorical"]},"●","●","●","—","—"],["donut",{"value":"part-to-whole","values":["part-to-whole"]},"●","●","●","—","●"],["pie",{"value":"part-to-whole","values":["part-to-whole"]},"●","●","●","—","●"],["waffle",{"value":"part-to-whole","values":["part-to-whole"]},"●","●","○","—","●"],["treemap",{"value":"hierarchy","values":["hierarchy"]},"●","●","○","—","●"],["heatmap",{"value":"matrix","values":["matrix"]},"●","●","○","—","●"],["histogram",{"value":"distribution","values":["distribution"]},"●","●","○","—","●"],["sparkline",{"value":"trend","values":["trend"]},"●","●","—","●","●"],["gauge",{"value":"goal","values":["goal"]},"●","●","—","●","●"],["radar",{"value":"categorical","values":["categorical"]},"●","●","○","—","●"],["box-plot",{"value":"distribution","values":["distribution"]},"●","●","○","—","●"],["bullet",{"value":"goal","values":["goal"]},"●","●","○","—","●"],["slope",{"value":"trend","values":["trend"]},"●","●","○","—","●"],["calendar-heatmap",{"value":"trend","values":["trend"]},"●","●","○","—","●"],["ridgeline",{"value":"distribution","values":["distribution"]},"●","●","○","●","●"],["sankey",{"value":"flow","values":["flow"]},"●","●","○","—","●"],["network",{"value":"flow","values":["flow"]},"●","●","○","—","●"],["scatter-matrix",{"value":"matrix","values":["matrix"]},"●","●","○","—","●"],["parallel-coordinates",{"value":"matrix","values":["matrix"]},"●","●","●","—","●"],["chord",{"value":"flow","values":["flow"]},"●","●","○","—","●"],["geo",{"value":"geo","values":["geo"]},"●","●","○","—","●"]]}
```

> [!NEUTRAL] Symbol key
> ● shipped · ○ queued · — not applicable. Tooltip + click-pin coverage is now complete across all 28 chart variants. Hover-highlight (fade-others when one element is hovered) is still queued for most non-Cartesian types; synced-cursor only makes sense for charts with a sweep axis (Cartesian, ridgeline, sparkline, gauge). Fullscreen lightbox preserves chart interactivity for SVG charts; bar variants are DIV-based and use the page's normal scroll instead.

## Open / in-flight {#open}

Kanban board — filter by area or priority to scope. Each chip filters; the board view groups by status.

```oku-table
{"view":"board","headers":["Item",{"label":"Status","boardOrder":["in-flight","queued","exploring","shipped"]},{"label":"Area","filter":"chips","values":["charts","diagrams","tables","kit","docs","build"]},{"label":"Priority","filter":"chips","values":["P1","P2","P3"]},{"label":"Effort","filter":"chips","values":["S","M","L"]}],"rows":[["Network — draggable nodes so readers can untangle the graph manually",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P1","values":["P1"]},{"value":"M","values":["M"]}],["Interactive legends across all chart types (donut/pie/waffle/radar/box-plot — match Cartesian + bar behavior)",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["Nested code highlighting (JS in HTML, bash in Markdown — sub-language detect inside fenced blocks)",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["Lightbox: scrollbar + picture-in-picture minimap for over-flowing expanded charts",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["Mermaid — investigate residual trim cases on wide architecture diagrams (overflow:hidden now clips, but content shouldn't extend past viewBox)",{"value":"exploring","values":["exploring"]},{"value":"diagrams","values":["diagrams"]},{"value":"P3","values":["P3"]},{"value":"M","values":["M"]}],["Hover-highlight (fade-others) for non-Cartesian charts (donut/pie/waffle/treemap/heatmap, etc.)",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P3","values":["P3"]},{"value":"S","values":["S"]}],["Catalog research — waterfall, marimekko, dot-matrix, joy-plot, sunburst",{"value":"exploring","values":["exploring"]},{"value":"charts","values":["charts"]},{"value":"P3","values":["P3"]},{"value":"M","values":["M"]}]]}
```

## Recent landings {#recent}

Highlights shipped in the current cycle. Full per-commit history lives in git log.

```oku-kpi-grid
{"tiles":[{"num":"29","label":"Chart variants with rich tooltip"},{"num":"5","label":"Charts with synced-cursor sweep"},{"num":"10","label":"Intent-grouped families on charts page"},{"num":"0","label":"Visible label-vs-corner overlaps on quadrant Playwright sweep"}]}
```

- Pick-by-family rewrite — 29 clickable mini-cards (one per variant) with live tiny renders; click goes straight to the variant's full example.
- Charts page regrouped into 10 intent families (Cartesian / Categorical / Part-to-whole / Distribution / Trend / Flow / Network / Multivariate / Goal / Geographic).
- Code / output alignment is universally zero-pixel — boxes line up at top across every example-pair on every doc page.
- Tooltip width is stable across pin states; pinned tooltip gets an × close button; viewport-fixed positioning surfaces it above the fullscreen lightbox.
- Cartesian charts gain a synced vertical-dash cursor + a per-position tooltip listing every series value at the cursor's nearest x.
- Ridgeline + sparkline cursor handlers update the rich tooltip per cursor position (was static-on-enter).
- Quadrant corner-pill + Cartesian legend-cluster are no-fly zones for data labels — `_deconflictLabels` shifts or hides labels that would land in them.
- Bubble legend backdrop fully opaque — a giant bubble can no longer bleed through the chip labels.
- Parallel-coordinates stroke 3.6px resting / 5px hover, fade-others on hover so the highlighted record stands out.
- Donut / pie pinned slices scale + accent-stroke; global focus-outline kill across chart shapes.
- Gauge zones gain optional labels + a cursor-driven value-at-position inspector.
- Mermaid trim mitigation: `.okd-render` now overflow:hidden, aspect-fit caps tall portrait diagrams at 70vh, font-size clamped to 13px for all SVG text.
- Compare-grid cards gain optional `href` — whole-tile clickable. Used by Pick-by-family.
- Tables `wrap: true` per-column for multi-line cell content.
- All html-doc surface references removed (only the GitHub URL remains on the legacy name).

## Locked decisions {#decisions}

Each was an open question once; collected here so future contributors don't relitigate.

- Project name = oku (Turkish 'read!'). Every layer reads `oku`: package (src/oku/), kit CSS prefixes (okt- / okc- / okd-), JS globals (__oku*), event names (oku:*), data-attrs (data-oku-*), and custom-element tag names.
- GitHub remote URL stays at github.com/mmdemirbas/html-doc — the schema $id, the git-clone example, and the jsdelivr CDN URL all point there. The local repo directory name follows the remote.
- Code / output columns inside example-pair MUST align at the top edge of the box. No 24px spacer for non-code outputs — the visible top edges of the code and output columns line up regardless of the output kind.
- Tooltip width is stable across pin states. Pinned vs unpinned switches the footer text + close-button visibility, NEVER the bounding box.
- ext-ref host is NOT a navigation link. Clicking pins the tooltip; the destination URL lives as a clickable domain anchor inside the citation card. One affordance per element.
- Pagefind is a Python dep, not a system binary — `oku[search]` extra pulls `pagefind[bin]>=1.5`.
- Layout = option A (centered document, four-mode content-width cycle: narrow / comfortable / wide / max).
- Tier 3 viz (sankey / network / scatter-matrix / parallel-coordinates / chord / geo) all ship as kit-native chart types — no third-party chart library.
- Charts / tables / diagrams are sub-pages of Reference (meta.parent: 'reference').
- Source format = v3 markdown-first. A page is `.md`: YAML front-matter + a strict-GFM body (no indented code blocks, no setext headings, no lazy continuation — linted, still valid GFM); kit primitives are ```oku-<kind> fences with one compact JSON body; diagrams are ```mermaid fences with an italic caption line; raw block-level HTML islands (script included) pass through to the kit untouched and are audited by `oku check`. Decided after measuring tokens (markdown ≈ 20% leaner than v2 JSON, far leaner than HTML), LLM emission accuracy, and ecosystem direction; HTML-first was evaluated and rejected for repo-resident continually-edited sources. JSON pages (v1/v2) keep rendering via shims; `oku migrate` converts them.
- Build outputs = two trees (standalone, site). No dist/markdown twins — the .md sources are the canonical AI/LLM surface; llms.txt lives at the site docs root.

## Principles {#principles}

Reader-, author-, and maintainer-facing rules every change honours.

- Single LEFT sidebar — TOC + site tree stacked. No right TOC, no mid-edge tab.
- Visual-first authoring. Pros/cons → comparison-cards, metrics → kpi-grid, trade-offs → table-with-chips. Paragraph + bullets is the fallback, not the default.
- Every fix pairs with a Playwright check. Browser-level fixes ship with numeric assertions captured in the commit body.
- Numbers in counters / badges only — no English words baked into the kit.
- No demo sibling pages. Every example for a primitive lives next to its heading.
- No process / round / historical references in docs — describe current behaviour, not how it got there.
- Layout invariants are numeric, not eyeball — express the rule as a boundingBox / computed-style assertion or accept it isn't a rule yet.
