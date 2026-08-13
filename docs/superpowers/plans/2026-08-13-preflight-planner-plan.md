# PreFlight Plan Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete VFR flight planning workflow — wizard/quick-plan form → live weather/NOTAM aggregation → briefing page → print-to-PDF → email via kw4 SMTP.

**Architecture:** Static SPA pages (`planner.html`, `plan/index.html`) served by CF Pages call the existing `ocl-api` Cloudflare Worker for plan save/fetch/email. A PHP relay script on kw4 handles SMTP sending. The briefing is a print-CSS-optimized HTML page; "Download PDF" triggers the browser print dialog.

**Tech Stack:** Cloudflare Workers (D1 SQLite, fetch), PHP 8 on kw4 (Exim SMTP relay), vanilla JS SPA, print CSS for PDF, `wrangler` CLI for deploy.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `worker/ocl-api/schema.sql` | Modify | Add `flight_plans` table |
| `worker/ocl-api/index.js` | Modify | Add 4 new routes |
| `worker/ocl-api/planner.html` | Create | Full wizard + quick-plan SPA |
| `worker/ocl-api/plan-detail.html` | Create | Briefing output + print + email |
| `/home/kitnetadm/public_html/openchecklists.net/ocl-mail.php` | Create | PHP SMTP relay on kw4 |
| `tools/build_site.py` | Modify | Nav item + copy pages + airport button + _redirects |

---

## Task 1: D1 Schema — flight_plans table

**Files:**
- Modify: `worker/ocl-api/schema.sql`

- [ ] **Step 1.1: Add flight_plans table to schema.sql**

Open `worker/ocl-api/schema.sql` and append this block after the last existing table:

```sql
CREATE TABLE IF NOT EXISTS flight_plans (
  id                TEXT PRIMARY KEY,
  user_id           TEXT,
  created_at        TEXT NOT NULL,
  aircraft_snapshot TEXT NOT NULL,
  departure         TEXT NOT NULL,
  destination       TEXT NOT NULL,
  alternate         TEXT,
  depart_at         TEXT,
  fuel_onboard      REAL,
  reserve_min       INTEGER DEFAULT 30,
  snapshot          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flight_plans_user ON flight_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_flight_plans_created ON flight_plans(created_at DESC);
```

- [ ] **Step 1.2: Apply migration to production D1**

```bash
cd worker/ocl-api
CLOUDFLARE_API_KEY=$(bw get item "d7d06d7d-5509-4520-906a-df7039d32013" | jq -r '.fields[0].value') \
CLOUDFLARE_EMAIL="openchecklists@keylinkit.net" \
  npx wrangler d1 execute openchecklists-users \
    --file schema.sql \
    --remote 2>&1 | tail -10
```

Expected: `Successfully executed` with no errors.

- [ ] **Step 1.3: Verify table exists**

```bash
CLOUDFLARE_API_KEY=$(bw get item "d7d06d7d-5509-4520-906a-df7039d32013" | jq -r '.fields[0].value') \
CLOUDFLARE_EMAIL="openchecklists@keylinkit.net" \
  npx wrangler d1 execute openchecklists-users \
    --command "SELECT name FROM sqlite_master WHERE type='table' AND name='flight_plans';" \
    --remote 2>&1 | grep flight_plans
```

Expected: `flight_plans` in output.

- [ ] **Step 1.4: Commit**

```bash
git add worker/ocl-api/schema.sql
git commit -m "feat: add flight_plans D1 table"
```

---

## Task 2: Worker — Plan Routes (list + save)

**Files:**
- Modify: `worker/ocl-api/index.js`

The existing router uses an object `const routes = { 'METHOD /path': handler }`. Add new entries following the same pattern. `auth(req, env)` returns the JWT payload or null.

- [ ] **Step 2.1: Add listPlans handler after the existing route handlers**

Open `worker/ocl-api/index.js`. Find the last route handler function (likely around line 450). Add these two functions before the routes object:

