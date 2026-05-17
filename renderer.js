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

    /** Fetch JSON, parse, and render into the host. */
    async renderFromUrl(url, host) {
      let page;
      try {
        const res = await fetch(url, { cache: 'no-cache' });
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
      if (block.title) {
        const h2 = document.createElement('h2');
        h2.textContent = block.title;
        tldr.appendChild(h2);
      }
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
      switch (block.kind) {
        case 'paragraph':    return this._renderParagraph(block);
        case 'heading':      return this._renderHeading(block);
        case 'callout':      return this._renderCallout(block);
        case 'insight':      return this._renderInsight(block);
        case 'info-tip':     return this._renderInfoTip(block);
        case 'list':         return this._renderList(block);
        case 'code':         return this._renderCode(block);
        case 'kpi-grid':     return this._renderKpiGrid(block);
        case 'bar-chart':    return this._renderBarChart(block);
        case 'step-flow':    return this._renderStepFlow(block);
        case 'compare-grid': return this._renderCompareGrid(block);
        case 'scope-grid':   return this._renderScopeGrid(block);
        case 'chart':        return this._renderChart(block);
        case 'diagram':      return this._renderDiagram(block);
        case 'live-snippet': return this._renderLiveSnippet(block);
        default:             return this._unknown(block);
      }
    }

    _renderChart(block) {
      const el = document.createElement('html-doc-chart');
      el.setAttribute('type', block.type || 'scatter');
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

    _renderBarChart(block) {
      const rows = block.rows || [];
      const max = block.max !== undefined ? block.max : Math.max.apply(null, rows.map(function (r) { return r.value || 0; }).concat([1]));
      const wrap = document.createElement('div');
      wrap.className = 'bar-chart';
      wrap.setAttribute('role', 'img');
      wrap.setAttribute('aria-label', 'Bar chart with ' + rows.length + ' rows');
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
        grid.appendChild(card);
      }
      return grid;
    }

    _renderScopeGrid(block) {
      const grid = document.createElement('div');
      grid.className = 'scope-grid';
      for (const col of (block.columns || [])) {
        const c = document.createElement('div');
        c.className = 'scope-col ' + (col.status || 'in');
        const h = document.createElement('h4');
        h.textContent = col.title || '';
        c.appendChild(h);
        const ul = document.createElement('ul');
        for (const it of (col.items || [])) {
          const li = document.createElement('li');
          li.appendChild(this._renderRich(it));
          ul.appendChild(li);
        }
        c.appendChild(ul);
        grid.appendChild(c);
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
        frag.appendChild(document.createTextNode(rich));
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

  window.HtmlDocRenderer = HtmlDocRenderer;
})();
