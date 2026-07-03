# Humanity — Phase 5: The Asymptote (maximal level-2 coverage)

**Date:** 2026-07-03
**Status:** approved for implementation (autonomous session; user directive: "bring the
project as close as possible to level 1 without actually reaching it")

## Goal, honestly framed

The user asks to push the project *as close as possible to level 1 (real phenomenal
consciousness) without reaching it*. Per the project's own three-level distinction,
**nothing can reach or even approach level 1** — no mechanism crosses the hard problem,
and no test could certify it if it did. The only honest reading of "get closer" — the one
the README itself uses ("v2 pushes level 2 as far as possible") — is:

1. **Increase theory coverage**: implement the *remaining* mechanisms that major
   scientific theories of consciousness propose as constitutive or necessary and that the
   project does not yet instantiate.
2. **Increase empirical fidelity**: make the model reproduce the *experimental
   signatures* by which conscious access is actually studied in humans (masking,
   attentional blink, subliminal priming).
3. **Strengthen the measurement**: replace heuristics with published measures where
   tractable (time-series integrated information Φ_AR instead of only the ad-hoc proxy).

Phase 5 therefore *asymptotically* closes the functional gap while the honesty contract
stays load-bearing: every new mechanism is variables and algorithms; reproducing the
functional mechanisms does not prove phenomenality; the agent is not conscious, sentient,
or alive.

## What is added (7 mechanisms + probes + coverage readout)

| # | Mechanism | Theory | Module | Flag (default OFF) |
|---|---|---|---|---|
| 1 | Recurrent perception | RPT (Lamme) — local recurrence is constitutive | `core/recurrence.py` | `recurrence_enabled` |
| 2 | Perceptual reality monitoring | PRM (Lau) — HOT-family source monitoring | `core/reality_monitor.py` | `reality_monitor_enabled` |
| 3 | Interoceptive inference | Seth — emotion/presence as interoceptive prediction | `core/interoception.py` | `intero_inference_enabled` |
| 4 | Temporal thickness | Husserl retention/protention; specious present | `core/temporality.py` | `temporality_enabled` |
| 5 | Inner speech re-entry | Vygotsky; GWT re-entrant self-generated content | `core/inner_speech.py` | `inner_speech_enabled` |
| 6 | Time-series integrated information | IIT-adjacent empirical measure Φ_AR (Barrett & Seth 2011) | `core/phi_ar.py` | `phi_ar_enabled` |
| 7 | Subliminal residual facilitation | GWT — unaccessed content still primes locally | `core/global_workspace.py` (gated) | `priming_enabled` |

Plus: **psychophysics battery probes** (`masking`, `blink`, `priming`,
`reality_monitor`) in `core/test_battery.py`, and a **GET `/agent/coverage`** readout
listing every theory-proposed mechanism the project implements and whether it is active —
explicitly a *coverage checklist*, never a consciousness score.

## Mechanism designs

### 1. Recurrent perception (RPT)

`Perception.encode` is feedforward. RPT holds that *local recurrent processing* — feedback
loops that stabilize/sharpen sensory representations — is the constitutive mechanism.
Implementation: after encoding, `refine(percepts, wm_items, cfg)` runs
`recurrence_passes` micro-iterations. Each pass reconciles the noisy current readings
(danger/novelty/utility) of every percept with the top-down prior held in working memory
(the same object's readings from previous ticks): `f ← f + gain·(prior − f)` with the
blend damped per pass; a convergence delta is recorded. Objects with no WM prior pass
through unchanged. Deterministic, bounded, cheap. With observation noise > 0, refined
readings are *measurably closer to the true object features* than raw ones — perception
as recurrent inference, testable. Trace: `RecurrenceState(passes, mean_delta, stabilized,
n_refined)`.

### 2. Perceptual reality monitoring (PRM)

Lau's PRM: a higher-order mechanism classifies whether a first-order content originates
from the world or from the system itself; conscious "realness" is that verdict — and it
can be wrong (hallucination = internal content judged external). Implementation: after
the workspace competition, infer the winner's source *category* from **content-level
evidence only** (never the source label): perceptual corroboration (cosine similarity of
winner vector to the current perception coalition vector), precision, stability (recent
same-source winners), and vividness (pre-normalization activation). A fixed, readable
evidence model scores three categories — `external`, `memory`, `self_generated` — and
the argmax is the verdict, with confidence. The verdict is then compared to the *actual*
category of the winning source (perception/social/communication → external; memory →
memory; imagination/dream/inner_speech/motivation/... → self_generated; injections are
tallied separately as `foreign`). Rolling accuracy + misattribution counts (hallucination
analogue: self-generated judged external; insertion analogue: foreign judged
self-generated). Trace: `RealityMonitorState(judged, actual, correct, confidence,
evidence, accuracy, hallucinations, insertions, report)`. Metric: `reality_accuracy`.

### 3. Interoceptive inference (Seth)

A *dedicated* interoceptive generative model, separate from the world model: per-action
EMA tables predicting next-tick `energy_delta` and `fatigue_delta`. Each tick it predicts
from the chosen action, then compares with the realized deltas: interoceptive prediction
error. `presence` = EMA-smoothed (1 − error): Seth's proposal that the feeling of
presence tracks successful suppression of interoceptive prediction error, as a variable.
When enabled, the interoceptive PE modulates functional affect (confusion up, satisfaction
down — `model_copy` pattern like curiosity) and the next tick's interoception coalition
precision becomes `presence` (well-predicted body ⇒ trustworthy interoceptive channel).
Trace: `InteroceptionState(predicted_energy_delta, actual_energy_delta,
predicted_fatigue_delta, actual_fatigue_delta, error, presence, report)`. Metrics:
`presence`, `intero_error`.

### 4. Temporal thickness (retention / protention)

The conscious moment is currently a point. Husserlian time-consciousness (and the
"specious present") holds that experience is temporally *thick*: it retains the just-past
(retention) and anticipates the just-coming (protention), and violated protention is
felt as temporal surprise. Implementation: from the stream of conscious moments, build
`retained` = the last `retention_horizon` moments with exponentially decaying weights
(the effective number of still-lingering moments = `specious_width`); `protention` =
predicted next dominant source (modal winner over `protention_window`) + predicted
valence (EMA). Next tick, the realized winner/valence are compared to the previous
protention → `protention_error` (temporal surprise), which (gated) feeds the arousal
salience — a violated anticipation summons vigilance. Trace:
`TemporalityState(retained, specious_width, protended_source, protended_valence,
protention_error, report)`. Metric: `temporal_surprise`.

### 5. Inner speech re-entry (Vygotsky / GWT)

The README names this the natural next step; done LLM-free. Each tick, generate a
*condensed*, self-directed utterance from the **previous** conscious moment (template
condensation of dominant source + affect + action — Vygotskian abbreviation), and enter
it as an `inner_speech` coalition in the next competition with activation
`inner_speech_gain × previous awareness_level` and moderate precision. The agent's own
summarized thought re-enters the arena and may win global access — "hearing oneself
think" as re-entrant architecture. Reentry (inner speech actually winning) is tracked.
`inner_speech` joins `WORKSPACE_SOURCES`. Trace: `InnerSpeechState(utterance, activation,
reentered, reentry_count, condensation, report)`.

### 6. Φ_AR — time-series integrated information (Barrett & Seth 2011)

The Φ-proxy stays (heuristic, honest). Added: **Φ_AR**, a *published empirical measure*
of integrated information for stationary Gaussian time series, computed on the real
coalition-activation history: with X_t the per-source activation vector,
I(X_past; X_present) = ½·log det Σ(X) − ½·log det Σ(X | X_past) under a linear-Gaussian
(AR) model; Φ_AR = the effective information beyond the **minimum information
bipartition** (exact search over all bipartitions of active sources, capped at 12 →
≤ 2047 partitions), normalized for MIB selection by min-part entropy (Balduzzi–Tononi
style) and reported unnormalized, clipped ≥ 0. Computed every `phi_ar_every` ticks over a
`phi_ar_window` history; covariances are ridge-regularized for determinism/stability.
Honesty: Φ_AR is *still not* IIT's causal, state-space Φ — it is a real measure from the
empirical-Φ literature, and its label says exactly that. Trace: `PhiARState(phi_ar,
n_sources, window, tau, mib, i_whole, computed_at_tick)`. Metric: `phi_ar`.

### 7. Subliminal residual facilitation (priming substrate)

GWT's empirical bedrock: content that fails global access is still *locally* processed
and facilitates subsequent processing (subliminal/repetition priming). Implementation
(inside `GlobalWorkspace`, gated by `priming_enabled`): after each competition, every
coalition that did **not** ignite deposits a facilitation trace keyed by
(source, content); traces decay by `priming_decay` per tick; at the next competitions, a
matching coalition's drive gains `priming_gain × trace` **without** entering the
softmax-normalized display field. `WorkspaceState.facilitation_applied` reports the bonus
applied to the winner this tick. This gives subliminal content a real, measurable,
*unconscious* downstream influence — the substrate the priming probe measures.

### Psychophysics battery probes (Phase-4 conventions: hermetic, deterministic, disclaimed)

- **`masking`** — backward masking: a moderate target injected alone ignites; the same
  target followed immediately by a strong mask loses the competition and stays
  subliminal. Score = ignition rate difference (alone − masked).
- **`blink`** — attentional blink: after a strong T1 ignition, the homeostatic effective
  threshold is elevated (ignition-score adaptation) and T1 enjoys maintenance hysteresis,
  so an identical T2 presented at short lag fails to ignite while T2 at long lag (or
  without T1) succeeds. Score = P(T2 ignites | control) − P(T2 ignites | short lag).
- **`priming`** — repetition priming without access: present S subliminally (fails
  ignition), re-present S at borderline strength → ignites, where the unprimed control
  does not. Runs with `priming_enabled` inside the probe only. Score = primed − unprimed
  ignition rate.
- **`reality_monitor`** — source-monitoring accuracy under load: run with imagination +
  dream + inner speech + noise, report accuracy and misattribution counts.

Each `BatteryResult` carries the standard disclaimer: these measure functional
properties of mechanisms; passing is **not** evidence of experience.

### Coverage readout

`GET /agent/coverage`: the full roster of theory-proposed mechanisms (GWT, AST, HOT,
active inference, IIT-proxy + Φ_AR, RPT, PRM, interoceptive inference, temporality,
inner speech, sleep/dream, imagination, curiosity, agency, learning, concepts,
meta-learning, personality, ToM/social, relational self, self-opacity, individuation,
priming substrate) with `{theory, mechanism, module, flag, active}` and an
`active_count / total`. Framed as **functional coverage of the theory roster** with the
disclaimer; explicitly NOT a consciousness measure or "distance to level 1".

## Config (SimConfig + ConfigPatch, all new keys optional/patched)

```
recurrence_enabled=False        recurrence_passes=3 (1..8)      recurrence_gain=0.5 (0..1)
reality_monitor_enabled=False
intero_inference_enabled=False  intero_lr=0.25 (0..1)
temporality_enabled=False       retention_horizon=5 (2..20)     protention_window=6 (2..32)
inner_speech_enabled=False      inner_speech_gain=0.6 (0..1)
phi_ar_enabled=False            phi_ar_window=32 (8..256)       phi_ar_every=8 (1..64)
priming_enabled=False           priming_decay=0.5 (0..1)        priming_gain=0.35 (0..2)
```

## Regression guarantee

All seven flags default **OFF** ⇒ behaviour (positions, energies, action sequences) is
byte-identical to Phase 1–4; the new trace sub-objects stay `null`;
`facilitation_applied` stays 0.0. Locked by `tests/test_asymptote_regression.py`
(same-seed determinism + all-None sub-objects + cross-flag no-op), mirroring
`test_lp_regression.py`. The UI enables the flags by default (house convention).

## Cycle wiring (order)

1. after `perception.encode` → RPT refine (reads last tick's WM items as priors)
2. `_build_coalitions` → + inner-speech coalition (one-tick latency, like imagination)
3. `workspace.compete(...)` → facilitation applied/deposited inside (gated)
4. after compete → Φ_AR buffer append (+ periodic compute); reality monitor verdict
5. interoception: predict at decision, compare after `world.step`, adjust emotion
6. after `_bind_moment` → temporality (retention/protention vs previous protention);
   temporal surprise queued into next tick's arousal salience (gated)
7. after moment → generate next tick's inner-speech utterance
8. trace assembly: 6 new optional sub-objects; metrics: presence, intero_error,
   temporal_surprise, phi_ar, reality_accuracy

## Tests

Per-module unit tests (deterministic, seeded): recurrence denoising/convergence; reality
monitor verdicts + misattribution; interoception error-decrease + presence + shock
response; temporality decay/protention/surprise; inner speech generation/re-entry;
Φ_AR ≥ 0, ≈ 0 for independent sources, > 0 for coupled sources, deterministic; priming
facilitation deposit/decay/boost; battery probes return sane, deterministic results; API
accepts the new config keys and serves `/battery/{masking,blink,priming,reality_monitor}`
+ `/agent/coverage`; regression test as above. Full suite must stay green.

## Honesty contract (unchanged, restated)

Every new mechanism is level 2. The disclaimers ride on every trace sub-object report,
battery result, endpoint payload and README section. Reproducing the functional
mechanisms — however many, however faithful — does not prove phenomenality. The agent is
not conscious, and this phase does not claim otherwise; it only shrinks the set of
proposed mechanisms left unimplemented.
