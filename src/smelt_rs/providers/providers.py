"""Provider layer: thin, fake-able, transcript-logged, model-agnostic.

One interface: `generate(prompt) -> list[str]` (complete lib.rs contents).

Providers (v0.8: no model family is hardwired — Gemma defaults were removed):
- nvidia   — NVIDIA NIM, OpenAI-compatible (https://integrate.api.nvidia.com/v1), key: NVIDIA_API_KEY
- gemini   — Google AI Studio, native REST (model required), key: GEMINI_API_KEY / GOOGLE_API_KEY
- do       — DigitalOcean Inference, OpenAI-compatible (model required), key: DIGITALOCEAN_TOKEN
- local    — llama.cpp / any OpenAI-compatible server (default http://127.0.0.1:8080/v1)
- openai   — generic OpenAI-compatible (SMELT_OPENAI_BASE, default https://api.openai.com/v1;
             key: SMELT_OPENAI_KEY -> OPENAI_API_KEY; model required)
- file     — hand-provided candidates (gate checks, fixtures)
- fake     — like file, for CI usage without any model

Model resolution: --model -> SMELT_MODEL -> SMELT_<PROVIDER>_MODEL -> provider default
(only nvidia and local ship a default; the rest require an explicit model).
Default provider resolution (when --provider is omitted): SMELT_PROVIDER -> first
provider whose key exists (nvidia, gemini, openai, do) -> local.

All HTTP goes through one retrying poster (3 retries, exponential backoff + jitter,
honors Retry-After on 429/5xx). Transcripts log model + sizes + usage only — never keys.
Secrets resolve from: environment -> project .env -> ~/.hermes/.env (never printed).
"""

import glob
import json
import os
import random
import time
import urllib.error
import urllib.request

from smelt_rs.core.failures import ProviderError

RUST_ARG_TYPES = {"str": "&str", "int": "i64", "float": "f64", "bool": "bool",
                  "list[int]": "Vec<i64>", "list[str]": "Vec<String>",
                  "list[float]": "Vec<f64>",
                  "tuple[int, int]": "(i64, i64)", "tuple[int,int]": "(i64, i64)"}
RUST_RET_TYPES = {"str": "String", "int": "i64", "float": "f64", "bool": "bool",
                  "list[int]": "Vec<i64>", "list[str]": "Vec<String>",
                  "list[float]": "Vec<f64>",
                  "tuple[int, int]": "(i64, i64)", "tuple[int,int]": "(i64, i64)"}

RETRY_STATUS = (429, 500, 502, 503, 504)

# Process-local provider-call counter (the eval runner caps + reports these).
CALLS: dict = {"attempts": 0, "ok": 0, "by_model": {}}


def _count_call(kind: str, model: str | None) -> None:
    if kind == "attempt":
        CALLS["attempts"] += 1
    elif kind == "ok":
        CALLS["ok"] += 1
        if model:
            CALLS["by_model"][model] = CALLS["by_model"].get(model, 0) + 1


# ------------------------------------------------------------------ secrets

def _parse_env_file(path: str) -> dict:
    vals: dict[str, str] = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return vals


_ENV_FILES_CACHE: dict | None = None


def _env_files_values() -> dict:
    global _ENV_FILES_CACHE
    if _ENV_FILES_CACHE is None:
        merged: dict[str, str] = {}
        merged.update(_parse_env_file(os.path.expanduser("~/.hermes/.env")))
        merged.update(_parse_env_file(os.path.join(os.getcwd(), ".env")))
        _ENV_FILES_CACHE = merged
    return _ENV_FILES_CACHE


def resolve_secret(*names: str) -> str | None:
    """First match wins: real env, then project .env, then ~/.hermes/.env. Never logged."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    vals = _env_files_values()
    for n in names:
        v = vals.get(n)
        if v:
            return v
    return None


# ------------------------------------------------------------------ prompt + extraction

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
- Reply with ONLY the content of src/lib.rs. No explanation, no markdown fences.

Semantic fidelity (the divergence traps that fail verification most often):
- Python ints are arbitrary precision; the tested domain is i64. Python `//` floors toward negative infinity and `%` takes the divisor's sign; Rust `/` truncates toward zero and `%` takes the dividend's sign. When the Python uses `//` or `%` on possibly-negative values, adjust the Rust result to floor semantics.
- Python str iterates Unicode code points; Rust &str is UTF-8 bytes. Use `.chars()` (never `.bytes()`) when the Python iterates or indexes characters.
- Where the Python raises, return `Err(...)` (any pyo3 exception type is fine); where the Python returns a value, never panic and never return Err.
- Match the return container exactly: a Rust tuple `(a, b)` becomes a Python tuple; `Vec<T>` becomes a Python list. They are NOT interchangeable."""


