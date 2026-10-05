// Server-rendered airport pages: /airport/<IDENT>
//
// The site ships ONE client-rendered airport template (/airport/index.html)
// because 19k static pages would break the Cloudflare Pages 20,000-file limit.
// That template is invisible to search engines ("Loading airport…"), so this
// Pages Function serves /airport/<IDENT> with the airport's facts, title,
// description, canonical link and structured data already in the HTML. The
// same client script then boots on top and adds the live weather layer.
//
// Functions take precedence over the Pages SPA fallback, which is why path
// URLs work here when a _redirects rewrite did not.

const IDENT_RE = /^[A-Z0-9]{2,5}$/;
// Canonicals, og:url, JSON-LD and redirects always name production. Preview and
// *.pages.dev hosts serve the same HTML, and must not advertise themselves as the
// canonical copy (or get that cached). The request origin is only used to fetch
// this deployment's own static assets.
const PROD_ORIGIN = 'https://openchecklists.net';
// Bump when the rendered HTML changes shape so stale edge copies are not served.
const CACHE_VERSION = 'v2';

function esc(v) {
  return String(v == null ? '' : v).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// FAA NASR abbreviates facility names; expand the common ones for titles.
const ABBR = { RGNL: 'Regional', INTL: 'International', MUNI: 'Municipal', ARPT: 'Airport',
  FLD: 'Field', MEML: 'Memorial', EXEC: 'Executive', CNTY: 'County', ARPK: 'Airpark' };
const KEEP = new Set(['AFB', 'NAS', 'ARB', 'LLC', 'II', 'III']);

function titleCase(s) {
  return String(s || '').split(/(\s+|-|\/)/).map(w => {
    const u = w.toUpperCase();
    if (ABBR[u]) return ABBR[u];
    if (KEEP.has(u)) return u;
    return w.toLowerCase().replace(/^([a-z])/, m => m.toUpperCase());
  }).join('');
}

// Near-airport shards are keyed by the first two characters of the FAA ident
// (tools/site_airport_near.py shard_key()).
function nearKey(ident) {
  return (String(ident || '').toUpperCase().slice(0, 2).replace(/[^A-Z0-9]/g, '_') + '__').slice(0, 2);
}

// FAA publication cycles. d-TPP (plates/diagrams) follows the 28-day AIRAC cycle;
// the Chart Supplement is on a 56-day cycle named after the AIRAC cycle it starts
// in. FAA search result URLs only work with a valid cycle id (verified: no cycle
// redirects to the blank search form).
const DAY = 86400000;
function airacId(t) {
  const ref = Date.UTC(2026, 0, 22);              // AIRAC 2601
  const start = ref + Math.floor((t - ref) / (28 * DAY)) * 28 * DAY;
  const y = new Date(start).getUTCFullYear();
  const n = Math.floor((start - Date.UTC(y, 0, 1)) / (28 * DAY)) + 1;
  return String(y % 100).padStart(2, '0') + String(n).padStart(2, '0');
}
function supplementCycle(t) {
  const ref = Date.UTC(2026, 8, 3);               // Chart Supplement 2609
  return airacId(ref + Math.floor((t - ref) / (56 * DAY)) * 56 * DAY);
}

function chartLinks(a) {
  const id = encodeURIComponent(a.ident || '');
  const now = Date.now();
  const links = [];
  if (a.use === 'public') {
    links.push(['FAA airport diagram & procedures (d-TPP)',
      `https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/search/results/?cycle=${airacId(now)}&ident=${id}`]);
    links.push(['FAA Chart Supplement',
      `https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/search/results/?cycle=${supplementCycle(now)}&ident=${id}`]);
  }
  links.push(['AirNav', `https://www.airnav.com/airport/${encodeURIComponent(a.icao || a.ident || '')}`]);
  links.push(['SkyVector', `https://skyvector.com/airport/${id}`]);
  return links;
}

function parseVar(s) {
  const m = String(s || '').match(/^(\d+(?:\.\d+)?)\s*([EW])$/i);
  if (!m) return null;
  return (m[2].toUpperCase() === 'E' ? 1 : -1) * parseFloat(m[1]);
}
const norm = h => { const x = ((Math.round(h) % 360) + 360) % 360; return x === 0 ? 360 : x; };
const hdg3 = h => String(h).padStart(3, '0');
const COMPASS_END = { N: 360, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
// True heading from NASR when published; otherwise runway number x 10 is the
// magnetic heading (±5°), converted to true with the airport's variation.
// East variation: magnetic = true − var. West: magnetic = true + var.
function endHeading(end, variation) {
  if (end.true_heading != null && end.true_heading !== '') {
    const t = norm(+end.true_heading);
    return { t, m: variation != null ? norm(t - variation) : null, src: 'NASR true heading' };
  }
  const id = String(end.end || '').toUpperCase();
  const num = id.match(/^(\d{1,2})[LRCW]?$/);
  const m = num ? norm(+num[1] * 10) : (COMPASS_END[id] || null);
  if (m == null) return null;
  return { t: variation != null ? norm(m + variation) : m, m, src: 'approx. from runway number' };
}

function nearRow(e) {
  // [url id, name, city, st, nm, brg true, longest rwy, fuel, use, type, hard]
  return `<tr><td><a href="/airport/${encodeURIComponent(e[0])}">${esc(e[0])}</a></td>` +
    `<td>${esc(titleCase(e[1]))}<br><small>${esc(titleCase(e[2]))}, ${esc(e[3])}</small></td>` +
    `<td>${esc(e[4])} nm ${esc(hdg3(e[5]))}°T</td><td>${e[9] === 's' ? 'water' : e[6] ? esc(e[6].toLocaleString('en-US')) + ' ft' + (e[10] ? '' : ' (soft)') : '—'}</td>` +
    `<td>${esc(e[7] || '—')}</td><td>${e[8] === 'pu' ? 'Public' : 'Private'}</td></tr>`;
}

function nearHtml(n, ident) {
  if (!n) return '';
  let h = '';
  if (n.n && n.n.length) {
    h += `<h2>Airports near ${esc(ident)}</h2><table class="near"><thead><tr><th>Id</th><th>Name</th>` +
      `<th>Distance / bearing</th><th>Longest rwy</th><th>Fuel</th><th>Use</th></tr></thead><tbody>` +
      n.n.map(nearRow).join('') + '</tbody></table>';
  }
  const quick = (label, list) => list && list.length
    ? `<p><strong>${label}:</strong> ` + list.map(e =>
      `<a href="/airport/${encodeURIComponent(e[0])}">${esc(e[0])}</a> ${esc(e[4])} nm` +
      (label.indexOf('fuel') !== -1 ? ` (${esc(e[7])})` : ` (${esc((+e[6]).toLocaleString('en-US'))} ft)`)).join(', ') + '</p>'
    : '';
  h += quick('Nearest public airports with fuel', n.f);
  h += quick('Nearest public airports with a runway of 3,000 ft or more', n.l);
  if (n.cp) h += `<p><a href="/airports-near/${encodeURIComponent(n.cp[0])}/">All airports near ${esc(n.cp[1])} &rarr;</a></p>`;
  return h;
}

async function asset(env, origin, path) {
  const r = await env.ASSETS.fetch(new URL(path, origin));
  if (!r.ok) throw new Error(`asset ${path}: ${r.status}`);
  return r;
}

function factsHtml(a, ident, near) {
  const rows = [];
  const add = (k, v) => { if (v !== null && v !== undefined && v !== '') rows.push(`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`); };
  add('Identifier', a.icao && a.icao !== a.ident ? `${a.ident} (ICAO ${a.icao})` : a.ident);
  add('Location', [titleCase(a.city), a.state].filter(Boolean).join(', '));
  add('Elevation', a.elevation_ft != null ? `${Math.round(a.elevation_ft)} ft MSL` : null);
  add('Pattern altitude', a.pattern_altitude_ft ? `${a.pattern_altitude_ft} ft AGL` : null);
  add('Use', a.use);
  add('Fuel', a.fuel);
  add('Sectional', titleCase(a.sectional));
  add('Magnetic variation', a.magnetic_variation);
  const rwys = (a.runways || []).map(r =>
    `<tr><td>${esc(r.id)}</td><td>${esc(r.length_ft)} × ${esc(r.width_ft)} ft</td><td>${esc(r.surface || '')}</td><td>${esc(r.lighting || '')}</td></tr>`).join('');
  const variation = parseVar(a.magnetic_variation);
  const ends = [];
  (a.runways || []).forEach(r => (r.ends || []).forEach(e => {
    const hd = endHeading(e, variation);
    if (hd) ends.push(`<tr><td>${esc(e.end)}</td><td>${esc(hdg3(hd.t))}°</td><td>${hd.m != null ? esc(hdg3(hd.m)) + '°' : '—'}</td><td>${esc(hd.src)}</td></tr>`);
  }));
  const freqs = (a.frequencies || []).slice(0, 30).map(f =>
    `<tr><td>${esc(f.use || '')}</td><td>${esc(f.frequency || '')}</td><td>${esc(f.facility || f.callsign || '')}</td></tr>`).join('');
  const charts = chartLinks(a).map(([t, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`).join(' &middot; ');
  return `<article class="ap-ssr">
<h1>${esc(titleCase(a.name))} (${esc(ident)})</h1>
<p>${esc(titleCase(a.city))}, ${esc(a.state_name ? titleCase(a.state_name) : a.state)} &middot; FAA NASR data. Live weather, NOTAMs, winds aloft and a crosswind calculator load below.</p>
<table class="facts"><tbody>${rows.join('')}</tbody></table>
${rwys ? `<h2>Runways</h2><table><thead><tr><th>Runway</th><th>Size</th><th>Surface</th><th>Lighting</th></tr></thead><tbody>${rwys}</tbody></table>` : ''}
${ends.length ? `<h2>Runway headings</h2><table><thead><tr><th>End</th><th>True</th><th>Magnetic</th><th>Source</th></tr></thead><tbody>${ends.join('')}</tbody></table>` : ''}
${freqs ? `<h2>Frequencies</h2><table><thead><tr><th>Use</th><th>MHz</th><th>Facility</th></tr></thead><tbody>${freqs}</tbody></table>` : ''}
<h2>Charts and airport diagram</h2><p>${charts}</p>
${nearHtml(near, ident)}
</article>`;
}

function jsonLd(a, ident, url) {
  const d = {
    '@context': 'https://schema.org',
    '@type': 'Airport',
    name: titleCase(a.name),
    url,
    faaCode: a.ident,
    address: { '@type': 'PostalAddress', addressLocality: titleCase(a.city), addressRegion: a.state, addressCountry: 'US' },
  };
  if (a.icao) d.icaoCode = a.icao;
  if (a.lat != null && a.lon != null) d.geo = { '@type': 'GeoCoordinates', latitude: +a.lat, longitude: +a.lon, elevation: a.elevation_ft };
  return `<script type="application/ld+json">${JSON.stringify(d).replace(/</g, '\\u003c')}</script>`;
}

export async function onRequestGet({ request, env, params }) {
  const url = new URL(request.url);
  const raw = String(params.ident || '');
  const want = raw.toUpperCase();

  if (!IDENT_RE.test(want)) return notFound(env, url, raw);

  // Keyed per host so a preview deployment never answers for production (or
  // vice versa), and per deployment (commit) so a new template isn't masked by
  // a day-old edge copy.
  const cache = caches.default;
  const build = (env.CF_PAGES_COMMIT_SHA || '').slice(0, 12) || CACHE_VERSION;
  const cacheKey = new Request(`https://${url.host}/__ssr/${build}/airport/${want}`, { method: 'GET' });
  if (raw === want && !url.pathname.endsWith('/')) {
    const hit = await cache.match(cacheKey);
    if (hit) return hit;
  }

  let icao = {};
  try { icao = await (await asset(env, url.origin, '/data/airports/icao.json')).json(); } catch { icao = {}; }
  const resolved = icao[want] || want;
  let shard = {};
  try {
    const key = /[A-Z0-9]/.test(resolved[0]) ? resolved[0] : '_';
    shard = await (await asset(env, url.origin, `/data/airports/detail/${key}.json`)).json();
  } catch { shard = {}; }
  const a = shard[resolved] || shard[want];
  if (!a) return notFound(env, url, want);

  // One URL per airport: ICAO where it has one (what pilots search for), else the FAA id.
  const canonicalId = a.icao || a.ident;
  if (want !== canonicalId || raw !== want || url.pathname.endsWith('/')) {
    return Response.redirect(`${PROD_ORIGIN}/airport/${encodeURIComponent(canonicalId)}`, 301);
  }

  let near = null;
  try { near = (await (await asset(env, url.origin, `/data/airports/near/${nearKey(a.ident)}.json`)).json())[a.ident] || null; } catch { near = null; }

  const pageUrl = `${PROD_ORIGIN}/airport/${canonicalId}`;
  const name = titleCase(a.name);
  const place = [titleCase(a.city), a.state].filter(Boolean).join(', ');
  const title = `${canonicalId} ${name} — ${place}: frequencies, runways, weather`;
  const longest = Math.max(0, ...(a.runways || []).map(r => +r.length_ft || 0));
  const ctaf = (a.frequencies || []).find(f => /CTAF|UNICOM/i.test(f.use || ''));
  const desc = `${name} (${canonicalId}), ${place}: ` +
    [a.elevation_ft != null ? `elevation ${Math.round(a.elevation_ft)} ft` : '',
     longest ? `longest runway ${longest} ft` : '',
     ctaf ? `${ctaf.use} ${ctaf.frequency}` : '',
     'live METAR, TAF, NOTAMs, winds aloft and nearby airports'].filter(Boolean).join(', ') + '.';

  let html = await (await asset(env, url.origin, '/airport/')).text();
  html = html
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/<meta name="description" content="[^"]*">/, `<meta name="description" content="${esc(desc)}">`)
    .replace(/<meta property="og:title" content="[^"]*">/, `<meta property="og:title" content="${esc(title)}">`)
    .replace(/<meta property="og:description" content="[^"]*">/, `<meta property="og:description" content="${esc(desc)}">`)
    .replace('</head>', `<link rel="canonical" href="${esc(pageUrl)}">\n<meta property="og:url" content="${esc(pageUrl)}">\n${jsonLd(a, canonicalId, pageUrl)}\n</head>`)
    .replace(/<div id="ap-root">[\s\S]*?<\/div>/, () => `<div id="ap-root">${factsHtml(a, canonicalId, near)}</div>`);

  const res = new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      // NASR changes every 28 days; a day at the edge is plenty fresh.
      'Cache-Control': 'public, max-age=3600, s-maxage=86400',
    },
  });
  await cache.put(cacheKey, res.clone());
  return res;
}

async function notFound(env, url, ident) {
  let html = await (await asset(env, url.origin, '/airport/')).text();
  html = html
    .replace(/<title>[^<]*<\/title>/, '<title>Airport not found — Open Checklists</title>')
    .replace('</head>', '<meta name="robots" content="noindex">\n</head>');
  return new Response(html, { status: 404, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}
