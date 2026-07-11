# 03 — Architecture de l'information

**Refonte du GUI de Humanity — d'une page verticale unique vers une application instrumentale multi-vues.**
Livrable de l'architecte d'information. Sources analysées : `ui/index.html` (21 panneaux `<section class="panel">` + masthead + colophon), `ui/app.js` (interactions, polling 350 ms, persistance `localStorage`), `README.md` (contrat d'honnêteté, distinction à trois niveaux), instrument vivant sur `http://127.0.0.1:8123/ui/index.html` (GET seulement).

**Langue de l'UI : anglais** (l'UI actuelle est en anglais ; tous les libellés cibles ci-dessous restent en anglais). Ce document est rédigé en français.

---

## 0. Principes directeurs

1. **Rien ne disparaît.** Chaque panneau, contrôle, readout, note d'honnêteté et attribut de source de l'UI actuelle reçoit une **maison canonique** dans une des 8 vues (ou dans le shell). La divulgation progressive remplace la suppression : ce qui encombre est replié, jamais retiré.
2. **Maison canonique + échos.** Un élément vit à un seul endroit canonique ; il peut être **échoé** ailleurs sous forme dérivée (miniature, KPI, chip) qui renvoie toujours vers la maison canonique d'un clic.
3. **Observer là où l'on intervient.** Les sondes causales sont invocables depuis n'importe quelle vue (dock transversal) pour fermer la boucle perturbation → lecture, mais leur établi complet et leur journal archivé vivent au Laboratory.
4. **La frontière scientifique est une signature, pas un bandeau publicitaire.** Formulation courte permanente (une ligne, partout), panneau développé à un clic (charte épistémique), chips `GET /endpoint` conservées dans chaque en-tête de panneau, disclaimers serveur rendus verbatim. Voir §6.
5. **Rangs de priorité visuelle** utilisés partout ci-dessous :
   - **hero** — domine la vue, lisible en premier ;
   - **primaire** — visible sans interaction, au-dessus du pli sur desktop ;
   - **secondaire** — visible mais dense/compact, peut passer sous le pli ;
   - **divulgation** — replié par défaut (accordéon, popover, onglet, dock), un geste pour ouvrir.
