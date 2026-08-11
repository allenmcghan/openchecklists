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
    return '<li class="aprow"><a href="airport.html?id=' + esc(a.i) + '" style="text-decoration:none;color:inherit;display:block"><b>' + esc(a.i) + '</b>' +
      (a.k ? ' <span class="muted">' + esc(a.k) + '</span>' : '') +
      ' ' + esc(a.n) + '<div class="sub">' + esc(a.c) + ', ' + esc(a.s) + ' · ' +
      bits.join(' · ') + '</div></a></li>';
  }

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


AIRPORT_DETAIL_CSS = """
.ap-hero{padding:1rem 0 .5rem}
.ap-ident{font-family:var(--mono);font-size:1.8rem;font-weight:800;color:var(--accent);letter-spacing:.04em}
.ap-name{font-size:1.35rem;font-weight:720;letter-spacing:-.015em;margin:.15rem 0}
.ap-meta{font-size:.9rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:.4rem .8rem}
.ap-meta span{white-space:nowrap}
.ap-type{display:inline-block;font-size:.68rem;font-weight:700;text-transform:uppercase;
letter-spacing:.05em;padding:.2rem .55rem;border-radius:999px;background:#eaf1fb;color:#1f4e79}
#ap-map{height:280px;border-radius:14px;border:1px solid var(--line);margin:1rem 0;
background:var(--card);overflow:hidden}
@media(min-width:700px){#ap-map{height:380px}}
.ap-sections{display:grid;gap:1rem;margin:1rem 0}
@media(min-width:700px){.ap-sections{grid-template-columns:1fr 1fr}}
.ap-box{border:1px solid var(--line);border-radius:14px;padding:1rem;background:#fff}
.ap-box h3{margin:0 0 .6rem;font-size:1rem;font-weight:700;color:var(--fg)}
.freq-row{display:grid;grid-template-columns:6rem 1fr;gap:.3rem .6rem;align-items:baseline;
padding:.35rem 0;border-bottom:1px solid var(--line);font-size:.9rem}
.freq-row:last-child{border-bottom:0}
.freq-mhz{font-family:var(--mono);font-weight:700;color:var(--accent)}
.freq-use{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.rwy-row{padding:.4rem 0;border-bottom:1px solid var(--line);font-size:.9rem}
.rwy-row:last-child{border-bottom:0}
.rwy-hdg{font-family:var(--mono);font-weight:700;font-size:1.1rem;color:var(--accent)}
.rwy-meta{font-size:.82rem;color:var(--muted)}
.wx-box{border:1px solid var(--line);border-radius:14px;padding:1rem;background:#fff;margin:1rem 0}
.wx-box h3{margin:0 0 .6rem;font-size:1rem;font-weight:700}
.wx-raw{font-family:var(--mono);font-size:.82rem;background:var(--card);padding:.7rem;
border-radius:9px;white-space:pre-wrap;word-break:break-all;line-height:1.55;margin:.4rem 0}
.wx-cond{display:flex;flex-wrap:wrap;gap:.5rem;margin:.4rem 0}
.wx-chip{font-size:.8rem;padding:.28rem .65rem;border-radius:999px;background:var(--card);font-weight:600}
.flt-VFR{background:#e9f6ec;color:#14521f}
.flt-MVFR{background:#eaf1fb;color:#1a3d6b}
.flt-IFR{background:#fdeceb;color:#7c1c16}
.flt-LIFR{background:#f3e8fb;color:#5b1a8a}
.ext-links{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0}
.ext-link{padding:.45rem .85rem;border:1px solid var(--line);border-radius:999px;
font-size:.85rem;color:var(--accent);text-decoration:none;font-weight:500;
background:#fff;transition:border-color .12s,background .12s}
.ext-link:hover{border-color:var(--accent);background:var(--accent-weak);text-decoration:none}
.notfound{padding:3rem 0;color:var(--muted);text-align:center}
"""

