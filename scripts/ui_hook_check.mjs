#!/usr/bin/env node
/**
 * ui_hook_check.mjs — PostToolUse hook body for Humanity.
 *
 * Reads the Claude Code hook payload on stdin; when the edited file is one of
 * the three UI sources, runs `node --check` (JS only) plus the static contract
 * checker. Exit 0 = fine / not a UI file; exit 2 = violation (the message is
 * fed back to the model). Fast and deterministic — no network, no pytest.
 */
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

let payload = {};
try {
  payload = JSON.parse(readFileSync(0, "utf8"));
} catch (e) {
  process.exit(0);
}
const file = String(
  (payload.tool_input || {}).file_path ||
  (payload.tool_response || {}).filePath || "",
).replace(/\\/g, "/");
if (!/\/ui\/(app\.js|index\.html|styles\.css)$/.test(file)) process.exit(0);

try {
  if (file.endsWith(".js")) {
    execFileSync(process.execPath, ["--check", file], { stdio: "pipe" });
  }
  execFileSync(process.execPath, ["scripts/check_ui_contract.mjs"], { stdio: "pipe" });
} catch (e) {
  console.error("UI contract hook failed:\n" + String(e.stderr || e.stdout || e.message));
  process.exit(2);
}
