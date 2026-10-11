# Oracle format

The oracle is smelt's ground truth. It is captured by RUNNING the current Python
function — never synthesized from a spec.

## Files (runs/<id>/oracle/)

- `oracle.jsonl` — one JSON object per case:
  `{case_id, args, kwargs, tags, expected_ok, expected, expected_err}`
  - `expected_ok: true` → `expected` is the encoded return value.
  - `expected_ok: false` → `expected_err` carries the Python exception (type + text).
  - Encoded values: `{t: "int"|"float"|"str"|"bool"|"none"|"list"|"dict"|"repr", v: …}`;
    floats encode NaN/inf as `"nan"`/`"inf"`/`"-inf"`.
- `meta.json` — `{target_path, module, func, seed, n_cases, params, return_annotation, smelt_tool}`.
- `sha256` — hash of `oracle.jsonl` + `meta.json` concatenated.

All three files are chmod 444 (read-only). `load_oracle()` re-hashes before every use;
any mismatch aborts the run with `oracle_tampered`.

## Case generation

1. Seeded random cases (default target 200; multi-parameter targets use independent
   random columns per parameter, `max(20, target // n)` each): per type —
   - `str`: random strings over a small alphabet, lengths 0–40
   - `int`: uniform within ±10^6
   - `float`: uniform ±100, rounded
   - `list[int]`: random-int lists, lengths 0–16
2. Fixed edge battery (always appended): empty string/list, single chars, repeats,
   long runs ("a"*33, "ab"*16), unicode (`éé`, `héllo`, `🎃🎃`, `a🚀b`), `0/1/-1`,
   `255`, `10^6`, `2^31`, i64 max/min, floats `0.0/-0.0/1.5/3.14159/1e-12`.

## Domain policy (tested domain)

- Integers stay inside the 64-bit range: the Rust mapping is `i64`, and values beyond
  i64 are outside the tested domain. They are rejected at capture time, never
  truncated.
- Exception TYPE equality is not required (pyo3 maps error types differently);
  outcome parity (returned vs raised) is compared instead.
- Floats compare with relative tolerance 1e-9; exact for ints/str/bool/None.

## What the oracle can and cannot prove

CAN: identical behavior on every recorded case, including the edge battery; no
argument mutation; deterministic outputs (first cases re-run).
CANNOT: equivalence outside the fixture distribution, complexity equivalence, or
performance. These limits are stated in the README.
