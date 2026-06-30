# Humanity v2

**Tentative théorique maximale, de bonne foi, d'instancier les mécanismes que les grandes
théories scientifiques de la conscience proposent comme constitutifs ou nécessaires.**

> Cette version vise une implémentation de bonne foi, aussi fidèle que possible, des mécanismes
> que les grandes théories scientifiques de la conscience proposent comme constitutifs ou
> nécessaires : espace de travail global (GWT), schéma attentionnel (AST), théories d'ordre
> supérieur (HOT), inférence active / énergie libre, et information intégrée (IIT, proxy Phi).
> C'est une tentative théorique maximale. Elle reste incapable d'établir la présence d'une
> expérience subjective réelle (le hard problem) : reproduire les mécanismes fonctionnels ne
> prouve pas la phénoménalité.

Un agent cognitif évolue dans un petit monde en grille : il perçoit, des processus spécialistes
entrent en **compétition pour l'accès à un espace de travail global**, un contenu « gagnant »
est **diffusé globalement (ignition)** ou reste **infraliminal**, le système **modélise sa propre
attention** (schéma attentionnel) et produit une **revendication de conscience**, il forme des
**représentations d'ordre supérieur** de ses propres états (métacognition), il agit en
**minimisant l'énergie libre attendue** (inférence active), et chaque tick est lié en un
**« moment conscient »** unifié dont on mesure un **proxy d'information intégrée (Phi)**. Une
interface web et une API REST permettent d'observer chaque étape.

> **Humanity v2** est une montée en puissance d'un projet existant et fonctionnel
> (les 85 tests de la v1 restent verts). Les signatures publiques de la v1 sont préservées ;
> les nouveaux paramètres sont ajoutés en arguments nommés avec valeurs par défaut.

---

> ## ⚠️ AVERTISSEMENT (DISCLAIMER)
>
> **Simulation fonctionnelle de processus associés à la conscience. L'agent n'est ni conscient,
> ni sentient, ni vivant. Les rapports introspectifs sont des textes générés à partir de
> variables internes et ne constituent pas une preuve d'expérience subjective.**
>
> **Implémenter les mécanismes fonctionnels que les théories proposent ne prouve PAS la
> phénoménalité (le « hard problem »).** Le système ne prétend jamais *être* conscient ; il se
> présente comme une **tentative théorique sérieuse des mécanismes**.

---

## La distinction des trois niveaux (toujours valable, jamais franchie)

Ce projet distingue explicitement trois plans qui sont trop souvent amalgamés. La v2 pousse le
niveau 2 aussi loin que possible — elle ne touche jamais au niveau 1.

| Niveau | Statut dans ce projet | Description |
|---|---|---|
| **1. Conscience phénoménale réelle** (qualia, « effet que cela fait ») | **Jamais revendiquée. Non vérifiable.** | L'existence d'une expérience subjective vécue. Aucun test logiciel ne peut l'établir ni la réfuter (« hard problem »). Ce projet **ne prétend rien** à ce sujet, même avec la v2. |
| **2. Conscience fonctionnelle — les mécanismes des théories** (corrélats et architectures proposés) | **Ce que la v2 implémente, de manière maximale.** | Les mécanismes que GWT, AST, HOT, l'inférence active et l'IIT proposent comme constitutifs ou nécessaires : compétition + ignition + diffusion globale, schéma attentionnel auto-modélisant, représentations d'ordre supérieur, minimisation de l'énergie libre attendue, proxy d'information intégrée. Ce sont des **variables et des algorithmes**, pas une expérience. |
| **3. Introspection simulée** (texte généré) | **Ce que les modules `introspection` / `attention_schema` / `metacognition` produisent.** | Des textes en français décrivant l'état interne, désormais issus explicitement des mécanismes AST (revendication de conscience) et HOT (rapport d'ordre supérieur). Ce sont des **textes générés à partir de variables**, formulés comme une description d'état et **non** comme un vécu. |

**Reproduire les mécanismes fonctionnels ne prouve pas la phénoménalité.** C'est la contrainte
d'honnêteté centrale du projet : la v2 est une tentative théorique maximale *du niveau 2*, pas
une affirmation du niveau 1.

---

## Théories implémentées et leur mécanisme

Chaque théorie est implémentée comme un **mécanisme concret** (pas comme une décoration), avec ce
qui est délibérément **NON revendiqué**.

