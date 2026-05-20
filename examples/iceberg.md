# Iceberg storage layer

*End-to-end demonstration of the JSON-source renderer, glossary tooltips, and the Visual Viewport pinch-zoom fix.*

> 2026-05-17 · Spark+Iceberg team · ~6 min read

> **TLDR**
>

- **JSON** — Source of truth
- **0** — Build steps for content
- **17** — Primitives in v1 library (3 wired in this demo)
- **EN+TR** — Multi-language registry

## Overview

Iceberg gives you ACID transactions, time travel, and schema evolution over object stores. It is engine-agnostic — read it from Spark, Flink, Trino, or anything else that speaks the format. Underneath, it relies on MVCC and snapshots to support concurrent readers and writers without coordination.

> **NEUTRAL: Try the interactive primitives**
> Hover any underlined term to see its definition. Click to pin the tooltip. Move the mouse toward the tooltip to select text inside it. Resize the window — the chrome buttons in the corners use the Visual Viewport API to stay anchored during pinch-zoom.

> **INFO-TIP**
> The HTML host is a tiny stub that loads chrome.css, chrome.js, and renderer.js. It then calls `new HtmlDocRenderer().renderFromUrl('iceberg.json')`. The renderer fetches the JSON, walks the tree, and emits DOM (regular tags + Custom Elements) into `<main id="main-content">`. When the renderer finishes, it fires an `html-doc:rendered` event that chrome.js listens for to build the TOC and initialize reading aids.Custom Elements (glossary-term, ext-ref) register themselves via customElements.define. When the renderer inserts them into the DOM, the browser fires their connectedCallback, and they resolve their term against kit.json + the per-domain glossary files. Tooltip behavior is shared via a single controller — hover with bridge, click to pin, touch-friendly fallback.


## Trade-offs

### Hive tables
Directory-listing-based; no snapshot model. Concurrent writes race. Schema evolution is a manual ALTER. No time travel.
### Iceberg tables
Snapshot-based; readers see immutable views. Concurrent writes resolved via optimistic concurrency on the catalog. Schema evolution is metadata-only. Time travel is a snapshot reference.

The cost: metadata accumulates. Without compaction and expire-snapshots maintenance, the manifest list grows linearly with snapshot count. Both are cheap to run as periodic jobs.

> **INSIGHT**
> The Iceberg catalog is the locking primitive. Two writers don't lock the table; they race to update the catalog's current-snapshot pointer. The loser retries with the new base snapshot. This is what makes concurrent writes possible without a coordinator.


## Engine support — relative capability

### Bar chart
- Spark: 95
- Flink: 80
- Trino: 75
- Snowflake: 60
- DuckDB: 50

Numbers are illustrative — feature coverage shifts release-to-release. The point is the shape: Spark is the deepest integration; analytics engines have been catching up since 2024.


## What's in v1 of this kit (vs. not)



## What's next

This demo covers build steps 1–3, plus the core renderer + tooltip pieces from steps 5–10. Still to wire in subsequent rounds: `<page-nav>` site-tree sidebar, `<live-snippet>`, `<chart>`/`<diagram>`, Pagefind integration, the forward-compat warning indicator, and the html-doc CLI extensions.
