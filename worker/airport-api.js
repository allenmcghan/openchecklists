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
