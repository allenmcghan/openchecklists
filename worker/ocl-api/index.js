/**
 * ocl-api — Open Checklists authenticated API Worker
 *
 * Routes (all under /api/*):
 *   GET  /api/me                  User profile + points + level
 *   PUT  /api/me                  Update username / display_name / share_leaderboard
 *   GET  /api/me/aircraft         List user aircraft
 *   POST /api/me/aircraft         Add aircraft
 *   DELETE /api/me/aircraft/:id   Remove aircraft
 *   GET  /api/me/airports         Favorite airports
 *   POST /api/me/airports         Add favorite airport
 *   DELETE /api/me/airports/:id   Remove favorite airport
 *   GET  /api/me/logs             Preflight log history (last 6 months)
 *   POST /api/me/logs             Save a preflight log (awards points)
 *   GET  /api/me/training         Training progress
 *   PUT  /api/me/training/:cert   Update training progress
 *   GET  /api/leaderboard         Top 100 (opted-in users only)
 *   POST /api/checklists/submit   Submit checklist for AI review + publish
 *   GET  /api/checklists          List public community checklists (with stats)
 *   GET  /api/checklists/stats    Bulk stats for ?ids=a,b,c (static slugs too)
 *   GET  /api/checklists/:id      Full JSON of a public community checklist
 *   GET  /api/checklists/:id/reviews  Reviews + aggregate for a checklist
 *   GET  /api/checklists/:id/stats    avg_stars/review_count/uses for a checklist
 *   POST /api/checklists/:id/review   Upsert a star rating + comment (auth)
 *   POST /api/checklists/:id/used     Increment anonymous usage counter (public)
 *   GET  /api/share/:logId        Public share snapshot for a log
 */

const CORS = {
  'Access-Control-Allow-Origin': 'https://openchecklists.net',
  'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  'Access-Control-Max-Age': '86400',
};

function cors(res) {
  const r = new Response(res.body, res);
  Object.entries(CORS).forEach(([k,v]) => r.headers.set(k,v));
  return r;
}

function json(data, status=200) {
  return cors(new Response(JSON.stringify(data), {
    status, headers: {'Content-Type':'application/json'}
  }));
}

function err(msg, status=400) { return json({error: msg}, status); }

// ---- JWT validation against Zitadel JWKS ----
let jwksCache = null, jwksCacheAt = 0;

async function getJwks(issuer) {
  if (jwksCache && Date.now() - jwksCacheAt < 3600_000) return jwksCache;
  const disc = await fetch(`${issuer}/.well-known/openid-configuration`);
  const {jwks_uri} = await disc.json();
  const resp = await fetch(jwks_uri);
  jwksCache = await resp.json();
  jwksCacheAt = Date.now();
  return jwksCache;
}

async function verifyToken(token, issuer) {
  const [headerB64, payloadB64, sigB64] = token.split('.');
  if (!headerB64 || !payloadB64 || !sigB64) throw new Error('malformed');
  const header  = JSON.parse(atob(headerB64.replace(/-/g,'+').replace(/_/g,'/')));
  const payload = JSON.parse(atob(payloadB64.replace(/-/g,'+').replace(/_/g,'/')));

  // Check expiry
  if (payload.exp && payload.exp < Date.now()/1000) throw new Error('expired');

  // Get the matching key
  const jwks = await getJwks(issuer);
  const key = jwks.keys.find(k => k.kid === header.kid);
  if (!key) throw new Error('key not found');

  // Import and verify
  const cryptoKey = await crypto.subtle.importKey(
    'jwk', key,
    {name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256'},
    false, ['verify']
  );
  const data  = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const sig   = Uint8Array.from(atob(sigB64.replace(/-/g,'+').replace(/_/g,'/')), c=>c.charCodeAt(0));
  const valid = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', cryptoKey, sig, data);
  if (!valid) throw new Error('invalid signature');
  return payload;
}

// ---- Auth middleware ----
async function auth(req, env) {
  const bearer = (req.headers.get('Authorization') || '').replace('Bearer ', '').trim();
  if (!bearer) return null;
  try {
    return await verifyToken(bearer, env.ZITADEL_ISSUER);
  } catch (e) {
    return null;
  }
}

// ---- Auto-register OTP-by-Email for new Zitadel users ----
// Zitadel passwordless magic-link ("send me a code") fails with COMMAND-JKLJ3 for any
// user that doesn't have the OTP-email factor. We register it automatically on first
// API contact so the user never hits that error. The call is idempotent in Zitadel
// (duplicate add is a no-op), so we fire it on every first_login event.
async function ensureOtpEmail(userId, issuer, svcToken) {
  if (!svcToken) return; // secret not configured — skip silently
  try {
    await fetch(`${issuer}/v2/users/${userId}/otp_email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${svcToken}`,
      },
      body: '{}',
    });
    // Non-2xx is fine — user may already have it; Zitadel returns 409 in that case.
  } catch (_) {
    // Network error — don't break login
  }
}

// ---- Ensure user exists ----
async function ensureUser(db, claims) {
  const id    = claims.sub;
  const email = claims.email || claims.preferred_username || '';
  const now   = new Date().toISOString();
  await db.prepare(
    `INSERT INTO users (id, email, joined_at) VALUES (?,?,?)
     ON CONFLICT(id) DO UPDATE SET email=excluded.email`
  ).bind(id, email, now).run();
  return db.prepare('SELECT * FROM users WHERE id=?').bind(id).first();
}

// ---- Points helpers ----
const POINTS = {
  preflight_complete: 10,
  preflight_partial:  5,
  first_of_day:       5,
  streak_7day:       50,
  quiz_correct:       3,
  quiz_perfect:      25,
  add_aircraft:      15,
  first_login:       25,
  checklist_contrib: 200,
  field_report:      100,
};

const LEVEL_THRESHOLDS = [0,100,300,750,1500,3000,6000];
function calcLevel(pts) {
  let lvl=1;
  for (let i=0;i<LEVEL_THRESHOLDS.length;i++) { if(pts>=LEVEL_THRESHOLDS[i]) lvl=i+1; }
  return lvl;
}

