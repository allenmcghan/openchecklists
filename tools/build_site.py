#!/usr/bin/env python3
"""Build the openchecklists.net static site from the corpus.

    python3 tools/build_site.py
    python3 tools/build_site.py --base-url https://openchecklists.net

Output under build/site/:

    index.html                      browsable, filterable catalogue
    about.html                      what the verification states mean
    c/<id>/index.html               the checklist, tickable, printable at any size
    c/<id>/<id>.{json,csv,tsv,md,txt,xml,docx,html}
    api/index.json                  machine-readable catalogue
    api/checklists/<id>.json        stable plain-HTTP path to every file
    manifest.sha256                 hash of every published artifact
    reviewed.txt / unreviewed.txt   bundle listings, kept separate on purpose
    robots.txt, sitemap.xml

No database, no server, no build-time network access. Everything derives from the
files in examples/, so the corpus in git is the only source of truth.

Two rules from docs/03-verification-model.md are enforced here rather than left to
the templates, because a static site generator is exactly where they get quietly
forgotten:

  * A quarantined file (unreviewed, or carrying an unresolved safety defect) is
    never offered in a vendor panel format, and its downloads carry the state in
    the filename.
  * Quarantined files are excluded from the default bundle listing and go in a
    separate one a consumer has to ask for.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export import EXT, FORMATS, export, is_quarantined, state_line, verify_export  # noqa: E402
from render import render as render_html  # noqa: E402
from site_editor import editor_page  # noqa: E402
from site_airports import WEATHER_WORKER, airports_page, airport_detail_page  # noqa: E402
from site_library import CHARTS, PROJECTS, library_page  # noqa: E402
from site_training import training_page  # noqa: E402
from site_pages import (  # noqa: E402
    BRAND_NAME, CONTACT, FAVICON_SVG, HERO_CSS, LOGO_SVG, PRIVACY, TAGLINE, TAKEDOWN, TERMS,
    contribute_body, landing_body,
)
from diff import diff as semantic_diff, render_markdown as diff_markdown  # noqa: E402
from validate import content_hash  # noqa: E402
from render_runway_diagram import render_runway_svg  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "build" / "site"

CSS = """
:root{
--bg:#ffffff;--card:#f5f7fb;--fg:#0f1826;--muted:#586274;--line:#e6e9f0;
--accent:#1f4e79;--accent-2:#2f6fbd;--accent-weak:#eaf1fb;
--warn:#b3261e;--warn-weak:#fdeceb;--ok:#186a2b;--ok-weak:#e9f6ec;--caut:#8a5a00;--caut-weak:#fbf3e0;
--radius:14px;--radius-sm:9px;--pill:999px;
--shadow-sm:0 1px 2px rgba(15,24,38,.06),0 1px 3px rgba(15,24,38,.04);
--shadow-md:0 6px 22px rgba(15,24,38,.09);--shadow-lg:0 18px 44px rgba(15,24,38,.14);
--maxw:62rem;
--sans:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);
font-size:16px;line-height:1.6;letter-spacing:-.006em;
-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
img,svg{max-width:100%}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 1.15rem;width:100%}
.skip{position:absolute;left:-9999px}
.skip:focus{left:.75rem;top:.75rem;z-index:80;background:#fff;color:var(--accent);
padding:.6rem .9rem;border-radius:9px;box-shadow:var(--shadow-md)}

/* Sticky header + scroll-snapping pill nav */
header.site{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.85);
backdrop-filter:saturate(1.5) blur(12px);-webkit-backdrop-filter:saturate(1.5) blur(12px);
border-bottom:1px solid var(--line)}
header.site .wrap{display:flex;flex-direction:column;gap:.25rem;padding-top:.6rem;padding-bottom:.45rem}
.brand{display:inline-flex;align-items:center;gap:.55rem;color:inherit;font-weight:800;letter-spacing:-.02em}
.brand:hover{text-decoration:none}
.brand .logo{width:1.6rem;height:1.6rem;color:var(--accent);flex:none}
.brand .bn{font-size:1.18rem}
.brandtag{display:none}
.tag{font-size:.82rem;color:var(--muted)}
.nav{display:flex;gap:.1rem;overflow-x:auto;scrollbar-width:none;
margin:0 -1.15rem;padding:.15rem 1.15rem .3rem;-webkit-overflow-scrolling:touch}
.nav::-webkit-scrollbar{display:none}
.nav a{white-space:nowrap;color:var(--muted);font-size:.9rem;font-weight:500;
padding:.5rem .72rem;border-radius:var(--pill);line-height:1}
.nav a:hover{color:var(--accent);background:var(--accent-weak);text-decoration:none}

/* Typographic rhythm */
h1{font-size:1.65rem;line-height:1.15;letter-spacing:-.022em;margin:.6rem 0 .4rem;font-weight:800}
h2{font-size:1.4rem;line-height:1.22;letter-spacing:-.02em;margin:2.1rem 0 .7rem;font-weight:750}
h3{font-size:1.05rem;margin:1.4rem 0 .45rem;font-weight:700}
h4{font-size:.78rem;margin:1.1rem 0 .35rem;font-weight:700;color:var(--muted);
text-transform:uppercase;letter-spacing:.05em}
p{margin:.6rem 0}
.lede{font-size:1.08rem;color:var(--muted);max-width:44rem}
ol,ul{padding-left:1.25rem}
li{margin:.3rem 0}
blockquote{margin:.85rem 0;padding:.6rem .95rem;border-left:3px solid var(--accent-2);
background:var(--card);border-radius:0 10px 10px 0;color:var(--muted)}
code{font-family:var(--mono);font-size:.85em;background:var(--card);padding:.12em .4em;border-radius:6px}
hr{border:0;border-top:1px solid var(--line);margin:2rem 0}

/* Hero */
.hero{position:relative;margin:0 0 1.4rem;padding:2.6rem 0 2rem;border-bottom:1px solid var(--line);overflow:hidden}
.hero::before{content:"";position:absolute;inset:-1px;z-index:-1;
background:radial-gradient(1100px 380px at 12% -20%,var(--accent-weak),transparent 62%)}
.hero-h{font-size:clamp(1.9rem,6vw,2.9rem);line-height:1.06;letter-spacing:-.032em;
margin:.1rem 0 .7rem;max-width:19ch;font-weight:820}
.hero-p{font-size:1.08rem;color:var(--muted);max-width:42rem;margin:0}
.hero-cta{display:flex;gap:.65rem;flex-wrap:wrap;margin:1.5rem 0 .7rem}
.cta{display:inline-flex;align-items:center;justify-content:center;min-height:2.9rem;
padding:.7rem 1.3rem;border-radius:var(--pill);background:var(--accent);color:#fff;font-weight:650;
box-shadow:var(--shadow-sm);transition:transform .12s ease,box-shadow .12s ease,background .12s ease}
.cta:hover{text-decoration:none;background:#1a4269;box-shadow:var(--shadow-md);transform:translateY(-1px)}
.cta:active{transform:translateY(0)}
.cta.ghost{background:#fff;color:var(--accent);border:1px solid var(--line);box-shadow:none}
.cta.ghost:hover{background:var(--card);border-color:var(--accent-2)}

/* Feature grid */
.grid3{display:grid;gap:1rem;grid-template-columns:1fr;margin:1.6rem 0}
.feat{border:1px solid var(--line);border-radius:var(--radius);padding:1.2rem;background:#fff;
box-shadow:var(--shadow-sm);transition:box-shadow .16s ease,transform .16s ease,border-color .16s ease}
.feat:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);border-color:var(--accent-weak)}
.feat h3{margin:.1rem 0 .45rem;font-size:1.02rem}
.feat p{margin:0;font-size:.92rem;color:var(--muted)}

