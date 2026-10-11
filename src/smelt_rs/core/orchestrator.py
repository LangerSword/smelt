"""Orchestrator: the deterministic core loop.

select -> capture oracle -> (generate -> scan -> build -> verify)* -> bench -> decide -> report

The model only acts inside `generate`; every other decision is code. Every transition is
checkpointed (state.json + events.jsonl), so runs can resume. Reviewed closely by the
developer (acceptance, refusal, and retry semantics live here).
"""

import ast
import json
import math
import os
import sys
import time

from smelt_rs.bench.protocol import WARMUP, decide, median_and_ci, suspicious_scaling, timer_limited
from smelt_rs.build.cargo import build_crate
from smelt_rs.core import purity
from smelt_rs.core.failures import (BenchInsufficient, BudgetExhausted, BuildError, ConfigError,
                                    OracleTampered, ProviderError, RefusedImpure, RefusedTarget,
                                    SafetyViolation,
                                    SmeltFailure, TargetChanged, VerifyCrash)
from smelt_rs.core.state import EventLog, SMELT_VERSION, RunState, new_run_id, sha256_file
from smelt_rs.oracle.capture import capture_oracle, load_oracle
from smelt_rs.oracle.verify import compare
from smelt_rs.providers.providers import build_candidate_prompt, make_provider, map_signature
from smelt_rs.report import write_report
from smelt_rs.scaffold.templates import GOLDEN_LIB_RS
from smelt_rs.worker_client import run_worker

BENCH_REPS = 10
BENCH_MULT_CAP = 240
SCALE_FACTOR = 4
EXIT_CODES = {"accepted": 0, "refused": 3, "rejected": 4, "error": 5}


# ---------------------------------------------------------------- helpers

def parse_target(spec: str):
    path, _, func = spec.partition(":")
    if not path or not func:
        raise ConfigError("target must look like path/to/file.py:function")
    return os.path.abspath(path), func