async function awardPoints(db, userId, event, detail='') {
  const pts = POINTS[event] || 0;
  if (!pts) return;
  const now = new Date().toISOString();
  await db.prepare(
    'INSERT INTO points_ledger (user_id,event,points,detail,earned_at) VALUES (?,?,?,?,?)'
  ).bind(userId, event, pts, detail, now).run();
  // Update user totals
  const newTotal = await db.prepare(
    'SELECT COALESCE(SUM(points),0) AS t FROM points_ledger WHERE user_id=?'
  ).bind(userId).first('t');
  const newLevel = calcLevel(newTotal);
  await db.prepare(
    'UPDATE users SET total_points=?,level=? WHERE id=?'
  ).bind(newTotal, newLevel, userId).run();
  return {points: pts, total: newTotal, level: newLevel};
}

// ---- AI checklist review ----
async function reviewChecklist(checklist, apiKey) {
  if (!apiKey) return {approved: true, notes: 'No AI review configured — auto-approved.'};
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 512,
      system: `You are a safety reviewer for an open aircraft checklist library.
Review submitted checklists for:
1. Aviation relevance (must be an actual aircraft/drone/flight operation checklist)
2. Safety — flag any items that are dangerously wrong or missing critical steps
3. No copyrighted verbatim text from manufacturer POHs or commercial products
4. No simulator/game content

Respond with JSON only: {"approved":true/false,"notes":"brief reason","safety_issues":["..."] or []}`,
      messages: [{
        role: 'user',
        content: `Review this checklist submission:\n\n${JSON.stringify(checklist, null, 2).substring(0, 4000)}`
      }]
    })
  });
  if (!resp.ok) return {approved: true, notes: 'Review service unavailable — auto-approved.'};
  const d = await resp.json();
  try {
    const text = d.content[0].text;
    return JSON.parse(text);
  } catch {
    return {approved: true, notes: 'Review parse error — auto-approved.'};
  }
}

// ---- Plan handlers ----

