// /sitemap-community.xml — community checklists are published at runtime into
// the API's database, so their URLs can't be in the static sitemaps. The
// sitemap index (written by tools/build_site.py) points here.

const ID_RE = /^[a-z0-9][a-z0-9-]{0,119}$/;
const SITE = 'https://openchecklists.net';
const DEFAULT_API = 'https://app.openchecklists.net';

function xmlEsc(v) {
  return String(v).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));
}

export async function onRequestGet({ request, env }) {
  const cache = caches.default;
  const cacheKey = new Request(new URL('/sitemap-community.xml', request.url), { method: 'GET' });
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const api = String(env.OCL_API_ORIGIN || DEFAULT_API).replace(/\/+$/, '');
  let list;
  try {
    const r = await fetch(`${api}/api/checklists`, { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`api ${r.status}`);
    list = (await r.json()).checklists;
    if (!Array.isArray(list)) throw new Error('bad payload');
  } catch {
    // An empty sitemap would read as "all removed"; ask crawlers to retry instead.
    return new Response('Sitemap temporarily unavailable', {
      status: 503, headers: { 'Retry-After': '600', 'Cache-Control': 'no-store' },
    });
  }

  const urls = list
    .filter(c => c && typeof c.id === 'string' && ID_RE.test(c.id))
    .slice(0, 50000)
    .map(c => {
      const day = typeof c.saved_at === 'string' && /^\d{4}-\d{2}-\d{2}/.test(c.saved_at) ? c.saved_at.slice(0, 10) : '';
      return `  <url><loc>${xmlEsc(`${SITE}/checklist/${c.id}`)}</loc>${day ? `<lastmod>${day}</lastmod>` : ''}</url>\n`;
    }).join('');

  const res = new Response(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '</urlset>\n',
    { headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=3600, s-maxage=3600' } },
  );
  await cache.put(cacheKey, res.clone());
  return res;
}
