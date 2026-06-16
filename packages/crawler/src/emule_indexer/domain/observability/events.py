"""Événements d'observabilité : faits métier PURS (spec Plan E §3-4).

Couche DOMAINE (pure). Une dataclass GELÉE par fait observable saillant ; union taguée
``Event``. Champs métier UNIQUEMENT — aucune notion de log/metric/notif (c'est le rôle de
``policy.describe``). Les faits de panne récurrents portent ``first_occurrence`` (calculé par
l'application via ``EdgeState``) pour l'anti-spam des notifications (E-D8).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchCycleCompleted:
    cycle_index: int
    duration_seconds: float


@dataclass(frozen=True)
class SearchExecuted:
    network: str
    n_results: int


@dataclass(frozen=True)
class InstanceUnreachable:
    instance: str


@dataclass(frozen=True)
class SearchFailed:
    instance: str
    network: str


@dataclass(frozen=True)
class AllInstancesBlind:
    first_occurrence: bool


@dataclass(frozen=True)
class ObservationRecorded:
    network: str


@dataclass(frozen=True)
class DecisionRecorded:
    target_id: str
    tier: str


@dataclass(frozen=True)
class DownloadQueued:
    target_id: str


@dataclass(frozen=True)
class DownloadCompleted:
    target_id: str
    ed2k_hash: str


@dataclass(frozen=True)
class PromotionFailed:
    ed2k_hash: str


@dataclass(frozen=True)
class VerificationCompleted:
    target_id: str
    verdict: str


@dataclass(frozen=True)
class VerifierUnavailable:
    first_occurrence: bool


@dataclass(frozen=True)
class ConnectedInstancesSampled:
    network: str
    count: int


@dataclass(frozen=True)
class VerificationQueueDepthSampled:
    count: int


@dataclass(frozen=True)
class CrawlerStarted:
    mode: str


@dataclass(frozen=True)
class PortSyncTriggered:
    old: int  # port d'écoute configuré avant
    new: int  # port forwardé visé (vers lequel on aligne amuled)


@dataclass(frozen=True)
class HighIdRecovered:
    port: int  # port High-ID confirmé après restart


@dataclass(frozen=True)
class PortMismatchUnresolved:
    first_occurrence: bool  # edge-triggered (E-D8) — calculé via EdgeState
    live: int  # port forwardé vivant (gluetun)
    configured: int  # port d'écoute d'amuled (resté faux)


type Event = (
    SearchCycleCompleted
    | SearchExecuted
    | InstanceUnreachable
    | SearchFailed
    | AllInstancesBlind
    | ObservationRecorded
    | DecisionRecorded
    | DownloadQueued
    | DownloadCompleted
    | PromotionFailed
    | VerificationCompleted
    | VerifierUnavailable
    | ConnectedInstancesSampled
    | VerificationQueueDepthSampled
    | CrawlerStarted
    | PortSyncTriggered
    | HighIdRecovered
    | PortMismatchUnresolved
)
