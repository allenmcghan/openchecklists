"""Pilot knowledge-test prep: /quiz/ hub, one practice page per test, one static page per question.

Source data lives in quiz/ (tracked): <test>.json holds the questions, figures.json the supplement
figures, figures/*.jpg the images. FAA sample questions and FAA-CT-8080-2H figures are U.S. Government
works; the answers, explanations and the Part 103 primer are our own, and every explanation cites
14 CFR, the AIM or an FAA handbook.
"""
from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "quiz"
ORDER = ["par", "spa", "uag", "p103"]
BLURB = {
    "par": "Airplane systems, aerodynamics, weather, airspace, regulations and charts: the material on the "
           "60-question FAA Private Pilot Airplane (PAR) knowledge test.",
    "spa": "The FAA Sport Pilot Airplane (SPA) knowledge test: regulations, weather, performance, navigation "
           "and sport-pilot limitations.",
    "uag": "The FAA Remote Pilot (UAG) knowledge test for the Part 107 drone certificate: airspace authorization, "
           "remote ID, operations over people, weather and charts.",
    "p103": "Weight, fuel, speed, daylight and airspace limits for ultralight vehicles, written from the text of "
            "14 CFR Part 103. No test required, but every ultralight pilot should know these.",
}
SIZES = (10, 20, 60)

QUIZ_CSS = """<style>
.crumbs{font-size:.86rem;color:var(--muted);margin:.4rem 0 .2rem}
.crumbs a{color:var(--muted)}
.qstem{font-size:1.12rem;line-height:1.5;font-weight:600;margin:.8rem 0 1rem}
ol.qch{list-style:none;padding:0;margin:0 0 1rem;display:grid;gap:.5rem}
ol.qch li{margin:0}
.qbtn{display:flex;gap:.6rem;align-items:flex-start;width:100%;text-align:left;font:inherit;color:var(--fg);
 background:var(--card);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:.7rem .85rem;cursor:pointer}
.qbtn:hover{border-color:var(--accent-2)}
.qbtn:disabled{cursor:default}
.qbtn b{flex:none;min-width:1.4rem;color:var(--accent)}
.qbtn.right{border-color:var(--ok);background:var(--ok-weak)}
.qbtn.wrong{border-color:var(--warn);background:var(--warn-weak)}
details.ans{border:1px solid var(--line);border-radius:var(--radius-sm);padding:.7rem .9rem;margin:1rem 0;background:#fff}
details.ans summary{cursor:pointer;font-weight:700;color:var(--accent)}
.ans .ok{color:var(--ok);font-weight:700}
.cites{font-size:.88rem;margin:.4rem 0 0}
.cites li{margin:.2rem 0}
figure.qfig{margin:.6rem 0 1rem}
figure.qfig img{max-width:100%;max-height:78vh;width:auto;height:auto;border:1px solid var(--line);border-radius:6px;background:#fff}
figure.qfig figcaption{font-size:.8rem;color:var(--muted);margin-top:.25rem}
.qnav{display:flex;justify-content:space-between;gap:.6rem;flex-wrap:wrap;margin:1.2rem 0}
.src{font-size:.82rem;color:var(--muted)}
.qbox{border:1px solid var(--line);border-radius:var(--radius);padding:1rem 1.1rem;margin:1rem 0;background:#fff;box-shadow:var(--shadow-sm)}
.qbar{height:6px;background:var(--line);border-radius:99px;overflow:hidden;margin:.3rem 0 .8rem}
.qbar i{display:block;height:100%;background:var(--accent-2);width:0}
.qmeta{display:flex;justify-content:space-between;font-size:.85rem;color:var(--muted)}
.qexp{margin:.8rem 0 0;padding:.7rem .85rem;border-radius:var(--radius-sm);background:var(--accent-weak)}
.qstart{display:flex;flex-wrap:wrap;gap:.5rem;margin:.8rem 0}
.qscore{font-size:2rem;font-weight:800;margin:.2rem 0}
.qrev{border-top:1px solid var(--line);padding:.7rem 0}
.qrev .you{color:var(--warn)}
.qrev .ok{color:var(--ok);font-weight:700}
ol.qlist{columns:2 22rem;padding-left:1.4rem}
ol.qlist li{break-inside:avoid;margin:.25rem 0;font-size:.92rem}
.qcards{list-style:none;padding:0;display:grid;gap:.8rem;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr))}
.qcards li{margin:0;border:1px solid var(--line);border-radius:var(--radius);padding:1rem;background:var(--card)}
.qcards h2{font-size:1.1rem;margin:0 0 .3rem}
@media print{.aff-slot,.aff-box,.ad-slot,.qstart,.qnav{display:none!important}}
</style>
"""


