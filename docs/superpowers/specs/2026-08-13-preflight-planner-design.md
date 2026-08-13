# PreFlight Plan Generator — Design Spec

**Date:** 2026-08-13
**Status:** Approved for implementation
**Mockups:** `/brainstorm/q1-scope.html` through `q5-briefing.html` (live at openchecklists.net)

---

## Overview

A complete VFR flight planning workflow embedded in openchecklists.net. Pilots enter aircraft, route, and fuel details; the system aggregates live weather, NOTAMs, airspace, and fuel data from existing worker endpoints; generates a downloadable PDF briefing; and emails it on request. The PDF works offline in the cockpit. A live-refresh URL in the footer lets the pilot pull current data when they have signal.

---

## Scope — VFR Only (v1)

- Visual flight rules planning only
- Departure → destination → optional alternate
- No SID/STAR routing, no IFR alternates, no FAA DUATS filing
- IFR support is a follow-on phase (documented in flight-planner-prd.md)

---

## Entry Points

### 1. Top navigation — "Plan a Flight"
- Added to the main site nav pill strip alongside Airports, Library, Training
- Visible to all visitors including unauthenticated guests
- Routes to `/planner`

### 2. Airport page shortcut
- Each `/airport/IDENT` page includes a "Plan a flight from [IDENT] →" button
- Clicking opens `/planner` with the departure field pre-filled
- Button appears in the airport quick-facts section, below frequencies

---

## Guest / Unauthenticated Access

Guests can use the full planner without signing in:

- All wizard/form fields available
- Briefing generates and displays normally
- "Download PDF" works immediately (client-side, no auth)
- "Email to Me" prompts for email address
  - Worker creates a Zitadel passwordless account for that email (same flow as the rest of the site)
  - OTP-by-email factor registered automatically
  - Welcome email includes magic-link sign-in + the briefing PDF as attachment
  - Subsequent visits: pilot is signed in and sees their plan history
- "Print" works immediately (browser print dialog)

---

## Planner UX — `/planner`

### Mode tabs
Two tabs at the top of the planner page:
1. **Guided Planning** (default) — 5-step wizard
2. **Quick Plan** — single-page form for returning pilots with saved aircraft

Both modes produce identical briefings.

### Guided Planning wizard (5 steps)

**Step 1 — Aircraft**
- Grid of saved aircraft cards (N-number, make/model, specs)
- "Add aircraft" card opens inline form
- Aircraft fields: N-number (required), make, model, fuel capacity (gal), burn rate (GPH), cruise speed (KTAS), notes
- Selecting an aircraft collapses step 1 into a summary strip; advances to step 2

**Step 2 — Route**
- Departure airport (text input, 4-char ICAO/FAA)
- Destination airport
- Alternate airport (optional; hint: "recommended when ceiling < 2,000 ft / vis < 3 SM")
- Saved favorite airports appear as clickable chips under each field
- Departure date/time (datetime-local, defaults to now, min = now, no past dates)
- Airports validated against the NASR index on input (fuzzy match)

**Step 3 — Weather preview**
- Calls `/api/airport/{IDENT}/weather` for departure and destination
- Shows METAR + TAF inline with VFR/MVFR/IFR badge
- Pilot reviews before continuing
- If IFR conditions exist, show advisory: "IFR conditions at [IDENT] — consider alternate"

**Step 4 — Fuel**
- Fuel onboard (gal, max = aircraft capacity, default = full tanks)
- Reserve: 30 min VFR / 45 min night-IFR / 1 hr conservative (select)
- Auto-calculates: fuel to destination, reserve required, margin, endurance
- Shows warning if margin < 1 hr

**Step 5 — Review & Generate**
- Summary of all inputs
- "Generate Briefing" button (orange, prominent)
- On click: fetches all live data → renders briefing page → triggers PDF generation

### Quick Plan (single-page form)
- Aircraft pre-selected (most recently used, changeable)
- Route fields (departure, destination, alternate)
- Fuel onboard + reserve select
- Departure datetime
- "Generate Briefing" button
- No step-by-step; all fields on one scrollable page

