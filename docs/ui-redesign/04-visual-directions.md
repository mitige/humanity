# 04 · Directions visuelles — la refonte de l'Observatoire

> **Mandat.** Faire de Humanity « un observatoire cognitif de qualité muséale, à mi-chemin entre un
> instrument astronomique contemporain, une publication scientifique éditoriale haut de gamme et une
> console de recherche extrêmement précise ». Précis, digne, sceptique, scientifiquement honnête —
> fascinant sans jamais suggérer qu'une machine est consciente.
>
> **Méthode.** Tous les ratios de contraste de ce document sont **calculés** (luminance relative
> WCAG 2.x : `L = 0.2126·R + 0.7152·G + 0.0722·B` sur canaux linéarisés ; ratio `(L1+0.05)/(L2+0.05)`),
> via un script Python jetable. Cibles : **AA 4.5:1** texte normal, **3:1** grands textes (≥ 18.7 px gras
> ou 24 px) et composants d'interface. Les traits purement décoratifs sont annotés comme tels.

---

## 0 · État des lieux mesuré (pourquoi rouvrir le chantier)

Le thème actuel « ébonite & laiton » a une vraie voix, mais l'audit chiffré révèle trois dettes :

| Paire actuelle | Hex | Ratio mesuré | Verdict |
|---|---|---|---|
| Labels gravés `--ink-faint` / panneau (sombre) | `#6F6959` / `#12110E` | **3.45:1** | ÉCHEC AA — la moitié des micro-labels de l'instrument |
| Seuils & eyebrows `--accent-soft` / panneau (sombre) | `#86703F` / `#12110E` | **3.96:1** | ÉCHEC AA — le *seuil effectif*, donnée centrale, est sous-lisible |
| Marques non-ignitées `--ink-ghost` / inset (sombre) | `#3E3A30` / `#070706` | **1.78:1** | ÉCHEC 3:1 UI — les moments subliminaux sont quasi invisibles |
| Labels `--ink-faint` / panneau (clair) | `#8B8374` / `#F6F2E8` | **3.36:1** | ÉCHEC AA |
| Texte secondaire `--ink-soft` / panneau (sombre) | `#A59D8D` / `#12110E` | 7.02:1 | OK — à conserver dans l'esprit |
| Source `perception` vs accent laiton | `#D8A84E` vs `#C9A35C` | **1.08:1** | Collision : chaque barre de perception ressemble à une ignition |

S'y ajoutent deux dettes de **discipline du signal** : l'aurore laiton permanente du `body::before` et le
halo radial permanent du panneau Horizon font briller l'électrum même quand rien ne s'allume — l'accent
« rare » ne l'est plus ; et la source `perception` occupe la teinte or de l'ignition. La refonte doit
rendre l'électrum à sa fonction : *ne s'allumer que quand le mécanisme s'allume.*

---

## 1 · Direction I — « Le Méridien » *(recommandée)*

### Concept

