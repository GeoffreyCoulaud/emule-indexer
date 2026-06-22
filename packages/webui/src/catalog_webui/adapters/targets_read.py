"""Chargement des cibles depuis un fichier YAML (spec W-D7 / Task 9).

``load_targets`` lit ``targets.yaml``, en valide minimalement la structure de
surface (mapping attendu en racine), puis délègue la validation complète à
``catalog_matching.validation.parse_targets``.

L'I/O (``yaml.safe_load``) est ici ; ``parse_targets`` est domaine pur.
"""

from pathlib import Path

import yaml

from catalog_matching.models import TargetSegment
from catalog_matching.validation import ConfigError, parse_targets


def load_targets(path: Path) -> tuple[TargetSegment, ...]:
    """Lit ``path`` (YAML) et retourne le tuple de :class:`TargetSegment` validés.

    Raises:
        OSError: si le fichier est illisible ou inexistant.
        ConfigError: si la racine YAML n'est pas un mapping ou si ``parse_targets``
            détecte une erreur de schéma/sémantique.
        ValueError: si la racine parsée n'est pas un dict (YAML non-mapping).
    """
    raw_text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text)
    if raw is None:
        raise ConfigError(f"{path} : fichier YAML vide, mapping attendu")
    if not isinstance(raw, dict):
        raise ConfigError(
            f"{path} : racine YAML invalide — mapping attendu, obtenu {type(raw).__name__}"
        )
    return parse_targets(raw)
