# Chart-library syntax research

Dated 2026-05-27. Survey of the seven mainstream JS chart libraries plus
the two BI tools, for the purpose of guiding oku's chart-syntax
unification (current state: 29 chart types — exploring a
`type: "plot", marks: [...]` collapse). Sources are listed at the
bottom; figures are pulled from npm, GitHub, and the official docs as
of the date above.

---

## TL;DR

- **State of the art** in 2026 is split into three camps: grammar-of-
  graphics JSON (Vega-Lite), grammar-of-graphics code (Observable Plot),
  and one-`type`-per-chart declarative JSON (ECharts, Plotly, Highcharts,
  Chart.js). D3 sits below the chart layer as primitives.
- **Recommended baseline for oku**: **Vega-Lite's grammar**, adapted to
  oku's authoring shape. The mark/encoding split is exactly what a
  `type: "plot", marks: [...]` collapse needs, and Vega-Lite has spent
  ten years working out the edge cases. Observable Plot is the same
  mental model in code form — useful as a sanity check, not as a wire
  format because it's a JS function-call API.
- **What NOT to copy**: Vega-Lite's transform pipeline (DSL inside a
  DSL — opaque to AI authors), ECharts' option-bag-per-type schema
  (29 sibling schemas, the very problem oku is trying to escape), and
  Plotly's `type: "scatter"` for line charts (mode is the type,
  surprise-level high for AI authors).

---

## Per-library snapshot

### 1. Vega-Lite — grammar-of-graphics in JSON

Syntax shape (line chart, minimum viable):

```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
  "data": { "values": [ {"date": "2026-01", "v": 10}, ... ] },
  "mark": "line",
  "encoding": {
    "x": { "field": "date", "type": "temporal" },
    "y": { "field": "v",    "type": "quantitative" }
  }
}
```

How types are expressed: **one `mark` field** ("line", "bar", "point",
"area", "rect", "tick", "rule", "circle", "square", "geoshape", "text",
"arc", "trail", "image", "boxplot", "errorband", "errorbar"). The
encoding map (`encoding.x`, `encoding.y`, `encoding.color`,
`encoding.size`, `encoding.shape`, `encoding.opacity`, ...) is the same
schema regardless of mark.

Data reuse across types: **best-in-class**. Switch `"mark": "line"` to
`"mark": "bar"` and the same encoding gives a bar chart. The Vega-Lite
paper makes this an explicit design goal — encodings are independent of
mark. Layered charts share a top-level encoding and each layer
overrides only the mark.

AI-friendliness: **5/5**.
- One required top-level mark, one required encoding object. Closed-set
  vocabulary (15 marks, ~12 channels). Schema published, validatable.
- Discoverable: every example on the gallery follows the same shape.
- Low-surprise: a generated line→bar transformation is a one-token edit.
- The trap (transform pipelines, selections, parameters) lives behind
  optional keys; an AI author who stays in `data + mark + encoding`
  never hits it.

Popularity:
- GitHub stars 5.1k, npm weekly downloads ~285k, latest 6.4.3 (May 2026).
- Smaller download count than ECharts/Chart.js because Vega-Lite is
  usually consumed via tools (Streamlit, Altair, Observable, Apache
  Superset includes a Vega-Lite layer alongside ECharts).

### 2. Observable Plot — mark-composition in code

Syntax shape (line chart):

```js
Plot.plot({
  marks: [
    Plot.ruleY([0]),
    Plot.lineY(stocks, { x: "Date", y: "Close" })
  ]
})
```

How types are expressed: **mark composition**. `Plot.line`, `Plot.dot`,
`Plot.bar`, `Plot.area`, `Plot.rule`, `Plot.tick`, `Plot.cell`,
`Plot.text`, `Plot.image`, `Plot.arrow`, ... ~40 mark constructors. A
chart is `Plot.plot({ marks: [...] })`. Multiple marks of different
types compose in one plot (line + dots + zero-rule is canonical).

Data reuse: **strong, but coupled to JS**. The same data array drives
any mark. Channel options (`{x, y, stroke, fill, ...}`) generalize
across mark types the way Vega-Lite's encodings do. The difference is
that this is a JS function call, not a serializable spec — you can't
ship a Plot chart as JSON without serializing the marks back through
a builder.

AI-friendliness: **3/5** as a wire format, **5/5** as a runtime API.
- Composition model is exactly right for AI: small set of marks,
  uniform channel options.
