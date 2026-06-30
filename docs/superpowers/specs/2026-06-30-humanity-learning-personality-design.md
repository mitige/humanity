# Humanity — Phase 3 : Apprentissage & personnalité — conception

**Date :** 2026-06-30
**Statut :** conception — en attente de relecture avant plan d'implémentation
**Pré-requis :** Phases 1 (société) + 2 (conscience approfondie) mergées dans `master`
**Périmètre :** 4 capacités par-agent qui rendent chaque agent *adaptatif* et *singulier*

---

## 1. Intention

Jusqu'ici, le comportement d'un agent vient d'un modèle du monde appris (delta-rule)
et d'une politique de scoring **fixe** (argmax heuristique). Les agents partent
identiques. La Phase 3 ajoute l'**apprentissage de la décision** et l'**émergence
d'une personnalité** : chaque agent apprend ce qui paie vraiment, catégorise son
monde, ajuste ses propres taux d'apprentissage, et **diverge** des autres au fil
de son vécu propre — ce qui est surtout spectaculaire en société.

Quatre mécanismes **par-agent** (fonctionnent en solo `n_agents=1` comme en société) :
1. **Politique apprise** (valeurs d'action apprises, au-delà de l'argmax one-step).
2. **Formation de concepts** (clustering en ligne des percepts → catégories émergentes).
3. **Méta-apprentissage** (l'agent ajuste son propre taux d'apprentissage).
4. **Personnalité divergente** (profil stable qui émerge du vécu et modèle l'affect).

## 2. Principes directeurs (inchangés)

1. **Sans LLM, tabulaire & interprétable.** Pas de réseau de neurones : des
   tables de valeurs Q, des prototypes (vecteurs), des dérives bornées — tout est
   lisible et inspectable. Déterministe au seed. Aucune dépendance ajoutée.
2. **Additif et flag-gated, désactivé par défaut.** Chaque mécanisme a un drapeau
   `*_enabled` défaut `False` ; tous off ⇒ comportement Phases 1-2 **byte-identique**
   (les 220 tests restent verts). L'UI active les drapeaux par défaut pour l'instrument live.
3. **Réutilisation.** Hooks additifs dans le cycle ; on ne réécrit ni la politique
   ni le modèle du monde — on les *augmente* (paramètres optionnels).
4. **Honnêteté.** « Apprendre » = mettre à jour des nombres depuis la récompense
   (Δénergie + progrès de but) ; « concept » = prototype le plus proche ;
   « personnalité » = agrégat du vécu. Aucune expérience vécue n'est impliquée.

## 3. Vue d'ensemble — branchements dans le cycle

```
1 observe → 2 perçoit ──CONCEPTS (percept → prototype le plus proche → coalition 'concept')──┐
3 motivation → 4 attention → 5 WM → 6 mémoire → 7 prédictions                                 │
   ──MÉTA-APPRENTISSAGE (dynamique d'erreur → taux effectif)──┐                               │
9 politique ◄── VALEURS APPRISES (bonus Q par action) ────────┘                              │
10 agit → 11 erreur (modèle du monde mis à jour au taux effectif) → POLICY-LEARNER.update(récompense)
12 émotion → PERSONNALITÉ.modulate(émotion) (biais d'ouverture/prudence) → self-model (profil)
13 Φ → 14 bind → 15 self-model → 16 stockage → 17 introspection → 18 métriques → 19 trace
```

## 4. Conception détaillée

### 4.1 Politique apprise — `core/learning.py`
- **`PolicyLearner`** (un par agent) : table `q[action_label] -> valeur` (init 0). À chaque tick, après le résultat : `reward = energy_delta + goal_progress` ; `q[a] ← q[a] + lr_eff * (reward_norm − q[a])` (EMA incrémentale, `reward` normalisé ~[-1,1]). `bonus(action_label)` renvoie une petite valeur apprise.
- **Usage** : `Policy.choose_action` gagne un paramètre optionnel `learned_values: dict[str,float] | None = None` ; quand fourni, ajoute `value_learning_weight * learned_values.get(label, 0)` au score (additif, comme le bonus d'imagination). L'argmax one-step reste le socle.
- **State** : `LearningState{q_values, last_reward, effective_lr}` dans la trace.
- **Décision** : tabulaire par *action* (pas par état complet) pour rester interprétable et déterministe ; clé optionnellement enrichie par le type d'objet dominant en vue (extension future). `learning_enabled` défaut `False`.

### 4.2 Formation de concepts — `core/concepts.py`
- **`ConceptFormation`** (un par agent) : jusqu'à `n_concepts` prototypes (vecteurs de features de percepts, cf. `AutobiographicalMemory.feature_vector`). Init **vide** ; un nouveau percept crée un prototype tant qu'il reste de la place, sinon il est **assigné au plus proche** (cosinus/euclidien) et le prototype glisse vers lui (`proto ← proto + concept_lr*(x−proto)`). Pas d'init aléatoire → déterministe.
- **Usage** : le concept dominant reconnu ce tick devient une coalition **`concept`** (« je reconnais une situation de type k ») qui entre en compétition GWT.
- **State** : `ConceptState{dominant_concept, match, n_concepts}` dans la trace.
- **Décision** : `n_concepts` borné (défaut 6). `concepts_enabled` défaut `False`.

### 4.3 Méta-apprentissage — `core/meta_learning.py`
- **`MetaLearner`** : `effective_lr(base_lr, recent_errors)` → taux borné. Quand l'erreur est **haute et décroissante** (apprentissage productif), augmente le taux ; quand elle est **basse et stable** (déjà appris) ou **chaotique**, le réduit. Calculé depuis la fenêtre d'erreurs récentes (déterministe).
- **Usage** : le taux effectif est passé (a) à `WorldModel.update` via un paramètre optionnel `lr_override`, et (b) au `PolicyLearner`. Sans le drapeau, `lr_override=None` ⇒ `config.learning_rate` (inchangé).
- **State** : `effective_lr` (dans `LearningState`) + `Metrics.effective_learning_rate`.
- **Décision** : multiplicateur borné (p. ex. ×[0.5, 2.0]) autour de `learning_rate`. `meta_learning_enabled` défaut `False`.

### 4.4 Personnalité divergente — `core/personality.py`
- **`PersonalityModel`** (un par agent) : accumule le vécu (signe des récompenses, exposition au danger, recherche de nouveauté, affect moyen) en un **vecteur de personnalité** + des traits nommés (p. ex. *openness* ↑ avec la nouveauté recherchée, *caution* ↑ avec l'évitement du danger), via EMA bornée. Produit un `label` (« explorateur prudent », « audacieux curieux »…) dérivé du trait dominant.
- **Usage** : `modulate(emotion)` applique un **biais d'affect de base** borné (un profil « curieux » garde la curiosité un peu plus haute, un profil « prudent » la peur), appliqué après l'émotion — ce biais se propage naturellement à l'attention (saillance de nouveauté) et à la politique, faisant **diverger** les agents. Le profil + label enrichissent le narratif du self-model.
- **State** : `PersonalityState{label, openness, caution, novelty_seeking, vector}` dans la trace.
- **Décision** : dérive **bornée** autour du tempérament de base (les agents restent reconnaissables). En société, la divergence vient du vécu distinct de chacun. `personality_enabled` défaut `False`.

### 4.5 Schémas, constantes, config (additifs, défauts sûrs)
- Nouveaux modèles : `LearningState`, `ConceptState`, `PersonalityState`.
- `CycleTrace` += `learning, concept, personality` (`| None = None`).
- `Metrics` += `effective_learning_rate: float = <learning_rate>`, `concept_match: float = 0.0`, `n_concepts: int = 0`.
- `WORKSPACE_SOURCES` += `"concept"`.
- `SimConfig` += `learning_enabled, value_learning_rate, value_learning_weight, concepts_enabled, n_concepts, concept_lr, meta_learning_enabled, meta_lr_min, meta_lr_max, personality_enabled, personality_drift` (+ `ConfigPatch`), défauts conservateurs, drapeaux `False`.
- `WorldModel.update` gagne `lr_override: float | None = None` (défaut → `config.learning_rate`).
- `Policy.choose_action` gagne `learned_values: dict[str,float] | None = None`.

### 4.6 API + UI
- Les nouveaux sous-états passent par `CycleTrace` (`/tick`, `/society/tick`, `/society/agent/{id}/...`).
- UI : panneau **Apprentissage & personnalité** — barres des valeurs Q apprises, concept dominant reconnu, taux d'apprentissage effectif, **carte/label de personnalité par agent** (la divergence en société est la démo phare). Toggles par-drapeau, activés par défaut côté UI.

## 5. Déterminisme & rétrocompatibilité
- Tout est déterministe : Q-EMA, prototypes init-depuis-percepts (pas d'aléatoire), méta-taux fonction de l'historique d'erreurs, dérive de personnalité bornée et déterministe.
- Chaque `*_enabled=False` rend son mécanisme inerte ⇒ comportement Phases 1-2 identique (test de régression « tous drapeaux off »).

## 6. Gestion des erreurs
- `WorldModel.update(lr_override=None)` ⇒ taux config (rétrocompat). `lr_override` borné [0,1].
- Aucun concept encore formé ⇒ pas de coalition `concept`, état neutre.
- Fenêtres d'historique vides ⇒ méta-taux = base, personnalité neutre.
- Dérive de personnalité bornée ⇒ pas d'emballement.

## 7. Stratégie de tests
**Unitaires :** `PolicyLearner` (Q monte sur récompense positive répétée ; bonus borné) ; `ConceptFormation` (crée jusqu'à n prototypes puis assigne au plus proche ; déterministe ; concept dominant) ; `MetaLearner` (taux ↑ sur erreur haute+décroissante, ↓ sur stable ; bornes) ; `PersonalityModel` (openness ↑ avec nouveauté, caution ↑ avec danger ; modulate borné ; label cohérent) ; `WorldModel.update(lr_override)` ; `Policy.choose_action(learned_values=...)`.
**Intégration :** un agent qui répète une action gratifiante voit sa valeur Q et sa préférence monter ; **deux agents au vécu différent en société développent des personnalités distinctes** (labels/vecteurs divergents) ; **régression** : tous drapeaux off ⇒ trajectoire Phases 1-2 identique ; déterminisme société+Phase3 reproductible au seed.
**TDD** pour chaque module.

## 8. Hors périmètre (Phase 3)
- Pas de réseaux de neurones / RL profond (tabulaire interprétable seulement).
- Pas d'apprentissage par état complet (Q par action, pas par observation complète).
- Pas de transmission culturelle/d'apprentissage social entre agents (extension future possible).
- Batterie de tests de conscience → Phase 4.

## 9. Découpage du plan (indicatif, ~11 tâches TDD)
1. Schémas + constantes + config. 2. `PolicyLearner`. 3. `ConceptFormation`. 4. `MetaLearner`. 5. `PersonalityModel`. 6. `WorldModel.update(lr_override)` + `Policy.choose_action(learned_values)`. 7. Intégration cycle (gated). 8. Métriques/trace. 9. API + UI. 10. Régression « tous drapeaux off ». 11. Société + personnalités divergentes + README.