6. **Deux surfaces transversales** (overlays, pas des routes) : le **Probe dock** (établi d'interventions, raccourci `p`) et la **Epistemic charter** (panneau frontière développé, raccourci `!` et lien permanent du boundary strip).

---

## 1. Inventaire → affectation

Inventaire exhaustif de `ui/index.html`, dans l'ordre du document. Colonnes : élément actuel (ids principaux) → vue cible, position dans la vue, rang.

### 1.1 Masthead (header actuel) → Shell (toutes les vues)

| Élément actuel (ids) | Vue cible | Position | Rang |
|---|---|---|---|
| Marque `brand-mark` (SVG anneaux) + `h1 Humanity` + `brand-sub` | Shell — topbar | Gauche : marque + nom ; le sous-titre complet migre dans la charte épistémique, la topbar garde « Humanity — Instrument » | primaire (shell) |
| Pill de statut `#status-pill` / `#status-label` (Running / Paused / error) | Shell — topbar | Zone statut live, à côté de l'identité ; conserve les 3 états `pill-running/idle/error` | primaire (shell) |
| Compteur de tick (actuellement dans `#world-meta` « tick N ») | Shell — topbar | Chip mono « t 1284 » à côté du statut, alimentée par le poll `/state` | primaire (shell) |
| Agent sélectionné (actuellement `#soc-selected` « viewing agent 0 ») | Shell — topbar | Sélecteur « agent 0 ▾ » (visible dès `n_agents > 1`) ; synchronisé avec le clic canvas société | primaire (shell) |
| `#btn-theme` (toggle light/dark, clé `cws-theme`) | Shell — topbar | Extrémité droite | secondaire (shell) |
| Transport `#btn-step` (`POST /tick`), `#btn-start` (`POST /run`), `#btn-pause` (`POST /pause`), `#btn-reset` (`POST /reset`) | Shell — topbar | Cluster transport centre-droit : Run/Pause (toggle), Step, Reset (Reset avec confirmation) ; les tooltips endpoint deviennent des sous-libellés visibles dans le popover | primaire (shell) |
| `#input-tps` (rate, 0.5–30 tps) | Shell — topbar | Popover « speed » accolé à Run/Pause (stepper + presets 1/4/10 tps) | secondaire (shell) |
| `#framing-text` (THEORY_FRAMING_EN, réécrit par `GET /state.framing`) | Epistemic charter (overlay) + écho Overview | Corps de la charte, texte serveur verbatim ; écho : carte « About this instrument » sur Overview | divulgation (short form permanente via boundary strip, §6) |
| `div.grain` (décor) | Shell | Décor global conservé | — |

### 1.2 Conscious moment (`panel-hero`, src `GET /agent/consciousness`) → #/overview + #/workspace

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Lampe + état `#ignition-lamp`, `#ignition-state` (« Global access » / « Subliminal »), `#ignition-sub` (qualification verbatim « global access — conscious (content broadcast) » / « present but subliminal (weakly conscious) ») | **#/overview** (canonique) | Cœur de l'**Ignition Aperture** (§2.1) : anneau central, état au centre, qualification en dessous — libellés actuels conservés au mot près | hero |
| Gate d'ignition `#ig-fill`, `#ig-thresh`, `#ig-score`, `#ig-eff` (score vs seuil effectif, src `GET /agent/workspace`) | **#/overview** (aperture = jauge annulaire score/seuil) ; écho linéaire dans #/workspace au-dessus des coalitions | Le marqueur de seuil est gravé sur l'anneau ; readout mono `0.412 / 0.300` sous l'état | hero |
| Contenu du moment `#moment-contents` (blockquote, animation flash) | **#/overview** sous l'aperture ; écho hero dans #/workspace | « Dominant content » — citation pleine largeur, flash conservé à chaque changement | hero |
| Stats hero : Awareness `#aw-fill/#aw-val`, Valence `#val-fill/#val-val` (bipolaire), Φ proxy `#phi-fill/#phi-val` | **#/workspace** (canonique, rail du moment) ; échos = 3 des 6 KPI d'Overview | Rangée de meters sous la citation | primaire |
| Stream of consciousness `#stream-track` (src `GET /agent/stream`, 48 barres) | **#/workspace** section « Stream » | Bande horizontale sous la compétition ; tooltips titre conservés (tick, arousal, Φ, contenu) | primaire |

### 1.3 Global workspace (`panel-workspace`, src `GET /agent/workspace · GWT`) → #/workspace

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| `#ws-broadcast` (broadcast strength), `#ws-winner` (source · contenu, état `subliminal`) | #/workspace | Ligne de tête de la section « Competition » | primaire |
| Rangée arousal `#arousal-fill`, `#arousal-baseline-mark`, `#arousal-val` (src `GET /state.arousal`, baseline = slider config) | #/workspace | Sous la ligne de tête ; le marqueur de baseline reste lié au slider `arousal_baseline` de #/settings | primaire |
| Barres de coalitions `#coalitions` + ligne de seuil `#threshold-line` / `#threshold-val` (winner/dominant states) | #/workspace | **Cœur de la vue** — pleine largeur, tri décroissant conservé | hero |
| Note explicative `.micro` (seuil effectif, ignition + broadcast) | #/workspace | Divulgation « How ignition works » sous les barres (ouverte au premier lancement, repliée ensuite) | divulgation |

### 1.4 Indicators (`panel-metrics`, `#metric-grid`, src `GET /metrics · /agent/consciousness`) → #/laboratory (canonique) + échos

Les 11 cellules sparkline (`phi_proxy`, `arousal`, `free_energy`, `prediction_error`, `self_coherence`, `meta_confidence`, `energy`, `phi_causal`, `vfe`, `wandering_occupancy`, `task_progress`) :

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Grille complète 11 cellules + sparklines (historique client 60 pts) | **#/laboratory** section « Live indicators » | Bandeau supérieur du Laboratory, toujours vivant pendant un run | primaire |
| Écho : 6 KPI prioritaires (Awareness, Φ proxy, Valence, Arousal, Free energy, Energy) avec tendance sparkline | #/overview | Rangée KPI sous l'aperture (§2.1) | primaire (overview) |
| Écho : `phi_causal`, `vfe`, `wandering_occupancy`, `task_progress` | #/mind — section Horizon | Repris dans les cellules horizon correspondantes (déjà le cas côté données) | secondaire |
| Écho : `self_coherence`, `meta_confidence` | #/mind (self) et #/workspace (HOT) | Valeurs déjà présentes dans ces panneaux ; la sparkline reste au Laboratory | secondaire |

### 1.5 Deep consciousness (`panel-deep`, Phase 2, src `/tick · /state`) → #/mind

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Cadran circadien `#circadian-dial` (canvas 120×120) | #/mind — section « Rhythms & drives (Phase 2) » | Première cellule de la grille | secondaire |
| Sommeil `#sleep-state` (awake/asleep) + rêve `#dream-line` | #/mind — Rhythms & drives | Cellule 2 ; la ligne de rêve s'étend en pleine largeur quand elle est non vide | secondaire |
| Agency `#agency-fill/#agency-val` ; Boredom/curiosity `#boredom-fill/#boredom-val` | #/mind — Rhythms & drives | Cellules 3–4 (meters) | secondaire |
| Imagined plan `#imagined-plan` (trace.imagination.best_first_action) | #/mind — Rhythms & drives | Cellule large en bas de la grille | secondaire |

### 1.6 Learning & personality (`panel-learning`, Phase 3, src `/tick · /metrics`) → #/learning-language

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Valeurs d'action apprises `#q-bars` (barres ± triées) | #/learning-language — section « Learned policy » | Colonne gauche, dominante | hero |
| Concept dominant `#concept-state` (#id · match · n_concepts) | #/learning-language — « Concepts » | Cellule à droite de la politique | primaire |
| Taux d'apprentissage effectif `#elr-val` | #/learning-language — « Learned policy » | Chip sous les q-bars | secondaire |
| Personnalité `#personality-label` + `#personality-traits` (openness / caution / novelty seeking) | #/learning-language — section « Personality » | Carte pleine largeur sous politique+concepts | primaire |

### 1.7 The asymptote (`panel-asymptote`, Phase 5) → #/mind

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Presence (interoceptive fit) `#presence-fill/#presence-val` | #/mind — section « The asymptote (Phase 5) » | Grille asymptote, cellule 1 | primaire |
| Temporal thickness `#specious-val` + protention `#protention-line` | #/mind — asymptote | Cellule 2 | primaire |
| Φ_AR (Barrett–Seth) `#phi-ar-val` + MIB `#phi-ar-mib` | #/mind — asymptote | Cellule 3 | primaire |
| Recurrent perception `#recurrence-state` (n refined / passes / stable) | #/mind — asymptote | Cellule 4 | primaire |
| Reality monitoring (PRM) `#reality-verdict` (+ MISATTRIBUTED) + `#reality-report` | #/mind — asymptote | Cellule large 5 | primaire |
| Inner speech `#inner-speech-line` + compteur de ré-entrées `#reentry-count` | #/mind — asymptote | Cellule large 6 | primaire |
| Bouton `#btn-inner-voice` (« Inner voice (LLM) », `POST /agent/inner-voice`) + `#inner-voice-status` | #/mind — asymptote, cellule inner speech | Action locale, badge **LLM** (§6.3) ; reste collée au readout qu'elle alimente (l'énoncé est mis en compétition au tick suivant) | secondaire |
| Note d'honnêteté `.micro` (« Every readout above is a level-2 variable… the agent is not conscious ») | #/mind — asymptote | Pied de section, texte visible (non replié : c'est une note de frontière) | secondaire |

### 1.8 The horizon (`panel-horizon`, Phase 7) → #/mind (+ échos Laboratory/Settings)

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Lede `.horizon-lede` (« The remaining functional frontier… ») | #/mind — section « The horizon (Phase 7) » | Sous-titre de section | secondaire |
| `#horizon-readouts` — 6 cellules : Causal Φ, Predictive level, Policy horizon, Semantic memory, TD(λ), Default mode (états `is-live`/`is-dormant` + notes « dormant — … ») | #/mind — horizon | Grille 3×2 ; les notes dormant/live conservées telles quelles | primaire |
| `#horizon-task` (tâche monde : kind · progress · description · completed) | #/mind — horizon | Ligne pleine largeur sous la grille ; écho : chip « task » sur #/world | secondaire |
| `#btn-horizon-profile` (« Activate all Phase 7 », patch des 8 flags) | #/mind — horizon (en-tête de section) + écho #/settings groupe Phase 7 | Action de profil ; même handler, même persistance | secondaire |
| `#btn-export-analysis` (`GET /export/analysis`) | **#/laboratory — Exports** (canonique) ; écho en-tête horizon #/mind | Rangée d'exports | secondaire |

### 1.9 Access dynamics (`panel-dynamics`) → #/workspace (+ écho Overview)

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| `#ignition-chart` (canvas 120 échantillons score vs seuil, points d'ignition) + `#ignition-chart-summary` (aria/texte) | #/workspace — section « Access dynamics » | Sous la compétition, pleine largeur | primaire |
| `#horizon-stream` (timeline des sources dominantes, couleur par source, saturation = ignition) + note `.horizon-stream-note` | **#/workspace** — Access dynamics (canonique) ; **écho compact sur #/overview** (« Winning sources », cliquable → #/workspace) | Bande sous le chart ; légende des couleurs de source ajoutée en divulgation | primaire (workspace) / secondaire (overview) |

### 1.10 Autobiographical topology (`panel-memory-graph`, src `GET /agent/memory/graph`) → #/memory

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Formulaire de recherche `#memory-search-form/-input` + bouton (src `GET /agent/memory/search`) | #/memory — barre « Search stored episodes » | En tête de vue, pleine largeur | primaire |
| Résultats `#memory-search-results` (aria-live) | #/memory | Liste sous la barre, remplace l'état vide | primaire |
| Graphe `#memory-graph` (canvas spirale dorée, tabindex, tooltip `#memory-graph-tooltip`, sélection clavier) | #/memory — « Autobiographical topology » | **Hero de la vue** | hero |
| Accessibilité : `#memory-graph-summary`, listes sr-only `#memory-graph-nodes/-edges`, annonce `#memory-graph-selection` | #/memory | Inchangés, attachés au graphe | primaire (a11y) |

### 1.11 Laboratory (`panel-lab`, Phase 4) → #/laboratory

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Sélecteur `#lab-metric` (11 métriques : energy, agency, phi_proxy, phi_ar, presence, temporal_surprise, reality_accuracy, language_success, vocabulary_size, prediction_error, arousal) + `#lab-chart` (multi-agents, src `GET /metrics/history`) | #/laboratory — section « Time series » | Sous les Live indicators ; le choix de métrique persiste (localStorage) | primaire |
| Exports `#btn-export-csv` (`GET /export.csv`), `#btn-export-json` (`GET /export.json`) + écho `#btn-export-analysis` | #/laboratory — « Exports & data » | Rangée de boutons regroupée avec Checkpoints | secondaire |
| Scénario `#lab-scenario` (textarea JSON), `#btn-scenario-run` (`POST /scenario/run`), `#lab-scenario-summary` | #/laboratory — « Scenario runner » | Éditeur repliable (placeholder JSON conservé comme gabarit) | secondaire → divulgation de l'éditeur |
| Batteries fonctionnelles : `#btn-mirror`, `#btn-false-memory`, `#btn-calibration`, `#btn-relational-self` + rangée Phase 5 `#btn-masking`, `#btn-blink`, `#btn-priming`, `#btn-reality-monitor`, `#btn-language-genesis` (`POST /battery/*`) | #/laboratory — « Functional batteries » | Grille de 9 sondes, groupées « Self & memory » / « Access psychophysics » ; tooltips actuels conservés en sous-libellés | primaire |
| Résultat `#lab-battery-result` + disclaimer `#lab-disclaimer` (⚠ réécrit verbatim par `r.disclaimer` serveur) | #/laboratory — Functional batteries | Zone de résultat sous la grille ; le disclaimer serveur reste rendu tel quel (§6.3) | primaire |
| Sondes LLM : `#btn-audit` (grounding audit), `#btn-report-card`, `#llmprobe-status`, `#audit-result` (verdicts FAITHFUL/CONFAB), `#report-card-out`, note `.report-note` | #/laboratory — « LLM probes — not consciousness tests » | Sous les batteries, badge **LLM** ; résultats en divulgation (hidden → visible au retour) | secondaire |
| Language organ (évaluatif) : `#btn-biography` (`POST /agent/biography`), `#btn-cross-examine` (`POST /agent/cross-examine`), `#organ-status`, `#biography-out`, `#crossx-out` (case for / rebuttal / verdict / grounding), note `.report-note` | #/laboratory — « LLM probes », sous-groupe « Renderings of the record » | Ces deux sondes lisent tout le run + batteries : ce sont des instruments d'évaluation, pas de l'observation live — d'où le Laboratory et non #/mind | secondaire |
| Fast training `#train-ticks`, `#btn-fast-train` (`POST /train`, coupe persist_memory/trace_logging et le reflète dans Settings), `#train-result`, note `.micro` | #/laboratory — « Fast training » | Carte compacte ; l'avertissement I/O reste visible | secondaire |
| Theory coverage `#coverage-count`, `#coverage-list` (src `GET /agent/coverage`, ●/○ par mécanisme) | #/laboratory — « Theory coverage » (canonique) ; lien depuis la charte épistémique | Liste dense, rafraîchie à chaque changement de flag | secondaire |
| Checkpoints `#ckpt-name`, `#btn-ckpt-save` (`POST /checkpoint/save`), `#ckpt-status`, `#ckpt-list` (Load/Delete par ligne, badge legacy) | #/laboratory — « Checkpoints » | Avec Exports & data ; liste on-demand (jamais pollée) conservée | primaire |

### 1.12 World (`panel-world`, src `GET /state`) → #/world

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| `#world-meta` (tick · GET /state) | Shell topbar (tick) + en-tête de vue #/world (chip src) | — | secondaire |
| `#world-canvas` (560×560, clic = injecter, flèches + Enter au clavier, curseur de cellule) | #/world | **Hero gauche** de la vue ; interactions pointeur + clavier inchangées | hero |
| Outils stimulus `#world-stimulus-kind` (food/hazard/tool/curio), `#world-stimulus-intensity`, `#world-interaction-status` (aria-live) | #/world — barre « Place » au-dessus du canvas | Ces contrôles alimentent le même `POST /world/stimulus` que la sonde Stimulus : le statut renvoie vers le ledger | primaire |
| Aide `#world-interaction-help` (clavier) | #/world | Divulgation « ? » à côté de la barre Place (texte intégral conservé) | divulgation |
| Légende `.legend` (Agent/Food/Hazard/Tool/Curiosity) | #/world | Sous le canvas, compacte | secondaire |

### 1.13 Society (`panel-society`, src `GET /society`) → #/world

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| `#input-nagents` (1–8) + `#btn-society-apply` (`POST /society/config`, reset client) | #/world — en-tête de la moitié « Society » ; écho dans #/settings groupe Society | Avertissement inline : « Apply resets the run » | primaire |
| `#soc-selected` (« viewing agent N ») | Shell topbar (sélecteur d'agent) + surlignage canvas | — | primaire (shell) |
| `#society-canvas` (agents numérotés, clic = sélectionner) | #/world | **Hero droit** (côte à côte avec le monde sur desktop) | hero |
| `#society-relations` (arêtes trust · affect) | #/world — « Relations » | Liste sous le canvas société | primaire |
| Écho « messages » : flux des derniers échanges de nommage (dérivé de `lang.utterance`/`lang.heard` et `GET /society/language`) | #/world — « Exchanges » (écho, canonique en #/learning-language) | Petit feed sous Relations ; chaque item renvoie vers #/learning-language | secondaire |

### 1.14 Experimental interventions (`panel-interventions`, `#experimental-interventions`) → Probe dock (transversal) + #/laboratory (canonique)

**Décision motivée — voir §1.17.**

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Lede `.intervention-lede` (« Perturb one mechanism at a time… ») | Probe dock (en-tête) + section Laboratory | Une phrase, toujours visible dans le dock | secondaire |
| Onglets `#intervention-tabs` : 01 Ask `POST /agent/ask` · 02 Stimulus `POST /world/stimulus` · 03 Inject `POST /agent/inject` · 04 Attend `POST /agent/attend` · 05 Perturb `POST /agent/perturb` (rôles ARIA tab, flèches clavier) | Probe dock + #/laboratory/probes | Mêmes 5 onglets, mêmes endpoints affichés en `code` ; l'onglet par défaut dépend de la vue d'origine (§1.17) | primaire |
| Formulaire Ask `#intervention-ask-question` (textarea), `#intervention-ask-intent` (8 intents) | Probe dock / Laboratory | Panneau d'onglet 01 | primaire |
| Formulaire Stimulus `#intervention-stimulus-kind/-intensity/-x/-y` | Probe dock / Laboratory | Panneau 02 ; bouton « Pick a cell » renvoie au canvas de #/world | primaire |
| Formulaire Inject `#intervention-inject-content/-activation/-precision/-ttl` | Probe dock / Laboratory | Panneau 03 | primaire |
| Formulaire Attend `#intervention-attend-target/-strength/-ttl` | Probe dock / Laboratory | Panneau 04 | primaire |
| Formulaire Perturb `#intervention-perturb-type` (shock/surprise/soothe) `/-magnitude` | Probe dock / Laboratory | Panneau 05 | primaire |
| Causal ledger `#interaction-log` (aria-live, entrées corrélées #NNN request/result/error, cap 40) + `#btn-clear-interactions` | **#/laboratory — « Causal probes & ledger »** (journal complet, canonique) ; les 6 dernières entrées visibles dans le dock | Une seule source de vérité, deux fenêtres dessus | primaire (lab) / secondaire (dock) |
| Disclaimer `.intervention-disclaimer` (« …causal sensitivity inside this model only ») | Probe dock (pied) + Laboratory | Toujours visible sous les formulaires | secondaire |
| État busy (`aria-busy`, désactivation croisée des boutons pendant une sonde) | Dock + Laboratory + barre Place de #/world | Comportement conservé globalement (une intervention à la fois) | — |

### 1.15 The invention of language (`panel-language`, Phase 6, src `/society/language`) → #/learning-language

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| Convergence lexicale `#lang-convergence` + `#lang-distinct` (meanings named · distinct words) | #/learning-language — section « The invention of language (Phase 6) » | **Stat de tête** de la moitié langage | hero |
| Communicative success `#lang-success-fill/-val` ; Goal deficit `#lang-deficit-fill/-val` | #/learning-language — langage | Deux meters sous la convergence | primaire |
| Dernier échange `#lang-exchange` (spoke/heard → inferred) | #/learning-language — langage ; écho feed « Exchanges » sur #/world | Ligne vivante | primaire |
| Vocabulaire inventé (agent sélectionné) `#lang-vocab` (chips “word” = meaning) | #/learning-language — langage | Rangée de chips | primaire |
| Dictionnaire émergent `#lang-dictionary` (modal word, agreement, speakers, variantes) | #/learning-language — langage | Table/rows, la plus grande zone de la section | primaire |
| Note d'honnêteté `.micro` (« …measurable convention formation — NOT understanding… The agents are not conscious. ») | #/learning-language | Pied de section, visible | secondaire |

### 1.16 AST, HOT, Introspection, Self-model, mémoires, Settings, footer

| Élément | Vue cible | Position | Rang |
|---|---|---|---|
| **AST** (`panel-ast`) : `#ast-aware` (aware of, opacité graduée), `#ast-stab-fill/-val` (stabilité), `#ast-attributed` (consciousness claim) | **#/workspace** — colonne « Attention schema (AST) » | À droite de la compétition (desktop) ; le claim `attributed_self` en voix de rapport | primaire |
| **Metacognition** (`panel-hot`) : jauges `#g-meta/#meta-conf-val`, `#g-perc/#perc-rel-val`, `#g-pred/#pred-rel-val` + rapport `#hot-report` | **#/workspace** — colonne « Metacognition (HOT) » sous l'AST | Les 3 demi-jauges + higher-order report | primaire |
| **Self-opacity** (`#self-opacity` : `#opacity-fill/-val`, `#opacity-report`) — actuellement dans le panneau HOT | **#/mind** — section « Self-opacity » (à côté d'Individuation) | Déplacé avec justification : c'est une lecture du *self* (ce qui échappe à son accès/contrôle), consommée en lisant le portrait de l'agent ; le mécanisme HOT reste crédité par la chip src | primaire |
| **Introspective report** (`panel-introspect`, src `GET /agent/introspection`) : note (« Text generated from internal variables… not a lived experience »), `#introspection` (7 champs perceive/attend/predict/intend/why/remember/self_state) | **#/mind** — colonne « Introspective report » | Rapport mécanique (déterministe) affiché en liste ; la note de provenance reste en tête | primaire |
| Narration LLM : `#btn-narrate` (`POST /agent/narrate`), `#narrate-status`, `#narrate-output`, `#narrate-model` (provenance) | #/mind — Introspective report, rangée d'action en pied | Badge **LLM** ; la ligne `#narrate-model` (« Generated from internal variables by <model> — text, not lived experience ») reste obligatoire sous chaque sortie | secondaire |
| Dialogue : `#converse-log` (tours interviewer / « agent (LLM rendering) »), `#converse-form/-input`, `#btn-converse` (`POST /agent/converse`, historique 6 tours), note de grounding | **#/mind** — section « Dialogue with the agent » sous le rapport introspectif (voir §1.18) | Fil de conversation + champ « Ask the agent anything… » ; badge **LLM** permanent dans l'en-tête | primaire |
| **Self-model** (`panel-self`, src `GET /agent/self-model`) : `#self-model` (identity, age, energy, confidence, mood, coherence, ligne Social mirror) | **#/mind** — carte « Self-model » en tête de vue | Portrait kv ; hero de la vue avec Individuation | hero |
| « Becoming someone » : `#indiv-fill/-val` + sous-meters `#indiv-coh/-dis/-con/-agy-*` + `#indiv-report` | #/mind — « Individuation » accolée au Self-model | Index + 4 composantes | primaire |
| Buts : `#self-goals` (chips), `#goal-form/#goal-input` (`POST /agent/goal`), narrative `#self-narrative` | #/mind — Self-model, pied de carte | « Set a functional goal… » conservé tel quel | primaire |
| **Working memory** (`panel-wm`, src `/state · wm_load`) : `#wm-load-fill/-val`, `#working-memory` (items percept + saliency) | **#/memory** — tiers « Working memory (now) » ; écho : chip « WM 60% » dans le rail de #/workspace | La vue Memory raconte la hiérarchie : tenue → épisodique → topologie | primaire |
| **Recent memories** (`panel-mem`, src `GET /agent/memory?limit=20`) : `#recent-memories` (action, tick, importance, ΔE, err) | **#/memory** — tiers « Recent episodes » | Liste médiane entre WM et graphe | primaire |
| **Settings** (`panel-config`, src `POST /config`) : 9 sliders `#config-sliders` (ignition_threshold, arousal_baseline, precision_weight, epistemic_weight, curiosity, caution, working_memory_capacity, initial_energy, world_noise) | **#/settings** — groupe « Core dynamics » | Sliders avec badge de valeur, application immédiate + persistance `humanity.settings` conservées | primaire |
| Toggles Phase 2 `#deep-toggles` (7 : circadian, sleep, dream, imagination, curiosity, agency, self-opacity) | #/settings — groupe « Deep consciousness (Phase 2) » | Grille de commutateurs, tooltips actuels → sous-libellés visibles | primaire |
| Toggles Phase 3 `#lp-toggles` (7 : learning, concepts, meta-learning, personality, satiation, social mirror, individuation) | #/settings — « Learning & personality (Phase 3) » | idem | primaire |
| Toggles Phase 5 `#asymptote-toggles` (7 : recurrence, reality monitor, interoception, temporality, inner speech, Φ_AR, priming) | #/settings — « The asymptote (Phase 5) » | idem | primaire |
| Toggle Phase 6 `#language-toggles` (language drive) | #/settings — « The invention of language (Phase 6) » | idem | primaire |
| Toggles Phase 7 `#horizon-toggles` (8 : causal Φ, predictive hierarchy, multi-step EFE, vector memory, TD(λ), mind-wandering, living world, world tasks) + écho du bouton « Activate all Phase 7 » | #/settings — « The horizon (Phase 7) » | idem, bouton de profil en tête de groupe | primaire |
| Persistance `#persistence-toggles` (persist memory, trace logging) + note « Any change applies POST /config immediately » | #/settings — « Persistence & I/O » | Fast training les manipule : lien croisé affiché | primaire |
| Écho Society (`n_agents`) | #/settings — groupe « Society » | Mirror du contrôle de #/world | secondaire |
| **Footer** `#footer-disclaimer` (rempli par `GET /state.disclaimer`) | Shell — **boundary strip** (§6.1) + texte intégral dans la charte | Une ligne permanente, cliquable | primaire (shell) |

### 1.17 Le cas « Experimental interventions » — placement raisonné

Le panneau actuel unit **cinq sondes causales** (Ask / Stimulus / Inject / Attend / Perturb) et un **journal corrélé** (causal ledger). Deux besoins entrent en tension : (a) une sonde ne vaut que si l'on **voit la réponse du mécanisme visé** — injecter une coalition en regardant les barres du workspace, perturber l'affect en regardant presence/valence ; (b) le journal est un **cahier de laboratoire** : il archive des paires requête/réponse déterministes et appartient à l'outillage scientifique.

Résolution — **un instrument, deux fenêtres** :

1. **Probe dock** (transversal) : un panneau latéral droit (drawer 380 px, bottom sheet sur mobile) invocable partout — bouton « Probe » dans la topbar + raccourci `p` + entrées de palette. Il contient les 5 onglets, les formulaires complets, l'état busy global et les **6 dernières entrées** du ledger. L'onglet par défaut est contextuel : depuis #/workspace → **Inject** ; #/world → **Stimulus** ; #/mind → **Perturb** ; #/memory → **Ask** (intent memory) ; ailleurs → dernier onglet utilisé. Le dock ne navigue jamais : la vue reste visible derrière, la boucle perturbation→lecture reste fermée.
2. **#/laboratory/probes** (canonique) : le même établi, à demeure, avec le **ledger complet** (40 entrées, Clear, corrélation #NNN) — car une intervention est une expérience, et son archive se consulte là où l'on analyse (batteries, séries, exports côte à côte).

Un seul état partagé (formulaires, log, busy) ; aucune duplication de vérité. Rang : primaire au Laboratory ; le dock est une divulgation globale.

### 1.18 Le cas « Introspection / dialogue LLM » — placement raisonné

Le panneau actuel mélange deux natures de texte : le **rapport introspectif mécanique** (`GET /agent/introspection` — 7 champs déterministes produits par AST/HOT) et les **rendus LLM** (Narrate, Dialogue/converse). Les séparer entre deux vues casserait le geste le plus utile de l'instrument : **comparer côte à côte ce que les mécanismes disent d'eux-mêmes et ce que le langage en rend**.

Résolution — les deux restent ensemble sur **#/mind**, colonne « Report & dialogue », dans cet ordre : (1) Introspective report (déterministe, note de provenance en tête) ; (2) Narrate (LLM, on-demand, ligne modèle obligatoire) ; (3) Dialogue with the agent (LLM, fil de conversation). La juxtaposition rend la différence de provenance **visible par construction** — chaque bloc LLM porte le badge LLM et sa note (« First person is a rendering convention — never evidence of experience »). Les sondes LLM **évaluatives** (Grounding audit, Report card, Biography, Cross-examination) vont au **#/laboratory** : elles jugent ou compilent le run entier (elles exécutent les batteries côté serveur), ce sont des mesures, pas de l'observation. La sonde **Ask** (déterministe, AskResponse avec grounding) reste dans le Probe dock/Laboratory, mais la section Dialogue de #/mind affiche un lien discret « Structured probe → Ask » qui ouvre le dock sur l'onglet 01.

### 1.19 Échos délibérés (dérivés, jamais des seconds originaux)

| Écho | Vue | Canonique |
|---|---|---|
| 6 KPI + sparklines | #/overview | #/laboratory Live indicators |
| Winning-sources timeline (compacte) | #/overview | #/workspace Access dynamics |
| Miniatures world + society (canvases réduits, live, cliquables) | #/overview | #/world |
| Chip « WM load » | #/workspace rail | #/memory Working memory |
| Chip « task » (progression tâche monde) | #/world | #/mind Horizon |
| Feed « Exchanges » | #/world | #/learning-language |
| Bouton « Activate all Phase 7 » | #/mind Horizon | #/settings Phase 7 |
| n_agents | #/settings Society | #/world Society |
| Export analysis | #/mind Horizon (en-tête) | #/laboratory Exports |
| 6 dernières entrées du causal ledger | Probe dock | #/laboratory/probes |

---

## 2. Composition par vue

Chaque vue précise : hiérarchie éditoriale (domine / respire / replié), état vide au premier lancement (tick 0, aucun run), et ce qui reste vivant pendant une simulation (poll 350 ms conservé ; seule la vue active et le shell rendent — les états client type historiques de sparklines continuent de s'accumuler en arrière-plan, comme aujourd'hui).

### 2.1 #/overview — le cockpit (compréhensible en < 5 s)

- **Domine — l'Ignition Aperture** (centre, ~40 % de la hauteur) : anneau (reprend la marque) dont le remplissage est `ignition_score` et dont une encoche gravée marque `effective_threshold` ; au centre la lampe et l'état (« Global access » / « Subliminal ») ; dessous, la qualification verbatim (« global access — conscious (content broadcast) » / « present but subliminal (weakly conscious) ») et le readout mono `score / threshold`. Sous l'aperture, le **dominant content** (`#moment-contents`, flash conservé).
- **Respire** : rangée de **6 KPI à tendance** (Awareness, Φ proxy, Valence, Arousal, Free energy, Energy) ; **Winning sources** (timeline compacte des sources dominantes) ; deux **miniatures live** World et Society (cliquables → #/world, l'agent sélectionné surligné).
- **Replié** : carte « About this instrument » (framing court + lien charte), légende des couleurs de source.
- **État vide** : anneau à 0, état « — », sous-titre « awaiting the stream », citation « The simulation has not produced a moment yet. », KPI « — », timeline vide avec le seul CTA de la vue : « Press Run — or Step once (`s`) ». Au tout premier lancement la charte épistémique s'ouvre par-dessus (§6.2).
- **Pendant un run** : tout est vivant ; l'aperture s'anime à chaque poll, la timeline défile, les miniatures bougent. Le transport (topbar) et le boundary strip ne bougent jamais.

### 2.2 #/workspace — le moment conscient et l'accès

- **Domine** : la **compétition de coalitions** (`#coalitions` + threshold line) pleine largeur, surmontée du bandeau moment (gate linéaire score/seuil, dominant content, broadcast + winner, arousal avec baseline).
- **Respire** : rangée hero-stats (Awareness / Valence / Φ proxy) ; **Stream of consciousness** (48 barres) ; **Access dynamics** (`#ignition-chart` + `#horizon-stream` + résumé textuel) ; colonne droite **AST** (aware of, stability, attributed self) puis **HOT** (3 jauges + higher-order report).
- **Replié** : « How ignition works » (micro-texte seuil effectif), légende des sources, chip WM load (écho → #/memory).
- **État vide** : barres absentes avec placeholder « empty perceptual field (no content available) », chart « No access-dynamics samples yet », stream vide ; bannière fine « Step the simulation to populate the workspace ».
- **Pendant un run** : compétition, gate, stream, chart et jauges se rafraîchissent à chaque poll ; le dock Probe (onglet Inject par défaut ici) peut rester ouvert à droite sans masquer la compétition.

### 2.3 #/world — le monde et la société

- **Domine** : les **deux canvases côte à côte** — World (curseur cellule, clic/clavier pour injecter) et Society (agents numérotés, clic = sélection, reflétée dans la topbar).
- **Respire** : barre « Place » (kind + intensity + statut aria-live) au-dessus du canvas World ; « Relations » (trust · affect) sous Society ; contrôle `agents` + Apply (avec l'avertissement reset) ; feed « Exchanges » (écho langage) ; chip task (écho horizon).
- **Replié** : aide clavier complète (`#world-interaction-help`), légende.
- **État vide** : grille dessinée, agent au centre, aucun objet ; statut « Cell cursor ready. » ; Relations « No relations yet. » ; Exchanges « No conventions yet — let the society talk. »
- **Pendant un run** : les deux canvases et Relations vivent ; la barre Place reste armée (statut passe à « Injecting… » pendant une sonde, verrou anti-concurrence conservé).

### 2.4 #/mind — le portrait intérieur

- **Domine** : la carte **Self-model** (identity, age, energy, confidence, mood, coherence, social mirror) accolée à **Individuation** (index + coherence/distinctiveness/continuity/agency + rapport).
- **Respire** : **Self-opacity** (fraction incontrôlée + rapport) ; **Rhythms & drives (Phase 2)** (cadran circadien, sommeil/rêve, agency, boredom, imagined plan) ; **The asymptote (Phase 5)** (presence, temporal thickness, Φ_AR, recurrence, PRM, inner speech + Inner voice LLM) ; **The horizon (Phase 7)** (6 readouts + task + Activate all) ; colonne **Report & dialogue** (introspection 7 champs → Narrate LLM → Dialogue LLM) ; buts actifs + goal form ; narrative.
- **Replié** : notes de mécanisme détaillées (tooltips actuels des cellules asymptote/horizon → popovers « ⓘ »), résultats Narrate tant qu'ils sont vides.
- **État vide** : self-model avec valeurs initiales ; individuation/asymptote/horizon à « — » avec leurs notes « dormant — … » conservées ; introspection « No report. » ; dialogue vide avec placeholder « Ask the agent anything… ».
- **Pendant un run** : tous les readouts vivent ; les actions LLM restent on-demand (jamais pollées) ; les notes d'honnêteté de section restent imprimées.

### 2.5 #/learning-language — apprendre, devenir, nommer

- **Domine** : à gauche **Learned policy** (q-bars triées ±), à droite la **convergence lexicale** (stat de tête de la moitié langage).
- **Respire** : Concepts (dominant, match, n) ; effective learning rate ; **Personality** (label + 3 traits) ; success & goal-deficit meters ; last exchange ; **vocabulaire inventé** (chips) ; **dictionnaire émergent** (agreement, speakers, variantes).
- **Replié** : variantes détaillées par convention (row-sub), note d'honnêteté Phase 6 visible en pied (non repliée).
- **État vide** : « No learned values yet. » ; personnalité « nascent » avec traits « — » ; « no invented words yet » ; « No conventions yet — let the society talk. » ; bannière fine « Language needs a society — set agents ≥ 2 in World » quand `n_agents < 2`.
- **Pendant un run** : q-bars, meters et dictionnaire se rafraîchissent (le dictionnaire via `GET /society/language` dans le même batch de poll).

### 2.6 #/laboratory — l'établi scientifique

- **Domine** : **Live indicators** (les 11 cellules sparkline) puis **Time series** (sélecteur 11 métriques + chart multi-agents `GET /metrics/history`).
- **Respire** : **Functional batteries** (9 sondes en deux groupes + zone résultat + disclaimer serveur verbatim) ; **Causal probes & ledger** (l'établi complet des 5 sondes + journal 40 entrées + Clear) ; **Checkpoints** (save/load/delete, badge legacy) ; **Exports & data** (CSV, JSON, analysis).
- **Replié** : **Scenario runner** (éditeur JSON repliable avec gabarit) ; **LLM probes** (audit, report card, biography, cross-examination — résultats en divulgation, badge LLM, statuts « ~10 s » conservés) ; **Fast training** (avec son avertissement I/O) ; **Theory coverage** (●/○, compteur actifs/total).
- **État vide** : indicateurs à « — », chart vide, ledger vide (« No interventions yet — open a probe (`p`) »), checkpoints « No checkpoints saved. », coverage chargée dès le boot (comme aujourd'hui).
- **Pendant un run** : indicateurs et time series vivent ; batteries/LLM/training restent des actions ponctuelles ; le ledger s'allonge à chaque sonde d'où qu'elle soit lancée.

### 2.7 #/memory — de l'instant à la vie

- **Domine** : le **graphe autobiographique** (canvas spirale, tooltip pointeur, sélection clavier, résumé textuel et listes sr-only).
- **Respire** : barre **Search stored episodes** (+ résultats sémantiques avec similarité) ; **Working memory (now)** (load + items saliency) ; **Recent episodes** (20 dernières, ΔE / err).
- **Replié** : rien de replié — la vue est une hiérarchie de lecture verticale : tenue → épisodes → topologie.
- **État vide** : « Working memory empty. » ; « No memory recorded. » ; « No indexed autobiographical memories » au centre du canvas ; recherche avec invite « Enter a search phrase to query stored episodes. »
- **Pendant un run** : WM et épisodes vivent au poll ; le graphe se réindexe tous les ~20 ticks (comportement actuel conservé) avec re-force après Step/Reset/Load.

### 2.8 #/settings — configuration groupée et recherchable

- **Domine** : champ **Filter settings…** en tête (filtre plein-texte sur libellés + descriptions + noms de flags), puis **Core dynamics** (9 sliders, valeur affichée).
- **Respire** : groupes **Phase 2 / Phase 3 / Phase 5 / Phase 6 / Phase 7** (32 toggles au total, descriptions issues des tooltips actuels rendues en sous-libellés visibles), **Persistence & I/O**, **Society** (écho n_agents).
- **Replié** : chaque groupe est un accordéon (tous ouverts par défaut sur desktop, tous fermés sur mobile sauf le premier) ; le filtre déplie automatiquement les groupes contenant une correspondance.
- **État vide** : n/a — les valeurs affichées sont la fusion `SETTINGS_DEFAULTS` + `humanity.settings` (localStorage), diffées contre `GET /config` au boot (comportement `applyDeepDefaults` conservé).
- **Pendant un run** : tout reste éditable ; « Any change applies POST /config immediately » reste imprimé en tête ; un changement de flag rafraîchit Theory coverage (lien croisé « Coverage → Laboratory »).

---

## 3. Navigation

### 3.1 Ordre, libellés, routes

L'UI reste **en anglais**. Ordre pensé du plus synthétique au plus technique, Settings en dernier :

| # | Libellé (sidebar) | Route | Sous-ancres (breadcrumb + scrollspy) |
|---|---|---|---|
| 1 | Overview | `#/overview` | — |
| 2 | Workspace | `#/workspace` | `/moment`, `/competition`, `/schema`, `/stream`, `/dynamics` |
| 3 | World | `#/world` | `/grid`, `/society`, `/relations`, `/exchanges` |
| 4 | Mind | `#/mind` | `/self`, `/opacity`, `/rhythms`, `/asymptote`, `/horizon`, `/report`, `/dialogue` |
| 5 | Learning & language | `#/learning-language` | `/policy`, `/concepts`, `/personality`, `/language`, `/dictionary` |
| 6 | Laboratory | `#/laboratory` | `/indicators`, `/timeseries`, `/batteries`, `/probes`, `/llm`, `/scenario`, `/training`, `/coverage`, `/checkpoints`, `/exports` |
| 7 | Memory | `#/memory` | `/working`, `/episodes`, `/search`, `/graph` |
| 8 | Settings | `#/settings` | `/core`, `/phase2`, `/phase3`, `/phase5`, `/phase6`, `/phase7`, `/persistence`, `/society` |

Route inconnue → redirection `#/overview` (jamais de 404 interne). Une sous-ancre (`#/laboratory/probes`) scrolle et surligne brièvement la section.

### 3.2 Icônes SVG (traits, pas d'emoji)

ViewBox 20×20, `stroke: currentColor`, épaisseur 1.5, caps ronds, aucun remplissage sauf mention :

- **Overview — « aperture »** : deux cercles concentriques (r≈7.5 et r≈3, le petit rempli) + quatre ticks radiaux à 45° hors de l'anneau — écho direct de la marque.
- **Workspace — « competition »** : cadre arrondi ; à l'intérieur trois barres verticales de hauteurs 40/75/55 % ; une ligne horizontale **pointillée** traverse à ~60 % (le seuil).
- **World — « grid »** : carré 3×3 en traits fins ; un disque plein dans la cellule centre-droit (l'agent).
- **Mind — « loop »** : cercle ouvert en haut à droite dont l'extrémité s'incurve vers l'intérieur en flèche pointant un point central (la boucle d'auto-modélisation).
- **Learning & language — « convergence »** : deux petits cercles à gauche reliés par deux segments qui convergent vers un cercle unique à droite, souligné d'un trait court (l'accord de nommage).
- **Laboratory — « flask »** : erlenmeyer en contour (col droit, corps triangulaire), ligne de liquide pointillée.
- **Memory — « constellation »** : trois disques de rayons différents reliés par deux arêtes fines (le graphe de similarité).
- **Settings — « faders »** : deux rails horizontaux, chacun portant un petit cercle-curseur à des offsets opposés.

### 3.3 Sidebar rétractable (desktop ≥ 1024 px)

- **Étendue** : 232 px — icône + libellé + (pour Laboratory) compteur discret d'entrées du ledger.
- **Rail** : 64 px — icônes seules, libellé au focus/hover (tooltip accessible), état actif = barre d'accent 2 px côté contenu.
- Bouton de rétraction en pied de sidebar + raccourci `[` ; état persisté (`humanity.ui.nav.collapsed`). Auto-rail entre 1024–1279 px. En pied de sidebar, au-dessus du toggle : la **vignette frontière** (une ligne, §6.1) quand le boundary strip global est masqué par l'utilisateur — la formulation courte n'est jamais absente de l'écran.

### 3.4 Topbar compacte (toutes vues)

Gauche → droite : marque + « Humanity », pill statut (`Running/Paused/error`), chip tick `t 1284`, sélecteur d'agent (si société), **breadcrumb**, espace flexible, bouton « Probe » (ouvre le dock, badge quand une sonde tourne), transport **Step · Run/Pause · Reset** + popover vitesse (`tps`), toggle thème. En scroll, la topbar reste (le comportement `is-scrolled` actuel — repli de l'épigraphe — est repris par le shell : l'épigraphe vit dans la charte).

### 3.5 Breadcrumbs sobres

Une ligne discrète sous la topbar : `Humanity › Laboratory › Causal probes`. Le segment de vue est cliquable (retour en haut de vue) ; le segment de section suit le scrollspy des sous-ancres. Jamais plus de trois segments, encre faible, séparateur `›`.

### 3.6 Préservation d'état par vue (hash + localStorage)

| État | Mécanisme |
|---|---|
| Vue + section actives | Hash (`#/laboratory/probes`) — restauré tel quel au rechargement |
| Dernière vue visitée | `humanity.ui.lastRoute` (utilisée si le hash est vide) |
| Scroll par vue, accordéons ouverts, onglet de sonde actif, métrique du lab-chart, agent sélectionné, rate tps, dock ouvert/fermé | `humanity.ui.view.<name>` (un objet par vue) + `humanity.ui.probe` |
| Thème | `cws-theme` (clé existante conservée) |
| Configuration simulateur (sliders + 32 flags) | `humanity.settings` (clé et logique `applyDeepDefaults` existantes conservées — diff contre `GET /config`, jamais de reset d'un run en cours) |
| Charte vue/masquée au premier lancement | `humanity.ui.charter.dismissed` |
| Données client volatiles (historiques sparkline, ignitionHistory, streamData, ledger) | Mémoire JS partagée entre vues (le routeur monte/démonte le DOM, pas l'état) ; `resetHorizonClientState()` reste le seul point de purge (Reset / Load checkpoint / Apply society) |

---

## 4. Palette de commandes (Ctrl/Cmd+K)

Champ unique, fuzzy. **Préfixes** : *(rien)* = tout ; `>` = commandes seulement ; `@` = métriques ; `#` = paramètres de configuration. Entrée = exécuter ; les commandes destructives (Reset, Delete checkpoint) demandent une confirmation Entrée×2. Raccourcis directs actifs hors champ de saisie.

| Catégorie | Commande (libellé affiché) | Raccourci |
|---|---|---|
| Navigation | Go to Overview / Workspace / World / Mind / Learning & language / Laboratory / Memory / Settings | `1`–`8` |
| Navigation | Open epistemic charter (framing & disclaimer) | `!` |
| Navigation | Show keyboard shortcuts | `?` |
| Transport | Run / Pause simulation (toggle, `POST /run` / `POST /pause`) | `r` |
| Transport | Step one tick (`POST /tick`) | `s` |
| Transport | Reset simulation… (confirmation, `POST /reset`) | `Shift+R` |
| Transport | Set simulation rate… (saisie tps) / Increase rate / Decrease rate | `+` / `-` |
| Probes | Toggle probe dock | `p` |
| Probes | Probe: Ask · Probe: Place stimulus · Probe: Inject coalition · Probe: Bias attention · Probe: Perturb state (ouvre le dock sur l'onglet) | — |
| Probes | Clear intervention ledger… | — |
| Display | Toggle theme (light/dark) | `t` |
| Display | Collapse/expand sidebar | `[` |
| Recherche | `@<metric>` — jump to metric (11 cellules indicators + 11 métriques time-series ; Entrée = ouvre #/laboratory avec la métrique sélectionnée) | `@` |
| Recherche | `#<setting>` — find setting (9 sliders + 32 flags par nom et description ; Entrée = #/settings, groupe déplié, contrôle focus + surligné) | `#` |
| Recherche | *(texte libre)* — sections et panneaux (« coalitions », « dictionary », « checkpoints »…) → navigation vers la sous-ancre | — |
| Laboratory | Run battery: Mirror / False memory / Calibration / Relational self / Masking / Attentional blink / Subliminal priming / Reality monitoring / Language genesis | — |
| Laboratory | Run scenario (focus l'éditeur JSON) ; Fast train… (saisie ticks) | — |
| Laboratory | Export CSV / Export JSON / Export analysis | — |
| Laboratory | Save checkpoint… (nom) ; Load checkpoint → sous-liste des noms ; Delete checkpoint → sous-liste | — |
| LLM (badgées) | Narrate current state · Ask the agent… (focus dialogue) · Inner voice (queue next competition) · Grounding audit · Report card · Biography · Cross-examination | — |
| World/Society | Place stimulus… (dock Stimulus) ; Set agent count… ; Select agent → 0…n | — |
| Memory | Search episodic memory… (focus la barre de #/memory) | `/` (sur #/memory) |
| Settings | Toggle: <chacun des 32 flags> (ex. « Toggle: inner speech », « Toggle: trace logging ») ; Activate all Phase 7 | via `#` |

Toute commande affiche sa cible réelle en sous-texte (`POST /battery/masking`, `#/settings › Phase 5`) — la palette respecte la signature de sources (§6.3).

---

## 5. Mobile (< 1024 px)

### 5.1 Pattern de navigation — pas une sidebar réduite

- **Bottom tab bar** (5 emplacements, 56 px, thumb-first) : **Overview · Workspace · Mind · Lab · More**. « More » ouvre une **sheet modale** listant World, Learning & language, Memory, Settings (+ Epistemic charter), chacune avec icône + description d'une ligne. Rationale : les trois vues d'observation + le laboratoire couvrent l'usage courant ; la sheet garde les huit destinations à deux gestes maximum.
- **Topbar deux rangées** : rangée 1 = marque, pill statut, tick, agent, thème ; rangée 2 = **transport** (Step, Run/Pause, rate stepper, Reset derrière « ⋯ ») — le transport reste visible sur toutes les vues, conforme au shell imposé.
- **Probe dock → bottom sheet** (mi-hauteur, extensible plein écran) au-dessus de la tab bar ; onglets de sonde en chips horizontales scrollables.
- **Palette** : bouton loupe dans « More » + geste appui long sur le titre ; Ctrl/Cmd+K reste actif avec clavier.

### 5.2 Transformations drawer / accordéon

- Toutes les sections de vue deviennent des **accordéons** à en-tête collant (titre + chip src) ; l'état ouvert/fermé est persisté par vue.
- La **charte épistémique** devient une sheet plein écran ; le **boundary strip** reste une ligne fixe au-dessus de la tab bar (tap → charte).
- Les **tables larges** (dictionnaire, ledger, checkpoints, coverage) scrollent horizontalement **dans leur carte** (`overflow-x` interne) — zéro scroll horizontal de page.
- Les **canvases** (world, society, graphe mémoire, charts) se redimensionnent à la largeur ; sur le monde, **tap 1 = sélectionner la cellule, tap 2 (même cellule) = injecter** — équivalent tactile du duo flèches+Enter, annoncé dans `#world-interaction-status`.
- **Zéro survol requis (390 px)** : tous les `title` actuels (endpoints, définitions de mécanismes, tooltips de barres du stream/timeline) deviennent soit des sous-libellés imprimés, soit des popovers « ⓘ » au tap ; le tooltip du graphe mémoire s'ouvre au tap sur nœud (fermeture ×) ; les side-labels du rail n'existent pas (pas de rail en mobile).

### 5.3 Ordre de lecture à 390 px (accordéons, de haut en bas)

- **Overview** : Aperture (ouverte) → dominant content → 6 KPI (2 colonnes) → Winning sources → miniature World → miniature Society → carte About (fermée).
- **Workspace** : bandeau moment (gate + winner) → Competition (ouverte) → hero-stats → AST → HOT → Stream → Access dynamics (fermée).
- **World** : barre Place → canvas World → légende → Society (canvas) → agents+Apply → Relations → Exchanges (fermée) → aide clavier (fermée).
- **Mind** : Self-model → Individuation → Self-opacity → Report & dialogue → Rhythms (fermée) → Asymptote → Horizon (fermée).
- **Learning & language** : convergence → success/deficit → dictionary → vocab → last exchange → Learned policy → Concepts → Personality.
- **Laboratory** : Live indicators (2 colonnes) → Time series → Batteries → Probes & ledger → Checkpoints → Exports → Scenario (fermée) → LLM probes (fermée) → Fast training (fermée) → Coverage (fermée).
- **Memory** : Search → Working memory → Recent episodes → Graph (ouvert, hauteur plafonnée, plein écran au tap).
- **Settings** : Filter → Core dynamics (ouvert) → groupes de phase (fermés) → Persistence → Society.

---

## 6. La frontière scientifique — visible en permanence, jamais envahissante

### 6.1 La formulation courte permanente — le « boundary strip »

Une ligne fixe en bas du shell (desktop : sous la zone de contenu, 26 px ; mobile : au-dessus de la tab bar), présente sur **les 8 vues** :

> **Functional simulation — the agent is not conscious, sentient, or alive.** · Framing & sources ↗

Le texte est la **première phrase de `GET /state.disclaimer` rendue verbatim** (source serveur, comme l'actuel `#footer-disclaimer`), jamais paraphrasée ni tronquée. Le lien ouvre la charte. Le strip est discret (encre faible, fond du shell) mais insupprimable ; si l'utilisateur le replie (chevron), la même phrase réapparaît en vignette au pied de la sidebar (desktop) ou dans l'en-tête de « More » (mobile) — l'écran n'est **jamais** sans la formulation courte.

### 6.2 Le panneau développé — « Epistemic charter »

Overlay global (raccourci `!`, lien du strip, carte About d'Overview, entrée de palette, lien en tête de #/settings). Contenu, dans l'ordre :

1. **THEORY_FRAMING_EN** — le texte de `#framing-text`, vivant depuis `GET /state.framing` (verbatim serveur) ;
2. **Le disclaimer complet** — `GET /state.disclaimer` intégral (l'actuel `#footer-disclaimer`) ;
3. **La distinction à trois niveaux** (copie statique du README : niveau 1 jamais revendiqué / niveau 2 implémenté / niveau 3 texte généré) ;
4. **Theory coverage** — lien direct « ●/○ mechanisms active → Laboratory › Coverage » ;
5. La convention de sources (§6.3) expliquée en deux phrases.

Au **premier lancement**, la charte s'ouvre d'elle-même par-dessus #/overview ; le bouton unique « Understood — keep the boundary line visible » la ferme et pose `humanity.ui.charter.dismissed`. Elle ne se rouvre plus jamais seule.

### 6.3 Les sources restent une signature

- **Chips d'endpoint par panneau** : chaque section conserve sa chip mono en en-tête, exactement comme aujourd'hui (`GET /agent/workspace · GWT`, `GET /society · multi-agent`, `Phase 5 · /tick`, `POST /config`…). C'est la signature d'honnêteté de l'instrument : on voit toujours *d'où* vient un chiffre. Sur mobile, la chip reste imprimée (pas de survol).
- **Sondes et formulaires** : les onglets du Probe dock gardent leur `code` d'endpoint (`POST /agent/inject`…) ; chaque entrée du causal ledger garde son endpoint et sa corrélation #NNN.
- **Disclaimers serveur verbatim** : le résultat de chaque batterie réaffiche `r.disclaimer` tel quel (comportement actuel conservé) ; AskResponse affiche son champ `disclaimer` dans le ledger.
- **Badge LLM systématique** : toute surface dont le texte provient d'un LLM (Narrate, Dialogue, Inner voice, Audit, Report card, Biography, Cross-examination) porte le badge « LLM » dans son en-tête + sa note de provenance sous la sortie (le pattern `#narrate-model` « Generated from internal variables by <model> — text, not lived experience » est généralisé). Le déterministe n'est jamais badgé : l'absence de badge signifie « mécanisme ».
- **Qualifications d'accès verbatim** : les libellés « global access — conscious (content broadcast) » et « present but subliminal (weakly conscious) » restent au mot près, partout où l'état d'ignition est qualifié (aperture, workspace, timeline).
- Les notes d'honnêteté de section (asymptote, langage, interventions, batteries, introspection) restent **imprimées** (rang secondaire), jamais reléguées en tooltip.

---

## 7. Cinq parcours utilisateur dans la nouvelle IA

### 7.1 Premier lancement

1. Ouverture → `#/overview` ; la **charte épistémique** se superpose : framing, disclaimer, trois niveaux. Clic « Understood — keep the boundary line visible ».
2. L'Overview vide se lit seule : aperture à 0, « awaiting the stream », KPI « — », CTA « Press Run — or Step once (`s`) ».
3. Appui `s` (Step) ×3 : l'aperture se remplit, le dominant content apparaît avec son flash, deux KPI bougent.
4. Clic **Run** (topbar) → pill « Running », tick défile, timeline des sources s'allonge, miniatures World/Society s'animent.
5. Clic miniature World → `#/world` ; breadcrumb « Humanity › World » ; le boundary strip est resté en place tout du long.

### 7.2 Observer une ignition

1. `2` → `#/workspace`. La compétition est le centre : barres triées, ligne de seuil, arousal avec baseline.
2. Popover vitesse (topbar) → `-` jusqu'à **1 tps** pour lire tick à tick.
3. Regarder le gate : `0.278 / 0.300` — « present but subliminal (weakly conscious) », winner grisé (`subliminal`).
4. Un stimulus apparaît (ou §7.3 pour le forcer) : le score franchit l'encoche, la lampe s'allume, l'état bascule sur « Global access », la barre gagnante passe en accent plein, le stream ajoute une barre saturée.
5. Scroll (ou clic breadcrumb « Dynamics ») → **Access dynamics** : le point d'ignition est marqué sur la courbe ; le résumé textuel donne le taux d'ignition sur 120 échantillons ; la timeline en dessous identifie la source gagnante par couleur.

### 7.3 Sonde causale + lecture du journal

1. Depuis `#/workspace`, appui `p` → **Probe dock** à droite, onglet **03 Inject** présélectionné (contexte workspace), compétition toujours visible.
2. Renseigner content « externally injected signal », activation 0.85, precision 0.9, TTL 1 → **Queue coalition**. Le dock passe busy (tous les boutons de sonde verrouillés).
3. L'entrée `#001 request POST /agent/inject` apparaît dans le mini-ledger du dock, suivie de `#001 result`.
4. `s` (Step) : la coalition injectée concourt sous les yeux — elle domine ou reste sous le seuil ; le gate et la lampe répondent.
5. Clic « Full ledger → Laboratory » (pied du dock) → `#/laboratory/probes` : les paires requête/réponse corrélées, payloads JSON complets, disclaimer d'intervention ; **Clear** disponible. Breadcrumb : « Humanity › Laboratory › Causal probes ».

### 7.4 Batterie fonctionnelle + rapport

1. `6` → `#/laboratory` ; section **Functional batteries**.
2. Clic **Masking** (`POST /battery/masking`) → ligne de résultat « masking: score=… — interpretation » + **disclaimer serveur réaffiché verbatim** dessous.
3. Enchaîner **Attentional blink** puis **Subliminal priming** ; comparer les scores dans la zone de résultat.
4. Section **LLM probes** (divulgation) → **Report card** ; statut « compiling… (runs the batteries + LLM, ~10s) » ; le rapport s'affiche en citation, badge LLM + note de provenance.
5. **Exports** : clic **Export JSON** (`GET /export.json`) ; puis **Checkpoints** : nom « post-masking » → **Save run** → la liste montre « post-masking · tick N · 1 agents ».

### 7.5 Société multi-agents + langage émergent

1. `3` → `#/world`. Dans Society : `agents` = **4** → **Apply** (l'avertissement « resets the run » est affiché ; l'état client est purgé comme aujourd'hui).
2. `r` (Run). Les 4 agents numérotés se déplacent ; **Relations** se peuple (trust · affect) ; le feed **Exchanges** affiche les premiers mots inventés.
3. Clic sur l'agent 2 dans le canvas → la topbar affiche « agent 2 » ; les vues agent-centrées (Mind, vocabulaire) suivent.
4. `5` → `#/learning-language` : la **convergence** monte, les chips de vocabulaire de l'agent 2 apparaissent, le **dictionnaire émergent** aligne modal word / agreement / speakers / variantes.
5. Contre-épreuve : Ctrl/Cmd+K → `#language drive` → toggle OFF (le deficit meter s'éteint), toggle ON ; puis palette → « Run battery: Language genesis » (`POST /battery/language_genesis`, ~20 s) → score ON vs OFF + interprétation + disclaimer, lisibles dans `#/laboratory/batteries`.

---

## Résumé

1. Les 21 panneaux et ~180 contrôles/readouts de la page unique sont **tous réaffectés** (tableaux §1) : rien ne disparaît, chaque élément a une maison canonique + échos déclarés (§1.19).
2. **Overview** = Ignition Aperture (score vs seuil, qualification verbatim), dominant content, 6 KPI à tendance, timeline des sources, miniatures World/Society — lisible en < 5 s.
3. Les **interventions** deviennent un instrument à deux fenêtres : Probe dock transversal (raccourci `p`, onglet contextuel) + établi/ledger canonique au Laboratory (§1.17).
4. **Introspection et dialogue LLM** restent juxtaposés sur #/mind pour rendre la provenance comparable ; les sondes LLM évaluatives vont au Laboratory (§1.18).
5. Navigation : sidebar rétractable 8 vues (icônes trait décrites §3.2), topbar transport/statut/tick/agent, breadcrumbs scrollspy, état par vue via hash + localStorage (§3.6).
6. Palette Ctrl/Cmd+K : navigation, transport, sondes, batteries, exports, checkpoints, LLM, et recherche `@métrique` / `#paramètre` (§4).
7. Mobile : bottom tab bar + sheet « More », dock en bottom sheet, accordéons, zéro survol et zéro scroll horizontal à 390 px (§5).
8. La frontière est une signature permanente : boundary strip serveur-verbatim sur les 8 vues, charte épistémique à un geste, chips `GET/POST` conservées partout, badge LLM systématique (§6).
