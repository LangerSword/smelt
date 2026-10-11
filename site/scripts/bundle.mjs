#!/usr/bin/env node
/**
 * smelt site JS build.
 *
 *   node scripts/bundle.mjs          build
 *   node scripts/bundle.mjs --check  fail if assets/js/site.js is stale vs src/
 *
 * tsc compiles src/site.ts (ES2020 modules) to build/js/site.js; this script
 * wraps it in an IIFE, minifies it with esbuild, and writes assets/js/site.js.
 * The build stamp records the source hash so CI can detect a stale bundle.
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const srcFile = join(siteDir, "src", "site.ts");
const outDir = join(siteDir, "build", "js");
const compiledFile = join(outDir, "site.js");
const targetFile = join(siteDir, "assets", "js", "site.js");
const minFile = join(outDir, "site.min.js");

const checkOnly = process.argv.includes("--check");

function run(cmd, args) {
  return execFileSync(cmd, args, { cwd: siteDir, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function typecheck() {
  run("npx", ["tsc", "-p", "tsconfig.json"]);
}

function compile() {
  if (!existsSync(compiledFile)) {
    throw new Error(`tsc did not emit ${compiledFile}`);
  }
  return readFileSync(compiledFile, "utf8");
}

/**
 * Minify with the local esbuild binary (a devDependency). Called directly
 * rather than through npx, which does not reliably resolve the local binary
 * in this environment. Falls back to the unminified body rather than failing
 * the build — the bundle stays correct either way, only the bytes differ.
 */
function minify(code) {
  const esbuild = join(siteDir, "node_modules", "esbuild", "bin", "esbuild");
  if (!existsSync(esbuild)) {
    console.warn("esbuild not installed, shipping unminified");
    return code;
  }
  try {
    return execFileSync(esbuild, ["--minify", "--target=es2020", "--log-level=warning"], {
      cwd: siteDir,
      input: code,
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (err) {
    console.warn("esbuild minify failed, shipping unminified:", String(err).slice(0, 160));
    return code;
  }
}

function stamp(source) {
  return [
    "/* smelt site — built from src/site.ts by scripts/bundle.mjs.",
    ` * source sha256: ${sha256(source)}`,
    " * Do not edit by hand; run: npm run build",
    " */",
    "",
  ].join("\n");
}

const src = readFileSync(srcFile);
const expectedStamp = stamp(src);

if (checkOnly) {
  if (!existsSync(targetFile)) {
    console.error("FAIL: assets/js/site.js does not exist — run npm run build");
    process.exit(1);
  }
  const current = readFileSync(targetFile, "utf8");
  if (!current.startsWith(expectedStamp.split("\n").slice(0, 3).join("\n"))) {
    console.error("FAIL: assets/js/site.js is stale — src/site.ts changed, run npm run build");
    process.exit(1);
  }
  console.log("assets/js/site.js is up to date");
  process.exit(0);
}

typecheck();
const compiled = compile();

mkdirSync(outDir, { recursive: true });
mkdirSync(dirname(targetFile), { recursive: true });

// tsc emits ESM imports of gsap; the page loads gsap as globals via the
// vendored <script> tags, so strip the import/export lines before wrapping.
const body = compiled
  .replace(/^import[^;]+;$/gm, "")
  .replace(/^export \{[^}]*\};?$/gm, "")
  .replace(/^export default .*$/gm, "")
  .trim();

// Minify only the body, then prepend the stamp: a minifier would strip the
// stamp comment, and the stamp is what --check uses to detect a stale build.
const wrapper = `(() => {\n"use strict";\n${body}\n})();\n`;
const minifiedBody = minify(wrapper);
writeFileSync(targetFile, `${expectedStamp}${minifiedBody.trim()}\n`);

rmSync(join(siteDir, "build"), { recursive: true, force: true });

const rawBytes = Buffer.byteLength(wrapper);
const outBytes = Buffer.byteLength(readFileSync(targetFile));
console.log(
  `wrote assets/js/site.js (${(outBytes / 1024).toFixed(1)} KB, minified from ${(rawBytes / 1024).toFixed(1)} KB)`,
);