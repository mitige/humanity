# README Roadmap Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the README's obsolete future-work framing with a verified completion checklist that explicitly names every Phase 7 deliverable and the final quality guarantees.

**Architecture:** Keep this as a documentation-only change guarded by the existing static README contract test. Replace one terminal README section, preserve the scientific boundary paragraph, and avoid duplicating the detailed Phase 7 chapter.

**Tech Stack:** Markdown, Python 3.11, pytest, Git, GitHub pull request #1.

---

## File map

- Modify: `tests/test_phase7_ui.py:354-370` — lock the final roadmap heading, grouping, eight Horizon mechanisms, quality evidence, and removal of the obsolete heading.
- Modify: `README.md:1440-1477` — replace `Future extensions` with the grouped completed-roadmap checklist.
- Verify: `docs/superpowers/specs/2026-07-10-readme-roadmap-completion-design.md` — source of truth for scope and wording constraints.

### Task 1: Lock the completed-roadmap contract

**Files:**
- Modify: `tests/test_phase7_ui.py:354-370`
- Test: `tests/test_phase7_ui.py`

- [ ] **Step 1: Replace the README scorecard assertions with the completed-roadmap contract**

Replace `test_phase7_is_documented_and_future_extensions_are_closed` with:

```python
def test_phase7_is_documented_and_final_roadmap_is_completed():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    violations = []

    if re.search(r"^## Phase 7\b", readme, re.MULTILINE) is None:
        violations.append("missing level-2 README heading: Phase 7")
    if re.search(r"^## Roadmap completed$", readme, re.MULTILINE) is None:
        violations.append("missing final completed-roadmap heading")
    if re.search(r"^## Future extensions$", readme, re.MULTILINE):
        violations.append("obsolete future-extensions heading remains")

    for marker in (
        "### Foundations delivered — Phases 1–6",
        "### Phase 7 — The Horizon delivered",
        "### Delivery quality completed",
        "Coarse causal Φ",
        "Predictive hierarchy and VFE",
        "Multi-step EFE planning",
        "Semantic vector memory",
        "Contextual TD(λ)",
        "Mind-wandering / default mode",
        "Living world dynamics",
        "Structured tasks",
        "Horizon Observatoire and interventions",
        "Atomic persistence and checkpoints",
        "627/627 tests",
    ):
        if marker not in readme:
            violations.append(f"missing completed-roadmap evidence: {marker}")

    assert not violations, _format_violations(violations)
```

- [ ] **Step 2: Run the contract to verify it fails for the current README**

Run:

```powershell
python -m pytest tests/test_phase7_ui.py::test_phase7_is_documented_and_final_roadmap_is_completed -q
```

Expected: FAIL listing the missing `Roadmap completed` heading and grouped Phase 7 markers.

### Task 2: Replace the final README roadmap

**Files:**
- Modify: `README.md:1440-1477`
- Test: `tests/test_phase7_ui.py`

- [ ] **Step 1: Replace the old terminal section with the approved grouped checklist**

Use this exact structure and factual scope:

