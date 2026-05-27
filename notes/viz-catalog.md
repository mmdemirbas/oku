# viz-catalog research notes

In-flight research notes on chart taxonomies and how the oku chart
picker should be organised. Sections below are appended as the
research progresses.

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

