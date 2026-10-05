#!/usr/bin/env python3
"""Nearest-airport data and "Airports near <city>" pages.

Both come from one k-nearest-neighbour pass over the 19k-row airport index at build
time, so neither the browser nor the /airport/<id> Pages Function ever has to load
the whole index to answer "what's near here?".

Outputs:
  data/airports/near/<KK>.json  — per airport (keyed by FAA ident, sharded by the
      first two characters so a page fetches ~25 KB, not megabytes): the 10 nearest
      airports plus the nearest public-use field with fuel and with a runway of at
      least 3,000 ft.
  airports-near/<city>-<st>/    — static pages for cities with 2+ airports within
      25 nm, capped so the deploy stays far under the Pages 20,000-file limit.

There is no city gazetteer in the data, so a city's position is the median of the
facilities that list it as their city. That is stated on the page.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

NM_PER_RAD = 3440.065
NEAR_K = 10
QUICK_K = 3
QUICK_MAX_NM = 150
CITY_RADIUS_NM = 25
CITY_PAGE_CAP = 1500
# Heliports and balloonports are mostly private hospital/corporate pads: noise in a
# "where can I land" list. They still get their own nearest list.
NEIGHBOUR_TYPES = {"a", "s", "u", "g"}
TYPE_NAMES = {"a": "Airport", "h": "Heliport", "s": "Seaplane base", "u": "Ultralight",
              "g": "Gliderport", "b": "Balloonport"}

ABBR = {"RGNL": "Regional", "INTL": "International", "MUNI": "Municipal", "ARPT": "Airport",
        "FLD": "Field", "MEML": "Memorial", "EXEC": "Executive", "CNTY": "County", "ARPK": "Airpark"}
KEEP = {"AFB", "NAS", "ARB", "LLC", "II", "III"}


def nice(s: str) -> str:
    """Python twin of titleCase()/niceName() in the Function and client template."""
    out = []
    for w in re.split(r"(\s+|-|/)", str(s or "")):
        u = w.upper()
        if u in ABBR:
            out.append(ABBR[u])
        elif u in KEEP:
            out.append(u)
        else:
            lw = w.lower()
            out.append(lw[:1].upper() + lw[1:] if lw[:1].isalpha() else lw)
    return "".join(out)


def shard_key(ident: str) -> str:
    """First two characters of the FAA ident; must match nearKey() in the JS."""
    return "".join(c if re.match(r"[A-Z0-9]", c) else "_" for c in (ident or "__").upper()[:2]).ljust(2, "_")


def dist_brg(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Great-circle distance (nm) and initial true bearing (deg) from point 1 to 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * NM_PER_RAD * math.asin(min(1.0, math.sqrt(h)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(brg: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((brg + 22.5) // 45) % 8]


class Grid:
    """1-degree buckets; k-nearest by expanding rings until nothing closer can exist."""

    def __init__(self, rows: list[dict]):
        self.cells: dict[tuple[int, int], list[dict]] = {}
        for r in rows:
            self.cells.setdefault((math.floor(r["y"]), math.floor(r["x"])), []).append(r)

    def nearest(self, lat: float, lon: float, k: int, skip: str = "", max_nm: float = 1e9,
                max_ring: int = 40) -> list[tuple[float, float, dict]]:
        cy, cx = math.floor(lat), math.floor(lon)
        found: list[tuple[float, float, dict]] = []
        for ring in range(max_ring + 1):
            for gy in range(cy - ring, cy + ring + 1):
                for gx in range(cx - ring, cx + ring + 1):
                    if max(abs(gy - cy), abs(gx - cx)) != ring:
                        continue
                    for r in self.cells.get((gy, gx), ()):
                        if r["i"] == skip:
                            continue
                        d, b = dist_brg(lat, lon, r["y"], r["x"])
                        if d <= max_nm:
                            found.append((d, b, r))
            # Anything outside this ring is at least `ring` cells away; a cell is
            # 60 nm tall but only 60*cos(lat) nm wide, so use the narrower side.
            edge = ring * 60 * max(0.05, math.cos(math.radians(min(89.0, abs(lat) + ring + 1))))
            found.sort(key=lambda t: t[0])
            if (len(found) >= k and found[k - 1][0] <= edge) or edge > max_nm:
                break
        return found[:k]


def load_details(detail_dir: Path) -> dict[str, dict]:
    recs: dict[str, dict] = {}
    for f in sorted(detail_dir.glob("*.json")):
        recs.update(json.loads(f.read_text()))
    return recs


def _entry(d: float, b: float, r: dict, det: dict) -> list:
    """Compact row: [url id, name, city, st, nm, brg true, longest rwy, fuel, use, type, hard]."""
    a = det.get(r["i"], {})
    return [r.get("k") or r["i"], r.get("n") or "", r.get("c") or "", r.get("s") or "",
            round(d, 1), round(b), r.get("r") or 0, a.get("fuel") or "", r.get("u") or "",
            r.get("t") or "", 1 if r.get("h") else 0]


def _city_slug(city: str, st: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-" + st.lower()).strip("-")


def _median(v: list[float]) -> float:
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def compute(index_rows: list[dict], details: dict[str, dict]) -> dict:
    """Nearest lists for every airport plus the chosen city pages."""
    rows = [r for r in index_rows if r.get("y") is not None and r.get("x") is not None]
    land = [r for r in rows if r.get("t") in NEIGHBOUR_TYPES]
    pub_fuel = [r for r in land if r.get("u") == "pu" and (details.get(r["i"], {}).get("fuel") or "").strip()]
    pub_long = [r for r in land if r.get("u") == "pu" and (r.get("r") or 0) >= 3000]
    g_land, g_fuel, g_long = Grid(land), Grid(pub_fuel), Grid(pub_long)

    # City candidates: every (city, state) any facility names.
    by_city: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        c, s = (r.get("c") or "").strip(), (r.get("s") or "").strip()
        if c and s:
            by_city.setdefault((c.upper(), s.upper()), []).append(r)
    cands = []
    for (c, s), members in by_city.items():
        lat = _median([m["y"] for m in members])
        lon = _median([m["x"] for m in members])
        near = g_land.nearest(lat, lon, 60, max_nm=CITY_RADIUS_NM, max_ring=1)
        if len(near) < 2:
            continue
        pub = sum(1 for t in near if t[2].get("u") == "pu")
        heli = sum(1 for m in members if m.get("t") == "h")
        own = any(m.get("u") == "pu" and m.get("k") and m.get("t") == "a" for m in members)
        # Population proxy. Cities with their own public ICAO airport come first
        # (that's what people search for), then: big cities have many facilities
        # carrying their name — heliports (hospitals, police, news) especially —
        # and many public fields around them. Raw private-strip counts would
        # otherwise favour rural Alaska and metro suburbs.
        cands.append({"city": c, "st": s, "lat": lat, "lon": lon, "near": near, "own": own,
                      "score": 2 * len(members) + 3 * heli + 4 * pub + len(near)})
    cands.sort(key=lambda c: (not c["own"], -c["score"], c["city"]))
    cities = cands[:CITY_PAGE_CAP]
    seen: set[str] = set()
    for c in cities:
        slug = _city_slug(c["city"], c["st"])
        while slug in seen:
            slug += "-2"
        seen.add(slug)
        c["slug"] = slug
    city_by_key = {(c["city"], c["st"]): c for c in cities}
    g_city = Grid([{"i": c["slug"], "y": c["lat"], "x": c["lon"], "c": c} for c in cities])

    near: dict[str, dict] = {}
    for r in rows:
        rec: dict = {
            "n": [_entry(d, b, o, details) for d, b, o in g_land.nearest(r["y"], r["x"], NEAR_K, skip=r["i"])],
            "f": [_entry(d, b, o, details) for d, b, o in
                  g_fuel.nearest(r["y"], r["x"], QUICK_K, skip=r["i"], max_nm=QUICK_MAX_NM, max_ring=4)],
            "l": [_entry(d, b, o, details) for d, b, o in
                  g_long.nearest(r["y"], r["x"], QUICK_K, skip=r["i"], max_nm=QUICK_MAX_NM, max_ring=4)],
        }
        # Link the airport to its own city's page, else the closest city page in range.
        cp = city_by_key.get(((r.get("c") or "").upper(), (r.get("s") or "").upper()))
        if not cp:
            hit = g_city.nearest(r["y"], r["x"], 1, max_nm=CITY_RADIUS_NM, max_ring=1)
            cp = hit[0][2]["c"] if hit else None
        if cp:
            rec["cp"] = [cp["slug"], f'{nice(cp["city"])}, {cp["st"]}']
        near[r["i"]] = rec
    return {"near": near, "cities": cities, "city_grid": g_city}


def write_near_shards(dest: Path, data: dict) -> list[Path]:
    shards: dict[str, dict] = {}
    for ident, rec in data["near"].items():
        shards.setdefault(shard_key(ident), {})[ident] = rec
    out = dest / "near"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, v in sorted(shards.items()):
        p = out / f"{k}.json"
        p.write_text(json.dumps(v, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        paths.append(p)
    return paths


def _freqs(a: dict) -> str:
    ctaf = tower = ""
    for f in a.get("frequencies") or []:
        use = (f.get("use") or "").upper()
        if not ctaf and use in ("CTAF", "UNICOM"):
            ctaf = f"{use} {f.get('frequency') or ''}".strip()
        if not tower and use == "TOWER":
            tower = f"Tower {f.get('frequency') or ''}".strip()
    return " · ".join(x for x in (tower, ctaf) if x)


CITY_CSS = ("<style>.nearcity td.n,.nearcity th.n{text-align:right;white-space:nowrap}"
            ".nearcity td{vertical-align:top}.nearcity .sub{font-size:.8rem;color:var(--muted)}"
            "ul.cols{columns:3 12rem;padding-left:1.1rem}</style>")


def write_city_pages(out: Path, data: dict, details: dict[str, dict], head, foot: str, esc,
                     state_names: dict[str, str], brand: str, effective: str) -> tuple[list[str], dict[str, list]]:
    """Write /airports-near/<slug>/ pages. Returns (sitemap paths, {state: [(slug, label)]})."""
    base = out / "airports-near"
    paths: list[str] = []
    by_state: dict[str, list] = {}
    for c in data["cities"]:
        city, st = nice(c["city"]), c["st"]
        stname = state_names.get(st, st)
        land = c["near"]
        pub = [t for t in land if t[2].get("u") == "pu"]
        rows_html = []
        for d, b, r in land:
            a = details.get(r["i"], {})
            uid = r.get("k") or r["i"]
            fuel = a.get("fuel") or ""
            rows_html.append(
                f'<tr><td><a href="/airport/{esc(uid)}"><b>{esc(uid)}</b></a></td>'
                f'<td>{esc(nice(r.get("n")))}<div class="sub">{esc(nice(r.get("c")))}'
                f' &middot; {esc(TYPE_NAMES.get(r.get("t"), ""))}</div></td>'
                f'<td class="n">{d:.1f} nm {compass(b)}</td>'
                f'<td>{"Public" if r.get("u") == "pu" else "Private"}</td>'
                + (f'<td class="n">water</td>' if r.get("t") == "s" else
                   f'<td class="n">{(r.get("r") or 0):,} ft{"" if r.get("h") else " <span class=sub>(soft)</span>"}</td>')
                + f'<td>{esc(fuel) or "—"}</td><td>{esc(_freqs(a)) or "—"}</td></tr>')
        best_fuel = next((t for t in pub if (details.get(t[2]["i"], {}).get("fuel") or "").strip()), None)
        # Water lanes (seaplane bases) list as 10,000 ft "runways"; not what people mean.
        longest = max([t for t in land if t[2].get("t") != "s"] or land, key=lambda t: t[2].get("r") or 0)
        facts = []
        if pub:
            d, b, r = pub[0]
            facts.append(f'Closest public-use field: <a href="/airport/{esc(r.get("k") or r["i"])}">'
                         f'{esc(nice(r.get("n")))} ({esc(r.get("k") or r["i"])})</a>, {d:.1f} nm {compass(b)}.')
        if best_fuel:
            d, b, r = best_fuel
            facts.append(f'Closest public fuel: <a href="/airport/{esc(r.get("k") or r["i"])}">'
                         f'{esc(r.get("k") or r["i"])}</a> ({esc(details.get(r["i"], {}).get("fuel"))}), {d:.1f} nm.')
        d, b, r = longest
        facts.append(f'Longest runway: {(r.get("r") or 0):,} ft at <a href="/airport/{esc(r.get("k") or r["i"])}">'
                     f'{esc(r.get("k") or r["i"])}</a>.')
        metar_ids = ",".join(t[2]["k"] for t in pub if t[2].get("k"))[:200].rstrip(",")
        others = [o[2]["c"] for o in data["city_grid"].nearest(c["lat"], c["lon"], 9, skip=c["slug"], max_nm=60, max_ring=1)]
        near_cities = "".join(f'<li><a href="/airports-near/{esc(o["slug"])}/">{esc(nice(o["city"]))}, {esc(o["st"])}</a></li>'
                              for o in others[:8])
        body = (
            CITY_CSS
            + f'<h2>Airports near {esc(city)}, {esc(st)}</h2>'
            f'<p class="lede">{len(land)} airports, seaplane bases and airstrips within {CITY_RADIUS_NM} nm of '
            f'{esc(city)}, {esc(stname)} — {len(pub)} of them public use. Runway lengths, fuel, CTAF and tower '
            f'frequencies from the FAA\'s NASR data (effective {esc(effective)}); each airport page adds live '
            f'METAR/TAF weather, NOTAMs, winds aloft and a crosswind calculator.</p>'
            f'<p>{" ".join(facts)}</p>'
            + (f'<p><a href="https://aviationweather.gov/data/metar/?ids={esc(metar_ids)}&amp;hours=0" '
               f'target="_blank" rel="noopener">Current METARs for these airports (aviationweather.gov) &rarr;</a></p>'
               if metar_ids else "")
            + '<div style="overflow-x:auto"><table class="nearcity"><thead><tr><th>Id</th><th>Name</th>'
            f'<th class="n">From {esc(city)}</th><th>Use</th><th class="n">Longest rwy</th><th>Fuel</th>'
            f'<th>Tower / CTAF</th></tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>'
            f'<p class="tag">Distances are great-circle nautical miles with direction from the centre of the '
            f'facilities that list {esc(city)} as their city (not a surveyed city centre). Heliports are not listed. '
            f'A snapshot of the 28-day NASR cycle: confirm frequencies and runway data against the current Chart '
            f'Supplement before flight.</p>'
            + (f'<h3>Airports near other cities nearby</h3><ul class="cols">{near_cities}</ul>' if near_cities else "")
            + f'<p><a href="/us-airports/{esc(st.lower())}/">All airports in {esc(stname)}</a> &middot; '
            f'<a href="/airports.html">Search airports</a></p>')
        d = base / c["slug"]
        d.mkdir(parents=True, exist_ok=True)
        path = f"airports-near/{c['slug']}/"
        title = f"Airports near {city}, {st} — runways, frequencies, weather"
        desc = (f"{len(land)} airports within {CITY_RADIUS_NM} nm of {city}, {stname} ({len(pub)} public use): "
                f"runway lengths, fuel, CTAF and tower frequencies, live weather and NOTAMs.")
        (d / "index.html").write_text(head(esc(title), desc, rel="/", path=path, ads=True) + body + foot,
                                      encoding="utf-8")
        paths.append(path)
        by_state.setdefault(st, []).append((c["slug"], city))
    for v in by_state.values():
        v.sort(key=lambda t: t[1])
    return paths, by_state
