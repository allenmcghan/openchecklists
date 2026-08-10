#!/usr/bin/env python3
"""Airport, frequency and weather pages for the site.

Two things live here because they share an audience: you look up an airport and you
want its frequencies and its weather in the same breath.

**Airports** are served from the static NASR ingest (tools/airports.py). Search runs
client-side over a lean index; detail loads one shard on demand. No backend, works
offline once cached, and every page states the AIRAC effective date because a stale
frequency is worse than no frequency.

**Weather** needs a proxy, and that is not a design preference. I tested
aviationweather.gov's API in a browser: it returns data to a server but blocks
cross-origin browser requests, so a static page cannot call it directly. Rather than
abandon the static architecture, the page talks to a one-file Cloudflare Worker
(emitted as worker/weather-proxy.js) which adds the CORS header and caches briefly.
Until that Worker is deployed the page says exactly what is missing and links to the
official source, instead of silently showing nothing.

Weather is deliberately never cached for offline use. Everything else on this site
degrades gracefully when stale; a METAR does not.
"""

from __future__ import annotations

import json

AIRPORT_CSS = """
.ap-search{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin:1rem 0}
.ap-search input[type=search]{flex:1;min-width:12rem}
.chips{display:flex;gap:.4rem;flex-wrap:wrap;margin:.4rem 0 1rem}
.chip{font-size:.78rem;padding:.25rem .55rem;border:1px solid var(--line);border-radius:1rem;
cursor:pointer;user-select:none;background:var(--bg)}
.chip[aria-pressed=true]{background:var(--accent);color:#fff;border-color:transparent}
.aplist{list-style:none;padding:0;margin:0;display:grid;gap:.4rem}
.aprow{border:1px solid var(--line);border-radius:.4rem;padding:.5rem .7rem;background:var(--card);
cursor:pointer}
.aprow:hover{border-color:var(--accent)}
.aprow b{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.aprow .sub{font-size:.8rem;color:var(--muted)}
.apdetail{border:1px solid var(--line);border-radius:.5rem;padding:1rem;margin:1rem 0}
.apdetail h3{margin:.1rem 0 .3rem;font-size:1.15rem}
.freqtable td{padding:.25rem .5rem;border-bottom:1px solid var(--line);font-size:.9rem}
.freqtable td:first-child{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:700;
white-space:nowrap;text-align:right}
.rwy{display:inline-block;border:1px solid var(--line);border-radius:.3rem;padding:.3rem .55rem;
margin:.2rem .3rem .2rem 0;font-size:.85rem}
.rwy b{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.cycle{font-size:.78rem;color:var(--caut);border:1px solid var(--caut);border-radius:.3rem;
padding:.35rem .6rem;display:inline-block;margin:.3rem 0}
.wx{border:1px solid var(--line);border-radius:.4rem;padding:.6rem .8rem;margin:.6rem 0;
font-size:.88rem}
.wx pre{white-space:pre-wrap;word-break:break-word;margin:.3rem 0;font-size:.85rem}
.wx .flt{font-weight:700}
.flt-VFR{color:var(--ok)}.flt-MVFR{color:#1f6feb}.flt-IFR{color:var(--warn)}
.flt-LIFR{color:#a21caf}
.muted{color:var(--muted)}
"""

AIRPORT_BODY = """
<h2>Airports, frequencies and weather</h2>
<p class="lede">Every US airport, heliport, seaplane base, gliderport and ultralight
strip in the FAA's database — 19,000 of them, including the private strips most
apps leave out. Runways, radio frequencies, fuel, pattern altitude and field
elevation. Search runs in your browser; nothing you type is sent anywhere.</p>

<div id="cycle"></div>

<div class="ap-search">
  <input type="search" id="apq" placeholder="Identifier, name or city — try FDK, KFDK, or Frederick"
         aria-label="Search airports">
  <button class="btn" id="near">Near me</button>
  <span class="count" id="apcount"></span>
</div>
<div class="chips">
  <span class="chip" id="f-public" role="button" tabindex="0" aria-pressed="true">Public use only</span>
  <span class="chip" id="f-hard" role="button" tabindex="0" aria-pressed="false">Hard surface</span>
  <span class="chip" id="f-freq" role="button" tabindex="0" aria-pressed="false">Has frequencies</span>
  <span class="chip" id="f-air" role="button" tabindex="0" aria-pressed="true">Airports only</span>
</div>

<div id="apdetail"></div>
<ul class="aplist" id="aplist"></ul>
<p class="hint" id="apmore"></p>
"""