/* Catalogue controls + cards */
.controls{display:flex;gap:.5rem;flex-wrap:wrap;margin:1.1rem 0;align-items:center}
input[type=search],select{font:inherit;padding:.6rem .8rem;min-height:2.75rem;
border:1px solid var(--line);border-radius:var(--radius-sm);background:#fff;color:var(--fg);box-shadow:var(--shadow-sm)}
input[type=search]{flex:1;min-width:12rem}
input[type=search]:focus,select:focus{outline:none;border-color:var(--accent-2);box-shadow:0 0 0 3px var(--accent-weak)}
.count{color:var(--muted);font-size:.85rem;font-variant-numeric:tabular-nums}
ul.cards{list-style:none;padding:0;margin:0;display:grid;gap:.8rem}
li.card{border:1px solid var(--line);border-radius:var(--radius);padding:1rem 1.1rem;background:#fff;
box-shadow:var(--shadow-sm);transition:box-shadow .16s ease,transform .16s ease,border-color .16s ease}
li.card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);border-color:var(--accent-weak)}
li.card h2{font-size:1.05rem;margin:0 0 .25rem;letter-spacing:-.01em}
li.card h2 a{text-decoration:none;color:var(--fg)}
li.card h2 a:hover{color:var(--accent)}
.meta{font-size:.82rem;color:var(--muted);display:flex;gap:.5rem;flex-wrap:wrap}
.meta span{white-space:nowrap}
.badge{display:inline-block;font-size:.68rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
border-radius:var(--pill);padding:.2rem .55rem;margin-right:.35rem;background:var(--card);color:var(--muted)}
.badge.quar{color:#7c1c16;background:var(--warn-weak)}
.badge.ok{color:var(--ok);background:var(--ok-weak)}
.badge.part{color:var(--caut);background:var(--caut-weak)}
.badge.community{color:#1f4e79;background:var(--accent-weak)}
.stats{margin-top:.5rem;font-size:.82rem;color:var(--muted);font-variant-numeric:tabular-nums}
.stats .star{color:#b8860b}
.stats .none{color:var(--muted);opacity:.8}

/* Tables */
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:1rem 0}
th,td{text-align:left;padding:.55rem .6rem;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.74rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:700}

/* Banners */
.banner{border-radius:var(--radius);padding:.9rem 1.05rem;margin:1.1rem 0;font-size:.92rem}
.banner.quar{background:var(--warn-weak);color:#7c1c16}
.banner.okb{background:var(--ok-weak);color:#14521f}

/* Footer */
footer.site{border-top:1px solid var(--line);margin-top:3rem;padding:1.8rem 0 3.5rem;
font-size:.84rem;color:var(--muted);background:var(--card)}
footer.site strong{color:var(--fg)}
.fnav{line-height:2.2}
.fnav a{color:var(--muted)}
.fnav a:hover{color:var(--accent)}

@media (min-width:640px){
.grid3{grid-template-columns:repeat(3,1fr)}
header.site .wrap{flex-direction:row;align-items:center;gap:1.1rem;flex-wrap:wrap}
.brand .bn{font-size:1.25rem}
.nav{margin:0;padding:0;overflow:visible;flex-wrap:wrap;gap:.15rem;margin-left:auto}
}
@media (min-width:960px){.wrap{padding:0 1.5rem}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

# HERO_CSS is appended at build time from site_pages.HERO_CSS
CSS = CSS.rstrip() + "\n" + HERO_CSS if "HERO_CSS" not in CSS else CSS


SW_HEADER = """// Offline support. A checklist you cannot open in a metal hangar is not a
// checklist, so the shell and every checklist page are precached.
"""

SW_BODY = """
self.addEventListener('install', function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){
    // addAll fails the whole install if any single request 404s, so add each
    // entry individually and tolerate misses.
    return Promise.all(ASSETS.map(function(u){
      return c.add(new Request(u, {cache: 'reload'})).catch(function(){});
    }));
  }).then(function(){ return self.skipWaiting(); }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){ return k !== CACHE; })
                           .map(function(k){ return caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});

self.addEventListener('fetch', function(e){
  if (e.request.method !== 'GET') return;
  if (new URL(e.request.url).origin !== self.location.origin) return;
  // Network first, so a corrected checklist is never served stale from cache,
  // falling back to the cache when there is no signal.
  e.respondWith(
    fetch(e.request).then(function(res){
      var copy = res.clone();
      caches.open(CACHE).then(function(c){ c.put(e.request, copy); }).catch(function(){});
      return res;
    }).catch(function(){ return caches.match(e.request); })
  );
});
"""



def head(title: str, desc: str, rel: str = "") -> str:
    icon = "data:image/svg+xml;utf8," + urllib.parse.quote(FAVICON_SVG)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#1f4e79">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{BRAND_NAME}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{icon}">
<link rel="apple-touch-icon" href="{rel}icon-192.png">
<link rel="manifest" href="{rel}manifest.webmanifest">
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{AUTH_PILL_JS}
<header class="site"><div class="wrap">
<a class="brand" href="{rel}index.html">{LOGO_SVG}<span class="bn">{BRAND_NAME}</span></a>
<p class="tag brandtag">{TAGLINE}</p>
<nav class="nav" aria-label="Primary">
<a href="{rel}catalogue.html">Checklists</a>
<a href="{rel}airports.html">Airports &amp; weather</a>
<a href="{rel}planner.html">Plan a Flight</a>
<a href="{rel}training.html">Training</a>
<a href="{rel}search.html">Troubleshooting</a>
</nav>
</div></header>
<main class="wrap" id="main">
"""

# Auth pill JS — injected into every page. Checks sessionStorage for token,
# renders a sign-in link or avatar pill in the nav. Self-contained, ~600 bytes.
AUTH_PILL_JS = r"""
<script>
/* ---- OCL auth helpers — available on every page ---- */
var OCL_API = 'https://app.openchecklists.net/api';

function oclToken() {
  var tok = sessionStorage.getItem('ocl:token');
  if (!tok) return null;
  try {
    var p = JSON.parse(atob(tok.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));
    if (p.exp && p.exp < Date.now()/1000) { sessionStorage.removeItem('ocl:token'); return null; }
    return tok;
  } catch(e) { return null; }
}

function oclReq(method, path, body) {
  var tok = oclToken();
  if (!tok) return Promise.reject('not signed in');
  return fetch(OCL_API + path, {
    method: method,
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok },
    body: body ? JSON.stringify(body) : undefined,
  }).then(function(r){ return r.json(); });
}

(function(){
  var nav = document.querySelector('nav.nav');
  if (!nav) return;
  var tok = oclToken();
  var pill = document.createElement('a');
  pill.style.cssText = 'margin-left:auto;font-weight:700;color:var(--accent);white-space:nowrap;padding:.5rem .72rem;border-radius:999px';
  pill.href = '/profile.html';
  pill.textContent = tok ? '👤 My Account' : 'Sign in';
  nav.appendChild(pill);
})();
</script>
"""


FOOT = """</main>
<footer class="site"><div class="wrap">
<p><strong>Nothing here is approved data.</strong> Every file records its source and its
verification state. Verify against your aircraft's own approved documentation before
flight. No warranty of any kind &mdash; see <a href="terms.html">terms</a>.</p>
<p class="fnav">
<a href="index.html">Home</a> &middot;
<a href="catalogue.html">Catalogue</a> &middot;
<a href="airports.html">Airports</a> &middot;
<a href="training.html">Training</a> &middot;
<a href="search.html">Troubleshooting</a> &middot;
<a href="charts.html">Charts</a> &middot;
<a href="projects.html">Projects</a> &middot;
<a href="editor.html">Editor</a> &middot;
<a href="contribute.html">Contribute</a> &middot;
<a href="about.html">Verification states</a> &middot;
<a href="api/index.json">API</a> &middot;
<a href="manifest.sha256">Manifest</a> &middot;
<a href="privacy.html">Privacy</a> &middot;
<a href="terms.html">Terms</a> &middot;
<a href="takedown.html">Takedown</a> &middot;
<a href="contact.html">Contact</a></p>
<p>Corpus rights are recorded per file. No analytics, no tracking cookies.
Optional account for saving aircraft profiles and plan history &mdash; see <a href="privacy.html">privacy policy</a>.</p>
</div></footer>
<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(function(){ /* offline is a bonus */ });
}
</script>
</body>
</html>
"""


def badges(doc: dict) -> str:
    v = doc.get("verification", {})
    out = []
    if is_quarantined(doc):
        out.append('<span class="badge quar">NOT REVIEWED</span>')
    else:
        out.append('<span class="badge ok">REVIEWED</span>')
    comp = v.get("completeness")
    if comp and comp != "full":
        out.append(f'<span class="badge part">{comp.replace("_", " ").upper()}</span>')
    return "".join(out)


def entry(doc: dict, path: Path) -> dict:
    ac = doc.get("aircraft", {})
    v = doc.get("verification", {})
    src = doc.get("provenance", {}).get("source", {})
    return {
        "id": doc["id"],
        "title": doc.get("title"),
        "aircraft": {
            "make": ac.get("make"),
            "model": ac.get("model"),
            "variant": ac.get("variant"),
            "category": ac.get("category"),
            "icao_type": ac.get("icao_type"),
        },
        "engine_type": (ac.get("engine") or [{}])[0].get("type"),
        "verification": {
            "source_fidelity": v.get("source_fidelity"),
            "operational_review": v.get("operational_review"),
            "completeness": v.get("completeness"),
            "quarantined": is_quarantined(doc),
            "safety_defects": sum(
                1 for i in v.get("known_issues", []) if i.get("severity") == "safety_defect"
            ),
        },
        "rights": {
            "status": doc.get("rights", {}).get("status"),
            "license": doc.get("rights", {}).get("corpus_license"),
            "redistribution": doc.get("rights", {}).get("redistribution"),
        },
        "source": {
            "kind": src.get("kind"),
            "title": src.get("title"),
            "revision": src.get("revision"),
        },
        "sections": len(doc.get("sections", [])),
        "items": sum(len(s.get("items", [])) for s in doc.get("sections", [])),
        "tickable_items": sum(
            1 for s in doc.get("sections", []) for i in s.get("items", []) if i.get("tickable")
        ),
        "memory_items": sum(
            1 for s in doc.get("sections", []) for i in s.get("items", []) if i.get("memory_item")
        ),
        "airframe_family": ac.get("airframe_family"),
        "modifications": [
            {
                "kind": m.get("kind"),
                "description": m.get("description"),
                "affects_procedures": bool(m.get("affects_procedures")),
            }
            for m in ac.get("modifications", [])
        ],
        "registration": (ac.get("airframe_specific") or {}).get("registration"),
        "derived_from": doc.get("derived_from"),
        "phases": sorted({s.get("phase") for s in doc.get("sections", []) if s.get("phase")}),
        "content_hash": content_hash(doc),
        "file_revision": doc.get("provenance", {}).get("revision", {}).get("file_revision"),
        "page": f"c/{doc['id']}/",
        "downloads": {},  # filled in by build
        "source_file": path.name,
    }


INDEX_JS = r"""
(function(){
  var data = JSON.parse(document.getElementById('catalogue').textContent);
  var q = document.getElementById('q'),
      cat = document.getElementById('cat'),
      ver = document.getElementById('ver'),
      list = document.getElementById('list'),
      count = document.getElementById('count');

  function fam(e){
    if (!e.airframe_family) return '';
    var f = (data.families || {})[e.airframe_family];
    if (!f) return '';
    var n = f.count;
    var mods = (e.modifications || []).length;
    var bits = [];
    if (n > 1) bits.push('<a href="' + f.page + '">' + n + ' variations of this airframe</a>');
    if (mods) bits.push(mods + ' modification' + (mods > 1 ? 's' : '') + ' recorded');
    if (e.derived_from) bits.push('forked from <code>' + e.derived_from.checklist_id + '</code>');
    return bits.length ? '<div class="meta" style="margin-top:.3rem">' +
      bits.map(function(b){ return '<span>' + b + '</span>'; }).join('') + '</div>' : '';
  }

  // Ratings/usage stats, keyed by checklist id. Filled in by loadStats() after
  // the cards are already on the page; cards render a placeholder first.
  var STATS = {};

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');
  }

  // The stats line for one entry. Rendered as its own node (id keyed off the
  // checklist id) so loadStats() can refresh just this line in place.
  function statsHtml(e){
    var st = STATS[e.id];
    if (!st) return '<span class="none">Loading ratings…</span>';
    var stars = +st.avg_stars || 0, revs = +st.review_count || 0, uses = +st.uses || 0;
    if (!revs && !uses) return '<span class="none">No ratings yet</span>';
    var bits = [];
    if (revs) {
      bits.push('<span class="star">★</span> ' + stars.toFixed(1) +
        ' · ' + revs + ' review' + (revs === 1 ? '' : 's'));
    } else {
      bits.push('<span class="none">No ratings yet</span>');
    }
    if (uses) bits.push(uses + ' used');
    return bits.join(' · ');
  }

  function statsId(e){ return 'st-' + String(e.id).replace(/[^a-zA-Z0-9_-]/g, '_'); }

  function card(e){
    var badge = '';
    if (e.community) {
      badge += '<span class="badge community">COMMUNITY</span>';
    } else if (e.verification && e.verification.quarantined) {
      badge += '<span class="badge quar">NOT REVIEWED</span>';
    } else if (e.verification) {
      badge += '<span class="badge ok">REVIEWED</span>';
    }
    if (e.verification && e.verification.completeness && e.verification.completeness !== 'full') {
      badge += '<span class="badge part">' +
        e.verification.completeness.replace(/_/g,' ').toUpperCase() + '</span>';
    }
    var ac = e.aircraft
      ? [e.aircraft.make, e.aircraft.model, e.aircraft.variant].filter(Boolean).join(' ')
      : (e.author ? 'by ' + esc(e.author) : '');
    var meta = '<div class="meta">' + badge + (ac ? '<span>' + esc(ac) + '</span>' : '');
    if (e.aircraft) {
      meta += '<span>' + (e.aircraft.category||'').replace(/_/g,' ') + '</span>' +
        '<span>' + e.tickable_items + ' items</span>' +
        (e.memory_items ? '<span>' + e.memory_items + ' memory</span>' : '') +
        '<span>' + esc((e.rights ? (e.rights.license || e.rights.status) : '') || '') + '</span>' +
        (e.registration ? '<span>' + esc(e.registration) + '</span>' : '');
    }
    meta += '</div>';
    return '<li class="card"><h2><a href="' + e.page + '">' + esc(e.title) + '</a></h2>' +
      meta + (e.community ? '' : fam(e)) +
      '<div class="stats" id="' + statsId(e) + '">' + statsHtml(e) + '</div></li>';
  }

  // Rank so highest-rated and most-used rise to the top. Score is
  // avg_stars * review_count (a well-reviewed 5-star beats a single review),
  // then raw uses; unrated items keep their original order but sink below rated.
  function score(e){
    var st = STATS[e.id] || {};
    return (+st.avg_stars || 0) * (+st.review_count || 0);
  }
  function rank(a, b){
    var sa = score(a), sb = score(b);
    if (sb !== sa) return sb - sa;
    var ua = +(STATS[a.id]||{}).uses || 0, ub = +(STATS[b.id]||{}).uses || 0;
    if (ub !== ua) return ub - ua;
    return 0;
  }

  function apply(){
    var s = q.value.toLowerCase().trim();
    var c = cat.value, vf = ver.value;
    var out = ALL.filter(function(e){
      if (c && (!e.aircraft || e.aircraft.category !== c)) return false;
      if (vf === 'reviewed' && (e.community || (e.verification && e.verification.quarantined))) return false;
      if (vf === 'unreviewed' && !(e.community || (e.verification && e.verification.quarantined))) return false;
      if (!s) return true;
      var ac = e.aircraft || {};
      var hay = [e.title, e.author, ac.make, ac.model, ac.variant,
                 ac.icao_type, ac.category, (e.source||{}).title,
                 e.engine_type, e.airframe_family, e.registration,
                 (e.modifications||[]).map(function(m){ return m.kind + ' ' + m.description; }).join(' ')
                ].join(' ').toLowerCase();
      return hay.indexOf(s) !== -1;
    });
    out.sort(rank);
    list.innerHTML = out.map(card).join('') ||
      '<li class="card">Nothing matches. Try a make, a model, or a category.</li>';
    count.textContent = out.length + ' of ' + ALL.length;
  }

  // Working list = static example checklists + any community-published ones.
  var ALL = (data.checklists || []).slice();

  // Bulk-fetch ratings/usage for the currently visible ids, then refresh each
  // card's stats line in place and re-sort by the new ranking. Static example
  // slugs and community ids are both valid ids for the stats endpoint.
  function loadStats(){
    var ids = ALL.map(function(e){ return e.id; }).filter(Boolean);
    if (!ids.length) return;
    var chunks = [];
    for (var i = 0; i < ids.length; i += 300) chunks.push(ids.slice(i, i + 300));
    Promise.all(chunks.map(function(chunk){
      return fetch(OCL_API + '/checklists/stats?ids=' + encodeURIComponent(chunk.join(',')))
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(j){ if (j && j.stats) Object.assign(STATS, j.stats); })
        .catch(function(){});
    })).then(function(){
      // Fill in each existing stats node, then re-sort so top-rated rise up.
      ALL.forEach(function(e){
        var node = document.getElementById(statsId(e));
        if (node) node.innerHTML = statsHtml(e);
      });
      apply();
    });
  }

  // Merge community-published checklists in, then load stats for everything.
  // A community entry links to /checklist/?id=<id> (path URLs don't work on
  // this host) and carries a distinct Community badge. If the API is
  // unreachable we just show the static examples.
  function loadCommunity(){
    fetch(OCL_API + '/checklists')
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(j){
        if (j && j.checklists && j.checklists.length) {
          var seen = {};
          ALL.forEach(function(e){ seen[e.id] = true; });
          j.checklists.forEach(function(c){
            if (!c || !c.id || seen[c.id]) return;
            seen[c.id] = true;
            ALL.push({
              id: c.id,
              title: c.title || 'Untitled checklist',
              author: c.author || '',
              community: true,
              page: '/checklist/?id=' + encodeURIComponent(c.id)
            });
          });
          apply();
        }
      })
      .catch(function(){ /* offline / API down — static examples still show */ })
      .then(function(){ loadStats(); });
  }

  [q, cat, ver].forEach(function(el){ el.addEventListener('input', apply); });
  apply();
  loadCommunity();
})();
"""


def build_index(entries: list[dict], catalogue: dict) -> str:
    cats = sorted({e["aircraft"]["category"] for e in entries if e["aircraft"].get("category")})
    opts = "".join(f'<option value="{c}">{c.replace("_", " ")}</option>' for c in cats)
    return (
        head(
            "Open Checklists — free machine-readable aircraft checklists",
            "A free, open library of aircraft checklists in a standard format anyone can "
            "consume, reformat, modify and redistribute.",
        )
        + f"""
