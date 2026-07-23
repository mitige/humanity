# Phase 8 — Situated Gendered Self Implementation Plan

> **Execution note:** implement task-by-task in this checkout. Preserve unrelated untracked files
> and keep every Phase-8 mechanism behind an explicit profile plus an OFF-by-default backend flag.

**Goal:** Deliver the approved life-course, factorized model of gender experience, including
identity self-understanding, dysphoria, euphoria, accentuated expression, multidimensional
transition, external/internalized transphobia, resilience, society dynamics and a complete
observatory.

**Architecture:** New deterministic core modules own all Phase-8 formulas and scenario state.
`CognitiveAgent` and `SocietyManager` only coordinate them. Private profiles are separated from
agent-readable state and public projections. All social feedback is one-tick deferred. Ordinary
traces never expose private profiles.

**Tech stack:** Python 3.11, Pydantic v2, FastAPI, NumPy, pytest, vanilla HTML/CSS/JavaScript.

**Design source:** `docs/superpowers/specs/2026-07-23-humanity-situated-gender-self-design.md`

---

## File map

- `schemas/models.py` — Phase-8 enums, requests, profile/state/event/intent contracts, config.
- `core/gender_scenarios.py` — built-in manifests, custom validation and deterministic factories.
- `core/gender_lifecycle.py` — configurable life-stage progression and body-change events.
- `core/gender_experience.py` — congruence, affect, stress, resilience, understanding, expression,
  transition and influence.
- `core/gender_society.py` — public projections, observer recognition and deferred social events.
- `core/agent.py` — gated orchestration, workspace coalition, trace and accessors.
- `core/self_model.py`, `core/motivation.py` — bounded Phase-8 influence/pressures.
- `core/society.py` — scenario install and order-independent social update.
- `core/test_battery.py` — matched gender-experience counterfactual.
- `app/api/routes.py` — scenario, agent, society, event, intent, export and battery endpoints.
- `storage/trace_export.py` — Phase-8-safe projection/export support if needed.
- `ui/index.html` — Gender experience panel, scenario builder and settings.
- `ui/app.js` — rendering, scenario/event/intent controls and background refresh.
- `ui/styles.css` — responsive, non-stereotyped accessible presentation.
- `README.md` — Phase-8 mechanism, API, config, limitations, sources and measured counters.
- `tests/test_gender_models.py` — schema and invariant contracts.
- `tests/test_gender_experience.py` — factorized update behavior and required trajectories.
- `tests/test_gender_society.py` — privacy, recognition and order independence.
- `tests/test_gender_api.py` — routes, reset, export and atomic failure behavior.
- `tests/test_gender_regression.py` — feature-off compatibility and determinism.
- `tests/test_gender_ui.py` — UI, a11y and README contracts.

## Task 1: Public contracts and backward-compatible configuration

**Files:**
- Modify: `schemas/models.py`
- Create: `tests/test_gender_models.py`

- [ ] Add open-label identity, gender axes, profile timeline and expression/body contracts.
- [ ] Add life-course, event, intent, transition, affect, stress, resilience and aggregate-state
      contracts.
- [ ] Add public projection, recognition, social context and full scenario request/response models.
- [ ] Add `gender_experience: GenderExperienceState | None = None` to `CycleTrace`.
- [ ] Add the six approved `SimConfig` fields and matching optional `ConfigPatch` fields.
- [ ] Enforce finite `[0,1]` values, positive durations, monotonic/non-overlapping segments,
      bounded strings and `extra="forbid"` request semantics.
- [ ] Verify a pristine `SimConfig` leaves Phase 8 off.

Focused command:

```powershell
python -m pytest tests/test_gender_models.py -q
```

## Task 2: Presets, lifecycle and factorized engine

**Files:**
- Create: `core/gender_scenarios.py`
- Create: `core/gender_lifecycle.py`
- Create: `core/gender_experience.py`
- Create: `tests/test_gender_experience.py`

- [ ] Implement every approved preset as a complete inspectable manifest.
- [ ] Derive each agent's gender RNG from the simulation seed and agent ID.
- [ ] Implement life-stage advancement and neutral lifecycle events.
- [ ] Implement alignment/congruence and empty-domain neutrality.
- [ ] Implement independent dysphoria, euphoria and slow fulfillment.
- [ ] Implement external/chronic stress, internalization and resilience recovery.
- [ ] Implement label-fit evidence without dysphoria/expression/observer inference.
- [ ] Implement private/trusted/public expression and personal-baseline accentuation drivers.
- [ ] Implement independent transition intent/status/progress, pause/revision/reversal/resumption.
- [ ] Implement event ledger, transactional queue application and profile checksum invariant.
- [ ] Implement bounded `GenderInfluence`.
- [ ] Cover euphoria-led, low-dysphoria, nonbinary, fluid, agender, compensation and late-realization
      trajectories.

Focused command:

```powershell
python -m pytest tests/test_gender_models.py tests/test_gender_experience.py -q
```

## Task 3: Cognitive-cycle integration

**Files:**
- Modify: `core/agent.py`
- Modify: `core/self_model.py`
- Modify: `core/motivation.py`
- Modify: `core/constants.py` only if dynamic workspace-source support needs a shared label
- Create: `tests/test_gender_regression.py`

