# 06 — Design spec (source de vérité de la refonte)

Synthèse du lead à partir de : 01-baseline-audit, 02-contract-map (contrats), 03-information-architecture
(adoptée avec cadrages ci-dessous), 04-visual-directions (direction retenue + tokens), 05-dataviz-a11y
(specs de visualisation). En cas de conflit entre documents, **cette spec tranche** ; en cas de conflit
avec 02-contract-map, **les contrats gagnent toujours**.

## 0. Décisions de cadrage (arbitrages du lead)

| # | Décision | Justification |
|---|---|---|
| D1 | `app.js` reste UN fichier, restructuré par bannières de sections ; aucun module ES. | pytest greppe la source (fonctions, ordres, littéraux) — 02 §3. |
| D2 | Le polling HTTP reste le canal de données ; `/ws/society` reste non consommé. | Structure race-safe éprouvée et verrouillée (générations, single-flight). Documenté comme choix. |
| D3 | Navigation par routes hash `#/view` avec **toutes les vues montées dans le DOM** ; le routeur toggle `hidden` + gère focus/scroll. Pas de montage/démontage. | Zéro re-bind de listeners (fuite impossible), ids uniques préservés, état client intact. |
| D4 | L'instrument reste focalisé **agent 0** (endpoints legacy). La société gagne un **inspecteur par agent sélectionné** (`/society/agent/{id}/consciousness|self-model`) qui n'altère pas le reste. | Suivi multi-agent complet = re-routage global des GET ; risque de mélange de focus (dés-honnête). Limite documentée au rapport final. |
| D5 | Le panneau interventions = **un seul nœud DOM**, maison canonique dans #/laboratory ; le « Probe dock » (raccourci `p`) **adopte le nœud** dans un drawer et le rend à sa maison à la fermeture. | « Un instrument, deux fenêtres » (03 §1.17) sans dupliquer ids ni état. |
| D6 | Bump cache-buster `?v=7.3 → ?v=8.0` + mise à jour des 3 assertions pytest correspondantes ; conservation de `body.is-scrolled` (compaction topbar) et des littéraux CSS épinglés. | Seule évolution de tests nécessaire ; le reste des contrats est satisfait tel quel. |
| D7 | Corrections d'honnêteté embarquées : options mortes du select lab retirées (séries réelles uniquement), rayon de perception lu depuis `GET /config` (plus de 3 codé en dur), re-teinte de TOUS les canvas au toggle thème, couleurs de sources thémables (`--src-*`). | Bugs/dettes relevés par 02 (§2.1, pièges 11/14). |
| D8 | Réglages : les 41 contrôles actuels (9 sliders + 32 flags) restent les seuls mutateurs ; le reste de SimConfig devient une **divulgation lecture seule** (valeur + défaut + badge structurel). | Zéro nouvelle surface de mutation à QA ; recherche et compréhension totales quand même. |
| D9 | Sous-routes `#/view/section` supportées (scroll + highlight) ; breadcrumb 2 niveaux max. | 03 §3.1 simplifié (pas de scrollspy continu). |
| D10 | Langue UI : anglais (existant). Textes serveur (framing, disclaimers) rendus verbatim, jamais paraphrasés. | Contrat d'honnêteté. |

## 1. Shell applicatif

```
body
├─ a.skip-link → #main
├─ svg#icon-defs (symbols : 8 vues + 12 actions, stroke currentColor)
├─ header.topbar
│   ├─ .brand (marque SVG + « Humanity ») + span.topbar-view (vue courante / breadcrumb)
│   ├─ #status-pill (#status-label) · chip tick « t N » (#topbar-tick) · chip agent (#topbar-agent, société)
│   └─ .transport : .transport-buttons (#btn-step #btn-start #btn-pause #btn-reset) +
│      label.tps-field (#input-tps) · #btn-probe (dock) · #btn-palette (Ctrl+K) · #btn-theme
├─ nav.sidebar (#app-nav, aria-label="Views") : 8 items (icône+libellé+aria-current) ;
│   pied : vignette frontière + #btn-nav-collapse ([)
├─ main#main.views : 8 × section.view[data-view][hidden] — chaque vue = grille de panneaux
├─ footer.boundary-strip : phrase courte statique + #footer-disclaimer (texte serveur, 1 ligne,
│   ellipsé, title=complet) + bouton « Framing & sources » → charte
├─ aside#probe-dock (drawer droit ; adopte #experimental-interventions)
├─ dialog#charter (charte épistémique : #framing-text (live), disclaimer complet, 3 niveaux, lien coverage)
├─ dialog#command-palette (input combobox + listbox résultats)
├─ dialog#confirm-dialog (Reset / suppression checkpoint)
└─ div#toast-region (aria-live="polite")
```

