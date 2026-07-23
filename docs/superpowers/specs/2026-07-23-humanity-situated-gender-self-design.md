# Phase 8 — The situated gendered self: a life-course model of gender experience

**Date:** 2026-07-23

**Status:** approved, implemented and validated

**Scope chosen by the user:** hybrid, factorized, multidimensional, full life course, including
external and internalized transphobia

## Goal

Add an inspectable, deterministic and explicitly limited functional model of gender experience to
Humanity. The model must be capable of representing transfeminine, transmasculine, nonbinary,
gender-fluid, agender, questioning and cisgender trajectories without treating any one trajectory
as the template.

The motivating sequence —

`gender → gender dysphoria → hyperfeminization/hypermasculinization → trans identity`

— is represented as **one possible path**, never as a causal pipeline. The implementation must also
support:

- trans identity with little or no dysphoria;
- euphoria-led self-understanding;
- dysphoria or gendered discomfort without a trans identity;
- identity without social, legal or medical transition;
- partial, paused, revised, reversed or resumed transition;
- nonbinary, fluid and unlabeled lives;
- accentuated expression toward an affirmed gender, toward an assigned gender as compensation, in
  multiple directions, or not at all;
- late realization, selective disclosure, concealment for safety and context-dependent expression.

The feature extends Humanity's level-2 functional self-model. It does **not** reproduce a lived
human subject, settle the phenomenology of gender, or establish a causal theory of trans identity.

## Scientific and ethical framing

The following sources constrain the design:

- The World Health Organization states that trans and gender-diverse identities are not conditions
  of mental ill-health, that gender-variant behaviour or preferences alone are not a basis for a
  diagnosis, and that some trans people seek medical or surgical transition while others do not.
  See [WHO, “Gender incongruence and transgender health in the ICD”][who].
- WPATH Standards of Care Version 8 emphasize individualized pathways and include specific
  consideration of nonbinary people. See [Coleman et al., 2022][wpath].
- The gender-minority-stress literature distinguishes distal/external stressors from
  proximal/internal stressors and identifies resilience factors. See
  [Hendricks and Testa, 2012][hendricks-testa] and [Testa et al., 2015][testa].
- Research on gender euphoria warns against reducing trans life to distress and identifies
  affirmation, calm, relief, joy, community and safety as meaningful positive dimensions. See
  [Jacobsen and Devor, 2022][euphoria].
- Longitudinal research shows that the labels people report can change over time and that label
  fluidity does not by itself invalidate a person's gender. See [Ocasio et al., 2024][fluidity].

These sources do **not** provide coefficients for a computational simulator. All numeric update
rules below are transparent modeling hypotheses selected for boundedness, interpretability and
counterfactual testing. They are not prevalence estimates, clinical thresholds or validated human
scales.

Every public surface must carry this concise framing:

> Functional qualitative model of gender experience. Not a diagnostic, clinical or predictive
> model, and not evidence of subjective experience.

## Non-goals

Phase 8 will not:

- diagnose, classify or estimate the probability that a real or simulated person is trans;
- infer identity from appearance, expression, dysphoria, anatomy or treatment choices;
- encode a biological etiology of gender identity;
- provide medical protocols, doses, eligibility rules or treatment recommendations;
- hard-code current law, age-of-consent rules or access policy as universal;
- model sexual orientation as if it followed from gender identity;
- model sexual content, self-harm, suicide or graphic violence;
- assign prejudice, resilience or identity based on race, culture, class, disability or another
  demographic stereotype;
- claim empirical fidelity to every culture or every trans person's life;
- alter the project's level-1 honesty boundary.

## Architecture

Phase 8 is a set of bounded modules with explicit contracts:

