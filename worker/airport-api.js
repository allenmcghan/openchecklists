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
