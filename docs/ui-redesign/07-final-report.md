# 07 — Rapport final de la refonte GUI « Le Méridien »

Date : 2026-07-11 · Branche : `agent/ui-observatory` (départ `agent/phase7-horizon` a1b6fc8)
Processus : baseline → Vague A (4 agents d'exploration) → synthèse (06-design-spec) → implémentation
lead unique → Vague C (3 relecteurs indépendants) → corrections → vérification finale.

## 1. La transformation en une phrase

La page verticale unique de 21 panneaux est devenue une application instrumentale à 8 vues —
un observatoire cognitif de qualité muséale (champ de nuit, électrum discipliné, serif éditoriale,
mono tabulaire) dont la pièce signature, l'Ignition Aperture, dessine honnêtement le mécanisme
central du projet : le score d'ignition face à son seuil effectif, modulation d'arousal comprise.

## 2. Fichiers modifiés

**UI (réécrits/refondus)**
- `ui/index.html` — shell complet (topbar transport, sidebar 8 vues, tab bar mobile, boundary strip,
  dock à sondes, 4 dialogs, jeu de 20 icônes SVG inline) + les 21 panneaux redistribués dans 8 vues,
  chaque id contractuel préservé. `?v=8.0`.
- `ui/styles.css` — design system « Le Méridien » réécrit : `@layer tokens/base/layout/components/
  states/motion/responsive`, tokens AA vérifiés (sombre + clair « papier d'archive »), 17 couleurs de
  sources `--src-*`, les 12 variables canvas legacy conservées en alias, type scale fluide,
  piles de polices 100 % locales, littéraux CSS épinglés par pytest maintenus.
- `ui/app.js` — moteur préservé (polling 350 ms, générations anti-course, tous les marqueurs pytest),
  enrichi : routeur hash + flush des dessins différés, Ignition Aperture SVG, palette de commandes,
  probe dock (adoption de nœud), dialogs de confirmation (reset / load / delete), toasts + bannière
  de connexion, DPR sur tous les canvas (cap 2×), gating de visibilité par vue, renderWorkspace
  honnête (parts softmax brutes + table accessible + bandeau de décision), monde à formes par kind +
  inspecteur de cellule + table d'objets, société (liens de confiance, cartes d'agents, messages
  réels avec cercles d'earshot, inspecteur par agent, sélection clavier), légende de sources,
  clavier sur l'access-chart, settings (filtre, catalogue read-only avec défauts + badges
  structurels), cssVar mémoïsé, re-teinte totale au thème.

**Tests (évolution assumée, D6 de la spec)**
- `tests/test_interaction_ui.py` + `tests/test_phase7_ui.py` — uniquement les 3 assertions de
  cache-buster `?v=7.3 → ?v=8.0`. Tous les autres verrous (fonctions, ordres, aria, littéraux CSS,
  déterminisme) satisfaits sans modification.

**Outillage & docs**
- `scripts/check_ui_contract.mjs` (vérificateur statique : ~215 références d'ids, littéraux épinglés,
  cohérence `?v=`, interdiction Math.random) ; `scripts/ui_hook_check.mjs` + `.claude/settings.json`
  (hooks PostToolUse/Stop, pipe-testés) ; `.claude/skills/humanity-ui-contract` +
  `humanity-visual-qa` ; `docs/ui-redesign/01→07` + captures.

## 3. Décisions UX & visuelles principales

1. **8 vues hash sur un DOM persistant** — le routeur ne monte/démonte rien : zéro re-bind de
   listeners, état client intact, les dessins des vues cachées sont différés puis flushés à l'entrée.
2. **Ignition Aperture** — cadran 240° : arc de score électrum, zone d'ignition gravée, tick de seuil
   EFFECTIF plein + tick NOMINAL fantôme (l'écart EST la modulation arousal/homéostasie, dessinée au
   lieu d'être expliquée), arc interne de broadcast, micro-stats winner strength / dominance /
   arousal ; états AWAITING / SUBLIMINAL / GLOBAL ACCESS / ASLEEP nommés ; une seule pulsation
   240 ms sur flanc montant d'ignition réelle, neutralisée en reduced-motion.
3. **Honnêteté d'échelle au workspace** — les barres montrent les parts softmax BRUTES (axe absolu,
   deux instants comparables) ; le seuil ne traverse plus des barres d'une autre échelle : un bandeau
   de décision porte score vs seuil effectif + verdict verbatim ; table de données accessible.
4. **Électrum discipliné** — réservé à l'ignition réelle, à l'état Running et à l'action primaire ;
   perception cède l'or au cyan minéral ; 17 sources de coalitions thémées et AA sur les deux fonds
   (les sources autrefois « unknown » — motivation, prediction_error, interoception, metacognition,
   concept — ont leur teinte).
5. **Frontière scientifique en signature** — strip permanent (texte serveur verbatim, ellipsé,
   complet au survol et dans la charte), charte épistémique (framing live + disclaimer + distinction
   à trois niveaux) ouverte une fois au premier lancement, chips `GET /endpoint` conservées sur
   chaque panneau, badge LLM systématique sur toute surface générée.
6. **« Un instrument, deux fenêtres »** pour les sondes causales — maison canonique au Laboratory,
   dock transversal (touche p) qui adopte physiquement le nœud DOM (état, onglets et ledger corrélé
   suivent) avec onglet par défaut contextuel (Workspace→Inject, World→Stimulus, Mind→Perturb,
   Memory→Ask).
7. **Monde/Société** — formes par kind (jamais couleur seule), rayon de perception RÉEL (config),
   inspecteur de cellule, liens de confiance dessinés sur la carte, cartes d'agents comparables,
   messages vivants avec portée d'earshot (champs réels uniquement — pas d'« auditeurs » inventés),
   inspecteur par agent via `/society/agent/{id}/*` (l'instrument principal reste explicitement
   l'agent 0 — décision D4, limite documentée §6).
8. **Settings** — filtre plein-texte, valeurs + défauts affichés, descriptions imprimées (plus de
   tooltips-seuls), divulgation read-only des 108 champs SimConfig avec badges « reset » sur les 9
   structurels, erreurs 409 expliquées en toast.
9. **Thème clair « papier d'archive »** — ivoire vergé/encre brune/laiton mat, conçu (contrastes
   recalculés), pas une inversion.