```text
GenderScenario
  ├── private GenderProfile(s)
  ├── LifeCoursePlan(s)
  └── GenderSocialContext
              │
              ▼
     lifecycle + body changes
              │
queued events ├──────── society's one-tick-deferred public responses
              ▼
     GenderExperienceEngine
       ├── GenderExperienceState ──▶ trace / API / observatory
       ├── GenderIntent           ──▶ independent transition progress
       ├── GenderInfluence        ──▶ bounded self-model / motivation effects
       └── gender_experience coalition ──▶ global-workspace competition
```

### Module boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| `core/gender_experience.py` | Pure or state-local update rules for congruence, affect, minority stress, resilience, self-understanding, expression strategy and intent | Read HTTP state, inspect other agents' private profiles, provide medical advice |
| `core/gender_lifecycle.py` | Advance configured life stages and generate abstract body/development events | Assign a universal age to a stage or decide identity |
| `core/gender_society.py` | Build public projections, recognition states and one-tick-deferred social events | Reveal latent profiles or mutate identity |
| `core/gender_scenarios.py` | Validate and instantiate presets/custom scenarios from a seed | Hide random defaults or infer profiles from behaviour |
| `schemas/models.py` | Pydantic contracts, bounds and enums/open-label fields | Encode causal policy |
| `core/agent.py` | Wire the feature into the existing cycle behind a default-off flag | Contain Phase-8 formulas |
| `core/society.py` | Apply social gender updates transactionally and order-independently | Let tick order change outcomes |

The engine owns a seeded RNG derived from `(SimConfig.random_seed, agent_id, "gender")`. No
wall-clock input or unseeded randomness is permitted.

## Data model

All continuous indicators are finite floats in `[0, 1]` unless stated otherwise. They are
qualitative simulator coordinates, not clinical scores.

### 1. Private profile: `GenderProfile`

The profile is an experiment input, never an inference result.

| Field | Meaning |
|---|---|
| `profile_id` | Stable scenario-local identifier |
| `assigned_category` | Open, user-supplied assigned category; not restricted to a binary enum |
| `felt_affinities` | Open map of identity terms to affinity values; multiple terms may be high |
| `felt_timeline` | Optional non-overlapping stage/tick segments that change affinities over time |
| `fluidity` | Permitted rate/amplitude of change in the felt profile |
| `gender_salience` | How central gender-related signals are in this scenario |
| `available_vocabulary` | Terms the agent currently has available for self-description |
| `preferred_expression` | Desired expression by channel and social context |
| `body_preferences` | Preferred affinities and salience by abstract body domain |
| `dysphoria_sensitivity` | Per-domain response to incongruence; may be zero |
| `euphoria_sensitivity` | Per-domain response to affirmation or positive change; independent of dysphoria |
| `transition_priorities` | Independent personal priority for each transition dimension |
| `initial_self_understanding` | Questioning state, initial labels and certainty |

The schema uses the term **felt profile**, not `true_gender`. It is allowed to be stable, fluid,
plural, agender, unlabeled or revised by the configured timeline. Hostility cannot mutate it.

### 2. Identity and expression coordinates

`GenderAxes` provides independent `feminine`, `masculine` and `androgynous` coordinates plus a
bounded `custom` map. Low values on all three can represent neutral or ungendered expression.
These coordinates describe the scenario; they are not definitions of womanhood, manhood or
nonbinary identity.

`GenderSelfUnderstanding` contains:

- `labels: list[str]`;
- `certainty`;
- `questioning`;
- `fit_by_label`, an evidence ledger rather than a probability distribution;
- `known_vocabulary`;
- `disclosure_scopes`, mapping contexts to disclosed labels/pronouns;
- `last_revision_tick`.

`ExpressionChannelState` exists independently for:

- presentation;
- name;
- pronouns;
- voice;
- social role.

Each channel holds desired, private, trusted-context and public coordinates; visibility; safety
cost; an accentuation index; and explicit driver tags.

### 3. Body and congruence

`BodyDomainState` is abstract and contains current affinities, preferred affinities, salience,
public visibility, alignment and current change rate. Presets may use:

