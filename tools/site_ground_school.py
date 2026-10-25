"""Ground school: free study courses for pilot knowledge tests, with the Aha Trivia games built in.

Source content lives in ground-school/<id>.json (tracked; format in ground-school/README.md).
Pages written:

  /ground-school/                     hub: every course, how to study, the game picker
  /ground-school/<id>/                course overview: the certificate, the tests, a study plan,
                                      the lessons with progress, the course's Aha Trivia game
  /ground-school/<id>/<lesson>/       one lesson: objectives, teaching, numbers, traps, readings,
                                      self-check questions, mark-complete
  /ground-school/<id>/print/          the whole course on one page, for printing or saving as PDF

The text is ours; every testable fact cites 14 CFR, the AIM, an ACS or an FAA handbook, which
are U.S. Government works we link to rather than copy. Progress is kept in this browser only
(localStorage "ocl:gs:<id>"), the same way the practice tests keep theirs.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

import aha_embed

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "ground-school"
LIBRARY_DOCS = {"faa-phak", "faa-awh", "faa-ifh", "faa-rmh", "faa-wb", "faa-pfh", "faa-wscfh",
                "faa-afh-8083-3c-ch2", "acs-private-airplane", "acs-instrument-airplane",
                "acs-commercial-airplane"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUIZ_SLUGS = {"private-pilot", "sport-pilot", "part-107", "part-103-ultralight"}


def esc(v: object) -> str:
    return escape("" if v is None else str(v), quote=True)


# --------------------------------------------------------------------------- validation

def validate(course: dict, name: str = "") -> list[str]:
    """Return every rule a course file breaks (empty list = valid). The build refuses invalid files."""
    errs: list[str] = []
    where = name or course.get("id", "?")

    def err(msg: str) -> None:
        errs.append(f"{where}: {msg}")

    def url_ok(u: object, ctx: str) -> None:
        if not isinstance(u, str) or not u.startswith("https://"):
            err(f"{ctx}: url must start with https:// (got {u!r})")

    def text(v: object, ctx: str) -> None:
        if not isinstance(v, str) or not v.strip():
            err(f"{ctx}: needs text")
        elif "<" in v and re.search(r"</?[a-zA-Z][^>]*>", v):
            err(f"{ctx}: plain text only, found HTML")

    for key in ("id", "title", "short", "summary", "who", "checked"):
        text(course.get(key), key)
    if not SLUG.match(str(course.get("id", ""))):
        err("id must be lowercase letters, digits and hyphens")
    if name and course.get("id") != name:
        err(f"id {course.get('id')!r} must match the file name {name!r}")
    if not isinstance(course.get("order"), int):
        err("order must be a whole number")
    aha = course.get("aha_course")
    if aha is not None and aha not in aha_embed.COURSES:
        err(f"aha_course {aha!r} is not a known Aha Trivia course")
    qs = course.get("quiz_slug")
    if qs is not None and qs not in QUIZ_SLUGS:
        err(f"quiz_slug {qs!r} is not an existing practice test")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(course.get("checked", ""))):
        err("checked must be a YYYY-MM-DD date")

    facts = course.get("facts") or []
    if not 3 <= len(facts) <= 10:
        err("facts: needs 3 to 10 items")
    for i, f in enumerate(facts):
        text(f.get("label"), f"facts[{i}].label")
        text(f.get("value"), f"facts[{i}].value")
        if f.get("cite"):
            url_ok(f["cite"].get("url"), f"facts[{i}].cite")
    for key in ("knowledge_test", "practical_test"):
        t = course.get(key)
        if t is None:
            continue
        if not isinstance(t, dict):
            err(f"{key}: must be an object or null")
            continue
        for i, n in enumerate(t.get("notes") or []):
            text(n, f"{key}.notes[{i}]")
        for i, c in enumerate(t.get("cites") or []):
            url_ok(c.get("url"), f"{key}.cites[{i}]")
        if t.get("url") is not None:
            url_ok(t["url"], f"{key}.url")
    for i, r in enumerate(course.get("requirements") or []):
        text(r.get("text"), f"requirements[{i}].text")
        if r.get("cite"):
            url_ok(r["cite"].get("url"), f"requirements[{i}].cite")
    if not course.get("requirements"):
        err("requirements: needs at least one item")

    mods = course.get("modules") or []
    if not 4 <= len(mods) <= 14:
        err(f"modules: needs 4 to 14 lessons (has {len(mods)})")
    ids: set[str] = set()
    for m in mods:
        mid = str(m.get("id", ""))
        ctx = f"module {mid or '?'}"
        if not SLUG.match(mid):
            err(f"{ctx}: id must be lowercase letters, digits and hyphens")
        if mid in ids:
            err(f"{ctx}: duplicate id")
        if mid == "print":
            err(f"{ctx}: 'print' is reserved for the printable page")
        ids.add(mid)
        text(m.get("title"), f"{ctx}.title")
        text(m.get("summary"), f"{ctx}.summary")
        if not m.get("objectives"):
            err(f"{ctx}: needs objectives")
        for i, o in enumerate(m.get("objectives") or []):
            text(o, f"{ctx}.objectives[{i}]")
        if not m.get("sections"):
            err(f"{ctx}: needs sections")
        for i, s in enumerate(m.get("sections") or []):
            text(s.get("heading"), f"{ctx}.sections[{i}].heading")
            if not s.get("points"):
                err(f"{ctx}.sections[{i}]: needs points")
            for j, p in enumerate(s.get("points") or []):
                text(p, f"{ctx}.sections[{i}].points[{j}]")
        for i, n in enumerate(m.get("numbers") or []):
            text(n.get("item"), f"{ctx}.numbers[{i}].item")
            text(n.get("value"), f"{ctx}.numbers[{i}].value")
        for i, t in enumerate(m.get("traps") or []):
            text(t, f"{ctx}.traps[{i}]")
        if not m.get("read"):
            err(f"{ctx}: needs readings")
        for i, r in enumerate(m.get("read") or []):
            text(r.get("label"), f"{ctx}.read[{i}].label")
            url_ok(r.get("url"), f"{ctx}.read[{i}]")
            lib = r.get("library")
            if lib is not None and (lib.get("doc") not in LIBRARY_DOCS or not lib.get("q")):
                err(f"{ctx}.read[{i}].library: unknown doc {lib.get('doc')!r} or empty q")
        checks = m.get("check") or []
        if not checks:
            err(f"{ctx}: needs self-check questions")
        for i, q in enumerate(checks):
            text(q.get("q"), f"{ctx}.check[{i}].q")
            text(q.get("why"), f"{ctx}.check[{i}].why")
            ch = q.get("choices") or []
            if not 3 <= len(ch) <= 4:
                err(f"{ctx}.check[{i}]: needs 3 or 4 choices")
            if len(set(map(str, ch))) != len(ch):
                err(f"{ctx}.check[{i}]: choices repeat")
            a = q.get("answer")
            if not isinstance(a, int) or not 0 <= a < len(ch):
                err(f"{ctx}.check[{i}]: answer index out of range")
    for i, step in enumerate(course.get("plan") or []):
        text(step.get("step"), f"plan[{i}].step")
        text(step.get("focus"), f"plan[{i}].focus")
        for mid in step.get("modules") or []:
            if mid not in ids:
                err(f"plan[{i}]: names unknown module {mid!r}")
    if not course.get("plan"):
        err("plan: needs at least one step")
    for key in ("test_day", "after"):
        for i, t in enumerate(course.get(key) or []):
            text(t, f"{key}[{i}]")
    return errs


def load(src: Path = SRC) -> list[dict]:
    """Load and validate every course; raise ValueError listing every problem."""
    courses, errs = [], []
    for p in sorted(src.glob("*.json")):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            errs.append(f"{p.stem}: not valid JSON ({e})")
            continue
        errs += validate(c, p.stem)
        courses.append(c)
    if errs:
        raise ValueError("ground-school content has problems:\n  " + "\n  ".join(errs))
    return sorted(courses, key=lambda c: (c["order"], c["id"]))


# --------------------------------------------------------------------------- page pieces

GS_CSS = """<style>
.crumbs{font-size:.86rem;color:var(--muted);margin:.4rem 0 .2rem}
.crumbs a{color:var(--muted)}
.gs-cards{list-style:none;padding:0;display:grid;gap:.9rem;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));margin:1rem 0}
.gs-cards li{margin:0;border:1px solid var(--line);border-radius:var(--radius);padding:1rem 1.1rem;background:var(--card);
 display:flex;flex-direction:column;gap:.35rem}