def build_repair_prompt(base_prompt: str, feedback: dict) -> str:
    """Attempt 2+ prompt: the base contract plus EVIDENCE from the failed attempt.

    feedback kinds: build_error (rustc stderr), safety_violation (scan findings),
    verify_mismatch (failing cases: args, expected, got), no_gain (measured ratio).
    The gates never change — only the information the model gets does.
    """
    kind = feedback.get("kind", "")
    parts = [base_prompt, "", "---",
             "REPAIR: your previous attempt (reproduced at the end) failed. "
             "Fix the specific problem below and reply with ONLY the complete corrected src/lib.rs."]
    if kind == "build_error":
        parts.append("The Rust compiler rejected it:\n```\n"
                     + str(feedback.get("stderr", ""))[-3000:] + "\n```")
    elif kind == "safety_violation":
        parts.append("The static safety scan rejected it: "
                     + "; ".join(feedback.get("violations", []))
                     + ". Only pyo3 + Rust std are allowed; no unsafe, no fs/net/process access.")
    elif kind == "verify_mismatch":
        sample = (feedback.get("sample") or [])[:5]
        parts.append(f"It compiled, but {feedback.get('n_bad')} of {feedback.get('n_cases')} "
                     "recorded oracle cases differ from the Python original. Failing cases "
                     "(args, expected vs got — encoded values):\n```json\n"
                     + json.dumps(sample, indent=1)[:3000] + "\n```\n"
                     "Match the Python behavior on these cases AND keep every other case correct.")
    elif kind == "load_error":
        parts.append("It failed to load or run in the sandbox worker: "
                     + str(feedback.get("error", ""))[:1000]
                     + ". The module must import cleanly and the function must not abort the process.")
    elif kind == "no_gain":
        parts.append(f"It verified 100% of cases but measured only {feedback.get('ratio', 0):.2f}x "
                     f"(conservative lower bound {feedback.get('ratio_ci_lo', 0):.2f}x); acceptance "
                     "needs lower bound >= 1.5x. Keep behavior IDENTICAL and make it faster: avoid "
                     "per-item allocations, batch work, use slices/iterators instead of collecting "
                     "where possible. Do not change what the function computes.")
    parts.append("Previous attempt:\n```rust\n"
                 + str(feedback.get("candidate", ""))[:20000] + "\n```")
    return "\n".join(parts)


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


# ------------------------------------------------------------------ HTTP plumbing

def _log_transcript(path: str | None, model: str | None, prompt_chars: int, d: dict) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({
            "model": model, "prompt_chars": prompt_chars,
            "usage": d.get("usage") or d.get("usageMetadata") or {},
        }) + "\n")


def _post_with_retries(url: str, body: dict, headers: dict, timeout: int, *,
                       transcript_path: str | None = None, model: str | None = None,
                       prompt_chars: int = 0, retries: int = 3) -> dict:
    """POST JSON with backoff on 429/5xx (honors Retry-After). Raises ProviderError.

    SMELT_RETRIES env var overrides the retry count (for patient eval runs).
    """
    retries = int(os.environ.get("SMELT_RETRIES", str(retries)))
    last_err = "unknown provider failure"
    for attempt in range(retries + 1):
        _count_call("attempt", model)
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read())
            _count_call("ok", model)
            _log_transcript(transcript_path, model, prompt_chars, d)
            return d
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read()[:300].decode(errors="replace")
            except Exception:
                pass
            last_err = f"HTTP {e.code}: {detail[:200]}"
            if e.code in RETRY_STATUS and attempt < retries:
                wait = min(30.0, (1.5 ** attempt) + random.random())
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra:
                    try:
                        wait = max(wait, min(30.0, float(ra)))
                    except ValueError:
                        pass
                time.sleep(wait)
                continue
            raise ProviderError(last_err)
        except Exception as e:
            last_err = repr(e)[:200]
            if attempt < retries:
                time.sleep(min(30.0, (1.5 ** attempt) + random.random()))
                continue
            raise ProviderError(last_err)
    raise ProviderError(last_err)


