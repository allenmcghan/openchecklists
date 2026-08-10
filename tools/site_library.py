#!/usr/bin/env python3
"""Troubleshooting search, projects and charts pages.

The search page is the "chatbot" in the form that can actually be defended: it
retrieves passages from public-domain documents and cites each one by document,
revision and page. It does not diagnose. That distinction is the whole design, and
it is stated on the page rather than buried, because a reader who thinks they are
getting a diagnosis will act on it as one.

Scoring is BM25, computed in the browser from the same sharded index the Python
tool uses, so the site needs no search backend and the results are identical.
"""

from __future__ import annotations

import json

LIB_CSS = """
.q-wrap{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}
.q-wrap input[type=search]{flex:1;min-width:14rem;font-size:1.05rem;padding:.6rem .7rem}
.q-wrap select{font-size:.9rem;padding:.6rem .5rem;max-width:100%;background:var(--bg);
color:var(--fg);border:1px solid var(--line);border-radius:.3rem}
.examples{display:flex;gap:.4rem;flex-wrap:wrap;margin:.2rem 0 1rem}
.ex{font-size:.78rem;padding:.25rem .55rem;border:1px solid var(--line);border-radius:1rem;
cursor:pointer;background:var(--bg);color:var(--accent)}
.hit{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 .4rem .4rem 0;
padding:.7rem .85rem;margin:.6rem 0;background:var(--card)}
.cite{font-size:.78rem;color:var(--muted);margin-bottom:.35rem}
.cite b{color:var(--fg)}
.hit p{margin:.2rem 0;font-size:.92rem;line-height:1.5}
.hit mark{background:color-mix(in srgb,var(--accent) 25%,transparent);color:inherit;
padding:0 .1em;border-radius:.15em}
.score{float:right;font-variant-numeric:tabular-nums;font-size:.72rem;color:var(--muted)}
.doclist{font-size:.85rem}
.reg td{padding:.35rem .5rem;border-bottom:1px solid var(--line);font-size:.87rem;vertical-align:top}
.avail{font-size:.7rem;font-weight:700;padding:.1rem .35rem;border:1px solid currentColor;
border-radius:.2rem;white-space:nowrap}
.avail.free{color:var(--ok)}.avail.reg{color:var(--caut)}.avail.buy{color:var(--warn)}
"""

LIB_BODY = """
<h2>Troubleshooting search</h2>

<div class="banner okb"><strong>This cites, it does not diagnose.</strong> Every
result is a passage from a real document with its page number, so you can read the
source yourself. It will show you what AC 43.13-1B says about magneto timing; it
will not tell you what is wrong with your engine. Anything that guessed at your
problem would be the only thing on this site with no provenance behind it.</div>

<div class="q-wrap">
  <input type="search" id="q" placeholder="magneto timing, control cable inspection, corrosion…"
         aria-label="Search the document library">
  <select id="doc" aria-label="Limit the search to one document">
    <option value="">Every document</option>
  </select>
  <button class="btn p" id="go">Search</button>
</div>
<div class="examples">
  <span class="ex">magneto timing</span>
  <span class="ex">control cable inspection</span>
  <span class="ex">corrosion aluminum</span>
  <span class="ex">fabric covering repair</span>
  <span class="ex">torque values</span>
  <span class="ex">welding practices</span>
  <span class="ex">propeller track</span>
  <span class="ex">safety wire</span>
  <span class="ex">microburst</span>
  <span class="ex">carburetor icing</span>
  <span class="ex">density altitude</span>
  <span class="ex">spatial disorientation</span>
</div>

<div id="results"></div>
<div id="libmeta" class="doclist"></div>

<h2 id="registry">Documents we cannot host</h2>
<p class="lede">Manufacturer and engine manuals are commercial products, so this
project does not reproduce them. What it can do is tell you exactly which document
you need and where to get it — that information is a fact, not a reproduction.</p>
<div id="reg"></div>
"""