async function listPlans(req, env) {
  const user = await auth(req, env);
  if (!user) return new Response('Unauthorized', { status: 401 });
  const { results } = await env.DB.prepare(
    `SELECT id, departure, destination, alternate, depart_at, created_at, aircraft_snapshot
     FROM flight_plans WHERE user_id=? ORDER BY created_at DESC LIMIT 20`
  ).bind(user.sub).all();
  return new Response(JSON.stringify(results || []), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}

// Fetch weather/NOTAMs from aviationweather.gov directly. Used when building a
// plan snapshot server-side. We call the upstream directly rather than our own
// /api/airport/* route — a Worker fetching its own zone route is unreliable
// (self-subrequests can be short-circuited), which silently produced empty
// weather in stored plans.
async function fetchAirportWeather(ident) {
  const id = (ident || '').toUpperCase();
  if (!id) return null;
  const icao = id.length === 3 ? 'K' + id : id;
  try {
    const r = await fetch(
      `https://aviationweather.gov/api/data/metar?ids=${icao}&format=json&taf=true&hours=2`,
      { signal: AbortSignal.timeout(8000) }
    );
    const data = await r.json();
    if (!Array.isArray(data) || !data.length) return null;
    const o = data[0];
    return {
      metar: o.rawOb || null,
      taf: o.rawTaf || null,
      flight_category: o.fltCat || null,
      temp_c: o.temp ?? null,
      wind_dir: o.wdir ?? null,
      wind_kt: o.wspd ?? null,
      gust_kt: o.wgst ?? null,
      visibility_sm: o.visib ?? null,
      ceiling_ft: o.ceiling ?? null,
      altim_inhg: o.altim ?? null,
      source: 'aviationweather.gov',
    };
  } catch (e) {
    return null;
  }
}

async function fetchAirportNotams(ident) {
  const id = (ident || '').toUpperCase();
  if (!id) return null;
  const icao = id.length === 3 ? 'K' + id : id;
  try {
    const r = await fetch(
      `https://aviationweather.gov/api/data/notam?ids=${icao}&format=json`,
      { signal: AbortSignal.timeout(8000) }
    );
    const data = await r.json();
    if (!Array.isArray(data)) return { notams: [] };
    return { notams: data.map(n => ({ text: n.notamTxt || n.rawText || String(n) })) };
  } catch (e) {
    return { notams: [] };
  }
}

async function savePlan(req, env) {
  const user = await auth(req, env);
  const userId = user ? user.sub : null;

  let body;
  try { body = await req.json(); } catch { return new Response('Bad JSON', { status: 400 }); }

  let { aircraft, departure, destination, alternate, depart_at, fuel_onboard, reserve_min, route } = body;

  // Multi-leg: if a route of ordered waypoints (length >= 2) is supplied, it
  // drives departure/destination and the weather/notam fetch covers every leg.
  const hasRoute = Array.isArray(route) && route.filter(Boolean).length >= 2;
  if (hasRoute) {
    route = route.filter(Boolean);
    departure = route[0];
    destination = route[route.length - 1];
  } else {
    route = null;
  }

  if (!departure || !destination) {
    return new Response(JSON.stringify({ error: 'departure and destination required' }), { status: 422, headers: { 'Content-Type': 'application/json' } });
  }

  // De-duplicate the idents we actually fetch — a route may repeat an airport
  // and the alternate may already be a waypoint.
  const baseAirports = hasRoute ? [...route, alternate] : [departure, destination, alternate];
  const airports = [...new Set(baseAirports.filter(Boolean))];
  const [wxResults, notamResults] = await Promise.all([
    Promise.all(airports.map(fetchAirportWeather)),
    Promise.all(airports.map(fetchAirportNotams)),
  ]);
  const fuelResult = null; // no free fuel API available

  const snapshot = {
    departure, destination, alternate: alternate || null,
    route: hasRoute ? route : null,
    weather: Object.fromEntries(airports.map((id, i) => [id, wxResults[i]])),
    notams: Object.fromEntries(airports.map((id, i) => [id, notamResults[i]])),
    fuel: fuelResult,
    aircraft,
    depart_at, fuel_onboard, reserve_min: reserve_min || 30,
    generated_at: new Date().toISOString()
  };

  const randBytes = new Uint8Array(4);
  crypto.getRandomValues(randBytes);
  const id = 'ocl-' + Array.from(randBytes).map(b => b.toString(36).padStart(2,'0')).join('').slice(0, 6);

  await env.DB.prepare(
    `INSERT INTO flight_plans (id, user_id, created_at, aircraft_snapshot, departure, destination,
       alternate, depart_at, fuel_onboard, reserve_min, snapshot)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).bind(
    id, userId, new Date().toISOString(),
    JSON.stringify(aircraft || {}),
    departure, destination, alternate || null, depart_at || null,
    fuel_onboard || null, reserve_min || 30,
    JSON.stringify(snapshot)
  ).run();

  return new Response(JSON.stringify({ id }), {
    status: 201,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}

async function getPlan(req, env) {
  const parts = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = parts[2]; // /api/plan/:id — take index 2
  if (!id || !/^ocl-[a-z0-9]+$/i.test(id)) {
    return new Response(JSON.stringify({ error: 'Invalid plan ID' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  const row = await env.DB.prepare('SELECT * FROM flight_plans WHERE id=?').bind(id).first();
  if (!row) return new Response(JSON.stringify({ error: 'Not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });

  let snapshot = JSON.parse(row.snapshot);
  const url = new URL(req.url);

  if (url.searchParams.get('refresh') === '1') {
    const airports = [row.departure, row.destination, row.alternate].filter(Boolean);
    const fresh = await Promise.all(airports.map(apt =>
      Promise.all([fetchAirportWeather(apt), fetchAirportNotams(apt)])
    ));
    airports.forEach((apt, i) => {
      if (!snapshot.weather) snapshot.weather = {};
      if (!snapshot.notams) snapshot.notams = {};
      snapshot.weather[apt] = fresh[i][0];
      snapshot.notams[apt] = fresh[i][1];
    });
    snapshot.refreshed_at = new Date().toISOString();
  }

  const plan = {
    id: row.id,
    departure: row.departure,
    destination: row.destination,
    alternate: row.alternate,
    depart_at: row.depart_at,
    fuel_onboard: row.fuel_onboard,
    reserve_min: row.reserve_min,
    aircraft: JSON.parse(row.aircraft_snapshot || '{}'),
    snapshot,
    created_at: row.created_at
  };

  return new Response(JSON.stringify(plan), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}

// ---- Email plan handler ----
async function emailPlan(req, env) {
  const parts = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = parts[2]; // /api/plan/:id/email
  if (!id) return new Response(JSON.stringify({ error: 'Missing plan ID' }), { status: 400, headers: { 'Content-Type': 'application/json' } });

  let body;
  try { body = await req.json(); } catch { return new Response('Bad JSON', { status: 400 }); }
  const { email } = body;
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return new Response(JSON.stringify({ error: 'Valid email required' }), { status: 422, headers: { 'Content-Type': 'application/json' } });
  }

  const row = await env.DB.prepare('SELECT * FROM flight_plans WHERE id=?').bind(id).first();
  if (!row) return new Response(JSON.stringify({ error: 'Plan not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });

  const snap = JSON.parse(row.snapshot || '{}');
  const ac = JSON.parse(row.aircraft_snapshot || '{}');
  const route = `${row.departure} → ${row.destination}${row.alternate ? ` (alt: ${row.alternate})` : ''}`;
  const depWx = snap.weather?.[row.departure];
  const destWx = snap.weather?.[row.destination];

  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a2e">
<div style="background:#1f4e79;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">&#9992; PreFlight Briefing</h1>
  <p style="margin:8px 0 0;opacity:.85">${route} &middot; ${ac.n_number || 'N/A'} &middot; ${row.depart_at ? new Date(row.depart_at).toLocaleDateString() : 'Today'}</p>
</div>
<div style="background:#f8fafd;padding:20px 24px;border:1px solid #e0e7f0">
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:6px 8px;color:#666">Aircraft</td><td style="padding:6px 8px;font-weight:700">${ac.n_number || '&mdash;'} &middot; ${ac.make || ''} ${ac.model || ''}</td></tr>
    <tr style="background:#fff"><td style="padding:6px 8px;color:#666">Route</td><td style="padding:6px 8px;font-weight:700">${route}</td></tr>
    <tr><td style="padding:6px 8px;color:#666">Departure wx</td><td style="padding:6px 8px;font-family:monospace;font-size:12px">${depWx?.metar || 'No METAR'}</td></tr>
    <tr style="background:#fff"><td style="padding:6px 8px;color:#666">Destination wx</td><td style="padding:6px 8px;font-family:monospace;font-size:12px">${destWx?.metar || 'No METAR'}</td></tr>
    <tr><td style="padding:6px 8px;color:#666">Fuel</td><td style="padding:6px 8px">${row.fuel_onboard || '&mdash;'} gal &middot; ${row.reserve_min}-min reserve</td></tr>
  </table>
</div>
<div style="background:#fbf3e0;color:#6b4e00;padding:12px 24px;font-size:12px;line-height:1.5;border:1px solid #e6d9b0;border-top:0">
  <strong>Not an official weather briefing.</strong> These are unverified snapshots from when this plan was generated.
  14 CFR 91.103 requires an official briefing before flight &mdash;
  <a href="https://www.1800wxbrief.com/" style="color:#8a5a00;font-weight:700">1800wxbrief.com</a> or 1-800-WX-BRIEF.
</div>
<div style="background:#1f4e79;color:#fff;padding:14px 24px;border-radius:0 0 8px 8px;font-size:13px">
  <p style="margin:0">Live refresh: <a href="https://openchecklists.net/plan/?id=${id}" style="color:#7fc8f8">openchecklists.net/plan/?id=${id}</a></p>
  <p style="margin:6px 0 0;opacity:.7">Generated by OpenChecklists PreFlight &middot; openchecklists.net</p>
</div>
</body></html>`;

  const RELAY_URL = 'https://keylinkit.net/ocl-mail.php';
  const resp = await fetch(RELAY_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-OCL-Secret': env.OCL_MAIL_SECRET },
    body: JSON.stringify({ to: email, subject: `Your PreFlight Briefing — ${route}`, html }),
    signal: AbortSignal.timeout(8000)
  }).then(r => r.json()).catch(e => ({ ok: false, error: e.message }));

  if (!resp.ok) {
    return new Response(JSON.stringify({ error: 'Email send failed', detail: resp }), {
      status: 502, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }

  return new Response(JSON.stringify({ ok: true }), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}

// ---- Route handlers ----
const routes = {
  // GET /api/me
  'GET /api/me': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const ledger = await env.DB.prepare(
      'SELECT SUM(points) as pts, COUNT(*) as entries FROM points_ledger WHERE user_id=?'
    ).bind(user.id).first();

    // Award first login points + register OTP-email factor if brand new
    const logCount = await env.DB.prepare(
      'SELECT COUNT(*) as n FROM points_ledger WHERE user_id=? AND event="first_login"'
    ).bind(user.id).first('n');
    if (!logCount) {
      // awardPoints updates the users row; refresh our in-memory copy so the
      // response reflects the just-awarded bonus instead of the pre-award total.
      const award = await awardPoints(env.DB, user.id, 'first_login');
      if (award) { user.total_points = award.total; user.level = award.level; }
      // Ensure the user can receive magic-link codes (idempotent in Zitadel)
      await ensureOtpEmail(user.id, env.ZITADEL_ISSUER, env.ZITADEL_SVC_TOKEN);
    }

    return json({
      id:                user.id,
      email:             user.email,
      username:          user.username,
      display_name:      user.display_name,
      joined_at:         user.joined_at,
      total_points:      user.total_points,
      level:             user.level,
      level_name:        ['Student','Solo','Cross-Country','Instrument','Commercial','ATP','Examiner'][user.level-1] || 'Student',
      next_level_at:     LEVEL_THRESHOLDS[user.level] || null,
      share_leaderboard: !!user.share_leaderboard,
    });
  },

  // PUT /api/me
  'PUT /api/me': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const body = await req.json().catch(()=>({}));
    const allowed = ['username','display_name','share_leaderboard'];
    const sets = [], vals = [];
    for (const k of allowed) {
      if (body[k] !== undefined) { sets.push(`${k}=?`); vals.push(body[k]); }
    }
    if (!sets.length) return err('Nothing to update');
    vals.push(user.id);
    await env.DB.prepare(`UPDATE users SET ${sets.join(',')} WHERE id=?`).bind(...vals).run();
    return json({ok: true});
  },

  // GET /api/me/aircraft
  'GET /api/me/aircraft': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const {results} = await env.DB.prepare(
      'SELECT * FROM user_aircraft WHERE user_id=? ORDER BY added_at DESC'
    ).bind(user.id).all();
    return json({aircraft: results});
  },

  // POST /api/me/aircraft
  'POST /api/me/aircraft': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const b = await req.json().catch(()=>({}));
    const now = new Date().toISOString();
    const r = await env.DB.prepare(
      'INSERT INTO user_aircraft (user_id,make,model,registration,profile_toml,added_at) VALUES (?,?,?,?,?,?)'
    ).bind(user.id, b.make||'', b.model||'', b.registration||'', b.profile_toml||'', now).run();
    await awardPoints(env.DB, user.id, 'add_aircraft', `${b.make} ${b.model}`);
    return json({id: r.meta.last_row_id, ok: true});
  },

  // DELETE /api/me/aircraft/:id
  'DELETE /api/me/aircraft': async (req, env, claims, params) => {
    const user = await ensureUser(env.DB, claims);
    await env.DB.prepare('DELETE FROM user_aircraft WHERE id=? AND user_id=?').bind(params.id, user.id).run();
    return json({ok: true});
  },

  // GET /api/me/airports
  'GET /api/me/airports': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const {results} = await env.DB.prepare(
      'SELECT * FROM favorite_airports WHERE user_id=? ORDER BY added_at DESC'
    ).bind(user.id).all();
    return json({airports: results});
  },

  // POST /api/me/airports
  'POST /api/me/airports': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const b = await req.json().catch(()=>({}));
    if (!b.ident) return err('ident required');
    const now = new Date().toISOString();
    await env.DB.prepare(
      'INSERT OR IGNORE INTO favorite_airports (user_id,airport_ident,airport_name,added_at) VALUES (?,?,?,?)'
    ).bind(user.id, b.ident.toUpperCase(), b.name||'', now).run();
    return json({ok: true});
  },

  // DELETE /api/me/airports/:ident
  'DELETE /api/me/airports': async (req, env, claims, params) => {
    const user = await ensureUser(env.DB, claims);
    await env.DB.prepare('DELETE FROM favorite_airports WHERE user_id=? AND airport_ident=?').bind(user.id, params.id).run();
    return json({ok: true});
  },

  // GET /api/me/logs — last 6 months only
  // ── Flight logbook (the real logbook; distinct from preflight_logs) ──────────
  // GET /api/me/logbook — list entries + running totals
  'GET /api/me/logbook': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const { results } = await env.DB.prepare(
      `SELECT id,flight_date,dep,arr,route,aircraft,total_time,pic_time,landings,remarks,source
       FROM logbook_entries WHERE user_id=? ORDER BY flight_date DESC, created_at DESC LIMIT 1000`
    ).bind(user.id).all();
    const t = await env.DB.prepare(
      `SELECT COUNT(*) AS flights, COALESCE(SUM(total_time),0) AS total_time,
              COALESCE(SUM(pic_time),0) AS pic_time, COALESCE(SUM(landings),0) AS landings
       FROM logbook_entries WHERE user_id=?`
    ).bind(user.id).first();
    return json({ entries: results, totals: t });
  },

  // POST /api/me/logbook — add/update one entry; or /import to pull from plans+preflights
  'POST /api/me/logbook': async (req, env, claims, params) => {
    const user = await ensureUser(env.DB, claims);
    const parts = ((params && params.id) || '').split('/');
    const now = new Date().toISOString();

    if (parts[0] === 'import') {
      // Pull saved plans + recent preflight completions the user hasn't logged yet.
      let imported = 0;
      const plans = await env.DB.prepare(
        `SELECT id,departure,destination,alternate,depart_at,created_at,aircraft_snapshot,snapshot
         FROM flight_plans WHERE user_id=? ORDER BY created_at DESC LIMIT 200`
      ).bind(user.id).all();
      for (const p of (plans.results || [])) {
        let ac = {}; let route = null;
        try { ac = JSON.parse(p.aircraft_snapshot || '{}'); } catch (e) {}
        try { route = (JSON.parse(p.snapshot || '{}').route) || null; } catch (e) {}
        const acStr = [ac.n_number || ac.registration, ac.make, ac.model].filter(Boolean).join(' ');
        const routeStr = Array.isArray(route) ? route.join(' ') : [p.departure, p.destination].filter(Boolean).join(' ');
        const date = (p.depart_at || p.created_at || now).slice(0, 10);
        try {
          const r = await env.DB.prepare(
            `INSERT OR IGNORE INTO logbook_entries
             (id,user_id,flight_date,dep,arr,route,aircraft,total_time,pic_time,landings,remarks,source,source_ref,created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`
          ).bind(crypto.randomUUID(), user.id, date, p.departure || '', p.destination || '', routeStr,
                 acStr, 0, 0, 0, 'Imported from saved plan', 'plan', 'plan:' + p.id, now).run();
          if (r.meta.changes) imported++;
        } catch (e) {}
      }
      return json({ ok: true, imported });
    }

    // Single entry (manual add or edit)
    const b = await req.json().catch(() => ({}));
    const id = (b.id && String(b.id)) || crypto.randomUUID();
    const num = (v) => { const n = parseFloat(v); return isFinite(n) && n >= 0 ? n : 0; };
    await env.DB.prepare(
      `INSERT INTO logbook_entries
       (id,user_id,flight_date,dep,arr,route,aircraft,total_time,pic_time,landings,remarks,source,source_ref,created_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
       ON CONFLICT(id) DO UPDATE SET
         flight_date=excluded.flight_date, dep=excluded.dep, arr=excluded.arr, route=excluded.route,
         aircraft=excluded.aircraft, total_time=excluded.total_time, pic_time=excluded.pic_time,
         landings=excluded.landings, remarks=excluded.remarks`
    ).bind(id, user.id, (b.flight_date || now.slice(0, 10)), (b.dep || '').toUpperCase(), (b.arr || '').toUpperCase(),
           b.route || '', b.aircraft || '', num(b.total_time), num(b.pic_time),
           Math.round(num(b.landings)), (b.remarks || '').slice(0, 500), 'manual', null, now).run();
    return json({ id, ok: true });
  },

  // DELETE /api/me/logbook/:id
  'DELETE /api/me/logbook': async (req, env, claims, params) => {
    const user = await ensureUser(env.DB, claims);
    await env.DB.prepare('DELETE FROM logbook_entries WHERE id=? AND user_id=?').bind(params.id, user.id).run();
    return json({ ok: true });
  },

  'GET /api/me/logs': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const cutoff = new Date(Date.now() - 180 * 86400_000).toISOString();
    const {results} = await env.DB.prepare(
      `SELECT id,checklist_id,checklist_title,checklist_hash,aircraft_id,
              completed_at,items_total,items_checked
       FROM preflight_logs
       WHERE user_id=? AND completed_at>?
       ORDER BY completed_at DESC LIMIT 200`
    ).bind(user.id, cutoff).all();
    return json({logs: results});
  },

  // POST /api/me/logs — save preflight log, award points
  'POST /api/me/logs': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const b = await req.json().catch(()=>({}));
    if (!b.checklist_id) return err('checklist_id required');

    const id  = crypto.randomUUID();
    const now = new Date().toISOString();
    const pct = b.items_total > 0 ? b.items_checked / b.items_total : 0;

    // Enforce 6-month rolling retention — delete old logs
    const cutoff = new Date(Date.now() - 180 * 86400_000).toISOString();
    await env.DB.prepare('DELETE FROM preflight_logs WHERE user_id=? AND completed_at<?').bind(user.id, cutoff).run();

    await env.DB.prepare(
      `INSERT INTO preflight_logs (id,user_id,checklist_id,checklist_hash,checklist_title,
       aircraft_id,completed_at,items_total,items_checked,log_json)
       VALUES (?,?,?,?,?,?,?,?,?,?)`
    ).bind(id, user.id, b.checklist_id, b.checklist_hash||'', b.checklist_title||'',
           b.aircraft_id||null, now, b.items_total||0, b.items_checked||0,
           JSON.stringify(b.items||[])).run();

    // Award points
    let pointResult;
    if (pct >= 1.0) {
      pointResult = await awardPoints(env.DB, user.id, 'preflight_complete', b.checklist_title);
      // Check for first-of-day bonus
      const todayStart = now.substring(0,10) + 'T00:00:00.000Z';
      const todayCount = await env.DB.prepare(
        'SELECT COUNT(*) as n FROM preflight_logs WHERE user_id=? AND completed_at>=? AND id!=?'
      ).bind(user.id, todayStart, id).first('n');
      if (!todayCount) await awardPoints(env.DB, user.id, 'first_of_day');
    } else if (pct >= 0.8) {
      pointResult = await awardPoints(env.DB, user.id, 'preflight_partial', b.checklist_title);
    }

    return json({id, ok: true, points: pointResult});
  },

  // GET /api/me/training
  'GET /api/me/training': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const {results} = await env.DB.prepare(
      'SELECT * FROM training_progress WHERE user_id=? ORDER BY cert_id,requirement_key'
    ).bind(user.id).all();
    return json({progress: results});
  },

  // PUT /api/me/training/:cert
  'PUT /api/me/training': async (req, env, claims, params) => {
    const user = await ensureUser(env.DB, claims);
    const b = await req.json().catch(()=>({}));
    const now = new Date().toISOString();
    for (const [key, val] of Object.entries(b)) {
      await env.DB.prepare(
        `INSERT INTO training_progress (user_id,cert_id,requirement_key,status,value,updated_at)
         VALUES (?,?,?,?,?,?)
         ON CONFLICT(user_id,cert_id,requirement_key) DO UPDATE SET status=excluded.status,value=excluded.value,updated_at=excluded.updated_at`
      ).bind(user.id, params.id, key, val.status||'not_started', val.value||null, now).run();
    }
    return json({ok: true});
  },

  // POST /api/me/quiz — award points for a correct quiz answer
  'POST /api/me/quiz': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const result = await awardPoints(env.DB, user.id, 'quiz_correct');
    return json({ok: true, points: result});
  },

  // GET /api/leaderboard — only users who opted in
  'GET /api/leaderboard': async (req, env) => {
    const {results} = await env.DB.prepare(
      `SELECT username, display_name, total_points, level
       FROM users
       WHERE share_leaderboard=1 AND (username IS NOT NULL OR display_name IS NOT NULL)
       ORDER BY total_points DESC LIMIT 100`
    ).all();
    return json({leaderboard: results.map(u => ({
      name:   u.display_name || u.username || 'Pilot',
      points: u.total_points,
      level:  u.level,
      level_name: ['Student','Solo','Cross-Country','Instrument','Commercial','ATP','Examiner'][u.level-1]||'Student',
    }))});
  },

  // POST /api/checklists/submit — AI review then auto-publish
  'POST /api/checklists/submit': async (req, env, claims) => {
    const user = await ensureUser(env.DB, claims);
    const b = await req.json().catch(()=>({}));
    if (!b.checklist) return err('checklist object required');

    // Run AI review
    const review = await reviewChecklist(b.checklist, env.ANTHROPIC_API_KEY);

    const id  = b.checklist.id || crypto.randomUUID().substring(0,8);
    const now = new Date().toISOString();
    const status = review.approved && (!review.safety_issues || !review.safety_issues.length)
      ? 'approved' : 'rejected';

    await env.DB.prepare(
      `INSERT OR REPLACE INTO saved_checklists (id,user_id,title,checklist_json,review_status,review_notes,is_public,saved_at)
       VALUES (?,?,?,?,?,?,?,?)`
    ).bind(id, user.id, b.checklist.title||'Untitled', JSON.stringify(b.checklist),
           status, review.notes||'', status==='approved'?1:0, now).run();

    if (status === 'approved') {
      await awardPoints(env.DB, user.id, 'checklist_contrib', b.checklist.title);
    }

    return json({
      id, status,
      approved: review.approved,
      notes:    review.notes,
      safety_issues: review.safety_issues || [],
      points_awarded: status === 'approved' ? POINTS.checklist_contrib : 0,
    });
  },

  // GET /api/checklists — community list, per-id reviews/stats, bulk stats, full JSON.
  // checklist_id is a free-form string: static example slugs and community IDs both work.
  'GET /api/checklists': async (req, env, _claims, params) => {
    const parts = (params.id || '').split('/').filter(Boolean);

    // GET /api/checklists — list public community checklists
    if (!parts.length) {
      const { results } = await env.DB.prepare(
        `SELECT sc.id, sc.title, sc.saved_at, u.username, u.display_name
         FROM saved_checklists sc LEFT JOIN users u ON sc.user_id=u.id
         WHERE sc.is_public=1 ORDER BY sc.saved_at DESC`
      ).all();
      const list = [];
      for (const c of (results || [])) {
        const agg = await env.DB.prepare(
          'SELECT ROUND(AVG(stars),1) AS avg_stars, COUNT(*) AS review_count FROM checklist_reviews WHERE checklist_id=?'
        ).bind(c.id).first();
        const uses = await env.DB.prepare(
          'SELECT uses FROM checklist_usage WHERE checklist_id=?'
        ).bind(c.id).first('uses');
        list.push({
          id: c.id,
          title: c.title,
          author: c.display_name || c.username || 'A pilot',
          saved_at: c.saved_at,
          avg_stars: agg?.avg_stars || 0,
          review_count: agg?.review_count || 0,
          uses: uses || 0,
        });
      }
      return json({ checklists: list });
    }

    // GET /api/checklists/stats?ids=a,b,c — bulk stats (static slugs included)
    if (parts.length === 1 && parts[0] === 'stats') {
      const url = new URL(req.url);
      const ids = (url.searchParams.get('ids') || '')
        .split(',').map(s => s.trim()).filter(Boolean).slice(0, 300);
      const stats = {};
      for (const cid of ids) {
        const agg = await env.DB.prepare(
          'SELECT ROUND(AVG(stars),1) AS avg_stars, COUNT(*) AS review_count FROM checklist_reviews WHERE checklist_id=?'
        ).bind(cid).first();
        const uses = await env.DB.prepare(
          'SELECT uses FROM checklist_usage WHERE checklist_id=?'
        ).bind(cid).first('uses');
        stats[cid] = {
          avg_stars: agg?.avg_stars || 0,
          review_count: agg?.review_count || 0,
          uses: uses || 0,
        };
      }
      return json({ stats });
    }

    // GET /api/checklists/:id/reviews — review list + aggregate
    if (parts.length === 2 && parts[1] === 'reviews') {
      const cid = parts[0];
      const agg = await env.DB.prepare(
        'SELECT ROUND(AVG(stars),1) AS avg_stars, COUNT(*) AS review_count FROM checklist_reviews WHERE checklist_id=?'
      ).bind(cid).first();
      const { results } = await env.DB.prepare(
        `SELECT r.stars, r.comment, r.created_at, u.username, u.display_name
         FROM checklist_reviews r LEFT JOIN users u ON r.user_id=u.id
         WHERE r.checklist_id=? ORDER BY r.created_at DESC LIMIT 100`
      ).bind(cid).all();
      return json({
        avg_stars: agg?.avg_stars || 0,
        review_count: agg?.review_count || 0,
        reviews: (results || []).map(r => ({
          stars: r.stars,
          comment: r.comment || '',
          author: r.display_name || r.username || 'A pilot',
          created_at: r.created_at,
        })),
      });
    }

    // GET /api/checklists/:id/stats — single-checklist stats
    if (parts.length === 2 && parts[1] === 'stats') {
      const cid = parts[0];
      const agg = await env.DB.prepare(
        'SELECT ROUND(AVG(stars),1) AS avg_stars, COUNT(*) AS review_count FROM checklist_reviews WHERE checklist_id=?'
      ).bind(cid).first();
      const uses = await env.DB.prepare(
        'SELECT uses FROM checklist_usage WHERE checklist_id=?'
      ).bind(cid).first('uses');
      return json({
        avg_stars: agg?.avg_stars || 0,
        review_count: agg?.review_count || 0,
        uses: uses || 0,
      });
    }

    // GET /api/checklists/:id — full JSON of a public community checklist
    if (parts.length === 1) {
      const row = await env.DB.prepare(
        'SELECT checklist_json FROM saved_checklists WHERE id=? AND is_public=1'
      ).bind(parts[0]).first();
      if (!row) return err('Not found', 404);
      try {
        return json(JSON.parse(row.checklist_json));
      } catch {
        return err('Not found', 404);
      }
    }

    return err('Not found', 404);
  },

  // POST /api/checklists/:id/review (auth) | /api/checklists/:id/used (public)
  'POST /api/checklists': async (req, env, claims, params) => {
    const parts = (params.id || '').split('/').filter(Boolean);

    // POST /api/checklists/:id/review — upsert a star rating + comment (auth required)
    if (parts.length === 2 && parts[1] === 'review') {
      if (!claims) return err('Sign in to review', 401);
      const user = await ensureUser(env.DB, claims);
      const cid = parts[0];
      const b = await req.json().catch(() => ({}));
      const stars = parseInt(b.stars, 10);
      if (!(stars >= 1 && stars <= 5)) return err('stars must be 1-5', 422);
      const comment = (b.comment || '').toString().trim().substring(0, 2000);
      const now = new Date().toISOString();
      await env.DB.prepare(
        `INSERT INTO checklist_reviews (checklist_id,user_id,stars,comment,created_at)
         VALUES (?,?,?,?,?)
         ON CONFLICT(checklist_id,user_id) DO UPDATE SET stars=excluded.stars,comment=excluded.comment,created_at=excluded.created_at`
      ).bind(cid, user.id, stars, comment, now).run();
      const agg = await env.DB.prepare(
        'SELECT ROUND(AVG(stars),1) AS avg_stars, COUNT(*) AS review_count FROM checklist_reviews WHERE checklist_id=?'
      ).bind(cid).first();
      return json({ ok: true, avg_stars: agg?.avg_stars || 0, review_count: agg?.review_count || 0 });
    }

    // POST /api/checklists/:id/used — anonymous usage counter (public)
    if (parts.length === 2 && parts[1] === 'used') {
      const cid = parts[0];
      const now = new Date().toISOString();
      await env.DB.prepare(
        `INSERT INTO checklist_usage (checklist_id,uses,updated_at) VALUES (?,1,?)
         ON CONFLICT(checklist_id) DO UPDATE SET uses=uses+1, updated_at=?`
      ).bind(cid, now, now).run();
      const uses = await env.DB.prepare(
        'SELECT uses FROM checklist_usage WHERE checklist_id=?'
      ).bind(cid).first('uses');
      return json({ uses: uses || 0 });
    }

    return err('Unknown checklists action', 404);
  },

  // GET /api/me/plans — list saved flight plans (auth required)
  'GET /api/me/plans': listPlans,

  // POST /api/me/plans — save a new flight plan (anonymous allowed)
  'POST /api/me/plans': savePlan,

  // GET /api/plan/:id — retrieve a flight plan by ID (public)
  'GET /api/plan': getPlan,

  // POST /api/plan/:id/email — email a briefing for a plan (public — no auth required)
  'POST /api/plan': emailPlan,

  // ── Public aviation data — no auth ──────────────────────────────────────────

  // POST /api/airport/email-pdf — email a client-generated airport PDF to the
  // user. The browser can't call the kw3 mailer directly (the server adds a
  // duplicate wildcard CORS header), so we relay server-side with a shared
  // secret. Body: { email, ident, name, pdf_base64 }.
  'POST /api/airport': async (req, env, _claims, params) => {
    const parts = (params.id || '').split('/');
    if ((parts[0] || '') !== 'email-pdf') return err('Unknown airport action', 404);
    const b = await req.json().catch(() => ({}));
    if (!b.email || !b.pdf_base64) return err('email and pdf_base64 required', 422);
    try {
      const r = await fetch('https://api.openchecklists.net/airport-pdf.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-OCL-Secret': env.OCL_PDF_SECRET || '' },
        body: JSON.stringify({ email: b.email, ident: b.ident || '', name: b.name || '', pdf_base64: b.pdf_base64 }),
        signal: AbortSignal.timeout(15000),
      });
      const data = await r.json().catch(() => ({ error: 'relay error' }));
      return json(data, r.ok ? 200 : 502);
    } catch (e) {
      return json({ error: 'mail relay unavailable' }, 502);
    }
  },

  // POST /api/log/email-pdf — email a client-generated checklist-log PDF to the
  // user (relayed to the kw3 mailer with the shared secret, like the airport one).
  // Body: { email, title, pdf_base64 }.
  'POST /api/log': async (req, env, _claims, params) => {
    const parts = (params.id || '').split('/');
    if ((parts[0] || '') !== 'email-pdf') return err('Unknown log action', 404);
    const b = await req.json().catch(() => ({}));
    if (!b.email || !b.pdf_base64) return err('email and pdf_base64 required', 422);
    const title = (b.title || 'Checklist').slice(0, 100);
    try {
      const r = await fetch('https://api.openchecklists.net/mail-pdf.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-OCL-Secret': env.OCL_PDF_SECRET || '' },
        body: JSON.stringify({
          email: b.email,
          subject: 'Your checklist log: ' + title,
          filename: title.replace(/[^A-Za-z0-9]+/g, '-').slice(0, 60) + '-log.pdf',
          text: 'Your completed checklist log for "' + title + '" is attached.',
          pdf_base64: b.pdf_base64,
        }),
        signal: AbortSignal.timeout(15000),
      });
      const data = await r.json().catch(() => ({ error: 'relay error' }));
      return json(data, r.ok ? 200 : 502);
    } catch (e) {
      return json({ error: 'mail relay unavailable' }, 502);
    }
  },

  // GET /api/airport/:ident/weather|notams|fuel
  // Proxies aviationweather.gov server-side so browsers avoid CORS errors.
  'GET /api/airport': async (req, env, _claims, params) => {
    const parts = (params.id || '').split('/');
    const ident = (parts[0] || '').toUpperCase();
    const dtype = parts[1] || '';
    if (!ident) return err('Airport identifier required', 400);
    // aviationweather.gov uses ICAO format — 3-letter FAA codes need K prefix for US airports
    const icao = ident.length === 3 ? 'K' + ident : ident;

    if (dtype === 'weather') {
      try {
        const r = await fetch(
          `https://aviationweather.gov/api/data/metar?ids=${icao}&format=json&taf=true&hours=2`,
          { signal: AbortSignal.timeout(8000) }
        );
        const data = await r.json();
        if (!Array.isArray(data) || !data.length) return json({ error: 'No METAR data' });
        const o = data[0];
        return json({
          metar: o.rawOb || null,
          taf: o.rawTaf || null,
          flight_category: o.fltCat || null,
          temp_c: o.temp ?? null,
          wind_dir: o.wdir ?? null,
          wind_kt: o.wspd ?? null,
          gust_kt: o.wgst ?? null,
          visibility_sm: o.visib ?? null,
          ceiling_ft: o.ceiling ?? null,
          altim_inhg: o.altim ?? null,
          source: 'aviationweather.gov',
        });
      } catch (e) {
        return json({ error: 'Weather unavailable' });
      }
    }

    if (dtype === 'notams') {
      try {
        const r = await fetch(
          `https://aviationweather.gov/api/data/notam?ids=${icao}&format=json`,
          { signal: AbortSignal.timeout(8000) }
        );
        const data = await r.json();
        if (!Array.isArray(data)) return json({ notams: [] });
        return json({
          notams: data.map(n => ({ text: n.notamTxt || n.rawText || String(n) })),
        });
      } catch (e) {
        return json({ notams: [] });
      }
    }

    if (dtype === 'fuel') {
      return json({ fuel_types: [], error: 'No free fuel API available' });
    }

    return err('Unknown airport data type', 404);
  },

  // GET /api/proxy/windtemp   — winds aloft (CORS proxy)
  // GET /api/proxy/pirep/:id  — PIREPs within 50nm (CORS proxy)
  'GET /api/proxy': async (req, env, _claims, params) => {
    const parts = (params.id || '').split('/');
    const ptype = parts[0];
    const pident = (parts[1] || '').toUpperCase();

    // Proxy handler — also add K prefix for PIREP queries
    const picao = pident.length === 3 ? 'K' + pident : pident;
    let url;
    if (ptype === 'windtemp') {
      url = 'https://aviationweather.gov/api/data/windtemp?region=all&level=low&fcst=06&format=json';
    } else if (ptype === 'pirep' && pident) {
      url = `https://aviationweather.gov/api/data/pirep?format=json&distance=50&id=${picao}`;
    } else {
      return err('Unknown proxy type', 400);
    }

    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
      const body = await r.text();
      return new Response(body, {
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'public, max-age=300',
        },
      });
    } catch (e) {
      return json({ error: 'Proxy fetch failed' });
    }
  },

  // GET /api/share/:logId — public shareable log snapshot
  'GET /api/share': async (req, env, _claims, params) => {
    const log = await env.DB.prepare(
      `SELECT pl.checklist_title, pl.completed_at, pl.items_total, pl.items_checked,
              pl.log_json, u.username, u.display_name, u.level
       FROM preflight_logs pl JOIN users u ON pl.user_id=u.id
       WHERE pl.id=?`
    ).bind(params.id).first();
    if (!log) return err('Log not found or not shared', 404);
    const pilot = log.display_name || log.username || 'Anonymous Pilot';
    const pct   = log.items_total > 0 ? Math.round(log.items_checked/log.items_total*100) : 0;
    return json({
      checklist: log.checklist_title,
      completed_at: log.completed_at,
      pilot, pct,
      items_checked: log.items_checked,
      items_total: log.items_total,
      level: log.level,
      level_name: ['Student','Solo','Cross-Country','Instrument','Commercial','ATP','Examiner'][log.level-1]||'Student',
    });
  },
};

