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

  // Named character references worth decoding. GFM decodes the full HTML5
  // set; a fixed map covers what documentation actually uses and cannot be
  // tricked into parsing markup the way an innerHTML round-trip can.
  const ENTITIES = {
    amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ',
    ndash: '–', mdash: '—', hellip: '…', laquo: '«',
    raquo: '»', ldquo: '“', rdquo: '”', lsquo: '‘',
    rsquo: '’', bull: '•', middot: '·', deg: '°',
    plusmn: '±', times: '×', divide: '÷', minus: '−',
    copy: '©', reg: '®', trade: '™', para: '¶',
    sect: '§', dagger: '†', permil: '‰', euro: '€',
    pound: '£', yen: '¥', cent: '¢', larr: '←',
    rarr: '→', uarr: '↑', darr: '↓', harr: '↔',
    lArr: '⇐', rArr: '⇒', hArr: '⇔', ne: '≠',
    le: '≤', ge: '≥', asymp: '≈', infin: '∞',
    sum: '∑', prod: '∏', radic: '√', check: '✓',
    cross: '✗', star: '★', hearts: '♥', ensp: ' ',
    emsp: ' ', thinsp: ' ', shy: '­', alpha: 'α',
    beta: 'β', gamma: 'γ', delta: 'δ', lambda: 'λ',
    mu: 'μ', pi: 'π', sigma: 'σ', tau: 'τ',
    phi: 'φ', omega: 'ω', Delta: 'Δ', Omega: 'Ω',
    Sigma: 'Σ'
  };
  const ENTITY_RE = /&(#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[a-zA-Z][a-zA-Z0-9]{1,31});/g;

  function decodeEntities(s) {
    if (s.indexOf('&') < 0) return s;
    return s.replace(ENTITY_RE, function (whole, body) {
      if (body.charAt(0) === '#') {
        const cp = body.charAt(1) === 'x' || body.charAt(1) === 'X'
          ? parseInt(body.slice(2), 16)
          : parseInt(body.slice(1), 10);
        if (!isFinite(cp) || cp <= 0 || cp > 0x10ffff) return whole;
        try { return String.fromCodePoint(cp); } catch (e) { return whole; }
      }
      return Object.prototype.hasOwnProperty.call(ENTITIES, body) ? ENTITIES[body] : whole;
    });
  }

  // A destination is safe when it cannot execute script on activation.
  // Returns the original href, or null when the URL must not be used —
  // callers then fall back to plain text (links) or to the alt text
  // (images). data: is allowed for images only, and only image/*.
  function safeUrl(href, forImage) {
    const probe = String(href).replace(/[\u0000-\u0020]/g, '').toLowerCase();
    if (/^(javascript|vbscript|file):/.test(probe)) return null;
    if (probe.indexOf('data:') === 0 && !(forImage && probe.indexOf('data:image/') === 0)) return null;
    return href;
  }

  function textNode(s) {
    return document.createTextNode(decodeEntities(s));
  }

  /* Sums of decimal values carry binary float error: 26.9 + 10.4 + 9.2 +
     9.0 + 6.6 + 0.2 prints as 62.300000000000004, and a page that shows
     that has told the reader its arithmetic cannot be trusted — in a
     tooltip, right next to the number the reader came for. Rounding at
     the sixth decimal removes the error without inventing precision: any
     value an author actually wrote survives it unchanged. */
  function numText(n) {
    const v = typeof n === 'number' ? n : parseFloat(n);
    if (!isFinite(v)) return String(n);
    return String(parseFloat(v.toFixed(6)));
  }

  /* ================================================================ *
   * Link-reference definitions and footnotes
   * Both are page-scoped, not string-scoped: md_to_v2_page splits a
   * page into several b[] strings at every typed fence, so a definition
   * can easily land in a different string than its reference. render()
   * collects them across the whole page before emitting anything.
   * ================================================================ */

  const LINK_DEF_RE = /^ {0,3}\[([^\]^][^\]]*)\]:\s*(\S+)(?:\s+"([^"]*)")?\s*$/;
  const FOOTNOTE_DEF_RE = /^ {0,3}\[\^([^\]]+)\]:\s*(.*)$/;

  let __linkDefs = new Map();
  let __footnoteDefs = new Map();
  let __footnoteUses = [];

  function resetDefinitions() {
    __linkDefs = new Map();
    __footnoteDefs = new Map();
    __footnoteUses = [];
  }

  // Pull definition lines out of one markdown string and return what is
  // left. A footnote body continues onto following indented lines.
  function extractDefinitions(src) {
    const lines = String(src || '').split('\n');
    const kept = [];
    let inFence = null;
    for (let i = 0; i < lines.length; i++) {
      const fence = lines[i].match(/^(`{3,}|~{3,})/);
      if (fence) {
        if (inFence && lines[i].charAt(0) === inFence.charAt(0) && fence[1].length >= inFence.length) inFence = null;
        else if (!inFence) inFence = fence[1];
        kept.push(lines[i]);
        continue;
      }
      if (inFence) { kept.push(lines[i]); continue; }
      const fn = lines[i].match(FOOTNOTE_DEF_RE);
      if (fn) {
        const body = [fn[2]];
        while (i + 1 < lines.length && /^\s{2,}\S/.test(lines[i + 1])) {
          body.push(lines[i + 1].trim());
          i++;
        }
        __footnoteDefs.set(fn[1], body.join('\n').trim());
        continue;
      }
      const ld = lines[i].match(LINK_DEF_RE);
      if (ld) {
        __linkDefs.set(ld[1].toLowerCase(), { href: ld[2], title: ld[3] || '' });
        continue;
      }
      kept.push(lines[i]);
    }
    return kept.join('\n');
  }

  // Reference number for a footnote id, assigned in order of first use.
  function footnoteNumber(id) {
    const at = __footnoteUses.indexOf(id);
    if (at >= 0) return at + 1;
    __footnoteUses.push(id);
    return __footnoteUses.length;
  }

  function renderFootnoteRef(id) {
    if (!__footnoteDefs.has(id)) return null;
    const n = footnoteNumber(id);
    const sup = document.createElement('sup');
    sup.className = 'okt-fn-ref';
    sup.id = uniqueAnchorId('fnref-' + n);
    const a = document.createElement('a');
    a.setAttribute('href', '#fn-' + n);
    a.textContent = String(n);
    sup.appendChild(a);
    return sup;
  }

  // The "Footnotes" block, emitted once at the end of a page that used
  // at least one. Only referenced notes appear, in reference order.
  function renderFootnoteSection() {
    if (!__footnoteUses.length) return null;
    const section = document.createElement('section');
    section.id = uniqueAnchorId('footnotes');
    section.className = 'okt-footnotes';
    const h2 = document.createElement('h2');
    h2.setAttribute('data-oku-t', 'Footnotes');
    h2.textContent = (typeof okuT === 'function') ? okuT('Footnotes') : 'Footnotes';
    section.appendChild(h2);
    const ol = document.createElement('ol');
    __footnoteUses.forEach(function (id, idx) {
      const li = document.createElement('li');
      li.id = 'fn-' + (idx + 1);
      const blocks = parseMarkdown(__footnoteDefs.get(id) || '', { noIslands: true });
      if (blocks.length === 1 && blocks[0].k === 'paragraph') parseInline(blocks[0].text, li);
      else emitMarkdown(li, blocks, null);
      const back = document.createElement('a');
      back.className = 'okt-fn-back';
      back.setAttribute('href', '#fnref-' + (idx + 1));
      back.setAttribute('aria-label', 'Back to reference');
      back.textContent = '↩';
      li.appendChild(document.createTextNode(' '));
      li.appendChild(back);
      ol.appendChild(li);
    });
    section.appendChild(ol);
    return section;
  }

  function parseInline(text, host) {
    // One regex pass so positions are tracked; alternation order IS the
    // precedence. Escape first (it must win over every construct it
    // protects), then code (literal body — the rule that protects it),
    // then image / emphasis / strike / link / autolink, and finally the
    // allow-listed inline HTML tags. Inline tags outside the allow-list
    // stay literal text.
    //
    // Emphasis and link bodies are parsed RECURSIVELY, so `**[a](b)**`,
    // `[**a**](b)`, `**`code`**` and `**bold with *em* inside**` all
    // compose. Strong therefore admits `*`/`_` in its body; em still
    // refuses them, which is what stops `*a **b** c*` from crossing.
    //
    // Link destinations forbid whitespace, as GFM does — EXCEPT the kit's
    // own `#g/` / `#x/` prefixes, whose ids are human-readable registry
    // keys with spaces in them ("Iceberg paper", "Time travel"). That
    // branch is tried first; everything else keeps the strict form.
    //
    // Groups: 1 escape · 2,3 code (fence run + body) · 4,5 image ·
    // 6,7 strong · 8 strike · 9,10 em · 11,12,13 link · 14 autolink ·
    // 15,16,17 inline HTML · 18 footnote ref · 19,20 reference link ·
    // 21 shortcut reference. A code span opens with N backticks and
    // closes on the next run of exactly N — the CommonMark rule that
    // lets ``a `b` c`` hold a backtick.
    // The three reference forms sit last: they are the loosest patterns
    // and only fire when the page actually defines that label.
    const re = /\\([\\`*_{}[\]()#+\-.!|~<>&"'])|(`+)([\s\S]+?)\2(?!`)|!\[([^\]]*?)\]\((#[gx]\/[^)\n]+?|[^)\s]+?)\)|\*\*([\s\S]+?)\*\*|__([\s\S]+?)__|~~([\s\S]+?)~~|\*([^*\s][^*]*?)\*|_([^_\s][^_]*?)_|\[([^\]]+?)\]\((#[gx]\/[^)\n]+?|[^)\s]+?)(?:\s+"([^"]*)")?\)|<((?:https?|mailto):[^>\s]+)>|<(kbd|sub|sup|mark|abbr|del|ins|samp|span)(\s+[^<>]*)?>([\s\S]*?)<\/\15\s*>|<br\s*\/?>|\[\^([^\]]+?)\]|\[([^\]]+?)\]\[([^\]]*?)\]|\[([^\]^][^\]]*?)\]/g;
    let pos = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      // `_` never opens or closes emphasis inside a word — snake_case_name
      // and a__b are identifiers, not markup (CommonMark's intraword rule).
      // Rejecting has to leave the run unconsumed: keep `pos` where it is
      // and restart one character in, so the text still lands verbatim.
      if ((m[7] !== undefined || m[10] !== undefined) && !underscoreRunIsFree(text, m.index, m[0].length)) {
        re.lastIndex = m.index + 1;
        continue;
      }
      // A reference form declines the match when the page never defined
      // that label — GFM leaves it as literal text. Declining has to
      // happen here, before any text is emitted, for the same reason.
      if (m[18] !== undefined && !__footnoteDefs.has(m[18])) {
        re.lastIndex = m.index + 1;
        continue;
      }
      if ((m[19] !== undefined || m[21] !== undefined)
          && !__linkDefs.has((m[19] !== undefined ? (m[20] || m[19]) : m[21]).toLowerCase())) {
        re.lastIndex = m.index + 1;
        continue;
      }
      if (m.index > pos) host.appendChild(textNode(text.slice(pos, m.index)));
      if (m[1] !== undefined) {
        host.appendChild(document.createTextNode(m[1]));
      } else if (m[3] !== undefined) {
        const e = document.createElement('code');
        // CommonMark strips one space at each end when both are there —
        // that is what lets `` `x` `` carry a leading backtick.
        e.textContent = /^ [\s\S]* $/.test(m[3]) && /[^ ]/.test(m[3]) ? m[3].slice(1, -1) : m[3];
        host.appendChild(e);
      } else if (m[4] !== undefined) {
        host.appendChild(renderImage(m[4], m[5]));
      } else if (m[6] !== undefined || m[7] !== undefined) {
        const e = document.createElement('strong'); parseInline(m[6] !== undefined ? m[6] : m[7], e); host.appendChild(e);
      } else if (m[8] !== undefined) {
        const e = document.createElement('del'); parseInline(m[8], e); host.appendChild(e);
      } else if (m[9] !== undefined || m[10] !== undefined) {
        const e = document.createElement('em'); parseInline(m[9] !== undefined ? m[9] : m[10], e); host.appendChild(e);
      } else if (m[11] !== undefined) {
        host.appendChild(renderLink(m[11], m[12], m[13]));
      } else if (m[14] !== undefined) {
        host.appendChild(renderLink(m[14], m[14]));
      } else if (m[15] !== undefined) {
        // Sanitised allow-list pass-through: bare element, recursive
        // inline body; only `title` survives from the attribute string
        // (tooltips on <abbr>). Everything else is dropped.
        const e = document.createElement(m[15].toLowerCase());
        const title = /\btitle="([^"]*)"/.exec(m[16] || '');
        if (title) e.title = title[1];
        parseInline(m[17], e);
        host.appendChild(e);
      } else if (m[18] !== undefined) {
        host.appendChild(renderFootnoteRef(m[18]));
      } else if (m[19] !== undefined || m[21] !== undefined) {
        // [text][label] · [label][] · [label] — all resolve against the
        // page's link-reference definitions.
        const def = __linkDefs.get((m[19] !== undefined ? (m[20] || m[19]) : m[21]).toLowerCase());
        host.appendChild(renderLink(m[19] !== undefined ? m[19] : m[21], def.href, def.title));
      } else {
        host.appendChild(document.createElement('br'));
      }
      pos = m.index + m[0].length;
    }
    if (pos < text.length) host.appendChild(textNode(text.slice(pos)));
  }

  // True when neither end of an underscore run touches a word character.
  // `snake_case`, `a__b` and `__init__`'s inner underscores all fail this;
  // a run that stands between spaces or punctuation passes.
  function underscoreRunIsFree(text, index, length) {
    const before = index > 0 ? text.charAt(index - 1) : '';
    const after = index + length < text.length ? text.charAt(index + length) : '';
    return !/[\w]/.test(before) && !/[\w]/.test(after);
  }

  /* An `oku-*` fence that did not lift is a documentation SAMPLE of a
     kit primitive, and its body is the JSON that primitive takes. Left
     as `language-oku-chart`, Prism's autoloader goes looking for a
     grammar that will never exist — a 404 in the reader's console on
     every page that documents the kit, and no highlighting either.
     JSON is both what the body is and a grammar that exists. */
  function codeLanguage(lang) {
    return /^oku-/.test(lang) ? 'json' : lang;
  }

  function renderImage(alt, src) {
    const url = safeUrl(src, true);
    if (url === null) return textNode(alt);
    const img = document.createElement('img');
    img.setAttribute('src', url);
    img.setAttribute('alt', alt);
    img.className = 'okt-inline-img';
    img.loading = 'lazy';
    return img;
  }

  function renderLink(label, href, title) {
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
    // A destination that would execute script on click is not a link.
    // Dropping the href (rather than the text) keeps the label readable.
    const url = safeUrl(href, false);
    if (url === null) {
      const span = document.createElement('span');
      parseInline(label, span);
      return span;
    }
    const a = document.createElement('a');
    parseInline(label, a);
    a.setAttribute('href', url);
    if (title) a.setAttribute('title', title);
    if (/^https?:/i.test(url)) {
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

  // Thematic break: three or more of the same marker, spaces allowed
  // between them, nothing else on the line.
  const HR_RE = /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/;

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
    'timeline', 'compare-grid', 'insight', 'example', 'live-snippet', 'annotated-code', 'diagram', 'info-tip'];
    // No 'tldr': `> [!TLDR]` is the one way to write one — see chrome/renderer admonition handling.

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

  // Anchor ids handed out during the current render pass. Two headings
  // with the same title slugify identically; a duplicate id makes
  // getElementById (deep links, the TOC, scroll-spy) reach the first one
  // forever, so later collisions get a numeric suffix — the convention
  // GitHub and every other renderer uses.
  let __anchorIds = new Set();

  function resetAnchorIds() { __anchorIds = new Set(); }

  function uniqueAnchorId(id) {
    if (!__anchorIds.has(id)) { __anchorIds.add(id); return id; }
    let n = 2;
    while (__anchorIds.has(id + '-' + n)) n++;
    const out = id + '-' + n;
    __anchorIds.add(out);
    return out;
  }

  // opts.noIslands — do not treat a block-level HTML tag as an island.
  // List-item content is dedented before it is re-parsed, so a line that
  // reads `<chart> renders …` is NOT at column 0 in the source and must
  // stay prose; only a page-level string can open an island.
  function parseMarkdown(src, opts) {
    const noIslands = !!(opts && opts.noIslands);
    const lines = String(src || '').split('\n');
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      // Blank line — skip.
      if (!line.trim()) { i++; continue; }
      // Thematic break — any of `---`, `***`, `___`, with optional inner
      // spaces (`- - -`). Only `---` used to qualify, so a `***` rule
      // rendered as a paragraph of asterisks.
      if (HR_RE.test(line)) { out.push({ k: 'hr' }); i++; continue; }
      // Fenced code block. Variable-length: a fence of N backticks (or
      // tildes) closes only at a line of N or more of the SAME character.
      // Lets authors nest a 3-tick fenced sample inside a 4-tick outer
      // fence — the CommonMark-compliant way to show markdown code
      // samples that contain code fences.
      const fence = line.match(/^(`{3,}|~{3,})\s*([\w-]*)[^\n]*$/);
      if (fence) {
        const openLen = fence[1].length;
        const fenceChar = fence[1].charAt(0);
        const lang = fence[2] || '';
        const body = [];
        i++;
        const closeRe = new RegExp('^' + (fenceChar === '~' ? '~' : '`') + '{' + openLen + ',}\\s*$');
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
      const island = noIslands ? null : isIslandStart(line);
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
      if (line.trim() && !isBlockStart(line, noIslands) && i + 1 < lines.length && /^:\s+\S/.test(lines[i + 1])) {
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
      // Heading. A closing sequence of #s is decoration, not title text.
      const head = line.match(/^(#{1,6})\s+(.+?)(?:\s+\{#([\w-]+)\})?\s*$/);
      if (head) {
        const level = head[1].length;
        const title = head[2].replace(/\s+#+\s*$/, '');
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
        const align = splitTableRow(lines[i + 1]).map(function (spec) {
          const left = spec.charAt(0) === ':';
          const right = spec.charAt(spec.length - 1) === ':';
          return left && right ? 'center' : right ? 'right' : left ? 'left' : '';
        });
        i += 2; // skip header + separator
        const rows = [];
        while (i < lines.length && lines[i].indexOf('|') >= 0 && lines[i].trim()) {
          // GFM: a row is padded with empty cells / truncated to the
          // header width, so the body can never out-column the head.
          const cells = splitTableRow(lines[i]);
          while (cells.length < hdr.length) cells.push('');
          rows.push(cells.slice(0, hdr.length));
          i++;
        }
        out.push({ k: 'table', headers: hdr, rows: rows, align: align });
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
      while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i], noIslands) && !(i + 1 < lines.length && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i + 1]))) {
        para.push(lines[i]);
        i++;
      }
      out.push({ k: 'paragraph', text: joinParagraph(para) });
    }
    return out;
  }

  // Collapse a paragraph's lines into one inline string. A line ending in
  // two or more spaces, or in a single backslash, is GFM's hard break and
  // survives as <br>; every other newline is a soft break, i.e. a space.
  function joinParagraph(lines) {
    let out = '';
    for (let k = 0; k < lines.length; k++) {
      const last = k === lines.length - 1;
      let line = lines[k];
      let hard = false;
      if (!last && /\s{2,}$/.test(line)) { hard = true; }
      else if (!last && /(^|[^\\])\\$/.test(line)) { hard = true; line = line.slice(0, -1); }
      out += line.replace(/\s+$/, '');
      if (!last) out += hard ? '<br>' : ' ';
    }
    return out.replace(/[^\S\n]+/g, ' ').trim();
  }

  // A block-level HTML tag at column 0 opens an island; inline-level
  // tags don't. Returns the lowercase tag name, or null.
  function isIslandStart(line) {
    const m = line.match(/^<\/?([a-zA-Z][\w-]*)(?:[\s/>]|$)/);
    if (!m) return null;
    const tag = m[1].toLowerCase();
    return INLINE_HTML_TAGS.indexOf(tag) < 0 ? tag : null;
  }

  function isBlockStart(line, noIslands) {
    return /^#{1,6}\s/.test(line)
      || /^>\s?/.test(line)
      || /^(```|~~~)/.test(line)
      || HR_RE.test(line)
      || /^(\s*)([-*]|\d+[.)])\s+/.test(line)
      || /^:\s+\S/.test(line)
      || (!noIslands && isIslandStart(line) !== null);
  }

  function splitTableRow(line) {
    // Trim leading/trailing pipes, then split on |. Two things escape the
    // split: a backslash-escaped pipe (`\|`, GFM's documented way to put
    // a pipe in a cell) and a pipe inside a `code` span.
    let s = line.trim();
    if (s.startsWith('|')) s = s.slice(1);
    if (s.endsWith('|')) s = s.slice(0, -1);
    const cells = [];
    let cur = '';
    let inCode = false;
    for (let k = 0; k < s.length; k++) {
      const c = s.charAt(k);
      if (c === '\\' && k + 1 < s.length && s.charAt(k + 1) === '|') { cur += '|'; k++; }
      else if (c === '`') { inCode = !inCode; cur += c; }
      else if (c === '|' && !inCode) { cells.push(cur.trim()); cur = ''; }
      else cur += c;
    }
    cells.push(cur.trim());
    return cells;
  }

  const LIST_ITEM_RE = /^(\s*)([-*]|\d+[.)])(\s+)(.*)$/;

  function parseList(lines, start) {
    // Walks lines starting at `start`. Returns { node, next }.
    // Supports bullet (- / *) and ordered (1. / 1)) at any indent depth.
    //
    // An item owns every following line that is indented past the marker,
    // blank lines included — that is what makes a second paragraph, a
    // fenced code block or a nested list part of the item instead of
    // ending the list. Each item is kept as raw (dedented) lines and
    // parsed as its own little markdown document at render time.
    const items = [];
    let i = start;
    const first = lines[start].match(LIST_ITEM_RE);
    const baseIndent = first[1].length;
    const ordered = /\d/.test(first[2]);
    const startNum = ordered ? parseInt(first[2], 10) : 1;
    // Switching marker family ends the list, as GFM specifies — an `-`
    // item after a `1.` item starts a new <ul> instead of joining the
    // <ol> (which silently renumbered it).
    const sameFamily = (marker) => /\d/.test(marker) === ordered;
    while (i < lines.length) {
      const m = lines[i].match(LIST_ITEM_RE);
      if (m && m[1].length === baseIndent && !sameFamily(m[2])) break;
      if (m && m[1].length === baseIndent) {
        const contentIndent = m[1].length + m[2].length + m[3].length;
        const itemLines = [m[4]];
        i++;
        while (i < lines.length) {
          if (!lines[i].trim()) {
            // A blank line continues the item only if indented content
            // follows it; otherwise it ends the item (and maybe the list).
            let j = i;
            while (j < lines.length && !lines[j].trim()) j++;
            const indent = j < lines.length ? lines[j].match(/^(\s*)/)[1].length : 0;
            if (j < lines.length && indent >= contentIndent) {
              for (let k = i; k < j; k++) itemLines.push('');
              i = j;
              continue;
            }
            break;
          }
          const indent = lines[i].match(/^(\s*)/)[1].length;
          if (indent >= contentIndent) {
            itemLines.push(lines[i].slice(contentIndent));
            i++;
            continue;
          }
          // A less-indented list marker belongs to this list (or an outer
          // one); anything else at column <= base ends the item.
          if (LIST_ITEM_RE.test(lines[i]) && indent > baseIndent) {
            itemLines.push(lines[i].slice(Math.min(indent, contentIndent)));
            i++;
            continue;
          }
          break;
        }
        while (itemLines.length && !itemLines[itemLines.length - 1].trim()) itemLines.pop();
        items.push(itemLines);
      } else if (!lines[i].trim()) {
        // Blank between items — the list continues if another item follows.
        let j = i;
        while (j < lines.length && !lines[j].trim()) j++;
        const next = j < lines.length ? lines[j].match(LIST_ITEM_RE) : null;
        if (next && next[1].length === baseIndent && sameFamily(next[2])) { i = j; continue; }
        break;
      } else {
        break;
      }
    }
    return { node: { k: 'list', ordered: ordered, start: startNum, items: items }, next: i };
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
          if (node.id) h.id = uniqueAnchorId(node.id);
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
          if (node.lang) code.className = 'language-' + codeLanguage(node.lang);
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
      section.id = uniqueAnchorId('tldr');
      const tldr = document.createElement('div');
      tldr.className = 'tldr';
      const lab = document.createElement('span');
      lab.className = 'tldr-label';
      lab.textContent = 'TL;DR';
      tldr.appendChild(lab);
      const h2 = document.createElement('h2');
      h2.textContent = node.title || 'TL;DR';
      // An untitled `> [!TLDR]` used to print the words twice — once in
      // the pill, once here — and that is exactly what the starter
      // template emits, so it was the default state of the block that
      // opens most pages. The heading still has to EXIST: buildTOC()
      // skips any section without an h2, and the search index reads the
      // section heading. So when it would only repeat the pill, keep it
      // for the outline and take it out of the visual flow.
      if (!node.title || node.title.trim().toLowerCase() === 'tl;dr') {
        h2.className = 'okt-sr-only';
      }
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
      // NOT a heading. `##` opens a section, so a callout sits under an
      // h2 and an h4 here skipped a level — six such breaks on
      // docs/architecture.html, four of them callouts. h3 is not the fix
      // either: buildTOC collects every h3 in a section, so promoting
      // these would put callout titles in the on-page contents.
      //
      // A callout is an aside with a name, not a section of the
      // document. So it becomes a labelled region: the title names the
      // region for assistive tech through aria-labelledby, and the
      // reader's heading-navigation list stays the document's own
      // outline.
      const h = document.createElement('p');
      h.className = 'callout-title';
      h.id = uniqueAnchorId('callout-title');
      h.textContent = node.title;
      c.setAttribute('role', 'note');
      c.setAttribute('aria-labelledby', h.id);
      c.appendChild(h);
    }
    const sub = parseMarkdown(node.body);
    emitMarkdown(c, sub, null);
    return c;
  }

  function renderList(node) {
    const tag = node.ordered ? 'ol' : 'ul';
    const list = document.createElement(tag);
    if (node.ordered && node.start && node.start !== 1) list.start = node.start;
    for (const item of node.items) {
      const li = document.createElement('li');
      const lines = item.slice();
      // GFM task-list item: leading [ ] / [x] becomes a checkbox.
      const task = (lines[0] || '').match(/^\[([ xX])\]\s+/);
      if (task) {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.disabled = true;
        cb.checked = task[1] !== ' ';
        li.className = 'task-item';
        li.appendChild(cb);
        li.appendChild(document.createTextNode(' '));
        lines[0] = lines[0].slice(task[0].length);
      }
      // Tight item (no blank line inside it): the leading prose goes
      // straight into the <li>, so `- a` stays `<li>a</li>` and a nested
      // list hangs off the same item without a <p> wrapper. A loose item
      // — second paragraph, fence, table — renders as its own markdown
      // sub-document, paragraphs included.
      const blocks = parseMarkdown(lines.join('\n'), { noIslands: true });
      const tight = lines.every(function (l) { return l.trim() !== ''; });
      if (tight && blocks.length && blocks[0].k === 'paragraph') {
        parseInline(blocks[0].text, li);
        emitMarkdown(li, blocks.slice(1), null);
      } else {
        emitMarkdown(li, blocks, null);
      }
      list.appendChild(li);
    }
    return list;
  }

  function renderMarkdownTable(node) {
    const table = document.createElement('table');
    const align = node.align || [];
    const thead = document.createElement('thead');
    const htr = document.createElement('tr');
    node.headers.forEach(function (h, col) {
      const th = document.createElement('th');
      parseInline(h, th);
      if (align[col]) th.style.textAlign = align[col];
      htr.appendChild(th);
    });
    thead.appendChild(htr);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    for (const row of node.rows) {
      const tr = document.createElement('tr');
      row.forEach(function (cell, col) {
        const td = document.createElement('td');
        parseInline(cell, td);
        if (align[col]) td.style.textAlign = align[col];
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    return table;
  }

  /* Derive a whole accent family — soft and strong surfaces, light and
     dark — from one authored colour. Used by `_applyAccent` for any
     accent that is not one of the three hand-tuned named palettes.

     Same hue throughout, by construction: `ui-aesthetics` calls a
     surface and its accent from different hue families "two unrelated
     light sources on one object", and that is exactly what a page got
     when only --accent moved.

     The lightness targets are read off the named palettes rather than
     invented — indigo's strong sits ~9 points below its accent, its
     soft near L 94, and its dark-theme accent up near L 79. */
  function deriveAccent(color) {
    const hex = String(color).trim().replace(/^#/, '');
    const full = hex.length === 3 ? hex.split('').map(function (c) { return c + c; }).join('') : hex;
    if (!/^[0-9a-fA-F]{6}$/.test(full)) return null;
    const r = parseInt(full.slice(0, 2), 16) / 255;
    const g = parseInt(full.slice(2, 4), 16) / 255;
    const b = parseInt(full.slice(4, 6), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const l = (max + min) / 2;
    const d = max - min;
    let h = 0;
    let s = 0;
    if (d !== 0) {
      s = d / (1 - Math.abs(2 * l - 1));
      if (max === r) h = 60 * (((g - b) / d) % 6);
      else if (max === g) h = 60 * ((b - r) / d + 2);
      else h = 60 * ((r - g) / d + 4);
      if (h < 0) h += 360;
    }
    const H = Math.round(h);
    const S = Math.round(s * 100);
    const L = Math.round(l * 100);
    const hsl = function (sat, lig) {
      return 'hsl(' + H + ' ' + Math.max(0, Math.min(100, Math.round(sat))) + '% ' +
        Math.max(0, Math.min(100, Math.round(lig))) + '%)';
    };
    return {
      light: {
        // The authored colour is used verbatim — an author who wrote a
        // hex expects to see that hex.
        accent: '#' + full,
        soft: hsl(Math.min(S, 90), 93),
        strong: hsl(S, Math.max(22, Math.min(45, L - 10))),
      },
      dark: {
        // A dark theme inverts the roles: the accent has to be light
        // enough to read on a near-black surface, and "soft" becomes a
        // deep tint rather than a pale one.
        accent: hsl(Math.min(S, 80), 72),
        soft: hsl(Math.min(S, 60), 14),
        strong: hsl(Math.min(S, 85), 82),
      },
    };
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
      // A file:// origin is opaque, so fetch() is blocked cross-origin
      // no matter what sits next to the file. Calling it anyway only
      // buys a browser-level console error before the same fallback
      // runs, so decide up front.
      if (window.location.protocol === 'file:') {
        if (this._renderManifestIndex(url, host)) return;
        this._fail(
          'page-source-unreachable',
          'Opened over file:// with no inlined page. A browser cannot read ' + url +
          ' from a file:// origin — use the dist/standalone/ build, which carries its page inside the HTML.'
        );
        return;
      }
      // Same reasoning as the file:// branch, one step earlier: when the
      // manifest already SAYS this page has no source of its own, the
      // fetch is known to 404 and buys nothing but a red line on the
      // console of every reader who opens the front door of the site.
      // The entry stub is the one page in a tree with `source: null`,
      // and it is also the one page that carries the manifest inline, so
      // the answer is on hand before the request is made.
      if (this._hasNoPageSource(url) && this._renderManifestIndex(url, host)) return;
      try {
        const res = await fetch(wa(url), { cache: 'no-cache' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        page = await res.json();
      } catch (e) {
        if (this._renderManifestIndex(url, host)) return;
        this._fail('page-fetch-failed', 'Could not load ' + url + ': ' + e.message);
        return;
      }
      this.render(page, host);
    }

    /* The entry stub `oku init` writes has no page source of its own —
     * it exists to be the door into the tree, and carries the site
     * manifest inline for the drawer. Rendering nothing there left the
     * front door of every docs tree blank (plus a fetch error in the
     * console), and the reader had to guess that the Contents button
     * held the actual site. Render the manifest as the page instead.
     *
     * Scoped to the index: on any other page a missing JSON is a real
     * failure and must keep reporting as one. Returns true if it
     * rendered. */
    /* Does the manifest name this page as having no source? Matched by
     * SUFFIX for the same reason the language switch is — a manifest
     * path is relative to the root it was built from, and that root is a
     * different thing in each mode. Absent manifest, absent entry or an
     * entry with a source: answer no and let the fetch decide. */
    _hasNoPageSource(url) {
      const m = window.__okuManifest;
      const pages = (m && Array.isArray(m.pages)) ? m.pages : [];
      if (!pages.length) return false;  // nothing known — let the fetch decide
      const here = String(url || '').replace(/\.json$/, '.html');
      for (const p of pages) {
        if (!p || !p.path) continue;
        const tail = '/' + String(p.path).replace(/\.json$/, '.html');
        if (here === p.path || here.endsWith(tail)) return !p.source;
      }
      // Listed nowhere. A manifest lists every page the build wrote a
      // source for, so a page missing from a manifest that has entries
      // has no source — the entry stub of a tree whose author never
      // wrote an index.md is exactly this, and it is the case the
      // caller has already narrowed to index.json.
      return true;
    }

    _renderManifestIndex(url, host) {
      if (!/(^|\/)index\.json$/.test(String(url || ''))) return false;
      const m = window.__okuManifest;
      const pages = (m && Array.isArray(m.pages)) ? m.pages : [];
      const rows = pages.filter((p) => p && p.path && !/(^|\/)index\.html$/.test(p.path));
      if (!rows.length) return false;
      // Summaries are author prose — keep them out of block position so
      // a stray character can't start a markdown construct.
      const esc = (s) => String(s).replace(/[\[\]]/g, '').replace(/\s+/g, ' ').trim();
      const body = rows.map((p) => {
        const title = esc(p.title || p.path);
        const summary = p.summary ? ' — ' + esc(p.summary) : '';
        return '- [' + title + '](' + p.path + ')' + summary;
      }).join('\n');
      const title = (document.title || 'Documentation').trim();
      this.render({
        k: 'page',
        t: title,
        b: ['## Pages {#pages}\n\n' + body + '\n'],
      }, host);
      return true;
    }

    render(page, host) {
      this.host = host || this.host || document.querySelector('main#main-content') || document.querySelector('main') || document.body;
      this.warnings = [];
      __renderTypedBlock = (block) => this._renderTyped(block);
      resetAnchorIds();
      resetDefinitions();

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
        if (heading.id) section.id = uniqueAnchorId(heading.id);
        const h2 = document.createElement('h2');
        h2.textContent = heading.title;
        section.appendChild(h2);
        main.appendChild(section);
        currentSection = section;
      };
      const target = () => currentSection || main;

      // Definitions are page-scoped: collect (and strip) them from every
      // string first, so a reference resolves against a definition that
      // lives in a later block.
      const blocks = (page.b || []).map(function (b) {
        return typeof b === 'string' ? extractDefinitions(b) : b;
      });

      for (const block of blocks) {
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

      const notes = renderFootnoteSection();
      if (notes) main.appendChild(notes);

      if (this.warnings.length) {
        window.dispatchEvent(new CustomEvent('oku:warnings', { detail: this.warnings }));
      }
      // An event is only observable by a listener that was already
      // attached. Anything arriving after the walk — a late subsystem, a
      // test, a consumer script — has no way to ask whether rendering
      // happened, so it waits a fixed number of milliseconds instead and
      // becomes load-dependent. The flag makes the state readable at any
      // time; the event still fires for anyone who wants the moment.
      window.__okuRendered = true;
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
      // `summary` is the one line the author always writes — it feeds the
      // nav, the page list and the search result. Authors were also
      // copying it verbatim into `subtitle` to fill the cover (three of
      // this repo's own pages carried the identical sentence in both
      // fields). Falling back removes the duplicate field without
      // removing the cover line it was there to produce.
      const subtitle = meta.subtitle || meta.summary;
      if (subtitle) {
        const sub = document.createElement('p');
        sub.className = 'subtitle';
        sub.textContent = subtitle;
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
      // Two hand-maintained dates that are usually the same one. When
      // they agree, `date` has already said it — printing "Last updated"
      // underneath in a second style says nothing and looks like drift.
      if (meta.updated && meta.updated !== meta.date) {
        const u = document.createElement('div');
        u.className = 'meta meta-updated';
        // Composed, so it cannot be matched as a whole string later —
        // it carries its template for the localize pass to rebuild.
        u.setAttribute('data-oku-t', 'Last updated {0}');
        u.setAttribute('data-oku-t0', meta.updated);
        u.textContent = (typeof okuT === 'function')
          ? okuT('Last updated {0}', meta.updated)
          : 'Last updated ' + meta.updated;
        cover.appendChild(u);
      }
      // A title on its own does not need a 156px tinted panel to sit in.
      if (cover.children.length === 1) cover.classList.add('cover-bare');
      return cover;
    }

    /* -------------------------------------------------------------- *
     * Typed primitives
     * -------------------------------------------------------------- */

    _renderTyped(block) {
      if (!block || !block.k) return this._unknown(block);
      // Contract check BEFORE rendering. Without it a payload the
      // renderer cannot read degrades instead of failing: a step flow
      // written with `title`/`detail` drew four cards containing the
      // numerals 1-4 and nothing else, and a KPI grid written with
      // `value`/`note` printed the literal string "undefined" into a
      // delivered document. Both passed a "did it draw anything" test.
      // The contract mirrors the schema's `required` lists, and
      // test_renderer_contract.py fails if the two drift.
      const missing = this._contractViolation(block);
      if (missing) {
        this._warn('block-contract', 'Block "' + block.k + '" is missing ' + missing, block);
        return this._blockError(block, missing);
      }
      let el;
      switch (block.k) {
        case 'diagram':        el = this._renderDiagram(block); break;
        case 'code':           el = this._renderCode(block); break;
        case 'annotated-code': el = this._renderAnnotatedCode(block); break;
        case 'live-snippet':   el = this._renderLiveSnippet(block); break;
        case 'table':          el = this._renderTable(block); break;
        case 'kpi-grid':       el = this._renderKpiGrid(block); break;
        case 'step-flow':      el = this._renderStepFlow(block); break;
        case 'timeline':       el = this._renderTimeline(block); break;
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
      // A KNOWN kind carrying a payload the renderer cannot read used
      // to produce an element with nothing in it — a band of white
      // space in a published document, with no console warning and no
      // clue in the page about which block it was. Three blocks on one
      // real page failed this way (a table written with `columns` +
      // keyed rows, a step flow written with `title`/`detail`) and the
      // page shipped. An empty typed block is always a defect: every
      // primitive here exists to draw something.
      if (el && !this._hasVisibleContent(el)) {
        this._warn('empty-block', 'Block "' + block.k + '" rendered nothing — check its payload against the schema.', block);
        return this._blockError(block);
      }
      return el;
    }

    /* Which fields a typed block must carry for its renderer to have
       anything to read. Mirrors the `required` arrays in
       kit/schema/page.schema.json — kept as a literal here because the
       renderer must not depend on fetching the schema at runtime, and
       kept honest by a test that compares the two files.
       `items` names an array property and what each element needs. */
    _contractViolation(block) {
      const C = OkuRenderer.BLOCK_CONTRACT[block.k];
      if (!C) return null;
      for (const key of (C.required || [])) {
        if (block[key] === undefined || block[key] === null) return '`' + key + '`';
      }
      for (const [field, keys] of Object.entries(C.items || {})) {
        const arr = block[field];
        if (!Array.isArray(arr)) continue;
        for (const item of arr) {
          if (!item || typeof item !== 'object') continue;
          for (const key of keys) {
            if (item[key] === undefined || item[key] === null) {
              return '`' + key + '` on an entry of `' + field + '`';
            }
          }
        }
      }
      return null;
    }

    /* Cheap "did this draw anything" test: any text, or any element
       that paints on its own (svg / img / canvas / a custom element
       that fills itself in later). Deliberately generous — the point is
       to catch a block that produced NOTHING, not to police sparse
       ones. */
    _hasVisibleContent(el) {
      if (!el) return false;
      if ((el.textContent || '').trim()) return true;
      return !!el.querySelector('svg, img, canvas, oku-chart, oku-diagram, oku-snippet, oku-annotated-code, input, td, th, li');
    }

    /* The same in-page error card a broken diagram gets. An author sees
       the problem where the block should have been, which is the only
       place they are looking. */
    _blockError(block, missing) {
      const card = document.createElement('div');
      card.className = 'okd-error-card okt-block-error';
      const head = document.createElement('div');
      head.className = 'okd-error-head';
      const kind = document.createElement('strong');
      kind.textContent = String(block.k);   // textContent, not innerHTML: `k` is authored input
      head.appendChild(kind);
      head.appendChild(document.createTextNode(missing ? ' is missing a required field' : ' rendered nothing'));
      card.appendChild(head);
      const msg = document.createElement('div');
      msg.className = 'okd-error-msg';
      const keys = Object.keys(block).filter(k => k !== 'k');
      msg.textContent =
        (missing ? 'Needs ' + missing + '. ' : '') +
        'The payload carries ' + (keys.length ? keys.map(k => '`' + k + '`').join(', ') : 'no fields') +
        '. Run `oku check` — the schema names the fields this block needs.';
      card.appendChild(msg);
      return card;
    }

    _renderInfoTip(block) {
      const det = document.createElement('details');
      det.className = 'info-tip';
      if (block.open) det.setAttribute('open', '');
      const sum = document.createElement('summary');
      parseInline(block.summary || '', sum);
      det.appendChild(sum);
      for (const sub of (block.content || [])) {
        // Three shapes reach here and only one of them is v1. The
        // markdown pipeline emits bare strings for prose and `k`-keyed
        // objects for typed blocks, and `convertV1Block` returns null
        // for both — so converting every item unconditionally discarded
        // everything an author could write in markdown and left a
        // <details> holding only its <summary>. Convert what is v1;
        // pass the rest through.
        const item = (sub && typeof sub === 'object' && sub.kind && !sub.k)
          ? convertV1Block(sub)
          : sub;
        if (item == null) continue;
        if (typeof item === 'string') {
          emitMarkdown(det, parseMarkdown(item), null);
        } else if (typeof item === 'object') {
          const el = this._renderTyped(item);
          if (el) det.appendChild(el);
        }
      }
      // The generic empty-block guard cannot see this one: a disclosure
      // that dropped its whole body still paints its summary, so
      // `_hasVisibleContent` passes and the page ships a box that opens
      // onto nothing. Content that was given and did not arrive is the
      // same defect as a block that drew nothing, and gets the same card.
      if ((block.content || []).length && det.childElementCount < 2) {
        this._warn('empty-block', 'Block "info-tip" dropped its content — nothing rendered inside the disclosure.', block);
        return this._blockError(block);
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
      if (block.lang) code.className = 'language-' + codeLanguage(block.lang);
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
        const h = document.createElement('p');
        h.className = 'okt-card-title';
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

    /* An ordered sequence where each entry carries a state. The rail is
       drawn by CSS (one ::before on the list, one per item), so the DOM
       here is just the reading order — nothing to keep in sync, and the
       page can be read with the stylesheet off. */
    _renderTimeline(block) {
      const STATUSES = ['note', 'done', 'open', 'dropped'];
      const list = document.createElement('ol');
      list.className = 'okt-timeline';
      (block.events || []).forEach((e) => {
        const item = document.createElement('li');
        const status = STATUSES.indexOf(e.status) === -1 ? 'note' : e.status;
        item.className = 'okt-tl-item okt-tl-' + status;
        const head = document.createElement('div');
        head.className = 'okt-tl-head';
        if (e.label) {
          const chip = document.createElement('span');
          chip.className = 'okt-tl-chip';
          chip.textContent = e.label;
          head.appendChild(chip);
        }
        const title = document.createElement('span');
        title.className = 'okt-tl-title';
        parseInline(e.t || '', title);
        head.appendChild(title);
        item.appendChild(head);
        if (e.b !== undefined && e.b !== '') {
          const body = document.createElement('div');
          body.className = 'okt-tl-body';
          emitMarkdown(body, parseMarkdown(e.b), null);
          item.appendChild(body);
        }
        list.appendChild(item);
      });
      return list;
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
      // Opt-in: a card linking to a figure on this page shows that
      // figure's silhouette. chrome.js does the cloning on oku:rendered,
      // when every figure it might copy has been drawn.
      if (block.preview) grid.setAttribute('data-oku-preview', '1');
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
          const h = document.createElement('p');
          h.className = 'okt-card-title';
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
        const h = document.createElement('p');
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
          chip.setAttribute('aria-label',
            (typeof okuT === 'function' ? okuT('Toggle {0} series', s.label) : 'Toggle ' + s.label + ' series'));
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
              { k: 'value', v: numText(v) },
              { k: 'share', v: Math.round(share * 100) + '%' }
            ],
            footer: 'in ' + cat + ' = ' + numText(rowTotal)
          }));
          if (s.label) fill.title = s.label + ': ' + numText(v);
          track.appendChild(fill);
        });
        row.appendChild(track);
        const val = document.createElement('span');
        val.className = 'bar-value';
        val.textContent = numText(rowTotal);
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
        const h = document.createElement('p');
        h.className = 'bar-chart-title';
        h.textContent = block.title;
        wrap.appendChild(h);
      }
      const total = rows.reduce((s, r) => s + (+r.value || 0), 0);
      // What the total is a total OF. Row values may be written for
      // display ("26.9 GB"), and a bare "of 62.3" beside them reads as a
      // different quantity. The unit is only appended when every row
      // agrees on it — "6.6 GB of compressed pages" disagrees, and
      // guessing there would be worse than staying silent.
      const units = rows.map(r => (r.display === undefined ? '' :
        String(r.display).replace(/^\s*[-+]?[\d.,\s]+/, '').trim()));
      const unit = units.every(u => u && u === units[0]) ? ' ' + units[0] : '';
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
            { k: 'value', v: r.display !== undefined ? String(r.display) : numText(r.value) },
            { k: 'share', v: Math.round(share * 100) + '%' }
          ],
          footer: 'of ' + numText(total) + unit
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
      // The unit the numbers are in. `x_label` is declared on `chart` in
      // the schema, which means the validator accepts it on a bar chart
      // and says nothing — and this renderer used to drop it, so the
      // author wrote a unit, `oku check` passed, and the page shipped a
      // column of bare numerals. Accepted-and-silently-discarded is the
      // same defect class as a block that renders nothing; a declared
      // property either draws or fails the check.
      if (block.x_label) {
        const cap = document.createElement('div');
        cap.className = 'bar-chart-unit';
        cap.textContent = block.x_label;
        wrap.appendChild(cap);
      }
      return wrap;
    }

    _renderChartGrid(block) {
      const wrap = document.createElement('div');
      wrap.className = 'okt-chart-grid';
      if (block.title) {
        const h = document.createElement('p');
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
        return;
      }
      // A custom colour used to set --accent and stop there, which left
      // --accent-soft and --accent-strong on the indigo defaults. The
      // page then rendered one hue on the borders and another on every
      // tinted surface behind them — an orange callout rule around an
      // indigo body, an indigo icon inside it. It reads as two unrelated
      // light sources on one object, and it went unnoticed because the
      // default accent IS indigo, so the bug is invisible until someone
      // picks a colour. Dark mode was not derived at all.
      const derived = deriveAccent(accent);
      if (!derived) {
        // Not a hex we can read (a named CSS colour, a gradient). Set
        // what was asked for and leave the rest alone rather than
        // guessing a family from something we cannot decompose.
        style.textContent = ':root { --accent: ' + accent + '; }';
        return;
      }
      style.textContent =
        ':root { --accent: ' + derived.light.accent +
          '; --accent-soft: ' + derived.light.soft +
          '; --accent-strong: ' + derived.light.strong + '; }' +
        ':root[data-theme="dark"] { --accent: ' + derived.dark.accent +
          '; --accent-soft: ' + derived.dark.soft +
          '; --accent-strong: ' + derived.dark.strong + '; }';
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

  /* Generated from the `required` arrays in kit/schema/page.schema.json.
     The renderer cannot fetch the schema at runtime (standalone builds
     have no network), so this is a copy — and a copy drifts, which is
     why test_renderer_contract.py regenerates it from the schema and
     fails on any difference. Regenerate rather than hand-edit. */
  OkuRenderer.BLOCK_CONTRACT = {
    'annotated-code': { required: ['src'], items: { annotations: ['id', 'content'] } },
    'chart': { required: ['type'], items: { rows: ['label'], slices: ['label', 'value'], segments: ['label', 'count'], zones: ['from', 'to'], axes: ['label'], boxes: ['label', 'q1', 'median', 'q3', 'min', 'max'], tracks: ['label', 'value', 'max'], items: ['label', 'from', 'to'], bins: ['lo', 'hi', 'count'], distributions: ['label', 'values'], stages: ['label', 'value'], nodes: ['id'], links: ['source', 'target'], variables: ['key'], groups: ['id'], regions: ['id', 'value'], steps: ['label', 'value'], points: ['x', 'y'], ranges: ['label', 'low', 'high'] } },
    'chart-grid': { required: ['panels'] },
    'code': { required: ['src'] },
    'compare-grid': { required: ['cards'], items: { cards: ['t'] } },
    'diagram': { required: ['src'] },
    'example': { required: ['code', 'output'] },
    'image': { required: ['src'] },
    'info-tip': { required: ['summary', 'content'] },
    'insight': { required: ['b'] },
    'kpi-grid': { required: ['tiles'], items: { tiles: ['num', 'label'] } },
    'live-snippet': { required: ['src'] },
    'step-flow': { required: ['steps'], items: { steps: ['t'] } },
    'timeline': { required: ['events'], items: { events: ['t'] } },
    'svg': { required: ['src'] },
    'table': { items: { groups: ['rows'] } },
  };

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

  /* ================================================================ *
   * Fragment rendering — a whole .md FILE into a host element
   *
   * `render()` is a page: it owns document.title, the accent, the cover
   * and the anchor-id namespace. The markdown viewer needs the same
   * typography for a file that is NOT this page, inside a document that
   * is already rendered — so it needs the block pipeline without any of
   * the page-level ownership.
   *
   * Two things make it safe to run a second pass in a live document:
   *
   *   idPrefix — ids are page-global. A viewed file whose heading
   *     slugifies to one the page already used would make
   *     getElementById reach the wrong element for the rest of the
   *     session (the same defect the rail's thumbnail clone rewrites
   *     its ids to avoid). Every emitted id gets the prefix, and every
   *     fragment-internal href is rewritten to match.
   *
   *   base — relative links and images inside the viewed file point at
   *     ITS directory, not at the page's. Resolving them here is what
   *     makes a link in a viewed file mean the same thing it means on
   *     disk.
   *
   * The module-level parser state (anchor ids, link + footnote
   * definitions, the typed-block hook) is saved and restored around the
   * pass. The page has finished rendering by the time a viewer opens,
   * so nothing reads that state in between — but leaving it clobbered
   * would break the next render for a reason nobody would find.
   * ================================================================ */

  // Strip a leading YAML front-matter block. Returns { meta, body },
  // where meta is the raw block text (null when absent) — the viewer
  // shows the source, not a half-implemented YAML parse.
  function splitFrontMatter(src) {
    const text = String(src || '').replace(/^\uFEFF/, '');
    const m = text.match(/^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/);
    if (!m) return { meta: null, body: text };
    return { meta: m[1], body: text.slice(m[0].length) };
  }

  OkuRenderer.splitFrontMatter = splitFrontMatter;

  /* Render markdown source into `host`. opts:
   *   idPrefix — string prepended to every emitted id (required in a
   *              live document; defaults to '' for a bare host)
   *   base     — URL the file was loaded from; relative hrefs and image
   *              srcs resolve against it
   * Returns the warnings the typed-block renderers raised. */
  OkuRenderer.renderMarkdownInto = function (src, host, opts) {
    opts = opts || {};
    const prefix = opts.idPrefix || '';
    const savedAnchors = __anchorIds;
    const savedLinkDefs = __linkDefs;
    const savedFootnoteDefs = __footnoteDefs;
    const savedFootnoteUses = __footnoteUses;
    const savedTyped = __renderTypedBlock;
    const inner = new OkuRenderer({});

    resetAnchorIds();
    resetDefinitions();
    __renderTypedBlock = (block) => inner._renderTyped(block);

    // Detached until every id is prefixed — an id must never be live in
    // the document under its unprefixed name, not even for a frame.
    const holder = document.createElement('div');
    try {
      const body = extractDefinitions(splitFrontMatter(src).body);
      const nodes = parseMarkdown(body);
      let section = null;
      const openSection = (heading) => {
        section = document.createElement('section');
        if (heading.id) section.id = uniqueAnchorId(heading.id);
        const h2 = document.createElement('h2');
        h2.textContent = heading.title;
        section.appendChild(h2);
        holder.appendChild(section);
      };
      let buffer = [];
      const flush = () => {
        if (buffer.length) { emitMarkdown(section || holder, buffer, null); buffer = []; }
      };
      for (const node of nodes) {
        if (node.k === 'heading' && node.level === 2) { flush(); openSection(node); }
        else buffer.push(node);
      }
      flush();
      const notes = renderFootnoteSection();
      if (notes) holder.appendChild(notes);
    } finally {
      __anchorIds = savedAnchors;
      __linkDefs = savedLinkDefs;
      __footnoteDefs = savedFootnoteDefs;
      __footnoteUses = savedFootnoteUses;
      __renderTypedBlock = savedTyped;
    }

    if (prefix) {
      holder.querySelectorAll('[id]').forEach((n) => { n.id = prefix + n.id; });
      holder.querySelectorAll('a[href^="#"]').forEach((a) => {
        a.setAttribute('href', '#' + prefix + a.getAttribute('href').slice(1));
      });
    }
    if (opts.base) {
      const rebase = (el, attr) => {
        const v = el.getAttribute(attr);
        // Absolute URLs, protocol-relative, fragments and root-absolute
        // paths already say where they point. Only a genuinely relative
        // path is ambiguous, and it is ambiguous because the reader is
        // looking at the file from somewhere else in the tree.
        if (!v || /^([a-z][a-z0-9+.-]*:|\/\/|#|\/)/i.test(v)) return;
        try { el.setAttribute(attr, new URL(v, opts.base).href); } catch (e) {}
      };
      holder.querySelectorAll('a[href]').forEach((a) => rebase(a, 'href'));
      holder.querySelectorAll('img[src]').forEach((i) => rebase(i, 'src'));
    }

    while (holder.firstChild) host.appendChild(holder.firstChild);
    return inner.warnings;
  };

  window.OkuRenderer = OkuRenderer;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { OkuRenderer.autoBoot(); });
  } else {
    OkuRenderer.autoBoot();
  }
})();
