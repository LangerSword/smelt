/**
 * Headless smoke test for the built site.
 *
 *   node scripts/smoke.mjs [--url http://localhost:8899]
 *
 * In a real browser, checks:
 *   1. zero console errors, zero 4xx/5xx
 *   2. GSAP + ScrollTrigger loaded
 *   3. hero headline words animate clear of the blur
 *   4. terminal replay renders every line, including the real verdict
 *   5. speedup bars reach their final scaleX
 *   6. counters (incl. the decimal speedup) reach their targets
 *   7. reduced-motion: content fully visible, no motion
 *   8. JS disabled: all content visible, nothing hidden
 *   9. results page: 24 rows, bars grown, rejections present
 */
import { chromium } from "playwright";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const BASE = process.argv.includes("--url")
  ? process.argv[process.argv.indexOf("--url") + 1]
  : "http://localhost:8899";

/**
 * Prefer a chromium already cached on this machine over the exact build this
 * playwright version pins — avoids a re-download in CI.
 */
function findChromium() {
  const root = join(homedir(), ".cache", "ms-playwright");
  if (!existsSync(root)) return undefined;
  const shells = readdirSync(root)
    .filter((d) => d.startsWith("chromium_headless_shell-"))
    .sort()
    .reverse();
  for (const d of shells) {
    const p = join(root, d, "chrome-headless-shell-linux64", "chrome-headless-shell");
    if (existsSync(p)) return p;
  }
  const full = readdirSync(root)
    .filter((d) => d.startsWith("chromium-"))
    .sort()
    .reverse();
  for (const d of full) {
    const p = join(root, d, "chrome-linux64", "chrome");
    if (existsSync(p)) return p;
  }
  return undefined;
}

const launchOpts = { args: ["--use-angle=swiftshader"] };
const exe = findChromium();
if (exe) launchOpts.executablePath = exe;

const browser = await chromium.launch(launchOpts);

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

/**
 * GSAP finishes a scaleX tween with `scale(x, 1)` or leaves it as
 * `matrix(a,b,c,d,...)` — parse both and return the horizontal scale.
 */
function readScaleX(transform) {
  if (!transform || transform === "none") return 0;
  let m = transform.match(/^matrix\(([-\d.e]+),/);
  if (m) return Number.parseFloat(m[1]);
  m = transform.match(/^scale\(([-\d.e]+)/);
  if (m) return Number.parseFloat(m[1]);
  m = transform.match(/^scale3d\(([-\d.e]+)/);
  if (m) return Number.parseFloat(m[1]);
  return 0;
}

function scrollAll(page, ms = 110) {
  return page.evaluate(async (delay) => {
    const step = window.innerHeight * 0.6;
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, delay));
    }
    window.scrollTo(0, document.body.scrollHeight);
  }, ms);
}

