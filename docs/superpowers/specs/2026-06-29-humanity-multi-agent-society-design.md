# Humanity — Société d'esprits : conception

**Date :** 2026-06-29
**Statut :** approuvé (conception) — en attente de relecture du spec avant plan d'implémentation
**Périmètre :** Phase 1 détaillée (société multi-agents) + feuille de route Phases 2–4

---

## 1. Contexte & intention

`Humanity` est un *instrument* : une implémentation de bonne foi des mécanismes que
les grandes théories scientifiques de la conscience proposent comme nécessaires
(GWT, AST, HOT, inférence active / énergie libre, IIT via un proxy Φ honnête).
Aujourd'hui le système fait tourner **un seul** `CognitiveAgent` dans un monde-grille,
exposé par une API FastAPI et une UI « instrument ».

Cette expansion transforme l'instrument mono-agent en une **société d'esprits** :
plusieurs agents dans un monde partagé, qui se perçoivent, communiquent, se
modélisent mutuellement, et s'influencent affectivement — puis enrichit chaque
agent (conscience approfondie), son apprentissage (personnalité émergente) et
l'outillage scientifique autour.

L'utilisateur a validé les quatre axes par ordre de priorité :
1. **Société multi-agents** (Phase 1, détaillée ici)
2. **Conscience approfondie** (Phase 2)
3. **Apprentissage & personnalité** (Phase 3)
4. **Instrument scientifique** (Phase 4)

---

## 2. Principes directeurs (non négociables)

1. **Sans LLM, déterministe, *grounded*.** Toute sortie reste traçable à des
   variables internes. La communication inter-agents n'est pas du texte généré
   librement : c'est un message dérivé mécaniquement de l'état interne de
   l'émetteur (moment conscient, décision, affect). Aucune dépendance externe,
   aucune clé API. Reproductible au seed près.
2. **Additif et rétrocompatible.** L'agent unique devient *une société de 1*.
   Les endpoints `/agent/*` et l'UI actuelle restent fonctionnels (ils ciblent
   l'agent 0). Les tests existants doivent continuer à passer.
3. **Réutilisation du cycle cognitif.** Le `CognitiveAgent.cognitive_cycle()`
   n'est pas réécrit. On lui fournit de nouvelles *entrées* (perception d'autrui,
   messages reçus) et de nouvelles *coalitions* (`communication`, `social`) qui
   se branchent sur la machinerie GWT déjà présente.
4. **Honnêteté maintenue.** Le disclaimer et le `THEORY_FRAMING` s'appliquent à la
   société comme à l'agent : une société d'agents non conscients reste non
   consciente. Aucun nouveau texte ne doit suggérer une expérience vécue.

---

## 3. Vue d'ensemble de l'architecture

```
MONDE          ┌──────────────────────────────────────────────────────┐
               │  SharedWorld : objets · N agents · messages · events  │   (étendu)
               └───────────────┬───────────────┬───────────────┬───────┘
                               ▼               ▼               ▼
AGENTS         ┌───────────┐   ┌───────────┐   ┌───────────┐
               │  Agent A  │   │  Agent B  │   │  Agent C  │              (réutilisé)
               │  cycle    │   │  cycle    │   │  cycle    │
               └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
                     ▼               ▼               ▼
COUCHE SOCIALE ┌───────────┐   ┌───────────────┐   ┌───────────┐
               │Communica- │   │ Théorie de    │   │  Affect   │          (nouveau)
               │tion       │   │ l'esprit (ToM)│   │  social   │
               └─────┬─────┘   └───────┬───────┘   └─────┬─────┘
                     └───────────────┬─┴─────────────────┘
                                     ▼
ORCHESTRATION              ┌──────────────────────┐
                           │   SocietyManager      │                      (nouveau)
                           │  ordonnance · scénarios│
                           └──────────┬────────────┘
                                      ▼
SURFACE              ┌────────────────┐   ┌────────────────┐
                     │ API multi-agent │   │   UI société   │            (nouveau/étendu)
                     │ REST + WebSocket│   │ N agents·graphe│
                     └────────────────┘   └────────────────┘
```

Chaque unité a une responsabilité unique, une interface explicite, et est
testable isolément.

---

## 4. Phase 1 — conception détaillée

### 4.1 Schémas (`schemas/models.py`, additif)

Nouveaux modèles Pydantic :

- **`AgentView`** — un autre agent tel que perçu : `id: int`, `x: int`, `y: int`,
  `distance: float`, `last_action: ActionType | None`, `dominant_affect: str`,
  `valence: float`.