def esc(v: object) -> str:
    return escape("" if v is None else str(v), quote=True)


def _absolute_links(foot: str) -> str:
    """FOOT uses root-relative-less links ("terms.html"); quiz pages are nested, so anchor them at /."""
    return re.sub(r'href="(?![/#]|https?:|mailto:)', 'href="/', foot)


def _short(stem: str, limit: int = 70) -> str:
    s = re.sub(r"^\(Refer to [^)]*\)\s*", "", stem).replace("`", "'").strip()
    if len(s) <= limit:
        return s.rstrip(".?")
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def _qpath(test: dict, q: dict) -> str:
    return f"quiz/{test['slug']}/q/{q['n']}-{q['slug']}/"


def _cite_html(c: dict) -> str:
    if c.get("doc"):
        href = f"/search.html?doc={esc(c['doc'])}&amp;q={esc(c['q'])}"
        return f'<li>{esc(c["label"])} &middot; <a href="{href}">search it in our library</a></li>'
    return f'<li><a href="{esc(c["url"])}" rel="noopener">{esc(c["label"])}</a></li>'


def _fig_html(key: str, figs: dict) -> str:
    f = figs[key]
    src = f"/quiz/figures/{esc(f['file'])}"
    return (f'<figure class="qfig"><a href="{src}" target="_blank" rel="noopener">'
            f'<img src="{src}" width="{f["w"]}" height="{f["h"]}" loading="lazy" alt="{esc(f["caption"])}"></a>'
            f'<figcaption>{esc(f["caption"])} U.S. Government work (public domain). '
            f'<a href="{esc(f["source"])}" rel="noopener">Source PDF</a>. Tap to enlarge.</figcaption></figure>')


def _source_line(test: dict, q: dict) -> str:
    if test["id"] == "p103":
        return (f'<p class="src">Original OpenChecklists question written from '
                f'<a href="{esc(test["url"])}" rel="noopener">14 CFR Part 103</a>.</p>')
    code = f' &middot; ACS/LSC code {esc(q["code"])}' if q.get("code") else ""
    return (f'<p class="src">Question {q["n"]} from the FAA document <a href="{esc(test["url"])}" rel="noopener">'
            f'{esc(test["source"])}</a> (U.S. Government work, public domain){code}. The FAA does not publish an '
            f'answer key; the answer and explanation are ours, with references. Verify against the current '
            f'regulations and handbooks.</p>')


def _jsonld(obj: dict) -> str:
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>")


SELF_CHECK_JS = """<script>
(function(){
  var box=document.getElementById('qone'); if(!box) return;
  var ans=box.getAttribute('data-ans'), done=false;
  box.querySelectorAll('.qbtn').forEach(function(b){
    b.addEventListener('click',function(){
      if(done) return; done=true;
      var pick=b.getAttribute('data-l');
      box.querySelectorAll('.qbtn').forEach(function(x){
        x.disabled=true;
        if(x.getAttribute('data-l')===ans) x.classList.add('right');
      });
      if(pick!==ans) b.classList.add('wrong');
      var d=document.getElementById('qans'); if(d) d.open=true;
      if(pick===ans && typeof oclToken==='function' && oclToken()){
        oclReq('POST','/me/quiz',{test:box.getAttribute('data-test'),n:+box.getAttribute('data-n'),answer:pick}).catch(function(){});
      }
    });
  });
})();
</script>
"""