/* ---------------- 1. Home: normal load ---------------- */
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  const bad = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`);
  });

  await page.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);

  check("no console/page errors", errors.length === 0, errors.slice(0, 3).join(" | "));
  check("no 4xx/5xx requests", bad.length === 0, bad.slice(0, 3).join(" | "));

  const gsapOk = await page.evaluate(() => typeof window.gsap !== "undefined");
  const stOk = await page.evaluate(() => typeof window.ScrollTrigger !== "undefined");
  check("GSAP + ScrollTrigger present", gsapOk && stOk, `gsap=${gsapOk} st=${stOk}`);

  // Hero words should have cleared the blur animation
  await page.waitForTimeout(2200);
  const hero = await page.evaluate(() => {
    const words = Array.from(document.querySelectorAll(".hero h1 .word"));
    return words.map((el) => {
      const cs = getComputedStyle(el);
      return { op: Number.parseFloat(cs.opacity), vis: cs.visibility, filter: cs.filter };
    });
  });
  const allClear = hero.length > 0 && hero.every((w) => w.op > 0.9 && w.vis !== "hidden");
  check("hero words fully revealed", allClear, `${hero.length} words, first opacity=${hero[0]?.op}`);

  const canvasOk = await page.evaluate(() => {
    const c = document.querySelector("#hero-canvas");
    return !!c && c.width > 0 && c.height > 0;
  });
  check("hero ember canvas sized", canvasOk);

  /* ---------------- scroll the rest ---------------- */
  await scrollAll(page);
  await page.waitForTimeout(2600);

  const termLines = await page.evaluate(
    () => document.querySelectorAll("#demo-terminal .terminal-body span").length,
  );
  check("terminal replay rendered lines", termLines >= 10, `${termLines} lines`);

  const termText = await page.evaluate(
    () => document.querySelector("#demo-terminal .terminal-body")?.textContent ?? "",
  );
  check("terminal shows the real verdict", /INGOT/.test(termText) && /4\.14x/.test(termText));

  const barTransforms = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".speedup-bar-fill")).map(
      (el) => getComputedStyle(el).transform,
    ),
  );
  // Home carries the stats band, not the per-function bars (those live on
  // Results). Only assert here when bars are actually present.
  if (barTransforms.length > 0) {
    const barsGrown = barTransforms.map(readScaleX).filter((sx) => sx > 0.01).length;
    check(
      "speedup bars grown (scaleX)",
      barsGrown === barTransforms.length,
      `${barsGrown}/${barTransforms.length}`,
    );
  } else {
    check("home uses the stats band (no per-function bars)", true);
  }

  const counters = await page.evaluate(() =>
    Array.from(document.querySelectorAll("[data-count]")).map((el) => ({
      target: el.getAttribute("data-count"),
      text: el.textContent,
    })),
  );
  const countersOk =
    counters.length > 0 &&
    counters.every((c) => {
      const t = Number.parseFloat(c.target ?? "0");
      const v = Number.parseFloat(c.text ?? "0");
      return Math.abs(t - v) < 0.005;
    });
  check("counters reached targets", countersOk, JSON.stringify(counters.slice(0, 4)));

  const stCount = await page.evaluate(() => window.ScrollTrigger.getAll().length);
  check("ScrollTriggers created", stCount > 8, `${stCount} triggers`);

  // Guard: after a full scroll-through, no content may remain stuck invisible.
  // This catches two animations owning one element (a from-state stranding it
  // at opacity 0), which is otherwise invisible to the other checks.
  const stranded = await page.evaluate(() => {
    const sel = [
      ".trust-item", ".card", ".verdict", ".stat", ".stat .num", ".feature-row",
      ".badge", ".hero h1 .word", ".hero-lead", ".hero-actions", ".hero-pill",
      ".stack-item",
    ].join(", ");
    return Array.from(document.querySelectorAll(sel))
      .filter((el) => {
        const cs = getComputedStyle(el);
        return Number.parseFloat(cs.opacity) < 0.9 || cs.visibility === "hidden";
      })
      .map((el) => `${el.tagName}.${String(el.className).split(" ")[0]} op=${getComputedStyle(el).opacity} vis=${getComputedStyle(el).visibility}`)
      .slice(0, 6);
  });
  check("no content left stuck invisible after scroll", stranded.length === 0, stranded.join(" | "));

  const gifOk = await page.evaluate(() => {
    const img = document.querySelector('img[src*="furnace-demo"]');
    return !!img && img.naturalWidth > 0;
  });
  check("furnace GIF loads", gifOk);

  const svgOk = await page.evaluate(() => {
    const svgs = Array.from(document.querySelectorAll('img[src$=".svg"]'));
    return svgs.length >= 2 && svgs.every((i) => i.naturalWidth > 0);
  });
  check("illustration SVGs load", svgOk);

  await page.close();
}

/* ---------------- 2. Reduced motion ---------------- */
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(`${BASE}/index.html`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);

  const termLines = await page.evaluate(
    () => document.querySelectorAll("#demo-terminal .terminal-body span").length,
  );
  check("reduced-motion: all terminal lines visible", termLines >= 10, `${termLines} lines`);

  const counters = await page.evaluate(() =>
    Array.from(document.querySelectorAll("[data-count]")).every(
      (el) => el.textContent === el.getAttribute("data-count"),
    ),
  );
  check("reduced-motion: counters final", counters);

  const hidden = await page.evaluate(() =>
    Array.from(
      document.querySelectorAll(".card, .verdict, .stat, .feature-row, .hero h1 .word, .trust-item"),
    ).filter((el) => Number.parseFloat(getComputedStyle(el).opacity) < 0.9).length,
  );
  check("reduced-motion: nothing left faded out", hidden === 0, `${hidden} faded`);

  check("reduced-motion: no page errors", errors.length === 0, errors.slice(0, 2).join(" | "));
  await page.close();
}

/* ---------------- 3. JS disabled ---------------- */
{
  const ctx = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1280, height: 900 },
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/index.html`, { waitUntil: "domcontentloaded" });

  const h1 = await page.evaluate(
    () => (document.querySelector(".hero h1")?.textContent ?? "").replace(/\s+/g, " ").trim(),
  );
  check("JS disabled: hero copy present", /Only proven metal ships/.test(h1), h1.slice(0, 60));

  const counts = await page.evaluate(() => ({
    verdicts: document.querySelectorAll(".verdict").length,
    cards: document.querySelectorAll(".card").length,
    stats: document.querySelectorAll(".stat").length,
    features: document.querySelectorAll(".feature-row").length,
    trust: document.querySelectorAll(".trust-item").length,
  }));
  check(
    "JS disabled: all sections present",
    counts.verdicts === 3 && counts.cards === 4 && counts.stats === 4 && counts.features === 4,
    JSON.stringify(counts),
  );

  const hidden = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".card, .verdict, .stat, .feature-row, .hero h1 .word")).filter(
      (el) => Number.parseFloat(getComputedStyle(el).opacity) < 0.9,
    ).length,
  );
  check("JS disabled: nothing hidden by baseline CSS", hidden === 0, `${hidden} hidden`);

  await ctx.close();
}

