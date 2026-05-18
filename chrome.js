/* html-doc · chrome.js
 * Web Components, theme cycler, TOC builder, scroll-spy, reading aids.
 * Loaded with defer; chrome-boot.js handles pre-paint state.
 */

/* ──────────────────────────────────────────────────────────────────
 * html-doc · chrome.js
 *
 *   Web Components, theme cycler, TOC builder, scroll-spy, tooltips,
 *   site nav, charts, diagrams, snippets, warnings, search.
 *
 *   Loaded via `defer`; chrome-boot.js handles pre-paint state.
 *   Pairs with renderer.js (JSON → Custom-Element DOM walker).
 *
 *   Section map — line numbers in the source listing of this file:
 *     SVG icons                                ~6
 *     Theme cycler                            ~13
 *     TOC toggle (legacy v1)                  ~46
 *     <page-chrome>                           ~61
 *     <page-toc>                              ~91
 *     TOC builder + scroll-spy               ~130
 *     Reading aids (progress, copy buttons)  ~258
 *     Docs-root discovery                    ~341
 *     escapeHTML helper                      ~360
 *     Visual Viewport pinch-zoom tracker     ~369
 *     Tooltip controller                     ~388
 *     kit.json + glossary loader             ~513
 *     <glossary-term>                        ~685
 *     <ext-ref>                              ~725
 *     <html-doc-chart>                       ~756
 *     <html-doc-diagram> (Mermaid)           ~874
 *     <html-doc-snippet>                     ~971
 *     <page-nav>                            ~1013
 *     Forward-compat warning indicator      ~1187
 *     Pagefind search                       ~1275
 *     Event hookups (theme, render, warn)   ~1455
 *
 *   Conventions:
 *     - Custom Element classes:  class FooBar extends HTMLElement { ... }
 *     - Shared controllers:      var __htmldocFoo = (function () { ... })();
 *     - Public helpers:          plain top-level function
 *     - Internal helpers:        nested inside their controller IIFE
 * ────────────────────────────────────────────────────────────────── */

/* ============ SVG icon set ============ */
const ICON_MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>';
const ICON_SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><line x1="4.5" y1="4.5" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.5" y2="19.5"/><line x1="4.5" y1="19.5" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.5" y2="4.5"/></svg>';
const ICON_MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const ICON_SYSTEM = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>';
const ICON_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
const ICON_CLIPBOARD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>';
const ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>';
const ICON_CROSS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>';
const ICON_BRACES = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2"/><path d="M16 3a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2"/></svg>';
const ICON_CAMERA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>';

/* ============ Three-mode theme cycler (system → light → dark → system) ============ */
function getThemeMode() {
  return document.documentElement.getAttribute('data-theme-mode') || 'system';
}
function applyTheme(mode, persist) {
  var actual = mode === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : mode;
  document.documentElement.setAttribute('data-theme', actual);
  document.documentElement.setAttribute('data-theme-mode', mode);
  if (persist) {
    try {
      if (mode === 'system') localStorage.removeItem('theme-pref');
      else localStorage.setItem('theme-pref', mode);
    } catch (e) {}
  }
}
function cycleTheme() {
  var current = getThemeMode();
  var next = current === 'system' ? 'light' : current === 'light' ? 'dark' : 'system';
  applyTheme(next, true);
  // Notify subscribers (e.g., <html-doc-diagram> rerenders Mermaid).
  window.dispatchEvent(new CustomEvent('html-doc:theme-changed', {
    detail: { mode: next, theme: document.documentElement.getAttribute('data-theme') }
  }));
}
/* Follow OS changes while in system mode */
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
  if (getThemeMode() === 'system') {
    document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
  }
});

/* ============ TOC toggle (collapse on desktop, drawer on mobile) ============ */
function toggleTOC() {
  var nav = document.querySelector('page-toc, nav.toc');
  if (!nav) return;
  if (window.innerWidth <= 920) {
    nav.classList.toggle('open');
  } else {
    document.body.classList.toggle('toc-collapsed');
    try {
      localStorage.setItem('tocCollapsed',
        document.body.classList.contains('toc-collapsed') ? '1' : '0');
    } catch (e) {}
  }
}

/* ============ <page-chrome> Web Component ============ */
class PageChrome extends HTMLElement {
  connectedCallback() {
    var skipLabel = this.getAttribute('skip-label') || 'Skip to content';
    var tocLabel = this.getAttribute('toc-label') || 'Toggle table of contents';
    var themeLabel = this.getAttribute('theme-label') || 'Cycle theme (system / light / dark)';
    var topLabel = this.getAttribute('top-label') || 'Back to top';

    this.innerHTML =
      '<a class="skip-link" href="#main-content">' + skipLabel + '</a>' +
      '<div class="progress-bar" id="progress-bar"></div>' +
      '<button class="ctrl-btn toc-toggle" type="button" aria-label="' + tocLabel + '" title="' + tocLabel + '">' + ICON_MENU + '</button>' +
      '<button class="ctrl-btn theme-toggle" type="button" aria-label="' + themeLabel + '" title="' + themeLabel + '">' +
        '<span class="icon-system">' + ICON_SYSTEM + '</span>' +
        '<span class="icon-sun">' + ICON_SUN + '</span>' +
        '<span class="icon-moon">' + ICON_MOON + '</span>' +
      '</button>' +
      '<button class="ctrl-btn back-to-top" type="button" aria-label="' + topLabel + '" title="' + topLabel + '">' + ICON_UP + '</button>';

    this.querySelector('.toc-toggle').addEventListener('click', toggleTOC);
    this.querySelector('.theme-toggle').addEventListener('click', cycleTheme);
    this.querySelector('.back-to-top').addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    initReadingAids();
  }
}
customElements.define('page-chrome', PageChrome);

/* ============ <page-toc> Web Component ============ */
class PageToc extends HTMLElement {
  connectedCallback() {
    var title = this.getAttribute('title') || 'Contents';
    var inV2Layout = !!this.closest('.layout page-nav, .layout:has(page-nav)');
    // Edge-tab toggle on the LEFT inner edge (proximity — facing main content).
    // Only render the tab when in v2 3-column layout; in legacy 2-column the
    // top-left ctrl-btn handles toggling.
    this.innerHTML =
      (inV2Layout ? '<button class="page-toc-tab" type="button" aria-label="Toggle on-this-page">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 6 15 12 9 18"/></svg>' +
      '</button>' : '') +
      '<div class="page-toc-panel">' +
        '<div class="toc-header"><h2>' + title + '</h2></div>' +
        '<ol class="toc-list"></ol>' +
      '</div>';
    var self = this;
    var tab = this.querySelector('.page-toc-tab');
    if (tab) {
      tab.addEventListener('click', function () {
        if (window.innerWidth <= 1024) {
          self.classList.toggle('open');
        } else {
          document.body.classList.toggle('toc-collapsed');
          try { localStorage.setItem('tocCollapsed', document.body.classList.contains('toc-collapsed') ? '1' : '0'); } catch (e) {}
        }
      });
    }
    // If <main> already has section content (pre-rendered HTML), build
    // the TOC now. For renderer-driven pages, html-doc:rendered will
    // trigger the build later — avoid the wasted empty first pass.
    if (document.querySelector('main > section')) {
      var list = self.querySelector('.toc-list');
      if (list) buildTOC(list);
    }
  }
}
customElements.define('page-toc', PageToc);

/* ============ TOC builder + scroll-spy ============ */
function slugify(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9çğıöşü]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function appendPermalink(heading, id, label) {
  if (heading.querySelector('.permalink')) return;
  var a = document.createElement('a');
  a.className = 'permalink';
  a.href = '#' + id;
  a.textContent = '#';
  a.setAttribute('aria-label', label || 'Permalink');
  heading.appendChild(a);
}

