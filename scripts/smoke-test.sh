#!/usr/bin/env bash
# End-to-end smoke test for a running deployment.
#
# Every request goes through the frontend origin, so a pass proves the whole
# path works: the nginx reverse proxy, the backend, and its MongoDB connection.
# The test creates, reads, and deletes its own item, leaving no residue.
#
# Usage: scripts/smoke-test.sh [base-url]   (default: http://localhost:8080)

set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
API="${BASE_URL}/api/v1/items"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# Readiness is polled because the reverse proxy and the database connection may
# still be settling when the rollout reports complete.
echo "Waiting for readiness at ${BASE_URL}/health/ready"
ready=""
for _ in $(seq 1 30); do
  if ready="$(curl -fsS "${BASE_URL}/health/ready" 2>/dev/null)"; then
    break
  fi
  sleep 2
done
[ -n "${ready}" ] || fail "readiness endpoint never succeeded"
echo "  ${ready}"
echo "${ready}" | jq -e '.status == "ready" and .checks.mongodb == "up"' >/dev/null \
  || fail "service is not ready: ${ready}"

echo "Serving the static client at ${BASE_URL}/"
curl -fsS "${BASE_URL}/" | grep -qi '<!doctype html' || fail "frontend did not return the HTML shell"

echo "Creating an item"
created="$(curl -fsS -X POST "${API}" \
  -H 'Content-Type: application/json' \
  -d '{"name":"smoke-test","description":"created by the CI smoke test","quantity":1,"tags":["ci"]}')"
item_id="$(echo "${created}" | jq -er '.id')" || fail "create returned no id: ${created}"
echo "  created ${item_id}"

echo "Reading the item back"
fetched="$(curl -fsS "${API}/${item_id}")"
echo "${fetched}" | jq -e '.name == "smoke-test" and .quantity == 1' >/dev/null \
  || fail "read-back mismatch: ${fetched}"

echo "Deleting the item"
code="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "${API}/${item_id}")"
[ "${code}" = "204" ] || fail "delete returned HTTP ${code}"

code="$(curl -sS -o /dev/null -w '%{http_code}' "${API}/${item_id}")"
[ "${code}" = "404" ] || fail "deleted item still resolvable (HTTP ${code})"

echo "Smoke test passed"
