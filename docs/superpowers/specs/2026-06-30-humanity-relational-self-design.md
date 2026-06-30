# Relational self (looking-glass self / social mirror) — design

## Honest framing (load-bearing)

This is a **level-2** mechanism. It does **not** bring the project closer to level 1 (real
phenomenal experience) — nothing can; that is the hard problem. It instantiates a respected idea
about *self-consciousness* — that the self is partly constituted by the regard of others (Cooley's
"looking-glass self", Mead, Hegelian recognition, Lacan's mirror stage) — as **variables and
algorithms**, and turns the question *"without social relation, could one conscientize one's own
being?"* into a **runnable experiment**. Reproducing the mechanism does not prove phenomenality.

## Idea

Each agent already runs theory of mind on others (`OtherMind` per congener: `trust`,
`inferred_valence`, `familiarity`). The relational self adds the **inverse**: a representation of
**how the agent is regarded by the others who model it**, fed back into its **self-model**.

- An agent embedded in a society has its self-model **co-constituted** by an external social anchor.
- An **isolated** agent (no congeners in range) has **no reflected appraisal** → its self-model
  rests on internal signals only → testably "thinner"/less anchored. That contrast is the experiment.

## Mechanism (additive, deterministic, grounded, flag-gated default-OFF, UI-ON)

1. **`core/social_self.py` — `reflected_appraisal(models_of_me, n_others, now_tick)` → `RelationalSelf`**
   (pure function). From the `OtherMind`s that *other* agents hold about this agent (only observers
   who saw it recently, `familiarity > 0`):
   - `reflected_appraisal` ∈ [0,1] = mean over observers of `0.5·trust + 0.5·(inferred_valence+1)/2`
     (how positively I am regarded), 0.5 when nobody models me;
   - `social_presence` ∈ [0,1] = (#observers) / (#others) — "am I seen, by how many";
   - `regard_consistency` ∈ [0,1] = `1 − std(regards)` — do observers agree (a stable mirror);
   - `n_observers`.

2. **`SocietyManager.tick()`** — after every agent has cycled (ToM refreshed), compute each agent's
   `RelationalSelf` from the *other* agents' ToM models of it, and store it on the agent as
   `incoming_appraisal`, **consumed on the next tick** (one-tick deferred ⇒ order-independent ⇒
   deterministic). Only when `social_mirror_enabled`.

3. **`CognitiveAgent`** — holds `incoming_appraisal: RelationalSelf | None`; when
   `social_mirror_enabled`, passes it to `SelfModel.update(..., reflected=...)`.

4. **`SelfModel.update`** — when given a `reflected` appraisal, stores it in
   `SelfModelState.relational_self` and applies a **looking-glass overlay** scaled by how *seen* the
   agent is (`w = social_mirror_weight · social_presence`):
   - `confidence ← (1−w)·confidence + w·reflected_appraisal` (well-regarded raises it, distrust lowers it);
   - `mood` nudged gently toward the reflected valence.
   With `social_presence = 0` (isolation) the overlay is null ⇒ numerically identical to baseline.

## Backward compatibility / determinism

- `social_mirror_enabled` defaults **`False`** ⇒ `relational_self` stays `None`, no nudge ⇒
  Phase-1/2/3 behaviour byte-identical; the whole historical suite stays green.
- Flag-on **single agent**: no congeners ⇒ `social_presence = 0` ⇒ overlay weight 0 ⇒ numeric
  trajectory identical to baseline (only `relational_self` is populated, neutral). The UI enables it.
- One-tick-deferred, single shared seeded RNG, fixed ascending tick order ⇒ a society stays
  reproducible (same `random_seed` ⇒ same society tick-for-tick), with the mirror active.

## Phase-4 experiment — `relational_self_test`

Runs the **same** agent **isolated** vs **in a society** (social mirror on), same seed/ticks, and
reports the social anchoring the mirror produces (social presence × regard consistency, and the
reflected contribution to the self-model) that the isolated agent lacks. Honest interpretation +
`BATTERY_DISCLAIMER`. Exposed as `POST /battery/relational_self` and a Laboratory button.

## Config

| Parameter | Default | Role |
|---|---|---|
| `social_mirror_enabled` | `False` | Enables the relational self (self-model fed by others' regard). |
| `social_mirror_weight` | `0.3` | Max strength of the looking-glass overlay (scaled by social presence). |
