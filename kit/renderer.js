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
      // Dispatch by type. Bar charts render as DIV-based horizontal bars
      // (the row-per-item shape is fundamentally different from a
      // Cartesian scatter/line and benefits from real DOM text + fluid
      // resizing). Scatter / line render through the HtmlDocChart Custom
      // Element which owns SVG, pan/zoom, and the export toolbar.
      const type = block.type || 'scatter';
      if (type === 'bar') return this._renderBars(block);
      const el = document.createElement('html-doc-chart');
      el.setAttribute('type', type);
      if (block.title) el.setAttribute('title', block.title);
      if (block.x_label) el.setAttribute('x-label', block.x_label);
      if (block.y_label) el.setAttribute('y-label', block.y_label);
      // Stash data as a JSON script tag inside the element; the
      // Custom Element parses it. Avoids encoding/quoting issues in
      // attributes for complex data.
      const data = document.createElement('script');
      data.type = 'application/json';
      data.textContent = JSON.stringify(block.series || []);
      el.appendChild(data);
      return el;
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

    _renderHeading(block) {
      const level = Math.max(3, Math.min(4, block.level || 3));
      const h = document.createElement('h' + level);
      if (block.id) h.id = block.id;
      h.textContent = block.title || '';
      return h;
    }

    _renderCallout(block) {
      const c = document.createElement('div');
      c.className = 'callout ' + (block.type || 'neutral');
      if (block.title) {
        const h = document.createElement('h4');
        h.textContent = block.title;
        c.appendChild(h);
      }
      if (block.content !== undefined) {
        const p = document.createElement('p');
        p.appendChild(this._renderRich(block.content));
        c.appendChild(p);
      }
      return c;
    }

    _renderInsight(block) {
      const ins = document.createElement('aside');
      ins.className = 'insight';
      ins.appendChild(this._renderRich(block.content));
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
      const table = document.createElement('table');
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
        const card = document.createElement('div');
        card.className = 'step-card';
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
      //   verdict: good | bad | neutral | in | out
      //     good/in render with a success-coloured top border;
      //     bad/out render with danger / muted respectively.
      //   content: rich-string body
      //   items:   array of rich-strings rendered as a <ul> inside the card
      // Either field is optional. When both are present, content appears
      // first, then the items list.
      const grid = document.createElement('div');
      grid.className = 'compare-grid';
      for (const c of (block.cards || [])) {
        const card = document.createElement('div');
        card.className = 'compare-card ' + (c.verdict || 'neutral');
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
      if (typeof rich === 'string') {
        // Strings authored with `<code>…</code>` (or other simple inline
        // tags) used to render as literal text. Detect and convert to
        // inline code/em/strong so authors can write either form. The
        // detection is intentionally narrow — only the three text-shape
        // primitives the kit also exposes in the JSON inline schema —
        // so unrelated angle-bracket text (e.g. element names in
        // documentation like "<callout>") still renders literally.
        const pseudoInline = HtmlDocRenderer._splitInlineTags(rich);
        if (pseudoInline.length > 1) {
          for (const part of pseudoInline) {
            if (typeof part === 'string') frag.appendChild(document.createTextNode(part));
            else { const el = this._renderInline(part); if (el) frag.appendChild(el); }
          }
        } else {
          frag.appendChild(document.createTextNode(rich));
        }
        return frag;
      }
      if (!Array.isArray(rich)) {
        this._warn('rich-string-invalid', 'Expected string or array', rich);
        return frag;
      }
      for (const item of rich) {
        if (typeof item === 'string') {
          frag.appendChild(document.createTextNode(item));
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
