"""Adapter ``Quarantine`` sur le système de fichiers (spec download §8 — DÉCISION D10).

``promote`` fait un ``os.replace`` (rename ATOMIQUE même-FS) du fichier de staging vers
``quarantine_dir / <hash>`` : opération de métadonnée seule, le contenu n'est JAMAIS ouvert,
lu, ni rendu exécutable (le rename ne touche pas les permissions). Un échec (FS plein,
cross-device → ``OSError`` ; source ET cible absentes → ``FileNotFoundError``) PROPAGE : la
boucle de download laisse alors le download en ``completed`` et retentera (spec §9). Mais
re-promouvoir un hash DÉJÀ promu (source consommée par ``os.replace``, cible en place) est un
no-op idempotent — la séquence post-promote (enqueue/set_state) peut donc être rejouée sans
risque après un échec transitoire (cf. logic-download#0). Le staging et la quarantaine DOIVENT
être sur le même système de fichiers (sinon ``os.replace`` lève — contrainte de déploiement,
vérifiée au câblage de D-verify).
"""

import os
from pathlib import Path


class FilesystemQuarantine:
    """Mise en quarantaine par rename atomique (satisfaction STRUCTURELLE du port)."""

    def __init__(self, quarantine_dir: Path) -> None:
        self._quarantine_dir = quarantine_dir

    def promote(self, staging_path: Path, ed2k_hash: str) -> None:
        """Rename atomique ``staging_path`` → ``quarantine_dir/<hash>`` (spec §8).

        ``os.replace`` est atomique sur le même FS ; il écrase une cible existante (un
        re-promote idempotent du même hash est sûr) et ne modifie pas les permissions (jamais
        +x).

        IDEMPOTENT face à une source DÉJÀ CONSOMMÉE : ``os.replace`` détruit la source, donc si
        une étape post-promote (enqueue/set_state) échoue et que la boucle retente, ``promote``
        est rappelé avec la source absente alors que ``quarantine/<hash>`` est déjà en place. Ce
        cas est un SUCCÈS (le fichier EST promu), pas un échec → no-op (sinon le fichier reste
        bloqué en ``completed`` pour toujours, jamais vérifié — cf. logic-download#0). Une source
        absente SANS cible (jamais promu) lève bien ``FileNotFoundError`` ; la boucle retentera.
        """
        # ed2k_hash : toujours 32 caractères [0-9a-f] (garanti en amont — _map_partfile .hex(),
        # _CANONICAL_HASH_RE, et la contrainte CHECK SQLite) → aucun '/'/'..' possible, pas de
        # traversée de chemin hors quarantine_dir.
        target = self._quarantine_dir / ed2k_hash
        try:
            os.replace(staging_path, target)
        except FileNotFoundError:
            if target.exists():
                return  # déjà promu (source consommée par une promotion antérieure) : idempotent
            raise  # jamais promu (source ET cible absentes) : vraie panne, la boucle retentera
