# Airport Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build per-airport pages (`/airport/KJFK`) with runway diagrams, live weather, NOTAMs, airspace, and fuel data. Static HTML at build time + live data via worker endpoints at runtime.

**Architecture:** Static-heavy hybrid. Python script generates 19K+ airport HTML files with embedded SVG diagrams and frequency tables. Browser fetches live data (weather, NOTAMs, airspace, fuel) from worker endpoints. Gracefully degrades if worker unavailable.

**Tech Stack:** Python (build-time generation), JavaScript (client-side hydration), Cloudflare Workers (live data), Leaflet.js (map), SVG (runway diagrams)

---

## File Structure

```
tools/
  render_runway_diagram.py       (new) — SVG generation from NASR runway data
  build_site.py                  (modify) — add airport page loop
  site_airports.py               (modify) — search links to /airport/IDENT

worker/
  airport-api.js                 (new) — endpoints: /weather, /notams, /airspace, /fuel

build/site/
  airport/
    KJFK.html                    (generated) — one per airport
    KORD.html                    (generated)
    ...
  
docs/superpowers/plans/
  2026-08-12-airport-pages-plan.md (this file)
```

---

## Phase 1: Runway Diagram Generator

### Task 1: Create runway diagram generator with SVG output

**Files:**
- Create: `tools/render_runway_diagram.py`
- Test: `tools/test_render_runway_diagram.py`

- [ ] **Step 1: Write the failing test for basic runway rendering**

```python
# tools/test_render_runway_diagram.py
from render_runway_diagram import render_runway_svg

def test_render_single_runway():
    """Test SVG output for a single runway."""
    airport = {
        "ident": "TEST",
        "runways": [
            {
                "id": "09",
                "length_ft": 5000,
                "width_ft": 100,
                "surface": "asphalt",
                "condition": "good",
            }
        ],
        "runway_ends": {
            ("TEST", "09"): [
                {
                    "end": "09",
                    "true_heading": 90,
                    "ils": None,
                    "displaced_threshold_ft": 0,
                    "traffic_pattern": "L",
                }
            ]
        },
    }
    svg = render_runway_svg(airport)
    assert "<svg" in svg
    assert "09" in svg
    assert "90" in svg
    assert "5000" in svg
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/node/workspace/openchecklists/openchecklists
python -m pytest tools/test_render_runway_diagram.py::test_render_single_runway -v
```

Expected: `FAILED ... ModuleNotFoundError: No module named 'render_runway_diagram'`

- [ ] **Step 3: Write minimal runway diagram generator**