- [ ] Construct the Phase-8 modules for every agent but keep them inert without a profile/flag.
- [ ] Advance lifecycle and consume events once per tick.
- [ ] Add a dynamic `gender_experience` coalition only when enabled and salient.
- [ ] Feed grounded coalition content into the existing workspace without changing feature-off
      source ordering.
- [ ] Apply mood/confidence/coherence caps after the normal self-model update.
- [ ] Add explicit seek-safety/explore/affirm/transition goal pressures without rewriting ordinary
      grid-world actions.
- [ ] Store the latest Phase-8 state on `CycleTrace` and `/agent/consciousness`.
- [ ] Expose safe accessors for state, debug profile, queued event and user-probe intent.
- [ ] Prove identical feature-off action/world/metrics/self-model trajectories.
- [ ] Prove same-seed Phase-8 traces are deterministic.

Focused command:

```powershell
python -m pytest tests/test_gender_regression.py tests/test_agent_cycle.py tests/test_self_model.py tests/test_motivation.py -q
```

## Task 4: Multi-agent gender society and privacy

**Files:**
- Create: `core/gender_society.py`
- Modify: `core/society.py`
- Create: `tests/test_gender_society.py`

- [ ] Build `PublicGenderProjection` strictly from disclosed/public fields.
- [ ] Keep observer-local recognition independent from the target's private profile.
- [ ] Generate affirmation, missing-knowledge misgendering and configured hostility from public
      state plus explicit observer/context variables only.
- [ ] Disable all hostile output under a supportive-only context.
- [ ] Compute social events after all agents cycle and deliver them one tick later.
- [ ] Install a validated multi-agent scenario through a full transactional reset.
- [ ] Ensure unspecified agents have no profile.
- [ ] Prove reversed agent iteration order yields identical Phase-8 social results.
- [ ] Prove private labels, body goals, internalization and undisclosed intents never leak.

Focused command:

```powershell
python -m pytest tests/test_gender_society.py tests/test_society.py tests/test_relational_self.py -q
```

## Task 5: API, counterfactual battery, checkpoints and exports

**Files:**
- Modify: `app/api/routes.py`
- Modify: `core/test_battery.py`
- Modify: `storage/trace_export.py` if projection support is required
- Create: `tests/test_gender_api.py`

- [ ] Add preset listing and full-reset scenario application.
- [ ] Add agent 0 and arbitrary-society-agent state/debug endpoints.
- [ ] Add next-tick event and `user_probe` intent queues.
- [ ] Add society summary built from public projections.
- [ ] Add explicit public/private scenario-manifest export.
- [ ] Add matched supportive/hostile, expression/coercion, euphoria/dysphoria and
      isolation/community battery arms.
- [ ] Return grounded `409`, `422` and accepted-false failures without partial mutation.
- [ ] Verify checkpoint bit-identical continuation with Phase 8 active.
- [ ] Verify ordinary trace/export excludes `GenderProfile`.

Focused command:

```powershell
python -m pytest tests/test_gender_api.py tests/test_checkpoint.py tests/test_trace_export.py -q
```

## Task 6: Complete observable product surface

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/app.js`
- Modify: `ui/styles.css`
- Create: `tests/test_gender_ui.py`

- [ ] Add a full-width Gender experience panel to Mind.
- [ ] Show distinct Experiment input, Self-understanding and Public presentation layers.
- [ ] Add life timeline plus a semantic ordered-list equivalent.
- [ ] Show congruence, dysphoria, euphoria, fulfillment, stress, internalization, resilience,
      expression drivers and transition dimensions with provenance.
- [ ] Add scenario preset/custom controls and explicit reset confirmation.
- [ ] Add neutral event and intent probes; hostile events use enum/template text only.
- [ ] Add unchecked Phase-8 settings and ensure localStorage cannot silently enable it.
- [ ] Refresh background runs from `/agent/consciousness`/`/agent/gender`.
- [ ] Use no pink/blue binary palette, stereotypes or color-only meaning.
- [ ] Validate keyboard semantics and compact 360/390 px layouts.
- [ ] Bump static asset query versions together.

Focused commands:

```powershell
python -m pytest tests/test_gender_ui.py tests/test_interaction_ui.py tests/test_phase7_ui.py -q
node scripts/check_ui_contract.mjs
```

## Task 7: Documentation and end-to-end release gate

**Files:**
- Modify: `README.md`
- Verify: all Phase-8 and historical test files

- [ ] Add the approved README claim, architecture, glossary, API/config, scenario walkthrough,
      counterfactual and source links.
- [ ] Document accentuated expression without treating it as a stage or diagnosis.
- [ ] Document explicit clinical, predictive, cultural and phenomenological limits.
- [ ] Run the complete pytest suite and update measured counters only afterward.
- [ ] Start the real FastAPI application and exercise scenario selection, events, ticks,
      background refresh, checkpoint round-trip, battery and export.
- [ ] Inspect browser console and network failures.
- [ ] Capture/inspect desktop and 390 px mobile Gender experience views.
- [ ] Re-run `git diff --check`, inspect the final dirty-file boundary and preserve unrelated
      untracked artifacts.

Release commands:

```powershell
python -m pytest -q
node scripts/check_ui_contract.mjs
node scripts/ui_hook_check.mjs
```

## Completion boundary

Do not call Phase 8 complete until all seven tasks pass, the real observatory path is inspected, and
the README contains measured—not projected—test/runtime evidence.
