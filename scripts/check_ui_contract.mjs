#!/usr/bin/env node
/**
 * check_ui_contract.mjs — static UI contract checker for Humanity.
 *
 * Verifies, without a browser:
 *   1. every element id literally referenced from ui/app.js exists in ui/index.html;
 *   2. the CSS selectors pinned by tests/test_interaction_ui.py and
 *      tests/test_phase7_ui.py are present in ui/styles.css;
 *   3. both static assets carry the same ?v= cache-buster in ui/index.html.
 *
 * Exit 0 = contracts hold. Exit 1 = violations (printed one per line).
 * Used by the humanity-ui-contract skill and the PostToolUse hook.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => readFileSync(join(root, p), "utf8");

const html = read("ui/index.html");
const js = read("ui/app.js");
const css = read("ui/styles.css");

const violations = [];

/* ---- 1. ids referenced from JS must exist in the HTML ---- */
const htmlIds = new Set([...html.matchAll(/\bid="([\w-]+)"/g)].map((m) => m[1]));
const jsNoComments = js
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
const refPatterns = [
  /\$\(\s*"#([\w-]+)/g,                      // $("#id ...")
  /\$\(\s*'#([\w-]+)/g,
  /getElementById\(\s*["']([\w-]+)["']\s*\)/g,
  /querySelector(?:All)?\(\s*"#([\w-]+)/g,
  /querySelector(?:All)?\(\s*'#([\w-]+)/g,
];
const referenced = new Set();
for (const re of refPatterns) {
  for (const m of jsNoComments.matchAll(re)) referenced.add(m[1]);
}
for (const id of [...referenced].sort()) {
  if (!htmlIds.has(id)) violations.push(`app.js references #${id} but index.html has no such id`);
}

/* ---- 2. selectors pinned by the pytest UI contract ---- */
const requiredCssLiterals = [
  ".panel-interventions",
  ".intervention-tabs",
  ".interaction-log",
  ".world-interaction-tools",
  "#world-canvas:focus-visible",
  ".panel-horizon",
  ".horizon-readouts",
  ".memory-graph-shell",
  ".sr-only",
  "#world-interaction-status { color: var(--ink-soft); }",
  ".interaction-sequence { color: var(--ink-soft);",
];
for (const literal of requiredCssLiterals) {
  if (!css.includes(literal)) violations.push(`styles.css is missing pinned selector/rule: ${literal}`);
}

/* ---- 3. cache-buster coherence ---- */
const cssV = html.match(/styles\.css\?v=([\w.]+)/);
const jsV = html.match(/app\.js\?v=([\w.]+)/);
if (!cssV || !jsV) violations.push("index.html must version both static assets with ?v=");
else if (cssV[1] !== jsV[1]) violations.push(`asset versions differ: styles.css?v=${cssV[1]} vs app.js?v=${jsV[1]}`);

/* ---- 4. determinism guard (mirrors pytest) ---- */
if (jsNoComments.includes("Math.random")) violations.push("app.js must stay deterministic: Math.random is forbidden");

if (violations.length) {
  console.error(`UI contract check FAILED (${violations.length} violation${violations.length > 1 ? "s" : ""}):`);
  for (const v of violations) console.error("  - " + v);
  process.exit(1);
}
console.log(`UI contract check OK — ${referenced.size} JS id references all resolved; pinned selectors present; assets at ?v=${cssV[1]}.`);
