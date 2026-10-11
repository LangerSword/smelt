# smelt site

The project site — a static landing page plus docs, results, install, changelog and
roadmap. Design: dark, "ore → ingot" (no networking imagery), built on a glass-pill
skeleton with a word-by-word blur hero and alternating feature rows.

Deployed to GitHub Pages at **https://smelt.langersword.in** —
`.github/workflows/deploy-site.yml`, one deployment kept via `tools/prune-deployments.mjs`.

## Stack

| Layer | What | Notes |
|---|---|---|
| Markup | Hand-written HTML | No framework, no template engine at serve time |
| Style | `assets/css/site.css` (source) → `site.min.css` (built) | Fonts inlined at build |
| Motion | `src/site.ts` → `assets/js/site.js` (built, minified) | TypeScript + GSAP 3.13 |
| Fonts | `assets/fonts/` | Barlow + Instrument Serif + JetBrains Mono, SIL OFL, latin subset |
| GSAP | `assets/js/vendor/` | Vendored (no CDN), GreenSock "No Charge" license |

## Build

```bash
cd site
npm install --include=dev      # tsc, esbuild, playwright (NODE_ENV=production prunes devDeps — keep --include=dev)
npm run build                  # tsc → esbuild minify → assets/js/site.js
npm run typecheck              # tsc --noEmit, strict
node scripts/bundle.mjs --check # fail if site.js is stale vs src/site.ts

cd .. && python3 site/scripts/build.py
# → regenerates results + CLI reference from the repo, injects page partials,
#   minifies site.css + fonts into site.min.css, writes sitemap.xml + robots.txt
```

`build.py` is idempotent: partials are injected between marker comments and replaced
on re-run, so it can be run any number of times.

## Test

```bash
cd site
python3 -m http.server 8899 &     # serve the built site
node scripts/smoke.mjs            # 33 checks in a real headless Chromium
```

The smoke test asserts, in a browser: no console/page errors, no failed requests,
GSAP present, the hero words clear their blur, the terminal replay renders every
line including the real verdict, the speedup bars reach their final `scaleX`, the
counters land on their targets, reduced-motion leaves everything visible, the page
works with JavaScript disabled, and — importantly — **no element is left stuck
invisible after a full scroll-through**. That last check exists because two
animations owning one element (or a `gsap.from()` that re-reads its own end state
after a `matchMedia` re-run) strands content at `opacity: 0` in a way no other
check would catch.

Lighthouse (mobile, simulated throttling) is wired through `lighthouserc.json` and
runs report-only in CI.

## Generated content — never hand-edited

| Output | Source | Script |
|---|---|---|
| Results table + speedup bars + strip | `evals/results.json` | `scripts/gen_results.py` |
| CLI reference | `smelt --help` + `docs/cli.md` | `scripts/gen_cli_ref.py` |
| `sitemap.xml`, `robots.txt`, page partials | — | `scripts/build.py` |

CI fails if the generated results page and `evals/results.json` disagree.

## Motion rules

GSAP only. Every reduced-motion branch goes through `gsap.matchMedia()` (so
animations revert cleanly when the preference changes) — never a bare
`matchMedia` check.

- Animate **transforms and `autoAlpha`** only. The speedup bars grow with
  `scaleX`, never `width`, to stay off the layout path.
- **`fromTo()`, not `from()`**, for anything a `matchMedia` handler creates:
  a `from()` tween records its end value from the element's current state, so a
  re-run reads back the already-animated value and animates 0 → 0.
- **One animation owner per element.** A parent's `autoAlpha` sets inherited
  `visibility: hidden`, which a child's own `autoAlpha` then records as its end
  state — animate leaves, not both levels.
- Ember canvases are capped (42 hero / 22 statement) and pause off-screen via
  `IntersectionObserver`.
- With JS disabled or with reduced motion, all content is visible and static.

## Install script

`install.sh` (also served at `/install.sh`): POSIX `sh`, `set -eu`, no sudo, no
piping into other shells, prints what it will do, asks before installing anything.
Flags: `--dry-run --yes --version X --uninstall --with-tui`.

**Untested on macOS.** Tested on Linux x86_64 (`--dry-run`, `--uninstall`,
`--with-tui` paths; `sh -n` syntax check; shellcheck-clean at warning level).