#!/usr/bin/env python
"""Meta-eval: prove the oracle rejects KNOWN-WRONG rewrites (gate: 10/10 rejected).

Each candidate below is a hand-written rle_encode that is wrong in a different way but
still compiles. Every one must come back REJECTED (verify_mismatch, exit code 4) when
run through the full pipeline against the frozen oracle. If any is accepted, the
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60, help="oracle size per candidate")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(repo, "examples/demo/run_length.py") + ":rle_encode"
    runs_root = tempfile.mkdtemp(prefix="smelt-meta-")
    results = []
    for name, src in sorted(WRONG.items()):
        d = os.path.join(runs_root, name)
        os.makedirs(d, exist_ok=True)
        cand = os.path.join(d, "candidate.rs")
        with open(cand, "w") as f:
            f.write(src)
        code, info = orchestrator.run(target=target, provider_name="file", candidate=cand,
                                      runs_dir=d, max_attempts=1, target_cases=args.cases,
                                      quiet=True)
        rejected = code == 4
        results.append({"wrong": name, "exit_code": code, "rejected": rejected,
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
