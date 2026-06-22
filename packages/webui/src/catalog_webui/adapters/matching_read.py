"""Recalcul d'explication de match depuis la config courante (spec W-D7 / Task 9).

``MatchingExplainer`` charge ``matcher.yaml`` + ``targets.yaml`` au moment de la
construction (une seule fois) et expose ``explain()`` pour recalculer l'explication
d'un fichier contre la config ACTUELLE.

Conversion ``size_bytes → size_mb`` : reproduit exactement la logique de
``emule_indexer.domain.observation.FileObservation.to_candidate`` sans importer le
crawler. Source : ``packages/crawler/src/emule_indexer/domain/observation.py`` :

    _BYTES_PER_MIB = 1024 * 1024
    size_mb=self.size_bytes / _BYTES_PER_MIB

Les champs ``duration_sec`` et ``bitrate_kbps`` sont convertis ``int → float | None``
de la même façon (``float(x) if x is not None else None``).
"""

from pathlib import Path

import yaml

from catalog_matching.engine import Explanation, MatchingEngine
from catalog_matching.models import FileCandidate, TargetSegment
from catalog_matching.validation import parse_matcher_config, parse_targets

# Décision 8 du crawler : les « MB » eMule sont des Mio (binaire).
_BYTES_PER_MIB = 1024 * 1024


class MatchingExplainer:
    """Construit et met en cache un :class:`MatchingEngine` depuis les fichiers YAML.

    L'engine est résolu UNE FOIS (arbres de matchers pré-compilés par cible) à la
    construction. Les appels successifs à ``explain()`` réutilisent le même engine.
    """

    def __init__(self, *, matcher_yaml: Path, targets_yaml: Path) -> None:
        matcher_raw = yaml.safe_load(matcher_yaml.read_text(encoding="utf-8"))
        targets_raw = yaml.safe_load(targets_yaml.read_text(encoding="utf-8"))
        matcher_config = parse_matcher_config(matcher_raw)
        targets: tuple[TargetSegment, ...] = parse_targets(targets_raw)
        self._engine = MatchingEngine(matcher_config, targets)

    def explain(
        self,
        filename: str,
        size_bytes: int | None,
        media_length_sec: int | None,
        bitrate_kbps: int | None,
        target_id: str,
    ) -> Explanation | None:
        """Recalcule l'explication de ``filename`` contre la cible ``target_id``.

        Reproduit la conversion d'unités du crawler :
        - ``size_bytes / (1024 * 1024)`` → ``size_mb`` (Mio binaire, toujours fourni
          si ``size_bytes`` est non-``None``).
        - ``float(media_length_sec)`` → ``duration_sec`` (``None`` si absent).
        - ``float(bitrate_kbps)`` → ``bitrate_kbps`` du ``FileCandidate`` (``None`` si
          absent).

        Retourne ``None`` si ``target_id`` est inconnu de la config actuelle.
        """
        size_mb = size_bytes / _BYTES_PER_MIB if size_bytes is not None else None
        duration = float(media_length_sec) if media_length_sec is not None else None
        bitrate = float(bitrate_kbps) if bitrate_kbps is not None else None
        candidate = FileCandidate(
            filename=filename,
            size_mb=size_mb,
            duration_sec=duration,
            bitrate_kbps=bitrate,
        )
        return self._engine.explain(candidate, target_id)
