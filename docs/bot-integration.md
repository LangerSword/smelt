# smelt bot mode — CodeRabbit-style PR suggestions (DESIGN — NOT YET BUILT)

**Status: design, not yet built. Nothing in this file runs.** No workflow
exists in `.github/workflows/`, and `tools/bot_run.py` does not exist yet.
Build and test the script + workflow on a scratch repo before enabling either
(G5 rules: label- or dispatch-triggered only, at most 3 candidates per run,
ONE PR comment, no secrets for fork PRs).

## Use smelt as a workflow

Three ways to run the loop, smallest first.

1. **Manual** — `smelt scan <path>` lists candidates, `smelt run <file.py:fn>`
   runs the loop, `smelt apply runs/<id>` prints the diff. You review it and
   open the PR yourself. Apply never writes anything.
2. **Agent** — install the skill (`skills/smelt`, Agent Skills format) and ask
   your coding agent to "speed up this function the smelt way". The agent runs
   scan → run → review and hands you the diff.
3. **CI / bot (CodeRabbit-style)** — trigger on a PR label or manual dispatch.
   Scan the changed files. Run at most 3 candidates. Post one PR comment with
   a results table and the diff. Never push. No secrets for fork PRs. Call
   caps keep the free tier safe.

**The GitHub Action is design, not yet built.** The reference workflow below
must be built and tested on a scratch repo first; the detailed design is
further down in this file.

### Reference workflow (design — not yet built)

```yaml
name: smelt-bot
on:
  pull_request:
    types: [labeled]
  workflow_dispatch:
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: smelt-bot-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: true
jobs:
  suggest:
    if: github.event.label.name == 'smelt-me' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: astral-sh/setup-uv@v5
      - run: uv tool install git+https://github.com/LangerSword/smelt
      - name: Scan (tier-1 candidates, capped at 3)
        run: smelt scan . --json > scan.json
      - name: Run (same-repo PRs only)
        if: ${{ github.event.pull_request.head.repo.full_name == github.repository || github.event_name == 'workflow_dispatch' }}
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python tools/bot_run.py scan.json --max 3 --out comment.md
      - name: Comment once
        run: gh pr comment ${{ github.event.pull_request.number }} --body-file comment.md
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

What each step does:

| step | what it does |
|---|---|
| trigger | fires only on the `smelt-me` label or a manual dispatch — never on every push (a run costs model calls and a Rust build) |
| toolchains | installs Rust, uv and the smelt CLI (pin a tag before enabling) |
| scan | lists candidates; the bot keeps tier-1 functions in files the PR touched, capped at 3 |
| run | one `smelt run` per candidate; skipped on fork PRs, so no secret is ever exposed |
| comment | exactly one PR comment: results table (status · exit code · speedup lb · attempts · model) + view-only diffs + reproduce commands |
| safety | the job never writes to the branch (`contents: read`); a concurrency group cancels duplicate runs |

## What it would do

Like CodeRabbit reviews diffs, the smelt bot reviews a PR for **smelt-shaped
opportunities**: slow, pure Python functions that can be smelted into verified
Rust. It comments once with a table of candidates, honest outcomes (accepted /
rejected / refused), measured speedups with lower bounds, and view-only diffs.

## Design (bounded by the G5 rules)

- **Trigger**: PR label `smelt-me` or manual `workflow_dispatch`. Never on every
  push — a run costs model calls and a Rust build.
- **Candidates**: `smelt scan <repo> --json`, filtered to tier-1 functions in
  files the PR touched; cap at 3.
- **Run**: `smelt run <file>:<fn> --provider gemini` (model `gemma-4-26b-a4b-it`),
  max attempts 2, per-candidate timeout.
- **Comment**: one PR comment — table (function · status · exit code · speedup lb ·
  attempts · model) + `smelt apply` diff blocks (view only) + the exact commands
  a human can run to reproduce.
- **Safety**: the bot never writes to the PR branch — comments only. `apply` is
  view-only by design. Fork PRs: no secrets are exposed; the job skips model runs
  and says so (public repo + no key = capture/verify still work offline, but no
  generation).
- **Cost control**: `GEMINI_API_KEY` secret (same-repo PRs only), global call cap
  per run, `concurrency` group to kill duplicate runs.

`tools/bot_run.py` does not exist yet — it would read `scan.json`, run smelt per
candidate with a call cap, and render the markdown table + diffs.
