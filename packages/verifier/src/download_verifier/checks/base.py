"""Modèle de check & agrégation worst-status (spec analysis §5).

Chaque check rend un ``CheckOutcome(name, status, meta)`` avec ``status`` dans
``clean < suspicious < malicious``. Le verdict du fichier = worst-status sur la liste des
statuts. ``error`` n'est PAS un statut de check (c'est un résultat service-level, §6) — il
n'apparaît jamais ici.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

Status = Literal["clean", "suspicious", "malicious"]

# Ordre de gravité : un check plus grave écrase un check moins grave (worst-status).
STATUS_RANK: dict[Status, int] = {"clean": 0, "suspicious": 1, "malicious": 2}
_RANK_TO_STATUS: dict[int, Status] = {rank: status for status, rank in STATUS_RANK.items()}


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """Résultat d'un check : son nom, son verdict de gravité, et son apport à ``real_meta``."""

    name: str
    status: Status
    meta: Mapping[str, object]


def worst_status(statuses: Iterable[Status]) -> Status:
    """Statut le plus grave de ``statuses`` ; liste vide → ``clean`` (rien de dangereux vu)."""
    return _RANK_TO_STATUS[max((STATUS_RANK[status] for status in statuses), default=0)]
