#!/usr/bin/env python
"""Sandboxed worker: ONE JSON request in on stdin, ONE JSON response out on stdout.

The target function and the generated extension only ever execute in THIS process,
under resource limits. Target stdout is captured and discarded so it can never
corrupt the protocol. Reviewed closely by the developer (sandbox boundary).
"""

import copy
import io
import json
import sys


def _apply_limits() -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))  # 1 GiB address space
        resource.setrlimit(resource.RLIMIT_CPU, (180, 180))  # 180 s CPU
    except Exception:
        pass  # limits unavailable (non-POSIX) -> proceed; caller still has wall timeouts


def _norm_ann(ann) -> str | None:
    import inspect
    if ann is inspect.Parameter.empty or ann is None:
        return None
    if isinstance(ann, type):
        return ann.__name__  # str / int / float / bool
    s = ann if isinstance(ann, str) else str(ann)
    return s.replace("typing.", "").replace("List", "list").replace("Dict", "dict")


def _load_fn(req: dict):
    import importlib.util
    import os
    side = req.get("side", "python")
    if side == "python":
        path = req["target_path"]
        sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
        spec = importlib.util.spec_from_file_location(req["module"], path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, req["func"])
    spec = importlib.util.spec_from_file_location("smelt_ext", req["so_path"])
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, req["func"])


def _enc(v, depth: int = 0) -> dict:
    if depth > 6:
        return {"t": "repr", "v": repr(v)}
    if v is None:
        return {"t": "none"}
    if isinstance(v, bool):
        return {"t": "bool", "v": v}
    if isinstance(v, int):
        return {"t": "int", "v": v}
    if isinstance(v, float):
        if v != v:
            return {"t": "float", "v": "nan"}
        if v == float("inf"):
            return {"t": "float", "v": "inf"}
        if v == float("-inf"):
            return {"t": "float", "v": "-inf"}
        return {"t": "float", "v": v}
    if isinstance(v, str):
        return {"t": "str", "v": v}
    if isinstance(v, (list, tuple)):
        return {"t": "list", "v": [_enc(x, depth + 1) for x in v]}
    if isinstance(v, dict):
        return {"t": "dict", "v": {str(k): _enc(x, depth + 1) for k, x in v.items()}}
    return {"t": "repr", "v": repr(v)}


def main() -> None:
    _apply_limits()
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()  # target output must never corrupt the protocol
    try:
        req = json.loads(sys.stdin.read())
        mode = req["mode"]
        out: dict = {"ok": True}
        if mode == "introspect":
            import inspect
            fn = _load_fn(req)
            sig = inspect.signature(fn)
            params = []
            for name, p in sig.parameters.items():
                params.append({"name": name, "annotation": _norm_ann(p.annotation),
                               "default": None if p.default is inspect.Parameter.empty else repr(p.default)})
            ret = None if sig.return_annotation is inspect.Signature.empty else _norm_ann(sig.return_annotation)
            out["params"] = params
            out["return_annotation"] = ret
        elif mode == "run":
            fn = _load_fn(req)
            results = []
            for case in req["cases"]:
                args = case.get("args", [])
                kwargs = case.get("kwargs", {})
                snap_a = copy.deepcopy(args)
                snap_k = copy.deepcopy(kwargs)
                try:
                    val = fn(*args, **kwargs)
                    rec = {"id": case["case_id"], "ok": True, "out": _enc(val)}
                except Exception as e:
                    rec = {"id": case["case_id"], "ok": False,
                           "err": f"{type(e).__name__}: {str(e)[:200]}"}
                if req.get("check_mutation") and (args != snap_a or kwargs != snap_k):
                    rec["mutated"] = True
                results.append(rec)
            out["results"] = results
        elif mode in ("time_once", "bench"):
            import time
            fn = _load_fn(req)
            cases = req["cases"]
            reps = 1 if mode == "time_once" else int(req["reps"])
            durations = []
            for _ in range(reps):
                t0 = time.perf_counter()
                for case in cases:
                    fn(*case.get("args", []), **case.get("kwargs", {}))
                durations.append(time.perf_counter() - t0)
            if mode == "time_once":
                out["duration"] = durations[0]
            else:
                out["durations"] = durations
        else:
            out = {"ok": False, "error": f"unknown mode {mode!r}"}
    except Exception as e:  # top-level: report, never crash raw
        out = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:400]}"}
    real_stdout.write(json.dumps(out))
    real_stdout.flush()


if __name__ == "__main__":
    main()
