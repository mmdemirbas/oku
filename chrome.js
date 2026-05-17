/* html-doc · chrome.js
 * Web Components, theme cycler, TOC builder, scroll-spy, reading aids.
 * Loaded with defer; chrome-boot.js handles pre-paint state.
 */

/* ============ SVG icon set ============ */
const ICON_MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>';
const ICON_SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><line x1="4.5" y1="4.5" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.5" y2="19.5"/><line x1="4.5" y1="19.5" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.5" y2="4.5"/></svg>';
const ICON_MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const ICON_SYSTEM = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>';
const ICON_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';

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
    requestAnimationFrame(function () { buildTOC(self.querySelector('.toc-list')); });
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

  sections.forEach(function (sec, i) {
    var h2 = sec.querySelector('h2');
    if (!h2) return;
    if (!sec.id) sec.id = 'sec-' + i;

    appendPermalink(h2, sec.id);

    var numEl = h2.querySelector('.num');
    var num = numEl ? numEl.textContent.trim() : (i + 1);
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
function initReadingAids() {
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

  /* Copy-to-clipboard on every <pre> block */
  (function () {
    if (!navigator.clipboard) return;
    document.querySelectorAll('pre').forEach(function (pre) {
      if (pre.querySelector('.copy-btn')) return;
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.textContent = 'Copy';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      pre.appendChild(btn);
      btn.addEventListener('click', function () {
        var code = pre.querySelector('code');
        var text = code ? code.textContent : pre.textContent.replace(/Copy$/, '').trim();
        navigator.clipboard.writeText(text).then(function () {
          btn.textContent = 'Copied';
          btn.classList.add('copied');
          setTimeout(function () { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
        }).catch(function () {
          btn.textContent = 'Error';
          setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
        });
      });
    });
  })();

  /* Glossary tooltip — mobile tap support */
  document.querySelectorAll('.g-wrap').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (window.matchMedia('(hover: none)').matches) {
        e.preventDefault();
        document.querySelectorAll('.g-wrap.open').forEach(function (o) { if (o !== el) o.classList.remove('open'); });
        el.classList.toggle('open');
      }
    });
  });

  /* Escape closes mobile TOC */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var nav = document.querySelector('page-toc, nav.toc');
      if (nav) nav.classList.remove('open');
    }
  });
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
  sync();
})();

/* ============ Tooltip controller (used by <glossary-term> + <ext-ref>) ============ */
var __htmldocTooltip = (function () {
  var HIDE_DELAY = 300;
  var SHOW_DELAY = 120;
  var isTouch = window.matchMedia('(hover: none)').matches;
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
    if (!isTouch) {
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
    // Standalone build: no project kit.json on disk — degrade silently.
    if (document.getElementById('__htmldoc_page__')) {
      loaded = true;
      waiters.forEach(function (w) { w(kit); });
      waiters = [];
      return Promise.resolve(kit);
    }
    // Project config lives next to the page; domain files live in _kit/.
    return fetch('kit.json', { cache: 'no-cache' })
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
            fetch('_kit/glossary/' + d + '.json', { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.glossary[d] = j.entries;
              }),
            fetch('_kit/extrefs/' + d + '.json', { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .catch(function () { return null; })
              .then(function (j) {
                if (j && j.entries) kit.extrefs[d] = j.entries;
              })
          ];
        });
        // Project-level additions / overrides
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
        return Promise.all(promises).then(function () {
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
      } else {
        self.setAttribute('data-def', '<em>Unknown term:</em> ' + term);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'unknown-glossary-term', msg: 'No entry for "' + term + '"', level: 'warn' }]
        }));
      }
      __htmldocTooltip.attach(self);
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
      } else {
        self.setAttribute('data-def', '<em>Unknown reference:</em> ' + name);
        self.classList.add('unknown');
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'unknown-ext-ref', msg: 'No entry for "' + name + '"', level: 'warn' }]
        }));
      }
      __htmldocTooltip.attach(self);
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
    // Series
    series.forEach(function (s, i) {
      var color = palette[s.color] || palette.accent;
      if (type === 'line') {
        var d = (s.data || []).map(function (p, idx) {
          return (idx === 0 ? 'M ' : 'L ') + sx(p.x) + ' ' + sy(p.y);
        }).join(' ');
        parts.push('<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2" class="hdc-line"/>');
      }
      (s.data || []).forEach(function (p) {
        parts.push('<circle cx="' + sx(p.x) + '" cy="' + sy(p.y) + '" r="4" fill="' + color + '" class="hdc-dot"/>');
        if (p.label) {
          parts.push('<text x="' + (sx(p.x) + 8) + '" y="' + (sy(p.y) + 4) + '" class="hdc-point-label">' + escapeXml(p.label) + '</text>');
        }
      });
      if (s.label) {
        var lx = W - pad.right - 12;
        var ly = pad.top + 14 + i * 18;
        parts.push('<rect x="' + (lx - 110) + '" y="' + (ly - 9) + '" width="14" height="14" rx="2" fill="' + color + '"/>');
        parts.push('<text x="' + (lx - 92) + '" y="' + (ly + 2) + '" class="hdc-legend">' + escapeXml(s.label) + '</text>');
      }
    });
    parts.push('</svg>');
    this.insertAdjacentHTML('beforeend', parts.join(''));
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