- Scroll = fenêtre (pas de conteneur interne) → `body.is-scrolled` reste fonctionnel.
- Topbar sticky ; sidebar fixe desktop (232px ; rail 64px replié/auto 1024–1279px ; persisté
  `humanity.ui.nav`).
- **Mobile <1024px** : sidebar masquée → **bottom tab bar** 5 slots (Overview, Workspace, World,
  Lab, More) ; « More » = sheet listant les 8 vues + charte. Topbar 2 rangées (identité+statut /
  transport). Boundary strip au-dessus de la tab bar.
- Routeur : `#/overview` défaut ; route inconnue → overview ; `#/view/section` scroll ; vue active
  → `data-view-active` sur body (styling), `hidden` sur les autres, `aria-current="page"` nav,
  titre topbar, `humanity.ui.lastRoute`. Événement interne `view:enter` → flush des redraws en attente.
- Palette (Ctrl/Cmd+K) : fuzzy sur un registre de commandes {label, hint(endpoint/route), run()} :
  navigation ×8, transport (run/pause/step/reset…), thème, dock, charte, raccourcis, batteries ×9,
  exports ×3, checkpoint save, `@métrique` (→ lab, métrique sélectionnée), `#paramètre` (→ settings,
  contrôle focus+highlight), sections (sous-routes). Dialog modal, combobox ARIA, flèches+Enter,
  Échap ferme, focus restauré.
- Raccourcis globaux (hors champs de saisie) : `1–8` vues, `r` run/pause, `s` step, `p` dock,
  `t` thème, `[` sidebar, `!` charte, `?` aide raccourcis, `Ctrl+K` palette, `Shift+R` reset (confirm).

## 2. Ignition Aperture (élément signature, #/overview)

SVG viewBox 0 0 340 348, cadran 240° (150°→390°), rayon piste 128, gap bas pour le readout.
Prototype validé (scratchpad/aperture-proto.html).

- **Piste** : arc hairline `--line` ; graduations mineures 0.05 (alpha .14), majeures 0/.25/.5/.75/1
  (alpha .35 + labels mono 9px).
- **Zone d'ignition** : arc `effective_threshold → 1`, électrum alpha .12 (statique).
- **Arc de score** : 0 → `ignition_score`, électrum (bright si `ignited`), 7px round.
- **Arc interne** (r=104, 3.5px, `--cool`) : `broadcast_strength`.
- **Marqueur seuil effectif** : tick radial plein (`--ink`) ; **seuil nominal** (`config.ignition_threshold`)
  en tick fantôme pointillé — l'écart visualise la modulation arousal/homéostasie. Étiquette du seuil
  DANS le cadran (pas de collision graduations).
- **Centre** : mot d'état (GLOBAL ACCESS électrum / SUBLIMINAL soft / ASLEEP cool / AWAITING faint),
  score mono 42px, « threshold N » ; en dessous : source gagnante (point coloré `--src-*` + nom) et
  contenu (serif italique, ellipsé).