- But it's JS code. An AI emitting JSON has to either (a) write JS
  strings (lossy, hard to validate) or (b) re-invent a JSON layer on
  top — which is what Vega-Lite already is.

Popularity:
- GitHub stars ~5.3k, active release cadence (last commit May 2026).
- Smaller user base than the JSON-first libraries; D3 team's heir to
  D3's chart-authoring story.

### 3. D3 — low-level primitives

Syntax shape: **none — not a chart spec**. D3 ships scales, axes, shape
generators, layouts, selections, transitions. A "line chart" is dozens
of lines: scale construction, axis rendering, path data via
`d3.line()`, DOM append.

How types are expressed: **separate code per chart**. Every chart is
hand-built. No `type` field exists.

Data reuse: same data flows through any custom code, but visualization
swap = rewrite. D3 is the substrate; chart-spec abstractions sit on top
(Plot, Vega-Lite, Plotly, Chart.js all use D3 internally to varying
degrees).

AI-friendliness: **1/5 as a spec language, 4/5 as a target**.
- No declarative surface — every AI emission is bespoke imperative code.
- But because D3 is so widely understood, AI tools can emit D3 with
  reasonable fluency when there's no other choice.
- Wrong layer for oku's question.

Popularity:
- GitHub stars 112k (highest in the survey).
- Ubiquitous as a transitive dependency. Direct end-user adoption has
  trended toward Plot/Vega-Lite/ECharts for the last 5 years.

### 4. Apache ECharts — option-bag JSON, one schema per type

Syntax shape (line chart):

```js
option = {
  xAxis: {},
  yAxis: {},
  series: [{ type: "line", data: [10, 22, 28, 23, 19] }]
}
```

How types are expressed: **`series[i].type`**. Each value of `type`
(`"line"`, `"bar"`, `"scatter"`, `"pie"`, `"radar"`, `"map"`,
`"treemap"`, `"sunburst"`, `"boxplot"`, `"candlestick"`, `"heatmap"`,
`"graph"`, `"lines"`, `"sankey"`, `"funnel"`, `"gauge"`, `"parallel"`,
`"pictorialBar"`, `"themeRiver"`, `"calendar"`, `"custom"`, ...) gates
a **distinct option subschema**. ECharts has ~22 series types plus
auxiliary components (visualMap, dataZoom, polar, radar, geo, ...).

Data reuse: **partial**. ECharts has a `dataset` component that lets
you point multiple series at the same data and pick fields via
`encode`. Without `dataset`, each series has its own `data` array.
Switching `type: "line"` to `type: "bar"` mostly works for cartesian
charts but cross-coordinate-system swaps (cartesian → polar → radar →
geo) often need different surrounding components.

AI-friendliness: **2/5**.
- Each type's option subschema is large and idiosyncratic. AI authors
  often produce mismatches (e.g. `radius` for `pie` vs `bar`).
- The schema page is famously huge (one HTML page, ~10k options).
- Mitigating factor: very widely indexed, training data is plentiful.

Popularity:
- GitHub stars ~66k, npm weekly downloads ~1.1M, latest 6.1.0 (May
  2026). Most powerful of the JSON libraries by feature surface.

### 5. Plotly.js — declarative JSON, trace-based

Syntax shape (line chart, written as scatter):

```js
const data = [{ x: [1,2,3,4], y: [10,15,13,17], type: "scatter", mode: "lines" }];
Plotly.newPlot("div", data);
```

How types are expressed: **`trace.type`** (~40 trace types: `scatter`,
`bar`, `pie`, `heatmap`, `histogram`, `box`, `violin`, `surface`,
`scatter3d`, `scattergl`, `choropleth`, ...). **Line chart is
`type: "scatter", mode: "lines"`** — the type/mode split is a known
gotcha.

Data reuse: traces share the top-level `layout`. Within a trace, swap
the `type` and most channels stay; cross-coord-system swaps (cartesian
→ ternary → 3d) require switching axis sets in `layout`.

AI-friendliness: **3/5**.
- Wide trace taxonomy is discoverable; the schema is published.
- The scatter-equals-line gotcha and the type-vs-mode split surprise
  AI authors. The mode value also depends on the trace family (`lines`,
  `markers`, `lines+markers`).

Popularity:
- GitHub stars 18.2k, latest 3.5.1 (May 1 2026).