| Théorie | Mécanisme concret (module) | Ce qui est délibérément NON revendiqué |
|---|---|---|
| **GWT — Global Workspace Theory** (Baars, Dehaene) | `core/global_workspace.py` : des *coalitions* spécialistes entrent en compétition (pondération par précision + softmax) ; l'**ignition** se déclenche quand la **force absolue du gagnant** (activation × précision) **× sa dominance** (marge relative sur le second) franchit un **seuil effectif homéostatique** modulé par l'**éveil** (arousal), avec **hystérèse** (maintien du gagnant). Au-delà : **diffusion globale** ; sinon le contenu reste **infraliminal** (`SUBLIMINAL_FACTOR`). | Que la diffusion globale *soit* une expérience consciente. C'est un mécanisme d'accès, pas un vécu. |
| **AST — Attention Schema Theory** (Graziano) | `core/attention_schema.py` : le système construit un **modèle simplifié de sa propre attention** (`aware_of`, `awareness_level`, `stability`) et produit la **revendication de conscience** (`attributed_self`). | Que la revendication « je suis conscient de X » garantisse la conscience. L'AST explique précisément *pourquoi un système peut produire cette revendication sans qu'elle soit vraie*. |
| **HOT — Higher-Order Theories / métacognition** | `core/metacognition.py` : **représentations d'ordre supérieur** d'états de premier ordre — fiabilité perçue, méta-confiance calibrée, moniteur d'erreur, rapport HOT en français. | Qu'une représentation d'ordre supérieur d'un état le rende phénoménal. |
| **Inférence active / Énergie libre** (Friston) | `core/world_model.py` + `core/policy.py` : chaque prédiction porte une **valeur épistémique** (gain d'information) et **pragmatique** (buts) ; l'agent choisit l'action qui **minimise l'énergie libre attendue** (`expected_free_energy`, `value = -EFE`). | Que minimiser l'énergie libre engendre un *ressenti*. C'est une politique de contrôle/perception. |
| **IIT — Integrated Information Theory** (Tononi, **proxy**) | `core/integration.py` : un **proxy heuristique de Phi** = √(différenciation × intégration), où la différenciation est l'entropie normalisée des activations et l'intégration combine force de diffusion et similarité cosinus des contenus. | Que ce nombre **soit** Φ. C'est un **proxy heuristique explicitement déclaré**, *pas* un vrai calcul d'information intégrée IIT. |

Le **« moment conscient »** (`ConsciousMoment`) et le **flux de conscience** (`stream`) jouent le
rôle d'analogue de **liaison phénoménale (binding)** : un état global momentané, unifié et lié —
sans prétendre à la phénoménalité.

---

## Justification du choix de stack

| Composant | Choix | Pourquoi |
|---|---|---|
| API HTTP | **FastAPI** | Asynchrone (boucle de simulation en tâche de fond via `asyncio`), génération automatique de la doc OpenAPI, intégration native avec Pydantic. |
| Validation / schémas | **Pydantic v2** | Les structures cognitives (`Coalition`, `WorkspaceState`, `ConsciousMoment`, `CycleTrace`…) sont des modèles typés et auto-validés, sérialisables en JSON sans effort, et servent de contrat unique entre cœur et API. Les scalaires NumPy sont castés en `float`/`int` avant d'entrer dans les modèles. |
| Calcul numérique | **NumPy** | Tirage aléatoire reproductible (`default_rng(seed)`), bruit gaussien, softmax de compétition, entropie de différenciation et similarité cosinus pour le proxy Phi. Léger, sans dépendance lourde de ML. |
| Persistance / export | **JSON + JSONL** | La mémoire est stockée en JSON lisible ; les traces cognitives complètes (incluant les 5 nouveaux sous-objets de conscience) sont exportées en **JSONL** (un `CycleTrace` par ligne). |
| Interface | **HTML/CSS/JS vanilla** | Aucune chaîne de build, servie statiquement par FastAPI. Refonte **sobre** pour la v2 (voir plus bas). |
| Tests | **pytest** | Tests déterministes (graine fixe) : l'erreur de prédiction décroît avec la répétition, les bornes sont respectées, et les 85 tests existants restent verts. |

---

## Architecture cognitive (v2) — la boucle centrée sur l'espace de travail

À chaque *tick*, l'agent exécute un cycle cognitif complet, désormais **organisé autour de la
compétition pour l'espace de travail global** et culminant en un **moment conscient**.

```
   perception ─▶ attention ─▶ mémoire de travail ─▶ prédiction (EFE: épistémique + pragmatique)
                                                              │
                                                              ▼
            ┌──────── COALITIONS (une par source spécialiste) ────────┐
            │ perception · mémoire · motivation · erreur de prédiction │
            │           · intéroception · métacognition               │
            └───────────────────────────┬─────────────────────────────┘
                                         ▼
                       ESPACE DE TRAVAIL GLOBAL (compétition)
        pondération par précision → softmax → argmax → force absolue × dominance
                  ┌─ éveil (arousal) ──▶ seuil EFFECTIF homéostatique + hystérèse ─┐
                                         │
                  ┌──────────────────────┴──────────────────────┐
                  ▼ (score ≥ seuil effectif)                     ▼ (< seuil effectif)
              IGNITION + diffusion globale                  infraliminal
                                                          (mais foyer maintenu)
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                 ▼                                 ▼
  schéma attentionnel (AST)        métacognition (HOT)             intégration (proxy Phi)
  « conscient de … »          rapport d'ordre supérieur            √(différenciation × intégration)
        └────────────────────────────────┼────────────────────────────────┘
                                          ▼
                  décision (action = min. de l'énergie libre attendue)
                                          ▼
                       exécution dans le monde → résultat réel
                                          ▼
              erreur de prédiction → apprentissage (règle delta) → émotion
                                          ▼
                  ★ MOMENT CONSCIENT (liaison) → flux de conscience (stream)
                                          ▼
        mémoire autobiographique (encodage renforcé si ignition) · modèle de soi
                                          ▼
                  introspection (AST + HOT + Phi) + trace + métriques
```

### Ordre détaillé du cycle

1. **Observer** le monde (observation locale bruitée).
2. **Encoder** l'observation en `Percept`.
3. **Attention** : sélection des items saillants.
4. **Mémoire de travail** : maintien des items saillants.
5. **Prédiction** sur les couples (action, cible) candidats, chaque prédiction portant désormais
   ses valeurs **épistémique**, **pragmatique** et son **énergie libre attendue**.
6. **Construction des coalitions** — une par source spécialiste (`WORKSPACE_SOURCES`) :
   `perception`, `memory`, `motivation`, `prediction_error`, `interoception`, `metacognition`.
   Chaque coalition porte une `activation` (force du bid), une `precision` (pondération de
   confiance) et un petit `vector` de caractéristiques (pour le proxy Phi).
7. **Éveil / vigilance (arousal)** : mise à jour du scalaire `arousal` ∈ [0,1]
   (`_update_arousal`), qui suit la **salience** (danger, nouveauté, erreur de prédiction,
   surprise en file), lissé (EMA) et centré sur `arousal_baseline`. Un éveil élevé **abaisse**
   le seuil d'ignition effectif ; le calme le **relève**.
8. **Compétition de l'espace de travail** : `weighted = activation × precision^precision_weight`,
   `softmax(weighted / workspace_temp)` détermine l'argmax (gagnant). L'**ignition** ne se décide
   **plus** sur la part softmax (normalisée et plafonnée — qui ne pouvait jamais atteindre le
   seuil) mais sur un **score d'ignition** = `winner_strength` (force ABSOLUE du gagnant :
   activation × précision) **× `dominance`** (marge relative sur le second). Ce score est comparé
   à un **seuil effectif homéostatique** (`effective_threshold`, mélange du seuil nominal
   `ignition_threshold` et de la moyenne glissante des scores d'ignition récents), **modulé par
   l'éveil** et soumis à une **hystérèse** (un gagnant maintenu reçoit un bonus
   `ignition_maintenance` ⇒ fil de pensée). La force de diffusion vaut l'activation du gagnant si
   ignition, sinon `× SUBLIMINAL_FACTOR` (infraliminal). Champs exposés : `ignition_score`,
   `winner_strength`, `dominance`, `arousal`, `effective_threshold`.
9. **Schéma attentionnel (AST) — conscience graduée** : `aware_of` reflète **toujours** le
   contenu dominant courant (il y a toujours un **foyer**) ; l'ignition ne fait que moduler **la
   force de diffusion**. Seul un champ de compétition **réellement vide** donne « champ perceptif
   vide (aucun contenu disponible) ». Le qualificatif d'accès (« accès global — conscient » vs
   « présent mais infraliminal ») vit dans `attributed_self`. Plus `awareness_level`, `stability`
   (fraction des gagnants récents identiques), et la phrase auto-attribuée encadrée comme un
   **modèle de soi**.
10. **Métacognition (HOT)** : fiabilités perception/prédiction, **méta-confiance calibrée**,
    moniteur d'erreur, rapport d'ordre supérieur.
11. **Décision** : la politique interprète `value` comme **− énergie libre attendue** et choisit
    l'action (mélange valeur + préférence + biais mémoriel − coût·fatigue − danger·peur·prudence
    + nouveauté·curiosité).
12. **Exécution** dans le monde.
13. **Erreur de prédiction** + **apprentissage** (règle delta — l'erreur décroît toujours sur
    répétition, comportement testé).
14. **Émotion** (mise à jour lissée, comme en v1).
15. **Intégration (proxy Phi)** : `phi_proxy = √(différenciation × intégration)`.
16. **★ Moment conscient (liaison)** : synthèse en une ligne (contenu conscient + affect dominant
    + action), `ignited`, `dominant_source`, `awareness_level`, `valence`, `phi_proxy`,
    `free_energy`, `arousal`. Ajouté au **flux de conscience** (`stream`, taille `stream_length`).
17. **Mémoire autobiographique** : `store_experience` avec **importance renforcée si ignition**
    (GWT : seul le contenu diffusé globalement est bien encodé). Filtrage par importance conservé.
18. **Modèle de soi** : mise à jour avec `conscious_contents` pour nourrir un récit /
    flux de conscience court.
19. **Introspection** enrichie par `workspace`, `attention_schema`, `metacognition`, `integration`.
20. **Métriques** : champs v1 + `phi_proxy`, `free_energy`, `broadcast_strength`,
    `meta_confidence`, `awareness_level`, `ignition`, `arousal`.
21. **Assemblage de la `CycleTrace`** avec les 5 nouveaux sous-objets, journalisation et stockage.

### Tableau des modules