```javascript
async function listPlans(req, env) {
  const user = await auth(req, env);
  if (!user) return new Response('Unauthorized', { status: 401 });
  const { results } = await env.DB.prepare(
    `SELECT id, departure, destination, alternate, depart_at, created_at,
            aircraft_snapshot
     FROM flight_plans WHERE user_id=? ORDER BY created_at DESC LIMIT 20`
  ).bind(user.sub).all();
  return new Response(JSON.stringify(results), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}

async function savePlan(req, env) {
  // Works for both authenticated and guest pilots
  const user = await auth(req, env);
  const userId = user ? user.sub : null;

  let body;
  try { body = await req.json(); } catch { return new Response('Bad JSON', { status: 400 }); }

  const { aircraft, departure, destination, alternate, depart_at, fuel_onboard, reserve_min } = body;
  if (!departure || !destination) return new Response('departure and destination required', { status: 422 });

  // Aggregate live data in parallel (5-second timeout per call)
  const airports = [departure, destination, alternate].filter(Boolean);
  const wxCalls = airports.map(id =>
    fetch(`https://openchecklists.net/api/airport/${id}/weather`, { signal: AbortSignal.timeout(5000) })
      .then(r => r.json()).catch(() => null)
  );
  const notamCalls = airports.map(id =>
    fetch(`https://openchecklists.net/api/airport/${id}/notams`, { signal: AbortSignal.timeout(5000) })
      .then(r => r.json()).catch(() => null)
  );
  const fuelCall = fetch(`https://openchecklists.net/api/airport/${departure}/fuel`, { signal: AbortSignal.timeout(5000) })
    .then(r => r.json()).catch(() => null);

  const [wxResults, notamResults, fuelResult] = await Promise.all([
    Promise.all(wxCalls),
    Promise.all(notamCalls),
    fuelCall
  ]);

  const snapshot = {
    departure, destination, alternate: alternate || null,
    weather: Object.fromEntries(airports.map((id, i) => [id, wxResults[i]])),
    notams: Object.fromEntries(airports.map((id, i) => [id, notamResults[i]])),
    fuel: fuelResult,
    aircraft,
    depart_at, fuel_onboard, reserve_min: reserve_min || 30,
    generated_at: new Date().toISOString()
  };

  // Generate short ID: "ocl-" + 6 random alphanum chars
  const id = 'ocl-' + Array.from(crypto.getRandomValues(new Uint8Array(4)))
    .map(b => b.toString(36).padStart(2,'0')).join('').slice(0, 6);

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
```

- [ ] **Step 2.2: Register routes in the routes object**

Find the `const routes = {` block. Add these two entries:

```javascript
'GET /api/me/plans': listPlans,
'POST /api/me/plans': savePlan,
```

- [ ] **Step 2.3: Add CORS preflight for new routes**

Check whether the existing router handles `OPTIONS` globally. In the main `fetch` handler, find where OPTIONS is handled. Ensure `/api/me/plans` and `/api/plan/` are covered. The existing pattern likely handles all OPTIONS with a blanket response — if so, no change needed. Verify by searching for `OPTIONS` in index.js.

If OPTIONS is handled per-route, add:
```javascript
'OPTIONS /api/me/plans': () => new Response(null, { status: 204, headers: corsHeaders }),
```

where `corsHeaders` matches the existing pattern in the file.

- [ ] **Step 2.4: Quick smoke test (local)**

```bash
cd worker/ocl-api
npx wrangler dev --port 8787 &
sleep 3
# Test without auth (should return 401 for list)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/api/me/plans
# Expected: 401
# Test save without auth (should work, guest plan)
curl -s -X POST http://localhost:8787/api/me/plans \
  -H "Content-Type: application/json" \
  -d '{"departure":"KBTL","destination":"KGRR","aircraft":{"n_number":"N12345","make":"Cessna","model":"172S","fuel_capacity_gal":35,"burn_rate_gph":8.5,"cruise_speed_ktas":110},"fuel_onboard":35,"reserve_min":30}' | jq .
# Expected: {"id":"ocl-XXXXXX"}
kill %1
```

- [ ] **Step 2.5: Commit**

```bash
git add worker/ocl-api/index.js
git commit -m "feat: add GET/POST /api/me/plans worker routes"
```

---

## Task 3: Worker — Public Plan Read

**Files:**
- Modify: `worker/ocl-api/index.js`

- [ ] **Step 3.1: Add getPlan handler**

In `worker/ocl-api/index.js`, add this function alongside the handlers from Task 2:

```javascript
async function getPlan(req, env) {
  // Extract plan ID from URL: /api/plan/ocl-abc123
  const id = new URL(req.url).pathname.split('/').pop();
  if (!id || !/^ocl-[a-z0-9]+$/i.test(id)) {
    return new Response('Invalid plan ID', { status: 400 });
  }

  const row = await env.DB.prepare(
    'SELECT * FROM flight_plans WHERE id=?'
  ).bind(id).first();

  if (!row) return new Response('Not found', { status: 404 });

  // Optionally refresh live data if ?refresh=1
  const url = new URL(req.url);
  let snapshot = JSON.parse(row.snapshot);

  if (url.searchParams.get('refresh') === '1') {
    const airports = [row.departure, row.destination, row.alternate].filter(Boolean);
    const fresh = await Promise.all(airports.map(apt =>
      Promise.all([
        fetch(`https://openchecklists.net/api/airport/${apt}/weather`, { signal: AbortSignal.timeout(5000) })
          .then(r => r.json()).catch(() => null),
        fetch(`https://openchecklists.net/api/airport/${apt}/notams`, { signal: AbortSignal.timeout(5000) })
          .then(r => r.json()).catch(() => null)
      ])
    ));
    airports.forEach((apt, i) => {
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
    aircraft: JSON.parse(row.aircraft_snapshot),
    snapshot,
    created_at: row.created_at
  };

  return new Response(JSON.stringify(plan), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}
```

- [ ] **Step 3.2: Register route**

In the routes object, add:
```javascript
'GET /api/plan/': getPlan,
```

Note: the existing router dispatches on prefix match for paths with trailing slash + param, so `GET /api/plan/` will match `/api/plan/ocl-abc123`. Verify this matches the routing logic in the file (around line 498).

- [ ] **Step 3.3: Commit**

```bash
git add worker/ocl-api/index.js
git commit -m "feat: add GET /api/plan/:id worker route with optional refresh"
```

---

## Task 4: Email Relay + Worker Email Route

**Files:**
- Create: `/home/kitnetadm/public_html/openchecklists.net/ocl-mail.php` (on kw4 via SSH)
- Modify: `worker/ocl-api/index.js`

The CF Worker cannot open raw TCP SMTP connections. Instead, a PHP script on kw4 accepts a POST request from the Worker and sends via Exim.

- [ ] **Step 4.1: Create PHP mail relay on kw4**

```bash
ssh -i /home/node/.ssh/kitwebhost_root_ed25519 -o StrictHostKeyChecking=no root@100.64.0.18 "
mkdir -p /home/kitnetadm/public_html/openchecklists.net
cat > /home/kitnetadm/public_html/openchecklists.net/ocl-mail.php << 'PHPEOF'
<?php
// OCL mail relay — called by the CF Worker to send plan emails
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-OCL-Secret');

if (\$_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
if (\$_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'Method not allowed']); exit; }

\$secret = getenv('OCL_MAIL_SECRET') ?: file_get_contents('/home/kitnetadm/.ocl-mail-secret');
\$provided = trim(\$_SERVER['HTTP_X_OCL_SECRET'] ?? '');
if (!hash_equals(trim(\$secret), \$provided)) {
  http_response_code(403);
  echo json_encode(['error'=>'Forbidden']);
  exit;
}

\$body = json_decode(file_get_contents('php://input'), true);
if (!isset(\$body['to'], \$body['subject'], \$body['html'])) {
  http_response_code(422);
  echo json_encode(['error'=>'Missing to, subject, or html']);
  exit;
}

\$to = filter_var(\$body['to'], FILTER_VALIDATE_EMAIL);
if (!\$to) { http_response_code(422); echo json_encode(['error'=>'Invalid email']); exit; }

\$subject = mb_encode_mimeheader(\$body['subject'], 'UTF-8', 'Q');
\$html = \$body['html'];
\$boundary = 'OCL_' . bin2hex(random_bytes(8));

\$headers  = 'From: OpenChecklists PreFlight <noreply@openchecklists.net>' . \"\\r\\n\";
\$headers .= 'Reply-To: noreply@openchecklists.net' . \"\\r\\n\";
\$headers .= 'MIME-Version: 1.0' . \"\\r\\n\";
\$headers .= 'Content-Type: multipart/alternative; boundary=\"' . \$boundary . '\"' . \"\\r\\n\";
\$headers .= 'X-Mailer: OpenChecklists-PreFlight/1.0' . \"\\r\\n\";

\$plain = strip_tags(str_replace(['<br>','<br/>','</p>','</div>'], \"\\n\", \$html));
\$message  = '--' . \$boundary . \"\\r\\n\";
\$message .= 'Content-Type: text/plain; charset=UTF-8' . \"\\r\\n\\r\\n\";
\$message .= wordwrap(\$plain, 72, \"\\r\\n\") . \"\\r\\n\";
\$message .= '--' . \$boundary . \"\\r\\n\";
\$message .= 'Content-Type: text/html; charset=UTF-8' . \"\\r\\n\\r\\n\";
\$message .= \$html . \"\\r\\n\";
\$message .= '--' . \$boundary . '--';

\$ok = mail(\$to, \$subject, \$message, \$headers,
  '-f noreply@openchecklists.net');

echo json_encode(['ok' => \$ok]);
PHPEOF
chmod 644 /home/kitnetadm/public_html/openchecklists.net/ocl-mail.php
chown kitnetadm:kitnetadm /home/kitnetadm/public_html/openchecklists.net/ocl-mail.php
echo 'PHP relay created'
"
```

- [ ] **Step 4.2: Generate and store the shared secret**

```bash
MAIL_SECRET=$(openssl rand -hex 24)
echo "Secret: $MAIL_SECRET"

# Store on kw4
ssh -i /home/node/.ssh/kitwebhost_root_ed25519 -o StrictHostKeyChecking=no root@100.64.0.18 \
  "echo '$MAIL_SECRET' > /home/kitnetadm/.ocl-mail-secret && chmod 600 /home/kitnetadm/.ocl-mail-secret && chown kitnetadm:kitnetadm /home/kitnetadm/.ocl-mail-secret"

# Store in vault
bw create item "$(bw get template item | python3 -c "
import sys, json
t = json.load(sys.stdin)
t['name'] = 'ocl-mail-relay-secret'
t['type'] = 1
t['login'] = {'password': '$MAIL_SECRET'}
t['notes'] = 'Shared secret for kw4 PHP mail relay. Used as X-OCL-Secret header from CF Worker.'
print(json.dumps(t))
" <<< "$(bw get template item)")" | jq -r '"Vault: " + .name'

# Set as Worker secret
echo "$MAIL_SECRET" | CLOUDFLARE_API_KEY=$(bw get item "d7d06d7d-5509-4520-906a-df7039d32013" | jq -r '.fields[0].value') \
  CLOUDFLARE_EMAIL="openchecklists@keylinkit.net" \
  npx wrangler --config worker/ocl-api/wrangler.toml secret put OCL_MAIL_SECRET
```

- [ ] **Step 4.3: Ensure mail.openchecklists.net vhost serves the file**

```bash
ssh -i /home/node/.ssh/kitwebhost_root_ed25519 -o StrictHostKeyChecking=no root@100.64.0.18 "
# Check if openchecklists.net has a docroot under kitnetadm
ls /home/kitnetadm/public_html/openchecklists.net/
# Verify Apache/LiteSpeed will serve it (check vhost config exists)
grep -r 'openchecklists' /etc/apache2/conf.d/ 2>/dev/null | head -5 || \
  grep -r 'openchecklists' /usr/local/apache/conf.d/ 2>/dev/null | head -5
"
```

If no vhost exists for openchecklists.net on kw4 webserver, create a symlink or configure cPanel to serve the domain. The mail subdomain (`mail.openchecklists.net` → `192.249.115.220`) should serve via the same webserver. Verify with:

```bash
curl -sk https://mail.openchecklists.net/ocl-mail.php -X OPTIONS -o /dev/null -w "%{http_code}"
# Expected: 204
```

If this fails (SSL or vhost issue), use `api.openchecklists.net` (also points to kw4 if updated) or update `mail.openchecklists.net` vhost config.

- [ ] **Step 4.4: Test the PHP relay**

```bash
MAIL_SECRET=$(bw get password "ocl-mail-relay-secret" 2>/dev/null)
curl -s -X POST https://mail.openchecklists.net/ocl-mail.php \
  -H "Content-Type: application/json" \
  -H "X-OCL-Secret: $MAIL_SECRET" \
  -d '{"to":"allen@keylinkit.com","subject":"OCL Mail Relay Test","html":"<p>PreFlight plan relay test. If you see this, email is working.</p>"}' | jq .
# Expected: {"ok": true}
```

Check allen@keylinkit.com for the test email.

- [ ] **Step 4.5: Add emailPlan handler to index.js**

```javascript
async function emailPlan(req, env) {
  const id = new URL(req.url).pathname.split('/')[3]; // /api/plan/:id/email
  if (!id) return new Response('Missing plan ID', { status: 400 });

  let body;
  try { body = await req.json(); } catch { return new Response('Bad JSON', { status: 400 }); }
  const { email } = body;
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return new Response('Valid email required', { status: 422 });
  }

  const row = await env.DB.prepare('SELECT * FROM flight_plans WHERE id=?').bind(id).first();
  if (!row) return new Response('Plan not found', { status: 404 });

  const snapshot = JSON.parse(row.snapshot);
  const aircraft = JSON.parse(row.aircraft_snapshot);
  const route = `${row.departure} → ${row.destination}${row.alternate ? ` (alt: ${row.alternate})` : ''}`;

  // Build HTML email body (inline CSS for mail clients)
  const depWx = snapshot.weather?.[row.departure];
  const destWx = snapshot.weather?.[row.destination];
  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a2e">
<div style="background:#1f4e79;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">✈ PreFlight Briefing</h1>
  <p style="margin:8px 0 0;opacity:.85">${route} · ${aircraft.n_number || ''} · ${row.depart_at ? new Date(row.depart_at).toLocaleDateString() : 'Today'}</p>
</div>
<div style="background:#f8fafd;padding:20px 24px;border:1px solid #e0e7f0">
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:6px 8px;color:#666">Aircraft</td><td style="padding:6px 8px;font-weight:700">${aircraft.n_number} · ${aircraft.make} ${aircraft.model}</td></tr>
    <tr style="background:#fff"><td style="padding:6px 8px;color:#666">Route</td><td style="padding:6px 8px;font-weight:700">${route}</td></tr>
    <tr><td style="padding:6px 8px;color:#666">Departure wx</td><td style="padding:6px 8px">${depWx?.metar || 'No METAR'}</td></tr>
    <tr style="background:#fff"><td style="padding:6px 8px;color:#666">Destination wx</td><td style="padding:6px 8px">${destWx?.metar || 'No METAR'}</td></tr>
    <tr><td style="padding:6px 8px;color:#666">Fuel onboard</td><td style="padding:6px 8px">${row.fuel_onboard || '—'} gal · ${row.reserve_min}-min reserve</td></tr>
  </table>
</div>
<div style="background:#1f4e79;color:#fff;padding:14px 24px;border-radius:0 0 8px 8px;font-size:13px">
  <p style="margin:0">Live refresh: <a href="https://openchecklists.net/plan/${id}" style="color:#7fc8f8">openchecklists.net/plan/${id}</a></p>
  <p style="margin:6px 0 0;opacity:.7">Generated by OpenChecklists PreFlight · openchecklists.net</p>
</div>
</body></html>`;

  // Send via kw4 PHP relay
  const resp = await fetch('https://mail.openchecklists.net/ocl-mail.php', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-OCL-Secret': env.OCL_MAIL_SECRET
    },
    body: JSON.stringify({
      to: email,
      subject: `Your PreFlight Briefing — ${route}`,
      html
    }),
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
```

- [ ] **Step 4.6: Register email route**

In the routes object, add:
```javascript
'POST /api/plan/': emailPlan,
```

Note: This prefix-matches `/api/plan/:id/email`. The handler extracts the ID from index 3 of the path split. Verify the routing logic handles this correctly — if the router matches `/api/plan/` prefix for both GET and POST, ensure the GET handler returns 404 for paths like `/api/plan/ocl-abc/email` (it will, because the snapshot query won't match).

If the router dispatches by exact method+prefix, this works as-is. If there's a conflict, rename the route to `'POST /api/plan-email/': emailPlan` and adjust the URL in plan-detail.html accordingly.

- [ ] **Step 4.7: Commit**

```bash
git add worker/ocl-api/index.js
git commit -m "feat: add POST /api/plan/:id/email route and kw4 PHP relay"
```

---

## Task 5: planner.html — Wizard + Quick Plan SPA

**Files:**
- Create: `worker/ocl-api/planner.html`

This is a self-contained SPA. It reads auth token from sessionStorage, loads saved aircraft/airports, renders wizard or quick-plan form, and POSTs to `/api/me/plans` on generate.

- [ ] **Step 5.1: Create planner.html**

Create `/home/node/workspace/openchecklists/openchecklists/worker/ocl-api/planner.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plan a Flight — OpenChecklists</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f4f9;color:#1a1a2e;min-height:100vh}
.page{max-width:900px;margin:0 auto;padding:1.5rem 1rem 3rem}
h1{font-size:1.55rem;font-weight:800;color:#1f4e79;margin-bottom:.3rem}
.sub{color:#666;font-size:.9rem;margin-bottom:1.2rem}
.guest-notice{background:#fff8e6;border:1px solid #f5d580;border-radius:8px;padding:10px 14px;font-size:.82rem;color:#7a5c00;margin-bottom:1rem;display:flex;gap:8px;align-items:flex-start}
.tabs{display:flex;border-bottom:2px solid #dde3ee;margin-bottom:1.4rem}
.tab{padding:10px 20px;font-size:.88rem;font-weight:600;color:#888;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px}
.tab.active{color:#1f4e79;border-color:#1f4e79}
.panel{display:none}.panel.active{display:block}
/* Steps */
.steps{display:flex;align-items:center;background:#fff;border-radius:10px;padding:10px 14px;box-shadow:0 1px 6px rgba(0,0,0,.06);margin-bottom:1.4rem;overflow-x:auto}
.snum{width:24px;height:24px;border-radius:50%;font-size:.7rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.snum.done{background:#27ae60;color:#fff}
.snum.active{background:#1f4e79;color:#fff}
.snum.todo{background:#e0e7f0;color:#888}
.slbl{font-size:.7rem;font-weight:600;margin-left:5px;white-space:nowrap}
.slbl.done{color:#27ae60}.slbl.active{color:#1f4e79}.slbl.todo{color:#aaa}
.sconn{flex:0 0 16px;height:2px;background:#e0e7f0;margin:0 4px;flex-shrink:0}
.sconn.done{background:#27ae60}
/* Cards */
.card{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.07);overflow:hidden;margin-bottom:.8rem}
.card-hdr{padding:1rem 1.2rem;border-bottom:1px solid #f0f4f9}
.card-hdr h2{font-size:1rem;font-weight:700;color:#1f4e79}
.card-hdr p{font-size:.82rem;color:#666;margin-top:3px}
.card-body{padding:1.2rem}
.card-foot{padding:.8rem 1.2rem;border-top:1px solid #f0f4f9;display:flex;justify-content:space-between;align-items:center}
/* AC grid */
.ac-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:.8rem}
.ac-card{border:2px solid #dde3ee;border-radius:10px;padding:10px 12px;cursor:pointer}
.ac-card.sel{border-color:#1f4e79;background:#eef4fb}
.ac-reg{font-size:1rem;font-weight:800;color:#1f4e79}
.ac-model{font-size:.78rem;color:#555;margin-top:2px}
.ac-specs{font-size:.68rem;color:#888;margin-top:4px;line-height:1.4}
.ac-add{border:2px dashed #ccd5e0;border-radius:10px;padding:10px 12px;cursor:pointer;color:#888;font-size:.8rem;display:flex;align-items:center;justify-content:center;gap:5px;min-height:80px}
.ac-add:hover{border-color:#1f4e79;color:#1f4e79}
/* Fields */
label{display:block;font-size:.68rem;font-weight:700;color:#1f4e79;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
input,select{width:100%;background:#f4f6f9;border:1.5px solid #dde3ee;border-radius:7px;padding:8px 11px;font-size:.88rem;font-family:inherit;color:#333}
input:focus,select:focus{outline:none;border-color:#1f4e79;background:#fff}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px}
.field{margin-bottom:10px}
.chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
.chip{background:#eef4fb;border:1px solid #c5d8ee;color:#1f4e79;font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:10px;cursor:pointer;letter-spacing:.04em}
.chip:hover{background:#1f4e79;color:#fff}
.hint{font-size:.68rem;color:#aaa;margin-top:3px}
/* Buttons */
.btn{display:inline-flex;align-items:center;gap:5px;padding:9px 18px;border-radius:8px;font-size:.85rem;font-weight:700;cursor:pointer;border:none;font-family:inherit}
.btn-primary{background:#1f4e79;color:#fff}
.btn-ghost{background:transparent;border:1.5px solid #dde3ee;color:#555}
.btn-ghost:hover{border-color:#1f4e79;color:#1f4e79}
.btn-generate{background:#e67e22;color:#fff;font-size:.95rem;padding:11px 24px}
.btn-generate:hover{background:#cf6d17}
.btn-generate:disabled{opacity:.5;cursor:not-allowed}
/* Summary strip */
.summary-strip{background:#f0f8f4;border:1px solid #c8e6d4;border-radius:8px;padding:8px 12px;font-size:.8rem;color:#333;display:flex;align-items:center;gap:8px;margin-bottom:.8rem}
.summary-strip .change{margin-left:auto;color:#1f4e79;cursor:pointer;font-size:.72rem;text-decoration:underline}
/* WX preview */
.wx-card{background:#f8fafd;border:1px solid #e0e7f0;border-radius:8px;padding:10px 14px;margin-bottom:8px}
.wx-apt{font-weight:800;color:#1f4e79;font-size:.88rem;margin-bottom:4px}
.wx-metar{font-family:monospace;font-size:.72rem;color:#555;word-break:break-all;margin-bottom:4px}
.wx-badge{display:inline-block;font-size:.65rem;font-weight:700;padding:1px 7px;border-radius:8px;color:#fff}
.vfr{background:#27ae60}.mvfr{background:#2980b9}.ifr{background:#c0392b}.lifr{background:#6c3483}
.wx-loading{color:#888;font-size:.8rem;font-style:italic}
/* Sidebar */
.layout{display:grid;grid-template-columns:1fr 240px;gap:1rem}
.sidebar-card{background:#fff;border-radius:10px;box-shadow:0 1px 8px rgba(0,0,0,.06);padding:1rem;margin-bottom:.8rem}
.sidebar-card h3{font-size:.72rem;font-weight:700;color:#1f4e79;text-transform:uppercase;letter-spacing:.07em;margin-bottom:.6rem}
.plan-row{padding:6px 0;border-bottom:1px solid #f0f4f9;cursor:pointer}
.plan-row:last-child{border-bottom:none}
.plan-route{font-size:.82rem;font-weight:700;color:#333}
.plan-meta{font-size:.68rem;color:#888;margin-top:1px}
.plan-reuse{font-size:.65rem;color:#1f4e79;margin-top:2px}
@media(max-width:680px){.layout{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}.grid3{grid-template-columns:1fr 1fr}.steps{gap:2px}}
</style>
</head>
<body>
<div class="page">
  <h1>Plan a Flight</h1>
  <p class="sub">VFR preflight briefing — weather, NOTAMs, frequencies, fuel. Print or email when done.</p>

  <div id="guest-notice" class="guest-notice" style="display:none">
    💡 Planning as a guest. Enter your email when you generate — we'll send the briefing and create your free account.
  </div>

  <div class="layout">
    <div id="main-col">
      <div class="tabs">
        <div class="tab active" onclick="switchTab('wizard',this)">Guided Planning</div>
        <div class="tab" onclick="switchTab('quick',this)">Quick Plan</div>
      </div>

      <!-- WIZARD PANEL -->
      <div id="wizard" class="panel active">
        <div class="steps" id="steps-bar">
          <!-- Rendered by JS -->
        </div>
        <div id="wizard-step-content"></div>
      </div>

      <!-- QUICK PLAN PANEL -->
      <div id="quick" class="panel">
        <div class="card">
          <div class="card-hdr"><h2>Quick Plan</h2><p>All fields on one page — for pilots with saved aircraft.</p></div>
          <div class="card-body">
            <div class="field">
              <label>Aircraft</label>
              <div id="qp-aircraft-area"><p style="color:#888;font-size:.85rem">Loading aircraft…</p></div>
            </div>
            <div class="grid2">
              <div class="field">
                <label>Departure</label>
                <input id="qp-dep" type="text" placeholder="ICAO" maxlength="4" style="text-transform:uppercase">
                <div class="chips" id="qp-dep-chips"></div>
              </div>
              <div class="field">
                <label>Destination</label>
                <input id="qp-dest" type="text" placeholder="ICAO" maxlength="4" style="text-transform:uppercase">
                <div class="chips" id="qp-dest-chips"></div>
              </div>
            </div>
            <div class="field">
              <label>Alternate <span style="font-weight:400;color:#aaa">(optional)</span></label>
              <input id="qp-alt" type="text" placeholder="ICAO" maxlength="4" style="text-transform:uppercase;max-width:160px">
            </div>
            <div class="grid3">
              <div class="field">
                <label>Fuel onboard (gal)</label>
                <input id="qp-fuel" type="number" min="0" step="0.5" placeholder="35">
                <div class="hint" id="qp-fuel-hint"></div>
              </div>
              <div class="field">
                <label>Reserve</label>
                <select id="qp-reserve">
                  <option value="30">30 min VFR</option>
                  <option value="45">45 min night/IFR</option>
                  <option value="60">60 min conservative</option>
                </select>
              </div>
              <div class="field">
                <label>Departure time</label>
                <input id="qp-depart" type="datetime-local">
              </div>
            </div>
          </div>
          <div class="card-foot">
            <span></span>
            <button class="btn btn-generate" id="qp-generate" onclick="submitPlan('quick')">Generate Briefing →</button>
          </div>
        </div>
      </div>
    </div><!-- /main-col -->

    <div id="sidebar">
      <div class="sidebar-card">
        <h3>Recent Plans</h3>
        <div id="recent-plans"><p style="font-size:.78rem;color:#888">Sign in to see your plan history.</p></div>
      </div>
      <div class="sidebar-card">
        <h3>My Aircraft</h3>
        <div id="sidebar-aircraft"><p style="font-size:.78rem;color:#888">Sign in to see saved aircraft.</p></div>
      </div>
    </div>
  </div>
</div>

<script>
const API = 'https://app.openchecklists.net';
let tok = null;
let aircraft = [];
let airports = [];
let wz = { step: 1, ac: null, dep: '', dest: '', alt: '', depart_at: '', fuel: null, reserve: 30 };
let wxCache = {};

// ── Auth ──
function getToken() { return sessionStorage.getItem('ocl:token'); }
tok = getToken();

// ── Init ──
async function init() {
  // Set default datetime (now, no past)
  const now = new Date();
  const pad = n => String(n).padStart(2,'0');
  const localNow = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
  document.querySelectorAll('input[type=datetime-local]').forEach(el => { el.value = localNow; el.min = localNow; });

  if (!tok) {
    document.getElementById('guest-notice').style.display = 'flex';
  } else {
    // Load aircraft, airports, recent plans
    const [acResp, apResp, planResp] = await Promise.allSettled([
      fetch(API + '/api/me/aircraft', { headers: { Authorization: 'Bearer ' + tok } }).then(r => r.json()),
      fetch(API + '/api/me/airports', { headers: { Authorization: 'Bearer ' + tok } }).then(r => r.json()),
      fetch(API + '/api/me/plans', { headers: { Authorization: 'Bearer ' + tok } }).then(r => r.json())
    ]);
    aircraft = acResp.status === 'fulfilled' && Array.isArray(acResp.value) ? acResp.value : [];
    airports = apResp.status === 'fulfilled' && Array.isArray(apResp.value) ? apResp.value : [];
    renderSidebar(planResp.status === 'fulfilled' ? planResp.value : []);
  }
  renderStep();
  renderQuickPlan();
}

// ── Sidebar ──
function renderSidebar(plans) {
  const rp = document.getElementById('recent-plans');
  const sa = document.getElementById('sidebar-aircraft');
  if (plans && plans.length) {
    rp.innerHTML = plans.slice(0,5).map(p => {
      const ac = JSON.parse(typeof p.aircraft_snapshot === 'string' ? p.aircraft_snapshot : '{}');
      return `<div class="plan-row" onclick="reusePlan(${JSON.stringify(p).replace(/"/g,'&quot;')})">
        <div class="plan-route">${p.departure} → ${p.destination}</div>
        <div class="plan-meta">${p.created_at ? p.created_at.slice(0,10) : ''} · ${ac.n_number||''}</div>
        <div class="plan-reuse">↺ Reuse this plan</div>
      </div>`;
    }).join('');
  } else {
    rp.innerHTML = '<p style="font-size:.78rem;color:#888">No recent plans.</p>';
  }
  if (aircraft.length) {
    sa.innerHTML = aircraft.map(a =>
      `<div style="font-size:.82rem;padding:4px 0;border-bottom:1px solid #f0f4f9">
        <strong>${a.n_number}</strong> · ${a.make} ${a.model}<br>
        <span style="color:#888;font-size:.7rem">${a.fuel_capacity_gal} gal · ${a.cruise_speed_ktas} kt · ${a.burn_rate_gph} GPH</span>
      </div>`
    ).join('') + `<a href="/profile" style="font-size:.72rem;color:#1f4e79;margin-top:6px;display:inline-block">+ Add aircraft</a>`;
  } else {
    sa.innerHTML = `<a href="/profile" style="font-size:.78rem;color:#1f4e79">+ Add your first aircraft</a>`;
  }
}

function reusePlan(p) {
  const ac = JSON.parse(typeof p.aircraft_snapshot === 'string' ? p.aircraft_snapshot : '{}');
  wz = { step: 2, ac, dep: p.departure, dest: p.destination, alt: p.alternate||'', depart_at: '', fuel: ac.fuel_capacity_gal||null, reserve: p.reserve_min||30 };
  document.querySelector('.tab').click();
  renderStep();
}

// ── Wizard ──
function renderStepBar() {
  const steps = ['Aircraft','Route','Weather','Fuel','Review'];
  const bar = document.getElementById('steps-bar');
  bar.innerHTML = steps.map((s,i) => {
    const n = i+1;
    const cls = n < wz.step ? 'done' : n === wz.step ? 'active' : 'todo';
    const lbl = n < wz.step ? '✓' : n;
    return (i > 0 ? `<div class="sconn ${n <= wz.step ? 'done' : ''}"></div>` : '') +
      `<div style="display:flex;align-items:center;gap:4px"><div class="snum ${cls}">${lbl}</div><span class="slbl ${cls}">${s}</span></div>`;
  }).join('');
}

function renderStep() {
  renderStepBar();
  const el = document.getElementById('wizard-step-content');
  if (wz.step === 1) el.innerHTML = renderAircraftStep();
  else if (wz.step === 2) el.innerHTML = renderRouteStep();
  else if (wz.step === 3) el.innerHTML = renderWeatherStep();
  else if (wz.step === 4) el.innerHTML = renderFuelStep();
  else if (wz.step === 5) el.innerHTML = renderReviewStep();

  // Re-attach event listeners
  document.querySelectorAll('.chip[data-field]').forEach(chip => {
    chip.onclick = () => {
      const inp = document.getElementById(chip.dataset.field);
      if (inp) inp.value = chip.textContent.trim();
    };
  });
  document.querySelectorAll('input[type=datetime-local]').forEach(el => {
    const now = new Date();
    const pad = n => String(n).padStart(2,'0');
    const localNow = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
    if (!el.value) el.value = localNow;
    el.min = localNow;
  });
}

function renderAircraftStep() {
  const cards = aircraft.map(a =>
    `<div class="ac-card${wz.ac?.n_number===a.n_number?' sel':''}" onclick='selectAC(${JSON.stringify(a)})'>
      <div class="ac-reg">${a.n_number}</div>
      <div class="ac-model">${a.make} ${a.model}</div>
      <div class="ac-specs">${a.fuel_capacity_gal} gal · ${a.cruise_speed_ktas} kt · ${a.burn_rate_gph} GPH</div>
    </div>`
  ).join('');
  const addCard = `<div class="ac-add" onclick="window.location='/profile'">+ Add aircraft in profile</div>`;
  return `<div class="card">
    <div class="card-hdr"><h2>Step 1 — Select your aircraft</h2><p>Your saved aircraft appear below. Manage them in your profile.</p></div>
    <div class="card-body">
      <div class="ac-grid">${cards}${addCard}</div>
      ${!aircraft.length ? '<p style="color:#888;font-size:.85rem">No aircraft saved. <a href="/profile" style="color:#1f4e79">Add one in your profile</a> or continue as guest.</p>' : ''}
    </div>
    <div class="card-foot">
      <span></span>
      <button class="btn btn-primary" onclick="nextStep()" ${!wz.ac?'disabled':''}>Next: Route →</button>
    </div>
  </div>
  ${wz.ac ? `<div class="summary-strip">✓ <strong>${wz.ac.n_number}</strong> · ${wz.ac.make} ${wz.ac.model} · ${wz.ac.fuel_capacity_gal} gal · ${wz.ac.cruise_speed_ktas} kt</div>` : ''}`;
}

function selectAC(a) {
  wz.ac = a;
  wz.fuel = a.fuel_capacity_gal;
  renderStep();
}

function renderRouteStep() {
  const favChips = (field) => airports.map(ap =>
    `<div class="chip" data-field="${field}">${ap.ident}</div>`).join('');
  return `<div class="card">
    <div class="card-hdr"><h2>Step 2 — Where are you flying?</h2><p>Enter ICAO identifiers. Click a saved airport chip to fill the field.</p></div>
    <div class="card-body">
      <div class="grid2">
        <div class="field">
          <label>Departure airport</label>
          <input id="wz-dep" type="text" value="${wz.dep}" maxlength="4" style="text-transform:uppercase" placeholder="e.g. KBTL">
          <div class="chips">${favChips('wz-dep')}</div>
        </div>
        <div class="field">
          <label>Destination airport</label>
          <input id="wz-dest" type="text" value="${wz.dest}" maxlength="4" style="text-transform:uppercase" placeholder="e.g. KGRR">
          <div class="chips">${favChips('wz-dest')}</div>
        </div>
      </div>
      <div class="field">
        <label>Alternate airport <span style="font-weight:400;color:#aaa">(optional)</span></label>
        <input id="wz-alt" type="text" value="${wz.alt}" maxlength="4" style="text-transform:uppercase;max-width:160px" placeholder="e.g. KAZO">
        <div class="hint">Recommended when ceiling &lt; 2,000 ft or vis &lt; 3 SM</div>
      </div>
      <div class="field" style="max-width:220px">
        <label>Departure time (local)</label>
        <input id="wz-depart" type="datetime-local" value="${wz.depart_at}">
      </div>
    </div>
    <div class="card-foot">
      <button class="btn btn-ghost" onclick="prevStep()">← Back</button>
      <button class="btn btn-primary" onclick="saveRoute()">Next: Weather →</button>
    </div>
  </div>
  ${wz.ac ? `<div class="summary-strip">✓ <strong>${wz.ac.n_number}</strong> · ${wz.ac.make} ${wz.ac.model}<span class="change" onclick="wz.step=1;renderStep()">Change aircraft</span></div>` : ''}`;
}

function saveRoute() {
  wz.dep = (document.getElementById('wz-dep').value||'').toUpperCase().trim();
  wz.dest = (document.getElementById('wz-dest').value||'').toUpperCase().trim();
  wz.alt = (document.getElementById('wz-alt').value||'').toUpperCase().trim();
  wz.depart_at = document.getElementById('wz-depart').value || '';
  if (!wz.dep || !wz.dest) { alert('Enter departure and destination airports.'); return; }
  nextStep();
  fetchWeather();
}

async function fetchWeather() {
  const apts = [wz.dep, wz.dest, wz.alt].filter(Boolean);
  for (const apt of apts) {
    if (!wxCache[apt]) {
      wxCache[apt] = 'loading';
      fetch(`https://openchecklists.net/api/airport/${apt}/weather`)
        .then(r => r.json()).then(d => { wxCache[apt] = d; renderStep(); })
        .catch(() => { wxCache[apt] = null; renderStep(); });
    }
  }
}

function wxBadge(metar) {
  if (!metar) return '';
  const vis = (metar.match(/\s(\d+)SM/) || [])[1];
  const ovc = metar.match(/(?:OVC|BKN)(\d{3})/)?.[1];
  const ceil = ovc ? parseInt(ovc) * 100 : 99999;
  const v = parseInt(vis || '10');
  let cat = 'vfr', lbl = 'VFR';
  if (ceil < 500 || v < 1) { cat = 'lifr'; lbl = 'LIFR'; }
  else if (ceil < 1000 || v < 3) { cat = 'ifr'; lbl = 'IFR'; }
  else if (ceil < 3000 || v < 5) { cat = 'mvfr'; lbl = 'MVFR'; }
  return `<span class="wx-badge ${cat}">${lbl}</span>`;
}

function renderWeatherStep() {
  const apts = [wz.dep, wz.dest, wz.alt].filter(Boolean);
  const cards = apts.map(apt => {
    const wx = wxCache[apt];
    const role = apt===wz.dep?'Departure':apt===wz.dest?'Destination':'Alternate';
    let body = '<p class="wx-loading">Loading…</p>';
    if (wx === null) body = '<p style="color:#c0392b;font-size:.8rem">Unable to load weather. Check aviationweather.gov.</p>';
    else if (wx && wx !== 'loading') {
      body = `<div class="wx-metar">${wx.metar || 'No METAR available'}</div>${wxBadge(wx.metar)}`;
      if (wx.taf) body += `<div class="hint" style="margin-top:6px"><strong>TAF:</strong> ${wx.taf.slice(0,120)}…</div>`;
    }
    return `<div class="wx-card"><div class="wx-apt">${apt} <span style="font-weight:400;color:#888;font-size:.75rem">${role}</span></div>${body}</div>`;
  }).join('');
  return `<div class="card">
    <div class="card-hdr"><h2>Step 3 — Weather Preview</h2><p>Live conditions at your airports. Review before continuing.</p></div>
    <div class="card-body">${cards || '<p style="color:#888">No airports selected.</p>'}</div>
    <div class="card-foot">
      <button class="btn btn-ghost" onclick="prevStep()">← Back</button>
      <button class="btn btn-primary" onclick="nextStep()">Next: Fuel →</button>
    </div>
  </div>`;
}

function renderFuelStep() {
  const cap = wz.ac?.fuel_capacity_gal || '';
  const fuel = wz.fuel || cap || '';
  const burn = wz.ac?.burn_rate_gph || 8.5;
  const cruise = wz.ac?.cruise_speed_ktas || 110;
  // Rough ETE calc if airports known (very rough: assumes direct, 1 kt = 1 nm/hr)
  let ete = '—', fuelNeeded = '—', margin = '';
  // Can't compute distance without coordinates; just show fields
  return `<div class="card">
    <div class="card-hdr"><h2>Step 4 — Fuel Planning</h2><p>Enter fuel onboard. We'll calculate your margin and endurance.</p></div>
    <div class="card-body">
      <div class="grid3">
        <div class="field">
          <label>Fuel onboard (gal)</label>
          <input id="wz-fuel" type="number" value="${fuel}" min="0" max="${cap||999}" step="0.5" oninput="calcFuel()">
          ${cap ? `<div class="hint">Full tanks = ${cap} gal</div>` : ''}
        </div>
        <div class="field">
          <label>Reserve requirement</label>
          <select id="wz-reserve" onchange="calcFuel()">
            <option value="30"${wz.reserve===30?' selected':''}>30 min VFR</option>
            <option value="45"${wz.reserve===45?' selected':''}>45 min night/IFR</option>
            <option value="60"${wz.reserve===60?' selected':''}>60 min conservative</option>
          </select>
        </div>
        <div class="field">
          <label>Burn rate (GPH)</label>
          <input id="wz-burn" type="number" value="${burn}" min="1" step="0.1" oninput="calcFuel()">
        </div>
      </div>
      <div id="fuel-result" style="margin-top:.5rem;font-size:.85rem;color:#444"></div>
    </div>
    <div class="card-foot">
      <button class="btn btn-ghost" onclick="prevStep()">← Back</button>
      <button class="btn btn-primary" onclick="saveFuel()">Next: Review →</button>
    </div>
  </div>`;
}

function calcFuel() {
  const fuel = parseFloat(document.getElementById('wz-fuel')?.value) || 0;
  const reserve = parseInt(document.getElementById('wz-reserve')?.value) || 30;
  const burn = parseFloat(document.getElementById('wz-burn')?.value) || 8.5;
  const reserveGal = (reserve / 60) * burn;
  const available = fuel - reserveGal;
  const endurance = fuel / burn;
  const enduranceH = Math.floor(endurance);
  const enduranceM = Math.round((endurance - enduranceH) * 60);
  const ok = available > 0;
  document.getElementById('fuel-result').innerHTML =
    `Reserve required: <strong>${reserveGal.toFixed(1)} gal</strong> ·
     Usable after reserve: <strong style="color:${ok?'#27ae60':'#c0392b'}">${available.toFixed(1)} gal</strong> ·
     Total endurance: <strong>${enduranceH} hr ${enduranceM} min</strong>`;
}

function saveFuel() {
  wz.fuel = parseFloat(document.getElementById('wz-fuel')?.value) || null;
  wz.reserve = parseInt(document.getElementById('wz-reserve')?.value) || 30;
  if (wz.ac) wz.ac.burn_rate_gph = parseFloat(document.getElementById('wz-burn')?.value) || wz.ac.burn_rate_gph;
  nextStep();
}

function renderReviewStep() {
  const ac = wz.ac || {};
  return `<div class="card">
    <div class="card-hdr"><h2>Step 5 — Review &amp; Generate</h2><p>Confirm your plan details, then generate your briefing.</p></div>
    <div class="card-body">
      <table style="width:100%;font-size:.85rem;border-collapse:collapse">
        <tr><td style="padding:5px 8px;color:#666;width:140px">Aircraft</td><td style="padding:5px 8px;font-weight:700">${ac.n_number||'Guest'} · ${ac.make||''} ${ac.model||''}</td></tr>
        <tr style="background:#f8fafd"><td style="padding:5px 8px;color:#666">Departure</td><td style="padding:5px 8px;font-weight:700">${wz.dep}</td></tr>
        <tr><td style="padding:5px 8px;color:#666">Destination</td><td style="padding:5px 8px;font-weight:700">${wz.dest}</td></tr>
        ${wz.alt?`<tr style="background:#f8fafd"><td style="padding:5px 8px;color:#666">Alternate</td><td style="padding:5px 8px;font-weight:700">${wz.alt}</td></tr>`:''}
        <tr${wz.alt?'':' style="background:#f8fafd"'}><td style="padding:5px 8px;color:#666">Depart at</td><td style="padding:5px 8px">${wz.depart_at||'Not specified'}</td></tr>
        <tr style="background:#f8fafd"><td style="padding:5px 8px;color:#666">Fuel onboard</td><td style="padding:5px 8px">${wz.fuel||'—'} gal · ${wz.reserve}-min reserve</td></tr>
      </table>
    </div>
    <div class="card-foot">
      <button class="btn btn-ghost" onclick="prevStep()">← Back</button>
      <button class="btn btn-generate" id="wz-generate" onclick="submitPlan('wizard')">Generate Briefing →</button>
    </div>
  </div>`;
}

function nextStep() { wz.step = Math.min(5, wz.step + 1); renderStep(); }
function prevStep() { wz.step = Math.max(1, wz.step - 1); renderStep(); }

// ── Quick Plan ──
function renderQuickPlan() {
  const area = document.getElementById('qp-aircraft-area');
  if (!area) return;
  if (!aircraft.length) {
    area.innerHTML = '<p style="color:#888;font-size:.85rem;margin-bottom:4px">No aircraft saved. <a href="/profile" style="color:#1f4e79">Add in profile</a> — or continue without (guest).</p>';
    return;
  }
  let sel = aircraft[0];
  area.innerHTML = `<div style="display:flex;gap:8px;flex-wrap:wrap">` +
    aircraft.map(a =>
      `<div class="ac-card" style="flex:0 0 auto;min-width:150px" id="qp-ac-${a.n_number}" onclick='qpSelectAC(${JSON.stringify(a)})'>
        <div class="ac-reg">${a.n_number}</div>
        <div class="ac-model">${a.make} ${a.model}</div>
      </div>`
    ).join('') + `</div>`;
  qpSelectAC(sel);

  const depChips = document.getElementById('qp-dep-chips');
  const destChips = document.getElementById('qp-dest-chips');
  if (depChips) depChips.innerHTML = airports.map(ap =>
    `<div class="chip" onclick="document.getElementById('qp-dep').value='${ap.ident}'">${ap.ident}</div>`).join('');
  if (destChips) destChips.innerHTML = airports.map(ap =>
    `<div class="chip" onclick="document.getElementById('qp-dest').value='${ap.ident}'">${ap.ident}</div>`).join('');
}

let qpAC = null;
function qpSelectAC(a) {
  qpAC = a;
  document.querySelectorAll('[id^=qp-ac-]').forEach(el => el.classList.remove('sel'));
  const el = document.getElementById('qp-ac-' + a.n_number);
  if (el) el.classList.add('sel');
  const fuelInp = document.getElementById('qp-fuel');
  if (fuelInp) { fuelInp.value = a.fuel_capacity_gal; fuelInp.max = a.fuel_capacity_gal; }
  const hint = document.getElementById('qp-fuel-hint');
  if (hint) hint.textContent = `Full tanks = ${a.fuel_capacity_gal} gal`;
}

// ── Submit ──
async function submitPlan(mode) {
  const btn = document.getElementById(mode === 'wizard' ? 'wz-generate' : 'qp-generate');
  if (btn) { btn.disabled = true; btn.textContent = 'Generating…'; }

  let ac, dep, dest, alt, depart_at, fuel_onboard, reserve_min;
  if (mode === 'wizard') {
    ac = wz.ac; dep = wz.dep; dest = wz.dest; alt = wz.alt;
    depart_at = wz.depart_at; fuel_onboard = wz.fuel; reserve_min = wz.reserve;
  } else {
    ac = qpAC;
    dep = (document.getElementById('qp-dep').value||'').toUpperCase().trim();
    dest = (document.getElementById('qp-dest').value||'').toUpperCase().trim();
    alt = (document.getElementById('qp-alt').value||'').toUpperCase().trim();
    depart_at = document.getElementById('qp-depart').value;
    fuel_onboard = parseFloat(document.getElementById('qp-fuel').value) || null;
    reserve_min = parseInt(document.getElementById('qp-reserve').value) || 30;
  }

  if (!dep || !dest) { alert('Enter departure and destination airports.'); if(btn){btn.disabled=false;btn.textContent='Generate Briefing →';} return; }

  const headers = { 'Content-Type': 'application/json' };
  if (tok) headers['Authorization'] = 'Bearer ' + tok;

  try {
    const resp = await fetch(API + '/api/me/plans', {
      method: 'POST',
      headers,
      body: JSON.stringify({ aircraft: ac, departure: dep, destination: dest, alternate: alt||null, depart_at, fuel_onboard, reserve_min })
    });
    if (!resp.ok) throw new Error('Server error ' + resp.status);
    const { id } = await resp.json();
    window.location.href = '/plan/' + id;
  } catch (e) {
    alert('Failed to generate plan: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = 'Generate Briefing →'; }
  }
}

// ── Tabs ──
function switchTab(id, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById(id).classList.add('active');
  if (id === 'quick') renderQuickPlan();
}

init();
</script>
</body>
</html>
```

- [ ] **Step 5.2: Verify file was created**

```bash
wc -l worker/ocl-api/planner.html
# Expected: ~300+ lines
```

- [ ] **Step 5.3: Commit**

```bash
git add worker/ocl-api/planner.html
git commit -m "feat: add planner.html VFR flight planner SPA"
```

---

## Task 6: plan-detail.html — Briefing Output

**Files:**
- Create: `worker/ocl-api/plan-detail.html`

This page reads the plan ID from `window.location.pathname`, fetches from `GET /api/plan/:id`, and renders the full briefing with print CSS.

- [ ] **Step 6.1: Create plan-detail.html**

Create `/home/node/workspace/openchecklists/openchecklists/worker/ocl-api/plan-detail.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PreFlight Briefing — OpenChecklists</title>
<style>
@media print{
  .no-print{display:none!important}
  body{background:#fff;font-size:10pt}
  .briefing{box-shadow:none;border-radius:0;max-width:100%}
  .airport-section{page-break-inside:avoid}
  .fuel-card{page-break-inside:avoid}
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#e8edf4;color:#1a1a2e;min-height:100vh}
/* Action bar */
.action-bar{background:#1f4e79;color:#fff;padding:.6rem 1.2rem;display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;position:sticky;top:0;z-index:50}
.ab-id{font-size:.78rem;opacity:.7;margin-right:auto}
.ab-id strong{opacity:1;font-size:.88rem}
.ab-btn{display:inline-flex;align-items:center;gap:4px;padding:6px 13px;border-radius:7px;font-size:.78rem;font-weight:700;cursor:pointer;border:none;font-family:inherit}
.ab-pdf{background:#e67e22;color:#fff}
.ab-email{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3)}
.ab-print{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3)}
.ab-refresh{background:rgba(255,255,255,.1);color:rgba(255,255,255,.8);border:1px solid rgba(255,255,255,.2);font-size:.72rem}
/* Briefing doc */
.briefing{max-width:780px;margin:1.5rem auto;background:#fff;border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,.1);overflow:hidden}
/* Banner */
.banner{background:linear-gradient(135deg,#1f4e79,#2980b9);color:#fff;padding:1.2rem 1.5rem}
.banner .route{font-size:1.7rem;font-weight:800;letter-spacing:-.02em;line-height:1;margin-bottom:.4rem}
.banner .meta{display:flex;gap:1.2rem;flex-wrap:wrap;margin-top:.5rem}
.banner .mi{font-size:.78rem;opacity:.85}
.banner .mi strong{display:block;font-size:.95rem;opacity:1;font-weight:700}
.badge{display:inline-block;font-size:.65rem;font-weight:800;padding:2px 8px;border-radius:8px;color:#fff;margin-left:6px;vertical-align:middle}
.vfr{background:#27ae60}.mvfr{background:#2980b9}.ifr{background:#c0392b}.lifr{background:#6c3483}
/* Airport section */
.apt-sec{border-bottom:2px solid #e8edf4;padding:1.1rem 1.5rem}
.apt-sec:last-of-type{border-bottom:none}
.apt-hdr{display:flex;gap:1rem;margin-bottom:.9rem;align-items:flex-start}
.apt-ident{font-size:1.8rem;font-weight:900;color:#1f4e79;line-height:1;letter-spacing:-.02em}
.apt-role{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#fff;padding:2px 8px;border-radius:8px;margin-top:3px;display:inline-block}
.dep{background:#1f4e79}.dest{background:#27ae60}.alt-role{background:#8e44ad}
.apt-name{font-size:1rem;font-weight:700}
.apt-sub{font-size:.78rem;color:#666;margin-top:2px;line-height:1.4}
.apt-phone{font-size:.78rem;color:#1f4e79;font-weight:600;margin-top:2px}
.apt-phone a{color:#1f4e79;text-decoration:none}
.data-grid{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}
.data-grid .full{grid-column:1/-1}
.db{background:#f8fafd;border:1px solid #e8edf4;border-radius:8px;padding:.7rem}
.dl{font-size:.62rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px}
.metar{font-family:monospace;font-size:.72rem;color:#333;background:#fff;padding:5px 7px;border:1px solid #e0e6f0;border-radius:5px;word-break:break-all;line-height:1.5;margin-bottom:4px}
.wx-sum{font-size:.78rem;color:#444;line-height:1.5}
.taf-hdr{font-size:.62rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.06em;margin:.5rem 0 3px;border-top:1px solid #e8edf4;padding-top:.4rem}
.taf-raw{font-family:monospace;font-size:.68rem;color:#555;line-height:1.5}
.notam-list{list-style:none}
.notam-item{border-left:3px solid #e0e6f0;padding:3px 8px;margin-bottom:4px;font-size:.75rem;color:#444;line-height:1.4}
.notam-item.warn{border-color:#e67e22}
.notam-hdr{font-size:.65rem;color:#888;margin-bottom:1px}
.no-notams{font-size:.78rem;color:#27ae60;font-weight:600}
.freq-tbl{width:100%;border-collapse:collapse;font-size:.75rem}
.freq-tbl th{text-align:left;color:#888;font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;padding:2px 5px 4px;border-bottom:1px solid #e8edf4}
.freq-tbl td{padding:3px 5px;border-bottom:1px solid #f0f4f9}
.freq-tbl tr:last-child td{border-bottom:none}
.freq-mhz{font-weight:700;color:#1f4e79;font-size:.82rem}
.freq-ctaf{color:#e67e22;font-weight:700}
.rwy-chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:4px}
.rwy-chip{background:#1f4e79;color:#fff;border-radius:6px;padding:3px 9px;font-size:.72rem;font-weight:700}
.rwy-chip.closed{background:#e67e22}
.rwy-detail{font-size:.7rem;color:#666;line-height:1.5}
/* Fuel card */
.fuel-card{border-top:2px solid #e8edf4;background:#f8fafd;padding:1.1rem 1.5rem}
.fuel-card h3{font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.07em;margin-bottom:.7rem}
.fuel-tbl{width:100%;border-collapse:collapse}
.fuel-tbl td{padding:4px 7px;font-size:.82rem;border-bottom:1px solid #e8edf4}
.fuel-tbl td:first-child{color:#555}
.fuel-tbl td:last-child{font-weight:700;text-align:right}
.fuel-tbl tr.total td{font-weight:800;color:#1f4e79;border-top:2px solid #dde3ee}
.fuel-ok{color:#27ae60!important}.fuel-warn{color:#c0392b!important}
.end-bar{height:11px;background:#e8edf4;border-radius:8px;overflow:hidden;display:flex;margin:.6rem 0 .3rem}
.bar-fl{background:#1f4e79}.bar-rv{background:#f39c12}.bar-ex{background:#27ae60}
.bar-leg{display:flex;gap:10px;font-size:.65rem;color:#666}
.bar-leg span::before{content:"■ "}
.bl1::before{color:#1f4e79}.bl2::before{color:#f39c12}.bl3::before{color:#27ae60}
/* Footer */
.brief-foot{background:#1f4e79;color:rgba(255,255,255,.65);font-size:.7rem;padding:.7rem 1.5rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.4rem}
.brief-foot strong{color:#fff}.brief-foot a{color:rgba(255,255,255,.75)}
/* Email modal */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:#fff;border-radius:12px;padding:1.5rem;max-width:400px;width:90%;box-shadow:0 8px 40px rgba(0,0,0,.2)}
.modal h3{font-size:1rem;font-weight:700;color:#1f4e79;margin-bottom:.5rem}
.modal p{font-size:.85rem;color:#555;margin-bottom:.8rem}
.modal input{width:100%;border:1.5px solid #dde3ee;border-radius:7px;padding:9px 12px;font-size:.88rem;font-family:inherit;margin-bottom:.8rem}
.modal input:focus{outline:none;border-color:#1f4e79}
.modal-btns{display:flex;gap:.5rem;justify-content:flex-end}
.m-cancel{background:transparent;border:1.5px solid #dde3ee;color:#555;padding:8px 16px;border-radius:7px;font-size:.82rem;cursor:pointer}
.m-send{background:#1f4e79;color:#fff;border:none;padding:8px 16px;border-radius:7px;font-size:.82rem;font-weight:700;cursor:pointer}
.error{color:#c0392b;font-size:.78rem;margin-top:.3rem}
@media(max-width:600px){.data-grid{grid-template-columns:1fr}.banner .meta{gap:.7rem}}
</style>
</head>
<body>

<!-- Email modal -->
<div class="modal-overlay" id="email-modal">
  <div class="modal">
    <h3>Email your briefing</h3>
    <p>We'll send the full briefing to your email. If you're new, this creates your free account.</p>
    <input type="email" id="email-input" placeholder="your@email.com">
    <div class="error" id="email-error" style="display:none"></div>
    <div class="modal-btns">
      <button class="m-cancel" onclick="closeEmail()">Cancel</button>
      <button class="m-send" id="email-send-btn" onclick="sendEmail()">Send Briefing</button>
    </div>
  </div>
</div>

<!-- Action bar -->
<div class="action-bar no-print">
  <div class="ab-id"><strong id="ab-route">Loading…</strong> · <span id="ab-id"></span></div>
  <button class="ab-btn ab-pdf" onclick="window.print()">⬇ Download PDF</button>
  <button class="ab-btn ab-email" onclick="openEmail()">✉ Email to Me</button>
  <button class="ab-btn ab-print" onclick="window.print()">🖨 Print</button>
  <button class="ab-btn ab-refresh" id="refresh-btn" onclick="refreshData()">🔄 Refresh <span id="data-age"></span></button>
</div>

<div class="briefing" id="briefing">
  <div style="padding:2rem;text-align:center;color:#888" id="loading-msg">Loading briefing…</div>
</div>

<script>
const API = 'https://app.openchecklists.net';
let planId = window.location.pathname.split('/').filter(Boolean).pop();
let planData = null;

async function load(refresh) {
  const url = API.replace('app.', '') + '/api/plan/' + planId + (refresh ? '?refresh=1' : '');
  // Note: /api/plan/:id is served by the ocl-api worker at openchecklists.net/api/plan/
  // Actually the worker route is at app.openchecklists.net per the wrangler.toml routes
  // Check which domain it's on — use the correct one
  const planUrl = 'https://app.openchecklists.net/api/plan/' + planId + (refresh ? '?refresh=1' : '');
  try {
    const resp = await fetch(planUrl);
    if (!resp.ok) throw new Error('Plan not found');
    planData = await resp.json();
    render(planData);
  } catch (e) {
    document.getElementById('briefing').innerHTML = `<div style="padding:2rem;text-align:center;color:#c0392b">
      <h2>Plan not found</h2><p>The plan ID "${planId}" doesn't exist or has expired.</p>
      <a href="/planner" style="color:#1f4e79;margin-top:1rem;display:inline-block">← Plan a new flight</a>
    </div>`;
  }
}

function wxBadge(metar) {
  if (!metar) return '';
  const ovc = metar.match(/(?:OVC|BKN)(\d{3})/)?.[1];
  const ceil = ovc ? parseInt(ovc) * 100 : 99999;
  const vis = parseInt((metar.match(/\s(\d+)SM/) || [])[1] || '10');
  let cat = 'vfr', lbl = 'VFR';
  if (ceil < 500 || vis < 1) { cat = 'lifr'; lbl = 'LIFR'; }
  else if (ceil < 1000 || vis < 3) { cat = 'ifr'; lbl = 'IFR'; }
  else if (ceil < 3000 || vis < 5) { cat = 'mvfr'; lbl = 'MVFR'; }
  return `<span class="badge ${cat}">${lbl}</span>`;
}

function wxSummary(metar) {
  if (!metar) return 'No METAR available for this airport.';
  // Parse key fields
  const wind = metar.match(/(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT/);
  const vis = metar.match(/\s(\d+)SM/);
  const sky = metar.match(/(FEW|SCT|BKN|OVC)(\d{3})/g);
  const temp = metar.match(/(\d{2})\/(\d{2})/);
  const alt = metar.match(/A(\d{4})/);
  let parts = [];
  if (wind) parts.push(`Wind ${wind[1]}° at ${parseInt(wind[2])} kt${wind[3]?' gust '+parseInt(wind[3])+' kt':''}`);
  if (vis) parts.push(`Vis ${vis[1]} SM`);
  if (sky?.length) parts.push(sky.map(s => {
    const [,cov,hft] = s.match(/(FEW|SCT|BKN|OVC)(\d{3})/);
    const h = parseInt(hft)*100;
    return `${cov.charAt(0)+cov.slice(1).toLowerCase()} ${h.toLocaleString()} ft`;
  }).join(', '));
  if (temp) parts.push(`Temp ${temp[1]}°C / Dew ${temp[2]}°C`);
  if (alt) parts.push(`Alt ${(parseInt(alt[1])/100).toFixed(2)} inHg`);
  return parts.join(' · ') || metar;
}

function formatNotams(notams) {
  if (!notams || !notams.notams?.length) return '<div class="no-notams">✓ No active NOTAMs</div>';
  return '<ul class="notam-list">' + notams.notams.map(n => {
    const isWarn = n.text && /RWY|CLSD|UNSERVICEABLE|OBST/i.test(n.text);
    return `<li class="notam-item${isWarn?' warn':''}">
      <div class="notam-hdr">${n.effective||''} – ${n.expiration||''}</div>
      ${n.text||''}
    </li>`;
  }).join('') + '</ul>';
}

function formatFreqs(apt, snap) {
  // Frequencies are in the static airport data, not the snapshot
  // Show what's available from NASR data baked into the briefing snapshot
  const freqs = snap?.frequencies?.[apt] || [];
  if (!freqs.length) return '<p style="font-size:.75rem;color:#888">See airport page for frequencies.</p>';
  const PRIORITY = ['CTAF','UNICOM','TOWER','GND','ATIS','AWOS','ASOS'];
  const sorted = [...freqs].sort((a,b) => {
    const ai = PRIORITY.findIndex(p => (a.use||'').toUpperCase().includes(p));
    const bi = PRIORITY.findIndex(p => (b.use||'').toUpperCase().includes(p));
    return (ai<0?99:ai)-(bi<0?99:bi);
  });
  return `<table class="freq-tbl">
    <thead><tr><th>MHz</th><th>Use</th></tr></thead>
    <tbody>${sorted.slice(0,6).map(f => {
      const isCtaf = /CTAF|UNICOM/i.test(f.use||'');
      return `<tr><td class="freq-mhz${isCtaf?' freq-ctaf':''}">${f.frequency||''}</td><td class="${isCtaf?'freq-ctaf':''}">${f.use||''}</td></tr>`;
    }).join('')}</tbody>
  </table>`;
}

function fuelBar(onboard, burnGph, etMin, reserveMin) {
  const total = onboard / burnGph * 60; // minutes
  const flPct = Math.min(100, (etMin / total) * 100);
  const rvPct = Math.min(100-flPct, (reserveMin / total) * 100);
  const exPct = Math.max(0, 100-flPct-rvPct);
  return `<div class="end-bar">
    <div class="bar-fl" style="width:${flPct}%"></div>
    <div class="bar-rv" style="width:${rvPct}%"></div>
    <div class="bar-ex" style="width:${exPct}%"></div>
  </div>
  <div class="bar-leg">
    <span class="bl1">Flight est.</span>
    <span class="bl2">Reserve (${reserveMin} min)</span>
    <span class="bl3">Extra margin</span>
  </div>`;
}

function renderAptSection(aptIdent, role, snap) {
  const wx = snap.weather?.[aptIdent];
  const notams = snap.notams?.[aptIdent];
  const metar = wx?.metar || null;
  const taf = wx?.taf || null;
  const roleCls = role === 'Departure' ? 'dep' : role === 'Destination' ? 'dest' : 'alt-role';
  const isAlt = role === 'Alternate';

  return `<div class="apt-sec">
    <div class="apt-hdr">
      <div>
        <div class="apt-ident" style="${isAlt?'font-size:1.4rem':''}">${aptIdent}</div>
        <span class="apt-role ${roleCls}">${role}</span>
      </div>
      <div style="flex:1">
        <div class="apt-name">See <a href="/airport/${aptIdent.toLowerCase()}" style="color:#1f4e79">${aptIdent} airport page</a> for full details</div>
        <div class="apt-sub">Frequencies, runway diagrams, and navigation aids on the airport page.</div>
      </div>
    </div>
    <div class="data-grid">
      <div class="db full">
        <div class="dl">Weather ${wxBadge(metar)}</div>
        ${metar ? `<div class="metar">${metar}</div><div class="wx-sum">${wxSummary(metar)}</div>` : '<p style="font-size:.78rem;color:#888">No METAR available for this airport.</p>'}
        ${taf && !isAlt ? `<div class="taf-hdr">TAF</div><div class="taf-raw">${taf.replace(/\n/g,'<br>')}</div>` : ''}
      </div>
      <div class="db">
        <div class="dl">NOTAMs</div>
        ${formatNotams(notams)}
      </div>
      <div class="db">
        <div class="dl">Frequencies</div>
        ${formatFreqs(aptIdent, snap)}
        <div style="margin-top:6px"><a href="/airport/${aptIdent.toLowerCase()}" style="font-size:.7rem;color:#1f4e79">Full frequency list →</a></div>
      </div>
    </div>
  </div>`;
}

function render(plan) {
  const snap = plan.snapshot || {};
  const ac = plan.aircraft || {};
  const dep = plan.departure, dest = plan.destination, alt = plan.alternate;
  const route = `${dep} → ${dest}${alt ? ` (alt: ${alt})` : ''}`;

  document.title = `PreFlight — ${dep} → ${dest} — OpenChecklists`;
  document.getElementById('ab-route').textContent = route;
  document.getElementById('ab-id').textContent = 'Plan #' + plan.id;

  // Data age
  const genAt = snap.generated_at || plan.created_at;
  if (genAt) {
    const mins = Math.round((Date.now() - new Date(genAt).getTime()) / 60000);
    document.getElementById('data-age').textContent = `(data ${mins < 60 ? mins + 'min' : Math.round(mins/60) + 'h'} old)`;
  }

  // Fuel math
  const fuelOnboard = plan.fuel_onboard || ac.fuel_capacity_gal || 0;
  const burnGph = ac.burn_rate_gph || 8.5;
  const cruise = ac.cruise_speed_ktas || 110;
  const reserveMin = plan.reserve_min || 30;
  const reserveGal = (reserveMin / 60) * burnGph;
  const etMin = 0; // Can't calc without coords — show N/A
  const margin = fuelOnboard - reserveGal;
  const enduranceMin = (fuelOnboard / burnGph) * 60;
  const endH = Math.floor(enduranceMin/60), endM = Math.round(enduranceMin%60);
  const marginOk = margin > (60/60*burnGph);

  const depAt = plan.depart_at ? new Date(plan.depart_at).toLocaleString() : 'Today';

  const html = `
    <div class="banner">
      <div class="route">${dep} → ${dest}${alt ? ` <span style="font-size:1rem;opacity:.75;font-weight:600">(alt: ${alt})</span>` : ''}</div>
      <div class="meta">
        <div class="mi"><strong>${ac.n_number||'Guest'}</strong>Aircraft</div>
        <div class="mi"><strong>${ac.make||''} ${ac.model||''}</strong>Type</div>
        <div class="mi"><strong>${depAt}</strong>Departure</div>
        <div class="mi"><strong>${fuelOnboard} gal onboard</strong>Fuel</div>
      </div>
    </div>
    ${renderAptSection(dep, 'Departure', snap)}
    ${renderAptSection(dest, 'Destination', snap)}
    ${alt ? renderAptSection(alt, 'Alternate', snap) : ''}
    <div class="fuel-card">
      <h3>⛽ Fuel Planning — ${ac.n_number||''} ${ac.make||''} ${ac.model||''}</h3>
      <table class="fuel-tbl">
        <tr><td>Fuel onboard</td><td>${fuelOnboard} gal</td></tr>
        <tr><td>Burn rate</td><td>${burnGph} GPH</td></tr>
        <tr><td>Reserve required (${reserveMin} min)</td><td>${reserveGal.toFixed(1)} gal</td></tr>
        <tr class="total"><td>Margin above reserve</td><td class="${marginOk?'fuel-ok':'fuel-warn'}">${margin.toFixed(1)} gal ${marginOk?'✓':'⚠'}</td></tr>
        <tr><td>Total endurance</td><td>${endH} hr ${endM} min</td></tr>
      </table>
      ${fuelBar(fuelOnboard, burnGph, etMin, reserveMin)}
    </div>
    <div class="brief-foot">
      <div><strong>OpenChecklists.net</strong> · Plan #${plan.id} · Generated ${genAt ? new Date(genAt).toLocaleString() : 'now'}</div>
      <div>Live refresh: <a href="https://openchecklists.net/plan/${plan.id}">openchecklists.net/plan/${plan.id}</a></div>
    </div>
  `;
  document.getElementById('briefing').innerHTML = html;
}

// ── Email ──
function openEmail() {
  const tok = sessionStorage.getItem('ocl:token');
  if (tok) {
    // Try to pre-fill from profile
    fetch('https://app.openchecklists.net/api/me', { headers: { Authorization: 'Bearer ' + tok } })
      .then(r => r.json()).then(d => { if (d.email) document.getElementById('email-input').value = d.email; }).catch(() => {});
  }
  document.getElementById('email-modal').classList.add('open');
  setTimeout(() => document.getElementById('email-input').focus(), 100);
}
function closeEmail() { document.getElementById('email-modal').classList.remove('open'); }
async function sendEmail() {
  const email = document.getElementById('email-input').value.trim();
  const errEl = document.getElementById('email-error');
  errEl.style.display = 'none';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { errEl.textContent = 'Enter a valid email address.'; errEl.style.display='block'; return; }
  const btn = document.getElementById('email-send-btn');
  btn.disabled = true; btn.textContent = 'Sending…';
  try {
    const resp = await fetch('https://app.openchecklists.net/api/plan/' + planId + '/email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!resp.ok) throw new Error('Send failed');
    btn.textContent = '✓ Sent!';
    setTimeout(closeEmail, 1500);
  } catch (e) {
    errEl.textContent = 'Failed to send. Try again.'; errEl.style.display = 'block';
    btn.disabled = false; btn.textContent = 'Send Briefing';
  }
}

// ── Refresh ──
async function refreshData() {
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true; btn.textContent = '🔄 Refreshing…';
  await load(true);
  btn.disabled = false; btn.textContent = '🔄 Refresh';
}

load(false);
</script>
</body>
</html>
```

- [ ] **Step 6.2: Commit**

```bash
git add worker/ocl-api/plan-detail.html
git commit -m "feat: add plan-detail.html briefing output page"
```

---

## Task 7: Build Integration

**Files:**
- Modify: `tools/build_site.py`

Four changes: (1) add "Plan a Flight" to nav, (2) copy planner.html to build, (3) copy plan-detail.html to build/plan/index.html, (4) add `_redirects` for SPA routing, (5) add "Plan from here" button to airport pages.

- [ ] **Step 7.1: Add "Plan a Flight" nav item**

In `tools/build_site.py`, find the nav block (around line 266-275). It looks like:
```python
<a href="{rel}airports.html">Airports &amp; weather</a>
```

Add after the airports link:
```python
<a href="{rel}planner.html">Plan a Flight</a>
```

The exact edit: find the string `Airports &amp; weather</a>` and append `\n        <a href="{rel}planner.html">Plan a Flight</a>` after it. Use `sed` or edit the file directly.

```bash
# Verify the current nav block
grep -n "Plan a Flight\|airports.html\|Airports" tools/build_site.py | head -10
```

Then add the line in the correct position in `build_site.py`.

- [ ] **Step 7.2: Copy planner.html and plan-detail.html during build**

Find the section in `build_site.py` where `profile.html` and `auth-callback.html` are copied (around line 1443-1454). Add after the auth-callback copy:

```python
    planner_src = ocl_api / "planner.html"
    if planner_src.exists():
        import shutil as _sh
        _sh.copy2(planner_src, args.out / "planner.html")
        artifacts.append(args.out / "planner.html")
    plan_src = ocl_api / "plan-detail.html"
    if plan_src.exists():
        import shutil as _sh
        plan_dir = args.out / "plan"
        plan_dir.mkdir(exist_ok=True)
        _sh.copy2(plan_src, plan_dir / "index.html")
        artifacts.append(plan_dir / "index.html")
```

- [ ] **Step 7.3: Add _redirects for SPA routing**

In `build_site.py`, after the `_headers` or at the end of the build output section, write the redirects file:

```python
    # SPA redirect: /plan/* → /plan/index.html so plan IDs work as URLs
    (args.out / "_redirects").write_text("/plan/* /plan/index.html 200\n", encoding="utf-8")
```

- [ ] **Step 7.4: Add "Plan from here" button to airport pages**

In `build_site.py`, find the `render_airport_page()` function. Locate where the quick-facts section ends and the runways section begins (search for `class="data-section"` near the runway diagram). Add the button after the quick-facts grid:

```python
# After the quick-facts cards, add a plan CTA
plan_cta = f'''<div style="margin-top:1rem">
  <a href="/planner.html?dep={ident}" class="cta" style="font-size:.88rem;padding:.6rem 1.1rem;display:inline-flex;gap:.4rem;align-items:center">
    ✈ Plan a flight from {ident} →
  </a>
</div>'''
```

Embed `plan_cta` in the rendered HTML string just before the runway section div.

- [ ] **Step 7.5: Handle `?dep=` pre-fill in planner.html**

In `worker/ocl-api/planner.html`, at the top of the `init()` function, add:

```javascript
// Pre-fill departure from URL param (set by airport pages)
const urlParams = new URLSearchParams(window.location.search);
const depParam = urlParams.get('dep');
if (depParam) wz.dep = depParam.toUpperCase();
```

- [ ] **Step 7.6: Rebuild and verify**

```bash
python3 tools/build_site.py --base-url https://openchecklists.net 2>&1 | tail -5
# Verify outputs
ls build/site/planner.html build/site/plan/index.html build/site/_redirects
cat build/site/_redirects
# Expected: /plan/* /plan/index.html 200
grep -c "Plan a Flight" build/site/index.html build/site/airports.html
# Expected: 1 in each
grep -c "Plan a flight from" build/site/airport/kbtl/index.html
# Expected: 1
```

- [ ] **Step 7.7: Commit**

```bash
git add tools/build_site.py worker/ocl-api/planner.html
git commit -m "feat: add Plan a Flight nav + copy planner/plan pages + airport CTA + _redirects"
```

---

## Task 8: Deploy Everything

- [ ] **Step 8.1: Deploy ocl-api worker**

```bash
cd worker/ocl-api
CLOUDFLARE_API_KEY=$(bw get item "d7d06d7d-5509-4520-906a-df7039d32013" | jq -r '.fields[0].value') \
CLOUDFLARE_EMAIL="openchecklists@keylinkit.net" \
  npx wrangler deploy 2>&1 | tail -8
```

Expected: `✨ Successfully deployed`

- [ ] **Step 8.2: Set OCL_MAIL_SECRET as worker secret (if not done in Task 4)**

```bash
MAIL_SECRET=$(bw get password "ocl-mail-relay-secret" 2>/dev/null)
echo "$MAIL_SECRET" | CLOUDFLARE_API_KEY=$(bw get item "d7d06d7d-5509-4520-906a-df7039d32013" | jq -r '.fields[0].value') \
  CLOUDFLARE_EMAIL="openchecklists@keylinkit.net" \
  npx wrangler --config worker/ocl-api/wrangler.toml secret put OCL_MAIL_SECRET
```

- [ ] **Step 8.3: Deploy CF Pages**

```bash
cd /home/node/workspace/openchecklists/openchecklists
CLOUDFLARE_API_KEY=$(bw get item "d7d06d7d-5509-4520-906a-df7039d32013" | jq -r '.fields[0].value') \
CLOUDFLARE_EMAIL="openchecklists@keylinkit.net" \
CLOUDFLARE_ACCOUNT_ID="978dcaac35dcbe8c7c7c9b200c3db416" \
  node worker/node_modules/.bin/wrangler pages deploy build/site \
    --project-name openchecklists-net --branch main 2>&1 | tail -5
```

Expected: `✨ Deployment complete!`

- [ ] **Step 8.4: Push to GitHub**

```bash
git push origin main 2>&1 | tail -3
```

- [ ] **Step 8.5: Smoke test end-to-end**

```bash
# 1. Planner page loads
curl -s -o /dev/null -w "%{http_code}" https://openchecklists.net/planner.html
# Expected: 200

# 2. Plan detail SPA loads for any ID
curl -s -o /dev/null -w "%{http_code}" https://openchecklists.net/plan/test-123
# Expected: 200 (serves plan/index.html via _redirects)

# 3. Save a guest plan
curl -s -X POST https://app.openchecklists.net/api/me/plans \
  -H "Content-Type: application/json" \
  -d '{"departure":"KBTL","destination":"KGRR","aircraft":{"n_number":"N12345","make":"Cessna","model":"172S","fuel_capacity_gal":35,"burn_rate_gph":8.5,"cruise_speed_ktas":110},"fuel_onboard":35,"reserve_min":30}' | jq .
# Expected: {"id":"ocl-XXXXXX"}

# 4. Read the plan back
PLAN_ID=$(curl -s -X POST https://app.openchecklists.net/api/me/plans \
  -H "Content-Type: application/json" \
  -d '{"departure":"KBTL","destination":"KGRR","aircraft":{},"fuel_onboard":35}' | jq -r '.id')
echo "Plan ID: $PLAN_ID"
curl -s "https://app.openchecklists.net/api/plan/$PLAN_ID" | jq '{id,departure,destination}'
# Expected: {id: "ocl-...", departure: "KBTL", destination: "KGRR"}

# 5. Email the plan
MAIL_SECRET=$(bw get password "ocl-mail-relay-secret" 2>/dev/null)
curl -s -X POST "https://app.openchecklists.net/api/plan/$PLAN_ID/email" \
  -H "Content-Type: application/json" \
  -d '{"email":"allen@keylinkit.com"}' | jq .
# Expected: {"ok":true}
# Check allen@keylinkit.com inbox

# 6. Airport page has plan CTA
curl -s https://openchecklists.net/airport/kbtl/ | grep "Plan a flight from"
# Expected: one match

# 7. Nav has Plan a Flight
curl -s https://openchecklists.net/ | grep "Plan a Flight"
# Expected: one match
```

- [ ] **Step 8.6: Final commit and tag**

```bash
git add -A
git commit -m "feat: PreFlight Plan Generator — complete VFR planner with briefing, PDF, email

- D1 flight_plans table with data aggregation on save
- GET/POST /api/me/plans, GET /api/plan/:id, POST /api/plan/:id/email
- PHP mail relay on kw4, DKIM/SPF verified
- planner.html: 5-step wizard + quick plan SPA
- plan-detail.html: briefing output with print-to-PDF + email modal
- Plan a Flight nav item + airport page CTAs
- CF Pages _redirects for /plan/* SPA routing"
git push origin main
```

---

## Self-Review Checklist

- ✅ D1 `flight_plans` table — Task 1
- ✅ `GET /api/me/plans` (authenticated list) — Task 2
- ✅ `POST /api/me/plans` (guest + auth save, data aggregation) — Task 2
- ✅ `GET /api/plan/:id` (public read + optional refresh) — Task 3
- ✅ `POST /api/plan/:id/email` (SMTP via kw4 PHP relay) — Task 4
- ✅ `planner.html` (wizard 5 steps + quick plan + ?dep= prefill) — Task 5
- ✅ `plan-detail.html` (briefing, fuel bar, print, email modal) — Task 6
- ✅ "Plan a Flight" nav item — Task 7
- ✅ Airport pages "Plan from here" button — Task 7
- ✅ `_redirects` for `/plan/*` SPA routing — Task 7
- ✅ Worker deploy + Pages deploy + smoke tests — Task 8
