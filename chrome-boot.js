/* html-doc · chrome-boot.js
 * Synchronous pre-paint init: sets theme + TOC state before body renders.
 * Must be the FIRST script in <head>, loaded synchronously (no defer/async).
 * Reads localStorage: 'theme-pref' (light|dark|absent=system), 'tocCollapsed'.
 */
(function () {
  try {
    var pref = localStorage.getItem('theme-pref');
    var mode = (pref === 'light' || pref === 'dark') ? pref : 'system';
    var actual = mode === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : mode;
    document.documentElement.setAttribute('data-theme', actual);
    document.documentElement.setAttribute('data-theme-mode', mode);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
    document.documentElement.setAttribute('data-theme-mode', 'system');
  }
  document.addEventListener('DOMContentLoaded', function () {
    try {
      if (localStorage.getItem('tocCollapsed') === '1' && window.innerWidth > 920) {
        document.body.classList.add('toc-collapsed');
      }
    } catch (e) {}
  });
})();
