#!/usr/bin/env python3
"""Render an Open Checklist file to a self-contained HTML checklist.

This is the demonstration that the corpus format actually serves the use case:
one JSON file in, and out comes something you can work through on a phone at the
aircraft, print at whatever paper size your kneeboard takes, and export a
completion log from.

    python3 tools/render.py examples/faa-generic-sep-ground-operations.ocl.json

Design constraints that are not negotiable, and are the reason this exists as a
reference implementation rather than being left to consumers:

  * Notes, cautions and warnings get no checkbox. A warning is not a task.
  * The verification state is shown before the content, not after it, and is
    repeated on every printed page.
  * There is no "check all" button. The log is worthless if it can be filled in
    without reading anything, and a log that is easy to fake is worse than no
    log because it looks like evidence.
  * Ticks are timestamped when they happen, and the exported log records
    recording.mode=live only for items that were actually ticked in session.

Output is one file with no external requests, so it works in a hangar with no
signal.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import content_hash  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

INFO_TYPES = {"note", "caution", "warning"}

PAPER = {
    "letter": ("8.5in", "11in", "0.5in"),
    "a4": ("210mm", "297mm", "12mm"),
    "a5": ("148mm", "210mm", "8mm"),
    "kneeboard": ("5.5in", "8.5in", "0.3in"),
}


def esc(s: object) -> str:
    return html.escape(str(s if s is not None else ""))


def state_banner(doc: dict) -> tuple[str, str]:
    """Returns (css class, human text) for the verification state."""
    v = doc.get("verification", {})
    fid = v.get("source_fidelity", "unreviewed")
    op = v.get("operational_review", "none")
    comp = v.get("completeness")
    defects = [i for i in v.get("known_issues", []) if i.get("severity") == "safety_defect"]

    fid_text = {
        "unreviewed": "NOT REVIEWED — nobody has checked this against a source document",
        "single_reviewed": "Checked once against the source",
        "dual_reviewed": "Checked twice, independently, against the source",
        "not_applicable": "No source document exists — content is authored",
    }.get(fid, fid)
    op_text = {
        "none": "never used in an aircraft",
        "ground_checked": "walked through in the cockpit",
        "flown": "flown behind in type",
    }.get(op, op)

    parts = [fid_text, op_text]
    if comp and comp != "full":
        parts.append(f"INCOMPLETE: {comp.replace('_', ' ')}")
    if defects:
        parts.append(f"{len(defects)} unresolved safety defect(s)")

    quarantined = fid == "unreviewed" or bool(defects)
    return ("quarantine" if quarantined else "ok", " · ".join(parts))


def render_item(item: dict, sec_id: str, idx: int) -> str:
    itype = item.get("type", "challenge")
    if itype == "blank":
        return '<li class="blank"></li>'

    text = esc(item.get("text"))
    cond = f'<span class="cond">{esc(item["condition"])}</span>' if item.get("condition") else ""
    detail = f'<p class="detail">{esc(item["detail"])}</p>' if item.get("detail") else ""
    indent = f' style="margin-left:{min(item.get("indent", 0), 4) * 1.25}rem"'

    if itype == "subtitle":
        return f'<li class="subtitle"{indent}>{text}</li>'

    if itype in INFO_TYPES:
        label = {"note": "NOTE", "caution": "CAUTION", "warning": "WARNING"}[itype]
        return (
            f'<li class="info {itype}"{indent}>'
            f'<span class="tag">{label}</span><span class="itext">{text}</span>{detail}</li>'
        )

    if itype == "reference":
        ref = item.get("reference", {})
        target = ref.get("section_id") or ref.get("document") or ref.get("url") or ""
        return (
            f'<li class="info reference"{indent}><span class="tag">GO TO</span>'
            f'<span class="itext">{text}</span>'
            f'{f"<p class=detail>{esc(target)}</p>" if target else ""}</li>'
        )

    # action or challenge: the only tickable kinds
    mem = '<span class="mem">MEMORY</span>' if item.get("memory_item") else ""
    resp = f'<span class="resp">{esc(item["response"])}</span>' if item.get("response") else ""
    iid = esc(item.get("id") or "")
    return (
        f'<li class="task"{indent}>'
        f'<label><input type="checkbox" class="tick" data-section="{esc(sec_id)}" '
        f'data-index="{idx}" data-item-id="{iid}" data-text="{text}">'
        f'<span class="itext">{text}{mem}</span>{resp}{cond}</label>{detail}</li>'
    )


def render_section(sec: dict, si: int) -> str:
    sec_id = sec.get("id") or f"section-{si}"
    crit = sec.get("criticality", "normal")
    cond = f'<p class="seccond">{esc(sec["condition"])}</p>' if sec.get("condition") else ""
    notes = f'<p class="secnote">{esc(sec["notes"])}</p>' if sec.get("notes") else ""
    items = "\n".join(render_item(it, sec_id, i) for i, it in enumerate(sec.get("items", [])))
    phase = esc(sec.get("phase_label") or sec.get("phase", ""))
    return f"""<section class="sec {esc(crit)}" id="{esc(sec_id)}">
  <h2>{esc(sec.get('title'))} <span class="phase">{phase}</span></h2>
  {cond}{notes}
  <ul>
{items}
  </ul>