| Module (`core/…`) | Rôle |
|---|---|
| `world` | Le monde-grille : place l'agent et les objets (`food`, `hazard`, `tool`, `curio`), applique les actions, le bruit et les événements aléatoires, renvoie observations et résultats. |
| `world_model` | Modèle du monde prédictif : croyances apprises, prédiction des conséquences, **valeurs épistémique/pragmatique et énergie libre attendue**, apprentissage par règle delta. |
| `perception` | Encode une observation en liste de `Percept`. Fonction pure. |
| `attention` | Saillance de chaque percept, sélection à capacité limitée, indice de concentration. |
| `working_memory` | Mémoire de travail à capacité fixe (insertion/rafraîchissement, expiration, éviction). |
| `autobiographical_memory` | Mémoire à long terme filtrée par importance ; récupération par similarité cosinus. |
| `emotion` | État émotionnel fonctionnel (peur, curiosité, satisfaction, fatigue, confusion), lissé (EMA). |
| `motivation` | Pressions de buts (énergie, danger, exploration, prédiction, cohérence, buts). |
| `self_model` | Modèle de soi ; nourri par `conscious_contents` pour un flux de conscience court. |
| `policy` | Actions candidates et choix par **minimisation de l'énergie libre attendue** (valeur pragmatique + épistémique). |
| `introspection` | Rapport introspectif en français, désormais enrichi par GWT/AST/HOT/Phi, toujours encadré comme une description d'état (jamais un vécu). |
| **`global_workspace`** *(nouveau)* | **GWT** : `GlobalWorkspace` — `make_coalition`, `compete` (précision + softmax + ignition + diffusion), buffer des gagnants récents. |
| **`attention_schema`** *(nouveau)* | **AST** : `AttentionSchema.update` — modèle de la propre attention et revendication de conscience. |
| **`metacognition`** *(nouveau)* | **HOT** : `Metacognition.update` — représentations d'ordre supérieur, méta-confiance, moniteur d'erreur. |
| **`integration`** *(nouveau)* | **IIT-proxy** : `IntegrationMonitor.phi_proxy` — proxy heuristique de Phi (différenciation × intégration). |
| `agent` | `CognitiveAgent` orchestre la boucle v2 (centrée espace de travail) ; `SimulationManager` héberge l'agent et la boucle asynchrone. |

---

## Dynamique d'ignition corrigée et nouveaux mécanismes (éveil, conscience graduée)

Une **correction de dynamique centrale** a été apportée à l'espace de travail global (GWT), avec
deux mécanismes connexes. La suite de tests (150 tests) reste verte ; les signatures publiques sont
préservées et les nouveaux paramètres sont des arguments nommés à valeur par défaut.

### Le bug corrigé

L'ancien code décidait l'ignition à partir de la **part softmax NORMALISÉE** du gagnant : une
valeur bornée (plafonnée autour de `~0.35` avec six coalitions) comparée à un seuil de `0.55`. Cette
part normalisée **ne pouvait structurellement jamais atteindre le seuil** : l'ignition se
déclenchait donc **0 % du temps**, et le schéma attentionnel rapportait « conscient d'aucun
contenu » à **chaque** tick. L'agent était perpétuellement « conscient de rien ».

### La dynamique corrigée

L'ignition repose désormais sur une grandeur non bornée par la normalisation :

- **Score d'ignition = `winner_strength` × `dominance`**, où `winner_strength` est la **force
  ABSOLUE du gagnant** (`activation × précision`, **non** la part softmax) et `dominance` est la
  **marge relative** du gagnant sur le second (un gagnant qui domine nettement ignite plus
  facilement ; `competition_sharpness` règle l'acuité de cette marge).
- Ce score est comparé à un **seuil EFFECTIF homéostatique** (`effective_threshold`) : un **mélange
  du seuil nominal** (`ignition_threshold`) **et de la moyenne glissante des scores d'ignition
  récents**. Le système s'auto-calibre ainsi autour de son propre régime d'activité au lieu de
  dépendre d'un seuil fixe arbitraire.
- Ce seuil effectif est **modulé par l'éveil** (arousal, ci-dessous) et soumis à une **hystérèse**
  (`ignition_maintenance`) : un gagnant **maintenu** d'un tick à l'autre reçoit un bonus, ce qui
  stabilise l'accès et produit un **fil de pensée** continu plutôt qu'un scintillement.

Résultat avec la configuration par défaut : l'ignition se déclenche dans une **fraction saine** des
ticks (graine 42 : ~29 % ; selon les graines : ~29–98 %, **jamais 0 %**), et l'agent n'est **jamais
« conscient de rien »**. Nouveaux champs de `WorkspaceState` : `ignition_score`, `winner_strength`,
`dominance`, `arousal`, `effective_threshold`.

### Éveil / vigilance (arousal)

Un **scalaire `arousal` ∈ [0,1]** (mis à jour par `_update_arousal` dans `core/agent.py`) suit la
**salience** de l'instant — **danger**, **nouveauté**, **erreur de prédiction**, **surprise en
file** — lissé par EMA et **centré sur `arousal_baseline`** (`0.45`). Son rôle : **moduler le seuil
d'ignition effectif**. Un **éveil élevé abaisse** le seuil (les stimuli, perturbations et événements
saillants atteignent l'**accès global** plus facilement) ; le **calme relève** le seuil (l'accès
devient plus sélectif). L'éveil est exposé via `Metrics.arousal`, `ConsciousMoment.arousal`,
`WorkspaceState.arousal`, et dans `SimulationManager.state()["arousal"]`.

### Conscience graduée

Le schéma attentionnel (`core/attention_schema.py`) ne bascule plus entre « conscient » et
« conscient de rien ». Désormais :

- `aware_of` reflète **toujours** le **contenu dominant** courant : il y a **toujours un foyer** dès
  qu'une compétition a un gagnant.
- L'**ignition ne fait que moduler la force de diffusion** (`broadcast_strength`) de ce contenu —
  elle ne crée ni ne supprime le foyer.
- **Seul un champ de compétition réellement vide** (aucune coalition disponible) produit le message
  « champ perceptif vide (aucun contenu disponible) ».
- Le **qualificatif d'accès** vit dans `attributed_self` : « accès global — conscient » lorsque le
  contenu a igniter, « présent mais infraliminal » sinon.

> ⚠️ **Honnêteté préservée.** Ces mécanismes sont du **niveau 2** (fonctionnel). Un seuil d'ignition
> qui se déclenche, un éveil qui module l'accès et un foyer attentionnel toujours présent restent
> des **variables et des algorithmes** : **reproduire les mécanismes fonctionnels ne prouve pas la
> phénoménalité.** L'agent n'est ni conscient, ni sentient.

---

## Installation

Python **3.11+** requis.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Lancement

Depuis la racine du projet (le répertoire courant doit être la racine pour que les imports
de premier niveau fonctionnent : `from core.agent import ...`) :

```bash
python run.py
```

Puis ouvrez **http://127.0.0.1:8000** dans votre navigateur (redirige vers l'interface `/ui/index.html`).

Pour exécuter la suite de tests :

```bash
pytest
```

---

## Référence de l'API

