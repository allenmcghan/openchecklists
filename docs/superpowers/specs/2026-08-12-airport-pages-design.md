# Airport Pages Design Spec

**Date:** 2026-08-12  
**Status:** Ready for implementation  
**Vision:** Comprehensive per-airport pages as foundational building blocks for a full flight-planner tool.

---

## Overview

Replace the current single-page airport search (`airports.html`) with **dedicated per-airport pages** (`/airport/KJFK`, `/airport/KORD`, etc.) that serve as a complete flight-planning reference for each airport. Every pilot planning a VFR or IFR flight should find everything needed on their airport page: runways, frequencies, weather, NOTAMs, airspace, fuel, and navigation aids — all on screen, no external sites.

**Architecture:** Static-heavy hybrid. Static HTML + runways/frequencies baked in at build time; live data (weather, NOTAMs, airspace, fuel) fetched at runtime via worker endpoints.

---

## Goals

1. **Single source of truth for airport info** — pilots get comprehensive context without leaving openchecklists.net
2. **Foundation for flight planning** — airport pages are composable building blocks for future route planners, fuel calculators, and flight-plan generators
3. **Works offline for reference** — static content (runways, frequencies, sectional name) is instantly available; live data gracefully degrades if the worker is down
4. **Supports VFR and IFR workflows** — frequencies for all phases of flight, airspace classification, approach plates, weather briefing all present

---

## Current State vs. Desired

### Current (`airports.html`)
- Single page with client-side search over a lean index
- Inline detail panel (not a URL)
- Shows frequencies and runways (from NASR data)
- Sectional chart name shown as text
- Weather box (if weather proxy is deployed)
- **Missing:** Maps, runway diagrams, NOTAMs, airspace, fuel, approach plates

### Desired (this design)
- Per-airport URLs (`/airport/KJFK`, `/airport/KORD`)
- Dedicated static HTML page per airport
- Comprehensive visual layout: runway diagram (SVG, interactive), map (Leaflet), frequencies, live weather, NOTAMs, airspace, fuel, sectional/approach links
- All data on screen
- **New data sources:** NOTAMs (scraped from FAA), airspace classification, fuel types/prices, live weather

---

## Architecture

### Static-Heavy Hybrid

**Build time (`tools/build_site.py`):**
1. Ingest NASR airport data (already done by `tools/airports.py`)
2. For each airport:
   - Generate runway diagram SVG (from runway geometry + ends data)
   - Generate static HTML page (`build/airport/IDENT.html`)
   - Embed reference data: frequencies, runways, airport metadata, sectional name, elevation, pattern altitude
   - Include worker endpoint URLs in page script for live data

**Runtime (browser):**
1. Page loads instantly (static HTML)
2. JavaScript detects live data zones and fetches from worker:
   - `GET /api/airport/KJFK/weather` → METAR/TAF
   - `GET /api/airport/KJFK/notams` → Active NOTAMs
   - `GET /api/airport/KJFK/airspace` → Airspace classification + MOAs
   - `GET /api/airport/KJFK/fuel` → Fuel types and prices
3. Renders live data into designated page zones
4. Shows loading spinners while fetching; gracefully handles timeouts
5. If worker unavailable: page still functional with reference data; live zones show "unable to load"

**Why this approach:**
- ✅ Instant load (static HTML cached by CDN/Pages)
- ✅ Graceful degradation if worker unavailable
- ✅ Works offline for reference data
- ✅ Composable for future flight-planner routes (worker endpoints can aggregate data across multiple airports)
- ✅ SEO-friendly (static URLs, no JS-only content)

---

## Page Structure

Each airport page includes these sections in order:

### 1. Header & Quick Facts
- Airport name, ICAO ID, city, state
- Elevation, pattern altitude
- Sectional chart name
- Status (e.g., "Seasonal, closed Oct–Mar")
- Ownership type (Public, Private)

### 2. Runway Diagram (Primary Focus)
Large SVG visual showing all runways with:
- Runway IDs (01L/01R, 09, etc) with true and magnetic headings
- Length × width in feet
- Surface type with color coding:
  - Asphalt = dark gray
  - Concrete = light gray
  - Grass = light green
  - Gravel = tan
  - Water = blue