- **`Message`** — `id: int`, `tick_emitted: int`, `sender_id: int`,
  `content: str` (résumé *grounded*), `vector: list[float]` (résumé affect/feature
  pour la coalition), `x: int`, `y: int` (lieu d'émission), `radius: int`
  (rayon d'audition), `ttl: int`.
- **`OtherMind`** — modèle qu'un agent a d'un congénère : `agent_id: int`,
  `inferred_action: ActionType | None`, `inferred_affect: str`,
  `inferred_valence: float` (−1..1), `trust: float` (0..1),
  `familiarity: float` (0..1), `last_seen_tick: int`, `note: str`.
- **`SocialState`** — état social d'un agent pour la trace/UI : `agent_id: int`,
  `others: list[OtherMind]`, `affiliation_pressure: float`,
  `last_emitted: str | None`, `received_count: int`.

Extensions :

- `Observation` gagne `visible_agents: list[AgentView] = []` et
  `audible_messages: list[Message] = []`.
- `Coalition.source` accepte deux nouvelles valeurs : `"communication"` et
  `"social"` ; `WORKSPACE_SOURCES` (dans `constants.py`) est étendu en
  conséquence.
- `CycleTrace` gagne `social: SocialState | None = None` (optionnel → les traces
  mono-agent restent valides).
- `SimConfig` gagne : `n_agents: int = 1`, `comm_radius: int = 4`,
  `message_ttl: int = 2`, `contagion_rate: float = 0.15`,
  `affiliation_drive: float = 1.0`, `social_seed_stride: int = 1000`.

Tous les nouveaux champs ont des valeurs par défaut → **aucune trace/réponse
existante ne casse**.

### 4.2 `SharedWorld` (`core/shared_world.py`)

Étend la dynamique de [`core/world.py`](../../../core/world.py) pour héberger
plusieurs agents.

- **État** : `objects` (partagés), `agents: dict[int, AgentBody]` où `AgentBody`
  = position + énergie + dernière action + affect dominant publié, `messages`
  (dépôt spatialisé), `tick`.
- **`observe(agent_id)`** : renvoie une `Observation` pour cet agent contenant
  (a) les objets dans le rayon, (b) `visible_agents` = autres `AgentBody` dans le
  rayon (exposant leur dernière action et leur affect dominant publiés), (c)
  `audible_messages` = messages dont l'agent est à portée (`distance ≤ radius`)
  **émis au tick précédent**.
- **`step(agent_id, decision)`** : applique l'action de cet agent uniquement,
  met à jour sa position/énergie, et — si l'action est `INTERACT` sur un objet —
  résout les effets comme aujourd'hui. Deux agents ne peuvent pas occuper la même
  cellule (résolution déterministe par id).
- **`publish(agent_id, last_action, dominant_affect, valence)`** : met à jour le
  signal social lisible par les autres.
- **`post_message(message)`** : dépose un `Message` (livré au tick suivant).
- **Déterminisme** : RNG par agent = `default_rng(seed_base + index * social_seed_stride)`.

`World` (mono-agent) reste en place et inchangé ; `SharedWorld` ne le modifie pas.

### 4.3 Communication (`core/communication.py`)

- **`MessageBus`** : file de messages avec livraison **décalée d'un tick** (les
  messages émis au tick T sont perçus au tick T+1), expiration par `ttl`,
  filtrage spatial par rayon.
- **Émission** : quand la décision d'un agent est `VERBALIZE` (aujourd'hui neutre),
  l'agent émet un `Message` dont `content` est un résumé *grounded* de son
  `ConsciousMoment` (p. ex. `"A: aware_of=<…>, affect=<dom>, action=<…>"`) et
  `vector` un petit résumé affect/feature. Honnête : rien n'est inventé.
