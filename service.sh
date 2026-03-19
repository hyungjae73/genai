#!/bin/bash
# =============================================================================
# Payment Compliance Monitor - Service Management Script
# =============================================================================
# Usage:
#   ./service.sh start     - Start all services (Docker + Frontend)
#   ./service.sh stop      - Stop all services
#   ./service.sh restart   - Restart all services
#   ./service.sh status    - Show service status
#   ./service.sh logs [service]  - Show logs (api, worker, beat, db, redis, frontend)
#   ./service.sh migrate   - Run database migrations
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

FRONTEND_PID_FILE="logs/frontend.pid"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ensure_logs_dir() {
  mkdir -p logs
}

stop_local_postgres() {
  # Stop homebrew PostgreSQL if running on port 5432 to avoid conflicts
  if lsof -i :5432 2>/dev/null | grep -q postgres; then
    local pg_pid
    pg_pid=$(lsof -ti :5432 -sTCP:LISTEN 2>/dev/null | head -1)
    if [ -n "$pg_pid" ]; then
      local pg_cmd
      pg_cmd=$(ps -p "$pg_pid" -o command= 2>/dev/null || true)
      if echo "$pg_cmd" | grep -q homebrew; then
        echo -e "${YELLOW}⚠  Stopping local PostgreSQL (homebrew) to free port 5432...${NC}"
        brew services stop postgresql@15 2>/dev/null || true
        brew services stop postgresql@18 2>/dev/null || true
        brew services stop postgresql 2>/dev/null || true
        sleep 2
      fi
    fi
  fi
}
