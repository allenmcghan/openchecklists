#!/usr/bin/env python3
"""Single-file, client-rendered community-checklist viewer.

Served at /checklist/?id=<id> for EVERY community-published checklist. Like the
airport app (tools/site_airport_app.py) this is ONE template rendered client-
side from data, not thousands of static files — the host serves the homepage for
path URLs, so the id ALWAYS arrives as ?id=<id> (never a path segment).

It mirrors what tools/render.py bakes into a static checklist page — sections,
items, tickable checkboxes, warning/caution callouts, [MEMORY] marks, print CSS —
but fetches the checklist JSON live from the API so any pilot can read, tick,
print, review and fork a community contribution.

Contract (wired by build_site.py):
    checklist_view_page(head_fn, foot) -> str
where head_fn is the site head(title, desc, rel="") — it emits the page top incl.
the nav header and the global oclToken()/oclReq(method,path,body) helpers that
talk to https://app.openchecklists.net/api — and foot is the site footer string
(it closes </main> and the document).

All fetches use the ABSOLUTE api base because the page is served from a rewritten
/checklist/ URL; relative paths would resolve against the wrong base.

Assumptions about the checklist JSON (GET /api/checklists/<id>):
  * Top level: title, aircraft{make,model,variant,category}, sections[].
    An {error:...} body means "not found".
  * section: {phase, title, criticality, items[]}. We also honour optional
    phase_label / condition / notes if present (render.py emits them).
  * item: {type, text, response, condition, detail, indent, memory_item,
    tickable}. type in note/caution/warning (info, NOT tickable) /
    action/challenge (tickable) / subtitle/reference/blank. We treat an item as
    tickable when type is action/challenge OR item.tickable === true, and never
    tickable for the info/structural types — safety first.
  * Reviews (GET .../reviews): array (or {reviews:[...]}) of
    {stars, author, comment, date|created_at}. Stats (GET .../stats): {uses}.
"""

from __future__ import annotations

