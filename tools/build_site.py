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
import shutil
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export import EXT, FORMATS, export, is_quarantined, state_line, verify_export  # noqa: E402
from render import render as render_html  # noqa: E402
from site_editor import editor_page  # noqa: E402
from site_pages import (  # noqa: E402
    BRAND_NAME, CONTACT, FAVICON_SVG, LOGO_SVG, PRIVACY, TAGLINE, TAKEDOWN, TERMS,
    contribute_body, landing_body,
)
from diff import diff as semantic_diff, render_markdown as diff_markdown  # noqa: E402
from validate import content_hash  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "build" / "site"

CSS = """
:root{--bg:#fff;--fg:#14161a;--muted:#5f6368;--line:#dcdfe4;--card:#f7f8fa;
--accent:#1f4e79;--warn:#b3261e;--ok:#1b5e20;--caut:#8a5a00}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#14161a;--fg:#e9eaec;--muted:#9aa0a6;--line:#2f333a;--card:#1c1f24;
--accent:#90caf9;--warn:#ff8a80;--ok:#a5d6a7;--caut:#ffcc80}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
-webkit-text-size-adjust:100%}
a{color:var(--accent)}
.wrap{max-width:56rem;margin:0 auto;padding:1.25rem}
header.site{border-bottom:1px solid var(--line);margin-bottom:1.25rem}
header.site .wrap{padding-bottom:.75rem}
h1{font-size:1.5rem;margin:.3rem 0}
.tag{font-size:.8rem;color:var(--muted)}
.lede{color:var(--muted);max-width:44rem}
.controls{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0;align-items:center}
input[type=search],select{font:inherit;padding:.45rem .6rem;border:1px solid var(--line);
border-radius:.35rem;background:var(--bg);color:var(--fg)}
input[type=search]{flex:1;min-width:12rem}
.count{color:var(--muted);font-size:.85rem;font-variant-numeric:tabular-nums}
ul.cards{list-style:none;padding:0;margin:0;display:grid;gap:.75rem}
li.card{border:1px solid var(--line);border-radius:.5rem;padding:.85rem 1rem;background:var(--card)}
li.card h2{font-size:1.05rem;margin:0 0 .2rem}
li.card h2 a{text-decoration:none}
.meta{font-size:.82rem;color:var(--muted);display:flex;gap:.5rem;flex-wrap:wrap}
.meta span{white-space:nowrap}
.badge{display:inline-block;font-size:.7rem;font-weight:700;letter-spacing:.03em;
border:1px solid currentColor;border-radius:.25rem;padding:.05rem .35rem;margin-right:.35rem}
.badge.quar{color:var(--warn)}
.badge.ok{color:var(--ok)}
.badge.part{color:var(--caut)}
.dl{margin-top:.5rem;font-size:.82rem}
.dl a{margin-right:.5rem;white-space:nowrap}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:1rem 0}
th,td{text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
code{font-size:.85em;background:var(--card);padding:.1em .3em;border-radius:.2rem}
.banner{border:2px solid;border-radius:.4rem;padding:.7rem .85rem;margin:1rem 0;font-size:.9rem}
.banner.quar{border-color:var(--warn);color:var(--warn)}
.banner.okb{border-color:var(--ok);color:var(--ok)}
footer.site{border-top:1px solid var(--line);margin-top:2.5rem;padding:1rem 0 3rem;
font-size:.82rem;color:var(--muted)}
.scroll{overflow-x:auto}
.brand{display:inline-flex;align-items:center;gap:.5rem;text-decoration:none;color:inherit;
margin:.4rem 0 .1rem}
.brand .logo{width:1.7rem;height:1.7rem;color:var(--accent);flex:none}
.brand .bn{font-size:1.35rem;font-weight:700;letter-spacing:-.01em}
.brandtag{margin:.1rem 0 .4rem}
.nav{display:flex;gap:.9rem;flex-wrap:wrap;font-size:.86rem;padding-bottom:.2rem}
.fnav{line-height:2}
.hero{padding:1rem 0 1.5rem;border-bottom:1px solid var(--line);margin-bottom:1.5rem}
.hero-h{font-size:1.9rem;line-height:1.15;margin:.2rem 0 .6rem;max-width:32rem}
.hero-p{font-size:1.05rem;color:var(--fg);max-width:40rem}
.hero-cta{display:flex;gap:.6rem;flex-wrap:wrap;margin:1.2rem 0 .6rem}
.cta{display:inline-block;padding:.6rem 1.1rem;border-radius:.4rem;background:var(--accent);
color:#fff;text-decoration:none;font-weight:600}
.cta.ghost{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.grid3{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));margin:1.5rem 0}
.feat{border:1px solid var(--line);border-radius:.5rem;padding:.9rem 1rem;background:var(--card)}
.feat h3{margin:.1rem 0 .4rem;font-size:1rem}
.feat p{margin:0;font-size:.9rem;color:var(--muted)}
h2{font-size:1.25rem;margin-top:1.8rem}
h3{font-size:1rem;margin-top:1.2rem}
h4{font-size:.9rem;margin-top:1rem}
ol,ul{padding-left:1.3rem}
li{margin:.25rem 0}
blockquote{margin:.6rem 0;padding:.5rem .8rem;border-left:3px solid var(--line);color:var(--muted)}
"""


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
<header class="site"><div class="wrap">
<a class="brand" href="{rel}index.html">{LOGO_SVG}<span class="bn">{BRAND_NAME}</span></a>
<p class="tag brandtag">{TAGLINE}</p>
<nav class="nav">
<a href="{rel}catalogue.html">Catalogue</a>
<a href="{rel}editor.html">Editor</a>
<a href="{rel}contribute.html">Contribute</a>
<a href="{rel}about.html">How to read a file</a>
</nav>
</div></header>
<div class="wrap">
"""


FOOT = """</div>
<footer class="site"><div class="wrap">
<p><strong>Nothing here is approved data.</strong> Every file records its source and its
verification state. Verify against your aircraft's own approved documentation before
flight. No warranty of any kind &mdash; see <a href="terms.html">terms</a>.</p>
<p class="fnav">
<a href="index.html">Home</a> &middot;
<a href="catalogue.html">Catalogue</a> &middot;
<a href="editor.html">Editor</a> &middot;
<a href="contribute.html">Contribute</a> &middot;
<a href="about.html">Verification states</a> &middot;
<a href="api/index.json">API</a> &middot;
<a href="manifest.sha256">Manifest</a> &middot;
<a href="privacy.html">Privacy</a> &middot;
<a href="terms.html">Terms</a> &middot;
<a href="takedown.html">Takedown</a> &middot;
<a href="contact.html">Contact</a></p>
<p>Corpus rights are recorded per file. This site collects nothing: no analytics, no
cookies, no accounts. Your saved checklists stay in your browser.</p>
</div></footer>
<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(function(){ /* offline is a bonus */ });
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

  function card(e){
    var dl = Object.keys(e.downloads).map(function(f){
      return '<a href="' + e.downloads[f] + '">' + f + '</a>';
    }).join('');
    var badge = e.verification.quarantined
      ? '<span class="badge quar">NOT REVIEWED</span>'
      : '<span class="badge ok">REVIEWED</span>';
    if (e.verification.completeness && e.verification.completeness !== 'full') {
      badge += '<span class="badge part">' +
        e.verification.completeness.replace(/_/g,' ').toUpperCase() + '</span>';
    }
    var ac = [e.aircraft.make, e.aircraft.model, e.aircraft.variant].filter(Boolean).join(' ');
    return '<li class="card"><h2><a href="' + e.page + '">' + e.title + '</a></h2>' +
      '<div class="meta">' + badge +
      '<span>' + ac + '</span>' +
      '<span>' + (e.aircraft.category||'').replace(/_/g,' ') + '</span>' +
      '<span>' + e.tickable_items + ' items</span>' +
      (e.memory_items ? '<span>' + e.memory_items + ' memory</span>' : '') +
      '<span>' + (e.rights.license || e.rights.status) + '</span>' +
      (e.registration ? '<span>' + e.registration + '</span>' : '') +
      '</div>' + fam(e) + '<div class="dl">' + dl + '</div></li>';
  }

  function apply(){
    var s = q.value.toLowerCase().trim();
    var c = cat.value, vf = ver.value;
    var out = data.checklists.filter(function(e){
      if (c && e.aircraft.category !== c) return false;
      if (vf === 'reviewed' && e.verification.quarantined) return false;
      if (vf === 'unreviewed' && !e.verification.quarantined) return false;
      if (!s) return true;
      var hay = [e.title, e.aircraft.make, e.aircraft.model, e.aircraft.variant,
                 e.aircraft.icao_type, e.aircraft.category, e.source.title,
                 e.engine_type, e.airframe_family, e.registration,
                 (e.modifications||[]).map(function(m){ return m.kind + ' ' + m.description; }).join(' ')
                ].join(' ').toLowerCase();
      return hay.indexOf(s) !== -1;
    });
    list.innerHTML = out.map(card).join('') ||
      '<li class="card">Nothing matches. Try a make, a model, or a category.</li>';
    count.textContent = out.length + ' of ' + data.checklists.length;
  }

  [q, cat, ver].forEach(function(el){ el.addEventListener('input', apply); });
  apply();
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, default=REPO / "examples")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--base-url", default="")
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

    precache = (
        ["index.html", "catalogue.html", "editor.html", "about.html", "contribute.html",
         "privacy.html", "terms.html", "takedown.html", "contact.html",
         "manifest.webmanifest", "icon.svg", "api/index.json"]
        + [f"c/{e['id']}/" for e in entries]
        + [f"api/checklists/{e['id']}.json" for e in entries]
    )
    (args.out / "sw.js").write_text(
        SW_HEADER + f"const CACHE = 'ocl-v1-{len(entries)}';\n"
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
        "privacy.html", "terms.html", "takedown.html", "contact.html",
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
    print(f"built {args.out.relative_to(REPO)}: {len(entries)} checklists, {total} files")
    print(f"  reviewed: {len(rev)}   quarantined: {len(unrev)}")
    print(f"  {violations} export contract violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