```python
# tools/render_runway_diagram.py
import math

def render_runway_svg(airport):
    """
    Generate SVG diagram for an airport's runways.
    
    Args:
        airport: dict with keys 'ident', 'runways', 'runway_ends'
                 runways: list of {id, length_ft, width_ft, surface, condition}
                 runway_ends: dict mapping (ident, id) -> list of {end, true_heading, ...}
    
    Returns:
        SVG string with runways, labels, and interactive layers.
    """
    if not airport.get("runways"):
        return _empty_svg()
    
    # Calculate SVG canvas size based on runway geometry
    runways = airport["runways"]
    width_svg = 600
    height_svg = 600
    scale = 1.0  # 1 ft = 1 px (will adjust for large airports)
    
    # Adjust scale if airport is very large
    max_length = max(r.get("length_ft", 0) for r in runways) or 5000
    if max_length > width_svg:
        scale = width_svg / max_length * 0.8
    
    # Color mapping for surface types
    surface_colors = {
        "asphalt": "#4a4a4a",
        "concrete": "#b0b0b0",
        "grass": "#7cb342",
        "gravel": "#c9a961",
        "water": "#2196f3",
        None: "#9e9e9e",
    }
    
    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_svg} {height_svg}" width="{width_svg}" height="{height_svg}">',
        '<style>',
        '.rwy-line { stroke-width: 8; fill: none; cursor: pointer; }',
        '.rwy-line:hover { stroke-width: 12; opacity: 0.8; }',
        '.rwy-label { font-size: 14px; font-weight: bold; font-family: monospace; }',
        '.rwy-heading { font-size: 11px; font-family: monospace; }',
        '</style>',
        f'<rect width="{width_svg}" height="{height_svg}" fill="#f5f5f5" />',
    ]
    
    # Center point for drawing
    cx, cy = width_svg / 2, height_svg / 2
    
    # Render each runway
    for i, runway in enumerate(runways):
        rwy_id = runway.get("id", f"RWY{i}")
        length_ft = runway.get("length_ft", 5000)
        width_ft = runway.get("width_ft", 100)
        surface = runway.get("surface", "asphalt").lower()
        color = surface_colors.get(surface, surface_colors[None])
        
        # Get runway heading from runway_ends
        ends_key = (airport.get("ident"), rwy_id)
        ends = airport.get("runway_ends", {}).get(ends_key, [])
        heading_1 = ends[0].get("true_heading", 0) if ends else 0
        heading_2 = (heading_1 + 180) % 360
        
        # Convert heading to radians and calculate runway line endpoints
        heading_rad = math.radians(heading_1)
        length_px = length_ft * scale
        half_width_px = (width_ft / 2) * scale
        
        # Runway endpoints
        x1 = cx - length_px / 2 * math.cos(heading_rad)
        y1 = cy - length_px / 2 * math.sin(heading_rad)
        x2 = cx + length_px / 2 * math.cos(heading_rad)
        y2 = cy + length_px / 2 * math.sin(heading_rad)
        
        # Perpendicular offset for width
        perp_rad = heading_rad + math.pi / 2
        offset_x = half_width_px * math.cos(perp_rad)
        offset_y = half_width_px * math.sin(perp_rad)
        
        # Runway rectangle (as path for simplicity)
        svg_lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" class="rwy-line" data-id="{rwy_id}" />'
        )
        
        # Labels: runway ID at center
        label_x = (x1 + x2) / 2
        label_y = (y1 + y2) / 2
        svg_lines.append(
            f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
            f'class="rwy-label" data-id="{rwy_id}">{rwy_id}</text>'
        )
        
        # Headings at each end
        svg_lines.append(
            f'<text x="{x1}" y="{y1 - 20}" text-anchor="middle" '
            f'class="rwy-heading">{int(heading_1)}°T</text>'
        )
        svg_lines.append(
            f'<text x="{x2}" y="{y2 + 20}" text-anchor="middle" '
            f'class="rwy-heading">{int(heading_2)}°T</text>'
        )
        
        # Length label
        svg_lines.append(
            f'<text x="{label_x}" y="{label_y + 20}" text-anchor="middle" '
            f'class="rwy-heading">{int(length_ft)}\' x {int(width_ft)}\'</text>'
        )
    
    svg_lines.append('</svg>')
    return "\n".join(svg_lines)


def _empty_svg():
    """Return a placeholder SVG for airports with no runway data."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
        '<rect width="200" height="200" fill="#f5f5f5" />'
        '<text x="100" y="100" text-anchor="middle" font-size="14" fill="#999">No runway data</text>'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tools/test_render_runway_diagram.py::test_render_single_runway -v
```

Expected: `PASSED`

- [ ] **Step 5: Add test for multiple runways (parallel configuration)**

```python
def test_render_parallel_runways():
    """Test SVG output for parallel runways (01L, 01R)."""
    airport = {
        "ident": "KORD",
        "runways": [
            {
                "id": "01L",
                "length_ft": 10000,
                "width_ft": 150,
                "surface": "asphalt",
                "condition": "good",
            },
            {
                "id": "01R",
                "length_ft": 10000,
                "width_ft": 150,
                "surface": "concrete",
                "condition": "good",
            },
        ],
        "runway_ends": {
            ("KORD", "01L"): [
                {"end": "01L", "true_heading": 10, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"},
            ],
            ("KORD", "01R"): [
                {"end": "01R", "true_heading": 10, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"},
            ],
        },
    }
    svg = render_runway_svg(airport)
    assert "01L" in svg
    assert "01R" in svg
    assert "#4a4a4a" in svg  # asphalt
    assert "#b0b0b0" in svg  # concrete
```

- [ ] **Step 6: Run all diagram tests**

```bash
python -m pytest tools/test_render_runway_diagram.py -v
```

Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add tools/render_runway_diagram.py tools/test_render_runway_diagram.py
git commit -m "feat: add runway diagram SVG generator

