/* html-doc · renderer.js
 *
 * Walks a JSON page tree and emits DOM into the host element. Custom
 * Elements (glossary-term, ext-ref, etc.) are registered in chrome.js
 * and provide their own behavior; the renderer just instantiates them.
 *
 * Entry point: HtmlDocRenderer.renderFromUrl(url, host?)
 *
 * Schema reference: ../schema/page.schema.json
 */

(function () {
  'use strict';

  /* ---------------------------------------------------------------- *
   * Public API
   * ---------------------------------------------------------------- */

  class HtmlDocRenderer {
    constructor(opts) {
      opts = opts || {};
      this.host = opts.host || null; // resolved at render() time if absent
      this.lang = opts.lang || (document.documentElement.lang) || 'en';
      this.warnings = [];
    }

    /* Split an authored prose string into a mixed [string, inline-node]
       array when it contains <code>…</code> / <em>…</em> / <strong>…</strong>
       tags. Author convenience — lets a writer keep flat strings for
       paragraphs that only carry inline-code without paying the cost of
       a content array. Match is non-greedy + restricted to three known
       tags so element-name documentation like "<callout>" stays literal. */
    static _splitInlineTags(text) {
      const re = /<(code|em|strong)>([\s\S]*?)<\/\1>/g;
      const out = [];
      let pos = 0;
      let m;
      while ((m = re.exec(text)) !== null) {
        if (m.index > pos) out.push(text.slice(pos, m.index));
        out.push({ kind: m[1], text: m[2] });
        pos = m.index + m[0].length;
      }
      if (pos === 0) return [text];     // no matches — single string
      if (pos < text.length) out.push(text.slice(pos));
      return out;
    }

    /* Inline-markdown split. Mirrors Python's `_md_inline` so an author
       can write `**bold**`, `*italic*`, `_italic_`, ``code``,
       `[text](url)` directly inside a content / lead / summary string —
       same vocabulary as a Markdown-twin source.

       Returns null when the string has no markdown markers (caller
       short-circuits to a plain text node). Order matters: bold (**)
       checked before italic (*) so `**a**` doesn't match as italic. */
    static _splitInlineMd(text) {
      const re = /\*\*([^*]+?)\*\*|\*([^*\s][^*]*?)\*|__([^_]+?)__|_([^_\s][^_]*?)_|`([^`]+?)`|\[([^\]]+?)\]\(([^)\s]+?)\)/g;
      const out = [];
      let pos = 0;
      let m;
      while ((m = re.exec(text)) !== null) {
        if (m.index > pos) out.push(text.slice(pos, m.index));
        if (m[1] !== undefined)      out.push({ kind: 'strong', text: m[1] });
        else if (m[2] !== undefined) out.push({ kind: 'em',     text: m[2] });
        else if (m[3] !== undefined) out.push({ kind: 'strong', text: m[3] });
        else if (m[4] !== undefined) out.push({ kind: 'em',     text: m[4] });
        else if (m[5] !== undefined) out.push({ kind: 'code',   text: m[5] });
        else if (m[6] !== undefined) out.push({ kind: 'link',   text: m[6], href: m[7] });
        pos = m.index + m[0].length;
      }
      if (pos === 0) return null;
      if (pos < text.length) out.push(text.slice(pos));
      return out;
    }

    /** Fetch JSON, parse, and render into the host. */
    async renderFromUrl(url, host) {
      let page;
      const wa = (window.__htmldocWithAuth || ((u) => u));
      try {
        const res = await fetch(wa(url), { cache: 'no-cache' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        page = await res.json();
      } catch (e) {
        this._fail('page-fetch-failed', 'Could not load page ' + url + ': ' + e.message);
        return;
      }
      this.render(page, host);
    }

    /** Render an already-parsed page object into the host. */
    render(page, host) {
      this.host = host || this.host || document.querySelector('main#main-content') || document.querySelector('main') || document.body;
      this.warnings = [];

      if (!page || page.kind !== 'page') {
        this._fail('schema-mismatch', 'Page root is not kind="page"', page);
        return;
      }
      if (page.schema_version && page.schema_version > 1) {
        this._fail('schema-future', 'Page schema_version ' + page.schema_version + ' newer than this renderer (1)');
      }

      // document-level setup
      if (page.title) {
        document.title = page.title;
      }
      if (page.meta && page.meta.lang) {
        document.documentElement.lang = page.meta.lang;
        this.lang = page.meta.lang;
      }
      if (page.accent) {
        this._applyAccent(page.accent);
      }

      // render
      const main = this.host;
      main.innerHTML = '';
      main.appendChild(this._renderCover(page));
      const blocks = page.blocks || [];
      for (const block of blocks) {
        const el = this._renderTopBlock(block);
        if (el) main.appendChild(el);
      }

      // expose warnings for forward-compat indicator
      if (this.warnings.length) {
        window.dispatchEvent(new CustomEvent('html-doc:warnings', { detail: this.warnings }));
      }
      // tell chrome.js to (re)build TOC, init reading aids
      window.dispatchEvent(new CustomEvent('html-doc:rendered', { detail: { page: page } }));
    }

    /* -------------------------------------------------------------- *
     * Cover
     * -------------------------------------------------------------- */

    _renderCover(page) {
      const cover = document.createElement('header');
      cover.className = 'cover';
      const meta = page.meta || {};
      if (meta.eyebrow) {
        const eb = document.createElement('div');
        eb.className = 'eyebrow';
        eb.textContent = meta.eyebrow;
        cover.appendChild(eb);
      }
      const h1 = document.createElement('h1');
      h1.textContent = page.title || '';
      cover.appendChild(h1);
      if (meta.subtitle) {
        const sub = document.createElement('p');
        sub.className = 'subtitle';
        sub.textContent = meta.subtitle;
        cover.appendChild(sub);
      }
      const metaParts = [];
      if (meta.date) metaParts.push(meta.date);
      if (meta.audience) metaParts.push(meta.audience);
      if (meta.read_time) metaParts.push(meta.read_time);
      if (metaParts.length) {
        const m = document.createElement('div');
        m.className = 'meta';
        m.textContent = metaParts.join(' · ');
        cover.appendChild(m);
      }
      // "Last updated" line — trust signal lifted from Vercel / VitePress /
      // Stripe. Quietly rendered below the main meta row in faint type.
      if (meta.updated) {
        const u = document.createElement('div');
        u.className = 'meta meta-updated';
        u.textContent = 'Last updated ' + meta.updated;
        cover.appendChild(u);
      }
      return cover;
    }

    /* -------------------------------------------------------------- *
     * Top-level blocks
     * -------------------------------------------------------------- */

    _renderTopBlock(block) {
      if (!block || !block.kind) return this._unknown(block);
      switch (block.kind) {
        case 'tldr':     return this._renderTldr(block);
        case 'kpi-grid': return this._renderKpiGrid(block);
        case 'section':  return this._renderSection(block);
        default:         return this._renderContentBlock(block); // tolerant: allow content-blocks at top level
      }
    }

    _renderTldr(block) {
      const section = document.createElement('section');
      section.id = 'tldr';
      const tldr = document.createElement('div');
      tldr.className = 'tldr';
      const label = document.createElement('span');
      label.className = 'tldr-label';
      label.textContent = 'TL;DR';
      tldr.appendChild(label);
      // Always emit an h2 so the TOC has an entry; default to "TL;DR".
      // Without it the buildTOC pass would still find the h2 inside .tldr
      // (descendant search) but it would be empty — and an empty TOC
      // entry takes up the "1." slot and shifts everything else.
      const h2 = document.createElement('h2');
      h2.textContent = block.title || 'TL;DR';
      tldr.appendChild(h2);
      if (block.summary) {
        const p = document.createElement('p');
        p.className = 'one-line';
        p.appendChild(this._renderRich(block.summary));
        tldr.appendChild(p);
      }
      if (block.bullets && block.bullets.length) {
        const ul = document.createElement('ul');
        for (const b of block.bullets) {
          const li = document.createElement('li');
          li.appendChild(this._renderRich(b));
          ul.appendChild(li);
        }
        tldr.appendChild(ul);
      }
      section.appendChild(tldr);
      return section;
    }

    _renderKpiGrid(block) {
      const grid = document.createElement('div');
      grid.className = 'kpi-grid';
      for (const tile of (block.tiles || [])) {
        const k = document.createElement('div');
        k.className = 'kpi';
        const num = document.createElement('div');
        num.className = 'num';
        num.textContent = String(tile.num);
        k.appendChild(num);
        const lab = document.createElement('div');
        lab.className = 'label';
        lab.textContent = tile.label || '';
        k.appendChild(lab);
        grid.appendChild(k);
      }
      return grid;
    }

    _renderSection(block) {
      const section = document.createElement('section');
      if (block.id) section.id = block.id;
      const h2 = document.createElement('h2');
      h2.textContent = block.title || '';
      section.appendChild(h2);
      if (block.lead) {
        const lead = document.createElement('p');
        lead.className = 'section-lead';
        lead.appendChild(this._renderRich(block.lead));
        section.appendChild(lead);
      }
      for (const sub of (block.blocks || [])) {
        const el = this._renderContentBlock(sub);
        if (el) section.appendChild(el);
      }
      return section;
    }

    /* -------------------------------------------------------------- *
     * Content blocks (allowed inside sections)
     * -------------------------------------------------------------- */

    _renderContentBlock(block) {
      if (!block || !block.kind) return this._unknown(block);
      let el;
      switch (block.kind) {
        case 'paragraph':    el = this._renderParagraph(block); break;
        case 'heading':      el = this._renderHeading(block); break;
        case 'callout':      el = this._renderCallout(block); break;
        case 'insight':      el = this._renderInsight(block); break;
        case 'info-tip':     el = this._renderInfoTip(block); break;
        case 'list':         el = this._renderList(block); break;
        case 'code':         el = this._renderCode(block); break;
        case 'annotated-code': el = this._renderAnnotatedCode(block); break;
        case 'example':      el = this._renderExample(block); break;
        case 'table':        el = this._renderTable(block); break;
        case 'tldr':         el = this._renderTldr(block); break;
        case 'kpi-grid':     el = this._renderKpiGrid(block); break;
        case 'step-flow':    el = this._renderStepFlow(block); break;
        case 'compare-grid': el = this._renderCompareGrid(block); break;
        case 'chart':        el = this._renderChart(block); break;
        case 'diagram':      el = this._renderDiagram(block); break;
        case 'live-snippet': el = this._renderLiveSnippet(block); break;
        default:             el = this._unknown(block); break;
      }
      // Propagate `bind` so chrome.js's data-bind hover-sync pairs work
      // for any block kind the author wants to pair (paragraph ↔ code
      // ↔ callout ↔ chart, etc.).
      if (el && block.bind) el.setAttribute('data-bind', block.bind);
      return el;
    }

    _renderChart(block) {
      // Dispatch by type. Three rendering paths:
      //
      // - bar / stacked-bar / grouped-bar — DIV-based horizontal CSS
      //   bars. Real DOM text, fluid resizing, no JS after first paint.
      // - scatter / line / area / bubble / quadrant / donut — the
      //   html-doc-chart Custom Element, which owns SVG + pan/zoom +
      //   PNG export. The element parses its data + extras from child
      //   <script> tags (avoids attribute-encoding pain).
      const type = block.type || 'scatter';
      if (type === 'bar') return this._renderBars(block);
      if (type === 'stacked-bar' || type === 'grouped-bar') {
        return this._renderMultiBars(block, type);
      }
      const el = document.createElement('html-doc-chart');
      el.setAttribute('type', type);
      if (block.title) el.setAttribute('title', block.title);
      if (block.x_label) el.setAttribute('x-label', block.x_label);
      if (block.y_label) el.setAttribute('y-label', block.y_label);
      // Cartesian data: stash series as JSON.
      const data = document.createElement('script');
      data.type = 'application/json';
      data.textContent = JSON.stringify(block.series || []);
      el.appendChild(data);
      // Quadrant overlay: ship the {x, y, labels} as a second JSON
      // script tag; the element looks for `script[data-extras]`.
      if (type === 'quadrant' && block.quadrants) {
        const q = document.createElement('script');
        q.type = 'application/json';
        q.setAttribute('data-extras', 'quadrants');
        q.textContent = JSON.stringify(block.quadrants);
        el.appendChild(q);
      }
      // Donut slices: separate payload from `series`.
      if (type === 'donut' && Array.isArray(block.slices)) {
        const d = document.createElement('script');
        d.type = 'application/json';
        d.setAttribute('data-extras', 'slices');
        d.textContent = JSON.stringify(block.slices);
        el.appendChild(d);
      }
      // Tier-1/3 extension types — each ships its own payload under
      // data-extras. The Custom Element switches by `type` in
      // connectedCallback and reads only the extras its renderer cares
      // about; unknown extras are ignored so the data shape can grow
      // without breaking older clients.
      const extraMap = {
        heatmap: { cells: block.cells, row_labels: block.row_labels, col_labels: block.col_labels, scale: block.scale, domain: block.domain },
        sparkline: { values: block.values, variant: block.variant, end_label: block.end_label },
        waffle: { segments: block.segments, total: block.total, grid_rows: block.grid_rows, grid_cols: block.grid_cols },
        gauge: { value: block.value, min: block.min, max: block.max, target: block.target, label: block.label, zones: block.zones },
        radar: { axes: block.axes },
        'box-plot': { boxes: block.boxes },
        bullet: { tracks: block.tracks },
        slope: { items: block.items, from_label: block.from_label, to_label: block.to_label },
        histogram: { bins: block.bins },
        'calendar-heatmap': { date_values: block.date_values, year: block.year, scale: block.scale, domain: block.domain },
        treemap: { tree: block.tree },
        ridgeline: { distributions: block.distributions },
        funnel: { stages: block.stages }
      };
      if (extraMap[type]) {
        const x = document.createElement('script');
        x.type = 'application/json';
        x.setAttribute('data-extras', type);
        x.textContent = JSON.stringify(extraMap[type]);
        el.appendChild(x);
      }
      return el;
    }

    _renderMultiBars(block, mode) {
      // Horizontal multi-series bar render. Each category is a row;
      // within the row, each series contributes either a stacked
      // segment (mode=stacked-bar) or a side-by-side mini-bar
      // (mode=grouped-bar). Layout is CSS-only — no SVG, no JS.
      const categories = block.categories || [];
      const series = block.series || [];
      const wrap = document.createElement('div');
      wrap.className = 'bar-chart bar-chart-multi bar-chart-' + mode;
      wrap.setAttribute('role', 'img');
      wrap.setAttribute('aria-label', (block.title ? block.title + ' — ' : '') + mode + ' with ' + categories.length + ' categories');
      if (block.title) {
        const h = document.createElement('h4');
        h.className = 'bar-chart-title';
        h.textContent = block.title;
        wrap.appendChild(h);
      }
      // Legend chip rack at the top — one entry per series.
      if (series.some(s => s.label)) {
        const legend = document.createElement('div');
        legend.className = 'bar-chart-legend';
        for (const s of series) {
          if (!s.label) continue;
          const chip = document.createElement('span');
          chip.className = 'bar-chart-legend-chip ' + (s.color || 'accent');
          const sw = document.createElement('span');
          sw.className = 'bar-chart-legend-swatch';
          chip.appendChild(sw);
          chip.appendChild(document.createTextNode(s.label));
          legend.appendChild(chip);
        }
        wrap.appendChild(legend);
      }
      // Compute the scale max.
      let scaleMax;
      if (block.max !== undefined) {
        scaleMax = block.max;
      } else if (mode === 'stacked-bar') {
        // Sum across series per category, then take the max.
        scaleMax = 0;
        for (let ci = 0; ci < categories.length; ci++) {
          let sum = 0;
          for (const s of series) sum += (s.values && s.values[ci]) || 0;
          if (sum > scaleMax) scaleMax = sum;
        }
      } else {
        // grouped: largest single value across all series.
        scaleMax = 1;
        for (const s of series) {
          for (const v of (s.values || [])) if (v > scaleMax) scaleMax = v;
        }
      }
      if (scaleMax <= 0) scaleMax = 1;
      // Per-category row totals — needed both for the readout and
      // for each fill's hover payload (share-of-category).
      const rowTotals = categories.map((_, ci) => {
        let t = 0;
        for (const s of series) t += (s.values && s.values[ci]) || 0;
        return t;
      });
      categories.forEach((cat, ci) => {
        const row = document.createElement('div');
        row.className = 'bar-row';
        const lab = document.createElement('span');
        lab.className = 'bar-label';
        lab.textContent = cat;
        row.appendChild(lab);
        const track = document.createElement('div');
        track.className = 'bar-track';
        const rowTotal = rowTotals[ci];
        series.forEach((s, si) => {
          const v = (s.values && s.values[ci]) || 0;
          const fill = document.createElement('div');
          fill.className = 'bar-fill ' + (s.color || 'accent');
          fill.setAttribute('data-series', String(si));
          const pct = Math.max(0, Math.min(100, (v / scaleMax) * 100));
          fill.style.width = pct + '%';
          // Rich hover payload — chrome.js wires .bar-chart-multi
          // .bar-fill to the shared tooltip controller.
          const share = rowTotal > 0 ? v / rowTotal : 0;
          fill.setAttribute('data-hover-payload', JSON.stringify({
            series: s.label || '',
            label: cat,
            kv: [
              { k: 'value', v: String(v) },
              { k: 'share', v: Math.round(share * 100) + '%' }
            ],
            footer: 'in ' + cat + ' = ' + rowTotal
          }));
          if (s.label) fill.title = s.label + ': ' + v;
          track.appendChild(fill);
        });
        row.appendChild(track);
        const val = document.createElement('span');
        val.className = 'bar-value';
        val.textContent = String(rowTotal);
        row.appendChild(val);
        wrap.appendChild(row);
      });
      return wrap;
    }

    _renderDiagram(block) {
      const el = document.createElement('html-doc-diagram');
      if (block.caption) el.setAttribute('caption', block.caption);
      const src = document.createElement('script');
      src.type = 'text/x-mermaid';
      src.textContent = block.source || '';
      el.appendChild(src);
      return el;
    }

    _renderLiveSnippet(block) {
      const el = document.createElement('html-doc-snippet');
      if (block.label) el.setAttribute('label', block.label);
      el.setAttribute('language', block.language || 'html-css-js');
      const src = document.createElement('script');
      src.type = 'text/plain';
      src.textContent = block.source || '';
      el.appendChild(src);
      return el;
    }

    _renderParagraph(block) {
      const p = document.createElement('p');
      p.appendChild(this._renderRich(block.content));
      return p;
    }

    /* Helper for blocks (callout, insight) that may carry richString
       content. Two shapes survive in the wild:

       - Single rich string OR mixed-inline array — render as ONE <p>.
       - Array of plain strings (no inline-kind objects) — author meant
         multiple paragraphs; render as N <p>s. Without this rule
         authors get a wall of run-together sentences whenever they
         pass a list of strings into a callout's content.

       The detector is mechanical: an array with at least one item that
       is itself an inline-kind object (eg {kind:'code',text:'x'}) is
       inline-shape, so single paragraph. An all-plain-string array of
       length ≥ 2 is multi-paragraph. */
    _appendRichAsParagraphs(host, content) {
      if (content === undefined || content === null) return;
      if (Array.isArray(content) && content.length > 1 &&
          content.every(function (it) { return typeof it === 'string'; })) {
        for (const text of content) {
          const p = document.createElement('p');
          p.appendChild(this._renderRich(text));
          host.appendChild(p);
        }
        return;
      }
      const p = document.createElement('p');
      p.appendChild(this._renderRich(content));
      host.appendChild(p);
    }

    _renderHeading(block) {
      const level = Math.max(3, Math.min(4, block.level || 3));
      const h = document.createElement('h' + level);
      if (block.id) h.id = block.id;
      h.textContent = block.title || '';
      return h;
    }

    _renderCallout(block) {
      const c = document.createElement('div');
      const type = block.type || 'neutral';
      c.className = 'callout ' + type;
      // Standard symbol per callout type so the reader sees the
      // semantic class at a glance, not just a colored border. The
      // CSS applies the symbol via ::before on .callout, keyed by
      // the type class — no DOM symbol needed here.
      c.setAttribute('data-callout-symbol', this._calloutSymbol(type));
      if (block.title) {
        const h = document.createElement('h4');
        h.textContent = block.title;
        c.appendChild(h);
      }
      if (block.content !== undefined) {
        this._appendRichAsParagraphs(c, block.content);
      }
      return c;
    }

    _calloutSymbol(type) {
      // Single-character glyphs that all renderable on system fonts
      // without falling back to emoji presentation. CSS does the
      // colour + sizing per type.
      switch (type) {
        case 'info':
        case 'note':    return 'ⓘ';        // ⓘ
        case 'tip':     return '✨';        // ✨
        case 'warn':
        case 'warning': return '⚠';        // ⚠
        case 'caution': return '⚠';        // ⚠ (caution shares glyph, differs by colour)
        case 'danger':  return '⛔';        // ⛔
        case 'success': return '✔';        // ✔
        case 'neutral':
        default:        return '●';        // ●
      }
    }

    _renderInsight(block) {
      const ins = document.createElement('aside');
      ins.className = 'insight';
      this._appendRichAsParagraphs(ins, block.content);
      return ins;
    }

    _renderInfoTip(block) {
      const det = document.createElement('details');
      det.className = 'info-tip';
      const sum = document.createElement('summary');
      sum.textContent = block.summary || 'Details';
      det.appendChild(sum);
      for (const sub of (block.content || [])) {
        const el = this._renderContentBlock(sub);
        if (el) det.appendChild(el);
      }
      return det;
    }

    _renderList(block) {
      const tag = block.style === 'numbered' ? 'ol' : 'ul';
      const list = document.createElement(tag);
      for (const item of (block.items || [])) {
        const li = document.createElement('li');
        li.appendChild(this._renderRich(item));
        list.appendChild(li);
      }
      return list;
    }

    _renderCode(block) {
      const pre = document.createElement('pre');
      const code = document.createElement('code');
      if (block.language) code.className = 'language-' + block.language;
      code.textContent = block.source || '';
      pre.appendChild(code);
      return pre;
    }

    _renderTable(block) {
      // Two valid shapes:
      //   { headers: [...], rows: [[c1, c2, ...], ...] }
      //   { headers: [...], groups: [{title, rows: [[...], ...]}, ...] }
      // The chrome.js post-processor (UX6) discovers groups by class /
      // colspan markers, so we emit those even from the JSON path.
      //
      // Header object form `{ label, filter: "chips", values: [...] }`
      // and cell object form `{ value, values: [...] }` are surfaced as
      // `data-filter` / `data-values` attributes so chrome.js can build
      // the chip rack without re-reading the JSON.
      //
      // Optional block.view ∈ {table, list, cards, board}: pins the
      // initial view shown by the table-chrome view toggle. Falls
      // through to 'table' when unset (the historical default).
      const table = document.createElement('table');
      if (block.view) table.setAttribute('data-default-view', block.view);
      const headers = block.headers || [];
      if (headers.length) {
        const thead = document.createElement('thead');
        const tr = document.createElement('tr');
        for (const h of headers) {
          const th = document.createElement('th');
          if (h && typeof h === 'object' && !Array.isArray(h)) {
            if (h.filter === 'chips') {
              th.setAttribute('data-filter', 'chips');
              if (Array.isArray(h.values)) th.setAttribute('data-values', h.values.join('|'));
            }
            if (Array.isArray(h.boardOrder) && h.boardOrder.length) {
              th.setAttribute('data-board-order', h.boardOrder.join('|'));
            }
            th.appendChild(this._renderRich(h.label));
          } else {
            th.appendChild(this._renderRich(h));
          }
          tr.appendChild(th);
        }
        thead.appendChild(tr);
        table.appendChild(thead);
      }
      const tbody = document.createElement('tbody');
      const cellCount = headers.length || 1;

      const renderCell = (cell) => {
        const td = document.createElement('td');
        if (cell && typeof cell === 'object' && !Array.isArray(cell) && Array.isArray(cell.values)) {
          td.setAttribute('data-values', cell.values.join('|'));
          td.appendChild(this._renderRich(cell.value != null ? cell.value : cell.values.join(', ')));
        } else {
          td.appendChild(this._renderRich(cell));
        }
        return td;
      };

      const renderRow = (row, opts) => {
        const tr = document.createElement('tr');
        if (opts && opts.bind) tr.setAttribute('data-bind', opts.bind);
        if (opts && opts.href) {
          // tr's don't have an href attribute, but the click handler can
          // read it from a data-href dataset.
          tr.setAttribute('data-href', opts.href);
          tr.style.cursor = 'pointer';
          tr.addEventListener('click', () => { window.location.href = opts.href; });
        }
        for (const cell of (row.cells || row)) {
          tr.appendChild(renderCell(cell));
        }
        tbody.appendChild(tr);
      };

      const renderGroupHeader = (title) => {
        const tr = document.createElement('tr');
        tr.className = 'group';
        const th = document.createElement('th');
        th.colSpan = cellCount;
        th.appendChild(this._renderRich(title));
        tr.appendChild(th);
        tbody.appendChild(tr);
      };

      if (Array.isArray(block.groups) && block.groups.length) {
        for (const g of block.groups) {
          if (g.title) renderGroupHeader(g.title);
          for (const row of (g.rows || [])) renderRow(row);
        }
      } else {
        for (const row of (block.rows || [])) renderRow(row);
      }
      table.appendChild(tbody);
      return table;
    }

    _renderAnnotatedCode(block) {
      const el = document.createElement('html-doc-annotated-code');
      if (block.language) el.setAttribute('language', block.language);
      const src = document.createElement('script');
      src.setAttribute('type', 'text/x-code');
      src.textContent = block.source || '';
      el.appendChild(src);
      if (Array.isArray(block.annotations) && block.annotations.length) {
        const data = document.createElement('script');
        data.setAttribute('type', 'application/json');
        data.textContent = JSON.stringify(block.annotations);
        el.appendChild(data);
      }
      return el;
    }

    _renderExample(block) {
      // Code + rendered-result pair. Two-column on wide screens (CSS
      // grid via .example-pair), stacked under ~900px. Each cell gets
      // its own label so the reader knows which side is which.
      const wrap = document.createElement('div');
      wrap.className = 'example-pair';
      if (block.title) {
        const t = document.createElement('div');
        t.className = 'example-title';
        t.textContent = block.title;
        wrap.appendChild(t);
      }
      const codeCol = document.createElement('div');
      codeCol.className = 'example-code';
      const codeLbl = document.createElement('div');
      codeLbl.className = 'example-col-label';
      codeLbl.textContent = 'Source';
      codeCol.appendChild(codeLbl);
      if (block.code) codeCol.appendChild(this._renderCode(block.code));
      const renderCol = document.createElement('div');
      renderCol.className = 'example-render';
      const renderLbl = document.createElement('div');
      renderLbl.className = 'example-col-label';
      renderLbl.textContent = 'Render';
      renderCol.appendChild(renderLbl);
      if (block.render) {
        const renderEl = this._renderContentBlock(block.render);
        if (renderEl) renderCol.appendChild(renderEl);
      }
      wrap.appendChild(codeCol);
      wrap.appendChild(renderCol);
      return wrap;
    }

    _renderBars(block) {
      // Horizontal CSS-bar markup. Used by chart type=bar (and
      // historically by the standalone bar-chart kind, which folded
      // into chart). One .bar-row per data row: [label] [track > fill]
      // [readout]. Width is derived from block.max (or auto-derived
      // from the largest value).
      const rows = block.rows || [];
      const max = block.max !== undefined ? block.max : Math.max.apply(null, rows.map(function (r) { return r.value || 0; }).concat([1]));
      const wrap = document.createElement('div');
      wrap.className = 'bar-chart';
      wrap.setAttribute('role', 'img');
      wrap.setAttribute('aria-label', (block.title ? block.title + ' — ' : '') + 'Bar chart with ' + rows.length + ' rows');
      if (block.title) {
        const h = document.createElement('h4');
        h.className = 'bar-chart-title';
        h.textContent = block.title;
        wrap.appendChild(h);
      }
      // Total for share-of-total readouts in hover tooltips.
      const total = rows.reduce((s, r) => s + (+r.value || 0), 0);
      for (const r of rows) {
        const row = document.createElement('div');
        row.className = 'bar-row';
        const lab = document.createElement('span');
        lab.className = 'bar-label';
        lab.textContent = r.label || '';
        const track = document.createElement('div');
        track.className = 'bar-track';
        const fill = document.createElement('div');
        fill.className = 'bar-fill ' + (r.color || 'accent');
        const pct = max > 0 ? Math.max(2, Math.min(100, (r.value / max) * 100)) : 0;
        fill.style.width = pct + '%';
        const share = total > 0 ? r.value / total : 0;
        fill.setAttribute('data-hover-payload', JSON.stringify({
          label: r.label || '',
          kv: [
            { k: 'value', v: r.display !== undefined ? String(r.display) : String(r.value) },
            { k: 'share', v: Math.round(share * 100) + '%' }
          ],
          footer: 'of ' + total
        }));
        track.appendChild(fill);
        const val = document.createElement('span');
        val.className = 'bar-value';
        val.textContent = r.display !== undefined ? r.display : String(r.value);
        row.appendChild(lab);
        row.appendChild(track);
        row.appendChild(val);
        wrap.appendChild(row);
      }
      return wrap;
    }

    _renderStepFlow(block) {
      const wrap = document.createElement('div');
      wrap.className = 'step-cards';
      (block.steps || []).forEach((s, i) => {
        // When href is set, the entire card becomes a single anchor so
        // it is keyboard-reachable AND clickable anywhere inside —
        // matching the visual cue that "this card opens that page".
        const card = document.createElement(s.href ? 'a' : 'div');
        card.className = 'step-card' + (s.href ? ' step-card-link' : '');
        if (s.href) {
          card.setAttribute('href', s.href);
          if (/^https?:/i.test(s.href)) {
            card.setAttribute('target', '_blank');
            card.setAttribute('rel', 'noopener');
          }
        }
        const num = document.createElement('span');
        num.className = 'step-num';
        num.textContent = String(s.num !== undefined ? s.num : i + 1);
        card.appendChild(num);
        const body = document.createElement('div');
        const h = document.createElement('h4');
        h.textContent = s.title || '';
        body.appendChild(h);
        if (s.meta) {
          const m = document.createElement('div');
          m.className = 'step-meta';
          m.textContent = s.meta;
          body.appendChild(m);
        }
        if (s.content !== undefined) {
          const p = document.createElement('p');
          p.appendChild(this._renderRich(s.content));
          body.appendChild(p);
        }
        card.appendChild(body);
        wrap.appendChild(card);
      });
      return wrap;
    }

    _renderCompareGrid(block) {
      // Unified comparison grid. Each card can carry:
      //   verdict: good | bad | neutral | in | out (legacy shorthand)
      //   accent:  accent | warn | danger | success | muted | neutral
      //     accent wins over verdict when both are present.
      //   content: rich-string body
      //   items:   array of rich-strings rendered as a <ul> inside the card
      //   blocks:  array of contentBlock — rich blocks (callouts,
      //            code, charts, tables) rendered after items.
      // Every payload field is optional. Order on the card is:
      // title → content → items → blocks.
      const grid = document.createElement('div');
      grid.className = 'compare-grid';
      for (const c of (block.cards || [])) {
        const card = document.createElement('div');
        // accent wins over verdict. Fall through to neutral.
        const styleKey = c.accent || c.verdict || 'neutral';
        card.className = 'compare-card ' + styleKey;
        if (c.title) {
          const h = document.createElement('h4');
          h.textContent = c.title;
          card.appendChild(h);
        }
        if (c.content !== undefined) {
          const p = document.createElement('p');
          p.appendChild(this._renderRich(c.content));
          card.appendChild(p);
        }
        if (Array.isArray(c.items) && c.items.length) {
          const ul = document.createElement('ul');
          for (const it of c.items) {
            const li = document.createElement('li');
            li.appendChild(this._renderRich(it));
            ul.appendChild(li);
          }
          card.appendChild(ul);
        }
        if (Array.isArray(c.blocks) && c.blocks.length) {
          for (const sub of c.blocks) {
            const el = this._renderContentBlock(sub);
            if (el) card.appendChild(el);
          }
        }
        grid.appendChild(card);
      }
      return grid;
    }

    /* -------------------------------------------------------------- *
     * Rich text (paragraph content arrays)
     * -------------------------------------------------------------- */

    _renderRich(rich) {
      const frag = document.createDocumentFragment();
      if (rich === undefined || rich === null) return frag;
      // Common pipeline used by both the plain-string branch and each
      // string entry inside the array branch: first try pseudo-HTML tag
      // detection (<code>…</code>), then markdown inline (**bold**,
      // *italic*, `code`, [text](url)). Either branch may yield nothing
      // (no matches) — in that case the whole string renders as a text
      // node.
      const self = this;
      const renderString = function (text) {
        const tags = HtmlDocRenderer._splitInlineTags(text);
        for (const part of tags) {
          if (typeof part === 'string') {
            const mds = HtmlDocRenderer._splitInlineMd(part);
            if (mds) {
              for (const sub of mds) {
                if (typeof sub === 'string') frag.appendChild(document.createTextNode(sub));
                else { const el = self._renderInline(sub); if (el) frag.appendChild(el); }
              }
            } else {
              frag.appendChild(document.createTextNode(part));
            }
          } else {
            const el = self._renderInline(part);
            if (el) frag.appendChild(el);
          }
        }
      };
      if (typeof rich === 'string') {
        renderString(rich);
        return frag;
      }
      if (!Array.isArray(rich)) {
        this._warn('rich-string-invalid', 'Expected string or array', rich);
        return frag;
      }
      for (const item of rich) {
        if (typeof item === 'string') {
          renderString(item);
        } else if (item && item.kind) {
          const el = this._renderInline(item);
          if (el) frag.appendChild(el);
        } else {
          this._warn('rich-item-invalid', 'Unexpected inline item', item);
        }
      }
      return frag;
    }

    _renderInline(node) {
      switch (node.kind) {
        case 'glossary-term': {
          const e = document.createElement('glossary-term');
          if (node.term) e.setAttribute('term', node.term);
          if (node.in)   e.setAttribute('in',   node.in);
          if (node.lang) e.setAttribute('lang', node.lang);
          e.textContent = node.text || node.term || '';
          return e;
        }
        case 'ext-ref': {
          const e = document.createElement('ext-ref');
          if (node.name) e.setAttribute('name', node.name);
          if (node.in)   e.setAttribute('in',   node.in);
          if (node.lang) e.setAttribute('lang', node.lang);
          e.textContent = node.text || node.name || '';
          return e;
        }
        case 'code': {
          const e = document.createElement('code');
          e.textContent = node.text || '';
          return e;
        }
        case 'em': {
          const e = document.createElement('em');
          e.textContent = node.text || '';
          return e;
        }
        case 'strong': {
          const e = document.createElement('strong');
          e.textContent = node.text || '';
          return e;
        }
        case 'link': {
          const e = document.createElement('a');
          e.textContent = node.text || node.href || '';
          if (node.href) e.setAttribute('href', node.href);
          if (node.href && /^https?:/.test(node.href)) {
            e.setAttribute('target', '_blank');
            e.setAttribute('rel', 'noopener');
          }
          return e;
        }
        case 'html': {
          // Sanitised inline HTML pass-through. Schema + Markdown
          // converter both restrict the tag vocabulary upstream;
          // here we just drop the string into a span via innerHTML
          // so the browser parses it as nodes.
          const span = document.createElement('span');
          span.innerHTML = node.text || '';
          return span;
        }
        default:
          return this._unknownInline(node);
      }
    }

    /* -------------------------------------------------------------- *
     * Helpers
     * -------------------------------------------------------------- */

    _applyAccent(accent) {
      // Named tokens map to known palettes; CSS hex passes through.
      const palettes = {
        teal:   { light: '#0f766e', soft: '#ccfbf1', strong: '#115e59', dark: '#2dd4bf', darkSoft: '#042f2e', darkStrong: '#5eead4' },
        amber:  { light: '#b45309', soft: '#fef3c7', strong: '#b45309', dark: '#fbbf24', darkSoft: '#422006', darkStrong: '#fcd34d' },
        indigo: { light: '#4338ca', soft: '#e0e7ff', strong: '#3730a3', dark: '#a5b4fc', darkSoft: '#1e1b4b', darkStrong: '#c7d2fe' }
      };
      const p = palettes[accent];
      let style = document.getElementById('html-doc-accent');
      if (!style) {
        style = document.createElement('style');
        style.id = 'html-doc-accent';
        document.head.appendChild(style);
      }
      if (p) {
        style.textContent =
          ':root { --accent: ' + p.light + '; --accent-soft: ' + p.soft + '; --accent-strong: ' + p.strong + '; }' +
          ':root[data-theme="dark"] { --accent: ' + p.dark + '; --accent-soft: ' + p.darkSoft + '; --accent-strong: ' + p.darkStrong + '; }';
      } else {
        // Treat as a raw color; user can override via richer CSS if needed.
        style.textContent = ':root { --accent: ' + accent + '; }';
      }
    }

    _unknown(block) {
      this._warn('unknown-block-kind', 'Unknown block.kind: ' + (block && block.kind), block);
      return null;
    }

    _unknownInline(node) {
      this._warn('unknown-inline-kind', 'Unknown inline.kind: ' + (node && node.kind), node);
      return null;
    }

    _warn(code, msg, payload) {
      this.warnings.push({ code: code, msg: msg, payload: payload, level: 'warn' });
      // eslint-disable-next-line no-console
      console.warn('[html-doc] ' + code + ': ' + msg, payload);
    }

    _fail(code, msg, payload) {
      this.warnings.push({ code: code, msg: msg, payload: payload, level: 'error' });
      // eslint-disable-next-line no-console
      console.error('[html-doc] ' + code + ': ' + msg, payload);
    }
  }

  /**
   * Auto-boot: pick up inline JSON if present, else fetch by URL.
   *
   *   <script type="application/json" id="__htmldoc_page__">
   *     { "kind": "page", "title": "...", ... }
   *   </script>
   *
   * Standalone builds (html-doc build → dist/standalone/) inline the
   * JSON via that tag so the page renders without a network fetch.
   * Dev pages and the dist/site/ build fall through to fetching the
   * sibling *.json file derived from the current URL.
   */
  HtmlDocRenderer.autoBoot = function (opts) {
    // Idempotent: legacy stubs include an inline autoBoot script that
    // races with the self-trigger below. Skip the second call so we
    // don't render twice.
    if (HtmlDocRenderer._autoBootRan) return HtmlDocRenderer._autoBootRan;
    const inline = document.getElementById('__htmldoc_page__');
    let result;
    if (inline) {
      try {
        const data = JSON.parse(inline.textContent);
        result = new HtmlDocRenderer(opts || {}).render(data);
      } catch (e) {
        console.error('[html-doc] inline page parse failed', e);
      }
    }
    if (result === undefined) {
      // Hash-based routing: when URL is "...index.html#architecture.html",
      // render that target instead of index.json. chrome.js's hashchange
      // handler covers subsequent navigation; this branch only handles
      // the very first paint so we don't show index then flash to the
      // requested page.
      const rawHash = (window.location.hash || '').replace(/^#/, '');
      const sep = rawHash.indexOf(':');
      const hashPage = sep >= 0 ? rawHash.slice(0, sep) : rawHash;
      let jsonName;
      let pagePath;
      if (hashPage && hashPage.endsWith('.html')) {
        pagePath = hashPage;
        jsonName = hashPage.replace(/\.html$/, '.json');
      } else {
        const last = window.location.pathname.split('/').pop() || '';
        pagePath = last.endsWith('.html') ? last : 'index.html';
        jsonName = last.replace(/\.html$/, '.json') || 'index.json';
      }
      // Set BEFORE renderFromUrl so chrome.js's render-event handlers
      // (e.g., buildTOC) namespace anchors to the right page.
      window.__htmldocCurrentPage = pagePath;
      result = new HtmlDocRenderer(opts || {}).renderFromUrl(jsonName);
      // Honor the in-page anchor on first paint: refresh on
      // "#architecture.html:perf" should land at #perf, not page-top.
      // hashchange doesn't fire on reload (URL is unchanged), so scroll
      // explicitly here once render resolves.
      const trailingAnchor = sep >= 0 ? rawHash.slice(sep + 1) : '';
      if (trailingAnchor && result && typeof result.then === 'function') {
        result.then(function () {
          requestAnimationFrame(function () {
            const el = document.getElementById(trailingAnchor)
              || document.querySelector('[id="' + trailingAnchor + '"]');
            if (el) el.scrollIntoView();
          });
        });
      }
    }
    HtmlDocRenderer._autoBootRan = result;
    return result;
  };

  window.HtmlDocRenderer = HtmlDocRenderer;

  // Self-trigger so per-page stubs don't need an inline autoBoot script.
  // The legacy inline form remains compatible — autoBoot itself is
  // idempotent (see _autoBootRan guard above).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { HtmlDocRenderer.autoBoot(); });
  } else {
    HtmlDocRenderer.autoBoot();
  }
})();