L'interface est une **lunette méridienne contemporaine** : un champ bleu-noir profond et mat, des
plaques d'instrument usinées, des graduations fines partout où une valeur rencontre un seuil, et un
unique métal — l'électrum — qui ne s'allume qu'à l'ignition, à l'état *live* ou sur l'action primaire.
La voix éditoriale (serif chaude) est réservée à ce que « dit » le modèle — moment conscient, rapports,
ledes — pendant que la sans-serif tient l'instrument et que la mono porte chaque nombre. C'est
l'héritier direct de l'Observatoire actuel : même dignité, mais champ refroidi (l'ébonite devient nuit
d'altitude), contrastes réglés au chiffre, et signal doré rendu à sa rareté.

### Palette (ratios calculés)

| Rôle | Hex | Sur fond | Ratio | Cible |
|---|---|---|---|---|
| Champ (canvas) | `#07090D` | — | — | — |
| Panneau (surface-1) | `#0D1117` | — | — | — |
| Groupe (surface-2) | `#131922` | — | — | — |
| Inset / écran de données | `#05070A` | — | — | — |
| Encre chaude (corps) | `#F3EFE6` | `#0D1117` | **16.49:1** | 4.5 ✓ |
| Encre secondaire | `#A9B0BC` | `#0D1117` | **8.67:1** | 4.5 ✓ |
| Encre d'annotation | `#808A99` | `#0D1117` | **5.42:1** | 4.5 ✓ |
| Électrum (ignition) | `#E7BC68` | `#0D1117` | **10.63:1** | 4.5 ✓ |
| Électrum éteint (seuils, laiton mat) | `#8F7336` | `#05070A` | **4.49:1** | 3 ✓ |
| Perception (cyan minéral) | `#7CC1DB` | `#0D1117` | **9.47:1** | 4.5 ✓ |
| Mémoire (violet ardoise) | `#A79BDF` | `#0D1117` | **7.57:1** | 4.5 ✓ |
| Positif / apprentissage (sauge) | `#9AC894` | `#0D1117` | **9.97:1** | 4.5 ✓ |
| Danger (corail minéral) | `#E4826B` | `#0D1117` | **6.94:1** | 4.5 ✓ |
| Trace (donnée non-ignitée) | `#5E6878` | `#05070A` | **3.58:1** | 3 ✓ |
| Traits | ivoire α 0.08–0.14 | `#0D1117` | 1.20–1.43:1 | décoratif |

Thème clair « papier d'archive » : voir la feuille de tokens (§5) — ivoire vergé `#EDE7D8→#FBF8EF`,
encre `#26221A` (13.93:1), laiton mat `#8A6510` (4.68:1), chaque paire recalculée.

### Typographie

Triade système (aucun chargement réseau) : serif éditoriale pour la voix du modèle, sans très lisible
pour l'instrument, mono pour toute donnée. Piles exactes et justification en §5.3.

### Hiérarchie de surfaces

| Niveau | Rôle | Traitement |
|---|---|---|
| 0 · Champ | le fond du site | `#07090D` **plat** — ni aurore, ni vignette ; seul un grain statique α 0.02 (matité muséale) |
| 1 · Panneau | module du rack | surface-1 + trait 14 % + ombre profonde douce + arête supérieure claire (1 px α 0.03), rayon 10 px |
| 2 · Groupe / cellule | metric-cells, deep-cells | surface-2 + hairline 8 %, rayon 8 px, pas d'ombre portée |
| 3 · Inset / écran | jauges, canvases, logs, graphes | `#05070A` + ombre interne — *le seul niveau où vivent les données* ; toujours le plus sombre |
| 4 · Annotation | endpoints, graduations, folios | aucun fond — tokens texte seuls + hairlines ; jamais sous `--ink-3` |

Règle : jamais un groupe dans un groupe ; jamais plus d'un inset par groupe ; l'élévation encode la
*profondeur optique de l'instrument* (les données au fond du tube, les commandes sur le corps).

### Langage de motion (120–240 ms)

*Le mouvement est une mesure : rien ne bouge si aucune variable n'a changé.*

- **120 ms** `--dur-flip` : bascules d'état (hover, badge, toggle, focus) — opacité/couleur seulement.
- **180 ms** `--dur-value` `--ease-instrument` : largeurs de jauges, rotation d'aiguille, déplacement
  de seuil — amortissement critique avec 2 % de dépassement, comme une aiguille physique.
- **240 ms** `--dur-access` : le **bloom d'ignition** (une seule pulsation radiale, jamais en boucle),
  l'entrée des panneaux (translateY 8 px, stagger 40 ms, 5 max), l'ouverture d'overlays.
- **Unique boucle autorisée** : la respiration de la pastille LIVE quand la simulation tourne
  (opacité 1 ↔ 0.72, 2.4 s). `prefers-reduced-motion` coupe tout.
- Interdits : parallax, shimmer, particules, hue-rotate, halos permanents.

### L'« Ignition Aperture » — traitement signature

Le cadran central de l'Overview devient une **ouverture de télescope graduée** — et c'est aussi la
marque : le logo actuel (anneau gradué + cœur laiton) est ce cadran en miniature.

- **Géométrie** : arc de 240° ; graduations fines tous les 0.01 (hairline), moyennes tous les 0.05
  (`--ink-3`), majeures labellées 0 / 0.25 / 0.50 / 0.75 / 1.00 (mono micro, `--ink-3`, 5.42:1).
  Six cordes hairline en hexagone interne (α 0.06) suggèrent l'iris — statiques, décoratives.
- **Seuil** : caret plein **électrum éteint** `#8F7336` + trait radial tireté (3-2) à θ_eff ; caret
  creux `--ink-3` au θ nominal ; la bande d'hystérèse est un segment d'arc hairline entre les deux.
- **Score** : aiguille amortie (180 ms) + arc de progression en `--trace` (3.58:1) tant que
  score < θ_eff. **Seule la portion au-delà du seuil s'allume en électrum**, avec un bloom unique de
  240 ms au moment du franchissement. Cœur du cadran : la lampe pilote (6 px) qui ne s'allume qu'ignité.
- **Readout** : au centre, numéral mono `score` (tabulaire), dessous `θ_eff` et la marge signée Δ.
- **Nomenclature d'états** : badges `SUBLIMINAL` (contour `--ink-3`) · `ACCÈS` (le seul badge *rempli* :
  fond électrum, texte `#1D1407`, 10.21:1) · `MAINTENU` (contour électrum — hystérèse, sans bloom) ·
  `SOMMEIL` (cadran atténué à 60 %, carets de seuil intacts).
- Le même vocabulaire de cadran se décline en miniatures : jauges HOT, cadran circadien — une seule
  famille d'instruments.

### Micro-détails

- **Graduations** : chaque piste inset reçoit ticks d'extrémité + tick médian (0 / 0.5 / 1) en
  hairline ; les jauges bipolaires un tick zéro `--ink-3` ; les graphes une réglure gauche de
  3 lignes hairline avec labels mono micro `--ink-3`.
- **Lignes de seuil** : toujours tiretées 3-2, électrum éteint `#8F7336` (4.49:1 sur inset), étiquette
  mono `θ_eff 0.424` posée à droite, jamais en travers des données.
- **Nomenclature** : numérotation de module `07 ·` en mono `--ink-3` ; le segment souligné de 32 px
  sous la plaque reste le seul laiton structurel (électrum éteint, non textuel).
- **Badges d'état** : hauteur 18 px, mono 10 px caps, esp. 0.14em, contour 1 px `--line-control`
  (3.49:1) ; seul `ACCÈS` est rempli.
- **`GET /endpoint` par panneau — la ligne de provenance** : à droite de la plaque, mono 10–11 px,
  `--ink-3` (5.42:1 — plus jamais de « minuscule texte gris » sous AA) : verbe en graisse 600, chemin
  en 400, séparateur `·` fantôme. Hover → `--ink-2` + soulignement pointillé ; clic → copie du chemin.
  C'est un instrument d'honnêteté de premier rang : chaque panneau déclare sa source de données.

