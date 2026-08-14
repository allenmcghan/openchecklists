#!/usr/bin/env python3
"""Single-file airport detail app.

Replaces ~19,000 pre-rendered static airport pages with ONE client-rendered
template served for every /airport/<id>/ URL (via a Cloudflare _redirects
rewrite). This keeps the Cloudflare Pages deployment under the 20,000-file
limit while preserving the full rich page: Leaflet map with layers, live
weather (OCL worker proxy -> Open-Meteo fallback), NOTAMs, fuel, winds aloft,
PIREPs, sun times, runways and frequencies.

Facts (runways, frequencies, elevation, etc.) are read client-side from the
same NASR detail shards already shipped to /data/airports/detail/<K>.json —
the exact data the static generator baked in. Live data is fetched from the
absolute worker/Open-Meteo endpoints, identical to the old static pages.

All internal links and data fetches use ABSOLUTE (/-rooted) paths because the
page is served from arbitrary /airport/<id>/ URLs via rewrite, so relative
paths would resolve against the wrong base.
"""

from __future__ import annotations

# CSS — carried over verbatim from the old static renderer so the page looks
# identical to what was already reviewed and approved.
AIRPORT_APP_CSS = """
#map{height:300px;border-radius:var(--radius);margin:1.5rem 0;border:1px solid var(--line);overflow:hidden}
.fact-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.65rem;margin:1rem 0 1.5rem}
.fact-card{background:#fff;border:1px solid var(--line);border-radius:var(--radius-sm);padding:.8rem .9rem}
.fact-card .lbl{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:.2rem}
.fact-card .val{font-size:1rem;font-weight:700}
.rwy-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin:.8rem 0}
.rwy-chip{background:var(--card);border:1px solid var(--line);border-radius:var(--pill);padding:.4rem .9rem;font-size:.88rem;font-weight:600;cursor:pointer;color:var(--fg);transition:background .15s,border-color .15s}
.rwy-chip:hover,.rwy-chip.active{background:var(--accent-weak);border-color:var(--accent-2);color:var(--accent)}
.rwy-detail{display:none;background:var(--card);border-radius:var(--radius-sm);padding:1rem 1.1rem;margin:.35rem 0 .8rem;border:1px solid var(--line);font-size:.9rem}
.rwy-detail.open{display:block}
.rwy-detail p{margin:.3rem 0}
.live-card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:1.1rem 1.2rem;margin:.8rem 0;box-shadow:var(--shadow-sm)}
.live-card h3{margin:0 0 .5rem;font-size:1rem;font-weight:700}
.spinner-sm{display:inline-block;width:13px;height:13px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:rsp .7s linear infinite;vertical-align:middle;margin-right:.4rem}
@keyframes rsp{to{transform:rotate(360deg)}}
.wx-badge{display:inline-block;padding:.18rem .52rem;border-radius:var(--pill);font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;vertical-align:middle}
.wx-vfr{background:var(--ok-weak);color:var(--ok)}
.wx-mvfr{background:var(--caut-weak);color:var(--caut)}
.wx-ifr{background:var(--warn-weak);color:var(--warn)}
.freq-ctaf{font-weight:700;color:var(--accent)}
.ext-links{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}
.ext-links a{display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .8rem;border:1px solid var(--line);border-radius:var(--pill);font-size:.84rem;color:var(--muted);text-decoration:none}
.ext-links a:hover{border-color:var(--accent-2);color:var(--accent)}
.ap-notfound{padding:3rem 0;text-align:center;color:var(--muted)}
"""

AIRPORT_APP_BODY = """
<div id="ap-root"><p class="muted" style="padding:2rem 0"><span class="spinner-sm"></span> Loading airport…</p></div>
"""

