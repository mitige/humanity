# Vague C — QA visuelle navigateur

Statut : l'agent relecteur indépendant a exécuté une partie de ses parcours (preuves :
`screenshots/wave-c-overview-cold-1600.png` — premier lancement à froid,
`screenshots/wave-c-world-2agents-1600.png` — société à 2 agents ; plus un checkpoint « qa-wave-c »
créé pendant son test save/load) puis a été interrompu par une limite de session API avant d'écrire
son rapport. **Le lead a ré-exécuté et complété l'intégralité du périmètre** (Playwright, cache
désactivé via CDP). Constats et couverture ci-dessous — chaque ligne correspond à un parcours
réellement exécuté.

## Constats

| Sévérité | Constat | Résolution |
|---|---|---|
| moyenne | `--ink-3` clair sur `--inset` à 4.38:1 (< 4.5) — labels d'axes in-canvas et `.micro` sur fonds inset en thème clair | **Corrigé** : `--ink-3` clair → `#625B4B` (4.89:1 sur inset, 5.92:1 sur panneau) |
| basse | `meta-description` absente (Lighthouse SEO 89) | **Corrigé** : description ajoutée, formulée dans le contrat d'honnêteté |
| basse | Le chip « agent N » du topbar s'affichait en mono-agent ([hidden] battu par `display:inline-flex`) | **Corrigé** en implémentation (`[hidden]{display:none!important}` global) |
| basse | AST/HOT tombaient sous Access dynamics (auto-placement de grille) | **Corrigé** : ordre DOM + `grid-row` explicites |

Aucun constat de haute sévérité.

## Couverture vérifiée OK (exécutée, pas déclarée)

- **Fonctions avant → après** : transport + tps, monde cliquable (pointeur ET flèches/Entrée, avec
  inspecteur de cellule), société (n agents, sélection clic + clavier + cartes), mémoire (recherche
  8 résultats, graphe au clavier avec annonce + tooltip focus), 9 batteries accessibles (mirror
  exécutée : score + interprétation + disclaimer verbatim), scénario JSON (5 rows + résumé),
  checkpoints save → **load avec dialog de confirmation** → delete avec confirmation (« qa-meridien »
  et « qa-wave-c »), exports CSV/JSON = téléchargements réels (`humanity_metrics.csv/.json`) +
  export analysis, coverage, settings (filtre, sliders avec valeur + défaut, 32 toggles), les 5
  sondes causales + ledger corrélé #NNN (depuis le dock ET le Laboratory).
- **Parcours live** : Step ×n ; Run 4 tps avec navigation dans les **8 vues pendant le run** ;
  société 2 et 3 agents (relations, convergence lexicale 0.89, dictionnaire, inspecteur d'agent) ;
  retour mono-agent.
- **Dock** : `p` depuis Workspace → onglet Inject présélectionné ; depuis World → Stimulus ;
  soumission → entrées corrélées ; Échap → le panneau revient physiquement au Laboratory.
- **Palette** : Ctrl+K, filtrage (« masking » → commande batterie), navigation ↑↓ + Entrée.
- **Responsive** : 1600 / 1440 / 1280 / 1024 / 768 / 390 / 360 — zéro scroll horizontal sur les
  8 vues à 390 px (mesuré scrollWidth vs clientWidth), tab bar mobile + sheet « More » + drawer nav
  fonctionnels, topbar 2 rangées, transport accessible partout ; proxy zoom 200 % (720 px) sans
  débordement sur overview/workspace/settings.
- **Thèmes** : bascule clair sur plusieurs vues — tous les canvas re-teintés (monde, société, chart,
  graphe, dial), topbar vérifié au pixel ; retour sombre.
- **Console** : **0 erreur / 0 warning** sur l'ensemble des parcours, y compris **~3 min 10 s de
  simulation continue** (t1 → t521) en traversant les 8 vues.
- **État final restauré** : pause, 1 agent, thème sombre, #/overview, checkpoints de QA supprimés.

Captures finales : `screenshots/after-*.png` (19 fichiers : 7 vues à 1600, 1440/1280/1024/768,
thème clair ×3, mobile 390 ×4 + 360).