- **Sous le cadran** : rangée micro-stats mono — winner strength · dominance · arousal (avec baseline).
- **États** : nodata (avant 1er cycle) → arcs vides + AWAITING ; asleep → dim + ASLEEP ;
  ignition réelle (flanc montant de `ignited`) → 1 pulse 240ms de l'anneau (classe `.igniting`),
  **désactivé sous prefers-reduced-motion** (l'état est porté par texte + remplissage).
- **A11y** : `role="img"` + `aria-label` synthétique réécrit (comme les canvas existants) ; toutes
  les valeurs sont AUSSI du texte DOM visible.
- Données : `renderIgnitionGate(ws)` (fonction existante, conservée) alimente le gate linéaire
  compact (ids `ig-*` conservés, intégré au bloc aperture) ET appelle `updateAperture(ws)` (nouveau).
  `is_sleeping` vient du poll metrics ; `nominal` de la config cliente.

## 3. Vues (affectations 03 §1 adoptées, avec D4/D5)

- **#/overview** : aperture + moment (état/qualification verbatim, `#moment-contents`, gate `ig-*`) ;
  6 KPI échos (`[data-kpi]` : awareness, phi_proxy, valence, arousal, free_energy, energy) ;
  timeline compacte des sources (écho DOM du horizon-stream) ; miniatures World/Society (canvas
  dédiés, clic → #/world) ; CTA premier lancement.
- **#/workspace** : bandeau moment (broadcast, winner, arousal+baseline) ; compétition `#coalitions`
  (barres par source `--src-*`, seuil hors des barres → panneau de décision : « score vs eff → état »,
  cf. 05) + table accessible ; stream `#stream-track` ; Access dynamics (`#ignition-chart` DPR +
  zones + `#horizon-stream` avec légende sources) ; colonne AST + HOT (3 jauges → meters lisibles,
  higher-order report).
- **#/world** : canvas World DPR (formes distinctes par kind + couleur, curseur clavier, rayon =
  `config.perception_radius`) + barre Place + **inspecteur de cellule** (kind/danger/novelty/utility
  de la cellule sélectionnée) ; Society : canvas + `n_agents` + relations + **feed messages/échanges**
  + **inspecteur d'agent sélectionné** (D4) ; chip task (écho).
- **#/mind** : Self-model + goals + narrative ; Individuation ; Self-opacity (déplacée ici) ;
  Rhythms & drives (P2) ; Asymptote (P5, + Inner voice LLM badgé) ; Horizon (P7, readouts + task +
  Activate all) ; Report & dialogue (introspection 7 champs → Narrate LLM → Converse LLM, badges).
- **#/learning-language** : Learned policy (q-bars) ; Concepts ; ELR ; Personality ;
  Language (convergence, success/deficit, last exchange, vocab chips, dictionnaire en **matrice
  lexicale** meaning × [modal word, agreement, speakers, variantes]) ; bannière « needs a society »
  si `n_agents < 2`.
- **#/laboratory** : Live indicators (`#metric-grid` canonique) ; Time series (`#lab-metric` épuré
  aux séries réelles + `#lab-chart` avec axes/légende/état vide) ; Functional batteries (9, groupées,
  disclaimers verbatim) ; **Causal probes & ledger** (maison du panneau interventions) ; LLM probes
  (audit, report card, biography, cross-exam — divulgation) ; Fast training ; Theory coverage ;
  Checkpoints ; Exports (csv/json/analysis).
- **#/memory** : Search + résultats ; Working memory (déplacée ici) ; Recent episodes ;
  graphe autobiographique (hero, DPR, tooltip focus, clavier existant).
- **#/settings** : filtre plein-texte ; Core dynamics (9 sliders + valeur + défaut) ; groupes P2/P3/
  P5/P6/P7 (toggles + sous-libellés descriptifs tirés des tooltips actuels) ; Persistence & I/O ;
  Society (écho n_agents) ; **Full configuration (read-only)** (D8) ; Appearance (thème) ; lien charte.
  Badge « requires reset » sur les 9 champs structurels ; erreurs 409/422 → toast explicite.

## 4. Design system (tokens : direction « observatoire », feuille finale en 04)

- `@layer reset, tokens, base, layout, components, utilities, states, motion, responsive;`
- **Tokens conservés par NOM** (canvas) : `--accent --accent-bright --pos --neg --cool --curio
  --line --ink --ink-soft --ink-faint --bg-inset --mono` + structurants existants (`--bg --serif
  --sans --radius…`) — nouvelles valeurs.
- Nouveaux : `--bg-elev`, `--electrum-deep`, `--src-{perception,memory,self,emotion,goal,imagination,
  dream,social,inner_speech,wandering,language,unknown}` (12, thémés), échelle d'espacement
  `--sp-1..8`, type scale fluide `--fs--1..6` (clamp), `--dur-1 120ms / --dur-2 200ms / --dur-3 240ms`,
  easing, `--control-h 36px / 44px tactile`, z-index (`--z-nav/topbar/drawer/dialog/toast`),
  ombres 3 niveaux, `--radius-sm/md/lg`.
- Hiérarchie de surfaces : canvas (bg) < panel < group < inset ; annotations en encre faible.
- Thème clair « papier d'archive » : ivoire chaud, encre brune-noire, laiton mat (accents plus
  sombres pour AA), surfaces à peine teintées ; PAS une inversion.
- Typographie : serif éditoriale (titres majeurs, moment) `Palatino Linotype/Georgia…` ; sans
  `Segoe UI Variable/system-ui…` ; mono `Cascadia Mono/Consolas…`. Piles 100 % locales.
