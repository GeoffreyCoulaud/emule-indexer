# Task 9 — Rapport : `targets_read` + `matching_read`

## Formule `size_mb` trouvée dans `observation.py`

Source : `packages/crawler/src/emule_indexer/domain/observation.py`, lignes 14 et 44 :

```python
_BYTES_PER_MIB = 1024 * 1024
# ...
size_mb=self.size_bytes / _BYTES_PER_MIB,
```

Commentaire du crawler : *« les "MB" affichés par les clients eMule sont binaires (Mio) »* (Décision 8).

Reproduit verbatim dans `matching_read.py` (`_BYTES_PER_MIB = 1024 * 1024` + `size_bytes / _BYTES_PER_MIB`). Vérifié par un test `attr_between` sur `size_mb` avec 104857600 octets = 100.0 MiB exactement.

## RED / GREEN

- **RED** : `ModuleNotFoundError` sur les deux imports (modules inexistants). ✓
- **GREEN** : 10/10 tests ciblés, puis 42/42 en suite complète, 100% branch coverage. ✓

## Signatures confirmées

- `parse_targets(raw: dict[str, Any]) -> tuple[TargetSegment, ...]` — lève `ConfigError` si `episodes` non-liste ou target_id en double.
- `parse_matcher_config(raw: dict[str, Any]) -> MatcherConfig` — lève `ConfigError`/`UnknownTokenError`/`CycleError`/`DepthExceededError`.
- `MatchingEngine.explain(candidate, target_id) -> Explanation | None` — `None` si target_id inconnu.

## Concern : conversion `size_mb` quand `size_bytes=None`

Dans l'interface `explain()`, `size_bytes` peut être `None` (observation sans taille). Dans ce cas `size_mb=None` est passé au `FileCandidate`. Le moteur gère `None` correctement pour `attr_between` (il écartera le token). Pas de problème.

## Fichiers créés

- `packages/webui/src/catalog_webui/adapters/targets_read.py`
- `packages/webui/src/catalog_webui/adapters/matching_read.py`
- `packages/webui/tests/test_webui_targets_read.py`
- `packages/webui/tests/test_webui_matching_read.py`
