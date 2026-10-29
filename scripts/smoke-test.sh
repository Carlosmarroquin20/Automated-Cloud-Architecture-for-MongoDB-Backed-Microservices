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

# The history outlives the item: the audit service built it from the events the
# outbox relay published, so it arrives asynchronously and is polled for.
echo "Reading the item's audit history"
history_url="${BASE_URL}/api/v1/audit/items/${item_id}/events"
history=""
for _ in $(seq 1 30); do
  history="$(curl -fsS "${history_url}" 2>/dev/null || true)"
  if echo "${history}" | jq -e 'length == 2' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "${history}" | jq -e --arg id "${item_id}" '
  map(.type) == ["item.created", "item.deleted"]
  and all(.[]; .subject == $id)
' >/dev/null || fail "audit history is incomplete: ${history}"
echo "  $(echo "${history}" | jq -r 'map(.type) | join(" -> ")')"

# Runs last because it deliberately exhausts this client's request budget. The
# burst is concurrent so it exceeds the configured rate regardless of the
# per-request latency of the path under test.
echo "Exceeding the API rate limit"
bodies="$(mktemp -d)"
trap 'rm -rf "${bodies}"' EXIT
# Each response body is kept so a throttled one is inspected directly; a request
# issued after the burst would find the budget already refilled.
statuses="$(seq 1 150 | xargs -P 30 -I{} \
  curl -s -o "${bodies}/{}" -w '%{http_code} {}\n' "${API}?limit=1")"
throttled="$(grep -c '^429 ' <<<"${statuses}" || true)"
echo "  ${throttled} of 150 requests throttled"
[ "${throttled}" -gt 0 ] || fail "no request was rate limited"

sample="$(grep -m1 '^429 ' <<<"${statuses}" | cut -d' ' -f2)"
jq -e '.error.code == "rate_limited"' "${bodies}/${sample}" >/dev/null \
  || fail "throttled response lacks the error envelope: $(cat "${bodies}/${sample}")"

echo "Smoke test passed"