function buildTOC(tocList) {
  if (!tocList) return;
  var sections = document.querySelectorAll('main > section');
  if (sections.length === 0) return;
  tocList.innerHTML = '';

  // Count TOC-eligible sections separately so the numbering doesn't
  // jump when buildable sections precede in DOM order.
  var tocIndex = 0;
  sections.forEach(function (sec, i) {
    var h2 = sec.querySelector('h2');
    if (!h2) return;
    var headingText = h2.cloneNode(true);
    var pre = headingText.querySelector('.num'); if (pre) pre.remove();
    var pl0 = headingText.querySelector('.permalink'); if (pl0) pl0.remove();
    if (!headingText.textContent.trim()) return;
    if (!sec.id) sec.id = 'sec-' + i;

    appendPermalink(h2, sec.id);

    tocIndex++;
    var numEl = h2.querySelector('.num');
    var num = numEl ? numEl.textContent.trim() : tocIndex;
    var titleClone = h2.cloneNode(true);
    var n = titleClone.querySelector('.num'); if (n) n.remove();
    var pl = titleClone.querySelector('.permalink'); if (pl) pl.remove();
    var title = titleClone.textContent.trim();

    var li = document.createElement('li');
    li.className = 'toc-h2';
    li.dataset.target = sec.id;

    var head = document.createElement('div');
    head.className = 'toc-head';
    head.innerHTML =
      '<span class="chevron">▸</span>' +
      '<span class="num">' + num + '.</span>' +
      '<a href="#' + sec.id + '">' + title + '</a>';
    li.appendChild(head);

    var h3s = sec.querySelectorAll('h3');
    var subOl = document.createElement('ol');
    subOl.className = 'toc-sub';
    h3s.forEach(function (h3) {
      if (!h3.id) h3.id = sec.id + '-' + slugify(h3.textContent).slice(0, 40);
      appendPermalink(h3, h3.id);
      var subLi = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + h3.id;
      a.textContent = h3.textContent.replace(/#$/, '').trim();
      subLi.appendChild(a);
      subOl.appendChild(subLi);
    });

    if (h3s.length > 0) {
      li.appendChild(subOl);
      head.addEventListener('click', function (e) {
        if (e.target.tagName !== 'A') { e.preventDefault(); li.classList.toggle('expanded'); }
      });
    } else {
      head.querySelector('.chevron').classList.add('hidden');
    }

    tocList.appendChild(li);
  });

  /* Scroll-spy */
  var tocItems = tocList.querySelectorAll('.toc-h2');
  var idToItem = {};
  tocItems.forEach(function (it) { idToItem[it.dataset.target] = it; });
  var allSubLinks = tocList.querySelectorAll('ol.toc-sub a');
  var idToSubLink = {};
  allSubLinks.forEach(function (a) { idToSubLink[a.getAttribute('href').slice(1)] = a; });

  function setActive(sectionId, h3Id) {
    tocItems.forEach(function (it) { it.classList.remove('active'); });
    allSubLinks.forEach(function (a) { a.classList.remove('active'); });
    var item = idToItem[sectionId];
    if (item) {
      item.classList.add('active', 'expanded');
      tocItems.forEach(function (it) { if (it !== item) it.classList.remove('expanded'); });
    }
    if (h3Id && idToSubLink[h3Id]) idToSubLink[h3Id].classList.add('active');
  }

  var headings = [];
  sections.forEach(function (sec) {
    headings.push({ el: sec, sectionId: sec.id, h3Id: null });
    sec.querySelectorAll('h3').forEach(function (h3) {
      headings.push({ el: h3, sectionId: sec.id, h3Id: h3.id });
    });
  });

  function updateActive() {
    var y = window.scrollY + 150;
    var current = headings[0];
    for (var k = 0; k < headings.length; k++) {
      var rect = headings[k].el.getBoundingClientRect();
      var top = rect.top + window.scrollY;
      if (top <= y) current = headings[k]; else break;
    }
    if (current) setActive(current.sectionId, current.h3Id);
  }

  var ticking = false;
  window.addEventListener('scroll', function () {
    if (!ticking) { window.requestAnimationFrame(function () { updateActive(); ticking = false; }); ticking = true; }
  }, { passive: true });
  updateActive();

  /* Close mobile drawer on link click */
  tocList.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () {
      var nav = document.querySelector('page-toc, nav.toc');
      if (nav) nav.classList.remove('open');
    });
  });
}

/* ============ Reading aids: progress, back-to-top, copy-btn, glossary ============ */
// The once-only globals (scroll + keydown listeners) are registered the
// first time initReadingAids runs; subsequent calls only re-scan the DOM
// for new <pre> blocks needing copy buttons. Without this guard, every
// renderer-rendered event would attach a duplicate scroll + keydown
// closure that can't be removed.
var __htmldocAidsInited = false;

function initReadingAids() {
  if (!__htmldocAidsInited) {
    __htmldocAidsInited = true;

    /* Progress bar + back-to-top */
    (function () {
      var bar = document.getElementById('progress-bar');
      var btt = document.querySelector('.back-to-top');
      var ticking = false;
      function update() {
        var h = document.documentElement;
        var max = h.scrollHeight - h.clientHeight;
        if (bar) bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
        if (btt) btt.classList.toggle('visible', h.scrollTop > 600);
        ticking = false;
      }
      window.addEventListener('scroll', function () {
        if (!ticking) { window.requestAnimationFrame(update); ticking = true; }
      }, { passive: true });
      update();
    })();

    /* Escape closes mobile TOC */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        var nav = document.querySelector('page-toc, nav.toc');
        if (nav) nav.classList.remove('open');
      }
    });
  }

  /* Copy-to-clipboard on every <pre> block — re-runs safely; already
     guarded by `if (pre.querySelector('.copy-btn')) return`. Icon-only
     (clipboard → checkmark on success → cross on failure). */
  (function () {
    if (!navigator.clipboard) return;
    document.querySelectorAll('pre').forEach(function (pre) {
      if (pre.querySelector('.copy-btn')) return;
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.innerHTML = ICON_CLIPBOARD;
      btn.title = 'Copy code to clipboard';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      pre.appendChild(btn);
      btn.addEventListener('click', function () {
        var code = pre.querySelector('code');
        var text = code ? code.textContent : pre.textContent;
        navigator.clipboard.writeText(text).then(function () {
          btn.innerHTML = ICON_CHECK;
          btn.classList.add('copied'); btn.classList.remove('error');
          setTimeout(function () {
            btn.innerHTML = ICON_CLIPBOARD;
            btn.classList.remove('copied');
          }, 1500);
        }).catch(function () {
          btn.innerHTML = ICON_CROSS;
          btn.classList.add('error'); btn.classList.remove('copied');
          setTimeout(function () {
            btn.innerHTML = ICON_CLIPBOARD;
            btn.classList.remove('error');
          }, 1500);
        });
      });
    });
  })();

  /* Prism syntax highlight — lazy CDN load; only triggers if at least
     one `<code class="language-...">` block exists on the page. */
  if (typeof __prismLoader !== 'undefined') {
    __prismLoader.highlightAll();
  }

  /* Glossary tooltip — legacy v1 .g-wrap mobile tap support. The new
     tooltip controller attaches its own listeners; this remains for
     hand-authored HTML using the legacy class. Per-element handler
     reattachment is harmless on re-run. */
  document.querySelectorAll('.g-wrap').forEach(function (el) {
    if (el.dataset.gwrapBound) return;
    el.dataset.gwrapBound = '1';
    el.addEventListener('click', function (e) {
      if (window.matchMedia('(hover: none)').matches) {
        e.preventDefault();
        document.querySelectorAll('.g-wrap.open').forEach(function (o) { if (o !== el) o.classList.remove('open'); });
        el.classList.toggle('open');
      }
    });
  });
}

/* ============ Docs-root discovery ============ *
 * Finds the project root by locating any kit reference in the document
 * and stripping the trailing path back to (and including) the directory
 * containing _kit/. Lets pages at any directory depth fetch kit.json
 * and site-manifest.json from the same place rather than guessing
 * based on the page's own path.
 * ---------------------------------------------------------------- */
var __htmldocDocsRoot = (function () {
  var refs = document.querySelectorAll('link[href*="_kit/"], script[src*="_kit/"]');
  for (var i = 0; i < refs.length; i++) {
    var url = refs[i].href || refs[i].src || '';
    var idx = url.indexOf('/_kit/');
    if (idx >= 0) return url.slice(0, idx + 1); // includes trailing slash
  }
  // No kit reference found (probably standalone with everything inlined,
  // or an unusual layout). Fall back to page directory.
  return new URL('.', window.location.href).href;
})();

/* ============ HTML-escape helper (module scope) ============ */
function escapeHTML(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ============ Visual Viewport API — pinch-zoom stability ============ *
 * Position: fixed anchors to the layout viewport. On Safari (and Chrome
 * with touch trackpad), pinch-zoom moves the visual viewport
 * independently — fixed elements appear to drift out of the corner the
 * user sees. We translate the chrome buttons by the visual viewport's
 * offset so they stay anchored to where the user looks.
 * --------------------------------------------------------------------- */
(function () {
  var vv = window.visualViewport;
  if (!vv) return;
  function sync() {
    document.documentElement.style.setProperty('--vv-left', vv.offsetLeft + 'px');
    document.documentElement.style.setProperty('--vv-top',  vv.offsetTop  + 'px');
  }
  vv.addEventListener('scroll', sync);
  vv.addEventListener('resize', sync);
  // Browser zoom (Ctrl+/-) fires window.resize but not always
  // visualViewport.resize. Subscribe to both so fixed chrome stays put.
  window.addEventListener('resize', sync);
  sync();
})();

/* ============ Edge-tab proximity sync ============ *
 * Keeps each pane's edge tab glued to that pane's inner boundary as the
 * layout shifts (responsive resize, .nav-collapsed toggle, .toc-collapsed
 * toggle, max-width centering, browser zoom). Writes
 * --nav-tab-left / --toc-tab-right CSS variables that chrome.css reads
 * for the tab's `left` / `right`. Falls back to viewport edges at narrow
 * widths (where panes become drawers — see the @media block in CSS).
 *
 * Proximity rule (~/.claude/rules/design-principles.md): a control that
 * operates on a panel should live on or near that panel's edge — not at
 * the absolute viewport edge with a wide gap of unrelated content between.
 * ----------------------------------------------------------------------- */
(function () {
  // Tab is 22px wide; we want it to overlap the panel's inner edge by 11
  // (half its width) so the tab visually attaches to the panel.
  var OVERHANG = 11;
  var NARROW = 1024;
  var _ro = null;
  function update() {
    var nav = document.querySelector('page-nav');
    var toc = document.querySelector('.layout:has(page-nav) page-toc');
    var narrow = window.innerWidth <= NARROW;
    var rootStyle = document.documentElement.style;
    if (nav && !narrow) {
      var r = nav.getBoundingClientRect();
      rootStyle.setProperty('--nav-tab-left', Math.round(r.right - OVERHANG) + 'px');
    } else {
      rootStyle.setProperty('--nav-tab-left', '0px');
    }
    if (toc && !narrow) {
      var r2 = toc.getBoundingClientRect();
      rootStyle.setProperty('--toc-tab-right', Math.round(window.innerWidth - r2.left - OVERHANG) + 'px');
    } else {
      rootStyle.setProperty('--toc-tab-right', '0px');
    }
  }

  function attach() {
    update();
    var nav = document.querySelector('page-nav');
    var toc = document.querySelector('page-toc');
    // ResizeObserver tracks the panes' size across CSS transitions
    // (the 0.25s grid-template-columns animation when collapsing).
    if (window.ResizeObserver && !_ro) {
      _ro = new ResizeObserver(update);
      if (nav) _ro.observe(nav);
      if (toc) _ro.observe(toc);
    }
    // MutationObserver on the layout/body picks up state-class flips
    // (.nav-collapsed on .layout, .toc-collapsed on body, .open on each pane).
    var mo = new MutationObserver(update);
    var layout = document.querySelector('.layout');
    if (layout) mo.observe(layout, { attributes: true, attributeFilter: ['class'] });
    mo.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    if (nav) mo.observe(nav, { attributes: true, attributeFilter: ['class'] });
    if (toc) mo.observe(toc, { attributes: true, attributeFilter: ['class'] });
  }

  // Resize / zoom / pinch
  window.addEventListener('resize', update);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', update);
    window.visualViewport.addEventListener('scroll', update);
  }
  // Renderer can swap layout mid-flight (JSON pages); rerun then.
  window.addEventListener('html-doc:rendered', update);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attach);
  } else {
    attach();
  }
})();

