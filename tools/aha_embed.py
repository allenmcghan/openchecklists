"""Aha Trivia pilot games, embedded with the Aha game engine's own embed mode.

Aha Trivia (ahatrivia.com) is a sister project. Its game engine plays one course inside an
iframe when the page is framed or the URL carries ?embed=1: no sign-in, scores stay on the
player's device, nothing is shared with the host page, and its links open ahatrivia.com in a
new tab. The embed code and the rules come from https://ahatrivia.com/embed/.

Each test course plays its first 50 cards free; the rest are part of Aha Trivia Premium on
ahatrivia.com. We say so next to every game, so nobody is surprised.
"""
from __future__ import annotations

from html import escape

AHA_BASE = "https://ahatrivia.com"

# id = the Aha Trivia course id (content/editions/<id>.yaml in the Aha Trivia repository).
COURSES: dict[str, dict] = {
    "pilot": {"name": "Private Pilot", "icon": "✈️", "title": "Stuff Every Private Pilot Should Know",
              "about": "FAA Private Pilot Airplane knowledge test: regulations, weather, airspace, "
                       "aerodynamics, navigation and systems."},
    "sport-pilot": {"name": "Sport Pilot", "icon": "🪂", "title": "Stuff Every Sport Pilot Should Know",
                    "about": "FAA Sport Pilot knowledge test, plus ultralight (Part 103) basics."},
    "drone": {"name": "Part 107 Drone", "icon": "🚁", "title": "Stuff Every Drone Pilot Should Know",
              "about": "FAA Part 107 Remote Pilot knowledge test: airspace, waivers, Remote ID, "
                       "weather and charts."},
    "instrument": {"name": "Instrument Rating", "icon": "🌫️", "title": "Stuff Every Instrument Pilot Should Know",
                   "about": "FAA Instrument Rating Airplane knowledge test: approaches, IFR charts, "
                            "clearances and IFR weather."},
    "commercial": {"name": "Commercial Pilot", "icon": "🛩️", "title": "Stuff Every Commercial Pilot Should Know",
                   "about": "FAA Commercial Pilot Airplane knowledge test: commercial rules, "
                            "performance, systems and maneuvers."},
    "aerospace": {"name": "Aerospace Explorer", "icon": "🚀", "title": "Stuff Every Aerospace Explorer Should Know",
                  "about": "Flight, weather, rockets and space for curious young aviators and cadets "
                           "(about 11 and up)."},
}
ORDER = ["pilot", "sport-pilot", "drone", "instrument", "commercial", "aerospace"]

EMBED_CSS = """<style>
.aha{border:1px solid var(--line);border-radius:var(--radius,16px);background:var(--card,#fff);
 padding:1rem;margin:1.4rem 0;box-shadow:var(--shadow-sm,none)}
.aha h2,.aha h3{margin:.1rem 0 .3rem}
.aha-grid{display:grid;gap:1rem;align-items:start}
@media(min-width:860px){.aha-grid{grid-template-columns:minmax(0,1fr) 480px}}
.aha-frame{width:100%;max-width:480px;height:680px;border:0;border-radius:16px;display:block;margin:0 auto;
 background:var(--accent-weak,#eef4fb)}
.aha-note{font-size:.84rem;color:var(--muted)}
.aha-tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 .8rem}
.aha-tab{font:inherit;font-size:.86rem;padding:.42rem .75rem;border:1.5px solid var(--line);border-radius:999px;
 background:var(--card,#fff);color:var(--fg);cursor:pointer}
.aha-tab[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.aha-tab:focus-visible,.aha-start:focus-visible{outline:3px solid var(--accent-2,#2a7ab8);outline-offset:2px}
.aha-face{max-width:480px;margin:0 auto;border-radius:16px;padding:1.4rem 1.2rem;text-align:center;
 background:linear-gradient(160deg,#10304f,#1f4e79 60%,#2a7ab8);color:#fff}
.aha-face p{color:#e5eef7;margin:.4rem 0 1rem}
.aha-face .aha-big{font-size:2.4rem;line-height:1}
.aha-start{font:inherit;font-weight:800;border:0;border-radius:999px;padding:.7rem 1.3rem;cursor:pointer;
 background:#ffb547;color:#10243a}
@media print{.aha{display:none!important}}
</style>
"""


def esc(v: object) -> str:
    return escape("" if v is None else str(v), quote=True)


def play_url(course: str, embed: bool = True) -> str:
    return f"{AHA_BASE}/play/?course={course}" + ("&embed=1" if embed else "")


def iframe(course: str, lazy: bool = True) -> str:
    """The Aha Trivia embed code for one course (the same markup ahatrivia.com/embed/ hands out)."""
    c = COURSES[course]
    return (f'<iframe class="aha-frame" src="{esc(play_url(course))}" '
            f'title="{esc(c["title"])} (Aha Trivia game)" width="100%" height="680"'
            f'{" loading=" + chr(34) + "lazy" + chr(34) if lazy else ""} '
            f'allow="clipboard-write; web-share" data-aha-course="{esc(course)}"></iframe>')


def _note() -> str:
    return (f'<p class="aha-note">The game runs on <a href="{AHA_BASE}/" '
            f'target="_blank" rel="noopener">Aha Trivia</a>, our sister project. No sign-up: your score is '
            f'saved on this device and nothing is shared with Open Checklists. The first 50 cards of each '
            f'test are free; the rest are part of Aha Trivia Premium.</p>')


