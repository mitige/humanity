# 05 — Data-viz & accessibilité : audit + specs de refonte

Date : 2026-07-11 · Auteur : data-viz-accessibility-specialist · Cible : WCAG 2.2 AA
Sources lues intégralement : `ui/app.js` (2 849 l.), `ui/index.html` (899 l.), `ui/styles.css` (1 303 l.),
`tests/test_phase7_ui.py`, `tests/test_interaction_ui.py`.
Sondes live (GET uniquement, `http://127.0.0.1:8123`) : `/agent/workspace`, `/agent/stream`, `/society`,
`/society/messages`, `/society/language`, `/metrics/history`, `/agent/memory/graph`.
Backend consulté pour les contrats de données : `core/global_workspace.py`, `core/society.py`,
`schemas/models.py` (`Message`), `app/api/routes.py`.

**Principes non négociables de ce document**
1. **Aucune donnée inventée.** Une valeur absente/`null` s'affiche « — » ; une série trop courte affiche
   « pas encore assez de données » ; un mécanisme à flag éteint s'affiche « dormant ». Aucune formule
   recomposée côté client qui ne soit pas celle du backend.
2. **Aucun contrat pytest cassé.** Les contrats ci-dessous (§0) sont préservés à l'identique par toutes
   les specs. Quand une spec *étend* un attribut verrouillé, elle le fait uniquement là où le test est
   ensembliste (⊇) et jamais là où il est d'égalité stricte (=).

---

## 0. Contrats verrouillés par pytest — à préserver tels quels

Relevé exhaustif de ce que `tests/test_phase7_ui.py` et `tests/test_interaction_ui.py` assertent
statiquement sur `ui/*` (toute refonte doit repasser ces tests sans modification des assertions a11y) :

| Contrat | Type | Conséquence pour la refonte |
|---|---|---|
| ids HTML : `horizon-readouts`, `ignition-chart`, `ignition-chart-summary`, `horizon-stream`, `memory-graph`, `memory-graph-nodes`, `memory-graph-edges`, `memory-graph-summary`, `memory-search-input`, `horizon-task` | présence | conserver ces ids sur les éléments équivalents |
| `#ignition-chart[aria-describedby]` ⊇ `ignition-chart-summary` ; `#memory-graph[aria-describedby]` ⊇ `memory-graph-summary memory-graph-nodes memory-graph-edges` | ensembliste | on PEUT ajouter des ids à ces `aria-describedby` |
| `#world-canvas[aria-describedby]` **= `world-interaction-help` exactement** | égalité stricte | INTERDIT d'y ajouter le futur panneau détail de cellule (le relier autrement, cf. §6) |
| `#world-canvas[tabindex]="0"`, `#memory-graph[tabindex]="0"` | égalité | clavier conservé |
| `#horizon-task` et `#ignition-chart-summary` **sans `aria-live`** | interdiction | ces résumés ne doivent JAMAIS devenir des live regions (ils changent à chaque poll) |
| `#interaction-log[aria-live]` ∈ {polite, assertive} + `aria-label` ; `#world-interaction-status[aria-live]` ∈ {polite, assertive} | présence | déjà `polite` — garder |
| labels exacts : `memory-graph-nodes[aria-label]="Indexed autobiographical memory nodes"`, `memory-graph-edges[aria-label]="Autobiographical memory similarity edges"` | égalité | ne pas traduire/reformuler |
| fonctions JS nommées : `renderHorizon`, `renderIgnitionDynamics`, `renderHorizonStream`, `refreshMemoryGraph`, `drawMemoryGraph` (+ `activateIntervention`, `submitIntervention`, `appendInterventionLog`, `mapWorldPointToGrid`, `postWorldStimulusAt`, `drawWorldCursor`, `setInterventionBusy`) déclarées `function NAME(` et appelées | présence | la refonte garde ces noms (le corps peut changer) |
| endpoints exacts dans le JS : `agent/memory/search?q=${encodeURIComponent(query)}&limit=8`, `agent/memory/graph?limit=60&edges=3`, `` `${API}/export.csv` ``, `` `${API}/export.json` `` | chaîne exacte | ne pas paramétrer autrement |
| `Math.random` interdit ; marqueurs `refreshInFlight`, `refreshQueued`, `horizonGeneration`, `resetHorizonClientState` ; throttle littéral `requestedTick - lastMemoryGraphTick < 20` et interdiction de `% 20` | déterminisme / races | l'ordonnanceur de rendu (cf. §13) doit rester déterministe et conserver ces gardes |
| séquences imposées : bootstrap (`applyDeepDefaults` → `refreshAll` → `refreshMemoryGraph(true)`), Step (génération capturée avant `await`, rejet stale avant `applyTrace`, `refreshAll` puis `refreshMemoryGraph(true)`), Reset / checkpoint-load / society-apply (invalidation + repaints ordonnés), `performRefreshAll` (garde génération + garde tick AVANT tout repaint) | ordre | le scheduler rAF s'insère APRÈS ces gardes, jamais avant |
| clavier graphe mémoire : `addEventListener("keydown")`, `"ArrowRight"`, `"ArrowLeft"`, `"Home"`, `"End"` ; tooltip mesuré via `tooltip.offsetWidth` / `tooltip.offsetHeight` | présence | conserver le pattern |
| CSS : sélecteurs exacts `.panel-horizon`, `.horizon-readouts`, `.memory-graph-shell`, `.sr-only` ; chaînes exactes `#world-interaction-status { color: var(--ink-soft); }`, `.interaction-sequence { color: var(--ink-soft);`, `body.is-scrolled .tps-field { display: none; }`, `body.is-scrolled .transport-buttons` | chaîne exacte | ne pas reformater ces règles |
| cache-buster : `?v=7.3` exactement, 2 occurrences dans `index.html` | égalité | tout bump d'asset (`?v=7.4`) doit mettre à jour les DEUX tests dans le même commit (convention déjà pratiquée dans le dépôt) — ce n'est pas un contrat a11y |
| `SETTINGS_DEFAULTS` avec les 8 flags Phase 7 à `true` ; `data-flag` des 8 flags dans le HTML | présence | conserver |

---

## Conventions transverses de la refonte (référencées §1–§11)

**C1 — Palette de sources thémée.** `SOURCE_COLORS` (app.js:19-24) est une palette unique appliquée
aux deux thèmes ; en thème clair elle est massivement < 3:1 sur `--bg-inset` (mesures §12.8 : perception
1,59:1, inner_speech 1,44:1). De plus la palette **ne couvre pas les sources réellement émises** par le
workspace live (`motivation`, `prediction_error`, `interoception`, `metacognition` observées sur
`/agent/workspace`) → elles tombent sur `unknown` gris. Spec :
- déplacer les couleurs de source en **CSS custom properties par thème** (`--src-perception`, …), le JS
  lisant `cssVar()` comme il le fait déjà pour le reste ;
- thème sombre : valeurs actuelles (toutes ≥ 3,6:1 sur inset, cf. §12.8) + 4 ajouts mesurés :
  `motivation #a8bd6a` (9,7:1), `prediction_error #c9807a` (6,6:1), `interoception #8fae9d` (8,4:1),
  `metacognition #b0a1d6` (8,6:1) ;
- thème clair : variantes assombries calculées (toutes ≥ 3:1 sur `#e2dccc`) : perception `#977536`,
  memory `#5d857a`, self `#8573ab`, emotion `#b36859`, goal `#66864b`, imagination `#5e7fa1`,
  dream `#755c9f` (inchangé, 4,05:1), social `#a06f85`, inner_speech `#8d7b4e`, wandering `#518386`,
  language `#91764e`, unknown `#7b7870` (inchangé), motivation `#728048`, prediction_error `#a86b66`,
  interoception `#698074`, metacognition `#82779e` ;
- **la couleur n'est jamais le seul canal** : partout où une source est encodée en couleur, le nom de la
  source est disponible en texte (légende, colonne, tooltip focusable, liste sr-only).

**C2 — Composant `meter` unique.** Toutes les barres 0..1 (`.meter`, `.co-bar`, `.q-bar`, `#ig-fill`,
fills du langage, individuation…) convergent vers un seul composant : conteneur
`role="meter" aria-valuemin="0" aria-valuemax="1" aria-valuenow="…" aria-label="…"`
(+ `aria-valuetext` quand l'unité n'est pas un ratio), valeur numérique toujours visible en texte mono
adjacent, remplissage ≥ 3:1 sur sa piste dans les deux thèmes. Valeur absente → `aria-valuenow` retiré,
texte « — », largeur 0. (Aujourd'hui : `div` muets + texte adjacent ; le texte existe presque partout,
la sémantique meter manque partout.)