/* ============ Live-reload (only when served via `html-doc serve`) ============ *
 * Opens an EventSource against /__reload — a Server-Sent Events stream
 * that the dev server pushes a message into whenever a watched file
 * changes. On message, the tab reloads. Only attempted when the page is
 * loaded from localhost/127.0.0.1 so production sites never try.
 * --------------------------------------------------------------------------- */
(function () {
  if (typeof window === 'undefined') return;
  var h = window.location && window.location.hostname;
  if (h !== 'localhost' && h !== '127.0.0.1' && h !== '::1') return;
  if (window.__htmldocReloadAttached) return;
  window.__htmldocReloadAttached = true;
  try {
    var es = new EventSource('/__reload');
    es.addEventListener('message', function () {
      try { es.close(); } catch (e) {}
      window.location.reload();
    });
    // Silently let the browser auto-reconnect on transient errors.
    es.addEventListener('error', function () { /* swallow */ });
  } catch (e) { /* SSE unsupported or blocked — no live reload */ }
})();

/* ============ Tooltip controller (used by <glossary-term> + <ext-ref>) ============ */
var __htmldocTooltip = (function () {
  var HIDE_DELAY = 300;
  var SHOW_DELAY = 120;
  // Re-evaluate on every attach so input-mode changes (e.g., user
  // attaches a mouse to a tablet) take effect on subsequently-rendered
  // elements. Existing attachments keep the wiring they had — acceptable
  // tradeoff vs. listening for matchMedia changes and re-binding.
  function isTouch() { return window.matchMedia('(hover: none)').matches; }
  var active = null; // { trigger, tooltip, pinned }
  var hideTimer = null;
  var showTimer = null;

  function clearTimers() {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    if (showTimer) { clearTimeout(showTimer); showTimer = null; }
  }

  function hideImmediate() {
    clearTimers();
    if (active) { active.tooltip.remove(); active = null; }
  }

  function scheduleHide() {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(hideImmediate, HIDE_DELAY);
  }

  function position(tooltip, trigger) {
    var r = trigger.getBoundingClientRect();
    tooltip.style.position = 'absolute';
    tooltip.style.top = '0px';
    tooltip.style.left = '0px';
    var tipH = tooltip.offsetHeight || 100;
    var tipW = tooltip.offsetWidth || 320;
    var top = r.top + window.scrollY - tipH - 10;
    if (top < window.scrollY + 8) top = r.bottom + window.scrollY + 10;
    var left = r.left + window.scrollX;
    if (left + tipW > window.innerWidth + window.scrollX - 12) {
      left = window.innerWidth + window.scrollX - tipW - 12;
    }
    if (left < 8) left = 8;
    tooltip.style.top  = top + 'px';
    tooltip.style.left = left + 'px';
  }

  // SECURITY: data-def is injected via innerHTML to render rich markup
  // (<strong>, <em>, <br>, inline <a>) inside tooltips. The trust
  // boundary is: data-def must only ever be set by code that reads from
  // kit-controlled sources — _kit/glossary/<domain>.json and
  // _kit/extrefs/<domain>.json. The GlossaryTerm and ExtRef
  // connectedCallback handlers are the only setters; both pull from the
  // kit resolver. Do NOT use this controller to render tooltips with
  // arbitrary author input.
  function build(trigger) {
    var body = trigger.getAttribute('data-def') || trigger.getAttribute('data-summary') || trigger.textContent;
    var link = trigger.getAttribute('data-link');
    var lang = trigger.getAttribute('data-lang-shown');
    var t = document.createElement('div');
    t.className = 'html-doc-tooltip';
    var html = '<div class="hdt-body">' + body + '</div>';
    if (lang) html += '<span class="hdt-lang">' + lang + '</span>';
    if (link) html += '<div class="hdt-link"><a href="' + link + '" target="_blank" rel="noopener">Learn more →</a></div>';
    html += '<span class="hdt-pin-hint">click to pin</span>';
    t.innerHTML = html;
    return t;
  }

  function show(trigger, pinned) {
    clearTimers();
    if (active && active.trigger === trigger) {
      if (pinned) { active.pinned = true; active.tooltip.classList.add('pinned'); }
      return;
    }
    hideImmediate();
    var tip = build(trigger);
    document.body.appendChild(tip);
    position(tip, trigger);
    if (pinned) tip.classList.add('pinned');

    tip.addEventListener('mouseenter', clearTimers);
    tip.addEventListener('mouseleave', function () {
      if (!active || !active.pinned) scheduleHide();
    });

    active = { trigger: trigger, tooltip: tip, pinned: !!pinned };
  }

  function attach(trigger) {
    if (!trigger.hasAttribute('tabindex')) trigger.setAttribute('tabindex', '0');
    if (!isTouch()) {
      trigger.addEventListener('mouseenter', function () {
        clearTimers();
        showTimer = setTimeout(function () { show(trigger, false); }, SHOW_DELAY);
      });
      trigger.addEventListener('mouseleave', function () {
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        if (active && active.trigger === trigger && active.pinned) return;
        scheduleHide();
      });
      trigger.addEventListener('focus', function () { show(trigger, false); });
      trigger.addEventListener('blur', function () {
        if (!active || !active.pinned) scheduleHide();
      });
    }
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      if (active && active.trigger === trigger && active.pinned) {
        hideImmediate();
      } else {
        show(trigger, true);
      }
    });
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.html-doc-tooltip, [data-html-doc-tooltip-trigger]')) hideImmediate();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && active && active.pinned) hideImmediate();
  });

  return { attach: attach, hide: hideImmediate };
})();

