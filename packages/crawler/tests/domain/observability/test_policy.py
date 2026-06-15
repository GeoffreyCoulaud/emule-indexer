"""``describe`` est un match exhaustif : un cas par événement + chaque branche conditionnelle
(verdict connu/inconnu, tier download/autre, first_occurrence vrai/faux)."""

from emule_indexer.domain.observability import events as ev
from emule_indexer.domain.observability.policy import (
    Audience,
    MetricInstruction,
    MetricName,
    Report,
    Severity,
    describe,
)

_COMMUNITY = frozenset({Audience.COMMUNITY})
_OPERATIONS = frozenset({Audience.OPERATIONS})
_BOTH = frozenset({Audience.COMMUNITY, Audience.OPERATIONS})


CASES: list[tuple[ev.Event, Report]] = [
    (
        ev.SearchCycleCompleted(cycle_index=3, duration_seconds=4.5),
        Report(
            Severity.INFO,
            "cycle 3 terminé (4.5s)",
            (
                MetricInstruction(MetricName.SEARCH_CYCLES, "inc"),
                MetricInstruction(MetricName.SEARCH_CYCLE_DURATION, "observe", value=4.5),
            ),
        ),
    ),
    (
        ev.SearchExecuted(network="ed2k", n_results=7),
        Report(
            Severity.DEBUG,
            "recherche ed2k : 7 résultat(s)",
            (MetricInstruction(MetricName.SEARCHES, "inc", (("network", "ed2k"),)),),
        ),
    ),
    (
        ev.InstanceUnreachable(instance="amule-1"),
        Report(
            Severity.WARNING,
            "instance amule-1 injoignable",
            (MetricInstruction(MetricName.MULE_UNREACHABLE, "inc", (("instance", "amule-1"),)),),
        ),
    ),
    (
        ev.SearchFailed(instance="amule-1", network="kad"),
        Report(
            Severity.WARNING,
            "recherche en échec sur kad (instance amule-1)",
            (MetricInstruction(MetricName.SEARCH_FAILURES, "inc", (("network", "kad"),)),),
        ),
    ),
    (
        ev.AllInstancesBlind(first_occurrence=True),
        Report(
            Severity.WARNING,
            "couverture aveugle : aucune instance search-capable",
            (MetricInstruction(MetricName.SEARCH_BLIND_CYCLES, "inc"),),
            _OPERATIONS,
        ),
    ),
    (
        ev.AllInstancesBlind(first_occurrence=False),
        Report(
            Severity.WARNING,
            "couverture aveugle : aucune instance search-capable",
            (MetricInstruction(MetricName.SEARCH_BLIND_CYCLES, "inc"),),
        ),
    ),
    (
        ev.ObservationRecorded(network="kad"),
        Report(
            Severity.DEBUG,
            "observation enregistrée (kad)",
            (MetricInstruction(MetricName.OBSERVATIONS, "inc", (("network", "kad"),)),),
        ),
    ),
    (
        ev.DecisionRecorded(target_id="S2E062A", tier="download"),
        Report(
            Severity.INFO,
            "décision download pour S2E062A",
            (MetricInstruction(MetricName.DECISIONS, "inc", (("tier", "download"),)),),
            _COMMUNITY,
        ),
    ),
    (
        ev.DecisionRecorded(target_id="S2E062A", tier="candidate"),
        Report(
            Severity.INFO,
            "décision candidate pour S2E062A",
            (MetricInstruction(MetricName.DECISIONS, "inc", (("tier", "candidate"),)),),
        ),
    ),
    (
        ev.DownloadQueued(target_id="S2E062A"),
        Report(
            Severity.INFO,
            "download mis en file : S2E062A",
            (MetricInstruction(MetricName.DOWNLOADS_QUEUED, "inc"),),
        ),
    ),
    (
        ev.DownloadCompleted(target_id="S2E062A", ed2k_hash="a" * 32),
        Report(
            Severity.INFO,
            "✅ téléchargement terminé : S2E062A",
            (MetricInstruction(MetricName.DOWNLOADS_COMPLETED, "inc"),),
            _COMMUNITY,
        ),
    ),
    (
        ev.PromotionFailed(ed2k_hash="a" * 32),
        Report(
            Severity.WARNING,
            f"mise en quarantaine échouée : {'a' * 32}",
            (MetricInstruction(MetricName.PROMOTION_FAILURES, "inc"),),
        ),
    ),
    (
        ev.VerificationCompleted(target_id="S2E062A", verdict="clean"),
        Report(
            Severity.INFO,
            "vérification S2E062A : verdict=clean",
            (MetricInstruction(MetricName.VERIFICATIONS, "inc", (("verdict", "clean"),)),),
            _COMMUNITY,
        ),
    ),
    (
        ev.VerificationCompleted(target_id="S2E062A", verdict="suspicious"),
        Report(
            Severity.INFO,
            "vérification S2E062A : verdict=suspicious",
            (MetricInstruction(MetricName.VERIFICATIONS, "inc", (("verdict", "suspicious"),)),),
            _OPERATIONS,
        ),
    ),
    (
        ev.VerificationCompleted(target_id="S2E062A", verdict="malicious"),
        Report(
            Severity.WARNING,
            "vérification S2E062A : verdict=malicious",
            (MetricInstruction(MetricName.VERIFICATIONS, "inc", (("verdict", "malicious"),)),),
            _OPERATIONS,
        ),
    ),
    (
        ev.VerificationCompleted(target_id="S2E062A", verdict="error"),
        Report(
            Severity.WARNING,
            "vérification S2E062A : verdict=error",
            (MetricInstruction(MetricName.VERIFICATIONS, "inc", (("verdict", "error"),)),),
        ),
    ),
    (
        # verdict INCONNU → défensif
        ev.VerificationCompleted(target_id="S2E062A", verdict="bogus"),
        Report(
            Severity.WARNING,
            "vérification S2E062A : verdict=bogus",
            (MetricInstruction(MetricName.VERIFICATIONS, "inc", (("verdict", "bogus"),)),),
        ),
    ),
    (
        ev.VerifierUnavailable(first_occurrence=True),
        Report(
            Severity.WARNING,
            "verifier injoignable",
            (MetricInstruction(MetricName.VERIFIER_UNAVAILABLE, "inc"),),
            _OPERATIONS,
        ),
    ),
    (
        ev.VerifierUnavailable(first_occurrence=False),
        Report(
            Severity.WARNING,
            "verifier injoignable",
            (MetricInstruction(MetricName.VERIFIER_UNAVAILABLE, "inc"),),
        ),
    ),
    (
        ev.ConnectedInstancesSampled(network="ed2k", count=2),
        Report(
            Severity.DEBUG,
            "instances connectées (ed2k) : 2",
            (
                MetricInstruction(
                    MetricName.CONNECTED_INSTANCES, "set", (("network", "ed2k"),), 2.0
                ),
            ),
        ),
    ),
    (
        ev.VerificationQueueDepthSampled(count=5),
        Report(
            Severity.DEBUG,
            "file de vérification : 5 en attente",
            (MetricInstruction(MetricName.VERIFICATION_QUEUE_DEPTH, "set", (), 5.0),),
        ),
    ),
    (
        ev.CrawlerStarted(mode="full"),
        Report(
            Severity.INFO,
            "🟢 instance en ligne (mode full)",
            (MetricInstruction(MetricName.CRAWLER_UP, "set", (), 1.0),),
            _BOTH,
        ),
    ),
]


def test_describe_maps_every_event() -> None:
    for event, expected in CASES:
        assert describe(event) == expected, f"mauvais Report pour {event!r}"
