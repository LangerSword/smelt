# Providers

v0.8: **model-agnostic** — no model family is hardwired (the former Gemma-4
defaults were removed). Bring any model; smelt's gates treat them all the same.

| name | what it is | key env var | model |
|---|---|---|---|
| `nvidia` | NVIDIA NIM, OpenAI-compatible (`https://integrate.api.nvidia.com/v1`) | `NVIDIA_API_KEY` | default picked empirically (`scripts/model_bakeoff.py` → `evals/bakeoff-v08.json`); override with `--model` / `SMELT_NVIDIA_MODEL` |
| `gemini` | Google AI Studio, native REST — any model the endpoint serves | `GEMINI_API_KEY` (falls back to `GOOGLE_API_KEY`) | required (`--model` / `SMELT_GEMINI_MODEL`) |
| `local` | any OpenAI-compatible server (llama.cpp, Ollama, vLLM); default `http://127.0.0.1:8080/v1` (`SMELT_LOCAL_BASE`) | none | `local-model` placeholder (servers ignore the name) |
| `do` | DigitalOcean Inference, OpenAI-compatible | `DIGITALOCEAN_TOKEN` | required (`--model` / `SMELT_DO_MODEL`) |
| `openai` | generic OpenAI-compatible endpoint; base `SMELT_OPENAI_BASE`, default `https://api.openai.com/v1` | `SMELT_OPENAI_KEY` → `OPENAI_API_KEY` | required (`--model` / `SMELT_MODEL`) |
| `openrouter` | OpenRouter (`https://openrouter.ai/api/v1`) | `SMELT_OPENAI_KEY` → `OPENROUTER_API_KEY` | required |
| `file` | candidates read from files, consumed IN ORDER across attempts (wraps) | — | — |
| `fake` | same as file, for CI — no model at all | — | — |

## Resolution

- **Provider** (when `--provider` is omitted): `SMELT_PROVIDER` env → first
  provider whose key exists (`nvidia`, `gemini`, `openai`, `do`) → `local`.
- **Model**: `--model` → `SMELT_MODEL` → `SMELT_<PROVIDER>_MODEL` → provider
  default. Only `nvidia` and `local` ship a default; the rest fail with a typed
  config error telling you exactly what to set — honest failure beats a stale
  default.

## Notes

- Reasoning models spend completion tokens on thinking before content. smelt
  requests 8192 output tokens by default (`SMELT_MAX_TOKENS` to override) and
  treats `content: null` as a typed ProviderError, never a crash. On the Gemini
  endpoint smelt requests `thinkingLevel: "minimal"` (`SMELT_GEMINI_THINKING`)
  and extracts only non-thought parts.
- Secrets resolve env → project `.env` → `~/.hermes/.env`; they are never
  logged, printed, or committed. Transcripts record model + sizes + usage only.
- Retries: 3 by default (`SMELT_RETRIES`), exponential backoff + jitter,
  honors `Retry-After`, capped waits.
- Offline use: `--provider local` with llama.cpp needs no network at all;
  `capture`, `verify` and `bench` never need the network either.
- Historical: every pre-v0.8 published result was produced by Gemma-4 models
  (`gemma-4-26b-a4b-it` via Gemini, `gemma-4-e2b-qat` locally). Those tables
  stay in `evals/` labeled with their model.
