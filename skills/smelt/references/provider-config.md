# Provider configuration

Six providers behind one interface (`generate(prompt) -> list[str]` of `lib.rs` text):

| name | what it is | key env var |
|---|---|---|
| `gemini` | Google AI Studio, native REST — `gemma-4-26b-a4b-it` (default, free-tier friendly) or `gemma-4-31b-it` (strongest, slower) | `GEMINI_API_KEY` (falls back to `GOOGLE_API_KEY`) |
| `do` | DigitalOcean Inference, OpenAI-compatible — `gemma-4-31B-it` | `DIGITALOCEAN_TOKEN` |
| `local` | any OpenAI-compatible server (llama.cpp, Ollama, vLLM); default `http://127.0.0.1:8080/v1` | none (or `SMELT_PROVIDER_KEY`) |
| `openai` | generic OpenAI-compatible (set base URL) | `SMELT_OPENAI_KEY`, base in `SMELT_OPENAI_BASE` |
| `file` | candidates read from a file (fixtures, gate checks, meta-eval) | n/a |
| `fake` | same as file, for CI — no model at all | n/a |

## Secret resolution (never logged, never printed)

Order: process environment → project `.env` → `~/.hermes/.env`.

## Tunables

| env var | default | effect |
|---|---|---|
| `SMELT_RETRIES` | 3 | HTTP retries per call (429/5xx backoff + jitter, honors Retry-After, waits capped at 30 s) |
| `SMELT_GEMINI_THINKING` | `minimal` | Gemini thinking level; set `default` to disable this override |
| `SMELT_LOCAL_BASE` | `http://127.0.0.1:8080/v1` | local server URL |
| `SMELT_TARGET_DIR` | `~/.cache/smelt/target` | shared cargo target cache |

## Notes

- Gemma 4 thinking mode is ON by default upstream and can consume the entire token
  budget; smelt requests `thinkingLevel: "minimal"` and extracts only non-thought parts.
- Speed guidance: `gemma-4-26b-a4b-it` is the default (MoE, 4B active — answers in
  seconds; free-tier friendly). `gemma-4-31b-it` is stronger but much slower per call.
- Transcripts: each call logs model + prompt size + usage to
  `runs/<id>/transcripts/provider.jsonl`; keys are never written.