**C3 — Canvas HiDPI partagé (« DPR sans fuite »).** Aucun des 6 canvas (`#world-canvas` 560×560,
`#society-canvas` 560×560, `#ignition-chart` 720×260, `#memory-graph` 720×440, `#lab-chart` 560×220,
`#circadian-dial` 120×120) ne gère `devicePixelRatio` : backing store fixe étiré par CSS
(`width:100%`, `aspect-ratio`) → flou sur tout écran HiDPI et à tout zoom. Spec, helper unique
`bindCanvas(canvas, draw)` :
- un `ResizeObserver` **créé une seule fois par canvas** à l'init (stocké en `WeakMap`), jamais dans une
  fonction de dessin ;
- écoute du changement de DPR via `matchMedia(`(resolution: ${dpr}dppx)`)` en ré-armant le listener
  `change` à chaque bascule (pattern « once » chaîné) — pas de `setInterval` ;
- redimensionnement : `canvas.width = round(clientWidth × dpr)` (dpr plafonné à 2 pour borner la
  mémoire), `ctx.setTransform(dpr·k, 0, 0, dpr·k, 0, 0)` où `k` = clientWidth/largeurLogique, tout le code
  de dessin restant en pixels logiques actuels (aucune réécriture des coordonnées) ;
- le redimensionnement marque le canvas « dirty » et laisse le scheduler rAF (§13) redessiner : jamais de
  dessin synchrone dans le callback de l'observer.

**C4 — Pattern « scrutation clavier » (déjà prouvé par le graphe mémoire).** Un seul tab-stop sur la
visualisation, flèches ←/→ (+ Home/End, Échap) déplacent une sélection, la sélection alimente : (a) un
tooltip positionné-mesuré (`offsetWidth/offsetHeight`, app.js:2041-2084), (b) un `<p class="sr-only"
aria-live="polite">` d'annonce **initiée par l'utilisateur** (jamais par le poll). Ce pattern est étendu
à l'access-dynamics (§3), à la timeline des sources (§4) et à la société (§7). Il remplace tous les
tooltips `title=""` (souris seule — inaccessibles clavier/tactile, cf. stream app.js:479, gate
index.html:84, arousal index.html:135).

**C5 — États vides honnêtes.** Trois états distincts, jamais confondus : **« — »** (valeur absente ce
tick), **« pas encore assez de données »** (série < 2 points), **« dormant — <flag> inactif »** (le flag
du mécanisme est décoché — état connu du client via les checkboxes Settings, donc réel). Le panneau
horizon (app.js:948-995) fait déjà la distinction live/dormant : généraliser sa formulation.

---

## 1. Compétition du workspace — `renderWorkspace` (app.js:405-466, HTML:126-149, CSS:529-561)

### État actuel
Tri des coalitions par `activation` décroissante ; barres `div` en grille `124px 1fr 44px` ; largeur de
barre = activation **normalisée au max de la fenêtre** ; gagnant = `.winner` (laiton plein) si ignition,
`.dominant` (laiton 38 %) sinon ; autres = dégradé `--cool`→`--ink-ghost` opacité 0,65. Ligne de seuil
positionnée en `calc(134px + (100% - 134px - 54px) * frac)` (app.js:465).

### Forces
- Tri par force lisible, gagnant distingué par un état ternaire (winner / dominant-subliminal / autres)
  qui reflète honnêtement l'accès gradué.
- `document.createDocumentFragment`, échappement systématique (`esc`), valeurs numériques affichées.
- Le commentaire du code (app.js:456-462) admet lui-même le **mismatch d'échelle** seuil/barres — le
  problème est connu, pas caché.

### Faiblesses
1. **Ligne de seuil fausse et fragile.** (a) *Fausse* : le backend (core/global_workspace.py:159-195)
   écrase `competition[].activation` par la **part softmax** (somme = 1, vérifié live), tandis que
   `effective_threshold` gate `ignition_score` = `winner_drive × (a + (1−a)·dominance)` — deux échelles
   incommensurables ; superposer le seuil aux barres suggère qu'une barre peut « franchir la ligne »,
   ce qui est faux. (b) *Fragile* : le `calc()` encode en dur `134px`/`54px`, couplés aux colonnes CSS
   `124px/44px` + gaps `10px` — toute retouche CSS désynchronise silencieusement la ligne.
2. Pas de couleur sémantique par source : la source n'est encodée que par un micro-libellé 9px
   `--ink-faint` (3,45:1 — sous AA, cf. §12.8).
3. `precision` et la force pondérée absolue (`winner_strength`, `dominance`) sont dans le payload mais
   invisibles ; « activation » n'est pas étiquetée comme part softmax.
4. Structure `div` sans sémantique tabulaire ; barres invisibles aux lecteurs d'écran (les valeurs texte
   sauvent l'essentiel, mais sans en-têtes de colonnes).
5. Fill par défaut `--ink-ghost` : 1,78:1 (sombre) / 1,30:1 (clair) sur la piste — sous 3:1.
6. Reconstruction complète des lignes à chaque poll (350 ms).

### Spec de refonte
- **Structure** : un vrai `<table>` stylé (ou grille `role="table"` si le rendu l'exige) — colonnes
  `Source | Contenu | Part du champ (barre + valeur) | Précision`. Caption sr-only :
  « Coalitions en compétition pour l'accès global, triées par part décroissante ».
- **Échelles honnêtes** : la barre encode la **part softmax brute** (0..1, PAS re-normalisée au max —
  la re-normalisation actuelle exagère les écarts entre polls et rend deux instants incomparables).
  En-tête de colonne : « part du champ (softmax) ». La précision s'affiche en colonne numérique `f2` +
  micro-barre secondaire fine (2px) sous la barre principale. **Aucune « force pondérée » par coalition
  n'est affichée** : le payload ne l'expose pas (le drive absolu pré-softmax reste interne) — l'inventer
  côté client est interdit. Extension backend optionnelle documentée : exposer `drive` par coalition.
- **Le seuil sort des barres.** La ligne `#threshold-line` est supprimée ; le rapport score/seuil vit
  dans l'Ignition Aperture (§2) et dans un bandeau de panneau : `ignition_score f3 / effective_threshold
  f3 · winner_strength f3 · dominance f3 · état (ignited/subliminal)` — quatre valeurs réelles du
  payload, en texte. Fin du `calc()` fragile.
- **Couleur par source** : pastille + liseré gauche de ligne aux couleurs C1 ; le nom de la source reste
  la première colonne en toutes lettres (couleur jamais seule). Ordre canonique des sources rappelé dans
  la légende partagée (C1) ; le tableau reste trié par part décroissante, avec flèche de tri visible.
- **Gagnant** : marqué par un badge texte `● access` (ignition) / `◐ dominant` (subliminal) dans la
  colonne Source — forme + texte, plus seulement la teinte laiton. Les non-gagnants gardent un fill
  neutre mais ≥ 3:1 : `--ink-soft` (7,5:1 sombre) au lieu de `--ink-ghost`.
- **Clavier** : les lignes du tableau sont focusables (`tbody` en C4 facultatif : ici la table native
  suffit — les cellules portent déjà tout en texte).
- **Perf** : lignes keyées par `source` ; mise à jour in-place (textContent + width), ajout/retrait
  seulement au diff (cf. §13).

---

## 2. Ignition gate héro → « Ignition Aperture » — `renderIgnitionGate` (app.js:373-386, HTML:84-90)

### État actuel
Piste linéaire 140×6px, `#ig-fill` (largeur %), `#ig-thresh` (tiret vertical), readout `0.000 / 0.300`,
classe `.over` → dégradé laiton. Tooltip `title` souris-seule. Lampe `#ignition-lamp` séparée avec
`animation: pulse 2.6s infinite` tant que `.is-ignited` (CSS:424-429).

### Forces
- Le rapport score/seuil effectif est LA bonne synthèse (c'est exactement ce que le backend gate) ;
  readout numérique toujours visible ; `.over` change aussi la luminosité, pas seulement la teinte.

### Faiblesses
1. 140px pour l'information centrale de l'instrument ; fill par défaut `--ink-ghost` 1,78:1.
2. `title` inaccessible ; aucun `role="meter"` ; l'état asleep (`metrics.is_sleeping`, dispo dans
   `/state`) n'existe pas visuellement.
3. La pulsation continue pendant tout l'état ignited (pas seulement l'événement) et n'est neutralisée
   que par le kill-switch global reduced-motion.

### Spec de refonte — cadran SVG central de l'Overview
**Géométrie exacte** (construite une fois à l'init avec `svgEl` app.js:40-44, mise à jour par
attributs — jamais reconstruite) :
- `viewBox="0 0 220 170"`, centre C = (110, 128), rayon R = 92, largeur de trait 10.
- Convention : angle θ mesuré depuis 12 h, sens horaire. Domaine t ∈ [0,1] → θ(t) = −120° + 240°·t.
  Point : `P(θ) = (110 + 92·sin θ, 128 − 92·cos θ)`.
- **Piste** : arc unique `M P(−120°) A 92 92 0 1 1 P(+120°)`, stroke `--bg-inset` bordé d'un hairline
  `--line`, extrémités droites (butt).