<p class="lede">Every checklist here is a structured data file. Read it on a phone,
print it at whatever size your kneeboard takes, or load it into your own software.
Each one records the document it came from and whether a human has checked it
against that document.</p>

<div class="controls">
  <input type="search" id="q" placeholder="Search make, model, category, source…"
         aria-label="Search checklists">
  <select id="cat" aria-label="Category"><option value="">All categories</option>{opts}</select>
  <select id="ver" aria-label="Verification">
    <option value="">Any state</option>
    <option value="reviewed">Reviewed only</option>
    <option value="unreviewed">Not reviewed</option>
  </select>
  <span class="count" id="count"></span>
</div>

<ul class="cards" id="list"></ul>

<h2>Using this from software</h2>
<p>No API key, no rate limit, no registration. Plain HTTP paths:</p>
<table><tbody>
<tr><td><code>api/index.json</code></td><td>The whole catalogue with metadata, verification state and rights per file</td></tr>
<tr><td><code>api/checklists/&lt;id&gt;.json</code></td><td>One checklist, canonical form</td></tr>
<tr><td><code>c/&lt;id&gt;/&lt;id&gt;.csv</code></td><td>Same content, one row per item, with a type column</td></tr>
<tr><td><code>manifest.sha256</code></td><td>SHA-256 of every published artifact, for verifying a mirror</td></tr>
<tr><td><code>reviewed.txt</code></td><td>Files that a human has checked against their source</td></tr>
<tr><td><code>unreviewed.txt</code></td><td>Files nobody has checked. Kept separate deliberately</td></tr>
</tbody></table>
<p>Validate any file against
<code>schema/open-checklist-1.0.schema.json</code>. Schema validity is necessary but
not sufficient — see <a href="about.html">what the states mean</a>.</p>

<script type="application/json" id="catalogue">{json.dumps(catalogue)}</script>
<script>{INDEX_JS}</script>
"""
        + FOOT
    )


ABOUT = """
<h2>What the verification states mean</h2>
<p>A checklist is a safety document. The most dangerous thing this project could do
is let an unchecked machine transcription look like a checked one, so every file
carries its state on two independent axes and neither implies the other.</p>

<h3>Does it match its source?</h3>
<table><tbody>
<tr><td><code>unreviewed</code></td><td>Machine or first-pass output. Nobody has compared it to the source document.</td></tr>
<tr><td><code>single_reviewed</code></td><td>One person, not the transcriber, compared it line by line against the source.</td></tr>
<tr><td><code>dual_reviewed</code></td><td>Two people did so independently.</td></tr>
<tr><td><code>not_applicable</code></td><td>There is no source document. The content is authored — common for Part 103, where no approved flight manual is required.</td></tr>
</tbody></table>

<h3>Has it been used in an aircraft?</h3>
<table><tbody>
<tr><td><code>none</code></td><td>Never exercised against a real aircraft.</td></tr>
<tr><td><code>ground_checked</code></td><td>Walked through in the actual cockpit, every control located.</td></tr>
<tr><td><code>flown</code></td><td>Flown behind in this type.</td></tr>
</tbody></table>

<h3>Why flying behind it is not the top state</h3>
<p>Flying behind a checklist cannot detect a missing item. Nothing prompts you to do
the check that was left out, so the flight feels entirely normal. That makes "flown"
weaker evidence of correctness than "two people compared it against the source" —
which is why operational review never lifts a file out of quarantine on its own.</p>

<h3>Completeness</h3>
<p>A file can be faithful to its source and still be missing whole sections. A
missing emergency procedure is invisible to the person holding the file, so
completeness is stated separately: <code>full</code>, <code>normal_only</code>,
<code>partial</code>, <code>excerpt</code>.</p>

<h3>Quarantine</h3>
<p>Files that are unreviewed, or that carry an unresolved safety defect, are
quarantined. They are still downloadable — review requires people to be able to read
them — but they are excluded from the default bundle, their filenames carry the
state, and they are never offered in a panel-loadable avionics format, because a
panel file has nowhere to put a warning label.</p>

<h3>Rights</h3>
<p>Rights are recorded per file, not repo-wide, because this project cannot grant a
licence in text it does not own. <code>public_domain</code> files state the basis
(most are US Government works under 17 U.S.C. 105). <code>original_expression</code>
means the wording is the contributor's own, expressing procedure taken as fact.
Files whose rights are unresolved are not published at all.</p>

