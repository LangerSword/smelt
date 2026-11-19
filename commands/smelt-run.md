---
description: Smelt one hot Python function into verified Rust (detached run, code-gated acceptance)
argument-hint: <file.py:function> [--provider p] [--model m]
allowed-tools: Bash(smelt run:*), Bash(smelt report:*), Bash(smelt apply:*), Bash(smelt resume:*), Bash(smelt capture:*)
---

Target: $ARGUMENTS

1. Confirm the target looks like `path/to/file.py:function`. If it is missing or
   malformed, ask for it — do not guess.
2. Start the run: `smelt run <target> --json` (append any --provider/--model the
   user gave; otherwise smelt auto-resolves from available keys). A run costs
   model calls and a Rust build — it is a mutating action the user asked for by
   invoking this command.
3. Read the JSON summary. Outcomes are typed:
   - exit 0 accepted: verified on every oracle case + measured speedup whose
     conservative lower bound clears 1.5x. Show `smelt report <run_dir>` and
     offer `smelt apply <run_dir>` (VIEW ONLY — it never writes the repo).
   - exit 4 rejected: honest — mismatch or no meaningful gain. Show the reason;
     do not retry in a loop or tune the oracle to force a win.
   - exit 3 refused: impure/unsupported/out-of-domain target. Show the refactor
     hint verbatim.
   - exit 2/5: config/harness error — surface it plainly.
4. Never edit the frozen oracle, never lower the acceptance threshold, never
   apply a change without the user reviewing the diff. The Python original
   stays as the fallback.