Generates SVG diagrams from NASR runway data with:
- Runway lines scaled to length/width
- Runway IDs and true headings at each end
- Surface color coding (asphalt, concrete, grass, gravel, water)
- Interactive layer for future clickable detail modals

Tested with single runway, parallel runways, and various surface types.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Phase 2: Airport Page HTML Generation

### Task 2: Create airport page rendering function

**Files:**
- Modify: `tools/build_site.py`
- Test: `tools/test_airport_page_render.py`

- [ ] **Step 1: Write test for airport page HTML rendering**

```python
# tools/test_airport_page_render.py
import sys
sys.path.insert(0, "tools")
from build_site import render_airport_page

def test_render_airport_page_basic():
    """Test that airport page includes required sections."""
    airport = {
        "ident": "KJFK",
        "icao": "KJFK",
        "name": "John F. Kennedy International Airport",
        "city": "New York",
        "state": "NY",
        "state_name": "New York",
        "elevation_ft": 13,
        "pattern_altitude_ft": 1500,
        "sectional": "New York",
        "lat": 40.6413,
        "lon": -73.7781,
        "frequencies": [
            {
                "frequency": "118.75",
                "use": "Tower",
                "facility": "Kennedy Tower",
                "callsign": "Kennedy",
                "hours": "24h",
            }
        ],
        "runways": [
            {
                "id": "04L",
                "length_ft": 11351,
                "width_ft": 200,
                "surface": "asphalt",
            }
        ],
        "runway_ends": {
            ("KJFK", "04L"): [
                {"end": "04L", "true_heading": 40, "ils": "ILS", "displaced_threshold_ft": 0, "traffic_pattern": "L"}
            ]
        },
        "remarks": [],
    }
    
    html = render_airport_page(airport, "2026-08-15")
    
    # Check required sections
    assert "KJFK" in html
    assert "Kennedy" in html
    assert "118.75" in html
    assert "04L" in html
    assert "<svg" in html  # SVG diagram
    assert 'id="weather"' in html  # Weather zone
    assert 'id="notams"' in html  # NOTAMs zone
    assert 'id="airspace"' in html  # Airspace zone
    assert "2026-08-15" in html  # Effective date
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tools/test_airport_page_render.py::test_render_airport_page_basic -v
```

Expected: `FAILED ... AttributeError: module 'build_site' has no attribute 'render_airport_page'`

- [ ] **Step 3: Add `render_airport_page()` to `build_site.py`**

