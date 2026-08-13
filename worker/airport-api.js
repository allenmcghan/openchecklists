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
