/* AI website template interaction contract: effects are opt-in and motion-safe. */
(function () {
  'use strict';

  var body = document.body;
  if (!body || body.getAttribute('data-site-template') !== 'openchecklists') return;

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var selector = [
    '[data-scroll-effect]',
    'main > section:not(.hero-video)',
    'main > article',
    'main > .card',
    'main > .cards',
    'main > h1',
    'main > h2',
    'main > .lede',
    'main > .search',
    '.wrap > section:not(.hero-video)',
    '.wrap > h1',
    '.wrap > .banner',
    '#ap-root > h1',
    '#ap-root > section',
    '#ap-root > .hero',
    '#main-col > .panel.active',
    '.page > .guest-notice',
    '#signin-prompt',
    '.panel.active > .card',
    '#profile-content > section',
    'body > section.sec',
    'body > section.reviews'
  ].join(',');
  var observer = null;

  if (!reduceMotion && 'IntersectionObserver' in window) {
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: .06 });
  }

  var prepared = 0;
  function prepare(root) {
    var nodes = [];
    if (root.nodeType === 1 && root.matches(selector)) nodes.push(root);
    if (root.querySelectorAll) nodes = nodes.concat(Array.prototype.slice.call(root.querySelectorAll(selector)));
    nodes.forEach(function (node) {
      if (node.getAttribute('data-template-motion-ready') === 'true') return;
      node.setAttribute('data-template-motion-ready', 'true');
      if (!node.hasAttribute('data-scroll-effect')) node.setAttribute('data-scroll-effect', 'rise');
      node.style.setProperty('--motion-delay', String((prepared++ % 5) * 55) + 'ms');
      if (observer) observer.observe(node);
      else node.classList.add('is-visible');
    });
  }
  prepare(document);

  var mutations = new MutationObserver(function (records) {
    records.forEach(function (record) {
      Array.prototype.forEach.call(record.addedNodes, prepare);
    });
  });
  mutations.observe(body, { childList: true, subtree: true });

  if (!document.querySelector('.hero-video')) {
    var orbit = document.createElement('div');
    orbit.className = 'template-orbit';
    orbit.setAttribute('aria-hidden', 'true');
    body.appendChild(orbit);
  }
})();
