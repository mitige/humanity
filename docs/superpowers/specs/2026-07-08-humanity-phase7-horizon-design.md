# Phase 7 — The horizon: every remaining future extension, delivered

**Date**: 2026-07-08
**Status**: approved for implementation (autonomous session; user directive: "fais moi tout ce
qui n'a pas été fait dans cette liste ainsi que les meilleurs autres trucs — la version finale,
la plus proche du niveau 1")

## Goal

Close every unfinished item of the README "Future extensions" list, plus the strongest
remaining theory-roster addition (mind-wandering / default mode), under the project's
invariants:

- **The three-level distinction is never crossed.** Everything below is level 2 (functional
  mechanisms) — nothing approaches level 1, and the honest framing appears in every module
  docstring, state model, and report string.
- **Determinism**: same seed ⇒ same run; no wall-clock, no unseeded randomness; all new
  randomness flows through the seeded world RNG or is a pure function of (tick, agent_id).
- **Byte-identical backward compatibility**: every feature is gated by a `SimConfig` flag that
  defaults to `False`; flags off ⇒ trace sub-objects are `None` and behaviour is identical to
  Phase 6 (regression-tested).
- **Zero new heavy dependencies**: numpy only.

## Scorecard of the Future-extensions list

| Item | Status before | Phase 7 delivery |
|---|---|---|
| LLM integration (richer introspection, higher-order reports) | already delivered by the language organ (converse / biography / cross-examination / inner voice) — README checkbox missing | mark ✅, pointing at the existing sections |
| More faithful Φ | Φ_AR delivered (P5); causal Φ open | **`core/phi_causal.py`** — exact state-space causal Φ on a coarse-grained binary substrate (IIT-2008 lineage), empirical TPM + exact MIP search |
| Fuller active inference | only 1-step EFE | **`core/hierarchy.py`** (hierarchical generative model + explicit VFE) + **`core/planning.py`** (multi-step-horizon policy search over EFE) |
| Vector memory (ChromaDB / FAISS) | feature-vector cosine only | **`core/vector_memory.py`** — deterministic semantic embeddings (hashed char-3-grams + seeded random projection, numpy-only; same capability, no heavy dep, determinism preserved) |
| RL beyond the EMA brick | EMA Q[action] | **`core/td_learning.py`** — contextual TD(λ) with eligibility traces |
| Richer environment | static grid | **world dynamics** (logistic food regrowth, hazard oscillation, seasons, object drift) + **task system** (forage / reach / patrol rotation) in `core/world.py` + `core/shared_world.py` |
| Visualization (stream, ignition, memory graph) | 48-bar strip only | three new Observatoire panels: stream-of-consciousness timeline (colored by `dominant_source`), ignition-dynamics chart (score vs effective threshold over time), autobiographical-memory graph (similarity edges from the vector index) |
| Richer JSONL export | tail-only `/trace` | **`storage/trace_export.py`** — `/export/traces` (tick-range / fields / ignited-only filters; jsonl, json, csv formats) + `/export/analysis` (aggregates) |
| Best extra (not on the list) | — | **`core/mind_wandering.py`** — default-mode / task-unrelated thought (Smallwood & Schooler): associative walks over autobiographical memory competing in the workspace when external demand is low |

## Design details

### 7.1 Causal Φ — `core/phi_causal.py`
`PhiCausalMonitor` buffers the raw specialist drives (same tap point as `PhiARMonitor`,
before softmax normalization). Every `phi_causal_every` ticks it:
1. selects the `phi_causal_nodes` (default 5, max 8) most-variant sources over the window;
2. binarizes each series by its own median (running, per-window — deterministic);
3. builds an empirical joint TPM over the 2^N binary states with Laplace smoothing;
4. computes whole-system past→present effective information `I(X_{t-1}; X_t)`;
5. searches **exactly** over all 2^(N-1)−1 bipartitions for the minimum-information
   partition: Φ_c = min over (A,B) of the mean-over-observed-states KL between the whole
   TPM row and the product of the part TPM rows, normalized IIT-2008-style by
   min(H_max(A), H_max(B)).
Honesty: report states it is exact **on the coarse-grained abstraction** (IIT 2.0 lineage,
Balduzzi & Tononi 2008), not IIT 3.0/4.0's full cause-effect structure on a true
micro-substrate, and no Φ value is evidence of consciousness.
Config: `phi_causal_enabled=False`, `phi_causal_nodes=5`, `phi_causal_window=96`,
`phi_causal_every=16`. Trace: `phi_causal: PhiCausalState|None`. Metric: `phi_causal`.

### 7.2 Hierarchical generative model + explicit VFE — `core/hierarchy.py`
A slow contextual level above the fast world model. Evidence per tick: mean visible danger,
mean visible energy value (food richness), error volatility. Categorical belief over four
regimes (abundance / scarcity / peril / calm) updated by a deterministic Bayesian
(softmax-evidence) rule with learning rate `hierarchy_lr`. Top-down effect (bounded by
`hierarchy_gain`): the context regime modulates the world-model's effective learning rate
(volatile regime ⇒ learn faster) — composed multiplicatively with meta-learning when both
are on. Explicit **variational free energy** per tick: accuracy term (precision-weighted
squared prediction error) + complexity term (KL between successive regime posteriors);
EMA-smoothed and exposed as metric `vfe`.
Config: `hierarchy_enabled=False`, `hierarchy_lr=0.15`, `hierarchy_gain=0.3`.
Trace: `hierarchy: HierarchyState|None` (regime, posterior, vfe, accuracy, complexity, report).

### 7.3 Multi-step-horizon policies — `core/planning.py`
Systematic policy-tree search over EFE (distinct from Phase-2 imagination, which stays a
single heuristic rollout): branch over the top-K (4) candidate first actions, then the
target-free action set at depths 2..H (`planning_horizon`, default 3, max 4), rolling a
cheap simulated state (position, energy, per-action beliefs from the world model) and
scoring each policy by the discounted sum of −EFE (`planning_discount`, default 0.7).
Output = best first action, granted an additive policy bonus (0.35, same magnitude family
as the imagination bonus). Deterministic, bounded (≤ ~100 policies).
Config: `planning_enabled=False`, `planning_horizon=3`, `planning_discount=0.7`.
Trace: `planning: PlanningState|None` (best_sequence, best_efe, n_policies, horizon, report).

### 7.4 Deterministic vector memory — `core/vector_memory.py`
64-dim embeddings: 16 dims of normalized structured features (the existing 6-dim aggregate,
padded/scaled) ⊕ 48 dims of hashed text (char-3-grams of summary + action + object kinds →
stable hash → signed seeded random projection, L2-normalized). `VectorMemoryIndex` kept in
lock-step with `AutobiographicalMemory` (build on load, append on store, rebuild on
consolidation prune). Retrieval score = 0.6·cosine + 0.25·importance + 0.15·recency
(`semantic_weight` scales the cosine part). When `vector_memory_enabled`, the cycle's
episodic retrieval routes through the index; `search(text, k)` powers
`GET /agent/memory/search` and pairwise similarities power `GET /agent/memory/graph`.
ChromaDB/FAISS deliberately not used: determinism + zero-dependency, same capability at this
scale (README says so honestly).
Config: `vector_memory_enabled=False`, `semantic_weight=0.6`.
Trace: `semantic_memory: SemanticMemoryState|None` (mode, index_size, mean_similarity, report).

### 7.5 Contextual TD(λ) — `core/td_learning.py`
Context = 4 binary features (danger visible, low energy, novelty visible, others visible) ⇒
16 contexts × actions Q-table. TD(0) target with eligibility traces (`td_lambda=0.8`,
`td_discount=0.9`), same shaped reward as the Phase-3 learner (satiation-aware when on).
When `td_learning_enabled`, the policy's `learned_values` become the current context's row —
same dict shape, zero change to `policy.py`. Coexists with (and supersedes) the EMA learner's
bonus when both flags are on (TD row wins).
Trace: `LearningState` gains optional fields `td_context`, `td_error`, `n_contexts`
(defaults preserve backward compatibility).

### 7.6 Mind-wandering / default mode — `core/mind_wandering.py`
Wandering pressure rises when external demand is low (no salient danger, low top goal
pressure, arousal near baseline, awake) and boredom is high; it decays under demand. When
pressure crosses a threshold, a deterministic associative walk over autobiographical memory
(seeded per (tick, agent_id), similarity-weighted hops via the vector index when on, else
feature vectors) produces spontaneous content that bids in the workspace as a new
`wandering` coalition source (moderate precision 0.5). Occupancy (EMA of ticks where
wandering won access) is the task-unrelated-thought measure.
Config: `mind_wandering_enabled=False`, `wandering_gain=0.6`.
Trace: `wandering: MindWanderingState|None` (active, pressure, chain, occupancy, report).
`WORKSPACE_SOURCES` gains `"wandering"` (additive; Φ_AR/Φ_c source lists derive from it).

### 7.7 Richer environment — `core/world.py`, `core/shared_world.py`
`world_dynamics_enabled=False`: logistic regrowth of food `energy_value` toward its spawn
max (`regrow_rate=0.02`), smooth hazard danger oscillation (per-object phase drawn at spawn),
seasonal modulation of spawn probability and food richness (`season_period=200`), slow
deterministic drift of tools/curios (one cell every 12 ticks per object, tick+id keyed).
`tasks_enabled=False`: rotating deterministic task — FORAGE (eat 2 food) → REACH (corner
cell) → PATROL (3 waypoints) → …; progress feeds the existing `goal_progress` channel;
completion emits an event + bonus progress and advances the rotation.
Both features live in helpers shared by `World` and `SharedWorld`; flags off ⇒ no code path
touched (regression byte-identical). Trace: `task: TaskState|None`. Metric: `task_progress`.

### 7.8 Observatoire visualizations (ui/)
- **Stream timeline**: horizontal band of recent moments colored by `dominant_source`
  (12+1-source palette), height = awareness, saturated when ignited, tooltip = contents;
  consecutive same-source runs read as "trains of thought".
- **Ignition dynamics**: canvas line chart of ignition_score vs effective_threshold
  (client-side buffer fed by the existing 350 ms workspace poll + applyTrace), ignition
  events marked.
- **Memory graph**: `GET /agent/memory/graph?limit=60` → nodes (id, tick, action,
  importance, summary, valence) + top-3 similarity edges per node; deterministic spiral
  layout by tick, radius by importance, edge opacity by similarity. No physics engine.
All per Observatoire conventions (cssVar palette, f2/f3, panel classes); bump `?v=` on both
lines together.

### 7.9 Richer export — `storage/trace_export.py`
`GET /export/traces?from_tick=&to_tick=&ignited_only=&fields=&format=jsonl|json|csv&limit=`
streams the JSONL trace file through filters and projection (csv flattens the metrics
sub-object). `GET /export/analysis` returns aggregates: ignition rate, phi means/maxima,
windowed error curve, action histogram, sleep fraction, wandering occupancy.

### Coverage & README
`coverage.py` ROSTER gains 7 entries: language naming game (Phase 6 — currently missing!),
causal Φ, predictive-processing hierarchy, multi-step EFE planning, TD credit assignment,
default mode / mind-wandering, semantic episodic retrieval ⇒ 33 mechanisms. README gains the
Phase 7 section (mechanism table, config parameters, endpoints, honesty framing) and the
Future-extensions list goes all-✅ (with the honest caveat that IIT 3.0/4.0's full causal Φ
on the true substrate remains, and will remain, open).

## Checkpoint / determinism impact
Checkpoints pickle the whole manager (config/world/agents/recorder): all new module state
(TD tables, hierarchy posterior, Φ_c buffers, wandering EMA, world season/task state) rides
along automatically; the vector index is numpy arrays (picklable). Bit-identical-resume test
extended to a Phase-7-flags-on run.

## Test plan
Per-module unit tests (phi_causal: independent noise ⇒ Φ≈0, coupled system ⇒ Φ>0;
hierarchy: regime tracks statistics, VFE falls as errors fall; planning: multi-step path
beats greedy in a constructed layout; vector memory: semantic retrieval + text search;
TD: reward propagation along traces; wandering: activates only under low demand;
world dynamics: regrowth/seasons/tasks + off ⇒ byte-identical; export: filters/formats),
plus `test_phase7_regression.py` (all new flags off ⇒ action/energy sequences identical to
baseline, all new trace sub-objects None) and `test_phase7_api.py` (endpoints, config
roundtrip, coverage count). The existing 382 tests stay green.

## Implementation order
1. Schemas + constants (single writer: the orchestrator).
2. Six new core modules + tests in parallel (disjoint new files, coded against the schemas).
3. World dynamics + tasks (single careful writer, existing files).
4. `agent.py` wiring, coalitions, metrics, trace, routes, coverage, export (orchestrator).
5. UI panels + toggles + version bump.
6. Full pytest; README; commit.