- **Graduations** : majeures à t ∈ {0, .25, .5, .75, 1} — segments radiaux de R−7 à R+7, stroke
  `--ink-soft` (≥ 3:1 les deux thèmes), étiquettes `0 · .25 · .5 · .75 · 1` en mono 10px `--ink-soft` à
  R+16 ; mineures tous les 0,05 — R−3 à R+3, stroke `--line`.
- **Arc de valeur** : même géométrie jusqu'à θ(`ignition_score`), `large-arc-flag = (score > 0.75) ? 1 : 0`
  (240°·score > 180°). Stroke : `--ink-soft` sous le seuil, `--accent` au-dessus (le changement
  au franchissement est redondé par le texte d'état et la lampe — pas couleur-seule).
- **Marqueur de seuil** (`effective_threshold`) : drapeau triangulaire pointant vers le centre —
  polygone [(R+4, 0), (R+14, −6), (R+14, +6)] tourné à θ(eff), fill `--ink` (14:1) + hairline radial
  `--accent` de R−10 à R+4. Triangle = forme distincte de l'arc : le seuil se lit sans couleur.
- **Centre** : `ignition_score` en mono 30px `--ink` ; dessous « seuil eff. `f3` » 11px `--ink-soft` ;
  dessous le mot d'état en 10px uppercase espacé : `● GLOBAL ACCESS` (accent) / `◐ SUBLIMINAL`
  (ink-soft) / `☾ ASLEEP` (cool, quand `metrics.is_sleeping` est vrai — donnée réelle de `/state`) —
  glyphe + mot, jamais la couleur seule.
- **États dégradés** : payload workspace absent → aucun arc de valeur, centre « — »,
  `aria-valuenow` retiré, `aria-valuetext="pas encore de mesure"`.
- **A11y** : le SVG est `aria-hidden="true"` ; son conteneur porte
  `role="meter" aria-valuemin="0" aria-valuemax="1" aria-valuenow="0.573"
  aria-valuetext="ignition 0.573 / seuil effectif 0.337 — accès global"`.
  Les ids existants `#ig-score` / `#ig-eff` sont conservés comme readout texte visible sous le cadran
  (continuité + aucun test à casser). Le `title=""` actuel est supprimé au profit d'un
  `aria-description`/texte visible.
- **Mouvement** : transition de l'arc et du drapeau 240 ms `cubic-bezier(0.2,0.7,0.2,1)`, déclenchée
  **uniquement quand le tick change**. Halo/pulsation autorisé **seulement pendant `ws.ignited === true`**
  (vraie ignition) et supprimé par `prefers-reduced-motion` : sous reduced-motion le changement d'état
  est instantané et signalé par **forme + texte** (dôme de lampe plein vs vide, mot d'état) — jamais par
  pulsation. Implémentation : brancher le `matchMedia("(prefers-reduced-motion: reduce)")` aussi en JS
  pour ne pas poser les classes d'animation (le kill-switch CSS global reste le filet).
- La jauge linéaire actuelle disparaît du héros (le panneau workspace garde le bandeau numérique §1) —
  on ne duplique pas deux représentations du même rapport.

---

## 3. Access dynamics — `renderIgnitionDynamics` (app.js:1022-1133, HTML:278-290)

### État actuel
Canvas 720×260 ; série `ignitionHistory` (cap 120, dédupliquée par tick — l'axe X est le temps de
simulation, pas le temps navigateur : très bien) ; ligne score pleine laiton, seuil pointillé
`--ink-faint` ; points aux ignitions ; légende dessinée dans le canvas (10px mono) ; labels d'axe
`t{first}`/`t{last}` ; résumé texte `#ignition-chart-summary` (taux d'ignition, derniers score/seuil) +
`aria-label` du canvas ré-écrit à chaque dessin. Pas d'`aria-live` (verrouillé).

### Forces
- Le résumé textuel est exemplaire (état vide compris) — **à préserver** ; échelle 0..1 fixe honnête ;
  déduplication par tick ; graduations 0/.25/.5/.75/1.

### Faiblesses
1. Pas de DPR (flou) ; texte in-canvas 10px `--ink-faint` (3,7:1 sombre sur inset, 2,7:1 clair —
   sous 3:1 en clair).
2. Zones ignited/subliminal absentes : seuls des points marquent l'ignition ; la relation « score
   au-dessus du seuil » se lit par croisement de courbes, difficile à échantillonner visuellement.
3. Source gagnante par échantillon non représentée (le payload workspace expose `winner_source` —
   non stocké dans l'échantillon).
4. Aucune interaction : ni tooltip, ni clavier ; le canvas n'est pas focusable.
5. Ligne de seuil `--ink-faint` pointillée : correcte en sombre, sous 3:1 en clair.

### Spec de refonte
- **Échantillon enrichi (données réelles)** : `{tick, score, effective_threshold, ignited,
  winner_source}` — `winner_source` lu du même payload `/agent/workspace` déjà en main (app.js:1023-1032).
- **Zones** : bandes verticales pleines `--accent` à 10 % d'opacité sur les intervalles où
  `ignited === true` (donnée booléenne réelle, pas une inférence) ; le point d'ignition existant est
  conservé (redondance forme + zone).
- **Bandeau des sources** : sous l'axe X, une rangée de tuiles de 4px de haut alignées aux échantillons,
  couleur C1 de `winner_source` — lisible comme un code-barres du « qui a gagné » ; légende C1 partagée
  au-dessus du panneau (HTML, pas in-canvas). La même information est disponible en texte via la
  scrutation clavier (ci-dessous).
- **Clavier + tooltip (C4)** : `tabindex="0"` sur le canvas (ajout autorisé — seuls world/memory-graph
  sont verrouillés, rien n'interdit d'en ajouter) ; ←/→ déplacent un curseur d'échantillon (réticule
  vertical dessiné), Home/End, Échap ; tooltip mesuré affichant `t · score · seuil · source · état` ;
  annonce dans un nouveau `<p id="ignition-chart-selection" class="sr-only" aria-live="polite">`
  (annonce initiée-utilisateur — autorisée ; **ne jamais** mettre `aria-live` sur
  `#ignition-chart-summary`, verrouillé). `aria-describedby` du canvas peut gagner l'id de sélection
  (test ensembliste).
- **Résumé** : conserver la phrase actuelle, y ajouter la source dominante majoritaire de la fenêtre
  (« source la plus fréquente : perception (62 %) » — calculée sur les échantillons réels).
- **Rendu** : DPR via C3 ; axes/légende sortis du canvas vers le HTML (contraste contrôlé par CSS,
  zoom texte fonctionnel) ; texte in-canvas restant ≥ 11px logiques et `--ink-soft`.
- État vide : conservé (« No access-dynamics samples yet », in-canvas + résumé).

---

## 4. Timeline des sources — `renderHorizonStream` (app.js:1135-1169, HTML:287-289, CSS:1087-1108)

### État actuel
`div role="img"` + `aria-label` de synthèse (n moments, n ignités, n sources, dernière source) ; 48
`span.moment` max : hauteur = awareness, `background-color` = SOURCE_COLORS, ignited = saturation/opacité
pleines + glow, subliminal = opacité 0,54 + `saturate(0.66)` ; chaque barre porte `title` + `aria-label`.

### Forces
- La synthèse `aria-label` du conteneur est le bon niveau d'information ; la note sous le graphe explique
  les encodages et précise « access timeline, not a measure of experience » (honnêteté) ; cap 48 côté client.

### Faiblesses
1. **Couleur-seule pour la source** : aucune légende ne mappe couleur → source nulle part dans la page ;
   en thème clair la palette est < 3:1 (C1).
2. **Conflit ARIA** : `role="img"` rend les descendants présentationnels — les `aria-label` posés sur
   chaque `span.moment` (app.js:1157) sont inertes ; les `title` sont souris-seule. L'information
   par-barre est donc inaccessible.
3. Distinction ignited/subliminal par opacité/saturation uniquement (dégradé de la même teinte) —
   faible pour les déficiences de perception des contrastes.
4. Rebuild innerHTML complet des 48 spans à chaque poll.

### Spec de refonte
- **Légende partagée C1** au-dessus de la bande : chips `pastille + nom de source`, générées depuis les
  sources réellement présentes dans la fenêtre (aucune source fantôme), avec compte d'occurrences.
- **Encodage ignited redondant** : barre ignitée = pleine + coiffe de 2px `--ink` en tête de barre ;
  subliminale = **contour** (fill transparent, stroke couleur source 1,5px) — différence de forme, plus
  seulement d'opacité.
- **A11y** : conserver `role="img"` + synthèse (pattern validé) ; retirer les `aria-label`/`title`
  par-barre (morts) ; ajouter une **liste sr-only équivalente** `<ol>` (pattern des memory-graph-nodes,
  éprouvé et verrouillable) : « t14 · perception · awareness 0.573 · ignited · <contenu> » ; brancher la
  scrutation clavier C4 (un tab-stop, tooltip par barre, annonce sélection).
- **Barres = spans keyés par tick**, mise à jour incrémentale (ajout à droite, retrait à gauche), pas de
  rebuild ; transitions de hauteur retirées du flux de poll (elles animent en continu — cf. §12.11) et
  remplacées par l'apparition simple de la nouvelle barre.
- Hauteur : conserver `height = awareness` mais avec un plancher visible 4px et une piste de fond
  hairline pour situer le 0..1 (deux repères 0/1 en micro-texte).

---

## 5. Sparklines métriques — `renderMetrics` / `sparkPath` (app.js:491-572, HTML:151-158, CSS:566-594)

### État actuel
11 tuiles (`METRIC_DEFS`), historique client 60 points, sparkline SVG 100×26 auto-échelonnée min/max de
fenêtre (négatifs gérés), valeur mono, tons par classe. Tuile à « — » tant qu'aucune valeur.

### Forces
- Auto-échelle honnête (pas d'écrasement des négatifs) ; fusion metrics/consciousness prudente
  (`!= null` partout) ; mise à jour d'attributs `d` (pas de rebuild DOM) — c'est le rendu le PLUS sobre
  de l'app.

### Faiblesses
1. Ni unités, ni domaine, ni min/max de fenêtre affichés : une sparkline auto-échelonnée sans bornes est
   illisible (une ligne plate peut couvrir 0,001 ou 1,0 d'amplitude).
2. Pas d'état « pas assez de données » (1 point → segment central trompeur) ni « dormant » (les tuiles
   `phi_causal`, `vfe`, `wandering_occupancy`, `task_progress` restent « — » pour toujours quand le flag
   est éteint, indistinguable d'un chargement).
3. Titres partiellement cryptiques (« Φ proxy », « VFE ») sans description accessible ; SVG sans
   `aria-hidden` (bruit potentiel).
4. Labels 9px `--ink-faint` : 3,45:1 (§12.8).

### Spec de refonte
- **Étendre `METRIC_DEFS`** : `[key, label, tone, fmt, norm, unit, domain, description]` avec
  `domain` ∈ {`[0,1]`, `unbounded`, `energy-units`} — métadonnées statiques, pas des données.
- **Pied de tuile** : `min f3 · max f3` de la fenêtre réelle (calculés de `HISTORY[key]`, déjà en
  mémoire) en mono 10px `--ink-soft` ; domaine affiché en filigrane (« 0–1 » ou « libre » ou « u »).
- **États** : < 2 points → sparkline masquée, mention « pas encore assez de données » ; flag connu
  décoché (checkbox Settings, état client réel) → tuile `.is-dormant` (opacité type horizon-readout)
  avec mention « dormant — <flag> inactif » ; sinon « — » (C5).
- **A11y** : `svg.mc-spark[aria-hidden="true"]` ; la tuile devient un mini-groupe
  `role="group" aria-label="Φ proxy, 0.514, fenêtre min 0.462 max 0.539"` mis à jour au tick ;
  `description` disponible via tooltip focusable (bouton « ? » 24px min) plutôt que `title`.
- Labels remontés à 10px avec le `--ink-faint` corrigé (§12.8).
- Fenêtre indiquée dans l'en-tête du panneau : « fenêtre 60 ticks ».

---

## 6. Monde — `drawWorld` (app.js:218-304, HTML:421-454, CSS:599-653)

### État actuel
Canvas 560×560 CSS-scalé (`width:100%`, `max-width:560px`, `aspect-ratio:1`) ; grille hairline ; objets =
**cercles** couleur-par-kind (`--pos/--neg/--cool/--curio`), rayon = novelty, opacité = danger, anneau
rouge si danger > 0,4 ; agent = point cerclé laiton ; anneau de perception pointillé (opacité 0,22) ;
curseur cellule pointillé clavier/pointeur (verrouillé par tests) ; statut live `polite` ; légende à
pastilles rondes couleur-seule.

### Forces
- Le clavier est complet et testé (flèches + Enter, annonce de cellule) ; la légende existe ; le rayon de
  perception est déjà dessiné ; le curseur survit au redraw.

### Faiblesses
1. **HiDPI : oui, c'est flou.** 560 pixels de backing store étirés sur 560 px CSS × DPR (1120+ pixels
   physiques à DPR 2) — tout écran retina rend grille et hairlines baveuses. (C3.)
2. **Kind = couleur-seule** : quatre cercles identiques dont seule la teinte varie (le rayon encode la
   novelty, pas le kind) ; légende également couleur-seule ; en thème clair `--pos/--neg/--cool` sont à
   3,6–3,9:1 (ok) mais la distinction inter-kinds repose sur la teinte uniquement.
3. **Aucun panneau de détail de cellule** : les propriétés réelles des objets (`energy_value`, `danger`,
   `novelty`, `utility` — présentes dans `/state`) sont invisibles ; le seul retour est le statut
   d'injection.
4. L'anneau de perception (opacité 0,22) est quasi invisible et absent de la légende.
5. `aria-label` du canvas statique (« Interactive view of the simulated world ») — aucun contenu.

### Spec de refonte
- **Formes par kind (couleur + forme, jamais couleur seule)** : food = disque, hazard = **triangle**
  (pointe en haut), tool = **carré**, curio = **losange**. Taille toujours = novelty ; anneau de danger
  conservé. La **légende** passe à des swatches SVG inline reprenant exactement ces formes + libellés
  texte (déjà présents) ; ajouter l'entrée « rayon de perception » (cercle pointillé) et « curseur »
  (carré pointillé). Anneau de perception remonté à opacité 0,45, stroke `--accent` 1,5px.
- **Panneau détail de cellule — À CRÉER** (`#world-cell-detail`, sous les outils d'injection) :
  à chaque déplacement du curseur (souris OU flèches), rendu depuis `currentWorldSnap` (données réelles,
  zéro fetch) : coordonnées, objets de la cellule (kind, id, `energy_value f2`, `danger f2`, `novelty f2`,
  `utility f2`), présence de l'agent, distance de Manhattan à l'agent, dans/hors rayon de perception.
  Cellule vide → « cellule vide ». **Contrainte verrouillée** : `#world-canvas[aria-describedby]` doit
  rester exactement `world-interaction-help` — le panneau n'y est PAS ajouté ; il est lié par proximité
  visuelle + l'annonce courte existante dans `#world-interaction-status` (aria-live polite verrouillé,
  annonces initiées-utilisateur : déjà le comportement des flèches, app.js:1927-1930 — y ajouter un
  résumé de contenu : « Selected cell (3,4): hazard #8, danger 0.69 »).
- **Table équivalente** : `<details>` « objets visibles (n) » sous la légende, table `kind | id | x,y |
  danger | novelty | utility` triée par distance — l'équivalent non-graphique du canvas (§12.7).
- **HiDPI** : C3 ; hairlines tracées à 0,5px logique alignées au demi-pixel physique.
- `aria-label` du canvas enrichi au tick (autorisé) : « World grid 12×12, tick 14, 11 objects, agent at
  5,4 » — le détail vit dans la table.

---

## 7. Société — `drawSociety` / `renderRelations` (app.js:2252-2331, HTML:456-472) + `/society/messages`

### État actuel
Canvas 560×560 : objets = petits carrés couleur-kind, agents = disques `--ink` avec id en texte, agent
sélectionné = `--accent` ; clic sur un agent → `SOC_SELECTED` (re-fetch `/society` par clic) ; relations
= lignes texte `from→to · trust f2 · affect` ; `aria-label` statique « Society world » ; pas de tabindex.
`GET /society/messages` **n'est jamais appelé par l'UI** (vérifié : aucun `society/messages` dans app.js ;
schéma réel `Message` = `{id, tick_emitted, sender_id, content, vector, x, y, radius, ttl, word}`).
Le payload `/society` expose aussi `agents{id: {metrics, self_model, social}}` — **non rendu**, et
`relations.edges[].familiarity` — **non rendu**.

### Faiblesses
1. Canvas souris-seule (pas de tabindex, pas de clavier), aria statique, pas de flou-DPR géré (C3).
2. La sélection d'agent ne pilote QUE la teinte du disque : ni les relations, ni des cartes, ni le reste.
3. Relations : familiarity absente ; texte brut sans structure ni barres comparables ; pas d'état
   « aucun agent autre ».
4. Flux de messages totalement absent alors que l'endpoint et le rendu spatial (x, y, radius, ttl)
   existent côté backend.
5. Agents indistinguables hors sélection (tous `--ink`) ; l'id en `fillText` sans fallback de contraste
   calculé.

### Spec de refonte
- **Carte spatiale** : mêmes formes-kind que §6 (helper de dessin partagé) ; agents = disques numérotés
  (id toujours en texte) ; sélection = anneau double `--accent` + épaisseur (forme, pas seulement
  couleur). **Clavier** : `tabindex="0"`, ←/→ cyclent la sélection parmi les agents (ordre par id),
  Enter confirme (met à jour `#soc-selected`, texte déjà existant), annonce via un
  `<p class="sr-only" aria-live="polite">` dédié (initiée-utilisateur).
- **Cartes agents comparables** (nouvelles, depuis `/society.agents` — données déjà téléchargées à
  chaque poll et jetées) : une carte par agent — id, `energy f0`, `phi_proxy f3`, `awareness f3`,
  `last_action`, `affect`, mini-meter d'énergie (C2) — mêmes colonnes pour tous = comparables ;
  la carte sélectionnée porte le même badge que la carte spatiale ; cliquer une carte = sélectionner.
- **Graphe relationnel** : par paire orientée `from→to` : `trust` ET `familiarity` en deux micro-meters
  C2 étiquetés + `affect` en texte ; regroupé par agent sélectionné d'abord (le reste en dessous) ;
  état vide « No relations yet » conservé ; n_agents = 1 → « un seul agent — pas de relations ».
- **Flux de messages — intégrer `GET /society/messages`** :
  - fetch seulement quand le panneau est visible ET que le tick a changé (§13) ;
  - **fil** : ligne par message vivant : `t{tick_emitted} · agent {sender_id} · « {word ?? —} » ·
    {content} · portée {radius} · ttl {ttl}` — état vide « aucun message vivant » (observé live :
    `{"messages": []}`) ;
  - **surcouche carte** : cercle d'earshot (rayon `radius` cellules) centré sur (x, y), opacité
    proportionnelle au ttl restant — uniquement des champs réels du Message ; on ne dessine PAS de
    flèches vers des « auditeurs » (la délivrance a lieu au tick suivant : les destinataires ne sont pas
    dans le payload — les inventer est interdit) ;
  - la sélection d'un agent filtre le fil sur `sender_id` (et l'indique : « messages de l'agent 1 »).
- **Synchronisation** : `SOC_SELECTED` devient l'unique source de vérité et re-rend carte + cartes +
  relations + fil sans re-fetch (les données du dernier poll suffisent).

---

## 8. Langage — `renderLanguage` / `refreshSocietyLanguage` (app.js:1367-1441, HTML:611-647)

### État actuel
Convergence (`—` si null — correct), succès + déficit en meters, dernier échange en phrase (`✓` si
compris), vocabulaire agent 0 en chips `kind-*` colorées, dictionnaire émergent : `« mot » = sens ·
agreement f2 · n speakers · variantes «w»×n`. Payload réel : `dictionary{meaning: {modal_word,
agreement, speakers, variants{word: count}}}`, `convergence`, `n_meanings_named`, `distinct_modal_words`.

### Forces
- Les états vides sont exemplaires (« No conventions yet — let the society talk ») ; la convergence null
  reste « — » ; les chips portent mot ET sens en texte (la couleur kind est décorative, pas seule).

### Faiblesses
1. Le dictionnaire en lignes ne permet pas de comparer les variantes entre sens : pas de **matrice**.
2. Polysémie/homonymie non signalées alors qu'elles sont dérivables du payload réel (même `modal_word`
   sur ≥ 2 sens ; `distinct_modal_words < n_meanings_named`).
3. Le dernier échange écrase l'historique (un seul événement, pas de fil) ; le `✓` est un glyphe nu.
4. `lang-chip` thème clair : couleurs kind à ~4,4–5,2:1 sur bg-3 (ok texte large, limite en 11px mono) —
   à re-vérifier après la correction de palette.
5. Rebuild innerHTML chips + dictionnaire à chaque poll + 1 fetch `/society/language` par poll.

### Spec de refonte
- **Matrice lexicale sens × variantes** (données réelles du dictionnaire) : lignes = sens
  (food/hazard/tool/curio…), colonnes = variantes observées ; cellule = compte de locuteurs `×n` ;
  la variante modale est marquée `★` + `agreement` en % ; en-têtes de ligne = sens en texte + pastille
  kind. Rendue en `<table>` (caption : « conventions par sens ; ★ = convention majoritaire »).
  **Limite honnête documentée** : une matrice **sens × agents** (qui parle quel mot) exigerait un
  endpoint par-agent (`/society/language` n'expose que des agrégats + `variants` par sens ; seul le
  lexique de l'agent 0 arrive via la trace). Ne PAS la simuler ; extension API optionnelle notée :
  exposer `lexicons: {agent_id: {meaning: word}}`.
- **Homonymie** (dérivée, pas inventée) : si un même `modal_word` couvre ≥ 2 sens → badge « homonyme »
  sur les lignes concernées, tooltip focusable listant les sens ; indicateur global :
  `distinct_modal_words / n_meanings_named` déjà affiché — le libeller « mots distincts / sens nommés »
  (aujourd'hui la ligne `#lang-distinct` est du jargon).
- **Dernier échange comme événement lisible** : conserver la phrase, remplacer `✓` par `✓ compris`
  (texte) / « → sans contexte » ; ajouter un mini-fil des 5 derniers échanges (bufferisé côté client
  depuis les traces successives — données réelles reçues, simplement non jetées).
- Chips : inchangées (texte complet présent) ; vérifier les contrastes post-C1.
- Fetch `/society/language` : passer à la cadence « froide » (§13) — le lexique n'évolue pas à 350 ms.

---

## 9. Graphe mémoire — `drawMemoryGraph` (app.js:1258-1361) + tooltip/clavier (app.js:2034-2156)

### État actuel
Spirale dorée déterministe **indexée par position dans le tableau** (`angle = index × goldenAngle +
tickPhase`, `radius = f(√index)`) ; rayon nœud = importance ; couleur = valence (>±0,12) sinon famille
d'action ; arêtes `--cool` alpha ∝ similarité ; sélection clavier complète (flèches/Home/End/Échap,
verrouillée), tooltip mesuré, listes sr-only nœuds + arêtes (verrouillées), résumé
`#memory-graph-summary` **avec `aria-live="polite"`** (HTML:312), throttle 20 ticks (verrouillé),
cap `limit=60&edges=3` (verrouillé).

### Forces
- Le socle a11y le plus complet de l'app : c'est LE pattern de référence (C4) ; déterminisme réel ;
  gestion générationnelle anti-races testée ; états vides propres.

### Faiblesses
1. **Instabilité visuelle** : l'angle dépend de l'INDEX ; quand la fenêtre de 60 glisse (nouveau
   souvenir → le plus ancien sort), TOUS les index décalent → tout le graphe pivote d'un cran à chaque
   entrée. L'ancre `tickPhase` (app.js:1330) module à peine.
2. `#memory-graph-summary` est une live region alimentée par le poll (throttlé 20 ticks, mais
   annonce non sollicitée quand même) — incohérent avec l'interdiction (juste) posée sur
   `ignition-chart-summary`.
3. Le formulaire de recherche (`/agent/memory/search`, verrouillé) ne dialogue pas avec le graphe :
   résultats et nœuds vivent séparés ; aucun filtre.
4. Encodage triple sur la couleur (valence OU action) ambigu : un nœud sage peut être « valence > 0,12 »
   ou « action rest » selon le seuil — indéchiffrable sans tooltip ; tick invisible hors tooltip.
5. DPR absent ; sr-only lists reconstruites entièrement à chaque draw (60 + ~90 `<li>`).

### Spec de refonte
- **Stabilité** : `angle = node.id × goldenAngle` (l'id d'épisode est stable et déterministe — vérifié :
  ids monotones 609…613 sur le live) ; `radius = 18 + √(rang du tick dans la fenêtre) × 24` — quand la
  fenêtre glisse, chaque nœud bouge d'au plus un rang radial, son azimut ne change JAMAIS. Repositionnement
  instantané (canvas — pas d'animation, conforme reduced-motion par construction).
- **`aria-live` retiré de `#memory-graph-summary`** (le test exige l'id et l'`aria-describedby`, pas la
  liveness — vérifié dans test_phase7_ui.py:114-127). `#memory-graph-selection` (annonces
  initiées-utilisateur) reste `polite`.
- **Recherche ↔ graphe** : chaque résultat de recherche gagne un bouton « situer dans le graphe » →
  si l'id est dans le cache courant, `selectMemoryGraphNode(indexOfId)` (fonction existante) + focus du
  canvas ; sinon mention « hors de la fenêtre des 60 derniers épisodes » (honnête).
- **Filtre client** (sur le cache, zéro fetch) : chips par famille d'action (explore/approach/avoid/
  rest/interact…) — les nœuds non retenus passent à opacité 0,25 SANS être retirés (la topologie reste
  entière) ; compte affiché « 12/60 visibles ».
- **Encodages clarifiés** : couleur = valence UNIQUEMENT (séquence pos/neutre/neg, trois classes
  discrètes annoncées dans une mini-légende) ; famille d'action = petit glyphe central (2–3px : point,
  croix, tiret — dessinés, pas des emoji) ; importance = rayon (inchangé) ; tick = déjà en tooltip +
  liste sr-only (suffisant, ne pas surcharger). Similarité = alpha + épaisseur (inchangé) avec seuil
  d'affichage optionnel (« arêtes ≥ 0,9 ») en contrôle client.
- **Tooltip au focus** : déjà fait via sélection clavier (C4) — conserver ; DPR via C3 ; listes sr-only
  mises à jour par diff keyé sur `node.id`/`(source,target)`.

---

## 10. Lab chart — `refreshLabChart` (app.js:2338-2391, HTML:325-343)

### État actuel
Une polyline par agent sur `GET /metrics/history?limit=200` (re-fetché À CHAQUE POLL de 350 ms),
auto-échelle y min/max, palette positionnelle `--accent/--cool/--pos/--curio/--neg`, aucun axe, aucune
légende, aucune unité, état vide = canvas nettoyé silencieusement, `aria-label` statique.

### Faiblesses
1. Illisible en l'état : pas d'axes ni de bornes → la courbe n'a aucun référentiel ; pas de légende
   agent ; la palette positionnelle **réutilise les couleurs sémantiques des kinds** (`--pos` = food,
   `--neg` = hazard) : un agent « rouge » suggère un danger.
2. État vide muet (on ne sait pas si c'est « pas de données » ou « en panne »).
3. Le fetch 200 lignes × ~3 polls/s est le pire coût réseau de l'app (§13).
4. Pas de DPR ; aucun équivalent textuel.

### Spec de refonte
- **Cadre** : axe Y avec min/max réels de la fenêtre + 4 gridlines étiquetées (HTML au-dessus/à côté du
  canvas, pas in-canvas) ; axe X `t{first} … t{last}` ; unité par métrique (map statique alignée sur
  §5 : energy en unités, le reste 0..1 ou libre).
- **Multi-agents** : 1 agent → une courbe `--accent`. 2–3 agents → superposition avec **légende chips
  « agent N »** au-dessus, palette catégorielle NEUTRE dédiée (déclinaisons de laiton/ardoise non
  sémantiques, C1 exclu, kinds exclus). > 3 agents → **small multiples** : une mini-fenêtre par agent
  (titre « agent N » en texte), même échelle Y partagée (comparabilité), une seule couleur `--accent` —
  la couleur cesse totalement d'encoder l'identité.
- **États** : aucune ligne → texte in-canvas + sous-titre « pas encore d'historique pour <métrique> » ;
  série d'un point → « pas encore assez de données » (C5).
- **Équivalent textuel** : `<p id="lab-chart-summary" class="micro chart-summary">` (SANS aria-live,
  même règle que le chart d'ignition) : « énergie, 3 agents, fenêtre t12–t212, min 84.2, max 120.0 » ;
  `aria-describedby` du canvas pointant dessus.
- **Réseau** : fetch seulement si (panneau visible) ∧ (tick a avancé) ∨ (métrique changée au select) —
  cf. §13 ; le select conserve son handler direct (app.js:2393).
- DPR : C3.

---

## 11. Jauges HOT, meters génériques, dial circadien (app.js:399-403, 754-799 ; HTML:667-697, 166-190)

### État actuel
3 demi-jauges SVG (dasharray 132 ≈ longueur d'arc réelle π×42) meta/perception/prediction ; dial
circadien canvas (anneau + arc de daylight + % au centre, disque soleil/lune) ; `.meter` 4–5px omniprésent
(héros, deep, individuation, langage, workspace, wm-load…) ; valence bipolaire avec zéro central.

### Forces
- Chaque jauge/meter a sa valeur numérique adjacente (rien n'est « graphique-seul ») ; la bipolaire a un
  signe textuel (+/−) en plus de la couleur pos/neg ; le dial affiche le % au centre.

### Faiblesses
1. **Jauges circulaires répétées** : 3 demi-donuts HOT + dial circadien + (bientôt) l'Aperture §2 —
   la forme circulaire perd son sens quand elle est partout ; les demi-donuts encodent 0..1 sans
   graduations ni seuils, un bullet fait mieux en 1/3 de la place.
2. `dasharray: 132` en dur (CSS:787) — recalibrage silencieusement faux si le path change ;
   `pathLength="100"` existe pour ça.
3. Dial : canvas 120×120 non-DPR ; texte du % dessiné en `--bg-inset` sur disque `--accent`/`--cool`
   (contraste dépendant de l'état) ; `aria-label` statique (« Circadian day/night dial ») sans la valeur ;
   sémantique cyclique correcte MAIS l'arc « proportion de daylight » démarre toujours à midi-haut :
   il encode une proportion, pas une heure — ambigu.
4. `.meter` : aucun `role`, fills parfois `--ink-ghost` (< 2:1) ; hauteur 4px sous le seuil de
   perceptibilité en 200 % zoom sur petits écrans.

### Spec de refonte
- **HOT → bullets horizontaux** (composant C2, hauteur 8px, piste graduée aux quarts) : le cercle est
  réservé à l'Aperture (l'instrument central) et au circadien (sémantique horaire réelle). Un seul
  cadran fort par vue — plus de « répétition de jauges ».
- Si un anneau HOT devait survivre pour raison d'identité visuelle : `pathLength="100"` +
  graduations + le même `role="meter"`.
- **Dial circadien conservé** (cycle = cercle légitime) mais : DPR (C3) ; l'arc devient une **aiguille
  d'horloge de simulation** si le backend expose la phase (sinon, rester sur la proportion mais la
  titrer « part de jour » explicitement) ; % au centre en `--ink` sur pastille neutre `--bg-3`
  (contraste stable dans les deux états) ; conteneur `role="meter"` avec
  `aria-valuetext="daylight 62 % — jour"` mis à jour ; soleil/lune = glyphe + mot (« jour »/« nuit »),
  pas seulement la teinte accent/cool.
- **`.meter` global** : hauteur minimale 6px ; fills uniquement dans {accent, ink-soft, pos, neg, cool,
  curio} corrigés (≥ 3:1 sur piste, §12.8) ; `--ink-ghost` banni comme fill ; C2 partout.
- **Valence bipolaire** : conserver (zéro central + signe) ; ajouter `aria-valuemin="-1"`
  `aria-valuemax="1"` via C2.

---

## 12. Checklist WCAG 2.2 AA spécifique à l'app

### 12.1 Landmarks, headings, skip link
- ✅ `header` / `main` / `footer` natifs ; chaque panneau est `section[aria-labelledby]` (nom accessible
  → landmark `region`) ; hiérarchie h1 (masthead) → h2 (panneaux) → h3 (`.sub`) sans trou.
- ❌ **Aucun skip link** : en ajouter un (`<a class="skip-link" href="#main">`) visible au focus, avant
  le masthead ; cible `main[id]` + `tabindex="-1"`.
- ⚠️ 21 regions nommées = paysage de landmarks très dense : acceptable pour un instrument, mais la
  palette Ctrl+K (§12.5) devient le vrai sommaire ; prévoir aussi un `nav` « modules » (liste
  d'ancres) dans le masthead compacté.
- ⚠️ Les numéros de modules sont générés par `counter()` CSS (content ::before) — exposés à l'accname :
  garder mais vérifier qu'ils ne polluent pas les intitulés annoncés (sinon `aria-hidden` sur le pseudo
  via un span réel).

### 12.2 Focus visible (les deux thèmes)
- État : `:focus-visible { outline: 1px solid var(--accent-soft) }` (CSS:136).
  Mesures : sombre 3,8–4,1:1 (passe 1.4.11) mais **1px est trop fin** ; clair **2,2–2,9:1 → ÉCHEC**.
- Spec : `outline: 2px solid var(--focus)` + `outline-offset: 2px`, avec `--focus` = `--accent` sombre
  (8,5:1) et `#7a5a1e` clair (5,1–6,0:1 sur bg/bg-2/bg-3, mesuré) ; conserver les focus renforcés des
  canvas (`#world-canvas:focus-visible` verrouillé par test — ne pas supprimer la règle, l'enrichir).
- Vérifier 2.4.11 (Focus Not Obscured) : le masthead sticky peut recouvrir un élément focusé au scroll —
  ajouter `scroll-padding-top: <hauteur masthead>` sur `html`.

### 12.3 Cibles (2.5.8 : 24px minimum AA ; objectif projet : 44px pour les commandes primaires)
- Boutons `.btn` ≈ 31px de haut, `.icon-btn` 36px, tabs interventions ≈ 44px ✅, sliders natifs ✅
  (exception), chips toggles ≈ 29px.
- Spec : transport (Step/Start/Pause/Reset) et boutons de soumission → min-height 44px ;
  tout autre contrôle ≥ 24×24 CSS px ou espacement compensatoire ; `.btn.micro` (checkpoints) 4px de
  padding vertical → à remonter ≥ 24px de hauteur totale.
- Les barres du stream (6px) et les moments (4px min) ne sont PAS des cibles : l'interaction passe par
  la scrutation C4 (un tab-stop) — aucun clic requis par barre.

### 12.4 aria-live mesuré (inventaire complet et politique)
| Élément | Aujourd'hui | Politique refonte |
|---|---|---|
| `#interaction-log` | polite (verrouillé) | garder — événements initiés-utilisateur |
| `#world-interaction-status` | polite (verrouillé) | garder — idem |
| `#memory-search-results` | polite | garder — réponse à une recherche |
| `#memory-graph-selection` | polite (sr-only) | garder — sélection clavier |
| `#memory-graph-summary` | **polite — à retirer** | alimenté par le poll : le retirer (tests ok) |
| `#ignition-chart-summary` | aucun (verrouillé) | ne JAMAIS ajouter |
| `#horizon-task` | aucun (verrouillé) | ne JAMAIS ajouter |
| `#status-pill` | aucun | `role="status"` (change à Start/Pause/erreur seulement — fréquence humaine) |
| nouveaux (`#ignition-chart-selection`, société) | — | polite, UNIQUEMENT sur action utilisateur |
| Règle générale | — | **rien de ce que le poll de 350 ms écrit ne doit être live** |

### 12.5 Dialogs (futurs Reset-confirm + palette Ctrl+K)
- `<dialog>` natif + `showModal()` : focus piégé nativement, `Esc` natif, `::backdrop` stylé.
- Spec : `aria-labelledby` (titre) + `aria-describedby` (conséquence : « Reset efface la run en cours ») ;
  focus initial sur l'action NON destructive (« Annuler ») ; retour de focus à l'élément déclencheur à la
  fermeture (mémoriser `document.activeElement`) ; boutons ≥ 44px ; le fond `inert` est géré par
  showModal. Palette Ctrl+K : `role="dialog"` + input labellisé + liste `role="listbox"` avec
  `aria-activedescendant`, résultats annoncés par un compteur live polite (« 4 modules »).
- Raccourci : `Ctrl+K` documenté dans l'aide, ne pas capturer quand un champ texte a le focus… si :
  Ctrl+K est acceptable même depuis un champ (pattern standard) mais préserver `Esc`.

### 12.6 Tooltips (1.4.13 : hover + focus, dismissible, persistant)
- Bannir les `title=""` porteurs d'information primaire (gate, arousal, stream, toggles Settings —
  les `title` des toggles contiennent la SEULE explication des mécanismes !).
- Spec : composant tooltip unique : déclencheur focusable (l'élément ou un bouton « ? » ≥ 24px),
  ouverture au focus ET au hover, fermeture `Esc`, contenu dans un élément référencé par
  `aria-describedby`, survolable (pas de gap souris), sans délai de disparition au survol du tooltip.
  Les explications des toggles Settings migrent dans ce composant (texte réel conservé tel quel).

### 12.7 Tables/équivalents textuels pour chaque canvas
| Canvas | Équivalent aujourd'hui | Spec |
|---|---|---|
| `#ignition-chart` | résumé texte ✅ (verrouillé) | + sélection clavier C4, + source majoritaire dans le résumé |
| `#memory-graph` | listes sr-only nœuds/arêtes ✅ (verrouillées) + résumé | conserver ; diff keyé |
| `#world-canvas` | rien (statut d'injection seulement) | table « objets visibles » §6 + détail de cellule |
| `#society-canvas` | relations texte partielles | cartes agents + relations complètes (trust+familiarity) + fil messages §7 |
| `#lab-chart` | rien | `#lab-chart-summary` + min/max/fenêtre §10 |
| `#circadian-dial` | aria-label statique | `role="meter"` + `aria-valuetext` §11 |
| `#horizon-stream` (div) | synthèse aria-label ✅ | + liste sr-only par moment §4 |

### 12.8 Contrastes graphiques 3:1 (1.4.11) et texte 4.5:1 (1.4.3) — mesures effectuées
Ratios calculés (formule WCAG, arrondi 2 déc.) sur les paires réellement utilisées :

**Thème sombre** — texte sur `--bg-2` : ink 14,6 ✅ · ink-soft 7,0 ✅ · **ink-faint 3,45 ❌ (utilisé
partout en 8,5–9,5px)** · accent 8,0 ✅ · pos 6,6 / neg 4,5 / cool 6,2 / curio 6,0 ✅.
Graphiques sur `--bg-inset` : accent 8,5 ✅ · accent-soft 4,2 ✅ · **ink-ghost 1,78 ❌ (fills par
défaut des meters/gate/coalitions)** · pos 7,0 / neg 4,8 / cool 6,6 / curio 6,4 ✅ · line 1,3
(hairlines décoratives, toléré).

**Thème clair** — texte sur `--bg-2` : ink 13,6 ✅ · ink-soft 6,6 ✅ · **ink-faint 3,36 ❌** ·
accent 4,8 ✅ · **accent-soft 2,72 ❌ (focus actuel !)**.
Graphiques sur `--bg-inset` : accent 3,9 ✅ · **accent-soft 2,22 ❌** · **ink-faint 2,74 ❌** ·
pos 3,6 / neg 3,9 / cool 3,9 / curio 4,2 ✅.

**SOURCE_COLORS sur `--bg-inset`** : sombre — tout ≥ 3,6 ✅ sauf néant ; clair — **perception 1,59,
memory 1,69, inner_speech 1,44, social 1,98, goal 2,00, wandering 1,95, imagination 2,12, language 2,07,
self 2,31, emotion 2,50 : ÉCHEC généralisé** → palette clair dédiée C1 (valeurs corrigées fournies,
toutes ≥ 3,0 mesurées).

**Corrections chiffrées** (à re-mesurer après intégration) :
- `--ink-faint` : sombre `#6f6959` → **`#918a79`** (5,5:1 bg-2 ; 5,3:1 bg-3) ; clair `#8b8374` →
  **`#6e6759`** (5,0:1 bg-2 ; 5,3:1 bg-3). Réservé aux textes ≥ 10px ; les gravures décoratives non
  textuelles peuvent garder l'ancienne teinte via une variable séparée `--engrave`.
- `--focus` (nouveau) : sombre `= --accent` ; clair `#7a5a1e` (§12.2).
- Fills subliminaux : `--ink-ghost` → `--ink-soft` (7,5:1 sombre) partout où le fill est porteur de sens.
- Les teintes adjacentes de C1 (perception vs inner_speech 1,1:1 entre elles) ne sont PAS distinguables
  entre elles : c'est accepté car la couleur n'est jamais le seul canal (légende, texte, position).

### 12.9 Information jamais couleur-seule — points restants
- Timeline sources : légende + contour/coiffe §4. Monde/société : formes par kind §6-§7.
- Coalition gagnante : badge texte §1. Aperture : glyphes + mots d'état §2.
- Q-values négatives (`.q-fill.neg`, rouge) : la valeur signée est déjà en texte ✅.
- Verdicts audit FAITHFUL/CONFAB : déjà des mots ✅ (couleur en renfort).
- Statut pill : mot « Running/Paused » ✅ + point coloré décoratif.

### 12.10 Zoom 200 % / reflow 320px (1.4.4, 1.4.10)
- Breakpoints existants corrects (720px → 1 colonne ; metric-grid 2 col ≤ 560px ; tabs interventions
  `overflow-x:auto` ✅ ; masthead compact mobile ✅).
- ❌ Tailles en px partout (8,5–14px) : passer les tailles de texte en `rem` (base 14px→0.875rem…) pour
  respecter le zoom texte-seul ; plancher effectif 10px.
- ⚠️ Colonnes fixes `124px` (coalitions §1 : devient table fluide `minmax(96px, 18ch)`) et `110px`
  (q-rows, traits) : `minmax`.
- ⚠️ Texte in-canvas : ne suit que le zoom page (flou avant C3) — post-C3 il est net ; le texte
  d'axes/légendes migré en HTML (§3, §10) suit le zoom texte-seul.
- Vérifier à 320 CSS px : `.horizon-stream` (grid auto-columns minmax(4px,1fr)) ✅ ; le fil
  d'interventions `min-width:150px` par tab + overflow ✅.

### 12.11 prefers-reduced-motion — inventaire des animations actuelles et politique
Kill-switch global existant (CSS:1300-1303 : `animation: none !important; transition-duration: 0.001ms
!important` + neutralisation explicite horizon) : **conserver** (les `transitionend` continuent de tirer,
aucun code ne casse).

| Animation | Où | Sous reduced-motion | Politique refonte |
|---|---|---|---|
| `pulse` 2,6s infinite | lampe ignition (CSS:424-429) | tuée ✅ | ne pulser QUE pendant `ws.ignited` réel ; reduced → état statique forme+texte (§2) ; guard JS `matchMedia` en plus du CSS |
| `breathe` 1,8s infinite | pill-dot Running (CSS:189) | tuée ✅ | garder (état, discret) ; reduced → point plein statique |
| `rise` 0,55s entrée + délais | tous les `.panel` (CSS:359-368) | tuée ✅ | garder (une fois au chargement) |
| `flashIn` 0,5s | `.moment-quote.flash` (app.js:333) | tuée ✅ | guard JS : ne pas poser la classe si reduced |
| transitions largeur 0,4–0,5s | tous les meters/fills/gate/co-fill | quasi-instantanées ✅ | **les retirer du chemin du poll** : elles réaniment en continu à 350 ms (coût + vection) ; ne transitionner que si le tick change, jamais plus vite que 240 ms |
| `height 0.4s` `.spark`, `0.22s` `.moment` | stream + timeline | tuées ✅ | supprimées en nominal aussi (§4) — barres immuables une fois posées |
| `left 0.4s` threshold/baseline/ig-thresh | marqueurs | tuées ✅ | Aperture : 240 ms tick-gated (§2) |
| fold masthead / framing 0,35–0,45s ; thème 0,4–0,5s | scroll + toggle thème | quasi-instantanés ✅ | garder |
| `stroke-dashoffset 0.6s` | jauges HOT (CSS:788) | tuée ✅ | disparaît avec les bullets (§11) |

Aucune animation n'est indispensable à la compréhension : chaque état animé a (ou reçoit, §2/§4) un
équivalent forme+texte — conforme 2.3.3 par construction, et 2.2.2 sans objet (rien ne clignote > 3/s ;
`pulse` 2,6s < 1 Hz mais on le gate quand même).

---

## 13. Performance de rendu

### 13.1 Ce que le polling de 350 ms fait aujourd'hui (mesuré dans le code)
**Réseau — 11 requêtes par poll** (~31 req/s à 350 ms) : `performRefreshAll` (app.js:1554-1642) tire en
parallèle `state`, `metrics`, `agent/consciousness`, `agent/workspace`, `agent/stream`,
`agent/self-model`, `agent/memory?limit=20`, `agent/introspection`, puis séquentiellement
`society/language` (app.js:1631), `metrics/history?limit=200` (via `refreshLabChart`, app.js:1634 —
**200 lignes re-téléchargées à chaque poll**), `society` (app.js:1637). Le graphe mémoire est, lui,
correctement throttlé (≥ 20 ticks, verrouillé).

**Rebuilds innerHTML intégraux à chaque poll** (pires d'abord) :
1. `renderHorizon` (app.js:997-1016) — 6 cartes `article` regénérées par concat de chaînes + le
   `#horizon-task`, même si RIEN n'a changé ;
2. `renderStream` (468-485) — 48 barres reconstruites + `scrollLeft = scrollWidth` (reflow forcé) ;
3. `renderHorizonStream` (1135-1169) — 48 spans reconstruits ;
4. `renderMemories` (662-677) — 20 lignes + copie inversée du tableau ;
5. `refreshLearning` (1451-1529) — q-bars + 3 traits ; `renderSelfModel` (577-610) ; `renderIntrospection`
   (624-635) ; `renderWorkingMemory` (642-660) ; `renderLanguage` chips (1390-1402) ;
   `refreshSocietyLanguage` dictionnaire (1420-1440) ; `renderRelations` (2293-2300).
6. **Canvas redessinés intégralement chaque poll** : monde, ignition-chart, lab-chart, société (+ dial
   circadien via `refreshDeep`). Chaque `drawX` relit ~8 `cssVar()` (getComputedStyle).
7. `canvas.setAttribute("aria-label", …)` à chaque draw (ignition, memory-graph) même à texte identique.

### 13.2 Spec : ordonnanceur rAF + dirty-flags
- **Store** : les réponses du poll écrivent dans un état central `S[endpoint] = {payload, tick, hash}` ;
  `hash` = clé bon marché déterministe (tick + longueurs + derniers scalaires — PAS Math.random,
  contrat §0). Si `hash` inchangé → aucun marquage.
- **Dirty-flags** : chaque vue déclare ses dépendances (`workspace-table ← agent/workspace`,
  `aperture ← agent/workspace + state.metrics.is_sleeping`, …). Écriture → `dirty.add(viewId)`.
- **Flush unique par frame** : un seul `requestAnimationFrame` en vol ; le callback draine `dirty`,
  appelle chaque `render*/draw*` UNE fois, dans l'ordre DOM. Les gardes verrouillées (génération, tick)
  restent DANS `performRefreshAll` AVANT toute écriture au store — le scheduler ne peut donc jamais
  repeindre un état périmé (contrats §0 respectés : les fonctions gardent leurs noms et restent appelées).
- **Écritures DOM keyées** : lignes/barres/chips keyées par id stable (source, tick, node.id, meaning) ;
  mise à jour `textContent`/`style.width`/attributs en place ; ajout/retrait au diff seulement. Plus
  aucun `innerHTML = ""` dans le chemin du poll.
- `cssVar()` : mémoïsé par thème (invalidé au toggle + `matchMedia` thème) — une lecture de
  `getComputedStyle` par variable et par thème, pas 40 par frame.
- `renderStream.scrollLeft` : seulement si l'utilisateur est déjà « collé » au bord droit
  (`scrollLeft ≥ scrollWidth − clientWidth − 8`).

### 13.3 Spec : IntersectionObserver hors-écran
- Un `IntersectionObserver` unique (`rootMargin: "200px"`, threshold 0) observe les 21 panneaux ;
  `visible.set(panelId, bool)`.
- Panneau invisible → (a) ses vues restent marquées dirty mais **ne sont pas rendues** ; (b) ses fetchs
  dédiés sont suspendus : `society`, `society/language`, `metrics/history` (lab), `agent/memory/graph`
  ne partent que si leur panneau est visible (le throttle 20-ticks du graphe reste inchangé par-dessus).
- Ré-entrée → rendu immédiat depuis le store (données du dernier poll) puis reprise du cycle.
- Les 8 GET « cœur » restent inconditionnels (ils alimentent le héros/statut, toujours visibles en haut
  de page) mais passent aux cadences ci-dessous.

### 13.4 Spec : cadences réseau
| Groupe | Endpoints | Cadence |
|---|---|---|
| chaud | `state`, `agent/workspace`, `agent/stream` | chaque poll (350 ms) |
| tiède | `metrics`, `agent/consciousness`, `agent/self-model`, `agent/memory`, `agent/introspection` | 1 poll sur 2, et seulement si le tick a avancé |
| froid | `society`, `society/language`, `metrics/history` (lab) | 1 poll sur 5 ∧ tick avancé ∧ panneau visible |
| exclusif | `agent/memory/graph` | inchangé (throttle 20 ticks verrouillé) |

Effet attendu : ~31 req/s → ~10 req/s en régime courant, ~3 req/s panneaux bas hors écran ; en pause,
zéro rendu (le poll s'arrête déjà, app.js:1697-1698 — inchangé).

### 13.5 Spec : caps de séries (état : sains — à conserver)
`HIST = 60` (sparklines), `STREAM_MAX = 48`, `IGNITION_HISTORY_MAX = 120` (+ dédup par tick),
`memory/graph limit=60&edges=3` (verrouillé), `metrics/history?limit=200`, log d'interventions cap 40
(app.js:1734). Ajouter : fil des messages société cap 48, fil des échanges langage cap 5.

### 13.6 Spec : DPR / resize sans fuite
Helper C3 : un `ResizeObserver` + un listener `matchMedia(resolution)` par canvas, créés UNE fois à
l'init dans une `WeakMap` — jamais dans un chemin de dessin ; resize → dirty-flag → le flush rAF
redessine ; dpr plafonné à 2 ; `disconnect()` inutile en single-page mais le helper l'expose (hygiène
checkpoint-load/reset : les canvas ne sont jamais recréés, donc aucun observer orphelin possible).

---

## Résumé (5 problèmes les plus graves → 3 specs prioritaires)

1. **Thème clair hors-la-loi** : SOURCE_COLORS à 1,4–2,5:1, focus `accent-soft` 2,2:1, `--ink-faint`
   3,4:1 sur des labels de 9px — échecs 1.4.3/1.4.11 systémiques (corrections chiffrées fournies, §12.8).
2. **Ligne de seuil du workspace fausse ET fragile** : seuil d'`ignition_score` superposé à des parts
   softmax via un `calc()` couplé aux pixels de la grille (§1).
3. **Réseau/DOM dilapidés** : 11 requêtes/350 ms (dont 200 lignes d'historique re-téléchargées à chaque
   poll) et ~10 rebuilds `innerHTML` complets par poll, canvas non-DPR flous partout (§13, C3).
4. **Information couleur-seule** : sources de la timeline sans légende (avec `aria-label` par-barre
   inertes sous `role="img"`), kinds du monde/société en cercles teintés identiques (§4, §6).
5. **Live regions et tooltips mal calibrés** : `#memory-graph-summary` live sous poll, informations
   primaires en `title` souris-seule, `/society/messages` et `agents{}` jamais exploités (§7, §12.4-6).
Specs prioritaires : **(a)** Ignition Aperture SVG `role="meter"` avec géométrie/états/reduced-motion
exacts (§2) ; **(b)** conventions transverses C1–C5 (palette thémée, meter unique, canvas HiDPI, scrutation
clavier, états vides honnêtes) ; **(c)** ordonnanceur rAF + dirty-flags + IntersectionObserver + cadences
réseau, sous les gardes pytest existantes (§13).
