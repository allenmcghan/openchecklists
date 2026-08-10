#!/usr/bin/env python3
"""Negative tests for logbook.py, plus currency-boundary tests.

The arithmetic checks matter because a logbook that silently accepts day + night
greater than total is a logbook with errors you discover during a checkride. The
currency tests matter more: the calendar-month boundary is where rolling-day
implementations give the wrong answer, and they give it in the unsafe direction.

Run: python3 tools/test_logbook.py
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logbook import (  # noqa: E402
    SCHEMA_PATH, currency, months_back_start, totals, validate_book,
)

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads(SCHEMA_PATH.read_text())
GOOD = json.loads((REPO / "examples" / "example-logbook.oclb.json").read_text())
TMP = Path(__file__).resolve().parent / ".test-tmp"


def run(book: dict):
    TMP.mkdir(exist_ok=True)
    p = TMP / "b.oclb.json"
    p.write_text(json.dumps(book, indent=2))
    try:
        return validate_book(p, SCHEMA)[0]
    finally:
        p.unlink(missing_ok=True)
        if not any(TMP.iterdir()):
            TMP.rmdir()


CASES: list[tuple[str, object, str]] = []


def case(label: str, expect: str):
    def deco(fn):
        CASES.append((label, fn, expect))
        return fn
    return deco


@case("day + night exceeding total", "exceeds total")
def _(b):
    b["entries"][0]["times"] = {"total": 1.0, "day": 0.8, "night": 0.5}


@case("PIC + SIC exceeding total", "cannot overlap")
def _(b):
    b["entries"][0]["times"] = {"total": 1.0, "pilot_in_command": 0.8, "second_in_command": 0.5}


@case("a component exceeding total", "exceeds times.total")
def _(b):
    b["entries"][0]["times"] = {"total": 1.0, "cross_country": 2.0}


@case("solo and dual on the same flight", "contradictory")
def _(b):
    b["entries"][0]["times"] = {"total": 1.0, "solo": 1.0, "dual_received": 1.0}


@case("missing total time", "times.total is required")
def _(b):
    b["entries"][0]["times"] = {"pilot_in_command": 1.0}


@case("more full-stop landings than landings", "exceeds landings.day")
def _(b):
    b["entries"][0]["landings"] = {"day": 2, "full_stop_day": 5}


@case("an approach with no location", "no location|'location' is a required property")
def _(b):
    b["entries"][1]["instrument"]["approaches"][0].pop("location")


@case("aircraft not declared", "not declared in the aircraft list")
def _(b):
    b["entries"][0]["aircraft_id"] = "N-NOPE"


@case("duplicate entry id", "duplicate entry id")
def _(b):
    b["entries"][1]["id"] = b["entries"][0]["id"]


@case("a flight dated in the future", "in the future")
def _(b):
    b["entries"][0]["date"] = "2099-01-01"


@case("Hobbs running backwards", "is before")
def _(b):
    b["entries"][0]["meters"] = {"hobbs_start": 100.0, "hobbs_end": 99.0}


@case("an unknown category and class", "is not one of")
def _(b):
    b["aircraft"][0]["category_class"] = "flying_carpet"


@case("no holder name", "minLength|should be non-empty|'name' is a required property")
def _(b):
    b["holder"] = {}


def boundary_tests() -> list[tuple[str, bool]]:
    """Calendar-month window behaviour, which is the subtle part."""
    results = []

    # 6 calendar months back from 10 August 2026 starts on 1 March 2026.
    results.append((
        "6 calendar months from 2026-08-10 starts 2026-03-01",
        months_back_start(date(2026, 8, 10), 6) == date(2026, 3, 1),
    ))
    # Crossing a year boundary.
    results.append((
        "6 calendar months from 2026-02-15 starts 2025-09-01",
        months_back_start(date(2026, 2, 15), 6) == date(2025, 9, 1),
    ))
    results.append((
        "24 calendar months from 2026-08-10 starts 2024-09-01",
        months_back_start(date(2026, 8, 10), 24) == date(2024, 9, 1),
    ))

    # An approach on the first day of the window counts; a rolling-183-day
    # implementation would also count one in late February, which is wrong.
    book = copy.deepcopy(GOOD)
    book["entries"] = [{
        "date": "2026-03-01", "aircraft_id": "N734XY",
        "times": {"total": 1.0, "pilot_in_command": 1.0},
        "instrument": {
            "approaches": [{"type": "ILS", "location": f"KFDK RWY {i}"} for i in range(6)],
            "holds": 1, "course_tracking": True,
        },
    }]
    res = {r["rule"]: r for r in currency(book, date(2026, 8, 31))}
    results.append((
        "approaches on the first day of the 6th month back still count",
        res["61.57(c) instrument"]["satisfied"] is True,
    ))

    # The same flight one day earlier falls outside the window.
    book["entries"][0]["date"] = "2026-02-28"
    res = {r["rule"]: r for r in currency(book, date(2026, 8, 31))}
    results.append((
        "approaches the day before the window do not count",
        res["61.57(c) instrument"]["satisfied"] is False,
    ))
    results.append((
        "a lapse inside 12 calendar months reports the fly-to-regain path",
        "regain currency" in res["61.57(c) instrument"]["evidence"],
    ))

    # Long lapse must point at an IPC rather than at flying the requirements.
    book["entries"][0]["date"] = "2025-01-05"
    res = {r["rule"]: r for r in currency(book, date(2026, 8, 31))}
    results.append((
        "a lapse beyond 12 calendar months requires an IPC",
        "instrument proficiency check is required" in res["61.57(c) instrument"]["evidence"],
    ))

    # Six approaches but no hold, and no tracking, must fail.
    book2 = copy.deepcopy(GOOD)
    book2["entries"] = [{
        "date": "2026-08-01", "aircraft_id": "N734XY",
        "times": {"total": 2.0, "pilot_in_command": 2.0},
        "instrument": {
            "approaches": [{"type": "ILS", "location": f"KFDK RWY {i}"} for i in range(6)],
        },
    }]
    r2 = {r["rule"]: r for r in currency(book2, date(2026, 8, 10))}
    results.append((
        "six approaches without a hold or tracking is not current",
        r2["61.57(c) instrument"]["satisfied"] is False,
    ))

    # Tailwheel and tricycle in the same category must be tracked separately: a
    # tricycle touch-and-go must not satisfy tailwheel currency.
    book3 = copy.deepcopy(GOOD)
    book3["entries"] = [
        {"date": "2026-08-01", "aircraft_id": "N734XY",
         "times": {"total": 1.0, "pilot_in_command": 1.0},
         "landings": {"day": 9}},
        {"date": "2026-08-02", "aircraft_id": "N88TW",
         "times": {"total": 1.0, "pilot_in_command": 1.0},
         "landings": {"day": 9, "full_stop_day": 0}},
    ]
    rules = {r["rule"]: r for r in currency(book3, date(2026, 8, 10))}
    tw = [k for k in rules if "tailwheel)" in k and "day" in k]
    tri = [k for k in rules if "tricycle" in k and "day" in k]
    results.append((
        "tailwheel currency is reported separately from tricycle",
        len(tw) == 1 and len(tri) == 1,
    ))
    results.append((
        "tailwheel touch-and-goes do not satisfy tailwheel currency",
        tw and rules[tw[0]]["satisfied"] is False,
    ))
    results.append((
        "tricycle landings still satisfy tricycle currency",
        tri and rules[tri[0]]["satisfied"] is True,
    ))

    # Part 103 is outside 61.57 entirely.
    book4 = copy.deepcopy(GOOD)
    book4["entries"] = [{"date": "2026-08-01", "aircraft_id": "N512JM",
                         "times": {"total": 1.0, "pilot_in_command": 1.0},
                         "landings": {"day": 1}}]
    r4 = [r["rule"] for r in currency(book4, date(2026, 8, 10))]
    results.append((
        "Part 103 flights report no 61.57 requirement",
        any("not applicable" in k for k in r4),
    ))

    # Carried-forward totals must be included but never drive currency.
    t = totals(GOOD)
    results.append((
        "carried-forward hours are included in totals",
        t["times"]["total"] > 214.6 and t["includes_carried_forward"] is True,
    ))
    return results


def main() -> int:
    base = run(copy.deepcopy(GOOD))
    if base.errors:
        print("BASELINE FAILED:")
        for e in base.errors:
            print("   ", e)
        return 1
    print("[ok]   baseline: example logbook validates cleanly")

    failures = 0
    for label, mutate, expect in CASES:
        book = copy.deepcopy(GOOD)
        mutate(book)
        f = run(book)
        blob = " | ".join(f.errors)
        if f.errors and any(part in blob for part in expect.split("|")):
            print(f"[ok]   caught: {label}")
        elif f.errors:
            print(f"[FAIL] {label}: rejected for the wrong reason (wanted {expect!r})")
            for e in f.errors:
                print(f"         {e}")
            failures += 1
        else:
            print(f"[FAIL] {label}: accepted, expected an error matching {expect!r}")
            failures += 1

    print()
    for label, ok in boundary_tests():
        print(f"[{'ok' if ok else 'FAIL'}]   {label}")
        failures += 0 if ok else 1

    total = len(CASES) + len(boundary_tests())
    print(f"\n{total - failures}/{total} check(s) behaved correctly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
