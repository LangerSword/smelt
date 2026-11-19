# Provider configuration

Model-agnostic since v0.8 — no model family is hardwired (the former Gemma-4
defaults were removed). Providers behind one interface
(`generate(prompt) -> list[str]` of `lib.rs` text):

| name | what it is | key env var | model |
|---|---|---|---|
| `nvidia` | NVIDIA NIM, OpenAI-compatible (`https://integrate.api.nvidia.com/v1`) | `NVIDIA_API_KEY` | default picked empirically (`scripts/model_bakeoff.py`); override via `--model`/`SMELT_NVIDIA_MODEL` |
| `gemini` | Google AI Studio, native REST — any served model | `GEMINI_API_KEY` (falls back to `GOOGLE_API_KEY`) | required |
| `do` | DigitalOcean Inference, OpenAI-compatible | `DIGITALOCEAN_TOKEN` | required |
| `local` | any OpenAI-compatible server (llama.cpp, Ollama, vLLM); default `http://127.0.0.1:8080/v1` | none (or `SMELT_PROVIDER_KEY`) | `local-model` placeholder |
| `openai` | generic OpenAI-compatible; base `SMELT_OPENAI_BASE`, default `https://api.openai.com/v1` | `SMELT_OPENAI_KEY` → `OPENAI_API_KEY` | required |
| `openrouter` | OpenRouter | `SMELT_OPENAI_KEY` → `OPENROUTER_API_KEY` | required |
| `file` | candidates read from files, consumed IN ORDER across attempts (wraps) | n/a | n/a |
| `fake` | same as file, for CI — no model at all | n/a | n/a |

## Resolution

- Provider (`--provider` omitted): `SMELT_PROVIDER` → first provider whose key
  exists (nvidia, gemini, openai, do) → local.
- Model: `--model` → `SMELT_MODEL` → `SMELT_<PROVIDER>_MODEL` → provider default
  (only nvidia/local ship one; the rest raise a typed config error).

## Secret resolution (never logged, never printed)

Order: process environment → project `.env` → `~/.hermes/.env`.

## Tunables

| env var | default | effect |
|---|---|---|
| `SMELT_RETRIES` | 3 | HTTP retries per call (429/5xx backoff + jitter, honors Retry-After, waits capped at 30 s) |
| `SMELT_MAX_TOKENS` | 8192 | output-token budget; reasoning models spend it on thinking first — raise it if completions come back empty |
| `SMELT_GEMINI_THINKING` | `minimal` | Gemini thinking level; set `default` to disable this override |
| `SMELT_LOCAL_BASE` | `http://127.0.0.1:8080/v1` | local server URL |
| `SMELT_OPENAI_BASE` | `https://api.openai.com/v1` | openai-compat base URL |
| `SMELT_TARGET_DIR` | `~/.cache/smelt/target` | shared cargo target cache |
| `SMELT_PROVIDER` / `SMELT_MODEL` | — | default provider / model overrides |

## Notes

- Reasoning models can return `content: null` when thinking exhausts the token
  budget; smelt treats that as a typed ProviderError (never a crash) — raise
  `SMELT_MAX_TOKENS`. On the Gemini endpoint smelt requests
  `thinkingLevel: "minimal"` and extracts only non-thought parts.
- Transcripts: each call logs model + prompt size + usage to
  `runs/<id>/transcripts/provider.jsonl`; keys are never written.
- Historical: pre-v0.8 results were produced by Gemma-4 models; those tables
  remain in `evals/` labeled with their model.