def _question_page(head, foot: str, test: dict, q: dict, prev_q, next_q, figs: dict) -> str:
    path = _qpath(test, q)
    short = _short(q["stem"])
    title = f"{short} — {test['short']} practice question"
    correct = q["choices"][q["answer"]]
    desc = (f"{test['short']} practice question {q['n']}: {_short(q['stem'], 110)} "
            f"Answer, explanation and FAA references.")
    choices = "".join(
        f'<li><button type="button" class="qbtn" data-l="{l}"><b>{l}.</b><span>{esc(t)}</span></button></li>'
        for l, t in q["choices"].items())
    cites = "".join(_cite_html(c) for c in q["cites"])
    nav = '<div class="qnav">'
    nav += (f'<a href="/{_qpath(test, prev_q)}">&larr; Question {prev_q["n"]}</a>' if prev_q else "<span></span>")
    nav += f'<a href="/quiz/{test["slug"]}/">All {esc(test["title"])} questions</a>'
    nav += (f'<a href="/{_qpath(test, next_q)}">Question {next_q["n"]} &rarr;</a>' if next_q else "<span></span>")
    nav += "</div>"
    ld = {"@context": "https://schema.org", "@type": "Quiz", "name": title,
          "about": {"@type": "Thing", "name": test["title"]},
          "hasPart": [{"@type": "Question", "eduQuestionType": "Multiple choice", "text": q["stem"],
                       "suggestedAnswer": [{"@type": "Answer", "text": t}
                                           for l, t in q["choices"].items() if l != q["answer"]],
                       "acceptedAnswer": {"@type": "Answer", "text": correct,
                                          "answerExplanation": {"@type": "Comment", "text": q["explanation"]}}}]}
    body = (QUIZ_CSS
            + f'<p class="crumbs"><a href="/quiz/">Test prep</a> &rsaquo; <a href="/quiz/{test["slug"]}/">'
            f'{esc(test["title"])}</a> &rsaquo; Question {q["n"]}</p>'
            f'<h1>{esc(test["title"])} practice question {q["n"]}</h1>'
            f'<div id="qone" data-ans="{q["answer"]}" data-test="{esc(test["id"])}" data-n="{q["n"]}">'
            f'<p class="qstem">{esc(q["stem"].replace("`", chr(39)))}</p>'
            + "".join(_fig_html(k, figs) for k in q["figures"])
            + f'<ol class="qch">{choices}</ol></div>'
            f'<details class="ans" id="qans"><summary>Show answer</summary>'
            f'<p class="ok">Correct answer: {q["answer"]}. {esc(correct)}</p>'
            f'<p>{esc(q["explanation"])}</p>'
            + (f'<p style="margin-bottom:0"><strong>References</strong></p><ul class="cites">{cites}</ul>' if cites else "")
            + "</details>"
            f'<p class="qstart"><a class="cta" href="/quiz/{test["slug"]}/#practice-10">Practice 10 random questions</a>'
            f'<a class="cta ghost" href="/quiz/{test["slug"]}/#practice-20">Practice 20</a></p>'
            + nav + _source_line(test, q)
            + '<div class="aff-slot" data-topic="test-prep"></div>'
            + _jsonld(ld) + SELF_CHECK_JS)
    return head(esc(title), esc(desc), rel="/", path=path, ads=True) + body + foot


