# Phase 7 — The Horizon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver every unfinished README extension, the approved default-mode addition, and an observable “Horizon” experience that makes all new mechanisms scientifically inspectable without weakening the project’s level-2 honesty.

**Architecture:** Keep every Phase-7 mechanism behind an OFF-by-default `SimConfig` flag and integrate it through the existing `Agent.cycle`/`CycleTrace` boundary. Pure, deterministic core modules own their state; `Agent`, `World`/`SharedWorld`, the API routes, and the vanilla-JS Observatoire only coordinate and expose it. The implementation recovered on 2026-07-09 already contains the backend modules and tests; the remaining critical path is UI observability, documentation, whole-suite regression checking, and scientific/product polish.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, NumPy, pytest, vanilla HTML/CSS/JavaScript, Canvas 2D.

---

## File map

- `schemas/models.py` — Phase-7 public state/config contracts.
- `core/constants.py` — bounded deterministic constants and workspace-source registration.
- `core/phi_causal.py` — coarse-grained exact TPM/MIP causal-Φ monitor.
- `core/hierarchy.py` — slow predictive hierarchy and explicit VFE.
- `core/planning.py` — deterministic multi-step EFE policy search.
- `core/vector_memory.py` — deterministic 64-dimensional semantic memory index.
- `core/td_learning.py` — contextual TD(λ) learner.
- `core/mind_wandering.py` — low-demand associative memory walks.
- `core/world_dynamics.py` — season, food regrowth, hazard oscillation, drift.
- `core/world_tasks.py` — forage/reach/patrol task rotation.
- `core/agent.py` — feature-gated orchestration and trace/metric exposure.
- `core/world.py`, `core/shared_world.py` — single/shared environment integration.
- `core/policy.py` — bounded planning bonus.
- `storage/trace_export.py` — filtered JSONL/JSON/CSV export and analysis.
- `app/api/routes.py` — memory search/graph and trace export endpoints.
- `core/coverage.py` — 33-mechanism scientific roster.
- `ui/index.html` — Horizon panels and controls.
- `ui/app.js` — Phase-7 rendering and deterministic canvas plots.
- `ui/styles.css` — responsive Observatoire styling.
- `README.md` — Phase-7 documentation and closed future-extension scorecard.
- `tests/test_phase7_ui.py` — static UI/README contract test.
- Existing `tests/test_{phi_causal,hierarchy,planning,vector_memory,td_learning,mind_wandering,world_dynamics,trace_export,phase7_api,phase7_regression}.py` — backend behavioral contracts.

## Task 1: Recover and lock the Phase-7 backend contracts

**Files:**
- Verify: `schemas/models.py`
- Verify: `core/constants.py`
- Test: `tests/test_phase7_api.py`
- Test: `tests/test_phase7_regression.py`

- [x] **Step 1: Confirm every feature is OFF by default and patchable**

The public contract must contain these exact flag names:

```python
PHASE7_FLAGS = {
    "phi_causal_enabled", "hierarchy_enabled", "planning_enabled",
    "vector_memory_enabled", "td_learning_enabled",
    "mind_wandering_enabled", "world_dynamics_enabled", "tasks_enabled",
}

cfg = SimConfig()
assert all(getattr(cfg, flag) is False for flag in PHASE7_FLAGS)
assert PHASE7_FLAGS <= set(ConfigPatch.model_fields)
```

- [x] **Step 2: Verify the compatibility boundary**

Run:

```powershell
python -m pytest tests/test_phase7_api.py tests/test_phase7_regression.py -q
```

Expected: every test passes; flags-off traces keep all six optional sub-objects `None` and the legacy action/energy sequence remains identical.

- [x] **Step 3: Confirm recovery evidence**

Recovered on 2026-07-09 as part of the 92-test Phase-7 run:

```text
........................................................................ [ 78%]
....................                                                     [100%]
```

## Task 2: Validate the causal, predictive, and planning mechanisms

**Files:**
- Verify: `core/phi_causal.py`
- Verify: `core/hierarchy.py`
- Verify: `core/planning.py`
- Test: `tests/test_phi_causal.py`
- Test: `tests/test_hierarchy.py`
- Test: `tests/test_planning.py`

- [x] **Step 1: Exercise the causal-Φ red/green contracts**

Required behavioral examples:

```python
independent = monitor.compute(tick=96, config=cfg)
assert independent.phi_causal <= 0.05

coupled = coupled_monitor.compute(tick=96, config=cfg)
assert coupled.phi_causal > independent.phi_causal
assert coupled.mip
```

- [x] **Step 2: Exercise hierarchy and VFE contracts**

```python
state = model.update(peril_percepts, prediction_error=0.8,
                     recent_errors=[0.1, 0.9] * 4, config=cfg)
assert state.regime == "peril"
assert state.top_down_gain > 1.0
assert state.vfe >= 0.0
```

