# Vague C — Revue accessibilité & performance

Statut : l'agent relecteur a terminé sa recherche puis a été interrompu par une limite de session
API au moment d'écrire. **Le lead a ré-exécuté le périmètre** : calculs de contraste WCAG par
script sur les paires réellement utilisées, audits statiques par grep, Lighthouse, et
instrumentation PerformanceObserver en conditions réelles.

## Constats

| Sévérité | Constat | Résolution |
|---|---|---|
| moyenne | LIGHT `--ink-3` (#6A6252) sur `--inset` (#E3DBC8) = **4.38:1** < 4.5 (labels d'axes canvas, `.micro` sur inset) | **Corrigé** → `#625B4B` : 4.89:1 sur inset, 5.92:1 sur panneau, 5.46:1 sur champ |
| basse | `role="meter"` posé sur les meters statiques principaux seulement ; les meters générés gardent la valeur en texte adjacent | Documenté comme limite (équivalence fonctionnelle) |
| basse | Palette de commandes sans `aria-activedescendant` (la sélection est portée par `aria-selected` + rendu visuel) | Documenté ; amélioration future |

Aucun constat de haute sévérité.

## Contrastes (calcul WCAG, les deux thèmes) — après correctif

23/23 paires passent. Extraits : sombre — ink-3/panneau 5.42, corps 8.67, électrum-texte 10.63,
bouton primaire 10.21, trace/inset 3.58 (UI ≥3), focus 9.37, pire source vs inset 6.58
(prediction_error) ; clair — ink-3/panneau 5.30, **ink-3/inset 4.89 (corrigé)**, électrum-texte
4.68, bouton primaire 5.04, focus 5.44, pire source vs inset 3.00 (metacognition, marque UI ≥3:1,
jamais texte seul — le nom de la source est toujours imprimé à côté).

## Structure & ARIA (vérifié)

- Landmarks uniques (header/nav[aria-label]/main/footer) + skip-link vers `#main` (cible existante).
- Hiérarchie de titres sans saut : 1 h1 (marque), 12 h2 (8 vues + 4 dialogs), 36 h3 (panneaux), 20 h4.
- `aria-live` : 8 régions, toutes `polite`, toutes bornées ou initiées par l'utilisateur
  (ledger, statut monde, sélections graphe/société, résultats de recherche, compteur de filtre,
  toasts) ; `#memory-graph-summary` n'est **plus** live (spam lecteur d'écran corrigé) ;
  `#horizon-task`/`#ignition-chart-summary` non-live (verrou pytest respecté).
- Dialogs natifs `<dialog>` : focus initial posé, Échap, fermeture par [data-close-dialog],
  le dock rend le focus à son déclencheur.
- Canvas interactifs : world + memory-graph (contrats existants préservés), + ignition-chart et
  society-canvas désormais focusables avec instructions clavier imprimées et aria-labels réécrits
  aux valeurs réelles ; tables DOM équivalentes (coalitions, objets du monde) ajoutées.
- Reduced motion : media query globale (animations/transitions → ~0 ms), pulse d'aperture et
  respiration LIVE neutralisées — vérifié par émulation (animation-duration mesurée 1e-05 s).

## Performance (mesuré, pas estimé)

- **PerformanceObserver longtask, ~3 min 10 s de run continu à 4 tps en traversant les 8 vues :
  1 seule long task (67 ms)** — aucune long task récurrente imputable au frontend.
- Lighthouse (desktop, navigation) : **Accessibilité 100, Best Practices 100**, SEO 89 → ~100 après
  ajout de la meta description ; CLS 0.004. (La catégorie Performance de ce runner n'émet pas de
  score pour cette page ; l'app étant un instrument de flux temps réel, l'instrumentation longtask
  ci-dessus est la mesure pertinente et elle est archivée ici.)
- Audits statiques : aucun `localStorage` dans le chemin de poll ; un seul `setInterval` (le poll) ;
  les `addEventListener` dans les renderers portent sur des nœuds recréés puis remplacés (pas
  d'accumulation) ; ResizeObserver un par canvas (WeakSet) ; fetch d'historique lab suspendu quand
  la vue est cachée ; canvas DPR plafonné à 2× ; caps de séries conservés (48/60/120/40).
