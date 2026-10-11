#!/usr/bin/env python
"""Meta-eval: prove the oracle rejects KNOWN-WRONG rewrites (gate: all rejected).

Three target sets:
  1) rle_encode (single str param) — 10 wrong rewrites, the original battery;
  2) divide (two int params, raises on b==0) — the G1 multi-parameter battery:
     wrong value / wrong exception (returns instead of raising) / panic where the
     Python returns (panics must become Python exceptions, never abort the process);
  3) manhattan (one tuple[int, int] param) — the tuple battery: wrong value
     (no abs), wrong value (ignores the pair's second element), wrong exception.

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

TARGETS = [
    ("rle_encode", "examples/demo/run_length.py", "rle_encode", WRONG),
    ("divide", "examples/demo/divide.py", "divide", WRONG_MULTI),
    ("manhattan", "examples/demo/manhattan.py", "manhattan", WRONG_TUPLE),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60, help="oracle size per candidate")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runs_root = tempfile.mkdtemp(prefix="smelt-meta-")
    results = []
    for set_name, rel_path, func, wrong in TARGETS:
        target = os.path.join(repo, rel_path) + ":" + func
        for name, src in sorted(wrong.items()):
            d = os.path.join(runs_root, name)
            os.makedirs(d, exist_ok=True)
            cand = os.path.join(d, "candidate.rs")
            with open(cand, "w") as f:
                f.write(src)
            code, info = orchestrator.run(target=target, provider_name="file", candidate=cand,
                                          runs_dir=d, max_attempts=1, target_cases=args.cases,
                                          quiet=True)
            rejected = code == 4
            results.append({"set": set_name, "wrong": name, "exit_code": code,
                            "rejected": rejected,
                            "reason": (info.get("stop_reason") or "")[:140]})
            print(("REJECTED ok " if rejected else "ACCEPTED  !! ") + name + f"  (exit {code})",
                  flush=True)
    summary = {"n": len(results),
               "rejected": sum(1 for r in results if r["rejected"]),
               "unexpected_accepted": sum(1 for r in results if not r["rejected"])}
    print(json.dumps(summary))
    if args.json:
        print(json.dumps(results, indent=2))
    return 1 if summary["unexpected_accepted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
