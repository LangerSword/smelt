"""Provider layer: thin, fake-able, transcript-logged.

One clean interface (`generate(prompt) -> list[str]` of complete lib.rs contents).
The `file` provider injects hand-written candidates (tests, gate checks, meta-eval).
The `local` provider talks to any OpenAI-compatible server (llama.cpp now; DigitalOcean
Inference `gemma-4-31B-it` later — same code path, different base URL + key).

No provider may see secrets beyond its own API key; transcripts log sizes/usage only.
"""

import glob
import json
import os
import urllib.request

from smelt_rs.core.failures import ProviderError

RUST_ARG_TYPES = {"str": "&str", "int": "i64", "float": "f64", "bool": "bool"}
RUST_RET_TYPES = {"str": "String", "int": "i64", "float": "f64", "bool": "bool"}


def map_signature(params: list[dict], ret: str | None):
    """Map Python annotations to Rust types. Returns (args_rs, ret_rs, error)."""
    args: list[str] = []
    for p in params:
        ann = p.get("annotation") or ""
        t = RUST_ARG_TYPES.get(ann)
        if t is None:
            return None, None, f"unsupported parameter type: {p['name']}: {ann!r}"
        args.append(f"{p['name']}: {t}")
    rt = RUST_RET_TYPES.get(ret or "")
    if rt is None:
        return None, None, f"unsupported return type: {ret!r} (annotate the function)"
    return args, rt, None


def build_candidate_prompt(*, func_name: str, py_source: str, args_rs: list[str], ret_rs: str,
                           golden: str) -> str:
    sig = ", ".join(args_rs)
    return f"""You are writing a Rust extension module (pyo3) that must behave EXACTLY like the given Python function for every input in the tested domain.

Python function (the behavioral contract):
```python
{py_source}
```

Write the complete content of src/lib.rs for a crate named `smelt_ext` that compiles against this golden example (same pyo3 API and structure):

```rust
{golden}
```

Requirements:
- Export exactly one function named `{func_name}` with this Rust signature: `fn {func_name}({sig}) -> {ret_rs}`.
- Keep the `#[pymodule] fn smelt_ext(...)` glue exactly like the golden example, calling `wrap_pyfunction!({func_name}, m)?`.
- Only the `pyo3` crate and Rust std. No unsafe. No build scripts. No file, network, or process access.
- Behavior must match the Python function for all tested inputs, including edge cases (empty input, repeated characters, unicode).
- Reply with ONLY the content of src/lib.rs. No explanation, no markdown fences."""


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


def extract_lib_rs(text: str) -> str:
    t = strip_fences(text)
    i = t.find("use pyo3")
    return t[i:] if i > 0 else t


class FileProvider:
    """Candidates read from file(s). Used for hand-injected rewrites and fixtures."""

    name = "file"

    def __init__(self, paths: list[str]):
        self.paths = paths

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        return [open(p).read() for p in self.paths[:n]]


class LocalOpenAIProvider:
    """Any OpenAI-compatible chat-completions server."""

    name = "local"

    def __init__(self, base_url: str = "http://127.0.0.1:8080/v1",
                 model: str = "gemma-4-e2b-qat", api_key: str | None = None,
                 timeout: int = 300, transcript_path: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key or os.environ.get("SMELT_PROVIDER_KEY")
        self.timeout = timeout
        self.transcript_path = transcript_path

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        return [self._one(prompt) for _ in range(n)]

    def _one(self, prompt: str) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2400,
            "temperature": 0.2,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.base_url + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                d = json.loads(r.read())
        except Exception as e:  # surface, don't swallow
            raise ProviderError(f"provider call failed: {e!r}")
        text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        if self.transcript_path:
            os.makedirs(os.path.dirname(self.transcript_path), exist_ok=True)
            with open(self.transcript_path, "a") as f:
                f.write(json.dumps({"model": self.model, "prompt_chars": len(prompt),
                                    "response_chars": len(text),
                                    "usage": d.get("usage", {})}) + "\n")
        if not text.strip():
            raise ProviderError("empty completion from provider")
        return extract_lib_rs(text)


def make_provider(name: str, model: str | None, candidate: str | None, run_dir: str | None):
    if name == "file":
        if not candidate:
            raise ProviderError("the 'file' provider needs --candidate PATH")
        paths = sorted(glob.glob(candidate)) if any(c in candidate for c in "*?[") else [candidate]
        if not paths:
            raise ProviderError(f"no candidate files match {candidate!r}")
        return FileProvider(paths)
    if name in ("local", "openai"):
        base = os.environ.get("SMELT_LOCAL_BASE", "http://127.0.0.1:8080/v1")
        tp = os.path.join(run_dir, "transcripts", "provider.jsonl") if run_dir else None
        return LocalOpenAIProvider(base_url=base, model=model or "gemma-4-e2b-qat",
                                   transcript_path=tp)
    raise ProviderError(f"unknown provider {name!r} (use 'local' or 'file')")