def extract_function_source(path: str, func_name: str) -> str:
    src = open(path).read()
    tree = ast.parse(src, filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            seg = ast.get_source_segment(src, node)
            if seg:
                return seg
    return src


def _load_entries(run_dir: str) -> list:
    with open(os.path.join(run_dir, "oracle", "oracle.jsonl")) as f:
        return [json.loads(line) for line in f]


def _target_dir() -> str:
    d = os.environ.get("SMELT_TARGET_DIR", os.path.expanduser("~/.cache/smelt/target"))
    os.makedirs(d, exist_ok=True)
    return d


def _finish(run_dir: str, st: RunState, events: EventLog, bench) -> None:
    write_report(run_dir, {
        "run_id": st.run_id,
        "target": st.target,
        "provider": {"name": st.config.get("provider", "?"), "model": st.config.get("model")},
        "oracle": st.oracle,
        "attempts": st.attempts,
        "bench": bench,
        "outcome": {"status": st.status, "reason": st.stop_reason},
    })
    events.emit("run_end", status=st.status, reason=st.stop_reason[:300])
    st.save(run_dir)


REFUSED_KINDS = {"refused_impure", "refused_unsupported_target"}


def _exit_for_kind(kind: str) -> int:
    if kind in REFUSED_KINDS:
        return 3
    if kind == "config_error":
        return 2
    return 5


def _halt(st, run_dir, events, e: SmeltFailure, quiet: bool = False) -> int:
    status = "refused" if e.kind in REFUSED_KINDS else (
        "config_error" if e.kind == "config_error" else "error")
    if st is not None:
        st.status = status
        st.stop_reason = f"{e.kind}: {e.message}"
        if run_dir and events:
            events.emit("halt", kind=e.kind, message=e.message[:300])
            _finish(run_dir, st, events, None)
    if not quiet:
        print(f"[smelt] {status}: {e.kind}: {e.message}")
    return _exit_for_kind(e.kind)


def _purity_failure(reasons: list[str]) -> None:
    """Raise the right typed failure for purity-probe reasons: a not-found target
    is a config problem (with a hint); everything else is an impurity refusal."""
    not_found = [r for r in reasons if "not found" in r]
    impure = [r for r in reasons if "not found" not in r]
    if not_found and not impure:
        raise ConfigError(
            not_found[0] + " — dotted qualnames (Class.method) are not supported yet; "
            "refactor hint: point smelt at a module-level function (split the method "
            "out if needed)")
    raise RefusedImpure("impure target: " + "; ".join((impure or not_found)[:4]),
                        details="; ".join(reasons))


def _run_info(run_dir, st) -> dict:
    info: dict = {"run_dir": run_dir, "status": st.status if st else "error"}
    if st is not None:
        info.update({"run_id": st.run_id, "stop_reason": st.stop_reason,
                     "target": st.target, "oracle": st.oracle, "attempts": st.attempts,
                     "config": st.config})
        if run_dir:
            bench_path = os.path.join(run_dir, "bench.json")
            if os.path.exists(bench_path):
                try:
                    info["bench"] = json.load(open(bench_path))
                except Exception:
                    pass
    return info


# ---------------------------------------------------------------- entry points

def run(*, target: str, provider_name: str, model: str | None = None, candidate: str | None = None,
        runs_dir: str = "runs", max_attempts: int = 3, target_cases: int = 200,
        seed: int | None = None, bench_min_s: float = 0.1, python_exe: str | None = None,
        quiet: bool = False) -> tuple[int, dict]:
    python_exe = python_exe or sys.executable
    st = None
    run_dir = None
    events = None
    try:
        path, func = parse_target(target)
        if not os.path.exists(path):
            raise ConfigError(f"target file not found: {path}")
        os.makedirs(runs_dir, exist_ok=True)
        run_id = new_run_id(path, func)
        run_dir = os.path.join(runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        events = EventLog(os.path.join(run_dir, "events.jsonl"))
        st = RunState(run_id=run_id, created_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                      smelt_version=SMELT_VERSION,
                      target={"path": path, "qualname": func, "source_sha256": sha256_file(path)},
                      oracle={},
                      config={"provider": provider_name, "model": model,
                              "max_attempts": max_attempts, "cases": target_cases,
                              "bench_min_s": bench_min_s})
        st.save(run_dir)
        events.emit("run_start", target=f"{path}:{func}", provider=provider_name, model=model or "-")
        if not quiet:
            print(f"[smelt] run {run_id} · {path}:{func} · provider={provider_name}")
        code = _drive(st, run_dir, events, path, func, provider_name, model, candidate,
                      max_attempts, target_cases, seed, bench_min_s, python_exe, quiet)
        if not quiet:
            print(f"[smelt] {st.status.upper()}: {st.stop_reason}")
        return code, _run_info(run_dir, st)
    except ConfigError as e:
        if not quiet:
            print(f"[smelt] config error: {e.message}")
        return 2, {"status": "config_error", "reason": e.message}
    except SmeltFailure as e:
        code = _halt(st, run_dir, events, e, quiet)
        return code, _run_info(run_dir, st)
    except Exception as e:
        code = _halt(st, run_dir, events, SmeltFailure(f"internal error: {e!r}"), quiet)
        return code, _run_info(run_dir, st)


def resume(*, run_dir: str, max_attempts: int = 3, python_exe: str | None = None,
           quiet: bool = False) -> tuple[int, dict]:
    python_exe = python_exe or sys.executable
    st = None
    events = None
    try:
        st = RunState.load(run_dir)
        events = EventLog(os.path.join(run_dir, "events.jsonl"))
        if st.status != "in_progress":
            raise ConfigError(f"run is not resumable (status={st.status})")
        entries, meta, h = load_oracle(os.path.join(run_dir, "oracle"))
        if h != st.oracle.get("sha256"):
            raise OracleTampered("oracle hash changed since checkpoint")
        if sha256_file(st.target["path"]) != st.target["source_sha256"]:
            raise TargetChanged("target file changed since checkpoint")
        events.emit("resume", from_attempt=len(st.attempts) + 1)
        args_rs, ret_rs, sig_err = map_signature(meta["params"], meta.get("return_annotation"))
        if sig_err:
            raise ConfigError(f"cannot map signature to Rust: {sig_err}")
        prompt = build_candidate_prompt(func_name=st.target["qualname"],
                                        py_source=extract_function_source(st.target["path"], st.target["qualname"]),
                                        args_rs=args_rs, ret_rs=ret_rs, golden=GOLDEN_LIB_RS)
        provider = make_provider(st.config.get("provider", "local"), st.config.get("model"), None, run_dir)
        code = _loop(st, run_dir, events, st.target["path"], meta["module"], st.target["qualname"],
                     provider, prompt, entries, python_exe,
                     float(st.config.get("bench_min_s", 0.1)), max_attempts)
        if not quiet:
            print(f"[smelt] {st.status.upper()}: {st.stop_reason}")
        return code, _run_info(run_dir, st)
    except ConfigError as e:
        if not quiet:
            print(f"[smelt] config error: {e.message}")
        return 2, {"status": "config_error", "reason": e.message}
    except SmeltFailure as e:
        code = _halt(st, run_dir, events, e, quiet)
        return code, _run_info(run_dir, st)
    except Exception as e:
        code = _halt(st, run_dir, events, SmeltFailure(f"internal error: {e!r}"), quiet)
        return code, _run_info(run_dir, st)


# ---------------------------------------------------------------- pipeline stages

def _drive(st, run_dir, events, path, func, provider_name, model, candidate,
           max_attempts, target_cases, seed, bench_min_s, python_exe, quiet: bool = False) -> int:
    reasons = purity.probe(path, func)
    if reasons:
        _purity_failure(reasons)
    events.emit("purity_ok")

    seeded = seed if seed is not None else int(time.time_ns() % (10 ** 9))
    module_name = os.path.splitext(os.path.basename(path))[0]
    meta, oh = capture_oracle(run_dir=run_dir, target_path=path, module_name=module_name,
                              func_name=func, python_exe=python_exe,
                              target_cases=target_cases, seed=seeded)
    st.oracle = {"dir": "oracle", "sha256": oh, "n_cases": meta["n_cases"], "seed": seeded}
    st.save(run_dir)
    events.emit("capture_done", n_cases=meta["n_cases"], sha256=oh[:16])
    if not quiet:
        print(f"[smelt] oracle captured: {meta['n_cases']} cases (sha {oh[:12]}…)")

    entries = _load_entries(run_dir)
    args_rs, ret_rs, sig_err = map_signature(meta["params"], meta.get("return_annotation"))
    if sig_err:
        raise ConfigError(f"cannot map signature to Rust: {sig_err}")
    assert args_rs is not None and ret_rs is not None
    prompt = build_candidate_prompt(func_name=func, py_source=extract_function_source(path, func),
                                    args_rs=args_rs, ret_rs=ret_rs, golden=GOLDEN_LIB_RS)
    provider = make_provider(provider_name, model, candidate, run_dir)
    return _loop(st, run_dir, events, path, module_name, func, provider, prompt, entries,
                 python_exe, bench_min_s, max_attempts)


def _loop(st, run_dir, events, path, module_name, func, provider, prompt, entries,
          python_exe, bench_min_s, max_attempts) -> int:
    start = len(st.attempts) + 1
    bench_result = None
    for attempt_no in range(start, max_attempts + 1):
        events.emit("attempt_start", attempt=attempt_no)
        attempt_dir = os.path.join(run_dir, "attempts", f"it{attempt_no}")
        os.makedirs(attempt_dir, exist_ok=True)
        rec = {"attempt": attempt_no, "source": provider.name}
        try:
            texts = provider.generate(prompt, n=1)
        except ProviderError as e:
            rec.update(build="-", verify="-", bench="-", outcome=f"provider_error: {e.message[:120]}")
            st.attempts.append(rec)
            st.save(run_dir)
            raise
        if not texts:
            rec.update(build="-", verify="-", bench="-", outcome="budget_exhausted: no candidate returned")
            st.attempts.append(rec)
            st.save(run_dir)
            raise BudgetExhausted("provider ran out of candidates")
        lib_rs = texts[0]
        with open(os.path.join(attempt_dir, "lib.rs"), "w") as f:
            f.write(lib_rs)

        # build (safety scan happens inside)
        try:
            so = build_crate(build_dir=os.path.join(attempt_dir, "build"), lib_rs=lib_rs,
                             func_name=func, python_exe=python_exe, target_dir=_target_dir())
        except SafetyViolation as e:
            rec.update(build="safety_violation", verify="-", bench="-",
                       outcome="safety_violation: " + e.message[:140])
            st.attempts.append(rec)
            st.save(run_dir)
            events.emit("safety_violation", attempt=attempt_no)
            continue
        except BuildError as e:
            rec.update(build=f"build_error({e.subkind})", verify="-", bench="-",
                       outcome=f"build_error[{e.subkind}]: {e.message[:100]}")
            st.attempts.append(rec)
            st.save(run_dir)
            events.emit("build_error", attempt=attempt_no, subkind=e.subkind)
            continue
        rec["build"] = "ok"

        # verify against the frozen oracle
        wreq = {"mode": "run", "side": "rust", "so_path": so, "func": func,
                "cases": [{"case_id": e["case_id"], "args": e["args"], "kwargs": e["kwargs"]}
                          for e in entries]}
        try:
            wres = run_worker(python_exe, wreq, timeout=300)
        except VerifyCrash as e:
            rec.update(verify="worker_crash", bench="-", outcome=f"verify_crash: {e.message[:100]}")
            st.attempts.append(rec)
            st.save(run_dir)
            continue
        if not wres.get("ok") or "results" not in wres:
            rec.update(verify=f"load_error: {str(wres.get('error'))[:110]}", bench="-",
                       outcome="verify_crash")
            st.attempts.append(rec)
            st.save(run_dir)
            continue
        n_bad, sample = compare(entries, wres["results"])
        with open(os.path.join(attempt_dir, "verify.json"), "w") as f:
            json.dump({"n_cases": len(entries), "n_mismatch": n_bad, "sample": sample}, f, indent=2)
        if n_bad:
            first = sample[0] if sample else {}
            rec.update(verify=f"mismatch {n_bad}/{len(entries)}", bench="-",
                       outcome=f"verify_mismatch: {first.get('case_id', '?')} {first.get('why', '')}")
            st.attempts.append(rec)
            st.save(run_dir)
            events.emit("verify_mismatch", attempt=attempt_no, n_bad=n_bad)
            continue
        rec["verify"] = f"pass {len(entries)}/{len(entries)}"

        # bench + decide
        try:
            bench_result = _bench(python_exe=python_exe, path=path, module_name=module_name,
                                  so=so, func=func, entries=entries, bench_min_s=bench_min_s,
                                  run_dir=run_dir, attempt_dir=attempt_dir)
        except SmeltFailure as e:
            rec.update(bench="-", outcome=f"{e.kind}: {e.message[:100]}")
            st.attempts.append(rec)
            st.save(run_dir)
            continue
        dec = bench_result["decision"]
        rec["bench"] = f"{bench_result['ratio']:.2f}x (lb {bench_result['ratio_ci_lo']:.2f}x)"
        if dec == "accept":
            rec["outcome"] = "ACCEPTED"
            st.attempts.append(rec)
            st.status = "accepted"
            st.stop_reason = (f"verified {len(entries)}/{len(entries)} cases; "
                              f"speedup {bench_result['ratio']:.2f}x "
                              f"(conservative lower bound {bench_result['ratio_ci_lo']:.2f}x)")
            events.emit("accept", ratio=bench_result["ratio"],
                        ratio_ci_lo=bench_result["ratio_ci_lo"], flags=bench_result.get("flags", []))
            _finish(run_dir, st, events, bench_result)
            return EXIT_CODES["accepted"]
        rec["outcome"] = (f"{dec}: ratio {bench_result['ratio']:.2f}x, "
                          f"lower bound {bench_result['ratio_ci_lo']:.2f}x")
        st.attempts.append(rec)
        st.save(run_dir)
        events.emit(dec, ratio=bench_result["ratio"])

    st.status = "rejected"
    last = st.attempts[-1].get("outcome", "") if st.attempts else "no attempts completed"
    st.stop_reason = f"no candidate accepted within {max_attempts} attempt(s); last: {last[:160]}"
    _finish(run_dir, st, events, bench_result)
    return EXIT_CODES["rejected"]


def _bench(*, python_exe, path, module_name, so, func, entries, bench_min_s, run_dir, attempt_dir) -> dict:
    cases = [{"case_id": e["case_id"], "args": e["args"], "kwargs": e["kwargs"]} for e in entries]

    py_once = run_worker(python_exe, {"mode": "time_once", "side": "python", "target_path": path,
                                      "module": module_name, "func": func, "cases": cases}, timeout=180)
    if not py_once.get("ok"):
        raise BenchInsufficient(f"python timing failed: {py_once.get('error')}")
    mult = max(1, min(BENCH_MULT_CAP, int(math.ceil(bench_min_s / max(py_once["duration"], 1e-9)))))
    workload = cases * mult

    def bench(side: str, wl: list, reps: int, timeout: int) -> list:
        req = {"mode": "bench", "side": side, "func": func, "cases": wl, "reps": reps}
        if side == "python":
            req.update({"target_path": path, "module": module_name})
        else:
            req["so_path"] = so
        res = run_worker(python_exe, req, timeout=timeout)
        if not res.get("ok"):
            raise BenchInsufficient(f"{side} bench failed: {res.get('error')}")
        return res["durations"]

    py = bench("python", workload, BENCH_REPS, 900)[WARMUP:]
    ru = bench("rust", workload, BENCH_REPS, 900)[WARMUP:]
    py_med, py_lo, py_hi = median_and_ci(py)
    ru_med, ru_lo, ru_hi = median_and_ci(ru)
    if ru_med <= 0:
        raise BenchInsufficient("rust median not measurable")
    ratio = py_med / ru_med
    ratio_ci_lo = py_lo / ru_med

    workload4 = cases * mult * SCALE_FACTOR
    py4 = bench("python", workload4, 5, 1200)[2:]
    ru4 = bench("rust", workload4, 5, 900)[2:]
    ru4_med = median_and_ci(ru4)[0]
    ratio4 = (median_and_ci(py4)[0] / ru4_med) if ru4_med > 0 else ratio

    flags = []
    if ratio > 100 and suspicious_scaling(ratio, ratio4):
        flags.append("suspicious_scaling")
    if timer_limited(ru_med):
        flags.append("timer_limited")

    decision = decide(ratio, ratio_ci_lo)
    summary = {"python_med_s": py_med, "python_ci_lo_s": py_lo, "python_ci_hi_s": py_hi,
               "rust_med_s": ru_med, "rust_ci_lo_s": ru_lo, "rust_ci_hi_s": ru_hi,
               "ratio": ratio, "ratio_ci_lo": ratio_ci_lo, "ratio_scaled_4x": ratio4,
               "flags": flags, "decision": decision, "workload_cases": len(workload),
               "reps": BENCH_REPS, "warmup": WARMUP}
    with open(os.path.join(attempt_dir, "bench.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(run_dir, "bench.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


# ---------------------------------------------------------------- capture-only mode

def capture_only(*, target: str, runs_dir: str = "runs", target_cases: int = 200,
                 seed: int | None = None, python_exe: str | None = None,
                 quiet: bool = False) -> tuple[int, dict]:
    """Freeze the oracle for a target without any generation or build."""
    python_exe = python_exe or sys.executable
    st = None
    run_dir = None
    events = None
    try:
        path, func = parse_target(target)
        if not os.path.exists(path):
            raise ConfigError(f"target file not found: {path}")
        os.makedirs(runs_dir, exist_ok=True)
        run_id = new_run_id(path, func)
        run_dir = os.path.join(runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        events = EventLog(os.path.join(run_dir, "events.jsonl"))
        st = RunState(run_id=run_id, created_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                      smelt_version=SMELT_VERSION,
                      target={"path": path, "qualname": func, "source_sha256": sha256_file(path)},
                      oracle={}, config={"provider": "-", "model": None, "max_attempts": 0,
                                         "cases": target_cases, "bench_min_s": None})
        st.save(run_dir)
        reasons = purity.probe(path, func)
        if reasons:
            _purity_failure(reasons)
        seeded = seed if seed is not None else int(time.time_ns() % (10 ** 9))
        module_name = os.path.splitext(os.path.basename(path))[0]
        meta, oh = capture_oracle(run_dir=run_dir, target_path=path, module_name=module_name,
                                  func_name=func, python_exe=python_exe,
                                  target_cases=target_cases, seed=seeded)
        st.oracle = {"dir": "oracle", "sha256": oh, "n_cases": meta["n_cases"], "seed": seeded}
        st.status = "captured"
        st.stop_reason = f"oracle captured: {meta['n_cases']} cases"
        events.emit("capture_done", n_cases=meta["n_cases"], sha256=oh[:16])
        st.save(run_dir)
        if not quiet:
            print(f"[smelt] oracle captured: {meta['n_cases']} cases · {run_dir}/oracle "
                  f"(sha {oh[:12]}…)")
        return 0, _run_info(run_dir, st)
    except ConfigError as e:
        if not quiet:
            print(f"[smelt] config error: {e.message}")
        if st is not None and run_dir and events:
            st.status = "config_error"
            st.stop_reason = f"{e.kind}: {e.message}"
            events.emit("halt", kind=e.kind, message=e.message[:300])
            _finish(run_dir, st, events, None)
        return 2, {"status": "config_error", "reason": e.message}
    except SmeltFailure as e:
        if not quiet:
            print(f"[smelt] {e.kind}: {e.message}")
        return _exit_for_kind(e.kind), {"status": e.kind, "reason": e.message}
    except Exception as e:
        if not quiet:
            print(f"[smelt] internal error: {e!r}")
        return 5, {"status": "error", "reason": repr(e)[:200]}
