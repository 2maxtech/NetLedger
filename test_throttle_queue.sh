#!/bin/bash
# Verifies the Root Cause B fix: pre-existing per-user simple queues
# get disabled on throttle/disconnect and re-enabled on reconnect.
#
# Prereqs:
#   - App running on http://localhost
#   - MT reachable at MT_URL with MT_USER/MT_PASS
#   - At least one customer exists with a PPPoE username bound to MT
#
# Usage:
#   MT_URL=http://192.168.40.30 MT_USER=admin MT_PASS=SeafoodCity12# \
#   PPPOE_USER=juan.delacruz CUSTOMER_ID=<uuid> ./test_throttle_queue.sh

set -e

MT_URL=${MT_URL:-http://192.168.40.30}
MT_USER=${MT_USER:-admin}
MT_PASS=${MT_PASS:-SeafoodCity12#}
PPPOE_USER=${PPPOE_USER:?set PPPOE_USER to a PPPoE secret name that exists on the MT}
CUSTOMER_ID=${CUSTOMER_ID:?set CUSTOMER_ID to the customer UUID}

MT_AUTH="$MT_USER:$MT_PASS"
APP_URL=${APP_URL:-http://localhost}

echo "=== Login to app ==="
TOKEN=$(curl -s -X POST $APP_URL/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"

echo "=== Cleanup any stale shadow queue ==="
for qid in $(curl -s $MT_URL/rest/queue/simple -u "$MT_AUTH" \
  | python3 -c "import sys,json; [print(q['.id']) for q in json.load(sys.stdin) if q.get('name')==\"$PPPOE_USER-shadow\"]"); do
  echo "  deleting stale $qid"
  curl -s -X DELETE $MT_URL/rest/queue/simple/$qid -u "$MT_AUTH" >/dev/null
done

echo "=== Create shadowing simple queue: 100M/100M targeting <pppoe-$PPPOE_USER> ==="
SHADOW_ID=$(curl -s -X PUT $MT_URL/rest/queue/simple \
  -u "$MT_AUTH" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$PPPOE_USER-shadow\",\"target\":\"<pppoe-$PPPOE_USER>\",\"max-limit\":\"100M/100M\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('.id',''))")
echo "  created queue $SHADOW_ID"

print_queue_state() {
  curl -s $MT_URL/rest/queue/simple/$SHADOW_ID -u "$MT_AUTH" \
    | python3 -c "import sys,json; q=json.load(sys.stdin); print('  queue disabled=%s max-limit=%s' % (q.get('disabled','false'), q.get('max-limit','')))"
}

echo "=== State BEFORE throttle ==="
print_queue_state

echo "=== Call /throttle on customer $CUSTOMER_ID ==="
curl -s -X POST $APP_URL/api/v1/customers/$CUSTOMER_ID/throttle \
  -H "$AUTH" | python3 -m json.tool

echo "=== State AFTER throttle (expect: queue disabled=true) ==="
print_queue_state

echo "=== Check secret profile on MT (expect: *-throttle) ==="
curl -s "$MT_URL/rest/ppp/secret?name=$PPPOE_USER" -u "$MT_AUTH" \
  | python3 -c "import sys,json; s=json.load(sys.stdin); print('  profile=%s disabled=%s' % (s[0].get('profile'), s[0].get('disabled'))) if s else print('  not found')"

echo "=== Check active sessions (expect: no active session for $PPPOE_USER) ==="
curl -s $MT_URL/rest/ppp/active -u "$MT_AUTH" \
  | python3 -c "import sys,json; names=[s.get('name') for s in json.load(sys.stdin)]; print('  active:', [n for n in names if n==\"$PPPOE_USER\"] or 'none')"

echo ""
echo "=== Call /reconnect ==="
curl -s -X POST $APP_URL/api/v1/customers/$CUSTOMER_ID/reconnect \
  -H "$AUTH" | python3 -m json.tool

echo "=== State AFTER reconnect (expect: queue disabled=false) ==="
print_queue_state

echo "=== Cleanup: delete shadow queue ==="
curl -s -X DELETE $MT_URL/rest/queue/simple/$SHADOW_ID -u "$MT_AUTH" >/dev/null
echo "  done"

echo ""
echo "=== Now test /disconnect path ==="
SHADOW_ID=$(curl -s -X PUT $MT_URL/rest/queue/simple \
  -u "$MT_AUTH" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$PPPOE_USER-shadow\",\"target\":\"<pppoe-$PPPOE_USER>\",\"max-limit\":\"100M/100M\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('.id',''))")
echo "  recreated shadow queue $SHADOW_ID"

echo "=== Call /disconnect ==="
curl -s -X POST $APP_URL/api/v1/customers/$CUSTOMER_ID/disconnect \
  -H "$AUTH" | python3 -m json.tool

echo "=== State AFTER disconnect (expect: queue disabled=true, secret disabled=true) ==="
print_queue_state
curl -s "$MT_URL/rest/ppp/secret?name=$PPPOE_USER" -u "$MT_AUTH" \
  | python3 -c "import sys,json; s=json.load(sys.stdin); print('  secret disabled=%s' % s[0].get('disabled')) if s else print('  not found')"

echo "=== Call /reconnect ==="
curl -s -X POST $APP_URL/api/v1/customers/$CUSTOMER_ID/reconnect \
  -H "$AUTH" | python3 -m json.tool

echo "=== Final state (expect: queue disabled=false, secret disabled=false) ==="
print_queue_state
curl -s "$MT_URL/rest/ppp/secret?name=$PPPOE_USER" -u "$MT_AUTH" \
  | python3 -c "import sys,json; s=json.load(sys.stdin); print('  secret disabled=%s' % s[0].get('disabled')) if s else print('  not found')"

echo "=== Cleanup: delete shadow queue ==="
curl -s -X DELETE $MT_URL/rest/queue/simple/$SHADOW_ID -u "$MT_AUTH" >/dev/null

echo ""
echo "=== DONE ==="
