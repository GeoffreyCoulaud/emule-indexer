"""Politique d'observabilité : ``describe(event) → Report`` (spec Plan E §3, E-D3).

Couche DOMAINE (pure). SEUL endroit qui décide — pour chaque événement — sévérité, message,
métrique(s), audiences. ``describe`` est un match EXHAUSTIF (``assert_never`` → 100 % branch).
Le domaine ne connaît ni ``logging`` ni Prometheus ni apprise : ``Severity``/``Audience``/
``MetricName`` sont des enums DOMAINE, traduits par les adapters (E-D3).

GOTCHA Prometheus : les noms de COUNTERS n'incluent PAS ``_total`` ici — ``prometheus_client``
l'ajoute à l'exposition (l'inclure produirait ``…_total_total``). Gauges/histogramme : nom tel
quel.
"""

from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from typing import Literal, assert_never

from emule_indexer.domain.observability.events import (
    AllInstancesBlind,
    ConnectedInstancesSampled,
    CrawlerStarted,
    DecisionRecorded,
    DownloadCompleted,
    DownloadQueued,
    Event,
    InstanceUnreachable,
    ObservationRecorded,
    PromotionFailed,
    SearchCycleCompleted,
    SearchExecuted,
    SearchFailed,
    VerificationCompleted,
    VerificationQueueDepthSampled,
    VerifierUnavailable,
)


class Severity(Enum):
    """Sévérité DOMAINE d'un fait (traduite en niveau ``logging`` par l'adapter)."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


class Audience(Enum):
    """Consommateur d'une notification (E-D7) — la VALEUR est le tag apprise."""

    COMMUNITY = "community"
    OPERATIONS = "operations"


class MetricName(StrEnum):
    """Noms de métriques. Counters SANS ``_total`` (ajouté par prometheus_client à l'expo)."""

    SEARCH_CYCLES = "emule_search_cycles"
    SEARCH_CYCLE_DURATION = "emule_search_cycle_duration_seconds"
    SEARCHES = "emule_searches"
    OBSERVATIONS = "emule_observations"
    SEARCH_FAILURES = "emule_search_failures"
    MULE_UNREACHABLE = "emule_mule_unreachable"
    SEARCH_BLIND_CYCLES = "emule_search_blind_cycles"
    DECISIONS = "emule_decisions"
    DOWNLOADS_QUEUED = "emule_downloads_queued"
    DOWNLOADS_COMPLETED = "emule_downloads_completed"
    PROMOTION_FAILURES = "emule_promotion_failures"
    VERIFICATIONS = "emule_verifications"
    VERIFIER_UNAVAILABLE = "emule_verifier_unavailable"
    CONNECTED_INSTANCES = "emule_connected_instances"
    VERIFICATION_QUEUE_DEPTH = "emule_verification_queue_depth"
    CRAWLER_UP = "emule_crawler_up"


MetricKind = Literal["inc", "set", "observe"]


@dataclass(frozen=True)
class MetricInstruction:
    """Une opération de métrique : compteur ``inc`` / jauge ``set`` / histogramme ``observe``.

    ``labels`` = tuple de paires (clé, valeur) ordonnées (hashable → utilisable dans un test
    d'égalité de ``Report``). ``value`` = quantité (défaut 1.0 pour les ``inc``).
    """

    name: MetricName
    kind: MetricKind
    labels: tuple[tuple[str, str], ...] = ()
    value: float = 1.0


@dataclass(frozen=True)
class Report:
    """Comment raconter un événement : sévérité + message + métrique(s) + audiences de notif.

    ``metrics`` est un TUPLE (un événement peut alimenter plusieurs métriques —
    ``SearchCycleCompleted`` = compteur + histogramme). ``audiences`` vide = aucune notif.
    """

    severity: Severity
    message: str
    metrics: tuple[MetricInstruction, ...] = ()
    audiences: frozenset[Audience] = frozenset()


_VERDICT_SEVERITY: dict[str, Severity] = {
    "clean": Severity.INFO,
    "suspicious": Severity.INFO,
    "malicious": Severity.WARNING,
    "error": Severity.WARNING,
}
_VERDICT_AUDIENCES: dict[str, frozenset[Audience]] = {
    "clean": frozenset({Audience.COMMUNITY}),
    "suspicious": frozenset({Audience.OPERATIONS}),
    "malicious": frozenset({Audience.OPERATIONS}),
    "error": frozenset(),
}