PRACTICE_JS = r"""<script>
(function(){
  var D=JSON.parse(document.getElementById('qdata').textContent);
  var KEY='ocl:quiz:'+D.id, app=document.getElementById('qapp');
  var store={}; try{ store=JSON.parse(localStorage.getItem(KEY)||'{}')||{}; }catch(e){}
  function save(){ try{ localStorage.setItem(KEY,JSON.stringify(store)); }catch(e){} }
  function el(tag,cls,text){ var e=document.createElement(tag); if(cls) e.className=cls; if(text!=null) e.textContent=text; return e; }
  function shuffle(a){ for(var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=a[i]; a[i]=a[j]; a[j]=t; } return a; }
  var run=null;

  function progress(){
    var seen=0,right=0; D.q.forEach(function(q){ var r=store[q.n]; if(r!=null){ seen++; if(r===1) right++; } });
    var p=document.getElementById('qprog');
    p.textContent = seen ? ('Your progress on this device: '+seen+' of '+D.q.length+' questions answered, '+right+' correct on the latest try.')
                         : 'Your progress is saved on this device as you practice.';
    var mb=document.getElementById('qmissed'); var missed=D.q.filter(function(q){ return store[q.n]===0; }).length;
    mb.hidden=!missed; mb.textContent='Retry the '+missed+' I missed';
  }

  function start(pool,label){
    run={qs:shuffle(pool.slice()),i:0,answers:[],label:label};
    app.hidden=false; show(); app.scrollIntoView({behavior:'smooth',block:'start'});
  }

  function show(){
    var q=run.qs[run.i]; app.textContent='';
    var meta=el('div','qmeta'); meta.appendChild(el('span',null,run.label));
    meta.appendChild(el('span',null,'Question '+(run.i+1)+' of '+run.qs.length)); app.appendChild(meta);
    var bar=el('div','qbar'), fill=el('i'); fill.style.width=(100*run.i/run.qs.length)+'%'; bar.appendChild(fill); app.appendChild(bar);
    app.appendChild(el('p','qstem',q.stem));
    q.figs.forEach(function(f){
      var fig=el('figure','qfig'), a=el('a'), img=el('img');
      a.href=f.src; a.target='_blank'; a.rel='noopener';
      img.src=f.src; img.width=f.w; img.height=f.h; img.alt=f.cap; img.loading='lazy';
      a.appendChild(img); fig.appendChild(a); fig.appendChild(el('figcaption',null,f.cap+' Tap to enlarge.')); app.appendChild(fig);
    });
    var ol=el('ol','qch');
    Object.keys(q.ch).forEach(function(l){
      var li=el('li'), b=el('button','qbtn'); b.type='button'; b.setAttribute('data-l',l);
      b.appendChild(el('b',null,l+'.')); b.appendChild(el('span',null,q.ch[l]));
      b.addEventListener('click',function(){ pick(q,l,ol); });
      li.appendChild(b); ol.appendChild(li);
    });
    app.appendChild(ol);
  }

  function pick(q,l,ol){
    if(run.answers.length>run.i) return;
    var ok=l===q.a; run.answers.push({q:q,pick:l,ok:ok}); store[q.n]=ok?1:0; save();
    ol.querySelectorAll('.qbtn').forEach(function(b){
      b.disabled=true; var bl=b.getAttribute('data-l');
      if(bl===q.a) b.classList.add('right'); else if(bl===l) b.classList.add('wrong');
    });
    var exp=el('div','qexp');
    exp.appendChild(el('strong',null,(ok?'Correct. ':'Not quite: the answer is '+q.a+'. ')));
    exp.appendChild(document.createTextNode(q.x+' '));
    var more=el('a',null,'References and full question page'); more.href=q.url; exp.appendChild(more);
    app.appendChild(exp);
    var next=el('button','cta',run.i+1<run.qs.length?'Next question':'See my score'); next.type='button';
    next.style.marginTop='.8rem';
    next.addEventListener('click',function(){ run.i++; if(run.i<run.qs.length) show(); else finish(); });
    app.appendChild(next); next.focus({preventScroll:true});
    if(ok && typeof oclToken==='function' && oclToken()){
      oclReq('POST','/me/quiz',{test:D.id,n:q.n,answer:l}).catch(function(){});
    }
  }

  function finish(){
    var right=run.answers.filter(function(a){ return a.ok; }).length, n=run.answers.length;
    var pct=Math.round(100*right/n); app.textContent='';
    app.appendChild(el('p','qmeta',run.label));
    app.appendChild(el('p','qscore',right+' / '+n+' ('+pct+'%)'));
    app.appendChild(el('p',null, D.id==='p103' ? (pct>=70?'Nice work — you know your Part 103 limits.':'Review the rules below and try again.')
      : (pct>=70?'At or above the 70% the FAA requires to pass the knowledge test.':'Below the 70% the FAA requires to pass. Review the misses and try again.')));
    var wrong=run.answers.filter(function(a){ return !a.ok; });
    var row=el('p','qstart');
    var again=el('button','cta','New quiz'); again.type='button';
    again.addEventListener('click',function(){ app.hidden=true; document.getElementById('qhome').scrollIntoView({behavior:'smooth'}); });
    row.appendChild(again);
    if(wrong.length){
      var redo=el('button','cta ghost','Retry these '+wrong.length+' misses'); redo.type='button';
      redo.addEventListener('click',function(){ start(wrong.map(function(a){ return a.q; }),'Retrying misses'); });
      row.appendChild(redo);
    }
    app.appendChild(row);
    if(wrong.length){
      app.appendChild(el('h3',null,'Review the questions you missed'));
      wrong.forEach(function(a){
        var d=el('div','qrev');
        d.appendChild(el('p','qstem',a.q.stem));
        d.appendChild(el('p','you','Your answer: '+a.pick+'. '+a.q.ch[a.pick]));
        d.appendChild(el('p','ok','Correct: '+a.q.a+'. '+a.q.ch[a.q.a]));
        var x=el('p',null,a.q.x+' '); var m=el('a',null,'Full question'); m.href=a.q.url; x.appendChild(m); d.appendChild(x);
        app.appendChild(d);
      });
    }
    progress();
  }

  document.querySelectorAll('[data-size]').forEach(function(b){
    b.addEventListener('click',function(){
      var n=+b.getAttribute('data-size'); start(shuffle(D.q.slice()).slice(0,n), n>=D.q.length?'All questions':'Random '+n);
    });
  });
  document.getElementById('qmissed').addEventListener('click',function(){
    start(D.q.filter(function(q){ return store[q.n]===0; }),'Questions I missed');
  });
  document.getElementById('qreset').addEventListener('click',function(){ store={}; save(); progress(); });
  progress();
  var m=/^#practice-(\d+)$/.exec(location.hash);
  if(m){ var n=Math.min(+m[1],D.q.length); start(shuffle(D.q.slice()).slice(0,n),'Random '+n); }
})();
</script>
"""