# The whole client app. Raw string (no .format) — the only server-injected
# value is the NASR effective date, substituted via a literal __EFFDATE__ token.
AIRPORT_APP_JS = r"""
(function(){
  var API_BASE = 'https://app.openchecklists.net/api/airport/';

  function esc(s){ return String(s==null?'':s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // Identifier comes from the path (/airport/kbna/ or /airport/kbna) or ?id=
  function getIdent(){
    var q = new URLSearchParams(location.search).get('id');
    if (q) return q.trim().toUpperCase();
    var parts = location.pathname.replace(/\/+$/,'').split('/');
    var last = parts[parts.length-1] || '';
    if (last && last.toLowerCase() !== 'airport' && last.toLowerCase() !== 'index.html')
      return last.toUpperCase();
    return '';
  }

  function shardKey(ident){
    var k = ident[0] ? ident[0].toUpperCase() : '_';
    if (!/[A-Z0-9]/.test(k)) k = '_';
    return k;
  }

  function notFound(root, ident){
    root.innerHTML = '<div class="ap-notfound"><h1 style="font-size:1.4rem">Airport not found</h1>' +
      '<p>No record for <strong>' + esc(ident || '(none)') + '</strong> in the FAA NASR data.</p>' +
      '<p><a class="cta" href="/airports.html">Search all airports</a></p></div>';
  }

  async function boot(){
    var root = document.getElementById('ap-root');
    var ident = getIdent();
    if (!ident){ notFound(root, ''); return; }

    // Resolve ICAO aliases (e.g. KXNX -> XNX) then load the detail shard.
    var icao = {};
    try { icao = await (await fetch('/data/airports/icao.json')).json(); } catch(e){ icao = {}; }
    var resolved = icao[ident] || ident;
    var shard;
    try {
      shard = await (await fetch('/data/airports/detail/' + shardKey(resolved) + '.json')).json();
    } catch(e){ notFound(root, ident); return; }

    var a = shard[resolved] || shard[ident];
    if (!a){
      // Last resort: try stripping/adding a leading K.
      var alt = ident.charAt(0)==='K' ? ident.slice(1) : 'K'+ident;
      a = shard[alt] || (icao[alt] ? shard[icao[alt]] : null);
    }
    if (!a){ notFound(root, ident); return; }

    renderAirport(root, a);
  }

  function renderAirport(root, a){
    var ident = a.ident || '';
    var name = a.name || ident;
    var city = a.city || '';
    var state = a.state_name || a.state || '';
    var elevation = (a.elevation_ft != null) ? a.elevation_ft : '';
    var patAlt = a.pattern_altitude_ft || '';
    var sectional = a.sectional || '';
    var status = a.status || 'Open';
    var owner = a.owner || 'Unknown';
    var phone = (a.manager_phone || '').trim();
    var lat = (a.lat === '' || a.lat == null) ? null : parseFloat(a.lat);
    var lon = (a.lon === '' || a.lon == null) ? null : parseFloat(a.lon);
    if (isNaN(lat)) lat = null;
    if (isNaN(lon)) lon = null;

    document.title = name + ' (' + ident + ') — ' + city + ', ' + state + ' — Open Checklists';

    var h = '';
    h += '<div style="display:flex;align-items:baseline;gap:.8rem;flex-wrap:wrap;margin-bottom:.2rem">' +
         '<span style="font-size:2.6rem;font-weight:800;letter-spacing:-.04em;color:var(--accent);line-height:1">' + esc(ident) + '</span>' +
         '<span class="badge">' + esc(status) + '</span></div>';
    h += '<h1 style="margin:.1rem 0 .05rem;font-size:1.5rem">' + esc(name) + '</h1>';
    h += '<p class="lede" style="margin:0 0 1.2rem;font-size:.95rem">' + esc(city) + ', ' + esc(state) + '</p>';

    h += '<div class="fact-grid">' +
      '<div class="fact-card"><div class="lbl">Elevation</div><div class="val">' + (elevation !== '' ? esc(elevation) : '—') + ' ft MSL</div></div>' +
      '<div class="fact-card"><div class="lbl">Pattern Alt</div><div class="val">' + (patAlt ? esc(patAlt) : '—') + ' ft</div></div>' +
      '<div class="fact-card"><div class="lbl">Sectional</div><div class="val">' + (sectional ? esc(sectional) : '—') + '</div></div>' +
      '<div class="fact-card"><div class="lbl">Ownership</div><div class="val">' + esc(owner) + '</div></div>' +
      (phone ? '<div class="fact-card"><div class="lbl">Phone</div><div class="val"><a href="tel:' + esc(phone) + '">' + esc(phone) + '</a></div></div>' : '') +
      '</div>';

    h += '<div style="margin:0 0 1.8rem">' +
      '<a class="cta" href="/planner.html?dep=' + encodeURIComponent(ident) + '" style="font-size:.88rem;min-height:2.4rem;padding:.5rem 1.1rem">✈ Plan a flight from ' + esc(ident) + '</a></div>';

    // Map placeholder
    if (lat != null && lon != null) h += '<section id="map"></section>';

    // Runways
    h += '<h2>Runways</h2>';
    if (a.runways && a.runways.length){
      h += '<div class="rwy-chips">';
      a.runways.forEach(function(r){
        if (r.id) h += '<button class="rwy-chip" onclick="oclToggleRwy(this,\'' + esc(r.id) + '\')">' + esc(r.id) + '</button>';
      });
      h += '</div>';
      a.runways.forEach(function(r){
        if (!r.id) return;
        var dims = ((r.length_ft || '?') ) + ' × ' + (r.width_ft || '?') + ' ft';
        var surf = r.surface || 'Unknown surface';
        var light = r.lighting || 'Not listed';
        h += '<div class="rwy-detail" id="rwy-' + esc(r.id) + '"><p><strong>' + esc(dims) + '</strong> · ' +
          esc(surf) + ' · Lighting: ' + esc(light) + '</p></div>';
      });
    } else {
      h += '<p class="muted">No runway data on record.</p>';
    }

    // Frequencies
    h += '<h2>Frequencies</h2><div class="scroll"><table class="freqtable">' +
      '<thead><tr><th>MHz</th><th>Use</th><th>Facility</th><th>Callsign</th><th>Hours</th></tr></thead><tbody>';
    if (a.frequencies && a.frequencies.length){
      var order = ['CTAF','UNICOM','TOWER','GROUND','CLEARANCE DELIVERY','ATIS','AWOS','ASOS'];
      var sorted = a.frequencies.slice().sort(function(x,y){
        var ix = order.indexOf((x.use||'').toUpperCase()); if (ix<0) ix = 99;
        var iy = order.indexOf((y.use||'').toUpperCase()); if (iy<0) iy = 99;
        return ix - iy || (x.use||'').localeCompare(y.use||'');
      });
      sorted.forEach(function(f){
        var use = (f.use||'');
        var ctaf = ['CTAF','UNICOM','TOWER'].indexOf(use.toUpperCase()) !== -1;
        var cls = ctaf ? ' class="freq-ctaf"' : '';
        h += '<tr><td' + cls + '>' + esc(f.frequency||'') + '</td><td' + cls + '>' + esc(use) + '</td><td>' +
          esc(f.facility||'') + '</td><td>' + esc(f.callsign||'') + '</td><td>' + esc(f.hours||'') + '</td></tr>';
      });
    } else {
      h += '<tr><td colspan="5" class="muted">No frequencies on record.</td></tr>';
    }
    h += '</tbody></table></div>';

    // Sun times
    if (lat != null && lon != null){
      h += '<div class="live-card" style="margin:.8rem 0"><h3 style="margin:0 0 .5rem">Sun Times</h3>' +
        '<div id="sun-times" style="display:flex;gap:1.5rem;flex-wrap:wrap;font-size:.9rem">' +
        '<div><span class="lbl">Sunrise</span><br><strong id="sun-rise">—</strong></div>' +
        '<div><span class="lbl">Sunset</span><br><strong id="sun-set">—</strong></div>' +
        '<div><span class="lbl">Civil Twilight</span><br><strong id="sun-twilight">—</strong></div>' +
        '<div><span class="lbl">Day Length</span><br><strong id="sun-daylen">—</strong></div></div></div>';
    }

    // Live data
    var windy = '';
    if (lat != null && lon != null){
      windy = '<div id="windy-wrap" style="display:none;margin:.6rem 0;border-radius:var(--radius);overflow:hidden;border:1px solid var(--line)">' +
        '<iframe width="100%" height="360" src="https://embed.windy.com/embed2.html?lat=' + lat + '&lon=' + lon +
        '&zoom=10&level=surface&overlay=wind&product=ecmwf&menu=&message=true&marker=true&metricWind=kt&metricTemp=%C2%B0F" ' +
        'frameborder="0" loading="lazy" title="Windy weather map"></iframe></div>';
    }
    h += '<h2>Live Data</h2>' +
      '<div id="weather" class="live-card"><span class="spinner-sm"></span> Loading weather...</div>' + windy +
      '<div id="notams" class="live-card"><span class="spinner-sm"></span> Loading NOTAMs...</div>' +
      '<div id="fuel" class="live-card"><span class="spinner-sm"></span> Loading fuel &amp; FBO...</div>' +
      '<div id="winds-aloft" class="live-card"><span class="spinner-sm"></span> Loading winds aloft...</div>' +
      '<div id="pireps" class="live-card"><span class="spinner-sm"></span> Loading PIREPs...</div>';

    // External links
    var elat = (lat != null) ? lat : '0', elon = (lon != null) ? lon : '0';
    h += '<h2>External Links</h2><div class="ext-links">' +
      '<a href="https://skyvector.com/?ll=' + elat + ',' + elon + '" target="_blank" rel="noopener">📡 SkyVector</a>' +
      '<a href="https://www.airnav.com/airports/' + encodeURIComponent(ident) + '" target="_blank" rel="noopener">📋 AirNav</a>' +
      '<a href="https://notams.faa.gov/notamSearch/search" target="_blank" rel="noopener">⚠ FAA NOTAMs</a>' +
      '<a href="https://aviationweather.gov/metar?ids=' + encodeURIComponent(ident) + '" target="_blank" rel="noopener">🌤 Wx Forecast</a></div>';

    h += '<h2>Live Resources</h2><div class="ext-links">' +
      '<a href="https://www.liveatc.net/search/?icao=' + encodeURIComponent(ident) + '" target="_blank" rel="noopener">🎧 LiveATC Audio</a>' +
      '<a href="https://www.flightaware.com/live/airport/' + encodeURIComponent(ident) + '" target="_blank" rel="noopener">✈ FlightAware</a>' +
      '<a href="https://weathercams.faa.gov/" target="_blank" rel="noopener">📷 FAA WxCams</a>' +
      '<a href="https://www.1800wxbrief.com/" target="_blank" rel="noopener">📋 1800wxBrief</a></div>';

    h += '<p class="tag" style="margin-top:1.5rem">Data from FAA NASR — effective __EFFDATE__. ' +
      'Always confirm frequencies against current charts and NOTAMs before flight.</p>';
    h += '<p><a href="/airports.html">← Back to airport search</a></p>';

    root.innerHTML = h;

    // Wire globals for the live-data layer, then run the map + live fetches.
    window.OCL_AIRPORT = ident;
    window.OCL_API_BASE = API_BASE;
    window.OCL_LAT = lat;
    window.OCL_LON = lon;

    if (lat != null && lon != null){
      initMap(lat, lon, ident, name, city, state, elevation);
      renderSunTimes(lat, lon);
    }
    setTimeout(loadLiveData, 300);
  }

  function initMap(lat, lon, ident, name, city, state, elevation){
    if (typeof L === 'undefined') return;
    var map = L.map('map', {zoomControl:true}).setView([lat, lon], 15);
    var streets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'© OpenStreetMap', maxZoom:19});
    var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {attribution:'ESRI World Imagery', maxZoom:19});
    var topo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {attribution:'ESRI World Topo', maxZoom:18});
    satellite.addTo(map);
    L.control.layers({'Satellite':satellite, 'Terrain':topo, 'Street':streets}, {}, {position:'topright', collapsed:false}).addTo(map);
    L.marker([lat, lon]).addTo(map)
      .bindPopup('<strong>' + esc(ident) + '</strong><br>' + esc(name) + '<br>' + esc(city) + ', ' + esc(state) +
        '<br>Elev: ' + (elevation !== '' ? esc(elevation) : 'N/A') + ' ft').openPopup();
  }

  // Runway detail toggle — exposed globally for inline onclick.
  window.oclToggleRwy = function(btn, id){
    var el = document.getElementById('rwy-' + id);
    if (!el) return;
    var open = el.classList.toggle('open');
    btn.classList.toggle('active', open);
  };

  // ---- Sun times (USNO algorithm, no API) ----
  function renderSunTimes(lat, lon){
    if (!lat || !lon) return;
    function calc(date, lat, lon, rise, zenithCos){
      var D2R = Math.PI/180, R2D = 180/Math.PI;
      var day = Math.floor((date - new Date(date.getFullYear(),0,0)) / 86400000);
      var lonHour = lon/15;
      var t = rise ? day + ((6 - lonHour)/24) : day + ((18 - lonHour)/24);
      var M = (0.9856*t) - 3.289;
      var L = M + (1.916*Math.sin(M*D2R)) + (0.020*Math.sin(2*M*D2R)) + 282.634;
      L = ((L%360)+360)%360;
      var RA = R2D*Math.atan(0.91764*Math.tan(L*D2R));
      RA = ((RA%360)+360)%360;
      var Lq = Math.floor(L/90)*90, RAq = Math.floor(RA/90)*90;
      RA = (RA + Lq - RAq)/15;
      var sinDec = 0.39782*Math.sin(L*D2R);
      var cosDec = Math.cos(Math.asin(sinDec));
      var cosH = (zenithCos - (sinDec*Math.sin(lat*D2R))) / (cosDec*Math.cos(lat*D2R));
      if (cosH > 1 || cosH < -1) return null;
      var H = rise ? 360 - R2D*Math.acos(cosH) : R2D*Math.acos(cosH);
      H = H/15;
      var T = H + RA - (0.06571*t) - 6.622;
      var UT = T - lonHour;
      UT = ((UT%24)+24)%24;
      var hrs = Math.floor(UT), mins = Math.round((UT-hrs)*60);
      return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hrs, mins));
    }
    function fmtUTC(d){ return d ? d.toISOString().slice(11,16) + 'Z' : 'N/A'; }
    function fmtLocal(d){ if(!d) return 'N/A'; try { return d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}); } catch(e){ return fmtUTC(d); } }
    var today = new Date();
    var sr = calc(today, lat, lon, true, -0.01454);
    var ss = calc(today, lat, lon, false, -0.01454);
    var ct = calc(today, lat, lon, false, -0.10453);
    var dawn = calc(today, lat, lon, true, -0.10453);
    var ri = document.getElementById('sun-rise'), si = document.getElementById('sun-set'),
        ti = document.getElementById('sun-twilight'), di = document.getElementById('sun-daylen');
    if (ri) ri.textContent = sr ? fmtLocal(sr) + ' (' + fmtUTC(sr) + ')' : 'N/A';
    if (si) si.textContent = ss ? fmtLocal(ss) + ' (' + fmtUTC(ss) + ')' : 'N/A';
    if (ti) ti.textContent = 'Begin ' + (dawn ? fmtLocal(dawn) : 'N/A') + ' / End ' + (ct ? fmtLocal(ct) : 'N/A');
    if (sr && ss && ss < sr) ss = new Date(ss.getTime() + 86400000);
    if (di && sr && ss){
      var mins = Math.round((ss - sr) / 60000);
      di.textContent = Math.floor(mins/60) + 'h ' + (mins%60) + 'm';
    }
  }

  async function fetchLive(url, timeout){
    var ctrl = new AbortController();
    var t = setTimeout(function(){ ctrl.abort(); }, timeout || 6000);
    try { var r = await fetch(url, {signal:ctrl.signal, cache:'no-store'}); clearTimeout(t); return r; }
    catch(e){ clearTimeout(t); throw e; }
  }

  async function loadLiveData(){
    var ident = window.OCL_AIRPORT;
    var base = window.OCL_API_BASE;

    function wxBadge(cat){
      if (!cat) return '';
      cat = cat.toUpperCase();
      var cls = cat === 'VFR' ? 'wx-vfr' : cat === 'MVFR' ? 'wx-mvfr' : 'wx-ifr';
      return '<span class="wx-badge ' + cls + '">' + cat + '</span> ';
    }
    function windyBtn(){
      return '<p style="margin:.6rem 0 0"><button onclick="oclShowWindy()" style="background:none;border:1px solid var(--line);border-radius:999px;padding:.28rem .75rem;font:inherit;font-size:.8rem;cursor:pointer;color:var(--muted)">🌐 Show weather map</button></p>';
    }
    function renderOCLWeather(el, d){
      var metar = d.metar || null, taf = d.taf || null;
      el.innerHTML = '<h3>Weather ' + wxBadge(d.flight_category) + '</h3>' +
        (metar ? '<p><strong>METAR:</strong> <code>' + esc(metar) + '</code></p>' : '') +
        (taf ? '<details style="margin:.3rem 0"><summary style="cursor:pointer;font-size:.88rem;font-weight:600">TAF</summary><p style="margin:.3rem 0"><code style="font-size:.8rem;white-space:pre-wrap">' + esc(taf) + '</code></p></details>' : '') +
        windyBtn();
    }
    var WMO = {0:'Clear sky',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',45:'Fog',48:'Freezing fog',
      51:'Light drizzle',53:'Drizzle',55:'Heavy drizzle',61:'Light rain',63:'Rain',65:'Heavy rain',
      71:'Light snow',73:'Snow',75:'Heavy snow',77:'Snow grains',80:'Light showers',81:'Showers',
      82:'Heavy showers',95:'Thunderstorm',96:'T-storm + hail',99:'T-storm + heavy hail'};
    function renderOpenMeteo(el, c){
      var desc = WMO[c.weather_code] || 'Unknown';
      var wspd = Math.round(c.wind_speed_10m || 0);
      var wgst = c.wind_gusts_10m ? Math.round(c.wind_gusts_10m) : null;
      var wdir = c.wind_direction_10m || 0;
      var tempF = c.temperature_2m != null ? Math.round(c.temperature_2m) + '°F' : '';
      var rhum = c.relative_humidity_2m ? c.relative_humidity_2m + '% RH' : '';
      var windStr = wdir + '° at ' + wspd + (wgst ? '/' + wgst : '') + ' kt';
      var cards = [['Conditions',desc],['Wind',windStr], tempF?['Temp',tempF]:null, rhum?['Humidity',rhum]:null]
        .filter(Boolean).map(function(p){ return '<div class="fact-card"><div class="lbl">' + p[0] + '</div><div class="val" style="font-size:.9rem">' + esc(p[1]) + '</div></div>'; }).join('');
      el.innerHTML = '<h3>Conditions <small style="font-weight:400;font-size:.72rem;color:var(--muted)"> Open-Meteo · no METAR at this airport</small></h3>' +
        '<div class="fact-grid" style="margin:.4rem 0 .5rem">' + cards + '</div>' +
        '<p class="muted" style="font-size:.75rem;margin:.1rem 0">Forecast model only — not a certified METAR. <a href="https://aviationweather.gov/metar?ids=' + encodeURIComponent(ident) + '" target="_blank" rel="noopener">Check nearest METAR ↗</a></p>' +
        windyBtn();
    }
    async function loadWeather(){
      var el = document.getElementById('weather');
      var LAT = window.OCL_LAT, LON = window.OCL_LON;
      try {
        var r1 = await fetchLive(base + ident + '/weather', 5000);
        var d1 = await r1.json();
        if (!d1.error && (d1.metar || d1.taf)){ renderOCLWeather(el, d1); return; }
      } catch(e){}
      if (LAT && LON){
        try {
          var omUrl = 'https://api.open-meteo.com/v1/forecast?latitude=' + LAT + '&longitude=' + LON +
            '&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation' +
            '&wind_speed_unit=kn&temperature_unit=fahrenheit&forecast_days=1';
          var r3 = await fetchLive(omUrl, 8000);
          var d3 = await r3.json();
          if (d3 && d3.current){ renderOpenMeteo(el, d3.current); return; }
        } catch(e){}
      }
      el.innerHTML = '<h3>Weather</h3><p class="muted">Weather unavailable. <a href="https://aviationweather.gov" target="_blank" rel="noopener">Check aviationweather.gov →</a></p>' + windyBtn();
    }
    loadWeather();

    // NOTAMs
    try {
      var r2 = await fetchLive(base + ident + '/notams');
      var d2 = await r2.json();
      var el2 = document.getElementById('notams');
      if (d2.error){
        el2.innerHTML = '<h3>NOTAMs</h3><p class="muted">NOTAMs unavailable for this airport. <a href="https://notams.faa.gov/notamSearch/search" target="_blank" rel="noopener">Check FAA NOTAM search</a></p>';
      } else if (d2.notams && d2.notams.length > 0){
        var items = d2.notams.map(function(n){ return '<li style="margin:.35rem 0;font-size:.88rem">' + esc(n.text || n) + '</li>'; }).join('');
        el2.innerHTML = '<h3>NOTAMs (' + d2.notams.length + ')</h3><ul style="padding-left:1.2rem;margin:.4rem 0">' + items + '</ul>';
      } else {
        el2.innerHTML = '<h3>NOTAMs</h3><p style="color:var(--ok)">✓ No active NOTAMs.</p>';
      }
    } catch(e){
      document.getElementById('notams').innerHTML = '<h3>NOTAMs</h3><p>Unable to load. <a href="https://notams.faa.gov/notamSearch/search" target="_blank">Check FAA NOTAM search</a></p>';
    }

    // Fuel
    try {
      var r3 = await fetchLive(base + ident + '/fuel');
      var d3 = await r3.json();
      var el3 = document.getElementById('fuel');
      if (d3.error){
        el3.innerHTML = '<h3>Fuel &amp; FBO</h3><p class="muted">No fuel data on record for this airport.</p>';
      } else {
        var fuels = (d3.fuel_types || []).join(', ') || 'None listed';
        var fbo = d3.fbo_name ? '<br><strong>FBO:</strong> ' + esc(d3.fbo_name) : '';
        el3.innerHTML = '<h3>Fuel &amp; FBO</h3><p><strong>Available:</strong> ' + esc(fuels) + fbo + '</p>';
      }
    } catch(e){
      document.getElementById('fuel').innerHTML = '<h3>Fuel &amp; FBO</h3><p>Unable to load fuel data.</p>';
    }

    // Winds aloft (Open-Meteo pressure levels)
    var elw = document.getElementById('winds-aloft');
    var WLAT = window.OCL_LAT, WLON = window.OCL_LON;
    if (WLAT && WLON){
      try {
        var wUrl = 'https://api.open-meteo.com/v1/forecast?latitude=' + WLAT + '&longitude=' + WLON +
          '&hourly=wind_speed_925hPa,wind_direction_925hPa,wind_speed_850hPa,wind_direction_850hPa,wind_speed_700hPa,wind_direction_700hPa,temperature_850hPa,temperature_700hPa' +
          '&wind_speed_unit=kn&temperature_unit=fahrenheit&forecast_days=1&timezone=auto';
        var rw = await fetchLive(wUrl, 10000);
        var dw = await rw.json();
        if (dw && dw.hourly){
          var hh = dw.hourly;
          var now = new Date();
          var hi = Math.min(now.getHours(), (hh.wind_speed_925hPa || []).length - 1);
          function wrow(alt, spd, dir, temp){
            if (spd == null) return '';
            var kts = Math.round(spd);
            var dirS = dir != null ? Math.round(dir) + '°' : '—';
            var tempS = temp != null ? ' / ' + Math.round(temp) + '°F' : '';
            return '<tr><td>' + alt + '</td><td>' + dirS + ' @ ' + kts + ' kt' + tempS + '</td></tr>';
          }
          var rows =
            wrow('~3,000 ft (925hPa)', hh.wind_speed_925hPa[hi], hh.wind_direction_925hPa[hi], null) +
            wrow('~5,000 ft (850hPa)', hh.wind_speed_850hPa[hi], hh.wind_direction_850hPa[hi], hh.temperature_850hPa ? hh.temperature_850hPa[hi] : null) +
            wrow('~10,000 ft (700hPa)', hh.wind_speed_700hPa[hi], hh.wind_direction_700hPa[hi], hh.temperature_700hPa ? hh.temperature_700hPa[hi] : null);
          elw.innerHTML = rows
            ? '<h3>Winds Aloft <small style="font-weight:400;font-size:.72rem;color:var(--muted)"> Open-Meteo forecast model</small></h3>' +
              '<table style="font-size:.86rem"><thead><tr><th>Altitude</th><th>Wind / Temp</th></tr></thead><tbody>' + rows + '</tbody></table>'
            : '<h3>Winds Aloft</h3><p class="muted">No winds aloft data.</p>';
        } else {
          elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">Winds aloft data unavailable.</p>';
        }
      } catch(e){
        elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">Winds aloft unavailable.</p>';
      }
    } else if (elw){
      elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">No coordinates for this airport.</p>';
    }

    // PIREPs
    try {
      var rp = await fetchLive('https://app.openchecklists.net/api/proxy/pirep/' + ident, 8000);
      var dp = await rp.json();
      var elp = document.getElementById('pireps');
      if (dp && Array.isArray(dp) && dp.length > 0){
        var recent = dp.slice(0, 5);
        var items = recent.map(function(p){
          var alt = p.altitude ? p.altitude + ' ft' : '';
          var sky = p.skyCondition || '';
          var turb = p.turbulence ? ' · Turb: ' + p.turbulence : '';
          var ice = p.icing ? ' · Ice: ' + p.icing : '';
          var loc = p.location || p.icaoId || '';
          return '<li style="margin:.35rem 0;font-size:.85rem"><strong>' + esc(alt || loc) + '</strong>' + esc(turb) + esc(ice) + (sky ? ' · ' + esc(sky) : '') + '</li>';
        }).join('');
        elp.innerHTML = '<h3>PIREPs — nearby pilot reports (' + dp.length + ')</h3><ul style="padding-left:1.2rem;margin:.3rem 0">' + items + '</ul>';
      } else {
        elp.innerHTML = '<h3>PIREPs</h3><p class="muted">No recent pilot reports within 50 nm.</p>';
      }
    } catch(e){
      document.getElementById('pireps').innerHTML = '<h3>PIREPs</h3><p class="muted">Pilot reports unavailable.</p>';
    }
  }

  window.oclShowWindy = function(){
    var w = document.getElementById('windy-wrap');
    if (w){ w.style.display = 'block'; w.scrollIntoView({behavior:'smooth', block:'nearest'}); }
  };

  boot();
})();
"""