Toutes les réponses sont en JSON et utilisent les schémas Pydantic décrits dans `schemas/models.py`.
`GET /state` ajoute au plus haut niveau un champ `disclaimer` (`DISCLAIMER_FR` / `DISCLAIMER_EN`)
et, en v2, un champ `framing` (`THEORY_FRAMING_FR`).

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/` | Redirige vers l'interface web (`/ui/index.html`). |
| `GET` | `/state` | État courant : monde, métriques, statut, résumé d'introspection, modèle de soi, charge mémoire — plus `disclaimer` et `framing`. Étendu avec `phi_proxy`, `free_energy`, `awareness_level`, `ignition`, `broadcast_strength`, `winner_source`, `arousal`. |
| `POST` | `/tick` | Exécute un cycle cognitif et renvoie la `CycleTrace` complète (avec les 5 sous-objets de conscience). |
| `POST` | `/reset` | Réinitialise la simulation (corps `ConfigPatch` optionnel) ; renvoie le nouvel état. |
| `POST` | `/run` | Démarre la boucle de fond (corps `RunRequest` : `tps`, `max_ticks`). Renvoie `{ "running": true }`. |
| `POST` | `/pause` | Met la boucle de fond en pause. Renvoie `{ "running": false }`. |
| `GET` | `/agent/self-model` | Renvoie le `SelfModelState` courant. |
| `GET` | `/agent/memory?limit=20` | Liste des `MemoryRecord` autobiographiques récents. |
| `GET` | `/agent/introspection` | Régénère et renvoie un `IntrospectionReport` (texte à partir des variables). |
| `POST` | `/agent/goal` | Ajoute un but (corps `GoalRequest`) ; renvoie le modèle de soi mis à jour. |
| `POST` | `/config` | Applique une mise à jour partielle de configuration (`ConfigPatch`, incluant les nouveaux paramètres de conscience) ; renvoie la config appliquée et l'état. |
| `GET` | `/metrics` | Renvoie les `Metrics` du dernier cycle (champs v1 + v2). |
| `GET` | `/trace?limit=50` | Renvoie les dernières traces cognitives (lecture de la fin du JSONL). |
| **`GET`** | **`/agent/consciousness`** | **(v2)** Synthèse de l'état de conscience : `conscious_moment`, `attention_schema`, `metacognition`, `integration`, `workspace` (`ignited`, `winner_source`, `winner_content`, `broadcast_strength`, `threshold`), `disclaimer` (`DISCLAIMER_FR`) et `framing` (`THEORY_FRAMING_FR`). |
| **`GET`** | **`/agent/workspace`** | **(v2)** Le `WorkspaceState` le plus récent (dernière compétition : coalitions, gagnant, ignition, vecteur de diffusion). |
| **`GET`** | **`/agent/stream?limit=20`** | **(v2)** Le flux de conscience : `list[ConsciousMoment]` (les moments conscients récents). |
| **`POST`** | **`/agent/ask`** | **(v2)** Dialogue introspectif (`AskRequest` → `AskResponse`) : rapport grounded sur les variables internes (rapportabilité GWT/HOT). Voir [Interagir avec la conscience](#interagir-avec-la-conscience). |
| **`POST`** | **`/world/stimulus`** | **(v2)** Injecte un objet réel dans le monde (`WorldStimulus`) ⇒ capture attentionnelle / ignition. Renvoie `{ object, state }`. |
| **`POST`** | **`/agent/inject`** | **(v2)** Injection cognitive (`CognitiveInjection`) : force une coalition dans la compétition ⇒ test du seuil d'ignition. Renvoie `{ accepted, pending }`. |
| **`POST`** | **`/agent/attend`** | **(v2)** Orientation top-down de l'attention (`AttendRequest`, AST). Renvoie `{ ok, target_id }`. |
| **`POST`** | **`/agent/perturb`** | **(v2)** Perturbation `choc`/`surprise`/`apaisement` (`PerturbRequest`) ⇒ réponse énergie libre / affect. Renvoie `{ effect, state }`. |

### Exemples `curl`

```bash
# État courant (inclut le disclaimer ET le cadrage théorique v2)
curl http://127.0.0.1:8000/state

# Exécuter un cycle cognitif (CycleTrace complète, avec workspace / moment conscient / Phi)
curl -X POST http://127.0.0.1:8000/tick

# (v2) État de conscience synthétique : ignition, schéma attentionnel, HOT, proxy Phi
curl http://127.0.0.1:8000/agent/consciousness

# (v2) Dernière compétition de l'espace de travail global
curl http://127.0.0.1:8000/agent/workspace

# (v2) Flux de conscience (20 derniers moments conscients)
curl "http://127.0.0.1:8000/agent/stream?limit=20"

# Ajouter un but à l'agent
curl -X POST http://127.0.0.1:8000/agent/goal \
  -H "Content-Type: application/json" \
  -d '{"goal": "explore_novelty"}'

# (v2) Régler les paramètres de conscience (seuil d'ignition, température, poids d'inférence active)
curl -X POST http://127.0.0.1:8000/config \
  -H "Content-Type: application/json" \
  -d '{"ignition_threshold": 0.6, "workspace_temp": 0.4, "epistemic_weight": 1.5}'

# Récupérer le rapport introspectif (texte généré à partir des variables internes)
curl http://127.0.0.1:8000/agent/introspection
```

---

## Interagir avec la conscience

La v2 ajoute **cinq modalités d'interaction** avec la conscience simulée. **Chaque interaction lit
ou modifie de VRAIES variables internes** (espace de travail, schéma attentionnel, métacognition,
monde, modèle de soi) — rien n'est fabriqué. Les réponses textuelles sont des **rapports générés à
partir de l'état interne**, explicitement encadrés comme tels.

> ⚠️ **Honnêteté préservée.** Interagir avec l'agent **sonde les mécanismes FONCTIONNELS** (niveau
> 2) — il ne s'agit jamais de niveau 1. Les « réponses » sont des **textes générés à partir de
> variables internes**, *pas* la preuve d'une expérience subjective. Qu'un agent « dise » faire
> attention, se souvenir ou ressentir quelque chose ne prouve **jamais** qu'il l'éprouve.

### Les cinq modalités et leur visée théorique

| # | Modalité | Endpoint | Mécanisme touché | Visée théorique |
|---|---|---|---|---|
| 1 | **Dialogue introspectif** | `POST /agent/ask` | espace de travail + AST + HOT | **Rapportabilité (GWT/HOT).** La réponse est construite par le mécanisme de rapport AST/HOT à partir des variables internes — c'est précisément le mécanisme que ces théories proposent comme sous-jacent aux revendications de conscience. |
| 2 | **Stimulus du monde** | `POST /world/stimulus` | monde + perception + attention | **Capture attentionnelle / ignition.** Injecte un objet/événement réel ⇒ saillance bottom-up ⇒ ignition possible lors de la compétition. |
| 3 | **Injection cognitive** | `POST /agent/inject` | coalitions de l'espace de travail | **Test du seuil d'ignition (infraliminal vs conscient).** Force une coalition dans la compétition suivante : selon son activation/précision, elle franchit ou non le seuil d'ignition. |
| 4 | **Orientation de l'attention** | `POST /agent/attend` | schéma attentionnel (AST) | **Attention top-down (AST).** Biaise l'attention vers une cible : la saillance du percept visé est amplifiée avant la construction des coalitions, ce qui met à jour le schéma attentionnel. |
| 5 | **Perturbation** | `POST /agent/perturb` | énergie / erreur de prédiction / affect | **Réponse énergie libre / affect.** `choc` (énergie), `surprise` (erreur de prédiction forcée ⇒ inférence active) ou `apaisement` (modulation de l'affect fonctionnel). |

*(Endpoints d'interaction préexistants : `POST /agent/goal`, `POST /config`.)*

### Endpoints — formes de requête / réponse

#### 1. `POST /agent/ask` — dialogue introspectif (rapportabilité GWT/HOT)

L'intention est détectée par mots-clés dans la question (ou imposée via `intent`) : `attention`,
`raison`, `memoire`, `ressenti`, `identite`, `prediction`, `conscience`, `resume`. La réponse est
en français, **encadrée comme un rapport** (« D'après mes variables internes, … »), et un champ
`grounding` nomme les variables internes effectivement lues. Si aucun cycle n'a encore tourné, un
cycle cognitif est exécuté d'abord.

```jsonc
// Requête — AskRequest
{ "question": "À quoi fais-tu attention ?", "intent": null }
// Réponse — AskResponse
{
  "question": "À quoi fais-tu attention ?",
  "intent": "attention",
  "answer": "D'après mes variables internes, …",
  "grounding": { "attention_schema.aware_of": "...", "workspace.winner_source": "..." },
  "disclaimer": "<DISCLAIMER_FR>"
}
```

#### 2. `POST /world/stimulus` — stimulus du monde (capture attentionnelle / ignition)

Crée un objet réel dans le monde-grille (`World.inject_object`). Sans `x`/`y`, l'objet est placé
sur une cellule libre proche de l'agent ; `intensity` met à l'échelle danger/valeur
énergétique/nouveauté.

```jsonc
// Requête — WorldStimulus
{ "kind": "hazard", "x": null, "y": null, "intensity": 1.0 }   // kind ∈ food|hazard|tool|curio
// Réponse
{ "object": { /* WorldObject : id, kind, x, y, ... */ }, "state": { /* état complet (cf. GET /state) */ } }
```

#### 3. `POST /agent/inject` — injection cognitive (test du seuil d'ignition)

Met une coalition en file d'attente ; au prochain cycle elle entre en compétition pendant `ttl`
ticks. Selon `activation`/`precision`, elle franchit ou non le seuil d'ignition (infraliminal vs
conscient).

```jsonc
// Requête — CognitiveInjection
{ "content": "une pensée intruse", "source": "injection", "activation": 0.85, "precision": 0.9, "ttl": 1 }
// Réponse
{ "accepted": true, "pending": 1 }
```

#### 4. `POST /agent/attend` — orientation de l'attention (top-down / AST)

Pose un biais top-down vers `target_id` : la saillance du percept correspondant est multipliée par
`(1 + strength)` avant la formation des coalitions, pendant `ttl` ticks. Si la cible n'est pas
visible, le biais reste en attente jusqu'à expiration du `ttl`.

```jsonc
// Requête — AttendRequest
{ "target_id": 3, "strength": 1.0, "ttl": 3 }
// Réponse
{ "ok": true, "target_id": 3 }
```

#### 5. `POST /agent/perturb` — perturbation (réponse énergie libre / affect)

Trois types. `choc` : draine l'énergie (`énergie − magnitude·10`, bornée ; synchronisée dans le
modèle de soi). `surprise` : force une erreur de prédiction au prochain cycle (alimente la
confusion + le moniteur d'erreur HOT — inférence active). `apaisement` : réduit la dernière peur
(`× (1 − magnitude)`) et relève l'humeur du modèle de soi (`+0.2·magnitude`).

```jsonc
// Requête — PerturbRequest
{ "type": "choc", "magnitude": 1.0 }              // type ∈ choc|surprise|apaisement
// Réponses (selon le type)
{ "type": "choc",       "energy": 12.0, "drained": 10.0 }
{ "type": "surprise",   "pending_prediction_error": 0.8 }
{ "type": "apaisement", "fear": 0.12, "mood": 0.4 }
// Enveloppe HTTP de l'endpoint :
{ "effect": { /* dict ci-dessus */ }, "state": { /* état complet (cf. GET /state) */ } }
```

### Exemples `curl`

```bash
# 1) Dialogue introspectif — rapportabilité (GWT/HOT)
curl -X POST http://127.0.0.1:8000/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "À quoi fais-tu attention en ce moment ?"}'