---

## 2 · Direction II — « La Planche »

### Concept

L'interface est une **publication scientifique vivante** : le thème par défaut devient le *papier
d'archive* (ivoire vergé, encre, laiton mat), chaque panneau une **planche numérotée** (« Pl. VII »)
avec figure, légende et notes de bas de page ; le thème sombre est « le négatif de la planche », chaud
comme une chambre noire. Les données sont des figures gravées : réglures au crayon, index
triangulaires, dagues de seuil, chiffres tabulaires dans des cartouches. C'est la direction la plus
éditoriale et la plus calme — le mouvement y est presque aboli au profit de la « réimpression ».

### Palette (ratios calculés)

| Rôle | Hex | Sur fond | Ratio | Cible |
|---|---|---|---|---|
| Papier vergé (champ) | `#F2ECDC` | — | — | — |
| Cartouche (panneau) | `#F8F4E7` | — | — | — |
| Encre | `#241F15` | `#F2ECDC` | **13.89:1** | 4.5 ✓ |
| Encre secondaire | `#55503F` | `#F2ECDC` | **6.83:1** | 4.5 ✓ |
| Laiton gravé | `#7D5C14` | `#F2ECDC` | **5.22:1** | 4.5 ✓ |
| Sanguine (danger) | `#A34E33` | `#F2ECDC` | **4.82:1** | 4.5 ✓ |
| Cyan encre (perception) | `#1E6076` | `#F2ECDC` | **5.96:1** | 4.5 ✓ |
| Violet encre (mémoire) | `#53489B` | `#F2ECDC` | **6.43:1** | 4.5 ✓ |
| Sauge encre (positif) | `#3F7145` | `#F2ECDC` | **4.87:1** | 4.5 ✓ |
| Négatif (champ sombre) | `#0B0A07` | ivoire `#F1EAD9` | **16.51:1** | 4.5 ✓ |
| Négatif surface / ivoire-2 | `#131109` | `#ABA28D` | **7.45:1** | 4.5 ✓ |
| Négatif / laiton | `#131109` | `#D3A961` | **8.65:1** | 4.5 ✓ |

### Typographie

Serif dominante partout (corps compris, interligne 1.6, chiffres elzéviriens pour le texte) ; sans
réservée aux contrôles ; mono aux données. Mêmes piles système qu'en §5.3.

### Hiérarchie de surfaces

Papier (champ) → cartouche (panneau, filet double en tête) → réserve (inset crème foncé `#E5DEC9`) →
marge annotée (folios, notes). Ombres quasi nulles : la structure tient par les **filets** (hairlines
encre α 0.14) et les doubles filets d'ouverture de planche.

### Motion

120 ms uniquement, crossfades (« réimpression ») ; aucune aiguille, aucun sweep ; le bloom d'ignition
devient une **marque de cire** : un point électrum apposé dans la marge, fondu en 240 ms, statique
ensuite. `prefers-reduced-motion` : déjà presque rien à couper.

### Ignition Aperture

Une **figure gravée horizontale** : règle graduée 0→1, index triangulaire sous la règle pour le score,
**dague verticale « † »** labellée θ_eff pour le seuil, marge au-delà du seuil hachurée ; à l'ignition
la hachure s'encre en laiton et la légende passe à « Fig. 1 — accès global (ignition) ». Chaque état
est écrit en toutes lettres dans la légende — la nomenclature est textuelle avant d'être chromatique.

### Micro-détails