- voice;
- face/hair;
- chest;
- body shape;
- primary/reproductive characteristics;
- general embodiment.

Custom scenarios may omit, rename or add domains. The model stores no dose, procedure technique or
anatomical image.

`GenderCongruenceState` reports body, expression, social-recognition and administrative
congruence separately, plus a salience-weighted total. A low value is a mismatch indicator, not an
identity classifier.

### 4. Affect, stress and resilience

`GenderAffectState` contains:

- `dysphoria_by_domain` and `dysphoria`;
- `euphoria_by_domain` and acute `euphoria`;
- slow `fulfillment`, representing sustained comfort/calm rather than an emotional spike;
- `last_affirming_event_ids` and `last_distressing_event_ids`.

`GenderMinorityStressState` contains:

- current and chronic external hostility;
- rejection expectation;
- concealment pressure;
- vigilance;
- internalized transphobia;
- an incident count and cumulative bounded exposure.

`GenderResilienceState` contains:

- interpersonal support;
- community connection;
- positive representation;
- pride;
- self-acceptance;
- a derived resilience index.

Internalized transphobia is modeled as learned negative social pressure, not an identity trait.

### 5. Transition state

A `TransitionDimensionState` exists independently for:

- social transition;
- administrative/legal recognition;
- voice work;
- hormonal transition;
- surgical transition.

Each dimension has:

- `desire`;
- `status`: `not_desired`, `considering`, `desired`, `seeking`, `blocked`, `underway`,
  `completed`, `paused` or `revising`;
- `access`;
- `progress`;
- `satisfaction` in `[-1, 1]`;
- `reversibility`: `fully`, `partly` or `not_modeled`;
- target body/expression domains;
- the last status-change reason and tick.

No dimension is required. Dysphoria is neither necessary nor sufficient to activate one.

### 6. Aggregate trace state

`GenderExperienceState` includes:

- life stage and tick within stage;
- self-understanding;
- expression channels;
- congruence;
- gender affect;
- minority stress;
- resilience;
- transition dimensions;
- current `GenderIntent`;
- recent event IDs;
- an agent-readable functional report;
- the mandatory non-diagnostic disclaimer.

It is optional on `CycleTrace` as `gender_experience: GenderExperienceState | None`.
The private `GenderProfile` never rides on the ordinary trace.

## Configurable life course

`LifeCoursePlan` is a sequence of positive-duration stages selected from `childhood`, `puberty`,
`adolescence`, `adulthood` and `later_life`. Stages are semantic simulator periods, not legal or
medical ages.

- A scenario may start at any stage.
- A stage may be omitted.
- Stages must be monotonic and non-overlapping.
- Each stage defines abstract body-domain deltas, autonomy, resource access and exposure to social
  norms.
- Puberty can change body-domain affinities and therefore congruence, but it cannot create an
  identity.
- Starting in adulthood can include an explicit, inspectable prior-event history rather than
  pretending the past did not exist.
- No medical action is enabled or disabled solely by a stage. Scenario access and explicit intent
  govern simulation progress.

Lifecycle updates run before the gender engine each tick and emit ordinary `GenderEvent`s, making
every change visible and replayable.

## Event model

`GenderEvent` has a stable ID, tick, target agent, optional actor, provenance, type, domain,
intensity, public/private visibility, deliberate/accidental marker and a bounded `context_code`.
Unknown fields are rejected. A short free-text note (maximum 240 characters) is accepted only for
self-exploration, affirmation and transition events; hostile events are rendered from neutral
server-owned templates and accept no free-text payload.

Supported event families are:

| Family | Event types |
|---|---|
| Self-exploration | reflection, reversible exploration, vocabulary discovery, label revision |
| Body/development | stage change, abstract body change, voice change, recovery |
| Affirmation | correct name/pronoun, support, community contact, positive representation, legal recognition |
| Hostility | misgendering, invalidation, rejection, discrimination, threat, care/access barrier |
| Transition | access granted/denied, dimension started, progressed, paused, revised, completed |

