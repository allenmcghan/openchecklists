# Flight Planner PRD

**Date:** 2026-08-13  
**Status:** Roadmap (post-MVP)  
**Vision:** Full-featured flight planning tool enabling pilots to plan, file, and execute VFR/IFR flights entirely within openchecklists.net without leaving the site.

---

## 1. Overview

The Flight Planner is a comprehensive planning and filing assistant for General Aviation pilots. It guides pilots through the standard pre-flight planning workflow: route planning → flight plan filing → weight & balance → fuel planning → weather briefing → airspace/obstacle checks → pre-flight checklists → PDF export for cockpit reference. The feature builds directly on the Airport Pages foundation, reusing all airport data sources (runways, frequencies, weather, NOTAMs, airspace) and composing them into a complete flight-planning workflow that removes the need for external sites like ForeFlight or skyvector.

**Core value:** Pilots can go from "I want to fly to KJFK" to "flight plan filed, PDF in hand" without leaving openchecklists.net, using data they already trust from the airport pages.

---

## 2. Features (MVP Scope)

### 2.1 Route Planning
- **Departure → Destination:** Enter departure and destination airports (autocomplete from airport index); map displays straight-line route
- **Alternate Airports:** Select one or more alternates (minimum for IFR) with auto-suggestion based on proximity and landing surface
- **Waypoints & VORs:** Optional: add enroute checkpoints (VORs, intersections, landmarks) to refine route for navigation planning
- **Route Visualization:** Leaflet map showing airports and route line; toggle airspace/obstacles/weather along route

### 2.2 Flight Plan Filing Integration
- **Pre-populated form:** Route, departure, destination, aircraft type/tail number, cruising altitude, true airspeed auto-filled from aircraft profile and route calc
- **Generate flight plan text:** Produces FAA 7233-1 format (or modern IFR flight plan syntax) ready to copy into ForeFlight or phone-file to ATC
- **Integration hook (future):** API call to direct-file via FAA or EFB integration (currently: copy/paste workflow)
- **All airport data:** Frequencies for all airports on route, NOTAMs, airspace restrictions automatically included in briefing

### 2.3 Weight & Balance Calculator
- **Aircraft data:** Reuse aircraft profile (empty weight, CG envelope, fuel capacity)
- **Payload input:** Pilot + passengers (weights and seat positions), fuel quantity
- **Output:** Computed CG, confirmation that CG is within envelope, graphical plot
- **Reuse:** Save calculated W&B as "flight profile" linked to this flight plan for later recall

### 2.4 Fuel Planning
- **Route distance & time:** Auto-calculated from route segments
- **Burn rates:** From aircraft profile (power setting, altitude dependent)
- **Reserve calculation:** Standard reserves (30 min VFR day, 45 min VFR night, IFR reserves per altimeter setting)
- **Fuel load required:** GPH × flight time + reserves; highlights if required fuel exceeds tank capacity
- **Alternates:** Fuel to destination + alternate + reserves (IFR requirement)
- **Range/endurance graph:** Visual showing fuel vs. distance along route

### 2.5 Weather Briefing Aggregation
- **Multi-airport weather:** Fetch METAR/TAF for departure, destination, alternates, and all route waypoints
- **Flight category summary:** "VFR throughout" or "MVFR destination, check TAF" color-coded at a glance
- **Formatted briefing:** Plain-English summary: winds aloft, turbulence, visibility, icing layers, thunderstorms on route
- **Instrument data:** SIGMETs, AIRMETs, GTG (guidance to airmen) if airspace supports IFR
- **Briefing export:** Include in PDF or link to full aviationweather.gov briefing

### 2.6 Airspace & Obstacle Checks
- **Route query:** "What airspace do I cross?" — uses airport pages' airspace endpoint to aggregate Class B/C/D/E, MOAs, restricted areas along route
- **Altitude conflicts:** Check if planned cruise altitude passes through airspace; flag altitude restrictions
- **Obstacle check:** Future: query terrain/obstacle database to warn of peaks along route
- **Airspace rules summary:** Display minimum altitudes, frequency requirements (transponder, radio), special procedures (SID/STAR if filing IFR)