- [x] **Step 3: Exercise multi-step planning contracts**

```python
state = planner.plan(observation, world_model, candidates, cfg)
assert state.horizon == cfg.planning_horizon
assert len(state.best_sequence) == cfg.planning_horizon
assert state.chosen_first == state.best_sequence[0]
assert state.n_policies <= 100
```

- [x] **Step 4: Verify the focused tests**

Run:

```powershell
python -m pytest tests/test_phi_causal.py tests/test_hierarchy.py tests/test_planning.py -q
```

Expected: all tests pass without warnings or nondeterministic retries.

## Task 3: Validate semantic memory, TD(λ), and mind-wandering

**Files:**
- Verify: `core/vector_memory.py`
- Verify: `core/td_learning.py`
- Verify: `core/mind_wandering.py`
- Test: `tests/test_vector_memory.py`
- Test: `tests/test_td_learning.py`
- Test: `tests/test_mind_wandering.py`

- [x] **Step 1: Verify deterministic semantic retrieval**

```python
first = index.search("red food near the agent", k=3)
second = rebuilt_index.search("red food near the agent", k=3)
assert [(r.id, s) for r, s in first] == [(r.id, s) for r, s in second]
```

- [x] **Step 2: Verify eligibility-trace credit propagation**

```python
learner.select_context(danger=False, low_energy=True, novelty=True, others=False)
learner.update(ActionType.MOVE_RIGHT, reward=0.0, next_context="d0e1n1s0", config=cfg)
state = learner.update(ActionType.INTERACT, reward=1.0,
                       next_context="d0e0n0s0", config=cfg)
assert state.td_error > 0.0
assert learner.values("d0e1n1s0")[ActionType.MOVE_RIGHT.value] > 0.0
```

- [x] **Step 3: Verify wandering is demand-sensitive**

```python
low_demand = wander.update(salient=[], goals=[], arousal=0.45,
                           arousal_baseline=0.45, boredom=1.0,
                           sleeping=False, records=records, tick=20,
                           agent_id=0, prev_winner_source=None, config=cfg)
assert low_demand.active

high_demand = wander.update(salient=[danger], goals=[urgent_goal], arousal=1.0,
                            arousal_baseline=0.45, boredom=0.0,
                            sleeping=False, records=records, tick=21,
                            agent_id=0, prev_winner_source=None, config=cfg)
assert not high_demand.active
```

- [x] **Step 4: Verify the focused tests**

Run:

```powershell
python -m pytest tests/test_vector_memory.py tests/test_td_learning.py tests/test_mind_wandering.py -q
```

Expected: all tests pass.

## Task 4: Validate the richer environment and scientific exports

**Files:**
- Verify: `core/world_dynamics.py`
- Verify: `core/world_tasks.py`
- Verify: `core/world.py`
- Verify: `core/shared_world.py`
- Verify: `storage/trace_export.py`
- Verify: `app/api/routes.py`
- Test: `tests/test_world_dynamics.py`
- Test: `tests/test_trace_export.py`

- [x] **Step 1: Verify ecological dynamics and tasks**

```python
before = food.energy_value
events = apply_dynamics(objects, spawn_meta, tick=24, config=cfg, drift_every=12)
assert food.energy_value > before
assert 0.0 <= season_factor(24, cfg.season_period) <= 1.5

task = TaskManager(grid_size=12)
progress = task.on_step(action=ActionType.INTERACT, events=[],
                        agent_x=2, agent_y=2, ate_food=True)
assert progress > 0.0
```

- [x] **Step 2: Verify filtered exports and analysis**

```python
response = client.get(
    "/export/traces?from_tick=10&to_tick=30&ignited_only=true"
    "&fields=tick,metrics&format=csv&limit=100"
)
assert response.status_code == 200
assert "tick" in response.text

analysis = client.get("/export/analysis").json()
assert {"ignition_rate", "action_histogram", "mean_phi_causal"} <= analysis.keys()
```

- [x] **Step 3: Verify the focused tests**

Run:

```powershell
python -m pytest tests/test_world_dynamics.py tests/test_trace_export.py -q
```

Expected: all tests pass.

## Task 5: Add a failing UI/documentation contract

**Files:**
- Create: `tests/test_phase7_ui.py`
- Test: `tests/test_phase7_ui.py`