- ILS indicators for each runway end (if equipped)
- Displaced threshold notches (if any)

**Interactive layer:**
- Hover runway → highlight
- Click runway → modal showing:
  - Both ends' true/magnetic headings
  - Length, width, surface, condition, lighting
  - ILS type (if any)
  - Traffic pattern (left/right for each end)
  - Displaced threshold info

### 3. Interactive Map (Below Diagram)
Leaflet map (OpenStreetMap) centered on airport showing:
- Runways as overlays (matching diagram)
- Fuel/facilities/FBO markers (if data available)
- Surrounding airspace zones (Class B/C/D/E, MOAs) as shaded layers
- Toggle layers: airspace on/off, fuel locations
- Zoom/pan controls

### 4. Frequencies
Table sorted by VFR pilot priority:
1. CTAF (Unicom if no CTAF)
2. Tower (if staffed)
3. Ground
4. Clearance delivery (if Class B)
5. Atis/AWOS/ASOS
6. Any other frequencies

Columns:
- **Frequency** (formatted: 118.25)
- **Use** (CTAF, Tower, Ground, Atis, AWOS, etc)
- **Facility name** (if available)
- **Callsign** (Tower callsign, Approach callsign, etc)
- **Hours** (24h, 9am–5pm, etc)

Color-coding:
- Green: staffed facility
- Gray: unattended/automated

### 5. Live Weather (METAR/TAF)
Loading state → fetches from `/api/airport/KJFK/weather`

Display:
- **METAR:** Plain-English summary + raw text
  - Wind, visibility, ceiling, temperature/dewpoint, altimeter, remarks
  - Flight category color badge (VFR=green, MVFR=blue, IFR=red, LIFR=purple)
- **TAF:** Plain-English summary + raw text (if available)
- **Last updated:** Timestamp + manual refresh button
- **Fallback:** "Unable to load live weather" with link to aviationweather.gov

### 6. NOTAMs
Loading state → fetches from `/api/airport/KJFK/notams`

Display as a list:
- Each NOTAM: effective/expiration dates, text
- Color-coded by severity (⚠ caution, 🔴 warning)
- "No active NOTAMs" if clear
- Fallback: "Unable to load NOTAMs" with link to FAA NOTAM search

### 7. Airspace
Loading state → fetches from `/api/airport/KJFK/airspace`

Display:
- Text summary: "Class D airspace; MOA [name] active 8am–5pm weekdays"
- Link to detailed airspace info
- Future: queryable for route planners

### 8. Fuel & FBO
Loading state → fetches from `/api/airport/KJFK/fuel`

Display:
- **Fuel types:** 100LL, Jet-A, etc. (from NASR, always available)
- **Current prices** (if data available, with timestamp and age disclaimer)
- **FBO contact:** Name, phone, hours
- Fallback: "Price data unavailable; contact FBO"