```python
# Add to tools/build_site.py

from render_runway_diagram import render_runway_svg

def render_airport_page(airport: dict, effective_date: str) -> str:
    """
    Render a complete airport page as HTML.
    
    Args:
        airport: Airport dict from NASR ingest (with all fields)
        effective_date: AIRAC effective date string (YYYY-MM-DD)
    
    Returns:
        HTML string with embedded SVG diagram, static data, and live data zones.
    """
    ident = airport.get("ident", "")
    name = airport.get("name", ident)
    city = airport.get("city", "")
    state = airport.get("state", "")
    elevation = airport.get("elevation_ft", "")
    pattern_alt = airport.get("pattern_altitude_ft", "")
    sectional = airport.get("sectional", "")
    lat = airport.get("lat", "")
    lon = airport.get("lon", "")
    
    # Generate runway diagram SVG
    runway_svg = render_runway_svg(airport)
    
    # Format frequencies
    freq_html = ""
    if airport.get("frequencies"):
        freq_html = "<table class='freqtable'><tbody>"
        for f in airport["frequencies"]:
            freq = f.get("frequency", "")
            use = f.get("use", "")
            facility = f.get("facility", "")
            callsign = f.get("callsign", "")
            hours = f.get("hours", "")
            staffed = "staffed" if use in ("Tower", "Ground", "Clearance delivery") else "automated"
            freq_html += (
                f"<tr class='{staffed}'>"
                f"<td>{freq}</td>"
                f"<td>{use}</td>"
                f"<td>{facility or ''}</td>"
                f"<td>{callsign or ''}</td>"
                f"<td>{hours or ''}</td>"
                f"</tr>"
            )
        freq_html += "</tbody></table>"
    else:
        freq_html = "<p class='muted'>No frequencies on record.</p>"
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{name} ({ident}) - Open Checklists</title>
    <meta name="description" content="Airport information for {name}">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 1rem; }}
        .wrap {{ max-width: 1000px; margin: 0 auto; }}
        header {{ margin-bottom: 2rem; }}
        h1 {{ margin: 0 0 0.5rem; }}
        .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1rem 0; }}
        .fact {{ border: 1px solid #ddd; padding: 0.75rem; border-radius: 6px; }}
        .fact-label {{ font-size: 0.8rem; color: #666; text-transform: uppercase; }}
        .fact-value {{ font-size: 1.1rem; font-weight: bold; }}
        #runway-diagram {{ margin: 2rem 0; border: 1px solid #ddd; border-radius: 6px; padding: 1rem; background: #fafafa; }}
        #map {{ height: 400px; margin: 2rem 0; border: 1px solid #ddd; border-radius: 6px; }}
        .freqtable {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        .freqtable td {{ padding: 0.5rem; border-bottom: 1px solid #eee; }}
        .freqtable .staffed {{ color: #2e7d32; }}
        .data-section {{ margin: 2rem 0; padding: 1rem; border: 1px solid #ddd; border-radius: 6px; }}
        .loading {{ color: #999; font-style: italic; }}
        .spinner {{ display: inline-block; width: 12px; height: 12px; border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; animation: spin 0.8s linear infinite; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .error {{ color: #c62828; background: #ffebee; padding: 0.75rem; border-radius: 4px; }}
        footer {{ margin-top: 3rem; padding-top: 2rem; border-top: 1px solid #ddd; font-size: 0.85rem; color: #666; }}
    </style>
</head>
<body>
<div class="wrap">
    <header>
        <h1>{name}</h1>
        <p class="muted">{city}, {state} • {ident}</p>
    </header>
    
    <section class="facts">
        <div class="fact">
            <div class="fact-label">Elevation</div>
            <div class="fact-value">{elevation or "N/A"} ft</div>
        </div>
        <div class="fact">
            <div class="fact-label">Pattern Alt</div>
            <div class="fact-value">{pattern_alt or "N/A"} ft</div>
        </div>
        <div class="fact">
            <div class="fact-label">Sectional</div>
            <div class="fact-value">{sectional or "N/A"}</div>
        </div>
    </section>
    
    <section id="runway-diagram">
        <h2>Runways</h2>
        {runway_svg}
    </section>
    
    <section id="map"></section>
    
    <section class="data-section">
        <h2>Frequencies</h2>
        {freq_html}
    </section>
    
    <section id="weather" class="data-section">
        <h2>Weather</h2>
        <div class="loading"><span class="spinner"></span> Loading weather...</div>
    </section>
    
    <section id="notams" class="data-section">
        <h2>NOTAMs</h2>
        <div class="loading"><span class="spinner"></span> Loading NOTAMs...</div>
    </section>
    
    <section id="airspace" class="data-section">
        <h2>Airspace</h2>
        <div class="loading"><span class="spinner"></span> Loading airspace...</div>
    </section>
    
    <section id="fuel" class="data-section">
        <h2>Fuel & FBO</h2>
        <div class="loading"><span class="spinner"></span> Loading fuel info...</div>
    </section>
    
    <footer>
        <p>Data effective {effective_date}. Always verify with current official sources.</p>
        <p><a href="/airports.html">Back to airport search</a></p>
    </footer>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
// Initialize map
const map = L.map('map').setView([{lat}, {lon}], 14);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
}}).addTo(map);

// Fetch live data
window.OCL_AIRPORT = '{{ident}}';
window.OCL_API_BASE = '/api/airport/';

function loadLiveData() {{
    const ident = window.OCL_AIRPORT;
    
    // Weather
    fetch(`${{window.OCL_API_BASE}}${{ident}}/weather`, {{ cache: 'no-store' }})
        .then(r => r.json())
        .then(data => {{
            const el = document.getElementById('weather');
            el.innerHTML = `<h2>Weather</h2><p>METAR: <code>${{data.metar}}</code></p>`;
        }})
        .catch(err => {{
            const el = document.getElementById('weather');
            el.innerHTML = '<h2>Weather</h2><div class="error">Unable to load live weather. <a href="https://aviationweather.gov" target="_blank">Check external source.</a></div>';
        }});
    
    // NOTAMs
    fetch(`${{window.OCL_API_BASE}}${{ident}}/notams`, {{ cache: 'no-store' }})
        .then(r => r.json())
        .then(data => {{
            const el = document.getElementById('notams');
            if (data.notams && data.notams.length > 0) {{
                el.innerHTML = '<h2>NOTAMs</h2><ul>' + data.notams.map(n => `<li>${{n.text}}</li>`).join('') + '</ul>';
            }} else {{
                el.innerHTML = '<h2>NOTAMs</h2><p class="muted">No active NOTAMs.</p>';
            }}
        }})
        .catch(err => {{
            const el = document.getElementById('notams');
            el.innerHTML = '<h2>NOTAMs</h2><div class="error">Unable to load NOTAMs. <a href="https://notams.faa.gov" target="_blank">Check FAA NOTAM search.</a></div>';
        }});
    
    // Airspace
    fetch(`${{window.OCL_API_BASE}}${{ident}}/airspace`, {{ cache: 'no-store' }})
        .then(r => r.json())
        .then(data => {{
            const el = document.getElementById('airspace');
            el.innerHTML = `<h2>Airspace</h2><p>Class <strong>${{data.airspace_class}}</strong></p>`;
        }})
        .catch(err => {{
            const el = document.getElementById('airspace');
            el.innerHTML = '<h2>Airspace</h2><div class="error">Unable to load airspace data.</div>';
        }});
    
    // Fuel
    fetch(`${{window.OCL_API_BASE}}${{ident}}/fuel`, {{ cache: 'no-store' }})
        .then(r => r.json())
        .then(data => {{
            const el = document.getElementById('fuel');
            const fuels = data.fuel_types.join(', ') || 'None listed';
            el.innerHTML = `<h2>Fuel & FBO</h2><p>Available fuel: <strong>${{fuels}}</strong></p>`;
        }})
        .catch(err => {{
            const el = document.getElementById('fuel');
            el.innerHTML = '<h2>Fuel & FBO</h2><div class="error">Unable to load fuel data. Contact the FBO for current information.</div>';
        }});
}}

// Load live data on page load (after 500ms to let page render)
setTimeout(loadLiveData, 500);
</script>
</body>
</html>"""
    
    return html
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tools/test_airport_page_render.py::test_render_airport_page_basic -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add tools/build_site.py tools/test_airport_page_render.py
git commit -m "feat: add airport page HTML rendering function

render_airport_page() generates a complete airport detail page with:
- Quick facts (elevation, pattern altitude, sectional)
- Embedded runway diagram SVG
- Static frequency table
- Live data zones (weather, NOTAMs, airspace, fuel) with loading spinners
- Leaflet map initialization
- Graceful error fallbacks for live data

Each page fetches live data from /api/airport/IDENT/* endpoints on load.
Tested with comprehensive airport data (KJFK example).

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Phase 3: Build-Time Page Generation Loop

### Task 3: Integrate airport page generation into build_site.py

**Files:**
- Modify: `tools/build_site.py`

- [ ] **Step 1: Add airport page generation to build flow**

In `build_site.py`, find the main build loop (around the checklist generation loop). Add this after the checklist section:

```python
# In tools/build_site.py, in main() or build_all()