<h3>Found a problem?</h3>
<p>File a report against the exact version you were looking at — every file has a
content hash. A confirmed transcription error or stale item costs the file its
verification badge automatically, which is how the corpus stays current instead of
merely claiming to.</p>
"""



ORDER_LABELS = ["Warnings and cautions", "Memory items", "Control settings", "Other changes"]


def diff_html(parent: dict, child: dict) -> str:
    """Render the semantic diff of a fork against its parent, safety-first."""
    findings, notes = semantic_diff(parent, child)
    buckets: dict[int, list] = {0: [], 1: [], 2: [], 3: []}
    for f in findings:
        buckets[f.rank].append(f)

    d = child.get("derived_from", {})
    out = ['<div class="lineage">']
    out.append(
        f'<p class="tag">Forked from <a href="../../c/{parent["id"]}/">{parent["id"]}</a>'
        + (
            " &middot; the parent has changed since this fork was taken"
            if d.get("content_hash") and d["content_hash"] != content_hash(parent)
            else ""
        )
        + "</p>"
    )
    if d.get("changes_summary"):
        out.append(f'<blockquote class="summary">{esc(d["changes_summary"])}</blockquote>')

    mods = child.get("aircraft", {}).get("modifications", [])
    if mods:
        out.append("<p><strong>Modifications</strong></p><ul>")
        for m in mods:
            flag = ' <em>(changes procedures)</em>' if m.get("affects_procedures") else ""
            out.append(f'<li><code>{esc(m["kind"])}</code>{flag} — {esc(m["description"])}</li>')
        out.append("</ul>")
    if notes:
        out.append("<p><strong>Configuration</strong></p><ul>")
        out += [f"<li>{esc(n)}</li>" for n in notes]
        out.append("</ul>")

    total = sum(len(v) for v in buckets.values())
    if total:
        out.append(f"<p><strong>{total} procedural difference(s)</strong></p>")
        for rank, label in enumerate(ORDER_LABELS):
            if not buckets[rank]:
                continue
            cls = "warn" if rank == 0 else ("mem" if rank == 1 else "")
            out.append(f'<p class="dlabel {cls}">{label}</p><ul class="dl-list">')
            for f in sorted(buckets[rank], key=lambda x: (x.where, x.kind)):
                out.append(
                    f'<li><code>{esc(f.kind)}</code> in <strong>{esc(f.where)}</strong> — {esc(f.text)}</li>'
                )
            out.append("</ul>")
    else:
        out.append("<p>No procedural differences from the parent.</p>")
    out.append("</div>")
    return "".join(out)


def esc(v: object) -> str:
    import html as _h

    return _h.escape(str(v if v is not None else ""))


FAMILY_CSS = """
.lineage{border-left:3px solid var(--line);padding-left:.9rem;margin:.6rem 0 1.2rem}
.summary{margin:.5rem 0;padding:.5rem .75rem;background:var(--card);border-radius:.3rem;
font-size:.88rem}
.dlabel{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
margin:.7rem 0 .2rem;font-weight:700}
.dlabel.warn{color:var(--warn)}
.dlabel.mem{color:var(--caut)}
.dl-list{font-size:.85rem;margin:.2rem 0 .5rem;padding-left:1.1rem}
.dl-list li{margin:.15rem 0}
.varhdr{display:flex;gap:.5rem;flex-wrap:wrap;align-items:baseline;margin-top:1.5rem}
.varhdr h2{margin:0;font-size:1.1rem}
"""


def family_page(family: str, members: list[dict], docs: dict[str, dict]) -> str:
    label = family.replace("-", " ")
    out = [
        head(f"{label} — variations — Open Checklists", f"Every checklist variation for the {label} airframe.", rel="../../"),
        f"<style>{FAMILY_CSS}</style>",
        f"<h2>{esc(label)}: {len(members)} variation(s)</h2>",
        '<p class="lede">Same airframe, different configurations. Engine swaps, panel '
        "rebuilds and gross weight changes are the norm in this class, so what one "
        "builder had to change is often exactly what the next one needs to know.</p>",
    ]
    by_id = {m["id"]: m for m in members}
    for m in sorted(members, key=lambda x: (bool(x.get("derived_from")), x["id"])):
        doc = docs[m["id"]]
        ac = m["aircraft"]
        eng = doc.get("aircraft", {}).get("engine", [{}])[0]
        engs = " ".join(filter(None, [eng.get("make"), eng.get("model")])) or "no engine"
        reg = f' &middot; {esc(m["registration"])}' if m.get("registration") else ""
        badge = (
            '<span class="badge quar">NOT REVIEWED</span>'
            if m["verification"]["quarantined"]
            else '<span class="badge ok">REVIEWED</span>'
        )
        out.append(
            f'<div class="varhdr">{badge}<h2><a href="../../c/{m["id"]}/">{esc(m["title"])}</a></h2></div>'
            f'<p class="tag">{esc(engs)}{reg} &middot; {m["tickable_items"]} items'
            f' &middot; {m["memory_items"]} memory</p>'
        )
        d = m.get("derived_from")
        if d and d.get("checklist_id") in docs:
            out.append(diff_html(docs[d["checklist_id"]], doc))
        elif m.get("modifications"):
            out.append('<div class="lineage"><p class="tag">Not forked from another file in the '
                       "corpus; modifications recorded directly.</p><ul>")
            for mod in m["modifications"]:
                flag = " <em>(changes procedures)</em>" if mod.get("affects_procedures") else ""
                out.append(f'<li><code>{esc(mod["kind"])}</code>{flag} — {esc(mod["description"])}</li>')
            out.append("</ul></div>")
        else:
            out.append('<div class="lineage"><p class="tag">Baseline file for this airframe.</p></div>')

    out.append(
        '<p><a href="../../editor.html">Make your own variation</a> — the editor will fork '
        "any of these and record the lineage for you.</p>"
    )
    out.append(FOOT)
    return "".join(out)


def build_airport_pages(airport_data: list[dict], effective_date: str, output_dir: Path) -> int:
    """
    Generate airport detail pages for all airports in the corpus.

    Args:
        airport_data: List of airport dicts from NASR data
        effective_date: AIRAC effective date (e.g., "2026-08-06")
        output_dir: Directory to write airport HTML files

    Returns:
        Number of airports successfully generated
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    errors = 0

    for i, airport in enumerate(airport_data, start=1):
        try:
            ident = airport.get("ident", "").lower()
            if not ident:
                errors += 1
                continue

            html = render_airport_page(airport, effective_date)
            out_file = output_dir / f"{ident}.html"
            out_file.write_text(html, encoding="utf-8")
            count += 1

            # Progress every 1000 airports
            if i % 1000 == 0:
                print(f"    {i:,} airports processed...")

        except Exception as e:
            errors += 1
            logging.warning(f"Error building {airport.get('ident')}: {e}")

    if errors:
        logging.warning(f"{errors} airport(s) skipped due to errors")

    return count


