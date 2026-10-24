#!/usr/bin/env bash
# HW7 Part 1 demo - JWT login, /auth/me and role checks on the trials API.
# Usage:  bash code/hw07_part1_demo.sh [section]   (sections 1-5, default: all)
# Needs the API running on PORT_BASE 8509 (make run-api) and `make hw07-migrate` done once.
set -u
cd "$(dirname "$0")/.." || exit 1
BASE=${BASE:-http://localhost:8509}
PY=${PY:-.venv/bin/python}
PW=$(grep '^HW7_DEMO_PASSWORD=' .env | cut -d= -f2-)
ONLY=${1:-all}

pretty() {  # pretty-print JSON; long lists are cut to 2 items
  "$PY" -c '
import json, sys
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except ValueError:
    print(raw); sys.exit()
if isinstance(data, dict) and isinstance(data.get("items"), list) and len(data["items"]) > 2:
    extra = len(data["items"]) - 2
    data["items"] = data["items"][:2] + ["... %d more items" % extra]
print(json.dumps(data, indent=2, default=str))'
}

call() {  # call "<label>" <method> <path> [token] [json-body]
  local label=$1 method=$2 path=$3 token=${4:-} body=${5:-}
  local args=(-s -o /tmp/s3209_body -w '%{http_code}' -X "$method" "$BASE$path")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  echo
  echo "--- $label"
  echo "    $method $path$([ -n "$token" ] && echo "   [Authorization: Bearer ${token:0:24}...]")"
  [ -n "$body" ] && echo "    body: $(echo "$body" | sed "s/$PW/********/")"
  local code; code=$(curl "${args[@]}")
  echo "    => HTTP $code"
  pretty < /tmp/s3209_body | sed 's/^/    /'
}

login() { curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$1\",\"password\":\"$PW\"}" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'; }

header() { echo; echo "================ HW7 Part 1.$1: $2 ================"; echo "Run by: Ani Taraiya (s3209)   $(date '+%Y-%m-%d %H:%M:%S')   API: $BASE"; }
want() { [ "$ONLY" = all ] || [ "$ONLY" = "$1" ]; }

if want 1; then
  header 1 "POST /auth/login"
  call "valid credentials -> JWT token" POST /auth/login "" "{\"username\":\"s3209_writer\",\"password\":\"$PW\"}"
  call "invalid credentials (wrong password) -> 401" POST /auth/login "" '{"username":"s3209_writer","password":"wrong-password"}'
fi

if want 2; then
  header 2 "GET /auth/me - missing / invalid / expired token"
  call "no token -> 401" GET /auth/me
  call "invalid (forged) token -> 401" GET /auth/me "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJoYWNrZXIifQ.not-a-real-signature"
  EXPIRED=$("$PY" -c '
import os, jwt, datetime as d
from dotenv import load_dotenv
load_dotenv(".env")
now = d.datetime.now(d.UTC)
print(jwt.encode({"sub": "s3209_reader", "role": "reader", "iss": "s3209",
                  "iat": now - d.timedelta(minutes=40), "exp": now - d.timedelta(minutes=10)},
                 os.environ["JWT_SECRET"], algorithm="HS256"))')
  call "expired token (correctly signed, exp 10 min ago) -> 401" GET /auth/me "$EXPIRED"
  call "valid token -> 200 identity + role" GET /auth/me "$(login s3209_reader)"
fi

READER=$(login s3209_reader); WRITER=$(login s3209_writer); MOD=$(login s3209_moderator)
SPONSOR=$(curl -s "$BASE/api/sponsors?page_size=1" -H "Authorization: Bearer $READER" \
  | "$PY" -c 'import json,sys;items=json.load(sys.stdin).get("items") or [{}];print(items[0].get("id",""))')
if [ -z "$SPONSOR" ] && { want 3 || want 4; }; then
  echo "No sponsor found in s3209_rel - run: cd code/web_application && python seed_hw05.py"; exit 1
fi
NEW_TRIAL="{\"trial_title\":\"HW7 RBAC Demo Study in Asthma\",\"nct_id\":\"NCT3209$(printf '%04d' $((RANDOM % 10000)))\",\"enrollment_slots\":40,\"status\":\"Recruiting\",\"sponsor_id\":$SPONSOR}"

if want 3 || want 4; then
  header 3 "POST /api/trials - create needs writer or moderator"
  call "create as reader -> 403" POST /api/trials "$READER" "$NEW_TRIAL"
  call "create as writer -> 201" POST /api/trials "$WRITER" "$NEW_TRIAL"
  NEW_ID=$("$PY" -c 'import json;print(json.load(open("/tmp/s3209_body"))["id"])')
fi

if want 4; then
  header 4 "DELETE /api/trials/{id} - moderator only"
  call "delete as writer -> 403" DELETE "/api/trials/$NEW_ID" "$WRITER"
  call "delete as moderator -> 200" DELETE "/api/trials/$NEW_ID" "$MOD"
fi

if want 5; then
  header 5 "GET /api/trials - read with any valid token"
  call "list as reader -> 200" GET "/api/trials?page_size=3" "$READER"
fi
echo