Events submitted through the API are queued for the next tick. Applying the queue and producing the
new state is transactional: validation or execution failure leaves the state and ledger unchanged.

Hostile events are summarized rather than dramatized. The feature does not generate slurs or accept
custom hostile-event dialogue.

## Update dynamics

### Congruence

For every configured domain, alignment is:

```text
alignment_d = clip01(1 - mean_absolute_distance(current_affinities, preferred_affinities))
```

The aggregate congruence is a salience-weighted mean. Empty domain sets are neutral (`1.0`) rather
than erroneous or implicitly dysphoric.

### Dysphoria, euphoria and fulfillment

Per-domain dysphoria is a smoothed response:

```text
target_dysphoria_d =
    sensitivity_d
    × salience_d
    × (1 - alignment_d)
    × (0.75 + 0.25 × contextual_pressure)
```

All terms are bounded. `sensitivity_d = 0` guarantees no dysphoria from that domain. External
hostility can amplify existing situated distress but cannot create or change the felt profile.

Euphoria is driven by positive **change** in alignment and affirming events:

```text
target_euphoria_d =
    euphoria_sensitivity_d
    × clip01(positive_alignment_delta_d + affirmation_d)
```

Acute euphoria decays. `fulfillment` is a slower EMA of sustained congruence and affirmation, so
the model can represent calm, relief and ordinary comfort instead of requiring permanent elation.
Dysphoria and euphoria are not complements and may coexist.

### External and internalized transphobia

External hostility combines this tick's hostile-event severity with configured institutional
exposure. Chronic hostility is an EMA.

Internalized transphobia updates slowly:

```text
gain =
    internalization_rate
    × external_exposure
    × (0.5 + 0.5 × norm_rigidity)
    × (1 - resilience)

recovery =
    recovery_rate
    × mean(support, community, pride, self_acceptance)

internalized_next = clip01(internalized_previous + gain - recovery)
```

This variable affects shame, concealment pressure, vigilance and confidence within strict caps. It
does not alter felt affinities and is never used as evidence against an identity.

### Self-understanding

The agent maintains fit scores for labels in its known vocabulary. Evidence comes from its own
responses to reversible exploration, sustained fit, relief, fulfillment and self-authored
reflection. Dysphoria alone and third-party observation are forbidden evidence sources.

- No label is forced when fit is ambiguous.
- `questioning` and no-label states are first-class outcomes.
- Multiple labels may be retained.
- A fluid profile may revise labels without a penalty or “failure” state.
- Safety can delay disclosure, not private understanding.
- New vocabulary can make an existing pattern newly describable without retroactively changing the
  felt profile.

### Accentuated expression

The implementation uses **accentuated expression** as the neutral UI term and documents
hyperfeminization/hypermasculinization as common-language examples.

Accentuated expression is measured relative to the agent's own rolling preferred baseline, never a
population norm:

```text
accentuation_axis =
    max(0, current_axis - rolling_personal_baseline_axis - accentuation_threshold)
```

Drivers are contribution tags selected from:

- exploration;
- euphoria/joy;
- recognition or legibility;
- compensation toward the assigned category;
- pressure to prove an affirmed identity;
- safety/concealment;
- personal aesthetic preference.

The same agent may have different expression in private, trusted and public contexts. High
femininity or masculinity is not automatically called accentuated, and accentuation has no
diagnostic effect.

### Intent and transition

`GenderIntent` is a parallel, explicit life-domain intent, not a replacement for the grid-world
`ActionDecision`. Types include exploration, expression change, disclosure, concealment,
name/pronoun assertion, support seeking, community connection, administrative recognition, voice
work, hormonal care, surgical care, pause, goal revision, reversal and resumption.

Desire arises from the private profile, current alignment, expected fulfillment and personal
priority. Dysphoria is optional. Safety and access affect whether an intent executes, not whether
the desire is considered valid.

