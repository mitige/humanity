# Wave C — Revue API indépendante de la refonte GUI (api-regression-reviewer)

Date : 2026-07-11 · Cible : `ui/app.js` (4 164 l., commit `536a388` « Le Méridien ») contre
`app/api/routes.py` (876 l.) · Serveur vivant sondé : `http://127.0.0.1:8123` (curl + python,
aucun Playwright, aucun endpoint LLM appelé) · Référence : `docs/ui-redesign/02-contract-map.md`
§2 et §5 · Baseline de diff : `09b30d2` (pré-refonte).

**Méthode** : grep exhaustif des `api("…")` / `postJSON("…")` / `window.open(…)` / `fetch(` de
`app.js` (le seul `fetch(` est le helper `api()`, l.68 ; aucun `WebSocket(`/`EventSource` côté UI),
mapping 1:1 contre les routes FastAPI, puis sondes réelles : GET de forme, quatre cas d'erreur,
et les écritures demandées. Diff des appels pré/post-refonte : **aucun appel retiré, deux ajouts**
(`GET /society/agent/{id}/consciousness` et `…/self-model`, tous deux existants côté backend).

---

## 1. Tableau des appels

Statuts observés en live sauf mention « code » (= vérifié par lecture routes.py + app.js,
non sondé pour ne pas perturber l'état vivant partagé).

### 1.1 Batch de poll (chaque appel `.catch(() => null)`)

| Appel | Méthode | Statut observé | Champs consommés | Note |
|---|---|---|---|---|
| `/state` | GET | 200 | OK — `world{grid_size,tick,agent,objects,season?,task?}`, `running`, `arousal`, `working_memory(_load)`, `self_model`, `disclaimer`, `framing` | forme legacy solo intacte |
| `/metrics` | GET | 200 | OK — 11 clés `METRIC_DEFS` + `tick,daylight,is_sleeping,agency,boredom,effective_learning_rate` | |
| `/agent/consciousness` | GET | 200 | OK — 30 clés (tous flags ON) ; sous-objets null tolérés (`\|\| {}`) | avant 1er tick : tout null, géré |
| `/agent/workspace` | GET | 200 | OK — WorkspaceState complet, `competition[]` inclus | reste la seule source des barres de compétition |
| `/agent/stream?limit=48` | GET | 200 | OK — `tick,ignited,awareness_level,phi_proxy,contents,dominant_source` | |
| `/agent/self-model` | GET | 200 | OK — `identity,age_ticks,energy,confidence,mood,coherence,relational_self,active_goals,narrative` | |
| `/agent/memory?limit=20` | GET | 200 | OK — liste MemoryRecord | |
| `/agent/introspection` | GET | 200 | OK — 7 champs INTRO_FIELDS | |

### 1.2 Blocs sérialisés après le batch

| Appel | Méthode | Statut observé | Champs consommés | Note |
|---|---|---|---|---|
| `/agent/memory/graph?limit=60&edges=3` | GET | 200 (sondé 10/2 : 10 nœuds, 11 arêtes) | OK — `nodes[{id,tick,action,importance,summary,valence}]`, `edges[{source,target,similarity}]` | littéral d'URL pytest intact |
| `/society/language` | GET | 200 | OK — `convergence`, `n_meanings_named`, `distinct_modal_words`, `dictionary{modal_word,agreement,speakers,variants}` | |
| `/metrics/history?limit=200` | GET | 200 | **OK — les 10 options du select existent toutes dans `series.fields`** (`tick,agent_id,energy,prediction_error,phi_proxy,awareness_level,ignition,arousal,agency,boredom,effective_learning_rate,meta_confidence`) | la refonte CORRIGE l'ancien bug (6 métriques fantômes → courbes plates) |
| `/society` | GET | 200 | OK — `world.agents[{id,x,y,energy,last_action,affect,valence}]` (sondé), `world.messages[]` = dumps complets `Message{id,tick_emitted,sender_id,content,vector,x,y,radius,ttl,word}` (schemas/models.py:41 + core/shared_world.py:455 ; liste vide au sondage), `agents{"0":{metrics{phi_proxy,awareness_level}}}` (sondé), `relations.edges[{from,to,trust,familiarity,affect}]` | **`familiarity` EXISTE** (core/society.py:492) — la lecture optionnelle `e.familiarity != null` est correcte ; la carte de contrats §2.3 était incomplète |
| `/society/agent/{id}/consciousness` | GET | 200 | OK — `conscious_moment.contents`, `workspace{ignited,ignition_score,effective_threshold,threshold}`, `attention_schema.aware_of` | **nouveau consommateur** ; avant le 1er tick le workspace est RÉDUIT (pas d'`ignition_score`/`effective_threshold`) → `num()`→0.000 + fallback `threshold`, dégradation propre vérifiée |
| `/society/agent/{id}/self-model` | GET | 200 | OK — `identity,energy,mood,coherence` | **nouveau consommateur** ; 404 agent absent → catch → « Inspector unavailable » |

### 1.3 À la demande

| Appel | Méthode | Statut observé | Champs consommés | Note |
|---|---|---|---|---|
| `/config` | GET | 200 | OK — 108 clés ; `perception_radius:3` (anneau du monde : vrai rayon, fini le 3 codé en dur), `ignition_threshold:0.3` | `CONFIG_CATALOG` (disclosure read-only) = 1:1 exact avec les 108 clés live, zéro clé inventée, zéro doublon ; `CONFIG_STRUCTURAL` == `RESET_REQUIRED_FIELDS` backend |
| `/agent/coverage` | GET | 200 | OK — `items[{theory,mechanism,module,flag,active}]`, `active_count`, `total` | |
| `/checkpoint/list` | GET | 200 | OK — `checkpoints[{name,tick,n_agents,saved_at,bytes,compatible}]` ; `compatible===false` → Load désactivé + « legacy » | |
| `/agent/memory/search?q=…&limit=8` | GET | 200 (q=rest&limit=3 : 3 résultats) | OK — `results[{similarity,action,tick,importance,summary}]` | littéral d'URL pytest intact |
| `/export/analysis` | GET (window.open) | 200 | OK — JSON agrégé (17 clés) | |
| `/export.csv` | GET (window.open) | 200 | OK — `Content-Disposition: attachment; filename=humanity_metrics.csv` | |
| `/export.json` | GET (window.open) | 200 | OK — `Content-Disposition: attachment` | |
| `/export/traces?limit=5&format=csv` | GET | 200 (54 Ko) | n/a — non consommé par l'UI | sondé sur demande de mission |

### 1.4 Écritures

| Appel | Méthode | Statut observé | Champs consommés | Note |
|---|---|---|---|---|
| `/tick` | POST | 200 | OK — CycleTrace complet (41 clés top-level ; toutes les clés lues par `applyTrace` présentes) | 1 seul tick tiré |
| `/run {tps}` | POST | code | rien consommé | non sondé : aurait démarré le run partagé (autre relecteur actif) |
| `/pause` | POST | code | rien | idem |
| `/reset` + patch sliders | POST | code | rien (puis reset client + refresh) | non sondé : destructif pour l'état vivant |
| `/config` (hot) | POST | 200 | OK — `{mode:"hot", changed_fields, config, state}` ; `state.world.agent` legacy présent (lecture `out.state.world \|\| out.world \|\| out.snapshot` valide) ; `out.config.ignition_threshold` présent | sondé avec un patch identité (`world_noise:0.1`, `changed_fields:[]`) |
| `/agent/goal {goal}` | POST | 200 | OK — SelfModelState complet, `active_goals` inclut « qa-goal » | |
| `/world/stimulus {kind,intensity}` | POST | 200 | OK — `{object{kind,x,y,…}, state}` | x/y omis → placé près de l'agent |
| `/agent/inject {content,activation,precision,ttl}` | POST | 200 | OK — `{accepted:true, pending:1}` (loggé entier) | |
| `/agent/attend {target_id,strength,ttl}` | POST | 200 | OK — `{ok:true, target_id:0}` (loggé entier) | |
| `/agent/perturb {type:"soothe",magnitude:0.5}` | POST | 200 | OK — `{effect{type,applied:true,fear,mood}, state}` ; le guard UI `effect.applied === false` correspond à la forme réelle | |
| `/agent/ask {question,intent?}` | POST | 200 | OK — `{question,intent,answer,grounding,disclaimer}` | probe gabarit, PAS un endpoint LLM (aucun crédit consommé) |
| `/society/config {n_agents}` | POST | code | `state.running` (forme society) | non sondé : reset complet destructif de la société vivante |
| `/scenario/run` (gabarit mission) | POST | 200 | OK — `series.rows` (5 lignes), `summary` dict → `JSON.stringify` côté UI | sim isolée |
| `/battery/{name}` | POST | 200 (mirror seed=42 ticks=3 : score 0.8227) + 404 (`inconnu`) | OK — `score`, `interpretation`, `disclaimer` (verbatim → `#lab-disclaimer`) | sim isolée |
| `/train {ticks:50}` | POST | 200 | OK — `ticks_run:50` | avance l'état vivant (assumé, mission) |
| `/checkpoint/save {name}` | POST | code | `name`, `tick` | non sondé : ~950 Mo par checkpoint sur cette machine |
| `/checkpoint/load {name}` | POST | 404 sondé (`n-existe-pas` → `{"detail":"checkpoint 'n-existe-pas' not found"}`) ; 200 code | `tick` + reset client + `refreshClientConfig()` | |
| `/checkpoint/delete {name}` | POST | code | rien | |
| `/agent/narrate` `/agent/audit` `/agent/report-card` `/agent/converse` `/agent/biography` `/agent/cross-examine` `/agent/inner-voice` | POST | **non appelés** (LLM — crédits) | routes existent ; guards 503 (pas de clé) / 502 (provider) vérifiés en code ; dégradation UI inline conforme §5.1 | interdits par la mission |
| `WS /ws/society` | WS | 1 frame reçue (python websockets) | frame = `{world, agents, n_agents, relations, running}` | non consommé par l'UI (toujours en polling) ; NB : la frame WS n'a PAS `disclaimer`/`framing` (le GET /society les ajoute) |

### 1.5 Cas d'erreur (sondés)

| Cas | Statut | Corps observé | Consommation frontend |
|---|---|---|---|
| `POST /config {"grid_size":20}` | **409** | `{"detail":{"fields":["grid_size"],"instruction":"Use POST /reset for structural changes."}}` | `api()` pose `err.status=409` et `err.detail`=corps entier → `configErrorFeedback` lit `e.detail.detail.fields` = `["grid_size"]` → **la chaîne de lecture correspond exactement à la forme réelle** ; toast « Structural field (grid_size) — apply it through Reset. » |
| `POST /config {"unknown_field":1}` | **422** | `{"detail":[{"type":"extra_forbidden",…}]}` (liste) | `Array.isArray(e.detail.detail.fields)` faux → chemin générique « Config error » (voulu) |
| `POST /checkpoint/load {"name":"n-existe-pas"}` | **404** | detail string | catch → « load failed » |
| `POST /battery/inconnu` | **404** | `{"detail":"unknown test 'inconnu'"}` | catch → « inconnu error: … » |

---

## 2. localStorage / invariants config

| Invariant | Verdict |
|---|---|
| Clé `humanity.settings` | **Intacte** — même const `SETTINGS_KEY` (l.89), même forme plate `{clé: bool\|number}`, try/catch partout ; écrite sur toggle (l.2753), commit slider (l.2729), profil P7 (l.2792), fast-train (l.3332) ; lue au bootstrap uniquement |
| Clé `cws-theme` | **Intacte** — mêmes clé/valeurs `dark`/`light`, lecture à l'init + écriture au toggle (l.196/202). La lecture d'init n'est pas enveloppée try/catch mais est OCTET-IDENTIQUE au code pré-refonte (`09b30d2` l.159) — pré-existant, pas une régression |
| `SETTINGS_DEFAULTS` | **Sémantique inchangée** — diff pré/post-refonte : ensemble de clés IDENTIQUE (30 flags), toutes `true`, objet littéral (pytest OK) |
| `applyDeepDefaults` | **Intact** — même algorithme : merge `{...DEFAULTS, ...saved}` → `GET /config` → diff → POST des seules clés différentes → `saveSettings(cfg)` → `applyControlStates(cfg)` ; fallback POST du set complet si GET échoue. Ajout non-cassant : mémorise `clientConfig` pour les cadrans |
| Nouvelles clés | `humanity.ui.nav`, `humanity.ui.lastRoute`, `humanity.ui.charter.dismissed` — additives, toutes try/catch, aucune collision |

---

## 3. Constats par sévérité

### Haute
**Aucun.**

### Moyenne
**Aucun.**

### Basse / informatif
1. **Ternaire mort dans `renderSocietyMessages`** (app.js:3001-3002) : `cond ? messages : messages` —
   les deux branches sont identiques (probable reliquat d'un filtre par agent abandonné). Aucun
   effet fonctionnel ; à nettoyer ou à finir.
2. **Parité WS** : la frame `WS /ws/society` (mgr.state() brut) n'a pas `disclaimer`/`framing`,
   contrairement à `GET /society`. Sans impact aujourd'hui (l'UI polle) ; à savoir si une itération
   future bascule le poll sur le WS.
3. **Inspecteur avant le 1er tick** : `GET /society/agent/{id}/consciousness` renvoie un workspace
   RÉDUIT (`{ignited,winner_source,winner_content,broadcast_strength,threshold}`) sans
   `ignition_score`/`effective_threshold` → l'inspecteur affiche « score 0.000 / eff 0.300 ».
   Dégradation propre (fallbacks vérifiés live), pas un crash — juste un affichage neutre.
4. **`02-contract-map.md` §2.3 à amender** : les arêtes de `GET /society(/relations)` portent AUSSI
   `familiarity` (core/society.py:492) — la carte documente `{from,to,trust,affect}` seulement.
   Le nouveau consommateur UI est correct ; c'est la doc de référence qui est incomplète.
5. **Lecture thème non gardée** (l.196, top-level IIFE) : un localStorage inaccessible ferait
   échouer tout app.js — mais c'est octet-identique au code pré-refonte, hors périmètre de la
   régression (durcissement possible un jour).

---

## 4. État du serveur après revue

- `POST /agent/goal` n'a pas d'inverse : le but « qa-goal » RESTE dans `active_goals` de
  l'agent 0 (aux côtés des buts permanents « invent a language », « become someone » issus des flags).
- Tick avancé par les écritures demandées (1 × /tick + 50 × /train + probes) ; un objet `food`
  injecté près de l'agent ; perturbation « soothe » transitoire. `running` laissé tel que trouvé
  (False). Patch config sondé en valeur identité (`world_noise:0.1`) → `changed_fields:[]`,
  zéro dérive de config. Aucun checkpoint créé/supprimé, aucun crédit LLM consommé.

---

## 5. Verdict global

**CONFORME.** Le frontend refondu consomme l'API sans aucune régression de contrat détectée :

- **38 appels uniques, 38 routes backend existantes, méthodes correctes, zéro chemin mort,
  zéro paramètre inventé.** Le delta d'appels de la refonte est strictement additif (les 2
  endpoints de l'inspecteur par-agent).
- Tous les champs lus par les NOUVEAUX consommateurs existent dans les payloads réels
  (society/messages/relations avec `familiarity`, inspecteur par-agent, les 10 métriques du
  select lab toutes présentes dans `series.fields`, `perception_radius`/`ignition_threshold`).
- La refonte CORRIGE deux mensonges silencieux de l'ancienne UI : le rayon de perception codé
  en dur (3) devient le vrai `config.perception_radius`, et le select lab ne propose plus de
  métriques absentes de la série.
- Les quatre cas d'erreur ont exactement la forme que le code consomme (le 409 structurel est
  désormais EXPLIQUÉ à l'utilisateur au lieu du « Config error » générique — amélioration).
- Les invariants localStorage (`humanity.settings`, `cws-theme`, `SETTINGS_DEFAULTS`,
  `applyDeepDefaults`) sont préservés à l'identique.
