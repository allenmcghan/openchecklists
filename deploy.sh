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
  python3 "$ROOT/tools/build_site.py" --base-url "$BASE_URL" --wx-proxy "$WX_PROXY"
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
  npx --yes wrangler@latest pages deploy "$ROOT/build/site" \
    --project-name="$PAGES_PROJECT" --branch=main
}

deploy_worker() {
  echo "▶ deploying Worker (ocl-api)…"
  ( cd "$ROOT/worker/ocl-api" && npx --yes wrangler@latest deploy )
}

case "$WHAT" in
  pages)  deploy_pages ;;
  worker) deploy_worker ;;
  all)    deploy_worker; deploy_pages ;;
  *) echo "usage: ./deploy.sh [all|pages|worker]" >&2; exit 2 ;;
esac
echo "✓ done."
