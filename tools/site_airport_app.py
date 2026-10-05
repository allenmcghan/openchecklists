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
.ap-ssr h1{font-size:1.5rem;margin:.6rem 0}.ap-ssr h2{font-size:1.05rem;margin:1rem 0 .3rem}
.ap-ssr table{border-collapse:collapse;font-size:.88rem;margin:.3rem 0}.ap-ssr th,.ap-ssr td{padding:.2rem .6rem;text-align:left;border-bottom:1px solid #e8edf4}
#map{height:460px;border-radius:var(--radius);margin:.8rem 0 1.5rem;border:1px solid var(--line);overflow:hidden}
@media(min-width:800px){#map{height:560px}}
.ap-controls{display:flex;flex-wrap:wrap;gap:.6rem 1rem;align-items:flex-end;margin:.4rem 0 .2rem}
.ap-controls .ctl{display:flex;flex-direction:column;gap:.2rem}
.ap-controls label{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.ap-controls select,.ap-controls input[type=date]{font:inherit;padding:.45rem .6rem;border:1px solid var(--line);border-radius:var(--radius-sm);background:#fff;min-height:2.5rem}
.ap-actions{display:flex;flex-wrap:wrap;gap:.5rem;margin-left:auto}
.ap-btn{display:inline-flex;align-items:center;gap:.35rem;padding:.5rem .85rem;border:1px solid var(--line);border-radius:var(--pill);background:#fff;font-size:.85rem;font-weight:600;cursor:pointer;color:var(--accent)}
.ap-btn:hover{border-color:var(--accent-2);background:var(--accent-weak)}
.ap-btn[disabled]{opacity:.5;cursor:wait}
.fc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:.5rem;margin:.5rem 0}
.fc-day{border:1px solid var(--line);border-radius:var(--radius-sm);padding:.6rem;background:var(--card);text-align:center}
.fc-day .d{font-size:.72rem;font-weight:700;color:var(--muted)}
.fc-day .t{font-size:1.05rem;font-weight:700;margin:.2rem 0}
.leaflet-container{font:inherit}
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
.near-t,.xw-t{border-collapse:collapse;font-size:.88rem;width:100%;margin:.3rem 0}
.near-t th,.near-t td,.xw-t th,.xw-t td{padding:.3rem .5rem;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
.near-t small{color:var(--muted)}
.xw-in{display:flex;flex-wrap:wrap;gap:.5rem .8rem;align-items:flex-end;margin:.3rem 0 .6rem}
.xw-in label{display:flex;flex-direction:column;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);gap:.15rem}
.xw-in input,.xw-in select{font:inherit;padding:.35rem .5rem;border:1px solid var(--line);border-radius:var(--radius-sm);background:#fff;width:6.5rem}
.xw-in select{width:auto}
.xw-t tr.best td{background:var(--ok-weak);font-weight:700}
.xw-tail{color:var(--warn);font-weight:700}
.xw-note{font-size:.78rem;color:var(--muted);margin:.4rem 0 0}
.brief-cta{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem 1rem;justify-content:space-between;
background:var(--caut-weak);border:1px solid var(--caut);border-radius:var(--radius);padding:.85rem 1.1rem;margin:.4rem 0 1rem;font-size:.9rem}
.brief-cta strong{color:var(--caut)}
.brief-cta-btn{background:var(--caut);color:#fff;border-radius:var(--pill);padding:.5rem 1rem;font-weight:700;white-space:nowrap;font-size:.85rem}
.brief-cta-btn:hover{text-decoration:none;filter:brightness(1.08)}
.wx-obs{font-weight:400;font-size:.72rem;color:var(--muted);margin-left:.4rem}
.wx-notbrief{font-size:.78rem;color:var(--caut);margin:.5rem 0 .1rem;font-weight:600}
.wx-src{font-size:.74rem;color:var(--muted);margin:.5rem 0 .1rem}
.wx-glossary{background:var(--card);border:1px solid var(--line);border-radius:var(--radius-sm);padding:.7rem 1rem;margin:.6rem 0;font-size:.88rem}
.wx-glossary summary{cursor:pointer;font-weight:600;color:var(--accent)}
.wx-glossary dl{margin:.6rem 0 0}
.wx-glossary dt{font-weight:700;margin:.5rem 0 .1rem;font-family:var(--mono);font-size:.82rem}
.wx-glossary dd{margin:0 0 .1rem;color:var(--muted)}
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
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

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

  // Same title format as the server-rendered /airport/<ID> page (functions/airport/[ident].js).
  var ABBR = {RGNL:'Regional', INTL:'International', MUNI:'Municipal', ARPT:'Airport', FLD:'Field',
              MEML:'Memorial', EXEC:'Executive', CNTY:'County', ARPK:'Airpark'};
  var KEEP = {AFB:1, NAS:1, ARB:1, LLC:1, II:1, III:1};
  function niceName(s){
    return String(s || '').split(/(\s+|-|\/)/).map(function(w){
      var u = w.toUpperCase();
      if (ABBR[u]) return ABBR[u];
      if (KEEP[u]) return u;
      return w.toLowerCase().replace(/^([a-z])/, function(m){ return m.toUpperCase(); });
    }).join('');
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
    // One URL per airport: /airport/<ICAO or FAA id>, served pre-rendered by the
    // Pages Function. Rewrite legacy ?id= links in place so shares use it.
    if (a && location.search && /[?&]id=/.test(location.search) && history.replaceState){
      history.replaceState(null, '', '/airport/' + encodeURIComponent(a.icao || a.ident));
    }
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

    document.title = (a.icao || ident) + ' ' + niceName(name) + ' — ' + niceName(a.city || '') + ', ' + (a.state || '') + ': frequencies, runways, weather';

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

    h += '<div style="margin:0 0 1rem">' +
      '<a class="cta" href="/planner.html?dep=' + encodeURIComponent(ident) + '" style="font-size:.88rem;min-height:2.4rem;padding:.5rem 1.1rem">✈ Plan a flight from ' + esc(ident) + '</a></div>';

    // Controls: aircraft type tailors what's shown; date drives forecast; PDF export.
    h += '<div class="ap-controls">' +
      '<div class="ctl"><label for="ap-actype">Aircraft type</label>' +
      '<select id="ap-actype">' +
      '<option value="ga">Airplane (GA)</option>' +
      '<option value="glider">Glider / Sailplane</option>' +
      '<option value="ultralight">Ultralight (Part 103)</option>' +
      '<option value="drone">Drone (Part 107)</option>' +
      '<option value="helicopter">Helicopter</option>' +
      '<option value="electric">Electric aircraft</option>' +
      '</select></div>' +
      '<div class="ctl"><label for="ap-date">Date</label><input type="date" id="ap-date"></div>' +
      '<div class="ap-actions">' +
      '<button class="ap-btn" id="ap-pdf" type="button">⬇ Save as PDF</button>' +
      '<button class="ap-btn" id="ap-email" type="button">✉ Email PDF</button>' +
      '</div></div>' +
      '<div id="ap-typenote" class="wx-src" style="margin:.1rem 0 0"></div>';

    // Map placeholder
    if (lat != null && lon != null) h += '<section id="map"></section>';

    // Runways
    h += '<h2>Runways</h2>';
    if (a.runways && a.runways.length){
      h += '<div class="rwy-chips">';
      a.runways.forEach(function(r){
        if (r.id) h += '<button class="rwy-chip" data-rwy="' + esc(r.id) + '" onclick="oclToggleRwy(this, this.dataset.rwy)">' + esc(r.id) + '</button>';
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

    // Crosswind calculator (advisory). Filled by setupXwind() after render.
    var XW_ENDS = runwayEnds(a);
    if (XW_ENDS.length){
      h += '<h2>Crosswind calculator</h2><div class="live-card" id="xw">' +
        '<p class="wx-notbrief">⚠ Advisory only — check the actual wind (ATIS/AWOS/tower) and your aircraft\'s ' +
        'demonstrated crosswind component in the POH. Not for runway selection by itself.</p>' +
        '<div class="xw-in">' +
        '<label>Wind from (°)<input id="xw-dir" type="text" maxlength="3" inputmode="numeric" placeholder="e.g. 270 or VRB"></label>' +
        '<label>Speed (kt)<input id="xw-spd" type="number" min="0" max="150" step="1" inputmode="numeric" placeholder="e.g. 12"></label>' +
        '<label>Gust (kt)<input id="xw-gst" type="number" min="0" max="200" step="1" inputmode="numeric" placeholder="optional"></label>' +
        '<label>Wind reference<select id="xw-ref"><option value="T">True (METAR / TAF)</option>' +
        '<option value="M">Magnetic (ATIS / AWOS / tower)</option></select></label>' +
        '</div><div id="xw-src" class="wx-src">Waiting for live wind… or type a wind above.</div>' +
        '<div class="scroll"><table class="xw-t"><thead><tr><th>Runway</th><th>Heading true / mag</th>' +
        '<th>Head / tailwind</th><th>Crosswind</th><th>Gust crosswind</th></tr></thead><tbody id="xw-body"></tbody></table></div>' +
        '<p class="xw-note">Runway headings: the NASR true heading where the FAA publishes one; otherwise runway number × 10 ' +
        '(a magnetic heading, ±5°) converted to true with the airport\'s magnetic variation' +
        (a.magnetic_variation ? ' (' + esc(a.magnetic_variation) + ')' : ' (not on record, so treated as 0°)') +
        '. METAR and TAF winds are relative to TRUE north; ATIS, AWOS broadcasts and tower winds are MAGNETIC. ' +
        'Components are computed against true headings.</p></div>';
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

    // Live data. The Windy map is always shown (its own interactive weather map);
    // the airport map above also has a live precip-radar overlay you can toggle.
    var windy = '';
    if (lat != null && lon != null){
      windy = '<h3 style="margin:1rem 0 .3rem;font-size:1rem">Interactive weather map (Windy)</h3>' +
        '<div id="windy-wrap" style="margin:.3rem 0 1rem;border-radius:var(--radius);overflow:hidden;border:1px solid var(--line)">' +
        '<iframe width="100%" height="420" src="https://embed.windy.com/embed2.html?lat=' + lat + '&lon=' + lon +
        '&detailLat=' + lat + '&detailLon=' + lon +
        '&zoom=9&level=surface&overlay=wind&product=ecmwf&menu=&message=true&marker=&calendar=now&metricWind=kt&metricTemp=%C2%B0F" ' +
        'frameborder="0" loading="lazy" title="Windy weather map"></iframe></div>';
    }
    h += '<h2>Live Data</h2>' +
      // FAR 91.103: this is a pre-check, not a legal briefing. Point pilots at
      // the official source before anything else.
      '<div class="brief-cta"><div><strong>This is a pre-check, not an official weather briefing.</strong>' +
      ' Federal regulations (14 CFR 91.103) require an official briefing before flight.</div>' +
      '<a class="brief-cta-btn" href="https://www.1800wxbrief.com/" target="_blank" rel="noopener">Get your official briefing →</a></div>' +
      '<div id="weather" class="live-card"><span class="spinner-sm"></span> Loading weather...</div>' + windy +
      '<div id="notams" class="live-card"><span class="spinner-sm"></span> Loading NOTAMs...</div>' +
      '<div id="winds-aloft" class="live-card"><span class="spinner-sm"></span> Loading winds aloft...</div>' +
      '<div id="pireps" class="live-card"><span class="spinner-sm"></span> Loading PIREPs...</div>' +
      // Plain-language glossary — the Outsider on the review council couldn't
      // decode METAR / 925hPa / PIREP, so spell them out.
      '<details class="wx-glossary"><summary>What do these terms mean?</summary>' +
      '<dl><dt>METAR</dt><dd>A coded report of current observed weather at the airport.</dd>' +
      '<dt>TAF</dt><dd>Terminal Aerodrome Forecast — the forecast for the airport over the next ~24–30 hours.</dd>' +
      '<dt>VFR / MVFR / IFR / LIFR</dt><dd>Flight-rules category from ceiling and visibility: VFR = good visual conditions, IFR = instrument conditions, LIFR = worst. MVFR is marginal.</dd>' +
      '<dt>Winds aloft</dt><dd>Wind (and temperature) at altitude. 925/850/700&nbsp;hPa are pressure levels ≈ 3,000 / 5,000 / 10,000&nbsp;ft.</dd>' +
      '<dt>PIREP</dt><dd>Pilot report — turbulence, icing, or cloud tops reported by pilots actually flying nearby.</dd>' +
      '<dt>NOTAM</dt><dd>Notice to Air Missions — temporary hazards or changes (closed runways, unlit towers, TFRs).</dd></dl></details>';

    // Charts & external references. FAA search URLs need the current cycle id.
    h += '<h2>Charts, diagram &amp; references</h2><div class="ext-links">' +
      chartLinks(a).map(function(l){
        return '<a href="' + esc(l[1]) + '" target="_blank" rel="noopener">' + esc(l[0]) + '</a>';
      }).join('') +
      '<a href="https://notams.faa.gov/notamSearch/search" target="_blank" rel="noopener">⚠ FAA NOTAMs</a>' +
      '<a href="https://aviationweather.gov/data/metar/?ids=' + encodeURIComponent(a.icao || ident) + '&amp;taf=1" target="_blank" rel="noopener">🌤 METAR / TAF</a></div>';

    h += '<div id="ap-near"></div>';

    h += '<h2>Live Resources</h2><div class="ext-links">' +
      '<a href="https://www.liveatc.net/search/?icao=' + encodeURIComponent(a.icao || ident) + '" target="_blank" rel="noopener">🎧 LiveATC Audio</a>' +
      '<a href="https://www.flightaware.com/live/airport/' + encodeURIComponent(a.icao || ident) + '" target="_blank" rel="noopener">✈ FlightAware</a>' +
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
    window.OCL_MAGVAR = parseVar(a.magnetic_variation);

    if (lat != null && lon != null){
      initMap(lat, lon, ident, name, city, state, elevation);
      renderSunTimes(lat, lon);
    }
    setTimeout(loadLiveData, 300);
    setupControls(a);
    if (XW_ENDS.length) setupXwind(XW_ENDS);
    loadNear(a);
  }

  // ---- FAA chart links ----
  // d-TPP (plates, airport diagram) is on the 28-day AIRAC cycle; the Chart
  // Supplement on a 56-day cycle named after the AIRAC cycle it starts in.
  // Must match chartLinks() in functions/airport/[ident].js.
  var DAY = 86400000;
  function airacId(t){
    var ref = Date.UTC(2026, 0, 22);   // AIRAC 2601
    var start = ref + Math.floor((t - ref) / (28*DAY)) * 28*DAY;
    var y = new Date(start).getUTCFullYear();
    var n = Math.floor((start - Date.UTC(y, 0, 1)) / (28*DAY)) + 1;
    return ('0' + (y % 100)).slice(-2) + ('0' + n).slice(-2);
  }
  function supplementCycle(t){
    var ref = Date.UTC(2026, 8, 3);    // Chart Supplement 2609
    return airacId(ref + Math.floor((t - ref) / (56*DAY)) * 56*DAY);
  }
  function chartLinks(a){
    var id = encodeURIComponent(a.ident || ''), now = Date.now(), out = [];
    if (a.use === 'public'){
      out.push(['📐 Airport diagram & procedures (FAA d-TPP)', 'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/search/results/?cycle=' + airacId(now) + '&ident=' + id]);
      out.push(['📖 FAA Chart Supplement', 'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/search/results/?cycle=' + supplementCycle(now) + '&ident=' + id]);
    }
    out.push(['📋 AirNav', 'https://www.airnav.com/airport/' + encodeURIComponent(a.icao || a.ident || '')]);
    out.push(['📡 SkyVector', 'https://skyvector.com/airport/' + id]);
    return out;
  }

  // ---- Runway headings & crosswind ----
  function parseVar(s){
    var m = String(s || '').match(/^(\d+(?:\.\d+)?)\s*([EW])$/i);
    return m ? (m[2].toUpperCase() === 'E' ? 1 : -1) * parseFloat(m[1]) : null;
  }
  function norm(h){ var x = ((Math.round(h) % 360) + 360) % 360; return x === 0 ? 360 : x; }
  function hdg3(h){ return ('00' + h).slice(-3); }
  var COMPASS_END = {N:360, NE:45, E:90, SE:135, S:180, SW:225, W:270, NW:315};
  // East variation: magnetic = true − var; west: magnetic = true + var.
  function runwayEnds(a){
    var v = parseVar(a.magnetic_variation), out = [];
    (a.runways || []).forEach(function(r){
      (r.ends || []).forEach(function(e){
        var t, m, src;
        if (e.true_heading != null && e.true_heading !== ''){
          t = norm(+e.true_heading); m = v != null ? norm(t - v) : null; src = 'NASR';
        } else {
          var id = String(e.end || '').toUpperCase();
          var num = id.match(/^(\d{1,2})[LRCW]?$/);
          m = num ? norm(+num[1] * 10) : (COMPASS_END[id] || null);
          if (m == null) return;
          t = v != null ? norm(m + v) : m; src = 'approx';
        }
        out.push({end: e.end, t: t, m: m, src: src, len: r.length_ft});
      });
    });
    return out;
  }
  function setupXwind(ends){
    var dirI = document.getElementById('xw-dir'), spdI = document.getElementById('xw-spd'),
        gstI = document.getElementById('xw-gst'), refI = document.getElementById('xw-ref'),
        src = document.getElementById('xw-src'), body = document.getElementById('xw-body');
    var variation = null;
    function calc(){
      var raw = dirI.value.trim(), spd = parseFloat(spdI.value), gst = parseFloat(gstI.value);
      var vrb = /^vrb$/i.test(raw), dir = parseFloat(raw);
      if (isNaN(spd) || (!vrb && isNaN(dir))){
        body.innerHTML = ends.map(function(e){
          return '<tr><td>' + esc(e.end) + '</td><td>' + hdg3(e.t) + '°T / ' + (e.m != null ? hdg3(e.m) + '°M' : '—') +
            (e.src === 'approx' ? ' <small>(approx)</small>' : '') + '</td><td colspan="3" class="muted">Enter a wind</td></tr>';
        }).join('');
        return;
      }
      // Manual magnetic wind -> true, using the airport's variation (0 if unknown).
      var wTrue = refI.value === 'M' ? dir + (window.OCL_MAGVAR || 0) : dir;
      var rows = ends.map(function(e){
        if (vrb || spd === 0) return {e: e};
        var ang = (wTrue - e.t) * Math.PI / 180;
        return {e: e, head: spd * Math.cos(ang), cross: spd * Math.sin(ang),
                gcross: isNaN(gst) ? null : gst * Math.sin(ang)};
      });
      var best = null;
      rows.forEach(function(r){
        if (r.head == null) return;
        if (!best || r.head > best.head + 0.5 || (Math.abs(r.head - best.head) <= 0.5 && Math.abs(r.cross) < Math.abs(best.cross))) best = r;
      });
      function side(x){ return Math.round(Math.abs(x)) + ' kt' + (Math.round(Math.abs(x)) ? (x > 0 ? ' from right' : ' from left') : ''); }
      body.innerHTML = rows.map(function(r){
        var e = r.e;
        var hd = hdg3(e.t) + '°T / ' + (e.m != null ? hdg3(e.m) + '°M' : '—') + (e.src === 'approx' ? ' <small>(approx)</small>' : '');
        if (r.head == null){
          return '<tr><td>' + esc(e.end) + '</td><td>' + hd + '</td><td colspan="3">' +
            (spd === 0 ? 'Calm' : 'Variable — crosswind up to ' + Math.round(Math.max(spd, isNaN(gst) ? 0 : gst)) + ' kt') + '</td></tr>';
        }
        var hw = Math.round(r.head);
        var hwTxt = hw >= 0 ? hw + ' kt headwind' : '<span class="xw-tail">' + (-hw) + ' kt tailwind</span>';
        return '<tr' + (r === best ? ' class="best"' : '') + '><td>' + esc(e.end) + (r === best ? ' ★ best' : '') + '</td><td>' + hd +
          '</td><td>' + hwTxt + '</td><td>' + side(r.cross) + '</td><td>' + (r.gcross == null ? '—' : side(r.gcross)) + '</td></tr>';
      }).join('');
    }
    [dirI, spdI, gstI, refI].forEach(function(i){
      i.addEventListener('input', function(){ if (i !== refI) src.textContent = 'Manual wind entry.'; calc(); });
      i.addEventListener('change', calc);
    });
    function setWind(dir, spd, gust, label){
      // Don't overwrite what the pilot has typed.
      if (src.textContent === 'Manual wind entry.') return;
      dirI.value = dir; spdI.value = spd; gstI.value = gust == null ? '' : gust; refI.value = 'T';
      src.textContent = label; calc();
    }
    // METAR winds are TRUE: dddff(Gfff)KT, VRBff, 00000KT = calm.
    window.oclXwMetar = function(metar){
      var m = String(metar || '').match(/\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT\b/);
      if (!m) return;
      var obs = String(metar).match(/\b\d{2}(\d{4})Z\b/);
      setWind(m[1] === 'VRB' ? 'VRB' : +m[1], +m[2], m[3] ? +m[3] : null,
        'Wind from the METAR' + (obs ? ' observed ' + obs[1] + 'Z' : '') + ' (true north). Type to override.');
    };
    window.oclXwModel = function(dir, spd, gust){
      setWind(Math.round(dir), Math.round(spd), gust ? Math.round(gust) : null,
        'No METAR here: wind from the Open-Meteo forecast model (true north) — less reliable. Type to override.');
    };
    calc();
  }

  // ---- Nearest airports (build-time precomputed shard, see site_airport_near.py) ----
  function nearKey(ident){ return (String(ident || '').toUpperCase().slice(0,2).replace(/[^A-Z0-9]/g,'_') + '__').slice(0,2); }
  function loadNear(a){
    var el = document.getElementById('ap-near');
    if (!el) return;
    fetch('/data/airports/near/' + nearKey(a.ident) + '.json').then(function(r){ return r.ok ? r.json() : {}; })
      .then(function(d){
        var n = d[a.ident];
        if (!n) return;
        function link(e){ return '<a href="/airport/' + encodeURIComponent(e[0]) + '">' + esc(e[0]) + '</a>'; }
        var h = '';
        if (n.n && n.n.length){
          h += '<h2>Airports near ' + esc(a.icao || a.ident) + '</h2><div class="scroll"><table class="near-t"><thead><tr>' +
            '<th>Id</th><th>Name</th><th>Distance / bearing</th><th>Longest rwy</th><th>Fuel</th><th>Use</th></tr></thead><tbody>' +
            n.n.map(function(e){
              return '<tr><td>' + link(e) + '</td><td>' + esc(niceName(e[1])) + '<br><small>' + esc(niceName(e[2])) + ', ' + esc(e[3]) +
                '</small></td><td>' + esc(e[4]) + ' nm ' + hdg3(e[5]) + '°T</td><td>' +
                (e[9] === 's' ? 'water' : e[6] ? Number(e[6]).toLocaleString('en-US') + ' ft' + (e[10] ? '' : ' (soft)') : '—') + '</td><td>' + esc(e[7] || '—') +
                '</td><td>' + (e[8] === 'pu' ? 'Public' : 'Private') + '</td></tr>';
            }).join('') + '</tbody></table></div><p class="xw-note">Great-circle distance and true bearing from ' +
            esc(a.icao || a.ident) + '. Heliports not listed.</p>';
        }
        if (n.f && n.f.length) h += '<p><strong>Nearest public airports with fuel:</strong> ' + n.f.map(function(e){
          return link(e) + ' ' + esc(e[4]) + ' nm (' + esc(e[7]) + ')'; }).join(', ') + '</p>';
        if (n.l && n.l.length) h += '<p><strong>Nearest public airports with a runway of 3,000 ft or more:</strong> ' + n.l.map(function(e){
          return link(e) + ' ' + esc(e[4]) + ' nm (' + Number(e[6]).toLocaleString('en-US') + ' ft)'; }).join(', ') + '</p>';
        if (n.cp) h += '<p><a href="/airports-near/' + encodeURIComponent(n.cp[0]) + '/">All airports near ' + esc(n.cp[1]) + ' →</a></p>';
        el.innerHTML = h;
      }).catch(function(){});
  }

  // Aircraft type tailors which data matters. Stored per-browser.
  var ACTYPES = {
    ga:         { hide: [],                       note: '' },
    glider:     { hide: [],                       note: 'Soaring: winds aloft and thermals matter; VFR daylight operations only.' },
    ultralight: { hide: ['winds-aloft','pireps'], note: 'Part 103: daylight only, uncontrolled airspace, stay clear of clouds — surface wind and visibility are what matter.' },
    drone:      { hide: ['winds-aloft','pireps'], note: 'Part 107: max 400 ft AGL, check TFRs and controlled-airspace (LAANC) authorization in NOTAMs; daylight or with anti-collision lighting.' },
    helicopter: { hide: [],                       note: '' },
    electric:   { hide: [],                       note: 'Electric: winds and temperature drive range and endurance — plan conservative reserves.' }
  };
  function applyAircraftType(type){
    var cfg = ACTYPES[type] || ACTYPES.ga;
    ['winds-aloft','pireps'].forEach(function(id){
      var el = document.getElementById(id);
      if (el) el.style.display = (cfg.hide.indexOf(id) !== -1) ? 'none' : '';
    });
    var note = document.getElementById('ap-typenote');
    if (note) note.textContent = cfg.note;
    try { localStorage.setItem('ocl:actype', type); } catch(e){}
  }

  function setupControls(a){
    // Aircraft type
    var sel = document.getElementById('ap-actype');
    if (sel){
      var saved = null; try { saved = localStorage.getItem('ocl:actype'); } catch(e){}
      if (saved && ACTYPES[saved]) sel.value = saved;
      // apply after live-data cards exist
      setTimeout(function(){ applyAircraftType(sel.value); }, 500);
      sel.addEventListener('change', function(){ applyAircraftType(sel.value); });
    }
    // Date → forecast
    var dt = document.getElementById('ap-date');
    if (dt){
      var today = new Date().toISOString().slice(0,10);
      var max = new Date(Date.now() + 15*86400000).toISOString().slice(0,10);
      dt.min = today; dt.max = max; dt.value = today;
      dt.addEventListener('change', function(){
        window.OCL_WXDATE = dt.value || today;
        if (window.__reloadWx) window.__reloadWx();
      });
    }
    var pdfBtn = document.getElementById('ap-pdf');
    if (pdfBtn) pdfBtn.addEventListener('click', function(){ oclAirportPdf(a); });
    var emBtn = document.getElementById('ap-email');
    if (emBtn) emBtn.addEventListener('click', function(){ oclEmailAirportPdf(a, emBtn); });
  }

  // Generate the PDF (as above) and email it as an attachment via the worker.
  function oclEmailAirportPdf(a, btn){
    var tok = sessionStorage.getItem('ocl:token');
    if (!tok){
      if (confirm('Emailing a PDF needs a free account. Sign in now? (You can still use "Save PDF" without one.)')){
        sessionStorage.setItem('ocl:return', location.pathname + location.search);
        location.href = '/profile.html';
      }
      return;
    }
    var doc = buildAirportPdf(a);
    if (!doc) return;
    // The API sends only to the signed-in account's verified email; no address is typed.
    if (!confirm('Email this PDF to the address on your account?')) return;
    var b64 = doc.output('datauristring').split(',')[1];
    var orig = btn.textContent; btn.textContent = 'Sending…'; btn.disabled = true;
    fetch('https://app.openchecklists.net/api/airport/email-pdf', {
      method:'POST', headers:{'Content-Type':'application/json', 'Authorization':'Bearer ' + tok},
      body: JSON.stringify({ ident: a.ident||'', name: a.name||'', pdf_base64: b64 })
    }).then(function(r){ return r.json().catch(function(){ return {error: 'HTTP ' + r.status}; }); }).then(function(d){
      btn.disabled = false;
      if (d.ok){ btn.textContent = '✓ Sent to ' + (d.to || 'your account email'); setTimeout(function(){ btn.textContent = orig; }, 5000); }
      else { btn.textContent = orig; alert('Could not send: ' + (d.error || 'unknown error')); }
    }).catch(function(){ btn.disabled = false; btn.textContent = orig; alert('Could not reach the mail service.'); });
  }

  // Build a clean, structured PDF of the airport from its data + whatever
  // weather is currently shown. Built from data (not a screenshot) so map tiles
  // and the Windy iframe don't need to render into a canvas.
  function oclAirportPdf(a){
    var doc = buildAirportPdf(a);
    if (doc) doc.save((a.ident || 'airport') + '-airport.pdf');
  }
  function buildAirportPdf(a){
    if (!(window.jspdf && window.jspdf.jsPDF)){ alert('PDF library still loading — try again in a second.'); return null; }
    var doc = new window.jspdf.jsPDF({unit:'pt', format:'letter'});
    var M = 48, y = 56, W = 612;
    function line(txt, opts){
      opts = opts || {};
      doc.setFont('helvetica', opts.bold ? 'bold' : 'normal');
      doc.setFontSize(opts.size || 10);
      if (opts.color) doc.setTextColor.apply(doc, opts.color); else doc.setTextColor(20,32,46);
      var lines = doc.splitTextToSize(String(txt), W - 2*M);
      for (var i=0;i<lines.length;i++){ if (y > 720){ doc.addPage(); y = 56; } doc.text(lines[i], M, y); y += (opts.size||10) + 4; }
    }
    function gap(n){ y += (n||8); }
    var ident = a.ident || '', name = a.name || ident;
    line(ident + ' — ' + name, {bold:true, size:20, color:[31,78,121]});
    line((a.city||'') + (a.state_name||a.state ? ', ' + (a.state_name||a.state) : ''), {size:11, color:[90,107,123]});
    gap(6);
    var facts = [];
    if (a.elevation_ft != null) facts.push('Elevation: ' + a.elevation_ft + ' ft MSL');
    if (a.pattern_altitude_ft) facts.push('Pattern: ' + a.pattern_altitude_ft + ' ft');
    if (a.sectional) facts.push('Sectional: ' + a.sectional);
    if (a.owner) facts.push('Ownership: ' + a.owner);
    if (a.lat != null && a.lon != null) facts.push('GPS: ' + Number(a.lat).toFixed(4) + ', ' + Number(a.lon).toFixed(4));
    if ((a.manager_phone||'').trim()) facts.push('Phone: ' + a.manager_phone.trim());
    line(facts.join('   ·   '), {size:10});
    gap(10);
    // Current weather (whatever card is showing)
    var wxEl = document.getElementById('weather');
    if (wxEl){ line('WEATHER', {bold:true, size:12, color:[31,78,121]});
      line(wxEl.innerText.replace(/\s*🌐.*$/,'').replace(/\n{2,}/g,'\n').trim(), {size:9}); gap(8); }
    var sunEl = document.getElementById('sun-times');
    if (sunEl && sunEl.innerText.trim()){ line('SUN TIMES', {bold:true, size:12, color:[31,78,121]});
      line(sunEl.innerText.replace(/\n{2,}/g,'  ').trim(), {size:9}); gap(8); }
    // Runways
    if (a.runways && a.runways.length){
      line('RUNWAYS', {bold:true, size:12, color:[31,78,121]});
      a.runways.forEach(function(r){ if(!r.id) return;
        line(r.id + ':  ' + (r.length_ft||'?') + ' × ' + (r.width_ft||'?') + ' ft · ' + (r.surface||'') + (r.lighting? ' · ' + r.lighting : ''), {size:9}); });
      gap(8);
    }
    // Frequencies
    if (a.frequencies && a.frequencies.length){
      line('FREQUENCIES', {bold:true, size:12, color:[31,78,121]});
      var order = ['CTAF','UNICOM','TOWER','GROUND','CLEARANCE DELIVERY','ATIS','AWOS','ASOS'];
      a.frequencies.slice().sort(function(x,y){var ix=order.indexOf((x.use||'').toUpperCase());if(ix<0)ix=99;var iy=order.indexOf((y.use||'').toUpperCase());if(iy<0)iy=99;return ix-iy;})
        .forEach(function(f){ line((f.frequency||'') + '   ' + (f.use||'') + (f.callsign? '  (' + f.callsign + ')':'') + (f.hours? '  ' + f.hours:''), {size:9}); });
      gap(8);
    }
    gap(6);
    line('Generated ' + new Date().toLocaleString() + ' from openchecklists.net. Unverified snapshot — NOT an official weather briefing. 14 CFR 91.103 requires an official briefing (1800wxbrief.com) before flight.', {size:8, color:[138,90,0]});
    return doc;
  }

  function initMap(lat, lon, ident, name, city, state, elevation){
    if (typeof L === 'undefined') return;
    var map = L.map('map', {zoomControl:true, minZoom:8}).setView([lat, lon], 10);
    window.OCL_MAP = map;
    var streets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'© OpenStreetMap', maxZoom:19});
    var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {attribution:'ESRI World Imagery', maxZoom:19});
    var topo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {attribution:'ESRI World Topo', maxZoom:18});
    // FAA VFR sectional chart tiles (Esri-hosted FAA VFR_Sectional; real chart
    // raster at z9–11, upscaled beyond). Reliable on the Esri CDN.
    var sectional = L.tileLayer('https://tiles.arcgis.com/tiles/ssFJjBXIUyZDrSYZ/arcgis/rest/services/VFR_Sectional/MapServer/tile/{z}/{y}/{x}', {attribution:'VFR Sectional © FAA', minNativeZoom:9, maxNativeZoom:11, maxZoom:15});
    sectional.addTo(map);
    var bases = {'Sectional (VFR)':sectional, 'Satellite':satellite, 'Terrain':topo, 'Street':streets};
    var overlays = {};
    var layerCtl = L.control.layers(bases, overlays, {position:'topright', collapsed:false}).addTo(map);
    L.marker([lat, lon]).addTo(map)
      .bindPopup('<strong>' + esc(ident) + '</strong><br>' + esc(name) + '<br>' + esc(city) + ', ' + esc(state) +
        '<br>Elev: ' + (elevation !== '' ? esc(elevation) : 'N/A') + ' ft').openPopup();
    // Live precipitation radar as a toggleable overlay (RainViewer — free, no key).
    fetch('https://api.rainviewer.com/public/weather-maps.json')
      .then(function(r){ return r.json(); })
      .then(function(d){
        var frames = (d.radar && (d.radar.past || [])).concat((d.radar && d.radar.nowcast) || []);
        if (!frames.length || !d.host) return;
        var latest = frames[frames.length-1];
        var radar = L.tileLayer(d.host + latest.path + '/256/{z}/{x}/{y}/4/1_1.png', {opacity:.6, attribution:'Radar © RainViewer'});
        layerCtl.addOverlay(radar, 'Precip radar (live)');
      }).catch(function(){});
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
    // Pull the HH:MMZ observation time out of a raw METAR (group is DDHHMMZ).
    function obsFromMetar(m){
      if (!m) return '';
      var mm = String(m).match(/\b\d{2}(\d{2})(\d{2})Z\b/);
      return mm ? (mm[1] + ':' + mm[2] + 'Z') : '';
    }
    // Every live-weather card carries this: the category badge is not a briefing.
    var NOT_BRIEF = '<p class="wx-notbrief">⚠ Unverified — not an official weather briefing. ' +
      '<a href="https://www.1800wxbrief.com/" target="_blank" rel="noopener">Get a legal briefing →</a></p>';
    var NOTAM_SRC = '<p class="wx-src">Source: FAA via aviationweather.gov · a snapshot, not guaranteed current. ' +
      'Confirm active NOTAMs at <a href="https://notams.faa.gov/notamSearch/search" target="_blank" rel="noopener">the official FAA NOTAM search</a> before flight.</p>';
    function windyBtn(){
      return '';  // Windy map is always shown in its own section now.
    }
    function renderOCLWeather(el, d){
      var metar = d.metar || null, taf = d.taf || null;
      var obs = obsFromMetar(metar);
      el.innerHTML = '<h3>Weather ' + wxBadge(d.flight_category) +
        '<small class="wx-obs">' + (obs ? 'observed ' + obs : 'snapshot') + '</small></h3>' +
        (metar ? '<p><strong>METAR:</strong> <code>' + esc(metar) + '</code></p>' : '') +
        (taf ? '<details style="margin:.3rem 0"><summary style="cursor:pointer;font-size:.88rem;font-weight:600">TAF</summary><p style="margin:.3rem 0"><code style="font-size:.8rem;white-space:pre-wrap">' + esc(taf) + '</code></p></details>' : '') +
        NOT_BRIEF +
        windyBtn();
      if (metar && window.oclXwMetar) window.oclXwMetar(metar);
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
        NOT_BRIEF +
        windyBtn();
      if (window.oclXwModel && c.wind_speed_10m != null) window.oclXwModel(wdir, c.wind_speed_10m, c.wind_gusts_10m);
    }
    function fToday(){ return new Date().toISOString().slice(0,10); }
    function renderForecast(el, d, dateStr){
      var day = (d.daily && d.daily.time) ? d.daily.time.indexOf(dateStr) : -1;
      if (!d.daily || day < 0){ el.innerHTML = '<h3>Forecast</h3><p class="muted">No forecast for ' + esc(dateStr) + '.</p>'; return; }
      var dl = d.daily;
      var wmoTxt = WMO[dl.weather_code ? dl.weather_code[day] : 0] || '';
      var cards = [
        ['Conditions', wmoTxt],
        ['High / Low', Math.round(dl.temperature_2m_max[day]) + '° / ' + Math.round(dl.temperature_2m_min[day]) + '°F'],
        ['Max wind', Math.round(dl.wind_speed_10m_max[day]) + (dl.wind_gusts_10m_max ? ' g' + Math.round(dl.wind_gusts_10m_max[day]) : '') + ' kt ' + (dl.wind_direction_10m_dominant ? Math.round(dl.wind_direction_10m_dominant[day]) + '°' : '')],
        ['Precip chance', (dl.precipitation_probability_max ? dl.precipitation_probability_max[day] : 0) + '%'],
        ['Sunrise', (dl.sunrise ? dl.sunrise[day].slice(11,16) : '—')],
        ['Sunset', (dl.sunset ? dl.sunset[day].slice(11,16) : '—')]
      ].map(function(p){ return '<div class="fact-card"><div class="lbl">' + p[0] + '</div><div class="val" style="font-size:.9rem">' + esc(p[1]) + '</div></div>'; }).join('');
      el.innerHTML = '<h3>Forecast — ' + esc(dateStr) + ' <small style="font-weight:400;font-size:.72rem;color:var(--muted)">Open-Meteo model</small></h3>' +
        '<div class="fact-grid" style="margin:.4rem 0 .5rem">' + cards + '</div>' + NOT_BRIEF;
    }
    async function loadWeather(){
      var el = document.getElementById('weather');
      var LAT = window.OCL_LAT, LON = window.OCL_LON;
      // Future date selected → daily forecast (Open-Meteo, up to 16 days out).
      var wxDate = window.OCL_WXDATE;
      if (wxDate && wxDate !== fToday() && LAT && LON){
        el.innerHTML = '<h3>Forecast</h3><p class="muted"><span class="spinner-sm"></span> Loading forecast for ' + esc(wxDate) + '…</p>';
        try {
          var fUrl = 'https://api.open-meteo.com/v1/forecast?latitude=' + LAT + '&longitude=' + LON +
            '&daily=weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,precipitation_probability_max,sunrise,sunset' +
            '&wind_speed_unit=kn&temperature_unit=fahrenheit&timezone=auto&start_date=' + wxDate + '&end_date=' + wxDate;
          var rf = await fetchLive(fUrl, 9000);
          var df = await rf.json();
          renderForecast(el, df, wxDate); return;
        } catch(e){ el.innerHTML = '<h3>Forecast</h3><p class="muted">Forecast unavailable for ' + esc(wxDate) + '.</p>'; return; }
      }
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
    window.__reloadWx = loadWeather;   // let the date picker re-run just the weather card
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
        el2.innerHTML = '<h3>NOTAMs (' + d2.notams.length + ')</h3><ul style="padding-left:1.2rem;margin:.4rem 0">' + items + '</ul>' + NOTAM_SRC;
      } else {
        el2.innerHTML = '<h3>NOTAMs</h3><p style="color:var(--ok)">✓ No active NOTAMs.</p>' + NOTAM_SRC;
      }
    } catch(e){
      document.getElementById('notams').innerHTML = '<h3>NOTAMs</h3><p>Unable to load. <a href="https://notams.faa.gov/notamSearch/search" target="_blank">Check FAA NOTAM search</a></p>';
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
        + '<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js" defer></script>'
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