AIRPORT_JS = r"""
(function(){
  var INDEX = null, CYCLE = null, shardCache = {}, icao = null;
  var LIMIT = 60;

  var TYPE = {a:'airport', h:'heliport', c:'seaplane base', g:'gliderport',
              b:'balloonport', u:'ultralight'};

  function el(id){ return document.getElementById(id); }
  function esc(s){ return String(s==null?'':s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  async function boot(){
    try {
      CYCLE = await (await fetch('data/airports/cycle.json')).json();
      INDEX = await (await fetch('data/airports/index.json')).json();
      try { icao = await (await fetch('data/airports/icao.json')).json(); } catch(e){ icao = {}; }
    } catch (err) {
      el('cycle').innerHTML = '<div class="banner quar"><strong>Airport data is not ' +
        'available.</strong> It is generated from the FAA NASR subscription and is not ' +
        'committed to the repository because it is about 30 MB. Run ' +
        '<code>tools/acquire.py fetch faa-nasr-28day</code> then ' +
        '<code>tools/airports.py ingest</code>, and rebuild. ' +
        '(Opening this page from a file:// URL will also fail, because browsers block ' +
        'local reads — serve the folder over HTTP.)</div>';
      return;
    }

    var eff = CYCLE.effective, next = CYCLE.next_cycle;
    var age = '';
    if (eff){
      var days = Math.floor((Date.now() - Date.parse(eff + 'T00:00:00Z')) / 86400000);
      age = days + ' day' + (days === 1 ? '' : 's') + ' old';
      if (next && Date.now() > Date.parse(next + 'T00:00:00Z')){
        age += ' — SUPERSEDED, a newer AIRAC cycle has been published';
      }
    }
    el('cycle').innerHTML = '<span class="cycle">FAA NASR data effective ' + esc(eff) +
      ' (' + esc(age) + '). Next cycle ' + esc(next) + '. A snapshot, not live data — ' +
      'verify against the current Chart Supplement before use.</span>';

    ['f-public','f-hard','f-freq','f-air'].forEach(function(id){
      var c = el(id);
      c.addEventListener('click', function(){ toggle(c); });
      c.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); toggle(c); }
      });
    });
    el('apq').addEventListener('input', render);
    el('near').addEventListener('click', locate);

    var want = new URLSearchParams(location.search).get('a');
    if (want) { el('apq').value = want; open_(resolve(want.toUpperCase())); }
    render();
  }

  function toggle(c){
    c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    render();
  }
  function on(id){ return el(id).getAttribute('aria-pressed') === 'true'; }
  function resolve(id){ return (icao && icao[id]) ? icao[id] : id; }

  function matches(a, q){
    if (on('f-public') && a.u !== 'pu') return false;
    if (on('f-hard') && !a.h) return false;
    if (on('f-freq') && !a.f) return false;
    if (on('f-air') && a.t !== 'a') return false;
    if (!q) return true;
    return (a.i + ' ' + (a.k||'') + ' ' + a.n + ' ' + a.c + ' ' + a.s).toLowerCase()
           .indexOf(q) !== -1;
  }

  function render(){
    if (!INDEX) return;
    var q = el('apq').value.trim().toLowerCase();
    var out = [], total = 0;
    for (var i = 0; i < INDEX.length; i++){
      var a = INDEX[i];
      if (!matches(a, q)) continue;
      total++;
      if (out.length < LIMIT) out.push(a);
    }
    el('apcount').textContent = total.toLocaleString() + ' of ' +
      INDEX.length.toLocaleString();
    el('aplist').innerHTML = out.map(row).join('') ||
      '<li class="aprow">Nothing matches. Try an identifier, a city, or turn off the filters.</li>';
    el('apmore').textContent = total > out.length
      ? 'Showing the first ' + out.length + '. Narrow the search to see the rest.' : '';
  }

  function row(a){
    var bits = [TYPE[a.t] || a.t, a.u === 'pu' ? 'public' : 'private'];
    if (a.r) bits.push(a.r.toLocaleString() + ' ft');
    if (a.e != null) bits.push(a.e + ' ft elev');
    if (a.f) bits.push(a.f + ' freq');
    return '<li class="aprow" data-i="' + esc(a.i) + '"><b>' + esc(a.i) + '</b>' +
      (a.k ? ' <span class="muted">' + esc(a.k) + '</span>' : '') +
      ' ' + esc(a.n) + '<div class="sub">' + esc(a.c) + ', ' + esc(a.s) + ' · ' +
      bits.join(' · ') + '</div></li>';
  }

  document.addEventListener('click', function(e){
    var r = e.target.closest && e.target.closest('.aprow');
    if (r && r.dataset.i) open_(r.dataset.i);
  });

  async function shard(ident){
    var k = ident[0].toUpperCase();
    if (!/[A-Z0-9]/.test(k)) k = '_';
    if (!shardCache[k]) shardCache[k] = (await (await fetch('data/airports/detail/' + k + '.json')).json());
    return shardCache[k];
  }

  async function open_(ident){
    ident = resolve(ident.toUpperCase());
    var data;
    try { data = await shard(ident); } catch (e) { return; }
    var a = data[ident];
    if (!a) return;

    var freqs = a.frequencies.map(function(f){
      return '<tr><td>' + esc(f.frequency) + '</td><td>' + esc(f.use) +
        (f.callsign ? ' <span class="muted">' + esc(f.callsign) + '</span>' : '') +
        (f.hours ? ' <span class="muted">' + esc(f.hours) + '</span>' : '') + '</td></tr>';
    }).join('');

    var rwys = a.runways.map(function(r){
      return '<span class="rwy"><b>' + esc(r.id) + '</b> ' +
        (r.length_ft ? r.length_ft.toLocaleString() + '×' + r.width_ft + ' ft ' : '') +
        esc(r.surface || '') + (r.condition ? ' · ' + esc(r.condition.toLowerCase()) : '') +
        '</span>';
    }).join('');

    var facts = [];
    if (a.elevation_ft != null) facts.push('Field elevation ' + a.elevation_ft + ' ft');
    if (a.pattern_altitude_ft) facts.push('Pattern ' + a.pattern_altitude_ft + ' ft');
    if (a.magnetic_variation) facts.push('Variation ' + esc(a.magnetic_variation));
    if (a.fuel) facts.push('Fuel ' + esc(a.fuel));
    if (a.sectional) facts.push('Sectional: ' + esc(a.sectional));
    if (a.manager) facts.push('Manager ' + esc(a.manager) +
      (a.manager_phone ? ' · ' + esc(a.manager_phone) : ''));

    var wxId = a.icao || (a.ident.length === 3 ? 'K' + a.ident : a.ident);

    el('apdetail').innerHTML =
      '<div class="apdetail"><h3>' + esc(a.ident) +
      (a.icao ? ' / ' + esc(a.icao) : '') + ' — ' + esc(a.name) + '</h3>' +
      '<p class="sub">' + esc(a.city) + ', ' + esc(a.state_name || a.state) + ' · ' +
      esc(a.type) + ' · ' + esc(a.use) + ' use · ' + esc(a.owner) + '-owned</p>' +
      (facts.length ? '<p class="sub">' + facts.join(' · ') + '</p>' : '') +
      (rwys ? '<p><strong>Runways</strong><br>' + rwys + '</p>' : '') +
      (freqs ? '<p><strong>Frequencies</strong></p><table class="freqtable"><tbody>' +
        freqs + '</tbody></table>' : '<p class="muted">No frequencies on record.</p>') +
      '<div id="wx" class="wx"><span class="muted">Loading weather…</span></div>' +
      (a.remarks && a.remarks.length
        ? '<p><strong>Remarks</strong></p><ul class="sub">' + a.remarks.map(function(r){
            return '<li>' + esc(r.text) + '</li>'; }).join('') + '</ul>' : '') +
      '<p class="sub"><a href="https://aviationweather.gov/data/metar/?id=' + esc(wxId) +
      '" rel="noopener">Official weather</a> · ' +
      '<a href="https://skyvector.com/airport/' + esc(a.ident) + '" rel="noopener">Charts</a> · ' +
      '<a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/" ' +
      'rel="noopener">Approach plates</a></p>' +
      '</div>';

    window.scrollTo({top: 0, behavior: 'smooth'});
    loadWx(wxId);
  }

  // Weather. Live by definition, so never cached and never presented as current
  // without a timestamp the reader can judge for themselves.
  async function loadWx(id){
    var box = el('wx');
    if (!box) return;
    var base = (window.OCL_WX_PROXY || '').replace(/\/$/, '');
    if (!base){
      box.innerHTML = '<span class="muted">Live weather needs a proxy — ' +
        'aviationweather.gov does not allow browser requests from other sites. ' +
        'Deploy <code>worker/weather-proxy.js</code> and set ' +
        '<code>window.OCL_WX_PROXY</code>. Meanwhile: ' +
        '<a href="https://aviationweather.gov/data/metar/?id=' + esc(id) +
        '" rel="noopener">METAR and TAF for ' + esc(id) + '</a>.</span>';
      return;
    }
    try {
      var r = await fetch(base + '/metar?ids=' + encodeURIComponent(id), {cache:'no-store'});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var d = await r.json();
      if (!d || !d.length){ box.innerHTML = '<span class="muted">No observation for ' +
        esc(id) + '.</span>'; return; }
      var m = d[0];
      var cat = m.fltCat || '';
      var age = m.reportTime ? Math.round((Date.now() - Date.parse(m.reportTime + 'Z'))/60000) : null;
      box.innerHTML = '<div><span class="flt flt-' + esc(cat) + '">' + esc(cat || 'METAR') +
        '</span> <span class="muted">observed ' + esc(m.reportTime || '?') +
        (age != null ? ' · ' + age + ' min ago' : '') + '</span></div>' +
        '<pre>' + esc(m.rawOb || '') + '</pre>' +
        '<span class="muted">Live from NOAA/NWS Aviation Weather Center. Not a briefing — ' +
        'get an official briefing before flight.</span>';
    } catch (e) {
      box.innerHTML = '<span class="muted">Weather unavailable (' + esc(e.message) + '). ' +
        '<a href="https://aviationweather.gov/data/metar/?id=' + esc(id) +
        '" rel="noopener">Check the official source</a>.</span>';
    }
  }

  function locate(){
    if (!navigator.geolocation){ alert('This browser has no location support.'); return; }
    el('near').textContent = 'Locating…';
    navigator.geolocation.getCurrentPosition(function(pos){
      var la = pos.coords.latitude, lo = pos.coords.longitude;
      var scored = INDEX.filter(function(a){
        return a.y != null && matches(a, '');
      }).map(function(a){
        var dy = (a.y - la) * 60, dx = (a.x - lo) * 60 * Math.cos(la * Math.PI/180);
        return {a: a, d: Math.sqrt(dy*dy + dx*dx)};
      }).sort(function(p, q){ return p.d - q.d; }).slice(0, 25);
      el('apq').value = '';
      el('aplist').innerHTML = scored.map(function(s){
        return row(s.a).replace('</div></li>',
          ' · ' + s.d.toFixed(0) + ' nm</div></li>');
      }).join('');
      el('apcount').textContent = 'nearest ' + scored.length;
      el('apmore').textContent = 'Straight-line distance from your device location, which ' +
        'stays in your browser.';
      el('near').textContent = 'Near me';
    }, function(err){
      el('near').textContent = 'Near me';
      alert('Could not get your location: ' + err.message);
    }, {timeout: 10000});
  }

  boot();
})();
"""

