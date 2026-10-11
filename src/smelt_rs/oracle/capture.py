"""Oracle capture: generate cases, record the current function's answers, freeze.

The oracle is the product's ground truth. It is captured by RUNNING the current
Python function (never by trusting the spec), hashed, and made read-only. Any later
tamper is detected by hash. Reviewed closely by the developer.
"""

import itertools
import json
import os
import random

from smelt_rs.core.failures import CaptureFailed, OracleTampered, RefusedTarget
from smelt_rs.core.state import sha256_bytes
from smelt_rs.worker_client import run_worker

EDGE_STRINGS = ["", "a", "aa", "aaa", "aab", "abb", "abab", "a" * 8, "a" * 33,
                "ab" * 16, "aabb", " b ", "  ", "1", "11", "112", "x1y", "zzz",
                "éé", "héllo", "🎃", "🎃🎃", "a🚀b", "a a a", "aaaaaaaaaaaaaaaaaaaa"]
# i64 domain policy: generated ints stay inside the 64-bit range so the Rust i64
# mapping can hold every generated case; out-of-range inputs are outside the tested
# domain (documented in the README limits). Big Python ints are NOT silently truncated.
EDGE_INTS = [0, 1, -1, 7, 255, 10 ** 6, 2 ** 31, 2 ** 63 - 1, -(2 ** 63)]
EDGE_FLOATS = [0.0, -0.0, 1.5, -2.25, 3.14159, 1e-12]
EDGE_LISTS_INT = [[], [0], [1, 2, 3], list(range(32))]


def gen_cases_for_param(annotation: str, rnd: random.Random, n_random: int):
    if annotation == "str":
        alphabet = "abcde 1!"
        random_cases = ["".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 40)))
                        for _ in range(n_random)]
        return random_cases, EDGE_STRINGS
    if annotation == "int":
        random_cases = [rnd.randint(-10 ** 6, 10 ** 6) for _ in range(n_random)]
        return random_cases, EDGE_INTS
    if annotation == "float":
        random_cases = [round(rnd.uniform(-100, 100), 4) for _ in range(n_random)]
        return random_cases, EDGE_FLOATS
    if annotation == "list[int]":
        random_cases = [[rnd.randint(-50, 50) for _ in range(rnd.randint(0, 16))]
                        for _ in range(n_random)]
        return random_cases, EDGE_LISTS_INT
    raise RefusedTarget(
        f"unsupported parameter type {annotation!r} — refactor hint: use one of "
        "str/int/float/bool/list[int]/list[str], or convert the argument before the call")


