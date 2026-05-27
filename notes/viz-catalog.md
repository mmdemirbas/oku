# Visualization catalog — gap analysis (2026-05-27)

## Sources

- **datylon** — https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization — vendor blog, exhaustive (60+ types) with one-line use-cases; strongest of the six for surfacing exotic types (bump, horizon, beeswarm, strip/jitter, contour, barcode, semicircle donut).
- **atlassian** — https://www.atlassian.com/data/charts/essential-chart-types-for-data-visualization — short editorial overview of ~13 "essential" types; shallow but well-edited.
- **quickchart** — https://quickchart.io/documentation/chart-types/ — implementation docs for a Chart.js-as-a-service renderer; useful as a reality check on which types ship in practice (bar/line/radar/pie/doughnut/polar/scatter/bubble/gauge/box/violin/funnel/sparkline/sankey/candlestick/OHLC).
- **datavizcatalogue** — https://datavizcatalogue.com/ — canonical reference catalogue; the landing page lists ~60 distinct types alphabetically and is heaviest on exotic types (Kagi, Point & Figure, Stem & Leaf, Tally, Spiral Plot, Span chart, Non-ribbon Chord, Parallel Sets).
- **holistics** — https://www.holistics.io/blog/types-of-charts/ — "40+ chart types" guide grouped by purpose (categorical / temporal / distribution / relational / hierarchical / geospatial / proportional); the only source with first-class Waterfall, Trellis (small multiples), and Org chart.
- **datawrapper** — https://www.datawrapper.de/blog/chart-types-guide — opinionated editorial; lightest on volume but richest in best-practice and chart-pair guidance (arrow vs slope, alluvial vs sankey, multi-line vs small multiples, locator vs symbol map).

Source initials used below: **daty**, **atla**, **qchart**, **dvc**, **holi**, **datw**.

## Master list (alphabetical)

| Visualization | Best for | In oku? | Sources |
|---|---|---|---|
| Alluvial diagram | Category switching / preference flow | partial (sankey) | datw |
| Arc diagram | Pairwise links along a 1-D axis | no | daty, dvc |
| Area chart | Continuous change with volume emphasis | yes | atla, daty, dvc, holi, datw |
| Arrow plot | Compact before/after for many categories | no | datw |
| Bar chart (horizontal & vertical/column) | Categorical comparison | yes | all |
| Barcode chart | 1-D distribution as a row of tick marks | no | daty |
| Beeswarm chart | 1-D distribution, non-overlapping dots | no | daty |
| Box plot (box & whisker) | Distribution summary across groups | yes | all |
| Bubble chart | XY + magnitude (3 vars) | yes | atla, daty, dvc, holi, qchart |
| Bullet graph | Single KPI vs target + bands | yes | atla, daty, dvc, holi |
| Bump chart | Rank changes over time | no | daty |
| Bump area chart | Stacked-rank changes over time | no | daty |
| Calendar heatmap | Daily value over a year grid | yes | dvc |
| Candlestick chart | OHLC price intervals | no | daty, dvc, holi, qchart |
| Cartogram | Geo distortion proportional to value | no | datw |
| Chord diagram | Pairwise flows in a circle | yes | daty, dvc, holi |
| Choropleth map | Value shading per region | partial (geo) | dvc, holi, datw |
| Circle packing | Hierarchy as nested circles | no | dvc, holi |
| Connected scatter plot | Trajectory of two paired metrics | no | daty |
| Connection map | Lines between locations | no | dvc, holi |
| Contour plot | 2-D density / surface levels | no | daty |
| Dendrogram | Hierarchical cluster tree | no | daty, datw, dvc |
| Density plot (KDE) | Continuous distribution curve | no | atla, daty, dvc, holi |
| Diverging stacked bar (Likert) | Sentiment / opinion split around center | no | daty, datw |
| Donut chart | Part-to-whole, centered KPI | yes | all |
| Dot map | Point locations on a map | no | dvc, holi |
| Dot plot | Categorical values without bar baseline | no | atla, daty, datw |
| Dual-axis chart | Two scales sharing one X | no | atla |
| Dumbbell plot | Two values per category | no | daty |
| Euler diagram | Set overlap, area-accurate | no | daty |
| Funnel chart | Pipeline stage drop-off | yes | atla, daty, dvc, holi, qchart |
| Gantt chart | Project schedule / overlapping intervals | no | daty, dvc, holi, datw |
| Gauge / radial gauge | Single KPI on a dial | yes | daty, holi, qchart |
| Grouped bar / column | Sub-category side-by-side | yes | atla, daty, holi, datw |
| Heatmap (2-D matrix) | Two-axis category × value matrix | yes | all |
| Histogram | Distribution of one numeric variable | yes | atla, daty, dvc, holi |
| Histogram, 2-D (binned scatter) | Joint distribution under overplotting | no | datw |
| Horizon chart | Many parallel time series, color-folded | no | daty |
| Illustration diagram | Annotated explanatory figure | no | dvc |
| Isotype / pictogram | Count-as-icons | no | daty, datw, dvc |
| Jitter / strip plot | Raw points along one axis | no | daty |
| Kagi chart | Price reversal regardless of time | no | dvc |
| Line chart | Continuous change over time | yes | all |
| Locator map | Pin / label specific points | no | datw |
| Lollipop chart | Bar chart with marked endpoint | no | daty |
| Marimekko / mosaic chart | Two-dim part-to-whole (size × share) | no | daty, dvc, holi, datw |
| Network diagram | Nodes + edges, general graph | yes | daty, dvc, holi |
| Nightingale rose / polar area / radial column | Bars on a circular axis | no | daty, dvc, holi, qchart |
| OHLC chart | Open-high-low-close bars | no | daty, dvc, qchart |
| Org chart | Reporting hierarchy | no | holi |
| Parallel coordinates | Multi-variable lines across axes | yes | daty, dvc, holi |
| Parallel sets | Categorical alluvial flow | no | dvc |
| Parliament chart | Seat distribution as a hemicycle | no | datw |
| Pie chart | Part-to-whole, ≤6 slices | yes | all |
| Point & figure chart | Price moves, no time axis | no | dvc |
| Population pyramid | Two-sided bars by age band & sex | no | daty, datw, dvc |
| Progress bar | Single horizontal % | partial (gauge / bar) | qchart |
| Proportional area chart | Bare circles/squares sized by value | no | daty, datw, dvc, holi |
| Pyramid chart | Stacked triangle of stages | no | daty, dvc |
| Quadrant chart | XY with reference cross | yes | daty |
| Radar / spider chart | Multivariate per item on a wheel | yes | daty, holi, qchart |
| Range plot | One range per category (low / high) | no | daty |
| Ridgeline / joyplot | Stacked density curves | yes | daty |
| Sankey diagram | Weighted flows between stages | yes | atla, daty, dvc, holi, qchart |
| Scatter matrix | Pairwise scatter grid | yes | daty |
| Scatter plot | Two numeric vars, correlation | yes | all |
| Semicircle donut | 180° gauge-like donut | no | daty |
| Slope chart | First vs last value, many categories | yes | daty, datw |
| Small multiples / trellis | Grid of sub-charts | no | holi, datw |
| Span chart | Min-max range per category | no | dvc |
| Sparkline | Inline mini time-series | yes | atla, dvc, qchart |
| Spiral plot | Cyclical patterns over a long span | no | dvc |
| Spline / step line | Smoothed or stepped line variants | partial (line) | daty |
| Stacked area chart | Continuous part-to-whole over time | yes | daty, holi, dvc |
| Stacked bar / column | Categorical part-to-whole | yes | all |
| Stem-and-leaf plot | Distribution preserving digits | no | dvc |
| Stream graph | Soft-baseline stacked area | no | daty, dvc, holi, datw |
| Sunburst chart | Hierarchical part-to-whole, radial | no | daty, dvc, holi |
| Symbol map | Symbols sized/colored per location | partial (geo) | datw |
| Table | Exact values | yes (kit primitive) | atla |
| Tally chart | Count by tally marks | no | dvc |
| Tile / hex map | Equal-area regional grid | partial (geo) | daty |
| Timeline | Events on a 1-D axis | no | dvc |
| Treemap | Hierarchy by rectangle area | yes | daty, dvc, holi |
| Venn diagram | Set overlap | no | daty, dvc |
| Violin plot | Distribution + density per group | no | atla, daty, dvc, holi, qchart |
| Waffle chart | 10×10 grid of part-to-whole | yes | daty, datw |
| Waterfall chart | Incremental positive/negative steps | no | daty, holi |
| Word cloud | Term frequency | no | dvc |