AIRPORT_DETAIL_JS = r"""
(function(){
var WX = window.OCL_WX_PROXY || '';
var apId = new URLSearchParams(location.search).get('id') || '';
if(!apId){ document.getElementById('ap-content').innerHTML='<p class="notfound">No airport specified. <a href="airports.html">Search airports</a></p>'; return; }
apId = apId.toUpperCase();

// Leaflet map init
var map, marker;
function initMap(lat,lon,name){
  if(map) return;
  // Load Leaflet CSS
  var lc=document.createElement('link');lc.rel='stylesheet';
  lc.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  document.head.appendChild(lc);
  // Load Leaflet JS then init
  var ls=document.createElement('script');
  ls.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  ls.onload=function(){
    map=L.map('ap-map',{zoomControl:true}).setView([lat,lon],13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom:18}).addTo(map);
    var ico=L.divIcon({className:'',html:'<div style="background:#1f4e79;border:3px solid #fff;border-radius:50%;width:18px;height:18px;box-shadow:0 2px 8px rgba(0,0,0,.35)"></div>',iconSize:[18,18],iconAnchor:[9,9]});
    marker=L.marker([lat,lon],{icon:ico}).addTo(map).bindPopup('<strong>'+name+'</strong>');
  };
  document.head.appendChild(ls);
}

function flightCategory(vis,ceil){
  if(ceil===null||vis===null) return '';
  if(ceil<200||vis<0.25) return 'LIFR';
  if(ceil<500||vis<1) return 'IFR';
  if(ceil<1000||vis<3) return 'MVFR';
  return 'VFR';
}

function parseVis(v){
  if(v===undefined||v===null) return null;
  if(typeof v==='number') return v;
  if(typeof v==='string'&&v.endsWith('+')) return parseFloat(v.replace('+',''));
  return parseFloat(v)||null;
}

function windStr(dir,spd,gust){
  if(!spd&&spd!==0) return '';
  var s=(dir===0&&spd===0)?'Calm':(dir+'° at '+spd+' kt');
  if(gust) s+=' gusting '+gust+' kt';
  return s;
}

function loadWeather(icao){
  if(!WX) return;
  var box=document.getElementById('ap-wx');
  box.innerHTML='<p style="color:var(--muted);font-size:.9rem">Loading weather…</p>';
  function fetchOk(url,cb){
    fetch(url).then(function(r){return r.ok?r.json():Promise.reject(r.status);}).then(cb).catch(function(e){console.warn(e);});
  }
  fetchOk(WX+'/metar?ids='+icao+'&format=json',function(d){
    if(!d||!d.length){box.innerHTML='<p style="color:var(--muted);font-size:.9rem">No METAR available.</p>';return;}
    var m=d[0];
    var vis=parseVis(m.visib);
    var ceil=null;
    if(m.clouds){var bknovc=m.clouds.filter(function(c){return c.cover==='BKN'||c.cover==='OVC';});
      if(bknovc.length) ceil=bknovc[0].base;}
    var cat=flightCategory(vis,ceil);
    var tc=m.temp!==undefined?Math.round(m.temp)+'°C / '+Math.round(m.temp*9/5+32)+'°F':'';
    var dp=m.dewp!==undefined?Math.round(m.dewp)+'°C':'';
    var w=windStr(m.wdir,m.wspd,m.wgust);
    var alt=m.altim?m.altim.toFixed(2)+' inHg':'';
    var chips='';
    if(cat) chips+='<span class="wx-chip flt-'+cat+'">'+cat+'</span>';
    if(w) chips+='<span class="wx-chip">'+w+'</span>';
    if(tc) chips+='<span class="wx-chip">'+tc+'</span>';
    if(alt) chips+='<span class="wx-chip">'+alt+'</span>';
    var raw=m.rawOb||'';
    var obs=m.reportTime?new Date(m.reportTime).toLocaleString('en-US',{hour12:false,timeZoneName:'short'}):'';
    var html='<h3>Current weather'+( obs?' <span style="font-size:.78rem;font-weight:400;color:var(--muted)">'+obs+'</span>':'')+'</h3>';
    html+='<div class="wx-cond">'+chips+'</div>';
    if(raw) html+='<div class="wx-raw">'+raw+'</div>';
    box.innerHTML=html;
  });
  // TAF
  fetchOk(WX+'/taf?ids='+icao+'&format=json',function(d){
    if(!d||!d.length) return;
    var t=d[0];
    var raw=t.rawTAF||t.rawTaf||'';
    if(!raw) return;
    var tafBox=document.getElementById('ap-taf');
    if(tafBox) tafBox.innerHTML='<h3>Forecast (TAF)</h3><div class="wx-raw">'+raw+'</div>';
  });
}

function renderAirport(ap){
  var typeLabel={'airport':'Airport','heliport':'Heliport','seaplane_base':'Seaplane Base',
    'ultralight':'Ultralight Strip','gliderport':'Gliderport','balloonport':'Balloonport',
    'closed':'Closed'};
  var useLabel={'public':'Public','private':'Private','military':'Military'};

  // Update page title
  document.title=(ap.icao||ap.ident)+' — '+(ap.name||'Airport')+' — Open Checklists';

  // Hero
  var hero='<div class="ap-hero">';
  hero+='<div style="display:flex;align-items:baseline;gap:.7rem;flex-wrap:wrap">';
  hero+='<span class="ap-ident">'+(ap.icao||ap.ident)+'</span>';
  if(ap.type) hero+='<span class="ap-type">'+(typeLabel[ap.type]||ap.type)+'</span>';
  if(ap.use&&ap.use!=='public') hero+='<span class="ap-type" style="background:#fbf3e0;color:#8a5a00">'+(useLabel[ap.use]||ap.use)+'</span>';
  hero+='</div>';
  hero+='<div class="ap-name">'+(ap.name||'')+'</div>';
  var metaParts=[];
  if(ap.city&&ap.state_name) metaParts.push('<span>'+ap.city+', '+ap.state_name+'</span>');
  if(ap.elevation_ft!==undefined&&ap.elevation_ft!==null) metaParts.push('<span>Elevation: '+Math.round(ap.elevation_ft)+' ft MSL</span>');
  if(ap.magnetic_variation) metaParts.push('<span>Variation: '+ap.magnetic_variation+'</span>');
  if(ap.sectional) metaParts.push('<span>Sectional: '+ap.sectional+'</span>');
  if(ap.fuel) metaParts.push('<span>Fuel: '+ap.fuel+'</span>');
  if(ap.longest_runway_ft) metaParts.push('<span>Longest runway: '+ap.longest_runway_ft.toLocaleString()+' ft</span>');
  hero+='<div class="ap-meta">'+metaParts.join('')+'</div>';
  hero+='</div>';

  // Map
  var mapDiv='<div id="ap-map"><p style="padding:.8rem;color:var(--muted);font-size:.9rem">Loading map…</p></div>';

  // Weather
  var wxDiv='<div class="wx-box" id="ap-wx"><p style="color:var(--muted);font-size:.9rem">Weather requires an internet connection.</p></div>';
  var tafDiv='<div class="wx-box" id="ap-taf" style="display:none"></div>';
  if(WX){wxDiv='<div class="wx-box" id="ap-wx"><p style="color:var(--muted);font-size:.9rem">Loading…</p></div>';
    tafDiv='<div class="wx-box" id="ap-taf"></div>';}

  // Frequencies
  var freqHtml='';
  if(ap.frequencies&&ap.frequencies.length){
    freqHtml='<div class="ap-box"><h3>Radio frequencies</h3>';
    // Sort: ATIS first, then CTAF/UNICOM, then APP/DEP, then TWR, then GND, others
    var order={'ATIS':0,'AWOS':1,'ASOS':2,'CTAF':3,'UNICOM':4,'APPROACH':5,'DEPARTURE':6,'TOWER':7,'GROUND':8};
    var sorted=ap.frequencies.slice().sort(function(a,b){
      return (order[a.use_code]??99)-(order[b.use_code]??99);});
    sorted.forEach(function(f){
      freqHtml+='<div class="freq-row">';
      freqHtml+='<span class="freq-mhz">'+f.frequency+'</span>';
      freqHtml+='<span><span class="freq-use">'+(f.use||f.use_code||'')+'</span>';
      if(f.callsign) freqHtml+=' '+f.callsign;
      if(f.hours) freqHtml+=' <span style="font-size:.78rem;color:var(--muted)">'+f.hours+'</span>';
      if(f.remark) freqHtml+='<br><span style="font-size:.78rem;color:var(--muted)">'+f.remark+'</span>';
      freqHtml+='</span></div>';
    });
    freqHtml+='</div>';
  }

  // Runways
  var rwyHtml='';
  if(ap.runways&&ap.runways.length){
    rwyHtml='<div class="ap-box"><h3>Runways</h3>';
    ap.runways.forEach(function(r){
      rwyHtml+='<div class="rwy-row">';
      rwyHtml+='<span class="rwy-hdg">'+(r.id||'RWY')+'</span>';
      var meta=[];
      if(r.length_ft) meta.push((r.length_ft||0).toLocaleString()+' ft');
      if(r.width_ft) meta.push((r.width_ft||0)+' ft wide');
      if(r.surface) meta.push(r.surface);
      if(r.lighted) meta.push('lighted');
      if(r.closed) meta.push('<span style="color:var(--warn)">CLOSED</span>');
      rwyHtml+='<div class="rwy-meta">'+meta.join(' · ')+'</div>';
      if(r.le_heading_degT!==undefined||r.he_heading_degT!==undefined){
        rwyHtml+='<div class="rwy-meta" style="font-family:var(--mono);font-size:.78rem">';
        if(r.le_ident) rwyHtml+=r.le_ident+': '+Math.round(r.le_heading_degT||0)+'°T';
        if(r.le_ident&&r.he_ident) rwyHtml+=' / ';
        if(r.he_ident) rwyHtml+=r.he_ident+': '+Math.round(r.he_heading_degT||0)+'°T';
        rwyHtml+='</div>';
      }
      rwyHtml+='</div>';
    });
    rwyHtml+='</div>';
  }

  // External links
  var icao=ap.icao||ap.ident||apId;
  var lat=ap.lat, lon=ap.lon;
  var extLinks='<div class="ext-links">';
  extLinks+='<a class="ext-link" href="https://skyvector.com/airport/'+encodeURIComponent(icao)+'" target="_blank" rel="noopener">SkyVector ↗</a>';
  extLinks+='<a class="ext-link" href="https://airnav.com/airport/'+encodeURIComponent(icao)+'" target="_blank" rel="noopener">AirNav ↗</a>';
  extLinks+='<a class="ext-link" href="https://www.faa.gov/airports/airport_safety/airportdata_5010/" target="_blank" rel="noopener">FAA 5010 ↗</a>';
  extLinks+='<a class="ext-link" href="https://www.aviationweather.gov/metar/data?ids='+encodeURIComponent(icao)+'&format=decoded" target="_blank" rel="noopener">Weather ↗</a>';
  extLinks+='<a class="ext-link" href="https://notams.aim.faa.gov/notamSearch/nsapp.html#/" target="_blank" rel="noopener">NOTAMs ↗</a>';
  if(lat&&lon) extLinks+='<a class="ext-link" href="https://www.google.com/maps/search/?api=1&query='+lat+','+lon+'" target="_blank" rel="noopener">Google Maps ↗</a>';
  extLinks+='</div>';

  // Pattern altitude note
  var patNote='';
  if(ap.pattern_altitude_ft) patNote='<p style="font-size:.88rem;color:var(--muted)">Traffic pattern altitude: <strong>'+ap.pattern_altitude_ft+' ft AGL</strong></p>';

  var html=hero+mapDiv+wxDiv+tafDiv;
  // ★ Save airport — calls OCL API if signed in, prompts sign-in otherwise
  var starBtn='<button id="ap-star-btn" onclick="oclStarAirport()" '
    +'style="margin:.6rem 0 1rem;background:none;border:1px solid var(--line);'
    +'border-radius:.5rem;padding:.45rem .9rem;cursor:pointer;font-size:.9rem;color:var(--text)">'
    +'☆ Save airport</button>';

  html+=starBtn;
  html+='<h2 style="margin-top:1.4rem">Airport information</h2>';
  html+=patNote;
  html+='<div class="ap-sections">'+freqHtml+rwyHtml+'</div>';
  html+='<h2>External resources</h2>'+extLinks;
  html+='<p class="tag" style="margin-top:1.5rem">Data from FAA NASR — effective '+
    (window.OCL_NASR_DATE||'current cycle')+'. Always confirm frequencies against current charts and NOTAMs before flight.</p>';
  html+='<p><a href="airports.html">&larr; Back to airport search</a></p>';

  document.getElementById('ap-content').innerHTML=html;

  // Init map after DOM update
  if(ap.lat&&ap.lon) setTimeout(function(){initMap(ap.lat,ap.lon,ap.name||apId);},50);
  if(WX&&(ap.icao||ap.ident)) setTimeout(function(){loadWeather(ap.icao||ap.ident);},100);
}

// ★ Save airport to user profile
function oclStarAirport(){
  var btn=document.getElementById('ap-star-btn');
  if(!btn) return;
  if(!oclToken()){
    sessionStorage.setItem('ocl:return',location.href);
    location.href='/profile';
    return;
  }
  var apId=new URLSearchParams(location.search).get('id')||'';
  var apName=document.querySelector('.ap-name')?document.querySelector('.ap-name').textContent.trim():'';
  btn.disabled=true; btn.textContent='Saving…';
  oclReq('POST','/me/airports',{ident:apId,name:apName})
    .then(function(d){
      if(d.ok||d.error==='airport already saved'){
        btn.textContent='★ Saved';
        btn.style.color='var(--accent)';
        btn.style.borderColor='var(--accent)';
      } else {
        btn.textContent='☆ Save airport';
        btn.disabled=false;
      }
    }).catch(function(){
      btn.textContent='☆ Save airport';
      btn.disabled=false;
    });
}

// Load airport data
function loadAirport(){
  var el=document.getElementById('ap-content');
  el.innerHTML='<p style="color:var(--muted);padding:2rem 0">Loading airport data…</p>';

  fetch('data/airports/icao.json')
    .then(function(r){return r.ok?r.json():Promise.reject('icao index not found');})
    .then(function(icaoMap){
      var shardKey=icaoMap[apId];
      if(!shardKey){
        // try without leading K (non-ICAO idents like FA01)
        var altId=apId.replace(/^K/,'');
        shardKey=icaoMap[altId]||icaoMap['K'+altId];
      }
      if(!shardKey){
        el.innerHTML='<div class="notfound"><p>Airport <strong>'+apId+'</strong> not found.</p><p><a href="airports.html">Search for an airport</a></p></div>';
        return;
      }
      return fetch('data/airports/detail/'+shardKey+'.json')
        .then(function(r){return r.ok?r.json():Promise.reject('shard not found');})
        .then(function(shard){
          var airports=Array.isArray(shard)?shard:Object.values(shard);
          var ap=airports.find(function(a){return (a.icao||a.ident)===apId||(a.ident)===apId;});
          if(!ap) ap=airports.find(function(a){return (a.icao||a.ident||'').toUpperCase()===apId;});
          if(!ap){el.innerHTML='<div class="notfound"><p>Airport not found in data.</p></div>';return;}
          renderAirport(ap);
        });
    })
    .catch(function(e){
      el.innerHTML='<div class="notfound"><p>Could not load airport data. <a href="airports.html">Search airports</a></p></div>';
      console.error(e);
    });
}
loadAirport();
})();
"""