### 2.7 Pre-flight Checklist Integration
- **Link to airport checklists:** Automated links to departure & destination airport checklists (from airport pages)
- **Aircraft checklists:** Reuse linked aircraft checklists (normal ops, emergency procedures)
- **Route-specific notes:** Pre-populate checklist with route-specific items (e.g., "confirm VFR entry to Class C airspace", "brief alternates")
- **Interactive checklist:** Check off items during pre-flight; export as part of flight plan PDF

### 2.8 Export to PDF
- **Complete flight plan PDF:** One document containing:
  - Filed flight plan (or template for phone filing)
  - Route map with waypoints and airspace zones
  - Weather briefing (METARs, TAF, SIGMETs, winds aloft)
  - W&B calculation and CG plot
  - Fuel planning table and endurance graph
  - Departure/destination airport briefings (from airport pages)
  - Pre-flight checklist (with checkbox images for printing)
  - NOTAMs, airspace restrictions, obstacle warnings
- **Cockpit-friendly:** Formatted for A4/letter print, readable in small cockpit notebook format
- **In-flight reference:** Pilot can reference entire flight plan from one PDF; no need to juggle tabs

---

## 3. Technical Details

### 3.1 Builds on Airport Pages
- **Reuses worker endpoints:** All airport data (`/api/airport/KJFK/[weather|notams|airspace|fuel]`) already available
- **Multi-airport aggregation:** Flight planner fetches data for all airports on route in parallel; worker can optimize with cache keys
- **Static airport data:** Runway/frequency data already baked into airport pages; flight planner can reuse via static API or pre-built data

### 3.2 Route Planning Engine
- **Map-based input:** Leaflet map with departure/destination pickers (autocomplete from airport index)
- **Straight-line route:** Draw route as geodesic line on map; calculate distance/time using great-circle math
- **Waypoint support:** Click map to add enroute waypoints; reorder via drag
- **Terrain query (future):** For complex routes, optional query to elevation database to warn of terrain conflicts

### 3.3 Integration with Aviation APIs
- **Weight & balance:** Open-source library or built-in calculator (no external dependency; CG math is simple geometry)
- **Weather aggregation:** Reuse existing aviationweather.gov worker integration; flight planner fetches weather for 4–10 airports (METAR/TAF)
- **Fuel burn tables:** Ingest POH (Pilot Operating Handbook) data per aircraft type; store in aircraft profile (currently stored in openchecklists.net DB)
- **Airspace query:** Reuse ingested FAA airspace data from airport pages; no new external API needed

### 3.4 PDF Generation
- **Library:** Use `pdfkit` (Node.js) or `html2pdf.js` (browser-side) to render HTML flight plan to PDF
- **Server-side (worker):** POST flight plan JSON to worker endpoint `/api/flight-plan/pdf`; worker generates PDF and streams to browser
- **Browser-side (lighter):** Render flight plan HTML; user clicks "Export PDF" → `html2pdf.js` generates file locally (no server round-trip)

---

## 4. Dependencies

### Current Status
- **Airport pages:** ✅ Complete (2026-08-12 design spec finalized)
- **Worker API:** ✅ Complete (weather, NOTAMs, airspace, fuel endpoints implemented)
- **Aircraft profile store:** ✅ Complete (W&B, burn rates, fuel capacity stored per aircraft)

### To Build
- **Route planning UI:** TBD — Leaflet map + departure/destination pickers; draw route line; calculate distance/time
- **Flight plan filing integration:** TBD — integrate with FAA direct-file API or EFB (currently: manual copy-paste template)
- **Weight & balance calculator:** TBD — build or embed library; link to aircraft profile CG envelope data
- **Fuel planning worksheet:** TBD — table/calculator integrating route distance, aircraft burn rates, reserves
- **Weather briefing formatter:** TBD — aggregate METAR/TAF/SIGMET/AIRMET from worker; render as plain-English summary
- **Airspace route checker:** TBD — extend airport pages' airspace endpoint to query "what airspace do I cross on this route?"
- **PDF export pipeline:** TBD — build HTML template + PDF generator (server or client)
- **Pre-flight checklist builder:** TBD — link to airport checklists; allow custom routing checklist items

