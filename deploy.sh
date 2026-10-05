#!/usr/bin/env bash
# Reproducible build + deploy for openchecklists.net.
#
# Deploys across two things in one Cloudflare account (978dcaac):
#   - the ocl-api Worker  (app.openchecklists.net/*)   — D1-backed API
#   - the Pages site      (openchecklists.net)          — static build/site/
#
# Credentials: uses a Cloudflare Global API Key via env vars. Export these first
# (the key lives in Vaultwarden item "Cloudflare openchecklists.net", field
# "Global API Key", account openchecklists@keylinkit.net):
#
#   export CLOUDFLARE_EMAIL="openchecklists@keylinkit.net"
#   export CLOUDFLARE_API_KEY="<global api key>"
#
# Usage:
#   ./deploy.sh            # build + deploy Pages + Worker
#   ./deploy.sh pages      # build + deploy Pages only
#   ./deploy.sh worker     # deploy Worker only
#
# Optional env: ADSENSE_PUB=pub-XXXXXXXXXXXXXXXX turns on ads.txt + AdSense on
# ad-eligible pages; PAGES_BRANCH=preview deploys a preview instead of production.
set -euo pipefail

ACCOUNT_ID="978dcaac35dcbe8c7c7c9b200c3db416"
PAGES_PROJECT="openchecklists-net"
BASE_URL="https://openchecklists.net"
WX_PROXY="https://ocl-weather.openchecklists.workers.dev"
ROOT="$(cd "$(dirname "$0")" && pwd)"
WHAT="${1:-all}"

if [[ -z "${CLOUDFLARE_EMAIL:-}" || -z "${CLOUDFLARE_API_KEY:-}" ]]; then
  echo "ERROR: export CLOUDFLARE_EMAIL and CLOUDFLARE_API_KEY first (see header)." >&2
  exit 1
fi
export CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID"

build_site() {
  echo "▶ building static site…"
  # data/ is gitignored; without it the build silently ships a site with no
  # airports, library or training data. Refuse rather than degrade production.
  if [[ ! -f "$ROOT/data/airports/index.json" ]]; then
    echo "ERROR: data/airports/index.json missing — regenerate data/ first (see README)." >&2
    exit 1
  fi
  python3 "$ROOT/tools/build_site.py" --base-url "$BASE_URL" --wx-proxy "$WX_PROXY" \
    ${ADSENSE_PUB:+--adsense-pub "$ADSENSE_PUB"}
  local n
  n="$(find "$ROOT/build/site" -type f | wc -l | tr -d ' ')"
  echo "  build/site: $n files"
  if (( n >= 20000 )); then
    echo "ERROR: $n files >= Cloudflare Pages' 20,000-file limit. Aborting." >&2
    exit 1
  fi
}

deploy_pages() {
  build_site
  echo "▶ deploying Pages ($PAGES_PROJECT)…"
  # Run from the repo root: wrangler picks up ./functions (the /airport/<ID>
  # server renderer) relative to the working directory.
  ( cd "$ROOT" && npx --yes wrangler@latest pages deploy build/site \
    --project-name="$PAGES_PROJECT" --branch="${PAGES_BRANCH:-main}" )
}

deploy_worker() {
  echo "▶ deploying Worker (ocl-api)…"
  # schema.sql is idempotent (CREATE ... IF NOT EXISTS); apply it so new tables
  # (e.g. rate_limits) exist before the new code that uses them goes live.
  python3 "$ROOT/tools/quiz_answers.py"
  ( cd "$ROOT/worker/ocl-api" && npx --yes wrangler@latest d1 execute openchecklists-users --remote --file=schema.sql --yes \
      && npx --yes wrangler@latest deploy )
}

case "$WHAT" in
  pages)  deploy_pages ;;
  worker) deploy_worker ;;
  all)    deploy_worker; deploy_pages ;;
  *) echo "usage: ./deploy.sh [all|pages|worker]" >&2; exit 2 ;;
esac
echo "✓ done."