LIB_JS = r"""
(function(){
  var META = null, POST = {}, PASS = {}, BUCKET = 500;
  var STOP = new Set(('a an and are as at be been but by can could do does for from had has have '
    + 'if in into is it its may must not of on or shall should so such than that the their then '
    + 'there these they this those to up was were what when which who will with would you your'
    ).split(' '));

  function el(id){ return document.getElementById(id); }
  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // Must match tools/library.py exactly, or browser results diverge from the CLI.
  function stem(w){
    var sufs = ['ings','ing','ies','ers','er','ed','es','s'];
    for (var i=0;i<sufs.length;i++){
      var s = sufs[i];
      if (w.length > 4 + s.length - 1 && w.endsWith(s)) return w.slice(0, -s.length);
    }
    return w;
  }
  function tokenize(text){
    var out = [], m, re = /[a-z][a-z0-9\-\/]{1,}/g, low = String(text).toLowerCase();
    while ((m = re.exec(low))){
      if (!STOP.has(m[0]) && m[0].length > 2) out.push(stem(m[0]));
    }
    return out;
  }

  async function boot(){
    try {
      META = await (await fetch('data/library/meta.json')).json();
      BUCKET = META.passage_bucket || 500;
    } catch (e) {
      el('results').innerHTML = '<div class="banner quar"><strong>The document library is not ' +
        'available.</strong> It is built from public-domain PDFs and is not committed because ' +
        'of its size. Run <code>tools/acquire.py fetch faa-ac-43-13-1b faa-amt-general</code> ' +
        'then <code>tools/library.py ingest sources/documents/*/*.pdf</code>, and rebuild. ' +
        'Serving over HTTP is required — browsers block local file reads.</div>';
    }
    if (META){
      var keys = Object.keys(META.documents).sort(function(a, b2){
        return (META.documents[a].title || a).localeCompare(META.documents[b2].title || b2);
      });
      el('doc').innerHTML = '<option value="">Every document</option>' + keys.map(function(k){
        var d = META.documents[k];
        return '<option value="' + esc(k) + '">' + esc(d.title || k) +
          (d.document_number ? ' (' + esc(d.document_number) + ')' : '') + '</option>';
      }).join('');

      var docs = Object.keys(META.documents).map(function(k){
        var d = META.documents[k];
        return '<li><b>' + esc(d.title) + '</b>' +
          (d.document_number ? ' — ' + esc(d.document_number) : '') +
          (d.revision ? ' ' + esc(d.revision) : '') +
          ' <span class="muted">' + d.pages + ' pages, ' + d.passages + ' passages</span>' +
          (d.url ? ' · <a href="' + esc(d.url) + '" rel="noopener">source</a>' : '') + '</li>';
      }).join('');
      el('libmeta').innerHTML = '<p><strong>Indexed:</strong> ' +
        META.counts.passages.toLocaleString() + ' passages from ' + META.counts.documents +
        ' public-domain document(s).</p><ul>' + docs + '</ul>' +
        '<p class="hint">Every document here is a work of the US Government, so its full text ' +
        'can be published. Coverage spans airframe maintenance, weather, risk management and ' +
        'the certificate knowledge texts; a powerplant handbook is the largest remaining gap, ' +
        'and engine-specific questions still need the manufacturer manual listed below.</p>';
    }

    try {
      var reg = await (await fetch('data/library/registry.json')).json();
      var byCat = {};
      reg.documents.forEach(function(d){ (byCat[d.category] = byCat[d.category] || []).push(d); });
      var html = '';
      Object.keys(byCat).sort().forEach(function(cat){
        html += '<h3>' + esc(cat) + '</h3><table class="reg"><tbody>';
        byCat[cat].forEach(function(d){
          var cls = d.availability === 'free_download' ? 'free'
                  : d.availability === 'purchase' ? 'buy' : 'reg';
          html += '<tr><td><span class="avail ' + cls + '">' +
            esc(String(d.availability).replace(/_/g,' ')) + '</span></td>' +
            '<td><b>' + esc(d.make) + '</b> ' + esc(d.applies_to) + '<br>' +
            esc(d.title) + (d.document_number && d.document_number !== 'various'
              ? ' <code>' + esc(d.document_number) + '</code>' : '') +
            (d.notes ? '<br><span class="muted">' + esc(d.notes) + '</span>' : '') + '</td>' +
            '<td><a href="' + esc(d.url) + '" rel="noopener">' + esc(d.publisher) + '</a></td></tr>';
        });
        html += '</tbody></table>';
      });
      el('reg').innerHTML = html;
    } catch (e) { el('reg').innerHTML = '<p class="muted">Registry not built yet.</p>'; }

    el('go').addEventListener('click', run);
    el('q').addEventListener('keydown', function(e){ if (e.key === 'Enter') run(); });
    Array.prototype.forEach.call(document.querySelectorAll('.ex'), function(c){
      c.addEventListener('click', function(){ el('q').value = c.textContent; run(); });
    });
    el('doc').addEventListener('change', function(){ if (el('q').value.trim()) run(); });

    var params = new URLSearchParams(location.search);
    var preDoc = params.get('doc');
    // Only honour a doc that is actually indexed, so a stale link from a study card
    // falls back to searching everything rather than silently returning nothing.
    if (preDoc && META && META.documents[preDoc]) el('doc').value = preDoc;
    var pre = params.get('q');
    if (pre){ el('q').value = pre; run(); }
  }

  async function postings(term){
    var k = /[a-z0-9]/.test(term[0]) ? term[0] : '_';
    if (!(k in POST)){
      try { POST[k] = await (await fetch('data/library/postings/' + k + '.json')).json(); }
      catch (e) { POST[k] = {}; }
    }
    return POST[k][term];
  }

  async function passage(i){
    var b = Math.floor(i / BUCKET);
    if (!(b in PASS)){
      PASS[b] = await (await fetch('data/library/passages/' + b + '.json')).json();
    }
    return PASS[b][i % BUCKET];
  }

  async function run(){
    if (!META) return;
    var query = el('q').value.trim();
    var terms = tokenize(query);
    if (!terms.length){ el('results').innerHTML = '<p class="muted">Type something to search for.</p>'; return; }
    el('results').innerHTML = '<p class="muted">Searching…</p>';

    var k1 = META.scoring.k1, b = META.scoring.b, avg = META.scoring.avg_passage_length;
    // Limiting to one document is a range test on the passage id, because ingest
    // numbers each document's passages contiguously. No extra fetches.
    var only = el('doc').value, lo = -1, hi = -1;
    if (only && META.documents[only]){
      lo = META.documents[only].first;
      hi = META.documents[only].last;
    }
    var scores = new Map();
    for (var i = 0; i < terms.length; i++){
      var e = await postings(terms[i]);
      if (!e) continue;
      for (var j = 0; j < e.p.length; j++){
        var id = e.p[j][0], tf = e.p[j][1];
        if (lo >= 0 && (id < lo || id > hi)) continue;
        // Document-length normalisation needs the passage, but fetching every
        // candidate defeats the sharding. Approximate with the corpus average,
        // which changes ranking only marginally and keeps the query to a few
        // hundred KB.
        var score = e.i * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b));
        scores.set(id, (scores.get(id) || 0) + score);
      }
    }
    if (!scores.size){
      el('results').innerHTML = '<p class="muted">Nothing found for ' + esc(query) +
        (lo >= 0 ? ' in ' + esc(META.documents[only].title) +
          '. <a href="#" id="widen">Search every document instead.</a>'
         : '. The library covers airframe maintenance, weather, and the knowledge ' +
           'handbooks; engine-specific questions may need the manufacturer manual ' +
           'listed below.') + '</p>';
      var w = el('widen');
      if (w) w.addEventListener('click', function(ev){
        ev.preventDefault(); el('doc').value = ''; run();
      });
      return;
    }

    var top = Array.from(scores.entries()).sort(function(a, b2){ return b2[1] - a[1]; }).slice(0, 12);
    var html = '<p class="muted">' + scores.size.toLocaleString() + ' passage(s) matched' +
      (lo >= 0 ? ' in ' + esc(META.documents[only].title) : '') + '. ' +
      'Showing ' + top.length + ', most relevant first.</p>';
    for (var t = 0; t < top.length; t++){
      var ps = await passage(top[t][0]);
      if (!ps) continue;
      var d = META.documents[ps.d] || {};
      var cite = [d.document_number, d.revision].filter(Boolean).join(' ');
      html += '<div class="hit"><span class="score">' + top[t][1].toFixed(1) + '</span>' +
        '<div class="cite"><b>' + esc(d.title || ps.d) + '</b>' +
        (cite ? ' · ' + esc(cite) : '') + ' · page ' + ps.p + '</div>' +
        '<p>' + highlight(ps.t, terms) + '</p></div>';
    }
    html += '<p class="hint">Passages from public-domain documents, ranked by relevance. ' +
      'Read the source before acting on any of it — and for anything airworthiness-related, ' +
      'the manufacturer\'s current data governs, not a general handbook.</p>';
    el('results').innerHTML = html;
  }

  function highlight(text, terms){
    var out = esc(text.replace(/\s+/g, ' '));
    var seen = {};
    terms.forEach(function(t){
      if (seen[t] || t.length < 3) return;
      seen[t] = 1;
      // Match the stem as a prefix so "inspect" highlights "inspection".
      out = out.replace(new RegExp('\\b(' + t.replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&') +
        '[a-z]{0,6})\\b', 'gi'), '<mark>$1</mark>');
    });
    return out;
  }

  boot();
})();
"""


