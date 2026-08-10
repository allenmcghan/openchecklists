#!/usr/bin/env python3
"""Validate an Open Logbook, total it, and report currency.

    python3 tools/logbook.py validate examples/example-logbook.oclb.json
    python3 tools/logbook.py totals   examples/example-logbook.oclb.json
    python3 tools/logbook.py currency examples/example-logbook.oclb.json --on 2026-08-10
    python3 tools/logbook.py import   mylog.csv --profile foreflight -o out.oclb.json
    python3 tools/logbook.py export   examples/example-logbook.oclb.json --profile generic

Three things here that proprietary logbooks generally do not do.

**The arithmetic is checked.** Time buckets in a logbook are not mutually
exclusive -- the same hour can be pilot_in_command and dual_received and night and
cross_country at once -- but some relationships must hold, and a logbook that
silently accepts day + night greater than total is a logbook with errors you will
discover during a checkride.

**Currency is computed in calendar months, not rolling days.** 61.57(c) says "the
preceding 6 calendar months", which means through the end of that month, not 183
days ago. Trackers that use rolling days give the wrong answer near month
boundaries, in the unsafe direction.

**Currency output is an aid, never an authority.** Every result says what it was
computed from. The regulations have conditions this cannot see -- an IPC, a
type-specific requirement, whether a landing was really to a full stop -- so the
tool reports its reasoning and refuses to say "you are legal".
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is required: pip install jsonschema")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import Findings  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "schema" / "open-logbook-1.0.schema.json"

TIME_KEYS = [
    "total", "pilot_in_command", "second_in_command", "dual_received", "instructor",
    "solo", "cross_country", "day", "night", "actual_instrument",
    "simulated_instrument", "ground_trainer",
]

TAILWHEEL_CLASSES = {"tailwheel", "retractable_tailwheel"}


# --------------------------------------------------------------------- helpers


def parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def months_back_start(ref: date, months: int) -> date:
    """First day of the month that begins a 'preceding N calendar months' window.

    61.57(c) counts calendar months, so on 2026-08-10 the preceding 6 calendar
    months begin on 2026-03-01: March through August inclusive. Using 183 rolling
    days instead would start on 2026-02-08 and wrongly count a February approach.
    """
    y, m = ref.year, ref.month - (months - 1)
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def within_calendar_months(d: date, ref: date, months: int) -> bool:
    return months_back_start(ref, months) <= d <= ref


# ------------------------------------------------------------------ validation


def check_arithmetic(book: dict, f: Findings) -> None:
    for i, e in enumerate(book.get("entries", [])):
        t = e.get("times", {})
        total = t.get("total")
        where = f"entries/{i} ({e.get('date')}, {e.get('aircraft_id')})"

        if total is None:
            f.error(f"policy: {where}: times.total is required; 61.51(b)(1) requires total flight time")
            continue

        day, night = t.get("day"), t.get("night")
        if day is not None and night is not None:
            if round(day + night, 2) > round(total, 2) + 1e-9:
                f.error(
                    f"policy: {where}: day ({day}) + night ({night}) = {round(day + night, 2)} "
                    f"exceeds total ({total})"
                )
            elif round(day + night, 2) < round(total, 2) - 1e-9:
                f.warn(
                    f"{where}: day + night = {round(day + night, 2)} is less than total ({total}); "
                    "some time is in neither bucket"
                )

        pic, sic = t.get("pilot_in_command"), t.get("second_in_command")
        if pic is not None and sic is not None and round(pic + sic, 2) > round(total, 2) + 1e-9:
            f.error(
                f"policy: {where}: pilot_in_command + second_in_command exceeds total; "
                "they cannot overlap in the same aircraft at the same time"
            )

        # Everything else is a subset of total time, however it overlaps.
        for k in ("pilot_in_command", "second_in_command", "dual_received", "instructor",
                  "solo", "cross_country", "actual_instrument", "simulated_instrument", "night", "day"):
            v = t.get(k)
            if v is not None and round(v, 2) > round(total, 2) + 1e-9:
                f.error(f"policy: {where}: {k} ({v}) exceeds times.total ({total})")

        if t.get("solo") and (t.get("dual_received") or 0) > 0:
            f.error(f"policy: {where}: solo time and dual_received in the same flight are contradictory")

        ld = e.get("landings", {})
        for a, b in (("full_stop_day", "day"), ("full_stop_night", "night")):
            if ld.get(a) is not None and ld.get(b) is not None and ld[a] > ld[b]:
                f.error(f"policy: {where}: landings.{a} ({ld[a]}) exceeds landings.{b} ({ld[b]})")

        if ld.get("night") and not t.get("night"):
            f.warn(f"{where}: night landings recorded but no night time")

        # An approach without its location and type does not satisfy 61.51(g)(3),
        # so it cannot be counted toward currency later.
        for j, ap in enumerate(e.get("instrument", {}).get("approaches", [])):
            if not ap.get("location"):
                f.error(f"policy: {where}: instrument/approaches/{j} has no location")

        m = e.get("meters", {})
        for s, en in (("hobbs_start", "hobbs_end"), ("tach_start", "tach_end")):
            if m.get(s) is not None and m.get(en) is not None and m[en] < m[s]:
                f.error(f"policy: {where}: {en} is before {s}")
        if m.get("hobbs_start") is not None and m.get("hobbs_end") is not None:
            span = round(m["hobbs_end"] - m["hobbs_start"], 2)
            if abs(span - round(total, 2)) > 0.2:
                f.warn(
                    f"{where}: Hobbs span {span} differs from logged total {total} by more than 0.2"
                )


def check_references(book: dict, f: Findings) -> None:
    ac = {a["id"]: a for a in book.get("aircraft", [])}
    seen_ids: set[str] = set()
    for i, e in enumerate(book.get("entries", [])):
        if e.get("aircraft_id") not in ac:
            f.error(
                f"policy: entries/{i}: aircraft_id {e.get('aircraft_id')!r} is not declared in "
                "the aircraft list"
            )
        eid = e.get("id")
        if eid:
            if eid in seen_ids:
                f.error(f"policy: entries/{i}: duplicate entry id {eid!r}")
            seen_ids.add(eid)

    dates = [parse_date(e.get("date", "")) for e in book.get("entries", [])]
    known = [d for d in dates if d]
    if known and known != sorted(known):
        f.warn("entries are not in date order; harmless, but totals and currency read better sorted")
    today = date.today()
    for i, d in enumerate(dates):
        if d and d > today:
            f.error(f"policy: entries/{i}: date {d.isoformat()} is in the future")

    cf = book.get("carried_forward")
    if cf and cf.get("as_of") and known:
        as_of = parse_date(cf["as_of"])
        early = [d for d in known if as_of and d < as_of]
        if early:
            f.warn(
                f"carried_forward is as of {cf['as_of']} but {len(early)} entry/entries predate it; "
                "those hours may be counted twice in totals"
            )


def validate_book(path: Path, schema: dict) -> tuple[Findings, dict | None]:
    f = Findings(path)
    try:
        book = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        f.error(f"invalid JSON: {exc}")
        return f, None

    for err in sorted(Draft202012Validator(schema).iter_errors(book), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        f.error(f"schema: {loc}: {err.message}")
    if f.errors:
        return f, None

    check_references(book, f)
    check_arithmetic(book, f)
    return f, book


# ---------------------------------------------------------------------- totals


def totals(book: dict) -> dict:
    out = {k: 0.0 for k in TIME_KEYS}
    land = {"day": 0, "night": 0, "full_stop_day": 0, "full_stop_night": 0}
    approaches = 0
    for e in book.get("entries", []):
        for k in TIME_KEYS:
            v = e.get("times", {}).get(k)
            if v:
                out[k] += v
        for k in land:
            v = e.get("landings", {}).get(k)
            if v:
                land[k] += v
        approaches += len(e.get("instrument", {}).get("approaches", []))

    cf = book.get("carried_forward") or {}
    cft = cf.get("totals") or {}
    for k in TIME_KEYS:
        if cft.get(k):
            out[k] += cft[k]
    for a, b in (("day", "landings_day"), ("night", "landings_night")):
        if cf.get(b):
            land[a] += cf[b]

    return {
        "times": {k: round(v, 2) for k, v in out.items() if v},
        "landings": land,
        "approaches_logged": approaches,
        "entry_count": len(book.get("entries", [])),
        "includes_carried_forward": bool(cf),
    }


# -------------------------------------------------------------------- currency


def currency(book: dict, ref: date) -> list[dict]:
    """Compute currency. Reports reasoning, never a verdict of legality."""
    ac = {a["id"]: a for a in book.get("aircraft", [])}
    entries = [e for e in book.get("entries", []) if parse_date(e.get("date", ""))]
    out: list[dict] = []

    # --- 61.56 flight review: 24 calendar months ---
    reviews = book.get("holder", {}).get("flight_reviews", [])
    valid = [
        r for r in reviews
        if parse_date(r["date"]) and within_calendar_months(parse_date(r["date"]), ref, 24)
    ]
    latest = max((parse_date(r["date"]) for r in reviews if parse_date(r["date"])), default=None)
    out.append({
        "rule": "61.56 flight review",
        "window": f"24 calendar months from {months_back_start(ref, 24).isoformat()}",
        "satisfied": bool(valid),
        "evidence": f"most recent: {latest.isoformat()} ({valid[0]['kind'] if valid else 'outside window'})"
        if latest else "no flight review recorded",
    })

    # --- 61.57(a)/(b) passenger carrying: 3 takeoffs and landings in 90 days ---
    # Grouped by category and class AND by tailwheel, not by class alone. A Cub and
    # a 172 are both airplane_single_engine_land, but 61.57(a)(2) requires the
    # landings for a tailwheel aeroplane to be to a full stop *in a tailwheel
    # aeroplane*. Merging them would let tricycle touch-and-goes appear to satisfy
    # tailwheel currency, which is wrong in the unsafe direction.
    #
    # Part 103 vehicles and ground trainers are excluded: 61.57 governs acting as
    # pilot in command under Part 61, and an ultralight vehicle needs no
    # certificate, so the rule does not reach it.
    EXCLUDED = {"ultralight_part103", "simulator", "flight_training_device"}
    since90 = ref - timedelta(days=90)
    groups: dict[tuple[str, bool], dict] = {}
    excluded_seen: set[str] = set()

    for e in entries:
        d = parse_date(e["date"])
        if not (since90 <= d <= ref):
            continue
        a = ac.get(e.get("aircraft_id"), {})
        cls = a.get("category_class", "unknown")
        if cls in EXCLUDED:
            excluded_seen.add(cls)
            continue
        tw = a.get("gear") in TAILWHEEL_CLASSES or "tailwheel" in (a.get("attributes") or [])
        b = groups.setdefault((cls, tw), {
            "landings_day": 0, "landings_night": 0, "full_stop_day": 0, "full_stop_night": 0,
        })
        ld = e.get("landings", {})
        for k in ("day", "night"):
            b[f"landings_{k}"] += ld.get(k) or 0
        for k in ("full_stop_day", "full_stop_night"):
            b[k] += ld.get(k) or 0

    for (cls, tw), b in sorted(groups.items()):
        label = f"{cls}{' (tailwheel)' if tw else ' (tricycle or other)'}"
        day_ct = b["full_stop_day"] if tw else b["landings_day"] + b["landings_night"]
        kind = "full-stop landings" if tw else "landings"
        out.append({
            "rule": f"61.57(a) passengers, day — {label}",
            "window": f"90 days from {since90.isoformat()}",
            "satisfied": day_ct >= 3,
            "evidence": f"{day_ct} {kind} logged (need 3)"
            + (" — tailwheel, so touch-and-goes do not count and they must be in a "
               "tailwheel aeroplane" if tw else ""),
        })
        night_ct = b["full_stop_night"]
        out.append({
            "rule": f"61.57(b) passengers, night — {label}",
            "window": f"90 days from {since90.isoformat()}",
            "satisfied": night_ct >= 3,
            "evidence": f"{night_ct} night full-stop landings logged (need 3, in the period from "
                        "1 hour after sunset to 1 hour before sunrise)",
        })

    if not groups:
        out.append({
            "rule": "61.57(a) passengers",
            "window": f"90 days from {since90.isoformat()}",
            "satisfied": False,
            "evidence": "no flights with landings in an aircraft 61.57 applies to in the last 90 days",
        })

    for cls in sorted(excluded_seen):
        out.append({
            "rule": f"61.57 not applicable — {cls}",
            "window": "n/a",
            "satisfied": True,
            "evidence": "61.57 governs acting as pilot in command under Part 61; flights in this "
                        "category are recorded but no currency requirement is computed for them",
        })

    # --- 61.57(c) instrument: 6 approaches + holding + course tracking in 6 calendar months ---
    start6 = months_back_start(ref, 6)
    appr = 0
    holds = 0
    tracking = False
    last_appr: date | None = None
    for e in entries:
        d = parse_date(e["date"])
        inst = e.get("instrument", {})
        n = len(inst.get("approaches", []))
        if n and (last_appr is None or d > last_appr):
            last_appr = d
        if not within_calendar_months(d, ref, 6):
            continue
        appr += n
        holds += inst.get("holds") or 0
        tracking = tracking or bool(inst.get("course_tracking"))

    limbs = []
    limbs.append(f"{appr} approaches (need 6)")
    limbs.append(f"{holds} holding procedures (need at least 1)")
    limbs.append("course intercepting and tracking logged" if tracking
                 else "no course intercepting and tracking logged")
    satisfied = appr >= 6 and holds >= 1 and tracking

    note = ""
    if not satisfied and last_appr:
        # After the 6-month window lapses there are 6 further calendar months in
        # which currency can be regained by flying the requirements; beyond that
        # it takes an IPC.
        grace_start = months_back_start(ref, 12)
        if last_appr >= grace_start:
            note = (" Within the further 6 calendar months in which the requirements may be "
                    "flown to regain currency; after that an instrument proficiency check is "
                    "required.")
        else:
            note = (" Last approach was more than 12 calendar months ago, so an instrument "
                    "proficiency check is required rather than simply flying the requirements.")

    out.append({
        "rule": "61.57(c) instrument",
        "window": f"6 calendar months from {start6.isoformat()}",
        "satisfied": satisfied,
        "evidence": "; ".join(limbs) + "." + note,
    })

    # --- medical ---
    med = book.get("holder", {}).get("medical") or {}
    if med.get("expires"):
        exp = parse_date(med["expires"])
        out.append({
            "rule": f"medical ({med.get('class', 'unspecified')})",
            "window": "as recorded",
            "satisfied": bool(exp and exp >= ref),
            "evidence": f"expires {med['expires']}",
        })

    return out


# ------------------------------------------------------------ import / export

# Column-mapping profiles. Deliberately data rather than code, and deliberately
# conservative: anything not recognised is preserved in imported_from.unmapped
# rather than dropped, because a silent lossy import is how somebody loses a
# decade of flying.
#
# These header names are drawn from the columns these products commonly emit and
# have NOT been verified against an official specification. Treat a first import
# as something to check, not to trust -- the tool reports what it could not map.
PROFILES: dict[str, dict[str, str]] = {
    "generic": {
        "date": "date", "aircraft": "aircraft_id", "registration": "aircraft_id",
        "from": "route.from", "to": "route.to",
        "total": "times.total", "total_time": "times.total",
        "pic": "times.pilot_in_command", "sic": "times.second_in_command",
        "dual": "times.dual_received", "dual_received": "times.dual_received",
        "instructor": "times.instructor", "cfi": "times.instructor",
        "solo": "times.solo", "cross_country": "times.cross_country", "xc": "times.cross_country",
        "day": "times.day", "night": "times.night",
        "actual_instrument": "times.actual_instrument", "actual": "times.actual_instrument",
        "simulated_instrument": "times.simulated_instrument", "hood": "times.simulated_instrument",
        "sim_instrument": "times.simulated_instrument",
        "day_landings": "landings.day", "night_landings": "landings.night",
        "landings_day": "landings.day", "landings_night": "landings.night",
        "remarks": "remarks", "notes": "remarks",
    },
    "foreflight": {
        "date": "date", "aircraftid": "aircraft_id",
        "from": "route.from", "to": "route.to", "route": "route.via",
        "totaltime": "times.total", "pic": "times.pilot_in_command",
        "sic": "times.second_in_command", "dualreceived": "times.dual_received",
        "dualgiven": "times.instructor", "solo": "times.solo",
        "crosscountry": "times.cross_country", "nighttime": "times.night",
        "actualinstrument": "times.actual_instrument",
        "simulatedinstrument": "times.simulated_instrument",
        "daylandingsfullstop": "landings.full_stop_day",
        "nightlandingsfullstop": "landings.full_stop_night",
        "alllandings": "landings.day",
        "distance": "route.distance_nm",
        "holds": "instrument.holds",
        "pilotcomments": "remarks", "instructorcomments": "remarks",
    },
}


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")


def set_path(obj: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def to_hours(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    if ":" in s:  # 1:30 -> 1.5
        try:
            h, m = s.split(":", 1)
            return round(int(h) + int(m) / 60.0, 2)
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def import_csv(text: str, profile: str, holder_name: str) -> tuple[dict, list[str]]:
    prof = PROFILES.get(profile)
    if prof is None:
        raise SystemExit(f"unknown profile {profile!r}; have: {', '.join(sorted(PROFILES))}")

    # Some products prepend metadata blocks before the real header row. Find the
    # first row that looks like a header by locating a date-ish column.
    rows = list(csv.reader(io.StringIO(text)))
    header_at = None
    for i, row in enumerate(rows[:60]):
        norm = [norm_header(c) for c in row]
        if "date" in norm and len(row) >= 3:
            header_at = i
            break
    if header_at is None:
        raise SystemExit("could not find a header row containing a 'Date' column")

    header = [norm_header(c) for c in rows[header_at]]
    unmapped_cols: set[str] = set()
    entries: list[dict] = []
    aircraft: dict[str, dict] = {}

    for rn, row in enumerate(rows[header_at + 1:], start=header_at + 2):
        if not any(c.strip() for c in row):
            continue
        rec: dict = {}
        unmapped: dict[str, str] = {}
        for col, raw in zip(header, row):
            val = (raw or "").strip()
            if not val:
                continue
            target = prof.get(col)
            if target is None:
                unmapped[col] = val
                unmapped_cols.add(col)
                continue
            if target.startswith("times.") or target == "route.distance_nm":
                num = to_hours(val)
                if num is not None:
                    set_path(rec, target, num)
            elif target.startswith("landings.") or target == "instrument.holds":
                try:
                    set_path(rec, target, int(float(val)))
                except ValueError:
                    unmapped[col] = val
            elif target == "route.via":
                set_path(rec, target, [p for p in re.split(r"[\s,>-]+", val) if p][:20])
            elif target == "remarks":
                rec["remarks"] = (rec.get("remarks", "") + " " + val).strip()[:4000]
            else:
                set_path(rec, target, val)

        d = rec.get("date", "")
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%Y/%m/%d"):
            try:
                rec["date"] = datetime.strptime(d, fmt).date().isoformat()
                break
            except ValueError:
                continue

        if not parse_date(rec.get("date", "")):
            continue
        rec.setdefault("aircraft_id", "UNKNOWN")
        rec.setdefault("times", {}).setdefault("total", 0.0)
        rec["imported_from"] = {"product": profile, "imported": date.today().isoformat(),
                                "source_row": rn}
        if unmapped:
            rec["imported_from"]["unmapped"] = unmapped
        entries.append(rec)
        aircraft.setdefault(rec["aircraft_id"], {
            "id": rec["aircraft_id"], "make": "Unknown", "model": "Unknown",
            "category_class": "airplane_single_engine_land",
        })

    book = {
        "open_logbook_version": "1.0",
        "holder": {"name": holder_name},
        "aircraft": sorted(aircraft.values(), key=lambda a: a["id"]),
        "entries": entries,
    }
    return book, sorted(unmapped_cols)


def export_csv(book: dict) -> str:
    cols = (["date", "aircraft_id", "from", "to"]
            + TIME_KEYS
            + ["landings_day", "landings_night", "full_stop_day", "full_stop_night",
               "approaches", "holds", "remarks"])
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(cols)
    for e in book.get("entries", []):
        t, ld = e.get("times", {}), e.get("landings", {})
        inst = e.get("instrument", {})
        w.writerow(
            [e.get("date", ""), e.get("aircraft_id", ""),
             e.get("route", {}).get("from", ""), e.get("route", {}).get("to", "")]
            + [t.get(k, "") for k in TIME_KEYS]
            + [ld.get("day", ""), ld.get("night", ""), ld.get("full_stop_day", ""),
               ld.get("full_stop_night", ""), len(inst.get("approaches", [])) or "",
               inst.get("holds", ""), e.get("remarks", "")]
        )
    return out.getvalue()


# ---------------------------------------------------------------------- driver


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate"); v.add_argument("files", nargs="+", type=Path)
    v.add_argument("--strict", action="store_true")
    t = sub.add_parser("totals"); t.add_argument("file", type=Path)
    c = sub.add_parser("currency"); c.add_argument("file", type=Path)
    c.add_argument("--on", help="reference date, default today")
    i = sub.add_parser("import"); i.add_argument("file", type=Path)
    i.add_argument("--profile", default="generic")
    i.add_argument("--holder", default="Unknown")
    i.add_argument("-o", "--out", type=Path)
    x = sub.add_parser("export"); x.add_argument("file", type=Path)
    x.add_argument("--profile", default="generic")

    args = ap.parse_args()
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)

    if args.cmd == "validate":
        failed = 0
        for p in args.files:
            f, _ = validate_book(p, schema)
            bad = f.errors or (args.strict and f.warnings)
            print(f"[{'FAIL' if bad else ('warn' if f.warnings else 'ok')}] {p.name}")
            for m in f.errors:
                print(f"    error: {m}")
            for m in f.warnings:
                print(f"    warn:  {m}")
            failed += bool(bad)
        print(f"\n{len(args.files) - failed}/{len(args.files)} logbook(s) passed")
        return 1 if failed else 0

    if args.cmd == "totals":
        f, book = validate_book(args.file, schema)
        if book is None:
            for m in f.errors:
                print(f"error: {m}")
            return 1
        print(json.dumps(totals(book), indent=2))
        return 0

    if args.cmd == "currency":
        f, book = validate_book(args.file, schema)
        if book is None:
            for m in f.errors:
                print(f"error: {m}")
            return 1
        ref = parse_date(args.on) if args.on else date.today()
        if ref is None:
            raise SystemExit("--on must be YYYY-MM-DD")
        print(f"Currency as of {ref.isoformat()} for {book['holder']['name']}\n")
        for r in currency(book, ref):
            mark = "yes" if r["satisfied"] else "NO "
            print(f"  [{mark}] {r['rule']}")
            print(f"         window: {r['window']}")
            print(f"         {r['evidence']}")
        print("\n  Computed from the logbook only, and an aid rather than an authority.")
        print("  It cannot see an IPC, a type-specific requirement, or whether a landing was")
        print("  truly to a full stop. Check the regulations and your own records.")
        return 0

    if args.cmd == "import":
        book, unmapped = import_csv(args.file.read_text(errors="replace"), args.profile, args.holder)
        blob = json.dumps(book, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.write_text(blob)
            print(f"wrote {args.out} — {len(book['entries'])} entries, "
                  f"{len(book['aircraft'])} aircraft")
        else:
            sys.stdout.write(blob)
        if unmapped:
            print(f"\n{len(unmapped)} column(s) not mapped, preserved per entry in "
                  f"imported_from.unmapped:", file=sys.stderr)
            for c in unmapped:
                print(f"  {c}", file=sys.stderr)
        print("\nAircraft make, model and category/class default to placeholders — fill them "
              "in, since currency depends on category and class.", file=sys.stderr)
        return 0

    if args.cmd == "export":
        f, book = validate_book(args.file, schema)
        if book is None:
            for m in f.errors:
                print(f"error: {m}")
            return 1
        sys.stdout.write(export_csv(book))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