### 9. Navigation Aids & References
Static links:
- Sectional chart (link to FAA's digital chart or downloadable PDF)
- Approach plate (if public/available, link to FAA)
- FAA airport diagram
- Airport remarks (from NASR, e.g., "soft field operations not permitted")

---

## Data Flow & Sources

### Build-Time Data (Static, Embedded)
- **Runways, taxiways, runway ends:** NASR APT_RWY.csv, APT_RWY_END.csv
  - Generated: Runway diagram SVG, embedded in HTML
- **Frequencies:** NASR FRQ.csv
  - Generated: Sorted frequency table, embedded in HTML
- **Airport metadata:** NASR APT.csv
  - Elevation, pattern altitude, sectional, ownership, status, etc.
  - Embedded: Quick facts section
- **Effective date:** NASR cycle date
  - Embedded: Page footer ("Data effective YYYY-MM-DD")

### Runtime Data (Live, Fetched)
- **Weather (METAR/TAF):** aviationweather.gov API
  - Via worker endpoint: `/api/airport/KJFK/weather`
  - Cache: 30 min
  - Source: Extend existing weather-proxy worker
- **NOTAMs:** FAA NOTAM search (scraped or via API if available)
  - Via worker endpoint: `/api/airport/KJFK/notams`
  - Cache: 1–2 hours
  - Fallback: "Unable to load NOTAMs"
- **Airspace:** Ingested FAA airspace data (shapefiles)
  - Via worker endpoint: `/api/airport/KJFK/airspace`
  - No cache (pre-computed, static until next AIRAC)
  - Returns: airspace classes, MOAs, altitude limits
- **Fuel prices:** Best-effort data source (TBD)
  - Via worker endpoint: `/api/airport/KJFK/fuel`
  - Cache: 1 day
  - Fallback: "Prices unavailable; contact FBO"

---

## Worker Endpoints

All endpoints return JSON and handle CORS for browser requests.

### `/api/airport/KJFK/weather`
**Returns:** `{ metar: "...", taf: "...", timestamp: "ISO8601" }`

**Implementation:**
- Call aviationweather.gov API for airport ICAO/ident
- Parse response, extract METAR and TAF
- Cache for 30 min
- Handle timeouts gracefully

### `/api/airport/KJFK/notams`
**Returns:** `{ notams: [{effective, expiration, severity, text}], timestamp }`

**Implementation:**
- Query FAA NOTAM search API or scrape aviationweather.gov
- Extract NOTAMs for this airport
- Sort by effective date (newest first)
- Cache for 1–2 hours
- Fallback: empty array if unavailable

### `/api/airport/KJFK/airspace`
**Returns:** `{ airspace_class: "D", moas: [{name, altitude, schedule}], ... }`

**Implementation:**
- Query ingested FAA airspace data (built at deploy time from shapefiles)
- Return airspace classification and MOAs at this airport's coordinates
- No external calls (pre-computed)

### `/api/airport/KJFK/fuel`
**Returns:** `{ fuel_types: ["100LL", "Jet-A"], prices: {fuel: cost, timestamp}, ... }`

**Implementation:**
- Return fuel types from NASR (always available)
- Attempt to fetch prices from a data source (TBD; may not exist)
- If prices unavailable, return `{ fuel_types: [...], prices: null }`
- Cache for 1 day

---

## Runway Diagram Generation

### SVG at Build Time

**Input:** NASR runway data (APT_RWY.csv, APT_RWY_END.csv)

**Output:** SVG embedded in airport HTML

**Content:**
- Coordinate system: runway positions drawn to approximate scale (visual, not flight-critical)
- Each runway: 
  - Draw line from one end to the other
  - Label with runway ID (e.g., "09L")
  - Add true heading label
  - Add magnetic heading label
  - Label length/width
- Surface color based on surface type
- ILS indicators (small markers) if equipped
- Displaced threshold notches (small tick marks)
- Taxiway outlines (if available in NASR, for context)

**Scalability:** For airports with many runways (e.g., KJFK, KORD, KLAX), use a viewBox that auto-scales; diagram should fit on screen without scrolling.

**Interactivity:** SVG elements clickable → JS modal with runway detail (no additional rendering needed).

---

## Map Integration (Leaflet + OpenStreetMap)

### Map Layer
- Center: airport coordinates (lat/lon from NASR)
- Zoom: level 14–15 (shows runways + immediate surroundings)
- Base layer: OpenStreetMap (free, no API key)

### Overlays
1. **Runways** — GeoJSON or SVG overlay, matching diagram
2. **Airspace zones** — polygon overlay (Class B/C/D/E, MOAs) from ingested FAA data
3. **Fuel/facilities markers** — if FBO data available
4. **Toggle controls** — check/uncheck airspace, fuel markers

### Future Extensibility
- Route lines (for flight planner)
- Weather station locations
- Obstacles, terrain

---

## Search & Discovery

### URL Scheme
- `/airport/KJFK` — airport detail by ident
- `/airport/K?` — wildcard search (TBD: client-side routing or server-side redirect?)

### Index Page
Keep the existing `airports.html` search interface:
- Client-side search over lean index (19K+ airports)
- Clicking a result navigates to `/airport/IDENT` (instead of inline detail panel)

### Reverse Lookup
- Browser search (Ctrl+F) for airport within the page
- Index remains for finding unknown airports by city/region

---

## Error Handling & Degradation

### If Worker is Down
- Static content (runways, frequencies, facts) still available
- Live data zones show: "Unable to load [weather/NOTAMs/airspace/fuel]"
- User can still access external links (aviationweather.gov, FAA NOTAM search)
- **Not ideal, but survivable:** pilot has reference data and can navigate to official sources

### If Airport Data is Missing
- NOTAM data for small/private airports may be sparse; show "No active NOTAMs"
- Fuel prices rarely available; show "Contact FBO for current prices"
- Airspace data is complete; always available
- Weather (METAR) not available for non-reporting airports; show "No weather station at this airport"

### Timeout Handling
- Live data fetch timeout: 5 sec per endpoint
- Show spinner for 5 sec, then fallback to error message
- Manual refresh button for user to retry

---

## Technical Implementation

### Build-Time Script Changes (`tools/build_site.py`)
1. New function: `render_airport_page(airport_dict) -> str` 
   - Takes NASR airport data
   - Returns HTML string with embedded diagram SVG, facts, frequencies
2. Loop through all 19K+ airports
   - Call `render_airport_page()`
   - Write to `build/airport/IDENT.html`
3. Update index for search

### New Runway Diagram Generator (`tools/render_runway_diagram.py` or inline)
- Takes `airport["runways"]` and `airport["runway_ends"]`
- Generates SVG string
- Returns embedded in HTML

### Worker Changes
- Extend existing weather-proxy worker OR create new `/api/airport/` worker
- Add endpoints for `/metar`, `/notams`, `/airspace`, `/fuel`
- Deploy as separate worker or route within existing one

### Page Script (Client-Side)
- Detect live data zones (weather, NOTAMs, etc.)
- Fetch from `/api/airport/KJFK/[endpoint]` on page load
- Render responses into the page
- Show spinners + error messages

### Routes (Cloudflare Pages)
- Static files: `build/airport/*.html` served as-is
- API calls: route to worker

---

## Integration with Flight Planner (Future)

These design choices support the upcoming full-flight-planner feature:

1. **Composable worker endpoints:** Flight planner can fetch weather/airspace/NOTAMs for multiple airports in a route
2. **Structured airspace data:** Route planner can query "what airspace do I cross?" without parsing text
3. **Frequencies are sortable:** Flight briefing can aggregate all frequencies for a route
4. **Static architecture:** New airport-related features (weight & balance references, obstacle analysis, etc.) can be added without breaking the page
5. **PDF export:** Complete flight plan (which includes airport briefings) can be generated from the same data sources

---

## Success Criteria

- ✅ Per-airport URLs work and load instantly (static page)
- ✅ Runway diagram renders clearly; interactive runway detail works
- ✅ Map displays airport location + airspace zones
- ✅ Live weather loads within 5 sec (or shows error)
- ✅ NOTAMs, airspace, fuel data fetch and render
- ✅ All data on-screen; no external site links required (except for regulatory/external services)
- ✅ Page gracefully degrades if worker unavailable
- ✅ Works offline for reference data (runways, frequencies, facts)
- ✅ Search finds airports and links to `/airport/IDENT`

---

## Open Questions (TBD During Implementation)

1. **Fuel prices data source:** Do we have a live source, or fallback to NASR (stale)?
2. **NOTAMs scraping:** Can we use FAA's NOTAM API, or do we scrape aviationweather.gov?
3. **Airspace shapes:** How detailed should MOA/restricted airspace be? Vector tiles or GeoJSON?
4. **Runway diagram zoom:** For very large airports (KJFK, KORD), how many runways fit in the viewport?
5. **Map tile provider:** OpenStreetMap is free; consider custom raster if we want satellite imagery.
6. **URL case sensitivity:** Should `/airport/kjfk` and `/airport/KJFK` both work?

---

## Files to Create/Modify

- `tools/render_runway_diagram.py` (new) — SVG generation
- `tools/build_site.py` (modify) — add airport page loop + index
- `tools/site_airports.py` (modify) — if keeping index search for `/airports.html`
- `worker/airport-api.js` (new) — endpoints for weather, NOTAMs, airspace, fuel
- `build/airport/*.html` (generated) — one per airport
- `docs/superpowers/specs/2026-08-12-airport-pages-design.md` (this file)