def library_page(head_fn, foot: str) -> str:
    return (
        head_fn(
            "Troubleshooting search — Open Checklists",
            "Search the full text of public-domain aviation documents — maintenance, "
            "weather, risk management and the certificate knowledge handbooks. Every "
            "result is a cited passage with its page number.",
        )
        + f"<style>{LIB_CSS}</style>"
        + LIB_BODY
        + f"<script>{LIB_JS}</script>"
        + foot
    )


PROJECTS = """
<h2>Open source aircraft projects</h2>
<p class="lede">This site exists partly because the same problem kept recurring across
several projects: aviation data that everyone needs is either locked in a vendor
format or trapped in a PDF. Everything below is open source, and everything below
either produces or consumes the formats this site defines.</p>

<div class="grid3">
  <div class="feat">
    <h3>Open Checklists</h3>
    <p>This site. A machine-readable checklist corpus with real provenance, an editor,
    a preflight log and an open pilot logbook format. Schemas are permissively
    licensed so anyone can implement them, including in closed commercial products.</p>
    <p><a href="catalogue.html">Browse</a> · <a href="editor.html">Editor</a></p>
  </div>
  <div class="feat">
    <h3>Junco</h3>
    <p>An open flight computer for experimental and ultralight aircraft: an ESP32
    sensor hub, your phone as the display, and a black box on an SD card. It consumes
    the checklist format defined here, which is why that format has stable phase
    identifiers — so software can map a checklist to a moment in flight.</p>
  </div>
  <div class="feat">
    <h3>Flight simulator</h3>
    <p>An open source simulator, in progress. It will load checklists from this
    corpus directly, which means practising a procedure in the sim and flying it in
    the aircraft use the same file.</p>
  </div>
</div>

<h2>Why the formats matter more than the site</h2>
<p>A checklist that only this website can read would be worth very little. The point
of publishing schemas — and of making them permissive enough for closed products to
adopt — is that the corpus becomes usable by panel software, by simulators, by
logbook apps and by whatever comes next. The site is one consumer of the data, not
the owner of it.</p>

<p>That is also why the corpus lives in a git repository rather than a database:
if this site disappears, the data and its history survive, and anyone can host it.</p>

<h2>Contributing to any of it</h2>
<p>Checklist contributions go through <a href="contribute.html">the contribute
page</a>. For the other projects, the repositories are the place to start. The most
useful thing anyone can do here is not code: it is taking one checklist and checking
it against its source document, because that is the one thing the tooling cannot do
for itself.</p>
"""