- **Réception** : à T+1, `audible_messages` est encodé par la perception en une
  entrée qui produit une **coalition `communication`** (activation = pertinence
  du message, précision = confiance/`trust` envers l'émetteur). Elle entre en
  compétition GWT comme les autres → peut s'enflammer ou rester subliminale.

### 4.4 Théorie de l'esprit (`core/theory_of_mind.py`)

- **`TheoryOfMind`** (un par agent) : maintient un `OtherMind` par congénère vu.
- **Mise à jour** : depuis les `visible_agents` (action + affect observés) et les
  messages reçus, infère l'`inferred_action`, l'`inferred_affect`/`valence`, et
  augmente `familiarity` (EMA). Produit une **coalition `social`** (activation =
  saillance sociale = proximité × intensité affective d'autrui ; précision =
  `familiarity`).
- **Usage par la politique** : les autres agents deviennent des cibles valides
  pour `APPROACH` / `AVOID` / `OBSERVE`. Un agent à valence négative/danger élevé
  pousse `AVOID` ; un agent à valence positive/utile pousse `APPROACH`.

### 4.5 Affect social (`core/social_emotion.py`)

- **Contagion émotionnelle** : après la mise à jour émotionnelle normale, l'affect
  de l'agent est *nudgé* vers la moyenne (pondérée par `trust` et proximité) de
  l'affect des `visible_agents`, via EMA de poids `contagion_rate`. Borné, doux,
  désactivé si personne en vue (no-op).
- **Réputation / confiance** : `trust[other]` évolue selon le signe de la
  récompense propre de l'agent lorsqu'il est à proximité de `other` ou a reçu un
  message de lui qui a réduit son erreur de prédiction. Borné [0,1], EMA.
- **Besoin d'affiliation** : `MotivationSystem` gagne une 7ᵉ pression `affiliate`
  (échelle `affiliation_drive`), forte quand l'agent est isolé / a une faible
  satisfaction sociale ; route vers `APPROACH` d'autres agents dans
  `attention._goal_relevance` et `policy._ACTION_NEED_WEIGHTS`.

### 4.6 Intégration dans le cycle cognitif

Points d'accroche **additifs** dans `CognitiveAgent` (no-ops en société de 1) :

1. Après perception : encoder `visible_agents` + `audible_messages`.
2. Avant la construction des coalitions : `TheoryOfMind.update(...)`.
3. Dans `_build_coalitions` : ajouter coalitions `communication` et `social`.
4. Après l'émotion : `SocialEmotion.apply_contagion(...)`.
5. Après la décision : si `VERBALIZE`, `MessageBus.emit(...)`.
6. Remplir `trace.social = SocialState(...)`.

Aucune de ces étapes ne s'active sans congénères → comportement mono-agent et
tests existants **identiques**.

### 4.7 `SocietyManager` (`core/society.py`)

- **Possède** un `SharedWorld`, N `CognitiveAgent` (chacun branché sur le monde
  partagé via son `agent_id`), le `MessageBus`, et une boucle asyncio.
- **`tick()`** : pour chaque agent, dans l'ordre déterministe (par id) :
  livrer ses messages T−1, exécuter son `cognitive_cycle()`, collecter la trace,
  publier son signal social. Puis avancer le tick de société et purger les
  messages expirés.
- **Boucle de fond** : comme `SimulationManager` aujourd'hui (tps, max_ticks,
  lock asyncio), mais ticke la société entière.
- **Scénarios** : `load_scenario(spec)` place agents/objets selon une config
  reproductible ; `save_state()/load_state()` (JSON) sérialise toute la société.
- **Rétrocompat** : `SimulationManager` est conservé comme **façade « société de
  1 »** ; `get_manager()` retourne un `SocietyManager` à 1 agent et expose les
  accesseurs de l'agent 0.

### 4.8 API (`app/api/routes.py`, additif)

Nouveaux endpoints :

- `GET /society` — état global : résumé par agent, tick, matrice de relations.
- `POST /society/tick` — un tick collectif → traces (ou résumés) par agent.
- `POST /society/run` · `POST /society/pause` — boucle de fond.
- `POST /society/config` — N agents + config monde.
- `GET /society/agent/{id}/consciousness|self-model|introspection|workspace|stream`
  — réutilisent les accesseurs existants pour l'agent ciblé.
- `GET /society/messages` — messages récents.
- `GET /society/relations` — graphe ToM/confiance (nœuds = agents, arêtes = trust).
- `WebSocket /ws/society` — pousse l'état de la société à chaque tick.

**Conservés à l'identique** : tous les `/agent/*`, `/state`, `/tick`, `/metrics`,
`/config`, `/trace` → ciblent l'agent 0 via la façade.

### 4.9 UI (`ui/`)