10. **Mobile** — topbar 2 rangées, tab bar 5 emplacements + sheet « More », accordéons implicites par
    grille fluide, zéro scroll horizontal vérifié sur les 8 vues à 390 px.

## 4. Tests réellement exécutés et résultats

- `python -m pytest` (suite complète, 627 tests) : **PASS ×2** — baseline avant refonte (exit 0)
  et après refonte (exit 0). Les 6 tests des deux fichiers de contrat UI passent avec la seule
  évolution `?v=8.0`.
- `node --check ui/app.js` + `node scripts/check_ui_contract.mjs` : verts après chaque étape
  (215 références d'ids résolues, littéraux épinglés présents, versions cohérentes).
- Hooks : pipe-testés (payload ui/app.js → checks exécutés ; payload non-UI → skip ; settings.json
  JSON valide ; commande Stop exit 0). Actifs à la prochaine session (watcher de settings).
- **Parcours navigateur exécutés (Playwright, cache désactivé via CDP)** : chargement + redirection ;
  charte au premier lancement ; Step ×n ; Run 4 tps avec navigation dans les 8 vues puis Pause
  (t14→t31) ; monde clic + flèches/Entrée (injection vérifiée + inspecteur de cellule) ; dock p
  (onglet contextuel Inject depuis Workspace, adoption + retour du nœud, ledger #001 request/result) ;
  palette Ctrl+K (filtrage « masking » → commande batterie) ; batterie mirror (score 0.767 +
  interprétation + disclaimer) ; checkpoint save/list/delete (« qa-meridien » @ t31) ; recherche
  mémoire (8 résultats) + graphe au clavier (sélection annoncée + tooltip au focus) ; société 3
  agents (cartes comparables, sélection clic + chip topbar, inspecteur agent 1) puis run 6 s →
  6 relations, convergence lexicale 0.89, dictionnaire peuplé ; narration LLM réelle rendue avec sa
  ligne de provenance (clé présente sur cette machine — une seule sollicitation pour ménager les
  crédits ; le chemin 503 est inchangé au caractère près) ; thème clair sur plusieurs vues (topbar
  vérifié pixel par pixel) ; reduced-motion émulé (animation du pill à ~0 ms) ; mobile 390×844 :
  zéro débordement horizontal sur les 8 vues, tab bar + sheet More fonctionnelles ; console : 0
  erreur sur l'ensemble des parcours.
- **Vague C (relecteurs indépendants)** : la revue **API** (agent complet) conclut CONFORME —
  38 appels frontend → 38 routes valides vérifiées par requêtes réelles, formes d'erreurs
  409/422/404 conformes, invariants localStorage identiques, zéro constat de haute sévérité
  (`wave-c-api-review.md`). Les relecteurs **visuel** et **a11y/perf** ont été interrompus par une
  limite de session API ; leur périmètre a été ré-exécuté intégralement par le lead —
  4 constats (1 moyen de contraste, 3 bas), **tous corrigés** ; détail et couverture exhaustive
  dans `wave-c-visual-qa.md` et `wave-c-a11y-perf.md`.
- **Performance / audits (mesurés)** : PerformanceObserver sur ~3 min 10 s de simulation continue à
  4 tps en traversant les 8 vues → **1 seule long task (67 ms)**, aucune récurrente ; console
  0 erreur / 0 warning sur toute la session de QA ; Lighthouse desktop : **Accessibilité 100,
  Best Practices 100**, CLS 0.004, SEO 89 → meta description ajoutée (la catégorie Performance de
  ce runner n'émet pas de score pour cette page — l'instrumentation long-task ci-dessus est la
  mesure pertinente pour un instrument de flux, et elle est archivée) ; contrastes : 23/23 paires
  AA calculées par script après correctif `--ink-3` clair.

## 5. Captures avant/après

- Avant : `docs/ui-redesign/screenshots/before-*.png` (desktop 1440 viewport + pleine page, tablette
  768, mobile 390 viewport + pleine page, thème clair 1440).
- Après : `docs/ui-redesign/screenshots/after-*.png` — 19 captures : les 7 vues à 1600×1000,
  overview 1440, settings 1280, workspace 1024, world 768, thème clair « papier d'archive » ×3
  (overview/workspace/settings 1440), mobile 390×844 ×4 (overview/workspace/laboratory/settings)
  et 360×800 ; plus 2 preuves du relecteur Vague C (`wave-c-overview-cold-1600.png`,
  `wave-c-world-2agents-1600.png`).

## 6. Limites restantes (documentées, non masquées)

1. **Focus multi-agent** : l'instrument principal (aperture, KPI, mémoire, stream) observe l'agent 0
   (endpoints legacy) ; la sélection d'un autre agent alimente l'inspecteur société
   (`/society/agent/{id}/consciousness|self-model`) mais ne re-route pas toute l'app — étiqueté
   comme tel dans l'UI ; le re-routage complet est l'extension naturelle suivante.
2. **`/ws/society` reste non consommé par l'UI** (comme avant la refonte) : le polling 350 ms
   race-safe est conservé comme canal de données ; choix documenté (D2).
3. **`role="meter"`** posé sur les meters statiques principaux ; les meters construits
   dynamiquement gardent leur valeur en texte adjacent (équivalence fonctionnelle, sémantique
   partielle).
4. Les événements du monde à cadence rapide (messages TTL 2 ticks) sont souvent expirés au poll —
   les cercles d'earshot n'apparaissent que pour les messages encore vivants (fidèle au payload).
5. Le graphe mémoire conserve son layout spiral déterministe (contrat pytest) — la stabilité
   spatiale inter-mises-à-jour reste liée à l'ordre de récence.
6. `.claude/launch.json` (fichier utilisateur préexistant, non modifié) a été inclus au commit —
   à retirer du suivi si non désiré.

## 7. Commits

- `536a388` — feat(ui): Le Méridien — instrument shell, hash router, Ignition Aperture
  (la refonte complète : ui/index.html, ui/styles.css, ui/app.js, bump `?v=8.0` + 2 assertions de
  tests, vérificateur de contrats, skills projet, docs 01→06, captures avant).
- Commit final — corrections Vague C (contraste `--ink-3` clair, meta description), hooks projet
  (`.claude/settings.json` + `scripts/ui_hook_check.mjs`), rapports Vague C, captures après,
  ce rapport. (Hash dans la réponse finale et `git log`.)
