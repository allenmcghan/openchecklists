// Server-rendered community checklists: /checklist/<id>
//
// Community checklists live in the API's D1 database, not in the static build,
// so the site ships ONE client-rendered viewer (/checklist/index.html). That
// template says "Loading checklist…" to a crawler, so this Pages Function
// fetches the public checklist from the API and serves /checklist/<id> with the
// title, description, canonical, structured data and the full item list already
// in the HTML. The viewer script then boots on top (ratings, ticking, forking).
//
// Everything here is user-submitted and untrusted: every interpolation is
// escaped, and replacements use callbacks so "$&"-style patterns in content are
// never interpreted by String.replace.

const ID_RE = /^[a-z0-9][a-z0-9-]{0,119}$/;
// Canonical URLs always point at production, whatever host served the request.
const SITE = 'https://openchecklists.net';
const DEFAULT_API = 'https://app.openchecklists.net';

function esc(v) {
  return String(v == null ? '' : v).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function str(v, max) {
  const s = typeof v === 'string' ? v : (typeof v === 'number' ? String(v) : '');
  return s.replace(/\s+/g, ' ').trim().slice(0, max || 500);
}

function clip(s, n) {
  return s.length <= n ? s : s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…';
}

function apiOrigin(env) {
  return String(env.OCL_API_ORIGIN || DEFAULT_API).replace(/\/+$/, '');
}

async function template(env, origin) {
  const r = await env.ASSETS.fetch(new URL('/checklist/', origin));
  if (!r.ok) throw new Error(`asset /checklist/: ${r.status}`);
  return r.text();
}

const INFO = { note: 'NOTE', caution: 'CAUTION', warning: 'WARNING' };
const TICKABLE = { action: 1, challenge: 1 };

// Mirrors the viewer's renderItem() so the client re-render is a no-op visually.
function itemHtml(it, secId, idx) {
  if (!it || typeof it !== 'object') return '';
  const t = str(it.type, 20) || 'challenge';
  if (t === 'blank') return '<li class="cv-blank"></li>';
  const text = esc(str(it.text, 1000));
  const cond = str(it.condition, 500) ? `<span class="cv-cond">${esc(str(it.condition, 500))}</span>` : '';
  const detail = str(it.detail, 2000) ? `<p class="cv-detail">${esc(str(it.detail, 2000))}</p>` : '';
  const indN = Math.min(Math.max(parseInt(it.indent, 10) || 0, 0), 4);
  const ind = indN ? ` style="margin-left:${indN * 1.25}rem"` : '';
  if (t === 'subtitle') return `<li class="cv-subtitle"${ind}>${text}</li>`;
  if (INFO[t]) {
    return `<li class="cv-info cv-${t}"${ind}><span class="cv-tag">${INFO[t]}</span><span class="cv-itext">${text}</span>${detail}</li>`;
  }
  if (t === 'reference') {
    const ref = it.reference && typeof it.reference === 'object' ? it.reference : {};
    const tgt = str(ref.section_id || ref.document || ref.url, 300);
    return `<li class="cv-info cv-reference"${ind}><span class="cv-tag">GO TO</span><span class="cv-itext">${text}</span>` +
      (tgt ? `<p class="cv-detail">${esc(tgt)}</p>` : '') + '</li>';
  }
  const resp = str(it.response, 300) ? `<span class="cv-resp">${esc(str(it.response, 300))}</span>` : '';
  const tickable = it.tickable !== false && (TICKABLE[t] || it.tickable === true);
  if (!tickable) {
    return `<li class="cv-subtitle" style="font-weight:600;text-transform:none;letter-spacing:0;color:var(--fg)"${ind}>` +
      `<span class="cv-itext">${text}</span>${resp}${cond}${detail}</li>`;
  }
  const mem = it.memory_item ? '<span class="cv-mem">MEMORY</span>' : '';
  return `<li class="cv-task"${ind}><label><input type="checkbox" class="cv-tick" data-section="${esc(secId)}" data-index="${idx}">` +
    `<span class="cv-itext">${text}${mem}</span>${resp}${cond}</label>${detail}</li>`;
}

function sectionsOf(doc) {
  return (Array.isArray(doc.sections) ? doc.sections : []).filter(s => s && typeof s === 'object').slice(0, 200);
}

function itemsOf(sec) {
  return (Array.isArray(sec.items) ? sec.items : []).slice(0, 500);
}

function bodyHtml(doc, id, agg) {
  const ac = doc.aircraft && typeof doc.aircraft === 'object' ? doc.aircraft : {};
  const acLine = [ac.make, ac.model, ac.variant].map(v => str(v, 100)).filter(Boolean).join(' ');
  const cat = str(ac.category, 60).replace(/_/g, ' ');
  const secs = sectionsOf(doc).map((sec, si) => {
    const secId = str(sec.id, 120) || `section-${si}`;
    const crit = str(sec.criticality, 30) || 'normal';
    const phase = str(sec.phase_label || sec.phase, 80);
    const cond = str(sec.condition, 500) ? `<p class="cv-seccond">${esc(str(sec.condition, 500))}</p>` : '';
    const notes = str(sec.notes, 2000) ? `<p class="cv-secnote">${esc(str(sec.notes, 2000))}</p>` : '';
    const items = itemsOf(sec).map((it, i) => itemHtml(it, secId, i)).join('');
    return `<section class="cv-sec ${esc(crit)}" id="${esc(secId)}"><h2>${esc(str(sec.title, 200))}` +
      (phase ? ` <span class="cv-phase">${esc(phase)}</span>` : '') + `</h2>${cond}${notes}<ul class="cv-list">${items}</ul></section>`;
  }).join('');
  const rating = agg.review_count > 0
    ? `<p class="cv-rsum"><span class="avg">${esc(agg.avg_stars.toFixed(1))}</span> / 5 from ${esc(agg.review_count)} ${agg.review_count === 1 ? 'review' : 'reviews'}</p>`
    : '';
  return '<div class="cv-head"><div class="cv-ident">Community checklist</div>' +
    `<h1 class="cv-title">${esc(str(doc.title, 200) || 'Checklist')}</h1>` +
    (acLine || cat ? `<p class="cv-ac">${esc(acLine)}${acLine && cat ? ' · ' : ''}${esc(cat)}</p>` : '') +
    '<div class="cv-badges"><span class="cv-badge unv">Unverified — community-contributed</span></div></div>' +
    '<div class="cv-disc"><strong>Not approved data.</strong> This checklist was contributed by a community member ' +
    'and has not been verified. Always check it against your aircraft’s own approved documentation (POH/AFM) before flight.</div>' +
    `<div class="cv-actions"><a class="cv-btn primary" href="/editor.html?fork=${encodeURIComponent(id)}">✎ Customize this Checklist</a></div>` +
    (secs || '<p class="muted">This checklist has no sections yet.</p>') +
    `<div class="cv-reviews" id="cv-reviews"><h2 style="border:0;font-size:1.15rem">Ratings &amp; reviews</h2>${rating}</div>`;
}

function jsonLd(doc, pageUrl, desc, agg) {
  const ac = doc.aircraft && typeof doc.aircraft === 'object' ? doc.aircraft : {};
  const d = {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: str(doc.title, 200) || 'Checklist',
    description: desc,
    url: pageUrl,
    inLanguage: 'en',
    isAccessibleForFree: true,
    publisher: { '@type': 'Organization', name: 'Open Checklists', url: SITE },
    step: sectionsOf(doc).map(sec => ({
      '@type': 'HowToSection',
      name: str(sec.title, 200),
      itemListElement: itemsOf(sec)
        .filter(it => it && str(it.text, 1000) && !['blank', 'subtitle'].includes(it.type))
        .map(it => ({
          '@type': 'HowToStep',
          text: [str(it.text, 1000), str(it.response, 300)].filter(Boolean).join(' — '),
        })),
    })).filter(s => s.itemListElement.length),
  };
  const about = [ac.make, ac.model, ac.variant].map(v => str(v, 100)).filter(Boolean).join(' ');
  if (about) d.about = { '@type': 'Product', name: about, category: 'Aircraft' };
  if (agg.review_count > 0) {
    d.aggregateRating = { '@type': 'AggregateRating', ratingValue: agg.avg_stars, reviewCount: agg.review_count, bestRating: 5, worstRating: 1 };
  }
  // Escape "<" so content can never close the script tag.
  const json = JSON.stringify(d).replace(/</g, '\\u003c');
  return `<script type="application/ld+json">${json}</script>`;
}

function describe(doc) {
  const ac = doc.aircraft && typeof doc.aircraft === 'object' ? doc.aircraft : {};
  const acLine = [ac.make, ac.model, ac.variant].map(v => str(v, 100)).filter(Boolean).join(' ');
  const secs = sectionsOf(doc);
  const n = secs.reduce((a, s) => a + itemsOf(s).filter(it => it && TICKABLE[it.type || 'challenge']).length, 0);
  const names = secs.map(s => str(s.title, 80)).filter(Boolean).slice(0, 4).join(', ');
  return clip(`${acLine ? acLine + ' checklist' : 'Aircraft checklist'}: ${secs.length} sections, ${n} items` +
    (names ? ` (${names})` : '') + '. Community-contributed and unverified — confirm against your POH/AFM. Print, tick or fork it free.', 300);
}

function page(html, status, cacheControl) {
  return new Response(html, {
    status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': cacheControl },
  });
}

export async function onRequestGet({ request, env, params }) {
  const url = new URL(request.url);
  const raw = String(params.id || '');
  const id = raw.toLowerCase();
  if (!ID_RE.test(id)) return notFound(env, url);
  // Published ids are always lowercase; fold case/trailing-slash variants onto one URL.
  if (raw !== id || url.pathname.endsWith('/')) {
    return Response.redirect(`${url.origin}/checklist/${encodeURIComponent(id)}`, 301);
  }

  const cache = caches.default;
  const cacheKey = new Request(`${url.origin}/checklist/${id}`, { method: 'GET' });
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const api = `${apiOrigin(env)}/api/checklists/${encodeURIComponent(id)}`;
  let doc, revs = null;
  try {
    const [r, rv] = await Promise.all([
      fetch(api, { headers: { Accept: 'application/json' } }),
      fetch(`${api}/reviews`, { headers: { Accept: 'application/json' } }).catch(() => null),
    ]);
    if (r.status === 404) {
      const res = await notFound(env, url);
      await cache.put(cacheKey, res.clone());
      return res;
    }
    if (!r.ok) throw new Error(`api ${r.status}`);
    doc = await r.json();
    if (rv && rv.ok) revs = await rv.json().catch(() => null);
  } catch (e) {
    return unavailable(env, url);
  }
  if (!doc || typeof doc !== 'object' || doc.error) return notFound(env, url);

  const agg = {
    avg_stars: Math.min(5, Math.max(0, Number(revs && revs.avg_stars) || 0)),
    review_count: Math.max(0, parseInt(revs && revs.review_count, 10) || 0),
  };
  const pageUrl = `${SITE}/checklist/${id}`;
  const title = `${str(doc.title, 120) || 'Checklist'} — community checklist | Open Checklists`;
  const desc = describe(doc);

  let html = await template(env, url.origin);
  html = html
    .replace(/<meta name="robots" content="noindex">\n?/, () => '')
    .replace(/<title>[^<]*<\/title>/, () => `<title>${esc(title)}</title>`)
    .replace(/<meta name="description" content="[^"]*">/, () => `<meta name="description" content="${esc(desc)}">`)
    .replace(/<meta property="og:title" content="[^"]*">/, () => `<meta property="og:title" content="${esc(title)}">`)
    .replace(/<meta property="og:description" content="[^"]*">/, () => `<meta property="og:description" content="${esc(desc)}">`)
    .replace(/<meta property="og:type" content="[^"]*">/, () => '<meta property="og:type" content="article">')
    .replace('</head>', () => `<link rel="canonical" href="${esc(pageUrl)}">\n<meta property="og:url" content="${esc(pageUrl)}">\n` +
      `<meta property="og:image" content="${SITE}/og-image.png">\n${jsonLd(doc, pageUrl, desc, agg)}\n</head>`)
    .replace(/<div id="cv-root" class="cv-wrap">[\s\S]*?<\/div>/, () => `<div id="cv-root" class="cv-wrap">${bodyHtml(doc, id, agg)}</div>`);

  // Edits and new reviews show up within ten minutes.
  const res = page(html, 200, 'public, max-age=300, s-maxage=600');
  await cache.put(cacheKey, res.clone());
  return res;
}

async function shell(env, url, title) {
  let html = await template(env, url.origin);
  html = html.replace(/<title>[^<]*<\/title>/, () => `<title>${esc(title)}</title>`);
  if (!/<meta name="robots"/.test(html)) html = html.replace('</head>', () => '<meta name="robots" content="noindex">\n</head>');
  return html;
}

async function notFound(env, url) {
  return page(await shell(env, url, 'Checklist not found — Open Checklists'), 404, 'public, max-age=60, s-maxage=60');
}

// API down: never answer 404 (search engines would drop the page). The client
// viewer still boots and retries from the browser.
async function unavailable(env, url) {
  const res = page(await shell(env, url, 'Checklist — Open Checklists'), 503, 'no-store');
  res.headers.set('Retry-After', '120');
  return res;
}