def _landing_page(head, foot: str, test: dict, figs: dict) -> str:
    qs = test["questions"]
    data = {"id": test["id"], "q": [
        {"n": q["n"], "stem": q["stem"].replace("`", "'"), "ch": q["choices"], "a": q["answer"], "x": q["explanation"],
         "url": "/" + _qpath(test, q),
         "figs": [{"src": "/quiz/figures/" + figs[k]["file"], "w": figs[k]["w"], "h": figs[k]["h"],
                   "cap": figs[k]["caption"]} for k in q["figures"]]} for q in qs]}
    sizes = [n for n in SIZES if n < len(qs)] + [len(qs)]
    buttons = "".join(
        f'<button type="button" class="cta{"" if i == 0 else " ghost"}" data-size="{n}">'
        f'{"All " + str(n) if n == len(qs) else str(n) + " questions"}</button>' for i, n in enumerate(sizes))
    listing = "".join(f'<li><a href="/{_qpath(test, q)}">{esc(_short(q["stem"], 90))}</a></li>' for q in qs)
    if test["id"] == "p103":
        about = ("<p>These questions are our own, written from the text of "
                 f'<a href="{esc(test["url"])}" rel="noopener">14 CFR Part 103</a>. Part 103 has no knowledge test '
                 "and no pilot certificate, so knowing these limits is on you.</p>")
    else:
        sk = test.get("skipped") or []
        about = (f'<p>The {len(qs)} questions are the FAA\'s own published sample questions '
                 f'(<a href="{esc(test["url"])}" rel="noopener">{esc(test["source"])}</a>, a U.S. Government work). '
                 "The FAA does not publish answers, so each answer and explanation is ours, and each cites 14 CFR, "
                 "the AIM or an FAA handbook. Chart and table questions show the figure from the FAA testing "
                 "supplement FAA-CT-8080-2H."
                 + (f" We left out {len(sk)} sample question{'s' if len(sk) != 1 else ''} whose answer we could not "
                    "pin to a single choice from the FAA sources." if sk else "") + "</p>")
    title = f"Free {test['short']} practice test — {len(qs)} questions with answers"
    desc = f"{BLURB[test['id']]} Free practice: {len(qs)} questions with answers, explanations and FAA references."
    body = (QUIZ_CSS
            + f'<p class="crumbs"><a href="/quiz/">Test prep</a> &rsaquo; {esc(test["title"])}</p>'
            f'<h1>{esc(test["title"])} practice test</h1>'
            f'<p class="lede">{esc(BLURB[test["id"]])}</p>'
            f'<div id="qhome"><p class="qstart">{buttons}'
            f'<button type="button" class="cta ghost" id="qmissed" hidden></button></p>'
            f'<p class="src"><span id="qprog"></span> <button type="button" id="qreset" '
            f'style="font:inherit;background:none;border:0;color:var(--accent);cursor:pointer;padding:0;text-decoration:underline">'
            f'Reset</button></p></div>'
            f'<section class="qbox" id="qapp" hidden aria-live="polite"></section>'
            + about
            + '<p class="src">Signed in? Correct answers earn points on your '
              '<a href="/profile.html">profile</a> (capped per day).</p>'
            + '<div class="aff-slot" data-topic="test-prep"></div>'
            + f'<h2>All {len(qs)} questions</h2><ol class="qlist">{listing}</ol>'
            + '<script type="application/json" id="qdata">'
            + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"
            + PRACTICE_JS)
    return head(esc(title), esc(desc), rel="/", path=f"quiz/{test['slug']}/", ads=True) + body + foot