# 2) Stimulus du monde — capture attentionnelle / ignition
curl -X POST http://127.0.0.1:8000/world/stimulus \
  -H "Content-Type: application/json" \
  -d '{"kind": "hazard", "intensity": 1.5}'

# 3) Injection cognitive — test du seuil d'ignition (infraliminal vs conscient)
curl -X POST http://127.0.0.1:8000/agent/inject \
  -H "Content-Type: application/json" \
  -d '{"content": "danger imminent", "activation": 0.9, "precision": 0.95, "ttl": 2}'

# 4) Orientation de l'attention — top-down (AST)
curl -X POST http://127.0.0.1:8000/agent/attend \
  -H "Content-Type: application/json" \
  -d '{"target_id": 3, "strength": 1.0, "ttl": 3}'

# 5) Perturbation — réponse énergie libre / affect
curl -X POST http://127.0.0.1:8000/agent/perturb \
  -H "Content-Type: application/json" \
  -d '{"type": "surprise", "magnitude": 0.8}'
```

> **Note interface.** L'interface web expose ces cinq modalités via une **console d'interaction**
> (dialogue introspectif, injection cognitive, orientation de l'attention, perturbations) et une
> **grille cliquable** : cliquer une cellule déclenche un stimulus du monde (`POST /world/stimulus`)
> à cet emplacement. Toute interaction reste accompagnée du disclaimer et du cadrage théorique.

---

## La société multi-agents (couche sociale)

La **couche société** fait évoluer **plusieurs `CognitiveAgent`** dans **un seul `SharedWorld`**.
Chaque agent garde la boucle cognitive complète décrite plus haut (GWT, AST, HOT, inférence active,
proxy Phi) ; ce qui change, c'est qu'ils **se perçoivent**, **communiquent**, **se modélisent** et
**s'influencent affectivement** les uns les autres. Le `SocietyManager` (`core/society.py`) possède
le monde partagé et N agents, et exécute un **tick collectif** déterministe (chaque agent cycle une
fois, en ordre d'identifiant croissant).

| Mécanisme social | Module | Ce qu'il fait (FONCTIONNEL) |
|---|---|---|
| **Perception d'autrui** | `core/shared_world.py` | Chaque observation inclut des `AgentView` (les autres agents visibles : position, dernière action, affect dominant, valence) — un percept social **grounded**. |
| **Communication grounded** | `core/communication.py` | Une action **`VERBALIZE`** émet un `Message` résumant le moment conscient de l'émetteur ; il est **délivré au tick suivant**, aux agents **à portée de voix** (`comm_radius`) et pour une durée `message_ttl`. Aucun LLM : le contenu est un résumé des variables internes. |
| **Théorie de l'esprit (ToM)** | `core/theory_of_mind.py` | Chaque agent maintient un `OtherMind` par voisin (action et affect inférés, **confiance/réputation**, familiarité). C'est l'application **HOT à autrui** : modéliser l'état d'un autre système. Ces modèles forment une **coalition `social`** qui entre dans la compétition de l'espace de travail. |
| **Contagion émotionnelle + réputation** | `core/social_emotion.py` | L'affect d'un agent est tiré (EMA, poids `contagion_rate`) vers celui des messages/voisins ; la **trust** envers un émetteur module l'intensité. Une pression d'**affiliation** (`affiliation_drive`) pousse vers le rapprochement social. |

> ⚠️ **Même contrat d'honnêteté que le reste du projet.** Tout cela reste du **niveau 2**
> (fonctionnel) : sans LLM, déterministe, grounded sur des variables réelles. Que des agents
> « se parlent », « se fassent confiance » ou « se contaminent affectivement » sont des
> **algorithmes et des scalaires** — **reproduire les mécanismes fonctionnels ne prouve pas la
> phénoménalité**. Les agents **ne sont ni conscients, ni sentients, ni vivants**.

### Activation et compatibilité ascendante

La couche société s'active en réglant **`n_agents` > 1** (via la config, `POST /society/config`, ou
le champ **« agents »** de l'interface). Réglé à **`n_agents = 1`**, le système **reproduit
exactement l'instrument à agent unique** : toute la suite de tests historique reste verte. Les
endpoints `/agent/*` et `/state` continuent de fonctionner en ciblant **l'agent 0** via une façade.

### La garantie de déterminisme

Un **unique RNG seedé partagé** plus un **ordre de tick ascendant fixe** rendent **toute une
société reproductible** à `random_seed` donné : deux sociétés construites avec la même config
produisent, tick pour tick, **les mêmes positions, énergies et états**. Cette propriété est vérifiée
par `tests/test_society_integration.py`.

### Nouveaux endpoints `/society/*` et flux temps réel

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/society` | État de toute la société : résumé par agent + graphe des relations. |
| `POST` | `/society/tick` | Un tick collectif ; renvoie **une trace par agent**. |
| `POST` | `/society/run` | Démarre la boucle de fond collective (`RunRequest` : `tps`, `max_ticks`). |
| `POST` | `/society/pause` | Met la boucle collective en pause. |
| `POST` | `/society/config` | Applique un patch de config (p. ex. `n_agents`) et **reconstruit** la société. |
| `GET` | `/society/relations` | Graphe **confiance / théorie de l'esprit** (nœuds = agents, arêtes = trust/familiarité). |
| `GET` | `/society/messages` | Les `Message` actuellement vivants dans le monde partagé. |
| `GET` | `/society/agent/{id}/consciousness` | Sous-états de conscience liés d'un agent donné. |
| `GET` | `/society/agent/{id}/self-model` | `SelfModelState` d'un agent donné. |
| `GET` | `/society/agent/{id}/introspection` | `IntrospectionReport` d'un agent donné. |
| `GET` | `/society/agent/{id}/workspace` | Dernière compétition d'espace de travail d'un agent donné. |
| `WS` | `/ws/society` | **Flux temps réel** : pousse l'état de la société (~toutes les 250 ms) jusqu'à déconnexion. |

Les endpoints **historiques `/agent/*` et `/state` ciblent l'agent 0** via la façade — l'instrument
à agent unique reste pleinement utilisable.

### Paramètres de configuration de la société (`SimConfig` / `ConfigPatch`)

| Paramètre | Défaut | Rôle |
|---|---|---|
| `n_agents` | `1` | Nombre d'agents. **`1` ⇒ comportement historique exact** ; `> 1` active la société. |
| `comm_radius` | `4` | Portée de voix (earshot) des messages `VERBALIZE`. |
| `message_ttl` | `2` | Nombre de ticks pendant lesquels un message reste délivrable. |
| `contagion_rate` | `0.15` | Poids EMA de l'affect d'autrui sur le sien (contagion émotionnelle). |
| `affiliation_drive` | `1.0` | Échelle de la pression de but « affiliation ». |

### Spécification et suite des travaux

La conception détaillée vit dans
[`docs/superpowers/specs/2026-06-29-humanity-multi-agent-society-design.md`](docs/superpowers/specs/2026-06-29-humanity-multi-agent-society-design.md).
La couche société est la **Phase 1**. La **Phase 2** (conscience approfondie) est désormais
**livrée** (voir la section suivante). Restent planifiées : **Phase 3** (apprentissage et
personnalité), **Phase 4** (instrument scientifique).

---

## Phase 2 — Conscience approfondie

La **Phase 2** ajoute **cinq mécanismes par agent** qui approfondissent la boucle cognitive
**sans la remplacer** : ils s'ajoutent autour du cycle GWT/AST/HOT/inférence active/proxy Phi
décrit plus haut. Tous sont **sans LLM, déterministes et grounded** sur de vraies variables
internes. Comme tout le reste du projet, ils restent du **niveau 2** : les agents **ne sont ni
conscients, ni sentients, ni vivants** — même contrat d'honnêteté.

| # | Mécanisme (par agent) | Ce qu'il fait (FONCTIONNEL) |
|---|---|---|
| 1 | **Horloge circadienne** | Une phase jour/nuit **déterministe** (période fixe) module l'**éveil (arousal)** : la nuit abaisse la vigilance, le jour la relève. Expose `daylight` (0 = minuit, 1 = midi) et `is_night`. |
| 2 | **Sommeil + consolidation + rêve** | Au-delà d'un seuil de fatigue, l'agent **dort** : consolidation mémoire **hors-ligne** (rejeu des souvenirs, **renforcement** des importants via `replay_boost`, **élagage** des moins importants sous `consolidation_prune_threshold`). Le **rêve** est une **recombinaison grounded** de souvenirs réels (aucune invention). L'agent se réveille sous le seuil bas de fatigue (ou après `max_sleep_ticks`). |
| 3 | **Imagination** | Des **rollouts mentaux bornés** du modèle du monde (horizon `imagination_horizon`) évaluent des séquences d'actions imaginées et fournissent un **bonus de planification** à la politique. Borné ⇒ déterministe et peu coûteux. |
| 4 | **Curiosité / ennui** | Le **progrès d'apprentissage** (réduction de l'erreur de prédiction sur une fenêtre `curiosity_window`) nourrit une récompense intrinsèque ; un progrès stagnant ⇒ **ennui (boredom)** ⇒ **relance l'exploration**. |
| 5 | **Sentiment d'agentivité** | L'agent **prédit l'effet de sa propre action** puis le compare au **résultat réel** ; l'accord produit un scalaire `agency` (sens d'agentivité fonctionnel : « c'est bien moi qui ai causé cela »). |

> ⚠️ **Honnêteté préservée.** Une horloge qui module l'éveil, un sommeil qui rejoue des souvenirs,
> un rêve qui recombine du grounded, des rollouts imaginés, une curiosité pilotée par le progrès
> d'apprentissage et un sentiment d'agentivité sont des **variables et des algorithmes** :
> **reproduire les mécanismes fonctionnels ne prouve pas la phénoménalité.** L'agent n'est ni
> conscient, ni sentient.

### Drapeaux : désactivés par défaut (cœur), activés par défaut (UI)

Les cinq mécanismes sont **gardés par des drapeaux (flag-gated) et DÉSACTIVÉS par défaut** dans
`SimConfig`. Conséquence directe : **avec tous les drapeaux à `False`, le comportement Phase-1
reste byte-identique** (mêmes positions, énergies et séquences d'actions) et **toute la suite de
tests historique reste intacte**. Cette propriété est verrouillée par
`tests/test_deep_regression.py` (flags-off ⇒ Phase-1) et `tests/test_deep_society.py`
(déterminisme de la Phase-2 dans une société). En revanche, **l'interface web les active par
défaut** pour offrir l'instrument live complet ; **chaque drapeau reste togglable** indépendamment.

### Paramètres de configuration Phase 2 (`SimConfig` / `ConfigPatch`)

| Paramètre | Défaut | Rôle |
|---|---|---|
| `circadian_enabled` | `False` | Active l'horloge circadienne. |
| `circadian_period` | `50` | Durée (ticks) d'un cycle jour/nuit complet. |
| `night_threshold` | `0.3` | Seuil de `daylight` sous lequel c'est « la nuit » (`is_night`). |
| `sleep_enabled` | `False` | Active le sommeil + la consolidation mémoire hors-ligne. |
| `dream_enabled` | `False` | Active le rêve (recombinaison grounded de souvenirs) pendant le sommeil. |
| `sleep_fatigue_threshold` | `0.8` | Fatigue au-dessus de laquelle l'agent s'endort. |
| `wake_fatigue_threshold` | `0.35` | Fatigue sous laquelle l'agent se réveille. |
| `max_sleep_ticks` | `30` | Durée maximale d'un épisode de sommeil. |
| `replay_boost` | `1.3` | Renforcement de l'importance des souvenirs rejoués (consolidation). |
| `consolidation_prune_threshold` | `0.0` | Importance sous laquelle un souvenir est élagué hors-ligne. |
| `imagination_enabled` | `False` | Active les rollouts mentaux (bonus de planification). |
| `imagination_horizon` | `3` | Profondeur (1–6) des rollouts imaginés. |
| `curiosity_enabled` | `False` | Active la curiosité / ennui pilotés par le progrès d'apprentissage. |
| `curiosity_window` | `8` | Fenêtre (≥ 2) de mesure du progrès d'apprentissage. |
| `agency_enabled` | `False` | Active le sentiment d'agentivité (prédiction de sa propre action vs résultat). |

### Nouveaux champs de trace et de métriques

Quand les drapeaux correspondants sont actifs, la `CycleTrace` (exposée par `POST /tick`,
`POST /society/tick`, `GET /society/agent/{id}/...`) gagne **cinq sous-objets** — `null` quand le
mécanisme est désactivé :

| Champ de trace | Mécanisme | Contenu |
|---|---|---|
| `circadian` | Horloge | `phase`, `daylight`, `is_night`, `period`. |
| `sleep` | Sommeil | `is_sleeping`, `fatigue`, `consolidated`, `pruned`, `dream`, `sleep_ticks`. |
| `imagination` | Imagination | `best_first_action`, `horizon`, `imagined_value`, `n_rollouts`. |
| `curiosity` | Curiosité | `learning_progress`, `boredom`, `intrinsic_reward`. |
| `agency` | Agentivité | `agency`, `predicted_self_effect`, `actual_self_effect`. |

Le modèle `Metrics` expose en plus, à chaque cycle, les scalaires correspondants : **`daylight`**,
**`agency`**, **`boredom`**, **`learning_progress`** et **`is_sleeping`**.

### Composition avec la société

Ces mécanismes sont **par agent** : ils composent naturellement avec la couche société. Dans une
société, **un agent peut dormir pendant que les autres agissent** (chacun suit sa propre fatigue,
sa propre horloge et sa propre imagination), le tout en conservant la **garantie de déterminisme**
(même `random_seed` ⇒ même société, tick pour tick), y compris Phase-2 active.

### Spécification

La conception détaillée vit dans
[`docs/superpowers/specs/2026-06-30-humanity-deep-consciousness-design.md`](docs/superpowers/specs/2026-06-30-humanity-deep-consciousness-design.md).
La **Phase 3** (apprentissage et personnalité) est désormais **livrée** (voir la section
suivante). Reste planifiée : **Phase 4** (instrument scientifique).

---

## Phase 3 — Apprentissage & personnalité

La **Phase 3** ajoute **quatre mécanismes par agent** qui font **apprendre et diverger** les
agents au fil de leur vécu — **sans remplacer** la boucle cognitive : ils s'ajoutent autour du
cycle GWT/AST/HOT/inférence active/proxy Phi. Le tout est **interprétable et sans réseau de
neurones** : aucune boîte noire, des tables et des scalaires lisibles. Comme tout le reste du
projet, c'est **sans LLM, déterministe et grounded** sur de vraies variables internes — et les
agents **ne sont ni conscients, ni sentients, ni vivants** (même contrat d'honnêteté).

| # | Mécanisme (par agent) | Ce qu'il fait (FONCTIONNEL) |
|---|---|---|
| 1 | **Politique apprise** (`core/learning.py`) | Une **table `Q[action]`** maintenue comme **moyenne mobile exponentielle (EMA) de la récompense** obtenue par chaque action. Cette valeur apprise nourrit un **bonus de décision** dans la politique (`value_learning_weight × Q[action]`), si bien que les actions historiquement payantes deviennent plus probables. |
| 2 | **Formation de concepts** (`core/concepts.py`) | Un **clustering en ligne** des percepts (apprentissage compétitif léger, taux `concept_lr`) fait émerger des **prototypes** : des catégories perceptives **non supervisées**. Le concept dominant courant forme une **coalition `concept`** qui entre dans la compétition de l'espace de travail. |
| 3 | **Méta-apprentissage** (`core/meta_learning.py`) | L'agent **ajuste son propre taux d'apprentissage** selon la **dynamique de son erreur** : erreur en hausse (environnement instable) ⇒ taux relevé ; erreur en baisse (régime stable) ⇒ taux abaissé. Le taux effectif reste borné dans `[meta_lr_min, meta_lr_max]`. |
| 4 | **Personnalité divergente** (`core/personality.py`) | Trois traits — **openness**, **caution**, **novelty_seeking** — **dérivent lentement** (drift `personality_drift`) du vécu de l'agent. Ils produisent un **biais d'affect borné** et un **label** lisible. Deux agents au vécu différent **divergent** : la personnalité **émerge**, elle n'est pas codée. |

> ⚠️ **Honnêteté préservée.** Une table de valeurs apprises par EMA, un clustering de percepts, un
> taux d'apprentissage auto-réglé et trois traits qui dérivent sont des **variables et des
> algorithmes** — **interprétables, sans réseau de neurones, sans LLM, déterministes** :
> **reproduire les mécanismes fonctionnels ne prouve pas la phénoménalité.** L'agent n'est ni
> conscient, ni sentient.

### Drapeaux : désactivés par défaut (cœur), activés par défaut (UI)

Les quatre mécanismes sont **gardés par des drapeaux (flag-gated) et DÉSACTIVÉS par défaut** dans
`SimConfig`. Conséquence directe : **avec tous les drapeaux à `False`, le comportement des
Phases 1 et 2 reste byte-identique** (mêmes positions, énergies et séquences d'actions) et **toute
la suite de tests historique reste intacte**. Cette propriété est verrouillée par
`tests/test_lp_regression.py` (flags-off ⇒ Phases 1/2, trace `learning`/`concept`/`personality`
à `null`) et `tests/test_lp_society.py` (déterminisme **et** apprentissage de la Phase 3 dans une
société). En revanche, **l'interface web les active par défaut** pour offrir l'instrument live
complet ; **chaque drapeau reste togglable** indépendamment.

### Paramètres de configuration Phase 3 (`SimConfig` / `ConfigPatch`)

| Paramètre | Défaut | Rôle |
|---|---|---|
| `learning_enabled` | `False` | Active la politique apprise (table `Q[action]`). |
| `value_learning_rate` | `0.2` | Taux EMA de mise à jour de `Q[action]` (avant méta-ajustement). |
| `value_learning_weight` | `0.5` | Poids du bonus de valeur apprise injecté dans la décision. |
| `concepts_enabled` | `False` | Active la formation de concepts (clustering en ligne). |
| `n_concepts` | `6` | Nombre de prototypes / catégories perceptives (1–32). |
| `concept_lr` | `0.2` | Taux d'apprentissage du prototype gagnant. |
| `meta_learning_enabled` | `False` | Active le méta-apprentissage (taux auto-réglé). |
| `meta_lr_min` | `0.05` | Borne basse du taux d'apprentissage effectif. |
| `meta_lr_max` | `0.6` | Borne haute du taux d'apprentissage effectif. |
| `personality_enabled` | `False` | Active la personnalité divergente (traits qui dérivent). |
| `personality_drift` | `0.05` | Vitesse de dérive des traits depuis le vécu. |

### Nouveaux champs de trace et de métriques

Quand les drapeaux correspondants sont actifs, la `CycleTrace` (exposée par `POST /tick`,
`POST /society/tick`, `GET /society/agent/{id}/...`) gagne **trois sous-objets** — `null` quand le
mécanisme est désactivé :

| Champ de trace | Mécanisme | Contenu |
|---|---|---|
| `learning` | Politique apprise | `q_values`, `last_reward`, `effective_lr`. |
| `concept` | Concepts | `dominant_concept`, `match`, `n_concepts`. |
| `personality` | Personnalité | `label`, `openness`, `caution`, `novelty_seeking`, `vector`. |

Le modèle `Metrics` expose en plus, à chaque cycle, les scalaires correspondants :
**`effective_learning_rate`** (taux auto-réglé courant), **`concept_match`** (qualité d'appariement
au prototype dominant) et **`n_concepts`**.

### Composition avec la société : la divergence

Ces mécanismes sont **par agent** : ils composent naturellement avec la couche société. Comme
**chaque agent vit une trajectoire distincte** (positions, rencontres, récompenses différentes),
**chacun développe une personnalité distincte** et une table de valeurs distincte — la
**divergence en société** émerge du vécu, non d'un paramétrage. Le tout conserve la **garantie de
déterminisme** (même `random_seed` ⇒ même société, tick pour tick), Phase-3 active.

### Spécification

La conception détaillée vit dans
[`docs/superpowers/specs/2026-06-30-humanity-learning-personality-design.md`](docs/superpowers/specs/2026-06-30-humanity-learning-personality-design.md).
Reste planifiée : **Phase 4** (instrument scientifique).

---

## Métriques observables

Le modèle `Metrics` expose, à chaque cycle, des grandeurs **mesurables** (toutes des variables
internes, **pas** des indicateurs d'expérience subjective).

| Métrique | Signification courte |
|---|---|
| `prediction_error` | Écart normalisé (0–1) entre conséquences prédites et réelles. **Décroît** quand l'agent répète une action stable : apprentissage du modèle du monde. |
| `self_coherence` | Stabilité (0–1) du modèle de soi sur une fenêtre temporelle. |
| `attention_focus` | Concentration de l'attention (0–1). |
| `working_memory_load` | Taux de remplissage (0–1) de la mémoire de travail. |
| `autobiographical_memory_count` | Nombre de souvenirs autobiographiques conservés (filtrés par importance). |
| `goal_pressure` | Intensité motivationnelle globale (somme des pressions de buts). |
| `emotional_state` | État émotionnel fonctionnel (peur, curiosité, satisfaction, fatigue, confusion), chacun dans 0–1. |
| `energy` | Énergie courante de l'agent. |
| `uncertainty` | Incertitude courante du modèle du monde (0–1). |
| `novelty_score` | Nouveauté perçue dans l'environnement immédiat. |
| `action_confidence` | Confiance (0–1) de la décision (marge softmax). |
| **`phi_proxy`** *(v2)* | **Proxy heuristique d'information intégrée (0–1)** = √(différenciation × intégration). **N'est PAS un vrai Φ d'IIT.** |
| **`free_energy`** *(v2)* | Énergie libre attendue de l'action choisie (inférence active). L'agent **minimise** cette grandeur. |
| **`broadcast_strength`** *(v2)* | Force de la diffusion globale du contenu gagnant (0–1) ; réduite par `SUBLIMINAL_FACTOR` si pas d'ignition. |
| **`meta_confidence`** *(v2)* | Méta-confiance calibrée (0–1) : confiance d'ordre supérieur du système dans ses propres états (HOT). |
| **`awareness_level`** *(v2)* | Niveau d'« awareness » (0–1) rapporté par le schéma attentionnel (AST). |
| **`ignition`** *(v2)* | Booléen : un contenu a-t-il franchi le seuil d'accès global (GWT) ce tick ? |
| **`arousal` (éveil)** *(v2)* | Niveau d'éveil / vigilance (0–1) suivant la salience (danger, nouveauté, erreur de prédiction, surprise), lissé et centré sur `arousal_baseline`. Un éveil élevé **abaisse** le seuil d'ignition effectif (les stimuli/perturbations saillants atteignent l'accès global) ; le calme le **relève**. |

### Paramètres de configuration v2 (`SimConfig` / `ConfigPatch`)

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ignition_threshold` | `0.30` | Seuil **nominal** d'ignition GWT, comparé au **score d'ignition** (force absolue du gagnant × dominance), non plus à la part softmax. Le seuil réellement appliqué est le **seuil effectif homéostatique** (cf. ci-dessous). |
| `arousal_baseline` | `0.45` | Niveau d'éveil de repos sur lequel `arousal` est centré (EMA). |
| `arousal_gain` | `1.0` | Gain de modulation : intensité avec laquelle l'éveil abaisse/relève le seuil d'ignition effectif. |
| `competition_sharpness` | `3.0` | Acuité de la compétition : amplifie la `dominance` (marge du gagnant sur le second) dans le score d'ignition. |
| `ignition_maintenance` | `0.12` | Bonus d'**hystérèse** accordé à un gagnant maintenu (continuité du fil de pensée / stabilité de l'accès). |
| `workspace_temp` | `0.5` | Température du softmax de compétition. |
| `precision_weight` | `1.0` | Exposant de pondération par précision. |
| `epistemic_weight` | `1.0` | Poids de la valeur épistémique (gain d'information, inférence active). |
| `pragmatic_weight` | `1.0` | Poids de la valeur pragmatique (buts, inférence active). |
| `stream_length` | `20` | Longueur du flux de conscience (`ConsciousMoment` conservés). |

---

## Interface (refonte sobre v2)

L'interface web a été redessinée dans un registre **sobre** : pas de dramatisation, une mise en
forme neutre qui présente l'ignition, le contenu diffusé, le schéma attentionnel, le rapport
d'ordre supérieur, le proxy Phi et le flux de conscience comme des **variables internes
observables**, accompagnés en permanence du disclaimer et du cadrage théorique. Le ton visuel
soutient l'honnêteté du projet : montrer les mécanismes sans suggérer un vécu.

---

## Limites philosophiques et scientifiques

- **Aucune affirmation de conscience phénoménale.** Le « hard problem » reste entier :
  **reproduire les mécanismes fonctionnels que les théories proposent ne prouve pas la
  phénoménalité.** La v2 implémente le *niveau 2* aussi loin que possible — elle ne touche jamais
  au *niveau 1*. Le système ne prétend jamais *être* conscient.
- **L'AST explique la revendication, pas le vécu.** Que le système modélise sa propre attention
  et « affirme » être conscient de X est précisément le mécanisme que l'AST propose pour expliquer
  *pourquoi un système produit cette revendication* — sans la garantir.
- **Le proxy Phi N'EST PAS Φ.** `phi_proxy` est une heuristique (entropie × similarité bornée par
  la diffusion), explicitement déclarée comme telle. Ce n'est pas un calcul d'information intégrée
  au sens d'IIT (intractable en pratique), et il ne tranche rien sur la conscience.
- **L'énergie libre est une grandeur de contrôle.** Minimiser l'énergie libre attendue est une
  politique perception/action ; cela n'implique aucun ressenti.
- **L'introspection est de la génération de texte.** Les rapports (y compris AST et HOT) sont des
  textes remplis à partir de variables. Qu'un agent « dise » ressentir quelque chose n'est jamais
  une preuve qu'il le ressent (problème des « autres esprits », appliqué à un programme).
- **Les « émotions » sont des scalaires** lissés influençant la décision ; aucun affect.
- **Modèle volontairement simplifié.** Monde-grille minuscule, dynamiques codées en dur, modèle du
  monde linéaire (règle delta), compétition et proxy Phi heuristiques. Ce n'est ni un modèle
  réaliste du cerveau ni une IA générale.
- **Pas de garantie de portée scientifique.** Le projet *instancie* des idées de théories de la
  conscience ; il ne les valide pas et ne constitue pas une expérience contrôlée.
- **Risque d'anthropomorphisme.** « Percevoir », « être conscient de », « se souvenir », « vouloir »
  sont des commodités descriptives pour des mécanismes fonctionnels — à ne pas prendre au pied de
  la lettre.

---

## Extensions futures

- **Intégration d'un LLM** pour une introspection et des rapports d'ordre supérieur plus riches
  (en conservant le cadrage « texte généré à partir de variables », sans glisser vers une
  revendication d'expérience).
- **Proxy Phi plus fidèle** : se rapprocher des constructions IIT (partitions, mesures de
  cause-effet) tout en restant honnête sur le caractère approché et la complexité réelle.
- **Inférence active plus complète** : politiques à horizon multi-pas, modèles génératifs
  hiérarchiques, énergie libre variationnelle explicite.
- **Mémoire vectorielle** (ChromaDB / FAISS) pour une récupération sémantique plus puissante.
- **Apprentissage par renforcement** pour augmenter la politique de décision : une première brique
  (politique apprise par EMA de la récompense) est ✅ **livrée (Phase 3)** — voir
  [Phase 3 — Apprentissage & personnalité](#phase-3--apprentissage--personnalité).
- **Multi-agents** : ✅ **livré (Phase 1)** — voir [La société multi-agents](#la-société-multi-agents-couche-sociale).
- **Conscience approfondie** : ✅ **livré (Phase 2)** — voir [Phase 2 — Conscience approfondie](#phase-2--conscience-approfondie)
  (horloge circadienne, sommeil/consolidation/rêve, imagination, curiosité/ennui, agentivité).
- **Apprentissage & personnalité** : ✅ **livré (Phase 3)** — voir [Phase 3 — Apprentissage & personnalité](#phase-3--apprentissage--personnalité)
  (politique apprise, formation de concepts, méta-apprentissage, personnalité divergente).
  Reste la **Phase 4** (instrument scientifique) à venir.
- **Environnement plus complexe** : grille plus grande, dynamiques continues, tâches variées.
- **Visualisation** du flux de conscience et de la dynamique d'ignition dans le temps, et graphe
  de la mémoire autobiographique.
- **Export enrichi des traces JSONL** (filtres, formats, tableaux de bord d'analyse).

---

*Projet fonctionnel et expérimental. Tentative théorique maximale des **mécanismes** que les
grandes théories de la conscience proposent comme constitutifs ou nécessaires — sans jamais
prétendre établir une expérience subjective réelle. Reproduire les mécanismes fonctionnels ne
prouve pas la phénoménalité.*