/* ============ kit.json loader (multi-domain glossary + ext-refs) ============ */
var __htmldocKit = (function () {
  var kit = { glossary: {}, extrefs: {}, lang: 'en', lang_fallback: ['en'], domains: [] };
  var loaded = false;
  var waiters = [];

  function load() {
    if (loaded) return Promise.resolve(kit);
    // Standalone build — if the build inlined a kit bundle, hydrate from it.
    var bundleTag = document.getElementById('__htmldoc_kit_bundle__');
    if (bundleTag) {
      try {
        var bundle = JSON.parse(bundleTag.textContent || '{}');
        var bk = bundle.kit || {};
        if (bk.lang) kit.lang = bk.lang;
        if (bk.lang_fallback) kit.lang_fallback = bk.lang_fallback;
        if (bk.domains) kit.domains = bk.domains;
        if (bundle.glossary) kit.glossary = bundle.glossary;
        if (bundle.extrefs) kit.extrefs = bundle.extrefs;
        // Project-local overrides from kit.json still apply on top.
        if (bk.glossary) {
          Object.keys(bk.glossary).forEach(function (d) {
            kit.glossary[d] = Object.assign({}, kit.glossary[d] || {}, bk.glossary[d]);
          });
        }
        if (bk.extrefs) {
          Object.keys(bk.extrefs).forEach(function (d) {
            kit.extrefs[d] = Object.assign({}, kit.extrefs[d] || {}, bk.extrefs[d]);
          });
        }
      } catch (e) {
        // Malformed bundle — fall through to empty kit.
      }
      loaded = true;
      waiters.forEach(function (w) { w(kit); });
      waiters = [];
      return Promise.resolve(kit);
    }
    // Standalone without a kit bundle: degrade silently.
    if (document.getElementById('__htmldoc_page__')) {
      loaded = true;
      waiters.forEach(function (w) { w(kit); });
      waiters = [];
      return Promise.resolve(kit);
    }
    // Project config lives at the docs root; domain files live in _kit/.
    return fetch(__htmldocDocsRoot + 'kit.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (data) {
        if (data) {
          if (data.lang) kit.lang = data.lang;
          if (data.lang_fallback) kit.lang_fallback = data.lang_fallback;
          if (data.domains) kit.domains = data.domains;
        }
        // Load each domain file in parallel
        var promises = kit.domains.flatMap(function (d) {
          return [
            fetch(__htmldocDocsRoot + '_kit/glossary/' + d + '.json', { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.glossary[d] = j.entries;
              }),
            fetch(__htmldocDocsRoot + '_kit/extrefs/' + d + '.json', { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.extrefs[d] = j.entries;
              })
          ];
        });
        return Promise.all(promises).then(function () {
          // Apply project-level overrides AFTER central domain files
          // have loaded — otherwise the per-domain fetch .then runs
          // last and wholesale-replaces kit.glossary[d], wiping the
          // override entries.
          if (data && data.glossary) {
            Object.keys(data.glossary).forEach(function (d) {
              kit.glossary[d] = Object.assign({}, kit.glossary[d] || {}, data.glossary[d]);
            });
          }
          if (data && data.extrefs) {
            Object.keys(data.extrefs).forEach(function (d) {
              kit.extrefs[d] = Object.assign({}, kit.extrefs[d] || {}, data.extrefs[d]);
            });
          }
          loaded = true;
          waiters.forEach(function (w) { w(kit); });
          waiters = [];
          return kit;
        });
      });
  }

  function resolveGlossary(term, opts) {
    opts = opts || {};
    var inDomain = opts.in;
    var lang = opts.lang || kit.lang;
    var domains = inDomain ? [inDomain] : kit.domains;
    for (var i = 0; i < domains.length; i++) {
      var d = domains[i];
      var entry = (kit.glossary[d] || {})[term];
      if (entry) {
        var hit = entry[lang];
        var shownLang = lang;
        if (!hit) {
          for (var j = 0; j < kit.lang_fallback.length; j++) {
            hit = entry[kit.lang_fallback[j]];
            if (hit) { shownLang = kit.lang_fallback[j]; break; }
          }
        }
        if (!hit) {
          var any = Object.keys(entry)[0];
          if (any) { hit = entry[any]; shownLang = any; }
        }
        if (hit) return { hit: hit, domain: d, lang: shownLang };
      }
    }
    return null;
  }

  function resolveExtRef(name, opts) {
    opts = opts || {};
    var inDomain = opts.in;
    var lang = opts.lang || kit.lang;
    var domains = inDomain ? [inDomain] : kit.domains;
    for (var i = 0; i < domains.length; i++) {
      var d = domains[i];
      var entry = (kit.extrefs[d] || {})[name];
      if (entry) {
        var hit = entry[lang];
        var shownLang = lang;
        if (!hit) {
          for (var j = 0; j < kit.lang_fallback.length; j++) {
            hit = entry[kit.lang_fallback[j]];
            if (hit) { shownLang = kit.lang_fallback[j]; break; }
          }
        }
        if (!hit) {
          var any = Object.keys(entry)[0];
          if (any) { hit = entry[any]; shownLang = any; }
        }
        if (hit) return { hit: hit, domain: d, lang: shownLang };
      }
    }
    return null;
  }

  function whenReady() {
    if (loaded) return Promise.resolve(kit);
    return new Promise(function (resolve) { waiters.push(resolve); });
  }

  // Defer the initial load until the document is parsed so the standalone
  // detection (looking for the inline page-data script) can see the tag
  // that gets parsed later in body.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }

  return {
    load: load,
    whenReady: whenReady,
    resolveGlossary: resolveGlossary,
    resolveExtRef: resolveExtRef,
    state: function () { return kit; }
  };
})();

/* ============ <glossary-term> Custom Element ============ */
// Standalone builds inline the page but not the glossary; in that mode
// we render the term inline without a tooltip rather than mark every
// term as "unknown". Detected via the inline page-data script.
var __htmldocStandalone = function () {
  return !!document.getElementById('__htmldoc_page__');
};

class GlossaryTerm extends HTMLElement {
  connectedCallback() {
    var self = this;
    this.setAttribute('data-html-doc-tooltip-trigger', '');
    this.classList.add('html-doc-gloss');
    __htmldocKit.whenReady().then(function () {
      var term = self.getAttribute('term') || self.textContent;
      var opts = { in: self.getAttribute('in') || undefined, lang: self.getAttribute('lang') || undefined };
      var r = __htmldocKit.resolveGlossary(term, opts);
      if (r) {
        self.setAttribute('data-def', r.hit.def || '');
        if (r.hit.link) self.setAttribute('data-link', r.hit.link);
        if (r.lang !== (opts.lang || __htmldocKit.state().lang)) {
          self.setAttribute('data-lang-shown', 'lang: ' + r.lang);
        }
        __htmldocTooltip.attach(self);
      } else if (__htmldocStandalone()) {
        // Standalone mode without inline glossary data — render text only.
        self.classList.remove('html-doc-gloss');
      } else {
        self.setAttribute('data-def', '<em>Unknown term:</em> ' + term);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'unknown-glossary-term', msg: 'No entry for "' + term + '"', level: 'warn' }]
        }));
        __htmldocTooltip.attach(self);
      }
    });
  }
}
if (!customElements.get('glossary-term')) customElements.define('glossary-term', GlossaryTerm);

/* ============ <ext-ref> Custom Element ============ */
class ExtRef extends HTMLElement {
  connectedCallback() {
    var self = this;
    this.setAttribute('data-html-doc-tooltip-trigger', '');
    this.classList.add('html-doc-extref');
    __htmldocKit.whenReady().then(function () {
      var name = self.getAttribute('name') || self.textContent;
      var opts = { in: self.getAttribute('in') || undefined, lang: self.getAttribute('lang') || undefined };
      var r = __htmldocKit.resolveExtRef(name, opts);
      if (r) {
        var body = '<strong>' + (r.hit.name || name) + '</strong>';
        if (r.hit.summary) body += '<br>' + r.hit.summary;
        self.setAttribute('data-def', body);
        if (r.hit.link) self.setAttribute('data-link', r.hit.link);
        __htmldocTooltip.attach(self);
      } else if (__htmldocStandalone()) {
        self.classList.remove('html-doc-extref');
      } else {
        self.setAttribute('data-def', '<em>Unknown reference:</em> ' + name);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'unknown-ext-ref', msg: 'No entry for "' + name + '"', level: 'warn' }]
        }));
        __htmldocTooltip.attach(self);
      }
    });
  }
}
if (!customElements.get('ext-ref')) customElements.define('ext-ref', ExtRef);

/* ============ <html-doc-chart> Custom Element ============ *
 * Generic data-driven SVG chart. Scatter and line types.
 * Series data lives in a child <script type="application/json">.
 * For row-per-item horizontal bars, use the bar-chart block instead
 * (handled directly by the renderer for layout-stability reasons).
 * --------------------------------------------------------------- */
