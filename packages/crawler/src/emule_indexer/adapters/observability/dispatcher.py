"""Dispatcher d'observabilité : route un ``Event`` vers log + métriques + notifs (E-D3/E-D13).

Couche ADAPTER. Implémente ``Telemetry``. ``emit`` : ``describe`` (pur) → log au niveau mappé +
``MetricsSink.apply`` pour chaque métrique + ``Notifier.notify`` par audience, chaque notif sous
``asyncio.wait_for(timeout)`` avec échec/timeout ABSORBÉ + loggé (un canal en panne ne casse
JAMAIS le crawl, E-D13). Aucun état (l'edge-trigger vit dans l'application — E-D8)."""

import asyncio
import logging

from emule_indexer.domain.observability.events import Event
from emule_indexer.domain.observability.policy import Severity, describe
from emule_indexer.ports.telemetry import MetricsSink, Notifier

_logger = logging.getLogger("emule_indexer.observability")

_LEVELS: dict[Severity, int] = {
    Severity.DEBUG: logging.DEBUG,
    Severity.INFO: logging.INFO,
    Severity.WARNING: logging.WARNING,
    Severity.ERROR: logging.ERROR,
}


class ObservabilityDispatcher:
    """Adapter ``Telemetry`` : un point d'émission, trois sorties (log/métrique/notif)."""

    def __init__(
        self, *, metrics: MetricsSink, notifier: Notifier, notify_timeout_seconds: float
    ) -> None:
        self._metrics = metrics
        self._notifier = notifier
        self._timeout = notify_timeout_seconds

    async def emit(self, event: Event) -> None:
        report = describe(event)
        _logger.log(_LEVELS[report.severity], report.message)
        for instruction in report.metrics:
            self._metrics.apply(instruction)
        for audience in report.audiences:
            try:
                await asyncio.wait_for(
                    self._notifier.notify(audience, report.message, report.severity),
                    timeout=self._timeout,
                )
            except Exception as error:  # noqa: BLE001 — une notif ne casse JAMAIS le crawl (E-D13)
                _logger.warning("notification %s échouée (%s)", audience.value, error)
