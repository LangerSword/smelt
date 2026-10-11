#!/usr/bin/env bash
# smelt — 3-minute demo (offline; file provider; no API calls).
#   one ACCEPTED run · one REJECTED run · one REFUSAL
set -u
cd "$(dirname "$0")/.."
SMELT=".venv/bin/smelt"
T0=$(date +%s)

echo "=== 1/3  ACCEPTED — clamp_all (list[int], int, int) → verified Rust, measured speedup"
$SMELT run examples/demo/clamp_all.py:clamp_all --provider file \
  --candidate tests/fixtures/candidates/clamp_all_correct.rs --cases 200
echo "exit=$? (0 = accepted)"
echo

echo "=== 2/3  REJECTED — a WRONG rewrite is never accepted (the oracle catches it)"
$SMELT run examples/demo/run_length.py:rle_encode --provider file \
  --candidate tests/fixtures/candidates/rle_encode_wrong.rs --cases 120
echo "exit=$? (4 = rejected — a correct, honest outcome)"
echo

echo "=== 3/3  REFUSED — impure target (randomness): clean refusal with the reason"
$SMELT run examples/demo/impure.py:noisy_max --provider file
echo "exit=$? (3 = refused — impure target)"
echo

echo "=== furnace: replay the accepted run (q quits)"
RID=$(ls -dt runs/*/ | head -1)
echo "run: $RID"
if [ -x ./tui/furnace ]; then
  ./tui/furnace replay "$RID"
else
  echo "(furnace not built — cd tui && go build -o furnace .)"
fi
echo
echo "demo finished in $(( $(date +%s) - T0 ))s"
