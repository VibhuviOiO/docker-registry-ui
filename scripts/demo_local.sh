#!/usr/bin/env bash
#
# One-command local demo: the UI with LDAP sign-in, against a throwaway registry
# and directory. Nothing is installed outside this repository, and no state
# survives `stop`.
#
#   ./scripts/demo_local.sh          start  (foreground; Ctrl-C stops the UI)
#   ./scripts/demo_local.sh stop     tear the containers down
#
# Then open http://localhost:5099 and sign in as either:
#   alice / alicepassword    admin  (member of cn=registry-admins)
#   bob   / bobpassword      viewer (cannot delete anything)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-5099}"
DATA="$ROOT/.e2e-tmp/demo"
FIXTURE="$ROOT/docker/ldap-auth"

PY="$ROOT/venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

if [ "${1:-start}" = "stop" ]; then
  echo "==> stopping the UI"
  # Matched by the exact command line including the port, never by app name, so
  # this can only ever stop the instance this script started.
  pkill -f "uvicorn asgi:app --host 127.0.0.1 --port $PORT" || true
  echo "==> stopping the containers"
  (cd "$FIXTURE" && docker compose down)
  exit 0
fi

echo "==> starting OpenLDAP and a registry"
(cd "$FIXTURE" && docker compose up -d --no-build openldap registry)

echo "==> waiting for OpenLDAP to report healthy (a cold start can take 90s)"
for _ in $(seq 1 60); do
  if (cd "$FIXTURE" && docker compose ps --format '{{.Service}} {{.Status}}') \
       | grep -qE "^openldap .*healthy"; then
    break
  fi
  sleep 3
done

echo "==> seeding test users (idempotent)"
(cd "$FIXTURE" && docker compose up -d --no-build ldap-bootstrap >/dev/null)

mkdir -p "$DATA"

echo
echo "    UI     : http://localhost:$PORT"
echo "    alice  : alicepassword   (admin)"
echo "    bob    : bobpassword     (viewer)"
echo "    registry API: http://127.0.0.1:5007"
echo
echo "    Ctrl-C stops the UI. Then: ./scripts/demo_local.sh stop"
echo

cd "$ROOT"
AUTH_ENABLED=true \
AUTH_MODE=ldap \
AUTH_SECRET_KEY=demo-shared-secret \
AUTH_DEFAULT_ROLE=viewer \
BREAK_GLASS_USER=emergency \
BREAK_GLASS_PASSWORD=recovery-password \
LDAP_URL=ldap://127.0.0.1:3389 \
LDAP_BASE_DN=dc=example,dc=com \
LDAP_BIND_DN='cn=registry-ui,ou=Services,dc=example,dc=com' \
LDAP_BIND_PASSWORD=ui-bind-password \
LDAP_ADMIN_GROUP=registry-admins \
DATA_DIR="$DATA" \
READ_ONLY=false \
LOG_LEVEL=INFO \
REGISTRIES='[{"name":"Local Registry","api":"http://127.0.0.1:5007"}]' \
exec "$PY" -m uvicorn asgi:app --host 127.0.0.1 --port "$PORT" --reload