// ---- Main handler ----
export default {
  async fetch(req, env) {
    const url = new URL(req.url);

    if (req.method === 'OPTIONS') {
      return new Response(null, {status: 204, headers: CORS});
    }

    if (!url.pathname.startsWith('/api/')) {
      return new Response('Not found', {status: 404});
    }

    const claims = await auth(req, env);

    // Routes that don't require auth
    const publicRoutes = ['GET /api/leaderboard', 'GET /api/share', 'GET /api/plan', 'POST /api/me/plans', 'POST /api/plan', 'GET /api/airport', 'POST /api/airport', 'POST /api/log', 'GET /api/proxy', 'GET /api/checklists', 'POST /api/checklists'];

    // Match most-specific (longest path) routes first so that e.g.
    // `GET /api/me/aircraft` is not swallowed by the `GET /api/me` prefix.
    const ordered = Object.entries(routes).sort(
      (a, b) => b[0].length - a[0].length
    );

    for (const [pattern, handler] of ordered) {
      const [method, routePath] = pattern.split(' ');

      // Check method
      if (method !== req.method) continue;

      // Exact match (no param) or prefix match with a single trailing :id param
      if (url.pathname === routePath || url.pathname.startsWith(routePath + '/')) {
        const suffix = url.pathname.slice(routePath.length).replace(/^\//, '');
        const params = {id: suffix ? decodeURIComponent(suffix) : null};

        // Auth check
        if (!publicRoutes.includes(pattern) && !claims) {
          return err('Unauthorized', 401);
        }

        try {
          return await handler(req, env, claims, params);
        } catch (e) {
          console.error(e);
          return err('Internal error', 500);
        }
      }
    }

    return err('Not found', 404);
  }
};