Medical dimensions change only abstract body-domain affinities and recovery load. Progress is
gradual for hormonal state and explicit/discrete for surgical state. No protocol, dose or clinical
outcome is implied. Satisfaction is computed from the actual modeled alignment change and may be
positive, neutral or negative; it is not pre-scripted.

## Cognitive integration

When `gender_experience_enabled` is on:

1. Lifecycle and queued events update.
2. The gender engine computes the new `GenderExperienceState`.
3. A `gender_experience` specialist coalition is created only when gender salience is nonzero.
   Its activation is the maximum of current dysphoria, euphoria, recent-event salience and intent
   urgency. Its content cites the exact source variables.
4. When it wins the existing workspace competition, its content can enter the `ConsciousMoment`
   and autobiographical stream like any other specialist.
5. `GenderInfluence` applies bounded deltas to the self-model and adds explicit motivational
   pressures such as seek safety, explore, seek affirmation or pursue an active transition intent.
6. Major gender events enter a bounded `GenderEventRecord` life ledger and can be cited by the
   narrative self.

Per-tick direct effects are capped after configuration weighting:

- mood: absolute delta at most `0.08`;
- confidence: absolute delta at most `0.05`;
- coherence: absolute delta at most `0.03`.

This prevents a numerical feedback loop among dysphoria, stress, mood and internalization.
Identity stability is not included in self-model coherence: a fluid or revised identity is not
treated as incoherent.

With the feature off, the coalition is not added, all Phase-8 pressures are absent, the trace field
is `None`, and historical action/metric trajectories remain unchanged.

## Social model and privacy boundary

Every agent has:

- a private `GenderProfile`;
- an agent-visible `GenderExperienceState`;
- a `PublicGenderProjection` per disclosure context;
- an observer-local `GenderRecognitionState` for each other agent.

Other agents can observe only public expression, disclosed labels/pronouns and prior public
interactions. They cannot read felt affinities, private labels, body preferences, internalized
transphobia or undisclosed transition goals.

`GenderSocialContext` contains bounded scenario inputs:

- norm rigidity;
- institutional hostility;
- baseline safety;
- care/resource access;
- community visibility;
- positive representation.

Observer states contain respect propensity, learned bias, relationship trust, known
labels/pronouns and knowledge confidence. These are scenario variables, never derived from
demographics.

Social processing occurs after all agents complete a tick and is consumed on the following tick,
matching Humanity's relational-self pattern. This one-tick deferral ensures that agent iteration
order cannot change recognition, affirmation or hostility outcomes.

Possible outcomes include affirmation, accidental misgendering, deliberate invalidation, support,
rejection, discrimination and non-graphic threat. Missing knowledge yields uncertainty, not
automatic hostility. The scenario can disable all hostile events while retaining affirmation and
recognition.

Intersectional pressure can be represented through open context tags and independent access/safety
modifiers. Presets must never associate a demographic label with prejudice, poverty, risk or a
particular gender path.

## Scenarios

No trans profile is silently assigned at application boot. The backend default is disabled and the
observatory shows an explicit “Choose a gender-life scenario” empty state.

Built-in, reproducible presets:

- `transfeminine_early`;
- `transfeminine_late`;
- `transmasculine_early`;
- `transmasculine_late`;
- `nonbinary`;
- `genderfluid`;
- `agender`;
- `euphoria_led`;
- `social_transition_only`;
- `partial_medical_transition`;
- `cis_control`.

Presets are examples, not archetypes. The UI exposes every field they set, and custom scenarios can
replace them.

Applying a `GenderScenario` is a structural operation that resets the full run. This avoids mixing
a new childhood/profile with old autobiographical memory, traces or social knowledge. The response
must state that reset explicitly. A scenario records:

- schema version;
- seed;
- selected preset or custom manifest;
- profiles by agent ID;
- life-course plans;
- social context;
- initial event history.

