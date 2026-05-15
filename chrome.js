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