def render_airport_page(airport: dict, effective_date: str) -> str:
    """
    Render a complete airport page as HTML.

    Args:
        airport: Airport dict from NASR ingest (with all fields)
        effective_date: AIRAC effective date string (YYYY-MM-DD)

    Returns:
        HTML string with embedded SVG diagram, static data, and live data zones.
    """
    from html import escape
    import json

    ident = escape(airport.get("ident", ""))
    name = escape(airport.get("name", ident))
    city = escape(airport.get("city", ""))
    state = escape(airport.get("state", ""))
    elevation = airport.get("elevation_ft", "")
    pattern_alt = airport.get("pattern_altitude_ft", "")
    sectional = escape(airport.get("sectional", ""))
    lat = airport.get("lat", "")
    lon = airport.get("lon", "")
    status = escape(airport.get("status") or "Open")
    ownership = escape(airport.get("owner") or "Unknown")
    manager_phone = escape((airport.get("manager_phone") or "").strip())

    # Generate runway diagram SVG
    runway_svg = render_runway_svg(airport)

    # Import magnetic variation parser
    from render_runway_diagram import parse_magnetic_variation

    # Build runway data object for modal
    runway_data = {}
    if airport.get("runways"):
        mag_var = airport.get("magnetic_variation", "")
        magnetic_variation = parse_magnetic_variation(mag_var)

        for runway in airport["runways"]:
            rwy_id = runway.get("id", "")
            if rwy_id:
                ends_key = (airport.get("ident"), rwy_id)
                ends = airport.get("runway_ends", {}).get(ends_key, [])
                runway_data[rwy_id] = {
                    "id": rwy_id,
                    "length_ft": runway.get("length_ft", ""),
                    "width_ft": runway.get("width_ft", ""),
                    "surface": runway.get("surface", ""),
                    "condition": runway.get("condition", "Good"),
                    "lighting": runway.get("lighting", "Not listed"),
                    "ends": [
                        {
                            "end": end.get("end", ""),
                            "true_heading": end.get("true_heading", 0),
                            "ils": end.get("ils", "None"),
                            "displaced_threshold_ft": end.get("displaced_threshold_ft", 0),
                            "traffic_pattern": end.get("traffic_pattern", "L"),
                        }
                        for end in ends
                    ]
                }

    runway_data_json = json.dumps(runway_data)
    magnetic_var_deg = parse_magnetic_variation(airport.get("magnetic_variation", ""))

    # Validate lat/lon before rendering map
    map_js = ""
    try:
        lat_f = float(lat) if lat else None
        lon_f = float(lon) if lon else None
        if lat_f is not None and lon_f is not None:
            map_js = f"""
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<section id="map"></section>
<script>
(function() {{
  var map = L.map('map', {{zoomControl: true}}).setView([{lat_f}, {lon_f}], 15);

  var streets = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '© OpenStreetMap',
    maxZoom: 19
  }});

  var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    attribution: 'ESRI World Imagery',
    maxZoom: 19
  }});

  var topo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    attribution: 'ESRI World Topo',
    maxZoom: 18
  }});

  satellite.addTo(map);

  var baseLayers = {{
    'Satellite': satellite,
    'Terrain': topo,
    'Street': streets
  }};

  L.control.layers(baseLayers, {{}}, {{position: 'topright', collapsed: false}}).addTo(map);

  L.marker([{lat_f}, {lon_f}])
    .addTo(map)
    .bindPopup('<strong>{ident}</strong><br>{escape(name)}<br>{escape(city)}, {escape(state)}<br>Elev: {elevation or "N/A"} ft')
    .openPopup();
}})();
</script>
"""
        else:
            map_js = ''
    except (ValueError, TypeError):
        map_js = ''

    # Format frequencies with priority sorting
    freq_html = ""
    if airport.get("frequencies"):
        freq_html = "<table class='freqtable'><thead><tr><th>Frequency</th><th>Use</th><th>Facility</th><th>Callsign</th><th>Hours</th></tr></thead><tbody>"
        # Sort frequencies by VFR pilot priority (case-insensitive)
        priority = ["CTAF", "Unicom", "Tower", "Ground", "Clearance delivery", "ATIS", "AWOS", "ASOS"]
        priority_upper = [p.upper() for p in priority]

        sorted_freqs = sorted(
            airport["frequencies"],
            key=lambda f: (
                priority_upper.index(f.get("use", "").upper()) if f.get("use", "").upper() in priority_upper else len(priority),
                f.get("use", "")
            )
        )
        for f in sorted_freqs:
            freq = escape(f.get("frequency", ""))
            use = escape(f.get("use", ""))
            facility = escape(f.get("facility", "") or "")
            callsign = escape(f.get("callsign", "") or "")
            hours = escape(f.get("hours", "") or "")
            staffed = "staffed" if use in ("Tower", "Ground", "Clearance delivery") else "automated"
            freq_html += (
                f"<tr class='{staffed}'>"
                f"<td>{freq}</td>"
                f"<td>{use}</td>"
                f"<td>{facility}</td>"
                f"<td>{callsign}</td>"
                f"<td>{hours}</td>"
                f"</tr>"
            )
        freq_html += "</tbody></table>"
    else:
        freq_html = "<p class='muted'>No frequencies on record.</p>"

    html = head(
        f"{name} ({ident}) — {city}, {state}",
        f"Airport information, radio frequencies, live weather and NOTAMs for {name} ({ident}).",
        rel="../"
    )
    html += f"""
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
#map{{height:300px;border-radius:var(--radius);margin:1.5rem 0;border:1px solid var(--line);overflow:hidden}}
.fact-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.65rem;margin:1rem 0 1.5rem}}
.fact-card{{background:#fff;border:1px solid var(--line);border-radius:var(--radius-sm);padding:.8rem .9rem}}
.fact-card .lbl{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:.2rem}}
.fact-card .val{{font-size:1rem;font-weight:700}}
.rwy-chips{{display:flex;flex-wrap:wrap;gap:.5rem;margin:.8rem 0}}
.rwy-chip{{background:var(--card);border:1px solid var(--line);border-radius:var(--pill);padding:.4rem .9rem;font-size:.88rem;font-weight:600;cursor:pointer;color:var(--fg);transition:background .15s,border-color .15s}}
.rwy-chip:hover,.rwy-chip.active{{background:var(--accent-weak);border-color:var(--accent-2);color:var(--accent)}}
.rwy-detail{{display:none;background:var(--card);border-radius:var(--radius-sm);padding:1rem 1.1rem;margin:.35rem 0 .8rem;border:1px solid var(--line);font-size:.9rem}}
.rwy-detail.open{{display:block}}
.rwy-detail p{{margin:.3rem 0}}
.live-card{{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:1.1rem 1.2rem;margin:.8rem 0;box-shadow:var(--shadow-sm)}}
.live-card h3{{margin:0 0 .5rem;font-size:1rem;font-weight:700}}
.spinner-sm{{display:inline-block;width:13px;height:13px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:rsp .7s linear infinite;vertical-align:middle;margin-right:.4rem}}
@keyframes rsp{{to{{transform:rotate(360deg)}}}}
.wx-badge{{display:inline-block;padding:.18rem .52rem;border-radius:var(--pill);font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;vertical-align:middle}}
.wx-vfr{{background:var(--ok-weak);color:var(--ok)}}
.wx-mvfr{{background:var(--caut-weak);color:var(--caut)}}
.wx-ifr{{background:var(--warn-weak);color:var(--warn)}}
.freq-ctaf{{font-weight:700;color:var(--accent)}}
.ext-links{{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}}
.ext-links a{{display:inline-flex;align-items:center;gap:.3rem;padding:.38rem .8rem;border:1px solid var(--line);border-radius:var(--pill);font-size:.84rem;color:var(--muted);text-decoration:none}}
.ext-links a:hover{{border-color:var(--accent-2);color:var(--accent)}}
</style>

<div style="display:flex;align-items:baseline;gap:.8rem;flex-wrap:wrap;margin-bottom:.2rem">
  <span style="font-size:2.6rem;font-weight:800;letter-spacing:-.04em;color:var(--accent);line-height:1">{ident}</span>
  <span class="badge">{status}</span>
</div>
<h1 style="margin:.1rem 0 .05rem;font-size:1.5rem">{name}</h1>
<p class="lede" style="margin:0 0 1.2rem;font-size:.95rem">{city}, {state}</p>

<div class="fact-grid">
  <div class="fact-card"><div class="lbl">Elevation</div><div class="val">{elevation or "—"} ft MSL</div></div>
  <div class="fact-card"><div class="lbl">Pattern Alt</div><div class="val">{pattern_alt or "—"} ft</div></div>
  <div class="fact-card"><div class="lbl">Sectional</div><div class="val">{sectional or "—"}</div></div>
  <div class="fact-card"><div class="lbl">Ownership</div><div class="val">{ownership}</div></div>
  {'<div class="fact-card"><div class="lbl">Phone</div><div class="val"><a href="tel:' + manager_phone + '">' + manager_phone + '</a></div></div>' if manager_phone else ''}
</div>

<div style="margin:0 0 1.8rem">
  <a class="cta" href="/planner.html?dep={ident}" style="font-size:.88rem;min-height:2.4rem;padding:.5rem 1.1rem">✈ Plan a flight from {ident}</a>
</div>

"""
    # Map (shown before runways so pilots see the aerial view right away)
    html += map_js

    html += """
<h2>Runways</h2>
"""
    # Runway inline detail cards
    if airport.get("runways"):
        html += '<div class="rwy-chips">'
        for rwy in airport["runways"]:
            rwy_id = escape(rwy.get("id", ""))
            if rwy_id:
                html += f'<button class="rwy-chip" onclick="toggleRwy(this,\'{rwy_id}\')">{rwy_id}</button>'
        html += '</div>'
        for rwy in airport["runways"]:
            rwy_id = escape(rwy.get("id", ""))
            if not rwy_id:
                continue
            length = rwy.get("length_ft", "?")
            width = rwy.get("width_ft", "?")
            surface = rwy.get("surface", "Unknown surface")
            lighting = rwy.get("lighting", "Not listed")
            ends = runway_data.get(rwy_id, {}).get("ends", [])
            ends_html = ""
            for end in ends:
                end_id = escape(str(end.get("end", "")))
                hdg = end.get("true_heading", "?")
                ils = escape(str(end.get("ils", "None") or "None"))
                dp = end.get("displaced_threshold_ft", 0) or 0
                pat = "Right" if end.get("traffic_pattern") == "R" else "Left"
                ends_html += f'<p><strong>Runway {end_id}:</strong> {hdg}°T · ILS: {ils} · Displaced: {dp} ft · Pattern: {pat}</p>'
            html += f'<div class="rwy-detail" id="rwy-{rwy_id}"><p><strong>{length} × {width} ft</strong> · {surface} · Lighting: {lighting}</p>{ends_html}</div>'
    else:
        html += '<p class="muted">No runway data on record.</p>'

    # Frequencies
    html += """
<h2>Frequencies</h2>
<div class="scroll">
<table class="freqtable">
<thead><tr><th>MHz</th><th>Use</th><th>Facility</th><th>Callsign</th><th>Hours</th></tr></thead>
<tbody>
"""
    if airport.get("frequencies"):
        for f in sorted(
            airport["frequencies"],
            key=lambda f: (
                ["CTAF", "UNICOM", "TOWER", "GROUND", "CLEARANCE DELIVERY", "ATIS", "AWOS", "ASOS"].index(f.get("use", "").upper())
                if f.get("use", "").upper() in ["CTAF", "UNICOM", "TOWER", "GROUND", "CLEARANCE DELIVERY", "ATIS", "AWOS", "ASOS"] else 99,
                f.get("use", "")
            )
        ):
            freq = escape(f.get("frequency", ""))
            use = escape(f.get("use", ""))
            facility = escape(f.get("facility", "") or "")
            callsign = escape(f.get("callsign", "") or "")
            hours = escape(f.get("hours", "") or "")
            is_ctaf = use.upper() in ("CTAF", "UNICOM", "TOWER")
            cls = ' class="freq-ctaf"' if is_ctaf else ''
            html += f'<tr><td{cls}>{freq}</td><td{cls}>{use}</td><td>{facility}</td><td>{callsign}</td><td>{hours}</td></tr>\n'
    else:
        html += '<tr><td colspan="5" class="muted">No frequencies on record.</td></tr>'
    html += '</tbody></table></div>'

    # Sun Times card (JS calculated from lat/lon, no API needed)
    if lat_f is not None and lon_f is not None:
        html += f"""
<div class="live-card" style="margin:.8rem 0">
  <h3 style="margin:0 0 .5rem">Sun Times</h3>
  <div id="sun-times" style="display:flex;gap:1.5rem;flex-wrap:wrap;font-size:.9rem">
    <div><span class="lbl">Sunrise</span><br><strong id="sun-rise">—</strong></div>
    <div><span class="lbl">Sunset</span><br><strong id="sun-set">—</strong></div>
    <div><span class="lbl">Civil Twilight</span><br><strong id="sun-twilight">—</strong></div>
    <div><span class="lbl">Day Length</span><br><strong id="sun-daylen">—</strong></div>
  </div>
</div>"""

    # Live data sections
    if lat_f is not None and lon_f is not None:
        windy_embed = f"""<div id="windy-wrap" style="display:none;margin:.6rem 0;border-radius:var(--radius);overflow:hidden;border:1px solid var(--line)">
<iframe width="100%" height="360" src="https://embed.windy.com/embed2.html?lat={lat_f}&lon={lon_f}&zoom=10&level=surface&overlay=wind&product=ecmwf&menu=&message=true&marker=true&metricWind=kt&metricTemp=%C2%B0F" frameborder="0" loading="lazy" title="Windy weather map"></iframe>
</div>"""
    else:
        windy_embed = ""

    html += f"""
<h2>Live Data</h2>
<div id="weather" class="live-card"><span class="spinner-sm"></span> Loading weather...</div>
{windy_embed}
<div id="notams" class="live-card"><span class="spinner-sm"></span> Loading NOTAMs...</div>
<div id="fuel" class="live-card"><span class="spinner-sm"></span> Loading fuel &amp; FBO...</div>
<div id="winds-aloft" class="live-card"><span class="spinner-sm"></span> Loading winds aloft...</div>
<div id="pireps" class="live-card"><span class="spinner-sm"></span> Loading PIREPs...</div>
"""

    # External links
    ext_lat = lat or "0"
    ext_lon = lon or "0"
    html += f"""
<h2>External Links</h2>
<div class="ext-links">
  <a href="https://skyvector.com/?ll={ext_lat},{ext_lon}" target="_blank" rel="noopener">📡 SkyVector</a>
  <a href="https://www.airnav.com/airports/{ident}" target="_blank" rel="noopener">📋 AirNav</a>
  <a href="https://notams.faa.gov/notamSearch/search" target="_blank" rel="noopener">⚠ FAA NOTAMs</a>
  <a href="https://aviationweather.gov/metar?ids={ident}" target="_blank" rel="noopener">🌤 Wx Forecast</a>
</div>
"""

    # Live Resources section
    html += f"""
<h2>Live Resources</h2>
<div class="ext-links">
  <a href="https://www.liveatc.net/search/?icao={ident}" target="_blank" rel="noopener">🎧 LiveATC Audio</a>
  <a href="https://www.flightaware.com/live/airport/{ident}" target="_blank" rel="noopener">✈ FlightAware</a>
  <a href="https://weathercams.faa.gov/" target="_blank" rel="noopener">📷 FAA WxCams</a>
  <a href="https://www.1800wxbrief.com/" target="_blank" rel="noopener">📋 1800wxBrief</a>
</div>
"""

    # Lat/lon JS vars for weather fallback
    _lat_lon_js = f"window.OCL_LAT={lat_f};window.OCL_LON={lon_f};" if (lat_f is not None and lon_f is not None) else "window.OCL_LAT=null;window.OCL_LON=null;"

    # Scripts and inline airport footer
    html += f"""
<script>
window.OCL_AIRPORT = '{ident}';
window.OCL_API_BASE = 'https://app.openchecklists.net/api/airport/';
{_lat_lon_js}

function toggleRwy(btn, id) {{
  var el = document.getElementById('rwy-' + id);
  if (!el) return;
  var open = el.classList.toggle('open');
  btn.classList.toggle('active', open);
}}

// Sun times calculated from lat/lon (no API needed)
(function() {{
  var lat = window.OCL_LAT, lon = window.OCL_LON;
  if (!lat || !lon) return;
  var now = new Date();
  function calcSun(date, lat, lon, rise) {{
    var D2R = Math.PI / 180, R2D = 180 / Math.PI;
    var day = Math.floor((date - new Date(date.getFullYear(),0,0)) / 86400000);
    var lonHour = lon / 15;
    var t = rise ? day + ((6 - lonHour) / 24) : day + ((18 - lonHour) / 24);
    var M = (0.9856 * t) - 3.289;
    var L = M + (1.916 * Math.sin(M * D2R)) + (0.020 * Math.sin(2 * M * D2R)) + 282.634;
    L = ((L % 360) + 360) % 360;
    var RA = R2D * Math.atan(0.91764 * Math.tan(L * D2R));
    RA = ((RA % 360) + 360) % 360;
    var Lq = Math.floor(L / 90) * 90, RAq = Math.floor(RA / 90) * 90;
    RA = (RA + Lq - RAq) / 15;
    var sinDec = 0.39782 * Math.sin(L * D2R);
    var cosDec = Math.cos(Math.asin(sinDec));
    var cosH = (-0.01454 - (sinDec * Math.sin(lat * D2R))) / (cosDec * Math.cos(lat * D2R));
    if (cosH > 1 || cosH < -1) return null;
    var H = rise ? 360 - R2D * Math.acos(cosH) : R2D * Math.acos(cosH);
    H = H / 15;
    var T = H + RA - (0.06571 * t) - 6.622;
    var UT = T - lonHour;
    UT = ((UT % 24) + 24) % 24;
    var hrs = Math.floor(UT), mins = Math.round((UT - hrs) * 60);
    return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hrs, mins));
  }}
  function calcTwilight(date, lat, lon, rise) {{
    var D2R = Math.PI / 180, R2D = 180 / Math.PI;
    var day = Math.floor((date - new Date(date.getFullYear(),0,0)) / 86400000);
    var lonHour = lon / 15;
    var t = rise ? day + ((6 - lonHour) / 24) : day + ((18 - lonHour) / 24);
    var M = (0.9856 * t) - 3.289;
    var L = M + (1.916 * Math.sin(M * D2R)) + (0.020 * Math.sin(2 * M * D2R)) + 282.634;
    L = ((L % 360) + 360) % 360;
    var RA = R2D * Math.atan(0.91764 * Math.tan(L * D2R));
    RA = ((RA % 360) + 360) % 360;
    var Lq = Math.floor(L / 90) * 90, RAq = Math.floor(RA / 90) * 90;
    RA = (RA + Lq - RAq) / 15;
    var sinDec = 0.39782 * Math.sin(L * D2R);
    var cosDec = Math.cos(Math.asin(sinDec));
    var cosH = (-0.10453 - (sinDec * Math.sin(lat * D2R))) / (cosDec * Math.cos(lat * D2R));
    if (cosH > 1 || cosH < -1) return null;
    var H = rise ? 360 - R2D * Math.acos(cosH) : R2D * Math.acos(cosH);
    H = H / 15;
    var T = H + RA - (0.06571 * t) - 6.622;
    var UT = T - lonHour;
    UT = ((UT % 24) + 24) % 24;
    var hrs = Math.floor(UT), mins = Math.round((UT - hrs) * 60);
    return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hrs, mins));
  }}
  function fmtUTC(d) {{
    if (!d) return 'N/A';
    return d.toISOString().slice(11,16) + 'Z';
  }}
  function fmtLocal(d) {{
    if (!d) return 'N/A';
    try {{ return d.toLocaleTimeString([], {{hour:'2-digit',minute:'2-digit'}}); }} catch(e) {{ return fmtUTC(d); }}
  }}
  var today = new Date();
  var sr = calcSun(today, lat, lon, true);
  var ss = calcSun(today, lat, lon, false);
  var ct = calcTwilight(today, lat, lon, false);
  var dawn = calcTwilight(today, lat, lon, true);
  var ri = document.getElementById('sun-rise');
  var si = document.getElementById('sun-set');
  var ti = document.getElementById('sun-twilight');
  var di = document.getElementById('sun-daylen');
  if (ri) ri.textContent = sr ? fmtLocal(sr) + ' (' + fmtUTC(sr) + ')' : 'N/A';
  if (si) si.textContent = ss ? fmtLocal(ss) + ' (' + fmtUTC(ss) + ')' : 'N/A';
  if (ti) ti.textContent = ct ? 'End ' + fmtLocal(ct) : 'N/A';
  if (dawn) ti.textContent = 'Begin ' + fmtLocal(dawn) + ' / End ' + (ct ? fmtLocal(ct) : 'N/A');
  // If UTC sunset is past midnight and appears "before" sunrise, add 24h
  if (sr && ss && ss < sr) ss = new Date(ss.getTime() + 86400000);
  if (di && sr && ss) {{
    var mins = Math.round((ss - sr) / 60000);
    di.textContent = Math.floor(mins/60) + 'h ' + (mins % 60) + 'm';
  }}
}})();

async function fetchLive(url, timeout) {{
  var ctrl = new AbortController();
  var t = setTimeout(function(){{ ctrl.abort(); }}, timeout || 6000);
  try {{
    var r = await fetch(url, {{ signal: ctrl.signal, cache: 'no-store' }});
    clearTimeout(t);
    return r;
  }} catch(e) {{ clearTimeout(t); throw e; }}
}}

async function loadLiveData() {{
  var ident = window.OCL_AIRPORT;
  var base = window.OCL_API_BASE;

  // ── Weather: OCL API → aviationweather.gov → Open-Meteo ────────
  var OCL_WX_IDENT = ident; // closure

  function wxBadge(cat) {{
    if (!cat) return '';
    cat = cat.toUpperCase();
    var cls = cat === 'VFR' ? 'wx-vfr' : cat === 'MVFR' ? 'wx-mvfr' : 'wx-ifr';
    return '<span class="wx-badge ' + cls + '">' + cat + '</span> ';
  }}

  function showWindy() {{
    var w = document.getElementById('windy-wrap');
    if (w) {{ w.style.display = 'block'; w.scrollIntoView({{behavior:'smooth',block:'nearest'}}); }}
  }}

  function windyBtn() {{
    return '<p style="margin:.6rem 0 0"><button onclick="showWindy()" style="background:none;border:1px solid var(--line);border-radius:999px;padding:.28rem .75rem;font:inherit;font-size:.8rem;cursor:pointer;color:var(--muted)">🌐 Show weather map</button></p>';
  }}

  function renderOCLWeather(el, d) {{
    var metar = d.metar || null;
    var taf = d.taf || null;
    el.innerHTML = '<h3>Weather ' + wxBadge(d.flight_category) + '</h3>' +
      (metar ? '<p><strong>METAR:</strong> <code>' + metar + '</code></p>' : '') +
      (taf ? '<details style="margin:.3rem 0"><summary style="cursor:pointer;font-size:.88rem;font-weight:600">TAF</summary><p style="margin:.3rem 0"><code style="font-size:.8rem;white-space:pre-wrap">' + taf + '</code></p></details>' : '') +
      windyBtn();
  }}

  function renderAWCWeather(el, obs) {{
    var raw = obs.rawOb || '';
    var taf = obs.rawTaf || '';
    var cat = obs.flight_category || '';
    var wdir = obs.wdir, wspd = obs.wspd, wgst = obs.wgst;
    var windStr = (wdir != null && wspd != null) ? wdir + '° at ' + wspd + (wgst ? '/' + wgst : '') + ' kt' : '';
    var tempF = obs.temp != null ? Math.round(obs.temp * 9/5 + 32) + '°F' : '';
    var visib = obs.visib ? obs.visib + ' SM' : '';
    var ceiling = obs.ceiling ? obs.ceiling + ' ft AGL' : 'Clear above';
    var altim = obs.altim ? obs.altim.toFixed(2) + ' inHg' : '';
    var parts = [windStr, visib ? 'Vis: ' + visib : '', 'Ceiling: ' + ceiling, tempF, altim].filter(Boolean);
    el.innerHTML = '<h3>Weather ' + wxBadge(cat) + '<small style="font-weight:400;font-size:.72rem;color:var(--muted)"> aviationweather.gov</small></h3>' +
      (raw ? '<p><strong>METAR:</strong> <code>' + raw + '</code></p>' : '') +
      (parts.length ? '<p class="muted" style="font-size:.86rem">' + parts.join(' · ') + '</p>' : '') +
      (taf ? '<details style="margin:.3rem 0"><summary style="cursor:pointer;font-size:.88rem;font-weight:600">TAF</summary><p style="margin:.3rem 0"><code style="font-size:.8rem;white-space:pre-wrap">' + taf + '</code></p></details>' : '') +
      windyBtn();
  }}

  var WMO = {{0:'Clear sky',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',
    45:'Fog',48:'Freezing fog',51:'Light drizzle',53:'Drizzle',55:'Heavy drizzle',
    61:'Light rain',63:'Rain',65:'Heavy rain',71:'Light snow',73:'Snow',75:'Heavy snow',
    77:'Snow grains',80:'Light showers',81:'Showers',82:'Heavy showers',
    95:'Thunderstorm',96:'T-storm + hail',99:'T-storm + heavy hail'}};

  function renderOpenMeteo(el, c) {{
    var desc = WMO[c.weather_code] || 'Unknown';
    var wspd = Math.round(c.wind_speed_10m || 0);
    var wgst = c.wind_gusts_10m ? Math.round(c.wind_gusts_10m) : null;
    var wdir = c.wind_direction_10m || 0;
    var tempF = c.temperature_2m != null ? Math.round(c.temperature_2m) + '°F' : '';
    var rhum = c.relative_humidity_2m ? c.relative_humidity_2m + '% RH' : '';
    var windStr = wdir + '° at ' + wspd + (wgst ? '/' + wgst : '') + ' kt';
    var cards = [
      ['Conditions', desc],
      ['Wind', windStr],
      tempF ? ['Temp', tempF] : null,
      rhum ? ['Humidity', rhum] : null,
    ].filter(Boolean).map(function(p){{
      return '<div class="fact-card"><div class="lbl">' + p[0] + '</div><div class="val" style="font-size:.9rem">' + p[1] + '</div></div>';
    }}).join('');
    el.innerHTML = '<h3>Conditions <small style="font-weight:400;font-size:.72rem;color:var(--muted)"> Open-Meteo · no METAR at this airport</small></h3>' +
      '<div class="fact-grid" style="margin:.4rem 0 .5rem">' + cards + '</div>' +
      '<p class="muted" style="font-size:.75rem;margin:.1rem 0">Forecast model only — not a certified METAR. <a href="https://aviationweather.gov/metar?ids=' + OCL_WX_IDENT + '" target="_blank" rel="noopener">Check nearest METAR ↗</a></p>' +
      windyBtn();
  }}

  async function loadWeather() {{
    var el = document.getElementById('weather');
    var LAT = window.OCL_LAT, LON = window.OCL_LON;

    // 1 — OCL API
    try {{
      var r1 = await fetchLive(base + ident + '/weather', 5000);
      var d1 = await r1.json();
      if (!d1.error && (d1.metar || d1.taf)) {{ renderOCLWeather(el, d1); return; }}
    }} catch(e) {{}}

    // 2 — Open-Meteo (airports with no METAR station)
    if (LAT && LON) {{
      try {{
        var omUrl = 'https://api.open-meteo.com/v1/forecast?latitude=' + LAT + '&longitude=' + LON +
          '&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation' +
          '&wind_speed_unit=kn&temperature_unit=fahrenheit&forecast_days=1';
        var r3 = await fetchLive(omUrl, 8000);
        var d3 = await r3.json();
        if (d3 && d3.current) {{ renderOpenMeteo(el, d3.current); return; }}
      }} catch(e) {{}}
    }}

    // All sources failed
    el.innerHTML = '<h3>Weather</h3><p class="muted">Weather unavailable. ' +
      '<a href="https://aviationweather.gov" target="_blank" rel="noopener">Check aviationweather.gov →</a></p>' +
      windyBtn();
  }}

  loadWeather();

  // NOTAMs
  try {{
    var r2 = await fetchLive(base + ident + '/notams');
    var d2 = await r2.json();
    var el2 = document.getElementById('notams');
    if (d2.error) {{
      el2.innerHTML = '<h3>NOTAMs</h3><p class="muted">NOTAMs unavailable for this airport. <a href="https://notams.faa.gov/notamSearch/search" target="_blank" rel="noopener">Check FAA NOTAM search</a></p>';
    }} else if (d2.notams && d2.notams.length > 0) {{
      var items = d2.notams.map(function(n){{ return '<li style="margin:.35rem 0;font-size:.88rem">' + (n.text || n) + '</li>'; }}).join('');
      el2.innerHTML = '<h3>NOTAMs (' + d2.notams.length + ')</h3><ul style="padding-left:1.2rem;margin:.4rem 0">' + items + '</ul>';
    }} else {{
      el2.innerHTML = '<h3>NOTAMs</h3><p style="color:var(--ok)">✓ No active NOTAMs.</p>';
    }}
  }} catch(e) {{
    document.getElementById('notams').innerHTML = '<h3>NOTAMs</h3><p>Unable to load. <a href="https://notams.faa.gov/notamSearch/search" target="_blank">Check FAA NOTAM search</a></p>';
  }}

  // Fuel
  try {{
    var r3 = await fetchLive(base + ident + '/fuel');
    var d3 = await r3.json();
    var el3 = document.getElementById('fuel');
    if (d3.error) {{
      el3.innerHTML = '<h3>Fuel &amp; FBO</h3><p class="muted">No fuel data on record for this airport.</p>';
    }} else {{
      var fuels = (d3.fuel_types || []).join(', ') || 'None listed';
      var fbo = d3.fbo_name ? '<br><strong>FBO:</strong> ' + d3.fbo_name : '';
      el3.innerHTML = '<h3>Fuel &amp; FBO</h3><p><strong>Available:</strong> ' + fuels + fbo + '</p>';
    }}
  }} catch(e) {{
    document.getElementById('fuel').innerHTML = '<h3>Fuel &amp; FBO</h3><p>Unable to load fuel data.</p>';
  }}

  // Winds aloft — Open-Meteo pressure-level winds (JSON, no CORS, lat/lon)
  var elw = document.getElementById('winds-aloft');
  var WLAT = window.OCL_LAT, WLON = window.OCL_LON;
  if (WLAT && WLON) {{
    try {{
      var wUrl = 'https://api.open-meteo.com/v1/forecast?latitude=' + WLAT + '&longitude=' + WLON +
        '&hourly=wind_speed_925hPa,wind_direction_925hPa,wind_speed_850hPa,wind_direction_850hPa,wind_speed_700hPa,wind_direction_700hPa,temperature_850hPa,temperature_700hPa' +
        '&wind_speed_unit=kn&temperature_unit=fahrenheit&forecast_days=1&timezone=auto';
      var rw = await fetchLive(wUrl, 10000);
      var dw = await rw.json();
      if (dw && dw.hourly) {{
        var h = dw.hourly;
        var now = new Date();
        var hi = Math.min(now.getHours(), (h.wind_speed_925hPa || []).length - 1);
        function wrow(alt, spd, dir, temp) {{
          if (spd == null) return '';
          var kts = Math.round(spd);
          var dirS = dir != null ? Math.round(dir) + '°' : '—';
          var tempS = temp != null ? ' / ' + Math.round(temp) + '°F' : '';
          return '<tr><td>' + alt + '</td><td>' + dirS + ' @ ' + kts + ' kt' + tempS + '</td></tr>';
        }}
        var rows =
          wrow('~3,000 ft (925hPa)', h.wind_speed_925hPa[hi], h.wind_direction_925hPa[hi], null) +
          wrow('~5,000 ft (850hPa)', h.wind_speed_850hPa[hi], h.wind_direction_850hPa[hi], h.temperature_850hPa ? h.temperature_850hPa[hi] : null) +
          wrow('~10,000 ft (700hPa)', h.wind_speed_700hPa[hi], h.wind_direction_700hPa[hi], h.temperature_700hPa ? h.temperature_700hPa[hi] : null);
        if (rows) {{
          elw.innerHTML = '<h3>Winds Aloft <small style="font-weight:400;font-size:.72rem;color:var(--muted)"> Open-Meteo forecast model</small></h3>' +
            '<table style="font-size:.86rem"><thead><tr><th>Altitude</th><th>Wind / Temp</th></tr></thead><tbody>' + rows + '</tbody></table>';
        }} else {{
          elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">No winds aloft data.</p>';
        }}
      }} else {{
        elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">Winds aloft data unavailable.</p>';
      }}
    }} catch(e) {{
      elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">Winds aloft unavailable.</p>';
    }}
  }} else {{
    if (elw) elw.innerHTML = '<h3>Winds Aloft</h3><p class="muted">No coordinates for this airport.</p>';
  }}

  // PIREPs
  try {{
    var rp = await fetchLive('https://app.openchecklists.net/api/proxy/pirep/' + ident, 8000);
    var dp = await rp.json();
    var elp = document.getElementById('pireps');
    if (dp && Array.isArray(dp) && dp.length > 0) {{
      var recent = dp.slice(0, 5);
      var items = recent.map(function(p) {{
        var alt = p.altitude ? p.altitude + ' ft' : '';
        var sky = p.skyCondition || '';
        var turb = p.turbulence ? ' · Turb: ' + p.turbulence : '';
        var ice = p.icing ? ' · Ice: ' + p.icing : '';
        var loc = p.location || p.icaoId || '';
        return '<li style="margin:.35rem 0;font-size:.85rem"><strong>' + (alt || loc) + '</strong>' + turb + ice + (sky ? ' · ' + sky : '') + '</li>';
      }}).join('');
      elp.innerHTML = '<h3>PIREPs — nearby pilot reports (' + dp.length + ')</h3><ul style="padding-left:1.2rem;margin:.3rem 0">' + items + '</ul>';
    }} else {{
      elp.innerHTML = '<h3>PIREPs</h3><p class="muted">No recent pilot reports within 50 nm.</p>';
    }}
  }} catch(e) {{
    document.getElementById('pireps').innerHTML = '<h3>PIREPs</h3><p class="muted">Pilot reports unavailable.</p>';
  }}
}}

setTimeout(loadLiveData, 400);
</script>
</main>
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
<p>Data effective {effective_date}. Source: FAA NASR 28-day cycle.</p>
</div></footer>
<script>
if ('serviceWorker' in navigator) {{
  navigator.serviceWorker.register('/sw.js').catch(function(){{}});
}}
</script>
</body>
</html>
"""
    return html


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, default=REPO / "examples")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--base-url", default="")
    ap.add_argument("--wx-proxy", default="", help="URL of the deployed weather Worker")
    ap.add_argument("--data", type=Path, default=REPO / "data",
                    help="ingested datasets (airports); pages degrade if absent")
    args = ap.parse_args()

    paths = sorted(args.corpus.glob("*.ocl.json"))
    if not paths:
        raise SystemExit(f"no *.ocl.json under {args.corpus}")

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    (args.out / "api" / "checklists").mkdir(parents=True)

    entries: list[dict] = []
    docs: dict[str, dict] = {}
    violations = 0
    artifacts: list[Path] = []

    for p in paths:
        doc = json.loads(p.read_text())
        docs[doc["id"]] = doc
        e = entry(doc, p)
        cid = doc["id"]
        cdir = args.out / "c" / cid
        cdir.mkdir(parents=True)

        quar = is_quarantined(doc)
        # Quarantine rule: state travels in the filename, because the filename is
        # what survives being emailed, printed, and found on a hangar computer.
        stem = f"{cid}.UNREVIEWED" if quar else cid

        for fmt in FORMATS:
            if fmt == "html":
                continue  # the page itself is the HTML artifact
            blob = export(doc, fmt)
            issues = verify_export(doc, fmt, blob)
            for msg in issues:
                print(f"  CONTRACT VIOLATION: {cid}: {msg}")
            violations += len(issues)
            out = cdir / f"{stem}.{EXT[fmt]}"
            out.write_bytes(blob)
            artifacts.append(out)
            e["downloads"][fmt] = f"c/{cid}/{out.name}"

        page = cdir / "index.html"
        page.write_text(render_html(doc, "letter", site_rel="../../"), encoding="utf-8")
        artifacts.append(page)

        api = args.out / "api" / "checklists" / f"{cid}.json"
        api.write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode())
        artifacts.append(api)

        entries.append(e)

    catalogue = {
        "openchecklists_catalogue_version": "1.0",
        "schema": "schema/open-checklist-1.0.schema.json",
        "base_url": args.base_url,
        "count": len(entries),
        "reviewed_count": sum(1 for e in entries if not e["verification"]["quarantined"]),
        "notice": (
            "Nothing in this catalogue is approved data. Every entry records its source and "
            "verification state. Schema validity is necessary but not sufficient: the corpus "
            "policy rules are enforced separately and the verification fields should not be "
            "trusted for files obtained outside this catalogue."
        ),
        "checklists": entries,
    }

    (args.out / "api" / "index.json").write_bytes(
        (json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n").encode()
    )
    artifacts.append(args.out / "api" / "index.json")

    def page(name: str, title: str, desc: str, body: str) -> Path:
        out = args.out / name
        out.write_text(head(title, desc) + body + FOOT, encoding="utf-8")
        return out

    (args.out / "catalogue.html").write_text(build_index(entries, catalogue), encoding="utf-8")
    static_pages = [
        args.out / "catalogue.html",
        page("index.html", f"{BRAND_NAME} — {TAGLINE}",
             "A free library of aircraft checklists as structured data: read on a phone, "
             "print at any size, load into your own software, fork and modify.",
             landing_body()),
        page("about.html", f"How to read a file — {BRAND_NAME}",
             "What the verification states mean and why flown-behind-it is not the top one.",
             ABOUT),
        page("contribute.html", f"Contribute a checklist — {BRAND_NAME}",
             "How to add a checklist for your aircraft, and the contributor warranty.",
             contribute_body()),
        page("privacy.html", f"Privacy — {BRAND_NAME}",
             "This site collects nothing: no analytics, no cookies, no accounts.",
             PRIVACY),
        page("terms.html", f"Terms of use — {BRAND_NAME}",
             "Safety notice, no warranty, per-file licensing, acceptable use.",
             TERMS),
        page("takedown.html", f"Takedown and corrections — {BRAND_NAME}",
             "How rights claims and error reports are handled.",
             TAKEDOWN),
        page("contact.html", f"Contact — {BRAND_NAME}", "How to reach the project.", CONTACT),
    ]

    # Airports, frequencies and weather. The page is always generated; it explains
    # itself if the NASR ingest has not been run, rather than failing the build.
    (args.out / "airports.html").write_text(
        airports_page(head, FOOT, args.wx_proxy), encoding="utf-8"
    )
    (args.out / "search.html").write_text(library_page(head, FOOT), encoding="utf-8")
    (args.out / "training.html").write_text(training_page(head, FOOT), encoding="utf-8")
    static_pages += [
        args.out / "airports.html",
        args.out / "search.html",
        args.out / "training.html",
        page("projects.html", f"Open source aircraft projects — {BRAND_NAME}",
             "Open source aviation projects that produce or consume these formats: "
             "Open Checklists, the Junco flight computer, and an open flight simulator.",
             PROJECTS),
        page("charts.html", f"Charts and plates — {BRAND_NAME}",
             "Where to get official FAA charts, plates and airport diagrams, and why this "
             "project links to them rather than republishing them.",
             CHARTS),
    ]

    training_data = args.data / "training"
    if (training_data / "certificates.json").exists():
        shutil.copytree(training_data, args.out / "data" / "training")
        artifacts.append(args.out / "data" / "training" / "certificates.json")

    library_data = args.data / "library"
    library_shipped = 0
    if (library_data / "meta.json").exists():
        shutil.copytree(library_data, args.out / "data" / "library")
        library_shipped = json.loads((library_data / "meta.json").read_text())["counts"]["passages"]
        for f in sorted((args.out / "data" / "library").rglob("*.json")):
            artifacts.append(f)

    airport_data = args.data / "airports"
    airports_shipped = 0
    airports_built = 0
    if (airport_data / "index.json").exists():
        dest = args.out / "data" / "airports"
        shutil.copytree(airport_data, dest)
        airports_shipped = len(json.loads((airport_data / "index.json").read_text()))
        for f in sorted(dest.rglob("*.json")):
            artifacts.append(f)

        # One client-rendered template serves every /airport/<id>/ URL. We used
        # to pre-render ~19,000 static pages here, but that blew past Cloudflare
        # Pages' 20,000-file deploy limit. The template reads the same NASR
        # detail shards (shipped above to /data/airports/detail/) in the browser,
        # so the page is identical while the deploy stays tiny. A _redirects
        # rewrite (written below) maps /airport/<id>/ onto this file.
        from site_airport_app import airport_app_page  # noqa: E402

        cycle_path = airport_data / "cycle.json"
        effective_date = "current cycle"
        if cycle_path.exists():
            try:
                effective_date = json.loads(cycle_path.read_text()).get("effective") or "current cycle"
            except (ValueError, OSError):
                effective_date = "current cycle"

        out_dir = args.out / "airport"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            airport_app_page(head, effective_date), encoding="utf-8"
        )
        artifacts.append(out_dir / "index.html")
        airports_built = 1
        print(f"  airport template: 1 client-rendered page for {airports_shipped:,} airports")

    # Hero and OG images
    for img_name in ("hero.png", "hero.svg", "og-image.png", "planner-hero.jpg"):
        src = REPO / "assets" / img_name
        if src.exists():
            import shutil as _sh
            _sh.copy2(src, args.out / img_name)
            artifacts.append(args.out / img_name)

    # Per-airport detail page (client-side template, bookmarkable by ?id=ICAO)
    (args.out / "airport.html").write_text(
        airport_detail_page(head, FOOT, args.wx_proxy), encoding="utf-8"
    )
    static_pages.append(args.out / "airport.html")

    # The weather Worker ships with the site so it is deployable without hunting
    # for it, and so the reason it exists travels with the code.
    (args.out / "worker").mkdir(exist_ok=True)
    (args.out / "worker" / "weather-proxy.js").write_text(WEATHER_WORKER, encoding="utf-8")
    artifacts.append(args.out / "worker" / "weather-proxy.js")

    # Auth + profile pages. These are hand-written (not templated) because they carry
    # the Zitadel PKCE flow and talk to the ocl-api Worker at api.openchecklists.net.
    # They live under worker/ocl-api/ next to the API they call; copy them into the
    # build so a rebuild does not drop them (build/site is wiped on every run).
    ocl_api = REPO / "worker" / "ocl-api"
    profile_src = ocl_api / "profile.html"
    if profile_src.exists():
        import shutil as _sh
        _sh.copy2(profile_src, args.out / "profile.html")
        artifacts.append(args.out / "profile.html")
    callback_src = ocl_api / "auth-callback.html"
    if callback_src.exists():
        import shutil as _sh
        (args.out / "auth").mkdir(exist_ok=True)
        _sh.copy2(callback_src, args.out / "auth" / "callback.html")
        artifacts.append(args.out / "auth" / "callback.html")
    planner_src = ocl_api / "planner.html"
    if planner_src.exists():
        shutil.copy2(planner_src, args.out / "planner.html")
        artifacts.append(args.out / "planner.html")
    plan_src = ocl_api / "plan-detail.html"
    if plan_src.exists():
        plan_dir = args.out / "plan"
        plan_dir.mkdir(exist_ok=True)
        shutil.copy2(plan_src, plan_dir / "index.html")
        artifacts.append(plan_dir / "index.html")
    # Community-checklist viewer. One client-rendered template serves every
    # /checklist/?id=<id> URL — it reads the checklist from the ocl-api Worker in
    # the browser, so community-published checklists (which the catalogue links to
    # here) have a real page without pre-rendering anything at build time.
    from site_checklist_view import checklist_view_page  # noqa: E402

    (args.out / "checklist").mkdir(parents=True, exist_ok=True)
    (args.out / "checklist" / "index.html").write_text(
        checklist_view_page(head, FOOT), encoding="utf-8"
    )
    static_pages.append(args.out / "checklist" / "index.html")

    (args.out / "editor.html").write_text(editor_page(head, FOOT, catalogue), encoding="utf-8")
    artifacts += static_pages + [args.out / "editor.html"]

    # PWA: installable on a phone, and cached so it works at the aircraft with no
    # signal. The corpus is small and static, so precaching the shell is enough.
    (args.out / "icon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    (args.out / "manifest.webmanifest").write_text(
        json.dumps(
            {
                "name": BRAND_NAME,
                "short_name": "Checklists",
                "description": TAGLINE,
                "start_url": "index.html",
                "scope": ".",
                "display": "standalone",
                "orientation": "portrait",
                "background_color": "#ffffff",
                "theme_color": "#1f4e79",
                "icons": [
                    {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
                    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for png in ("icon-192.png", "icon-512.png"):
        src = REPO / "assets" / png
        if src.exists():
            shutil.copy(src, args.out / png)
            artifacts.append(args.out / png)

    # Path-segment rewrites (best effort). NOTE: this Pages project has SPA
    # not-found handling that serves the root index.html for unmatched paths,
    # and it currently wins over these rewrites — so airport links use the
    # query form /airport/?id=<IDENT> (a real directory index that needs no
    # rewrite). These lines are kept so pretty URLs work if the project's
    # not-found handling is ever changed.
    (args.out / "_redirects").write_text(
        "/plan/* /plan/index.html 200\n"
        "/airport/* /airport/index.html 200\n",
        encoding="utf-8",
    )

    precache = (
        ["index.html", "catalogue.html", "editor.html", "about.html", "contribute.html",
         "privacy.html", "terms.html", "takedown.html", "contact.html", "airports.html",
         "search.html", "charts.html", "projects.html", "training.html",
         "manifest.webmanifest", "icon.svg", "api/index.json"]
        + (["data/airports/index.json", "data/airports/cycle.json", "data/airports/icao.json"]
           if airports_shipped else [])
        + [f"c/{e['id']}/" for e in entries]
        + [f"api/checklists/{e['id']}.json" for e in entries]
    )
    # Cache name is a content hash of the precache list + the shell pages, so a
    # new deploy always gets a fresh cache and never serves a stale shell.
    # (Live weather is cross-origin and never SW-cached; this covers the app HTML.)
    import hashlib as _hashlib
    _cache_src = json.dumps(precache, sort_keys=True).encode() + SW_BODY.encode()
    for _shell in ("index.html", "catalogue.html", "airports.html", "training.html",
                   "planner.html", "airport/index.html"):
        _sp = args.out / _shell
        if _sp.exists():
            _cache_src += _sp.read_bytes()
    _cache_ver = _hashlib.sha256(_cache_src).hexdigest()[:12]
    (args.out / "sw.js").write_text(
        SW_HEADER + f"const CACHE = 'ocl-{_cache_ver}';\n"
        + "const ASSETS = " + json.dumps(precache) + ";\n"
        + SW_BODY,
        encoding="utf-8",
    )
    artifacts += [args.out / "sw.js", args.out / "manifest.webmanifest", args.out / "icon.svg"]

    # Family pages: every variation of one airframe, with each fork's diff inline.
    families: dict[str, list[dict]] = {}
    for e in entries:
        fam = e.get("airframe_family")
        if fam:
            families.setdefault(fam, []).append(e)
    for fam, members in sorted(families.items()):
        fdir = args.out / "f" / fam
        fdir.mkdir(parents=True, exist_ok=True)
        fpage = fdir / "index.html"
        fpage.write_text(family_page(fam, members, docs), encoding="utf-8")
        artifacts.append(fpage)
    catalogue["families"] = {
        fam: {"count": len(ms), "page": f"f/{fam}/", "checklists": [m["id"] for m in ms]}
        for fam, ms in sorted(families.items())
    }
    # Rewrite the catalogue now that family links exist.
    (args.out / "api" / "index.json").write_bytes(
        (json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n").encode()
    )
    (args.out / "catalogue.html").write_text(build_index(entries, catalogue), encoding="utf-8")

    # Bundle listings, kept apart so a consumer cannot pick up unreviewed content
    # by accident.
    rev = [e for e in entries if not e["verification"]["quarantined"]]
    unrev = [e for e in entries if e["verification"]["quarantined"]]
    (args.out / "reviewed.txt").write_text(
        "".join(f"api/checklists/{e['id']}.json\n" for e in rev) or "# none yet\n"
    )
    (args.out / "unreviewed.txt").write_text(
        "# Nobody has checked these against a source document. Not for flight.\n"
        + "".join(f"api/checklists/{e['id']}.json\n" for e in unrev)
    )
    (args.out / "robots.txt").write_text("User-agent: *\nAllow: /\n")

    base = args.base_url.rstrip("/")
    urls = [
        "", "catalogue.html", "editor.html", "about.html", "contribute.html",
        "privacy.html", "terms.html", "takedown.html", "contact.html", "airports.html",
        "search.html", "charts.html", "projects.html", "training.html",
    ] + [f"f/{fam}/" for fam in sorted(families)] + [f"c/{e['id']}/" for e in entries]
    (args.out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{base}/{u}</loc></url>\n" for u in urls)
        + "</urlset>\n"
    )
    artifacts += [args.out / "reviewed.txt", args.out / "unreviewed.txt", args.out / "sitemap.xml"]

    lines = []
    for a in sorted(artifacts):
        lines.append(f"{hashlib.sha256(a.read_bytes()).hexdigest()}  {a.relative_to(args.out)}")
    (args.out / "manifest.sha256").write_text("\n".join(lines) + "\n")

    total = sum(1 for _ in args.out.rglob("*") if _.is_file())
    try:
        out_rel = args.out.relative_to(REPO)
    except ValueError:
        out_rel = args.out
    print(f"built {out_rel}: {len(entries)} checklists, {total} files")
    print(f"  reviewed: {len(rev)}   quarantined: {len(unrev)}")
    print(f"  library passages: {library_shipped:,}"
          + ("" if library_shipped else "  (run tools/library.py ingest)"))
    print(f"  airports shipped: {airports_shipped:,}"
          + ("" if airports_shipped else "  (run tools/airports.py ingest)"))
    if airports_built:
        print(f"  airport pages built: {airports_built:,}")
    print(f"  {violations} export contract violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