Unspecified agents are Phase-8-disabled, not silently assigned a cis or trans profile.
The request has an `enable` field defaulting to `true`; after a successful reset,
`gender_experience_enabled` equals that explicit value.

## Configuration

Simple runtime coefficients live in `SimConfig` and `ConfigPatch`:

| Parameter | Default | Role |
|---|---:|---|
| `gender_experience_enabled` | `False` | Enables Phase-8 updates for agents with an explicit profile |
| `gender_affect_weight` | `0.20` | Scales bounded mood/confidence/coherence influence |
| `gender_motivation_weight` | `1.0` | Scales Phase-8 goal pressures |
| `gender_internalization_rate` | `0.05` | Maximum slow gain from hostile exposure |
| `gender_recovery_rate` | `0.03` | Slow reduction from resilience inputs |
| `gender_event_memory_max` | `256` | Bound on the private gender-event ledger |

These fields are hot-applicable and validated. Profile, life-course and social-context changes are
structural and must go through the scenario reset endpoint.

## API contract

| Method | Endpoint | Contract |
|---|---|---|
| `GET` | `/gender/scenarios` | List preset IDs, descriptions and complete manifests |
| `POST` | `/gender/scenario` | Validate a preset/custom scenario, reset transactionally and return the initial state |
| `GET` | `/agent/gender` | Agent-readable state; never includes the latent profile |
| `GET` | `/agent/gender/debug` | Explicit observatory/debug view containing experiment inputs and the current state |
| `POST` | `/agent/gender/event` | Queue one validated event for the next tick |
| `POST` | `/agent/gender/intent` | Queue a `user_probe` intent/opportunity; return accepted or a grounded rejection reason |
| `GET` | `/society/agent/{id}/gender` | Agent-readable Phase-8 state for any configured society member |
| `GET` | `/society/agent/{id}/gender/debug` | Explicit private-input observatory view for that member |
| `GET` | `/society/gender` | Public projections, recognition states, social climate and aggregate event counts |
| `GET` | `/export/gender-scenario` | Export the public manifest; private inputs require `include_private=true` |
| `POST` | `/battery/gender-experience` | Run bounded supportive/hostile and dysphoria/euphoria counterfactuals off-line |

The debug endpoint is a conceptual observability boundary, not an authentication boundary; Humanity
is a local simulator. Its response labels every private field as an experiment input unavailable
to simulated observers.

Requests use `extra="forbid"`, finite-number checks, bounded strings/lists, valid agent IDs and
known event/intent types. A malformed request returns `422`; a structural mutation attempted through
a hot endpoint returns `409`; an unavailable or unsafe intent returns a non-mutating accepted-false
result with a reason.

## Observatory

The Mind view gains a full-width **Gender experience** panel. It uses Humanity's existing sober
instrument language and separates:

1. **Experiment input** — private felt profile, visibly marked debug-only;
2. **Self-understanding** — current labels, questioning, certainty and known vocabulary;
3. **Public presentation** — disclosed information and expression by context.

Readouts:

- configurable life-course timeline with event provenance;
- body, expression, social and administrative congruence;
- dysphoria, acute euphoria and sustained fulfillment by domain;
- current expression by channel/context;
- accentuation level and driver tags;
- external hostility, chronic exposure, concealment pressure, vigilance and internalized
  transphobia;
- support, community, pride, self-acceptance and resilience;
- independent transition dimension status, desire, access, progress and satisfaction;
- current intent and grounded report.

The scenario builder offers preset selection and complete custom editing. Applying it uses a reset
confirmation that explains which run data will be replaced.

Visual and accessibility requirements:

- no pink/blue binary color code and no stereotyped icons;
- text labels and patterns in addition to color;
- semantic HTML meters/tables/lists with keyboard access;
- an ordered textual event list backing every visual timeline;
- compact mobile layout at 360/390 px without horizontal data loss;
- hostility details collapsed by default, with a “supportive context only” control;
- source/provenance badges on every derived headline;
- no simulated slurs or graphic copy;
- no celebratory or tragic visual treatment imposed on a path;
- the non-diagnostic disclaimer remains visible in the panel.