### Recent Plans sidebar
- Shows last 5 saved plans with "↺ Reuse this plan" shortcut
- Reuse pre-fills all wizard fields
- Guests see empty sidebar with sign-in prompt

---

## Briefing Output — `/plan/:id`

Generated briefing is a full HTML page rendered at `/plan/:id` (also the live-refresh URL).

### Action bar (sticky, no-print)
- **⬇ Download PDF** — triggers jsPDF generation in browser; saves to device; works fully offline
- **✉ Email to Me** — sends PDF as attachment via noreply@openchecklists.net; prompts for address if guest
- **🖨 Print** — window.print(); action bar suppressed via `@media print`
- **🔄 Refresh live data** — re-fetches all worker endpoints, updates briefing in place; shows data age

### Flight summary banner
- Route: `KBTL → KGRR (alt: KAZO)`
- Aircraft N-number + type
- Date, departure time (local), estimated en route time, distance (nm)
- Overall VFR/MVFR/IFR badge derived from worst condition across all airports

### Per-airport sections (Departure, Destination, Alternate)

Each section contains:

**Airport header**
- IDENT (large), role badge (Departure / Destination / Alternate)
- Full name, city/state, airspace class, elevation, pattern altitude
- Phone number (tel: link, from NASR `manager_phone` field)

**Weather**
- METAR raw text (monospace)
- Plain-English summary: wind, visibility, ceiling, temp/dew, altimeter
- VFR/MVFR/IFR/LIFR color badge
- TAF raw text (destination and alternate only)

**NOTAMs**
- All active NOTAMs listed
- Runway-closure NOTAMs: orange left border + ⚠ chip on affected runway
- "No active NOTAMs" shown in green if clear

**Frequencies**
- Table: MHz, Use, Facility
- CTAF/Tower row highlighted orange
- Rows: CTAF/Tower, Ground (if Class D+), ATIS/AWOS, Approach/Departure

**Runways**
- Chip per runway pair (e.g., "08R/26L")
- Closed runways: orange chip with ⚠
- Detail line: length × width, surface, ILS if equipped

**Alternate section** is compact (half-height): METAR summary + key frequency + NOTAM status only.

### Fuel planning card
- Table: fuel onboard, burn rate, ETE, fuel to destination, reserve required, total required, margin at destination
- Margin shown green if ≥ 1 hr extra, red if < 30 min extra
- Visual endurance bar: flight time / reserve / extra margin (three colors)

### Briefing footer
- "Generated [datetime] · openchecklists.net · Plan #[id]"
- Live refresh URL: `openchecklists.net/plan/[id]`
- Data age disclaimer: "Weather data as of [timestamp]"

---

## Data Model

### D1 additions (`ocl-api` worker)

**`flight_plans` table (new)**
```sql
CREATE TABLE flight_plans (
  id           TEXT PRIMARY KEY,        -- e.g. "ocl-4829"
  user_id      TEXT,                    -- null for guest plans
  created_at   TEXT NOT NULL,           -- ISO 8601
  aircraft_id  TEXT,                    -- FK to user_aircraft (nullable)
  aircraft_snapshot TEXT NOT NULL,      -- JSON: {n_number, make, model, fuel_cap, burn_rate, cruise_ktas}
  departure    TEXT NOT NULL,           -- ICAO ident
  destination  TEXT NOT NULL,
  alternate    TEXT,
  depart_at    TEXT,                    -- ISO 8601 local datetime
  fuel_onboard REAL,
  reserve_min  INTEGER,
  snapshot     TEXT NOT NULL            -- JSON: full briefing data at generation time
);
```

**`user_aircraft` table (exists — schema verified)**
Fields: `id`, `user_id`, `n_number`, `make`, `model`, `fuel_capacity_gal`, `burn_rate_gph`, `cruise_speed_ktas`, `notes`

### New worker endpoints (`ocl-api`)

