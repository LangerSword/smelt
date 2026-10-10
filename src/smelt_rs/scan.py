"""Candidate scanner for the Furnace T3 picker: lists functions with status + reason.

Honest about current capability: single-file targets with one simple-typed
parameter. Relative imports are skipped with a clear reason (package loading is
not supported yet — see evals/general.md BUG-1). This is the minimal scan the
TUI picker needs; the full G3 scan (type tiers, profile hints) is separate.
"""

import ast
import os

from smelt_rs.core import purity

SUPPORTED_PARAMS = {"str", "int", "float", "bool", "list[int]", "list[str]"}
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
            candidates.append({"file": rel, "function": "", "status": "skip",
                               "reason": f"cannot parse: {type(e).__name__}"})
            continue
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        if not funcs:
            continue
        relative = _has_relative_import(tree)
        for fn_node in funcs:
            entry = {"file": rel, "function": fn_node.name, "line": fn_node.lineno}
            if relative:
                entry.update(status="skip",
                             reason="relative imports — package loading not supported yet (BUG-1)")
                candidates.append(entry)
                continue
            reasons = purity.probe(path, fn_node.name)
            if reasons:
                entry.update(status="skip", reason="impure: " + reasons[0])
                candidates.append(entry)
                continue
            args = fn_node.args
            total = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
            if total == 0:
                entry.update(status="skip", reason="no parameters")
                candidates.append(entry)
                continue
            if total > 1 or args.vararg or args.kwarg:
                entry.update(status="skip",
                             reason="multiple parameters (single-parameter build)")
                candidates.append(entry)
                continue
            ann = _ann_str(args.args[0].annotation if args.args else args.posonlyargs[0].annotation)
            if ann not in SUPPORTED_PARAMS:
                entry.update(status="skip",
                             reason=f"unsupported parameter type: {ann or 'unannotated'}")
                candidates.append(entry)
                continue
            entry.update(status="candidate", tier="simple", param=ann,
                         reason=f"one {ann} parameter")
            candidates.append(entry)

    summary = {
        "root": root,
        "files": len(files),
        "functions": len(candidates),
        "candidates": sum(1 for c in candidates if c["status"] == "candidate"),
        "skipped": sum(1 for c in candidates if c["status"] == "skip"),
    }
    return {"summary": summary, "candidates": candidates}