AIRPORT_DETAIL_BODY = """
<div id="ap-content">
  <p style="color:var(--muted);padding:2rem 0">Loading…</p>
</div>
"""


def airport_detail_page(head_fn, foot: str, wx_proxy: str = "") -> str:
    """Per-airport bookmarkable page. URL: airport.html?id=KJFK"""
    cfg = f"<script>window.OCL_WX_PROXY={__import__('json').dumps(wx_proxy)};</script>" if wx_proxy else ""
    # Read NASR cycle date from meta.json if available
    nasr_date_js = ""
    import pathlib, json as _json
    meta = pathlib.Path(__file__).resolve().parent.parent / "data" / "airports" / "meta.json"
    if meta.exists():
        try:
            m = _json.loads(meta.read_text())
            nasr_date_js = f"<script>window.OCL_NASR_DATE={_json.dumps(m.get('effective',''))};</script>"
        except Exception:
            pass
    return (
        head_fn(
            "Airport — Open Checklists",
            "Frequencies, runways, weather and links for US airports. "
            "From the FAA's public-domain NASR data.",
        )
        + f"<style>{AIRPORT_DETAIL_CSS}</style>"
        + AIRPORT_DETAIL_BODY
        + cfg
        + nasr_date_js
        + f"<script>{AIRPORT_DETAIL_JS}</script>"
        + foot
    )


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
