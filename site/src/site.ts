/**
 * smelt site — motion layer.
 *
 * TypeScript + GSAP 3.13, following the gsap-core / gsap-timeline /
 * gsap-scrolltrigger / gsap-plugins / gsap-performance skills:
 *
 *   - gsap.matchMedia() owns every reduced-motion branch (never a bare
 *     matchMedia check) so animations revert cleanly when it changes
 *   - timelines with the position parameter, never setTimeout chains
 *   - transforms + autoAlpha only; the speedup bars scaleX, never width
 *   - ScrollTrigger on top-level tweens/timelines only, never nested
 *   - ember canvases are capped and paused off-screen
 *   - content is visible with JS off and with reduced motion
 */

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { SplitText } from "gsap/SplitText";

gsap.registerPlugin(ScrollTrigger, DrawSVGPlugin, SplitText);
gsap.defaults({ ease: "power3.out" });

type TerminalLine = readonly [cls: string, text: string, holdMs: number];

/* ------------------------------------------------------------------ *
 * DOM helpers
 * ------------------------------------------------------------------ */

const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T | null =>
  root.querySelector<T>(sel);

const $$ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T[] =>
  Array.from(root.querySelectorAll<T>(sel));

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function parseTerminalLines(el: HTMLElement): TerminalLine[] {
  const raw = el.getAttribute("data-lines");
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (l): l is TerminalLine => Array.isArray(l) && l.length >= 2 && typeof l[1] === "string",
    );
  } catch {
    return [];
  }
}

/* ------------------------------------------------------------------ *
 * 1. EMBER FIELD — canvas particles.
 *    Prism backs its hero with video; smelt animates a warm ember field
 *    instead (no stock footage, no video weight). Capped, paused when
 *    off-screen, skipped entirely under reduced motion.
 * ------------------------------------------------------------------ */

const EMBER_CAP = 42;

interface Ember {
  x: number;
  y: number;
  r: number;
  vx: number;
  vy: number;
  life: number;
  decay: number;
}