def game_section(course: str, heading: str = "Practice with the Aha Trivia game", intro: str = "",
                 hid: str = "play") -> str:
    """One course, loaded lazily when it scrolls near the screen."""
    c = COURSES[course]
    lead = intro or f"{c['title']}. {c['about']} Answer a card, read why it is right, and build a streak."
    return (EMBED_CSS
            + f'<section class="aha" id="{esc(hid)}" aria-labelledby="{esc(hid)}-h"><div class="aha-grid"><div>'
            f'<h2 id="{esc(hid)}-h">{c["icon"]} {esc(heading)}</h2><p>{esc(lead)}</p>'
            + _note()
            + f'<p class="aha-note"><a href="{esc(play_url(course, embed=False))}" target="_blank" rel="noopener">'
            f'Open the game full screen</a> (new tab).</p></div><div>'
            + iframe(course) + "</div></div></section>")


FACADE_JS = """<script>
(function(){
  document.querySelectorAll('[data-aha-load]').forEach(function(btn){
    btn.addEventListener('click',function(){
      var box=document.getElementById(btn.getAttribute('data-aha-load')); if(!box) return;
      var tpl=box.querySelector('template'); if(!tpl) return;
      box.innerHTML=tpl.innerHTML;
      var f=box.querySelector('iframe'); if(f){ f.focus({preventScroll:true}); }
      if(window.oclTrack) oclTrack('aha-game-open',{course:btn.getAttribute('data-course'),where:'lesson'});
    });
  });
})();
</script>
"""


def game_facade(course: str, heading: str, hid: str = "play") -> str:
    """One course behind a Start button, for lesson pages: the game loads only when asked for."""
    c = COURSES[course]
    box = f"{hid}-box"
    return (EMBED_CSS
            + f'<section class="aha" id="{esc(hid)}" aria-labelledby="{esc(hid)}-h">'
            f'<h2 id="{esc(hid)}-h">{c["icon"]} {esc(heading)}</h2>'
            f'<div id="{esc(box)}"><div class="aha-face"><div class="aha-big" aria-hidden="true">{c["icon"]}</div>'
            f'<p><strong>{esc(c["title"])}</strong><br>Quick question cards from Aha Trivia. Play a few right here.</p>'
            f'<button type="button" class="aha-start" data-aha-load="{esc(box)}" data-course="{esc(course)}">'
            f'Start the game</button></div><template>{iframe(course, lazy=False)}</template></div>'
            + _note() + "</section>" + FACADE_JS)


PICKER_JS = """<script>
(function(){
  var root=document.getElementById('aha-picker'); if(!root) return;
  var frame=root.querySelector('iframe'), name=root.querySelector('[data-aha-name]'),
      about=root.querySelector('[data-aha-about]'), full=root.querySelector('[data-aha-full]');
  root.querySelectorAll('.aha-tab').forEach(function(b){
    b.addEventListener('click',function(){
      root.querySelectorAll('.aha-tab').forEach(function(x){ x.setAttribute('aria-pressed', x===b?'true':'false'); });
      frame.src=b.getAttribute('data-src'); frame.title=b.getAttribute('data-title')+' (Aha Trivia game)';
      frame.setAttribute('data-aha-course', b.getAttribute('data-course'));
      name.textContent=b.getAttribute('data-title'); about.textContent=b.getAttribute('data-about');
      full.href=b.getAttribute('data-full');
      if(window.oclTrack) oclTrack('aha-game-open',{course:b.getAttribute('data-course'),where:'picker'});
    });
  });
})();
</script>
"""


def game_picker(courses: list[str] | None = None, heading: str = "Play the Aha Trivia pilot games",
                first: str | None = None) -> str:
    """Every pilot course behind one set of tabs and one iframe, so the page loads a single game."""
    ids = [c for c in (courses or ORDER) if c in COURSES]
    first = first if first in ids else ids[0]
    tabs = "".join(
        f'<button type="button" class="aha-tab" aria-pressed="{"true" if cid == first else "false"}" '
        f'data-course="{esc(cid)}" data-src="{esc(play_url(cid))}" data-full="{esc(play_url(cid, embed=False))}" '
        f'data-title="{esc(COURSES[cid]["title"])}" data-about="{esc(COURSES[cid]["about"])}">'
        f'{COURSES[cid]["icon"]} {esc(COURSES[cid]["name"])}</button>' for cid in ids)
    c = COURSES[first]
    return (EMBED_CSS
            + '<section class="aha" id="aha-picker" aria-labelledby="aha-picker-h"><div class="aha-grid"><div>'
            f'<h2 id="aha-picker-h">{esc(heading)}</h2>'
            '<p>Pick a test. Each game serves short question cards with the answer explained, so a few '
            'minutes a day adds up.</p>'
            f'<div class="aha-tabs" role="group" aria-label="Choose a pilot game">{tabs}</div>'
            f'<p><strong data-aha-name>{esc(c["title"])}</strong><br><span data-aha-about>{esc(c["about"])}</span></p>'
            + _note()
            + f'<p class="aha-note"><a data-aha-full href="{esc(play_url(first, embed=False))}" target="_blank" '
            'rel="noopener">Open this game full screen</a> (new tab).</p></div><div>'
            + iframe(first) + "</div></div></section>" + PICKER_JS)
