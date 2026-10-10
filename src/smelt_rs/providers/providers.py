"""Provider layer: thin, fake-able, transcript-logged.

One interface: `generate(prompt) -> list[str]` (complete lib.rs contents).

Providers:
- gemini   — Google AI Studio, native REST (`gemma-4-31b-it`), key: GEMINI_API_KEY
- do       — DigitalOcean Inference, OpenAI-compatible, model `gemma-4-31B-it`, key: DIGITALOCEAN_TOKEN
- local    — llama.cpp / any OpenAI-compatible server (default http://127.0.0.1:8080/v1)
- openai   — generic OpenAI-compatible (set SMELT_OPENAI_BASE / SMELT_OPENAI_KEY)
- file     — hand-provided candidates (gate checks, fixtures)
- fake     — like file, for CI usage without any model

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
                  "list[int]": "Vec<i64>", "list[str]": "Vec<String>"}
RUST_RET_TYPES = {"str": "String", "int": "i64", "float": "f64", "bool": "bool",
                  "list[int]": "Vec<i64>", "list[str]": "Vec<String>"}

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
    """Candidates read from file(s). Used for hand-injected rewrites and fixtures."""

    name = "file"

    def __init__(self, paths: list[str]):
        self.paths = paths

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        return [open(p).read() for p in self.paths[:n]]


class FakeProvider(FileProvider):
    """Same as file, but named for CI/docs (no model involved at all)."""

    name = "fake"


class OpenAICompatProvider:
    """Any OpenAI-compatible chat-completions server (llama.cpp, DigitalOcean Inference, ...)."""

    def __init__(self, *, base_url: str, model: str, name: str = "openai-compat",
                 key_env: str | None = None, timeout: int = 300,
                 transcript_path: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = name
        self.timeout = timeout
        self.transcript_path = transcript_path
        self.api_key = resolve_secret(key_env) if key_env else None
        if self.api_key is None:
            self.api_key = resolve_secret("SMELT_PROVIDER_KEY")

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
        d = _post_with_retries(self.base_url + "/chat/completions", body, headers,
                               self.timeout, transcript_path=self.transcript_path,
                               model=self.model, prompt_chars=len(prompt))
        text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        if not text.strip():
            raise ProviderError("empty completion from provider")
        return extract_lib_rs(text)


class GeminiProvider:
    """Google AI Studio (Gemini API), native REST. Default model: gemma-4-31b-it."""

    name = "gemini"

    def __init__(self, model: str = "gemma-4-31b-it", timeout: int = 300,
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
        gen: dict = {"maxOutputTokens": 3000}
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


def make_provider(name: str, model: str | None, candidate: str | None, run_dir: str | None):
    tp = os.path.join(run_dir, "transcripts", "provider.jsonl") if run_dir else None
    if name in ("file", "fake"):
        if not candidate:
            raise ProviderError(f"provider {name!r} needs --candidate PATH")
        paths = sorted(glob.glob(candidate)) if any(c in candidate for c in "*?[") else [candidate]
        if not paths:
            raise ProviderError(f"no candidate files match {candidate!r}")
        return FakeProvider(paths) if name == "fake" else FileProvider(paths)
    if name == "local":
        base = os.environ.get("SMELT_LOCAL_BASE", "http://127.0.0.1:8080/v1")
        return OpenAICompatProvider(base_url=base, model=model or "gemma-4-e2b-qat",
                                    name="local", transcript_path=tp)
    if name in ("do", "digitalocean"):
        return OpenAICompatProvider(base_url="https://inference.do-ai.run/v1",
                                    model=model or "gemma-4-31B-it", name="do",
                                    key_env="DIGITALOCEAN_TOKEN", transcript_path=tp)
    if name in ("openai", "openai-compat", "openrouter"):
        default = "https://openrouter.ai/api/v1" if name == "openrouter" else ""
        base = os.environ.get("SMELT_OPENAI_BASE", default)
        if not base:
            raise ProviderError("set SMELT_OPENAI_BASE for the openai-compat provider")
        return OpenAICompatProvider(base_url=base, model=model or "gemma-4-31b-it",
                                    name=name, key_env="SMELT_OPENAI_KEY", transcript_path=tp)
    if name == "gemini":
        return GeminiProvider(model=model or "gemma-4-31b-it", transcript_path=tp)
    raise ProviderError(f"unknown provider {name!r} (local|gemini|do|openai|file|fake)")