function emberField(canvas: HTMLCanvasElement | null, opts: { cap: number; alpha: number }): () => void {
  if (!canvas) return () => {};
  const ctx = canvas.getContext("2d");
  const parent = canvas.parentElement;
  if (!ctx || !parent) return () => {};

  let w = 0;
  let h = 0;
  let raf = 0;
  let visible = true;
  const particles: Ember[] = [];

  const resize = (): void => {
    w = canvas.width = parent.offsetWidth;
    h = canvas.height = parent.offsetHeight;
  };

  const spawn = (initial = false): Ember => ({
    x: Math.random() * w,
    y: initial ? Math.random() * h : h + 8,
    r: Math.random() * 1.9 + 0.5,
    vx: (Math.random() - 0.5) * 0.28,
    vy: -(Math.random() * 0.38 + 0.12),
    life: 1,
    decay: Math.random() * 0.0035 + 0.0015,
  });

  const tick = (): void => {
    if (!visible) {
      raf = 0;
      return;
    }
    ctx.clearRect(0, 0, w, h);
    for (let i = 0; i < particles.length; i += 1) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.life -= p.decay;
      if (p.life <= 0 || p.y < -8) {
        particles[i] = spawn();
        continue;
      }
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 109, 58, ${(p.life * opts.alpha).toFixed(3)})`;
      ctx.fill();
    }
    raf = requestAnimationFrame(tick);
  };

  const start = (): void => {
    if (raf === 0) raf = requestAnimationFrame(tick);
  };

  resize();
  for (let i = 0; i < opts.cap; i += 1) particles.push(spawn(true));
  start();

  window.addEventListener("resize", resize);

  const io = new IntersectionObserver(
    (entries) => {
      visible = entries[0]?.isIntersecting ?? false;
      if (visible) start();
    },
    { threshold: 0 },
  );
  io.observe(canvas);

  return () => {
    if (raf) cancelAnimationFrame(raf);
    window.removeEventListener("resize", resize);
    io.disconnect();
    ctx.clearRect(0, 0, w, h);
  };
}

function initEmbers(mm: gsap.MatchMedia): void {
  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      if (reduceMotion) return;
      const stopHero = emberField($("#hero-canvas") as HTMLCanvasElement | null, {
        cap: EMBER_CAP,
        alpha: 0.65,
      });
      const stopStatement = emberField($("#statement-canvas") as HTMLCanvasElement | null, {
        cap: 22,
        alpha: 0.4,
      });
      return () => {
        stopHero();
        stopStatement();
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 2. HERO — word-by-word blur-in (the Prism move)
 * ------------------------------------------------------------------ */

function initHero(mm: gsap.MatchMedia): void {
  const h1 = $(".hero h1");
  if (!h1) return;

  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      if (reduceMotion) return;

      const words = $$(".word", h1);
      if (words.length === 0) return;

      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

      // fromTo (never from) with explicit end values: a matchMedia handler can
      // run more than once (resize / refresh), and a from() tween would then
      // read the already-animated state back in as its end value — animating
      // 0 -> 0 and stranding the element invisible.
      tl.fromTo(
        words,
        { autoAlpha: 0, y: 26, filter: "blur(14px)" },
        {
          autoAlpha: 1,
          y: 0,
          filter: "blur(0px)",
          duration: 1.05,
          stagger: 0.085,
          clearProps: "filter",
        },
        0.15,
      )
        .fromTo(".hero-pill", { autoAlpha: 0, y: -10 }, { autoAlpha: 1, y: 0, duration: 0.6 }, 0)
        .fromTo(".hero-lead", { autoAlpha: 0, y: 16 }, { autoAlpha: 1, y: 0, duration: 0.8 }, "-=0.6")
        .fromTo(".hero-actions", { autoAlpha: 0, y: 16 }, { autoAlpha: 1, y: 0, duration: 0.7 }, "-=0.55")
        .fromTo(".hero-note", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5 }, "-=0.45")
        // Only the items fade — never the .trust container. autoAlpha on a
        // parent sets inherited visibility:hidden, which a child's own
        // autoAlpha would then record as its end state.
        .fromTo(
          ".trust-item",
          { autoAlpha: 0, y: 10 },
          { autoAlpha: 1, y: 0, duration: 0.5, stagger: 0.06 },
          "-=0.4",
        );

      return () => {
        gsap.set(
          [words, ".hero-pill", ".hero-lead", ".hero-actions", ".hero-note", ".trust-item"],
          { clearProps: "all" },
        );
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 3. TERMINAL REPLAY — one timeline drives the line buffer
 * ------------------------------------------------------------------ */

function initTerminal(mm: gsap.MatchMedia): void {
  const term = $("#demo-terminal");
  const body = term ? $(".terminal-body", term) : null;
  if (!term || !body) return;
  const lines = parseTerminalLines(term);
  if (lines.length === 0) return;

  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      body.innerHTML = "";

      if (reduceMotion) {
        // Static: every line present, no typing. Values are escaped because
        // they come from our own data-lines attribute, not user input.
        body.innerHTML = lines
          .map(([cls, text]) => `<span class="${cls}">${escapeHtml(text)}</span>`)
          .join("");
        return;
      }

      const tl = gsap.timeline({ paused: true });
      let cursor = 0;
      for (const [cls, text] of lines) {
        tl.call(
          () => {
            const span = document.createElement("span");
            span.className = cls;
            span.textContent = text;
            body.append(span);
            gsap.from(span, { autoAlpha: 0, x: -6, duration: 0.22 });
          },
          undefined,
          cursor,
        );
        cursor += 0.24;
      }

      const start = ScrollTrigger.create({
        trigger: term,
        start: "top 78%",
        once: true,
        onEnter: () => tl.play(),
      });

      return () => {
        start.kill();
        tl.kill();
        body.innerHTML = "";
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 4. COUNTERS — scroll-triggered, decimals respected
 * ------------------------------------------------------------------ */

function initCounters(mm: gsap.MatchMedia): void {
  const els = $$("[data-count]");
  if (els.length === 0) return;

  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      const tweens: gsap.core.Tween[] = [];

      els.forEach((el) => {
        const target = Number.parseFloat(el.getAttribute("data-count") ?? "0");
        if (Number.isNaN(target)) return;
        const decimals = target % 1 === 0 ? 0 : 2;
        const fmt = (v: number): string => v.toFixed(decimals);

        if (reduceMotion) {
          el.textContent = fmt(target);
          return;
        }

        const obj = { v: 0 };
        const tween = gsap.to(obj, {
          v: target,
          duration: 1.4,
          ease: "power2.out",
          paused: true,
          onUpdate: () => {
            el.textContent = fmt(obj.v);
          },
          onComplete: () => {
            el.textContent = fmt(target);
          },
        });
        tweens.push(tween);

        ScrollTrigger.create({
          trigger: el,
          start: "top 88%",
          once: true,
          onEnter: () => tween.play(),
        });
      });

      return () => {
        tweens.forEach((t) => t.kill());
        els.forEach((el) => {
          const t = Number.parseFloat(el.getAttribute("data-count") ?? "0");
          if (!Number.isNaN(t)) el.textContent = t.toFixed(t % 1 === 0 ? 0 : 2);
        });
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 5. SPEEDUP BARS — scaleX on a transform-origin:left fill.
 *    Width would trigger layout; scaleX stays on the compositor.
 *    Bars already scrolled past still complete (onRefresh).
 * ------------------------------------------------------------------ */

function initBars(mm: gsap.MatchMedia): void {
  const rows = $$(".speedup-row");
  if (rows.length === 0) return;

  interface ParsedRow {
    readonly fill: HTMLElement;
    readonly w: number;
  }

  const parsed: ParsedRow[] = rows.flatMap((row): ParsedRow[] => {
    const fill = $(".speedup-bar-fill", row);
    if (!fill) return [];
    const w = Number.parseFloat(fill.getAttribute("data-w") ?? "0");
    return [{ fill, w }];
  });

  if (parsed.length === 0) return;

  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };

      if (reduceMotion) {
        parsed.forEach(({ fill, w }) => {
          gsap.set(fill, { scaleX: w / 100, transformOrigin: "left center" });
        });
        gsap.set(".speedup-lb", { autoAlpha: 1 });
        return;
      }

      const triggers: ScrollTrigger[] = [];
      const tweens: gsap.core.Tween[] = [];
      parsed.forEach(({ fill, w }) => {
        gsap.set(fill, { scaleX: 0, transformOrigin: "left center" });
        const tween = gsap.to(fill, {
          scaleX: w / 100,
          duration: 0.95,
          ease: "power3.out",
          delay: 0.05,
          paused: true,
        });
        tweens.push(tween);
        const st = ScrollTrigger.create({
          trigger: fill,
          start: "top 92%",
          once: true,
          onEnter: () => tween.play(),
          onRefresh: (self) => {
            if (self.progress > 0 && tween.progress() === 0) tween.play();
          },
        });
        triggers.push(st);
      });

      const lbTriggers = $$(".speedup-lb").map((lb) =>
        ScrollTrigger.create({
          trigger: lb,
          start: "top 92%",
          once: true,
          animation: gsap.to(lb, { autoAlpha: 1, duration: 0.3, delay: 0.6 }),
        }),
      );

      return () => {
        [...triggers, ...lbTriggers].forEach((t) => t.kill());
        tweens.forEach((t) => t.kill());
        parsed.forEach(({ fill, w }) => {
          gsap.set(fill, { scaleX: w / 100, clearProps: "transform,will-change" });
        });
        gsap.set(".speedup-lb", { clearProps: "opacity,visibility" });
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 6. PIPELINE PATH — DrawSVG on a top-level tween
 * ------------------------------------------------------------------ */

function initPipeline(mm: gsap.MatchMedia): void {
  const path = $<SVGPathElement>(".pipeline-path");
  if (!path) return;

  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      if (reduceMotion) {
        gsap.set(path, { drawSVG: "100%" });
        return;
      }
      const st = ScrollTrigger.create({
        trigger: path,
        start: "top 82%",
        once: true,
        animation: gsap.fromTo(
          path,
          { drawSVG: "0%" },
          { drawSVG: "100%", duration: 1.8, ease: "power2.inOut" },
        ),
      });
      return () => {
        st.kill();
        gsap.set(path, { drawSVG: "100%" });
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 7. SECTION REVEALS — ScrollTrigger.batch, one stagger per batch
 *
 *    Ownership rule: exactly ONE animation may target an element.
 *    .trust-item belongs to the hero timeline and .stat to the stats
 *    band, so neither appears here — two owners on one element means
 *    the later tween's from-state can win and strand it at opacity 0.
 * ------------------------------------------------------------------ */

const REVEAL_SELECTOR = ".card, .verdict, .stack-item, .feature-row, .badge";

function initReveals(mm: gsap.MatchMedia): void {
  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      if (reduceMotion) return;

      const batch = ScrollTrigger.batch(REVEAL_SELECTOR, {
        start: "top 88%",
        onEnter: (elements) =>
          gsap.fromTo(
            elements,
            { y: 26, autoAlpha: 0 },
            { y: 0, autoAlpha: 1, duration: 0.65, stagger: 0.08, overwrite: true },
          ),
      });

      return () => {
        batch.forEach((t) => t.kill());
        gsap.set(REVEAL_SELECTOR, { clearProps: "all" });
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 8. STATS BAND — the numbers rise as the band enters
 * ------------------------------------------------------------------ */

function initStatBand(mm: gsap.MatchMedia): void {
  const band = $(".stats-band");
  if (!band) return;

  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      noReduce: "(prefers-reduced-motion: no-preference)",
    },
    (ctx) => {
      const { reduceMotion } = ctx.conditions as { reduceMotion: boolean };
      if (reduceMotion) return;

      const nums = band.querySelectorAll(".stat .num");
      const st = ScrollTrigger.create({
        trigger: band,
        start: "top 72%",
        once: true,
        animation: gsap.fromTo(
          nums,
          { autoAlpha: 0, y: 22 },
          { autoAlpha: 1, y: 0, duration: 0.8, stagger: 0.12 },
        ),
      });
      return () => {
        st.kill();
        gsap.set(nums, { clearProps: "all" });
      };
    },
  );
}

/* ------------------------------------------------------------------ *
 * 9. Copy buttons + docs search (plain DOM, no animation)
 * ------------------------------------------------------------------ */

function initCopy(): void {
  $$("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const text = btn.getAttribute("data-copy") ?? "";
      void navigator.clipboard?.writeText(text).then(() => {
        const original = btn.textContent ?? "";
        btn.textContent = "copied";
        window.setTimeout(() => {
          btn.textContent = original;
        }, 1500);
      });
    });
  });
}

function initSearch(): void {
  const input = $("#docs-search");
  if (!(input instanceof HTMLInputElement)) return;
  const items = $$(".doc-item");
  input.addEventListener("input", () => {
    const q = input.value.toLowerCase();
    items.forEach((it) => {
      it.style.display = it.textContent?.toLowerCase().includes(q) === false ? "none" : "";
    });
  });
}

/* ------------------------------------------------------------------ *
 * Boot
 * ------------------------------------------------------------------ */

function boot(): void {
  document.documentElement.classList.add("js");

  const mm = gsap.matchMedia();

  initEmbers(mm);
  initHero(mm);
  initTerminal(mm);
  initCounters(mm);
  initBars(mm);
  initPipeline(mm);
  initReveals(mm);
  initStatBand(mm);

  initCopy();
  initSearch();

  // Fonts change line boxes; re-measure once they land.
  void document.fonts?.ready.then(() => ScrollTrigger.refresh());
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}