.gs-cards h2,.gs-cards h3{font-size:1.1rem;margin:0}
.gs-cards p{margin:0}
.gs-icon{font-size:1.7rem;line-height:1}
.gs-meta{font-size:.84rem;color:var(--muted)}
.gs-prog{height:6px;background:var(--line);border-radius:99px;overflow:hidden;margin:.35rem 0 0}
.gs-prog i{display:block;height:100%;background:var(--ok);width:0}
.gs-facts{width:100%;border-collapse:collapse;margin:.8rem 0;font-size:.95rem}
.gs-facts th,.gs-facts td{text-align:left;padding:.5rem .55rem;border-bottom:1px solid var(--line);vertical-align:top}
.gs-facts th{width:38%;font-weight:700}
.gs-cite{font-size:.8rem;color:var(--muted);display:block;margin-top:.15rem}
.gs-cite a{color:var(--muted)}
.gs-steps{counter-reset:s;list-style:none;padding:0;margin:.8rem 0;display:grid;gap:.55rem}
.gs-steps li{counter-increment:s;position:relative;padding:.7rem .9rem .7rem 3rem;border:1px solid var(--line);
 border-radius:var(--radius-sm);background:var(--card)}
.gs-steps li::before{content:counter(s);position:absolute;left:.85rem;top:.65rem;width:1.6rem;height:1.6rem;border-radius:50%;
 background:var(--accent);color:#fff;font-weight:800;display:grid;place-items:center;font-size:.85rem}
.gs-lessons{list-style:none;padding:0;margin:.8rem 0;display:grid;gap:.5rem}
.gs-lessons li{margin:0}
.gs-lessons a{display:flex;gap:.75rem;align-items:flex-start;padding:.75rem .9rem;border:1px solid var(--line);
 border-radius:var(--radius-sm);background:var(--card);color:var(--fg);text-decoration:none}
.gs-lessons a:hover{border-color:var(--accent-2)}
.gs-lessons .n{flex:none;width:1.9rem;height:1.9rem;border-radius:50%;display:grid;place-items:center;font-weight:800;
 background:var(--accent-weak);color:var(--accent)}
.gs-lessons .done .n{background:var(--ok);color:#fff}
.gs-lessons small{display:block;color:var(--muted)}
.gs-box{border:1px solid var(--line);border-radius:var(--radius);padding:1rem 1.1rem;margin:1.1rem 0;background:var(--card)}
.gs-box h2{margin-top:0;font-size:1.15rem}
.gs-obj li,.gs-list li{margin:.3rem 0}
.gs-sec h2{font-size:1.2rem;margin:1.6rem 0 .4rem}
.gs-sec p{line-height:1.6}
.gs-nums{width:100%;border-collapse:collapse;font-size:.93rem}
.gs-nums td{padding:.45rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
.gs-nums td:nth-child(2){font-weight:700;white-space:normal}
.gs-nums .cfr{font-size:.76rem;color:var(--muted);font-family:ui-monospace,Menlo,monospace}
.gs-traps li{margin:.35rem 0}
.gs-q{border-top:1px solid var(--line);padding:.9rem 0}
.gs-q:first-of-type{border-top:0}
.gs-q .qstem{font-weight:700;margin:0 0 .6rem}
.gs-q ol{list-style:none;padding:0;margin:0 0 .4rem;display:grid;gap:.45rem}
.gs-q li{margin:0}
.gs-btn{display:flex;gap:.6rem;align-items:flex-start;width:100%;text-align:left;font:inherit;color:var(--fg);
 background:var(--card);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:.6rem .8rem;cursor:pointer}
.gs-btn:hover{border-color:var(--accent-2)}
.gs-btn:disabled{cursor:default}
.gs-btn b{flex:none;min-width:1.3rem;color:var(--accent)}
.gs-btn.right{border-color:var(--ok);background:var(--ok-weak)}
.gs-btn.wrong{border-color:var(--warn);background:var(--warn-weak)}
.gs-why{margin:.5rem 0 0;padding:.65rem .8rem;border-radius:var(--radius-sm);background:var(--accent-weak)}
.gs-score{font-weight:700}
.gs-nav{display:flex;justify-content:space-between;gap:.6rem;flex-wrap:wrap;margin:1.4rem 0}
.gs-done{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;margin:1.2rem 0}
.gs-src{font-size:.82rem;color:var(--muted)}
.gs-actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:.9rem 0}
@media print{
 header.site,footer.site,.gs-actions,.gs-nav,.gs-done,.aha,.aff-slot,.ad-slot,.skip{display:none!important}
 .gs-box,.gs-lessons a{break-inside:avoid}
 .gs-print-lesson{break-before:page}
 a{color:inherit;text-decoration:none}
}
</style>
"""

CHECK_JS = """<script>
(function(){
  var root=document.getElementById('gs-check'); if(!root) return;
  var course=root.getAttribute('data-course'), lesson=root.getAttribute('data-lesson');
  var KEY='ocl:gs:'+course, total=root.querySelectorAll('.gs-q').length, answered=0, right=0;
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'{}')||{}; }catch(e){ return {}; } }
  function save(s){ try{ localStorage.setItem(KEY,JSON.stringify(s)); }catch(e){} }
  root.querySelectorAll('.gs-q').forEach(function(q){
    var ans=q.getAttribute('data-ans'), done=false;
    q.querySelectorAll('.gs-btn').forEach(function(b){
      b.addEventListener('click',function(){
        if(done) return; done=true; answered++;
        var pick=b.getAttribute('data-i'), ok=pick===ans; if(ok) right++;
        q.querySelectorAll('.gs-btn').forEach(function(x){
          x.disabled=true; if(x.getAttribute('data-i')===ans) x.classList.add('right');
        });
        if(!ok) b.classList.add('wrong');
        var w=q.querySelector('.gs-why'); w.hidden=false;
        w.querySelector('strong').textContent=ok?'Correct. ':'Not quite. ';
        if(answered===total){
          var s=load(); s.checks=s.checks||{}; s.checks[lesson]=[right,total]; save(s);
          var out=document.getElementById('gs-score');
          out.textContent='You got '+right+' of '+total+' right.'+(right===total?' Nice work.':' Read the explanations, then try the lesson again later.');
          out.hidden=false;
          if(window.oclTrack) oclTrack('lesson-check',{course:course,lesson:lesson,score:right+'/'+total});
        }
      });
    });
  });
})();
(function(){
  var btn=document.getElementById('gs-mark'); if(!btn) return;
  var course=btn.getAttribute('data-course'), lesson=btn.getAttribute('data-lesson'), KEY='ocl:gs:'+course;
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'{}')||{}; }catch(e){ return {}; } }
  function paint(){ var d=(load().done||{})[lesson]; btn.textContent=d?'Lesson complete \\u2713 (tap to undo)':'Mark this lesson complete';
    btn.setAttribute('aria-pressed',d?'true':'false'); }
  btn.addEventListener('click',function(){
    var s=load(); s.done=s.done||{};
    if(s.done[lesson]) delete s.done[lesson]; else { s.done[lesson]=Date.now(); if(window.oclTrack) oclTrack('lesson-complete',{course:course,lesson:lesson}); }
    try{ localStorage.setItem(KEY,JSON.stringify(s)); }catch(e){}
    paint();
  });
  paint();
})();
</script>
"""

PROGRESS_JS = """<script>
(function(){
  document.querySelectorAll('[data-gs-course]').forEach(function(el){
    var course=el.getAttribute('data-gs-course'), s={};
    try{ s=JSON.parse(localStorage.getItem('ocl:gs:'+course)||'{}')||{}; }catch(e){}
    var done=s.done||{}, n=0;
    el.querySelectorAll('[data-gs-lesson]').forEach(function(li){
      if(done[li.getAttribute('data-gs-lesson')]){ li.classList.add('done'); n++;
        var t=li.querySelector('.n'); if(t){ t.textContent='\\u2713'; t.setAttribute('aria-label','complete'); } }
    });
    var total=+el.getAttribute('data-gs-total')||0;
    if(!total) total=el.querySelectorAll('[data-gs-lesson]').length;
    for(var k in done){ if(!el.querySelector('[data-gs-lesson]')) n++; }
    var bar=el.querySelector('.gs-prog i'); if(bar) bar.style.width=(total?100*Math.min(n,total)/total:0)+'%';
    var txt=el.querySelector('[data-gs-count]');
    if(txt) txt.textContent=n?(Math.min(n,total)+' of '+total+' lessons complete on this device'):(total+' lessons');
  });
})();
</script>
"""


def _cite(c: dict | None) -> str:
    if not c:
        return ""
    return f'<span class="gs-cite"><a href="{esc(c["url"])}" rel="noopener">{esc(c["label"])}</a></span>'


def _read_item(r: dict) -> str:
    s = f'<li><a href="{esc(r["url"])}" rel="noopener">{esc(r["label"])}</a>'
    lib = r.get("library")
    if lib:
        s += (f' &middot; <a href="/search.html?doc={esc(lib["doc"])}&amp;q={esc(lib["q"])}">'
              f'search it in our library</a>')
    return s + "</li>"


def _jsonld(obj: dict) -> str:
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>")


def _lesson_path(c: dict, m: dict) -> str:
    return f"ground-school/{c['id']}/{m['id']}/"


def _quiz_link(c: dict, cls: str = "cta ghost") -> str:
    if not c.get("quiz_slug"):
        return ""
    return f'<a class="{cls}" href="/quiz/{esc(c["quiz_slug"])}/">FAA sample-question practice test</a>'


DISCLAIMER = ('<p class="gs-src">Study material, not an authority. The text is ours and was checked against the '
              'sources on {checked}. Regulations, tests and standards change: confirm anything that matters in the '
              'current 14 CFR (eCFR), the AIM and the FAA handbooks, and with your instructor. Found a mistake? '
              'Tell us on the <a href="/contact.html">contact page</a>.</p>')


def _hub_page(head, foot: str, courses: list[dict], base: str) -> str:
    cards = ""
    for c in courses:
        n = len(c["modules"])
        cards += (f'<li data-gs-course="{esc(c["id"])}" data-gs-total="{n}"><span class="gs-icon" aria-hidden="true">'
                  f'{c["icon"]}</span><h2><a href="/ground-school/{esc(c["id"])}/">{esc(c["title"])}</a></h2>'
                  f'<p>{esc(c["summary"])}</p><p class="gs-meta" data-gs-count>{n} lessons</p>'
                  f'<div class="gs-prog" aria-hidden="true"><i></i></div></li>')
    steps = ("<li><strong>Pick your course</strong> and read the overview: what the certificate allows, "
             "what the tests look like and what you need first.</li>"
             "<li><strong>Work through the lessons in order.</strong> Each one ends with self-check questions "
             "and the official readings behind it.</li>"
             "<li><strong>Play the Aha Trivia game</strong> for that test a few minutes a day. Short cards "
             "with the answer explained are a painless way to keep facts fresh.</li>"
             "<li><strong>Take the FAA sample-question practice tests</strong> until you score well above "
             "the 70% pass mark, every time.</li>"
             "<li><strong>Get your endorsement and book the test.</strong> Each course ends with a test-day "
             "checklist.</li>")
    total = sum(len(c["modules"]) for c in courses)
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Open Checklists ground school",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{base}/ground-school/{c['id']}/",
                               "name": c["title"]} for i, c in enumerate(courses)]}
    body = (GS_CSS
            + "<h1>Free ground school</h1>"
            f'<p class="lede">Complete, free study courses for pilot knowledge tests: {len(courses)} courses and '
            f"{total} lessons, from Part 103 ultralights to the commercial certificate. Every lesson teaches in "
            "plain English, cites the regulation or FAA handbook behind each fact, and ends with self-check "
            "questions. No account needed; your progress stays on this device.</p>"
            f'<ul class="gs-cards">{cards}</ul>'
            "<h2>How to use ground school</h2>"
            f'<ol class="gs-steps">{steps}</ol>'
            + aha_embed.game_picker()
            + "<h2>More free study tools</h2>"
            '<ul class="gs-list"><li><a href="/quiz/">FAA sample-question practice tests</a>: Private, Sport, '
            "Part 107 and a Part 103 primer, with answers and references.</li>"
            '<li><a href="/training.html">Training hub</a>: the free FAA handbooks, and progress toward a '
            "certificate computed from your logbook.</li>"
            '<li><a href="/search.html">Library search</a>: full text of the FAA handbooks, cited by page.</li></ul>'
            + DISCLAIMER.format(checked=esc(max(c["checked"] for c in courses)))
            + '<div class="aff-slot" data-topic="test-prep"></div>'
            + _jsonld(ld) + PROGRESS_JS)
    return head("Free pilot ground school: Part 103, Part 107, Sport, Private, Instrument, Commercial",
                "Free online ground school for FAA pilot knowledge tests: plain-English lessons with references, "
                "self-check questions, study plans, test-day checklists and Aha Trivia practice games.",
                rel="/", path="ground-school/", ads=True) + body + foot


def _test_box(c: dict) -> str:
    kt, pt = c.get("knowledge_test"), c.get("practical_test")
    out = ""
    if kt:
        cites = " ".join(_cite(x) for x in kt.get("cites") or [])
        rows = "".join(f"<tr><th>{lab}</th><td>{esc(val)}</td></tr>" for lab, val in (
            ("Test code", kt.get("code")), ("Questions", kt.get("questions")),
            ("Time allowed", f'{kt["minutes"]} minutes' if kt.get("minutes") else None),
            ("Passing score", kt.get("passing"))) if val)
        notes = "".join(f"<li>{esc(n)}</li>" for n in kt.get("notes") or [])
        out += (f'<section class="gs-box"><h2>The knowledge test</h2><table class="gs-facts">{rows}</table>'
                + (f'<ul class="gs-list">{notes}</ul>' if notes else "") + cites + "</section>")
    if pt:
        notes = "".join(f"<li>{esc(n)}</li>" for n in pt.get("notes") or [])
        std = esc(pt.get("standard"))
        if pt.get("url"):
            std = f'<a href="{esc(pt["url"])}" rel="noopener">{std}</a>'
        out += (f'<section class="gs-box"><h2>The practical test (checkride)</h2>'
                f'<p>Conducted against the {std}.</p>' + (f'<ul class="gs-list">{notes}</ul>' if notes else "")
                + "</section>")
    return out


def _course_page(head, foot: str, c: dict, base: str) -> str:
    cid = c["id"]
    facts = "".join(f'<tr><th>{esc(f["label"])}</th><td>{esc(f["value"])}{_cite(f.get("cite"))}</td></tr>'
                    for f in c["facts"])
    reqs = "".join(f'<li>{esc(r["text"])}{_cite(r.get("cite"))}</li>' for r in c["requirements"])
    titles = {m["id"]: m["title"] for m in c["modules"]}
    plan = "".join(
        f'<li><strong>{esc(s["step"])}:</strong> {esc(s["focus"])}'
        + (" <span class=\"gs-meta\">Lessons: " + ", ".join(
            f'<a href="/{_lesson_path(c, {"id": mid})}">{esc(titles[mid])}</a>' for mid in s.get("modules") or [])
           + "</span>" if s.get("modules") else "") + "</li>" for s in c["plan"])
    lessons = "".join(
        f'<li data-gs-lesson="{esc(m["id"])}"><a href="/{_lesson_path(c, m)}"><span class="n">{i + 1}</span>'
        f'<span><strong>{esc(m["title"])}</strong><small>{esc(m["summary"])}</small></span></a></li>'
        for i, m in enumerate(c["modules"]))
    test_day = "".join(f"<li>{esc(t)}</li>" for t in c.get("test_day") or [])
    after = "".join(f"<li>{esc(t)}</li>" for t in c.get("after") or [])
    first = c["modules"][0]
    actions = (f'<p class="gs-actions"><a class="cta" href="/{_lesson_path(c, first)}">Start lesson 1</a>'
               + (f'<a class="cta ghost" href="#play">Play the game</a>' if c.get("aha_course") else "")
               + _quiz_link(c)
               + f'<a class="cta ghost" href="/ground-school/{esc(cid)}/print/">Print the full course</a></p>')
    game = (aha_embed.game_section(c["aha_course"], heading=f"Practice for the {c['short']} test with Aha Trivia")
            if c.get("aha_course") else "")
    ld = {"@context": "https://schema.org", "@type": "Course", "name": f"{c['title']} ground school",
          "description": c["summary"], "url": f"{base}/ground-school/{cid}/", "isAccessibleForFree": True,
          "inLanguage": "en-US",
          "provider": {"@type": "Organization", "name": "Open Checklists", "url": base or "https://openchecklists.net"},
          "hasPart": [{"@type": "LearningResource", "name": m["title"],
                       "url": f"{base}/{_lesson_path(c, m)}"} for m in c["modules"]]}
    body = (GS_CSS
            + f'<p class="crumbs"><a href="/ground-school/">Ground school</a> &rsaquo; {esc(c["title"])}</p>'
            f'<h1>{c["icon"]} {esc(c["title"])} ground school</h1>'
            f'<p class="lede">{esc(c["summary"])}</p>' + actions
            + f'<p>{esc(c["who"])}</p>'
            f'<table class="gs-facts">{facts}</table>'
            + _test_box(c)
            + f'<section class="gs-box"><h2>What you need</h2><ul class="gs-list">{reqs}</ul></section>'
            f'<section data-gs-course="{esc(cid)}" data-gs-total="{len(c["modules"])}">'
            f'<h2 id="lessons">The lessons</h2><p class="gs-meta" data-gs-count>{len(c["modules"])} lessons</p>'
            f'<div class="gs-prog" aria-hidden="true"><i></i></div><ol class="gs-lessons">{lessons}</ol></section>'
            f'<h2 id="plan">Study plan</h2><ol class="gs-steps">{plan}</ol>'
            + game
            + (f'<section class="gs-box"><h2>Test day checklist</h2><ul class="gs-list">{test_day}</ul></section>'
               if test_day else "")
            + (f'<section class="gs-box"><h2>After you pass</h2><ul class="gs-list">{after}</ul></section>'
               if after else "")
            + DISCLAIMER.format(checked=esc(c["checked"]))
            + '<div class="aff-slot" data-topic="test-prep"></div>'
            + _jsonld(ld) + PROGRESS_JS)
    title = f"{c['title']} ground school: free lessons, study plan and practice"
    desc = (f"{c['summary']} {len(c['modules'])} free lessons with references, self-check questions, a study "
            "plan and a test-day checklist.")
    return head(esc(title), esc(desc), rel="/", path=f"ground-school/{cid}/", ads=True) + body + foot


def _lesson_body(c: dict, m: dict, interactive: bool = True) -> str:
    """The teaching part of a lesson, shared by the lesson page and the printable course."""
    objectives = "".join(f"<li>{esc(o)}</li>" for o in m["objectives"])
    secs = "".join(f'<h2>{esc(s["heading"])}</h2>' + "".join(f"<p>{esc(p)}</p>" for p in s["points"])
                   for s in m["sections"])
    nums = "".join(f'<tr><td>{esc(n["item"])}</td><td>{esc(n["value"])}</td>'
                   f'<td class="cfr">{esc(n.get("cite", ""))}</td></tr>' for n in m.get("numbers") or [])
    traps = "".join(f"<li>{esc(t)}</li>" for t in m.get("traps") or [])
    reads = "".join(_read_item(r) for r in m["read"])
    out = (f'<section class="gs-box"><h2>In this lesson you will learn to</h2><ul class="gs-obj">{objectives}</ul></section>'
           f'<div class="gs-sec">{secs}</div>')
    if nums:
        out += (f'<section class="gs-box"><h2>Numbers to know</h2><table class="gs-nums">'
                f'<tbody>{nums}</tbody></table></section>')
    if traps:
        out += f'<section class="gs-box"><h2>Common test traps</h2><ul class="gs-traps">{traps}</ul></section>'
    out += f'<section class="gs-box"><h2>Read the source</h2><ul class="gs-list">{reads}</ul></section>'
    letters = "ABCD"
    if interactive:
        qs = ""
        for i, q in enumerate(m["check"]):
            ch = "".join(f'<li><button type="button" class="gs-btn" data-i="{j}"><b>{letters[j]}.</b>'
                         f'<span>{esc(t)}</span></button></li>' for j, t in enumerate(q["choices"]))
            cite = f' <span class="gs-cite">Reference: {esc(q["cite"])}</span>' if q.get("cite") else ""
            qs += (f'<div class="gs-q" data-ans="{q["answer"]}"><p class="qstem">{i + 1}. {esc(q["q"])}</p>'
                   f'<ol>{ch}</ol><p class="gs-why" hidden><strong></strong>The answer is '
                   f'{letters[q["answer"]]}. {esc(q["why"])}{cite}</p></div>')
        out += (f'<section class="gs-box" id="gs-check" data-course="{esc(c["id"])}" data-lesson="{esc(m["id"])}">'
                f'<h2>Check yourself</h2>{qs}<p class="gs-score" id="gs-score" role="status" hidden></p></section>')
    else:
        qs = "".join(f'<li><p>{esc(q["q"])}</p><ol type="A">'
                     + "".join(f"<li>{esc(t)}</li>" for t in q["choices"]) + "</ol></li>" for q in m["check"])
        key = "".join(f'<li>{letters[q["answer"]]}. {esc(q["why"])}</li>' for q in m["check"])
        out += (f'<section class="gs-box"><h2>Check yourself</h2><ol>{qs}</ol>'
                f'<p><strong>Answers</strong></p><ol>{key}</ol></section>')
    return out


def _lesson_page(head, foot: str, c: dict, i: int, base: str) -> str:
    m = c["modules"][i]
    prev_m = c["modules"][i - 1] if i else None
    next_m = c["modules"][i + 1] if i + 1 < len(c["modules"]) else None
    nav = '<div class="gs-nav">'
    nav += (f'<a href="/{_lesson_path(c, prev_m)}">&larr; {esc(prev_m["title"])}</a>' if prev_m else "<span></span>")
    nav += f'<a href="/ground-school/{esc(c["id"])}/#lessons">All {esc(c["short"])} lessons</a>'
    nav += (f'<a href="/{_lesson_path(c, next_m)}">{esc(next_m["title"])} &rarr;</a>' if next_m else "<span></span>")
    nav += "</div>"
    game = (aha_embed.game_facade(c["aha_course"], f"Practice {c['short']} questions with Aha Trivia")
            if c.get("aha_course") else "")
    done = (f'<div class="gs-done"><button type="button" class="cta" id="gs-mark" aria-pressed="false" '
            f'data-course="{esc(c["id"])}" data-lesson="{esc(m["id"])}">Mark this lesson complete</button>'
            + _quiz_link(c) + "</div>")
    ld = {"@context": "https://schema.org", "@type": "LearningResource", "name": f"{m['title']} ({c['short']})",
          "description": m["summary"], "url": f"{base}/{_lesson_path(c, m)}", "learningResourceType": "Lesson",
          "isAccessibleForFree": True, "inLanguage": "en-US", "teaches": m["objectives"],
          "isPartOf": {"@type": "Course", "name": f"{c['title']} ground school",
                       "url": f"{base}/ground-school/{c['id']}/"}}
    body = (GS_CSS
            + f'<p class="crumbs"><a href="/ground-school/">Ground school</a> &rsaquo; '
            f'<a href="/ground-school/{esc(c["id"])}/">{esc(c["title"])}</a> &rsaquo; Lesson {i + 1}</p>'
            f'<h1>{esc(m["title"])}</h1>'
            f'<p class="lede">{esc(m["summary"])}</p>'
            f'<p class="gs-meta">{esc(c["title"])} ground school, lesson {i + 1} of {len(c["modules"])}</p>'
            + _lesson_body(c, m) + done + game + nav
            + DISCLAIMER.format(checked=esc(c["checked"]))
            + '<div class="aff-slot" data-topic="test-prep"></div>'
            + _jsonld(ld) + CHECK_JS)
    title = f"{m['title']}: {c['short']} ground school lesson {i + 1}"
    desc = f"{m['summary']} Free {c['short']} lesson with references and self-check questions."
    return head(esc(title), esc(desc), rel="/", path=_lesson_path(c, m), ads=True) + body + foot


def _print_page(head, foot: str, c: dict) -> str:
    toc = "".join(f'<li><a href="#l-{esc(m["id"])}">{esc(m["title"])}</a></li>' for m in c["modules"])
    facts = "".join(f'<tr><th>{esc(f["label"])}</th><td>{esc(f["value"])}'
                    + (f' <span class="gs-cite">{esc(f["cite"]["label"])}</span>' if f.get("cite") else "")
                    + "</td></tr>" for f in c["facts"])
    reqs = "".join(f'<li>{esc(r["text"])}' + (f' ({esc(r["cite"]["label"])})' if r.get("cite") else "") + "</li>"
                   for r in c["requirements"])
    plan = "".join(f'<li><strong>{esc(s["step"])}:</strong> {esc(s["focus"])}</li>' for s in c["plan"])
    lessons = "".join(
        f'<section class="gs-print-lesson" id="l-{esc(m["id"])}"><h1>Lesson {i + 1}: {esc(m["title"])}</h1>'
        f'<p class="lede">{esc(m["summary"])}</p>' + _lesson_body(c, m, interactive=False) + "</section>"
        for i, m in enumerate(c["modules"]))
    test_day = "".join(f"<li>{esc(t)}</li>" for t in c.get("test_day") or [])
    body = (GS_CSS
            + f'<p class="crumbs gs-actions"><a href="/ground-school/{esc(c["id"])}/">&larr; Back to the course</a>'
            '<button type="button" class="cta" onclick="window.print()">Print or save as PDF</button></p>'
            f'<h1>{esc(c["title"])} ground school</h1><p class="lede">{esc(c["summary"])}</p>'
            f'<p>{esc(c["who"])}</p><table class="gs-facts">{facts}</table>'
            + _test_box(c)
            + f'<h2>What you need</h2><ul class="gs-list">{reqs}</ul>'
            f'<h2>Study plan</h2><ol>{plan}</ol><h2>Lessons</h2><ol>{toc}</ol>'
            + lessons
            + (f'<section class="gs-print-lesson"><h1>Test day checklist</h1><ul class="gs-list">{test_day}</ul>'
               "</section>" if test_day else "")
            + DISCLAIMER.format(checked=esc(c["checked"]))
            + f'<p class="gs-src">From openchecklists.net/ground-school/{esc(c["id"])}/ (free, CC BY 4.0).</p>')
    page = head(esc(f"{c['title']} ground school (printable)"), esc(c["summary"]), rel="/",
                path=f"ground-school/{c['id']}/print/")
    page = page.replace("<head>", '<head>\n<meta name="robots" content="noindex,follow">', 1)
    return page + body + foot


def write_ground_school(out: Path, head, foot: str, src: Path = SRC, base: str = "") -> list[str]:
    """Write /ground-school/ into the site at `out`; return the indexable page paths for the sitemap."""
    if not src.is_dir() or not any(src.glob("*.json")):
        return []
    courses = load(src)
    foot = re.sub(r'href="(?![/#]|https?:|mailto:)', 'href="/', foot)
    root = out / "ground-school"
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(_hub_page(head, foot, courses, base), encoding="utf-8")
    paths = ["ground-school/"]
    for c in courses:
        d = root / c["id"]
        (d / "print").mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(_course_page(head, foot, c, base), encoding="utf-8")
        (d / "print" / "index.html").write_text(_print_page(head, foot, c), encoding="utf-8")
        paths.append(f"ground-school/{c['id']}/")
        for i, m in enumerate(c["modules"]):
            (d / m["id"]).mkdir(parents=True, exist_ok=True)
            (d / m["id"] / "index.html").write_text(_lesson_page(head, foot, c, i, base), encoding="utf-8")
            paths.append(_lesson_path(c, m))
    return paths