The Settings panel adds Phase-8 coefficients and an unchecked feature toggle. Unlike earlier
mechanisms, local-storage defaults do not silently enable Phase 8 without a selected profile.

## Persistence, reset and export

- `CycleTrace.gender_experience` stores the ordinary observable state or `None`.
- `/agent/consciousness` exposes the latest optional `gender_experience` state so background runs
  refresh the observatory consistently with the existing optional Phase states.
- The manager checkpoint includes profiles, lifecycle position, queued events, event ledger,
  recognition states, transition state and the gender RNG state.
- Checkpoint load must resume bit-for-bit from the next tick.
- The ordinary trace/export never includes a private profile.
- A scenario manifest can be exported separately with an explicit `include_private=true`
  debug choice.
- Scenario reset clears incompatible gender events, social recognition, autobiographical state and
  traces by resetting the full run.
- Hot coefficient changes preserve current Phase-8 state.
- The bounded event ledger uses deterministic oldest-first eviction.

## Error handling and invariants

The engine validates these invariants before committing a tick:

1. No NaN, infinity or out-of-range indicator.
2. No event or observer mutation of `GenderProfile.felt_affinities`.
3. No identity-label update whose sole evidence is dysphoria, expression or third-party appraisal.
4. No transition progress without an active intent and access.
5. No medical-domain event containing a protocol or dose field.
6. No private field in a public projection, ordinary trace or society summary.
7. No negative stage duration, overlapping profile segment or unknown target agent.
8. No self-model delta above the declared caps.
9. No hostile-event generator when the scenario disables hostility.
10. No partial mutation after a validation, worker or persistence failure.

Invariant failure aborts the Phase-8 update, restores its pre-tick snapshot and surfaces an explicit
instrument error. It must not silently coerce identity, invent a fallback profile or continue with
partial social events.

## Scientific battery

`POST /battery/gender-experience` runs off-line with persistence and trace logging disabled. It
contains matched, same-seed counterfactuals:

1. identical profile in supportive versus hostile contexts;
2. identical profile with expression allowed versus coerced/concealed;
3. euphoria-sensitive/low-dysphoria versus dysphoria-sensitive paths;
4. isolated versus community-connected contexts.

It reports:

- felt-profile checksum equality;
- self-understanding and disclosure trajectories;
- congruence, dysphoria, euphoria and fulfillment curves;
- external and internalized transphobia;
- resilience;
- transition intentions/progress;
- identity-inference invariant violations, which must remain zero.

Interpretation must state that this demonstrates consequences of the **implemented assumptions**,
not evidence about causal effects in real people.

## Test plan

### Unit tests

- all schemas accept valid open labels/custom domains and reject malformed/non-finite data;
- congruence math, empty-domain neutrality and EMA bounds;
- zero dysphoria sensitivity produces zero dysphoria despite mismatch;
- positive alignment change/affirmation can produce euphoria without dysphoria;
- acute euphoria decays while fulfillment can remain;
- internalization rises only with exposure and falls only through configured recovery inputs;
- profile checksum remains unchanged under every event;
- accentuation is relative to personal baseline and exposes correct drivers;
- every transition dimension progresses independently;
- pause, revision, reversal and resumption preserve a coherent event ledger;
- disabled feature adds no coalition, pressure or self-model delta.

### Trajectory tests

- euphoria-led trans trajectory with negligible dysphoria;
- dysphoria/discomfort without automatic trans labeling;
- transfeminine and transmasculine early and late paths;
- nonbinary, fluid, agender and unlabeled paths;
- accentuation toward affirmed identity;
- compensation toward assigned category before later self-recognition;
- social-only, partial-medical and no-transition outcomes;
- selective disclosure across private/trusted/public contexts;
- pause, detransition and retransition without forced identity invalidation;
- same profile in supportive/hostile contexts: identical profile checksum, different stress and
  resilience outcomes.