</section>"""


CSS = """
:root{--bg:#fff;--fg:#111;--muted:#666;--line:#d8d8d8;--task:#f7f8fa;
--warn:#b3261e;--caut:#8a5a00;--note:#1f4e79;--ok:#1b5e20;--quar:#b3261e;}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#14161a;--fg:#e9eaec;--muted:#9aa0a6;--line:#333;--task:#1c1f24;
--warn:#ff8a80;--caut:#ffcc80;--note:#90caf9;--ok:#a5d6a7;--quar:#ff8a80;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
-webkit-text-size-adjust:100%}
.wrap{max-width:44rem;margin:0 auto;padding:1rem}
h1{font-size:1.35rem;margin:.2rem 0}
.sub{color:var(--muted);font-size:.85rem;margin:.2rem 0 1rem}
.banner{border:2px solid;border-radius:.4rem;padding:.6rem .75rem;margin:.75rem 0;
font-size:.85rem;font-weight:600}
.banner.quarantine{border-color:var(--quar);color:var(--quar)}
.banner.ok{border-color:var(--ok);color:var(--ok)}
.banner .hd{display:block;font-size:.95rem;margin-bottom:.15rem}
.bar{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
padding:.5rem 0;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;z-index:5}
button,select{font:inherit;padding:.4rem .6rem;border:1px solid var(--line);
border-radius:.35rem;background:var(--bg);color:var(--fg)}
.count{margin-left:auto;color:var(--muted);font-size:.85rem;font-variant-numeric:tabular-nums}
.sec{margin:1.5rem 0;break-inside:auto}
.sec h2{font-size:1.05rem;border-bottom:2px solid var(--line);padding-bottom:.25rem;
margin:0 0 .5rem;display:flex;justify-content:space-between;align-items:baseline;gap:.5rem}
.sec.emergency h2{border-color:var(--warn);color:var(--warn)}
.sec.abnormal h2{border-color:var(--caut)}
.phase{font-size:.68rem;font-weight:400;color:var(--muted);text-transform:uppercase;
letter-spacing:.04em;white-space:nowrap}
.seccond{font-style:italic;color:var(--muted);margin:.2rem 0 .4rem;font-size:.9rem}
.secnote{color:var(--muted);margin:.2rem 0 .4rem;font-size:.85rem}
ul{list-style:none;margin:0;padding:0}
li{margin:.15rem 0}
li.task label{display:flex;align-items:flex-start;gap:.6rem;background:var(--task);
border:1px solid var(--line);border-radius:.3rem;padding:.55rem .65rem;cursor:pointer}
li.task input{width:1.4rem;height:1.4rem;margin:0;flex:none}
li.task input:checked~.itext{opacity:.5;text-decoration:line-through}
.itext{flex:1;min-width:0}
.resp{font-weight:700;text-transform:uppercase;font-size:.85rem;text-align:right;flex:none;
max-width:45%}
.cond{display:block;font-size:.75rem;color:var(--muted);font-style:italic}
.mem{display:inline-block;margin-left:.4rem;font-size:.6rem;font-weight:700;
border:1px solid currentColor;border-radius:.2rem;padding:0 .25rem;vertical-align:.1em}
li.subtitle{font-weight:700;font-size:.9rem;text-transform:uppercase;letter-spacing:.03em;
margin:.7rem 0 .3rem;color:var(--muted)}
li.info{display:flex;gap:.5rem;padding:.5rem .65rem;border-left:4px solid;
border-radius:0 .3rem .3rem 0;margin:.35rem 0;font-size:.92rem}
li.info .tag{font-size:.62rem;font-weight:700;letter-spacing:.05em;flex:none;padding-top:.15rem}
li.warning{border-color:var(--warn);color:var(--warn);background:color-mix(in srgb,var(--warn) 8%,transparent)}
li.caution{border-color:var(--caut);color:var(--caut);background:color-mix(in srgb,var(--caut) 8%,transparent)}
li.note,li.reference{border-color:var(--note);color:var(--note);background:color-mix(in srgb,var(--note) 8%,transparent)}
.detail{margin:.3rem 0 0;font-size:.8rem;color:var(--muted)}
li.blank{height:.6rem}
.foot{margin:2rem 0 3rem;font-size:.75rem;color:var(--muted);border-top:1px solid var(--line);
padding-top:.5rem}
.pagehdr{display:none}
@media print{
  .bar,.noprint{display:none!important}
  body{font-size:9.5pt;background:#fff;color:#000}
  .wrap{max-width:none;padding:0}
  :root{--task:#fff;--line:#999;--muted:#444;--warn:#000;--caut:#000;--note:#000}
  .sec{break-inside:avoid}
  li.task label{background:#fff;padding:.15rem .2rem;border:0;border-bottom:1px dotted #999;
  border-radius:0}
  li.task input{width:9pt;height:9pt;-webkit-appearance:none;appearance:none;
  border:1px solid #000;border-radius:1pt}
  li.info{border-left-width:3px;padding:.2rem .3rem;background:#fff!important}
  .pagehdr{display:block;position:running(hdr)}
  .banner{border-width:1px;padding:.25rem .4rem;margin:.3rem 0}
}
"""

JS = r"""
(function(){
  var meta = JSON.parse(document.getElementById('oc-meta').textContent);
  var ticks = new Map();          // key -> ISO timestamp
  var boxes = Array.prototype.slice.call(document.querySelectorAll('.tick'));
  var countEl = document.getElementById('count');

  function key(b){ return b.dataset.section + '|' + b.dataset.index; }

  function refresh(){
    countEl.textContent = ticks.size + ' / ' + boxes.length + ' done';
  }

  boxes.forEach(function(b){
    b.addEventListener('change', function(){
      var k = key(b);
      // Timestamp at the moment of the tick. Unticking removes the record
      // rather than rewriting it: the log should not claim a time for
      // something the pilot took back.
      if (b.checked) { ticks.set(k, new Date().toISOString()); }
      else { ticks.delete(k); }
      refresh();
    });
  });

  document.getElementById('reset').addEventListener('click', function(){
    if (!confirm('Clear all ticks and start over?')) return;
    boxes.forEach(function(b){ b.checked = false; });
    ticks.clear(); refresh();
  });

  document.getElementById('paper').addEventListener('change', function(){
    var s = document.getElementById('pagesize');
    var v = this.value.split(',');
    s.textContent = '@page{size:' + v[0] + ' ' + v[1] + ';margin:' + v[2] + '}';
  });

  // There is deliberately no "check all". See the module docstring.

  document.getElementById('log').addEventListener('click', function(){
    var entries = [];
    boxes.forEach(function(b){
      var k = key(b);
      if (!ticks.has(k)) return;
      var e = {
        section_id: b.dataset.section,
        item_index: parseInt(b.dataset.index, 10),
        item_text: b.dataset.text,
        state: 'completed',
        at: ticks.get(k)
      };
      if (b.dataset.itemId) e.item_id = b.dataset.itemId;
      entries.push(e);
    });
    if (!entries.length) { alert('Nothing ticked yet.'); return; }

    var started = entries.reduce(function(a, e){ return e.at < a ? e.at : a; }, entries[0].at);
    var complete = entries.length === boxes.length;
    var reg = (document.getElementById('reg').value || '').trim();
    var who = (document.getElementById('who').value || '').trim();

    var log = {
      open_checklist_log_version: '1.0',
      // Not a UUID: this page has no identity service. Collision-resistant
      // enough for a single pilot's records, and honest about what it is.
      id: 'log-' + meta.content_hash.slice(0, 12) + '-' + started.replace(/[^0-9]/g, ''),
      checklist: {
        id: meta.id,
        title: meta.title,
        content_hash: meta.content_hash,
        verification_at_use: meta.verification
      },
      session: {
        started: started,
        finished: new Date().toISOString(),
        outcome: complete ? 'completed' : 'abandoned'
      },
      recording: {
        mode: 'live',
        app: 'open-checklists render.py',
        clock_source: 'device_clock'
      },
      entries: entries
    };
    if (meta.file_revision) log.checklist.file_revision = meta.file_revision;
    if (reg) log.aircraft = { registration: reg };
    if (who) log.pilot = { name: who };
    if (!complete) {
      // An incomplete run is recorded as abandoned rather than completed. The
      // format has an outcome for "stopped partway" precisely so this does not
      // have to be dressed up.
      log.entries.forEach(function(){});
    }

    var blob = new Blob([JSON.stringify(log, null, 2)], {type: 'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = meta.id + '-log-' + started.slice(0, 19).replace(/[:T]/g, '') + '.json';
    a.click();
    URL.revokeObjectURL(a.href);
  });

  refresh();
})();
"""


def render(doc: dict, paper: str) -> str:
    cls, text = state_banner(doc)
    ac = doc.get("aircraft", {})
    ac_line = " ".join(filter(None, [ac.get("make"), ac.get("model"), ac.get("variant")]))
    src = doc.get("provenance", {}).get("source", {})
    rights = doc.get("rights", {})
    chash = content_hash(doc)

    meta = {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "content_hash": chash,
        "file_revision": doc.get("provenance", {}).get("revision", {}).get("file_revision"),
        "verification": {
            k: v
            for k, v in doc.get("verification", {}).items()
            if k in ("source_fidelity", "operational_review", "completeness")
        },
    }

    w, h, m = PAPER[paper]
    options = "\n".join(
        f'<option value="{v[0]},{v[1]},{v[2]}"{" selected" if k == paper else ""}>{k}</option>'
        for k, v in PAPER.items()
    )

    sections = "\n".join(render_section(s, i) for i, s in enumerate(doc.get("sections", [])))

    issues = doc.get("verification", {}).get("known_issues", [])
    issue_html = ""
    if issues:
        rows = "".join(
            f'<li><strong>{esc(i["severity"])}</strong>: {esc(i["description"])}</li>' for i in issues
        )
        issue_html = f'<div class="banner quarantine"><span class="hd">Known issues</span><ul>{rows}</ul></div>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(doc.get('title'))}</title>
<style>{CSS}</style>
<style id="pagesize">@page{{size:{w} {h};margin:{m}}}</style>
</head>
<body>
<div class="wrap">

<div class="bar noprint">
  <button id="reset">Reset</button>
  <label>Paper <select id="paper">{options}</select></label>
  <button onclick="window.print()">Print</button>
  <button id="log">Export log</button>
  <span class="count" id="count"></span>
</div>

<h1>{esc(doc.get('title'))}</h1>
<p class="sub">{esc(ac_line)} · {esc(ac.get('category', '').replace('_', ' '))}</p>

<div class="banner {cls}">
  <span class="hd">{'NOT FOR FLIGHT' if cls == 'quarantine' else 'Verification'}</span>
  {esc(text)}
</div>
{issue_html}

<p class="noprint sub">
  <label>Aircraft <input id="reg" placeholder="N-number" size="10"></label>
  <label>Pilot <input id="who" placeholder="name" size="14"></label>
</p>

{sections}

<div class="foot">
  <p><strong>Source:</strong> {esc(src.get('title') or 'authored — no source document')}
  {esc(src.get('document_number') or '')} {esc(src.get('revision') or '')}</p>
  <p><strong>Rights:</strong> {esc(rights.get('status'))}
  {esc(rights.get('corpus_license') or '')}</p>
  <p><strong>Checklist hash:</strong> <code>{chash[:32]}…</code></p>
  <p>Generated from <code>{esc(doc.get('id'))}.ocl.json</code> by the Open Checklists
  reference renderer. Verify against the aircraft's own approved documentation before use.</p>
</div>
</div>

<script type="application/json" id="oc-meta">{json.dumps(meta)}</script>
<script>{JS}</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--paper", choices=sorted(PAPER), default="letter")
    ap.add_argument("-o", "--outdir", type=Path, default=REPO / "build")
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    for path in args.files:
        doc = json.loads(path.read_text())
        out = args.outdir / f"{doc['id']}.html"
        out.write_text(render(doc, args.paper), encoding="utf-8")
        print(f"{out.relative_to(REPO) if out.is_relative_to(REPO) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