### 6. Highcharts — declarative JSON, series-based, commercial

Syntax shape:

```js
Highcharts.chart("container", {
  chart: { type: "line" },
  series: [{ data: [10, 22, 28, 23, 19] }]
})
```

How types are expressed: **`chart.type` (default) and/or
`series[i].type`** — series type is inherited from chart.type, with
per-series override for mixed charts. ~50 chart/series types
(`line`, `bar`, `column`, `area`, `pie`, `scatter`, `bubble`,
`heatmap`, `treemap`, `sankey`, `dependencywheel`, `funnel`,
`pyramid`, `gantt`, `xrange`, `polygon`, ...).

Data reuse: data arrays are series-local. Same data can drive multiple
series types via `plotOptions.series`. Type swap is one field.

AI-friendliness: **3/5**.
- One-field type swap is good.
- Per-type option subschemas are documented per series but the API is
  vast (Highcharts has Highcharts Core, Highcharts Stock, Highcharts
  Maps, Highcharts Gantt — each with its own type vocabulary).
- Commercial license limits training-data sprawl in code samples.

Popularity:
- GitHub stars 12.4k, npm weekly downloads ~2.1M, latest core 12.5.0
  (Jan 2026), latest grid v2.3.0 (Mar 2026). Trusted by 80 of the
  world's 100 largest companies per their marketing.

### 7. Chart.js — minimal declarative JSON

Syntax shape:

```js
new Chart(ctx, {
  type: "line",
  data: {
    labels: ["Jan","Feb","Mar"],
    datasets: [{ label: "S1", data: [10,22,28] }]
  }
});
```

How types are expressed: **top-level `type`** (`line`, `bar`, `radar`,
`doughnut`, `pie`, `polarArea`, `bubble`, `scatter`). ~8 types. Mixed
charts allow per-dataset type via `datasets[i].type`.

Data reuse: very strong for the small type set. Same `labels` +
`datasets` shape powers any cartesian or radial chart by swapping
`type`.

AI-friendliness: **4/5**.
- Tiny type vocabulary, uniform `data: { labels, datasets }` shape,
  one-field swap.
- Cap: only ~8 types. Anything beyond covers needs plugins or other
  libraries.

Popularity:
- GitHub stars 67.4k (highest among declarative JSON chart libs), npm
  weekly downloads **10.4M** (highest in this survey), latest 4.5.1
  (October 2025).

### 8. Superset / Metabase — BI layers, not chart-spec authors

Neither defines a novel chart-spec format that competes with the
above. Superset's chart configurations are persisted as JSON in its
own dashboard schema, but the *rendered* charts use ECharts (with an
"Advanced ECharts Option Editor" exposing the underlying ECharts JSON
via deep-merge). Metabase's Representation Format is YAML/JSON for the
*content* tree (questions, dashboards, cards) — the chart rendering
underneath is its own JS code, not a public spec.

Implication for oku: there is no third syntax family worth borrowing
from BI tooling. The interesting designs all live in the seven
above.

---

## Synthesis

### State of the art, 2026

Two design philosophies dominate, and the boundary is sharp.

**Camp A — grammar of graphics (mark + encoding).** Vega-Lite and
Observable Plot. One small mark vocabulary (~15-40 items), uniform
encoding/channel object that works across marks. Chart "types" are
emergent: a line chart is `mark: line` with x/y encodings; a bar chart
is `mark: bar` with the same encodings. Composition (layers, facets,
concat) is first-class. Both came from research on how to make
visualization specs *generative* — given an encoding, the renderer
picks defaults that make it readable, and a small JSON change yields a
semantically different chart. This is the camp that's easy for AI to
author *correctly* because the surface area is small and consistent.

