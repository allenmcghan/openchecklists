#!/usr/bin/env python3
"""Certificate and rating requirements, and progress toward them from a logbook.

    python3 tools/training.py list
    python3 tools/training.py requirements private-airplane-sel
    python3 tools/training.py progress examples/example-logbook.oclb.json --for private-airplane-sel
    python3 tools/training.py emit          # -> data/training/certificates.json for the site

This is the piece that makes a logbook worth more than a spreadsheet: it reads the
aeronautical experience requirements out of 14 CFR part 61 and reports what a real
logbook has against them.

**Three honesty rules, because this is regulatory and a student will act on it.**

*Every requirement cites its CFR paragraph.* Not "40 hours" but "61.109(a) — 40
hours". If the tool and the regulation disagree, the regulation wins, and the citation
is how you find that out.

*Requirements that cannot be computed from a logbook say so rather than being
guessed.* "3 hours in preparation for the practical test within the preceding 2
calendar months" depends on an instructor's endorsement, not on hours. Those are
reported as `manual` — listed, unchecked, and never counted toward a total that looks
complete.

*It reports, it does not certify.* Eligibility is determined by an instructor and an
examiner. The tool's job is to stop you discovering a missing 0.4 hours of night
cross-country the week of your checkride.

Hour requirements below were read from 14 CFR part 61. Verify against the current
eCFR text before relying on them; part 61 changes, and the MOSAIC rule in particular
has been moving the light-sport requirements.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logbook import SCHEMA_PATH, parse_date, totals, validate_book  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "training"
ECFR = "https://www.ecfr.gov/current/title-14/chapter-I/subchapter-D/part-61"

# Requirement kinds:
#   total          hours in a named bucket from logbook totals
#   dual           hours of dual_received
#   solo           hours of solo
#   flight         a specific qualifying flight, checked against entries where the
#                  logbook records enough to check it
#   manual         cannot be computed from a logbook; listed for completeness
CERTIFICATES: list[dict] = [
    {
        "id": "sport-airplane",
        "name": "Sport Pilot — Airplane",
        "cfr": "61.313(a)",
        "summary": "The lowest-hour path to carrying a passenger in a light-sport aircraft. "
                   "No medical required if you hold a valid US driver's licence.",
        "requirements": [
            {"kind": "total", "bucket": "total", "hours": 20, "cfr": "61.313(a)",
             "label": "Total flight time"},
            {"kind": "dual", "hours": 15, "cfr": "61.313(a)(1)",
             "label": "Flight training from an authorized instructor"},
            {"kind": "solo", "hours": 5, "cfr": "61.313(a)(2)", "label": "Solo flight time"},
            {"kind": "total", "bucket": "cross_country", "hours": 2, "cfr": "61.313(a)(1)(i)",
             "label": "Cross-country flight training"},
            {"kind": "manual", "cfr": "61.313(a)(1)(iii)",
             "label": "3 hours of preparation for the practical test within the preceding "
                      "2 calendar months"},
            {"kind": "manual", "cfr": "61.309",
             "label": "Aeronautical knowledge and instructor endorsements"},
        ],
    },
    {
        "id": "private-airplane-sel",
        "name": "Private Pilot — Airplane Single-Engine Land",
        "cfr": "61.109(a)",
        "summary": "The standard certificate for carrying passengers for pleasure or business.",
        "requirements": [
            {"kind": "total", "bucket": "total", "hours": 40, "cfr": "61.109(a)",
             "label": "Total flight time"},
            {"kind": "dual", "hours": 20, "cfr": "61.109(a)",
             "label": "Flight training from an authorized instructor"},
            {"kind": "solo", "hours": 10, "cfr": "61.109(a)",
             "label": "Solo flight time"},
            {"kind": "total", "bucket": "cross_country", "hours": 3, "cfr": "61.109(a)(1)",
             "label": "Cross-country flight training"},
            {"kind": "total", "bucket": "night", "hours": 3, "cfr": "61.109(a)(2)",
             "label": "Night flight training"},
            {"kind": "total", "bucket": "simulated_instrument", "hours": 3,
             "cfr": "61.109(a)(3)", "label": "Instrument training (actual or simulated)",
             "also": "actual_instrument"},
            {"kind": "flight", "test": "night_xc_100nm", "cfr": "61.109(a)(2)(i)",
             "label": "One night cross-country over 100 nm total distance"},
            {"kind": "flight", "test": "night_10_landings", "cfr": "61.109(a)(2)(ii)",
             "label": "10 night takeoffs and landings to a full stop at an airport"},
            {"kind": "total", "bucket": "cross_country", "hours": 5, "cfr": "61.109(a)(5)(i)",
             "label": "Solo cross-country time", "solo_only": True},
            {"kind": "flight", "test": "solo_xc_150nm", "cfr": "61.109(a)(5)(ii)",
             "label": "One solo cross-country of at least 150 nm total, landings at three "
                      "points, one leg at least 50 nm straight-line"},
            {"kind": "flight", "test": "towered_3_landings", "cfr": "61.109(a)(5)(iii)",
             "label": "3 solo takeoffs and landings to a full stop at a towered airport"},
            {"kind": "manual", "cfr": "61.109(a)(4)",
             "label": "3 hours of preparation for the practical test within the preceding "
                      "2 calendar months"},
            {"kind": "manual", "cfr": "61.105 / 61.107",
             "label": "Aeronautical knowledge test and areas of operation"},
            {"kind": "manual", "cfr": "61.23",
             "label": "Medical certificate (or BasicMed where applicable)"},
        ],
    },
    {
        "id": "instrument-airplane",
        "name": "Instrument Rating — Airplane",
        "cfr": "61.65(d)",
        "summary": "Lets you fly in instrument meteorological conditions under IFR.",
        "requirements": [
            {"kind": "total", "bucket": "cross_country", "hours": 50, "cfr": "61.65(d)(1)",
             "label": "Cross-country time as pilot in command", "pic_only": True},
            {"kind": "total", "bucket": "actual_instrument", "hours": 40, "cfr": "61.65(d)(2)",
             "label": "Actual or simulated instrument time", "also": "simulated_instrument"},
            {"kind": "dual_instrument", "hours": 15, "cfr": "61.65(d)(2)",
             "label": "Instrument flight training from an authorized instrument instructor"},
            {"kind": "flight", "test": "ifr_xc_250nm", "cfr": "61.65(d)(2)(ii)",
             "label": "One IFR cross-country of at least 250 nm along airways or ATC-directed "
                      "routing, with an instrument approach at each airport and three "
                      "different kinds of approaches"},
            {"kind": "manual", "cfr": "61.65(d)(2)(i)",
             "label": "3 hours of instrument flight training within the preceding "
                      "2 calendar months"},
            {"kind": "manual", "cfr": "61.65(a)(2)",
             "label": "Instrument knowledge test"},
        ],
    },
    {
        "id": "commercial-airplane-sel",
        "name": "Commercial Pilot — Airplane Single-Engine Land",
        "cfr": "61.129(a)",
        "summary": "Lets you be paid to fly. The big jump in hour requirements.",
        "requirements": [
            {"kind": "total", "bucket": "total", "hours": 250, "cfr": "61.129(a)",
             "label": "Total flight time"},
            {"kind": "total", "bucket": "pilot_in_command", "hours": 100, "cfr": "61.129(a)(2)",
             "label": "Pilot in command time"},
            {"kind": "total", "bucket": "cross_country", "hours": 50, "cfr": "61.129(a)(2)(i)",
             "label": "Cross-country time as pilot in command", "pic_only": True},
            {"kind": "total", "bucket": "night", "hours": 5, "cfr": "61.129(a)(4)(ii)",
             "label": "Night flight time"},
            {"kind": "dual", "hours": 20, "cfr": "61.129(a)(3)",
             "label": "Flight training from an authorized instructor"},
            {"kind": "dual_instrument", "hours": 10, "cfr": "61.129(a)(3)(i)",
             "label": "Instrument training, at least 5 hours in a single-engine airplane"},
            {"kind": "flight", "test": "day_xc_100nm_2h", "cfr": "61.129(a)(3)(iii)",
             "label": "One 2-hour day cross-country over 100 nm from departure"},
            {"kind": "flight", "test": "night_xc_100nm_2h", "cfr": "61.129(a)(3)(iv)",
             "label": "One 2-hour night cross-country over 100 nm from departure"},
            {"kind": "flight", "test": "commercial_xc_300nm", "cfr": "61.129(a)(4)(i)",
             "label": "One cross-country of at least 300 nm total with landings at three "
                      "points, one at least 250 nm straight-line from departure"},
            {"kind": "manual", "cfr": "61.129(a)(3)(ii)",
             "label": "10 hours in a complex, turbine-powered or technically advanced airplane"},
            {"kind": "manual", "cfr": "61.129(a)(3)(v)",
             "label": "3 hours of preparation for the practical test within the preceding "
                      "2 calendar months"},
            {"kind": "manual", "cfr": "61.125",
             "label": "Commercial knowledge test"},
        ],
    },
    {
        "id": "cfi-airplane",
        "name": "Flight Instructor — Airplane",
        "cfr": "61.183",
        "summary": "Lets you teach. Requires a commercial or ATP certificate first.",
        "requirements": [
            {"kind": "manual", "cfr": "61.183(a)",
             "label": "Hold a commercial or airline transport pilot certificate"},
            {"kind": "total", "bucket": "pilot_in_command", "hours": 250, "cfr": "61.129",
             "label": "Pilot in command time (via the commercial prerequisite)"},
            {"kind": "manual", "cfr": "61.183(c)",
             "label": "Instrument rating for airplane category"},
            {"kind": "manual", "cfr": "61.183(f)",
             "label": "15 hours as pilot in command in the category and class sought"},
            {"kind": "manual", "cfr": "61.183(d)",
             "label": "Fundamentals of instructing knowledge test"},
            {"kind": "manual", "cfr": "61.183(i)",
             "label": "Spin training and an instructor endorsement on spin awareness"},
        ],
    },
    {
        "id": "atp-airplane",
        "name": "Airline Transport Pilot — Airplane",
        "cfr": "61.159(a)",
        "summary": "The airline certificate. Restricted-privileges ATP has lower minimums "
                   "under 61.160, which this does not model.",
        "requirements": [
            {"kind": "total", "bucket": "total", "hours": 1500, "cfr": "61.159(a)",
             "label": "Total flight time"},
            {"kind": "total", "bucket": "cross_country", "hours": 500, "cfr": "61.159(a)(1)",
             "label": "Cross-country flight time"},
            {"kind": "total", "bucket": "night", "hours": 100, "cfr": "61.159(a)(2)",
             "label": "Night flight time"},
            {"kind": "total", "bucket": "actual_instrument", "hours": 75, "cfr": "61.159(a)(3)",
             "label": "Instrument time, actual or simulated", "also": "simulated_instrument"},
            {"kind": "total", "bucket": "pilot_in_command", "hours": 250, "cfr": "61.159(a)(4)",
             "label": "Pilot in command time"},
            {"kind": "manual", "cfr": "61.156",
             "label": "ATP certification training program before the knowledge test"},
            {"kind": "manual", "cfr": "61.153",
             "label": "Age 23, or 21 for a restricted-privileges ATP"},
        ],
    },
]


def hours(book: dict, bucket: str, *, pic_only=False, solo_only=False, also=None) -> float:
    """Sum a time bucket, optionally intersected with PIC or solo.

    Intersecting is approximate and deliberately conservative: a logbook records
    both cross_country and pilot_in_command for a flight but not the overlap
    between them, so this takes the smaller of the two per entry. It can understate
    and will not overstate, which is the right direction to be wrong in.
    """
    total = 0.0
    for e in book.get("entries", []):
        t = e.get("times", {})
        v = t.get(bucket) or 0.0
        if also:
            v += t.get(also) or 0.0
        if pic_only:
            v = min(v, t.get("pilot_in_command") or 0.0)
        if solo_only:
            v = min(v, t.get("solo") or 0.0)
        total += v

    cf = (book.get("carried_forward") or {}).get("totals") or {}
    if not (pic_only or solo_only):
        total += cf.get(bucket) or 0.0
        if also:
            total += cf.get(also) or 0.0
    return round(total, 1)


def dual_instrument(book: dict) -> float:
    """Instrument time flown as dual received, which is what 61.65(d)(2) counts."""
    total = 0.0
    for e in book.get("entries", []):
        t = e.get("times", {})
        inst = (t.get("actual_instrument") or 0.0) + (t.get("simulated_instrument") or 0.0)
        total += min(inst, t.get("dual_received") or 0.0)
    return round(total, 1)


def qualifying_flights(book: dict) -> dict[str, dict]:
    """Look for the specific flights the regulations name.

    Where the logbook does not record enough to decide -- a distance, or whether a
    landing was at a towered airport -- the result is 'unknown' rather than 'no'.
    Telling a student they have not met a requirement they may well have met is its
    own kind of wrong.
    """
    out: dict[str, dict] = {}
    ac = {a["id"]: a for a in book.get("aircraft", [])}

    def note(key, met, detail, unknown=False):
        out[key] = {"met": met, "unknown": unknown, "detail": detail}

    night_xc = [e for e in book["entries"]
                if (e.get("times", {}).get("night") or 0) > 0
                and (e.get("times", {}).get("cross_country") or 0) > 0]
    with_dist = [e for e in night_xc if (e.get("route") or {}).get("distance_nm")]
    over100 = [e for e in with_dist if e["route"]["distance_nm"] >= 100]
    if over100:
        note("night_xc_100nm", True, f"{over100[0]['date']}, "
             f"{over100[0]['route']['distance_nm']} nm")
    elif night_xc and not with_dist:
        note("night_xc_100nm", False, f"{len(night_xc)} night cross-country flight(s) logged "
             "but none records a distance", unknown=True)
    else:
        note("night_xc_100nm", False, "no night cross-country over 100 nm found")

    night_landings = sum((e.get("landings", {}).get("full_stop_night") or 0)
                         for e in book["entries"])
    note("night_10_landings", night_landings >= 10,
         f"{night_landings} night full-stop landing(s) logged")

    solo_xc = [e for e in book["entries"]
               if (e.get("times", {}).get("solo") or 0) > 0
               and (e.get("route") or {}).get("distance_nm")]
    solo150 = [e for e in solo_xc if e["route"]["distance_nm"] >= 150]
    if solo150:
        note("solo_xc_150nm", True, f"{solo150[0]['date']}, {solo150[0]['route']['distance_nm']} nm "
             "— confirm three points and a 50 nm leg")
    else:
        any_solo = [e for e in book["entries"] if (e.get("times", {}).get("solo") or 0) > 0]
        note("solo_xc_150nm", False,
             "no solo cross-country of 150 nm found"
             + (" (solo flights are logged but without distances)" if any_solo and not solo_xc else ""),
             unknown=bool(any_solo and not solo_xc))

    note("towered_3_landings", False,
         "cannot be determined from a logbook — whether an airport had an operating "
         "control tower is not a logged field", unknown=True)

    ifr = [e for e in book["entries"]
           if len((e.get("instrument") or {}).get("approaches") or []) >= 3
           and ((e.get("route") or {}).get("distance_nm") or 0) >= 250]
    if ifr:
        kinds = {a["type"] for a in ifr[0]["instrument"]["approaches"]}
        note("ifr_xc_250nm", len(kinds) >= 3,
             f"{ifr[0]['date']}, {ifr[0]['route']['distance_nm']} nm, "
             f"{len(kinds)} kind(s) of approach: {', '.join(sorted(kinds))}")
    else:
        note("ifr_xc_250nm", False, "no IFR cross-country of 250 nm with three approach types found")

    for key, need_night, hrs in (("day_xc_100nm_2h", False, 2.0), ("night_xc_100nm_2h", True, 2.0)):
        cands = [e for e in book["entries"]
                 if (e.get("times", {}).get("total") or 0) >= hrs
                 and ((e.get("route") or {}).get("distance_nm") or 0) >= 100
                 and (((e.get("times", {}).get("night") or 0) > 0) == need_night
                      or (not need_night and (e.get("times", {}).get("day") or 0) > 0))]
        note(key, bool(cands),
             f"{cands[0]['date']}, {cands[0]['route']['distance_nm']} nm, "
             f"{cands[0]['times']['total']} h" if cands else "not found")

    xc300 = [e for e in book["entries"]
             if ((e.get("route") or {}).get("distance_nm") or 0) >= 300]
    note("commercial_xc_300nm", bool(xc300),
         f"{xc300[0]['date']}, {xc300[0]['route']['distance_nm']} nm — confirm three points "
         "and a 250 nm leg" if xc300 else "no cross-country of 300 nm found")

    return out


def progress(book: dict, cert: dict) -> dict:
    flights = qualifying_flights(book)
    rows = []
    met = unmet = manual = unknown = 0

    for req in cert["requirements"]:
        kind = req["kind"]
        row = {"label": req["label"], "cfr": req["cfr"], "kind": kind}

        if kind == "manual":
            row["status"] = "manual"
            manual += 1
        elif kind == "flight":
            f = flights.get(req["test"], {"met": False, "unknown": True, "detail": "not evaluated"})
            row["detail"] = f["detail"]
            if f["unknown"]:
                row["status"] = "unknown"
                unknown += 1
            else:
                row["status"] = "met" if f["met"] else "short"
                met += f["met"]
                unmet += not f["met"]
        else:
            if kind == "dual":
                have = hours(book, "dual_received")
            elif kind == "solo":
                have = hours(book, "solo")
            elif kind == "dual_instrument":
                have = dual_instrument(book)
            else:
                have = hours(book, req["bucket"], pic_only=req.get("pic_only", False),
                             solo_only=req.get("solo_only", False), also=req.get("also"))
            need = req["hours"]
            row.update({"have": have, "need": need,
                        "remaining": round(max(0.0, need - have), 1),
                        "status": "met" if have >= need else "short"})
            # Intersected buckets cannot use carried-forward totals, because a lump
            # sum records no per-flight overlap. Say so rather than quietly
            # dropping the hours -- a student would otherwise think the tool had
            # lost them.
            cf = (book.get("carried_forward") or {}).get("totals") or {}
            if (req.get("pic_only") or req.get("solo_only")) and cf.get(req.get("bucket")):
                row["note"] = (
                    f"excludes {cf[req['bucket']]} h of carried-forward "
                    f"{req['bucket'].replace('_', ' ')}, because a carried-forward total "
                    "records no overlap with PIC or solo time — count those by hand"
                )
            met += have >= need
            unmet += have < need
        rows.append(row)

    return {
        "certificate": cert["id"],
        "name": cert["name"],
        "cfr": cert["cfr"],
        "counts": {"met": met, "short": unmet, "manual": manual, "unknown": unknown},
        "requirements": rows,
    }


def emit(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "notice": (
            "Aeronautical experience requirements read from 14 CFR part 61. An aid, not an "
            "authority: eligibility is determined by an instructor and an examiner, part 61 "
            "changes, and requirements marked 'manual' cannot be computed from a logbook. "
            "Verify against the current eCFR text."
        ),
        "ecfr": ECFR,
        "certificates": CERTIFICATES,
    }
    (out / "certificates.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("requirements"); r.add_argument("cert")
    p = sub.add_parser("progress"); p.add_argument("logbook", type=Path)
    p.add_argument("--for", dest="cert", required=True)
    e = sub.add_parser("emit"); e.add_argument("-o", "--out", type=Path, default=OUT)
    args = ap.parse_args()

    by_id = {c["id"]: c for c in CERTIFICATES}

    if args.cmd == "list":
        for c in CERTIFICATES:
            n = sum(1 for r in c["requirements"] if r["kind"] != "manual")
            print(f"  {c['id']:<26} {c['name']}  ({c['cfr']}, {n} computable requirement(s))")
        return 0

    if args.cmd == "emit":
        payload = emit(args.out)
        print(f"wrote {args.out / 'certificates.json'}: {len(payload['certificates'])} certificates")
        return 0

    if args.cmd == "requirements":
        c = by_id.get(args.cert)
        if not c:
            raise SystemExit(f"unknown certificate {args.cert!r}; try: training.py list")
        print(f"{c['name']}  ({c['cfr']})\n  {c['summary']}\n")
        for req in c["requirements"]:
            tag = "manual" if req["kind"] == "manual" else (
                f"{req['hours']} h" if req.get("hours") else "flight")
            print(f"  [{tag:>8}] {req['label']}")
            print(f"             {req['cfr']}")
        print(f"\n  Authority: {ECFR}")
        return 0

    c = by_id.get(args.cert)
    if not c:
        raise SystemExit(f"unknown certificate {args.cert!r}; try: training.py list")
    schema = json.loads(SCHEMA_PATH.read_text())
    f, book = validate_book(args.logbook, schema)
    if book is None:
        for m in f.errors:
            print(f"error: {m}")
        return 1

    res = progress(book, c)
    t = totals(book)
    print(f"{res['name']}  ({res['cfr']})")
    print(f"  logbook: {t['times'].get('total', 0)} h total, {res['counts']['met']} requirement(s) met, "
          f"{res['counts']['short']} short, {res['counts']['unknown']} undetermined, "
          f"{res['counts']['manual']} to confirm manually\n")
    for row in res["requirements"]:
        if row["status"] == "met":
            mark = "MET "
        elif row["status"] == "short":
            mark = "SHORT"
        elif row["status"] == "unknown":
            mark = " ?  "
        else:
            mark = "----"
        line = f"  [{mark}] {row['label']}"
        print(line)
        if "have" in row:
            extra = f"have {row['have']} of {row['need']} h"
            if row["remaining"]:
                extra += f", {row['remaining']} h remaining"
            print(f"          {extra}   ({row['cfr']})")
            if row.get("note"):
                print(f"          note: {row['note']}")
        else:
            print(f"          {row.get('detail', 'confirm with your instructor')}   ({row['cfr']})")
    print("\n  Reported from your logbook, not a determination of eligibility. Requirements")
    print("  marked ---- cannot be computed from a logbook; ? means your logbook does not")
    print(f"  record enough to decide. Authority: {ECFR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