Nouvelle vue « société » (additive, l'instrument mono-agent reste accessible) :

- Canvas du monde partagé avec N agents colorés + bulles de communication.
- **Graphe de relations** (force-directed léger, sans dépendance) : arêtes
  pondérées par `trust`.
- Mini-panneaux par agent ; sélectionner un agent ré-affiche les panneaux de
  conscience existants (réutilisés) pour cet agent.
- Flux temps réel via WebSocket (fallback polling si indisponible).

### 4.10 Déterminisme & rétrocompatibilité

- Seed par agent dérivé du seed de base → société entièrement reproductible.
- Ordre de tick et de livraison de messages fixés par id.
- Façade « société de 1 » → `n_agents=1` reproduit exactement le comportement
  actuel ; la suite de tests existante sert de test de non-régression.

---

## 5. Flux de données — un tick de société

1. `SocietyManager.tick()` ouvre un snapshot du `SharedWorld`.
2. Pour chaque agent (ordre par id) :
   a. Livraison des messages audibles émis au tick T−1.
   b. `observe(agent_id)` → objets + `visible_agents` + `audible_messages`.
   c. Perception encode le tout ; `TheoryOfMind` se met à jour.
   d. Coalitions (dont `communication`, `social`) → compétition GWT → ignition.
   e. Émotion mise à jour, puis contagion sociale appliquée.
   f. Politique choisit l'action ; `SharedWorld.step` l'applique.
   g. Si `VERBALIZE` → message émis (livré à T+1).
   h. Trace (avec `social`) collectée ; signal social publié.
3. Tick de société incrémenté ; messages expirés purgés.

---

## 6. Gestion des erreurs

- `agent_id` inconnu → HTTP 404.
- Société vide / aucun congénère en vue → couches sociales en no-op, états neutres.
- Message sans destinataire à portée → bufferisé puis abandonné après `ttl`.
- Énergie nulle → géré par le clamp existant du monde (pas de « mort » en Phase 1 ;
  introduite en option Phase 4).
- WebSocket indisponible → l'UI bascule en polling REST.
- Collision de cellules → résolution déterministe (l'agent au plus petit id garde
  la cellule ; l'autre reste sur place).

---

## 7. Stratégie de tests

**Unitaires :**
- `SharedWorld.observe` expose bien les autres agents et messages dans le rayon, pas au-delà.
- `MessageBus` : livraison décalée d'un tick, expiration par `ttl`, filtrage spatial.
- `TheoryOfMind.update` : inférence et `familiarity` croissante.
- `SocialEmotion` : contagion borne et déplace l'affect vers autrui ; no-op si isolé.
- Réputation : `trust` monte/descend selon le signe de la récompense.
- `SocietyManager` : ordre déterministe, purge des messages.

**Intégration :**
- Société à 3 agents sur N ticks : reproductible au seed (trace identique).
- Un `VERBALIZE` de A est perçu par B voisin à T+1 (coalition `communication`).
- La contagion rapproche l'affect de B de celui de A.
- **Non-régression** : `n_agents=1` ⇒ tous les tests `/agent/*` et de cycle
  existants passent inchangés.

**Propriété :** même seed + même config ⇒ traces de société bit-à-bit identiques.

Approche TDD : test d'abord pour chaque nouveau module (RED → GREEN → refactor).

---

## 8. Feuille de route — Phases 2 à 4 (conçues, livrées ensuite)

**Phase 2 — Conscience approfondie**
- Sommeil/rêve + **consolidation mémoire** (rejeu hors-ligne, renforcement des
  épisodes importants, élagage).
- **Imagination** : rollouts mentaux du modèle du monde pour planifier sur
  plusieurs pas (inférence active étendue).
- Curiosité/ennui (modulation de la nouveauté recherchée selon l'historique).
- *Sense of agency* : comparaison prédiction↔résultat de **sa propre** action.
- Horloge circadienne modulant l'arousal de base.

**Phase 3 — Apprentissage & personnalité**
- Politique **apprise** (au-delà de l'argmax actuel) — bandit/valeur incrémentale.
- Formation de concepts (clustering en ligne des percepts).
- Méta-apprentissage des taux (learning_rate, EMA) par agent.
- **Personnalités divergentes** émergeant du vécu propre de chaque agent.

**Phase 4 — Instrument scientifique**
- Tableau de bord multi-agents (métriques comparatives, séries temporelles).
- **Scénarios reproductibles** scriptés + export de données (CSV/JSON).
- **Batterie de tests de conscience** : auto-reconnaissance (test du miroir),
  injection de faux souvenirs, calibration métacognitive, reportabilité.

Chaque phase fera l'objet de son propre plan d'implémentation et de son propre
cycle de validation.

---

## 9. Hors périmètre (YAGNI)

- Pas de LLM ni de génération de langage naturel libre.
- Pas de monde 3D, pas de multijoueur réseau, pas de GPU.
- Pas de base de données (on conserve la persistance JSON existante).
- Pas de vrai calcul IIT (le proxy Φ reste explicitement heuristique).
- Pas de « mort »/reproduction d'agents en Phase 1 (option Phase 4).
```