def _index_page(head, foot: str, tests: list[dict]) -> str:
    cards = "".join(
        f'<li><h2><a href="/quiz/{t["slug"]}/">{esc(t["title"])}</a></h2>'
        f'<p>{esc(BLURB[t["id"]])}</p><p class="src">{len(t["questions"])} questions &middot; '
        f'<a href="/quiz/{t["slug"]}/#practice-10">quick 10-question quiz</a></p></li>' for t in tests)
    total = sum(len(t["questions"]) for t in tests)
    body = (QUIZ_CSS
            + "<h1>Free pilot knowledge test practice</h1>"
            f'<p class="lede">Practice for the FAA Private Pilot, Sport Pilot and Part 107 Remote Pilot knowledge '
            f"tests, plus a Part 103 ultralight primer: {total} questions with answers, plain-English "
            "explanations and references to the regulations and FAA handbooks. No account needed.</p>"
            f'<ul class="qcards">{cards}</ul>'
            "<h2>Where the questions come from</h2>"
            "<p>The test questions are the FAA's published sample questions, and the charts and tables come from the "
            "FAA's own testing supplement (FAA-CT-8080-2H). Both are U.S. Government works in the public domain. "
            "The FAA publishes no answer key, so the answers and explanations here are ours, each with a reference "
            "you can check in 14 CFR, the AIM, or the handbooks in our "
            '<a href="/search.html">library</a>. Questions with no single answer we could ground in those sources '
            "were left out. Study material only: always check the current regulations.</p>"
            '<div class="aff-slot" data-topic="test-prep"></div>')
    return head("Free FAA knowledge test practice questions — Private, Sport, Part 107",
                "Free FAA knowledge test prep: Private Pilot, Sport Pilot and Part 107 Remote Pilot practice "
                "questions with answers, explanations and FAA references, plus a Part 103 ultralight primer.",
                rel="/", path="quiz/", ads=True) + body + foot


def write_quiz(out: Path, head, foot: str, src: Path = SRC) -> list[str]:
    """Write /quiz/ into the site at `out`; return the page paths for the sitemap."""
    if not (src / "figures.json").exists():
        return []
    foot = _absolute_links(foot)
    figs = json.loads((src / "figures.json").read_text(encoding="utf-8"))
    tests = [json.loads((src / f"{t}.json").read_text(encoding="utf-8")) for t in ORDER if (src / f"{t}.json").exists()]
    root = out / "quiz"
    (root / "figures").mkdir(parents=True, exist_ok=True)
    for f in figs.values():
        shutil.copy2(src / "figures" / f["file"], root / "figures" / f["file"])
    paths = ["quiz/"]
    (root / "index.html").write_text(_index_page(head, foot, tests), encoding="utf-8")
    for t in tests:
        d = root / t["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(_landing_page(head, foot, t, figs), encoding="utf-8")
        paths.append(f"quiz/{t['slug']}/")
        qs = t["questions"]
        for i, q in enumerate(qs):
            p = _qpath(t, q)
            (out / p).mkdir(parents=True, exist_ok=True)
            (out / p / "index.html").write_text(
                _question_page(head, foot, t, q, qs[i - 1] if i else None, qs[i + 1] if i + 1 < len(qs) else None, figs),
                encoding="utf-8")
            paths.append(p)
    return paths
