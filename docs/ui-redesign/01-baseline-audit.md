# 01 — Baseline audit (avant refonte)

Date : 2026-07-11 · Branche : `agent/ui-observatory` (départ `agent/phase7-horizon`, a1b6fc8)
Serveur d'audit : `PORT=8123 python run.py` · pytest baseline : **627 tests verts** (exit 0)
Captures : `docs/ui-redesign/screenshots/before-*.png` (1440×900 viewport + pleine page, 768×1024, 390×844 viewport + pleine page, thème clair 1440).
Console navigateur après chargement + 14 ticks : **0 erreur, 0 warning**.

## État des lieux

L'UI actuelle (« L'Observatoire », ébonite & laiton, v7.3) est **une seule page verticale de 17 panneaux**
(~899 lignes de HTML), pilotée par un `app.js` monolithique de 2 849 lignes (IIFE, polling HTTP 350 ms,
8 endpoints par cycle + société + langage + lab). Elle est fonctionnellement riche et déjà honnête
scientifiquement (framing permanent, disclaimers par panneau, sources `GET /endpoint` affichées).

## Problèmes par catégorie

### 1. Architecture d'information
- **Pile unique de 17 panneaux** : la hiérarchie est l'ordre du scroll. Le Laboratory (batteries,
  scénarios, checkpoints, LLM, coverage, training) est un fourre-tout de 100 lignes de HTML à lui seul.
- Aucune navigation : pas de sommaire, pas d'URL adressable par section, pas de raccourci clavier global.
- Le panneau Settings mélange 9 sliders + 6 groupes de toggles sans recherche ni explication des unités,
  sans distinction hot-apply / reset requis (le backend la connaît : 409 `ConfigRequiresReset`).
- Les interventions expérimentales (5 sondes causales) sont à mi-page, loin du monde et du workspace
  qu'elles perturbent.

### 2. Densité et lisibilité
- Tous les panneaux ont le même poids visuel (même carte, même bordure) : « mur de cartes ».
- Les tuiles Indicators affichent 11 métriques identiques sans unités ni plages ; sparklines auto-échelonnées
  sans min/max affichés.
- Beaucoup de micro-texte gris (`--ink-faint` #6f6959 sur #12110e ≈ 3,4:1) sous le seuil AA pour du texte normal.

### 3. Navigation et parcours
- Comprendre « où en est l'instrument » exige de scroller ~7 000 px (pleine page 1440) ; le moment conscient,
  le monde et la société ne sont jamais co-visibles.
- Aucun état de navigation persistant ; le masthead sticky se compacte au scroll (`body.is-scrolled`) mais ne
  donne accès à rien d'autre que le transport.

### 4. Accessibilité
- Bon socle existant (verrouillé par pytest) : canvas monde/graphe mémoire focusables + clavier, listes sr-only
  du graphe, `aria-live` mesuré, résumés textuels des charts. À préserver intégralement.
- Manques : pas de skip-link, pas de landmarks `<nav>`, hiérarchie de titres plate (17 `<h2>` sans structure),
  focus visible inégal, cibles < 44 px (boutons `.micro` des checkpoints), information parfois couleur-seule
  (objets du monde, timeline des sources), pas de `prefers-reduced-motion` (flash du moment, pulse de la lampe
  d'ignition), zoom 200 % non conçu.
- Le grand disclaimer est un paragraphe d'en-tête ; pas de panneau développable dédié à la frontière scientifique.

### 5. Visualisation
- **Ignition gate** : simple barre horizontale de 140 px dans le héros — le mécanisme central du projet
  (score vs seuil effectif) mérite l'élément signature, pas un track de 6 px.
- **Compétition GWT** : bars triées mais la ligne de seuil est positionnée par un `calc(134px + …)` fragile,
  couleur unique quel que soit la source, pas de table accessible.
- **Access dynamics** : canvas 720×260 non-DPR (flou en HiDPI), pas de zones ignited/subliminal, tooltips absents.
- **Monde/Société** : canvas 560×560 non-DPR, différenciation food/hazard/tool/curio par couleur seule,
  pas de panneau de détail de cellule ; société = disques numérotés + liste texte des relations, messages
  (`/society/messages`) jamais affichés.
- **Langage** : dictionnaire en lignes de texte ; pas de matrice sens×agents, la polysémie n'est pas visible.
- **Lab chart** : polylignes sans axes, sans légende, sans unités, sans état vide explicite.
- **Jauges HOT** : trois demi-cercles répétés — famille à remplacer par des meters comparables.

### 6. Performance
- Chaque poll (350 ms) reconstruit par `innerHTML` : stream (48 nœuds), coalitions, mémoires (20 lignes),
  introspection, self-model, société, dictionnaire langage — même quand rien n'a changé.
- Tous les canvas sont redessinés à chaque poll même hors viewport ; aucune utilisation de rAF,
  d'IntersectionObserver ni de dirty-flags.
- Les canvas ne tiennent pas compte du devicePixelRatio.
- Points forts à conserver : sérialisation des refresh (`refreshInFlight`/`refreshQueued`), générations
  anti-course (`horizonGeneration`), rejet des ticks obsolètes, throttle du graphe mémoire (≥ 20 ticks).

### 7. Cohérence esthétique
- Direction « ébonite & laiton » réussie mais mono-accent : le laiton signale à la fois l'ignition (rare,
  précieux) et n'importe quel bouton primaire ou fill de meter (fréquent) — le signal est dilué.
- Le thème clair est une transposition (mêmes surfaces, valeurs inversées), pas un « papier d'archive » conçu.
- Icônes quasi absentes (un seul glyphe de thème) ; numérotation `01`-`05` des panneaux sous-exploitée.

## Contrats à ne pas casser (résumé — détail dans 02-contract-map.md)
- ~80 ids DOM consommés par app.js ; sélecteurs `.panel-config input[data-flag]`, `.slider-row[data-key]`,
  `.panel-hero.is-ignited`, variables CSS lues par les canvas (`--accent`, `--pos`, `--neg`, `--cool`,
  `--curio`, `--line`, `--ink*`, `--bg-inset`, `--mono`).
- `tests/test_interaction_ui.py` + `tests/test_phase7_ui.py` : ids, aria exacts, sélecteurs CSS littéraux,
  noms de fonctions JS, marqueurs de race-safety, `?v=` compté, `Math.random` interdit.
- localStorage : `humanity.settings` (config persistée, fusion SETTINGS_DEFAULTS), `cws-theme`.
- Fonctionnement complet sans clé LLM (503 propres sur 8 endpoints LLM).

## Décisions de cadrage issues de l'audit
1. **app.js reste un fichier unique** (les tests pytest greppent ses définitions) — restructuré en sections,
   enrichi (routeur, palette, aperture) sans casser les marqueurs.
2. Les **noms de variables CSS existants sont conservés** comme couche sémantique (nouvelles valeurs) pour
   ne pas toucher au code canvas.
3. La **navigation devient le chantier n°1** : 8 vues hash, shell topbar+sidebar, palette Ctrl+K.
4. Le **polling reste le canal de données** (éprouvé, race-safe) ; `/ws/society` reste disponible côté
   backend, non consommé par l'UI (comme aujourd'hui) — décision documentée.
5. Bump du cache-buster `?v=7.3 → ?v=8.0` avec mise à jour des deux assertions de tests correspondantes
   (seule évolution de tests légitime identifiée à ce stade, avec les sélecteurs de masthead si le pattern change).
