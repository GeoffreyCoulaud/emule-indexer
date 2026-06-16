# Handoff — passe « réduction du backlog post-Plan E » COMPLÈTE (2026-06-16)

> Point d'entrée pour la prochaine session. La passe planifiée dans
> `docs/superpowers/specs/2026-06-15-backlog-parallelization-design.md` (méthodo **séquentielle
> subagent-driven**) est **terminée** : 7 tâches + 1 correctif holistique, **8 commits sur `main`**,
> gate vert à chaque étape. Jalon recommandé **`v0.12.0-hardening-highid`** (tag annoté, non poussé).

## 1. Ce qui a été construit (ordre des commits)

| Commit | Tâche | Résumé |
|---|---|---|
| `6ba42f9` | **1. fusion** | `python -m emule_indexer.merge` : N `catalog.db` → 1, idempotent (`INSERT OR IGNORE` + `WHERE NOT EXISTS`/`IS` + `SELECT DISTINCT` intra-source), safe-by-default. **Résout le dedup `file_verifications`.** |
| `901c4b7` | **2. docs** | déspéc ProtonVPN (4 providers PF/Low-ID), runbook public-moyen + pin `3.0.0-1` + egress-boot, enrichissement richesse EC. |
| `4eb3df3` | **3. crawler-cli** | sous-commande `validate-config` (invocation nue préservée) + `ec_probe --all-tags` (`fetch_results_raw`). |
| `6ec038b` | **4. crawler-app** | I2 (isolation `RepositoryError` par étape dans `run_download_cycle`) + T12 (test d'invariant « aucune tâche ne fuit » ; guard `if not task.done()` **non ajouté** — branche inatteignable). |
| `ce769da` | **5a. clamav** | check par signatures (opt-in `ENABLED_CHECKS`), `clamscan` standalone, rlimits relâchés conditionnellement ; sidecar `freshclam` + volume RO `clamav-db` ; `mem_limit` 2g. |
| `2d1b481` | **5b. ring seccomp** | `confine.py` : blocklist seccomp-bpf par-enfant (`pyseccomp`), fail-open, sans capability (`no_new_privs` posé par le conteneur). |
| `d8af87d` | **6. port-sync** | boucle High-ID : EC `SetPort` + restart amuled via `wollomatic/socket-proxy` (surface restart-amuled-only), lecteur gluetun, rate-limit, 3 events ; auth gluetun none + delta compose. |
| `1004485` | **7. e2e** | couche A (stub eD2k pur + MD4) + build couche B (`compose.e2e.yaml`, Dockerfile `ed2kd`) **tentés** ; le **transfert réel a été ABANDONNÉ** (même motif que la couche C, voir §4) et tout le scaffolding e2e **supprimé du dépôt** (stub, `test_e2e.py`, `compose.e2e.yaml`, submodule `submodules/ed2kd`, marqueur `e2e_integration`). DV10 reste couvert par les unit-tests + une hypothèse de déploiement. |
| `b94fa2c` | **holistique** | **fix** : les 3 métriques port-sync manquaient dans `PrometheusSink._COUNTERS` → `KeyError` qui crashait tout le crawl au 1er sync. Counters ajoutés + test de garde structurel policy→sink. |

Méthodo par tâche : implémenteur frais (TDD) → revue spec + revue code (sous-agents) → corrections → commit. Revue holistique finale sur l'ensemble (a trouvé le bug métriques).

## 2. État du gate (vert)

- `( cd packages/crawler && uv run pytest -q )` → **901 passed, 100 % branch**.
- `( cd packages/verifier && uv run pytest -q )` → **142 passed, 100 % branch**.
- `ruff check` / `ruff format --check` / `mypy` (strict, 241 fichiers) / `sqlfluff` → tous verts.
- Intégration runnable en sandbox lancée : `verify_integration` (1 passed), `analysis_integration`
  (8 passed, **3 skipped** = clamav/seccomp, faute de `clamscan`/`no_new_privs` dans le sandbox).
- `docker compose config` validé pour `--profile full` et `compose.smoke.yaml`.

## 3. Ce qui reste à Geoffrey (vrai shell / matériel — le sandbox ne peut pas)

1. **clamav réel** : `( cd packages/verifier && uv run pytest -m analysis_integration --no-cov )`
   avec `clamscan` + une base. **Valider/ajuster `RLIMIT_AS_BYTES_CLAMAV`/`mem_limit`** (si un média
   sain ressort `suspicious`, le scan se fait OOM/CPU-kill → relever).
2. **seccomp réel** : idem `analysis_integration` avec `pyseccomp`/`libseccomp` ; confirmer
   qu'un média sain reste `clean` sous filtre, et le comportement `no_new_privs` hors conteneur.
3. **port-sync** : EC réel (R3 — confirmer que la réponse `GET_PREFERENCES` porte l'opcode `0x40` ;
   R4 — detail level) contre un vrai `amuled` (`ec_integration`, `tests/integration/test_amuled_preferences.py`) ;
   restart réel → High-ID via un déploiement réel derrière le VPN.
4. **R1/R2 port-sync** (déjà confirmés via context7, à re-valider en réel) : syntaxe allowlist
   `wollomatic` + var `HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE` sur la version gluetun épinglée.
5. **DV10 — hypothèse de déploiement (ex-R6)** : confirmer **au premier vrai téléchargement** qu'amuled
   écrit un fichier fini dans son *Incoming* = le dossier monté comme `staging_dir` (pour que
   `resolve_staging_path`/`os.replace` promeuve vers la quarantaine intra-FS). Ce n'est **pas** un test
   à écrire : c'est un fait de configuration de déploiement (l'e2e « transfert réel » qui l'aurait
   synthétisé a été abandonné — voir §4).

