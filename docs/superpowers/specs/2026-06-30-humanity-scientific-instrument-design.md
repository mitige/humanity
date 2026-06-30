# Humanity — Phase 4 : Instrument scientifique — conception

**Date :** 2026-06-30
**Statut :** conception — en attente de relecture avant plan d'implémentation
**Pré-requis :** Phases 1 (société) + 2 (conscience approfondie) + 3 (apprentissage/personnalité) mergées dans `master`
**Périmètre :** outillage scientifique non-invasif au-dessus de l'agent/société existants

---

## 1. Intention

Les Phases 1-3 ont construit le *sujet d'étude*. La Phase 4 construit l'*instrument
d'étude* : de quoi faire de la **science reproductible** sur cette implémentation —
des **scénarios scriptés déterministes**, l'**export des données**, un **tableau de
bord** de séries temporelles comparatives, et une **batterie de tests** standardisés
qui sondent les mécanismes (auto-reconnaissance, faux souvenirs, calibration
métacognitive).

C'est une couche **non-invasive** : elle *orchestre* et *observe* l'agent/société
existants sans modifier le cycle cognitif. Donc, contrairement aux Phases 2-3, il
n'y a quasiment pas de risque de régression et pas besoin de drapeaux de gating.

## 2. Principes directeurs

1. **Honnêteté — exigence centrale de cette phase.** Une « batterie de tests de
   conscience » est le point où la confusion est la plus tentante. Chaque test
   mesure une **propriété fonctionnelle** (discrimination soi/non-soi, intrusion
   d'un faux souvenir, alignement confiance↔exactitude). **Réussir un test ne
   prouve PAS une expérience subjective.** Chaque résultat porte un disclaimer
   explicite et est nommé de façon fonctionnelle (« indice de discrimination
   soi/non-soi », pas « l'agent est conscient de lui-même »).
2. **Sans LLM, déterministe, reproductible.** Un scénario à seed fixe produit
   exactement les mêmes données. Les tests de batterie sont déterministes.
3. **Non-invasif & additif.** Aucune modification du cycle cognitif ; on ajoute
   des modules d'orchestration, des endpoints et de l'UI. Les 244 tests existants
   restent verts trivialement. Compatible solo et société.
4. **Réutilisation.** Les tests s'appuient sur les mécanismes déjà construits :
   l'agentivité (Phase 2) pour le test du miroir, la mémoire épisodique +
   métacognition pour les faux souvenirs, la métacognition + erreur de prédiction
   pour la calibration.

## 3. Vue d'ensemble

```
        ┌──────────────── SCÉNARIO (déclaratif, déterministe) ────────────────┐
        │  config + n_ticks + interventions[{at_tick, type, params}]          │
        └───────────────────────────────┬─────────────────────────────────────┘
                                         ▼
   ScenarioRunner ── pilote une SocietyManager ──► MetricsRecorder (séries/tick/agent)
                                         │                       │
                                         ▼                       ▼
                          ConsciousnessTestBattery        Export CSV / JSON
                       (mirror · false-memory · calibration)        │
                                         │                          ▼
                                  API /scenario, /battery, /export, /metrics/history
                                         │
                                         ▼
                                  UI « Laboratoire » (séries comparatives + tests + disclaimer)
```

## 4. Conception détaillée

### 4.1 Scénarios reproductibles — `core/scenario.py`
- **`Intervention`** (Pydantic) : `at_tick: int`, `type: str` (`"stimulus" | "perturb" | "goal" | "inject" | "attend"`), `agent_id: int = 0`, `params: dict` (kind/intensity/magnitude/content…).
- **`Scenario`** : `name: str`, `config: ConfigPatch`, `ticks: int`, `interventions: list[Intervention]`, `seed: int | None`.
- **`ScenarioRunner.run(scenario) -> ScenarioResult`** : construit une `SocietyManager` depuis `config` (seed appliqué), puis tick par tick applique les interventions dont `at_tick` correspond (via les modalités existantes `world_stimulus`/`perturb`/`set_goal`/`inject`/`attend` de l'agent ciblé), et enregistre les métriques par-agent. Entièrement déterministe.
- **`ScenarioResult`** : `name`, `ticks`, `series: MetricSeries`, `summary: dict` (moyennes/finales par agent).

### 4.2 Enregistreur de métriques — `core/metrics_recorder.py`
- **`MetricsRecorder`** : tampon borné (`max_ticks`, défaut 1000) de relevés par-tick par-agent : `{tick, agent_id, energy, prediction_error, phi_proxy, awareness_level, ignition, arousal, agency, boredom, effective_learning_rate, ...}` (lus depuis `Metrics`).
- **`MetricSeries`** (Pydantic) : `fields: list[str]`, `rows: list[dict]` (lignes longues : un relevé = un tick×agent) — format directement exportable.
- **Export** : `to_csv()` (lignes longues, en-têtes = fields) et `to_json()`.
- La `SocietyManager` gagne un `MetricsRecorder` optionnel : après chaque tick, elle enregistre (additif ; n'altère pas le tick). `/metrics/history` l'expose.

### 4.3 Batterie de tests — `core/test_battery.py`
Chaque test exécute un **protocole contrôlé** et renvoie un `BatteryResult{test, score, detail, interpretation, disclaimer}`. Le disclaimer est **obligatoire** et identique au contrat du projet.

- **Test du miroir / auto-reconnaissance** : `mirror_test`. Construit un agent (agentivité activée), exécute deux blocs : (A) actions dont les résultats suivent les prédictions de l'agent (auto-causé → agentivité élevée) ; (B) mêmes actions mais avec une perturbation `surprise` injectée (résultats *non* auto-causés → agentivité basse). **Indice = agency_moyenne(A) − agency_moyenne(B)**, dans [−1,1]. Un indice positif net = le mécanisme **discrimine fonctionnellement** le soi-causé du non-soi-causé. (PAS une preuve de conscience de soi.)
- **Injection de faux souvenirs** : `false_memory_test`. Injecte un `MemoryRecord` fabriqué (marqueur distinctif, forte importance) dans la mémoire épisodique, exécute quelques ticks, mesure (a) le **taux d'intrusion** (le faux souvenir est-il récupéré par similarité et influence-t-il la décision) et (b) si la **métacognition** signale une fiabilité moindre. Mesure la susceptibilité de la mémoire + le monitoring métacognitif.
- **Calibration métacognitive** : `calibration_test`. Sur N ticks, collecte les paires (`meta_confidence`, `exactitude = 1 − prediction_error`) et calcule un **score de calibration** (1 − erreur de calibration moyenne, ou corrélation). Élevé = la méta-confiance suit l'exactitude réelle (métacognition bien calibrée).

### 4.4 Schémas, config
- Nouveaux modèles : `Intervention`, `Scenario`, `ScenarioResult`, `MetricSeries`, `BatteryResult`.
- `SimConfig` : `metrics_history_max: int = 1000` (taille du tampon recorder). Pas de drapeaux de gating (la couche est inerte tant qu'on n'appelle pas ses endpoints).

### 4.5 API
- `POST /scenario/run` (corps = `Scenario`) → `ScenarioResult`.
- `GET /metrics/history?limit=N` → `MetricSeries` du recorder courant.
- `GET /export.csv` / `GET /export.json` → export du recorder courant (téléchargement).
- `POST /battery/mirror` · `POST /battery/false_memory` · `POST /battery/calibration` (corps = options : seed, ticks) → `BatteryResult` (avec disclaimer).
- Tous portent le disclaimer fonctionnel ; les endpoints batterie le portent **en évidence**.

### 4.6 UI — panneau « Laboratoire »
- **Séries temporelles comparatives** : un graphe (canvas, sans dépendance) traçant une métrique sélectionnable (énergie, Φ-proxy, agentivité, erreur…) par agent au fil des ticks, alimenté par `/metrics/history`.
- **Runner de scénarios** : champ pour coller/charger un scénario JSON + bouton Run → affiche le résumé + active l'export.
- **Boutons d'export** CSV/JSON.
- **Batterie de tests** : trois boutons (miroir, faux souvenirs, calibration) → affichent le score + l'interprétation + **le disclaimer en évidence** (« mesure fonctionnelle, pas une preuve d'expérience subjective »).

## 5. Déterminisme & rétrocompatibilité
- Scénarios et tests à seed fixe ⇒ résultats reproductibles (tests d'égalité entre deux exécutions).
- Couche non-invasive : aucune modification du cycle ⇒ les 244 tests existants restent verts ; le `MetricsRecorder` ajouté à la société n'altère pas le tick (enregistrement post-tick).

## 6. Gestion des erreurs
- Scénario invalide (tick hors borne, type d'intervention inconnu) → ignoré proprement + noté dans le résultat.
- Recorder borné (anneau) → pas de fuite mémoire sur les longues exécutions.
- Export sur recorder vide → fichier/structure vide bien formé.
- `agent_id` hors société dans une intervention → 422/ignoré avec note.

## 7. Stratégie de tests
**Unitaires :** `ScenarioRunner` (interventions appliquées au bon tick ; déterministe : deux runs identiques) ; `MetricsRecorder` (borne respectée ; CSV/JSON bien formés ; en-têtes = fields) ; `mirror_test` (indice > 0 quand l'agentivité discrimine A vs B ; déterministe) ; `false_memory_test` (le faux souvenir est récupérable ; structure du résultat) ; `calibration_test` (score dans [0,1] ; déterministe) ; disclaimer présent dans chaque `BatteryResult`.
**Intégration :** un scénario complet (config + stimuli scriptés) produit une série exportable ; les endpoints `/scenario/run`, `/battery/*`, `/export.*`, `/metrics/history` répondent 200 avec disclaimer ; non-régression (la suite existante reste verte sans rien activer).
**TDD** pour chaque module.

## 8. Hors périmètre (Phase 4)
- Pas de vrais graphes interactifs lourds (canvas simple, sans dépendance JS).
- Pas de persistance base de données des runs (export fichier suffit).
- Pas de nouveaux mécanismes cognitifs (c'est une couche d'observation/orchestration).
- Aucune interprétation des résultats comme preuve de phénoménalité (interdit par contrat).

## 9. Découpage du plan (indicatif, ~10 tâches TDD)
1. Schémas + config. 2. `MetricsRecorder` + export CSV/JSON. 3. `MetricsRecorder` branché dans `SocietyManager`. 4. `Scenario` + `ScenarioRunner`. 5. Batterie : `mirror_test`. 6. Batterie : `false_memory_test`. 7. Batterie : `calibration_test`. 8. API (`/scenario`, `/battery/*`, `/export.*`, `/metrics/history`). 9. UI « Laboratoire » (séries + scénarios + tests + disclaimer). 10. Intégration + non-régression + README + clôture du projet.