# A one-file Cloudflare Worker. Chosen because the site is already going behind
# Cloudflare, so this adds no new infrastructure and no cost at these volumes.
WEATHER_WORKER = r"""// Weather proxy for Open Checklists.
//
// Why this exists: aviationweather.gov serves its API happily to a server but does
// not send an Access-Control-Allow-Origin header, so a browser on another origin
// cannot read the response. Tested and confirmed. This Worker is the smallest thing
// that fixes it without introducing a backend for the rest of the site.
//
// Deploy:
//   wrangler deploy worker/weather-proxy.js --name ocl-weather
// then in the site, before the page scripts:
//   <script>window.OCL_WX_PROXY = 'https://ocl-weather.<subdomain>.workers.dev';</script>
//
// Endpoints: /metar?ids=KFDK  /taf?ids=KFDK  /pirep  /airsigmet
//
// Deliberate choices:
//   * Only the aviationweather host is reachable, and only these paths. An open
//     proxy is an abuse liability.
//   * Short cache. Weather that is cached for long is weather that lies.
//   * No logging of identifiers. The site promises it collects nothing, and a proxy
//     that logged what airports people looked up would quietly break that promise.

const UPSTREAM = 'https://aviationweather.gov/api/data/';
const ALLOWED = new Set(['metar', 'taf', 'pirep', 'airsigmet', 'sigmet', 'gairmet']);
const CACHE_SECONDS = 60;

function cors(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Max-Age': '86400',
    'Cache-Control': `public, max-age=${CACHE_SECONDS}`,
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin');

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors(origin) });
    }
    if (request.method !== 'GET') {
      return new Response('GET only', { status: 405, headers: cors(origin) });
    }

    const product = url.pathname.replace(/^\/+/, '').split('/')[0];
    if (!ALLOWED.has(product)) {
      return new Response(
        JSON.stringify({ error: 'unknown product', allowed: [...ALLOWED] }),
        { status: 404, headers: { ...cors(origin), 'Content-Type': 'application/json' } },
      );
    }

    // Rebuild the query rather than forwarding it, so nothing unexpected is passed
    // upstream.
    const ids = (url.searchParams.get('ids') || '').slice(0, 200);
    const hours = (url.searchParams.get('hours') || '').slice(0, 4);
    const upstream = new URL(UPSTREAM + product);
    upstream.searchParams.set('format', 'json');
    if (ids) upstream.searchParams.set('ids', ids);
    if (hours) upstream.searchParams.set('hours', hours);

    try {
      const res = await fetch(upstream.toString(), {
        headers: { 'Accept': 'application/json', 'User-Agent': 'open-checklists-weather-proxy' },
        cf: { cacheTtl: CACHE_SECONDS, cacheEverything: true },
      });
      const body = await res.text();
      return new Response(body, {
        status: res.status,
        headers: { ...cors(origin), 'Content-Type': 'application/json; charset=utf-8' },
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: 'upstream unavailable' }), {
        status: 502,
        headers: { ...cors(origin), 'Content-Type': 'application/json' },
      });
    }
  },
};
"""


def airports_page(head_fn, foot: str, wx_proxy: str = "") -> str:
    cfg = (
        f"<script>window.OCL_WX_PROXY = {json.dumps(wx_proxy)};</script>"
        if wx_proxy is not None
        else ""
    )
    return (
        head_fn(
            "Airports, frequencies and weather — Open Checklists",
            "Every US airport, heliport, seaplane base and ultralight strip with runways, "
            "radio frequencies, fuel and field elevation, from the FAA's public-domain data.",
        )
        + f"<style>{AIRPORT_CSS}</style>"
        + AIRPORT_BODY
        + cfg
        + f"<script>{AIRPORT_JS}</script>"
        + foot
    )
