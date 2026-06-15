"""Ports d'observabilité (spec Plan E §3). ``Telemetry`` (façade émise par l'application) +
sinks ``MetricsSink``/``Notifier`` (branchés dans le dispatcher). Protocols structurels —
les adapters réels ET les fakes de test les satisfont sans héritage. Stubs sur UNE ligne."""

from typing import Protocol, runtime_checkable

from emule_indexer.domain.observability.events import Event
from emule_indexer.domain.observability.policy import Audience, MetricInstruction, Severity


@runtime_checkable
class MetricsSink(Protocol):
    def apply(self, instruction: MetricInstruction) -> None: ...


@runtime_checkable
class Notifier(Protocol):
    async def notify(self, audience: Audience, body: str, severity: Severity) -> None: ...


@runtime_checkable
class Telemetry(Protocol):
    async def emit(self, event: Event) -> None: ...
