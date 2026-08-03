/* oku · renderer.js (v2)
 *
 * Walks the compact v2 page tree { k:'page', t, m, b } and emits DOM into
 * the host element. Strings inside b[] are parsed as GFM markdown; objects
 * are typed primitives. Sections are implicit from heading levels inside
 * markdown.
 *
 * Entry: OkuRenderer.renderFromUrl(url, host?)
 * Schema: ../schema/page.schema.json
 */

(function () {
  'use strict';

  /* ================================================================ *
   * v1 → v2 shim
   * Older pages authored against the v1 schema ({kind:"page", title,
   * accent, meta, blocks: [{kind:"section",…}, {kind:"paragraph",…}, …]})
   * load through this converter so they keep rendering. New pages skip
   * it. The same transformation logic lives in `oku migrate` for the
   * persistent disk-side update.
   * ================================================================ */

  function richToMd(rich) {
    if (rich == null) return '';
    if (typeof rich === 'string') return rich;
    if (!Array.isArray(rich)) return '';
    return rich.map(seg => {
      if (typeof seg === 'string') return seg;
      if (!seg || !seg.kind) return '';
      switch (seg.kind) {
        case 'em':       return '*' + (seg.text || '') + '*';
        case 'strong':   return '**' + (seg.text || '') + '**';
        case 'code':     return '`' + (seg.text || '') + '`';
        case 'link':     return '[' + (seg.text || seg.href || '') + '](' + (seg.href || '') + ')';
        case 'glossary-term': return '[' + (seg.text || seg.term || '') + '](#g/' + (seg.term || '') + ')';
        case 'ext-ref':  return '[' + (seg.text || seg.name || '') + '](#x/' + (seg.name || '') + ')';
        case 'html':     return seg.text || '';
        default:         return '';
      }
    }).join('');
  }

  function richToBlockquoteBody(rich) {
    return richToMd(rich).split('\n').map(l => '> ' + l).join('\n');
  }

  function convertV1Block(b) {
    if (!b || !b.kind) return null;
    switch (b.kind) {
      case 'paragraph': return richToMd(b.content);
      case 'heading': {
        const lvl = '#'.repeat(Math.max(3, Math.min(6, b.level || 3)));
        return lvl + ' ' + (b.title || '') + (b.id ? ' {#' + b.id + '}' : '');
      }
      case 'list': {
        const items = (b.items || []).map((it, i) => {
          const marker = b.style === 'numbered' ? (i + 1) + '.' : '-';
          return marker + ' ' + richToMd(it);
        });
        return items.join('\n');
      }
      case 'callout': {
        const type = (b.type || 'note').toUpperCase();
        const titleSuffix = b.title ? ' ' + b.title : '';
        const body = b.content !== undefined ? '\n' + richToBlockquoteBody(b.content) : '';
        return '> [!' + type + ']' + titleSuffix + body;
      }
      case 'tldr': {
        let body = '';
        if (b.summary) body += '\n> ' + richToMd(b.summary);
        if (Array.isArray(b.bullets) && b.bullets.length) {
          body += '\n>';
          for (const bl of b.bullets) body += '\n> - ' + richToMd(bl);
        }
        const tt = b.title ? ' ' + b.title : '';
        return '> [!TLDR]' + tt + body;
      }
      case 'info-tip': {
        // Collapsible disclosure: <details class="info-tip"><summary>.
        // The summary is the visible cue; the body stays hidden until
        // the reader expands it (real "think first, then reveal" for
        // self-check boxes). Content blocks are carried through verbatim
        // so nested lists / tables render correctly inside the details.
        return {
          k: 'info-tip',
          summary: b.summary || '',
          content: Array.isArray(b.content) ? b.content : [],
          open: !!b.open
        };
      }
      case 'insight':
        return { k: 'insight', b: richToMd(b.content) };
      case 'code':
        return '```' + (b.language || '') + '\n' + (b.source || '') + '\n```';
      case 'diagram': {
        const o = { k: 'diagram', src: b.source || '' };
        if (b.caption) o.caption = b.caption;
        return o;
      }
      case 'image': {
        const o = { k: 'image', src: b.src || '' };
        if (b.alt) o.alt = b.alt;
        if (b.caption) o.caption = b.caption;
        if (b.width != null) o.width = b.width;
        return o;
      }
      case 'svg': {
        const o = { k: 'svg', src: b.source || '' };
        if (b.caption) o.caption = b.caption;
        if (b.label) o.label = b.label;
        return o;
      }
      case 'live-snippet': {
        const o = { k: 'live-snippet', src: b.source || '' };
        if (b.language) o.lang = b.language;
        if (b.label) o.label = b.label;
        return o;
      }
      case 'annotated-code': {
        const o = { k: 'annotated-code', src: b.source || '' };
        if (b.language) o.lang = b.language;
        if (b.annotations) o.annotations = b.annotations;
        return o;
      }
      case 'table': {
        const o = { k: 'table' };
        if (b.view) o.view = b.view;
        if (b.headers) o.headers = b.headers.map(convertV1TableHeader);
        if (b.rows) o.rows = b.rows.map(convertV1TableRow);
        if (b.groups) o.groups = b.groups.map(g => ({
          t: g.title ? richToMd(g.title) : '',
          rows: (g.rows || []).map(convertV1TableRow)
        }));
        return o;
      }
      case 'kpi-grid':
        return { k: 'kpi-grid', tiles: (b.tiles || []) };
      case 'step-flow':
        return {
          k: 'step-flow',
          steps: (b.steps || []).map(s => {
            const o = { t: s.title || '' };
            if (s.content !== undefined) o.b = richToMd(s.content);
            if (s.meta) o.meta = s.meta;
            if (s.href) o.href = s.href;
            return o;
          })
        };
      case 'compare-grid':
        return {
          k: 'compare-grid',
          cards: (b.cards || []).map(c => {
            const o = { t: c.title || '' };
            const parts = [];
            if (c.content !== undefined) parts.push(richToMd(c.content));
            if (Array.isArray(c.items) && c.items.length) {
              parts.push(c.items.map(it => '- ' + richToMd(it)).join('\n'));
            }
            if (Array.isArray(c.blocks) && c.blocks.length) {
              for (const sub of c.blocks) {
                const conv = convertV1Block(sub);
                if (typeof conv === 'string') parts.push(conv);
              }
            }
            o.b = parts.join('\n\n');
            if (c.verdict) o.verdict = c.verdict;
            if (c.accent) o.accent = c.accent;
            if (c.href) o.href = c.href;
            return o;
          })
        };
      case 'chart': {
        const o = Object.assign({}, b);
        delete o.kind; o.k = 'chart';
        return o;
      }
      case 'chart-grid': {
        const o = Object.assign({}, b);
        delete o.kind; o.k = 'chart-grid';
        return o;
      }
      case 'example': {
        const o = { k: 'example' };
        if (b.title) o.t = b.title;
        if (b.code) o.code = { k: 'code', src: b.code.source || '', lang: b.code.language };
        if (b.output) {
          const conv = convertV1Block(b.output);
          o.output = conv;
        }
        return o;
      }
      default:
        return null;
    }
  }

  function convertV1TableHeader(h) {
    if (h && typeof h === 'object' && !Array.isArray(h) && h.label !== undefined) {
      const o = Object.assign({}, h);
      o.label = richToMd(h.label);
      return o;
    }
    return richToMd(h);
  }

  function convertV1TableRow(r) {
    if (Array.isArray(r)) return r.map(convertV1TableCell);
    if (r && typeof r === 'object' && r.cells) {
      const o = Object.assign({}, r);
      o.cells = r.cells.map(convertV1TableCell);
      return o;
    }
    return r;
  }

  function convertV1TableCell(c) {
    if (c && typeof c === 'object' && !Array.isArray(c) && Array.isArray(c.values)) {
      const o = Object.assign({}, c);
      if (c.value !== undefined) o.value = richToMd(c.value);
      return o;
    }
    return richToMd(c);
  }

  function convertV1ToV2(page) {
    const out = { k: 'page' };
    if (page.title) out.t = page.title;
    const meta = Object.assign({}, page.meta || {});
    if (page.accent && !meta.accent) meta.accent = page.accent;
    if (Object.keys(meta).length) out.m = meta;
    const b = [];
    let buf = '';
    const flush = () => {
      const s = buf.replace(/\n+$/, '').replace(/^\n+/, '');
      if (s) b.push(s);
      buf = '';
    };
    const appendMd = (md) => {
      if (!md) return;
      if (buf) buf += '\n\n';
      buf += md;
    };
    for (const top of (page.blocks || [])) {
      if (top && top.kind === 'section') {
        flush();
        let head = '## ' + (top.title || '');
        if (top.id) head += ' {#' + top.id + '}';
        appendMd(head);
        if (top.lead) appendMd(richToMd(top.lead));
        for (const sub of (top.blocks || [])) {
          const conv = convertV1Block(sub);
          if (typeof conv === 'string') appendMd(conv);
          else if (conv) { flush(); b.push(conv); }
        }
      } else {
        const conv = convertV1Block(top);
        if (typeof conv === 'string') appendMd(conv);
        else if (conv) { flush(); b.push(conv); }
      }
    }
    flush();
    out.b = b;
    return out;
  }

  /* ================================================================ *
   * Inline markdown parser
   * Handles *em*, **strong**, `code`, [text](href). The href prefixes
   * `#g/` and `#x/` rewrite into <glossary-term> and <ext-ref> elements
   * so glossary / ext-ref tooltips keep working from markdown.
   * ================================================================ */

  function parseInline(text, host) {
    // Order: code (literal — protect from other rules) → strong → em →
    // link → allow-listed inline HTML. One regex pass so positions are
    // tracked. Inline tags OUTSIDE the allow-list stay literal text.
    //
    // Emphasis and link bodies are parsed RECURSIVELY, so `**[a](b)**`,
    // `[**a**](b)`, `**`code`**` and `**bold with *em* inside**` all
    // compose. Only `code` keeps a literal body — that is the rule that
    // protects it. Strong therefore admits `*`/`_` in its body; em still
    // refuses them, which is what stops `*a **b** c*` from crossing.
    const re = /`([^`]+?)`|\*\*([\s\S]+?)\*\*|__([\s\S]+?)__|\*([^*\s][^*]*?)\*|_([^_\s][^_]*?)_|\[([^\]]+?)\]\(([^)\s]+?)\)|<(kbd|sub|sup|mark|abbr|del|ins|samp|span)(\s+[^<>]*)?>([\s\S]*?)<\/\8\s*>|<br\s*\/?>/g;
    let pos = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > pos) host.appendChild(document.createTextNode(text.slice(pos, m.index)));
      if (m[1] !== undefined) {
        const e = document.createElement('code'); e.textContent = m[1]; host.appendChild(e);
      } else if (m[2] !== undefined || m[3] !== undefined) {
        const e = document.createElement('strong'); parseInline(m[2] !== undefined ? m[2] : m[3], e); host.appendChild(e);
      } else if (m[4] !== undefined || m[5] !== undefined) {
        const e = document.createElement('em'); parseInline(m[4] !== undefined ? m[4] : m[5], e); host.appendChild(e);
      } else if (m[6] !== undefined) {
        host.appendChild(renderLink(m[6], m[7]));
      } else if (m[8] !== undefined) {
        // Sanitised allow-list pass-through: bare element, recursive
        // inline body; only `title` survives from the attribute string
        // (tooltips on <abbr>). Everything else is dropped.
        const e = document.createElement(m[8].toLowerCase());
        const title = /\btitle="([^"]*)"/.exec(m[9] || '');
        if (title) e.title = title[1];
        parseInline(m[10], e);
        host.appendChild(e);
      } else {
        host.appendChild(document.createElement('br'));
      }
      pos = m.index + m[0].length;
    }
    if (pos < text.length) host.appendChild(document.createTextNode(text.slice(pos)));
  }

  function renderLink(label, href) {
    // Kit-extension prefixes: #g/term-id  → <glossary-term>
    //                        #x/source-id → <ext-ref>
    // Labels go through parseInline so `[**a**](b)` keeps its markup;
    // the term / name attribute carries the id either way.
    if (href.startsWith('#g/')) {
      const e = document.createElement('glossary-term');
      e.setAttribute('term', href.slice(3));
      parseInline(label, e);
      return e;
    }
    if (href.startsWith('#x/')) {
      const e = document.createElement('ext-ref');
      e.setAttribute('name', href.slice(3));
      parseInline(label, e);
      return e;
    }
    // Cross-page markdown link: a relative `foo.md(#frag)` href points
    // at the rendered page — rewrite to .html. Absolute URLs,
    // fragment-only and root-absolute hrefs pass through untouched.
    const mdLink = href.match(/^(?!\w+:|\/\/|#|\/)(.+?)\.md(#[^\s]*)?$/i);
    if (mdLink) href = mdLink[1] + '.html' + (mdLink[2] || '');
    const a = document.createElement('a');
    parseInline(label, a);
    a.setAttribute('href', href);
    if (/^https?:/i.test(href)) {
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener');
    }
    return a;
  }

  /* ================================================================ *
   * Block markdown parser
   * Splits the source into block-level nodes. Each node has a kind and
   * payload; the caller walks them and emits DOM. Headings are returned
   * as their own nodes so the outer walker can use h2 to open sections.
   * ================================================================ */

  // Slugify a heading title for a default anchor id.
  function slugify(text) {
    return String(text).toLowerCase()
      .replace(/[^a-z0-9\s-]+/g, '')
      .trim()
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-');
  }

  // Fence tags that lift to typed blocks — mirrors _FENCE_KINDS in
  // src/oku/cli.py so a fence renders identically whether the page
  // arrived as .md (lifted at build time) or as a fence inside a v2
  // markdown string (lifted here).
  const FENCE_KINDS = ['chart', 'chart-grid', 'table', 'kpi-grid', 'step-flow',
    'compare-grid', 'insight', 'example', 'live-snippet', 'annotated-code', 'diagram', 'tldr'];

  function liftTypedFence(lang, src) {
    if (lang === 'mermaid') return { k: 'diagram', src: src };
    if (!lang.startsWith('oku-')) return null;
    const kind = lang.slice(4);
    if (FENCE_KINDS.indexOf(kind) < 0) return null;
    let payload;
    try { payload = JSON.parse(src); } catch (e) { return null; }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
    payload.k = kind;
    return payload;
  }

  // Inline-level tags never open an HTML island — a paragraph that
  // happens to start with `<kbd>` stays prose.
  const INLINE_HTML_TAGS = ['a', 'abbr', 'br', 'code', 'del', 'em', 'ins',
    'kbd', 'mark', 'samp', 'span', 'strong', 'sub', 'sup'];

  // The active renderer's typed-block dispatch; set per render() pass so
  // emitMarkdown can hand lifted fence nodes to the same renderers that
  // handle typed b[] objects.
  let __renderTypedBlock = null;

  function parseMarkdown(src) {
    const lines = String(src || '').split('\n');
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      // Blank line — skip.
      if (!line.trim()) { i++; continue; }
      // Horizontal rule.
      if (/^-{3,}\s*$/.test(line)) { out.push({ k: 'hr' }); i++; continue; }
      // Fenced code block. Variable-length: a fence of N backticks
      // closes only at a line of N (or more) backticks. Lets authors
      // nest a 3-tick fenced sample inside a 4-tick outer fence — the
      // CommonMark-compliant way to show markdown code samples that
      // contain code fences.
      const fence = line.match(/^(`{3,})\s*([\w-]*)\s*$/);
      if (fence) {
        const openLen = fence[1].length;
        const lang = fence[2] || '';
        const body = [];
        i++;
        const closeRe = new RegExp('^`{' + openLen + ',}\\s*$');
        while (i < lines.length && !closeRe.test(lines[i])) {
          body.push(lines[i]);
          i++;
        }
        i++; // skip closing fence
        const fsrc = body.join('\n');
        const typed = liftTypedFence(lang, fsrc);
        if (typed) {
          // Italic-caption convention — diagrams only (the one typed
          // block whose schema carries `caption`).
          if (typed.k === 'diagram' && typed.caption === undefined) {
            let j = i;
            while (j < lines.length && !lines[j].trim()) j++;
            const cap = j < lines.length && lines[j].match(/^\*([^*].*)\*\s*$/);
            if (cap && (j + 1 >= lines.length || !lines[j + 1].trim())) {
              typed.caption = cap[1].trim();
              i = j + 1;
            }
          }
          out.push({ k: 'typed', block: typed });
        } else {
          out.push({ k: 'code', lang: lang, src: fsrc });
        }
        continue;
      }
      // Raw HTML island — a block-level tag at column 0 passes through
      // untouched (full capability: custom elements, <script>, <style>).
      // script/style/pre/textarea consume to their closing tag; anything
      // else to the next blank line — CommonMark type-1/6 semantics.
      const island = isIslandStart(line);
      if (island) {
        const tag = island;
        const buf = [];
        if (tag === 'script' || tag === 'style' || tag === 'pre' || tag === 'textarea') {
          const closeRe = new RegExp('</' + tag + '\\s*>', 'i');
          while (i < lines.length) {
            buf.push(lines[i]);
            if (closeRe.test(lines[i])) { i++; break; }
            i++;
          }
        } else {
          while (i < lines.length && lines[i].trim()) {
            buf.push(lines[i]);
            i++;
          }
        }
        out.push({ k: 'html', src: buf.join('\n') });
        continue;
      }
      // Definition list — a term line whose next line is `: definition`.
      if (line.trim() && !isBlockStart(line) && i + 1 < lines.length && /^:\s+\S/.test(lines[i + 1])) {
        const pairs = [];
        while (i < lines.length && lines[i].trim() && !/^:\s/.test(lines[i])
               && i + 1 < lines.length && /^:\s+\S/.test(lines[i + 1])) {
          const term = lines[i].trim();
          i++;
          const defs = [];
          while (i < lines.length && /^:\s+\S/.test(lines[i])) {
            defs.push(lines[i].replace(/^:\s+/, ''));
            i++;
          }
          pairs.push({ term: term, defs: defs });
        }
        out.push({ k: 'dl', pairs: pairs });
        continue;
      }
      // Heading.
      const head = line.match(/^(#{1,6})\s+(.+?)(?:\s+\{#([\w-]+)\})?\s*$/);
      if (head) {
        const level = head[1].length;
        const title = head[2];
        const id = head[3] || slugify(title);
        out.push({ k: 'heading', level: level, title: title, id: id });
        i++;
        continue;
      }
      // Blockquote — gather all consecutive `> ` lines, then check for admonition.
      if (/^>\s?/.test(line)) {
        const block = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          block.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        // Admonition extension: first non-empty line is `[!TYPE]` or `[!TYPE] Title`.
        const adm = block[0] && block[0].match(/^\[!([A-Z]+)\](?:\s+(.+))?$/);
        if (adm) {
          out.push({ k: 'admonition', type: adm[1].toLowerCase(), title: adm[2] || '', body: block.slice(1).join('\n') });
        } else {
          out.push({ k: 'quote', body: block.join('\n') });
        }
        continue;
      }
      // Pipe table — header row, separator row, data rows.
      if (line.indexOf('|') >= 0 && i + 1 < lines.length && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i + 1])) {
        const hdr = splitTableRow(line);
        i += 2; // skip header + separator
        const rows = [];
        while (i < lines.length && lines[i].indexOf('|') >= 0 && lines[i].trim()) {
          rows.push(splitTableRow(lines[i]));
          i++;
        }
        out.push({ k: 'table', headers: hdr, rows: rows });
        continue;
      }
      // List — bullet (- / *) or numbered (1. / 1)).
      if (/^(\s*)([-*]|\d+[.)])\s+/.test(line)) {
        const consumed = parseList(lines, i);
        out.push(consumed.node);
        i = consumed.next;
        continue;
      }
      // Paragraph — gather until blank line or block-start.
      const para = [line];
      i++;
      while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i]) && !(i + 1 < lines.length && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i + 1]))) {
        para.push(lines[i]);
        i++;
      }
      out.push({ k: 'paragraph', text: para.join(' ').replace(/\s+/g, ' ').trim() });
    }
    return out;
  }

  // A block-level HTML tag at column 0 opens an island; inline-level
  // tags don't. Returns the lowercase tag name, or null.
  function isIslandStart(line) {
    const m = line.match(/^<\/?([a-zA-Z][\w-]*)(?:[\s/>]|$)/);
    if (!m) return null;
    const tag = m[1].toLowerCase();
    return INLINE_HTML_TAGS.indexOf(tag) < 0 ? tag : null;
  }

  function isBlockStart(line) {
    return /^#{1,6}\s/.test(line)
      || /^>\s?/.test(line)
      || /^```/.test(line)
      || /^-{3,}\s*$/.test(line)
      || /^(\s*)([-*]|\d+[.)])\s+/.test(line)
      || /^:\s+\S/.test(line)
      || isIslandStart(line) !== null;
  }

  function splitTableRow(line) {
    // Trim leading/trailing pipes, then split on |. Backtick-protected
    // pipes (inside `code`) escape from the split.
    let s = line.trim();
    if (s.startsWith('|')) s = s.slice(1);
    if (s.endsWith('|')) s = s.slice(0, -1);
    const cells = [];
    let cur = '';
    let inCode = false;
    for (const c of s) {
      if (c === '`') { inCode = !inCode; cur += c; }
      else if (c === '|' && !inCode) { cells.push(cur.trim()); cur = ''; }
      else cur += c;
    }
    cells.push(cur.trim());
    return cells;
  }

  function parseList(lines, start) {
    // Walks lines starting at `start`. Returns { node, next }.
    // Supports bullet (- / *) and ordered (1. / 1)) at any indent depth.
    const items = [];
    let i = start;
    const first = lines[start].match(/^(\s*)([-*]|\d+[.)])\s+/);
    const baseIndent = first[1].length;
    const ordered = /\d/.test(first[2]);
    while (i < lines.length) {
      const m = lines[i].match(/^(\s*)([-*]|\d+[.)])\s+(.*)$/);
      if (m && m[1].length === baseIndent) {
        const itemLines = [m[3]];
        i++;
        while (i < lines.length) {
          const continuation = lines[i].match(/^(\s+)(.*)$/);
          if (continuation && continuation[1].length > baseIndent && !/^(\s*)([-*]|\d+[.)])\s+/.test(lines[i])) {
            itemLines.push(lines[i].trim());
            i++;
          } else if (continuation && /^(\s*)([-*]|\d+[.)])\s+/.test(lines[i]) && continuation[1].length > baseIndent) {
            // Nested list start — collect lines while still indented past base.
            const subStart = i;
            while (i < lines.length) {
              const sub = lines[i].match(/^(\s+)/);
              if (!sub || sub[1].length <= baseIndent) break;
              i++;
            }
            // Capture the nested-list source for recursive parse.
            const nested = lines.slice(subStart, i).map(l => l.slice(baseIndent + 2));
            itemLines.push({ __nested: nested });
          } else {
            break;
          }
        }
        items.push(itemLines);
      } else if (lines[i].trim() === '') {
        // Blank inside list — peek; if next is still a list item, continue.
        if (i + 1 < lines.length && /^(\s*)([-*]|\d+[.)])\s+/.test(lines[i + 1])) {
          i++;
          continue;
        }
        break;
      } else {
        break;
      }
    }
    return { node: { k: 'list', ordered: ordered, items: items }, next: i };
  }

  /* ================================================================ *
   * Markdown → DOM
   * Emits block-level DOM into the given host. Returns nothing; caller
   * handles section-opening when heading nodes appear.
   * ================================================================ */

  function emitMarkdown(host, blocks, openSection) {
    for (const node of blocks) {
      switch (node.k) {
        case 'heading': {
          if (node.level === 2 && openSection) {
            openSection(node);
            break;
          }
          const h = document.createElement('h' + Math.min(6, Math.max(1, node.level)));
          if (node.id) h.id = node.id;
          parseInline(node.title, h);
          host.appendChild(h);
          break;
        }
        case 'paragraph': {
          const p = document.createElement('p');
          parseInline(node.text, p);
          host.appendChild(p);
          break;
        }
        case 'code': {
          const pre = document.createElement('pre');
          const code = document.createElement('code');
          if (node.lang) code.className = 'language-' + node.lang;
          code.textContent = node.src;
          pre.appendChild(code);
          host.appendChild(pre);
          break;
        }
        case 'hr': {
          host.appendChild(document.createElement('hr'));
          break;
        }
        case 'quote': {
          const bq = document.createElement('blockquote');
          const sub = parseMarkdown(node.body);
          emitMarkdown(bq, sub, null);
          host.appendChild(bq);
          break;
        }
        case 'admonition': {
          host.appendChild(renderAdmonition(node));
          break;
        }
        case 'list': {
          host.appendChild(renderList(node));
          break;
        }
        case 'table': {
          host.appendChild(renderMarkdownTable(node));
          break;
        }
        case 'html': {
          // Raw HTML island. createContextualFragment (unlike
          // innerHTML) yields <script> elements that execute on
          // insertion — islands are full-capability by design.
          host.appendChild(document.createRange().createContextualFragment(node.src));
          break;
        }
        case 'dl': {
          const dl = document.createElement('dl');
          dl.className = 'md-dl';
          for (const pair of node.pairs) {
            const dt = document.createElement('dt');
            parseInline(pair.term, dt);
            dl.appendChild(dt);
            for (const d of pair.defs) {
              const dd = document.createElement('dd');
              parseInline(d, dd);
              dl.appendChild(dd);
            }
          }
          host.appendChild(dl);
          break;
        }
        case 'typed': {
          if (__renderTypedBlock) {
            const el = __renderTypedBlock(node.block);
            if (el) host.appendChild(el);
          }
          break;
        }
      }
    }
  }

  // Map admonition types to kit callout classes. Standard GFM types
  // (note, tip, important, warning, caution) map directly; TLDR is the
  // one kit extension and gets its own special layout. The extra kit
  // types (danger/info/success/neutral/warn) have their own .callout.*
  // CSS + icon already; without this map they silently fell back to
  // 'note' (e.g. a [!DANGER] critical warning rendered neutral-indigo
  // instead of red).
  const ADM_CLASS = {
    note: 'note',
    tip: 'tip',
    important: 'important',
    warning: 'warning',
    caution: 'caution',
    danger: 'danger',
    info: 'info',
    success: 'success',
    neutral: 'neutral',
    warn: 'warn',
    tldr: 'tldr'
  };

  function renderAdmonition(node) {
    const type = ADM_CLASS[node.type] || 'note';
    if (type === 'tldr') {
      // TLDR keeps the legacy .tldr layout — h2 + summary + bullets.
      const section = document.createElement('section');
      section.id = 'tldr';
      const tldr = document.createElement('div');
      tldr.className = 'tldr';
      const lab = document.createElement('span');
      lab.className = 'tldr-label';
      lab.textContent = 'TL;DR';
      tldr.appendChild(lab);
      const h2 = document.createElement('h2');
      h2.textContent = node.title || 'TL;DR';
      tldr.appendChild(h2);
      // Body is a markdown sub-document — first paragraph becomes the
      // summary line; any list becomes the bullet block.
      const sub = parseMarkdown(node.body);
      let summarised = false;
      for (const s of sub) {
        if (s.k === 'paragraph' && !summarised) {
          const p = document.createElement('p');
          p.className = 'one-line';
          parseInline(s.text, p);
          tldr.appendChild(p);
          summarised = true;
        } else if (s.k === 'list') {
          tldr.appendChild(renderList(s));
        } else {
          emitMarkdown(tldr, [s], null);
        }
      }
      section.appendChild(tldr);
      return section;
    }
    const c = document.createElement('div');
    c.className = 'callout ' + type;
    c.setAttribute('data-callout-symbol', type);
    if (node.title) {
      const h = document.createElement('h4');
      h.textContent = node.title;
      c.appendChild(h);
    }
    const sub = parseMarkdown(node.body);
    emitMarkdown(c, sub, null);
    return c;
  }

  function renderList(node) {
    const tag = node.ordered ? 'ol' : 'ul';
    const list = document.createElement(tag);
    for (const item of node.items) {
      const li = document.createElement('li');
      // Item is an array of strings and {__nested: lines} objects.
      const text = [];
      const sub = [];
      for (const seg of item) {
        if (typeof seg === 'string') text.push(seg);
        else if (seg.__nested) sub.push(seg.__nested.join('\n'));
      }
      let itemText = text.join(' ').trim();
      // GFM task-list item: leading [ ] / [x] becomes a checkbox.
      const task = itemText.match(/^\[([ xX])\]\s+/);
      if (task) {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.disabled = true;
        cb.checked = task[1] !== ' ';
        li.className = 'task-item';
        li.appendChild(cb);
        li.appendChild(document.createTextNode(' '));
        itemText = itemText.slice(task[0].length);
      }
      parseInline(itemText, li);
      for (const ns of sub) {
        const parsed = parseMarkdown(ns);
        emitMarkdown(li, parsed, null);
      }
      list.appendChild(li);
    }
    return list;
  }

  function renderMarkdownTable(node) {
    const table = document.createElement('table');
    const thead = document.createElement('thead');
    const htr = document.createElement('tr');
    for (const h of node.headers) {
      const th = document.createElement('th');
      parseInline(h, th);
      htr.appendChild(th);
    }
    thead.appendChild(htr);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    for (const row of node.rows) {
      const tr = document.createElement('tr');
      for (const cell of row) {
        const td = document.createElement('td');
        parseInline(cell, td);
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    return table;
  }

  /* ================================================================ *
   * Public API
   * ================================================================ */

  class OkuRenderer {
    constructor(opts) {
      opts = opts || {};
      this.host = opts.host || null;
      this.lang = opts.lang || document.documentElement.lang || 'en';
      this.warnings = [];
    }

    async renderFromUrl(url, host) {
      let page;
      const wa = window.__okuWithAuth || ((u) => u);
      try {
        const res = await fetch(wa(url), { cache: 'no-cache' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        page = await res.json();
      } catch (e) {
        this._fail('page-fetch-failed', 'Could not load ' + url + ': ' + e.message);
        return;
      }
      this.render(page, host);
    }

    render(page, host) {
      this.host = host || this.host || document.querySelector('main#main-content') || document.querySelector('main') || document.body;
      this.warnings = [];
      __renderTypedBlock = (block) => this._renderTyped(block);

      // v1 → v2 shim. Older pages still on disk (or in other projects
      // sharing this kit) keep rendering — no migrate run required.
      if (page && page.kind === 'page' && !page.k) {
        page = convertV1ToV2(page);
      }

      if (!page || page.k !== 'page') {
        this._fail('schema-mismatch', 'Page root is not { k: "page" }', page);
        return;
      }

      const meta = page.m || {};
      if (page.t) document.title = page.t;
      if (meta.lang) {
        document.documentElement.lang = meta.lang;
        this.lang = meta.lang;
      }
      if (meta.accent) this._applyAccent(meta.accent);

      const main = this.host;
      main.innerHTML = '';
      main.appendChild(this._renderCover(page));

      let currentSection = null;
      const openSection = (heading) => {
        const section = document.createElement('section');
        if (heading.id) section.id = heading.id;
        const h2 = document.createElement('h2');
        h2.textContent = heading.title;
        section.appendChild(h2);
        main.appendChild(section);
        currentSection = section;
      };
      const target = () => currentSection || main;

      for (const block of (page.b || [])) {
        if (typeof block === 'string') {
          const parsed = parseMarkdown(block);
          // Walk node-by-node so h2 can open a section mid-string.
          let buffer = [];
          const flush = () => {
            if (buffer.length) {
              emitMarkdown(target(), buffer, null);
              buffer = [];
            }
          };
          for (const node of parsed) {
            if (node.k === 'heading' && node.level === 2) {
              flush();
              openSection(node);
            } else {
              buffer.push(node);
            }
          }
          flush();
        } else if (block && typeof block === 'object') {
          const el = this._renderTyped(block);
          if (el) target().appendChild(el);
        }
      }

      if (this.warnings.length) {
        window.dispatchEvent(new CustomEvent('oku:warnings', { detail: this.warnings }));
      }
      window.dispatchEvent(new CustomEvent('oku:rendered', { detail: { page: page } }));
    }

    /* -------------------------------------------------------------- *
     * Cover
     * -------------------------------------------------------------- */

    _renderCover(page) {
      const cover = document.createElement('header');
      cover.className = 'cover';
      const meta = page.m || {};
      if (meta.eyebrow) {
        const eb = document.createElement('div');
        eb.className = 'eyebrow';
        eb.textContent = meta.eyebrow;
        cover.appendChild(eb);
      }
      const h1 = document.createElement('h1');
      h1.textContent = page.t || '';
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
      if (meta.updated) {
        const u = document.createElement('div');
        u.className = 'meta meta-updated';
        u.textContent = 'Last updated ' + meta.updated;
        cover.appendChild(u);
      }
      return cover;
    }

    /* -------------------------------------------------------------- *
     * Typed primitives
     * -------------------------------------------------------------- */

    _renderTyped(block) {
      if (!block || !block.k) return this._unknown(block);
      let el;
      switch (block.k) {
        case 'diagram':        el = this._renderDiagram(block); break;
        case 'code':           el = this._renderCode(block); break;
        case 'annotated-code': el = this._renderAnnotatedCode(block); break;
        case 'live-snippet':   el = this._renderLiveSnippet(block); break;
        case 'table':          el = this._renderTable(block); break;
        case 'kpi-grid':       el = this._renderKpiGrid(block); break;
        case 'step-flow':      el = this._renderStepFlow(block); break;
        case 'compare-grid':   el = this._renderCompareGrid(block); break;
        case 'chart':          el = this._renderChart(block); break;
        case 'chart-grid':     el = this._renderChartGrid(block); break;
        case 'example':        el = this._renderExample(block); break;
        case 'insight':        el = this._renderInsight(block); break;
        case 'info-tip':       el = this._renderInfoTip(block); break;
        case 'image':          el = this._renderImage(block); break;
        case 'svg':            el = this._renderSvg(block); break;
        default:               el = this._unknown(block); break;
      }
      return el;
    }

    _renderInfoTip(block) {
      const det = document.createElement('details');
      det.className = 'info-tip';
      if (block.open) det.setAttribute('open', '');
      const sum = document.createElement('summary');
      parseInline(block.summary || '', sum);
      det.appendChild(sum);
      for (const sub of (block.content || [])) {
        const conv = convertV1Block(sub);
        if (conv == null) continue;
        if (typeof conv === 'string') {
          emitMarkdown(det, parseMarkdown(conv), null);
        } else {
          det.appendChild(this._renderTyped(conv));
        }
      }
      return det;
    }

    _renderImage(block) {
      const fig = document.createElement('figure');
      fig.className = 'okt-figure';
      const img = document.createElement('img');
      img.src = block.src || '';
      img.alt = block.alt || '';
      img.loading = 'lazy';
      if (block.width != null) {
        img.style.maxWidth = typeof block.width === 'number' ? block.width + 'px' : String(block.width);
      }
      fig.appendChild(img);
      if (block.caption) {
        const cap = document.createElement('figcaption');
        parseInline(block.caption, cap);
        fig.appendChild(cap);
      }
      return fig;
    }

    _renderSvg(block) {
      const fig = document.createElement('figure');
      fig.className = 'okt-figure okt-svg';
      const holder = document.createElement('div');
      holder.className = 'okt-svg-holder';
      if (block.label) {
        holder.setAttribute('role', 'img');
        holder.setAttribute('aria-label', block.label);
      }
      // Author-trusted inline SVG (same trust model as diagram / HTML
      // islands). Scripts stripped defensively — illustrations never need them.
      holder.innerHTML = String(block.src || '').replace(/<script[\s\S]*?<\/script\s*>/gi, '');
      fig.appendChild(holder);
      if (block.caption) {
        const cap = document.createElement('figcaption');
        parseInline(block.caption, cap);
        fig.appendChild(cap);
      }
      return fig;
    }

    _renderDiagram(block) {
      const el = document.createElement('oku-diagram');
      if (block.caption) el.setAttribute('caption', block.caption);
      const src = document.createElement('script');
      src.type = 'text/x-mermaid';
      src.textContent = block.src || '';
      el.appendChild(src);
      return el;
    }

    _renderCode(block) {
      const pre = document.createElement('pre');
      const code = document.createElement('code');
      if (block.lang) code.className = 'language-' + block.lang;
      code.textContent = block.src || '';
      pre.appendChild(code);
      return pre;
    }

    _renderAnnotatedCode(block) {
      const el = document.createElement('oku-annotated-code');
      if (block.lang) el.setAttribute('language', block.lang);
      const src = document.createElement('script');
      src.setAttribute('type', 'text/x-code');
      src.textContent = block.src || '';
      el.appendChild(src);
      if (Array.isArray(block.annotations) && block.annotations.length) {
        const data = document.createElement('script');
        data.setAttribute('type', 'application/json');
        data.textContent = JSON.stringify(block.annotations);
        el.appendChild(data);
      }
      return el;
    }

    _renderLiveSnippet(block) {
      const el = document.createElement('oku-snippet');
      if (block.label) el.setAttribute('label', block.label);
      el.setAttribute('language', block.lang || 'html-css-js');
      const src = document.createElement('script');
      src.type = 'text/plain';
      src.textContent = block.src || '';
      el.appendChild(src);
      return el;
    }

    _renderKpiGrid(block) {
      // Optional per-tile icon turns a wall of numbers into a scannable
      // spec sheet — the eye jumps straight to the right metric instead of
      // reading every label. Curated semantic set (24x24, stroke); an
      // unknown or absent name simply renders no icon (back-compatible).
      const ICONS = {
        weight: '<path d="M8 8a4 4 0 0 1 8 0"/><path d="M5 8h14l-1.3 11.1a1 1 0 0 1-1 .9H7.3a1 1 0 0 1-1-.9z"/>',
        wind: '<path d="M3 8h10a2.5 2.5 0 1 0-2.5-2.5"/><path d="M3 12h15a2.5 2.5 0 1 1-2.5 2.5"/><path d="M3 16h7a2 2 0 1 1-2 2"/>',
        range: '<path d="M4.5 9a8 8 0 0 1 15 0"/><path d="M7.5 11a4.5 4.5 0 0 1 9 0"/><circle cx="12" cy="13" r="1.6" fill="currentColor" stroke="none"/><path d="M12 14.5V20"/>',
        globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3.5 2"/>',
        light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
        camera: '<circle cx="12" cy="12" r="9"/><path d="M14.3 9.6 21 9"/><path d="M16.3 14.4 19.5 18"/><path d="M9.7 14.4 6.5 21"/><path d="M9.7 9.6 3 9"/><path d="M14.3 9.6 7.7 14.4"/>',
        resolution: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
        sensor: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
        film: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
        iso: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4.5-5"/><circle cx="12" cy="18" r="1.6" fill="currentColor" stroke="none"/>',
        contrast: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none"/>',
        data: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
        battery: '<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 10.5v3"/><path d="M5.5 10.5v3M9 10.5v3M12.5 10.5v3"/>',
        audio: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a3 3 0 0 1 0 6"/><path d="M18.5 7a6 6 0 0 1 0 10"/>',
        list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 5.2 5.2 6.4 7.4 4.2M4 11.2l1.2 1.2L7.4 10.2M4 17.2l1.2 1.2L7.4 16.2"/>',
        chart: '<path d="M3 21h18"/><path d="M6 21V11M11 21V5M16 21v-7"/>',
        users: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 5.5a3.2 3.2 0 0 1 0 6M17.5 20a5.5 5.5 0 0 0-3-4.9"/>',
        percent: '<path d="M19 5 5 19"/><circle cx="7.5" cy="7.5" r="2.3"/><circle cx="16.5" cy="16.5" r="2.3"/>',
        eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
        file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
      };
      const grid = document.createElement('div');
      grid.className = 'kpi-grid';
      for (const tile of (block.tiles || [])) {
        const k = document.createElement('div');
        k.className = 'kpi';
        const inner = tile.icon && ICONS[tile.icon];
        if (inner) {
          const ico = document.createElement('div');
          ico.className = 'kpi-icon';
          ico.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + inner + '</svg>';
          k.appendChild(ico);
        }
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

    _renderStepFlow(block) {
      const wrap = document.createElement('div');
      // ordered (default): numbered single-column flow. ordered:false: an
      // unordered 2-up grid of link cards (navigation / parallel options)
      // with no step numerals — a numeral here reads as a sequence the
      // items don't have.
      const ordered = block.ordered !== false;
      wrap.className = 'step-cards' + (ordered ? '' : ' step-cards-grid');
      (block.steps || []).forEach((s, i) => {
        const card = document.createElement(s.href ? 'a' : 'div');
        card.className = 'step-card' + (s.href ? ' step-card-link' : '');
        if (s.href) {
          card.setAttribute('href', s.href);
          if (/^https?:/i.test(s.href)) {
            card.setAttribute('target', '_blank');
            card.setAttribute('rel', 'noopener');
          }
        }
        if (ordered) {
          const num = document.createElement('span');
          num.className = 'step-num';
          num.textContent = String(i + 1);
          card.appendChild(num);
        }
        const body = document.createElement('div');
        const h = document.createElement('h4');
        h.textContent = s.t || '';
        body.appendChild(h);
        if (s.meta) {
          const m = document.createElement('div');
          m.className = 'step-meta';
          m.textContent = s.meta;
          body.appendChild(m);
        }
        if (s.b !== undefined && s.b !== '') {
          const sub = parseMarkdown(s.b);
          emitMarkdown(body, sub, null);
        }
        card.appendChild(body);
        wrap.appendChild(card);
      });
      return wrap;
    }

    _renderCompareGrid(block) {
      // Verdict icon makes each card scannable at a glance (traffic-light
      // read) instead of a uniform pile of text. good/bad get check/cross,
      // warn/caution an alert triangle; neutral gets a quiet judgment-free
      // ring (used for informational peer cards like "ISO" / "GNSS" where a
      // warning glyph would be a false alarm). Coloured by verdict in CSS.
      const ICONS = {
        good: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
        bad: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
        warn: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
        accent: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
        neutral: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>'
      };
      const iconFor = (k) => {
        if (k === 'good' || k === 'success' || k === 'in') return ICONS.good;
        if (k === 'bad' || k === 'danger' || k === 'fail') return ICONS.bad;
        if (k === 'warn' || k === 'caution' || k === 'warning') return ICONS.warn;
        if (k === 'accent' || k === 'note' || k === 'info' || k === 'tip') return ICONS.accent;
        return ICONS.neutral;
      };
      const grid = document.createElement('div');
      grid.className = 'compare-grid';
      for (const c of (block.cards || [])) {
        const card = document.createElement(c.href ? 'a' : 'div');
        const styleKey = c.accent || c.verdict || 'neutral';
        card.className = 'compare-card ' + styleKey + (c.href ? ' compare-card-link' : '');
        if (c.href) card.setAttribute('href', c.href);
        if (c.t) {
          const head = document.createElement('div');
          head.className = 'compare-card-head';
          const ico = document.createElement('span');
          ico.className = 'compare-card-icon';
          ico.innerHTML = iconFor(styleKey);
          const h = document.createElement('h4');
          h.textContent = c.t;
          head.appendChild(ico);
          head.appendChild(h);
          card.appendChild(head);
        }
        if (c.b) {
          const sub = parseMarkdown(c.b);
          emitMarkdown(card, sub, null);
        }
        grid.appendChild(card);
      }
      return grid;
    }

    _renderInsight(block) {
      const ins = document.createElement('aside');
      ins.className = 'insight';
      if (block.b) {
        const sub = parseMarkdown(block.b);
        emitMarkdown(ins, sub, null);
      }
      return ins;
    }

    _renderExample(block) {
      const wrap = document.createElement('div');
      wrap.className = 'example-pair';
      if (block.t) {
        const t = document.createElement('div');
        t.className = 'example-title';
        t.textContent = block.t;
        wrap.appendChild(t);
      }
      const codeCol = document.createElement('div');
      codeCol.className = 'example-code';
      const codeLbl = document.createElement('div');
      codeLbl.className = 'example-col-label';
      codeLbl.textContent = 'Code';
      codeCol.appendChild(codeLbl);
      if (block.code) codeCol.appendChild(this._renderCode(block.code));
      const outputCol = document.createElement('div');
      outputCol.className = 'example-output';
      const outputLbl = document.createElement('div');
      outputLbl.className = 'example-col-label';
      outputLbl.textContent = 'Output';
      outputCol.appendChild(outputLbl);
      if (typeof block.output === 'string') {
        const sub = parseMarkdown(block.output);
        emitMarkdown(outputCol, sub, null);
      } else if (block.output) {
        const outputEl = this._renderTyped(block.output);
        if (outputEl) outputCol.appendChild(outputEl);
      }
      wrap.appendChild(codeCol);
      wrap.appendChild(outputCol);
      return wrap;
    }

    /* -------------------------------------------------------------- *
     * Table (typed, sortable/filterable form)
     * -------------------------------------------------------------- */

    _renderTable(block) {
      const table = document.createElement('table');
      if (block.view) table.setAttribute('data-default-view', block.view);
      const headers = block.headers || [];
      const wrapColumn = headers.map(h =>
        h && typeof h === 'object' && !Array.isArray(h) && h.wrap === true
      );
      // Per-column value→verdict map. A matching cell renders as a coloured
      // status pill; its td.textContent stays the bare value so sort /
      // filter / group / board all read it unchanged.
      const statusColumn = headers.map(h =>
        (h && typeof h === 'object' && !Array.isArray(h) && h.status && typeof h.status === 'object')
          ? h.status : null
      );
      const STATUS_VERDICT = {
        good: 'good', success: 'good', ok: 'good', pass: 'good',
        warn: 'warn', warning: 'warn', caution: 'warn',
        bad: 'bad', danger: 'bad', fail: 'bad', error: 'bad',
        info: 'info', accent: 'info', tip: 'info',
        neutral: 'neutral',
      };
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
            if (h.wrap === true) th.setAttribute('data-wrap', '1');
            parseInline(h.label || '', th);
          } else {
            parseInline(h || '', th);
          }
          tr.appendChild(th);
        }
        thead.appendChild(tr);
        table.appendChild(thead);
      }
      const tbody = document.createElement('tbody');
      const cellCount = headers.length || 1;

      const renderCell = (cell, colIdx) => {
        const td = document.createElement('td');
        if (wrapColumn[colIdx]) td.setAttribute('data-wrap', '1');
        const statusMap = statusColumn[colIdx];
        if (cell && typeof cell === 'object' && !Array.isArray(cell) && Array.isArray(cell.values)) {
          td.setAttribute('data-values', cell.values.join('|'));
          parseInline(cell.value != null ? cell.value : cell.values.join(', '), td);
        } else if (statusMap && typeof cell === 'string' &&
                   Object.prototype.hasOwnProperty.call(statusMap, cell.trim())) {
          const verdict = STATUS_VERDICT[String(statusMap[cell.trim()]).toLowerCase()] || 'neutral';
          const chip = document.createElement('span');
          chip.className = 'okt-status okt-status-' + verdict;
          chip.textContent = cell;          // textContent === value: sort/filter unaffected
          td.appendChild(chip);
        } else {
          parseInline(typeof cell === 'string' ? cell : '', td);
        }
        return td;
      };

      const renderRow = (row) => {
        const tr = document.createElement('tr');
        if (row && typeof row === 'object' && !Array.isArray(row) && row.href) {
          tr.setAttribute('data-href', row.href);
          tr.style.cursor = 'pointer';
          tr.addEventListener('click', () => { window.location.href = row.href; });
        }
        const cells = (row && row.cells) || row;
        for (let ci = 0; ci < cells.length; ci++) {
          tr.appendChild(renderCell(cells[ci], ci));
        }
        tbody.appendChild(tr);
      };

      const renderGroupHeader = (title) => {
        const tr = document.createElement('tr');
        tr.className = 'group';
        const th = document.createElement('th');
        th.colSpan = cellCount;
        parseInline(title || '', th);
        tr.appendChild(th);
        tbody.appendChild(tr);
      };

      if (Array.isArray(block.groups) && block.groups.length) {
        for (const g of block.groups) {
          if (g.t) renderGroupHeader(g.t);
          for (const row of (g.rows || [])) renderRow(row);
        }
      } else {
        for (const row of (block.rows || [])) renderRow(row);
      }
      table.appendChild(tbody);
      return table;
    }

    /* -------------------------------------------------------------- *
     * Chart family — unchanged dispatch, key renames only
     * -------------------------------------------------------------- */

    _normaliseChartData(block) {
      if (!block || !Array.isArray(block.data) || !block.data.length) return block;
      const enc = block.encoding || {};
      const xField     = enc.x     || 'x';
      const yField     = enc.y     || 'y';
      const colorField = enc.color || null;
      const sizeField  = enc.size  || null;
      const labelField = enc.label || null;
      const cartesian = /^(plot|scatter|line|area|bubble|quadrant)$/i.test(String(block.type || ''));
      if (!cartesian) return block;
      const series = new Map();
      const seriesPalette = ['accent', 'success', 'warn', 'danger', 'muted'];
      block.data.forEach((rec) => {
        const seriesKey = colorField ? String(rec[colorField] ?? '') : '__default';
        if (!series.has(seriesKey)) {
          const idx = series.size;
          series.set(seriesKey, {
            label: colorField ? seriesKey : (block.title || ''),
            color: seriesPalette[idx % seriesPalette.length],
            data: []
          });
        }
        const point = { x: +rec[xField], y: +rec[yField] };
        if (sizeField  && rec[sizeField]  != null) point.size  = +rec[sizeField];
        if (labelField && rec[labelField] != null) point.label = String(rec[labelField]);
        series.get(seriesKey).data.push(point);
      });
      const out = Object.assign({}, block);
      out.series = Array.from(series.values());
      delete out.data;
      delete out.encoding;
      return out;
    }

    _normaliseChartType(block) {
      block = this._normaliseChartData(block);
      const out = Object.assign({}, block || {});
      const t = String(out.type || 'scatter').toLowerCase();
      if (t === 'plot') {
        const marks = Array.isArray(out.marks) && out.marks.length ? out.marks : ['dots'];
        out.marks = marks;
        if (marks.includes('area'))      out.type = 'area';
        else if (marks.includes('line')) out.type = 'line';
        else                              out.type = 'scatter';
      } else if (t === 'arc') {
        const mode = out.mode || 'donut';
        out.mode = mode;
        out.type = mode === 'pie' ? 'pie' : 'donut';
      } else if (t === 'bar') {
        const mode = out.mode || 'single';
        out.mode = mode;
        if (mode === 'stacked') out.type = 'stacked-bar';
        else if (mode === 'grouped') out.type = 'grouped-bar';
        else out.type = 'bar';
      } else {
        if (t === 'scatter') out.marks = Array.isArray(out.marks) ? out.marks : ['dots'];
        else if (t === 'line') out.marks = Array.isArray(out.marks) ? out.marks : ['line'];
        else if (t === 'area') out.marks = Array.isArray(out.marks) ? out.marks : ['line', 'area'];
        else if (t === 'pie') out.mode = out.mode || 'pie';
        else if (t === 'donut') out.mode = out.mode || 'donut';
        else if (t === 'stacked-bar') out.mode = out.mode || 'stacked';
        else if (t === 'grouped-bar') out.mode = out.mode || 'grouped';
      }
      return out;
    }

    _renderChart(block) {
      block = this._normaliseChartType(block);
      const type = block.type || 'scatter';
      if (type === 'bar') return this._renderBars(block);
      if (type === 'stacked-bar' || type === 'grouped-bar') {
        return this._renderMultiBars(block, type);
      }
      const el = document.createElement('oku-chart');
      el.setAttribute('type', type);
      if (Array.isArray(block.marks)) el.setAttribute('marks', block.marks.join(','));
      if (block.mode) el.setAttribute('mode', String(block.mode));
      if (block.arc && (block.arc.start !== undefined || block.arc.end !== undefined)) {
        const s = block.arc.start !== undefined ? block.arc.start : 0;
        const e = block.arc.end   !== undefined ? block.arc.end   : 360;
        el.setAttribute('arc-start', String(s));
        el.setAttribute('arc-end',   String(e));
      }
      if (block.inner_radius !== undefined) el.setAttribute('inner-radius', String(block.inner_radius));
      if (block.title) el.setAttribute('title', block.title);
      if (block.x_label) el.setAttribute('x-label', block.x_label);
      if (block.y_label) el.setAttribute('y-label', block.y_label);
      if (block.curve) el.setAttribute('curve', String(block.curve));
      const data = document.createElement('script');
      data.type = 'application/json';
      data.textContent = JSON.stringify(block.series || []);
      el.appendChild(data);
      if (type === 'quadrant' && block.quadrants) {
        const q = document.createElement('script');
        q.type = 'application/json';
        q.setAttribute('data-extras', 'quadrants');
        q.textContent = JSON.stringify(block.quadrants);
        el.appendChild(q);
      }
      if ((type === 'donut' || type === 'pie') && Array.isArray(block.slices)) {
        const d = document.createElement('script');
        d.type = 'application/json';
        d.setAttribute('data-extras', 'slices');
        d.textContent = JSON.stringify(block.slices);
        el.appendChild(d);
      }
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
        funnel: { stages: block.stages },
        sankey: { nodes: block.nodes, links: block.links },
        network: { nodes: block.nodes, links: block.links },
        'scatter-matrix': { variables: block.variables, records: block.records },
        'parallel-coordinates': { variables: block.variables, records: block.records },
        chord: { groups: block.groups, matrix: block.matrix },
        geo: { regions: block.regions },
        'dot-plot':   { rows: block.rows, min: block.min, max: block.max },
        density:      { values: block.values, min: block.min, max: block.max, bandwidth: block.bandwidth, sample_count: block.sample_count, color: block.color },
        candlestick:  { entries: block.entries },
        sunburst:     { tree: block.tree },
        marimekko:    { categories: block.categories, series: block.series },
        stream:       { categories: block.categories, series: block.series },
        violin:       { distributions: block.distributions },
        beeswarm:     { values: block.values, min: block.min, max: block.max, color: block.color, dot_radius: block.dot_radius },
        waterfall:    { steps: block.steps },
        lollipop:     { rows: block.rows, min: block.min, max: block.max },
        dumbbell:     { rows: block.rows, from_label: block.from_label, to_label: block.to_label, from_color: block.from_color, to_color: block.to_color },
        'polar-area': { sectors: block.sectors },
        gantt:        { tasks: block.tasks, tick_format: block.tick_format },
        bump:         { categories: block.categories, series: block.series },
        'population-pyramid': { categories: block.categories, left: block.left, right: block.right },
        'tile-map':   { regions: block.regions },
        horizon:      { categories: block.categories, series: block.series, bands: block.bands },
        hexbin:       { points: block.points, radius: block.radius, scale: block.scale },
        'arc-diagram': { nodes: block.nodes, links: block.links },
        'range-bar':  { ranges: block.ranges },
        pareto:       { rows: block.rows }
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
      const categories = block.categories || [];
      const series = block.series || [];
      const wrap = document.createElement('div');
      wrap.className = 'bar-chart bar-chart-multi bar-chart-' + mode + (block.orientation === 'vertical' ? ' bar-chart-vertical' : '');
      wrap.setAttribute('role', 'img');
      wrap.setAttribute('aria-label', (block.title ? block.title + ' — ' : '') + mode + ' with ' + categories.length + ' categories');
      if (block.title) {
        const h = document.createElement('h4');
        h.className = 'bar-chart-title';
        h.textContent = block.title;
        wrap.appendChild(h);
      }
      const TOKEN_COLORS = ['accent', 'warn', 'danger', 'success', 'muted'];
      function resolveSeriesColor(s, idx) {
        if (s && TOKEN_COLORS.indexOf(s.color) >= 0) return { className: s.color, inlineBackground: null };
        if (s && s.color) return { className: '', inlineBackground: s.color };
        const slot = (idx % 10) + 1;
        return { className: '', inlineBackground: 'var(--series-' + slot + ')' };
      }
      if (series.some(s => s.label)) {
        const legend = document.createElement('div');
        legend.className = 'bar-chart-legend';
        series.forEach((s, si) => {
          if (!s.label) return;
          const colorInfo = resolveSeriesColor(s, si);
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'bar-chart-legend-chip ' + (colorInfo.className || '');
          chip.setAttribute('data-series-idx', String(si));
          chip.setAttribute('aria-pressed', 'false');
          chip.setAttribute('aria-label', 'Toggle ' + s.label + ' series');
          const sw = document.createElement('span');
          sw.className = 'bar-chart-legend-swatch';
          if (colorInfo.inlineBackground) sw.style.background = colorInfo.inlineBackground;
          chip.appendChild(sw);
          chip.appendChild(document.createTextNode(s.label));
          legend.appendChild(chip);
        });
        wrap.appendChild(legend);
      }
      let scaleMax;
      if (block.max !== undefined) scaleMax = block.max;
      else if (mode === 'stacked-bar') {
        scaleMax = 0;
        for (let ci = 0; ci < categories.length; ci++) {
          let sum = 0;
          for (const s of series) sum += (s.values && s.values[ci]) || 0;
          if (sum > scaleMax) scaleMax = sum;
        }
      } else {
        scaleMax = 1;
        for (const s of series) for (const v of (s.values || [])) if (v > scaleMax) scaleMax = v;
      }
      if (scaleMax <= 0) scaleMax = 1;
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
          const colorInfo = resolveSeriesColor(s, si);
          const fill = document.createElement('div');
          fill.className = 'bar-fill ' + (colorInfo.className || '');
          if (colorInfo.inlineBackground) fill.style.background = colorInfo.inlineBackground;
          fill.setAttribute('data-series', String(si));
          const pct = Math.max(0, Math.min(100, (v / scaleMax) * 100));
          fill.style.setProperty('--bar-pct', String(pct));
          fill.style.width = pct + '%';
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

    _renderBars(block) {
      const rows = block.rows || [];
      const max = block.max !== undefined ? block.max : Math.max.apply(null, rows.map(r => r.value || 0).concat([1]));
      const wrap = document.createElement('div');
      wrap.className = 'bar-chart' + (block.orientation === 'vertical' ? ' bar-chart-vertical' : '');
      wrap.setAttribute('role', 'img');
      wrap.setAttribute('aria-label', (block.title ? block.title + ' — ' : '') + 'Bar chart with ' + rows.length + ' rows');
      if (block.title) {
        const h = document.createElement('h4');
        h.className = 'bar-chart-title';
        h.textContent = block.title;
        wrap.appendChild(h);
      }
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
        fill.style.setProperty('--bar-pct', String(pct));
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

    _renderChartGrid(block) {
      const wrap = document.createElement('div');
      wrap.className = 'okt-chart-grid';
      if (block.title) {
        const h = document.createElement('h4');
        h.className = 'okt-chart-grid-title';
        h.textContent = block.title;
        wrap.appendChild(h);
      }
      const grid = document.createElement('div');
      grid.className = 'okt-chart-grid-cells';
      const cols = +block.cols;
      if (cols && cols > 0) {
        grid.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
      } else {
        grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(220px, 1fr))';
      }
      const childType = block.child_type || 'sparkline';
      (block.panels || []).forEach((panel) => {
        if (!panel || typeof panel !== 'object') return;
        const childBlock = Object.assign({ k: 'chart', type: childType, title: panel.label || '' }, panel);
        delete childBlock.label;
        const cell = document.createElement('div');
        cell.className = 'okt-chart-grid-cell';
        const chartEl = this._renderChart(childBlock);
        if (chartEl) cell.appendChild(chartEl);
        grid.appendChild(cell);
      });
      wrap.appendChild(grid);
      return wrap;
    }

    /* -------------------------------------------------------------- *
     * Accent + helpers
     * -------------------------------------------------------------- */

    _applyAccent(accent) {
      const palettes = {
        teal:   { light: '#0f766e', soft: '#ccfbf1', strong: '#115e59', dark: '#2dd4bf', darkSoft: '#042f2e', darkStrong: '#5eead4' },
        amber:  { light: '#b45309', soft: '#fef3c7', strong: '#b45309', dark: '#fbbf24', darkSoft: '#422006', darkStrong: '#fcd34d' },
        indigo: { light: '#4338ca', soft: '#e0e7ff', strong: '#3730a3', dark: '#a5b4fc', darkSoft: '#1e1b4b', darkStrong: '#c7d2fe' }
      };
      const p = palettes[accent];
      let style = document.getElementById('oku-accent');
      if (!style) {
        style = document.createElement('style');
        style.id = 'oku-accent';
        document.head.appendChild(style);
      }
      if (p) {
        style.textContent =
          ':root { --accent: ' + p.light + '; --accent-soft: ' + p.soft + '; --accent-strong: ' + p.strong + '; }' +
          ':root[data-theme="dark"] { --accent: ' + p.dark + '; --accent-soft: ' + p.darkSoft + '; --accent-strong: ' + p.darkStrong + '; }';
      } else {
        style.textContent = ':root { --accent: ' + accent + '; }';
      }
    }

    _unknown(block) {
      this._warn('unknown-block', 'Unknown block.k: ' + (block && block.k), block);
      return null;
    }

    _warn(code, msg, payload) {
      this.warnings.push({ code: code, msg: msg, payload: payload, level: 'warn' });
      console.warn('[oku] ' + code + ': ' + msg, payload);
    }

    _fail(code, msg, payload) {
      this.warnings.push({ code: code, msg: msg, payload: payload, level: 'error' });
      console.error('[oku] ' + code + ': ' + msg, payload);
    }
  }

  /* ================================================================ *
   * Auto-boot
   * ================================================================ */

  OkuRenderer.autoBoot = function (opts) {
    if (OkuRenderer._autoBootRan) return OkuRenderer._autoBootRan;
    const inline = document.getElementById('__oku_page__');
    let result;
    // render() returns nothing, so its return value can't tell us whether
    // the inline path ran — a standalone build would fall through and also
    // fetch <page>.json, which isn't there. Track the outcome explicitly.
    let renderedInline = false;
    if (inline) {
      try {
        const data = JSON.parse(inline.textContent);
        result = new OkuRenderer(opts || {}).render(data);
        renderedInline = true;
      } catch (e) {
        console.error('[oku] inline page parse failed', e);
      }
    }
    if (!renderedInline) {
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
      window.__okuCurrentPage = pagePath;
      result = new OkuRenderer(opts || {}).renderFromUrl(jsonName);
      const trailingAnchor = sep >= 0 ? rawHash.slice(sep + 1) : '';
      if (trailingAnchor && result && typeof result.then === 'function') {
        result.then(function () {
          requestAnimationFrame(function () {
            const el = document.getElementById(trailingAnchor) || document.querySelector('[id="' + trailingAnchor + '"]');
            if (el) el.scrollIntoView();
          });
        });
      }
    }
    // The inline path has no promise to hand back; store a truthy marker so
    // the once-only guard at the top still holds on a second call.
    OkuRenderer._autoBootRan = result === undefined ? true : result;
    return result;
  };

  window.OkuRenderer = OkuRenderer;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { OkuRenderer.autoBoot(); });
  } else {
    OkuRenderer.autoBoot();
  }
})();
