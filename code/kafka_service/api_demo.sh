#!/usr/bin/env bash
# HW8 Part 1: the same CREATE -> GET flow through the FastAPI wrapper (port 8509).
# The caller sets X-Correlation-ID; the API, worker and response keep it unchanged.
set -u
BASE=${BASE:-http://127.0.0.1:8509}
echo "Run by: Ani Taraiya (s3209)   $(date '+%Y-%m-%d %H:%M:%S')   API: $BASE"
CID=$(python3 -c 'import uuid; print(uuid.uuid4())')
echo; echo "POST /trials   X-Correlation-ID: $CID"
BODY='{"trialTitle":"Phase III Trial of Vaccine Y in Older Adults","sponsor":"UCSF Medical Center","email":"trials@ucsf-med.org","content":"Placebo-controlled study of a seasonal vaccine in adults over 65, tracking antibody levels for one year.","status":"Recruiting","terms":true}'
OUT=$(curl -s -H "X-Correlation-ID: $CID" -H 'Content-Type: application/json' -d "$BODY" "$BASE/trials")
echo "$OUT" | python3 -m json.tool
TID=$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("trial_id",""))')
CID2=$(python3 -c 'import uuid; print(uuid.uuid4())')
echo; echo "GET /trials/$TID   X-Correlation-ID: $CID2"
curl -s -H "X-Correlation-ID: $CID2" "$BASE/trials/$TID" | python3 -m json.tool
