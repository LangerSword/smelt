#!/usr/bin/env python
"""Meta-eval: prove the oracle rejects KNOWN-WRONG rewrites (gate: all rejected).

Four target sets:
  1) rle_encode (single str param) — 10 wrong rewrites, the original battery;
  2) divide (two int params, raises on b==0) — the G1 multi-parameter battery:
     wrong value / wrong exception (returns instead of raising) / panic where the
     Python returns (panics must become Python exceptions, never abort the process);
  3) manhattan (one tuple[int, int] param) — the tuple battery: wrong value
     (no abs), wrong value (ignores the pair's second element), wrong exception;
  4) rms (one list[float] param, raises on empty) — the v0.8 float-list battery:
     wrong value (mean-abs), wrong value (first element only), wrong exception
     (returns 0.0 on empty instead of raising);
  5) sum_pair (list[int] -> tuple[int, int]) — the v0.8 tuple-RETURN battery:
     swapped elements, list-instead-of-tuple (type fidelity), wrong second
     element. The list-not-tuple candidate false-accepts without the v0.8
     tuple tag — it is the gate for return-container fidelity.

Every candidate must come back REJECTED (verify_mismatch, exit code 4) when run
through the full pipeline against the frozen oracle. If any is accepted, the
verifier has a false-accept bug — the gate for that is: unexpected == 0.
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from smelt_rs.core import orchestrator  # noqa: E402

GLUE = """

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rle_encode, m)?)?;
    Ok(())
}
"""

GLUE_DIVIDE = """

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(divide, m)?)?;
    Ok(())
}
"""

GLUE_TUPLE = """

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(manhattan, m)?)?;
    Ok(())
}
"""

GLUE_RMS = """

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rms, m)?)?;
    Ok(())
}
"""

GLUE_SUM_PAIR = """

#[pymodule]
fn smelt_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_pair, m)?)?;
    Ok(())
}
"""

WRONG = {
    "w01_omit_singles": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        if j - i > 1 { out.push_str(&(j - i).to_string()); }
        i = j;
    }
    out
}
""" + GLUE,
    "w02_off_by_one": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        out.push_str(&(j - i + 1).to_string());
        i = j;
    }
    out
}
""" + GLUE,
    "w03_no_merge": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let mut out = String::new();
    for c in text.chars() {
        out.push(c);
        out.push('1');
    }
    out
}
""" + GLUE,
    "w04_count_before_char": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push_str(&(j - i).to_string());
        out.push(chars[i]);
        i = j;
    }
    out
}
""" + GLUE,
    "w05_skip_last_run": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i + 1 < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        out.push_str(&(j - i).to_string());
        i = j;
    }
    out
}
""" + GLUE,
    "w06_unary_count": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        for _ in 0..(j - i) { out.push('+'); }
        i = j;
    }
    out
}
""" + GLUE,
    "w07_reversed_runs": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut parts: Vec<String> = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        parts.push(format!("{}{}", chars[i], j - i));
        i = j;
    }
    parts.reverse();
    parts.concat()
}
""" + GLUE,
    "w08_drop_first_char": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 1;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        out.push_str(&(j - i).to_string());
        i = j;
    }
    out
}
""" + GLUE,
    "w09_duplicated_output": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        out.push_str(&(j - i).to_string());
        i = j;
    }
    let dup = out.clone();
    out.push_str(&dup);
    out
}
""" + GLUE,
    "w10_trailing_total": """use pyo3::prelude::*;

#[pyfunction]
fn rle_encode(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let mut j = i;
        while j < chars.len() && chars[j] == chars[i] { j += 1; }
        out.push(chars[i]);
        out.push_str(&(j - i).to_string());
        i = j;
    }
    out.push_str(&chars.len().to_string());
    out
}
""" + GLUE,
}

WRONG_MULTI = {
    # wrong value: modulo instead of integer division (returns when Python returns,
    # but the value is wrong)
    "m01_wrong_value": """use pyo3::prelude::*;

#[pyfunction]
fn divide(a: i64, b: i64) -> PyResult<i64> {
    if b == 0 {
        return Err(pyo3::exceptions::PyZeroDivisionError::new_err("integer division or modulo by zero"));
    }
    Ok(a % b)
}
""" + GLUE_DIVIDE,
    # wrong exception behaviour: returns 0 where the Python raises ZeroDivisionError
    "m02_wrong_exception": """use pyo3::prelude::*;

#[pyfunction]
fn divide(a: i64, b: i64) -> PyResult<i64> {
    if b == 0 {
        return Ok(0);
    }
    Ok(a / b)
}
""" + GLUE_DIVIDE,
    # panic where the Python returns: panics must become Python exceptions and the
    # worker must survive (never abort the process)
    "m03_panic_where_python_returns": """use pyo3::prelude::*;

#[pyfunction]
fn divide(a: i64, b: i64) -> PyResult<i64> {
    if a < 0 {
        panic!("boom: negative dividend");
    }
    if b == 0 {
        return Err(pyo3::exceptions::PyZeroDivisionError::new_err("integer division or modulo by zero"));
    }
    Ok(a / b)
}
""" + GLUE_DIVIDE,
}