---

## 5. Success Metrics

### Pilot Workflow Completion
- **Metric:** Pilot can file a complete flight plan from openchecklists.net without opening external tools
- **Target:** 80% of test pilots report they can complete a typical VFR/IFR flight plan start-to-finish in under 10 minutes
- **Measurement:** Usability testing; time-on-task for standard routes (e.g., KJFK → KORD)

### Data Completeness
- **Metric:** Flight plan includes all relevant airport/weather/airspace data
- **Target:** PDF export includes METAR, TAF, NOTAMs, airspace summary, runway/frequency info, W&B, fuel plan for 100% of filed routes
- **Measurement:** PDF audit; verify no external links needed to complete briefing

### PDF Quality
- **Metric:** PDF is printable and usable in cockpit
- **Target:** Pilot can print one 3–5 page PDF and reference it in-flight without additional materials
- **Measurement:** Cockpit feedback; test pilots print PDF and navigate using it as primary briefing

### Data Pre-filling
- **Metric:** Flight plan form pre-filled with airport/aircraft data
- **Target:** 80% of flight plan fields auto-filled (aircraft type, cruise altitude, departure/destination frequencies)
- **Measurement:** Form audit; count fields requiring manual entry

---

## Integration with Existing Systems

### Airport Pages → Flight Planner Handoff
- Airport pages are the "detail source" for any airport on a flight plan route
- Flight planner aggregates airport data via worker API
- Future feature: "File flight plan to these airports" button on airport page → pre-populate flight planner with this airport

### Aircraft Profiles → Flight Planner
- Aircraft profile includes W&B envelope, fuel capacity, cruise performance (burn rates, true airspeed)
- Flight planner pulls this data to auto-calculate required fuel, CG, cruise performance
- Link: "Plan a flight in this aircraft" from aircraft profile page

### Worker API → Flight Planner
- Flight planner is the primary consumer of the new worker endpoints (weather, NOTAMs, airspace, fuel)
- This justifies the server cost and ensures the worker API is battle-tested before other tools use it

---

## Open Questions (TBD During Implementation)

1. **Flight plan filing:** Direct-file to FAA (requires API keys + legal terms), or always manual copy-paste?
2. **Airspace detail:** How granular should route airspace checks be? (Class B rings, MOA polygons, special-use airspace)
3. **PDF styling:** Single-column cockpit format, or printable 8.5×11 briefing-style?
4. **Crew briefing:** Should flight planner support multiple crew roles (PIC, SIC, navigator) with role-specific checklists?
5. **Performance data:** Source for aircraft burn rates — POH scraping, user-input calibration, or generic models?
6. **Alternates:** Should flight planner suggest alternates automatically, or require manual selection?

---

## File Structure (Future)

```
docs/superpowers/specs/
  flight-planner-prd.md (this file)

ui/
  flight-planner.html (new)
  flight-planner.js (new)
  components/
    flight-plan-form.js (route, aircraft, crew)
    weight-balance-calc.js (W&B table + CG plot)
    fuel-planning.js (fuel table, endurance graph)
    weather-briefing.js (aggregated METAR/TAF/SIGMET/AIRMET)
    airspace-checker.js (display airspace along route)
    checklist-builder.js (interactive pre-flight checklist)
    flight-plan-pdf.js (PDF export)

worker/
  flight-planner-api.js (new)
    /api/flight-plan/validate — validate route, check conflicts
    /api/flight-plan/pdf — generate PDF from flight plan JSON
    /api/flight-plan/weather — multi-airport weather aggregation
    (reuse existing /api/airport/* endpoints)

spec/
  flight-planner-schema.md (JSON schema for flight plan object)
```

---

## Version History

| Date | Status | Notes |
|------|--------|-------|
| 2026-08-13 | Roadmap | Initial PRD; depends on completed airport pages + worker API |