def airport_app_page(head_fn, effective_date: str = "current cycle") -> str:
    """Return the single client-rendered airport template.

    head_fn: the site head() function. Called with rel="/" so every nav and
    asset link is absolute — required because this file is served from many
    /airport/<id>/ URLs via a Cloudflare rewrite.
    """
    js = AIRPORT_APP_JS.replace("__EFFDATE__", effective_date or "current cycle")
    return (
        head_fn(
            "Airport — Open Checklists",
            "Frequencies, runways, live weather, NOTAMs, winds aloft and PIREPs "
            "for US airports, from the FAA's public-domain NASR data.",
            rel="/",
        )
        + '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'
        + f"<style>{AIRPORT_APP_CSS}</style>"
        + AIRPORT_APP_BODY
        + '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        + f"<script>{js}</script>"
        + """</main>
<footer class="site"><div class="wrap">
<p><strong>Nothing here is approved data.</strong> Always verify with current official sources before flight.</p>
<p class="fnav">
<a href="/">Home</a> &middot;
<a href="/airports.html">Airports</a> &middot;
<a href="/planner.html">Plan a Flight</a> &middot;
<a href="/training.html">Training</a> &middot;
<a href="/catalogue.html">Checklists</a> &middot;
<a href="/privacy.html">Privacy</a> &middot;
<a href="/terms.html">Terms</a>
</p>
</div></footer>
<script>
if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js').catch(function(){}); }
</script>
</body>
</html>"""
    )
