"""Exercise ground school and the embedded Aha Trivia games in a real browser.

    python3 tests/e2e/ground_school_e2e.py [BASE]     # default http://127.0.0.1:8790

No sign-in and no email. Checks, desktop and phone:
- the hub lists every course and its game picker switches the embedded game;
- a course page lists every lesson and its Aha Trivia iframe actually loads the game;
- a lesson's self-check scores, "mark complete" persists, and the course and hub show it;
- a lesson's "Start the game" button loads the game on request;
- the practice tests carry their game; the print page holds every lesson;
- no page scrolls sideways on a phone, and our own pages log no JavaScript errors.
Exits non-zero when any check fails.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8790").rstrip("/")
SRC = Path(__file__).resolve().parents[2] / "ground-school"
COURSES = sorted((json.loads(p.read_text()) for p in SRC.glob("*.json")), key=lambda c: c["order"])
results = []


def rec(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), name, ("- " + str(detail)[:300]) if detail and not ok else "", flush=True)


def attach(pg, errs):
    def on_console(m):
        if m.type == "error" and (m.location or {}).get("url", "").startswith(B):
            errs.append(m.text)
    pg.on("console", on_console)
    pg.on("pageerror", lambda e: errs.append(str(e)))


def frame_text(pg, selector, wait_ms=15000):
    """Wait for the Aha Trivia game inside the iframe to render something readable."""
    fr = pg.frame_locator(selector)
    try:
        fr.locator("body").wait_for(timeout=wait_ms)
        pg.wait_for_timeout(2500)
        return fr.locator("body").inner_text(timeout=wait_ms)
    except Exception as e:  # noqa: BLE001 - report, do not crash the run
        return f"ERROR {e}"


def no_overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 1366, "height": 900})
    ctx.add_init_script("try{localStorage.setItem('umami.disabled','1')}catch(e){}")
    pg = ctx.new_page()
    errs: list[str] = []
    attach(pg, errs)

    # Hub
    pg.goto(B + "/ground-school/")
    rec("hub lists every course", pg.locator("ul.gs-cards > li").count() == len(COURSES),
        pg.locator("ul.gs-cards > li").count())
    rec("hub game picker has 6 courses", pg.locator("#aha-picker .aha-tab").count() == 6)
    pg.locator("#aha-picker").scroll_into_view_if_needed()
    txt = frame_text(pg, "#aha-picker iframe")
    rec("hub picker game loads (private pilot)", len(txt) > 40 and not txt.startswith("ERROR"), txt[:120])
    pg.click('#aha-picker .aha-tab[data-course="drone"]')
    src = pg.get_attribute("#aha-picker iframe", "src")
    rec("picker switches the game to Part 107", "course=drone" in src and "embed=1" in src, src)
    rec("picker marks the chosen tab", pg.get_attribute('#aha-picker .aha-tab[data-course="drone"]',
                                                         "aria-pressed") == "true")

    # Course page and its game
    c = next(x for x in COURSES if x["id"] == "private-pilot") if any(
        x["id"] == "private-pilot" for x in COURSES) else COURSES[0]
    pg.goto(f"{B}/ground-school/{c['id']}/")
    rec("course lists every lesson", pg.locator("ol.gs-lessons > li").count() == len(c["modules"]))
    if c.get("aha_course"):
        pg.locator("#play").scroll_into_view_if_needed()
        txt = frame_text(pg, "#play iframe")
        rec("course game loads inside the page", len(txt) > 40 and not txt.startswith("ERROR"), txt[:120])

    # Lesson: self-check, mark complete
    m = c["modules"][0]
    pg.goto(f"{B}/ground-school/{c['id']}/{m['id']}/")
    qs = pg.locator("#gs-check .gs-q")
    n = qs.count()
    rec("lesson shows every self-check question", n == len(m["check"]), n)
    for i in range(n):
        q = qs.nth(i)
        a = q.get_attribute("data-ans")
        pick = a if i % 2 == 0 else str((int(a) + 1) % len(m["check"][i]["choices"]))
        q.locator(f'.gs-btn[data-i="{pick}"]').click()
        rec(f"question {i + 1} shows its explanation", q.locator(".gs-why").is_visible())
    want = sum(1 for i in range(n) if i % 2 == 0)
    score = pg.locator("#gs-score").inner_text()
    rec("self-check scores the answers", score.startswith(f"You got {want} of {n}"), score)
    pg.click("#gs-mark")
    rec("mark complete toggles", pg.get_attribute("#gs-mark", "aria-pressed") == "true")
    if c.get("aha_course"):
        pg.click("#play .aha-start")
        txt = frame_text(pg, "#play iframe")
        rec("lesson Start button loads the game", len(txt) > 40 and not txt.startswith("ERROR"), txt[:120])
    pg.goto(f"{B}/ground-school/{c['id']}/")
    rec("course shows the lesson complete", pg.locator(f'li[data-gs-lesson="{m["id"]}"].done').count() == 1)
    pg.goto(B + "/ground-school/")
    cnt = pg.locator(f'li[data-gs-course="{c["id"]}"] [data-gs-count]').inner_text()
    rec("hub card shows progress", cnt.startswith("1 of "), cnt)

    # Print page and practice-test games
    pg.goto(f"{B}/ground-school/{c['id']}/print/")
    rec("print page holds every lesson", pg.locator(".gs-print-lesson[id^=l-]").count() == len(c["modules"]))
    for slug, course in (("private-pilot", "pilot"), ("sport-pilot", "sport-pilot"), ("part-107", "drone")):
        pg.goto(f"{B}/quiz/{slug}/")
        rec(f"practice test {slug} embeds the {course} game",
            pg.locator(f'iframe[src*="course={course}&embed=1"]').count() == 1)
    pg.goto(B + "/quiz/")
    rec("test prep hub has the game picker", pg.locator("#aha-picker iframe").count() == 1)
    rec("no JavaScript errors on our desktop pages", not errs, errs[:3])
    ctx.close()

    # Phone
    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.add_init_script("try{localStorage.setItem('umami.disabled','1')}catch(e){}")
    pg = ctx.new_page()
    errs = []
    attach(pg, errs)
    pages = ["/ground-school/"] + [f"/ground-school/{x['id']}/" for x in COURSES] + \
            [f"/ground-school/{x['id']}/{x['modules'][-1]['id']}/" for x in COURSES] + ["/quiz/", "/quiz/part-107/"]
    for path in pages:
        pg.goto(B + path)
        pg.wait_for_timeout(300)
        rec(f"phone: {path} has no sideways scroll", no_overflow(pg))
    pg.goto(f"{B}/ground-school/{c['id']}/")
    pg.locator("#play").scroll_into_view_if_needed()
    txt = frame_text(pg, "#play iframe")
    rec("phone: course game loads", len(txt) > 40 and not txt.startswith("ERROR"), txt[:120])
    rec("no JavaScript errors on our phone pages", not errs, errs[:3])
    ctx.close()
    br.close()

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} ground school checks passed")
sys.exit(1 if bad else 0)