/* ============ <html-doc-diagram> — Mermaid (lazy-loaded) ============ */
var __mermaidLoader = (function () {
  var loadPromise = null;
  function load() {
    if (loadPromise) return loadPromise;
    loadPromise = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
      script.async = true;
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
        });
      })
      .catch(function (err) {
        renderHost.innerHTML = '<pre class="hdd-fallback">' + escapeXml(src) + '</pre>';
        window.dispatchEvent(new CustomEvent('html-doc:warnings', {
          detail: [{ code: 'mermaid-render-failed', msg: String(err.message || err), level: 'warn' }]
        }));
      });
  }
  rerender() {
    if (!this._src) return;
    var renderHost = this.querySelector('.hdd-render');
    __mermaidLoader.reset();
    __mermaidLoader.load().then(function (mermaid) {
      var id = 'hdd-' + Math.random().toString(36).slice(2, 9);
      return mermaid.render(id, this._src).then(function (out) {
        renderHost.innerHTML = out.svg;
      });
    }.bind(this)).catch(function () { /* swallow */ });
  }
}
if (!customElements.get('html-doc-diagram')) customElements.define('html-doc-diagram', HtmlDocDiagram);

// Re-render every diagram on theme toggle so colors track the theme.
var __htmldocOrigCycleTheme = cycleTheme;
cycleTheme = function () {
  __htmldocOrigCycleTheme();
  document.querySelectorAll('html-doc-diagram').forEach(function (d) {
    if (typeof d.rerender === 'function') d.rerender();
  });
};

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
      fetch('site-manifest.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; })
        .then(function (manifest) {
          self._renderTree(manifest);
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
    if (!manifest || !Array.isArray(manifest.pages)) {
      tree.innerHTML = '<li class="page-nav-empty">No site-manifest.json found. Run <code>html-doc build</code>.</li>';
      window.dispatchEvent(new CustomEvent('html-doc:warnings', {
        detail: [{ code: 'manifest-missing', msg: 'site-manifest.json not loaded', level: 'warn' }]
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

  function escapeHTML(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
    var candidates = ['./pagefind/pagefind.js', './_kit/pagefind/pagefind.js'];
    pagefindPromise = candidates.reduce(function (acc, rel) {
      return acc.catch(function () {
        var abs = new URL(rel, window.location.href).href;
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
              li.innerHTML =
                '<a href="' + d.url + '">' +
                  '<div class="search-result-title">' + (d.meta && d.meta.title ? d.meta.title : d.url) + '</div>' +
                  '<div class="search-result-excerpt">' + (d.excerpt || '') + '</div>' +
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

  function show() {
    var m = ensureModal();
    m.classList.add('open');
    var input = m.querySelector('.search-input');
    setTimeout(function () { input.focus(); }, 20);
  }
  function hide() {
    if (modal) modal.classList.remove('open');
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