- Électrum = signal rare : ignition réelle, statut Running, action primaire. Interdiction de halo ailleurs.

## 5. Motion

Uniquement : pulse d'ignition (1×240ms), flash du moment (existant, conservé), transitions de vue
(fondu 120ms), ouverture drawer/dialog (160-200ms transform+opacity), hover/focus (100ms).
`prefers-reduced-motion` : tout à 0ms/aucune animation, états portés par forme+texte. Aucune
animation infinie. Pas de re-animation par tick.

## 6. États (matrice complète en 02 §5 — tous rendus intentionnels)

Premier lancement (charte + CTA), pause, run, asleep, no-ignition, ignition, données insuffisantes
(par graphique), mécanisme désactivé (« dormant — … » conservés), mono/multi-agent, mémoire vide,
recherche vide, LLM 503 (inline), WS déconnecté n/a (polling : statut « API error » + retry au poll
suivant — bandeau discret si ≥3 échecs consécutifs), requête lente (aria-busy existants), 409
structurel (toast explicite + lien reset), checkpoint legacy (Load désactivé), 390px, clair/sombre.

## 7. Accessibilité (cibles WCAG 2.2 AA)

Skip-link ; landmarks header/nav/main/footer ; h1 (topbar) → h2 (vue) → h3 (panneau) ;
focus-visible 2px `--accent` partout (les 2 thèmes) ; cibles ≥44px mobile ; dialogs natifs `<dialog>`
avec focus initial + restauration ; palette = combobox ARIA ; aria-live conservés/interdits selon 02 ;
tables/list équivalentes pour toute viz (coalitions → table, charts → résumés textuels existants
enrichis, world → inspecteur + statut, aperture → texte intégral) ; jamais couleur seule (formes
par kind, saturation+bordure pour ignition, badges texte) ; zoom 200% (layout fluide, pas de
hauteur fixe de texte) ; contrastes AA vérifiés (04).

## 8. Performance

rAF-coalescing des redraws canvas (un seul par frame) ; skip des draws pour vues `hidden` + flush à
`view:enter` (D3) ; DPR sur les 6+2 canvas (backing store × dpr, coordonnées logiques, hit-tests
convertis) ; ResizeObserver (un par canvas, debounce rAF) ; caps existants conservés (STREAM_MAX 48,
HIST 60, IGNITION_HISTORY_MAX 120, log 40) ; renderers à diff minimal (textContent inchangé → skip,
réutilisation des nœuds de rangées quand le count est stable) ; aucune allocation dans les boucles
de dessin (helpers réutilisant des tableaux) ; listeners délégués pour les nav items/palette ;
`IntersectionObserver` pour suspendre les charts hors écran DANS une vue longue (lab). Objectif
DevTools : pas de long task >50ms récurrente pendant un run à 4 tps.

## 9. Politique tests (D6)

Modifiés : les 3 assertions de version (`?v=8.0`). Conservés à l'identique : tout le reste de
02 §3 (fonctions, ordres, aria, littéraux CSS épinglés, déterminisme). Ajout éventuel de tests :
non (hors périmètre backend).

## 10. Ordre d'implémentation

1. index.html : shell + 8 vues + déplacement des panneaux (ids intacts) + icônes + dialogs/dock.
2. styles.css : réécriture complète (layers, tokens 04, composants, thème clair, responsive).
3. app.js : bloc « shell » (routeur, palette, dock, dialogs, toasts, raccourcis, préférences UI),
   `updateAperture`, échos overview, DPR/rAF, gardes de visibilité, inspecteurs world/society,
   settings (filtre + catalogue + read-only + badges), corrections D7. Fonctions/ordres pytest intacts.
4. Bump `?v=8.0` + tests. `node --check` + `check_ui_contract.mjs` + pytest UI à chaque étape.
5. QA navigateur par vue/viewport (skill humanity-visual-qa), corrections, Vague C.

## 11. Critères d'acceptation

Ceux de la définition de terminé du brief (§21) + : aucune régression des 163 références d'ids ;
les 41 contrôles de config opérationnels ; les 5 sondes + ledger fonctionnels depuis dock ET
laboratory ; ignition observable en <5s depuis l'Overview à froid ; charte au premier lancement ;
electrum discipliné ; 0 erreur console sur 3 min de run à 4 tps en naviguant les 8 vues.