class HtmlDocChart extends HTMLElement {
  connectedCallback() {
    var dataNode = this.querySelector('script[type="application/json"]');
    var series = [];
    if (dataNode) {
      try { series = JSON.parse(dataNode.textContent || '[]'); } catch (e) { series = []; }
    }
    var type = this.getAttribute('type') || 'scatter';
    var title = this.getAttribute('title') || '';
    var xLabel = this.getAttribute('x-label') || '';
    var yLabel = this.getAttribute('y-label') || '';

    this.innerHTML = '';
    if (dataNode) this.appendChild(dataNode);

    // Compute bounds
    var allPoints = [];
    series.forEach(function (s) { (s.data || []).forEach(function (p) { allPoints.push(p); }); });
    if (allPoints.length === 0) {
      this.appendChild(document.createTextNode(''));
      return;
    }
    var xs = allPoints.map(function (p) { return p.x; });
    var ys = allPoints.map(function (p) { return p.y; });
    var xMin = Math.min.apply(null, xs), xMax = Math.max.apply(null, xs);
    var yMin = Math.min.apply(null, ys), yMax = Math.max.apply(null, ys);
    if (xMin === xMax) { xMin -= 1; xMax += 1; }
    if (yMin === yMax) { yMin -= 1; yMax += 1; }
    // Pad 5%
    var xPad = (xMax - xMin) * 0.05;
    var yPad = (yMax - yMin) * 0.05;
    xMin -= xPad; xMax += xPad;
    yMin -= yPad; yMax += yPad;

    var W = 640, H = 360;
    var pad = { top: title ? 32 : 16, right: 24, bottom: xLabel ? 50 : 32, left: yLabel ? 56 : 40 };
    var plotW = W - pad.left - pad.right;
    var plotH = H - pad.top - pad.bottom;

    function sx(x) { return pad.left + ((x - xMin) / (xMax - xMin)) * plotW; }
    function sy(y) { return pad.top + plotH - ((y - yMin) / (yMax - yMin)) * plotH; }

    var palette = {
      accent:  'var(--accent)',
      warn:    'var(--warning)',
      danger:  'var(--danger)',
      success: 'var(--success)',
      muted:   'var(--text-soft)'
    };

    var parts = [];
    parts.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + (title || (type + ' chart')) + '" class="hdc-svg">');
    if (title) {
      parts.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="hdc-title">' + escapeXml(title) + '</text>');
    }
    // Axes
    parts.push('<line x1="' + pad.left + '" y1="' + (pad.top + plotH) + '" x2="' + (W - pad.right) + '" y2="' + (pad.top + plotH) + '" class="hdc-axis"/>');
    parts.push('<line x1="' + pad.left + '" y1="' + pad.top + '" x2="' + pad.left + '" y2="' + (pad.top + plotH) + '" class="hdc-axis"/>');
    // Axis labels
    if (xLabel) parts.push('<text x="' + (pad.left + plotW / 2) + '" y="' + (H - 14) + '" text-anchor="middle" class="hdc-axis-label">' + escapeXml(xLabel) + '</text>');
    if (yLabel) parts.push('<text x="' + 14 + '" y="' + (pad.top + plotH / 2) + '" text-anchor="middle" class="hdc-axis-label" transform="rotate(-90 14,' + (pad.top + plotH / 2) + ')">' + escapeXml(yLabel) + '</text>');
    // Ticks (3 per axis)
    for (var t = 0; t <= 4; t++) {
      var xTickVal = xMin + (t / 4) * (xMax - xMin);
      var xTickPos = sx(xTickVal);
      parts.push('<line x1="' + xTickPos + '" y1="' + (pad.top + plotH) + '" x2="' + xTickPos + '" y2="' + (pad.top + plotH + 4) + '" class="hdc-axis"/>');
      parts.push('<text x="' + xTickPos + '" y="' + (pad.top + plotH + 16) + '" text-anchor="middle" class="hdc-tick">' + fmtNum(xTickVal) + '</text>');
      var yTickVal = yMin + (t / 4) * (yMax - yMin);
      var yTickPos = sy(yTickVal);
      parts.push('<line x1="' + (pad.left - 4) + '" y1="' + yTickPos + '" x2="' + pad.left + '" y2="' + yTickPos + '" class="hdc-axis"/>');
      parts.push('<text x="' + (pad.left - 6) + '" y="' + (yTickPos + 4) + '" text-anchor="end" class="hdc-tick">' + fmtNum(yTickVal) + '</text>');
    }
    // Series — each wrapped in a <g data-series-idx> so the legend can
    // toggle its `.dim` class to mute/unmute the series visually.
    series.forEach(function (s, i) {
      var color = palette[s.color] || palette.accent;
      parts.push('<g class="hdc-series" data-series-idx="' + i + '">');
      if (type === 'line') {
        var d = (s.data || []).map(function (p, idx) {
          return (idx === 0 ? 'M ' : 'L ') + sx(p.x) + ' ' + sy(p.y);
        }).join(' ');
        parts.push('<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2" class="hdc-line"/>');
      }
      (s.data || []).forEach(function (p) {
        var dotLabel = escapeXml(String(p.label != null ? p.label : ''));
        var seriesLbl = escapeXml(String(s.label != null ? s.label : ''));
        parts.push(
          '<circle cx="' + sx(p.x) + '" cy="' + sy(p.y) + '" r="4" fill="' + color +
          '" class="hdc-dot"' +
          ' data-x="' + p.x + '" data-y="' + p.y +
          '" data-point-label="' + dotLabel +
          '" data-series-label="' + seriesLbl + '"' +
          ' tabindex="0" role="img" aria-label="' +
            (seriesLbl ? seriesLbl + ': ' : '') + (dotLabel ? dotLabel + ' ' : '') +
            '(' + fmtNum(p.x) + ', ' + fmtNum(p.y) + ')' +
          '"/>'
        );
        if (p.label) {
          parts.push('<text x="' + (sx(p.x) + 8) + '" y="' + (sy(p.y) + 4) + '" class="hdc-point-label">' + escapeXml(p.label) + '</text>');
        }
      });
      parts.push('</g>');
      if (s.label) {
        var lx = W - pad.right - 12;
        var ly = pad.top + 14 + i * 18;
        parts.push(
          '<g class="hdc-legend-chip" data-series-idx="' + i + '" tabindex="0" role="button" ' +
          'aria-label="Toggle ' + escapeXml(s.label) + ' series">' +
            '<rect x="' + (lx - 116) + '" y="' + (ly - 12) + '" width="120" height="20" rx="4" class="hdc-legend-bg"/>' +
            '<rect x="' + (lx - 110) + '" y="' + (ly - 9) + '" width="14" height="14" rx="2" fill="' + color + '" class="hdc-legend-swatch"/>' +
            '<text x="' + (lx - 92) + '" y="' + (ly + 2) + '" class="hdc-legend">' + escapeXml(s.label) + '</text>' +
          '</g>'
        );
      }
    });
    parts.push('</svg>');
    this.insertAdjacentHTML('beforeend', parts.join(''));
    this._wireInteractivity();

    var self = this;
    var chartTitle = title || (type + '-chart');
    __htmldocVisualTools.makeToolbar(this, [
      {
        title: 'Download as PNG',
        icon: ICON_CAMERA,
        run: function (btn) {
          var svg = self.querySelector('.hdc-svg');
          __htmldocVisualTools.svgToPng(svg, chartTitle)
            .then(function () { __htmldocVisualTools.flash(btn, 'ok', ICON_CAMERA); })
            .catch(function () { __htmldocVisualTools.flash(btn, 'fail', ICON_CAMERA); });
        }
      }
    ]);
  }

  _wireInteractivity() {
    var self = this;

    /* Hover tooltip — one shared element per chart, lazily created. */
    function ensureTip() {
      var t = self.querySelector(':scope > .hdc-tooltip');
      if (t) return t;
      t = document.createElement('div');
      t.className = 'hdc-tooltip';
      t.setAttribute('role', 'tooltip');
      t.setAttribute('aria-hidden', 'true');
      self.appendChild(t);
      return t;
    }
    function showTip(dot) {
      var tip = ensureTip();
      var seriesLbl = dot.getAttribute('data-series-label') || '';
      var pointLbl  = dot.getAttribute('data-point-label')  || '';
      var x = dot.getAttribute('data-x');
      var y = dot.getAttribute('data-y');
      var html = '';
      if (seriesLbl) html += '<div class="hdc-tt-series">' + escapeXml(seriesLbl) + '</div>';
      if (pointLbl)  html += '<div class="hdc-tt-label">'  + escapeXml(pointLbl)  + '</div>';
      html += '<div class="hdc-tt-coords">(' + fmtNum(parseFloat(x)) + ', ' + fmtNum(parseFloat(y)) + ')</div>';
      tip.innerHTML = html;
      tip.setAttribute('aria-hidden', 'false');
      var hostRect = self.getBoundingClientRect();
      var dotRect  = dot.getBoundingClientRect();
      var left = (dotRect.left - hostRect.left) + dotRect.width / 2;
      var top  = (dotRect.top  - hostRect.top)  - 8;
      tip.style.left = left + 'px';
      tip.style.top  = top  + 'px';
      tip.classList.add('visible');
    }
    function hideTip() {
      var tip = self.querySelector(':scope > .hdc-tooltip');
      if (tip) { tip.classList.remove('visible'); tip.setAttribute('aria-hidden', 'true'); }
    }
    this.querySelectorAll('.hdc-dot').forEach(function (dot) {
      dot.addEventListener('mouseenter', function () { showTip(dot); });
      dot.addEventListener('mouseleave', hideTip);
      dot.addEventListener('focus',      function () { showTip(dot); });
      dot.addEventListener('blur',       hideTip);
    });

    /* Legend chip — click or Enter/Space toggles `.dim` on the matching
       <g class="hdc-series"> so the user can mute series visually. */
    function toggleSeries(chip) {
      var idx = chip.getAttribute('data-series-idx');
      var series = self.querySelector('.hdc-series[data-series-idx="' + idx + '"]');
      if (!series) return;
      var on = series.classList.toggle('dim');
      chip.classList.toggle('off', on);
      chip.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
    this.querySelectorAll('.hdc-legend-chip').forEach(function (chip) {
      chip.setAttribute('aria-pressed', 'false');
      chip.addEventListener('click', function () { toggleSeries(chip); });
      chip.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggleSeries(chip);
        }
      });
    });
  }
}
if (!customElements.get('html-doc-chart')) customElements.define('html-doc-chart', HtmlDocChart);