WRONG_TUPLE = {
    # wrong value: no abs — wrong on any negative coordinate
    "t01_wrong_value_no_abs": """use pyo3::prelude::*;

#[pyfunction]
fn manhattan(p: (i64, i64)) -> i64 {
    p.0 + p.1
}
""" + GLUE_TUPLE,
    # wrong value: ignores the second element of the pair
    "t02_wrong_value_ignore_y": """use pyo3::prelude::*;

#[pyfunction]
fn manhattan(p: (i64, i64)) -> i64 {
    p.0.abs()
}
""" + GLUE_TUPLE,
    # wrong exception: raises ValueError where the Python returns
    "t03_wrong_exception": """use pyo3::prelude::*;

#[pyfunction]
fn manhattan(p: (i64, i64)) -> PyResult<i64> {
    if p.0 < 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("negative x"));
    }
    Ok(p.0.abs() + p.1.abs())
}
""" + GLUE_TUPLE,
}

WRONG_FLOATLIST = {
    # wrong value: mean of absolute values instead of root-mean-square
    "f01_mean_abs_not_rms": """use pyo3::prelude::*;

#[pyfunction]
fn rms(xs: Vec<f64>) -> PyResult<f64> {
    if xs.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("empty sample"));
    }
    let s: f64 = xs.iter().map(|x| x.abs()).sum();
    Ok(s / xs.len() as f64)
}
""" + GLUE_RMS,
    # wrong value: ignores every element after the first
    "f02_first_element_only": """use pyo3::prelude::*;

#[pyfunction]
fn rms(xs: Vec<f64>) -> PyResult<f64> {
    if xs.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("empty sample"));
    }
    Ok(xs[0].abs())
}
""" + GLUE_RMS,
    # wrong exception behavior: returns 0.0 where the Python raises ValueError
    "f03_empty_returns_zero": """use pyo3::prelude::*;

#[pyfunction]
fn rms(xs: Vec<f64>) -> f64 {
    if xs.is_empty() {
        return 0.0;
    }
    let s: f64 = xs.iter().map(|x| x * x).sum();
    (s / xs.len() as f64).sqrt()
}
""" + GLUE_RMS,
}

WRONG_TUPLE_RET = {
    # wrong value: swapped elements
    "g01_swapped_elements": """use pyo3::prelude::*;

#[pyfunction]
fn sum_pair(xs: Vec<i64>) -> (i64, i64) {
    let s: i64 = xs.iter().sum();
    let q: i64 = xs.iter().map(|x| x * x).sum();
    (q, s)
}
""" + GLUE_SUM_PAIR,
    # wrong TYPE: returns a Python list where the contract is a tuple.
    # Pre-fidelity this FALSE-ACCEPTS (both sides encoded as lists); the v0.8
    # tuple tag in the oracle + verifier must reject it on merits.
    "g02_list_not_tuple": """use pyo3::prelude::*;

#[pyfunction]
fn sum_pair(xs: Vec<i64>) -> Vec<i64> {
    let s: i64 = xs.iter().sum();
    let q: i64 = xs.iter().map(|x| x * x).sum();
    vec![s, q]
}
""" + GLUE_SUM_PAIR,
    # wrong value: ignores the squares entirely
    "g03_wrong_second_element": """use pyo3::prelude::*;

#[pyfunction]
fn sum_pair(xs: Vec<i64>) -> (i64, i64) {
    let s: i64 = xs.iter().sum();
    (s, s)
}
""" + GLUE_SUM_PAIR,
}

TARGETS = [
    # (set, target file, function, wrong battery, domain_guard)
    # divide keeps the guard OFF: its edge battery deliberately straddles the
    # i64 domain ((i64::MIN, -1) -> 2**63) so the battery tests the VERIFIER on
    # merits, not the domain policy. Production runs keep the guard on.
    ("rle_encode", "examples/demo/run_length.py", "rle_encode", WRONG, True),
    ("divide", "examples/demo/divide.py", "divide", WRONG_MULTI, False),
    ("manhattan", "examples/demo/manhattan.py", "manhattan", WRONG_TUPLE, True),
    ("rms", "examples/demo/rms.py", "rms", WRONG_FLOATLIST, True),
    ("sum_pair", "examples/demo/sum_pair.py", "sum_pair", WRONG_TUPLE_RET, True),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60, help="oracle size per candidate")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runs_root = tempfile.mkdtemp(prefix="smelt-meta-")
    results = []
    for set_name, rel_path, func, wrong, domain_guard in TARGETS:
        target = os.path.join(repo, rel_path) + ":" + func
        for name, src in sorted(wrong.items()):
            d = os.path.join(runs_root, name)
            os.makedirs(d, exist_ok=True)
            cand = os.path.join(d, "candidate.rs")
            with open(cand, "w") as f:
                f.write(src)
            code, info = orchestrator.run(target=target, provider_name="file", candidate=cand,
                                          runs_dir=d, max_attempts=1, target_cases=args.cases,
                                          quiet=True, domain_guard=domain_guard)
            rejected = code == 4
            refused = code == 3  # pre-support RED state: a refusal is not a verdict
            results.append({"set": set_name, "wrong": name, "exit_code": code,
                            "rejected": rejected, "refused": refused,
                            "reason": (info.get("stop_reason") or "")[:140]})
            label = "REJECTED ok " if rejected else ("REFUSED red " if refused else "ACCEPTED  !! ")
            print(label + name + f"  (exit {code})", flush=True)
    summary = {"n": len(results),
               "rejected": sum(1 for r in results if r["rejected"]),
               "refused": sum(1 for r in results if r["refused"]),
               "unexpected_accepted": sum(1 for r in results
                                          if not r["rejected"] and not r["refused"])}
    print(json.dumps(summary))
    if args.json:
        print(json.dumps(results, indent=2))
    return 1 if summary["unexpected_accepted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