```
GET  /api/me/plans              — list authenticated pilot's plans (last 20, desc)
POST /api/me/plans              — create/save a plan; returns {id}
GET  /api/plan/:id              — public read of saved plan (no auth; for refresh link)
POST /api/plan/:id/email        — (re)send plan email; body: {email}
```

`POST /api/me/plans` aggregates live data by calling:
- `/api/airport/{DEP}/weather`, `/api/airport/{DEST}/weather`, `/api/airport/{ALT}/weather`
- `/api/airport/{DEP}/notams`, `/api/airport/{DEST}/notams`, `/api/airport/{ALT}/notams`
- `/api/airport/{DEP}/fuel`

Aggregation happens server-side (worker), stored as `snapshot` JSON so the refresh URL always has a starting point even without live data.

---

## Email Infrastructure

**Sending account:** `noreply@openchecklists.net`
**Server:** kitwebhost4 (kw4), IP `192.249.115.220`
**Port:** 465 (SSL) or 587 (STARTTLS)
**Auth:** LOGIN (credentials in vault: "noreply@openchecklists.net SMTP kw4")

**DNS (all verified/updated 2026-08-13):**
- `mail.openchecklists.net` A → `192.249.115.220`
- SPF: `v=spf1 +mx +ip4:192.249.115.220 ~all`
- DKIM: `default._domainkey.openchecklists.net` — 2048-bit key generated on kw4
- DMARC: `v=DMARC1; p=quarantine`

Worker sends via SMTP using `SMTP_PASSWORD` secret (set via `wrangler secret put`).

**Email content:**
- Subject: `Your PreFlight Briefing — [ROUTE] [DATE]`
- Body: HTML briefing (same content as `/plan/:id` page, inline CSS)
- Attachment: PDF (base64 encoded, generated server-side from briefing HTML)
- Footer CTA: magic-link sign-in for guests

---

## PDF Generation

- Library: **jsPDF** (client-side)
- Triggered by "Download PDF" button
- Renders from the live briefing DOM (same HTML as screen)
- Filename: `preflight-[ROUTE]-[DATE].pdf` (e.g. `preflight-KBTL-KGRR-20260813.pdf`)
- Print CSS (`@media print`) used as fallback for browser Print → Save as PDF
- PDF includes refresh URL in footer so pilot can get fresh data when online

---

## Static Page

`/planner` is a static HTML page (generated by `build_site.py`, same as `profile.html`):
- Ships as `build/site/planner.html`
- Source in `worker/ocl-api/planner.html` (next to profile.html)
- Loads saved aircraft and airports from `/api/me/aircraft` and `/api/me/airports` on auth
- Guest state: shows planner with empty aircraft/airport quickfills, no sidebar history

---

## Error Handling & Degradation

| Scenario | Behavior |
|----------|----------|
| Worker endpoint timeout (5s) | Show "Unable to load [weather/NOTAMs]" with link to external source |
| Airport not found in NASR | Show error inline on route step: "Airport not found — check identifier" |
| jsPDF fails | Fall back to "Print this page → Save as PDF" instruction |
| Email send fails | Show error with "Try again" button; plan still saved |
| Guest with no email | Briefing still generates and displays; email prompt only on "Email to Me" click |

---

## Success Criteria

- ✅ Any pilot (guest or authenticated) can plan a KBTL→KGRR flight in under 2 minutes
- ✅ PDF downloads to device and opens offline
- ✅ Email delivers within 30 seconds of request
- ✅ Refresh URL shows current weather/NOTAMs when pilot taps it with signal
- ✅ NOTAM warnings are visible at a glance (no hunting required)
- ✅ Fuel math is correct and cross-checked against aircraft performance figures
- ✅ Unauthenticated guest who emails plan lands in Zitadel with account created

---

## Out of Scope (v1)

- IFR routing, alternates, instrument approaches
- FAA flight plan filing (DUATS/Leidos)
- Weight & balance calculator
- SID/STAR/preferred route suggestions
- Route waypoints beyond direct DEP→DEST
- Obstacle/terrain analysis
- Mobile app / PWA install for the planner specifically
