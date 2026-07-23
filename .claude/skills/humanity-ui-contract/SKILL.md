---
name: humanity-ui-contract
description: Use BEFORE and AFTER any edit to ui/index.html, ui/styles.css or ui/app.js — the Humanity UI is pinned by pytest contracts, ~163 DOM id references, exact CSS selector literals, localStorage schemas and a scientific-honesty framing that must never regress.
---

# Humanity UI contract

## Scientific honesty (non-negotiable)
- The agent is **never** presented as conscious, sentient or alive. Introspective text = generated from internal variables.
- Never invent data: a `null`/absent value renders as `—` or an explicit "not enough data" state — never a fabricated number.
- Battery/LLM responses carry server-side `disclaimer`/`interpretation` fields: render them **verbatim**.
- The permanent boundary line + expandable disclaimer (`#framing-text`, `#footer-disclaimer`, boundary dialog) must stay reachable from every view.
- Electrum accent = reserved signal (real ignition, live state, primary action). No decorative glow.

## Hard contracts (break these → pytest fails)
Run `node scripts/check_ui_contract.mjs` after every UI edit; it verifies most of the list below.
- `tests/test_interaction_ui.py` + `tests/test_phase7_ui.py` grep ui/* literally: JS function names
  (renderHorizon, renderIgnitionDynamics, renderHorizonStream, refreshMemoryGraph, drawMemoryGraph,
  activateIntervention, submitIntervention, appendInterventionLog, mapWorldPointToGrid,
  postWorldStimulusAt, drawWorldCursor…), race markers (refreshInFlight, refreshQueued,
  horizonGeneration, resetHorizonClientState, stepInFlight, interventionPending), exact call ORDER
  inside #btn-step / #btn-reset / checkpoint-load / society-apply listeners, `Math.random` forbidden,
  memory-graph throttle `requestedTick - lastMemoryGraphTick < 20` (and no `% 20`).
- Pinned CSS literals: `.panel-interventions`, `.intervention-tabs`, `.interaction-log`,
  `.world-interaction-tools`, `#world-canvas:focus-visible`, `.panel-horizon`, `.horizon-readouts`,
  `.memory-graph-shell`, `.sr-only`, `#world-interaction-status { color: var(--ink-soft); }`,
  `.interaction-sequence { color: var(--ink-soft);`, `body.is-scrolled .tps-field { display: none; }`,
  `body.is-scrolled .transport-buttons`.
- ARIA pins: `#interaction-log` + `#world-interaction-status` aria-live polite; `#horizon-task` and
  `#ignition-chart-summary` must NOT be aria-live; `#memory-graph` tabindex=0 +
  aria-describedby="memory-graph-summary memory-graph-nodes memory-graph-edges"; the two sr-only lists
  keep their exact aria-labels; `#world-canvas` tabindex=0 + aria-describedby=world-interaction-help;
  intervention tabs keep data-endpoint attrs for all five probes.
- Cache-buster: `styles.css?v=X` and `app.js?v=X` — same X, exactly twice in index.html, and the two
  pytest assertions (`test_interaction_ui.py` count + `test_phase7_ui.py` hrefs/srcs) must match X.
  Bump X on every UI change.
- app.js stays ONE file (tests grep it); no framework, no CDN, no network fonts, no telemetry.

## Soft contracts
- CSS variables read by canvases via `cssVar()`: `--accent --accent-bright --pos --neg --cool --curio
  --line --ink --ink-soft --ink-faint --bg-inset --mono` — keep the names, retune values only.
- JS selector hooks: `.panel-config input[data-flag]`, `#config-sliders .slider-row[data-key]` +
  `.slider-val`, `.panel-hero` + `is-ignited`, `#memory-search-form button[type='submit']`.
- localStorage: `humanity.settings` (merged over SETTINGS_DEFAULTS — additive migration only),
  `cws-theme` (`dark`|`light`), `humanity.view` (active hash view). Never rename without migration.
- API layer: polling via `refreshAll()` (350 ms) is the data backbone; `/ws/society` intentionally
  unused by the UI. Endpoints and payloads in docs/ui-redesign/02-contract-map.md.
- Full function without an LLM key: the 8 LLM endpoints 503 → inline "unavailable" message, never an error dialog.

## Non-regression checklist (run before claiming done)
1. `node --check ui/app.js` && `node scripts/check_ui_contract.mjs`
2. `python -m pytest tests/test_interaction_ui.py tests/test_phase7_ui.py -q` (fast) — full suite before finishing.
3. Browser: load `/ui/index.html`, Step, Run/Pause, Reset (confirm dialog), theme toggle, all 8 views
   reachable, console clean for 3 minutes of Run.