function escapeXml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function fmtNum(n) {
  if (n === undefined || n === null) return '';
  var abs = Math.abs(n);
  if (abs >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  if (abs >= 10) return n.toFixed(0);
  if (abs >= 1) return n.toFixed(1).replace(/\.0$/, '');
  return n.toFixed(2);
}

/* ============ Visual-tools toolbar (diagrams + charts) ============ *
 * Shared helpers for icon-only Copy / Screenshot buttons on charts and
 * diagrams. Toolbar reveals on hover/focus-within; buttons flash green
 * (success) or red (failure) for 1.5s.
 * -------------------------------------------------------------------- */
var __htmldocVisualTools = (function () {
  function flash(btn, kind, restoreIcon) {
    var icon = kind === 'ok' ? ICON_CHECK : ICON_CROSS;
    var cls  = kind === 'ok' ? 'flash-ok' : 'flash-fail';
    btn.innerHTML = icon;
    btn.classList.add(cls);
    setTimeout(function () {
      btn.classList.remove(cls);
      btn.innerHTML = restoreIcon;
    }, 1500);
  }

  function copyText(btn, text, restoreIcon) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text)
      .then(function () { flash(btn, 'ok', restoreIcon); })
      .catch(function () { flash(btn, 'fail', restoreIcon); });
  }

  function slugifyFilename(s) {
    return String(s || 'diagram')
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60) || 'diagram';
  }

  /* Render an SVG element to PNG and trigger a download.
     CSS variables don't survive serialization (they resolve against
     the document, not the cloned SVG), so we inline currentColor and
     a fixed --bg fallback. 2× DPR for crisp output. */
  function svgToPng(svgEl, filename) {
    if (!svgEl) { return Promise.reject(new Error('no svg')); }
    return new Promise(function (resolve, reject) {
      try {
        var bbox = svgEl.getBoundingClientRect();
        var w = bbox.width || (svgEl.viewBox && svgEl.viewBox.baseVal && svgEl.viewBox.baseVal.width)  || 800;
        var h = bbox.height || (svgEl.viewBox && svgEl.viewBox.baseVal && svgEl.viewBox.baseVal.height) || 600;

        // Clone so we don't mutate the live diagram.
        var clone = svgEl.cloneNode(true);
        if (!clone.getAttribute('xmlns')) {
          clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        }
        if (!clone.getAttribute('width'))  clone.setAttribute('width',  w);
        if (!clone.getAttribute('height')) clone.setAttribute('height', h);
        // Inline computed CSS so var(--token) usages resolve through the
        // browser before serialization.
        inlineComputedStyles(svgEl, clone);

        var xml = new XMLSerializer().serializeToString(clone);
        var bg  = getComputedStyle(document.body).backgroundColor || '#ffffff';
        var blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var img = new Image();
        img.onload = function () {
          var scale = Math.max(window.devicePixelRatio || 1, 2);
          var canvas = document.createElement('canvas');
          canvas.width  = Math.round(w * scale);
          canvas.height = Math.round(h * scale);
          var ctx = canvas.getContext('2d');
          ctx.fillStyle = bg;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.setTransform(scale, 0, 0, scale, 0, 0);
          ctx.drawImage(img, 0, 0, w, h);
          URL.revokeObjectURL(url);
          canvas.toBlob(function (pngBlob) {
            if (!pngBlob) { reject(new Error('toBlob failed')); return; }
            var a = document.createElement('a');
            a.href = URL.createObjectURL(pngBlob);
            a.download = slugifyFilename(filename) + '.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function () { URL.revokeObjectURL(a.href); }, 100);
            resolve();
          }, 'image/png');
        };
        img.onerror = function (e) { URL.revokeObjectURL(url); reject(e); };
        img.src = url;
      } catch (e) { reject(e); }
    });
  }

  /* Inline computed styles from a live element tree onto a clone so
     CSS-variable-driven colors survive serialization. Walks both trees
     in lockstep. Property list kept short; pulling all of getComputedStyle
     bloats the SVG and slows large diagrams. */
  var STYLE_PROPS = ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'font-family', 'font-size', 'font-weight', 'text-anchor', 'color', 'opacity'];
  function inlineComputedStyles(live, clone) {
    if (!live || !clone) return;
    if (live.nodeType === 1 && clone.nodeType === 1) {
      var cs = getComputedStyle(live);
      var s = '';
      for (var i = 0; i < STYLE_PROPS.length; i++) {
        var v = cs.getPropertyValue(STYLE_PROPS[i]);
        if (v && v !== 'normal' && v !== 'none' && v !== '') {
          s += STYLE_PROPS[i] + ':' + v + ';';
        }
      }
      if (s) {
        var existing = clone.getAttribute('style') || '';
        clone.setAttribute('style', s + existing);
      }
    }
    var lc = live.children, cc = clone.children;
    if (!lc || !cc) return;
    for (var j = 0; j < lc.length && j < cc.length; j++) {
      inlineComputedStyles(lc[j], cc[j]);
    }
  }

  function makeToolbar(host, actions) {
    if (!host) return null;
    var existing = host.querySelector(':scope > .hdt-bar');
    if (existing) existing.remove();
    host.classList.add('hdt-host');
    var bar = document.createElement('div');
    bar.className = 'hdt-bar';
    actions.forEach(function (a) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.title = a.title;
      btn.setAttribute('aria-label', a.title);
      btn.innerHTML = a.icon;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        try { a.run(btn); }
        catch (err) { flash(btn, 'fail', a.icon); }
      });
      bar.appendChild(btn);
    });
    host.appendChild(bar);
    return bar;
  }

  return { makeToolbar: makeToolbar, copyText: copyText, svgToPng: svgToPng, flash: flash };
})();

/* ============ Prism syntax highlighter (lazy CDN) ============ *
 * Loads Prism.js + autoloader on first call. Autoloader fetches
 * per-language components on demand, so this page-level script
 * stays small and Prism only pays for languages the page actually
 * uses. Tokens themed via chrome.css custom properties — no second
 * Prism theme stylesheet needed.
 * --------------------------------------------------------------- */
var __prismLoader = (function () {
  var loadPromise = null;
  var VERSION = '1.29.0';
  var CDN = 'https://cdn.jsdelivr.net/npm/prismjs@' + VERSION + '/';

  function ensureScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.crossOrigin = 'anonymous';
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error('failed to load ' + src)); };
      document.head.appendChild(s);
    });
  }

  function load() {
    if (loadPromise) return loadPromise;
    // Set the manual flag BEFORE prism.min.js runs so Prism doesn't
    // auto-highlight on DOMContentLoaded — we control the timing.
    window.Prism = window.Prism || {};
    window.Prism.manual = true;

    loadPromise = ensureScript(CDN + 'prism.min.js')
      .then(function () {
        return ensureScript(CDN + 'plugins/autoloader/prism-autoloader.min.js');
      })
      .then(function () {
        if (window.Prism && window.Prism.plugins && window.Prism.plugins.autoloader) {
          window.Prism.plugins.autoloader.languages_path = CDN + 'components/';
        }
        return window.Prism;
      });
    return loadPromise;
  }

  function highlightAll(root) {
    // Skip if no language-tagged blocks exist on the page — saves the
    // CDN round-trip for plain-text-only pages.
    var ctx = root || document;
    var blocks = ctx.querySelectorAll('code[class*="language-"]');
    if (!blocks.length) return Promise.resolve();
    return load().then(function (Prism) {
      if (Prism && typeof Prism.highlightAllUnder === 'function') {
        Prism.highlightAllUnder(ctx);
      } else if (Prism && typeof Prism.highlightAll === 'function') {
        Prism.highlightAll();
      }
    }).catch(function (e) {
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'prism-load-failed', msg: 'Could not load Prism: ' + (e.message || e), level: 'info' }]
      }));
    });
  }
  return { load: load, highlightAll: highlightAll };
})();

/* ============ <html-doc-diagram> — Mermaid (lazy-loaded) ============ */
var __mermaidLoader = (function () {
  var loadPromise = null;
  // SUPPLY-CHAIN NOTE: this loads Mermaid from a CDN at runtime. The
  // @10 pin allows any 10.x update from jsDelivr — acceptable for a
  // personal tool, exposed for any hosted deployment. For strict
  // integrity, pin to a fully-qualified version and add an integrity
  // attribute. Procedure:
  //   1. Pick a version, e.g. mermaid@10.9.4
  //   2. Visit https://www.srihash.org/ — paste the jsDelivr URL,
  //      copy the sha384 hash
  //   3. Replace script.src below with the pinned URL
  //   4. Set script.integrity = 'sha384-...' (from step 2)
  //   5. Set script.crossOrigin = 'anonymous'  (required for SRI to work)
  function load() {
    if (loadPromise) return loadPromise;
    loadPromise = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
      script.async = true;
      // To enable SRI: set script.integrity = 'sha384-...';
      //                set script.crossOrigin = 'anonymous';
      script.onload = function () {
        try {
          window.mermaid.initialize({
            startOnLoad: false,
            theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'default',
            fontFamily: 'Inter, sans-serif'
          });
          resolve(window.mermaid);
        } catch (e) { reject(e); }
      };
      script.onerror = function () { reject(new Error('Mermaid CDN load failed')); };
      document.head.appendChild(script);
    });
    return loadPromise;
  }
  // Re-initialize Mermaid on theme toggle so diagrams pick up dark/light tokens.
  function reset() {
    if (!loadPromise || !window.mermaid) return;
    window.mermaid.initialize({
      startOnLoad: false,
      theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'default',
      fontFamily: 'Inter, sans-serif'
    });
  }
  return { load: load, reset: reset };
})();

class HtmlDocDiagram extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/x-mermaid"]');
    var src = srcNode ? srcNode.textContent.trim() : '';
    var caption = this.getAttribute('caption') || '';
    this.classList.add('hdd-wrap');
    this.innerHTML =
      '<div class="hdd-render" aria-label="Diagram loading">Rendering…</div>' +
      (caption ? '<figcaption class="hdd-caption">' + escapeXml(caption) + '</figcaption>' : '');
    var renderHost = this.querySelector('.hdd-render');
    var self = this;
    this._src = src;
    __mermaidLoader.load()
      .then(function (mermaid) {
        var id = 'hdd-' + Math.random().toString(36).slice(2, 9);
        return mermaid.render(id, src).then(function (out) {
          renderHost.innerHTML = out.svg;
          self._rendered = true;
          self._attachToolbar();
        });
      })
      .catch(function (err) {
        renderHost.innerHTML = '<pre class="hdd-fallback">' + escapeXml(src) + '</pre>';
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'mermaid-render-failed', msg: String(err.message || err), level: 'warn' }]
        }));
      });
  }
  _attachToolbar() {
    var self = this;
    var caption = this.getAttribute('caption') || 'diagram';
    __htmldocVisualTools.makeToolbar(this, [
      {
        title: 'Copy diagram source',
        icon: ICON_CLIPBOARD,
        run: function (btn) {
          __htmldocVisualTools.copyText(btn, self._src || '', ICON_CLIPBOARD);
        }
      },
      {
        title: 'Copy rendered SVG markup',
        icon: ICON_BRACES,
        run: function (btn) {
          var svg = self.querySelector('.hdd-render svg');
          if (!svg) { __htmldocVisualTools.flash(btn, 'fail', ICON_BRACES); return; }
          var xml = new XMLSerializer().serializeToString(svg);
          __htmldocVisualTools.copyText(btn, xml, ICON_BRACES);
        }
      },
      {
        title: 'Download as PNG',
        icon: ICON_CAMERA,
        run: function (btn) {
          var svg = self.querySelector('.hdd-render svg');
          __htmldocVisualTools.svgToPng(svg, caption || 'diagram')
            .then(function () { __htmldocVisualTools.flash(btn, 'ok', ICON_CAMERA); })
            .catch(function () { __htmldocVisualTools.flash(btn, 'fail', ICON_CAMERA); });
        }
      }
    ]);
  }
  rerender() {
    if (!this._src) return;
    var renderHost = this.querySelector('.hdd-render');
    var self = this;
    __mermaidLoader.reset();
    __mermaidLoader.load().then(function (mermaid) {
      var id = 'hdd-' + Math.random().toString(36).slice(2, 9);
      return mermaid.render(id, self._src).then(function (out) {
        renderHost.innerHTML = out.svg;
        self._attachToolbar();
      });
    }).catch(function () { /* swallow */ });
  }
}
if (!customElements.get('html-doc-diagram')) customElements.define('html-doc-diagram', HtmlDocDiagram);

