# Humanity — Phase 2 : Conscience approfondie — conception

**Date :** 2026-06-30
**Statut :** conception — en attente de relecture avant plan d'implémentation
**Pré-requis :** Phase 1 (société multi-agents) mergée dans `master`
**Périmètre :** 5 capacités cognitives par-agent qui approfondissent chaque `CognitiveAgent`

---

## 1. Intention

La Phase 1 a élargi Humanity *horizontalement* (plusieurs agents). La Phase 2 l'approfondit *verticalement* : chaque agent gagne cinq mécanismes que les théories de la cognition associent à une conscience plus riche — **sommeil/rêve + consolidation mémoire**, **imagination (rollouts mentaux)**, **curiosité/ennui (progrès d'apprentissage)**, **sentiment d'agentivité (sense of agency)**, et une **horloge circadienne**.

Toutes ces capacités sont **par-agent** : elles fonctionnent identiquement en mode solo (`n_agents=1`) et en société (un agent fatigué dort pendant que les autres agissent ; un agent qui rêve diffuse un contenu recombiné ; l'agentivité est propre à chaque agent).

## 2. Principes directeurs (inchangés)

1. **Sans LLM, déterministe, *grounded*.** Les rêves, plans imaginés et rapports d'agentivité sont dérivés mécaniquement des variables internes (mémoire épisodique, modèle du monde, erreurs de prédiction). Aucun texte libre.
2. **Additif et rétrocompatible.** Tous les mécanismes sont gardés par des drapeaux de config (par défaut activés mais désactivables) ; quand désactivés, le cycle est byte-identique à la Phase 1. Les 194 tests existants doivent rester verts.
3. **Réutilisation du cycle.** On ajoute des modules + des hooks dans `cognitive_cycle`, on ne le réécrit pas. Le sommeil est une *modulation* du cycle linéaire, pas une branche parallèle.
4. **Honnêteté.** Aucun de ces mécanismes n'établit une expérience vécue ; le disclaimer et le framing s'appliquent. « Rêver » = recombiner des enregistrements épisodiques et les diffuser ; « imaginer » = dérouler le modèle du monde ; « agentivité » = comparer prédiction et résultat de sa propre action.

## 3. Vue d'ensemble — où chaque mécanisme se branche dans le cycle

```
        ┌─────────────── CIRCADIEN (phase du tick → module l'arousal de base) ───────────────┐
        ▼                                                                                      │
1 observe → 2 perçoit → 3 motivation → 4 attention → 5 WM → 6 mémoire → 7 prédictions          │
                                                                   │                           │
                                          ┌── IMAGINATION (rollouts N-pas) ──┐                 │
                                          ▼                                  ▼                 │
6b coalitions (+ imagination, + dream si sommeil) → arousal(◄circadien) → 7 espace de travail  │
   → AST → HOT → 9 politique ──(SOMMEIL: force REST + consolidation + rêve)── → 10 agit         │
   → 11 erreur ── CURIOSITÉ (progrès d'apprentissage → ennui, novelty drive) ─┐                │
   → 12 émotion → AGENTIVITÉ (prédiction propre vs résultat) → self-model ◄───┘                │
   → 13 Φ → 14 bind → 15 self-model → 16 stockage → 17 introspection → 18 métriques → 19 trace ─┘
```

## 4. Conception détaillée

### 4.1 Horloge circadienne — `core/circadian.py`
- **`Circadian.phase(tick)`** : phase déterministe dans `[0,1)` = `(tick % period) / period`. `daylight = 0.5*(1+cos(2π·phase))` (1 à midi, 0 à minuit). `is_night = daylight < night_threshold`.
- **Effet** : module l'arousal de base — `effective_arousal_baseline = arousal_baseline * (0.5 + 0.5*daylight)`. La nuit, l'arousal de base baisse → seuil d'ignition plus haut → accès conscient plus difficile (somnolence), et la pression de sommeil monte.
- **State** : `CircadianState{phase, daylight, is_night, period}` dans la trace.
- **Décision** : `circadian_period` configurable (défaut 50 ticks). Activable via `circadian_enabled` (défaut `True`). Désactivé → `daylight=1.0` constant → arousal inchangé (rétrocompat).

### 4.2 Sommeil / rêve + consolidation — `core/sleep.py`
- **`SleepCycle`** (un par agent) : maintient `is_sleeping`. **Endormissement** quand `fatigue ≥ sleep_fatigue_threshold` ET (`is_night` OU fatigue très élevée). **Réveil** quand `fatigue ≤ wake_fatigue_threshold` ET `not is_night` (ou après `max_sleep_ticks`).
- **Pendant le sommeil**, le cycle est *modulé* (pas forké) :
  1. Les coalitions externes (perception, communication, social) sont **atténuées** (yeux fermés) ; on injecte une coalition **`dream`**.
  2. La **décision est forcée à `REST`** (récupération d'énergie → la fatigue baisse → réveil éventuel). Aucune action mutant le monde.
  3. **Consolidation hors-ligne** : rejeu des `k` souvenirs les plus importants → leur importance est renforcée (×`replay_boost`, borné), et les souvenirs sous un seuil sont élagués (oubli). Opère sur `AutobiographicalMemory`.
  4. **Rêve** : recombinaison *grounded* de 2 souvenirs récents/importants en une chaîne (`"dream: <résumé A> + <résumé B>"`) diffusée comme coalition `dream` (l'agent peut « être conscient » de rêver via l'ignition).
- **State** : `SleepState{is_sleeping, fatigue, consolidated, pruned, dream}` dans la trace.
- **Décision** : seuils configurables (`sleep_fatigue_threshold=0.8`, `wake_fatigue_threshold=0.35`), `dream_enabled` (défaut `True`), `sleep_enabled` (défaut `True`). Désactivé → jamais de sommeil (rétrocompat). Note : `REST` régénère l'énergie ⇒ la fatigue (= 1 − énergie/initiale) baisse, donc le réveil est garanti.

### 4.3 Imagination (rollouts mentaux) — `core/imagination.py`
- **`Imagination.rollout(world_model, observation, salient, depth)`** : déroule mentalement, sur `imagination_horizon` pas (défaut 3), les séquences d'actions candidates en chaînant `WorldModel.predict` (sans toucher le monde), et score chaque plan par la **somme d'EFE négative** (valeur cumulée actualisée). Renvoie le meilleur plan + sa valeur imaginée.
- **Usage** : enrichit la politique — le premier pas du meilleur plan imaginé reçoit un bonus dans le scoring de `Policy.choose_action` (planification profonde), **sans remplacer** l'argmax one-step (qui reste le fallback). Produit aussi une coalition **`imagination`** (l'agent « se projette »).
- **State** : `ImaginationState{best_first_action, horizon, imagined_value, n_rollouts}` dans la trace.
- **Décision** : borné (horizon ≤ 4) pour tractabilité + déterminisme. `imagination_enabled` (défaut `True`). Désactivé → politique one-step inchangée (rétrocompat). Pendant le sommeil, l'imagination est suspendue.

### 4.4 Curiosité / ennui (progrès d'apprentissage) — `core/curiosity.py`
- **`Curiosity.update(recent_errors)`** : calcule le **progrès d'apprentissage** = baisse de l'erreur de prédiction sur une fenêtre glissante (`curiosity_window`, défaut 8). `intrinsic_reward = max(0, learning_progress)` (apprendre est gratifiant). `boredom` monte quand l'erreur **et** le progrès stagnent bas longtemps (environnement « résolu ») ; il est atténué quand l'erreur est trop haute (débordement).
- **Effet** : l'ennui **amplifie** la recherche de nouveauté (boost dynamique de `explore_novelty`/`curiosity`), poussant l'agent à chercher de l'inédit quand le monde devient prévisible ; l'`intrinsic_reward` nourrit la `satisfaction`.
- **State** : `CuriosityState{learning_progress, boredom, intrinsic_reward}` dans la trace.
- **Décision** : `curiosity_enabled` (défaut `True`). Désactivé → drives inchangés (rétrocompat).

### 4.5 Sentiment d'agentivité (sense of agency) — `core/agency.py`
- **`Agency.compute(chosen_prediction, result)`** : compare la prédiction de **l'action choisie par l'agent** à son résultat réel, **sur les dimensions auto-causées** (`energy_delta`, `goal_progress`). `agency = 1 − erreur_normalisée` : élevé quand « j'avais prédit l'effet de mon acte » (forte attribution de causalité à soi), bas en cas de surprise (l'effet ne vient pas de moi).
- **Distinction** : c'est spécifiquement l'erreur sur l'action **exécutée** (auto-causation), pas l'erreur de prédiction globale.
- **Effet** : nourrit le self-model (une agentivité élevée renforce la confiance/cohérence) et devient une **métrique** + un facteur du moment conscient.
- **State** : `AgencyState{agency, predicted_self_effect, actual_self_effect}` dans la trace + `Metrics.agency`.
- **Décision** : `agency_enabled` (défaut `True`). Désactivé → self-model/métriques inchangés (rétrocompat).

### 4.6 Schémas, constantes, config (additifs, défauts sûrs)
- Nouveaux modèles : `CircadianState`, `SleepState`, `ImaginationState`, `CuriosityState`, `AgencyState`.
- `CycleTrace` gagne `circadian, sleep, imagination, curiosity, agency` (tous `| None = None`).
- `Metrics` gagne `agency, boredom, learning_progress, daylight, is_sleeping` (défauts).
- `ConsciousMoment` : le résumé inclut l'état veille/sommeil + agentivité.
- `WORKSPACE_SOURCES` += `imagination`, `dream`.
- `SimConfig` += `circadian_enabled, circadian_period, night_threshold, sleep_enabled, dream_enabled, sleep_fatigue_threshold, wake_fatigue_threshold, max_sleep_ticks, imagination_enabled, imagination_horizon, curiosity_enabled, curiosity_window, agency_enabled` (+ `ConfigPatch`), tous avec défauts conservateurs.

### 4.7 Intégration dans `cognitive_cycle` (hooks additifs, gardés par drapeaux)
1. **Début** : `circadian` calcule la phase → arousal de base effectif passé à `_update_arousal`.
2. **Sommeil** : `sleep_cycle.evaluate(fatigue, circadian)` ; si endormi → atténuer coalitions externes, injecter `dream`, forcer `decision=REST`, lancer `consolidate()`.
3. **Imagination** (si éveillé) : entre prédictions et politique → meilleur plan → bonus de scoring + coalition `imagination`.
4. **Curiosité** : après l'erreur → `update(recent_errors)` → module les drives pour le tick suivant + `intrinsic_reward` → satisfaction.
5. **Agentivité** : après le step → `agency.compute(chosen_prediction, result)` → self-model + métrique.
Chaque hook est un no-op quand son drapeau est `False` → cycle Phase 1 identique.

### 4.8 API + UI
- `CycleTrace` étendu expose tout (déjà via `/tick`, `/society/tick`, `/society/agent/{id}/...`).
- Nouveaux champs dans `/state` / `/society` (daylight, is_sleeping, agency, boredom).
- UI : un **cadran circadien** (jour/nuit), un **indicateur de sommeil + bulle de rêve**, une **jauge d'agentivité**, une **jauge d'ennui/curiosité**, et l'**affichage du plan imaginé**. Additif aux panneaux existants.

## 5. Déterminisme & rétrocompatibilité
- Tous les mécanismes sont déterministes (phase circadienne = fonction du tick ; rollouts = modèle du monde déterministe ; consolidation = tri stable par importance).
- Chaque drapeau `*_enabled=False` rend son mécanisme inerte → le cycle Phase 1 (et les 194 tests) restent identiques. Un test de régression vérifiera qu'avec tous les drapeaux à `False`, la trace est équivalente à la Phase 1.

## 6. Gestion des erreurs
- Réveil garanti : `REST` régénère l'énergie, la fatigue baisse sous `wake_fatigue_threshold` ; garde-fou `max_sleep_ticks`.
- Mémoire vide → consolidation/rêve no-op.
- Horizon d'imagination borné ; aucune mutation du monde pendant le rollout (copies/predict pur).
- Fenêtres glissantes vides → curiosité/agentivité neutres.

## 7. Stratégie de tests
**Unitaires :** phase circadienne (bornes, jour/nuit, désactivé→1.0) ; endormissement/réveil sur seuils ; consolidation (renforce le top-k, élague le bas) ; rêve grounded (recombine de vrais résumés) ; rollout (profondeur respectée, choisit le meilleur plan, pur) ; progrès d'apprentissage/ennui (monte quand l'erreur stagne) ; agentivité (1 quand prédiction=résultat, bas sinon).
**Intégration :** un agent fatigué la nuit s'endort, consolide, puis se réveille ; agentivité varie avec la précision ; **régression** : tous drapeaux `False` ⇒ comportement Phase 1 ; déterminisme société+Phase2 reproductible au seed ; tout fonctionne en société (un agent dort, les autres agissent).
**TDD** pour chaque module (RED → GREEN → refactor).

## 8. Hors périmètre (Phase 2)
- Pas d'apprentissage de politique profond (Phase 3) ; l'imagination utilise le modèle du monde existant.
- Pas de vrai sommeil paradoxal/lent différencié ; un seul état de sommeil + rêve.
- Pas de génération de langage des rêves (recombinaison de résumés uniquement).

## 9. Découpage du plan (indicatif, ~13 tâches TDD)
1. Schémas + constantes + config. 2. Circadian. 3. Sleep+consolidation. 4. Dream. 5. Imagination. 6. Curiosity. 7. Agency. 8. Intégration cycle (drapeaux). 9. Métriques/trace. 10. API. 11. UI. 12. Régression « tous drapeaux off = Phase 1 ». 13. Intégration société+Phase2.