/* ---------------- 4. Results page ---------------- */
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${BASE}/results.html`, { waitUntil: "networkidle" });
  await scrollAll(page);
  await page.waitForTimeout(2400);

  const rows = await page.evaluate(() => document.querySelectorAll(".results-table tbody tr").length);
  check("results page: 24 rows", rows === 24, `${rows} rows`);

  const bars = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".speedup-bar-fill")).map((el) => getComputedStyle(el).transform),
  );
  const grown = bars.map(readScaleX).filter((sx) => sx > 0.01).length;
  check("results page: all bars grown", grown === bars.length && grown > 0, `${grown}/${bars.length}`);

  const rejectedShown = await page.evaluate(() => {
    const t = document.querySelector(".results-table")?.textContent ?? "";
    return /rejected/.test(t) && /linear_score/.test(t);
  });
  check("results page: rejections shown", rejectedShown);

  const cliOk = await page.evaluate(() => {
    const t = document.body.textContent ?? "";
    return /smelt run/.test(t) && /Exit codes|exit code/i.test(t);
  });
  check("results page: CLI reference present", cliOk);

  check("results page: no errors", errors.length === 0, errors.slice(0, 2).join(" | "));
  await page.close();
}

/* ---------------- 5. Other pages load clean ---------------- */
{
  for (const p of ["docs.html", "install.html", "changelog.html", "roadmap.html"]) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`${BASE}/${p}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    const navOk = await page.evaluate(() => !!document.querySelector(".site-nav .brand"));
    const footOk = await page.evaluate(() => !!document.querySelector(".footer-cols"));
    check(`${p}: nav + footer render`, navOk && footOk);
    check(`${p}: no page errors`, errors.length === 0, errors.slice(0, 2).join(" | "));
    await page.close();
  }
}

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length === 0 ? 0 : 1);