CHECKLIST_VIEW_CSS = """
.cv-wrap{max-width:46rem}
.cv-head{margin:.2rem 0 1rem}
.cv-ident{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.cv-title{font-size:1.6rem;line-height:1.15;letter-spacing:-.02em;margin:.15rem 0 .1rem;font-weight:800}
.cv-ac{color:var(--muted);font-size:.92rem;margin:.1rem 0 .7rem}
.cv-badges{display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0}
.cv-badge{display:inline-block;padding:.2rem .6rem;border-radius:var(--pill);font-size:.68rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.cv-badge.unv{background:var(--caut-weak,#fbf1de);color:var(--caut,#8a5a00)}
.cv-disc{background:var(--caut-weak,#fbf1de);border:1px solid var(--caut,#8a5a00);border-radius:var(--radius,14px);
padding:.75rem 1rem;margin:.5rem 0 1.1rem;font-size:.88rem;color:var(--caut,#8a5a00)}
.cv-disc strong{color:var(--caut,#8a5a00)}
.cv-actions{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 1.2rem}
.cv-btn{display:inline-flex;align-items:center;gap:.35rem;padding:.55rem 1rem;border:1px solid var(--line);
border-radius:var(--pill);background:#fff;font:inherit;font-size:.88rem;font-weight:600;cursor:pointer;
color:var(--accent);text-decoration:none;min-height:2.6rem}
.cv-btn:hover{border-color:var(--accent-2,var(--accent));background:var(--accent-weak);text-decoration:none}
.cv-btn.primary{background:var(--accent);color:#fff;border-color:transparent}
.cv-btn.primary:hover{filter:brightness(1.07);background:var(--accent)}
.cv-count{margin-left:auto;align-self:center;color:var(--muted);font-size:.85rem;font-weight:600;font-variant-numeric:tabular-nums}
.cv-sec{margin:1.6rem 0}
.cv-sec h2{font-size:1.12rem;letter-spacing:-.01em;border-bottom:2px solid var(--line);padding-bottom:.3rem;
margin:0 0 .6rem;display:flex;justify-content:space-between;align-items:baseline;gap:.5rem}
.cv-sec.emergency h2{border-color:var(--warn);color:var(--warn)}
.cv-sec.abnormal h2{border-color:var(--caut)}
.cv-phase{font-size:.62rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;
white-space:nowrap;background:var(--card,#f5f7fb);padding:.22rem .55rem;border-radius:var(--pill)}
.cv-seccond{font-style:italic;color:var(--muted);margin:.2rem 0 .4rem;font-size:.9rem}
.cv-secnote{color:var(--muted);margin:.2rem 0 .4rem;font-size:.85rem}
.cv-list{list-style:none;margin:0;padding:0}
.cv-list li{margin:.3rem 0}
li.cv-task label{display:flex;align-items:center;gap:.75rem;background:var(--card,#f5f7fb);
border:1px solid var(--line);border-radius:var(--radius-sm,10px);padding:.72rem .85rem;cursor:pointer;
transition:border-color .12s ease,box-shadow .12s ease}
li.cv-task label:hover{border-color:var(--accent);box-shadow:var(--shadow-sm)}
li.cv-task input{width:1.5rem;height:1.5rem;margin:0;flex:none;accent-color:var(--accent)}
li.cv-task input:checked~.cv-itext{opacity:.5;text-decoration:line-through}
.cv-itext{flex:1;min-width:0}
.cv-resp{font-weight:700;text-transform:uppercase;font-size:.82rem;text-align:right;flex:none;max-width:45%;color:var(--accent)}
.cv-cond{display:block;font-size:.75rem;color:var(--muted);font-style:italic}
.cv-mem{display:inline-block;margin-left:.4rem;font-size:.58rem;font-weight:700;background:var(--warn);color:#fff;
border-radius:var(--pill);padding:.08rem .42rem;vertical-align:.12em;text-transform:uppercase;letter-spacing:.04em}
li.cv-subtitle{font-weight:700;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin:.9rem 0 .3rem;color:var(--muted)}
li.cv-info{display:flex;gap:.5rem;padding:.6rem .75rem;border-left:4px solid;border-radius:0 10px 10px 0;margin:.4rem 0;font-size:.92rem}
li.cv-info .cv-tag{font-size:.62rem;font-weight:700;letter-spacing:.05em;flex:none;padding-top:.15rem}
li.cv-warning{border-color:var(--warn);color:var(--warn);background:color-mix(in srgb,var(--warn) 8%,#fff)}
li.cv-caution{border-color:var(--caut);color:var(--caut);background:color-mix(in srgb,var(--caut) 9%,#fff)}
li.cv-note,li.cv-reference{border-color:var(--accent);color:var(--accent);background:var(--accent-weak)}
.cv-detail{margin:.3rem 0 0;font-size:.8rem;color:var(--muted)}
li.cv-blank{height:.6rem}
.cv-reviews{margin:2.2rem 0 1rem;border-top:1px solid var(--line);padding-top:1.2rem}
.cv-stars{color:#e8a91e;letter-spacing:.05em}
.cv-stars .off{color:var(--line)}
.cv-rsum{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;font-size:.95rem;margin:.3rem 0 .8rem}
.cv-rsum .avg{font-size:1.3rem;font-weight:800}
.cv-review{border:1px solid var(--line);border-radius:var(--radius-sm,10px);padding:.7rem .9rem;margin:.5rem 0;background:#fff}
.cv-review .meta{font-size:.78rem;color:var(--muted);margin:.15rem 0 0}
.cv-review .cmt{margin:.3rem 0 0;font-size:.9rem}
.cv-form{border:1px solid var(--line);border-radius:var(--radius,14px);padding:1rem 1.1rem;margin:1rem 0;background:var(--card,#f7f9fc)}
.cv-form h3{margin:0 0 .5rem;font-size:1rem}
.cv-pick{font-size:1.7rem;cursor:pointer;user-select:none;color:var(--line);line-height:1}
.cv-pick.on{color:#e8a91e}
.cv-form textarea{width:100%;font:inherit;padding:.6rem .7rem;border:1px solid var(--line);border-radius:var(--radius-sm,10px);
background:#fff;color:var(--fg);min-height:4.5rem;resize:vertical;margin:.5rem 0}
.cv-notfound{padding:3rem 0;text-align:center;color:var(--muted)}
.cv-spin{display:inline-block;width:13px;height:13px;border:2px solid var(--line);border-top-color:var(--accent);
border-radius:50%;animation:cvsp .7s linear infinite;vertical-align:middle;margin-right:.4rem}
@keyframes cvsp{to{transform:rotate(360deg)}}
@media print{
  header.site,footer.site,.cv-actions,.cv-reviews,.cv-form,.noprint{display:none!important}
  body{font-size:9.5pt;color:#000}
  .cv-wrap,main.wrap{max-width:none;padding:0}
  li.cv-task label{background:#fff;padding:.15rem .2rem;border:0;border-bottom:1px dotted #999;border-radius:0}
  li.cv-task input{width:9pt;height:9pt;-webkit-appearance:none;appearance:none;border:1px solid #000;border-radius:1pt}
  li.cv-info{border-left-width:3px;padding:.2rem .3rem;background:#fff!important}
  .cv-disc{border-width:1px;padding:.25rem .4rem}
  .cv-sec{break-inside:avoid}
}
"""

