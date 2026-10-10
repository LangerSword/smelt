#!/usr/bin/env sh
# Deterministic fake `smelt` for furnace live-mode tests.
# Ignores its CLI arguments; emits a realistic events stream with sleeps,
# then prints a JSON summary and exits with $FAKE_EXIT (default 0).
#
# Env knobs: FAKE_RUNS_DIR (default "runs"), FAKE_SLEEP (seconds, default 1),
#            FAKE_EXIT (default 0), FAKE_BADJSON (1 = emit a corrupt line),
#            FAKE_NOEVENTS (1 = exit immediately without a run dir).
set -eu

if [ "${FAKE_NOEVENTS:-0}" = "1" ]; then
  echo "fake-smelt: crashing before any events" >&2
  exit "${FAKE_EXIT:-1}"
fi

RUNS="${FAKE_RUNS_DIR:-runs}"
RID="261011-999999-fake01"
D="$RUNS/$RID"
mkdir -p "$D"
TS=$(date +%s)

echo "{\"ts\": $TS, \"schema_version\": \"1\", \"event\": \"run_start\", \"node\": \"\", \"target\": \"fake.py:fn\", \"provider\": \"fake\", \"model\": \"fake-model\"}" > "$D/events.jsonl"
sleep "${FAKE_SLEEP:-1}"
echo "{\"ts\": $TS, \"schema_version\": \"1\", \"event\": \"purity_ok\", \"node\": \"\"}" >> "$D/events.jsonl"
sleep "${FAKE_SLEEP:-1}"
echo "{\"ts\": $TS, \"schema_version\": \"1\", \"event\": \"capture_done\", \"node\": \"\", \"n_cases\": 42, \"sha256\": \"0123456789abcdef\"}" >> "$D/events.jsonl"
if [ "${FAKE_BADJSON:-0}" = "1" ]; then
  echo "{\"ts\": BADJSON{{{ this line is corrupt" >> "$D/events.jsonl"
fi
sleep "${FAKE_SLEEP:-1}"
echo "{\"ts\": $TS, \"schema_version\": \"1\", \"event\": \"attempt_start\", \"node\": \"\", \"attempt\": 1}" >> "$D/events.jsonl"
sleep "${FAKE_SLEEP:-1}"
echo "{\"ts\": $TS, \"schema_version\": \"1\", \"event\": \"accept\", \"node\": \"\", \"ratio\": 2.5, \"ratio_ci_lo\": 2.2, \"flags\": []}" >> "$D/events.jsonl"
echo "{\"ts\": $TS, \"schema_version\": \"1\", \"event\": \"run_end\", \"node\": \"\", \"status\": \"accepted\", \"reason\": \"verified 42/42 cases; speedup 2.50x\"}" >> "$D/events.jsonl"

printf '{"run_id": "%s", "status": "accepted"}\n' "$RID"
exit "${FAKE_EXIT:-0}"
