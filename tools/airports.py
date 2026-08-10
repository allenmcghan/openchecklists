#!/usr/bin/env python3
"""Ingest FAA NASR airport, runway and frequency data into static JSON.

    python3 tools/airports.py ingest /path/to/28DaySubscription_Effective_YYYY-MM-DD.zip
    python3 tools/airports.py show KFDK

Source: the FAA's 28 Day NASR Subscription, a work of the US Government in the
public domain. The subscriber bundle contains a CSV_Data zip; this reads that
rather than the 232 MB fixed-width APT.txt.

Output under data/airports/:

    cycle.json          effective date and record counts
    index.json          every airport, compact, for client-side search
    detail/<C>.json     full records sharded by first character of the identifier

Sharding matters: 19,426 airports would be 19,426 files as individual pages, which
makes a static build slow and a deploy heavy. One lean index plus ~36 detail shards
keeps the file count small, the search instant, and the whole thing cacheable for
offline use.

**On staleness, which is the honest problem with this data.** NASR is published on a
28-day cycle. A snapshot goes out of date, and a frequency that has changed is worse
than no frequency. So the effective date is recorded in the data, shown on every
airport page, and `cycle.json` carries the next cycle date so the site can say how
old what you are reading is. This is the same discipline the checklist corpus
applies to its own source revisions.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "airports"

# NASR frequency use codes to something a pilot reads. Unknown codes pass through
# unchanged rather than being dropped -- a frequency you cannot label is still a
# frequency, and guessing at it would be worse.
FREQ_USE = {
    "CTAF": "CTAF",
    "UNICOM": "UNICOM",
    "LCL/P": "Tower",
    "LCL/S": "Tower (secondary)",
    "GND/P": "Ground",
    "GND/S": "Ground (secondary)",
    "CD/P": "Clearance delivery",
    "ATIS": "ATIS",
    "AWOS": "AWOS",
    "ASOS": "ASOS",
    "EMERG": "Emergency",
    "APCH/P": "Approach",
    "DEP/P": "Departure",
    "APCH/P DEP/P": "Approach / Departure",
    "APCH/P DEP/P IC": "Approach / Departure (initial contact)",
    "CLASS B": "Class B",
    "CLASS C": "Class C",
    "CLASS D": "Class D",
    "CLASS E": "Class E",
    "TRSA": "TRSA",
    "PTD": "Pre-taxi clearance",
    "RDO": "Radio",
    "FSS": "Flight Service",
    "RCO": "Remote comm outlet",
    "DIRCTY": "Direct",
    "TMA": "Terminal",
}

SITE_TYPE = {"A": "airport", "H": "heliport", "C": "seaplane base", "G": "gliderport",
             "B": "balloonport", "U": "ultralight"}
USE = {"PU": "public", "PR": "private"}
OWNER = {"PU": "public", "PR": "private", "MA": "air force", "MN": "navy",
         "MR": "army", "CG": "coast guard"}
SURFACE = {"ASPH": "asphalt", "CONC": "concrete", "TURF": "turf", "GRVL": "gravel",
           "DIRT": "dirt", "WATER": "water", "SNOW": "snow", "MATS": "mats",
           "TREATED": "treated", "GRASS": "grass"}


def rows(z: zipfile.ZipFile, name: str):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"))


def num(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def find_csv_bundle(path: Path) -> zipfile.ZipFile:
    """The subscription zip contains an inner CSV_Data zip; accept either."""
    z = zipfile.ZipFile(path)
    names = z.namelist()
    if "APT_BASE.csv" in names:
        return z
    inner = [n for n in names if n.startswith("CSV_Data/") and n.lower().endswith(".zip")]
    if not inner:
        raise SystemExit(
            f"{path.name} contains neither APT_BASE.csv nor a CSV_Data/*.zip; "
            "is this a NASR subscriber file?"
        )
    return zipfile.ZipFile(io.BytesIO(z.read(inner[0])))


def ingest(path: Path, out: Path) -> dict:
    z = find_csv_bundle(path)
    have = set(z.namelist())

    airports: dict[str, dict] = {}
    eff_dates: set[str] = set()

    for r in rows(z, "APT_BASE.csv"):
        ident = (r.get("ARPT_ID") or "").strip()
        if not ident:
            continue
        if r.get("EFF_DATE"):
            eff_dates.add(r["EFF_DATE"])
        lat, lon = num(r.get("LAT_DECIMAL")), num(r.get("LONG_DECIMAL"))
        airports[ident] = {
            "ident": ident,
            "icao": (r.get("ICAO_ID") or "").strip() or None,
            "name": (r.get("ARPT_NAME") or "").strip(),
            "city": (r.get("CITY") or "").strip(),
            "state": (r.get("STATE_CODE") or "").strip(),
            "state_name": (r.get("STATE_NAME") or "").strip(),
            "county": (r.get("COUNTY_NAME") or "").strip(),
            "type": SITE_TYPE.get(r.get("SITE_TYPE_CODE", ""), r.get("SITE_TYPE_CODE", "")),
            "use": USE.get(r.get("FACILITY_USE_CODE", ""), r.get("FACILITY_USE_CODE", "")),
            "owner": OWNER.get(r.get("OWNERSHIP_TYPE_CODE", ""), r.get("OWNERSHIP_TYPE_CODE", "")),
            "lat": lat,
            "lon": lon,
            "elevation_ft": num(r.get("ELEV")),
            "magnetic_variation": (r.get("MAG_VARN") or "").strip()
            + (r.get("MAG_HEMIS") or "").strip(),
            "pattern_altitude_ft": num(r.get("TPA")),
            "sectional": (r.get("CHART_NAME") or "").strip(),
            "fuel": (r.get("FUEL_TYPES") or "").strip(),
            "manager": (r.get("MANAGER") or "").strip(),
            "manager_phone": (r.get("MANAGER_PHONE_NO") or "").strip(),
            "attendance": (r.get("ARPT_STATUS") or "").strip(),
            "runways": [],
            "frequencies": [],
            "remarks": [],
        }

    for r in rows(z, "APT_RWY.csv"):
        a = airports.get((r.get("ARPT_ID") or "").strip())
        if not a:
            continue
        a["runways"].append({
            "id": (r.get("RWY_ID") or "").strip(),
            "length_ft": num(r.get("RWY_LEN")),
            "width_ft": num(r.get("RWY_WIDTH")),
            "surface": SURFACE.get((r.get("SURFACE_TYPE_CODE") or "").strip(),
                                   (r.get("SURFACE_TYPE_CODE") or "").strip()),
            "condition": (r.get("COND") or "").strip(),
            "lighting": (r.get("RWY_LGT_CODE") or "").strip(),
        })

    # Runway end data adds true/magnetic headings, which is what a pilot actually
    # wants when picking a runway from the wind.
    if "APT_RWY_END.csv" in have:
        ends: dict[tuple[str, str], list] = defaultdict(list)
        for r in rows(z, "APT_RWY_END.csv"):
            ident = (r.get("ARPT_ID") or "").strip()
            rwy = (r.get("RWY_ID") or "").strip()
            end = (r.get("RWY_END_ID") or "").strip()
            if not (ident and rwy and end):
                continue
            ends[(ident, rwy)].append({
                "end": end,
                "true_heading": num(r.get("TRUE_ALIGNMENT")),
                "ils": (r.get("APCH_LGT_SYSTEM_CODE") or "").strip() or None,
                "displaced_threshold_ft": num(r.get("DISPLACED_THR_LEN")),
                "traffic_pattern": (r.get("RH_TRAFFIC_PAT_FLAG") or "").strip(),
            })
        for ident, a in airports.items():
            for rw in a["runways"]:
                got = ends.get((ident, rw["id"]))
                if got:
                    rw["ends"] = got

    for r in rows(z, "FRQ.csv"):
        ident = (r.get("SERVICED_FACILITY") or "").strip()
        a = airports.get(ident)
        freq = (r.get("FREQ") or "").strip()
        if not a or not freq:
            continue
        use = (r.get("FREQ_USE") or "").strip()
        a["frequencies"].append({
            "frequency": freq,
            "use": FREQ_USE.get(use, use),
            "use_code": use or None,
            "facility": (r.get("FAC_NAME") or "").strip() or None,
            "callsign": (r.get("TOWER_OR_COMM_CALL") or "").strip()
            or (r.get("PRIMARY_APPROACH_RADIO_CALL") or "").strip() or None,
            "hours": (r.get("TOWER_HRS") or "").strip() or None,
            "sector": (r.get("SECTORIZATION") or "").strip() or None,
            "remark": (r.get("REMARK") or "").strip() or None,
        })

    if "APT_RMK.csv" in have:
        for r in rows(z, "APT_RMK.csv"):
            a = airports.get((r.get("ARPT_ID") or "").strip())
            txt = (r.get("REMARK") or "").strip()
            # Capped deliberately: remarks were a third of the payload, and the
            # long tail is FAA internal notes rather than anything a pilot needs.
            if a and txt and len(a["remarks"]) < 8:
                a["remarks"].append({
                    "element": (r.get("REF_COL_NAME") or "").strip(),
                    "text": txt[:300],
                })

    # Tidy: order frequencies so the ones a VFR pilot needs first come first.
    priority = ["CTAF", "UNICOM", "Tower", "Ground", "Clearance delivery", "ATIS",
                "AWOS", "ASOS", "Approach / Documentation"]
    def freq_key(f):
        try:
            p = priority.index(f["use"])
        except ValueError:
            p = len(priority)
        return (p, f["use"] or "", f["frequency"])
    for a in airports.values():
        a["frequencies"].sort(key=freq_key)
        a["runways"].sort(key=lambda r: -(r.get("length_ft") or 0))
        a["longest_runway_ft"] = a["runways"][0]["length_ft"] if a["runways"] else None
        a["has_hard_surface"] = any(
            (r.get("surface") or "").lower() in ("asphalt", "concrete") for r in a["runways"]
        )

    effective = sorted(eff_dates)[-1] if eff_dates else None
    eff_iso = None
    if effective:
        try:
            eff_iso = datetime.strptime(effective, "%Y/%m/%d").date().isoformat()
        except ValueError:
            eff_iso = effective

    out.mkdir(parents=True, exist_ok=True)
    (out / "detail").mkdir(exist_ok=True)

    # Compact index for search. Kept lean deliberately: this file is downloaded by
    # every visitor, so it carries only what search and the result list need.
    def r3(v):
        return round(v, 3) if isinstance(v, (int, float)) else None

    index = [
        {
            "i": a["ident"], "n": a["name"], "c": a["city"], "s": a["state"],
            "t": a["type"][:1], "u": a["use"][:2],
            "y": r3(a["lat"]), "x": r3(a["lon"]),
            "e": a["elevation_ft"], "r": a["longest_runway_ft"],
            "f": len(a["frequencies"]), "h": 1 if a["has_hard_surface"] else 0,
            **({"k": a["icao"]} if a.get("icao") else {}),
        }
        for a in sorted(airports.values(), key=lambda a: a["ident"])
    ]

    # NASR keys on the FAA identifier (FDK), but people type the ICAO one (KFDK),
    # and the two live in different shards. Ship the mapping rather than making
    # every consumer rediscover it.
    icao_map = {a["icao"]: a["ident"] for a in airports.values() if a.get("icao")}

    shards: dict[str, dict] = defaultdict(dict)
    for ident, a in airports.items():
        shards[shard_key(ident)][ident] = a
    for key, group in shards.items():
        (out / "detail" / f"{key}.json").write_text(
            json.dumps(group, separators=(",", ":"), ensure_ascii=False)
        )

    cycle = {
        "source": "FAA 28 Day NASR Subscription",
        "rights": {"status": "public_domain", "basis": "us_government_work"},
        "effective": eff_iso,
        "next_cycle": (date.fromisoformat(eff_iso) + timedelta(days=28)).isoformat()
        if eff_iso else None,
        "ingested_from": path.name,
        "counts": {
            "airports": len(airports),
            "runways": sum(len(a["runways"]) for a in airports.values()),
            "frequencies": sum(len(a["frequencies"]) for a in airports.values()),
            "public_use": sum(1 for a in airports.values() if a["use"] == "public"),
            "shards": len(shards),
        },
        "notice": (
            "Snapshot of a 28-day cycle, not live data. Frequencies and runway "
            "information change. Verify against the current Chart Supplement or the "
            "FAA source before use."
        ),
    }
    (out / "cycle.json").write_text(json.dumps(cycle, indent=2) + "\n")
    (out / "index.json").write_text(json.dumps(index, separators=(",", ":"), ensure_ascii=False))
    (out / "icao.json").write_text(json.dumps(icao_map, separators=(",", ":")))
    cycle["counts"]["icao_mapped"] = len(icao_map)
    return cycle


def shard_key(ident: str) -> str:
    c = ident[0].upper()
    return c if c.isalnum() else "_"


def show(ident: str, out: Path) -> int:
    ident = ident.upper()
    f = out / "detail" / f"{shard_key(ident)}.json"
    if not f.exists():
        raise SystemExit(f"no data ingested yet; run: airports.py ingest <nasr.zip>")
    # Resolve an ICAO identifier to the FAA one first, since they can live in
    # different shards: KFDK is ICAO for FDK, which is in shard F, not K.
    icao_path = out / "icao.json"
    if icao_path.exists():
        mapped = json.loads(icao_path.read_text()).get(ident)
        if mapped and mapped != ident:
            ident = mapped
            f = out / "detail" / f"{shard_key(ident)}.json"
    if not f.exists():
        print(f"{ident} not found")
        return 1
    data = json.loads(f.read_text())
    a = data.get(ident)
    if not a:
        print(f"{ident} not found in shard {shard_key(ident)}")
        return 1

    print(f"{a['ident']}  {a['name']}  ({a['city']}, {a['state']})")
    print(f"  {a['type']}, {a['use']} use, {a['owner']}-owned"
          f"{'  ICAO ' + a['icao'] if a.get('icao') else ''}")
    print(f"  {a['lat']}, {a['lon']}  elev {a['elevation_ft']} ft"
          f"  var {a['magnetic_variation']}"
          + (f"  pattern {a['pattern_altitude_ft']} ft" if a.get("pattern_altitude_ft") else ""))
    if a.get("sectional"):
        print(f"  sectional: {a['sectional']}")
    if a.get("fuel"):
        print(f"  fuel: {a['fuel']}")
    if a["frequencies"]:
        print("  frequencies:")
        for f_ in a["frequencies"]:
            extra = f"  [{f_['callsign']}]" if f_.get("callsign") else ""
            print(f"    {f_['frequency']:>9}  {f_['use']}{extra}")
    if a["runways"]:
        print("  runways:")
        for r in a["runways"]:
            print(f"    {r['id']:>9}  {r['length_ft']}x{r['width_ft']} ft  {r['surface']}"
                  f"  {r.get('condition','')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest"); i.add_argument("zip", type=Path)
    i.add_argument("-o", "--out", type=Path, default=OUT)
    s = sub.add_parser("show"); s.add_argument("ident")
    s.add_argument("-o", "--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.cmd == "ingest":
        cycle = ingest(args.zip, args.out)
        print(json.dumps(cycle, indent=2))
        return 0
    return show(args.ident, args.out)


if __name__ == "__main__":
    sys.exit(main())