def _verification(event: VerificationCompleted) -> Report:
    # verdict inconnu (contrat verifier non respecté) → traité comme ``error`` (défensif, E-D13).
    severity = _VERDICT_SEVERITY.get(event.verdict, Severity.WARNING)
    audiences = _VERDICT_AUDIENCES.get(event.verdict, frozenset())
    return Report(
        severity,
        f"vérification {event.target_id} : verdict={event.verdict}",
        (MetricInstruction(MetricName.VERIFICATIONS, "inc", (("verdict", event.verdict),)),),
        audiences,
    )


def describe(event: Event) -> Report:
    """Mappe un événement vers son ``Report`` (match EXHAUSTIF → 100 % branch)."""
    match event:
        case SearchCycleCompleted():
            return Report(
                Severity.INFO,
                f"cycle {event.cycle_index} terminé ({event.duration_seconds:.1f}s)",
                (
                    MetricInstruction(MetricName.SEARCH_CYCLES, "inc"),
                    MetricInstruction(
                        MetricName.SEARCH_CYCLE_DURATION, "observe", value=event.duration_seconds
                    ),
                ),
            )
        case SearchExecuted():
            return Report(
                Severity.DEBUG,
                f"recherche {event.network} : {event.n_results} résultat(s)",
                (MetricInstruction(MetricName.SEARCHES, "inc", (("network", event.network),)),),
            )
        case InstanceUnreachable():
            return Report(
                Severity.WARNING,
                f"instance {event.instance} injoignable",
                (
                    MetricInstruction(
                        MetricName.MULE_UNREACHABLE, "inc", (("instance", event.instance),)
                    ),
                ),
            )
        case SearchFailed():
            return Report(
                Severity.WARNING,
                f"recherche en échec sur {event.network} (instance {event.instance})",
                (
                    MetricInstruction(
                        MetricName.SEARCH_FAILURES, "inc", (("network", event.network),)
                    ),
                ),
            )
        case AllInstancesBlind():
            return Report(
                Severity.WARNING,
                "couverture aveugle : aucune instance search-capable",
                (MetricInstruction(MetricName.SEARCH_BLIND_CYCLES, "inc"),),
                frozenset({Audience.OPERATIONS}) if event.first_occurrence else frozenset(),
            )
        case ObservationRecorded():
            return Report(
                Severity.DEBUG,
                f"observation enregistrée ({event.network})",
                (MetricInstruction(MetricName.OBSERVATIONS, "inc", (("network", event.network),)),),
            )
        case DecisionRecorded():
            return Report(
                Severity.INFO,
                f"décision {event.tier} pour {event.target_id}",
                (MetricInstruction(MetricName.DECISIONS, "inc", (("tier", event.tier),)),),
                frozenset({Audience.COMMUNITY}) if event.tier == "download" else frozenset(),
            )
        case DownloadQueued():
            return Report(
                Severity.INFO,
                f"download mis en file : {event.target_id}",
                (MetricInstruction(MetricName.DOWNLOADS_QUEUED, "inc"),),
            )
        case DownloadCompleted():
            return Report(
                Severity.INFO,
                f"✅ téléchargement terminé : {event.target_id}",
                (MetricInstruction(MetricName.DOWNLOADS_COMPLETED, "inc"),),
                frozenset({Audience.COMMUNITY}),
            )
        case PromotionFailed():
            return Report(
                Severity.WARNING,
                f"mise en quarantaine échouée : {event.ed2k_hash}",
                (MetricInstruction(MetricName.PROMOTION_FAILURES, "inc"),),
            )
        case VerificationCompleted():
            return _verification(event)
        case VerifierUnavailable():
            return Report(
                Severity.WARNING,
                "verifier injoignable",
                (MetricInstruction(MetricName.VERIFIER_UNAVAILABLE, "inc"),),
                frozenset({Audience.OPERATIONS}) if event.first_occurrence else frozenset(),
            )
        case ConnectedInstancesSampled():
            return Report(
                Severity.DEBUG,
                f"instances connectées ({event.network}) : {event.count}",
                (
                    MetricInstruction(
                        MetricName.CONNECTED_INSTANCES,
                        "set",
                        (("network", event.network),),
                        float(event.count),
                    ),
                ),
            )
        case VerificationQueueDepthSampled():
            return Report(
                Severity.DEBUG,
                f"file de vérification : {event.count} en attente",
                (
                    MetricInstruction(
                        MetricName.VERIFICATION_QUEUE_DEPTH, "set", (), float(event.count)
                    ),
                ),
            )
        case CrawlerStarted():
            return Report(
                Severity.INFO,
                f"🟢 instance en ligne (mode {event.mode})",
                (MetricInstruction(MetricName.CRAWLER_UP, "set", (), 1.0),),
                frozenset({Audience.COMMUNITY, Audience.OPERATIONS}),
            )
        case _:  # pragma: no cover
            assert_never(event)