For reference the 29 oku types are: scatter, line, area, bubble, quadrant, bar, stacked-bar, grouped-bar, donut, pie, waffle, treemap, histogram, box-plot, ridgeline, sparkline, slope, calendar-heatmap, funnel, sankey, network, chord, heatmap, scatter-matrix, parallel-coordinates, gauge, bullet, radar, geo.

## Gaps — visualizations oku doesn't have yet (ranked by usefulness)

Ranked by (a) how often a serious doc would need the type, (b) how cheap the renderer is on top of existing primitives, (c) how many catalogues flagged it.

### 1. Waterfall chart — high

Incremental gains/losses connecting two totals (start → +A → −B → +C → end). Canonical "what changed between these two numbers" chart — financial bridge, retention loss-explanation, performance breakdown. holi and daty both flag it first-class; stacked-bar is the wrong substitute (loses the cumulative axis). Pure layout on top of the existing bar primitive, small lift. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/).

### 2. Dot plot / lollipop chart — high

One dot (or stem + dot) per category, value encoded by position, no bar baseline. Default replacement for "too many bars" — atla, daty, datw all recommend. Lollipop = same chart with a thin stem. Cheap addition, reuses bar layout. Sources: [atla](https://www.atlassian.com/data/charts/essential-chart-types-for-data-visualization), [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 3. Dumbbell / arrow plot — high

Two dots per category joined by a line — before/after, men/women, 2010/2020. datw positions arrow plot explicitly as the compact alternative to slope when many categories don't fit; daty's dumbbell is the same chart with a different name. Heavy use in news graphics. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 4. Small multiples / trellis — high

Not a chart type — a layout primitive. Same chart repeated in a grid, one panel per category. The single most-recommended "declutter" pattern across the six sources; holi calls it Trellis, datw a peer of slope and arrow plot. Implementation is a wrapper that repeats any existing kind. Sources: [holi](https://www.holistics.io/blog/types-of-charts/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 5. Stream graph — medium-high

Stacked area with a centered baseline; emphasises shape over absolute values. Cited in 4 of 6 sources (daty, dvc, holi, datw). datw explicitly suggests it as the antidote to "too familiar" charts. Layered on the existing area renderer with a different baseline function. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 6. Marimekko / mosaic chart — medium

Stacked-column where column width is also proportional to a second variable (country × age band, market × segment). Distinct from treemap (preserves a categorical axis) and from stacked-bar (varying width). 4-source mention. Higher lift — needs a variable-width axis. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 7. Density curve (KDE) + violin plot — medium

Smoothed-frequency curve (1-D) and its mirrored twin for per-group comparison. Preferred over histogram when bin choice is arbitrary and shape matters; violin replaces box plot when shape detail is wanted. 4 of 6 sources treat them as first-class peers. The existing ridgeline already implies a KDE primitive — lift into standalone density and add violin as a box-plot variant. Sources: [atla](https://www.atlassian.com/data/charts/essential-chart-types-for-data-visualization), [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/).

### 8. Population pyramid / diverging stacked bar — medium

Stacked bars mirrored around a center axis. Any "split by category" — male/female by age, agree/disagree on a Likert, sentiment +/−, gain/loss. datw specifically calls out diverging-bar for Likert-survey rendering, a common doc artifact. Small lift (stacked-bar in two passes, mirrored axis). Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 9. Bump chart — medium

Line chart where the Y axis is rank instead of value. "Who was #1 each year" — leaderboards, standings, popularity drift. Reuses line renderer with a rank-transform pre-pass. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization).

### 10. Polar area / Nightingale rose / radial column — medium

Bars laid out around a circle. Cyclical categorical data (months, hours, compass) where the cyclic shape itself carries meaning. Common ask for time-of-day / month-of-year viz. Distinct from radar (radar = filled polygon over multi-vars). Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [qchart](https://quickchart.io/documentation/chart-types/), [dvc](https://datavizcatalogue.com/).

### 11. Candlestick / OHLC chart — medium-low

Open/high/low/close per period; box body = open→close, wicks = high/low. Any time-series with an explicit range per tick — financial, weather min/max, latency p50/p95 intervals. Modest lift on top of scatter/line. Particularly worth it because oku ships into engineering docs that often need latency interval rendering without inventing new shapes. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [qchart](https://quickchart.io/documentation/chart-types/), [dvc](https://datavizcatalogue.com/).

### 12. Gantt chart — medium-low

Horizontal bars positioned on a time axis, one per task. Project schedules, release plans, roadmap windows. 4 of 6 sources list it. Mid-effort: reuses bar layout but needs a time-axis primitive. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [dvc](https://datavizcatalogue.com/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### 13. Sunburst chart — low-medium

Treemap on a polar axis — concentric rings for hierarchy levels. Sibling of the existing treemap; lift is mostly a polar projection pass. Skip if treemap covers the use case in practice — they answer the same author question. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [dvc](https://datavizcatalogue.com/).

### 14. Connected scatter plot — low

Scatter with points connected in temporal order — trajectory of two paired metrics over time (unemployment vs inflation each year). Tiny lift on top of scatter (add an ordered-connection layer). Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization).

### 15. Horizon chart — low

Time series folded into colour bands so many series fit in tight strips. Dashboards with 20+ time series in narrow columns. Distinctive but niche; defer unless a concrete dashboard need surfaces. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization).

## Improvements to existing oku types

Each item is a delta against current behaviour — what the catalogues describe that the current renderer either doesn't expose or doesn't enforce.

### bar — horizontal vs vertical as a single primitive, sorted by default

datw: "a bar chart is often a safer pick for small screens than a column chart, since it grows vertically rather than horizontally." atla and qchart treat `bar` and `horizontalBar` as one type with an orientation flag. The oku bar should accept `orientation: horizontal | vertical` and default to sorted-by-value unless the X axis is intrinsically ordered (time, age band). Sources: [atla](https://www.atlassian.com/data/charts/essential-chart-types-for-data-visualization), [qchart](https://quickchart.io/documentation/chart-types/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### stacked-bar — 100 % (relative) variant + split-bar mode

datw and daty both flag the 100 %-stacked variant as a distinct visual mode (each bar normalised, useful for survey-share comparison). Today it requires pre-computing percentages in the data. A `normalize: percent` mode would be the right affordance. The same control underlies datw's "split bar chart" (two-sided stacked, basis of the population pyramid above). Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### line — multi-line guidance + step / spline variants

holi: keep two or three lines at most with direct labels (no legend look-up). daty: step-line and spline-line as first-class variants. line should accept a `mode: linear | step | spline` switch, and the authoring docs should call out the direct-label-over-legend convention (the kit can default to end-of-line labels above ~3 series). Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/).

### area — stacked-area + stream-graph share the renderer

daty groups stacked-area, stream-graph, and bump-area under one family. Today oku has line/area but not stacked-area as a first-class kind. Bringing stacked-area in (and treating stream-graph as `baseline: center`) consolidates three gap entries into one renderer family. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization).

### donut + pie — semicircle / half-donut + "use bar instead" warning

daty's semicircle donut and qchart's half-doughnut-as-gauge both demonstrate one affordance: a 180° rotation parameter that turns the chart into a horizontal gauge / progress dial. Expose as `arc: 360 | 180 | <degrees>` on donut. Also: holi, datw, and atla all warn that for ≥4 categories a bar chart beats a pie/donut — surface as a "when not to use" note in the authoring docs next to the primitive. Sources: [daty](https://www.datylon.com/blog/types-of-charts-graphs-examples-data-visualization), [qchart](https://quickchart.io/documentation/chart-types/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### histogram — bin-count guidance + 2-D histogram mode

datw flags the 2-D histogram (binned scatter) as the cure for a "sea of overlapping dots" in scatter. atla and holi both warn that bin count materially changes the perceived distribution. A `bins: auto | <int>` option with a sensible default (Sturges or Freedman-Diaconis) plus a 2-D mode that takes `x` and `y` bins closes two gaps at once. Sources: [atla](https://www.atlassian.com/data/charts/essential-chart-types-for-data-visualization), [holi](https://www.holistics.io/blog/types-of-charts/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### box-plot — raw-points overlay + violin variant

qchart explicitly: "for best results, add a scatter plot to your box or violin chart." atla, daty, dvc, holi all treat violin as the next step when shape matters. box-plot should accept `points: none | jitter | strip` overlay and `shape: box | violin`. Sources: [qchart](https://quickchart.io/documentation/chart-types/), [atla](https://www.atlassian.com/data/charts/essential-chart-types-for-data-visualization).

### scatter — overplotting fallback to 2-D histogram

holi flags overlapping bubbles as the dominant failure mode; datw recommends 2-D-histogram for dense scatter. Add a `density: points | hex | rect` mode on scatter to switch to binned rendering when overplotting is detected. Even an `oku check` lint that warns when point count × point-size ratio exceeds a threshold would help. Sources: [holi](https://www.holistics.io/blog/types-of-charts/), [datw](https://www.datawrapper.de/blog/chart-types-guide).

### geo — choropleth / dot map / symbol map / connection map / hex-tile as modes

Today the kit ships a single `geo` kind. The catalogues split this family cleanly into five: choropleth (region shading), dot map (raw points), symbol map (sized markers), connection map (lines between points), hex-tile (equal-area regions). datw splits by purpose — point locations → symbol or locator, regions → choropleth or hex-tile. A single `geo` with `mode: choropleth | dots | symbols | hex | connections` would map the docs guidance directly. Sources: [datw](https://www.datawrapper.de/blog/chart-types-guide), [holi](https://www.holistics.io/blog/types-of-charts/), [dvc](https://datavizcatalogue.com/).

### gauge — multi-value variant + orientation doc vs bullet

holi's "multi-value gauge" is the right primitive when several related KPIs share one dial. The kit ships gauge and bullet separately; documenting the choice (one KPI vs target → bullet; multiple KPIs in one frame → multi-gauge; single KPI no benchmark → gauge) closes the orientation gap without new code. Sources: [holi](https://www.holistics.io/blog/types-of-charts/), [qchart](https://quickchart.io/documentation/chart-types/).

## Defer / reject

Types the catalogues list but oku should not pursue near-term, with reasoning.

- **3-D bar / 3-D pie / 3-D anything** — datw, holi, atla all explicitly warn against. Adds occlusion, hides values. Reject.
- **Word cloud** — dvc only. Visually loud, analytically poor (size encodes frequency but layout encodes nothing). Skip unless a doc specifically needs decorative term display.
- **Tally chart / stem-and-leaf plot** — dvc only. Pedagogical curiosities. Histogram does the same job, better. Reject.
- **Kagi chart / Point & Figure chart** — dvc only. Highly specialised technical-trading charts. Defer indefinitely.
- **Spiral plot** — dvc only. Cyclical patterns over a long span. The existing calendar-heatmap already covers the canonical use case. Defer.
- **Pictogram / isotype chart** — daty, datw, dvc. Eye-candy for count-as-icons. Waffle already covers part-to-whole; pictogram needs custom SVG icons per dataset, which doesn't fit the kit's data-only authoring model. Defer.
- **Parliament chart** — datw only. A semicircle donut with seat-shaped tiles; narrow use case. Build as a special case of the semicircle donut affordance above.
- **Org chart** — holi only. Hierarchical relationship — the existing network kind or the diagram (Mermaid) primitive covers it.
- **Cartogram** — datw only. Geographic value-distortion. Powerful but implementation lift is huge (Dorling / hex / contiguous variants are distinct algorithms). Defer.
- **Brainstorm / illustration diagram** — dvc only. Not charts — document layouts. The existing comparison-cards / steps / cards primitives already cover this space.
- **Timeline / Timetable** — dvc only. A timeline can be served by Gantt (proposed above) or by the existing steps primitive; no separate type warranted.
- **QR codes** — qchart only. Not a chart. Out of scope.
- **Euler diagram (vs Venn)** — daty only. Subtle distinction (Euler drops empty intersections from Venn). If Venn ships, the same primitive covers Euler.
- **Span chart** — dvc only. A degenerate form of range-plot / dumbbell (proposed above). Skip as a distinct type.
- **Non-ribbon chord diagram** — dvc only. A network laid out circularly. Existing chord and network kinds together cover the space.
- **Parallel sets** — dvc only. Categorical alluvial. Folded into the alluvial improvement (sankey-mode).
- **Contour plot** — daty only. Continuous 2-D density. The 2-D histogram proposed under histogram improvements covers the practical need; contour adds smoothing for limited gain.
- **Beeswarm / jitter / strip plot** — daty only. Strong visualisations of 1-D distribution, but the proposed `points` overlay on box-plot covers the common case. Promote later if a doc specifically needs standalone versions.
- **Barcode chart** — daty only. A degenerate strip plot used as a 1-D distribution glyph. Sparkline neighbour; skip unless asked.
- **Bump area chart** — daty only. A streamgraph variant on rank. Niche enough to defer until bump and stream both ship.
- **Radial bar / radial column** — daty, dvc. Decorative variants of bar. Cover via polar-area / Nightingale (gap #10) instead of a separate type.
- **Dendrogram** — daty, datw, dvc. Hierarchical cluster tree. Useful for statistics docs, but the existing network and treemap cover most cases. Defer; reconsider if a stats-heavy doc lands.
- **Dual-axis chart** — atla only. Best practice is divided; many designers consider dual-axis misleading. If shipped at all, ship as a `secondaryAxis: ...` mode on line/bar rather than a distinct type. Defer.


## Function-based taxonomy (from datavizcatalogue/search.html)

Source: https://datavizcatalogue.com/search.html — "What do you want
to show?" Sixteen function categories, verbatim labels as displayed
on the page. The page links each label to a subpage that enumerates
visualisations grouped under that function. The same chart can (and
does) appear under multiple functions — these are tags, not a
partition.

### 1. The functions (verbatim, in page order)

1. Comparisons
2. Proportions
3. Relationships
4. Hierarchy
5. Concepts
6. Location
7. Part-to-a-whole
8. Distribution
9. How things work
10. Processes & methods
11. Movement or flow
12. Patterns
13. Range
14. Data over time
15. Analysing text
16. Reference tool

### 2. Visualisations grouped under each function

Names verbatim from each subpage. Counts in parentheses are membership
in that function only (a chart appearing under N functions is counted
N times across the catalogue).

**Comparisons (28).** Bar Chart, Box & Whisker Plot, Bubble Chart,
Bullet Graph, Line Graph, Marimekko Chart, Multi-set Bar Chart,
Nightingale Rose Chart, Parallel Coordinates Plot, Population
Pyramid, Radar Chart, Radial Bar Chart, Radial Column Chart, Span
Chart, Stacked Area Graph, Stacked Bar Graph, Chord Diagram,
Choropleth Map, Donut Chart, Dot Matrix Chart, Heatmap, Parallel
Sets, Pictogram Chart, Pie Chart, Proportional Area Chart, Tally
Chart, Treemap, Venn Diagram.

**Proportions (14).** Bubble Chart, Bubble Map, Circle Packing, Dot
Matrix Chart, Nightingale Rose Chart, Proportional Area Chart,
Stacked Bar Graph, Word Cloud, Donut Chart, Marimekko Chart, Parallel
Sets, Pie Chart, Sankey Diagram, Treemap.

**Relationships (14).** Heatmap, Marimekko Chart, Parallel
Coordinates Plot, Radar Chart, Venn Diagram, Arc Diagram, Brainstorm,
Chord Diagram, Connection Map, Network Diagram, Non-ribbon Chord
Diagram, Tree Diagram, Bubble Chart, Scatterplot.

**Hierarchy (4).** Circle Packing, Sunburst Diagram, Tree Diagram,
Treemap.

**Concepts (4).** Brainstorm, Flow Chart, Illustration Diagram, Venn
Diagram.

**Location (5).** Bubble Map, Choropleth Map, Connection Map, Dot
Map, Flow Map.

**Part-to-a-whole (6).** Donut Chart, Marimekko Chart, Pie Chart,
Stacked Bar Graph, Sunburst Diagram, Treemap.

**Distribution (17).** Box & Whisker Plot, Bubble Chart, Density
Plot, Dot Matrix Chart, Histogram, Multi-set Bar Chart, Parallel
Sets, Pictogram Chart, Stem & Leaf Plot, Tally Chart, Timeline,
Violin Plot, Dot Map, Connection Map, Flow Map, Population Pyramid,
Word Cloud.

**How things work (3).** Flow Chart, Illustration Diagram, Sankey
Diagram.

**Processes & methods (5).** Flow Chart, Gantt Chart, Illustration
Diagram, Parallel Sets, Sankey Diagram.

**Movement or flow (4).** Connection Map, Flow Map, Parallel Sets,
Sankey Diagram.

**Patterns (27).** Arc Diagram, Area Graph, Bar Chart, Box & Whisker
Plot, Bubble Chart, Candlestick Chart, Choropleth Map, Connection
Map, Density Plot, Dot Map, Dot Matrix Chart, Heatmap, Histogram,
Kagi Chart, Line Graph, Multi-set Bar Chart, Open-high-low-close
Chart, Parallel Coordinates Plot, Point & Figure Chart, Population
Pyramid, Radar Chart, Scatterplot, Spiral Plot, Stacked Area Graph,
Stream Graph, Timeline, Violin Plot.

**Range (9).** Box & Whisker Plot, Bullet Graph, Candlestick Chart,
Error Bars, Gantt Chart, Kagi Chart, Open-high-low-close Chart, Span
Chart, Violin Plot.

**Data over time (14).** Area Graph, Bubble Chart, Candlestick Chart,
Gantt Chart, Heatmap, Line Graph, Nightingale Rose Chart,
Open-high-low-close Chart, Spiral Plot, Stacked Area Graph, Stream
Graph, Calendar, Timeline, Time Table.

**Analysing text (1).** Word Cloud.

**Reference tool (5).** Calendar, Gantt Chart, Time Table, Tree
Diagram, Stem & Leaf Plot.

### 3. Is function-based grouping better for oku?

**Recommendation: hybrid — function as the primary picker axis,
family as a secondary filter.** Not pure function-based, not pure
family-based.

The reasoning, concretely.

**What function-based wins.** The picker UI exists to answer "I have
this data and this thing I want to communicate — which chart?" That
question is phrased in functional language by every author who isn't
already a dataviz native. "I want to show how the parts add up" maps
to Part-to-a-whole. "I want to show how X relates to Y" maps to
Relationships. Family labels (cartesian, categorical, radial,
geospatial) describe how a chart is rendered, not what it
communicates — they're useful to a developer choosing render code,
useless to an author choosing meaning. Datavizcatalogue picked the
right primary axis for a discovery UI, and the user's instinct
matches that: when authors arrive at the picker cold, the function
question is the one they can actually answer.

**Where function-based fails alone.** Six pain points stand out
when applied directly:

1. *Overlap is heavy.* Bubble Chart appears under five functions
   (Comparisons, Proportions, Relationships, Distribution, Patterns,
   Data over time). Heatmap appears under four. The picker becomes a
   tag cloud, not a hierarchy, and the author who clicks Comparisons
   then Proportions sees the same chart twice and questions whether
   the system knows what it's doing.
2. *"Patterns" is a junk drawer.* 27 charts. It means "any chart
   where you might spot a pattern" — which is most of them.
   Datavizcatalogue lists it but it's the function with the lowest
   discriminative value.
3. *"Reference tool" is a meta-function, not a function.* It groups
   Calendar / Gantt / Time Table / Tree Diagram / Stem & Leaf Plot
   on the basis that "you look things up in them" — that's a usage
   mode, not a communication intent. The label sits awkwardly
   beside the other fifteen.
4. *"Concepts" and "How things work" overlap with "Processes &
   methods".* All three are diagram-territory (Flow Chart, Sankey,
   Venn, Brainstorm, Illustration Diagram). Datavizcatalogue itself
   couldn't keep them clean.
5. *Author still needs the family axis at some point.* When the
   picker lands on a function with 14+ entries, the author wants to
   sub-filter — "show me only the bar-family ones, hide the radial
   ones." Without family as a secondary axis, the long lists become
   a scroll exercise.
6. *Family labels carry render-cost information* (radial = expensive,
   geospatial = needs map asset, network = needs layout engine).
   That's invisible from a pure function taxonomy, and the author
   making a budget-aware choice benefits from seeing it.

**Why hybrid, specifically.** Function as the entry question
(picker default view) — what you want to show — and family as a
visible secondary filter (chips along the top: cartesian /
categorical / radial / geospatial / network / part-to-whole /
flow / specialised). The two axes are orthogonal: function answers
*why*, family answers *how*. Both views surface the same underlying
chart set. The picker can default to function-first because that
matches the author's mental model, but the family chips stay
clickable so a render-budget-aware author can prune.

A pure function picker is closer to right than a pure family picker
for oku's audience (technical writers, not data scientists), but
omitting family entirely sacrifices the secondary filtering that the
long lists make necessary.

### 4. Suggested function labels for oku

Riffing on datavizcatalogue's wording — keeping what works,
collapsing the overlapping ones, and dropping the ones that don't
discriminate. Eight labels, in suggested picker order (most-asked
first, specialised last):

1. **Compare values** — bar / column / radar / parallel coordinates.
   The single most-common picker question. Datavizcatalogue's
   "Comparisons" is fine but "compare values" is more concrete.
2. **Show change over time** — line / area / stream / candlestick /
   spiral / calendar. Datavizcatalogue splits this off as "Data over
   time"; keep the split — time is a distinct enough axis that
   merging it into "Compare values" hides the appropriate charts.
3. **Show distribution** — histogram / box plot / violin / density /
   dot matrix. Datavizcatalogue's "Distribution" mostly. Drop the
   geo-related entries (Dot Map, Connection Map) that DVC bizarrely
   includes here — they belong under location/flow.
4. **Show parts of a whole** — pie / donut / stacked bar / treemap /
   sunburst / marimekko. Collapses DVC's "Proportions" and
   "Part-to-a-whole" — they're the same question phrased twice.
   "Proportions" is the broader of the two and absorbs it cleanly.
5. **Show relationships** — scatter / bubble / heatmap / chord /
   network / arc / Venn. Datavizcatalogue's "Relationships" plus
   the connection-style diagrams. Drop "Brainstorm" — it's a UI
   pattern, not a chart.
6. **Show hierarchy** — tree / treemap / sunburst / circle packing.
   Datavizcatalogue's "Hierarchy" as-is. Keep separate from
   relationships: hierarchy is a constrained subset (acyclic,
   rooted) and authors think of it differently.
7. **Show flow or movement** — Sankey / flow map / connection map /
   parallel sets / chord. Collapses DVC's "Movement or flow",
   "Processes & methods", and "How things work" into one. The
   three DVC categories shared Flow Chart, Sankey, and Illustration
   Diagram across all of them — they were never really three
   things.
8. **Show location** — choropleth / bubble map / dot map / flow map
   / connection map. Datavizcatalogue's "Location" as-is. Geo is a
   discrete enough domain (needs a base map) that it deserves its
   own label.

Dropped from datavizcatalogue: *Concepts*, *Patterns*, *Range*,
*Analysing text*, *Reference tool*. Reasoning:

- *Concepts* — collapses into "Show relationships" (Venn,
  Brainstorm) and "Show flow" (Flow Chart, Illustration Diagram).
- *Patterns* — too broad (27 charts) to discriminate. Pattern-spotting
  is a use mode, not a chart-type intent.
- *Range* — collapses into "Show distribution" (box / violin) and
  "Show change over time" (candlestick / OHLC). Range is a sub-question
  of distribution or time, not its peer.
- *Analysing text* — one chart (Word Cloud). Park it under "Show
  parts of a whole" or "Specialised". Not worth a top-level slot.
- *Reference tool* — usage mode, not function. Calendar / Gantt /
  Time Table can sit under "Show change over time". Tree Diagram
  under "Show hierarchy". Stem & Leaf under "Show distribution".

Ordering rationale: 1–4 cover the bulk of everyday picker traffic
(compare, time, distribution, parts). 5–6 are next-most-common but
require more specific data shapes. 7–8 are domain-specialised (flow
needs flow data; geo needs geo data) and sit last.

## D3 gallery (from observablehq.com/@d3/gallery)

Source: https://observablehq.com/@d3/gallery — curated by Mike Bostock
and the D3 team. Unlike the marketing-style catalogues already
surveyed (DatavizCatalogue, FT Visual Vocabulary, Datawrapper), this
is a working-code gallery: every entry is a forkable Observable
notebook with real data plugged in. ~170 examples organised into 14
sections (Animation, Interaction, Analysis, Hierarchies, Networks,
Bars, Lines, Areas, Dots, Radial, Annotation, Maps, Essays, Just for
fun). It matters as a source because (a) it reflects what working
practitioners actually reach for, not what a taxonomy editor thinks
they should reach for; (b) it includes niche shapes (horizon, hexbin,
contour, voronoi, beeswarm) that marketing catalogues skip; and
(c) it documents interaction techniques (brush, lasso-equivalent,
zoom-to-bounds, force-relax, click-to-fix-node) inline with the
chart code, so each technique has a copyable reference impl.

### Visualizations seen here that DIDN'T appear in the marketing catalogues

1. **Horizon chart** (https://observablehq.com/@d3/horizon-chart/2) —
   stacked, banded variant of an area chart that folds magnitude into
   colour bands, letting a small-multiples grid pack many time series
   into a fraction of the vertical space. Worth considering for oku
   because dashboards comparing 20+ series (servers, regions,
   stocks) hit the line-chart density limit fast.
2. **Hexbin / hexbin map / hexbin area**
   (https://observablehq.com/@d3/hexbin) — binned 2D density on a
   hex grid; the cartographic variant aggregates point geo data
   without choropleth's polygon dependency. Worth considering because
   oku's scatter degrades to a black-blob at >5k points; hexbin is
   the canonical fix.
3. **Density contours / KDE contours**
   (https://observablehq.com/@d3/density-contours) — 2D kernel-
   density estimate rendered as iso-density contours over a
   scatter. Worth considering as a scatter "overlay mode" so
   high-density regions become legible without losing individual
   points.
4. **Contour plot (scalar field)**
   (https://observablehq.com/@d3/contours,
   https://observablehq.com/@d3/volcano-contours/2) — iso-lines /
   iso-bands for a 2D scalar function (z = f(x,y)). Worth considering
   for any engineer-author plotting loss surfaces, terrain, or
   thermal maps.
5. **Voronoi diagram / voronoi labels**
   (https://observablehq.com/@d3/voronoi-labels,
   https://observablehq.com/@d3/us-airports-voronoi) — partitions
   the plane into nearest-neighbour cells. Worth considering as an
   *interaction substrate* (mouse-to-nearest-point hit testing for
   any oku scatter) and as a label-collision technique.
6. **Q-Q plot / normal quantile plot**
   (https://observablehq.com/@d3/q-q-plot,
   https://observablehq.com/@d3/normal-quantile-plot) — plots sample
   quantiles against theoretical quantiles to test for distribution
   fit. Worth considering because oku is technical-author-facing and
   "is this data Normal?" is a real question that histogram alone
   doesn't answer.
7. **Indented tree / collapsible tree / tidy tree / radial tree /
   cluster / radial cluster**
   (https://observablehq.com/@d3/indented-tree,
   https://observablehq.com/@d3/tree/2,
   https://observablehq.com/@d3/radial-tree/2,
   https://observablehq.com/@d3/cluster/2) — six distinct tree
   layouts; the indented one is a file-tree shape, radial puts the
   root in the centre. Oku's `network` covers force layouts but the
   tree family is a structurally different shape (rooted, acyclic)
   that authors think about separately.
8. **Sunburst / zoomable sunburst / sequences sunburst**
   (https://observablehq.com/@d3/sunburst/2,
   https://observablehq.com/@kerryrodden/sequences-sunburst) —
   radial hierarchical part-to-whole. Sequences variant ties the
   sunburst to a breadcrumb tracking the focused path.
9. **Icicle / zoomable icicle**
   (https://observablehq.com/@d3/icicle/2) — rectangular cousin of
   sunburst; tree depth maps to horizontal/vertical axis. Reads
   easier than sunburst for >3 levels of depth.
10. **Circle pack / nested pack / pack-enclose**
    (https://observablehq.com/@d3/pack/2,
    https://observablehq.com/@d3/d3-packenclose) — hierarchical
    layout that nests circles within circles. Worth considering as
    a treemap alternative when the visual metaphor of "containment"
    matters more than precise area comparison.
11. **Arc diagram**
    (https://observablehq.com/@d3/arc-diagram) — graph with nodes on
    a line and edges drawn as arcs above. Worth considering for
    sequence-aware networks (call graphs, dependency orders) where
    full force layout obscures the order.
12. **Hierarchical edge bundling**
    (https://observablehq.com/@d3/hierarchical-edge-bundling/2) —
    radial node layout with edges bundled through a hierarchy
    backbone. Worth considering for showing cross-module dependencies
    in a large codebase without the hairball failure mode of force-
    directed.
13. **Tangled-tree visualization**
    (https://observablehq.com/@nitaku/tangled-tree-visualization-ii)
    — visualises a DAG that's mostly a tree with a few cross-links
    (think Linux distro lineage). Useful niche for oku because plain
    tree breaks on cross-links and plain network ignores the
    dominant tree shape.
14. **Bar-chart race**
    (https://observablehq.com/@d3/bar-chart-race) — animated bar
    chart where ranks change frame-by-frame; the canonical "viral"
    chart of 2018-2020. Worth considering because oku already has
    animated transitions in the kit; bar-race is a small JSON-shape
    extension on top of grouped-bar.
15. **Cartogram (non-contiguous)**
    (https://observablehq.com/@d3/non-contiguous-cartogram) — sizes
    geographic regions by a data variable rather than by physical
    area. Worth considering as a `geo` rendering mode for the case
    where population-weighted reading matters more than physical
    accuracy.
16. **Marey's trains diagram**
    (https://observablehq.com/@d3/mareys-trains) — 2D time-space
    diagram (time on x, position on y) where each line is one
    vehicle's trajectory. Worth considering for any oku doc
    explaining scheduling, latency, request-flight, or pipeline
    timelines.
17. **Connected scatterplot**
    (https://observablehq.com/@d3/connected-scatterplot/2) — scatter
    where points are connected by a path in time order. Worth
    considering as a scatter variant for showing trajectory of a
    paired-metric pair over time (e.g., latency vs throughput across
    deploys).
18. **Diverging bar / diverging stacked bar**
    (https://observablehq.com/@d3/diverging-bar-chart/2,
    https://observablehq.com/@d3/diverging-stacked-bar-chart/2) —
    bars that grow left/right from a centre axis. Worth considering
    for survey-style net-promoter / Likert visualisations where
    "neutral" is the centre.
19. **Spike map**
    (https://observablehq.com/@d3/spike-map/2) — geographic map
    where each location grows a vertical spike whose height encodes
    the value. Alternative to bubble-map when areas can't overlap
    well.
20. **Bivariate choropleth**
    (https://observablehq.com/@d3/bivariate-choropleth) — choropleth
    encoding two variables simultaneously via a 2D colour matrix
    (typically 3x3). Worth considering for any oku map comparing two
    rates (e.g., income × education).

### Advanced shapes of existing oku types

1. **Beeswarm / mirrored beeswarm** vs oku `scatter` — collision-
   resolved jitter where every point keeps its true x-value but the
   y is solved to avoid overlap. Better than vanilla scatter when x
   is the only real axis. https://observablehq.com/@d3/beeswarm/2 ,
   https://observablehq.com/@d3/beeswarm-mirrored/2
2. **Brushable SPLOM** vs oku `scatter-matrix` — the off-diagonal
   cells respond to a rectangular brush in any one cell, painting
   selected points across all the others. Wins because the SPLOM
   becomes an interactive filter, not just an inspection grid.
   https://observablehq.com/@d3/brushable-scatterplot-matrix
3. **Q-Q / normal quantile plot** vs oku `histogram` — see above;
   serves the distribution-shape question that histogram only
   approximates. https://observablehq.com/@d3/q-q-plot
4. **Kernel-density estimation** vs oku `histogram` — smooth density
   curve (continuous) over the discrete-bin histogram. Pairs well
   with histogram in the same panel. Could be a histogram mode
   instead of a separate type.
   https://observablehq.com/@d3/kernel-density-estimation
5. **Density-contour scatter** vs oku `scatter` — the same scatter
   with KDE contour lines drawn on top so the high-density blob is
   readable. https://observablehq.com/@d3/density-contours
6. **Bollinger bands / moving average** vs oku `line` — line with a
   shaded band (rolling mean ± k·rolling sd) around it. The
   canonical "noisy time series" rendering.
   https://observablehq.com/@d3/bollinger-bands/2 ,
   https://observablehq.com/@d3/moving-average
7. **Band chart / difference chart** vs oku `area` — area between
   two lines, often with a colour split where one crosses the
   other (rainfall above/below normal). Reads completely differently
   from a single area-from-zero. https://observablehq.com/@d3/band-chart/2 ,
   https://observablehq.com/@d3/difference-chart/2
8. **Streamgraph (centred baseline)** vs oku `stacked-bar` /
   `area` — stacked area with a symmetric/centred baseline instead
   of a flat zero-baseline. Hard to read for precise values, great
   for ebb-and-flow narratives.
   https://observablehq.com/@d3/streamgraph/2
9. **Variable-color line / gradient-encoded line / threshold-encoded
   line** vs oku `line` — a single line whose stroke colour varies
   along its length (mapping a third variable, often time or value
   sign). Replaces a multi-series line where the "series" is
   actually one series with shifting state.
   https://observablehq.com/@d3/variable-color-line ,
   https://observablehq.com/@d3/gradient-encoding ,
   https://observablehq.com/@d3/threshold-encoding
10. **Slope chart with annotations**
    (https://observablehq.com/@d3/slope-chart/3) vs oku `slope` —
    the D3 version handles long category lists with overlap-
    resolved labels and a slope-coloring rule (gain = green, loss =
    red). Worth lifting the label algorithm.
11. **Marimekko** vs oku `stacked-bar` — stacked bar where bar
    *widths* also encode a magnitude (so column width × segment
    height = the absolute count). Wins over 100%-stacked bar when
    the column totals themselves matter.
    https://observablehq.com/@d3/marimekko-chart
12. **Diverging-stacked bar** vs oku `stacked-bar` — stacked bar
    pivoted around a midpoint so positive/negative segments grow
    outward. Standard for Likert.
    https://observablehq.com/@d3/diverging-stacked-bar-chart/2
13. **Hierarchical bar chart**
    (https://observablehq.com/@d3/hierarchical-bar-chart) vs oku
    `bar` — drill-down bar chart where clicking a bar expands its
    children. Treemap-class data in a bar idiom.
14. **Calendar (year-on-year)**
    (https://observablehq.com/@d3/calendar/2) vs oku
    `calendar-heatmap` — same chart shape, but D3's version stacks
    multiple years and adds month boundaries; worth lifting the
    layout.
15. **Cascaded / nested treemap**
    (https://observablehq.com/@d3/cascaded-treemap,
    https://observablehq.com/@d3/nested-treemap) vs oku `treemap` —
    treemap variants that show internal nodes (not just leaves) so
    the hierarchy is legible at a glance, with padding/colour to
    separate levels.

### Interactivity techniques worth lifting

1. **Brush-to-filter on scatter** — drag a rectangular region on a
   scatter; points outside the brush dim. Canonical for "show me
   the cluster that's interesting". 
   https://observablehq.com/@d3/brushable-scatterplot
2. **Linked brush across small multiples** — brush in one panel,
   matching points light up in all others. Foundation for any
   coordinated-views dashboard.
   https://observablehq.com/@d3/brushable-scatterplot-matrix
3. **Zoom-to-bounding-box** — click a region, the viewport
   smoothly zooms to fit that region's bounds. Better UX than
   wheel-zoom for hierarchical drill-downs.
   https://observablehq.com/@d3/zoom-to-bounding-box
4. **Smooth semantic zoom** — wheel/pinch zooms the data domain
   rather than the rendered pixels, so ticks, gridlines, and
   labels stay legible at every zoom level.
   https://observablehq.com/@d3/smooth-zooming
5. **Pannable horizontal scroll on a chart** — chart is wider
   than the viewport; horizontal scrollbar lets the user pan
   without changing data domain. Cheaper than zoom for time-
   series. https://observablehq.com/@d3/pannable-chart
6. **Zoomable area chart with x-axis re-scaling** — wheel-zoom
   on an area chart that re-scales the x domain (not the SVG
   transform), preserving label legibility.
   https://observablehq.com/@d3/zoomable-area-chart
7. **Force-directed drag-and-pin** — drag a node in a force
   layout; release to let the simulation relax around it; click
   to fix-in-place or release. Standard interaction for
   network graphs. https://observablehq.com/@d3/force-directed-graph/2
8. **Click-to-zoom on hierarchical layouts** — click a treemap /
   icicle / sunburst / pack node, layout reroots to that node
   with a smooth transition. The "drill-down" gesture for
   hierarchies. https://observablehq.com/@d3/zoomable-treemap ,
   https://observablehq.com/@d3/zoomable-icicle ,
   https://observablehq.com/@d3/zoomable-sunburst ,
   https://observablehq.com/@d3/zoomable-circle-packing
9. **Sequences-sunburst breadcrumb** — hovering a sunburst arc
   lights up the path from the root and renders it as a
   breadcrumb above. The path becomes the legend.
   https://observablehq.com/@kerryrodden/sequences-sunburst
10. **Tooltip with trail line on multi-line chart** — hovering
    anywhere on a multi-line chart draws a vertical guide and
    displays the y-values of every series at that x.
    https://observablehq.com/@d3/line-with-tooltip/2
11. **Voronoi-overlay for nearest-point hit testing** — invisible
    voronoi cells on top of a scatter so every pixel maps to a
    real data point; eliminates the "I clicked between two dots"
    problem. https://observablehq.com/@d3/us-airports-voronoi
12. **Versor-drag on a globe** — drag a 3D globe with the
    correct spherical rotation maths (no equator-tearing).
    https://observablehq.com/@d3/versor-dragging
13. **Index chart (rebase to clicked date)** — click a point on
    a time-series; every series rebases to 1.0 at that point so
    relative changes from the click-date are visible.
    https://observablehq.com/@d3/index-chart/2
14. **Scatterplot tour (camera path)** — animated guided
    transitions that fly the viewport between predefined
    points-of-interest in a scatter. Companion technique for
    "stepper" essays. https://observablehq.com/@d3/scatterplot-tour
15. **Bar-chart race transitions** — ordered animated transitions
    where bars swap rank with object-constancy (each bar keeps
    its identity across frames). The animation primitive that
    bar-chart-race is built on is itself a reusable technique.
    https://observablehq.com/@d3/bar-chart-race ,
    https://observablehq.com/@d3/stacked-to-grouped-bars

