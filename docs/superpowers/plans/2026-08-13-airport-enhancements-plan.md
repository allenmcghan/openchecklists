# Airport Pages Enhancements Plan

**Date:** 2026-08-13  
**Phase:** Post-launch enhancements  
**Status:** Planning

---

## Overview

Six optional enhancements to the production airport pages system:

1. **Live NOTAMs from FAA API** — Replace stubbed NOTAMs endpoint with real FAA data
2. **Airspace lookup from FAA shapefiles** — Replace generic airspace class with actual airspace data
3. **Fuel prices integration** — Connect to aviation fuel pricing data source
4. **Runway detail modals** — Make runways clickable; show detailed runway info in modal
5. **Search page integration** — Update airports.html search to link to new `/airport/IDENT` pages
6. **Flight planner PRD section** — Add new section to PRD documenting full flight-planner feature

---

## Task Breakdown

### Enhancement 1: Live NOTAMs from FAA API
**Goal:** Replace stubbed NOTAMs endpoint with real FAA NOTAM search data

**Current state:**
- `/api/airport/{IDENT}/notams` returns empty array `{notams: []}`
- Placeholder ready for implementation

**Implementation:**
- Integrate with FAA NOTAM API or aviationweather.gov NOTAM search
- Parse NOTAMs for specific airport
- Return with proper timestamp
- Cache for 1-2 hours

**Files to modify:**
- `worker/airport-api.js` — enhance `handleNotams()` function

**Test:**
- Verify endpoint returns real NOTAMs for active airports
- Test fallback when no NOTAMs present

---

### Enhancement 2: Airspace Lookup from FAA Shapefiles
**Goal:** Replace generic "Class E" with actual airspace classification from FAA data

**Current state:**
- `/api/airport/{IDENT}/airspace` returns `{airspace_class: "E", moas: []}`
- Placeholder implementation

**Implementation:**
- Ingest FAA airspace shapefiles (Class B/C/D/E, MOAs, restricted areas)
- Query by airport coordinates
- Return actual classification + surrounding MOAs
- Cache as static pre-computed data

**Files to modify:**
- `worker/airport-api.js` — enhance `handleAirspace()` function
- Airspace data ingestion script (new)

**Test:**
- Verify endpoints return correct airspace for known airports (KJFK→B, KORD→B, small airport→E)
- Test MOA detection near military ranges

---

### Enhancement 3: Fuel Prices Integration
**Goal:** Add live or near-live fuel prices to fuel endpoint

**Current state:**
- `/api/airport/{IDENT}/fuel` returns `{fuel_types: [...], prices: null}`
- Placeholder implementation

**Implementation:**
- Research fuel price data sources (FAA, aviation fuel sites, Jet-A APIs)
- If no real-time source available: display NASR fuel types + "Contact FBO for current prices"
- If source available: integrate and cache for 1 day
- Handle missing data gracefully

**Files to modify:**
- `worker/airport-api.js` — enhance `handleFuel()` function

**Test:**
- Verify endpoint returns fuel types for all airports
- Verify prices (or null) with age disclaimer

---

### Enhancement 4: Runway Detail Modals
**Goal:** Make runways clickable; show detailed modal on click

**Current state:**
- Runway diagram is static SVG
- No interactivity

**Implementation:**
- Add click handlers to runway SVG elements (already have `data-id` attributes)
- Create modal/popup with runway details:
  - Both ends (e.g., 09/27)
  - True and magnetic headings
  - Length, width, surface
  - Lighting, condition
  - ILS info (if equipped)
  - Displaced threshold info
  - Traffic pattern (left/right)
- Style modal with close button

**Files to modify:**
- `tools/build_site.py` — update airport page script to add modal HTML + CSS + JS
- Add modal styles to page CSS

**Test:**
- Click a runway in diagram
- Modal appears with full runway details
- Close button works
- Works for large airports (KJFK with 4 runways)

---

### Enhancement 5: Search Page Links
**Goal:** Update airports.html search results to link to new airport pages

**Current state:**
- Search page exists at `airports.html`
- Likely has inline detail panel (old architecture)

**Implementation:**
- Update search page results to link to `/airport/{IDENT}` instead of inline panel
- Test that links work for all airports
- Remove old inline detail panel code if present

**Files to modify:**
- `tools/site_airports.py` — update airport row rendering
- Rebuild site

**Test:**
- Search for an airport (e.g., "Kennedy")
- Click result
- Navigates to `/airport/KJFK`
- Page loads correctly

---

### Enhancement 6: Flight Planner PRD Section
**Goal:** Document full flight-planner feature for future development

**Current state:**
- Airport pages complete and live
- Flight planner is future work

**Implementation:**
- Create new section in project PRD (or separate flight-planner PRD)
- Document scope: what a "full flight planner" includes
  - Route planning (departure → destination → alternate)
  - Weight & balance calculator
  - Fuel planning
  - Flight plan filing
  - Weather briefing aggregation
  - Airspace/obstacle checks along route
  - Pre-flight checklist integration
- Define MVP scope
- Identify dependencies (airport pages = foundation ✓)

**Files to modify/create:**
- `docs/superpowers/specs/flight-planner-prd.md` (new) or update existing PRD

**Test:**
- Verify PRD is clear and complete
- Share with team for feedback

---

## Execution Plan

**Phase 1: Worker Enhancements (Enhancements 1-3)**
- Implement live NOTAMs
- Implement airspace lookup
- Implement fuel prices
- Test all 3 endpoints
- Deploy worker

**Phase 2: Frontend Enhancements (Enhancements 4-5)**
- Add runway detail modals
- Update search page links
- Rebuild site
- Deploy Pages

**Phase 3: Documentation (Enhancement 6)**
- Write flight-planner PRD section

---

## Success Criteria

- ✅ NOTAMs endpoint returns real FAA data (not empty array)
- ✅ Airspace endpoint returns correct classification (not generic "E")
- ✅ Fuel endpoint shows prices or "Contact FBO" (not null)
- ✅ Runway diagrams are clickable; modal shows full details
- ✅ Search page links to `/airport/IDENT`
- ✅ Flight planner PRD documented and ready for next phase

---

## Timeline

- Enhancement 1-3: ~2-3 hours (worker implementation + testing)
- Enhancement 4-5: ~1-2 hours (frontend + rebuild)
- Enhancement 6: ~30 min (documentation)

**Total estimate:** 4-6 hours

---

## Dependencies

- **Enhancement 2:** Requires FAA airspace shapefile ingestion (research phase)
- **Enhancement 3:** Requires fuel price data source investigation (research phase)
- **Enhancement 4:** No dependencies; can run in parallel with 1-3
- **Enhancement 5:** Depends on Enhancement 4 (need updated site)
- **Enhancement 6:** No dependencies; can run in parallel