// Re-render every diagram on theme toggle so colors track the theme.
window.addEventListener('html-doc:theme-changed', function () {
  document.querySelectorAll('html-doc-diagram').forEach(function (d) {
    if (typeof d.rerender === 'function') d.rerender();
  });
});

/* ============ <html-doc-snippet> — editable HTML/CSS/JS playground ============ */
class HtmlDocSnippet extends HTMLElement {
  connectedCallback() {
    var srcNode = this.querySelector('script[type="text/plain"]');
    var source = srcNode ? srcNode.textContent : '';
    // Trim a single leading newline if present (common in JSON-encoded multi-line strings)
    source = source.replace(/^\n/, '');
    var label = this.getAttribute('label') || 'Editable code · live preview';

    this.classList.add('hds-wrap');
    this.innerHTML =
      '<div class="hds-header">' +
        '<span class="hds-label">' + escapeXml(label) + '</span>' +
        '<button type="button" class="hds-reset" aria-label="Reset to original">Reset</button>' +
      '</div>' +
      '<div class="hds-body">' +
        '<textarea class="hds-editor" spellcheck="false" aria-label="Code"></textarea>' +
        '<iframe class="hds-preview" sandbox="allow-scripts" aria-label="Preview"></iframe>' +
      '</div>';
    var editor = this.querySelector('.hds-editor');
    var preview = this.querySelector('.hds-preview');
    var reset = this.querySelector('.hds-reset');
    var original = source;
    editor.value = source;

    var t = null;
    function render() {
      preview.srcdoc = editor.value;
    }
    editor.addEventListener('input', function () {
      if (t) clearTimeout(t);
      t = setTimeout(render, 220);
    });
    reset.addEventListener('click', function () {
      editor.value = original;
      render();
    });
    render();
  }
}
if (!customElements.get('html-doc-snippet')) customElements.define('html-doc-snippet', HtmlDocSnippet);

/* ============ <page-nav> Custom Element ============ *
 * Loads site-manifest.json from the docs root (adjacent to the page)
 * and renders a collapsible tree of pages. Active page highlighted
 * based on location.pathname. Carries its own edge-tab toggle on the
 * right inner edge (proximity rule).
 * ----------------------------------------------------------------- */
class PageNav extends HTMLElement {
  connectedCallback() {
    var title = this.getAttribute('title') || 'Pages';
    this.innerHTML =
      '<div class="page-nav-panel">' +
        '<div class="page-nav-header"><h2>' + title + '</h2></div>' +
        '<ol class="page-nav-tree"><li class="page-nav-loading">Loading…</li></ol>' +
      '</div>' +
      '<button class="page-nav-tab" type="button" aria-label="Toggle pages">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 6 9 12 15 18"/></svg>' +
      '</button>';
    var self = this;
    this.querySelector('.page-nav-tab').addEventListener('click', function () {
      var layout = self.closest('.layout');
      if (window.innerWidth <= 1024) {
        self.classList.toggle('open');
      } else if (layout) {
        layout.classList.toggle('nav-collapsed');
        try { localStorage.setItem('pageNavCollapsed', layout.classList.contains('nav-collapsed') ? '1' : '0'); } catch (e) {}
      }
    });
    // Restore desktop collapsed state
    var layout = this.closest('.layout');
    if (layout) {
      try {
        if (localStorage.getItem('pageNavCollapsed') === '1') layout.classList.add('nav-collapsed');
      } catch (e) {}
    }
    // Close mobile drawer on Esc
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') self.classList.remove('open');
    });

    // Defer until the document is fully parsed so we can reliably detect
    // the standalone-build inline page-data script (which sits at the
    // end of body, after <page-nav>).
    function start() {
      if (document.getElementById('__htmldoc_page__')) {
        self.style.display = 'none';
        return;
      }
      fetch(__htmldocDocsRoot + 'site-manifest.json', { cache: 'no-cache' })
        .then(function (r) {
          if (r.ok) return r.json();
          // Differentiate "served but missing" from network error so the
          // warning channel can offer a specific remediation hint.
          var err = new Error('manifest http ' + r.status);
          err.__htmldocManifestStatus = r.status;
          throw err;
        })
        .then(function (manifest) {
          self._renderTree(manifest);
        })
        .catch(function (e) {
          self._renderTree(null);
          window.dispatchEvent(new CustomEvent('html-doc:warnings', {
            detail: [{
              code: 'manifest-fetch-failed',
              msg: 'Could not load site-manifest.json' +
                   (e && e.__htmldocManifestStatus ? ' (HTTP ' + e.__htmldocManifestStatus + ')' : '') +
                   ' — run `html-doc build` to regenerate it.',
              level: 'warn'
            }]
          }));
        });
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start);
    } else {
      start();
    }
  }

  _renderTree(manifest) {
    var tree = this.querySelector('.page-nav-tree');
    if (!tree) return;
    tree.innerHTML = '';
    if (!manifest) {
      // Fetch failed — the catch handler in start() already dispatched a
      // specific warning. Just show inline placeholder.
      tree.innerHTML = '<li class="page-nav-empty">No site-manifest.json found. Run <code>html-doc build</code>.</li>';
      return;
    }
    if (!Array.isArray(manifest.pages)) {
      tree.innerHTML = '<li class="page-nav-empty">site-manifest.json is malformed (no <code>pages</code> array). Run <code>html-doc build</code>.</li>';
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'manifest-malformed', msg: 'site-manifest.json missing pages[]', level: 'warn' }]
      }));
      return;
    }
    if (manifest.schema_version && manifest.schema_version > 1) {
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'manifest-schema-future', msg: 'site-manifest.schema_version=' + manifest.schema_version + ' newer than this kit (1)', level: 'warn' }]
      }));
    }

    var pages = manifest.pages.slice();
    pages.sort(function (a, b) {
      var oa = a.order !== undefined ? a.order : 1000;
      var ob = b.order !== undefined ? b.order : 1000;
      if (oa !== ob) return oa - ob;
      return (a.title || a.path).localeCompare(b.title || b.path);
    });

    // Group by parent folder, build a folder→pages map.
    var byParent = {};
    pages.forEach(function (p) {
      var key = p.parent || '';
      if (!byParent[key]) byParent[key] = [];
      byParent[key].push(p);
    });

    var here = window.location.pathname;
    function isActive(page) {
      // page.path is project-relative (e.g., "iceberg.html"); the URL
      // path may include a longer prefix. Endswith catches the common case.
      return here.endsWith('/' + page.path);
    }

    function renderLevel(parentKey, depth) {
      var ol = document.createElement('ol');
      ol.className = 'page-nav-level depth-' + depth;
      var items = byParent[parentKey] || [];
      items.forEach(function (page) {
        var li = document.createElement('li');
        li.className = 'page-nav-item';
        var anchor = document.createElement('a');
        anchor.href = relativizeHref(here, page.path);
        anchor.textContent = page.title || page.path;
        if (page.summary) anchor.title = page.summary;
        if (isActive(page)) {
          li.classList.add('active');
          anchor.setAttribute('aria-current', 'page');
        }
        li.appendChild(anchor);
        // Children are pages whose parent is the path-without-extension OR a folder ancestor.
        // We treat sub-folders: build a key based on this page's folder if any pages declare it.
        var childFolder = page.path.replace(/\.[^/]+$/, '');
        if (byParent[childFolder] && byParent[childFolder].length) {
          li.appendChild(renderLevel(childFolder, depth + 1));
        }
        ol.appendChild(li);
      });
      // Folders that have no own page but have children
      Object.keys(byParent).forEach(function (folder) {
        if (folder === parentKey || folder === '' || folder.indexOf(parentKey === '' ? '' : parentKey + '/') !== 0) return;
        // Direct child folder of parentKey
        var rest = parentKey === '' ? folder : folder.slice(parentKey.length + 1);
        if (rest.indexOf('/') !== -1) return; // not a direct child
        // Skip if already rendered as a page above
        if (byParent[parentKey].some(function (p) { return p.path.replace(/\.[^/]+$/, '') === folder; })) return;
        var li = document.createElement('li');
        li.className = 'page-nav-item folder';
        var label = document.createElement('div');
        label.className = 'page-nav-folder';
        label.textContent = rest;
        li.appendChild(label);
        li.appendChild(renderLevel(folder, depth + 1));
        ol.appendChild(li);
      });
      return ol;
    }

    var root = renderLevel('', 0);
    tree.appendChild(root);
  }
}
if (!customElements.get('page-nav')) customElements.define('page-nav', PageNav);

