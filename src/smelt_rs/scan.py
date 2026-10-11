"""Candidate scanner for the Furnace T3 picker: lists functions with status + reason.

Honest about current capability: single-file targets with one simple-typed
parameter. Relative imports are skipped with a clear reason (package loading is
not supported yet — see evals/general.md BUG-1). This is the minimal scan the
TUI picker needs; the full G3 scan (type tiers, profile hints) is separate.
"""

import ast
import os

from smelt_rs.core import purity

SUPPORTED_PARAMS = {"str", "int", "float", "bool", "list[int]", "list[str]",
                    "tuple[int, int]"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache",
             ".pytest_cache", "dist", "build", ".tox", "site-packages", ".hermes"}


def _ann_str(node) -> str | None:
    """Render a simple annotation node as a string (first alternative of unions)."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        base = _ann_str(node.value)
        if base == "list":
            inner = _ann_str(node.slice)
            return f"list[{inner}]" if inner else "list"
        if base == "tuple" and isinstance(node.slice, ast.Tuple):
            parts = [p for p in (_ann_str(e) for e in node.slice.elts) if p]
            if parts:
                return f"tuple[{', '.join(parts)}]"
            return "tuple"
        return base
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _ann_str(node.left)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _has_relative_import(tree) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.level or 0) > 0:
            return True
    return False


def scan_path(root: str) -> dict:
    root = os.path.abspath(root)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                files.append(os.path.join(dirpath, fn))

    candidates = []
    for path in sorted(files):
        rel = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
        except (SyntaxError, UnicodeDecodeError) as e:
            candidates.append({"file": rel, "function": "", "status": "skip", "tier": "refused",
                               "reason": f"cannot parse: {type(e).__name__}"})
            continue
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        if not funcs:
            continue
        relative = _has_relative_import(tree)
        for fn_node in funcs:
            entry = {"file": rel, "function": fn_node.name, "line": fn_node.lineno}
            if relative:
                entry.update(status="skip", tier="refused",
                             reason="relative imports — package loading not supported yet (BUG-1)")
                candidates.append(entry)
                continue
            reasons = purity.probe(path, fn_node.name)
            if reasons:
                entry.update(status="skip", tier="refused", reason="impure: " + reasons[0])
                candidates.append(entry)
                continue
            args = fn_node.args
            positional = args.posonlyargs + args.args
            if not positional and not args.kwonlyargs:
                entry.update(status="skip", tier="refused", reason="no parameters")
                candidates.append(entry)
                continue
            if args.vararg or args.kwarg:
                entry.update(status="skip", tier="refused",
                             reason="variadic parameters (*args/**kwargs) are not supported yet")
                candidates.append(entry)
                continue
            if args.kwonlyargs:
                entry.update(status="skip", tier="refused",
                             reason="keyword-only parameters are not supported yet — "
                                    "refactor hint: make them positional")
                candidates.append(entry)
                continue
            anns = [_ann_str(a.annotation) for a in positional]
            bad = [a for a in anns if a not in SUPPORTED_PARAMS]
            if bad:
                entry.update(status="skip", tier="refused",
                             reason=f"unsupported parameter type: {bad[0] or 'unannotated'} — "
                                    "refactor hint: use str/int/float/bool/list[int]/list[str]/tuple[int, int]")
                candidates.append(entry)
                continue
            n = len(positional)
            entry.update(status="candidate", tier="1",
                         param=anns[0] if n == 1 else f"{n} params",
                         reason=(f"one {anns[0]} parameter" if n == 1
                                 else f"{n} simple parameters: {', '.join(anns)}"))
            candidates.append(entry)

    summary = {
        "root": root,
        "files": len(files),
        "functions": len(candidates),
        "candidates": sum(1 for c in candidates if c["status"] == "candidate"),
        "skipped": sum(1 for c in candidates if c["status"] == "skip"),
    }
    return {"summary": summary, "candidates": candidates}