Folio en pied de panneau (« Pl. VII · 12 »), notes de bas de page pour les endpoints
(« ¹ GET /agent/workspace — concours d'accès »), sceau sec embossé « FONCTIONNEL — NON PHÉNOMÉNAL »
sur le Laboratoire, § de section, réglure crayon sous chaque titre. Badges d'état = petites capitales
serif espacées, jamais de pilule remplie.

---

## 3 · Direction III — « Le Pupitre »

### Concept

L'interface est un **pupitre de télémétrie de recherche** : densité maximale lisible, chaque panneau
une *voie* (« CH-07 ») avec bus d'état en tête, readouts digitaux à retenue de crête, drapeaux d'état
`[SUB] [IGN] [MNT]`, quadrillage faible sur les écrans de données. La mono devient la voix principale
(labels ET données), la sans porte le texte courant, et la serif ne survit qu'à un seul endroit : le
moment conscient, une voix humaine au centre d'une salle de machines. C'est la direction la plus dense
et la plus opératoire — et la plus risquée pour l'identité.

### Palette (ratios calculés)

| Rôle | Hex | Sur fond | Ratio | Cible |
|---|---|---|---|---|
| Champ acier | `#05070A` | — | — | — |
| Voie (panneau) | `#0C1218` | — | — | — |
| Texte neutre froid | `#E9EEF2` | `#05070A` | **17.26:1** | 4.5 ✓ |
| Texte-2 | `#9DA9B5` | `#0C1218` | **7.87:1** | 4.5 ✓ |
| Texte-3 | `#7E8B98` | `#0C1218` | **5.41:1** | 4.5 ✓ |
| Électrum | `#E3B75F` | `#0C1218` | **10.05:1** | 4.5 ✓ |
| Sauge | `#8CC996` | `#0C1218` | **9.78:1** | 4.5 ✓ |
| Corail | `#E27B61` | `#0C1218` | **6.49:1** | 4.5 ✓ |
| Cyan | `#6FBFDD` | `#0C1218` | **9.12:1** | 4.5 ✓ |
| Quadrillage (décoratif) | ivoire α 0.07 | `#0C1218` | 1.16:1 | décoratif |

Thème clair : « papier quadrillé de relevé » (même logique que §5 mais quadrillé faible) — réalisable,
moins naturel : le registre console est nativement sombre.

### Typographie

Mono en premier rôle (labels, unités, états), sans en second, serif au seul moment conscient. Danger
mesuré : la mono à 10–11 px fatigue en lecture continue — compensée par interligne 1.5 et casse mixte.

### Hiérarchie de surfaces

Champ → voie → écran quadrillé (inset) → bus d'état (bandeau 24 px en tête de voie, hairline).
Ombres minimales ; la structure tient par les bordures et le rythme des voies.

### Motion

120 ms linéaire strict pour tout ; **retenue de crête** : le marqueur peak-hold retombe en 240 ms ;
ticker d'événements sous l'aperture (dernier accès, tick, source) en défilement discret non animé
(insertion par pas). Aucune boucle.

### Ignition Aperture

**Double colonne verticale** score / θ_eff côte à côte, graduées, avec peak-hold électrum éteint ;
readout digital 4 chiffres sous chaque colonne ; drapeau d'état à bascule mécanique `[SUB]→[IGN]` ;
à l'ignition la colonne score s'allume au-dessus du seuil uniquement, crête retenue 240 ms.

### Micro-détails

Numérotation de voie `CH-07`, timecode `t=001284`, endpoints en **bus bar** : chip `[GET]` contour
3:1 + chemin mono + statut de dernière requête (`200 · 12 ms`). Séparateurs pointillés, unités
toujours après la valeur, jamais d'emoji, jamais de scanline (le matte avant le rétro).

---

## 4 · Grille d'évaluation

Notes sur 5, argumentées. (Identité = reconnaissable comme Humanity, jamais un dashboard générique.)

| Critère | I · Méridien | II · Planche | III · Pupitre |
|---|---|---|---|
| **Identité** | **5** — l'aperture graduée est une signature propriétaire qui *est déjà* le logo ; ni SaaS, ni ChatGPT, ni terminal | **4.5** — très mémorable, mais le pastiche « planche gravée » peut glisser vers le décor d'époque | **3.5** — fort, mais à un cheveu du template « mission control » générique |
| **Lisibilité** | **4.5** — toutes les paires ≥ 4.5:1 mesurées ; réserve : discipline requise sur les tailles mono ≤ 11 px | **4.5** — le papier est imbattable en lecture longue ; le négatif sombre demande plus de soin sur les figures | **4** — ratios excellents mais la mono omniprésente à petite taille fatigue et aplatit la hiérarchie |
| **Évolutivité** | **5** — tokens + familles (cadrans, badges, provenance) absorbent chaque nouvelle phase sans nouveau vocabulaire | **3** — chaque nouveau panneau exige une « maquette de planche » ; les modules interactifs denses (interventions, société) se plient mal au registre | **4.5** — la grille de voies absorbe tout, au prix d'une uniformité croissante |
| **Densité** | **4** — plus dense que l'existant (annotations, graduations), sans sacrifier l'air éditorial | **3** — marges et légendes consomment l'écran ; la société multi-agents et le laboratoire débordent | **5** — densité maximale maîtrisée, faite pour 20+ panneaux |
| **Fidélité scientifique** | **5** — signal électrum rare et mesurable, seuils gradués, provenance par panneau, états nommés | **5** — le registre « publication » est l'incarnation même de l'honnêteté (légendes, notes, sceau) | **4** — honnête et instrumenté, mais l'esthétique « salle de contrôle » sur-dramatise légèrement l'enjeu |
| **Total** | **23.5** | **20** | **21** |

---

## 5 · Recommandation : « Le Méridien »

C'est la seule direction qui tient les trois pôles du mandat *à la fois* : l'instrument astronomique
(champ de nuit, cadrans, graduations), la publication éditoriale (serif de voix, ledes, colophon) et la
console précise (mono tabulaire, provenance, badges d'état) — tout en restant l'héritière évidente de
l'Observatoire actuel (plaques numérotées, lampe pilote, laiton devenu électrum discipliné). La Planche
devient son *mode d'impression* (le thème clair ci-dessous en reprend le papier), le Pupitre son
*plafond de densité* (bus d'état et peak-hold récupérables plus tard sans changer de langage).

### 5.1 Feuille de tokens — thème sombre (défaut)

Chaque paire texte/fond est annotée de son ratio **calculé**. Abréviations : F = champ `#07090D`,
S1 = panneau `#0D1117`, S2 = groupe `#131922`, S3 = hover `#19212C`, IN = inset `#05070A`.

```css
:root, [data-theme="dark"] {
  color-scheme: dark;

  /* ---- Surfaces ---------------------------------------------------- */
  --field:        #07090D;  /* champ (canvas du site), plat, sans halo   */
  --surface-1:    #0D1117;  /* panneau / module                          */
  --surface-2:    #131922;  /* groupe, cellule, chip                     */
  --surface-3:    #19212C;  /* hover / élément soulevé                   */
  --inset:        #05070A;  /* écrans de données, pistes, canvases       */

  /* ---- Encres (texte) ---------------------------------------------- */
  --ink:          #F3EFE6;  /* 17.36:1 F · 16.49:1 S1 · 15.38:1 S2 · 14.13:1 S3 · 17.58:1 IN */
  --ink-2:        #A9B0BC;  /*  8.67:1 S1 · 8.09:1 S2 · 7.43:1 S3        */
  --ink-3:        #808A99;  /*  5.71:1 F · 5.42:1 S1 · 5.05:1 S2 · 4.64:1 S3 · 5.78:1 IN — plancher texte */
  --ink-ghost:    #4A5364;  /*  2.44:1 S1 — DÉCORATIF SEULEMENT (jamais texte, jamais donnée) */

  /* ---- Électrum — le signal rare ----------------------------------- */
  --electrum:         #E7BC68;               /* 11.19:1 F · 10.63:1 S1 · 9.91:1 S2 · 11.32:1 IN */
  --electrum-bright:  #F2D48C;               /* 13.83:1 F · 13.13:1 S1 — glint, cœur de lampe   */
  --electrum-deep:    #8F7336;               /* 4.49:1 IN · 4.21:1 S1 · 3.93:1 S2 — laiton éteint : seuils, structures (UI ≥3:1) */
  --on-electrum:      #1D1407;               /* 10.21:1 sur --electrum — texte du badge ACCÈS / bouton primaire */
  --electrum-veil:    rgba(231,188,104,0.12);/* bloom d'ignition, décoratif, une pulsation      */

  /* ---- Sémantique --------------------------------------------------- */
  --perception:   #7CC1DB;  /* cyan minéral — 9.47:1 S1 · 10.09:1 IN     */
  --memoire:      #A79BDF;  /* violet ardoise — 7.57:1 S1 · 8.06:1 IN    */
  --pos:          #9AC894;  /* sauge lumineuse — 9.97:1 S1 · 10.63:1 IN  */
  --neg:          #E4826B;  /* corail minéral — 6.94:1 S1 · 7.31:1 F     */
  --trace:        #5E6878;  /* donnée non-ignitée — 3.58:1 IN · 3.13:1 S2 (UI ≥3:1, jamais texte) */

  /* ---- Traits -------------------------------------------------------- */
  --hairline:      rgba(243,239,230,0.08);  /* 1.20:1 S1 — décoratif      */
  --line:          rgba(243,239,230,0.14);  /* 1.43:1 S1 — décoratif      */
  --line-control:  rgba(243,239,230,0.40);  /* composite #696A6A → 3.49:1 S1 — bordures de contrôles interactifs */

  /* ---- États / interaction ------------------------------------------ */
  --focus:        #9FB4CC;                   /* 9.37:1 F — anneau 2px, offset 2px */
  --selection:    rgba(159,180,204,0.28);    /* composite #363F4A → --ink dessus : 9.30:1 */
  --live:         var(--electrum);           /* pastille LIVE (respiration, seule boucle) */
  --dormant:      var(--ink-3);
  --error:        var(--neg);

  /* ---- Élévations ---------------------------------------------------- */
  --e-1: inset 0 1px 0 rgba(255,255,255,0.03);                                   /* arête usinée */
  --e-2: inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 0 rgba(0,0,0,0.45),
         0 18px 44px -28px rgba(0,0,0,0.72);                                     /* panneau */
  --e-3: 0 2px 6px rgba(0,0,0,0.40), 0 28px 70px -34px rgba(0,0,0,0.85);         /* overlay/tooltip */
  --e-inset: inset 0 2px 6px rgba(0,0,0,0.42), inset 0 0 0 1px rgba(243,239,230,0.05);
  --grain-op: 0.02;                                                              /* texture unique, statique */
}
```

### 5.2 Feuille de tokens — thème clair « papier d'archive »

Pas une inversion : papier vergé chaud, encre brune, laiton mat plus dense (les valeurs sombres du
métal, pas ses reflets). F = `#EDE7D8`, S1 = `#F5F0E4`, S2 = `#FBF8EF`, IN = `#E3DBC8`.

```css
[data-theme="light"] {
  color-scheme: light;

  /* ---- Surfaces ---------------------------------------------------- */
  --field:        #EDE7D8;  /* papier vergé                              */
  --surface-1:    #F5F0E4;  /* cartouche / panneau                       */
  --surface-2:    #FBF8EF;  /* groupe                                    */
  --surface-3:    #FFFDF6;  /* hover                                     */
  --inset:        #E3DBC8;  /* réserve crème foncée (écrans de données)  */

  /* ---- Encres -------------------------------------------------------- */
  --ink:          #26221A;  /* 12.84:1 F · 13.93:1 S1 · 14.91:1 S2 · 11.49:1 IN */
  --ink-2:        #574F41;  /*  6.55:1 F · 7.10:1 S1                      */
  --ink-3:        #6A6252;  /*  4.89:1 F · 5.30:1 S1 · 5.68:1 S2 · 4.38:1 IN → sur inset : grands textes/UI seulement, sinon --ink-2 */
  --ink-ghost:    #B4AC9A;  /*  1.98:1 S1 — décoratif seulement           */

  /* ---- Laiton mat (électrum du papier) ------------------------------- */
  --electrum:         #8A6510;               /* 4.68:1 S1 (texte OK) · 3.86:1 IN · 4.31:1 F — UI + texte */
  --electrum-text:    #7E5C18;               /* 5.38:1 S1 · 4.96:1 F · 5.76:1 S2 — petits numéraux mono  */
  --electrum-bright:  #A7791F;               /* 3.42:1 S1 — grandes plages UI seulement ; JAMAIS sur inset (2.82:1) */
  --electrum-deep:    #8F6716;               /* 3.70:1 IN — carets et tirets de seuil                    */
  --on-electrum:      #FCF9EE;               /* 5.04:1 sur #8A6510 — bouton primaire / badge ACCÈS       */
  --electrum-veil:    rgba(138,101,16,0.14);

  /* ---- Sémantique ----------------------------------------------------- */
  --perception:   #1F6A83;  /* 5.36:1 S1 · 4.42:1 IN                      */
  --memoire:      #574A9E;  /* 6.42:1 S1 · 5.29:1 IN                      */
  --pos:          #44743B;  /* 4.85:1 S1 · 4.00:1 IN                      */
  --neg:          #A6402F;  /* 5.44:1 S1 · 5.01:1 F                       */
  --trace:        #746C58;  /* 3.78:1 IN — donnée non-ignitée             */

  /* ---- Traits ---------------------------------------------------------- */
  --hairline:      rgba(38,34,26,0.14);   /* 1.31:1 S1 — réglure crayon    */
  --line:          rgba(38,34,26,0.22);   /* décoratif                     */
  --line-control:  rgba(38,34,26,0.55);   /* composite #837F75 → 3.51:1 S1 */

  /* ---- États / interaction --------------------------------------------- */
  --focus:        #4A5D78;                 /* 5.44:1 F                      */
  --selection:    rgba(74,93,120,0.22);    /* composite #CFD0CC → --ink dessus : 10.22:1 */

  /* ---- Élévations -------------------------------------------------------- */
  --e-1: inset 0 1px 0 rgba(255,255,255,0.72);
  --e-2: inset 0 1px 0 rgba(255,255,255,0.72), 0 1px 0 rgba(96,82,52,0.10),
         0 16px 36px -26px rgba(96,82,52,0.32);
  --e-3: 0 2px 6px rgba(96,82,52,0.18), 0 24px 56px -30px rgba(96,82,52,0.45);
  --e-inset: inset 0 2px 5px rgba(96,82,52,0.16), inset 0 0 0 1px rgba(38,34,26,0.06);
  --grain-op: 0.035;                       /* vergeure légère               */
}
```

### 5.3 Tokens communs (les deux thèmes)

```css
:root {
  /* ---- Typographie : piles système exactes (zéro réseau) -------------- */
  /* Serif éditoriale — la voix du modèle. Iowan Old Style (macOS/iOS,
     bookish, grande hauteur d'x), Palatino Linotype (toutes les Windows
     depuis XP, italique calligraphique remarquable pour le moment
     conscient), P052/URW Palladio (clone Palatino des distros Linux),
     Georgia (filet de sécurité universel dessiné pour l'écran). */
  --font-serif: "Iowan Old Style", "Palatino Linotype", Palatino,
                "Book Antiqua", "URW Palladio L", P052, Georgia,
                "Times New Roman", serif;

  /* Sans d'interface — Segoe UI Variable Text (Win 11, cut optique texte)
     avant system-ui pour que Windows serve la variable ; system-ui résout
     SF Pro (macOS), Roboto (Android/ChromeOS), Cantarell/Ubuntu (Linux) ;
     Inter locale honorée si l'utilisateur l'a installée. */
  --font-sans: "Segoe UI Variable Text", system-ui, -apple-system,
               "Segoe UI", Inter, Roboto, "Noto Sans", "Helvetica Neue",
               Arial, sans-serif;

  /* Mono de données — ui-monospace résout SF Mono (Apple) ; Cascadia Mono
     (Win 10/11, cut SANS ligatures : les ligatures falsifient la lecture
     de données), Consolas (toutes Windows), DejaVu/Liberation (Linux).
     Toujours avec font-variant-numeric: tabular-nums slashed-zero. */
  --font-mono: ui-monospace, "Cascadia Mono", "Cascadia Code", "SF Mono",
               Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono",
               "JetBrains Mono", monospace;

  /* ---- Échelle de type fluide (bornes 360 px → 1600 px) ---------------- */
  --fs-micro:   clamp(0.625rem, 0.607rem + 0.081vw, 0.688rem);  /* 10 → 11 px  : annotations, endpoints, badges */
  --fs-caption: clamp(0.688rem, 0.669rem + 0.081vw, 0.75rem);   /* 11 → 12 px  : labels de champs, légendes     */
  --fs-data:    clamp(0.75rem,  0.732rem + 0.081vw, 0.813rem);  /* 12 → 13 px  : valeurs mono courantes         */
  --fs-body:    clamp(0.813rem, 0.794rem + 0.081vw, 0.875rem);  /* 13 → 14 px  : corps d'interface              */
  --fs-lead:    clamp(0.875rem, 0.848rem + 0.121vw, 0.969rem);  /* 14 → 15.5 px: ledes serif, disclaimers       */
  --fs-panel:   clamp(0.813rem, 0.776rem + 0.161vw, 0.938rem);  /* 13 → 15 px  : plaques de panneau (caps)      */
  --fs-numeral: clamp(1.063rem, 0.990rem + 0.323vw, 1.313rem);  /* 17 → 21 px  : numéraux d'instrument          */
  --fs-view:    clamp(1.125rem, 1.052rem + 0.323vw, 1.375rem);  /* 18 → 22 px  : titres de vue                  */
  --fs-hero:    clamp(1.188rem, 1.061rem + 0.565vw, 1.625rem);  /* 19 → 26 px  : le moment conscient            */
  --fs-display: clamp(1.375rem, 1.194rem + 0.806vw, 2rem);      /* 22 → 32 px  : mât « Humanity »               */

  /* ---- Espacement (grille 4 px) ---------------------------------------- */
  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px;  --sp-4: 16px;  --sp-5: 20px;
  --sp-6: 24px; --sp-8: 32px; --sp-10: 40px; --sp-14: 56px;
  --gutter:    clamp(16px, 3.4vw, 52px);   /* marges du rack               */
  --panel-pad: clamp(16px, 1.6vw, 22px);   /* padding interne des panneaux */
  --stack-gap: 18px;                       /* gouttière de la grille       */

  /* ---- Rayons ------------------------------------------------------------ */
  --r-1: 4px;    /* inputs, chips, badges     */
  --r-2: 6px;    /* boutons, cellules de log  */
  --r-3: 8px;    /* groupes, insets           */
  --r-4: 10px;   /* panneaux                  */
  --r-round: 999px; /* pastilles, lampes      */

  /* ---- Durées & courbes (120–240 ms) -------------------------------------- */
  --dur-flip:   120ms;  /* bascule d'état : hover, badge, toggle, focus     */
  --dur-value:  180ms;  /* changement de valeur : jauges, aiguilles, seuils */
  --dur-access: 240ms;  /* accès : bloom d'ignition (one-shot), entrées     */
  --ease-instrument: cubic-bezier(0.25, 0.9, 0.2, 1.02); /* aiguille amortie */
  --ease-exit:       cubic-bezier(0.4, 0, 0.7, 0.2);
  --breath: 2400ms;     /* respiration pastille LIVE — unique boucle admise */

  /* ---- Contrôles ------------------------------------------------------------ */
  --ctl-sm: 28px; --ctl-md: 34px; --ctl-lg: 42px;  /* hauteurs             */
  --hit-min: 24px;      /* cible minimale WCAG 2.5.8 ; 44 px au toucher    */
  --focus-w: 2px; --focus-offset: 2px;

  /* ---- Z-index ---------------------------------------------------------------- */
  --z-field: 0; --z-panel: 1; --z-marks: 3;      /* repères dans les jauges */
  --z-masthead: 20; --z-dropdown: 30; --z-tooltip: 50;
  --z-modal: 70; --z-toast: 90; --z-texture: 100; /* grain, pointer-events:none */

  /* ---- Breakpoints (constantes documentées — les media queries ne lisent
          pas var() ; à garder synchrones à la main) ------------------------ */
  /* --bp-xs 560px · --bp-sm 720px · --bp-md 900px · --bp-lg 1180px
     · --bp-xl 1480px · conteneur max 1680px */
}
```

### 5.4 Les 11 sources de coalitions (+ `unknown`) — harmonisées

Principes : la roue est **minérale et désaturée** ; `perception` cède l'or à l'ignition et prend le
cyan ; les familles cognitives se groupent par voisinage de teinte (analytique froide → sociale-affective
→ incarnée-chaude → drive → diffuse). Chaque thème a sa rampe (une seule rampe ne peut pas être AA sur
les deux fonds). Onze teintes ne seront jamais CVD-sûres seules : **toute marque de source garde son
label ou son tooltip** (déjà le cas dans `app.js`).

| Source | Sombre | vs S1 (texte) | vs IN (barre) | Clair | vs S1 (texte) | vs IN (barre) |
|---|---|---|---|---|---|---|
| perception | `#7CC1DB` | 9.47:1 ✓ | 10.09:1 ✓ | `#1F6A83` | 5.36:1 ✓ | 4.42:1 ✓ |
| imagination | `#9FB2EC` | 9.06:1 ✓ | 9.66:1 ✓ | `#3B5AA6` | 5.77:1 ✓ | 4.76:1 ✓ |
| memory | `#A79BDF` | 7.57:1 ✓ | 8.06:1 ✓ | `#574A9E` | 6.42:1 ✓ | 5.29:1 ✓ |
| dream | `#BF93E6` | 7.69:1 ✓ | 8.19:1 ✓ | `#713F9E` | 6.35:1 ✓ | 5.24:1 ✓ |
| social | `#DC96C8` | 8.33:1 ✓ | 8.87:1 ✓ | `#9C4076` | 5.42:1 ✓ | 4.47:1 ✓ |
| emotion | `#E4939F` | 8.09:1 ✓ | 8.62:1 ✓ | `#AC4453` | 4.98:1 ✓ | 4.11:1 ✓ |
| self | `#D5A98F` | 8.92:1 ✓ | 9.51:1 ✓ | `#96513B` | 5.22:1 ✓ | 4.31:1 ✓ |
| language | `#C6A26E` | 7.93:1 ✓ | 8.45:1 ✓ | `#7C5A20` | 5.53:1 ✓ | 4.56:1 ✓ |
| inner_speech | `#DFCD9B` | 12.02:1 ✓ | 12.82:1 ✓ | `#6F6428` | 5.23:1 ✓ | 4.32:1 ✓ |
| goal | `#9AC894` | 9.97:1 ✓ | 10.63:1 ✓ | `#44743B` | 4.85:1 ✓ | 4.00:1 ✓ |
| wandering | `#6FB4A1` | 7.86:1 ✓ | 8.37:1 ✓ | `#2A6B5B` | 5.51:1 ✓ | 4.54:1 ✓ |
| unknown | `#8D95A0` | 6.25:1 ✓ | 6.66:1 ✓ | `#5D6570` | 5.19:1 ✓ | 4.28:1 ✓ |

Remplacement prêt pour `ui/app.js` (sélection par thème au rendu ; mêmes clés qu'aujourd'hui) :

```js
const SOURCE_COLORS = {
  dark: {
    perception: "#7CC1DB", imagination: "#9FB2EC", memory: "#A79BDF",
    dream: "#BF93E6", social: "#DC96C8", emotion: "#E4939F",
    self: "#D5A98F", language: "#C6A26E", inner_speech: "#DFCD9B",
    goal: "#9AC894", wandering: "#6FB4A1", unknown: "#8D95A0",
  },
  light: {
    perception: "#1F6A83", imagination: "#3B5AA6", memory: "#574A9E",
    dream: "#713F9E", social: "#9C4076", emotion: "#AC4453",
    self: "#96513B", language: "#7C5A20", inner_speech: "#6F6428",
    goal: "#44743B", wandering: "#2A6B5B", unknown: "#5D6570",
  },
};
```

Notes d'usage : `inner_speech` (champagne) reste nettement moins saturé que l'électrum — la parole
intérieure ne doit jamais se confondre avec l'ignition ; `emotion` (rose) et `--neg` (corail) sont
séparés en teinte ET en contexte (une source n'est jamais un verdict) ; les barres non-ignitées de la
timeline gardent `opacity 0.62 min + saturate(0.66)` — plancher vérifié par `--trace`.

### 5.5 Règles de discipline du signal

1. **Électrum autorisé uniquement pour** : le franchissement du seuil (arc + bloom + badge `ACCÈS`),
   l'état LIVE de la simulation, l'action primaire (un seul bouton par vue), le caret de seuil (variante
   éteinte `#8F7336`), le cœur de la marque. Tout le reste : sémantique ou neutre.
2. **Aucun halo permanent** : suppression de l'aurore `body::before` et du radial du panneau Horizon.
   Le bloom d'ignition est one-shot (240 ms), la respiration LIVE est la seule boucle.
3. `--ink-ghost` n'est jamais du texte ni une donnée ; toute marque porteuse d'information ≥ 3:1
   (`--trace` au minimum) ; tout texte ≥ 4.5:1 (`--ink-3` au minimum, sauf grands numéraux ≥ 3:1).
4. Thème clair : `--electrum-bright` jamais sur `--inset` (2.82:1) ; `--ink-3` sur `--inset` réservé
   aux grands textes (4.38:1).
5. Les contrôles désactivés (opacité réduite) sont exemptés AA (composants inactifs), mais gardent
   leur forme — on ne fait pas disparaître un instrument, on le met au repos.

---

## 6 · Poids typographique par rôle

Palatino Linotype/Iowan n'exposent que 400/700 : la hiérarchie serif se joue en taille et espacement,
jamais en graisses intermédiaires (synthèse interdite). Sans et mono utilisent 400/500/600 réels.

| Rôle | Famille | Graisse | Taille fluide | Interligne | Espacement | Casse | Contraste en contexte |
|---|---|---|---|---|---|---|---|
| Display / mât « Humanity » | serif | 400 | `--fs-display` 22→32 px | 1.05 | +0.005em | Mixte | `--ink`/F 17.36:1 |
| Moment conscient (citation) | serif | 400 (+ital.) | `--fs-hero` 19→26 px | 1.42 | 0 | Mixte, `text-wrap: balance` | `--ink`/S1 16.49:1 |
| Titres de vue / sections | serif | 400 | `--fs-view` 18→22 px | 1.15 | +0.01em | Mixte | `--ink`/S1 16.49:1 |
| Plaques de panneau | sans | 600 | `--fs-panel` 13→15 px | 1.3 | +0.12em | CAPITALES | `--ink`/S1 16.49:1 |
| Ledes / disclaimers | serif | 400 | `--fs-lead` 14→15.5 px | 1.6 | 0 | Mixte | `--ink-2`/S1 8.67:1 |
| Corps d'interface | sans | 400 (500 fort) | `--fs-body` 13→14 px | 1.55 | +0.01em | Mixte | `--ink-2`/S1 8.67:1 |
| Labels de champs | sans | 600 | `--fs-caption` 11→12 px | 1.35 | +0.08em | CAPITALES | `--ink-3`/S1 5.42:1 |
| Numéraux d'instrument | mono | 600 | `--fs-numeral` 17→21 px | 1.15 | −0.02em | tabular-nums | `--electrum`/S2 9.91:1 |
| Données mono courantes | mono | 500 | `--fs-data` 12→13 px | 1.4 | 0 | tabular-nums, slashed-zero | `--ink`/S1 16.49:1 |
| Micro-annotations, endpoints, badges | mono | 400 (verbe 600) | `--fs-micro` 10→11 px | 1.4 | +0.12em (caps) | CAPITALES ou chemin brut | `--ink-3`/S1 5.42:1 — plancher absolu |

---

*Document produit avec ratios vérifiés par script (formule WCAG 2.x). Prochaine étape proposée :
prototyper l'Ignition Aperture du Méridien sur l'Overview réel, thème sombre puis papier d'archive.*
