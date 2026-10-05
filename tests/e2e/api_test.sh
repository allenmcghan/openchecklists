#!/bin/bash
# Exercise the ocl-api worker at $B. Uses the real OCL Tester token in ./token.
B=${B:-http://127.0.0.1:8787}; T=$(cat ${OCL_TOKEN_FILE:-/tmp/ocl-e2e/token}); pass=0; fail=0
chk(){ # name expected actual
  if [[ "$3" == $2 ]]; then echo "PASS $1 ($3)"; pass=$((pass+1)); else echo "FAIL $1: expected $2 got $3"; fail=$((fail+1)); fi; }
code(){ curl -s -o /tmp/r.json -w '%{http_code}' "$@"; }
D1(){ (cd /workspace/openchecklists/openchecklists/worker/ocl-api && npx wrangler d1 execute openchecklists-users --local --json --command "$1" 2>/dev/null); }
A=(-H "Authorization: Bearer $T" -H 'Content-Type: application/json')
J=(-H 'Content-Type: application/json')
# CORS
chk cors-pages-dev "https://abc.openchecklists-net.pages.dev" "$(curl -s -D - -o /dev/null -X OPTIONS $B/api/me -H 'Origin: https://abc.openchecklists-net.pages.dev' | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')"
chk cors-evil "https://openchecklists.net" "$(curl -s -D - -o /dev/null $B/api/leaderboard -H 'Origin: https://evil.example' | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')"
chk cors-on-error "https://openchecklists.net" "$(curl -s -D - -o /dev/null $B/api/plan/bad -H 'Origin: https://openchecklists.net' | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')"
# Auth
chk me-noauth 401 "$(code $B/api/me)"
chk me-garbage 401 "$(code $B/api/me -H 'Authorization: Bearer a.b.c')"
chk me-auth 200 "$(code "${A[@]}" $B/api/me)"
chk bad-percent 400 "$(code $B/api/checklists/%E0%A4%A)"
# Profile
chk username-bad 422 "$(code -X PUT "${A[@]}" $B/api/me -d '{"username":"<script>"}')"
chk username-ok 200 "$(code -X PUT "${A[@]}" $B/api/me -d '{"username":"ocl_tester"}')"
# Email endpoints require auth
chk airport-pdf-noauth 401 "$(code -X POST "${J[@]}" $B/api/airport/email-pdf -d '{"email":"x@example.com","pdf_base64":"AAAA"}')"
chk log-pdf-noauth 401 "$(code -X POST "${J[@]}" $B/api/log/email-pdf -d '{"email":"x@example.com","pdf_base64":"AAAA"}')"
chk log-email-noauth 401 "$(code -X POST "${J[@]}" $B/api/log/email -d '{"email":"x@example.com"}')"
chk log-email-signed-in "502" "$(code -X POST "${A[@]}" $B/api/log/email -d "{\"email\":\"someone-else@example.com\"}")"
# Plans
chk plan-bad-ident 422 "$(code -X POST "${J[@]}" $B/api/me/plans -d '{"departure":"<img>","destination":"KOSH"}')"
chk plan-long-route 422 "$(code -X POST "${J[@]}" $B/api/me/plans -d '{"route":["KA","KB","KC","KD","KE","KF","KG","KH","KI","KJ","KK"]}')"
chk plan-create 201 "$(code -X POST "${J[@]}" $B/api/me/plans -d '{"route":["KBNA","KOSH"],"aircraft":{"n_number":"N1<b>","make":"Cessna","model":"172"},"fuel_onboard":40}')"
PID=$(python3 -c "import json;print(json.load(open('/tmp/r.json'))['id'])"); echo "  plan id $PID"
chk plan-id-long "ocl-????????????????" "$PID"
chk plan-get 200 "$(code $B/api/plan/$PID)"
chk plan-metar-present "*KBNA*" "$(python3 -c "import json;d=json.load(open('/tmp/r.json'));print(d['snapshot']['weather']['KBNA']['metar'] if d['snapshot']['weather'].get('KBNA') else 'none')")"
chk plan-email-noauth 401 "$(code -X POST "${J[@]}" $B/api/plan/$PID/email -d '{"email":"x@example.com"}')"
chk plan-refresh 200 "$(code "$B/api/plan/$PID?refresh=1")"
chk plan-mine 200 "$(code "${A[@]}" $B/api/me/plans)"
# Airport proxies
chk wx-kbna 200 "$(code $B/api/airport/KBNA/weather)"
chk wx-badident 400 "$(code "$B/api/airport/K%3Cx/weather")"
chk pirep 200 "$(code $B/api/proxy/pirep/KBNA)"
# Aircraft / airports
chk ac-add 200 "$(code -X POST "${A[@]}" $B/api/me/aircraft -d '{"make":"Cessna","model":"172","registration":"n12345"}')"
chk ac-list "*N12345*" "$(curl -s "${A[@]}" $B/api/me/aircraft)"
chk ap-bad 422 "$(code -X POST "${A[@]}" $B/api/me/airports -d '{"ident":"<x>"}')"
chk ap-add 200 "$(code -X POST "${A[@]}" $B/api/me/airports -d '{"ident":"kosh","name":"Wittman"}')"
# Logbook ownership: plant a foreign row, try to overwrite it
D1 "INSERT OR REPLACE INTO logbook_entries (id,user_id,flight_date,dep,arr,route,aircraft,total_time,pic_time,landings,remarks,source,source_ref,created_at) VALUES ('victim-1','someone-else','2026-01-01','KAAA','KBBB','','',1,1,1,'orig','manual',NULL,'2026-01-01')" >/dev/null
chk logbook-foreign 404 "$(code -X POST "${A[@]}" $B/api/me/logbook -d '{"id":"victim-1","flight_date":"2026-02-02","remarks":"pwned"}')"
chk logbook-foreign-intact "*orig*" "$(D1 "SELECT remarks FROM logbook_entries WHERE id='victim-1'")"
chk logbook-own 200 "$(code -X POST "${A[@]}" $B/api/me/logbook -d '{"flight_date":"2026-02-02","dep":"KBNA","arr":"KOSH","total_time":3.2}')"
# Checklist overwrite: plant someone else's public checklist, submit same id
D1 "INSERT OR REPLACE INTO saved_checklists (id,user_id,title,checklist_json,review_status,review_notes,is_public,saved_at) VALUES ('victim-cl','someone-else','Victim','{}','approved','',1,'2026-01-01')" >/dev/null
chk submit 200 "$(code -X POST "${A[@]}" $B/api/checklists/submit -d '{"checklist":{"id":"victim-cl","title":"Attacker","sections":[]}}')"
chk submit-new-id "victim-cl-*" "$(python3 -c "import json;print(json.load(open('/tmp/r.json'))['id'])")"
chk submit-pending-no-key "pending" "$(python3 -c "import json;print(json.load(open('/tmp/r.json'))['status'])")"
chk victim-intact "*Victim*" "$(D1 "SELECT title FROM saved_checklists WHERE id='victim-cl'")"
# Usage counter dedupe
CID=e2e-$RANDOM$RANDOM; curl -s -X POST $B/api/checklists/$CID/used >/dev/null; chk used-dedupe '{"uses":1}' "$(curl -s -X POST $B/api/checklists/$CID/used)"
chk used-bad-id 422 "$(code -X POST "$B/api/checklists/%3Cx%3E/used")"
# Quiz: real question + correct answer credited once; wrong/unknown not credited
chk quiz-unknown 422 "$(code -X POST "${A[@]}" $B/api/me/quiz -d '{}')"
chk quiz-wrong '*"correct":false*' "$(curl -s -X POST "${A[@]}" $B/api/me/quiz -d '{"test":"par","n":1,"answer":"A"}')"
Q1=$(curl -s -X POST "${A[@]}" $B/api/me/quiz -d '{"test":"p103","n":2,"answer":"'$(python3 -c "import json;print(json.load(open('/workspace/openchecklists/openchecklists/quiz/p103.json'))['questions'][1]['answer'])")'"}')
Q2=$(curl -s -X POST "${A[@]}" $B/api/me/quiz -d '{"test":"p103","n":2,"answer":"'$(python3 -c "import json;print(json.load(open('/workspace/openchecklists/openchecklists/quiz/p103.json'))['questions'][1]['answer'])")'"}')
chk quiz-second-credit-null '*"points":null*' "$Q2"
# Public reads
chk checklists-list 200 "$(code $B/api/checklists)"
chk checklist-stats 200 "$(code "$B/api/checklists/stats?ids=a,b")"
chk leaderboard 200 "$(code $B/api/leaderboard)"
echo "== $pass passed, $fail failed"