**Camp B — one-`type`-per-chart with per-type options.** ECharts,
Plotly, Highcharts, Chart.js. Each chart type has its own subschema;
options like `radius`, `roseType`, `barWidth`, `nodeAlign` exist only
for some types. This is the camp that's easy for AI to author *broadly*
(training data is plentiful) but hard to author *correctly without
checking* — a wrong-key emission validates structurally and renders
wrong, or fails silently. This camp wins on feature surface (ECharts'
sankey, Highcharts' gantt, etc.) but loses on uniformity.

D3 sits below both — substrate, not chart spec.

The *consumption* market still favors Camp B (Chart.js, ECharts,
Highcharts have the install numbers). The *expressiveness* camp is
Camp A. oku is closer to Camp A's question because it's trying to
collapse 29 sibling schemas — Camp B *is* "29 sibling schemas," that's
its native shape.

### Which syntax oku should take cues from

**Vega-Lite.** Specifically: its mark/encoding split is the
strongest declarative analogue to the `type: "plot", marks: [...]`
collapse oku is considering, and it's been pressure-tested over a
decade. What to steal, concretely:

- **One closed-set mark vocabulary, decoupled from data shape.** Vega-
  Lite's 15-mark vocabulary covers the bulk of mainstream chart types
  through encoding combinations rather than through 15 separate
  subschemas. For oku, this means a single `marks` array of mark
  objects, each with one `type` from a closed enum, and a shared
  encoding/channel model that applies uniformly.
- **Encoding channels as the spec for "what the data means."** `x`,
  `y`, `color`, `size`, `shape`, `opacity`, `tooltip`, `text` —
  uniform across marks. The data-type tag (`temporal`,
  `quantitative`, `ordinal`, `nominal`) on each channel is what
  drives default axis scales, formats, legends; this also gives oku's
  renderer a place to make smart choices without authors fighting
  defaults.
- **Layered composition under one top-level encoding.** Vega-Lite's
  `layer:` and `concat:` are conservative — they let multiple marks
  share an encoding without re-stating it, which is exactly the win
  Observable Plot gets through `marks: [...]` but expressed as JSON.
- **The schema-first stance.** Vega-Lite ships a JSON Schema (`v6.json`)
  that validates every spec. oku already validates docs against
  `kit/schema/page.schema.json`; a chart sub-schema in the same style
  becomes one more closed surface AI authors can target safely.
- **The mark-as-string shorthand.** Vega-Lite accepts both
  `"mark": "line"` and `"mark": { "type": "line", ... }`. Short form
  for the 80% case, long form for the 20%. oku's current chart shapes
  vary too much in verbosity for casual cases; this shorthand
  precedent is the cheapest improvement on AI-authoring ergonomics.

Observable Plot is the same mental model but as JS. Read its mark
catalog and channel naming for sanity-check — if a name is used both
in Vega-Lite and in Plot, that's the schelling-point naming for oku.
Diverge only where one of them is clearly wrong.

### What NOT to copy

- **Vega-Lite's transform pipeline.** `transform: [{ filter: ... },
  { aggregate: ... }, { window: ... }, { regression: ... }]` is a DSL
  inside a DSL — powerful, but opaque to AI authors and a documented
  source of confusion. oku's chart layer should keep transforms out
  of the spec; if a user needs aggregation, they aggregate before
  authoring. Push transform into the surrounding doc layer if at all.
- **Vega-Lite's `params` / `selection` interactivity DSL.** Same
  reason — a second grammar layered on top of the first. oku's
  interactivity (hover, click-pin, legend toggle) already lives in
  chrome.js as imperative code triggered by `data-oku-*` attrs; keep
  it there.
- **ECharts' "every type has its own subschema."** This is the
  current oku shape and it's what the unification is trying to
  escape. Don't reproduce it under a new name.
- **Plotly's "line chart is `type: scatter, mode: lines`."** The
  type-vs-mode split, where the same `type` value covers points
  *and* lines and the difference lives in a sibling field, is the
  exact "surprise the AI author" anti-pattern. If oku has multi-
  encoding marks (e.g. line + dot overlay), express it as
  composition (`marks: [{type:"line",...}, {type:"point",...}]`), not
  as a sibling-field switch on one mark.
- **Highcharts' chart.type + series.type inheritance.** Two ways to
  set the same thing creates ambiguity (which wins when they
  disagree?). Pick one location for type. The mark-on-mark approach
  Vega-Lite takes — type lives on each mark, no inheritance — is
  simpler.
- **Chart.js' tiny vocabulary as the ceiling.** Chart.js is the
  cleanest schema in the survey but it can't express sankey,
  parallel-coords, treemap, chord, geo. Don't anchor oku's mark
  catalog at Chart.js's 8 types; the catalog should be Vega-Lite's
  ~15 plus the niche ones oku already supports (sankey, network,
  scatter-matrix, parallel-coordinates, geo, chord) — kept as marks,
  not as `type` values that gate sibling schemas.

---

## Library scorecard

| Library | Type model | AI-fit | Stars | Weekly npm | Last release |
|---|---|---|---|---|---|
| Vega-Lite | mark + encoding (15 marks) | 5/5 | 5.1k | 285k | 6.4.3 (May 2026) |
| Observable Plot | mark composition (~40 marks, JS) | 5/5 runtime, 3/5 spec | 5.3k | n/a | active May 2026 |
| D3 | primitives (no type field) | 1/5 spec / 4/5 target | 112k | huge transitive | ongoing |
| ECharts | one `series.type`, ~22 subschemas | 2/5 | 66k | 1.1M | 6.1.0 (May 2026) |
| Plotly.js | one `trace.type`, ~40 types + mode | 3/5 | 18.2k | n/a | 3.5.1 (May 2026) |
| Highcharts | `chart.type` or `series.type`, ~50 types | 3/5 | 12.4k | 2.1M | 12.5.0 (Jan 2026) |
| Chart.js | top-level `type`, ~8 types | 4/5 | 67.4k | 10.4M | 4.5.1 (Oct 2025) |
| Superset | uses ECharts under the hood | — | — | — | — |
| Metabase | YAML repr for content, not chart-spec | — | — | — | — |

Stars/downloads as of late May 2026. "Weekly npm" omitted where the
library is consumed primarily via CDN or a meta-package.

---

## Concrete recommendation for oku

1. Adopt **`type: "plot"`** as the umbrella, with a required
   `marks: [...]` array. Inside each mark, **one `type` field** from a
   closed enum (start: `line`, `bar`, `point`, `area`, `rect`, `rule`,
   `tick`, `text`, `arc`, `geoshape`, plus the niche marks oku already
   ships — `sankey`, `chord`, `network`, `scatter-matrix`,
   `parallel-coordinates`).
2. Hoist `encoding` / channels (`x`, `y`, `color`, `size`, `shape`,
   `opacity`, `tooltip`) to the plot level **and** allow per-mark
   overrides. Channels carry a `type` tag (`temporal`, `quantitative`,
   `ordinal`, `nominal`) — this is what drives default axes and
   formats.
3. Accept both `mark: "line"` shorthand (where the mark has no
   per-mark options) and the full `{type: "line", ...}` object.
4. Keep transforms, selections, animation OUT of the spec. If a future
   need appears, layer it as a separate doc-level primitive, not as a
   sub-grammar inside chart JSON.
5. Validate the chart sub-schema in `oku check` the same way
   `page.schema.json` is validated today.

This collapses the 29 sibling schemas into ~one schema with ~15 mark
shapes. AI authors get a closed vocabulary; humans get less to learn
to author a non-trivial chart; oku's renderer dispatches off the mark
type rather than the chart type, which matches how chrome.js's bar/
line/scatter/pie code paths already overlap.

---

## Sources

- [Vega-Lite docs (mark, encoding)](https://vega.github.io/vega-lite/docs/) /
  [line example](https://vega.github.io/vega-lite/examples/line.html) /
  [npm page](https://www.npmjs.com/package/vega-lite)
- [Observable Plot — marks](https://observablehq.com/plot/features/marks) /
  [Plot.plot reference](https://observablehq.com/plot/features/plots) /
  [repo](https://github.com/observablehq/plot)
- [D3 — what is d3](https://d3js.org/what-is-d3) /
  [repo](https://github.com/d3/d3)
- [ECharts handbook](https://echarts.apache.org/handbook/en/get-started) /
  [option reference](https://echarts.apache.org/en/option.html) /
  [npm](https://www.npmjs.com/package/echarts)
- [Plotly.js line charts](https://plotly.com/javascript/line-charts/) /
  [repo](https://github.com/plotly/plotly.js)
- [Highcharts series API](https://api.highcharts.com/highcharts/series.line) /
  [npm](https://www.npmjs.com/package/highcharts)
- [Chart.js line chart](https://www.chartjs.org/docs/latest/charts/line.html) /
  [releases](https://github.com/chartjs/Chart.js/releases)
- [Apache Superset — ECharts Option Editor discussion](https://github.com/apache/superset/discussions/31802)
- [Metabase Representation Format](https://github.com/metabase/representations)
- [Vega-Lite paper (Satyanarayan et al., InfoVis 2017)](https://idl.cs.washington.edu/files/2017-VegaLite-InfoVis.pdf)
