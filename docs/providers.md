# Providers

| name | what it is | key env var |
|---|---|---|
| `gemini` | Google AI Studio, native REST — `gemma-4-26b-a4b-it` (default, free-tier friendly) or `gemma-4-31b-it` (strongest, slower) | `GEMINI_API_KEY` (falls back to `GOOGLE_API_KEY`) |
| `local` | any OpenAI-compatible server (llama.cpp, Ollama, vLLM); default `http://127.0.0.1:8080/v1` | none |
| `do` | DigitalOcean Inference, OpenAI-compatible — `gemma-4-31B-it` | `DIGITALOCEAN_TOKEN` |
| `openai` | generic OpenAI-compatible endpoint | `SMELT_OPENAI_KEY` + `SMELT_OPENAI_BASE` |
| `file` | candidates read from a file (fixtures, gate runs, meta-eval) | — |
| `fake` | same as file, for CI — no model at all | — |

**Model story (one story, kept consistent):** `gemma-4-26b-a4b-it` is the
default — fast and free-tier friendly; every published result was produced with
it. `gemma-4-31b-it` is the opt-in strongest option (slower per call).

Notes:

- Gemma 4 thinking mode is ON by default upstream and can consume the whole
  token budget; smelt requests `thinkingLevel: "minimal"` and extracts only
  non-thought parts.
- Secrets resolve env → project `.env` → `~/.hermes/.env`; they are never
  logged, printed, or committed. Transcripts record model + sizes + usage only.
- Retries: 3 by default (`SMELT_RETRIES`), exponential backoff + jitter,
  honors `Retry-After`, capped waits.
- Offline use: `--provider local` with llama.cpp needs no network at all;
  `capture`, `verify` and `bench` never need the network either.
