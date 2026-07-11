---
name: humanity-visual-qa
description: Use whenever visually validating the Humanity UI (after any ui/* change, before claiming a milestone done) — defines the capture viewports, test journeys, visual criteria and where screenshots live.
---

# Humanity visual QA

## Launch recipe
`PORT=8123 python run.py` (never touch a server already on 8000 — it may be the user's).
UI at `http://127.0.0.1:8123/ui/index.html`. Drive with Playwright MCP; check
`browser_console_messages(onlyErrors)` after every journey — 0 unexplained errors.

## Capture viewports (validate ALL at milestones; the starred three for quick checks)
1600×1000 · **1440×900** · 1280×800 · 1024×768 · **768×1024** · **390×844** · 360×800

## Test journeys
1. **Cold start**: load → Overview renders with "awaiting" states (no fake data), boundary line visible,
   0 console errors.
2. **Live run**: Run at 4 tps → aperture + moment + tiles update; navigate all 8 hash views during the
   run; return to Overview; pause. No listener duplication (Step once → exactly one tick).
3. **Interventions**: each of the 5 probes once → request+result rows in the causal ledger.
4. **World**: click a cell → stimulus lands; keyboard (focus grid, arrows, Enter) → same.
5. **Society**: set 3 agents → canvases + relations + language update; select agent; back to 1 agent.
6. **Laboratory**: one battery (mirror), scenario textarea run, CSV/JSON export click, checkpoint
   save/list/load/delete, coverage list populated.
7. **Memory**: search a word; keyboard through graph nodes (arrows/Home/End/Escape); tooltip on focus.
8. **Settings**: search filters params; slider change hot-applies (POST /config); structural field warns
   reset; toggles persist across reload.
9. **Theme + reduced motion**: toggle light (archive paper) — check every view; emulate
   `prefers-reduced-motion` → no pulse/flash, states still readable.
10. **LLM-less**: narrate/converse/biography/cross-examine/audit/report-card/inner-voice → inline
    "unavailable (set OPENROUTER_API_KEY)" message, no dialog, no console error.

## Visual criteria
- No horizontal scroll at any viewport; no overlapping/truncated critical control; focus ring visible on
  every interactive element in BOTH themes; touch targets ≥ 44px on mobile.
- Alignment: values right-aligned in mono; meters share a common label column; threshold ticks crisp
  (0.5px offset on hairlines); canvas sharp at devicePixelRatio > 1.
- Density: hero > panel > group > inset hierarchy readable; no wall of identical cards.
- Electrum glow ONLY on: real ignition, live/running status, primary action. Nothing else may pulse.
- Empty/null = "—" or explicit empty state; NEVER an invented number; disclaimers rendered verbatim.

## Screenshot conventions
- Location: `docs/ui-redesign/screenshots/`
- Baseline: `before-*.png` (already captured). Finals: `after-<view>-<width>.png` +
  `after-light-<width>.png` + `after-mobile-<view>-390.png`.
- Compare against `before-*` at the same viewport before signing off a milestone.