CHECKLIST_VIEW_BODY = """
<div id="cv-root" class="cv-wrap"><p class="muted" style="padding:2rem 0"><span class="cv-spin"></span> Loading checklist…</p></div>
"""

# Whole client app. Raw string — no server-side substitution needed.
CHECKLIST_VIEW_JS = r"""
(function(){
  var API = 'https://app.openchecklists.net/api';

  function esc(s){ return String(s==null?'':s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  function getId(){
    // Path URLs are served the homepage by the host, so the id ALWAYS arrives
    // as ?id=<id>. Do not rely on path segments.
    var q = new URLSearchParams(location.search).get('id');
    return q ? q.trim() : '';
  }

  function stars(n, max){
    max = max || 5; n = Math.round(n||0);
    var on = ''; for (var i=0;i<max;i++) on += (i<n ? '★' : '<span class="off">★</span>');
    return '<span class="cv-stars">' + on + '</span>';
  }
  function fmtDate(d){
    if (!d) return '';
    var t = new Date(d);
    if (isNaN(t)) return esc(d);
    try { return t.toLocaleDateString([], {year:'numeric',month:'short',day:'numeric'}); }
    catch(e){ return t.toISOString().slice(0,10); }
  }

  var INFO = {note:1, caution:1, warning:1};
  var TICKABLE = {action:1, challenge:1};

  function isTickable(it){
    var t = (it.type||'challenge');
    if (INFO[t] || t==='subtitle' || t==='reference' || t==='blank') return false;
    if (it.tickable === false) return false;
    return TICKABLE[t] || it.tickable === true;
  }

  function renderItem(it, secId, idx){
    var t = (it.type||'challenge');
    if (t === 'blank') return '<li class="cv-blank"></li>';

    var text = esc(it.text);
    var cond = it.condition ? '<span class="cv-cond">' + esc(it.condition) + '</span>' : '';
    var detail = it.detail ? '<p class="cv-detail">' + esc(it.detail) + '</p>' : '';
    var ind = it.indent ? ' style="margin-left:' + (Math.min(it.indent,4)*1.25) + 'rem"' : '';

    if (t === 'subtitle') return '<li class="cv-subtitle"' + ind + '>' + text + '</li>';

    if (INFO[t]){
      var label = {note:'NOTE', caution:'CAUTION', warning:'WARNING'}[t];
      return '<li class="cv-info cv-' + t + '"' + ind + '><span class="cv-tag">' + label +
        '</span><span class="cv-itext">' + text + '</span>' + detail + '</li>';
    }
    if (t === 'reference'){
      var ref = it.reference || {};
      var tgt = ref.section_id || ref.document || ref.url || '';
      return '<li class="cv-info cv-reference"' + ind + '><span class="cv-tag">GO TO</span>' +
        '<span class="cv-itext">' + text + '</span>' +
        (tgt ? '<p class="cv-detail">' + esc(tgt) + '</p>' : '') + '</li>';
    }
    // Anything else with text but not marked tickable → plain (non-checkbox) line.
    if (!isTickable(it)){
      var resp0 = it.response ? '<span class="cv-resp">' + esc(it.response) + '</span>' : '';
      return '<li class="cv-subtitle" style="font-weight:600;text-transform:none;letter-spacing:0;color:var(--fg)"' + ind + '>' +
        '<span class="cv-itext">' + text + '</span>' + resp0 + cond + detail + '</li>';
    }
    // Tickable action / challenge
    var mem = it.memory_item ? '<span class="cv-mem">MEMORY</span>' : '';
    var resp = it.response ? '<span class="cv-resp">' + esc(it.response) + '</span>' : '';
    return '<li class="cv-task"' + ind + '><label>' +
      '<input type="checkbox" class="cv-tick" data-section="' + esc(secId) + '" data-index="' + idx + '">' +
      '<span class="cv-itext">' + text + mem + '</span>' + resp + cond + '</label>' + detail + '</li>';
  }

  function renderSection(sec, si){
    var secId = sec.id || ('section-' + si);
    var crit = esc(sec.criticality || 'normal');
    var phase = esc(sec.phase_label || sec.phase || '');
    var cond = sec.condition ? '<p class="cv-seccond">' + esc(sec.condition) + '</p>' : '';
    var notes = sec.notes ? '<p class="cv-secnote">' + esc(sec.notes) + '</p>' : '';
    var items = (sec.items || []).map(function(it, i){ return renderItem(it, secId, i); }).join('');
    return '<section class="cv-sec ' + crit + '" id="' + esc(secId) + '">' +
      '<h2>' + esc(sec.title || '') + (phase ? ' <span class="cv-phase">' + phase + '</span>' : '') + '</h2>' +
      cond + notes + '<ul class="cv-list">' + items + '</ul></section>';
  }

  function notFound(root, id, msg){
    root.innerHTML = '<div class="cv-notfound"><h1 style="font-size:1.4rem">Checklist not found</h1>' +
      '<p>' + esc(msg || ('No community checklist matches ' + (id ? '“' + id + '”' : 'that id') + '.')) + '</p>' +
      '<p><a class="cv-btn" href="/catalogue.html">Browse the catalogue</a></p></div>';
  }

  var CID = '';

  async function boot(){
    var root = document.getElementById('cv-root');
    var id = getId();
    if (!id){
      root.innerHTML = '<div class="cv-notfound"><h1 style="font-size:1.4rem">No checklist specified</h1>' +
        '<p>This page needs a checklist id, e.g. <code>/checklist/?id=…</code></p>' +
        '<p><a class="cv-btn" href="/catalogue.html">Browse the catalogue</a></p></div>';
      return;
    }
    CID = id;
    var doc;
    try {
      var r = await fetch(API + '/checklists/' + encodeURIComponent(id));
      doc = await r.json();
    } catch(e){ notFound(root, id, 'Could not reach the checklist service. Check your connection and retry.'); return; }
    if (!doc || doc.error || !doc.title && !doc.sections){ notFound(root, id, doc && doc.error); return; }

    render(root, doc, id);

    // Count a use (fire-and-forget) and load ratings/reviews.
    fetch(API + '/checklists/' + encodeURIComponent(id) + '/used', {method:'POST'}).catch(function(){});
    loadReviews(id);
  }

  function render(root, doc, id){
    var ac = doc.aircraft || {};
    var acLine = [ac.make, ac.model, ac.variant].filter(Boolean).join(' ');
    var cat = (ac.category || '').replace(/_/g,' ');
    var title = doc.title || 'Checklist';
    document.title = title + ' — Open Checklists';

    var h = '';
    h += '<div class="cv-head">';
    h += '<div class="cv-ident">Community checklist</div>';
    h += '<h1 class="cv-title">' + esc(title) + '</h1>';
    if (acLine || cat) h += '<p class="cv-ac">' + esc(acLine) + (acLine && cat ? ' · ' : '') + esc(cat) + '</p>';
    h += '<div class="cv-badges"><span class="cv-badge unv">Unverified — community-contributed</span></div>';
    h += '</div>';

    h += '<div class="cv-disc"><strong>Not approved data.</strong> This checklist was contributed by a ' +
      'community member and has not been verified. Always check it against your aircraft’s own approved ' +
      'documentation (POH/AFM) before flight.</div>';

    h += '<div class="cv-actions">' +
      '<button class="cv-btn" type="button" id="cv-print">🖨 Print</button>' +
      '<a class="cv-btn primary" href="/editor.html?fork=' + encodeURIComponent(id) + '">✎ Customize this Checklist</a>' +
      '<span class="cv-count" id="cv-count"></span></div>';

    var sections = (doc.sections || []).map(renderSection).join('');
    h += (sections || '<p class="muted">This checklist has no sections yet.</p>');

    // Reviews container (filled after fetch).
    h += '<div class="cv-reviews" id="cv-reviews"><h2 style="border:0;font-size:1.15rem">Ratings &amp; reviews</h2>' +
      '<p class="muted"><span class="cv-spin"></span> Loading reviews…</p></div>';

    root.innerHTML = h;

    var pb = document.getElementById('cv-print');
    if (pb) pb.addEventListener('click', function(){ window.print(); });

    wireTicks();
  }

  function wireTicks(){
    var boxes = Array.prototype.slice.call(document.querySelectorAll('.cv-tick'));
    var countEl = document.getElementById('cv-count');
    function refresh(){
      var done = boxes.filter(function(b){ return b.checked; }).length;
      if (countEl) countEl.textContent = boxes.length ? (done + ' / ' + boxes.length + ' done') : '';
    }
    boxes.forEach(function(b){ b.addEventListener('change', refresh); });
    refresh();
  }

  // ---- Ratings & reviews ----
  function loadReviews(id){
    var wrap = document.getElementById('cv-reviews');
    if (!wrap) return;
    var uses = null, reviews = [];

    var pStats = fetch(API + '/checklists/' + encodeURIComponent(id) + '/stats')
      .then(function(r){ return r.json(); }).then(function(d){ if (d && !d.error) uses = d.uses; }).catch(function(){});
    var pRev = fetch(API + '/checklists/' + encodeURIComponent(id) + '/reviews')
      .then(function(r){ return r.json(); }).then(function(d){
        if (Array.isArray(d)) reviews = d;
        else if (d && Array.isArray(d.reviews)) reviews = d.reviews;
      }).catch(function(){});

    Promise.all([pStats, pRev]).then(function(){ renderReviews(wrap, id, reviews, uses); });
  }

  function renderReviews(wrap, id, reviews, uses){
    var n = reviews.length;
    var avg = n ? (reviews.reduce(function(a,r){ return a + (Number(r.stars)||0); }, 0) / n) : 0;

    var h = '<h2 style="border:0;font-size:1.15rem">Ratings &amp; reviews</h2>';
    h += '<div class="cv-rsum">';
    if (n){
      h += '<span class="avg">' + avg.toFixed(1) + '</span>' + stars(avg) +
        '<span class="muted">' + n + (n===1 ? ' review' : ' reviews') + '</span>';
    } else {
      h += '<span class="muted">No reviews yet — be the first.</span>';
    }
    if (uses != null) h += '<span class="muted">· ' + uses + (uses===1 ? ' use' : ' uses') + '</span>';
    h += '</div>';

    reviews.forEach(function(r){
      h += '<div class="cv-review">' + stars(r.stars) +
        '<span class="meta">' + esc(r.author || 'Anonymous') +
        (r.date || r.created_at ? ' · ' + fmtDate(r.date || r.created_at) : '') + '</span>' +
        (r.comment ? '<p class="cmt">' + esc(r.comment) + '</p>' : '') + '</div>';
    });

    // Review form (signed in) or sign-in prompt.
    if (typeof oclToken === 'function' && oclToken()){
      h += '<div class="cv-form"><h3>Leave a review</h3>' +
        '<div id="cv-pick" aria-label="Rating">' +
        [1,2,3,4,5].map(function(i){ return '<span class="cv-pick" data-v="' + i + '">★</span>'; }).join('') +
        '</div>' +
        '<textarea id="cv-cmt" placeholder="How did this checklist work for you? (optional)"></textarea>' +
        '<button class="cv-btn primary" type="button" id="cv-submit">Submit review</button>' +
        '<span id="cv-msg" class="muted" style="margin-left:.6rem;font-size:.88rem"></span></div>';
    } else {
      h += '<div class="cv-form"><h3>Rate this checklist</h3>' +
        '<p class="muted" style="margin:.2rem 0 .6rem">Sign in to leave a star rating and review.</p>' +
        '<a class="cv-btn" href="/profile.html">Sign in to review</a></div>';
    }

    wrap.innerHTML = h;
    wireReviewForm(id);
  }

  function wireReviewForm(id){
    var pick = document.getElementById('cv-pick');
    if (!pick) return;
    var chosen = 0;
    var picks = Array.prototype.slice.call(pick.querySelectorAll('.cv-pick'));
    function paint(v){ picks.forEach(function(p){ p.classList.toggle('on', Number(p.dataset.v) <= v); }); }
    picks.forEach(function(p){
      p.addEventListener('mouseenter', function(){ paint(Number(p.dataset.v)); });
      p.addEventListener('click', function(){ chosen = Number(p.dataset.v); paint(chosen); });
    });
    pick.addEventListener('mouseleave', function(){ paint(chosen); });

    var btn = document.getElementById('cv-submit');
    var msg = document.getElementById('cv-msg');
    btn.addEventListener('click', function(){
      if (!chosen){ msg.textContent = 'Pick a star rating first.'; msg.style.color = 'var(--warn)'; return; }
      var cmt = (document.getElementById('cv-cmt').value || '').trim();
      btn.disabled = true; msg.style.color = 'var(--muted)'; msg.textContent = 'Submitting…';
      oclReq('POST', '/checklists/' + encodeURIComponent(id) + '/review', {stars: chosen, comment: cmt})
        .then(function(d){
          if (d && d.error){ btn.disabled = false; msg.style.color = 'var(--warn)'; msg.textContent = d.error; return; }
          msg.style.color = 'var(--ok)'; msg.textContent = '✓ Thanks!';
          loadReviews(id);   // re-render with the new review included
        })
        .catch(function(){ btn.disabled = false; msg.style.color = 'var(--warn)'; msg.textContent = 'Could not submit — try again.'; });
    });
  }

  boot();
})();
"""


def checklist_view_page(head_fn, foot) -> str:
    """Return the single client-rendered community-checklist viewer template.

    head_fn: the site head(title, desc, rel="") function. Called with rel="/" so
    every nav/asset link is absolute — required because this file is served from
    a rewritten /checklist/ URL. head_fn also injects the global oclToken() and
    oclReq(method, path, body) helpers used by the review form.

    foot: the site footer HTML string (closes </main> and the document).
    """
    return (
        head_fn(
            "Checklist — Open Checklists",
            "Read, tick, print, review and fork any community-published aircraft "
            "checklist. Unverified community data — always confirm against your POH.",
            rel="/",
        )
        + f"<style>{CHECKLIST_VIEW_CSS}</style>"
        + CHECKLIST_VIEW_BODY
        + f"<script>{CHECKLIST_VIEW_JS}</script>"
        + foot
    )