def generate_cases(params: list[dict], target_cases: int, seed: int) -> list[dict]:
    if len(params) == 1:
        # Single parameter: byte-identical to the original generator (corpus oracles
        # must stay reproducible).
        p = params[0]
        rnd = random.Random(seed)
        random_cases, edges = gen_cases_for_param(p["annotation"], rnd, target_cases)
        cases = [{"case_id": f"r{i:04d}", "args": [v], "kwargs": {}, "tags": ["random"]}
                 for i, v in enumerate(random_cases)]
        cases += [{"case_id": f"e{i:04d}", "args": [v], "kwargs": {}, "tags": ["edge"]}
                  for i, v in enumerate(edges)]
        if len(cases) < target_cases:
            raise CaptureFailed(f"generated only {len(cases)} cases (< target {target_cases})")
        return cases

    # Multi-parameter (G1 widening): independent random columns per parameter,
    # plus a capped product of the edge batteries.
    rnd = random.Random(seed)
    per = max(20, target_cases // len(params))
    cols = [gen_cases_for_param(p["annotation"], rnd, per) for p in params]
    n_rand = min(len(c[0]) for c in cols)
    cases = []
    for i in range(n_rand):
        args = [c[0][i] for c in cols]
        cases.append({"case_id": f"r{i:04d}", "args": args, "kwargs": {}, "tags": ["random"]})
    edge_combos = list(itertools.product(*[c[1] for c in cols]))
    if len(edge_combos) > 60:
        step = max(1, len(edge_combos) // 60)
        edge_combos = edge_combos[::step]
    for i, combo in enumerate(edge_combos):
        cases.append({"case_id": f"e{i:04d}", "args": list(combo), "kwargs": {}, "tags": ["edge"]})
    if len(cases) < 40:
        raise CaptureFailed(f"generated only {len(cases)} cases for {len(params)} parameters")
    return cases


def capture_oracle(*, run_dir: str, target_path: str, module_name: str, func_name: str,
                   python_exe: str, target_cases: int, seed: int):
    """Returns (meta dict, oracle hash). Raises CaptureFailed / OracleTampered."""
    # 1. introspect (types only; the worker imports the module, not the parent)
    req = {"mode": "introspect", "target_path": target_path, "module": module_name, "func": func_name}
    try:
        intro = run_worker(python_exe, req, timeout=60)
    except Exception as e:
        raise CaptureFailed(f"introspection failed: {e}")
    if intro.get("error"):
        err = str(intro["error"])
        if "import" in err.lower() or "no module named" in err.lower():
            raise RefusedTarget(
                f"could not load the target module: {err} — package layouts (relative "
                "imports) are not supported yet; refactor hint: point smelt at a "
                "standalone module or copy the target file out of the package")
        raise CaptureFailed(f"could not load the target: {err}")
    params = intro.get("params") or []
    ret_ann = intro.get("return_annotation")
    if not params:
        raise CaptureFailed("target function has no parameters (nothing to test)")

    # 2. generate cases, record answers
    cases = generate_cases(params, target_cases, seed)
    req = {"mode": "run", "side": "python", "target_path": target_path, "module": module_name,
           "func": func_name, "cases": cases, "check_mutation": True}
    try:
        res = run_worker(python_exe, req, timeout=180)
    except Exception as e:
        raise CaptureFailed(f"recording failed: {e}")

    # 3. determinism: rerun the first three cases
    try:
        res2 = run_worker(python_exe, {**req, "cases": cases[:3], "check_mutation": False}, timeout=60)
    except Exception as e:
        raise CaptureFailed(f"determinism check failed: {e}")
    for a, b in zip(res["results"][:3], res2["results"][:3]):
        if a != b:
            raise CaptureFailed("nondeterministic output detected on rerun")

    mutated = [r["id"] for r in res["results"] if r.get("mutated")]
    if mutated:
        raise CaptureFailed(f"function mutates its arguments (cases: {mutated[:3]})")

    # 4. freeze
    entries = []
    for case, r in zip(cases, res["results"]):
        entries.append({
            "case_id": case["case_id"], "args": case["args"], "kwargs": case["kwargs"],
            "tags": case.get("tags", []),
            "expected_ok": bool(r.get("ok")), "expected": r.get("out"), "expected_err": r.get("err"),
        })
    oracle_dir = os.path.join(run_dir, "oracle")
    os.makedirs(oracle_dir, exist_ok=True)
    with open(os.path.join(oracle_dir, "oracle.jsonl"), "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    meta = {"target_path": target_path, "module": module_name, "func": func_name,
            "seed": seed, "n_cases": len(entries), "params": params,
            "return_annotation": ret_ann, "smelt_tool": "0.1.0"}
    with open(os.path.join(oracle_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    h = sha256_bytes(open(os.path.join(oracle_dir, "oracle.jsonl"), "rb").read()
                     + open(os.path.join(oracle_dir, "meta.json"), "rb").read())
    with open(os.path.join(oracle_dir, "sha256"), "w") as f:
        f.write(h + "\n")
    for name in ("oracle.jsonl", "meta.json", "sha256"):
        os.chmod(os.path.join(oracle_dir, name), 0o444)
    return meta, h


def load_oracle(oracle_dir: str):
    """Load + validate a frozen oracle. Raises OracleTampered on hash mismatch."""
    try:
        h = open(os.path.join(oracle_dir, "sha256")).read().strip()
        cur = sha256_bytes(open(os.path.join(oracle_dir, "oracle.jsonl"), "rb").read()
                           + open(os.path.join(oracle_dir, "meta.json"), "rb").read())
    except FileNotFoundError as e:
        raise OracleTampered(f"oracle files missing: {e}")
    if cur != h:
        raise OracleTampered("oracle hash mismatch (files changed after freeze)")
    entries = [json.loads(line) for line in open(os.path.join(oracle_dir, "oracle.jsonl"))]
    meta = json.load(open(os.path.join(oracle_dir, "meta.json")))
    return entries, meta, h
