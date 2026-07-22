#!/usr/bin/env bash
# =============================================================================
# build_dashboards.sh — Build & deploy the NHIOTPipeline Dashboard
# =============================================================================
# Usage:
#   ./build_dashboards.sh        # Rebuild and run the dashboard in the terminal
#   ./build_dashboards.sh --stop # Stop and remove the dashboard container
# =============================================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
COMPOSE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/docker-compose.yml"
SERVICE="dashboard"
CONTAINER="nhiot_dashboard"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Argument parsing ──────────────────────────────────────────────────────────
STOP_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --stop)  STOP_ONLY=true ;;
    *)
      error "Unknown argument: $arg"
      echo "Usage: $0 [--stop]"
      exit 1
      ;;
  esac
done

# ── Stop-only mode ────────────────────────────────────────────────────────────
if $STOP_ONLY; then
  info "Stopping and removing container: ${CONTAINER}"
  docker compose -f "$COMPOSE_FILE" stop "$SERVICE"
  docker compose -f "$COMPOSE_FILE" rm -f "$SERVICE"
  info "Done."
  exit 0
fi

# ── Build & deploy ────────────────────────────────────────────────────────────
info "Building Docker image for service: ${SERVICE}"
docker compose -f "$COMPOSE_FILE" build --no-cache "$SERVICE"

info "Stopping existing container (if running)..."
docker compose -f "$COMPOSE_FILE" stop "$SERVICE" 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" rm -f "$SERVICE" 2>/dev/null || true

info "Starting dashboard (Ctrl+C to stop)..."
info "Dashboard → http://localhost:8080"
docker compose -f "$COMPOSE_FILE" up "$SERVICE"
