"""Static purity probe: refuses targets with side effects or nondeterminism sources.

Conservative by design: refusing a pure function is annoying, accepting an impure one
is dangerous. The refusal message names every reason found, so the fix is obvious.
Reviewed closely by the developer (refusal semantics).
"""

import ast

BLOCKED_MODULES = {
    "os", "io", "sys", "socket", "subprocess", "time", "random", "secrets",
    "threading", "multiprocessing", "asyncio", "tempfile", "shutil", "pathlib",
    "importlib", "http", "urllib", "requests",
}
BLOCKED_CALLS = {"open", "input", "eval", "exec", "compile", "__import__"}


def probe(target_path: str, func_name: str) -> list[str]:
    """Return the list of reasons the target is not a safe pure function ([] = pass)."""
    reasons: list[str] = []
    try:
        with open(target_path) as f:
            tree = ast.parse(f.read(), filename=target_path)
    except SyntaxError as e:
        return [f"cannot parse target: {e}"]

    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            func = node
            break
    if func is None:
        return [f"function {func_name!r} not found in {target_path}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    reasons.append(f"module imports {alias.name!r} (side effects / nondeterminism)")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in BLOCKED_MODULES:
                    reasons.append(f"module imports from {node.module!r}")

    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if name in BLOCKED_CALLS:
                reasons.append(f"function calls {name}()")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            reasons.append("function uses global/nonlocal state")

    return sorted(set(reasons))
