# 02 — Carte de contrats (référence anti-régression de la refonte GUI)

Date : 2026-07-11 · Sources auditées : `ui/app.js` (2 850 l.), `ui/index.html` (899 l.),
`ui/styles.css` (1 303 l.), `app/api/routes.py` (877 l.), `app/main.py`, `schemas/models.py`,
`core/constants.py`, `core/society.py`, `core/agent.py` (`consciousness_state`, l.1701),
`tests/test_interaction_ui.py`, `tests/test_phase7_ui.py`.
Payloads observés en live (GET uniquement) sur `http://127.0.0.1:8123` (tick 14, tous flags OFF —
donc les formes « dégradées / null » ci-dessous sont des observations réelles, pas des suppositions).

**Règle d'or de la refonte** : tout ce qui est listé ici est un contrat. Un id, une classe, un
attribut `data-*`, une chaîne littérale JS ou CSS, un ordre d'appels — chacun est soit consommé par
`app.js`, soit verrouillé par pytest, soit les deux.

---

## 1. Inventaire DOM contractuel

### 1.1 Ids HTML référencés par app.js (complets, groupés par panneau)

**Masthead / transport / statut**

| id | usage JS (app.js) |
|---|---|
| `status-pill` | `setStatus` réécrit `className = "pill pill-" + kind` (kinds : `idle`, `running`, `error`) — l.146-150 |
| `status-label` | texte du statut |
| `btn-theme` | toggle `data-theme` sur `<html>` + re-teinte les canvas (l.161-169) |
| `framing-text` | ÉCRASÉ à chaque poll par `GET /state.framing` (l.1595) |
| `btn-step` / `btn-start` / `btn-pause` / `btn-reset` | transport ; `disabled` piloté (`setRunningUI`, step in-flight) |
| `input-tps` | `parseFloat(...) \|\| 4` → `POST /run {tps}` |
| `footer-disclaimer` | rempli depuis `GET /state.disclaimer` (l.1594) |

`window.scrollY > 40` bascule `body.classList.toggle("is-scrolled")` (l.2842-2848) — la CSS du
masthead compact en dépend, et pytest verrouille deux règles `body.is-scrolled ...` (§3).

**Hero — moment conscient (`.panel-hero`)**

| id | usage |
|---|---|
| `ignition-state`, `ignition-sub` | textes « Global access » / « Subliminal » + sous-titre |
| `ig-fill` | largeur % + classe **`over`** togglée quand score ≥ seuil (l.379-381) |
| `ig-thresh` | `style.left` % (marqueur du seuil effectif) |
| `ig-score`, `ig-eff` | valeurs f3 |
| `moment-contents` | texte du moment ; classe **`flash`** retirée/reposée avec `void q.offsetWidth` pour relancer l'animation (l.331-334) |
| `aw-fill`/`aw-val`, `val-fill`/`val-val`, `phi-fill`/`phi-val` | meters ; `val-fill` est BIPOLAIRE : `left`+`width` calculés depuis le centre 50 %, fond `--pos`/`--neg` (l.342-347) |
| `stream-track` | rebuild innerHTML : barres `div.spark[.ignited]`, hauteur `10 + aw*30 px`, `title` multi-ligne ; auto-scroll à droite (l.472-484) |

`ignition` et `ignition-lamp` existent dans le HTML mais ne sont **pas** référencés par le JS
(hooks CSS uniquement : `.is-ignited .ignition-lamp`). La classe **`is-ignited`** est togglée sur
**`.panel-hero`** (sélecteur `$(".panel-hero")`, l.311/319) — c'est un sélecteur de classe contractuel.

**Global workspace (`.panel-workspace`)**

| id | usage |
|---|---|
| `ws-broadcast`, `ws-winner` | readout ; `ws-winner` reçoit la classe **`subliminal`** quand non-igné (l.424) |
| `arousal-fill`, `arousal-val`, `arousal-baseline-mark` | meter arousal ; le marqueur baseline lit **le slider** `configValue("arousal_baseline")`, PAS le backend (l.428, 1583) |
| `coalitions` | conteneur : `querySelectorAll(".coalition").forEach(remove)` puis rebuild — **l'enfant `#threshold-line` doit survivre** (l.415) |
| `threshold-line` | `style.left = calc(134px + (100% - 134px - 54px) * frac)` — couplé DUR à la géométrie CSS (label 124px + gap 10px ; valeur 44px + gap 10px) (l.463-465) |
| `threshold-val` | seuil effectif f3 ; aussi réécrit depuis `POST /config` → `out.config.ignition_threshold` (l.2198-2200) |

Rangées construites : `div.coalition[.winner|.dominant]` > `div.co-label` (contenant
`span.co-src`), `div.co-bar` > `div.co-fill` (largeur relative au max), `div.co-val`.
`winner` = dominant ET igné ; `dominant` = dominant non-igné (l.437-452).

**Indicateurs (metrics strip)**

`metric-grid` : rempli une seule fois par `ensureMetricCells()` (garde
`grid.childElementCount`, l.505-518). Cellules : `div.metric-cell.tone-{accent|cool|neg|pos}`
avec `dataset.key`, inner : `[data-val]`, `svg.mc-spark` > `path.area[data-area]` + `path[data-line]`.
Sélecteur de mise à jour : `.metric-cell[data-key="<k>"]` (l.565).
`METRIC_DEFS` (l.491-503) : `phi_proxy` (accent/f3), `arousal` (cool/f3), `free_energy` (neg/f3,
auto-échelle, peut être négatif), `prediction_error` (neg), `self_coherence` (pos),
`meta_confidence` (accent), `energy` (pos/f2), `phi_causal` (accent), `vfe` (neg),
`wandering_occupancy` (cool), `task_progress` (pos). Historique client `HIST = 60` points.

**Deep consciousness (Phase 2)** : `circadian-dial` (canvas 120×120), `sleep-state`
(classe **`is-asleep`** togglée), `dream-line`, `agency-fill`/`agency-val`,
`boredom-fill`/`boredom-val`, `imagined-plan`.

**Learning & personality (Phase 3)** : `q-bars` (rangées `div.q-row` > `span.q-label`,
`div.q-bar` > `div.q-fill[.neg]`, `span.q-val.mono` ; triées décroissant, échelle = max |v|),
`concept-state`, `elr-val`, `personality-label`, `personality-traits` (`div.trait-row` >
`span.trait-k`, `div.meter` > `div.meter-fill`, `span.trait-v.mono`).

**L'asymptote (Phase 5)** : `presence-fill`/`presence-val`, `specious-val`, `protention-line`,
`phi-ar-val`, `phi-ar-mib`, `recurrence-state`, `reality-verdict`, `reality-report`,
`inner-speech-line`, `reentry-count`, `btn-inner-voice`, `inner-voice-status`.

**L'horizon (Phase 7)** : `horizon-readouts` (6 `article.horizon-readout.is-live|.is-dormant` >
`span.hr-label`, `strong.hr-value`, `span.hr-note` — innerHTML régénéré à chaque poll, l.997-1006),
`horizon-task`, `btn-horizon-profile` (POST des 8 flags `HORIZON_FLAGS`, l.25-29 + 2224-2242),
`btn-export-analysis` (`window.open('${API}/export/analysis')`).