function relativizeHref(fromUrl, toPath) {
  // fromUrl is location.pathname like /a/b/c.html; toPath is the manifest entry like "spark.html" or "storage/iceberg.html".
  // Compute relative href from the directory of fromUrl to toPath.
  var fromDir = fromUrl.replace(/[^/]*$/, ''); // ends in '/'
  // Strip leading slash from fromDir for relative computation.
  // Use URL constructor for correctness:
  try {
    var base = new URL(fromDir, window.location.origin);
    var target = new URL(toPath, base);
    // Compute relative from base.pathname to target.pathname
    var fromParts = base.pathname.split('/');
    var toParts = target.pathname.split('/');
    fromParts.pop(); // last is empty
    var i = 0;
    while (i < fromParts.length && i < toParts.length && fromParts[i] === toParts[i]) i++;
    var up = fromParts.length - i;
    var rest = toParts.slice(i).join('/');
    return (up > 0 ? '../'.repeat(up) : './') + rest;
  } catch (e) {
    return toPath;
  }
}

/* ============ Forward-compat warning indicator ============ *
 * One indicator regardless of error count. Sits in the top-right
 * system cluster. Click reveals a panel listing entries with code +
 * message. Per-session dismiss; reappears on next load if errors
 * persist.
 * ----------------------------------------------------------------- */
var __htmldocWarnings = (function () {
  var list = [];
  var dismissed = false;
  var btn = null;
  var panel = null;

  function ensureBtn() {
    if (btn) return btn;
    btn = document.createElement('button');
    btn.className = 'ctrl-btn warning-indicator';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'View warnings');
    btn.title = 'View warnings';
    btn.style.display = 'none';
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    document.body.appendChild(btn);
    btn.addEventListener('click', function () {
      if (panel && panel.parentNode) {
        panel.parentNode.removeChild(panel);
        panel = null;
      } else {
        renderPanel();
      }
    });
    return btn;
  }

  function renderPanel() {
    panel = document.createElement('div');
    panel.className = 'warning-panel';
    var html = '<header><strong>' + list.length + ' warning' + (list.length === 1 ? '' : 's') + '</strong>' +
               '<button type="button" class="warning-panel-dismiss" aria-label="Dismiss for this session">Dismiss</button></header>';
    html += '<ul>';
    list.forEach(function (w) {
      var levelClass = (w.level === 'error') ? 'level-error' : 'level-warn';
      html += '<li class="' + levelClass + '"><code>' + (w.code || 'warn') + '</code> ' + escapeHTML(w.msg || '') + '</li>';
    });
    html += '</ul>';
    panel.innerHTML = html;
    document.body.appendChild(panel);
    panel.querySelector('.warning-panel-dismiss').addEventListener('click', function () {
      dismissed = true;
      hide();
      if (panel && panel.parentNode) { panel.parentNode.removeChild(panel); panel = null; }
    });
  }

  function refresh() {
    if (dismissed || list.length === 0) {
      hide();
      return;
    }
    ensureBtn();
    btn.style.display = 'flex';
    btn.setAttribute('data-count', String(list.length));
  }

  function hide() {
    if (btn) btn.style.display = 'none';
    if (panel && panel.parentNode) { panel.parentNode.removeChild(panel); panel = null; }
  }

  function push(entries) {
    entries.forEach(function (w) { list.push(w); });
    refresh();
  }

  // Capture standard error channels too
  window.addEventListener('error', function (e) {
    push([{ code: 'window-error', msg: (e.message || 'unknown') + ' @ ' + (e.filename || '?') + ':' + (e.lineno || 0), level: 'error' }]);
  });
  window.addEventListener('unhandledrejection', function (e) {
    push([{ code: 'unhandled-rejection', msg: String((e && e.reason && e.reason.message) || e.reason || 'unknown'), level: 'error' }]);
  });

  return { push: push };
})();

window.addEventListener('html-doc:warnings', function (e) {
  if (e && e.detail) __htmldocWarnings.push(e.detail);
});

/* ============ Pagefind search ============ *
 * Search button in the top-right system cluster opens a modal with
 * an input + result list. Pagefind is loaded lazily on first invoke;
 * if the bundle is absent (e.g., dev mode without a build) the modal
 * shows a graceful message.
 * ----------------------------------------------------------------- */
var __htmldocSearch = (function () {
  var pagefindPromise = null;
  var modal = null;
  var btn = null;

  function loadPagefind() {
    if (pagefindPromise) return pagefindPromise;
    // Resolve pagefind relative to the kit. _kit/../pagefind covers both
    // the standalone-build layout (where pagefind sits next to the HTML)
    // and a custom override.
    // ES dynamic import needs a relative-resolved URL ('./...') or absolute.
    // Pagefind index lives at the docs root (next to kit.json + site-manifest.json).
    var candidates = [
      __htmldocDocsRoot + 'pagefind/pagefind.js',
      __htmldocDocsRoot + '_kit/pagefind/pagefind.js'
    ];
    pagefindPromise = candidates.reduce(function (acc, abs) {
      return acc.catch(function () {
        return import(/* @vite-ignore */ abs).then(function (mod) {
          if (mod && mod.search) return mod;
          throw new Error('pagefind module shape unexpected');
        });
      });
    }, Promise.reject(new Error('init')));
    return pagefindPromise;
  }

  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'search-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Search');
    modal.innerHTML =
      '<div class="search-backdrop"></div>' +
      '<div class="search-panel">' +
        '<header class="search-header">' +
          '<input type="search" class="search-input" placeholder="Search the site…" aria-label="Search query" autocomplete="off">' +
          '<button type="button" class="search-close" aria-label="Close">Esc</button>' +
        '</header>' +
        '<div class="search-status"></div>' +
        '<ul class="search-results"></ul>' +
      '</div>';
    document.body.appendChild(modal);
    var input = modal.querySelector('.search-input');
    var status = modal.querySelector('.search-status');
    var resultsEl = modal.querySelector('.search-results');

    var t = null;
    input.addEventListener('input', function () {
      if (t) clearTimeout(t);
      var query = input.value.trim();
      if (!query) {
        resultsEl.innerHTML = '';
        status.textContent = '';
        return;
      }
      t = setTimeout(function () { runSearch(query, status, resultsEl); }, 180);
    });
    modal.querySelector('.search-backdrop').addEventListener('click', hide);
    modal.querySelector('.search-close').addEventListener('click', hide);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('open')) hide();
    });

    // Focus trap — keep Tab / Shift-Tab inside the panel while the modal
    // is open. Keyboard-only and screen-reader users otherwise tab into
    // the document behind the backdrop.
    modal.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab' || !modal.classList.contains('open')) return;
      var focusables = modal.querySelectorAll(
        'input, button, a[href], [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });

    return modal;
  }

  function runSearch(query, status, resultsEl) {
    status.textContent = 'Searching…';
    resultsEl.innerHTML = '';
    loadPagefind()
      .then(function (pagefind) {
        return pagefind.search(query);
      })
      .then(function (search) {
        if (!search.results.length) {
          status.textContent = 'No results.';
          return;
        }
        status.textContent = search.results.length + ' result' + (search.results.length === 1 ? '' : 's');
        // Resolve top 10 results' data
        return Promise.all(search.results.slice(0, 10).map(function (r) { return r.data(); }))
          .then(function (datas) {
            resultsEl.innerHTML = '';
            datas.forEach(function (d) {
              var li = document.createElement('li');
              li.className = 'search-result';
              var url = escapeHTML(d.url || '');
              var title = escapeHTML((d.meta && d.meta.title) ? d.meta.title : (d.url || ''));
              // d.excerpt intentionally raw — Pagefind injects <mark> tags
              // for match highlighting. Source is the index we just built.
              var excerpt = d.excerpt || '';
              li.innerHTML =
                '<a href="' + url + '">' +
                  '<div class="search-result-title">' + title + '</div>' +
                  '<div class="search-result-excerpt">' + excerpt + '</div>' +
                '</a>';
              resultsEl.appendChild(li);
            });
          });
      })
      .catch(function (err) {
        var msg = String((err && err.message) || err);
        if (/pagefind|404|404|Not Found|fetch/i.test(msg)) {
          status.innerHTML = 'Search index not found. Run <code>html-doc build</code> and view from <code>dist/site/</code>.';
        } else {
          status.textContent = 'Search error: ' + msg;
        }
      });
  }

  var _focusBeforeOpen = null;
  function show() {
    _focusBeforeOpen = document.activeElement;
    var m = ensureModal();
    m.classList.add('open');
    var input = m.querySelector('.search-input');
    setTimeout(function () { input.focus(); }, 20);
  }
  function hide() {
    if (modal) modal.classList.remove('open');
    if (_focusBeforeOpen && typeof _focusBeforeOpen.focus === 'function') {
      _focusBeforeOpen.focus();
      _focusBeforeOpen = null;
    }
  }

  function addButton() {
    if (btn) return;
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ctrl-btn search-toggle';
    btn.setAttribute('aria-label', 'Search (Cmd/Ctrl+K)');
    btn.title = 'Search (⌘K)';
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>';
    document.body.appendChild(btn);
    btn.addEventListener('click', show);
  }

  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    if ((e.metaKey || e.ctrlKey) && k === 'k') {
      e.preventDefault();
      show();
    }
  });

  return { addButton: addButton, show: show };
})();

document.addEventListener('DOMContentLoaded', function () { __htmldocSearch.addButton(); });

/* ============ Rebuild TOC after JSON renderer completes ============ */
window.addEventListener('html-doc:rendered', function () {
  var tocList = document.querySelector('page-toc .toc-list');
  if (tocList) buildTOC(tocList);
  initReadingAids();
});