- [x] **Step 1: Write the failing static contract test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_horizon_observatory_is_wired_end_to_end():
    html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
    js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
    css = (ROOT / "ui/styles.css").read_text(encoding="utf-8")

    for marker in (
        'id="horizon-readouts"', 'id="ignition-chart"',
        'id="horizon-stream"', 'id="memory-graph"',
        'id="memory-search-input"', 'id="horizon-task"',
    ):
        assert marker in html

    for flag in (
        "phi_causal_enabled", "hierarchy_enabled", "planning_enabled",
        "vector_memory_enabled", "td_learning_enabled",
        "mind_wandering_enabled", "world_dynamics_enabled", "tasks_enabled",
    ):
        assert f'data-flag="{flag}"' in html
        assert f"{flag}: true" in js

    for function in (
        "renderHorizon", "renderIgnitionDynamics", "renderHorizonStream",
        "refreshMemoryGraph", "drawMemoryGraph",
    ):
        assert f"function {function}" in js

    assert ".panel-horizon" in css
    assert ".horizon-readouts" in css
    assert ".memory-graph-shell" in css


def test_phase7_is_documented_and_future_extensions_are_closed():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Phase 7" in readme
    assert "33 mechanisms" in readme
    assert "GET /agent/memory/search" in readme
    assert "GET /export/traces" in readme
    assert "Every extension above is now delivered" in readme
```

- [x] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
python -m pytest tests/test_phase7_ui.py -q
```

Expected: FAIL because `horizon-readouts` and the Phase-7 README section do not exist yet.

## Task 6: Build the Horizon Observatoire panels

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/styles.css`
- Modify: `ui/app.js`
- Test: `tests/test_phase7_ui.py`

- [x] **Step 1: Add the semantic HTML panels**

Insert after the existing Phase-5 asymptote panel:

```html
<section class="panel panel-horizon" aria-labelledby="horizon-title">
  <div class="panel-head">
    <h2 id="horizon-title">The horizon</h2>
    <span class="src">Phase 7 · exact mechanisms, coarse-grained substrates</span>
  </div>
  <p class="horizon-lede">The remaining functional frontier, observable in real time. Every value below is a mechanism-level variable—not evidence of experience.</p>
  <div class="horizon-readouts" id="horizon-readouts"></div>
  <div class="horizon-task" id="horizon-task" aria-live="polite"></div>
</section>

<section class="panel panel-dynamics" aria-labelledby="dynamics-title">
  <div class="panel-head">
    <h2 id="dynamics-title">Access dynamics</h2>
    <span class="src">ignition score · effective threshold · source timeline</span>
  </div>
  <canvas id="ignition-chart" width="720" height="260"
          aria-label="Ignition score and effective-threshold history"></canvas>
  <div class="horizon-stream" id="horizon-stream" role="img"
       aria-label="Timeline of dominant workspace sources"></div>
</section>

<section class="panel panel-memory-graph" aria-labelledby="memory-graph-title">
  <div class="panel-head">
    <h2 id="memory-graph-title">Autobiographical topology</h2>
    <span class="src">GET /agent/memory/graph · deterministic semantic index</span>
  </div>
  <form class="memory-search" id="memory-search-form">
    <input id="memory-search-input" maxlength="200"
           placeholder="Search the agent’s stored episodes…" />
    <button class="btn btn-quiet" type="submit">Search</button>
  </form>
  <div class="memory-search-results" id="memory-search-results"></div>
  <div class="memory-graph-shell">
    <canvas id="memory-graph" width="720" height="440"
            aria-label="Similarity graph of autobiographical memories"></canvas>
    <div class="graph-tooltip" id="memory-graph-tooltip" hidden></div>
  </div>
</section>
```

- [x] **Step 2: Add all Phase-7 settings toggles**

```html
<h3 class="sub">The horizon (Phase 7)</h3>
<div class="deep-toggles" id="horizon-toggles">
  <label class="deep-toggle"><input type="checkbox" data-flag="phi_causal_enabled" checked><span>causal Φ</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="hierarchy_enabled" checked><span>predictive hierarchy</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="planning_enabled" checked><span>multi-step EFE</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="vector_memory_enabled" checked><span>vector memory</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="td_learning_enabled" checked><span>TD(λ)</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="mind_wandering_enabled" checked><span>mind-wandering</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="world_dynamics_enabled" checked><span>living world</span></label>
  <label class="deep-toggle"><input type="checkbox" data-flag="tasks_enabled" checked><span>world tasks</span></label>