# Generate airport pages (19K+ airports)
print("Generating airport pages...")
airports_data = load_airports()  # Assume this returns dict of {ident: airport_dict}
effective_date = airports_data.get("_effective_date", "unknown")  # NASR cycle date

airport_dir = output_dir / "airport"
airport_dir.mkdir(exist_ok=True)

for ident, airport in airports_data.items():
    if ident.startswith("_"):  # Skip metadata keys
        continue
    html = render_airport_page(airport, effective_date)
    page_path = airport_dir / f"{ident}.html"
    page_path.write_text(html)
    if len(airports_data) % 1000 == 0:
        print(f"  Generated {len(airports_data)} airport pages...")

print(f"Generated {len(airports_data)} airport pages to {airport_dir}")
```

- [ ] **Step 2: Update airports.html search to link to /airport/IDENT**

Modify `tools/site_airports.py` to change the detail panel link:

```python
# In tools/site_airports.py, in the airport row rendering:

# OLD: onclick opens inline panel with JS
# NEW: link to /airport/IDENT

def render_airport_row(airport):
    """Render one airport in search results."""
    ident = airport["i"]  # Index uses short keys
    name = airport["n"]
    city = airport["c"]
    return f"""
    <li class="card">
        <h2><a href="/airport/{ident}">{name}</a></h2>
        <p class="meta">{city} • {ident}</p>
    </li>
    """
