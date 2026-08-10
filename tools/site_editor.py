#!/usr/bin/env python3
"""The browser checklist editor page, generated into the site.

This is the "anyone can create their own checklist" half of the project. It runs
entirely client-side: no server, no account, no upload. You start blank, open a
file you already have, or fork any checklist in the catalogue, edit it, and
download a valid .ocl.json.

Three things it does that a plain form would not:

  * Forking fills in `derived_from` automatically, including the parent's content
    hash computed in the browser with the same canonical serialization the Python
    tooling uses. Lineage is recorded without the author having to understand it.

  * Information items cannot be made tickable. Choosing warning, caution or note
    removes the response field and forces tickable false, so the one rule that
    matters most cannot be broken by the editing UI itself.

  * It validates before it lets you download, and says what is wrong in the terms
    a builder would use rather than as schema errors.

The generated page embeds the catalogue so forking works offline once loaded.
"""

from __future__ import annotations

import json

EDITOR_CSS = """
.ed{display:grid;gap:1rem}
.row{display:flex;gap:.5rem;flex-wrap:wrap;align-items:flex-end}
.f{display:flex;flex-direction:column;gap:.2rem;flex:1;min-width:9rem}
.f label{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.f input,.f select,.f textarea{font:inherit;padding:.4rem .5rem;border:1px solid var(--line);
border-radius:.3rem;background:var(--bg);color:var(--fg);width:100%}
.f textarea{min-height:3.5rem;resize:vertical}
fieldset{border:1px solid var(--line);border-radius:.5rem;padding:.75rem 1rem;margin:0}
legend{font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);padding:0 .3rem}
.sec{border:1px solid var(--line);border-radius:.5rem;padding:.75rem;margin:.6rem 0;background:var(--card)}
.itm{display:grid;grid-template-columns:7.5rem 1fr 1fr auto;gap:.4rem;align-items:center;
padding:.3rem;border-bottom:1px dotted var(--line)}
.itm.info{grid-template-columns:7.5rem 1fr auto}
.itm select,.itm input{font:inherit;padding:.3rem .4rem;border:1px solid var(--line);
border-radius:.25rem;background:var(--bg);color:var(--fg);min-width:0}
.itm .mem{display:flex;align-items:center;gap:.25rem;font-size:.7rem;white-space:nowrap}
.btn{font:inherit;padding:.35rem .6rem;border:1px solid var(--line);border-radius:.3rem;
background:var(--bg);color:var(--fg);cursor:pointer;white-space:nowrap}
.btn.p{background:var(--accent);color:#fff;border-color:transparent;font-weight:600}
.btn.d{color:var(--warn)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.problems{border:2px solid var(--warn);color:var(--warn);border-radius:.4rem;padding:.6rem .8rem;font-size:.85rem}
.problems ul{margin:.3rem 0 0;padding-left:1.2rem}
.okmsg{border:2px solid var(--ok);color:var(--ok);border-radius:.4rem;padding:.6rem .8rem;font-size:.85rem}
.hint{font-size:.78rem;color:var(--muted)}
@media(max-width:640px){.itm,.itm.info{grid-template-columns:1fr;gap:.25rem}}
"""