## 4. Décisions actées / ouvertes (à trancher avec Geoffrey)

- **e2e « transfert réel » — ABANDONNÉE (décision actée).** Faire signaler un download terminé par un
  vrai `amuled` impose un vrai transfert eD2k → orchestrer/reverse-engineerer des outils tiers
  (`amuled`, `ed2kd` : `server.met` statique, isolation réseau, partage, High-ID), ce qui valide surtout
  du **comportement tiers de confiance**, pas notre code. **C'est le motif exact qui a fait abandonner la
  couche C** (port-forwarding gluetun). DV10 (`resolve_staging_path`, `os.replace`/promote, boucle
  download, détection de complétion) est **unit-testé à 100 %** ; la seule inconnue réelle (R6) est une
  **hypothèse de déploiement** (`staging_dir` = l'Incoming d'amuled), à confirmer en prod (cf. §3.5), pas
  via un transfert synthétique. Conséquence : tout le scaffolding e2e (stub eD2k + MD4 + planted,
  `tests/integration/test_e2e.py`, `compose.e2e.yaml`, `tests/e2e/` ed2kd, le submodule
  `submodules/ed2kd` + `.gitmodules`, le marqueur `e2e_integration`) a été **supprimé du dépôt**. Le
  design daté `docs/superpowers/specs/2026-06-15-e2e-suite-design.md` est conservé comme **record
  historique**.
- **Dispatcher & métriques (E-D13)** : `ObservabilityDispatcher` absorbe les pannes de **notif**
  (canal mort) mais **pas** celles de **métrique** (`metrics.apply` hors try/except). Le fix `b94fa2c`
  + le test de garde garantissent qu'aucune métrique émise n'est non-déclarée (donc plus de `KeyError`
  possible), mais une cohérence stricte « observability never breaks the crawl » voudrait absorber
  aussi `metrics.apply`. **Décision laissée à Geoffrey** (absorber masquerait un bug de déclaration —
  le test de garde est le meilleur filet ; ne pas absorber = fail-fast au test). 
- **Nom du jalon** `v0.12.0-hardening-highid` : recommandation, renommable (tag local non poussé).

## 5. Pièges appris cette passe (utiles pour la suite)

- **`SELECT DISTINCT` pour la dédup intra-source** (fusion) : `WHERE NOT EXISTS` ne dédupe que contre
  la destination ; deux lignes identiques DANS une même source passent toutes deux en un passage (et
  survivent à tout re-merge). Le `DISTINCT` ferme ça (cohérent avec le `IS` NULL-safe).
- **Guard inerte = branche inatteignable** (T12) : `if not task.done()` au point d'annulation du
  `TaskGroup` a sa branche vraie **inatteignable** (aucun `await` entre le réveil du shutdown et le
  `cancel()`) → l'ajouter casserait le 100 % branch. Le vrai livrable était le test d'invariant.
- **policy → sink** : ajouter un `MetricName` + une branche `describe` SANS l'ajouter à
  `PrometheusSink._COUNTERS` passe le gate (aucun test ne fermait la boucle) mais **crashe en prod**.
  Le test de garde `test_every_emitted_metric_is_declared_in_the_sink` (réutilise `CASES`) verrouille.
- **Frontière hexagonale dans une boucle** : capter `MuleClientError` (port) et non `EcError`
  (adapter) ; `EcError(MuleClientError)` → couvre injoignable ET `EC_OP_FAILED` sans importer l'adapter.
- **Deltas compose intégration-owned** : édités/validés par l'orchestrateur (`docker compose config`),
  pas par l'implémenteur (interactions topologie smoke). `freshclam`/`docker-proxy` désactivés en
  smoke via `profiles: !override [disabled]` ; clamav OFF en smoke via override `ENABLED_CHECKS`.
- **Lire la source amont avant de coder un tiers** : pendant le build e2e (depuis abandonné), ancrer
  l'intégration d'`ed2kd` dans sa source amont a corrigé une **erreur du design** (ed2kd n'a pas de
  flag `-c` — `optString="vhg"`, conf relative). Leçon générale toujours valable : ancrer dans la
  source amont d'un outil tiers quand c'est dispo, ne pas se fier au design seul.

## 6. Étape suivante recommandée

La passe est complète. Options pour la suite (par priorité décroissante de « est-ce que ça marche ») :
1. **Geoffrey lance les validations réseau/réel §3** (clamav rlimits, port-sync EC réel, et l'hypothèse
   de déploiement DV10 au premier vrai téléchargement) et remonte les inconnus restants → on fige les
   réponses dans les design docs / ce handoff.
2. **Trancher la décision ouverte §4** (absorption métriques ; l'abandon e2e est déjà acté).
3. Backlog basse-prio non planifié : WebUI, hub central (Postgres/push), rétention/compaction, le
   reste du **ring noyau** (`net=none`/bwrap/RO-mounts/tmpfs — exige un changement de stratégie de
   confinement, `CAP_SYS_ADMIN`/userns).
