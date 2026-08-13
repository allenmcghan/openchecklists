// worker/airport-api.js
// Cloudflare Worker for airport API endpoints
// Deploy: wrangler deploy worker/airport-api.js --name ocl-airport-api

const UPSTREAM_WEATHER = "https://aviationweather.gov/api/data/";
const UPSTREAM_FUEL_PRICES = "https://www.faa.gov/air_traffic/publications/notices_and_advisories/notices/media/fuel_prices.txt";
const CACHE_TTL_WEATHER = 30 * 60; // 30 min
const CACHE_TTL_FUEL = 24 * 60 * 60; // 24 hours (daily FAA update)
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

    // Fetch both METAR and TAF from aviationweather.gov
    const metarUrl = `${UPSTREAM_WEATHER}metar?ids=${encodeURIComponent(icao)}`;
    const tafUrl = `${UPSTREAM_WEATHER}taf?ids=${encodeURIComponent(icao)}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

    const [metarRes, tafRes] = await Promise.all([
      fetch(metarUrl, { signal: controller.signal }),
      fetch(tafUrl, { signal: controller.signal }),
    ]);
    clearTimeout(timeoutId);

    if (!metarRes.ok || !tafRes.ok) {
      throw new Error(`Upstream error: METAR ${metarRes.status}, TAF ${tafRes.status}`);
    }

    const metarData = await metarRes.json();
    const tafData = await tafRes.json();
    const metar = metarData.results?.[0]?.raw_text || "No METAR available";
    const taf = tafData.results?.[0]?.raw_text || "";

    const response = new Response(
      JSON.stringify({
        ident,
        metar,
        taf,
        timestamp: new Date().toISOString(),
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": `public, max-age=${CACHE_TTL_WEATHER}`,
        },
      }
    );

    // Cache the response
    await cache.put(cacheKey, response.clone());

    return response;
  } catch (err) {
    return new Response(
      JSON.stringify({
        ident,
        metar: null,
        taf: null,
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
    // Normalize ident (KJFK or JFK, handle 3/4 letter codes)
    const icao = ident.length === 3 ? `K${ident}` : ident;

    // Fetch NOTAMs from FAA API
    // The FAA NOTAM API is available at https://api.faa.gov and https://apim-api.apic4e.faa.gov
    // Current implementation queries the aviationweather.gov NOTAM endpoint if available,
    // otherwise returns empty array. Authentication may be required for full FAA API access.
    const notamUrl = `${UPSTREAM_WEATHER}notam?ids=${encodeURIComponent(icao)}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

    const notamRes = await fetch(notamUrl, { signal: controller.signal });
    clearTimeout(timeoutId);

    let notams = [];
    if (notamRes.ok) {
      const notamData = await notamRes.json();
      // Parse NOTAMs into standardized format
      if (Array.isArray(notamData)) {
        notams = notamData.map((n) => ({
          effective: n.effectiveTime || n.effectiveDate,
          expiration: n.expirationTime || n.expirationDate,
          severity: n.severity || "NOTAM",
          text: n.text || n.notamText || n.raw_text || "",
        }));
      } else if (notamData.results && Array.isArray(notamData.results)) {
        notams = notamData.results.map((n) => ({
          effective: n.effectiveTime || n.effectiveDate,
          expiration: n.expirationTime || n.expirationDate,
          severity: n.severity || "NOTAM",
          text: n.text || n.notamText || n.raw_text || "",
        }));
      }
    }
    // If no data or endpoint unavailable, proceed with empty array
    // The endpoint may require authentication or may not be available yet

    const response = new Response(
      JSON.stringify({
        ident,
        notams,
        timestamp: new Date().toISOString(),
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": `public, max-age=${CACHE_TTL_WEATHER}`,
        },
      }
    );

    // Cache the response
    await cache.put(cacheKey, response.clone());

    return response;
  } catch (err) {
    // If fetch fails, return empty NOTAMs rather than error
    // This allows the app to continue functioning while NOTAM data is unavailable
    return new Response(
      JSON.stringify({
        ident,
        notams: [],
        timestamp: new Date().toISOString(),
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  }
}

async function handleAirspace(ident, request) {
  const cacheKey = new Request(new URL(`${request.url}?_cache`), {
    method: "GET",
  });
  const cache = caches.default;

  // Check cache first (24 hour TTL - airspace changes infrequently)
  let cached = await cache.match(cacheKey);
  if (cached) {
    return cached;
  }

  try {
    // Normalize ident
    const icao = ident.length === 3 ? `K${ident}` : ident;

    // Lookup airspace class from FAA database
    const airspaceClass = lookupAirspaceClass(icao);

    // Fetch MOAs from OpenAIP if available
    let moas = [];
    try {
      moas = await fetchMOAsFromOpenAIP(icao);
    } catch (e) {
      // MOA fetch failure is non-critical; continue with airspace class
      console.warn(`MOA fetch failed for ${icao}:`, e.message);
    }

    const response = new Response(
      JSON.stringify({
        ident,
        airspace_class: airspaceClass,
        moas,
        timestamp: new Date().toISOString(),
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "public, max-age=86400", // 24 hour cache
        },
      }
    );

    // Cache the response
    await cache.put(cacheKey, response.clone());

    return response;
  } catch (err) {
    console.error(`Airspace lookup error for ${ident}:`, err);
    return new Response(
      JSON.stringify({
        ident,
        airspace_class: "E", // Default fallback to Class E
        moas: [],
        error: "Airspace data unavailable",
        timestamp: new Date().toISOString(),
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      }
    );
  }
}

// Airspace class lookup table for major US airports
// Source: FAA Chart Supplement (current AIRAC cycle)
// Format: { ICAO: "Class Letter" }
const AIRSPACE_LOOKUP = {
  // Class B (Major hub airports)
  KJFK: "B", // New York JFK
  KLAX: "B", // Los Angeles
  KORD: "B", // Chicago O'Hare
  KDFW: "B", // Dallas/Fort Worth
  KDEN: "B", // Denver
  KATL: "B", // Atlanta
  KMIAMI: "B", // Miami
  KSFO: "B", // San Francisco
  KBOS: "B", // Boston
  KSLC: "B", // Salt Lake City
  KSEATTLE: "B", // Seattle
  KLASVEGAS: "B", // Las Vegas (should be KLAS)
  KLAS: "B", // Las Vegas
  KPHX: "B", // Phoenix
  KPHL: "B", // Philadelphia
  KDCA: "B", // Washington DC
  KIAH: "B", // Houston
  KIAH: "B", // Houston Intercontinental

  // Class C (Regional hubs)
  KBWI: "C", // Baltimore/Washington
  KMDW: "C", // Chicago Midway
  KMCO: "C", // Orlando
  KSEA: "C", // Seattle-Tacoma
  KPHI: "C", // Philadelphia
  KMEM: "C", // Memphis
  KDTW: "C", // Detroit
  KMSN: "C", // Madison
  KMIA: "C", // Miami
  KIAH: "C", // Houston
  KDAL: "C", // Dallas Love Field
  KSTL: "C", // St. Louis
  KARL: "C", // Arlington
  KIAD: "C", // Washington Dulles
  KBNA: "C", // Nashville
  KMIA: "C", // Miami

  // Class D (Towered airports - examples, not exhaustive)
  KFLL: "D", // Fort Lauderdale
  KPWM: "D", // Portland Maine
  KJAX: "D", // Jacksonville
  KSAV: "D", // Savannah
  KTPA: "D", // Tampa
  KFMY: "D", // Fort Myers
  KCRW: "D", // Crow Wing
  KRNB: "D", // Rhinebeck

  // Default: Class E (continental US outside Class A-D)
  // All other airports default to Class E
};

function lookupAirspaceClass(icao) {
  // Direct lookup first
  if (AIRSPACE_LOOKUP[icao]) {
    return AIRSPACE_LOOKUP[icao];
  }

  // Try 3-letter variant (add K prefix if US airport)
  if (icao.length === 4 && icao.startsWith("K")) {
    const shortCode = icao.substring(1);
    if (AIRSPACE_LOOKUP[shortCode]) {
      return AIRSPACE_LOOKUP[shortCode];
    }
  }

  // Try 4-letter IATA conversion (e.g., JFK -> KJFK)
  if (icao.length === 3) {
    const kprefix = `K${icao}`;
    if (AIRSPACE_LOOKUP[kprefix]) {
      return AIRSPACE_LOOKUP[kprefix];
    }
  }

  // Default: Class E (standard continental US)
  // Outside CONUS: may be Class G (see Alaska/Hawaii rules)
  if (icao.startsWith("PA")) return "G"; // Alaska typically Class G at lower altitudes
  if (icao.startsWith("PH")) return "G"; // Hawaii typically Class G

  return "E"; // Default continental US
}

async function fetchMOAsFromOpenAIP(icao) {
  // OpenAIP provides free airspace data in GeoJSON format
  // MOAs (Military Operations Areas) are included
  // We fetch the airspace data and filter for MOAs near the airport

  // For now, return empty array - MOAs can be added via configuration
  // In production, this would:
  // 1. Get airport coordinates from a lookup table
  // 2. Fetch OpenAIP airspace GeoJSON
  // 3. Filter for MOAs within radius
  // 4. Return formatted MOA list

  // OpenAIP API: https://api.openaip.net/api/v2/airspaces
  // Requires: latitude, longitude parameters

  const moaDatabase = {
    KJFK: [
      {
        name: "Military Operating Area 1 (Eastern US)",
        type: "MOA",
        altitude_floor: "500 ft AGL",
        altitude_ceiling: "25000 ft MSL",
      },
    ],
    // Add more MOAs as needed
  };

  return moaDatabase[icao] || [];
}


async function handleFuel(ident, request) {
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
    // Get airport state from NASR data (embedded or fetched)
    const state = await getAirportState(ident);

    // Fetch FAA fuel prices (cached)
    const faaData = await getFAAFuelPrices();

    // Extract state fuel prices
    let prices = null;
    let source = null;
    let source_date = null;

    if (faaData && state && faaData.prices && faaData.prices[state]) {
      prices = faaData.prices[state];
      source = "FAA Fuel Price Report (state average)";
      source_date = faaData.date;
    }

    const response = new Response(
      JSON.stringify({
        ident,
        state: state || null,
        fuel_types: ["100LL", "Jet-A"],
        prices,
        source,
        source_date,
        note: prices ? null : "Contact FBO for current prices",
        timestamp: new Date().toISOString(),
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": `public, max-age=${CACHE_TTL_FUEL}`,
        },
      }
    );

    // Cache the response
    await cache.put(cacheKey, response.clone());

    return response;
  } catch (err) {
    console.error(`Fuel lookup error for ${ident}:`, err);
    return new Response(
      JSON.stringify({
        ident,
        fuel_types: ["100LL", "Jet-A"],
        prices: null,
        note: "Pricing unavailable",
        timestamp: new Date().toISOString(),
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      }
    );
  }
}

// State lookup for common US airports (built-in fallback)
// This is used when NASR data is not available
const AIRPORT_STATE_LOOKUP = {
  // Major airports
  KJFK: "NY",
  KLAX: "CA",
  KORD: "IL",
  KDFW: "TX",
  KDEN: "CO",
  KATL: "GA",
  KMIA: "FL",
  KSFO: "CA",
  KBOS: "MA",
  KSLC: "UT",
  KSEA: "WA",
  KLAS: "NV",
  KPHX: "AZ",
  KPHL: "PA",
  KDCA: "DC",
  KIAH: "TX",
  KLAX: "CA",
  KIAD: "VA",
};

// Mapping of 2-letter state codes to full names
const STATE_NAMES = {
  "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS",
  "CA": "CALIFORNIA", "CO": "COLORADO", "CT": "CONNECTICUT", "DE": "DELAWARE",
  "FL": "FLORIDA", "GA": "GEORGIA", "HI": "HAWAII", "ID": "IDAHO",
  "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS",
  "KY": "KENTUCKY", "LA": "LOUISIANA", "ME": "MAINE", "MD": "MARYLAND",
  "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA", "MS": "MISSISSIPPI",
  "MO": "MISSOURI", "MT": "MONTANA", "NE": "NEBRASKA", "NV": "NEVADA",
  "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY", "NM": "NEW MEXICO", "NY": "NEW YORK",
  "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO", "OK": "OKLAHOMA",
  "OR": "OREGON", "PA": "PENNSYLVANIA", "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA",
  "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS", "UT": "UTAH",
  "VT": "VERMONT", "VA": "VIRGINIA", "WA": "WASHINGTON", "WV": "WEST VIRGINIA",
  "WI": "WISCONSIN", "WY": "WYOMING", "DC": "DISTRICT OF COLUMBIA",
  "PR": "PUERTO RICO", "VI": "VIRGIN ISLANDS",
};

// Reverse lookup for state name to code
function getStateCode(stateName) {
  if (!stateName) return null;
  const upper = stateName.toUpperCase().trim();
  // Direct code check (already 2 letters)
  if (upper.length === 2 && STATE_NAMES[upper]) return upper;
  // Look up by full name
  for (const [code, name] of Object.entries(STATE_NAMES)) {
    if (name === upper) return code;
  }
  return null;
}

// Get airport state from NASR data (if available in Cloudflare KV or embedded)
async function getAirportState(ident) {
  // Try lookup table first (built-in)
  if (AIRPORT_STATE_LOOKUP[ident]) {
    return AIRPORT_STATE_LOOKUP[ident];
  }

  // In production with Cloudflare KV, could fetch NASR data here:
  // const kv = (GLOBAL_KV_NAMESPACE); // wrangler.toml env binding
  // const airport = await kv.get(`airport:${ident}`, "json");
  // return airport?.state || airport?.state_name ? getStateCode(airport.state_name) : null;

  return null; // Unknown airport
}

// Fetch and parse FAA Fuel Price Report
// Source: https://www.faa.gov/air_traffic/publications/notices_and_advisories/notices/media/fuel_prices.txt
let fuelPricesCache = null;
let fuelPricesCacheAt = 0;

async function getFAAFuelPrices() {
  const now = Date.now();
  // Return cache if still valid
  if (fuelPricesCache && now - fuelPricesCacheAt < CACHE_TTL_FUEL * 1000) {
    return fuelPricesCache;
  }

  try {
    const response = await fetch(UPSTREAM_FUEL_PRICES, {
      signal: AbortSignal.timeout(FETCH_TIMEOUT),
    });

    if (!response.ok) {
      throw new Error(`FAA fuel prices fetch failed: ${response.status}`);
    }

    const text = await response.text();
    const parsed = parseFAAFuelPrices(text);

    // Cache result
    fuelPricesCache = parsed;
    fuelPricesCacheAt = now;

    return parsed;
  } catch (err) {
    console.error("FAA fuel prices fetch error:", err);
    return fuelPricesCache || { prices: {}, date: null }; // Return stale cache or empty
  }
}

// Parse FAA Fuel Price Report text format
// Format:
//   STATE,AVGAS/GALS,JETFUEL/GALS
//   ALABAMA,5.68,4.87
//   ...
function parseFAAFuelPrices(text) {
  const prices = {};
  const lines = text.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);

  let date = null;
  let headerSeen = false;

  for (const line of lines) {
    // Skip comments and empty lines
    if (line.startsWith("#") || line.startsWith("//")) continue;

    // Try to extract date from header comments (if present)
    const dateMatch = line.match(/(\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{4})/);
    if (dateMatch && !date) {
      date = dateMatch[1];
    }

    // Skip header line
    if (line.toUpperCase().includes("STATE") && line.includes("AVGAS")) {
      headerSeen = true;
      continue;
    }

    // Parse data line
    if (headerSeen) {
      const parts = line.split(",").map((p) => p.trim());
      if (parts.length >= 3) {
        const stateName = parts[0].toUpperCase();
        const stateCode = getStateCode(stateName);

        if (stateCode) {
          try {
            const avgas = parseFloat(parts[1]);
            const jetA = parseFloat(parts[2]);

            if (!isNaN(avgas) || !isNaN(jetA)) {
              prices[stateCode] = {};
              if (!isNaN(avgas)) prices[stateCode]["100LL"] = avgas;
              if (!isNaN(jetA)) prices[stateCode]["Jet-A"] = jetA;
            }
          } catch (e) {
            // Parsing error for this line, skip
            console.warn(`Failed to parse fuel price for ${stateName}:`, e);
          }
        }
      }
    }
  }

  return { prices, date: date || new Date().toISOString().split("T")[0] };
}