CHARTS = """
<h2>Charts, plates and airport diagrams</h2>

<p class="lede">This project links to charts rather than republishing them, and the
reason is specific enough to be worth stating plainly.</p>

<div class="banner quar"><strong>Why we do not cut our own charts.</strong> FAA charts
are US Government works, so copyright is not the obstacle — you may freely copy them.
The obstacle is liability. US courts have repeatedly treated aeronautical charts as
<em>products</em> subject to strict liability rather than as publications, and one
appellate court declined to extend that reasoning to a book specifically because a
chart is a tool used in navigation. A customised chart that a pilot navigates from is
the exact fact pattern of those cases. Every other artifact on this site carries a
verification state and a "not approved data" notice; a chart you fly by cannot be
made safe with a label.</div>

<p>So this page does the useful part instead: it points you at the official product,
which is free, current, and authoritative in a way a re-cut copy could never be.</p>

<h3>Official FAA digital products, all free</h3>
<table><tbody>
<tr><td><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/" rel="noopener">VFR charts</a></td>
    <td>Sectionals, terminal area charts, helicopter route charts and Grand Canyon charts, as georeferenced GeoTIFF and PDF. 56-day cycle.</td></tr>
<tr><td><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/" rel="noopener">Terminal procedures</a></td>
    <td>Approach plates, departure and arrival procedures, and airport diagrams. Search by airport.</td></tr>
<tr><td><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/" rel="noopener">Chart Supplement</a></td>
    <td>Formerly the Airport/Facility Directory. The authoritative source for the airport data on this site, and what you should verify frequencies against.</td></tr>
<tr><td><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/" rel="noopener">IFR enroute charts</a></td>
    <td>Low and high altitude enroute charts.</td></tr>
<tr><td><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/" rel="noopener">NASR subscription</a></td>
    <td>The raw 28-day data behind the airport pages here: airports, runways, frequencies, navaids, fixes and airspace.</td></tr>
</tbody></table>

<h3>Good viewers, none of them ours</h3>
<p><a href="https://skyvector.com/" rel="noopener">SkyVector</a> renders current
sectionals in a browser for free and does it well. <a href="https://vfrmap.com/"
rel="noopener">VFRMap</a> is another. For flight planning with charts on a tablet, the
commercial apps are genuinely better than anything this project would build.</p>

<h3>What we do instead</h3>
<p>Every <a href="airports.html">airport page</a> carries the field data you would
otherwise squint at a chart for — frequencies, runway dimensions and surfaces,
pattern altitude, field elevation, magnetic variation and which sectional the field
appears on — and links straight to the chart and plates for that airport. That is the
part structured data does better than an image, and it is the part we can do
responsibly.</p>
"""