**Access dynamics** : `ignition-chart` (canvas 720×260 ; `aria-label` RÉÉCRIT dynamiquement avec le
résumé, l.1132), `ignition-chart-summary` (texte résumé ; PAS d'aria-live — verrouillé par pytest),
`horizon-stream` (barres `span.moment[.ignited]` ; hauteur `max(4, aw*50)px` ; `backgroundColor`
depuis la table **`SOURCE_COLORS` en dur** — hex non thémés : perception `#d8a84e`, memory
`#7fb5a6`, self `#9b86c8`, emotion `#c87463`, goal `#80a85e`, imagination `#739bc5`, dream
`#755c9f`, social `#c98ba7`, inner_speech `#d0b674`, wandering `#69a9ad`, language `#b69462`,
unknown `#7b7870` (l.19-24) ; `aria-label` d'ensemble réécrit, l.1165-1168).

**Topologie autobiographique (memory graph)** : `memory-search-form` (+ sélecteur
**`#memory-search-form button[type='submit']`**, l.129 ; le submit passe par
`ev.currentTarget.querySelector("button[type='submit']")`), `memory-search-input`,
`memory-search-results` (`div.memory-search-status[.is-error]` ou `article.memory-search-result` >
`.msr-top` > `.msr-action` + `.msr-meta`, puis `.msr-summary`), `memory-graph` (canvas 720×440,
`tabindex=0` ; **expando `canvas._placedNodes`** = contrat interne pour hit-test/tooltip/clavier),
`memory-graph-tooltip` (attribut `hidden` togglé ; contenu `strong` + `span` + `br` ; positionné via
`offsetWidth/offsetHeight` mesurés — verrouillé), `memory-graph-summary`, `memory-graph-nodes` /
`memory-graph-edges` (`ol.sr-only`, un `li` par nœud/arête — miroir accessible complet),
`memory-graph-selection` (`aria-live=polite`, annonce la sélection clavier).
Clavier : flèches/Home/End/Escape (l.2128-2156). Layout déterministe : spirale à angle d'or
`2.399963229728653` + phase `tick % 24` (l.1329-1340).

**Laboratory (Phase 4)** : `lab-metric` (select — options littérales : `energy`, `agency`,
`phi_proxy`, `phi_ar`, `presence`, `temporal_surprise`, `reality_accuracy`, `language_success`,
`vocabulary_size`, `prediction_error`, `arousal`), `lab-chart` (canvas 560×220, une polyline par
`agent_id`), `btn-export-csv`, `btn-export-json`, `lab-scenario` (textarea JSON), `btn-scenario-run`,
`lab-scenario-summary`, `btn-mirror`, `btn-false-memory`, `btn-calibration`, `btn-relational-self`,
`btn-masking`, `btn-blink`, `btn-priming`, `btn-reality-monitor`, `btn-language-genesis`,
`lab-battery-result`, `lab-disclaimer` (ÉCRASÉ verbatim par `r.disclaimer` de chaque batterie,
l.2432-2434), `btn-audit`, `btn-report-card`, `llmprobe-status`, `audit-result` (`hidden` ;
rangées avec `.row-title.verdict-faithful|.verdict-confab`), `report-card-out` (`hidden`),
`btn-biography`, `btn-cross-examine`, `organ-status`, `biography-out` (`hidden`), `crossx-out`
(`hidden` ; rangée `.crossx-verdict`), `train-ticks`, `btn-fast-train`, `train-result`,
`coverage-count`, `coverage-list`, `ckpt-name`, `btn-ckpt-save`, `ckpt-status`, `ckpt-list`
(rangées avec `div.ckpt-actions` > 2 boutons `btn btn-quiet micro` Load/Delete ; Load `disabled`
si `compatible === false` + suffixe « · legacy », l.2551-2555).

**World** : `world-canvas` (canvas 560×560, `tabindex=0` ; clic ET clavier
flèches/Enter/Espace injectent un stimulus), `world-meta` (texte « tick N · GET /state » ou
« tick N · synchronizing post-action world » après Step), `world-stimulus-kind`,
`world-stimulus-intensity`, `world-interaction-status` (`aria-live`).
`world-interaction-help` n'est référencé que par `aria-describedby` (valeur exacte verrouillée).

**Society** : `input-nagents`, `btn-society-apply`, `soc-selected` (texte « viewing agent N »),
`society-canvas` (560×560 ; clic = sélection d'agent par hit-test de cellule), `society-relations`
(innerHTML de `div.row` > `span.mono` + `span.micro`, sinon `<div class="micro">No relations yet.</div>`).

**Interventions expérimentales** : `experimental-interventions` (attribut `aria-busy` togglé),
`intervention-tabs` (+ enfants `[role='tab']` — ids `intervention-tab-{ask,stimulus,inject,attend,perturb}` ;
gestion `aria-selected`/`tabIndex`/roving focus + flèches/Home/End), panneaux-formulaires
`intervention-{ask,stimulus,inject,attend,perturb}` (attribut `hidden` togglé via
`[data-intervention-panel]`), champs : `intervention-ask-question`, `intervention-ask-intent`,
`intervention-stimulus-kind|-intensity|-x|-y`, `intervention-inject-content|-activation|-precision|-ttl`,
`intervention-attend-target|-strength|-ttl`, `intervention-perturb-type|-magnitude`,
`btn-clear-interactions`, `interaction-log` (`li.interaction-entry.is-{request|result|error}` >
`.interaction-entry-head` > `span.interaction-sequence.mono` (« #001 ») + `strong.interaction-kind` +
`code.interaction-endpoint`, puis `pre.interaction-payload` ; **cap 40 entrées** ; payload tronqué à
1200 chars → 1197 + « ... », l.1713-1736).

**L'invention du langage (Phase 6)** : `lang-convergence`, `lang-distinct`, `lang-success-fill`/`-val`,
`lang-deficit-fill`/`-val`, `lang-exchange`, `lang-vocab` (`span.chip.lang-chip.kind-<meaning>` ou
`span.chip.chip-empty`), `lang-dictionary` (rangées ; `.row-title.kind-<meaning>`).

**Attention schema** : `ast-aware` (classes **`aware-conscious`**/**`aware-subliminal`** togglées +
`style.opacity` inline `0.55 + 0.45*aw`, l.356-359), `ast-stab-fill`, `ast-stab-val`, `ast-attributed`.

**Métacognition (HOT)** : `g-meta`, `g-perc`, `g-pred` (paths SVG : `strokeDashoffset = 132*(1-v)` —
**la constante 132 doit égaler le `stroke-dasharray` CSS**, l.399-403), `meta-conf-val`,
`perc-rel-val`, `pred-rel-val`, `hot-report`, `opacity-fill`, `opacity-val`, `opacity-report`
(`self-opacity` est un conteneur HTML non référencé en JS).

**Introspection** : `introspection` (liste `.report-item` > `.ri-key` + `.ri-text`, ou `.empty` ;
7 champs `INTRO_FIELDS` : perceive/attend/predict/intend/why/remember/self_state, l.615-623),
`btn-narrate`, `narrate-status`, `narrate-output` (`hidden`), `narrate-model` (`hidden`),
`converse-log` (`hidden` jusqu'au 1er tour ; `div.cv-turn.cv-q|.cv-a[.cv-error]` > `span.cv-who` +
`div.cv-text`), `converse-form`, `converse-input`, `btn-converse`.

**Self-model** : `self-model` (paires `span.k` + `span.v` ; ligne « Social mirror » ajoutée si
`relational_self` présent), `indiv-fill`/`indiv-val` + sous-meters `indiv-coh|dis|con|agy` —
**le JS concatène l'id : `setBar("#indiv-coh")` cherche `#indiv-coh-fill` et `#indiv-coh-val`**
(l.872-875), `indiv-report`, `self-goals` (`span.chip` ou `span.chip.chip-empty` « no goal »),
`goal-form`, `goal-input`, `self-narrative`. (`individuation` = conteneur HTML non référencé en JS.)

**Working memory / mémoires** : `wm-load-fill`, `wm-load-val` (en %), `working-memory`,
`recent-memories` — toutes deux en rangées `div.row` > `div.row-top` >
`span.row-title[.kind-{food|hazard|tool|curio}]` + `span.row-tag`, puis `div.row-sub` ; vide →
`div.empty`.

**Settings (`.panel-config`)** : `config-sliders` + 6 groupes de toggles `deep-toggles`,
`lp-toggles`, `asymptote-toggles`, `language-toggles`, `horizon-toggles`, `persistence-toggles`
(les ids de groupes ne sont PAS lus par le JS — le sélecteur réel est global, voir 1.2).

### 1.2 Classes CSS utilisées comme sélecteurs JS (querySelector/querySelectorAll)

| Sélecteur | où (app.js) |
|---|---|
| `.panel-hero` | l.311 (toggle `is-ignited`) |
| `.panel-config input[data-flag]` | l.714, 2213 (reflet + change-listeners de TOUS les toggles) |
| `.panel-config input[data-flag="persist_memory"], .panel-config input[data-flag="trace_logging"]` | l.2492 (fast-train) |
| `#config-sliders .slider-row` (+ variante `[data-key="<k>"]`) | l.718, 2167, 2173, 2182 |
| `.slider-val` (dans une `.slider-row`), `input` (premier input de la row) | l.722-724, 2184-2186 |
| `.metric-cell[data-key="<k>"]`, `[data-val]`, `[data-line]`, `[data-area]` | l.565-570 |
| `.coalition` (remove ciblé dans `#coalitions`) | l.415 |
| `#memory-search-form button[type='submit']` | l.129 (reset d'état) |
| `#intervention-tabs [role='tab']` | l.1834, 1845 |
| `[data-intervention-panel]` | l.1835 |
| `.intervention-form` | l.1859 |
| `#intervention-tabs button, .intervention-form button[type='submit'], #btn-clear-interactions` | l.1744-1746 (`setInterventionBusy`) |
| `button[type='submit']` (dans le form soumis) | l.1804, 2000 |

Classes d'état posées/togglées par le JS (la CSS doit les garder) : `is-ignited`, `flash`, `over`,
`subliminal`, `winner`, `dominant`, `aware-conscious`, `aware-subliminal`, `is-asleep`,
`is-scrolled` (sur `body`), `is-live`/`is-dormant` (horizon), `ignited` (sur `.spark` et `.moment`),
`is-request`/`is-result`/`is-error` (interaction-entry), `is-error` (memory-search-status),
`verdict-faithful`/`verdict-confab`, `cv-q`/`cv-a`/`cv-error`, `crossx-verdict`, `neg` (q-fill),
`chip-empty`, `lang-chip`, `kind-*`, `tone-*`, `pill-idle`/`pill-running`/`pill-error`, `empty`.

### 1.3 Attributs data-* contractuels

- **`data-flag`** (checkboxes Settings) — 32 valeurs :
  P2 : `circadian_enabled sleep_enabled dream_enabled imagination_enabled curiosity_enabled agency_enabled self_opacity_enabled` ·
  P3 : `learning_enabled concepts_enabled meta_learning_enabled personality_enabled satiation_enabled social_mirror_enabled individuation_enabled` ·
  P5 : `recurrence_enabled reality_monitor_enabled intero_inference_enabled temporality_enabled inner_speech_enabled phi_ar_enabled priming_enabled` ·
  P6 : `language_drive_enabled` ·
  P7 : `phi_causal_enabled hierarchy_enabled planning_enabled vector_memory_enabled td_learning_enabled mind_wandering_enabled world_dynamics_enabled tasks_enabled` (les 8 sont verrouillés par pytest) ·
  Persistance : `persist_memory trace_logging`.
- **`data-key`** + **`data-fmt`** (sliders — 9 rows, `fmt ∈ {f2, int, f0}`, défaut f3 dans `fmtSlider`) :
  `ignition_threshold` (f2), `arousal_baseline` (f2), `precision_weight` (f2), `epistemic_weight` (f2),
  `curiosity` (f2), `caution` (f2), `working_memory_capacity` (int → `Math.round` au POST),
  `initial_energy` (f0), `world_noise` (f2).
- **`data-intervention`** + **`data-endpoint`** (tabs) et **`data-intervention-panel`** +
  **`data-endpoint`** (forms) : valeurs `ask|stimulus|inject|attend|perturb` et endpoints
  `/agent/ask /world/stimulus /agent/inject /agent/attend /agent/perturb` — doivent rester
  synchrones avec la map JS `INTERVENTION_ENDPOINTS` (l.1703-1709) ; pytest lit les `data-endpoint`.
- **`data-theme`** sur `<html>` (valeurs `dark`/`light` ; `dark` posé dans le HTML source).
- Créés par le JS : `data-key` (metric-cell), `data-val`, `data-line`, `data-area`.
- `data-id` sur `.gauge` : décoratif (non lu).
- Expando JS : `canvas._placedNodes` (memory-graph).

### 1.4 Variables CSS lues par les canvas (`cssVar()`, l.173-175)

Exactement 12 : `--accent`, `--accent-bright`, `--pos`, `--neg`, `--cool`, `--curio`, `--line`,
`--ink`, `--ink-faint`, `--ink-soft`, `--bg-inset`, `--mono` (police du cadran circadien).
Définies dans `:root, [data-theme="dark"]` (styles.css l.22-46) et `[data-theme="light"]` (l.51-74).
Toute nouvelle palette DOIT fournir ces 12 variables sur `documentElement`, sinon les 6 canvas
(world, society, circadian, ignition-chart, memory-graph, lab-chart) deviennent invisibles/noirs.
Les variables non lues par JS mais structurantes : `--bg`, `--ink-ghost`, `--line-soft`,
`--accent-soft`, `--accent-glow`, `--halo`, `--shadow`, `--grain-op`, `--serif`, `--sans`, `--radius`.

---

## 2. Contrat API frontend

`API = ".."` (l.14) : l'UI est servie sous `/ui/`, l'API à la racine — tout fetch est relatif
(`fetch("../state")`). `api()` (l.56-64) : jette `Error("path -> status")` si `!res.ok` ; renvoie
`null` si le content-type n'est pas JSON. `POLL_MS = 350 ms` pendant un run ; le cycle complet est
mono-file (`refreshInFlight`/`refreshQueued`, l.1534-1552).

### 2.1 Appels réseau d'app.js et champs réellement consommés

**Batch de poll `performRefreshAll` (Promise.all, chaque appel `.catch(() => null)`) :**

| Appel | Champs consommés |
|---|---|
| `GET /state` | `world \|\| snapshot \|\| <racine>` (puis `.grid_size .tick .agent{x,y} .objects[{x,y,kind,novelty,danger}] .radius?` — absent du /state legacy → 3, `.season?/.task?` via renderHorizon), `.tick` (fallback `metrics.tick`), `.arousal`, `.running` (pilote `setRunningUI` + start/stopPolling), `.working_memory`, `.working_memory_load`, `.self_model` (fallback si /agent/self-model échoue), `.disclaimer`, `.framing` |
| `GET /metrics` | les 11 clés de `METRIC_DEFS` + `tick`, `daylight`, `is_sleeping`, `agency`, `boredom` (via `refreshDeep(state…)` qui lit `state.metrics`), `effective_learning_rate` |
| `GET /agent/consciousness` | `conscious_moment{ignited,contents,awareness_level,valence,phi_proxy,arousal(non lu),…}`, `workspace` (RÉDUIT, cf. 2.3), `attention_schema{aware_of,awareness_level,stability,attributed_self}`, `metacognition{meta_confidence,perception_reliability,prediction_reliability,higher_order_report}`, `integration{phi_proxy}`, `phi_causal`, `hierarchy`, `wandering`, `task` (metrics merge) + LES 23 SOUS-OBJETS optionnels (traceish pour tous les panneaux : `sleep.dream`, `imagination.best_first_action`, `learning.q_values/.effective_lr/.td_*`, `concept`, `personality`, `self_opacity`, `individuation`, `recurrence`, `reality_monitor`, `interoception`, `temporality`, `inner_speech`, `phi_ar`, `language`, `planning`, `semantic_memory`) |
| `GET /agent/workspace` | TOUT `WorkspaceState` : `ignited threshold effective_threshold ignition_score broadcast_strength winner_source winner_content arousal competition[{source,content,activation}]` (`precision`, `vector`, `winner_strength`, `dominance`, `facilitation_applied` non lus) |
| `GET /agent/stream?limit=48` | liste de `ConsciousMoment` : `tick ignited awareness_level phi_proxy contents dominant_source` |
| `GET /agent/self-model` | `identity age_ticks energy confidence mood coherence relational_self{reflected_appraisal,n_observers,social_presence} active_goals[] narrative` |
| `GET /agent/memory?limit=20` | liste : `action target_id tick importance summary result_energy_delta prediction_error` (rendue inversée) |
| `GET /agent/introspection` | `perceive attend predict intend why remember self_state` |

**Sérialisés après le batch (mêmes générations `horizonGeneration`) :**

| Appel | Déclencheur | Champs consommés |
|---|---|---|
| `GET /agent/memory/graph?limit=60&edges=3` | si le tick a avancé de ≥ 20 (throttle l.1174-1177) ; FORCÉ (`true`) au bootstrap, Step, Reset, checkpoint-load, society-apply | `nodes[{id,tick,action,importance,summary,valence}]`, `edges[{source,target,similarity}]` |
| `GET /society/language` | chaque cycle | `convergence`, `n_meanings_named`, `distinct_modal_words`, `dictionary{<meaning>: {modal_word, agreement, speakers, variants{<word>: n}}}` |
| `GET /metrics/history?limit=200` | chaque cycle (lab chart) + change du select | `series.rows[]` : `agent_id` + la métrique sélectionnée. Champs réels de la série : `tick agent_id energy prediction_error phi_proxy awareness_level ignition arousal agency boredom effective_learning_rate meta_confidence` — **le select propose des métriques absentes de la série** (`phi_ar`, `presence`, `temporal_surprise`, `reality_accuracy`, `language_success`, `vocabulary_size`) → courbe plate à 0 (num() sur undefined) |
| `GET /society` | chaque cycle | `world{grid_size, agents[{id,x,y}], objects[{kind,x,y}]}`, `relations.edges[{from,to,trust,affect}]` ; clic canvas : re-fetch et hit-test `agents[{id,x,y}]` |

**À la demande :**

| Appel | Déclencheur | Consommé |
|---|---|---|
| `GET /config` | bootstrap (`applyDeepDefaults`, diff avant POST) | `config{...}` (108 clés) |
| `GET /agent/coverage` | bootstrap + chaque toggle + profil Phase 7 | `items[{theory,mechanism,module,flag,active}]`, `active_count`, `total` |
| `GET /checkpoint/list` | bootstrap + après save/load/delete | `checkpoints[{name,tick,n_agents,saved_at,bytes,compatible}]` (`schema` non lu) |
| `GET /agent/memory/search?q=<enc>&limit=8` | submit du form recherche | `results[{action,tick,importance,similarity,summary}]` |
| `window.open` | boutons export | `GET /export/analysis` (JSON brut), `GET /export.csv`, `GET /export.json` (Content-Disposition attachment) |

**POST (tous via `postJSON`, body JSON) :**

| POST | Body envoyé | Réponse consommée |
|---|---|---|
| `/tick` | `{}` | **CycleTrace entier** → `applyTrace` (la source la plus riche ; `trace.tick` guard) |
| `/run` | `{tps}` | rien (déclenche polling) |
| `/pause` | `{}` | rien |
| `/reset` | **le patch des 9 sliders** (`currentConfigPatch()`) | rien (puis `resetHorizonClientState` + refresh) |
| `/config` | patch (sliders : LES 9 à chaque change, débounce 120 ms ; toggles : `{flag: bool}` unitaire ; profil P7 : 8 flags ; fast-train : `{persist_memory:false, trace_logging:false}`) | `out.state.world \|\| out.world \|\| out.snapshot` (redraw), `out.config.ignition_threshold` |
| `/agent/goal` | `{goal}` | `SelfModelState` complet (re-render) |
| `/world/stimulus` | `{kind, x, y, intensity}` (x/y omis pour le form intervention si vides) | `response.object` (loggé) |
| `/agent/inject` | `{content, activation, precision, ttl}` | réponse entière loggée |
| `/agent/attend` | `{target_id, strength, ttl}` | réponse entière loggée |
| `/agent/perturb` | `{type, magnitude}` (`type ∈ shock\|surprise\|soothe` côté UI) | `effect` ; **`effect.applied === false` ⇒ erreur UI** (l.1813-1815) |
| `/agent/ask` | `{question, intent?}` | `intent answer grounding disclaimer` (loggés) |
| `/society/config` | `{n_agents}` | `state.running` (forme society, PAS legacy) |
| `/scenario/run` | JSON libre du textarea (schéma `Scenario`) | `res.series.rows.length`, `res.summary` |
| `/battery/{name}` | `{seed, ticks}` — mirror/false_memory/calibration `{42,12}`, relational_self `{7,40}`, masking/blink `{42,3}`, priming `{42,2}`, reality_monitor `{42,40}`, language_genesis `{42,120}` | `score` (f3), `interpretation`, `disclaimer` (verbatim dans `#lab-disclaimer`) |
| `/train` | `{ticks}` | `ticks_run` |
| `/checkpoint/save` | `{name}` | `name`, `tick` |
| `/checkpoint/load` | `{name}` | `tick` (+ reset client + refresh forcé) |
| `/checkpoint/delete` | `{name}` | rien |
| `/agent/narrate` | `{}` | `narration`, `model` |
| `/agent/audit` | `{}` | `score`, `interpretation`, `detail.verdicts[{faithful,question,note}]` |
| `/agent/report-card` | `{}` | `report_card` |
| `/agent/converse` | `{question, history:[-6:]}` (`{role,content}` ; max 6 côté serveur) | `answer` |
| `/agent/biography` | `{}` | `biography` |
| `/agent/cross-examine` | `{}` | `case_for case_against verdict grounding{coverage, probes{k:v}}` |
| `/agent/inner-voice` | `{}` | `entered utterance note` |

### 2.2 Endpoints backend NON utilisés par l'UI (routes.py)

- `GET /trace?limit=` (l.457) — traces JSONL brutes (liste de CycleTrace dicts, 41 clés top-level).
- `GET /export/traces` (l.513) — export filtré/projeté (`from_tick to_tick ignited_only fields format|fmt limit`, formats `jsonl|json|csv`).
- `WS /ws/society` (l.862) — push du state society toutes les ~250 ms (candidat évident pour remplacer le polling dans la refonte).
- `POST /society/tick`, `POST /society/run`, `POST /society/pause` (l.570-588).
- `GET /society/relations` (l.612) — l'UI lit les relations via `GET /society` à la place.
- `GET /society/messages` (l.629) — `{messages:[Message]}`.
- `GET /society/agent/{id}/consciousness|self-model|introspection|workspace` (l.643-667) — **la vue
  par-agent existe côté API mais l'UI actuelle n'affiche QUE l'agent 0** (la sélection society ne
  change que la teinte du canvas).
- `GET /` → redirect `/ui/index.html` (main.py l.77-80).

### 2.3 Formes réelles des payloads (sondées en live, GET, tick 14, flags OFF)

**`GET /state`** — forme legacy solo (routes.py `_society_state_legacy`, l.114-139) :
```
world: {grid_size:12, tick:14, agent:{x:5,y:4,energy:118.5}, objects:[11×WorldObject],
        season?: float (si world_dynamics), task?: TaskState (si tasks)}   ← PAS de clé "radius"
metrics: {…41 champs Metrics…}          running: false
introspection_summary: str              self_model: {…SelfModelState…}
working_memory: [{percept:{object_id,kind,dx,dy,distance,danger,novelty,utility,energy_value},
                  saliency, created_tick, last_seen_tick}]
working_memory_load: 0.6
phi_proxy/free_energy/awareness_level/ignition/broadcast_strength/winner_source/arousal (doublons plats)
disclaimer, disclaimer_en, framing: str
```

**`GET /metrics`** — `Metrics` (schemas/models.py l.366-407), 41 champs plats + `emotional_state{5}`.
Ex : `tick:14, phi_proxy:0.5389, arousal:0.7729, ignition:true, daylight:1.0, is_sleeping:false,
phi_causal:0.0, vfe:0.0, wandering_occupancy:0.0, task_progress:0.0, …` (les champs de phase
inactive valent 0/false, jamais absents).

**`GET /agent/consciousness`** (core/agent.py l.1701-1755) :
```
conscious_moment: {tick, contents, ignited, dominant_source, awareness_level, valence,
                   phi_proxy, free_energy, arousal, summary}
attention_schema: {aware_of, awareness_level, stability, attributed_self}
metacognition: {meta_confidence, perception_reliability, prediction_reliability,
                error_monitor, higher_order_report}
integration: {phi_proxy, n_elements, partition, differentiation, integration}
workspace: {ignited, winner_source, winner_content, broadcast_strength, threshold,
            ignition_score, effective_threshold, winner_strength, dominance, arousal}
            ← RÉDUIT : PAS de competition[], broadcast_vector, facilitation_applied
circadian…task: null (23 sous-objets, null tant que flag OFF ou aucun cycle)
disclaimer, framing
```
Avant le premier tick, TOUTES les clés (y compris `conscious_moment`) sont `null` (l.1756+).

**`GET /agent/workspace`** — `WorkspaceState` complet :
```
ignited:true, threshold:0.3, winner_source:"perception", winner_content:"perception: object 8 (hazard)",
broadcast_strength:0.5732, competition:[6×{source,content,activation,precision,vector[4]}],
broadcast_vector:[4], ignition_score:0.5732, winner_strength:0.9309, dominance:0.4877,
arousal:0.7729, effective_threshold:0.3367, facilitation_applied:0.0
```

**`GET /agent/stream?limit=3`** — `list[ConsciousMoment]` (mêmes 10 champs que conscious_moment).

**`GET /agent/self-model`** — `SelfModelState` : `identity:"Aurora-fn-01", age_ticks, energy,
confidence, mood, preferences{9 actions}, active_goals:[], capability_beliefs{9}, coherence,
narrative, relational_self:null` (objet `{reflected_appraisal, social_presence, regard_consistency,
n_observers, note}` si social_mirror + observateurs).

**`GET /agent/memory?limit=3`** — `list[MemoryRecord]` : `id tick perception[Percept]
action target_id result_energy_delta prediction_error emotion{5} importance summary`.

**`GET /agent/coverage`** — `items:[33×{theory, mechanism, module, flag:str|null, active:bool}],
active_count:6, total:33, note, disclaimer, framing`.

**`GET /society`** — forme society (≠ legacy !) :
```
world: {grid_size, tick, agents:[{id,x,y,energy,last_action,affect,valence}],
        objects:[…], messages:[…], season?, task?}
running:false, n_agents:1
agents: {"0": {metrics:{41}, self_model:{…}, social:{agent_id,others[],affiliation_pressure,
                last_emitted,received_count} | null}}
relations: {nodes:[0], edges:[]}         disclaimer, framing
```

**`GET /society/language`** — `dictionary:{} (vide) | {<meaning>:{modal_word,agreement,speakers,
variants{word:n}}}, convergence:null|float, n_meanings_named:0, distinct_modal_words:0, note,
disclaimer`.

**`GET /society/relations`** — `{nodes:[int], edges:[{from,to,trust,affect}]}` (edges vide en mono).

**`GET /society/messages`** — `{messages:[Message{id,tick_emitted,sender_id,content,vector,x,y,
radius,ttl,word?}]}`.

**`GET /metrics/history?limit=5`** — `series:{fields:[12] = tick agent_id energy prediction_error
phi_proxy awareness_level ignition arousal agency boredom effective_learning_rate meta_confidence,
rows:[{…}]}, disclaimer` (`ignition` sérialisé en int 0/1).

**`GET /config`** — `{config:{108 champs SimConfig}}` (dump complet, cf. §6).

**`GET /checkpoint/list`** — `{checkpoints:[{name:"789", tick:39568, n_agents:1,
saved_at:"2026-07-10 12:06:59", bytes:952192757, schema:2, compatible:true}]}`.

**`GET /agent/memory/graph?limit=10&edges=2`** — `{nodes:[{id,tick,action,importance,summary,
valence}], edges:[{source,target,similarity}], disclaimer}` (ids d'arêtes = ids de nœuds).

**`GET /agent/memory/search?q=rest&limit=2`** — `{query, results:[{similarity, …MemoryRecord}],
disclaimer}`.

**`GET /export/analysis`** — `{n_traces, tick_range:[2], ignition_rate, mean/max_phi_proxy,
mean_phi_ar, n_phi_ar_computations, max_phi_ar, mean/max_phi_causal, n_phi_causal_computations,
mean_prediction_error, error_curve:[{tick_start,mean}], action_histogram{action:n},
sleep_fraction, wandering_occupancy_last, disclaimer}`.

**`GET /agent/introspection`** — `{tick, disclaimer, perceive, attend, predict, intend, why,
remember, self_state}` (que des strings).

---

## 3. Contrats pytest UI (liste de survie de la refonte)

Ces tests lisent les SOURCES (`index.html`, `app.js` sans commentaires, `styles.css`) — pas le DOM
rendu. Toute réécriture doit satisfaire les littéraux suivants À L'OCTET PRÈS.

### 3.1 `tests/test_interaction_ui.py`

**`test_observatory_exposes_all_five_intervention_modalities` (l.46-84)**
- id `experimental-interventions` présent.
- L'ensemble des `data-endpoint` du HTML ⊇ `{/agent/ask, /world/stimulus, /agent/inject, /agent/attend, /agent/perturb}`.
- Ids présents : `intervention-tabs`, `intervention-ask-question`, `intervention-stimulus-kind`,
  `intervention-inject-content`, `intervention-attend-target`, `intervention-perturb-type`, `interaction-log`.
- `#interaction-log` : `aria-live ∈ {polite, assertive}` ET possède `aria-label`.
- Chacun des 5 endpoints apparaît littéralement dans app.js décommenté.
- Définitions par MOT-CLÉ `function` : `function activateIntervention`, `function submitIntervention`,
  `function appendInterventionLog` (une arrow function casse le test).
- styles.css contient `.panel-interventions`, `.intervention-tabs`, `.interaction-log`.

**`test_world_canvas_posts_pointer_and_keyboard_stimuli` (l.87-105)**
- `#world-canvas` : `tabindex="0"` et `aria-describedby="world-interaction-help"` (valeur EXACTE).
- Ids : `world-stimulus-kind`, `world-stimulus-intensity`, `world-interaction-status` ; ce dernier
  a `aria-live ∈ {polite, assertive}`.
- `function mapWorldPointToGrid`, `function postWorldStimulusAt`, `function drawWorldCursor`.
- Regex : `worldCanvas.addEventListener("click"` et `…("keydown"` (le nom de variable
  **`worldCanvas`** est donc contractuel).
- Littéraux JS : `postJSON("world/stimulus"`, `ArrowLeft`, `ArrowRight`, `ev.key === "Enter"`.
- styles.css : `.world-interaction-tools`, `#world-canvas:focus-visible`.

**`test_interventions_are_serialized_correlated_and_cache_busted` (l.108-122)**
- `html.count("?v=7.3") == 2` — EXACTEMENT deux occurrences (styles.css + app.js ; en ajouter une
  3e ou bumper une seule des deux casse le test).
- Littéraux JS : `let interventionPending = false`, `function setInterventionBusy`,
  `if (interventionPending) return`, `correlationId`, `response.effect.applied === false`.
- Littéraux CSS À L'OCTET : `#world-interaction-status { color: var(--ink-soft); }` ·
  `.interaction-sequence { color: var(--ink-soft);` · `body.is-scrolled .tps-field { display: none; }` ·
  `body.is-scrolled .transport-buttons`.

**`test_manual_step_is_strictly_serialized_and_generation_safe` (l.124-155)**
- Ancres de découpage : `$("#btn-step").addEventListener` … `$("#btn-start").addEventListener`
  (les DEUX chaînes littérales, `$` compris, sont contractuelles).
- `let stepInFlight = false` déclaré AVANT le listener ; `if (stepInFlight) return` dedans.
- Ordre dans le listener : `stepInFlight = true` ET `stepButton.disabled = true` avant le premier
  `await ` ; bloc `finally {` contenant `stepInFlight = false` et `stepButton.disabled = false`.
- Ordre complet : `const generation = horizonGeneration` < 1er await <
  `generation !== horizonGeneration` < `applyTrace(trace)` < `await refreshAll()` < 2e guard <
  `await refreshMemoryGraph(true)` < `finally`.

### 3.2 `tests/test_phase7_ui.py`

**`test_horizon_observatory_is_wired_end_to_end` (l.87-351)**
- Ids requis : `horizon-readouts ignition-chart ignition-chart-summary horizon-stream memory-graph
  memory-graph-nodes memory-graph-edges memory-graph-summary memory-search-input horizon-task`.
- `data-flag` requis (les 8 P7) : `phi_causal_enabled hierarchy_enabled planning_enabled
  vector_memory_enabled td_learning_enabled mind_wandering_enabled world_dynamics_enabled tasks_enabled`.
- `href` contient exactement `styles.css?v=7.3` ; `src` contient exactement `app.js?v=7.3` ;
  au moins un `href` commence par `data:image/svg+xml` (favicon inline, zéro 404).
- `#ignition-chart` : `aria-describedby` ⊇ `ignition-chart-summary` ; `#memory-graph` :
  `aria-describedby` ⊇ `{memory-graph-summary, memory-graph-nodes, memory-graph-edges}` ;
  les éléments summary existent ; `#memory-graph` a `tabindex="0"`.
- `#memory-graph-nodes` : `aria-label == "Indexed autobiographical memory nodes"` (EXACT) ;
  `#memory-graph-edges` : `aria-label == "Autobiographical memory similarity edges"` (EXACT).
- `#horizon-task` et `#ignition-chart-summary` ne doivent PAS avoir `aria-live`.
- `SETTINGS_DEFAULTS` : littéral `(const|let|var) SETTINGS_DEFAULTS = { … };` dont le corps
  contient `flag: true` pour chacun des 8 flags P7 (objet construit dynamiquement = échec).
- Fonctions définies par `function NAME(` ET appelées ailleurs : `renderHorizon`,
  `renderIgnitionDynamics`, `renderHorizonStream`, `refreshMemoryGraph`, `drawMemoryGraph`.
- Littéraux d'endpoints EXACTS dans le JS :
  `` agent/memory/search?q=${encodeURIComponent(query)}&limit=8 `` et `agent/memory/graph?limit=60&edges=3`.
- `Math.random` INTERDIT dans app.js.
- Marqueurs requis : `refreshInFlight`, `refreshQueued`, `horizonGeneration`, `resetHorizonClientState`.
- Throttle du graphe : la regex `requestedTick - lastMemoryGraphTick < 20` doit matcher ; AUCUN
  `% 20` dans le JS.
- Corps de `async function refreshAll(` (jusqu'à `function applyTrace(`) contient
  `refreshMemoryGraph(false)` ; corps d'`applyTrace` (jusqu'à `function startPolling(`) ne contient
  AUCUN `refreshMemoryGraph(`.
- `async function bootstrap(` … `void bootstrap()` : ordre `await applyDeepDefaults()` <
  `await refreshAll()` < `await refreshMemoryGraph(true)`.
- Corps de `async function performRefreshAll(` : `const generation = horizonGeneration` <
  `if (generation !== horizonGeneration) return` < premier `drawWorld(` ; et `const incomingTick` <
  `if (incomingTick < lastTick) return` < `drawWorld(`.
- Corps de `async function refreshMemoryGraph(` (jusqu'à `function drawGraphEdge(`) : ≥ 2
  occurrences de `generation !== horizonGeneration`, la première AVANT `memoryGraphCache =` ;
  contient `memoryGraphRequest === request`.
- Listener Reset (`$("#btn-reset").addEventListener` → `$("#goal-form")`) contient
  `resetHorizonClientState()`.
- Bloc checkpoint-load (`loadBtn.addEventListener("click"` → `const delBtn`) contient
  `resetHorizonClientState()` ET `refreshMemoryGraph(true)`.
- Listener Step : `const generation = horizonGeneration` AVANT `try {` ; regex stricte
  `const trace = await postJSON("tick"); if (generation !== horizonGeneration) return; applyTrace(trace);`
  (espaces libres) ; puis `await refreshAll()` puis `await refreshMemoryGraph(true)`.
- Bloc society-apply (`document.getElementById("btn-society-apply")?.addEventListener` →
  `document.getElementById("society-canvas")?.addEventListener`) : ordre
  `await postJSON("society/config"` < `resetHorizonClientState()` < `await refreshAll()` <
  `await refreshMemoryGraph(true)`.
- Exports : les templates `` `${API}/export.csv` `` et `` `${API}/export.json` `` littéraux.
- Marqueurs clavier : `addEventListener("keydown"`, `"ArrowRight"`, `"ArrowLeft"`, `"Home"`, `"End"`.
- Tooltip mesuré : `tooltip.offsetHeight` ET `tooltip.offsetWidth` présents.
- styles.css (commentaires retirés) : sélecteurs EN DÉBUT DE LIGNE suivis de `{` pour
  `.panel-horizon`, `.horizon-readouts`, `.memory-graph-shell`, `.sr-only`.

**`test_phase7_is_documented_and_future_extensions_are_closed` (l.354-370)** — contrat README (pas
UI) : heading `## Phase 7`, littéraux `33 mechanisms`, `GET /agent/memory/search`,
`GET /export/traces`, `Every extension above is now delivered`.

Aucun autre fichier de `tests/` ne référence `ui/` (grep exhaustif).

---

## 4. localStorage

| Clé | Forme | Écriture | Lecture |
|---|---|---|---|
| `humanity.settings` | objet PLAT `{<clé SimConfig>: bool\|number}` — flags des toggles + valeurs des 9 sliders, fusionnés au fil de l'eau | `persistSetting(patch)` à chaque toggle (l.2218), chaque commit slider (l.2194), profil P7 (l.2232), fast-train (l.2494) ; `saveSettings(cfg)` au bootstrap (l.748) | `loadSettings()` au bootstrap uniquement |
| `cws-theme` | `"dark"` \| `"light"` | au clic sur `#btn-theme` (l.165) | à l'init (IIFE `initTheme`, l.158-160) → `data-theme` sur `<html>` |

Tous les accès sont enveloppés try/catch (mode privé ⇒ silencieusement défauts, jamais de throw).

**`SETTINGS_DEFAULTS` (l.686-706)** : 30 flags, TOUS `true` (littéral verrouillé par pytest pour
les 8 P7) — P2 (6) + P3 (4 : learning, concepts, meta_learning, personality) + satiation +
social_mirror + self_opacity + individuation + P5 (7) + P6 (1) + P7 (8). Les clés `persist_memory`
/ `trace_logging` n'y figurent PAS (elles n'entrent dans le storage que si l'utilisateur y touche).

**Migration `applyDeepDefaults` (l.734-751)** :
1. `cfg = { ...SETTINGS_DEFAULTS, ...(loadSettings() || {}) }` — un mécanisme nouvellement livré
   passe ON même pour un vieux storage, mais chaque choix utilisateur gagne.
2. `GET /config` → diff : seules les clés différentes du live sont POSTées (un simple reload ne
   reset plus rien et ne peut plus mettre en pause un run) ; si `GET /config` échoue → POST du
   set complet.
3. `saveSettings(cfg)` (ajoute les nouvelles clés au storage) puis `applyControlStates(cfg)`
   (reflète flags → checkboxes, valeurs → sliders + badge `.slider-val` ; ne touche QUE les clés
   présentes dans cfg).

---

## 5. États à gérer

### 5.1 LLM absent / en erreur
- **503** (`No LLM backend configured. Set OPENROUTER_API_KEY…`) sur : `POST /agent/narrate`,
  `/agent/audit`, `/agent/report-card`, `/agent/converse`, `/agent/biography`,
  `/agent/cross-examine`, `/agent/inner-voice`. **502** si le provider échoue (RuntimeError).
- L'UI dégrade en message inline : « LLM unavailable (set OPENROUTER_API_KEY in .env). »
  (narrate : « LLM narrator unavailable… » ; audit/report-card : constante `AUDIT_UNAVAIL`),
  cache les blocs de sortie, ré-active le bouton. Jamais de modal, jamais de retry.

### 5.2 503 « society busy » (gate d'exclusivité)
`_manager()` (routes.py l.59-68) renvoie **503 + Retry-After: 1** sur QUASI TOUS les endpoints
pendant un job exclusif (`/train`, checkpoint save/load, tout job LLM, `/agent/memory/search`,
`/agent/memory/graph`). Le poll actuel survit parce que chaque GET du batch a son `.catch(() => null)`
et chaque bloc sérialisé son try vide. Une refonte qui retire ces catchs gèlera l'UI pendant un
fast-train.

### 5.3 Société mono vs multi-agent
- `GET /state` garde TOUJOURS la forme solo (agent 0) — clé `agent` singulière, quel que soit
  `n_agents`.
- `GET /society` : `world.agents` pluriel (1..128 entrées), `relations.edges` vide en mono,
  `agents` dict indexé par id string.
- `POST /society/config` répond en forme SOCIETY (`world.agents`), PAS legacy ; l'UI n'y lit que
  `running`. C'est un RESET complet (mode:"reset") qui reprend le run s'il tournait.
- La sélection d'agent (clic canvas) ne change QUE la teinte du canvas + le libellé
  `#soc-selected` ; tous les panneaux restent l'agent 0 (`/society/agent/{id}/*` existe côté API
  mais n'est pas branché).
- `relational_self` n'apparaît sur le self-model qu'avec `social_mirror_enabled` ET des
  observateurs ; `social` (trace) n'existe qu'en société.

### 5.4 Sous-objets null par flag désactivé (mapping exact)
`GET /agent/consciousness` et `CycleTrace` partagent les mêmes clés optionnelles → `null` :

| Flag OFF | Sous-objet null | Panneau dégradé |
|---|---|---|
| `circadian_enabled` | `circadian` (mais `metrics.daylight` reste, défaut 1.0) | cadran plein |
| `sleep_enabled` (+`dream_enabled` pour le texte) | `sleep` / `sleep.dream` | « awake », dream vide |
| `imagination_enabled` | `imagination` | plan « — » |
| `curiosity_enabled` | `curiosity` (metrics.boredom=0) | meter 0 |
| `agency_enabled` | `agency` (metrics.agency=0) | meter 0 |
| `learning_enabled` | `learning` | q-bars conservent leurs placeholders (PAS vidées) |
| `td_learning_enabled` | `learning.td_context` null → cellule TD(λ) dormante |
| `concepts_enabled` | `concept` | « — » |
| `personality_enabled` | `personality` | « nascent » + traits « — » |
| `self_opacity_enabled` | `self_opacity` | « — », width 0 |
| `individuation_enabled` | `individuation` | 5 meters « — » |
| `recurrence_enabled` | `recurrence` | « — » |
| `reality_monitor_enabled` | `reality_monitor` | « — » |
| `intero_inference_enabled` | `interoception` | presence « — » |
| `temporality_enabled` | `temporality` | « — » |
| `inner_speech_enabled` | `inner_speech` | « — » |
| `phi_ar_enabled` | `phi_ar` | « — » |
| `language_drive_enabled` | `language` | tous « — », chips vides |
| `phi_causal_enabled` | `phi_causal` | readout « dormant » |
| `hierarchy_enabled` | `hierarchy` | « dormant » |
| `planning_enabled` | `planning` | « dormant » |
| `vector_memory_enabled` | `semantic_memory` (la recherche/graph mémoire marchent QUAND MÊME — index synchronisé à la demande, routes.py l.469-510) | « dormant » |
| `mind_wandering_enabled` | `wandering` | « dormant » |
| `tasks_enabled` | `task` (+ clé `task` du world snapshot) | « World task system dormant. » |
| `world_dynamics_enabled` | clé `season` du world snapshot absente | (non affiché) |
| `priming_enabled` | `workspace.facilitation_applied` = 0.0 | (non affiché) |
| `meta_learning_enabled` | (rien de null : `metrics.effective_learning_rate` figé 0.2) | |

**Avant le tout premier tick d'un process** : `/agent/consciousness` renvoie TOUTES les clés
null (y compris `conscious_moment`) — le hero doit tolérer `cm = {}`.

### 5.5 États vides
- Mémoire : `GET /agent/memory` → `[]` → « No memory recorded. » ; graph `nodes:[]` →
  canvas placeholder + « No indexed memories yet. » + sélection annoncée impossible.
- Recherche : `results:[]` → « No stored episode matched this query. » ; erreur → statut
  `.is-error` « Memory search unavailable… ».
- Checkpoints : `checkpoints:[]` → « No checkpoints saved. » ; `compatible:false` → Load désactivé.
- Langage : `dictionary:{}` + `convergence:null` → « No conventions yet — let the society talk. »,
  convergence « — » ; vocab vide → chip « no invented words yet ».
- Stream vide → piste vide + aria « No dominant-source moments recorded yet. » ; ignition-chart
  sans échantillon → texte in-canvas « No access-dynamics samples yet ».
- Working memory vide → « Working memory empty. » ; goals vides → chip « no goal » ;
  introspection null → « No report. » ; coverage vide → « Coverage unavailable. » ;
  relations vides → « No relations yet. » ; q_values vides → « No learned values yet. ».

### 5.6 Erreurs HTTP et leurs formes
- **409 config structurelle** (`POST /config`) : `{detail: {fields: [...], instruction: "Use POST /reset for structural changes."}}` — l'UI actuelle l'affale en `setStatus("error", "Config error")` générique (opportunité de refonte, mais le contrat minimal est : ne pas crasher, signaler).
- **422** : `POST /config|/reset|/society/config` (ValidationError pydantic, detail string) et
  toute validation FastAPI (handler custom NaN-safe, main.py l.50-58, detail = liste d'erreurs).
- **404** : `POST /checkpoint/load` (FileNotFoundError), `POST /checkpoint/delete` (inconnu),
  `POST /battery/<inconnu>`, `GET /society/agent/{id}/*` (agent absent).
- **400** : `POST /checkpoint/load` sur checkpoint corrompu (`InvalidCheckpointError`).
- `api()` : réponse non-JSON ⇒ retourne `null` (les renderers doivent tolérer null).
- Échec du batch de poll ⇒ `setStatus("error", "API error")` ; erreurs d'intervention ⇒ entrée
  `is-error` dans le log + `setStatus("error", "Intervention error")`.

### 5.7 Garde-fous de concurrence côté client (à préserver tels quels — pytest les lit)
`refreshInFlight`/`refreshQueued`/`refreshDrainPromise` (poll mono-file, re-drain),
`stepInFlight` (+ bouton désactivé), `interventionPending` + `worldStimulusPending`
(interventions strictement sérialisées, log corrélé `#NNN`), `horizonGeneration` incrémenté par
`resetHorizonClientState()` (appelé sur Reset, checkpoint-load, society-apply) — CHAQUE réponse
async re-vérifie sa génération avant d'écrire ; `lastTick` (drop des snapshots plus vieux) ;
`memoryGraphRequest` (single-flight du graphe) + throttle 20 ticks ; `configDebounce` 120 ms.

---

## 6. Config SimConfig (schemas/models.py l.797-959)

**Champs STRUCTURELS — `RESET_REQUIRED_FIELDS` (core/society.py l.22-32) : `POST /config` → 409 ;
il faut `POST /reset` (ou `POST /society/config`)** :
`grid_size, n_objects, random_seed, n_agents, stream_length, metrics_history_max, phi_ar_window,
phi_causal_window, n_concepts`.
Tout le reste est hot-apply (avec migrations transactionnelles préparées/committées/rollbackées
pour `vector_memory_enabled`, `tasks_enabled`, `persist_memory`, et les goals standing
d'`individuation_enabled`/`language_drive_enabled` — core/society.py l.229-470).

Table complète (type · défaut · bornes ; **S** = structurel) :

**Monde** : `grid_size` int 12 [1,256] **S** · `n_objects` int 10 [0,10000] **S** ·
`world_noise` float 0.1 [0,1] · `perception_radius` int 3 [0,256] · `random_seed` int 42 [0,2³²-1] **S**.
**Agent** : `initial_energy` float 100.0 (0,1e6].
**Attention/WM** : `attention_capacity` int 4 [1,256] · `working_memory_capacity` int 5 [1,256] ·
`working_memory_decay` int 4 [1,100000].
**Drives** : `curiosity`/`caution`/`energy_drive`/`coherence_drive` float 1.0 [0,100].
**Apprentissage** : `learning_rate` float 0.2 [0,1].
**Mémoire** : `memory_importance_threshold` float 0.25 [0,1] · `memory_retrieval_k` int 3 [1,10000].
**Conscience v2** : `ignition_threshold` float 0.30 [0,1] · `workspace_temp` float 0.5 (0,100] ·
`precision_weight` float 1.0 [0,100] · `epistemic_weight` float 1.0 [0,100] ·
`pragmatic_weight` float 1.0 [0,100] · `stream_length` int 20 [1,100000] **S**.
**Ignition v2.1** : `arousal_baseline` float 0.45 [0,1] · `arousal_gain` float 1.0 [0,100] ·
`competition_sharpness` float 3.0 [0,100] · `ignition_maintenance` float 0.12 [0,1].
**Société v3** : `n_agents` int 1 [1,128] **S** · `comm_radius` int 4 [0,256] ·
`message_ttl` int 2 [0,100000] · `contagion_rate` float 0.15 [0,1] · `affiliation_drive` float 1.0 [0,100].
**Phase 2 (défaut OFF)** : `circadian_enabled` F · `circadian_period` int 50 [1,100000] ·
`night_threshold` 0.3 [0,1] · `sleep_enabled` F · `dream_enabled` F ·
`sleep_fatigue_threshold` 0.8 [0,1] · `wake_fatigue_threshold` 0.35 [0,1] ·
`max_sleep_ticks` int 30 [1,100000] · `replay_boost` 1.3 [1,100] ·
`consolidation_prune_threshold` 0.0 [0,1] · `imagination_enabled` F · `imagination_horizon` int 3 [1,6] ·
`curiosity_enabled` F · `curiosity_window` int 8 [2,100000] · `agency_enabled` F.
**Phase 3 (OFF)** : `learning_enabled` F · `value_learning_rate` 0.2 [0,1] ·
`value_learning_weight` 0.5 [0,100] · `concepts_enabled` F · `n_concepts` int 6 [1,32] **S** ·
`concept_lr` 0.2 [0,1] · `meta_learning_enabled` F · `meta_lr_min` 0.05 [0,1] · `meta_lr_max` 0.6 [0,1] ·
`personality_enabled` F · `personality_drift` 0.05 [0,1].
**Phase 4** : `metrics_history_max` int 1000 [1,1e6] **S**.
**Performance** : `persist_memory` **T** · `trace_logging` **T**.
**Équilibre** : `satiation_enabled` F · `satiation_weight` 3.0 [0,100] · `explore_reward_weight` 0.5 [0,100].
**Miroir social / self** : `social_mirror_enabled` F · `social_mirror_weight` 0.3 [0,100] ·
`self_opacity_enabled` F · `individuation_enabled` F · `individuation_drive` 1.0 [0,100].
**Phase 5 (OFF)** : `recurrence_enabled` F · `recurrence_passes` int 3 [1,8] · `recurrence_gain` 0.5 [0,1] ·
`reality_monitor_enabled` F · `intero_inference_enabled` F · `intero_lr` 0.25 [0,1] ·
`temporality_enabled` F · `retention_horizon` int 5 [2,20] · `protention_window` int 6 [2,32] ·
`inner_speech_enabled` F · `inner_speech_gain` 0.6 [0,1] · `phi_ar_enabled` F ·
`phi_ar_window` int 32 [8,256] **S** · `phi_ar_every` int 8 [1,64] · `priming_enabled` F ·
`priming_decay` 0.5 [0,1] · `priming_gain` 0.35 [0,2].
**Phase 6 (OFF)** : `language_drive_enabled` F · `language_drive` 1.0 [0,100].
**Phase 7 (OFF)** : `phi_causal_enabled` F · `phi_causal_nodes` int 5 [2,8] ·
`phi_causal_window` int 96 [16,512] **S** · `phi_causal_every` int 16 [1,128] ·
`hierarchy_enabled` F · `hierarchy_lr` 0.15 [0,1] · `hierarchy_gain` 0.3 [0,1] ·
`planning_enabled` F · `planning_horizon` int 3 [2,4] · `planning_discount` 0.7 [0,1] ·
`vector_memory_enabled` F · `semantic_weight` 0.6 [0,1] · `td_learning_enabled` F ·
`td_lambda` 0.8 [0,1] · `td_discount` 0.9 [0,1] · `mind_wandering_enabled` F ·
`wandering_gain` 0.6 [0,2] · `world_dynamics_enabled` F · `season_period` int 200 [10,100000] ·
`regrow_rate` 0.02 [0,1] · `tasks_enabled` F.
Validateur croisé : `n_agents ≤ grid_size²`. `ConfigPatch` = mêmes 108 champs, tous optionnels,
`extra="forbid"`, re-validé contre un SimConfig fusionné (l.1075-1079).

Note refonte : les 9 sliders exposent des plages PLUS ÉTROITES que SimConfig (ex. `curiosity`
slider [0,3] vs modèle [0,100]) — c'est un choix UX, pas une borne API.

---

## 7. Risques de régression — top 15 pièges concrets

1. **Cache-buster `?v=7.3`** : exactement 2 occurrences dans index.html, valeurs `styles.css?v=7.3`
   et `app.js?v=7.3` littérales (test_interaction_ui.py:112, test_phase7_ui.py:107-110). Tout bump
   doit changer LES DEUX ET les deux tests — ajouter un 3e asset versionné `?v=7.3` casse le count.
2. **`#threshold-line` couplé à la géométrie CSS** : `app.js:465` calcule
   `calc(134px + (100% - 134px - 54px) * frac)` d'après la grille
   `.coalition { grid-template-columns: 124px 1fr 44px; gap: 10px; }` (styles.css:541).
   Changer une largeur de colonne des coalitions sans
   retoucher ces constantes place le marqueur de seuil au mauvais endroit — silencieusement.
3. **Rebuild sélectif de `#coalitions`** : `app.js:415` supprime uniquement `.coalition` et suppose
   que `#threshold-line` reste enfant direct. Une structure DOM différente (wrapper, grid)
   double le marqueur ou le détruit.
4. **Workspace réduit dans `/agent/consciousness`** (core/agent.py:1715-1728) : pas de
   `competition[]`. Le fallback `renderWorkspace(consciousness.workspace)` (app.js:1601) donne un
   panneau de coalitions VIDE. Une refonte qui « simplifie » en ne gardant que
   `/agent/consciousness` perd les barres de compétition pendant les runs.
5. **Hit-test canvas = attributs width/height, pas la taille CSS** : world (app.js:206-216),
   society (2318-2323), memory-graph (2106-2108) remappent clientX/Y via `getBoundingClientRect`
   et les dimensions INTERNES (560×560, 720×440…). Un canvas letterboxé (`object-fit`,
   aspect-ratio différent) fausse tous les clics ; `canvas._placedNodes` doit rester en
   coordonnées internes.
6. **Noms de fonctions et littéraux JS verrouillés par pytest** : `function renderHorizon(` etc.
   (les 11 de §3) + `worldCanvas.addEventListener("click")`, `$("#btn-step").addEventListener`,
   `postJSON("world/stimulus"`, les 2 URLs mémoire EXACTES, `` `${API}/export.csv` ``… Passer aux
   arrow functions, renommer `worldCanvas`, ou reformater ces URLs (`?limit=60&edges=3` →
   params dynamiques) casse la suite sans toucher au comportement.
7. **Ordres d'exécution parsés dans la SOURCE** (test_phase7_ui.py:220-324,
   test_interaction_ui.py:124-155) : bootstrap (defaults → refreshAll → graph), Step (generation →
   await tick → guard → applyTrace → refreshAll → graph forcé), performRefreshAll (guards avant
   `drawWorld(`), refreshMemoryGraph (2 guards, avant l'écriture du cache), society-apply,
   checkpoint-load, Reset. Même un déplacement de bloc sémantiquement équivalent casse ces tests
   s'il change l'ordre textuel des ancres.
8. **`Math.random` interdit + layout déterministe** (test_phase7_ui.py:196-197) : la spirale à
   angle d'or (app.js:1303, 1329-1340) est le layout contractuel. Une lib de force-directed layout
   ou un `Math.random()` de jitter est un échec pytest ET une trahison du principe « instrument
   déterministe ».
9. **Contrats ARIA exacts** : `aria-describedby` en chaîne multiple sur `#memory-graph`
   (`memory-graph-summary memory-graph-nodes memory-graph-edges`), aria-labels À L'OCTET sur les
   deux `<ol>` sr-only, `tabindex="0"` sur les 2 canvas interactifs, `aria-live` OBLIGATOIRE sur
   `interaction-log`/`world-interaction-status`/`memory-graph-selection`/`memory-search-results`
   et INTERDIT sur `horizon-task`/`ignition-chart-summary` (anti-spam de lecteur d'écran,
   test_phase7_ui.py:146-149). Les `aria-label` des canvas sont RÉÉCRITS par le JS à chaque frame.
10. **Littéraux CSS à l'octet** (test_interaction_ui.py:118-121, test_phase7_ui.py:345-349) :
    `#world-interaction-status { color: var(--ink-soft); }` (une seule ligne, cet espacement),
    `.interaction-sequence { color: var(--ink-soft);`, `body.is-scrolled .tps-field { display: none; }`,
    `body.is-scrolled .transport-buttons`, et les 4 sélecteurs début-de-ligne
    `.panel-horizon/.horizon-readouts/.memory-graph-shell/.sr-only`. Un reformatage Prettier de la
    CSS (espaces, retours ligne) casse ces asserts.
11. **Les 12 variables CSS des canvas + re-teinte au toggle thème** : `cssVar()` lit
    `--accent --accent-bright --pos --neg --cool --curio --line --ink --ink-faint --ink-soft
    --bg-inset --mono` sur `documentElement`. Le handler thème (app.js:161-169) ne redessine QUE
    world, ignition-chart et memory-graph — tout nouveau canvas doit s'y inscrire (le cadran
    circadien, lab-chart et society attendent le poll suivant : quirk existant). Les couleurs du
    horizon-stream (`SOURCE_COLORS`) sont des hex en dur qui ignorent le thème.
12. **`SETTINGS_DEFAULTS` littéral + migration localStorage** : le test regex exige un objet
    littéral `SETTINGS_DEFAULTS = { flag: true, … };`. Générer ces défauts dynamiquement, renommer
    `humanity.settings`, ou perdre la fusion defaults←saved (app.js:734-751) reset les préférences
    utilisateur ou ré-éteint les mécanismes nouvellement livrés.
13. **Sémantique du poll** : ne JAMAIS paralléliser les blocs sérialisés (graph → language →
    lab-chart → society) ni retirer les `.catch(() => null)` du batch — le 503 « busy » pendant
    /train, les 404 transitoires et les résets de génération sont absorbés par cette structure.
    `POLL_MS=350`, throttle graphe 20 ticks (regex verrouillée), débounce config 120 ms,
    cap log 40, `STREAM_MAX=48`, `HIST=60`, `IGNITION_HISTORY_MAX=120` sont le budget perf réel.
14. **Formes de réponse hétérogènes** : `POST /society/config` répond en forme society
    (`world.agents[]`) là où `POST /config` répond `{state:{world:{agent:{}}}}` legacy et
    `POST /reset` répond le state legacy À PLAT (`world` à la racine). Le code actuel les
    distingue (`out.state ? out.state.world : (out.world || out.snapshot)`, app.js:2195) ; une
    couche fetch unifiée naïve mélangera les deux mondes. De même `drawWorld` lit `snapshot.radius`
    qui N'EXISTE PAS dans le /state legacy (toujours 3 — quirk à connaître avant de « corriger »).
15. **Écrasements runtime des textes statiques** : `#framing-text` (GET /state.framing),
    `#footer-disclaimer` (.disclaimer), `#lab-disclaimer` (r.disclaimer de CHAQUE batterie,
    verbatim — exigence d'honnêteté du projet), `aria-label` des canvas, `#world-meta`. Une
    refonte qui traduit/reformule ces conteneurs verra son texte remplacé au premier poll ; le
    contenu honnête vient du serveur (`THEORY_FRAMING_EN`, core/constants.py:57).

Mentions honorables : le double-guard `stepInFlight`+`disabled` avant tout await (pytest) ;
`checkpoint.compatible === false` ⇒ bouton Load désactivé + tag « legacy » ; l'historique converse
tronqué à 6 tours (aligné sur `max_length=6` serveur, routes.py:315) ; `input-tps` fallback 4 ;
`window.open` (popup-blockers) pour les 3 exports ; `API = ".."` suppose l'UI servie sous `/ui/`
(main.py:74) — un déplacement du mount casse TOUS les fetchs.
