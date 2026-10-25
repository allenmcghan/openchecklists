#!/usr/bin/env python3
"""Prove the ground school content is valid and the pages it builds are complete.

    python3 tools/test_ground_school.py

What matters, and is not visible from reading one page:

1. **Every course file passes the content rules** (ground-school/README.md). A self-check
   question whose answer index points past its choices marks a right answer wrong.
2. **The validator rejects bad content rather than rendering it**, so a broken file fails
   the build instead of shipping.
3. **Every page is written, linked and escaped**: the hub links every course, every course
   links every lesson, every lesson carries its self-check, the print page holds them all,
   and text that looks like HTML is shown as text.
4. **The Aha Trivia games use the engine's embed mode** (?embed=1 on ahatrivia.com/play/),
   with a title for screen readers, on the hub, course pages, lessons and practice tests.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aha_embed  # noqa: E402
import site_ground_school as gs  # noqa: E402
import site_quiz  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name + (f": {detail}" if detail else ""))


def fake_head(title: str, desc: str, rel: str = "", path: str | None = None, ads: bool = False) -> str:
    return f"<!doctype html><html><head><title>{title}</title></head><body><main>"


FOOT = '</main><footer><a href="terms.html">Terms</a></footer></body></html>'

MINI = {
    "id": "mini", "title": "Mini & < 1 Course>", "short": "Mini", "icon": "*", "order": 1,
    "summary": "A tiny course.", "who": "Testers.", "aha_course": "pilot", "quiz_slug": "private-pilot",
    "checked": "2026-10-25",
    "facts": [{"label": f"Fact {i}", "value": "v", "cite": {"label": "14 CFR 1.1",
               "url": "https://www.ecfr.gov/current/title-14/section-1.1"}} for i in range(3)],
    "knowledge_test": {"code": "XYZ", "questions": 10, "minutes": 30, "passing": "70%", "notes": ["n"], "cites": []},
    "practical_test": None,
    "requirements": [{"text": "Be a tester."}],
    "plan": [{"step": "Week 1", "focus": "Everything.", "modules": ["one", "two"]}],
    "modules": [
        {"id": mid, "title": f"Lesson {mid}", "summary": "s", "objectives": ["o"],
         "sections": [{"heading": "h", "points": ["Visibility < 3 SM & \"gusts\" get escaped."]}],
         "numbers": [{"item": "i", "value": "v", "cite": "c"}], "traps": ["t"],
         "read": [{"label": "PHAK", "url": "https://www.faa.gov/x", "library": {"doc": "faa-phak", "q": "lift"}}],
         "check": [{"q": "Q?", "choices": ["a", "b", "c"], "answer": 2, "why": "w", "cite": "c"}]}
        for mid in ("one", "two", "three", "four")],
    "test_day": ["Bring ID."], "after": ["Celebrate."],
}


def main() -> int:
    # 1. The real course files.
    files = sorted(gs.SRC.glob("*.json"))
    check("ground-school/ has course files", len(files) >= 1, f"{len(files)} files")
    try:
        courses = gs.load()
        check("every course file passes the content rules", True)
    except ValueError as e:
        courses = []
        check("every course file passes the content rules", False, str(e)[:2000])
    ids = {c["id"] for c in courses}
    expected_ids = {"part-103", "part-107", "sport-pilot", "private-pilot",
                    "instrument-rating", "commercial-pilot"}
    check("ground school includes every promised pilot course", ids == expected_ids,
          f"missing {sorted(expected_ids - ids)}; extra {sorted(ids - expected_ids)}")
    for c in courses:
        check(f"{c['id']}: has a full lesson sequence", len(c["modules"]) >= 8,
              f"{len(c['modules'])} lessons")
        n_checks = sum(len(m["check"]) for m in c["modules"])
        check(f"{c['id']}: has at least 3 self-check questions per lesson",
              n_checks >= 3 * len(c["modules"]), f"{n_checks} for {len(c['modules'])} lessons")
        text = json.dumps(c, ensure_ascii=False)
        check(f"{c['id']}: no em dashes in the text", "—" not in text)

    # 2. The validator rejects bad content.
    check("the sample course is valid", gs.validate(MINI, "mini") == [], "; ".join(gs.validate(MINI, "mini")))
    bad_cases = {
        "answer index past the choices": lambda d: d["modules"][0]["check"][0].__setitem__("answer", 3),
        "two choices only": lambda d: d["modules"][0]["check"][0].__setitem__("choices", ["a", "b"]),
        "http reading": lambda d: d["modules"][0]["read"][0].__setitem__("url", "http://faa.gov"),
        "duplicate lesson id": lambda d: d["modules"][1].__setitem__("id", "one"),
        "plan names a missing lesson": lambda d: d["plan"][0]["modules"].append("nope"),
        "HTML in text": lambda d: d.__setitem__("who", "Click <a href='x'>here</a>"),
        "unknown Aha course": lambda d: d.__setitem__("aha_course", "chess"),
        "unknown library doc": lambda d: d["modules"][0]["read"][0].__setitem__("library", {"doc": "x", "q": "y"}),
        "file name mismatch": None,
    }
    for name, mutate in bad_cases.items():
        d = copy.deepcopy(MINI)
        if mutate:
            mutate(d)
        errs = gs.validate(d, "other" if mutate is None else "mini")
        check(f"validator rejects: {name}", bool(errs))

    # 3 and 4. Build a site from the sample course and inspect the pages.
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "src", Path(tmp) / "out"
        src.mkdir()
        (src / "mini.json").write_text(json.dumps(MINI), encoding="utf-8")
        paths = gs.write_ground_school(out, fake_head, FOOT, src=src, base="https://example.test")
        check("sitemap paths: hub, course and 4 lessons (print page left out)",
              paths == ["ground-school/", "ground-school/mini/"] + [f"ground-school/mini/{m}/" for m in
                                                                     ("one", "two", "three", "four")], str(paths))
        hub = (out / "ground-school/index.html").read_text()
        course = (out / "ground-school/mini/index.html").read_text()
        lesson = (out / "ground-school/mini/two/index.html").read_text()
        printp = (out / "ground-school/mini/print/index.html").read_text()
        check("hub links the course", 'href="/ground-school/mini/"' in hub)
        check("hub carries the game picker with every pilot course",
              all(f'data-course="{c}"' in hub for c in aha_embed.ORDER))
        check("course links every lesson", all(f'href="/ground-school/mini/{m}/"' in course
                                              for m in ("one", "two", "three", "four")))
        check("course embeds its Aha game in embed mode",
              'src="https://ahatrivia.com/play/?course=pilot&amp;embed=1"' in course)
        check("every Aha iframe has a title", all(re.search(r'title="[^"]+\(Aha Trivia game\)"', f)
                                                  for f in re.findall(r"<iframe[^>]*>", hub + course + lesson)))
        check("course links the practice test", 'href="/quiz/private-pilot/"' in course)
        check("course escapes special characters", "Mini &amp; &lt; 1 Course" in course and "Mini & < 1" not in re.sub(r"<script.*?</script>", "", course, flags=re.S))
        check("lesson escapes special characters", "Visibility &lt; 3 SM &amp; &quot;gusts&quot;" in lesson)
        check("lesson has the self-check with the right answer index", 'data-ans="2"' in lesson)
        check("lesson links previous and next lessons",
              'href="/ground-school/mini/one/"' in lesson and 'href="/ground-school/mini/three/"' in lesson)
        check("lesson loads the game only on request", "<template><iframe" in lesson and "data-aha-load" in lesson)
        check("lesson links the library search", "/search.html?doc=faa-phak&amp;q=lift" in lesson)
        check("lesson foot links are absolute", 'href="/terms.html"' in lesson)
        check("print page holds every lesson and the answers",
              all(f'id="l-{m}"' in printp for m in ("one", "two", "three", "four")) and "<strong>Answers</strong>" in printp)
        check("print page is kept out of search", 'name="robots" content="noindex,follow"' in printp)
        check("print page has no game", "<iframe" not in printp)
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', course, re.S)
        check("course JSON-LD parses as a Course",
              bool(ld) and json.loads(ld.group(1).replace("<\\/", "</"))["@type"] == "Course")

    # The practice tests carry their Aha game and link to ground school.
    qcheck = {"par": "pilot", "spa": "sport-pilot", "uag": "drone"}
    for test, course_id in qcheck.items():
        check(f"practice test {test} maps to Aha course {course_id}", site_quiz.AHA.get(test) == course_id)
    for test, gid in site_quiz.GROUND_SCHOOL.items():
        if ids:
            check(f"practice test {test} links an existing course ({gid})", gid in ids)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all ground school checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