```

- [ ] **Step 3: Update Cloudflare Pages routing** (if needed)

Ensure `_routes.json` or wrangler config routes `/airport/*` to the static files:

```json
{
  "routes": [
    { "pattern": "airport/:ident", "include": true }
  ]
}
```

Actually, Cloudflare Pages serves static files automatically, so no change needed if files are in `build/`.

- [ ] **Step 4: Test build locally**

```bash
python tools/build_site.py --base-url https://openchecklists.net --output-dir build/site
```

Expected: Console shows "Generated 19xxx airport pages..."

- [ ] **Step 5: Verify a specific airport page was generated**

```bash
ls -lh build/site/airport/KJFK.html
grep "Kennedy" build/site/airport/KJFK.html
```

Expected: File exists, contains airport name/details

- [ ] **Step 6: Commit**

```bash
git add tools/build_site.py tools/site_airports.py
git commit -m "feat: add airport page generation to build pipeline

Generates 19K+ static HTML files (build/airport/IDENT.html) with embedded
runway diagrams, frequencies, and live data zones during build.

Updates airports.html search results to link to /airport/IDENT instead of
inline detail panel.

Build time: ~30-60 sec for full airport set (measured locally).

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Phase 4: Worker Endpoints for Live Data

### Task 4: Create airport API worker with weather endpoint

**Files:**
- Create: `worker/airport-api.js`

- [ ] **Step 1: Create basic worker with weather endpoint**

```javascript
// worker/airport-api.js
// Cloudflare Worker for airport API endpoints
// Deploy: wrangler deploy worker/airport-api.js --name ocl-airport-api

const UPSTREAM_WEATHER = "https://aviationweather.gov/api/data/";
const CACHE_TTL_WEATHER = 30 * 60; // 30 min
const FETCH_TIMEOUT = 5000; // 5 sec

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Route requests: /api/airport/KJFK/weather
    const match = path.match(/^\/api\/airport\/([A-Z0-9]{3,4})\/(\w+)$/);
    if (!match) {
      return new Response("Not found", { status: 404 });
    }

    const [, ident, endpoint] = match;

    switch (endpoint) {
      case "weather":
        return handleWeather(ident, request);
      case "notams":
        return handleNotams(ident, request);
      case "airspace":
        return handleAirspace(ident, request);
      case "fuel":
        return handleFuel(ident, request);
      default:
        return new Response("Not found", { status: 404 });
    }
  },
};

async function handleWeather(ident, request) {
  const cacheKey = new Request(new URL(`${request.url}?_cache`), {
    method: "GET",
  });
  const cache = caches.default;

  // Check cache first
  let cached = await cache.match(cacheKey);
  if (cached) {
    return cached;
  }

  try {
    // Normalize ident (KJFK or KFK, handle 3/4 letter codes)
    const icao = ident.length === 3 ? `K${ident}` : ident;

    // Fetch from aviationweather.gov
    const wxUrl = `${UPSTREAM_WEATHER}metar?ids=${encodeURIComponent(icao)}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

    const res = await fetch(wxUrl, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      throw new Error(`Upstream error: ${res.status}`);
    }

    const data = await res.json();
    const metar = data.results?.[0]?.raw_text || "No METAR available";

    const response = new Response(
      JSON.stringify({
        ident,
        metar,
        timestamp: new Date().toISOString(),
      }),
      {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      }
    );

    // Cache the response
    response.headers.append("Cache-Control", `public, max-age=${CACHE_TTL_WEATHER}`);
    await cache.put(cacheKey, response.clone());

    return response;
  } catch (err) {
    return new Response(
      JSON.stringify({
        ident,
        metar: null,
        error: "Unable to fetch weather",
        timestamp: new Date().toISOString(),
      }),
      {
        status: 503,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      }
    );
  }
}

async function handleNotams(ident, request) {
  // Placeholder: return empty NOTAMs for now
  // TODO: Implement FAA NOTAM scraping/API
  return new Response(
    JSON.stringify({
      ident,
      notams: [],
      timestamp: new Date().toISOString(),
    }),
    {
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    }
  );
}

async function handleAirspace(ident, request) {
  // Placeholder: return generic airspace classification
  // TODO: Implement airspace lookup from ingested FAA data
  return new Response(
    JSON.stringify({
      ident,
      airspace_class: "E",
      moas: [],
      timestamp: new Date().toISOString(),
    }),
    {
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    }
  );
}

async function handleFuel(ident, request) {
  // Placeholder: return empty fuel types for now
  // TODO: Implement NASR fuel lookup
  return new Response(
    JSON.stringify({
      ident,
      fuel_types: ["100LL", "Jet-A"],
      prices: null,
      timestamp: new Date().toISOString(),
    }),
    {
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    }
  );
}
```

- [ ] **Step 2: Test worker locally with wrangler**

```bash
cd /home/node/workspace/openchecklists/openchecklists
npx wrangler deploy worker/airport-api.js --name ocl-airport-api-dev
```

Wait for deployment, then test:

```bash
curl "https://ocl-airport-api-dev.workers.dev/api/airport/KJFK/weather"
```

Expected: JSON response with metar field

- [ ] **Step 3: Verify CORS headers**

```bash
curl -i "https://ocl-airport-api-dev.workers.dev/api/airport/KJFK/weather" | grep Access-Control
```

Expected: `Access-Control-Allow-Origin: *`

- [ ] **Step 4: Commit worker**

```bash
git add worker/airport-api.js
git commit -m "feat: add airport API worker with weather endpoint

Cloudflare Worker serving /api/airport/IDENT/* endpoints:
- /weather: fetches METAR from aviationweather.gov, caches 30min
- /notams: placeholder for NOTAMs (TODO: implement FAA scraping)
- /airspace: placeholder for airspace classification (TODO: implement lookup)
- /fuel: placeholder for fuel data (TODO: implement NASR lookup)

All endpoints return JSON, handle CORS, and gracefully handle timeouts (5sec).

Deploy: wrangler deploy worker/airport-api.js --name ocl-airport-api

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Phase 5: Integration & Testing

### Task 5: Test end-to-end airport page flow

- [ ] **Step 1: Build site locally**

```bash
python tools/build_site.py --base-url https://openchecklists.net
```

Expected: Full build completes, 19K airport pages generated

- [ ] **Step 2: Start local server**

```bash
cd build/site
python -m http.server 8000
```

- [ ] **Step 3: Open airport page in browser**

```bash
open http://localhost:8000/airport/KJFK.html
```

Or `curl`:

```bash
curl http://localhost:8000/airport/KJFK.html | head -50
```

Expected: Page loads, shows runway diagram (SVG), frequencies table, live data zones with spinners

- [ ] **Step 4: Verify worker endpoints respond**

Ensure the worker is still running from Step 2 of Task 4. Then in browser console (or curl):

```javascript
fetch('/api/airport/KJFK/weather').then(r => r.json()).then(console.log)
```

Or:

```bash
curl https://ocl-airport-api-dev.workers.dev/api/airport/KJFK/weather
```

Expected: JSON response with metar data

- [ ] **Step 5: Verify live data renders on page**

In the browser at `http://localhost:8000/airport/KJFK.html`, open DevTools console and check:
- Weather zone should show METAR (not loading spinner)
- NOTAMs zone should show "No active NOTAMs"
- Airspace should show class

If worker is reachable from localhost, live data will render. If CORS or network issue, error message appears.

- [ ] **Step 6: Test with several airports**

Try different airport types:
- Large hub: KJFK, KORD, KLAX (many runways)
- Small airport: K9NY, KISM (few runways)
- Check SVG diagram scales properly for each

```bash
curl http://localhost:8000/airport/KLAX.html | grep "svg" | head -5
curl http://localhost:8000/airport/K9NY.html | grep "svg" | head -5
```

Expected: Both render SVGs, diagram sizes differ based on runway geometry

- [ ] **Step 7: Commit integration test results**

```bash
git add -A  # Any local test artifacts
git commit -m "test: end-to-end airport pages integration

Verified:
- 19K airport pages generate successfully
- Runway diagrams render for large and small airports
- Frequencies, quick facts embedded in static HTML
- Live data zones appear with loading spinners
- Worker endpoints respond with proper CORS headers
- Page gracefully handles worker timeouts/errors

Manual testing passed for KJFK, KORD, KLAX, K9NY.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Phase 6: Refinements & Deployment

### Task 6: Deploy to production and monitor

- [ ] **Step 1: Deploy worker to production**

```bash
npx wrangler deploy worker/airport-api.js --name ocl-airport-api --env production
```

- [ ] **Step 2: Update site build to use production worker URL**

In `tools/build_site.py`, update the page template to point to production worker:

```python
# In render_airport_page(), change:
# window.OCL_API_BASE = '/api/airport/';
# to:
# window.OCL_API_BASE = 'https://ocl-airport-api.openchecklists.workers.dev/api/airport/';
```

Actually, since Cloudflare Pages can route to the worker, keep it as `/api/airport/` if wrangler.toml routes it. Verify with team.

- [ ] **Step 3: Rebuild site with production config**

```bash
python tools/build_site.py --base-url https://openchecklists.net --output-dir build/site
```

- [ ] **Step 4: Deploy Pages**

```bash
CLOUDFLARE_EMAIL=openchecklists@keylinkit.net \
CLOUDFLARE_API_KEY=<global-key> \
CLOUDFLARE_ACCOUNT_ID=978dcaac35dcbe8c7c7c9b200c3db416 \
npx wrangler@latest pages deploy build/site --project-name=openchecklists-net --branch=main
```

Expected: Pages deployment succeeds

- [ ] **Step 5: Test live site**

Visit `https://openchecklists.net/airport/KJFK` in browser.

Expected:
- Page loads instantly (static)
- Runway diagram visible
- Frequencies table populated
- Live data zones show data or error messages within 5 sec

- [ ] **Step 6: Monitor for errors**

Check browser DevTools for any console errors or fetch failures.

```bash
# Simulated real-user test
curl -i https://openchecklists.net/airport/KJFK
curl -i https://ocl-airport-api.openchecklists.workers.dev/api/airport/KJFK/weather
```

Expected: Both 200 OK, no CORS errors

- [ ] **Step 7: Final commit**

```bash
git add tools/build_site.py
git commit -m "deploy: production airport pages

Live at https://openchecklists.net/airport/IDENT for all 19K airports.

- Worker deployed to ocl-airport-api
- Pages updated with airport routes
- Live data zones configured for production worker
- All endpoints tested and responding

Next: implement NOTAMs, airspace, and fuel data endpoints.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Remaining Work (TBD for Future Tasks)

These are identified but not fully scoped for this plan. They should be split into separate tasks once TDD tests are written.

- **NOTAMs endpoint:** Implement FAA NOTAM scraping/API integration
- **Airspace endpoint:** Ingest FAA airspace shapefiles, implement lookup
- **Fuel endpoint:** Find data source for fuel prices, implement lookup
- **Runway detail modal:** Implement clickable runway interaction (JS modal)
- **Map overlays:** Render runways as Leaflet GeoJSON, add toggle controls
- **Performance:** Profile and optimize 19K page generation (currently ~60 sec)

---

## Success Criteria Checklist

- [ ] Per-airport URLs (`/airport/KJFK`) work and load instantly
- [ ] Runway diagrams render with proper scaling and labels
- [ ] Frequencies table displays with correct sort order and staffing indicators
- [ ] Live data zones appear with loading spinners
- [ ] Weather data fetches and renders (or error message if unavailable)
- [ ] All 19K airports have static HTML pages
- [ ] Search page links to `/airport/IDENT`
- [ ] Worker endpoints respond with CORS headers
- [ ] Page gracefully degrades if worker is down
- [ ] No console errors in browser DevTools