EDITOR_BODY = """
<h2>Checklist editor</h2>
<p class="lede">Build a checklist for your aircraft, or start from someone else's and
change what your aeroplane does differently. Everything happens in this page — no
account, nothing uploaded. You get a file you can keep, print, load into software,
or contribute back.</p>

<div class="row">
  <div class="f" style="flex:2">
    <label for="startfrom">Start from</label>
    <select id="startfrom"></select>
  </div>
  <button class="btn p" id="load">Load</button>
  <button class="btn" id="openfile">Open a .ocl.json file</button>
  <input type="file" id="file" accept=".json,.ocl.json" hidden>
</div>
<p class="hint" id="lineage"></p>

<div class="ed">
<fieldset><legend>Aircraft</legend>
  <div class="row">
    <div class="f"><label for="make">Make</label><input id="make" placeholder="Kitfox"></div>
    <div class="f"><label for="model">Model</label><input id="model" placeholder="Series 7"></div>
    <div class="f"><label for="variant">Variant</label><input id="variant" placeholder="tri-gear"></div>
  </div>
  <div class="row">
    <div class="f"><label for="category">Category</label><select id="category"></select></div>
    <div class="f"><label for="family">Airframe family
      </label><input id="family" placeholder="kitfox"></div>
    <div class="f"><label for="reg">Registration (optional)</label><input id="reg" placeholder="N123AB"></div>
  </div>
  <p class="hint">The family slug is how other people flying your airframe find your
  file. Use the airframe, not the engine: every Kitfox is <code>kitfox</code>
  whatever is bolted to the front.</p>
  <div class="row">
    <div class="f"><label for="engmake">Engine make</label><input id="engmake" placeholder="Rotax"></div>
    <div class="f"><label for="engmodel">Engine model</label><input id="engmodel" placeholder="912ULS"></div>
    <div class="f"><label for="engtype">Engine type</label><select id="engtype"></select></div>
  </div>
</fieldset>

<fieldset><legend>What is different about your aircraft</legend>
  <p class="hint">Engine swaps, prop changes, panel rebuilds, gross weight increases.
  This is the part other builders search for.</p>
  <div id="mods"></div>
  <button class="btn" id="addmod">Add a modification</button>
</fieldset>

<fieldset><legend>About this checklist</legend>
  <div class="row">
    <div class="f" style="flex:3"><label for="title">Title</label><input id="title"></div>
    <div class="f"><label for="id">File id (slug)</label><input id="id" placeholder="kitfox-7-912uls-n123ab"></div>
  </div>
  <div class="row">
    <div class="f"><label for="author">Your name</label><input id="author" placeholder="Required — who stands behind this"></div>
    <div class="f"><label for="contact">Contact (optional)</label><input id="contact"></div>
    <div class="f"><label for="completeness">Completeness</label><select id="completeness"></select></div>
  </div>
  <div class="f"><label for="changes">What you changed and why (for a fork)</label>
    <textarea id="changes" placeholder="The 912 swap moved the fuel pump switch into the start sequence and added a separate carb heat check…"></textarea></div>
  <p class="hint">Every file you make here is recorded as authored by you, never
  reviewed, and not airworthy. Those states are not editable in this page — they are
  earned by someone else checking your file, not claimed by writing it.</p>
</fieldset>

<fieldset><legend>Sections and items</legend>
  <div id="sections"></div>
  <button class="btn" id="addsec">Add a section</button>
</fieldset>

<div id="status"></div>
<div class="row">
  <button class="btn p" id="download">Check and download .ocl.json</button>
  <button class="btn" id="preview">Preview as a checklist</button>
  <span class="hint" id="counts"></span>
</div>
<p class="hint">To contribute it: open a pull request adding the file to
<code>examples/</code>, or send it to the project with the source you worked from.
CI runs the same checks this page runs, plus the ones that need the whole corpus.</p>
</div>
"""

