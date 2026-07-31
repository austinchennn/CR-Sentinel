#!/usr/bin/env bash
# Applies every migrations/*.sql file in order against CRDB_ADMIN_URL.
# Idempotent -- safe to re-run against an existing cluster (PRD-01
# functional requirement 5).
set -euo pipefail

: "${CRDB_ADMIN_URL:?Set CRDB_ADMIN_URL to a cockroach sql connection string}"

cd "$(dirname "$0")/.."
for f in migrations/*.sql; do
  echo "Applying $f"
  cockroach sql --url "$CRDB_ADMIN_URL" -f "$f"
done
