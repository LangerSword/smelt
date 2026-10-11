# Submission payload — DRAFT (do NOT submit until the maintainer says "submit now")

Platform: **mlh.com OrganizerHQ → Challenges → Add Submission** (sudo Hacktober).

## Fields

- **Title:** smelt — smelt a slow Python function into verified Rust (oracle-gated; Gemma 4)
- **Public code:** https://github.com/LangerSword/smelt
- **Tagline:** One hot pure Python function in. Oracle-verified Rust out, speedup measured.
  Code — not the model — accepts; wrong rewrites never ship.
- **Description:**
  smelt converts ONE slow, pure Python function into an equivalent Rust (pyo3)
  extension, and only accepts the result if code proves it. The original function is
  run to freeze a differential oracle (seeded random + edge cases, hashed, read-only);
  Gemma 4 writes the Rust; a static safety scan rejects unsafe code; the built
  extension must reproduce every recorded output (and exception) — mismatches feed
  back for up to N attempts, then the run is honestly rejected. Accepted rewrites are
  benchmarked with a bootstrap CI; the conservative 1.5x lower bound is the bar.
  Everything is checkable: a 24-function corpus (23/24 accepted on
  `gemma-4-26b-a4b-it`), a 13/13 wrong-rewrite meta-eval, and a blind test over 3
  real open-source repos / 10 functions with zero crashes and typed outcomes.
  Includes a Go TUI (Furnace, CI-tested) and a validated Agent Skill.
- **Technologies:** Python · Rust (pyo3, maturin) · Go (Bubble Tea) · Gemma 4
  (Gemini API) · llama.cpp · GitHub Actions
- **Challenges entered:** Best Open-Source AI Project · Best Use of Gemma 4
- **AI-use disclosure:** Built live during the event with Hermes Agent as the build
  agent under continuous developer review; runtime models: Gemma 4 via the Gemini API
  (`gemma-4-26b-a4b-it` default; `gemma-4-31b-it` opt-in) and `gemma-4-e2b-qat`
  locally via llama.cpp. Full log: AI_USE.md.
- **Demo:** `scripts/demo.sh` (3 min: accepted / rejected / refusal; rehearsed twice,
  16–22 s of compute + replay) · `tui/testdata/demo.gif`
- **Evidence links:** README (results + honest limits) · `evals/general.md` (blind
  test, before/after) · `evals/results.md` (corpus) · `docs/` (how it works, CLI,
  providers, safety, evals, FAQ)

## After approval (not done yet)

- PyPI (optional): `uv publish dist/smelt_rs-0.6.0.tar.gz dist/smelt_rs-0.6.0-py3-none-any.whl`
  (needs a PyPI token in `UV_PUBLISH_TOKEN`; name `smelt-rs` is unclaimed).
- The maintainer performs the actual submission on mlh.com (organizer account).