EDITOR_JS = r"""
(function(){
  var CAT = JSON.parse(document.getElementById('catalogue').textContent);
  var CATEGORIES = ["part103_ultralight","light_sport","experimental_amateur_built",
    "experimental_exhibition","primary","standard_normal","standard_utility",
    "standard_acrobatic","glider","powered_parachute","weight_shift_control",
    "rotorcraft","balloon","other"];
  var ENGTYPES = ["piston_2stroke","piston_4stroke","turboprop","turbofan","turbojet",
    "electric","rotary","none"];
  var MODKINDS = ["engine_swap","propeller_change","fuel_system","electrical_system",
    "avionics","instrument_panel","gross_weight_increase","aerodynamic","landing_gear",
    "float_or_ski_install","control_system","ballistic_parachute","structural","other"];
  var ITEMTYPES = ["action","challenge","subtitle","note","caution","warning"];
  var PHASES = ["preflight_inspection","before_start","engine_start","after_start",
    "before_taxi","taxi","before_takeoff","takeoff","after_takeoff","climb","cruise",
    "descent","approach","before_landing","landing","go_around","after_landing",
    "shutdown","securing","limitations","engine_failure_before_rotation",
    "engine_failure_after_takeoff","engine_failure_in_flight","engine_fire_in_flight",
    "electrical_fire","forced_landing","landing_gear_malfunction","icing","other"];
  var INFO = {note:1,caution:1,warning:1,subtitle:1};

  var state = { sections: [], mods: [], parent: null };

  function opt(sel, arr, cur){
    sel.innerHTML = arr.map(function(v){
      return '<option value="'+v+'"'+(v===cur?' selected':'')+'>'+v.replace(/_/g,' ')+'</option>';
    }).join('');
  }
  function el(id){ return document.getElementById(id); }

  opt(el('category'), CATEGORIES, 'experimental_amateur_built');
  opt(el('engtype'), ENGTYPES, 'piston_4stroke');
  opt(el('completeness'), ['partial','normal_only','full','excerpt'], 'partial');

  el('startfrom').innerHTML = '<option value="">Blank checklist</option>' +
    CAT.checklists.map(function(c){
      return '<option value="'+c.id+'">Fork: '+c.title+'</option>';
    }).join('');

  // ---- canonical hash, matching tools/validate.py content_hash ----
  function sortDeep(v){
    if (Array.isArray(v)) return v.map(sortDeep);
    if (v && typeof v === 'object'){
      var o = {};
      Object.keys(v).sort().forEach(function(k){ o[k] = sortDeep(v[k]); });
      return o;
    }
    return v;
  }
  function canonical(doc){
    var stripped = {};
    Object.keys(doc).forEach(function(k){ if (k !== 'verification') stripped[k] = doc[k]; });
    return JSON.stringify(sortDeep(stripped), null, 2) + '\n';
  }
  async function hashOf(doc){
    var bytes = new TextEncoder().encode(canonical(doc));
    var d = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(d)).map(function(b){
      return b.toString(16).padStart(2,'0'); }).join('');
  }

  // ---- sections / items ----
  function renderMods(){
    el('mods').innerHTML = state.mods.map(function(m,i){
      return '<div class="row" data-mi="'+i+'">' +
        '<div class="f"><label>Kind</label><select class="mk">' +
          MODKINDS.map(function(k){ return '<option'+(k===m.kind?' selected':'')+'>'+k+'</option>'; }).join('') +
        '</select></div>' +
        '<div class="f" style="flex:3"><label>What was done</label>' +
          '<input class="md" value="'+esc(m.description||'')+'"></div>' +
        '<div class="f" style="flex:0 0 auto"><label>Changes procedures?</label>' +
          '<input type="checkbox" class="ma"'+(m.affects_procedures?' checked':'')+'></div>' +
        '<button class="btn d rmmod">Remove</button></div>';
    }).join('');
  }
  function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }

  function renderSections(){
    el('sections').innerHTML = state.sections.map(function(s,si){
      var items = s.items.map(function(it,ii){
        var isInfo = INFO[it.type];
        var typeSel = '<select class="it">' + ITEMTYPES.map(function(t){
          return '<option'+(t===it.type?' selected':'')+'>'+t+'</option>'; }).join('') + '</select>';
        var text = '<input class="ix" placeholder="'+(isInfo?'The warning or note':'Control or action')+
                   '" value="'+esc(it.text||'')+'">';
        if (isInfo){
          return '<div class="itm info" data-si="'+si+'" data-ii="'+ii+'">' + typeSel + text +
                 '<button class="btn d rmitem">×</button></div>';
        }
        return '<div class="itm" data-si="'+si+'" data-ii="'+ii+'">' + typeSel + text +
          '<input class="ir" placeholder="Expected response e.g. BOTH" value="'+esc(it.response||'')+'">' +
          '<span class="mem"><input type="checkbox" class="im"'+(it.memory_item?' checked':'')+
          '> memory</span><button class="btn d rmitem">×</button></div>';
      }).join('');
      return '<div class="sec" data-si="'+si+'">' +
        '<div class="row"><div class="f" style="flex:2"><label>Section title</label>' +
        '<input class="st" value="'+esc(s.title||'')+'"></div>' +
        '<div class="f"><label>Phase</label><select class="sp">' +
          PHASES.map(function(p){ return '<option'+(p===s.phase?' selected':'')+'>'+p+'</option>'; }).join('') +
        '</select></div>' +
        '<div class="f"><label>Criticality</label><select class="sc">' +
          ['normal','abnormal','emergency'].map(function(c){
            return '<option'+(c===s.criticality?' selected':'')+'>'+c+'</option>'; }).join('') +
        '</select></div>' +
        '<button class="btn" data-up>↑</button><button class="btn" data-down>↓</button>' +
        '<button class="btn d rmsec">Remove section</button></div>' +
        items + '<button class="btn additem">Add item</button></div>';
    }).join('');
    updateCounts();
  }

  function updateCounts(){
    var n = 0, mem = 0, warn = 0;
    state.sections.forEach(function(s){ s.items.forEach(function(it){
      if (it.type === 'action' || it.type === 'challenge') n++;
      if (it.memory_item) mem++;
      if (it.type === 'warning' || it.type === 'caution') warn++;
    }); });
    el('counts').textContent = state.sections.length + ' sections · ' + n +
      ' tickable · ' + mem + ' memory · ' + warn + ' warnings/cautions';
  }

  // Delegated events keep this simple and survive re-render.
  el('sections').addEventListener('click', function(e){
    var secEl = e.target.closest('.sec'); if (!secEl) return;
    var si = +secEl.dataset.si;
    if (e.target.classList.contains('additem')){
      state.sections[si].items.push({type:'action', text:'', response:''});
      renderSections();
    } else if (e.target.classList.contains('rmsec')){
      state.sections.splice(si,1); renderSections();
    } else if (e.target.classList.contains('rmitem')){
      var ii = +e.target.closest('.itm').dataset.ii;
      state.sections[si].items.splice(ii,1); renderSections();
    } else if (e.target.hasAttribute('data-up') && si > 0){
      var t = state.sections[si]; state.sections[si] = state.sections[si-1];
      state.sections[si-1] = t; renderSections();
    } else if (e.target.hasAttribute('data-down') && si < state.sections.length-1){
      var t2 = state.sections[si]; state.sections[si] = state.sections[si+1];
      state.sections[si+1] = t2; renderSections();
    }
  });

  el('sections').addEventListener('change', function(e){
    var secEl = e.target.closest('.sec'); if (!secEl) return;
    var si = +secEl.dataset.si, s = state.sections[si];
    if (e.target.classList.contains('st')) s.title = e.target.value;
    if (e.target.classList.contains('sp')) s.phase = e.target.value;
    if (e.target.classList.contains('sc')) s.criticality = e.target.value;
    var itmEl = e.target.closest('.itm');
    if (itmEl){
      var it = s.items[+itmEl.dataset.ii];
      if (e.target.classList.contains('it')){
        it.type = e.target.value;
        // The rule that must not be breakable from the UI: an information item is
        // not a task, so it loses its response and can never be a memory item.
        if (INFO[it.type]){ delete it.response; it.memory_item = false; }
        renderSections(); return;
      }
      if (e.target.classList.contains('ix')) it.text = e.target.value;
      if (e.target.classList.contains('ir')) it.response = e.target.value;
      if (e.target.classList.contains('im')) it.memory_item = e.target.checked;
    }
    updateCounts();
  }, true);
  el('sections').addEventListener('input', function(e){
    var secEl = e.target.closest('.sec'); if (!secEl) return;
    var si = +secEl.dataset.si, itmEl = e.target.closest('.itm');
    if (e.target.classList.contains('st')) state.sections[si].title = e.target.value;
    if (itmEl){
      var it = state.sections[si].items[+itmEl.dataset.ii];
      if (e.target.classList.contains('ix')) it.text = e.target.value;
      if (e.target.classList.contains('ir')) it.response = e.target.value;
    }
  });

  el('mods').addEventListener('click', function(e){
    if (e.target.classList.contains('rmmod')){
      state.mods.splice(+e.target.closest('[data-mi]').dataset.mi,1); renderMods();
    }
  });
  el('mods').addEventListener('input', function(e){
    var r = e.target.closest('[data-mi]'); if (!r) return;
    var m = state.mods[+r.dataset.mi];
    if (e.target.classList.contains('mk')) m.kind = e.target.value;
    if (e.target.classList.contains('md')) m.description = e.target.value;
    if (e.target.classList.contains('ma')) m.affects_procedures = e.target.checked;
  });
  el('addmod').addEventListener('click', function(){
    state.mods.push({kind:'engine_swap', description:'', affects_procedures:true});
    renderMods();
  });
  el('addsec').addEventListener('click', function(){
    state.sections.push({title:'New section', phase:'preflight_inspection',
                         criticality:'normal', items:[]});
    renderSections();
  });

  // ---- load / fork ----
  function adopt(doc, asFork){
    var ac = doc.aircraft || {};
    el('make').value = ac.make || ''; el('model').value = ac.model || '';
    el('variant').value = ac.variant || ''; el('family').value = ac.airframe_family || '';
    el('reg').value = (ac.airframe_specific||{}).registration || '';
    opt(el('category'), CATEGORIES, ac.category || 'experimental_amateur_built');
    var eng = (ac.engine||[])[0] || {};
    el('engmake').value = eng.make || ''; el('engmodel').value = eng.model || '';
    opt(el('engtype'), ENGTYPES, eng.type || 'piston_4stroke');
    state.mods = JSON.parse(JSON.stringify(ac.modifications || []));
    state.sections = (doc.sections||[]).map(function(s){
      return { title: s.title, phase: s.phase, criticality: s.criticality || 'normal',
               items: (s.items||[]).map(function(it){
                 return { type: it.type, text: it.text, response: it.response,
                          memory_item: !!it.memory_item, detail: it.detail,
                          condition: it.condition, indent: it.indent };
               }) };
    });
    el('title').value = asFork ? (doc.title || '') + ' (my variation)' : (doc.title || '');
    el('id').value = asFork ? (doc.id || '') + '-variant' : (doc.id || '');
    el('completeness').value = (doc.verification||{}).completeness || 'partial';
    renderMods(); renderSections();
  }

  el('load').addEventListener('click', async function(){
    var id = el('startfrom').value;
    if (!id){
      state = { sections: [], mods: [], parent: null };
      ['make','model','variant','family','reg','engmake','engmodel','title','id','changes']
        .forEach(function(k){ el(k).value = ''; });
      state.sections = [{title:'Preflight Inspection', phase:'preflight_inspection',
                         criticality:'normal', items:[{type:'action',text:'',response:''}]}];
      el('lineage').textContent = 'Starting from a blank checklist.';
      renderMods(); renderSections(); return;
    }
    var doc;
    try {
      var res = await fetch('api/checklists/' + id + '.json');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      doc = await res.json();
    } catch (err) {
      // Opening this page straight off the filesystem blocks fetch, so forking
      // cannot load the parent. Say so plainly instead of failing silently.
      el('lineage').innerHTML = '<strong>Cannot load that checklist from a local ' +
        'file.</strong> Forking needs to read the parent, which browsers block for ' +
        'file:// pages. Serve the folder over HTTP — <code>python3 -m http.server</code> ' +
        'in the site directory — or use "Open a .ocl.json file" to load a copy you ' +
        'already have. (' + err.message + ')';
      return;
    }
    var h = await hashOf(doc);
    state.parent = { checklist_id: doc.id, content_hash: h,
                     file_revision: (doc.provenance||{}).revision &&
                                    doc.provenance.revision.file_revision,
                     relationship: 'variant_of', diverged: false };
    adopt(doc, true);
    el('lineage').textContent = 'Forked from ' + doc.id + ' (parent hash ' +
      h.slice(0,12) + '…). Your file will record that lineage automatically.';
  });

  el('openfile').addEventListener('click', function(){ el('file').click(); });
  el('file').addEventListener('change', function(e){
    var f = e.target.files[0]; if (!f) return;
    var r = new FileReader();
    r.onload = function(){
      try {
        var doc = JSON.parse(r.result);
        state.parent = doc.derived_from || null;
        adopt(doc, false);
        el('lineage').textContent = 'Opened ' + f.name + '.';
      } catch (err) { alert('That file is not valid JSON: ' + err.message); }
    };
    r.readAsText(f);
  });

  // ---- build, validate, download ----
  function build(){
    var doc = {
      open_checklist_version: '1.0',
      id: (el('id').value || '').trim(),
      title: (el('title').value || '').trim(),
      aircraft: {
        make: (el('make').value||'').trim(),
        model: (el('model').value||'').trim(),
        category: el('category').value
      },
      provenance: {
        source: { kind: 'none', notes: 'Authored in the Open Checklists browser editor.' },
        transcription: { method: 'authored', date: new Date().toISOString().slice(0,10) },
        contributors: [{ name: (el('author').value||'').trim(), role: ['author'] }]
      },
      verification: {
        source_fidelity: 'not_applicable',
        operational_review: 'none',
        completeness: el('completeness').value,
        known_issues: [{
          severity: 'safety_defect',
          description: 'Authored by its contributor and not reviewed by anyone else. ' +
            'No item has been checked against a source document or against the aircraft. ' +
            'Not airworthy data.',
          location: 'whole file'
        }]
      },
      rights: { status: 'original_expression', corpus_license: 'CC-BY-4.0',
                redistribution: 'attribution_required' },
      sections: []
    };
    if (el('variant').value.trim()) doc.aircraft.variant = el('variant').value.trim();
    if (el('family').value.trim()) doc.aircraft.airframe_family = el('family').value.trim();
    if (el('engmake').value.trim() || el('engmodel').value.trim()){
      doc.aircraft.engine = [{ make: el('engmake').value.trim() || 'Unknown',
                               model: el('engmodel').value.trim() || 'Unknown',
                               type: el('engtype').value, count: 1 }];
    }
    var mods = state.mods.filter(function(m){ return (m.description||'').trim(); });
    if (mods.length) doc.aircraft.modifications = mods.map(function(m){
      return { kind: m.kind, description: m.description.trim(),
               affects_procedures: !!m.affects_procedures, approval: 'owner_designed' };
    });
    if (el('reg').value.trim())
      doc.aircraft.airframe_specific = { registration: el('reg').value.trim() };
    if (el('contact').value.trim())
      doc.provenance.contributors[0].contact = el('contact').value.trim();

    if (state.parent){
      doc.derived_from = {
        checklist_id: state.parent.checklist_id,
        relationship: state.parent.relationship || 'variant_of',
        diverged: false
      };
      if (state.parent.content_hash) doc.derived_from.content_hash = state.parent.content_hash;
      if (state.parent.file_revision) doc.derived_from.file_revision = state.parent.file_revision;
      var cs = (el('changes').value||'').trim();
      if (cs) doc.derived_from.changes_summary = cs;
    }

    doc.sections = state.sections.map(function(s, si){
      return {
        id: slug(s.title) || ('section-' + si),
        phase: s.phase,
        title: (s.title||'').trim(),
        criticality: s.criticality || 'normal',
        items: (function(){
          var used = {};
          return s.items.filter(function(it){ return (it.text||'').trim(); }).map(function(it){
          var o = { type: it.type, text: it.text.trim() };
          if (INFO[it.type]){ o.tickable = false; }
          else {
            o.tickable = true;
            if ((it.response||'').trim()) o.response = it.response.trim();
            if (it.memory_item){
              o.memory_item = true;
              // A memory item must be addressable so reviewers and tooling can
              // refer to it stably. Derive an id from the text and de-duplicate.
              var base = slug(it.text) || 'memory-item';
              var id = base, n = 2;
              while (used[id]) { id = base + '-' + (n++); }
              used[id] = 1;
              o.id = id;
            }
          }
          if (it.detail) o.detail = it.detail;
          if (it.condition) o.condition = it.condition;
          if (it.indent) o.indent = it.indent;
          return o;
          });
        })()
      };
    });
    return doc;
  }
  function slug(s){
    return (s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,60);
  }

  function problems(doc){
    var p = [];
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(doc.id))
      p.push('File id must be a lowercase slug like kitfox-7-912uls (letters, numbers, hyphens).');
    if (doc.id.length < 3) p.push('File id is too short.');
    if (!doc.title) p.push('Give the checklist a title.');
    if (!doc.aircraft.make) p.push('Aircraft make is required.');
    if (!doc.aircraft.model) p.push('Aircraft model is required.');
    if (!doc.provenance.contributors[0].name)
      p.push('Put your name in — a file nobody stands behind cannot be assessed.');
    if (!doc.sections.length) p.push('Add at least one section with one item.');
    doc.sections.forEach(function(s, i){
      if (!s.title) p.push('Section ' + (i+1) + ' needs a title.');
      if (!s.items.length) p.push('Section "' + (s.title||i+1) + '" has no items with any text.');
      s.items.forEach(function(it, j){
        if (it.type === 'action' && !it.response)
          p.push('"' + it.text + '" is an action, so it needs an expected response ' +
                 '(or change it to a challenge).');
        if (INFO[it.type] && it.tickable !== false)
          p.push('Internal error: information item marked tickable.');
      });
    });
    if (doc.aircraft.modifications && !doc.aircraft.airframe_family)
      p.push('You recorded modifications but no airframe family — without it, nobody ' +
             'browsing your airframe will find this file.');
    if (doc.derived_from && !doc.derived_from.changes_summary &&
        !(doc.aircraft.modifications||[]).length)
      p.push('This is a fork, so say what you changed (or record a modification).');
    var ids = doc.sections.map(function(s){ return s.id; });
    if (new Set(ids).size !== ids.length)
      p.push('Two sections ended up with the same id. Give them distinct titles.');
    return p;
  }

  function show(doc){
    var p = problems(doc);
    if (p.length){
      el('status').innerHTML = '<div class="problems"><strong>Not ready yet:</strong><ul>' +
        p.map(function(x){ return '<li>' + esc(x) + '</li>'; }).join('') + '</ul></div>';
      return false;
    }
    el('status').innerHTML = '<div class="okmsg">Looks structurally valid. It will be ' +
      'marked <strong>authored, not reviewed, not airworthy</strong> — which is correct ' +
      'until somebody else checks it.</div>';
    return true;
  }

  el('download').addEventListener('click', function(){
    var doc = build();
    if (!show(doc)) return;
    var blob = new Blob([JSON.stringify(doc, null, 2) + '\n'], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = doc.id + '.ocl.json';
    a.click(); URL.revokeObjectURL(a.href);
  });

  el('preview').addEventListener('click', function(){
    var doc = build();
    if (!show(doc)) return;
    var w = window.open('', '_blank');
    var h = '<h1>' + esc(doc.title) + '</h1><p><em>NOT REVIEWED — authored, not airworthy</em></p>';
    doc.sections.forEach(function(s){
      h += '<h2>' + esc(s.title) + '</h2><ul style="list-style:none;padding:0">';
      s.items.forEach(function(it){
        if (INFO[it.type] && it.type !== 'subtitle')
          h += '<li style="color:#b3261e"><strong>' + it.type.toUpperCase() + ':</strong> ' + esc(it.text) + '</li>';
        else if (it.type === 'subtitle') h += '<li><strong>' + esc(it.text) + '</strong></li>';
        else h += '<li>&#9744; ' + esc(it.text) + (it.response ? ' — <strong>' + esc(it.response) + '</strong>' : '') +
                  (it.memory_item ? ' <small>[MEMORY]</small>' : '') + '</li>';
      });
      h += '</ul>';
    });
    w.document.write('<meta name=viewport content="width=device-width,initial-scale=1">' +
      '<style>body{font:16px/1.5 system-ui;max-width:40rem;margin:2rem auto;padding:0 1rem}</style>' + h);
    w.document.close();
  });

  el('load').click();
})();
"""


def editor_page(head_fn, foot: str, catalogue: dict) -> str:
    return (
        head_fn(
            "Checklist editor — Open Checklists",
            "Build a checklist for your aircraft, or fork someone else's and change what "
            "yours does differently. Runs entirely in your browser.",
        )
        + f"<style>{EDITOR_CSS}</style>"
        + EDITOR_BODY
        + f'<script type="application/json" id="catalogue">{json.dumps(catalogue)}</script>'
        + f"<script>{EDITOR_JS}</script>"
        + foot
    )
