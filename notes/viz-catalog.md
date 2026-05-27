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