```markdown
## Roadmap completed

Every engineering objective previously listed as future work is now delivered. The detailed
[Phase 7 chapter](#phase-7--the-horizon-every-remaining-extension-delivered) remains the technical
reference; this final checklist is the completion ledger.

### Foundations delivered — Phases 1–6

- ✅ **Multi-agent society (Phase 1).** Shared world, communication, theory of mind, social mirror,
  isolated per-agent persistence, and deterministic collective ticks.
- ✅ **Deep mechanisms (Phase 2).** Circadian state, sleep/consolidation, dreams, imagination,
  curiosity/boredom, agency, relational self, and self-opacity.
- ✅ **Learning and personality (Phase 3).** Learned values, concepts, meta-learning, divergent
  personality, and individuation from accumulated history.
- ✅ **Scientific instrument (Phase 4).** Reproducible scenarios, metric history, CSV/JSON export,
  fast training, and deterministic functional probes.
- ✅ **The asymptote (Phase 5).** Recurrence, reality monitoring, interoceptive inference,
  temporality, inner speech, Φ_AR, subliminal facilitation, and psychophysics probes.
- ✅ **The invention of language (Phase 6).** Deterministic naming games, emergent conventions,
  language metrics, society dictionary, and the language-genesis probe.
- ✅ **Optional LLM peripheral.** Grounded narration, conversation, biography, skeptical audit,
  cross-examination, and inner-voice re-entry without changing the deterministic cognitive core.

### Phase 7 — The Horizon delivered

- ✅ **Coarse causal Φ.** Empirical binary TPM, exact bounded MIP search, trace state, metric, and
  real-trace analysis.
- ✅ **Predictive hierarchy and VFE.** Slow regime inference, top-down modulation, and explicit
  variational free energy.
- ✅ **Multi-step EFE planning.** Deterministic bounded policy-tree search with inspectable best
  sequence and planning depth.
- ✅ **Semantic vector memory.** Stable 64-dimensional embeddings, cosine retrieval, free-text
  search, and deterministic autobiographical graph.
- ✅ **Contextual TD(λ).** Context/action values and eligibility traces for delayed credit
  assignment.
- ✅ **Mind-wandering / default mode.** Demand-sensitive associative memory walks that can re-enter
  workspace competition.
- ✅ **Living world dynamics.** Seasons, renewable food, oscillating hazards, deterministic drift,
  and auditable world events.
- ✅ **Structured tasks.** Deterministic forage, reach, and patrol rotation with progress metrics.

### Delivery quality completed

- ✅ **Horizon Observatoire and interventions.** Live Horizon readouts, ignition/source timelines,
  semantic memory topology, all five causal interventions, and a keyboard-operable world grid.
- ✅ **Scientific trace surface.** Filtered JSONL/JSON/CSV export plus streaming ignition, error,
  sleep, wandering, action, and Φ-family analysis.
- ✅ **Atomic persistence and checkpoints.** Multi-file rollback, managed memory/trace branch
  restoration, corruption preflight, legacy marking, and recoverable double-fault handling.
- ✅ **Responsive and strict public contracts.** Heavy jobs run outside the event loop behind a busy
  gate; cancellation, stale UI responses, bounded schemas, and concurrent live reads are covered.
- ✅ **Accessible and reproducible delivery.** Keyboard/text equivalents, locked dependencies,
  hermetic runtime storage, deterministic flags-off behavior, and **627/627 tests passing**.

**The engineering roadmap is complete at the strongest deterministic scale this project can defend
honestly.** This does not establish phenomenal consciousness. Full IIT 3.0/4.0 cause-effect
structure on a true micro-substrate remains computationally out of scope, and subjective experience
remains empirically undecidable here.
```

- [ ] **Step 2: Run the focused README/UI contract**

Run:

```powershell
python -m pytest tests/test_phase7_ui.py -q
```

Expected: all tests in `tests/test_phase7_ui.py` PASS.

- [ ] **Step 3: Check the documentation diff**

Run:

```powershell
git diff --check -- README.md tests/test_phase7_ui.py
rg -n "^## Roadmap completed|^## Future extensions|627/627 tests" README.md
```

Expected: `git diff --check` exits 0; `rg` finds `Roadmap completed` and `627/627 tests`, but no
`Future extensions` heading.

### Task 3: Validate and publish the README update

**Files:**
- Verify: `README.md`
- Verify: `tests/test_phase7_ui.py`
- Verify: `docs/superpowers/specs/2026-07-10-readme-roadmap-completion-design.md`
- Verify: `docs/superpowers/plans/2026-07-10-readme-roadmap-completion.md`

- [ ] **Step 1: Run the full regression suite**

Run:

```powershell
python -m pytest -q
```

Expected: 627 tests pass with no failure or error.

- [ ] **Step 2: Stage only the roadmap documentation and its contract**

Run:

```powershell
git add -- README.md tests/test_phase7_ui.py docs/superpowers/plans/2026-07-10-readme-roadmap-completion.md
git diff --cached --check
git status --short
```

Expected: the README, contract test, and this plan are staged; local `.claude/` and `output/`
artifacts remain untracked and unstaged.

- [ ] **Step 3: Commit and push into the existing pull request**

Run:

```powershell
git commit -m "docs: mark the roadmap complete"
git push
gh pr view 1 --repo mitige/humanity --json url,headRefName,state,isDraft
```

Expected: the commit is on `agent/phase7-horizon`; pull request #1 remains open as a draft and
contains the updated README.