### Society and privacy tests

- other agents see only `PublicGenderProjection`;
- undisclosed labels/pronouns never leak;
- accidental misgendering requires missing/incorrect recognition rather than latent-profile access;
- deliberate hostility is impossible in hostility-disabled scenarios;
- social results are identical under reversed agent iteration order;
- no demographic tag changes prejudice unless an explicit independent context modifier says so.

### API, persistence and export tests

- all endpoints, `409`/`422`/accepted-false paths and atomic rollback;
- scenario application performs a full explicit reset;
- standard traces/exports exclude the private profile;
- private manifest export requires the explicit debug flag;
- checkpoint save/load yields the same subsequent Phase-8 and ordinary cognitive traces;
- full scenario JSON round-trip is stable and versioned.

### UI and runtime validation

- static UI contract tests for all controls, labels, disclaimers and settings defaults;
- keyboard and screen-reader semantics for scenario editing, meters and event timeline;
- desktop and 360/390 px mobile screenshots;
- browser-console validation with no errors;
- real runtime probe covering scenario selection, hostile and affirming event injection, background
  run, checkpoint round-trip and trace export;
- the complete historical pytest suite remains green;
- a feature-off regression compares action, world, metrics and self-model trajectories against the
  pre-Phase-8 baseline, with only the new optional trace key allowed to be `None`.

## Documentation requirements

The README receives:

- a Phase-8 section with the honesty framing;
- a diagram of the private/self/public separation;
- data-field and endpoint tables;
- a worked supportive-versus-hostile counterfactual;
- configuration and scenario instructions;
- the accentuated-expression explanation;
- an explicit distinction among gender incongruence, dysphoria, euphoria and trans identity;
- scientific references and a limitations section;
- updated test/runtime counters only after they are measured.

README wording must not claim that Humanity “reproduces trans identity” without qualification. The
approved claim is:

> Humanity implements an inspectable qualitative functional model of multiple gender-identity and
> transition trajectories, including minority stress and resilience; it is not a diagnostic,
> clinical or empirically calibrated model of real people.

## Delivery slices

The implementation plan must preserve these independently testable boundaries:

1. **Contracts and factorized engine** — schemas, scenarios, congruence, affect, stress, resilience,
   expression and transition unit tests.
2. **Life course and cognition** — lifecycle events, intent, self-model/motivation influence,
   workspace coalition, trace and counterfactual battery.
3. **Society and state surfaces** — public projections, recognition, deferred social events, API,
   checkpoint and export.
4. **Observatory and publication quality** — scenario builder, Mind panel, responsive/a11y QA,
   README and full runtime validation.

No slice may claim completion for Phase 8 until all four are integrated and the real observatory
path has been exercised.

## Acceptance criteria

Phase 8 is complete only when:

- all four delivery slices are implemented;
- every invariant above has a direct test;
- the required trajectory and counterfactual suite passes deterministically;
- the historical full suite passes with feature-off compatibility;
- checkpoint replay and exports are verified on a real Phase-8 run;
- the desktop and mobile observatory expose every approved dimension without private-data leakage;
- the README states measured test/runtime results and the exact limitations;
- no implementation or documentation path encodes
  `dysphoria → accentuated expression → trans identity` as mandatory.

[who]: https://www.who.int/standards/classifications/frequently-asked-questions/gender-incongruence-and-transgender-health-in-the-icd
[wpath]: https://doi.org/10.1080/26895269.2022.2100644
[hendricks-testa]: https://doi.org/10.1037/a0029597
[testa]: https://doi.org/10.1037/sgd0000081
[euphoria]: https://doi.org/10.57814/ggfg-4j14
[fluidity]: https://doi.org/10.1177/00333549231223922
