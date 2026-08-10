#!/usr/bin/env python3
"""Flight training page: the free study library, and progress toward a certificate.

The study section is a catalogue of what the FAA publishes free, which is nearly
everything a student needs and is not obvious to find.

The progress section is the part nothing free does well: it reads a logbook — the one
saved in this browser, or a file — and reports it against the aeronautical experience
requirements in 14 CFR part 61, citing the paragraph for every line. It runs entirely
client-side, so a logbook never leaves the device.

It reports; it does not certify. Requirements a logbook cannot answer are listed and
left unchecked rather than guessed at, because a student who thinks a box is ticked
will stop looking at it.
"""

from __future__ import annotations

TRAINING_CSS = """
.certtabs{display:flex;gap:.4rem;flex-wrap:wrap;margin:1rem 0 .6rem}
.certtab{font-size:.82rem;padding:.4rem .7rem;border:1px solid var(--line);border-radius:.35rem;
cursor:pointer;background:var(--bg)}
.certtab[aria-pressed=true]{background:var(--accent);color:#fff;border-color:transparent}
.reqtable{width:100%;border-collapse:collapse;font-size:.9rem}
.reqtable td{padding:.45rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
.reqtable td.mark{width:4.5rem;white-space:nowrap;font-size:.7rem;font-weight:700;
letter-spacing:.03em}
.m-met{color:var(--ok)}.m-short{color:var(--warn)}.m-unknown{color:var(--caut)}
.m-manual{color:var(--muted)}
.reqtable .cfr{font-size:.74rem;color:var(--muted);font-family:ui-monospace,Menlo,monospace}
.reqtable .note{font-size:.78rem;color:var(--caut);display:block;margin-top:.2rem}
.bar{height:.4rem;background:var(--line);border-radius:1rem;overflow:hidden;margin-top:.25rem;
max-width:14rem}
.bar span{display:block;height:100%;background:var(--ok)}
.bar.short span{background:var(--caut)}
.summary{display:flex;gap:1rem;flex-wrap:wrap;margin:.6rem 0;font-size:.85rem}
.summary b{font-size:1.3rem;display:block;font-variant-numeric:tabular-nums}
.studygrid{display:grid;gap:.6rem;grid-template-columns:repeat(auto-fit,minmax(17rem,1fr));margin:1rem 0}
.study{border:1px solid var(--line);border-radius:.4rem;padding:.6rem .8rem;background:var(--card)}
.study h4{margin:.1rem 0 .3rem;font-size:.95rem}
.study p{margin:0;font-size:.83rem;color:var(--muted)}
.study .num{font-family:ui-monospace,Menlo,monospace;font-size:.75rem}
"""

TRAINING_BODY = """
<h2>Flight training</h2>
<p class="lede">Almost everything a student pilot needs to study is published free by
the FAA, and almost none of it is easy to find. This page collects it, and then does
the thing nothing free does well: reads your logbook against the actual experience
requirements in 14 CFR part 61.</p>

<h2 id="progress">Progress toward a certificate</h2>

<div class="banner okb"><strong>This reports, it does not certify.</strong> Every line
cites its CFR paragraph, and requirements a logbook cannot answer — an instructor's
endorsement, whether an airport had an operating tower — are listed and left
unchecked rather than guessed. Eligibility is determined by your instructor and your
examiner. The point is to stop you discovering a missing 0.4 hours the week of your
checkride.</div>

<div class="certtabs" id="certtabs"></div>

<div class="row" style="gap:.5rem;align-items:center;margin:.6rem 0">
  <button class="btn p" id="uselocal">Use my saved logbook</button>
  <button class="btn" id="openlb">Open a logbook file</button>
  <input type="file" id="lbfile" accept=".json,.oclb.json" hidden>
  <span class="hint" id="lbstatus">Nothing loaded yet.</span>
</div>

<div id="progress"></div>

<h2 id="study">Free study material</h2>
<p class="lede">All of it public domain, all of it current, none of it behind a
paywall. The handbooks are the source of the knowledge-test questions; the ACS is the
document your checkride is conducted against, task by task.</p>
<div id="study"></div>

<h2>What to read, in order</h2>
<ol>
  <li><strong>Pilot's Handbook of Aeronautical Knowledge</strong> — the core text.
  Read it once end to end early, then use it as reference.</li>
  <li><strong>The ACS for your certificate</strong> — read this second, not last.
  It tells you exactly what you will be tested on and to what tolerance, which makes
  everything else easier to prioritise.</li>
  <li><strong>Airplane Flying Handbook</strong> — the manoeuvres, and why each one
  is flown the way it is.</li>
  <li><strong>Aviation Weather Handbook</strong> and <strong>Risk Management
  Handbook</strong> — the two areas where accidents actually come from.</li>
  <li><strong>Instrument Flying Handbook</strong> once you start the rating.</li>
  <li><strong>14 CFR part 61 and part 91</strong> — dull, short, and the source of
  more checkride questions than anything else.</li>
</ol>
<p class="hint">Searchable full text of several of these is in the
<a href="search.html">troubleshooting search</a>, which cites document and page.</p>
"""

