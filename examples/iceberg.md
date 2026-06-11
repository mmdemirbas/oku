---
title: Iceberg storage layer
eyebrow: Architecture · demo
subtitle: End-to-end demonstration of the JSON-source renderer, glossary tooltips, and the Visual Viewport pinch-zoom fix.
audience: Spark+Iceberg team
date: 2026-05-17
read_time: ~6 min read
order: 10
summary: Open table format for huge analytic datasets.
accent: teal
---

> [!TLDR]
> This page is rendered entirely from JSON by html-doc's runtime renderer. Glossary tooltips resolve against per-domain registries; the chrome buttons stay anchored during pinch-zoom; visual richness comes from kit primitives, not authored HTML.
>
> - Authoring source = JSON. The file you'd hand to an AI to read, modify, or extend.
> - Renderer = chrome.js + renderer.js running in the browser. No build step for content.
> - Custom Elements provide behavior: tooltips, expandable detail, callouts, charts.
> - Same vocabulary covers reviews, study docs, plan reviews, team briefs.

```oku-kpi-grid
{"tiles":[{"num":"JSON","label":"Source of truth"},{"num":"0","label":"Build steps for content"},{"num":"17","label":"Primitives in v1 library (3 wired in this demo)"},{"num":"EN+TR","label":"Multi-language registry"}]}
```

## Overview {#overview}

Apache Iceberg is an open table format designed to bring database-grade semantics to data-lake storage.

Iceberg gives you [ACID](#g/ACID) transactions, time travel, and schema evolution over object stores. It is engine-agnostic — read it from [Spark](#g/Spark), [Flink](#g/Flink), Trino, or anything else that speaks the format. Underneath, it relies on [MVCC](#g/MVCC) and [snapshots](#g/Snapshot) to support concurrent readers and writers without coordination.

> [!NEUTRAL] Try the interactive primitives
> Hover any underlined term to see its definition. Click to pin the tooltip. Move the mouse toward the tooltip to select text inside it. Resize the window — the chrome buttons in the corners use the Visual Viewport API to stay anchored during pinch-zoom.

> [!TIP] How this page was rendered
> The HTML host is a tiny stub that loads chrome.css, chrome.js, and renderer.js. It then calls `new HtmlDocRenderer().renderFromUrl('iceberg.json')`. The renderer fetches the JSON, walks the tree, and emits DOM (regular tags + Custom Elements) into `<main id="main-content">`. When the renderer finishes, it fires an `html-doc:rendered` event that chrome.js listens for to build the TOC and initialize reading aids.
> 
> Custom Elements (glossary-term, ext-ref) register themselves via customElements.define. When the renderer inserts them into the DOM, the browser fires their connectedCallback, and they resolve their term against kit.json + the per-domain glossary files. Tooltip behavior is shared via a single controller — hover with bridge, click to pin, touch-friendly fallback.

## Trade-offs {#trade-offs}

Iceberg's per-file metadata gives precise time-travel and concurrent-write isolation, but the metadata size grows with snapshot count.

```oku-compare-grid
{"cards":[{"t":"Hive tables","b":"Directory-listing-based; no snapshot model. Concurrent writes race. Schema evolution is a manual ALTER. No time travel.","verdict":"bad"},{"t":"Iceberg tables","b":"Snapshot-based; readers see immutable views. Concurrent writes resolved via optimistic concurrency on the catalog. Schema evolution is metadata-only. Time travel is a snapshot reference.","verdict":"good"}]}
```

The cost: metadata accumulates. Without [compaction](#g/Compaction) and expire-snapshots maintenance, the manifest list grows linearly with snapshot count. Both are cheap to run as periodic jobs.

```oku-insight
{"b":"The Iceberg [catalog](#g/Catalog) is the locking primitive. Two writers don't lock the table; they race to update the catalog's current-snapshot pointer. The loser retries with the new base snapshot. This is what makes concurrent writes possible without a coordinator."}
```

## Engine support — relative capability {#engines}

All major OLAP engines support Iceberg, but feature coverage varies. Bar chart below shows rough capability scores out of 100, where 100 = full read/write/maintenance/predicate-pushdown support.

```oku-chart
{"type":"bar","rows":[{"label":"Spark","value":95,"display":"95 / 100"},{"label":"Flink","value":80,"display":"80 / 100"},{"label":"Trino","value":75,"display":"75 / 100"},{"label":"Snowflake","value":60,"display":"60 / 100"},{"label":"DuckDB","value":50,"display":"50 / 100"}]}
```

Numbers are illustrative — feature coverage shifts release-to-release. The point is the shape: Spark is the deepest integration; analytics engines have been catching up since 2024.

## What's in v1 of this kit (vs. not) {#scope}

Demonstrating compare-grid's in / out verdict variant: parallel columns with semantic borders.

```oku-compare-grid
{"cards":[{"t":"In v1","b":"- JSON-source rendering at runtime (no build)\n- Glossary tooltips with bridge-hover + click-pin\n- Multi-domain, multi-language glossary architecture\n- Visual Viewport API pinch-zoom stability\n- Core primitives: paragraph, callout, insight, info-tip, kpi-grid, compare-grid, step-flow, chart\n- Three-mode theme cycler + sticky TOC + scroll-spy","verdict":"in"},{"t":"Out (later or never)","b":"- Markdown authoring path\n- Client-side routing / SPA navigation\n- Mermaid diagrams (still TODO in build sequence step 11)\n- Live-snippet primitive (build step 12)\n- Pagefind search (build step 13)\n- Server-side rendering","verdict":"out"}]}
```

## What's next {#next}

This demo covers build steps 1–3, plus the core renderer + tooltip pieces from steps 5–10. Still to wire in subsequent rounds: `<page-nav>` site-tree sidebar, `<live-snippet>`, `<chart>`/`<diagram>`, Pagefind integration, the forward-compat warning indicator, and the html-doc CLI extensions.
