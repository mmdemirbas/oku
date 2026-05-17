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
    this.innerHTML =
      '<div class="toc-header"><h2>' + title + '</h2></div>' +
      '<ol class="toc-list"></ol>';
    var self = this;
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

  load();

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

/* ============ Rebuild TOC after JSON renderer completes ============ */
window.addEventListener('html-doc:rendered', function () {
  var tocList = document.querySelector('page-toc .toc-list');
  if (tocList) buildTOC(tocList);
  initReadingAids();
});
window.addEventListener('html-doc:warnings', function (e) {
  // Placeholder hook for the forward-compat warning indicator. The
  // indicator UI lands in a later build step; for now warnings are in
  // the console.
  if (e && e.detail) {
    e.detail.forEach(function (w) { console.warn('[html-doc warning]', w); });
  }
});
