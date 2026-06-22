"""View-models PRÉCALCULÉS (spec webui W-D8) : les templates n'itèrent et n'interpolent
que ces champs — aucune logique côté template."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageStatus:
    status: str  # "found" | "partial" | "none"
    best_tier: str | None  # "download" | "notify" | "catalog" | None
    file_count: int


# ---------------------------------------------------------------------------
# Explorateur de fichiers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileRow:
    """Vue résumée d'un fichier pour l'explorateur (liste paginée)."""

    ed2k_hash: str
    size_bytes: int
    filename: str  # dernier nom observé
    source_count: int  # compteur de sources (dernière observation)
    last_seen: str  # observed_at de la dernière observation (ISO-8601 UTC)
    target_id: str | None  # dernière décision
    tier: str | None  # tier de la dernière décision
    last_verdict: str | None  # dernier verdict de vérification


# ---------------------------------------------------------------------------
# Détail d'un fichier
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationRow:
    """Une entrée de la timeline des observations."""

    id: int
    filename: str
    size_bytes: int
    source_count: int
    complete_source_count: int
    keyword: str
    observed_at: str
    node_id: str


@dataclass(frozen=True)
class DecisionView:
    """Dernière décision de matching pour un fichier."""

    target_id: str
    rule_name: str
    tier: str
    decided_at: str
    node_id: str


@dataclass(frozen=True)
class VerificationRow:
    """Un résultat de vérification."""

    id: int
    verdict: str
    verified_at: str
    node_id: str


@dataclass(frozen=True)
class FileDetail:
    """Vue complète d'un fichier : timeline + décision + verdicts."""

    ed2k_hash: str
    size_bytes: int
    aich_hash: str | None
    observations: tuple[ObservationRow, ...]
    decision: DecisionView | None  # None si aucune décision
    verifications: tuple[VerificationRow, ...]


# ---------------------------------------------------------------------------
# État du nœud (local.db)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DownloadRow:
    """Un téléchargement actif ou terminé (table downloads)."""

    ed2k_hash: str
    target_id: str
    state: str
    queued_at: str
    completed_at: str | None
    size_bytes: int


@dataclass(frozen=True)
class VerifTaskRow:
    """Une tâche de vérification (table verification_tasks)."""

    ed2k_hash: str
    status: str
    attempts: int
    enqueued_at: str
    lease_until: str | None


@dataclass(frozen=True)
class NodeState:
    """État complet du nœud : téléchargements, vérifications, scheduler, identité."""

    downloads: tuple[DownloadRow, ...]
    verification_tasks: tuple[VerifTaskRow, ...]
    scheduler: Mapping[str, str]  # toutes les paires de scheduler_state
    node_id: str | None  # None si absent de node_runtime
    created_at: str | None  # None si absent de node_runtime