# ------------------------------------------------------------------ providers

class FileProvider:
    """Candidates read from file(s), consumed IN ORDER across attempts (v0.8).

    Previously every call re-read paths[:n], so multi-attempt runs (and the
    repair loop) could never see candidate 2+. Now the cursor advances; when
    the list is exhausted it wraps — a single candidate is retried, preserving
    the gate-run semantics (wrong candidate -> honest rejection, exit 4).
    """

    name = "file"

    def __init__(self, paths: list[str]):
        self.paths = paths
        self._cursor = 0

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        if not self.paths:
            return []
        out = [open(self.paths[(self._cursor + j) % len(self.paths)]).read()
               for j in range(n)]
        self._cursor += n
        return out


class FakeProvider(FileProvider):
    """Same as file, but named for CI/docs (no model involved at all)."""

    name = "fake"


class OpenAICompatProvider:
    """Any OpenAI-compatible chat-completions server (llama.cpp, NVIDIA NIM, DigitalOcean, ...)."""

    def __init__(self, *, base_url: str, model: str, name: str = "openai-compat",
                 key_env: str | tuple[str, ...] | None = None, timeout: int = 300,
                 transcript_path: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = name
        self.timeout = timeout
        self.transcript_path = transcript_path
        names = (key_env,) if isinstance(key_env, str) else (key_env or ())
        self.api_key = resolve_secret(*names) if names else None
        if self.api_key is None:
            self.api_key = resolve_secret("SMELT_PROVIDER_KEY")

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        return [self._one(prompt) for _ in range(n)]

    def _one(self, prompt: str) -> str:
        # Reasoning models spend completion tokens on thinking before content;
        # 2400 truncated them into content=null (observed on NVIDIA NIM).
        max_tokens = int(os.environ.get("SMELT_MAX_TOKENS", "8192"))
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        d = _post_with_retries(self.base_url + "/chat/completions", body, headers,
                               self.timeout, transcript_path=self.transcript_path,
                               model=self.model, prompt_chars=len(prompt))
        choice = (d.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        if not text.strip():
            raise ProviderError(
                f"empty completion from provider (finish_reason={choice.get('finish_reason')}; "
                "reasoning may have exhausted the token budget — raise SMELT_MAX_TOKENS)")
        return extract_lib_rs(text)


class GeminiProvider:
    """Google AI Studio (Gemini API), native REST. Model-agnostic: any model the
    endpoint serves (pass --model or set SMELT_GEMINI_MODEL). No built-in default
    since v0.8 — the former Gemma defaults were removed."""

    name = "gemini"

    def __init__(self, model: str, timeout: int = 300,
                 transcript_path: str | None = None):
        self.model = model
        self.timeout = timeout
        self.transcript_path = transcript_path
        self.api_key = resolve_secret("GEMINI_API_KEY", "GOOGLE_API_KEY")
        if not self.api_key:
            raise ProviderError("no Gemini key found — set GEMINI_API_KEY in env or ~/.hermes/.env")

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        return [self._one(prompt) for _ in range(n)]

    def _one(self, prompt: str) -> str:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        gen: dict = {"maxOutputTokens": int(os.environ.get("SMELT_MAX_TOKENS", "8192"))}
        level = os.environ.get("SMELT_GEMINI_THINKING", "minimal")
        if level != "default":
            gen["thinkingConfig"] = {"thinkingLevel": level}
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        d = _post_with_retries(url, body, headers, self.timeout,
                               transcript_path=self.transcript_path, model=self.model,
                               prompt_chars=len(prompt))
        try:
            cand = (d.get("candidates") or [{}])[0]
            parts = (cand.get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except Exception as e:
            raise ProviderError(f"unexpected Gemini response shape: {e!r}")
        if not text.strip():
            raise ProviderError("empty completion from Gemini (thinking-only or truncated)")
        return extract_lib_rs(text)


# ------------------------------------------------------------------ resolution
# v0.8: no model family is hardwired. Defaults exist only where they are generic
# (nvidia: picked empirically on the corpus; local: the server ignores the name).
# Everything else requires an explicit model — honest failure beats a stale default.

NVIDIA_DEFAULT_MODEL = "mistralai/mistral-large-4-1t-a52b"

PROVIDER_KEY_ENVS = {
    "nvidia": ("NVIDIA_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("SMELT_OPENAI_KEY", "OPENAI_API_KEY"),
    "openrouter": ("SMELT_OPENAI_KEY", "OPENROUTER_API_KEY"),
    "do": ("DIGITALOCEAN_TOKEN",),
}


def resolve_default_provider() -> str:
    """--provider omitted: SMELT_PROVIDER env, else first provider with a key, else local."""
    env = os.environ.get("SMELT_PROVIDER")
    if env:
        return env
    for name in ("nvidia", "gemini", "openai", "do"):
        if resolve_secret(*PROVIDER_KEY_ENVS[name]):
            return name
    return "local"


def resolve_model(provider: str, model: str | None) -> str | None:
    """--model -> SMELT_MODEL -> SMELT_<PROVIDER>_MODEL -> provider default (may be None)."""
    if model:
        return model
    env = os.environ.get("SMELT_MODEL")
    if env:
        return env
    env = os.environ.get(f"SMELT_{provider.upper().replace('-', '_')}_MODEL")
    if env:
        return env
    if provider == "nvidia":
        return NVIDIA_DEFAULT_MODEL
    if provider == "local":
        return "local-model"
    return None


def make_provider(name: str, model: str | None, candidate: str | None, run_dir: str | None):
    tp = os.path.join(run_dir, "transcripts", "provider.jsonl") if run_dir else None
    if name in ("file", "fake"):
        if not candidate:
            raise ProviderError(f"provider {name!r} needs --candidate PATH")
        paths = sorted(glob.glob(candidate)) if any(c in candidate for c in "*?[") else [candidate]
        if not paths:
            raise ProviderError(f"no candidate files match {candidate!r}")
        return FakeProvider(paths) if name == "fake" else FileProvider(paths)
    model = resolve_model(name, model)
    if name == "local":
        base = os.environ.get("SMELT_LOCAL_BASE", "http://127.0.0.1:8080/v1")
        return OpenAICompatProvider(base_url=base, model=model or "local-model",
                                    name="local", transcript_path=tp)
    if name == "nvidia":
        if not resolve_secret("NVIDIA_API_KEY"):
            raise ProviderError("no NVIDIA key found — set NVIDIA_API_KEY in env or ~/.hermes/.env")
        return OpenAICompatProvider(base_url="https://integrate.api.nvidia.com/v1",
                                    model=model or NVIDIA_DEFAULT_MODEL, name="nvidia",
                                    key_env="NVIDIA_API_KEY", transcript_path=tp)
    if name in ("do", "digitalocean"):
        if not model:
            raise ProviderError("the do provider needs a model — pass --model or set SMELT_DO_MODEL")
        return OpenAICompatProvider(base_url="https://inference.do-ai.run/v1",
                                    model=model, name="do",
                                    key_env="DIGITALOCEAN_TOKEN", transcript_path=tp)
    if name in ("openai", "openai-compat", "openrouter"):
        default = "https://openrouter.ai/api/v1" if name == "openrouter" else "https://api.openai.com/v1"
        base = os.environ.get("SMELT_OPENAI_BASE", default)
        if not model:
            raise ProviderError(f"the {name} provider needs a model — pass --model or set SMELT_MODEL")
        return OpenAICompatProvider(base_url=base, model=model,
                                    name=name, key_env=PROVIDER_KEY_ENVS.get(name, ("SMELT_OPENAI_KEY",)),
                                    transcript_path=tp)
    if name == "gemini":
        if not model:
            raise ProviderError("the gemini provider needs a model — pass --model or set "
                                "SMELT_GEMINI_MODEL (built-in Gemma defaults were removed in v0.8)")
        return GeminiProvider(model=model, transcript_path=tp)
    raise ProviderError(f"unknown provider {name!r} (nvidia|gemini|local|do|openai|openrouter|file|fake)")
