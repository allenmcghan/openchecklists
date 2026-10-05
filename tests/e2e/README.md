# End-to-end tests

Real-browser and API checks for openchecklists.net. Nothing here sends email or
touches production data: email endpoints are stubbed in the browser tests, and the
API tests run against a local `wrangler dev` worker with a local D1.

| Script | What it does |
| --- | --- |
| `login.py [BASE]` | Signs in as the **OCL Tester** account (vault item `7205bfb7`: password + TOTP via `lab-totp`) and writes the access token to `/tmp/ocl-e2e/token` |
| `api_test.sh` | 42 API checks (auth, CORS, email gating, ownership, rate limits) against `B=http://127.0.0.1:8787` |
| `fakeidp.py` | Local JWKS/issuer on :9911 that mints tokens with bad `aud`/`iss`/`exp`/`alg` for JWT-validation tests |
| `crawl.py [BASE]` | Every page type, desktop + mobile: console errors, failed requests, overflow, stuck loaders |
| `features.py [BASE]` | Exercises features: catalogue, checklist ticks/downloads/email, editor fork, airports + live data, planner → plan briefing → PDF, profile, search, training, service worker |

Typical local run:

```sh
python3 tools/build_site.py --base-url https://openchecklists.net --out /tmp/ocl-site
(cd worker/ocl-api && npx wrangler d1 execute openchecklists-users --local --file=schema.sql \
   && npx wrangler dev --local --port 8787) &
npx wrangler pages dev /tmp/ocl-site --port 8790 &      # from the repo root so functions/ is active
mkdir -p /tmp/ocl-e2e && python3 tests/e2e/login.py      # real token, 12 h
bash tests/e2e/api_test.sh
API_LOCAL=http://127.0.0.1:8787 python3 tests/e2e/features.py http://127.0.0.1:8790
```