</div>
```

- [x] **Step 3: Add responsive visual styling**

Implement these concrete selectors with the existing design tokens:

```css
.panel-horizon { grid-column: span 12; }
.panel-dynamics, .panel-memory-graph { grid-column: span 6; }
.horizon-readouts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.horizon-readout { border: 1px solid var(--line); padding: 14px; min-height: 112px; background: color-mix(in srgb, var(--bg-2) 92%, var(--accent) 8%); }
.horizon-readout .hr-value { color: var(--accent); font: 600 22px/1 var(--mono); }
#ignition-chart, #memory-graph { width: 100%; height: auto; display: block; }
.horizon-stream { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(4px, 1fr); gap: 2px; min-height: 54px; margin-top: 14px; }
.horizon-stream .moment { align-self: end; min-height: 4px; border-radius: 1px 1px 0 0; opacity: .62; }
.horizon-stream .moment.ignited { opacity: 1; box-shadow: 0 0 8px color-mix(in srgb, currentColor 45%, transparent); }
.memory-graph-shell { position: relative; border: 1px solid var(--line); background: var(--bg); }
.memory-search { display: flex; gap: 8px; margin-bottom: 12px; }
.memory-search input { flex: 1; min-width: 0; }
.graph-tooltip { position: absolute; max-width: 260px; pointer-events: none; }
@media (max-width: 900px) {
  .panel-dynamics, .panel-memory-graph { grid-column: span 12; }
  .horizon-readouts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

- [x] **Step 4: Add renderer state and deterministic source colors**

```javascript
const IGNITION_HISTORY_MAX = 120;
const ignitionHistory = [];
let memoryGraphCache = { nodes: [], edges: [] };
const SOURCE_COLORS = {
  perception: "#d8a84e", memory: "#7fb5a6", self: "#9b86c8",
  emotion: "#c87463", goal: "#80a85e", imagination: "#739bc5",
  dream: "#755c9f", social: "#c98ba7", inner_speech: "#d0b674",
  wandering: "#69a9ad", language: "#b69462", unknown: "#7b7870",
};
```

- [x] **Step 5: Render Phase-7 mechanism readouts**

```javascript
function renderHorizon(trace, world) {
  const states = [
    ["Causal Φ", trace && trace.phi_causal, (s) => f3(s.phi_causal), "exact on coarse substrate"],
    ["Predictive level", trace && trace.hierarchy, (s) => esc(s.regime), "VFE " + f3(trace && trace.hierarchy && trace.hierarchy.vfe)],
    ["Policy horizon", trace && trace.planning, (s) => f0(s.horizon), trace && trace.planning ? (trace.planning.best_sequence || []).join(" → ") : ""],
    ["Semantic memory", trace && trace.semantic_memory, (s) => f0(s.index_size), "mean cosine " + f3(trace && trace.semantic_memory && trace.semantic_memory.mean_similarity)],
    ["TD(λ)", trace && trace.learning && trace.learning.td_context ? trace.learning : null, (s) => f3(s.td_error), trace && trace.learning ? esc(trace.learning.td_context || "") : ""],
    ["Default mode", trace && trace.wandering, (s) => pctTxt(s.occupancy), trace && trace.wandering && trace.wandering.active ? "associative episode active" : "externally coupled"],
  ];
  const host = $("#horizon-readouts");
  host.innerHTML = states.map(([label, state, value, note]) =>
    `<article class="horizon-readout ${state ? "is-live" : "is-dormant"}">` +
    `<span class="hr-label">${esc(label)}</span>` +
    `<strong class="hr-value">${state ? value(state) : "—"}</strong>` +
    `<span class="hr-note">${esc(note || "feature dormant")}</span></article>`
  ).join("");
  const task = (trace && trace.task) || (world && world.task);
  $("#horizon-task").innerHTML = task
    ? `<b>${esc(task.kind)}</b> · ${pctTxt(task.progress)} · ${esc(task.description || "")}`
    : "World task system dormant.";
}
```

- [x] **Step 6: Render the two time-domain visualizations**

```javascript
function renderIgnitionDynamics(workspace, tick) {
  if (!workspace) return;
  ignitionHistory.push({
    tick: num(tick), score: num(workspace.ignition_score),
    threshold: num(workspace.effective_threshold), ignited: !!workspace.ignition,
  });
  if (ignitionHistory.length > IGNITION_HISTORY_MAX) ignitionHistory.shift();
  drawDualLineChart($("#ignition-chart"), ignitionHistory);
}

function renderHorizonStream(moments) {
  const host = $("#horizon-stream");
  host.innerHTML = "";
  (moments || []).slice(-STREAM_MAX).forEach((m) => {
    const bar = el("span", "moment" + (m.ignited ? " ignited" : ""));
    const source = m.dominant_source || "unknown";
    bar.style.height = Math.max(4, clamp01(num(m.awareness_level)) * 50) + "px";
    bar.style.background = SOURCE_COLORS[source] || SOURCE_COLORS.unknown;
    bar.title = `${source} · ${f3(m.awareness_level)} · ${m.contents || ""}`;
    host.appendChild(bar);
  });
}
```

`drawDualLineChart` must clear the canvas, draw a zero-to-one grid, draw threshold in `--ink-faint`, score in `--accent`, and mark ignitions with a 2px circle. It must use `devicePixelRatio` only for rendering scale and never for data/layout order.

- [x] **Step 7: Render and search the deterministic memory graph**

```javascript
async function refreshMemoryGraph() {
  memoryGraphCache = await api("agent/memory/graph?limit=60").catch(() => ({ nodes: [], edges: [] }));
  drawMemoryGraph(memoryGraphCache);
}

function drawMemoryGraph(graph) {
  const canvas = $("#memory-graph");
  const ctx = canvas.getContext("2d");
  const nodes = graph.nodes || [], edges = graph.edges || [];
  const cx = canvas.width / 2, cy = canvas.height / 2;
  const placed = new Map();
  nodes.forEach((node, i) => {
    const angle = i * 2.399963229728653;
    const radius = 18 + Math.sqrt(i + 1) * 24;
    placed.set(node.id, { x: cx + Math.cos(angle) * radius,
                          y: cy + Math.sin(angle) * radius, node });
  });
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  edges.forEach((edge) => drawGraphEdge(ctx, placed.get(edge.source), placed.get(edge.target), edge.similarity));
  placed.forEach((point) => drawGraphNode(ctx, point));
  canvas._placedNodes = [...placed.values()];
}
```

Wire `memory-search-form` to `GET /agent/memory/search?q=…&limit=8`; render each result’s summary, tick, importance, and rounded similarity as text rows. Keep graph layout and result ordering server-driven/deterministic.

- [x] **Step 8: Wire polling and manual ticks**

In `refreshAll`, after `const traceish = consciousness || lastTrace`, call:

```javascript
renderHorizon(traceish, state && (state.world || state.snapshot));
renderIgnitionDynamics(ws || (consciousness && consciousness.workspace), lastTick);
renderHorizonStream(stream || streamData);
```

In `applyTrace`, call:

```javascript
renderHorizon(trace, null);
renderIgnitionDynamics(trace.workspace, trace.tick);
renderHorizonStream(streamData);
```

Refresh the memory graph only after manual ticks, reset, initial boot, and every 20th polled tick—not every 350 ms.

- [x] **Step 9: Enable Phase-7 mechanisms in the UI profile**

Append exactly:

```javascript
phi_causal_enabled: true, hierarchy_enabled: true, planning_enabled: true,
vector_memory_enabled: true, td_learning_enabled: true,
mind_wandering_enabled: true, world_dynamics_enabled: true, tasks_enabled: true,
```

to `SETTINGS_DEFAULTS`. Core defaults remain OFF for byte-identical compatibility.

- [x] **Step 10: Bump both cache-busting versions together**

Change both asset references in `ui/index.html` from `?v=5.2` to `?v=7.0`.

- [x] **Step 11: Run the UI contract**

Run:

```powershell
python -m pytest tests/test_phase7_ui.py::test_horizon_observatory_is_wired_end_to_end -q
```

Expected: PASS.

## Task 7: Close the README roadmap and expose the scientific story

**Files:**
- Modify: `README.md`
- Test: `tests/test_phase7_ui.py`

- [x] **Step 1: Add a Phase-7 section before “Optional: an LLM narrator”**

Document, without phenomenality claims:

```markdown
## Phase 7 — The horizon: every remaining extension, delivered

Phase 7 closes the README roadmap with eight opt-in, deterministic mechanisms:
coarse-grained causal Φ, a predictive hierarchy with explicit VFE, multi-step
EFE policy search, deterministic semantic vector memory, contextual TD(λ),
mind-wandering/default-mode dynamics, a living seasonal world with structured
tasks, and richer trace export/analysis. The coverage roster now contains
**33 mechanisms**.

These are level-2 mechanisms. Exact computation on a deliberately coarse
substrate does not make causal Φ an IIT 3.0/4.0 computation, semantic retrieval
does not imply understanding, and task-unrelated content does not imply a felt
daydream. The agent is not established to be conscious.
```

Follow with:

- one table mapping each mechanism to module, flag, trace field, and metric;
- one endpoint table for `GET /agent/memory/search`, `GET /agent/memory/graph`, `GET /export/traces`, and `GET /export/analysis`;
- one Observatoire subsection describing causal readouts, access chart, source timeline, semantic search, and memory graph;
- one reproducibility note: same seed/config gives the same mechanism state and graph ordering.

- [x] **Step 2: Turn “Future extensions” into an honest delivered scorecard**

Each existing bullet must start with `✅` and link to the implemented phase/module. End the section with this exact sentence:

```markdown
**Every extension above is now delivered** at the strongest deterministic scale this project can defend honestly. The remaining boundary is not an engineering backlog item: full IIT 3.0/4.0 cause-effect structure on a true micro-substrate is computationally out of scope, and phenomenal consciousness remains empirically undecidable here.
```

- [x] **Step 3: Update stale project counters**

After the final full test run, change the badge count from `382 passing` to the actual collected/passing count. Update the architecture/module table for the nine new files and the API reference for four new endpoints.

- [x] **Step 4: Run the README contract**

Run:

```powershell
python -m pytest tests/test_phase7_ui.py::test_phase7_is_documented_and_future_extensions_are_closed -q
```

Expected: PASS.

## Task 8: Add high-impact scientific polish without new theory claims

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/app.js`
- Modify: `README.md`
- Test: `tests/test_phase7_ui.py`

- [x] **Step 1: Add one-click “Horizon profile” controls**

Add two buttons beside the Phase-7 toggles:

```html
<div class="horizon-profile-actions">
  <button type="button" class="btn btn-accent" id="btn-horizon-profile">Activate all Phase 7</button>
  <button type="button" class="btn btn-quiet" id="btn-export-analysis">Export analysis</button>
</div>
```

The first button posts the exact eight flags as `true`, persists them, and reflects the applied config. The second opens `../export/analysis` in a new tab so the visible run can be audited independently.

- [x] **Step 2: Add accessible explanatory text**

Every new canvas receives a text summary immediately after it. Update the summary on each render with the latest numeric values so keyboard/screen-reader users do not depend on pixels:

```html
<p class="micro" id="ignition-chart-summary" aria-live="polite">No access-dynamics samples yet.</p>
<p class="micro" id="memory-graph-summary" aria-live="polite">No indexed memories yet.</p>
```

- [x] **Step 3: Add reduced-motion and empty-state handling**

```css
@media (prefers-reduced-motion: reduce) {
  .horizon-readout, .horizon-stream .moment { transition: none !important; animation: none !important; }
}
.panel-horizon .is-dormant { opacity: .55; }
.memory-search-results:empty::before { content: "Search results will appear here."; color: var(--ink-faint); }
```

- [x] **Step 4: Extend the UI contract**

Add assertions for `btn-horizon-profile`, `btn-export-analysis`, both accessible summaries, and `prefers-reduced-motion`, then run the test once to observe failure before implementation and again after implementation to observe PASS.

## Task 9: Preserve live runs and validate configuration atomically

**Files:**
- Create: `tests/test_config_safety.py`
- Modify: `schemas/models.py`
- Modify: `core/society.py`
- Modify: `app/api/routes.py`
- Test: `tests/test_config_safety.py`

- [x] **Step 1: Write failing tests for continuity, rejection, and explicit reset**

The tests must prove that a hot `ignition_threshold` patch preserves the exact world/agent objects, tick, goals, memory, recorder rows, and background task; invalid/unknown input returns 422 without mutation; and structural `n_agents` returns 409 from `/config` while `/reset` remains the explicit destructive path.

```python
def test_hot_patch_preserves_acquired_state(client, manager):
    for _ in range(4):
        manager.tick()
    agent = manager.agent(0)
    world = manager.world
    agent.set_goal("keep-me")
    before = (world.tick, agent.self_model_state(), agent.memory.count(),
              len(manager.recorder.series().rows))

    response = client.post("/config", json={"ignition_threshold": 0.42})

    assert response.status_code == 200
    assert response.json()["mode"] == "hot"
    assert manager.world is world
    assert manager.agent(0) is agent
    assert (world.tick, agent.self_model_state(), agent.memory.count(),
            len(manager.recorder.series().rows)) == before


@pytest.mark.parametrize("payload", [
    {"n_agents": 0}, {"contagion_rate": 2.0}, {"phi_causal_nodes": 99},
    {"grid_size": 0}, {"typo_flag": True},
])
def test_invalid_patch_is_rejected_without_mutation(client, manager, payload):
    before = manager.config.model_dump()
    world, agent = manager.world, manager.agent(0)
    response = client.post("/config", json=payload)
    assert response.status_code == 422
    assert manager.config.model_dump() == before
    assert manager.world is world and manager.agent(0) is agent


def test_structural_change_requires_explicit_reset(client, manager):
    manager.tick()
    world, tick = manager.world, manager.world.tick
    response = client.post("/config", json={"n_agents": 2})
    assert response.status_code == 409
    assert manager.world is world and manager.world.tick == tick
    reset = client.post("/reset", json={"n_agents": 2})
    assert reset.status_code == 200
    assert manager.world.tick == 0 and len(manager.agents) == 2
```

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_config_safety.py -q
```

Expected: continuity test fails because `/config` currently calls `reset`; invalid payloads are accepted; structural patch returns 200.

- [x] **Step 3: Add strict model validation**

Set `ConfigDict(extra="forbid")` on `SimConfig`, `ConfigPatch`, and bounded request models. Add missing practical bounds to world sizes, populations, histories, ticks, and rates. Validate a merged candidate with:

```python
candidate = SimConfig.model_validate({
    **self.config.model_dump(),
    **patch.model_dump(exclude_none=True),
})
```

Never use `model_copy(update=...)` as the final validation boundary.

- [x] **Step 4: Implement a lock-guarded hot patch**

Add `SocietyManager.apply_config`. It must compare the validated candidate to the live config, reject reconstruction-only fields (`grid_size`, `n_objects`, `random_seed`, `n_agents`, plus constructor-sized buffers not explicitly migrated), then mutate the existing shared config instance under `_lock`. `initial_energy` is a hot reference/plafond update: existing agent energy remains unchanged.

```python
for field in changed:
    setattr(self.config, field, getattr(candidate, field))
```

This preserves every shared reference. Implement explicit migrations for `vector_memory_enabled`, `tasks_enabled`, `persist_memory`, `language_drive_enabled`, and `individuation_enabled`, or classify them as reset-required until their migration has a test.

- [x] **Step 5: Route `/config` through the hot path**

Return `{"mode": "hot", "changed_fields": [...], "config": ..., "state": ...}`. Convert a reconstruction-required exception to HTTP 409. Keep `/reset` and `/society/config` explicitly destructive and label their responses `mode="reset"` where their response shape permits it.

- [x] **Step 6: Run GREEN and nearby regressions**

```powershell
python -m pytest tests/test_config_safety.py tests/test_api.py tests/test_asymptote_api.py tests/test_phase7_api.py -q
```

Expected: all pass; update old tests that encoded reset-on-config only where the public behavior intentionally changed.

## Task 10: Make scientific probes and multi-agent persistence hermetic

**Files:**
- Create: `tests/test_hermetic_probes.py`
- Modify: `core/scenario.py`
- Modify: `core/test_battery.py`
- Modify: `core/agent.py`
- Modify: `storage/persistence.py`
- Modify: `storage/trace_logger.py`
- Test: `tests/test_hermetic_probes.py`

- [x] **Step 1: Write failing no-I/O tests**

Monkeypatch `MemoryStore.load_records`, `MemoryStore.save_records`, and `TraceLogger.log` to raise. Run a short `ScenarioRunner` scenario and the isolated battery helper; both must complete without invoking any patched method. Add a two-agent test asserting their memory and trace paths differ.

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_hermetic_probes.py -q
```

Expected: scenario/battery call global persistence during construction or ticks; multi-agent paths collide.

- [x] **Step 3: Construct probes in hermetic mode from the start**

Before creating any manager/agent, validate a config with:

```python
isolated = SimConfig.model_validate({
    **base.model_dump(),
    "persist_memory": False,
    "trace_logging": False,
})
```

Construct `SocietyManager(isolated)` directly; delete private `_records`/`_vectors` surgery. Do the same in `_isolated_agent`.

- [x] **Step 4: Separate multi-agent stores**

Preserve legacy `memory.json`/`traces.jsonl` for a one-agent run. For `config.n_agents > 1`, derive stable filenames `memory-agent-{agent_id}.json` and `traces-agent-{agent_id}.jsonl`. Routes reading agent 0 then naturally expose agent 0 only.

- [x] **Step 5: Run GREEN and science regressions**

```powershell
python -m pytest tests/test_hermetic_probes.py tests/test_scenario.py tests/test_si_integration.py tests/test_battery_mirror.py tests/test_battery_false_memory.py tests/test_battery_calibration.py tests/test_society.py -q
```

Expected: all pass and no probe touches the live store.

## Task 11: Align public contracts and close Phase-7 backend divergences

**Files:**
- Create: `tests/test_public_contracts.py`
- Modify: `schemas/models.py`
- Modify: `core/agent.py`
- Modify: `core/vector_memory.py`
- Modify: `core/mind_wandering.py`
- Modify: `storage/trace_export.py`
- Modify: `app/api/routes.py`
- Modify: `tests/test_checkpoint.py`

- [x] **Step 1: Write failing contract tests**

Cover all of these independently:

```python
assert client.get("/export/traces", params={"format": "csv"}).headers["content-type"].startswith("text/csv")
assert client.post("/agent/perturb", json={"type": "shock", "magnitude": 1}).json()["effect"]["applied"] is not False
assert client.post("/agent/perturb", json={"type": "soothe", "magnitude": 1}).json()["effect"]["applied"] is not False
analysis = client.get("/export/analysis").json()
assert {"max_phi_ar", "max_phi_causal"} <= analysis
```

Add unit tests showing that vector-memory embeddings are stable across process construction, semantically related text ranks above unrelated text, and mind-wandering uses the semantic index path when enabled. Add a checkpoint flags-on continuation test comparing the next trace after save/load with the uninterrupted next trace.

- [x] **Step 2: Run RED and record each expected failure**

```powershell
python -m pytest tests/test_public_contracts.py tests/test_vector_memory.py tests/test_mind_wandering.py tests/test_checkpoint.py -q
```

- [x] **Step 3: Implement compatibility aliases and aggregates**

Accept both `format` (documented canonical name) and legacy `fmt`. Normalize perturbation aliases `shock -> choc` and `soothe -> apaisement` while preserving old French inputs. Add Φ_AR/causal maxima and means to analysis.

- [x] **Step 4: Complete semantic projection and wandering composition**

Keep CRC32 as the stable n-gram hash, then apply one module-level deterministic orthogonal/sign projection generated from a fixed NumPy seed to the 48-dimensional text block before normalization. Inject or pass `VectorMemoryIndex` into mind-wandering when semantic memory is enabled; retain the feature-vector fallback otherwise.

- [x] **Step 5: Run GREEN**

```powershell
python -m pytest tests/test_public_contracts.py tests/test_vector_memory.py tests/test_mind_wandering.py tests/test_trace_export.py tests/test_checkpoint.py tests/test_phase7_api.py -q
```

## Task 12: Restore the five-interaction console and clickable world promised by README

**Files:**
- Create: `tests/test_interaction_ui.py`
- Modify: `ui/index.html`
- Modify: `ui/app.js`
- Modify: `ui/styles.css`
- Test: `tests/test_interaction_ui.py`

- [x] **Step 1: Write a failing static UI contract**

Parse HTML attributes and uncommented JS to require controls for `agent/ask`, `world/stimulus`, `agent/inject`, `agent/attend`, and `agent/perturb`; require an interaction log with `aria-live`; and require a real click/keyboard handler on `world-canvas` that posts a stimulus with mapped grid coordinates.

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/test_interaction_ui.py -q
```

Expected: FAIL because no endpoint is referenced by the current UI.

- [x] **Step 3: Build an “Experimental interventions” deck**

Use compact tabs or a segmented control for the five modalities. Each action must show its exact endpoint, send a typed payload, append request/result/error to a timestamp-free deterministic log, and trigger one `refreshAll()` after success. Add visible labels; placeholders alone are insufficient.

- [x] **Step 4: Make the world canvas operable**

Give it `tabindex="0"`; click maps CSS-scaled client coordinates to integer grid coordinates and posts a selected `food|hazard|tool|curio` stimulus. Arrow keys move a visible grid cursor; Enter posts at the selected cell. Provide an `aria-live` textual result.

- [x] **Step 5: Run GREEN**

```powershell
python -m pytest tests/test_interaction_ui.py tests/test_interaction.py -q
```

## Task 13: Whole-project verification and handoff

**Files:**
- Verify: all changed files
- Modify if needed: `README.md` badge only

- [x] **Step 1: Run focused Phase-7 and integrity tests**

```powershell
python -m pytest tests/test_phi_causal.py tests/test_hierarchy.py tests/test_planning.py tests/test_vector_memory.py tests/test_td_learning.py tests/test_mind_wandering.py tests/test_world_dynamics.py tests/test_trace_export.py tests/test_phase7_regression.py tests/test_phase7_api.py tests/test_phase7_ui.py tests/test_config_safety.py tests/test_hermetic_probes.py tests/test_public_contracts.py tests/test_interaction_ui.py -q
```

Expected: all Phase-7 tests pass.

- [x] **Step 2: Run the full test suite**

```powershell
python -m pytest -q
```

Expected: zero failures and zero errors.

- [x] **Step 3: Check source hygiene**

```powershell
git diff --check
python -m compileall -q app core schemas storage
```

Expected: both commands exit 0 with no output.

- [x] **Step 4: Validate README truthfulness**

```powershell
python -m pytest --collect-only -q
rg -n "382 passing|Future extensions|Phase 7|33 mechanisms" README.md
```

Replace the stale badge number with the exact collected/passing count, rerun `python -m pytest -q`, and do not claim a count that was not freshly observed.

- [x] **Step 5: Review the final diff**

```powershell
git status --short
git diff --stat
git diff --check
```

Confirm no `.env`, checkpoint, trace, cache, or unrelated user file is staged or modified.

## Self-review

- **Spec coverage:** Tasks 1–4 cover every backend item in sections 7.1–7.7 and 7.9; Task 6 covers all three section-7.8 visualizations plus live Phase-7 readouts; Task 7 covers the roster, endpoints, README, and closed roadmap; Tasks 9–12 close the audit’s state-integrity, hermeticity, public-contract, and promised-interaction gaps; Task 13 performs whole-project verification.
- **Extra product impact:** Task 8 adds a one-click Horizon profile, auditable analysis export, accessible canvas summaries, and robust empty/reduced-motion states without inventing a new consciousness claim or new scientific mechanism.
- **Placeholder scan:** Clean. Every mutation names exact files and concrete markup/code/commands.
- **Type consistency:** UI readers use existing `CycleTrace` names (`phi_causal`, `hierarchy`, `planning`, `semantic_memory`, `wandering`, `task`) and existing endpoint shapes. Configuration names match `SimConfig`/`ConfigPatch` exactly.

## Execution mode

The user explicitly requested autonomous completion and the most impressive aligned result. Use **Subagent-Driven execution** for independent UI contract, UI/CSS implementation, and README review tasks, with the primary agent integrating, testing, visually inspecting, and running the complete suite.