TRAINING_JS = r"""
(function(){
  var CERTS = null, current = null, BOOK = null;
  var LIB_KEY = 'ocl.logbook.v1';

  function el(id){ return document.getElementById(id); }
  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  var STUDY = [
    {t:'Pilot’s Handbook of Aeronautical Knowledge', n:'FAA-H-8083-25C',
     d:'The core knowledge text. Basis of the private pilot knowledge test.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak'},
    {t:'Airplane Flying Handbook', n:'FAA-H-8083-3C',
     d:'Manoeuvres, procedures and why each is flown the way it is.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/airplane_handbook'},
    {t:'Aviation Weather Handbook', n:'FAA-H-8083-28',
     d:'Replaced AC 00-6 and AC 00-45. Weather theory plus how to read every product.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Risk Management Handbook', n:'FAA-H-8083-2A',
     d:'Decision making and hazard identification. Where accidents actually come from.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Instrument Flying Handbook', n:'FAA-H-8083-15B',
     d:'The instrument rating knowledge text.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Instrument Procedures Handbook', n:'FAA-H-8083-16B',
     d:'IFR procedures in practice: departures, arrivals, approaches.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Aircraft Weight and Balance Handbook', n:'FAA-H-8083-1',
     d:'Weight and balance theory and computation. Essential for modified aircraft.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Aviation Instructor’s Handbook', n:'FAA-H-8083-9B',
     d:'How to teach. Required reading for the CFI, useful for any student.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Airman Certification Standards', n:'FAA-S-ACS series',
     d:'What your checkride tests, task by task, with tolerances. Read early.',
     u:'https://www.faa.gov/training_testing/testing/acs'},
    {t:'Glider, Helicopter, Balloon and Powered Parachute Flying Handbooks', n:'FAA-H-8083 series',
     d:'Full handbooks for every category, including weight-shift control.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'14 CFR (the FARs) and the AIM', n:'part 61, 91',
     d:'The regulations themselves, always current, free on eCFR.',
     u:'https://www.ecfr.gov/current/title-14'},
    {t:'Chart User’s Guide', n:'FAA',
     d:'How to read every symbol on a sectional and an approach plate.',
     u:'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/aero_guide/'},
    {t:'Airman Knowledge Testing Supplements', n:'FAA-CT-8080 series',
     d:'The figure booklets you are given in the test. Practise with the real ones.',
     u:'https://www.faa.gov/training_testing/testing/supplements'},
    {t:'Advisory Circulars', n:'AC series',
     d:'Thousands of them, free. AC 43.13-1B is the maintenance one worth knowing.',
     u:'https://www.faa.gov/regulations_policies/advisory_circulars'},
    {t:'FAA Safety Briefing', n:'magazine',
     d:'Bi-monthly, free, genuinely good on human factors and recurring mistakes.',
     u:'https://www.faa.gov/newsroom/safety-briefing'},
    {t:'WINGS Pilot Proficiency Program', n:'FAASafety.gov',
     d:'Free courses that also satisfy the flight review requirement.',
     u:'https://www.faasafety.gov/'}
  ];

  el('study').innerHTML = '<div class="studygrid">' + STUDY.map(function(s){
    return '<div class="study"><h4><a href="' + esc(s.u) + '" rel="noopener">' + esc(s.t) +
      '</a></h4><p><span class="num">' + esc(s.n) + '</span> — ' + esc(s.d) + '</p></div>';
  }).join('') + '</div>';

  async function boot(){
    try {
      CERTS = await (await fetch('data/training/certificates.json')).json();
    } catch (e) {
      el('progress').innerHTML = '<div class="banner quar">Certificate requirement data is ' +
        'not built. Run <code>tools/training.py emit</code> and rebuild. Serving over HTTP ' +
        'is required.</div>';
      return;
    }
    el('certtabs').innerHTML = CERTS.certificates.map(function(c, i){
      return '<span class="certtab" role="button" tabindex="0" data-c="' + esc(c.id) + '" ' +
        'aria-pressed="' + (i === 1 ? 'true' : 'false') + '">' + esc(c.name) + '</span>';
    }).join('');
    current = CERTS.certificates[1] || CERTS.certificates[0];

    Array.prototype.forEach.call(document.querySelectorAll('.certtab'), function(t){
      function pick(){
        Array.prototype.forEach.call(document.querySelectorAll('.certtab'), function(o){
          o.setAttribute('aria-pressed', o === t ? 'true' : 'false');
        });
        current = CERTS.certificates.filter(function(c){ return c.id === t.dataset.c; })[0];
        render();
      }
      t.addEventListener('click', pick);
      t.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pick(); }
      });
    });

    el('uselocal').addEventListener('click', function(){
      var saved = null;
      try { saved = JSON.parse(localStorage.getItem(LIB_KEY) || 'null'); } catch (e) {}
      if (!saved){
        el('lbstatus').textContent = 'No logbook saved in this browser yet. Open a file instead.';
        return;
      }
      BOOK = saved;
      el('lbstatus').textContent = 'Using your saved logbook (' +
        (saved.entries || []).length + ' entries).';
      render();
    });
    el('openlb').addEventListener('click', function(){ el('lbfile').click(); });
    el('lbfile').addEventListener('change', function(e){
      var f = e.target.files[0]; if (!f) return;
      var r = new FileReader();
      r.onload = function(){
        try {
          BOOK = JSON.parse(r.result);
          el('lbstatus').textContent = 'Loaded ' + f.name + ' (' +
            (BOOK.entries || []).length + ' entries). It stays in this browser.';
          render();
        } catch (err){ el('lbstatus').textContent = 'Could not read that file: ' + err.message; }
      };
      r.readAsText(f);
    });

    render();
  }

  // Mirrors tools/training.py. Conservative in the same direction: intersected
  // buckets take the smaller of the two per entry, so this understates rather
  // than overstates.
  function hours(bucket, opt){
    opt = opt || {};
    var total = 0;
    (BOOK.entries || []).forEach(function(e){
      var t = e.times || {}, v = t[bucket] || 0;
      if (opt.also) v += t[opt.also] || 0;
      if (opt.pic) v = Math.min(v, t.pilot_in_command || 0);
      if (opt.solo) v = Math.min(v, t.solo || 0);
      total += v;
    });
    var cf = ((BOOK.carried_forward || {}).totals) || {};
    if (!opt.pic && !opt.solo){
      total += cf[bucket] || 0;
      if (opt.also) total += cf[opt.also] || 0;
    }
    return Math.round(total * 10) / 10;
  }
  function dualInstrument(){
    var total = 0;
    (BOOK.entries || []).forEach(function(e){
      var t = e.times || {};
      total += Math.min((t.actual_instrument||0) + (t.simulated_instrument||0), t.dual_received||0);
    });
    return Math.round(total * 10) / 10;
  }

  function flightTests(){
    var E = BOOK.entries || [], out = {};
    function put(k, met, detail, unknown){ out[k] = {met:met, detail:detail, unknown:!!unknown}; }

    var nightXc = E.filter(function(e){ return (e.times||{}).night > 0 && (e.times||{}).cross_country > 0; });
    var withD = nightXc.filter(function(e){ return ((e.route||{}).distance_nm||0) > 0; });
    var over = withD.filter(function(e){ return e.route.distance_nm >= 100; });
    if (over.length) put('night_xc_100nm', true, over[0].date + ', ' + over[0].route.distance_nm + ' nm');
    else if (nightXc.length && !withD.length)
      put('night_xc_100nm', false, nightXc.length + ' night cross-country flight(s) but none records a distance', true);
    else put('night_xc_100nm', false, 'no night cross-country over 100 nm found');

    var nl = E.reduce(function(a,e){ return a + ((e.landings||{}).full_stop_night||0); }, 0);
    put('night_10_landings', nl >= 10, nl + ' night full-stop landing(s) logged');

    var soloXc = E.filter(function(e){ return (e.times||{}).solo > 0 && ((e.route||{}).distance_nm||0) > 0; });
    var s150 = soloXc.filter(function(e){ return e.route.distance_nm >= 150; });
    if (s150.length) put('solo_xc_150nm', true, s150[0].date + ', ' + s150[0].route.distance_nm +
      ' nm — confirm three points and a 50 nm leg');
    else {
      var anySolo = E.filter(function(e){ return (e.times||{}).solo > 0; });
      put('solo_xc_150nm', false, 'no solo cross-country of 150 nm found' +
        (anySolo.length && !soloXc.length ? ' (solo flights logged without distances)' : ''),
        anySolo.length && !soloXc.length);
    }

    put('towered_3_landings', false, 'cannot be determined from a logbook — whether an ' +
      'airport had an operating control tower is not a logged field', true);

    var ifr = E.filter(function(e){
      return (((e.instrument||{}).approaches)||[]).length >= 3 && ((e.route||{}).distance_nm||0) >= 250; });
    if (ifr.length){
      var kinds = {}; ifr[0].instrument.approaches.forEach(function(a){ kinds[a.type] = 1; });
      var n = Object.keys(kinds).length;
      put('ifr_xc_250nm', n >= 3, ifr[0].date + ', ' + ifr[0].route.distance_nm + ' nm, ' +
        n + ' kind(s) of approach');
    } else put('ifr_xc_250nm', false, 'no IFR cross-country of 250 nm with three approach types found');

    [['day_xc_100nm_2h', false], ['night_xc_100nm_2h', true]].forEach(function(pair){
      var c = E.filter(function(e){
        var t = e.times || {};
        return (t.total||0) >= 2 && ((e.route||{}).distance_nm||0) >= 100 &&
          (pair[1] ? (t.night||0) > 0 : (t.day||0) > 0); });
      put(pair[0], !!c.length, c.length ? c[0].date + ', ' + c[0].route.distance_nm + ' nm, ' +
        c[0].times.total + ' h' : 'not found');
    });

    var x300 = E.filter(function(e){ return ((e.route||{}).distance_nm||0) >= 300; });
    put('commercial_xc_300nm', !!x300.length, x300.length ? x300[0].date + ', ' +
      x300[0].route.distance_nm + ' nm — confirm three points and a 250 nm leg'
      : 'no cross-country of 300 nm found');

    return out;
  }

  function render(){
    if (!current) return;
    var head = '<h3>' + esc(current.name) + ' <span class="cfr">' + esc(current.cfr) +
      '</span></h3><p class="sub">' + esc(current.summary) + '</p>';

    if (!BOOK){
      head += '<table class="reqtable"><tbody>' + current.requirements.map(function(r){
        var tag = r.kind === 'manual' ? 'manual' : (r.hours ? r.hours + ' h' : 'flight');
        return '<tr><td class="mark m-manual">' + esc(tag) + '</td><td>' + esc(r.label) +
          '<span class="cfr"> ' + esc(r.cfr) + '</span></td></tr>';
      }).join('') + '</tbody></table>' +
      '<p class="hint">Load a logbook above to see what you have against these.</p>';
      el('progress').innerHTML = head;
      return;
    }

    var tests = flightTests(), met = 0, short_ = 0, manual = 0, unknown = 0;
    var rows = current.requirements.map(function(r){
      var mark, cls, body = esc(r.label) + '<span class="cfr"> ' + esc(r.cfr) + '</span>';
      if (r.kind === 'manual'){ mark = 'confirm'; cls = 'manual'; manual++; }
      else if (r.kind === 'flight'){
        var f = tests[r.test] || {met:false, unknown:true, detail:'not evaluated'};
        if (f.unknown){ mark = '?'; cls = 'unknown'; unknown++; }
        else { mark = f.met ? 'met' : 'short'; cls = f.met ? 'met' : 'short'; f.met ? met++ : short_++; }
        body += '<span class="note">' + esc(f.detail) + '</span>';
      } else {
        var have = r.kind === 'dual' ? hours('dual_received')
                 : r.kind === 'solo' ? hours('solo')
                 : r.kind === 'dual_instrument' ? dualInstrument()
                 : hours(r.bucket, {pic:r.pic_only, solo:r.solo_only, also:r.also});
        var ok = have >= r.hours;
        mark = ok ? 'met' : 'short'; cls = ok ? 'met' : 'short'; ok ? met++ : short_++;
        var pct = Math.min(100, Math.round(have / r.hours * 100));
        body += '<span class="note">have ' + have + ' of ' + r.hours + ' h' +
          (ok ? '' : ', ' + (Math.round((r.hours - have) * 10) / 10) + ' h remaining') + '</span>' +
          '<div class="bar' + (ok ? '' : ' short') + '"><span style="width:' + pct + '%"></span></div>';
        var cf = ((BOOK.carried_forward || {}).totals) || {};
        if ((r.pic_only || r.solo_only) && cf[r.bucket]){
          body += '<span class="note">excludes ' + cf[r.bucket] + ' h carried forward — a ' +
            'carried-forward total records no overlap with PIC or solo time, so count those by hand</span>';
        }
      }
      return '<tr><td class="mark m-' + cls + '">' + mark + '</td><td>' + body + '</td></tr>';
    }).join('');

    el('progress').innerHTML = head +
      '<div class="summary"><div><b class="m-met">' + met + '</b> met</div>' +
      '<div><b class="m-short">' + short_ + '</b> short</div>' +
      '<div><b class="m-unknown">' + unknown + '</b> undetermined</div>' +
      '<div><b class="m-manual">' + manual + '</b> to confirm</div></div>' +
      '<table class="reqtable"><tbody>' + rows + '</tbody></table>' +
      '<p class="hint">Computed from your logbook in this browser. Nothing was uploaded. ' +
      'Authority is <a href="' + esc(CERTS.ecfr) + '" rel="noopener">14 CFR part 61</a>, ' +
      'not this page.</p>';
  }

  boot();
})();
"""


def training_page(head_fn, foot: str) -> str:
    return (
        head_fn(
            "Flight training — Open Checklists",
            "Free FAA study material for student through commercial pilots, and progress "
            "toward a certificate computed from your own logbook.",
        )
        + f"<style>{TRAINING_CSS}</style>"
        + TRAINING_BODY
        + f"<script>{TRAINING_JS}</script>"
        + foot
    )
