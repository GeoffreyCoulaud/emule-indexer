import asyncio
import datetime
import sqlite3
from pathlib import Path

import pytest

from emule_indexer.adapters.config.crawler_config import BackoffConfig, CrawlerConfig
from emule_indexer.adapters.config.local_config import AmuleEndpoint, LocalConfig
from emule_indexer.adapters.config.yaml_loader import load_yaml
from emule_indexer.composition.app import CrawlerApp, default_client_factory
from emule_indexer.domain.matching.config import MatcherConfig
from emule_indexer.domain.matching.models import TargetSegment
from emule_indexer.domain.matching.validation import parse_matcher_config
from emule_indexer.domain.observation import FileObservation
from emule_indexer.ports.mule_client import NetworkStatus
from tests.application.fakes import FakeClock, FakeMuleClient, RecordingSignal

_TARGETS = (
    TargetSegment(
        season=2,
        number=62,
        segment="A",
        title="Les demoiselles cambrioleuses",
        broadcast_date=datetime.date(2008, 9, 21),
    ),
)
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_DL_NAME = "Keroro N°062A Les demoiselles cambrioleuses.avi"


class _NoopRng:
    """Rng identité : conserve l'ordre + jitter nul (déterminisme du test)."""

    def shuffled(self, items: tuple[str, ...], seed: str) -> tuple[str, ...]:
        return items

    def jitter(self, span: float) -> float:
        return 0.0


@pytest.fixture
def matcher_config() -> MatcherConfig:
    return parse_matcher_config(load_yaml(_FIXTURES / "canonical_config.yaml"))


def _crawler_config(shutdown_deadline: float = 30.0) -> CrawlerConfig:
    return CrawlerConfig(
        cycle_interval_seconds=300.0,
        search_poll_budget_seconds=10.0,
        search_poll_interval_seconds=5.0,
        keyword_pause_min_seconds=1.0,
        keyword_pause_max_seconds=2.0,
        backoff=BackoffConfig(base_seconds=2.0, cap_seconds=60.0, factor=2.0, jitter_ratio=0.0),
        decision_poll_interval_seconds=5.0,
        shutdown_deadline_seconds=shutdown_deadline,
    )


def _local_config(tmp_path: Path, *, count: int = 1, node_id: str | None = None) -> LocalConfig:
    return LocalConfig(
        amules=tuple(
            AmuleEndpoint(name=f"amule-{i}", host="h", port=4712 + i, password="p")
            for i in range(count)
        ),
        catalog_db_path=str(tmp_path / "catalog.db"),
        local_db_path=str(tmp_path / "local.db"),
        node_id=node_id,
    )


def _make_app(
    tmp_path: Path,
    matcher_config: MatcherConfig,
    *,
    factory: object,
    clock: FakeClock | None = None,
    node_id: str | None = None,
    shutdown_deadline: float = 30.0,
) -> CrawlerApp:
    return CrawlerApp(
        crawler_config=_crawler_config(shutdown_deadline),
        local_config=_local_config(tmp_path, node_id=node_id),
        targets=_TARGETS,
        matcher_config=matcher_config,
        clock=clock or FakeClock(),
        rng=_NoopRng(),
        signal_hub=RecordingSignal(),
        client_factory=factory,  # type: ignore[arg-type]
    )


class _ShutdownOnStatusClient(FakeMuleClient):
    """Client qui déclenche l'arrêt de l'app au PREMIER relevé de statut (1 cycle puis stop)."""

    def __init__(
        self,
        app_holder: dict[str, CrawlerApp],
        results: list[tuple[FileObservation, ...]] | None = None,
    ) -> None:
        super().__init__(results=results)
        self._app_holder = app_holder
        self._fired = False

    async def network_status(self) -> NetworkStatus:
        if not self._fired:
            self._fired = True
            self._app_holder["app"]._on_signal()  # simule un SIGINT après le démarrage du cycle
        return await super().network_status()


@pytest.mark.asyncio
async def test_app_runs_one_cycle_then_shuts_down_cleanly(
    tmp_path: Path, matcher_config: MatcherConfig
) -> None:
    created: list[_ShutdownOnStatusClient] = []
    app_holder: dict[str, CrawlerApp] = {}

    def factory(endpoint: AmuleEndpoint) -> _ShutdownOnStatusClient:
        client = _ShutdownOnStatusClient(app_holder)
        created.append(client)
        return client

    app = _make_app(tmp_path, matcher_config, factory=factory)
    app_holder["app"] = app
    await asyncio.wait_for(app.run(), timeout=5.0)
    assert created and created[0].close_calls == 1  # client fermé APRÈS l'unwind
    assert (tmp_path / "catalog.db").exists()
    assert (tmp_path / "local.db").exists()


@pytest.mark.asyncio
async def test_node_id_override_is_used(tmp_path: Path, matcher_config: MatcherConfig) -> None:
    observation = FileObservation(
        ed2k_hash="31d6cfe0d16ae931b73c59d7e0c089c0",
        filename=_DL_NAME,
        size_bytes=234_000_000,
        source_count=3,
        complete_source_count=1,
        keyword="keroro",
    )
    app_holder: dict[str, CrawlerApp] = {}

    def factory(endpoint: AmuleEndpoint) -> _ShutdownOnStatusClient:
        return _ShutdownOnStatusClient(app_holder, results=[(observation,)])

    app = _make_app(tmp_path, matcher_config, factory=factory, node_id="forced-node")
    app_holder["app"] = app
    await asyncio.wait_for(app.run(), timeout=5.0)
    catalog = sqlite3.connect(tmp_path / "catalog.db")
    try:
        rows = catalog.execute("SELECT DISTINCT node_id FROM file_observations").fetchall()
    finally:
        catalog.close()
    assert rows == [("forced-node",)]


@pytest.mark.asyncio
async def test_second_signal_forces_exit(tmp_path: Path, matcher_config: MatcherConfig) -> None:
    app = _make_app(tmp_path, matcher_config, factory=lambda e: FakeMuleClient())
    app._on_signal()  # 1er signal : demande d'arrêt
    with pytest.raises(SystemExit):
        app._on_signal()  # 2e signal : escalade → SystemExit


class _ShutdownOnSleepClock(FakeClock):
    """Horloge qui déclenche l'arrêt sur le LONG sleep inter-cycle (≥ 100s), PAS sur les
    courtes pauses inter-mots-clés (1-2s) → le cycle se TERMINE, puis la boucle re-teste sa
    condition et SORT d'elle-même (sans annulation) au tour suivant."""

    def __init__(self, app_holder: dict[str, CrawlerApp]) -> None:
        super().__init__()
        self._app_holder = app_holder

    async def sleep(self, seconds: float) -> None:
        await super().sleep(seconds)
        if seconds >= 100.0:  # le sommeil inter-cycle (cycle_interval − écoulé), pas une pause
            self._app_holder["app"]._shutdown.set()


@pytest.mark.asyncio
async def test_loop_exits_cleanly_when_shutdown_set_during_sleep(
    tmp_path: Path, matcher_config: MatcherConfig
) -> None:
    # L'arrêt est posé pendant le sleep inter-cycle : la boucle re-teste sa condition et
    # SORT d'elle-même (sans annulation) → couvre la sortie normale du `while`.
    app_holder: dict[str, CrawlerApp] = {}
    clock = _ShutdownOnSleepClock(app_holder)
    app = _make_app(tmp_path, matcher_config, factory=lambda e: FakeMuleClient(), clock=clock)
    app_holder["app"] = app
    await asyncio.wait_for(app.run(), timeout=5.0)


class _BlockingClient(FakeMuleClient):
    """Client dont ``fetch_results`` BLOQUE : la boucle reste en vol → l'annulation la frappe."""

    async def fetch_results(self) -> tuple[FileObservation, ...]:
        await asyncio.Event().wait()  # ne se résout jamais : bloque jusqu'à annulation
        return ()


@pytest.mark.asyncio
async def test_signal_cancels_an_in_flight_cycle(
    tmp_path: Path, matcher_config: MatcherConfig
) -> None:
    # Un travailleur est BLOQUÉ dans fetch_results ; un SIGINT externe annule le TaskGroup →
    # couvre le chemin d'annulation (unwind propre + ligne « Travailleurs arrêtés »).
    app = _make_app(tmp_path, matcher_config, factory=lambda e: _BlockingClient())
    run_task = asyncio.create_task(app.run())
    for _ in range(20):  # laisse le cycle démarrer et bloquer dans fetch_results
        await asyncio.sleep(0)
    app._on_signal()
    await asyncio.wait_for(run_task, timeout=5.0)


def test_default_client_factory_builds_an_amule_client() -> None:
    from emule_indexer.adapters.mule_ec.client import AmuleEcClient

    endpoint = AmuleEndpoint(name="amule-1", host="gluetun", port=4712, password="secret")
    assert isinstance(default_client_factory(endpoint), AmuleEcClient)


class _SlowCloseClient(_ShutdownOnStatusClient):
    """Client dont ``close`` traîne au-delà du délai d'arrêt → la borne le coupe."""

    async def close(self) -> None:
        await asyncio.sleep(10.0)  # > shutdown_deadline (réel) → TimeoutError


@pytest.mark.asyncio
async def test_shutdown_deadline_forces_exit(tmp_path: Path, matcher_config: MatcherConfig) -> None:
    # Fermeture qui traîne + délai d'arrêt minuscule → la borne lève TimeoutError (spec §6 :
    # l'app ne peut PAS paraître bloquée).
    app_holder: dict[str, CrawlerApp] = {}

    def factory(endpoint: AmuleEndpoint) -> _SlowCloseClient:
        return _SlowCloseClient(app_holder)

    app = _make_app(tmp_path, matcher_config, factory=factory, shutdown_deadline=0.05)
    app_holder["app"] = app
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(app.run(), timeout=5.0)


@pytest.mark.asyncio
async def test_observations_are_catalogued_during_the_cycle(
    tmp_path: Path, matcher_config: MatcherConfig
) -> None:
    observation = FileObservation(
        ed2k_hash="31d6cfe0d16ae931b73c59d7e0c089c0",
        filename=_DL_NAME,
        size_bytes=234_000_000,
        source_count=3,
        complete_source_count=1,
        keyword="keroro",
    )
    app_holder: dict[str, CrawlerApp] = {}

    def factory(endpoint: AmuleEndpoint) -> _ShutdownOnStatusClient:
        return _ShutdownOnStatusClient(app_holder, results=[(observation,)])

    app = _make_app(tmp_path, matcher_config, factory=factory)
    app_holder["app"] = app
    await asyncio.wait_for(app.run(), timeout=5.0)
    catalog = sqlite3.connect(tmp_path / "catalog.db")
    try:
        count = catalog.execute("SELECT count(*) FROM match_decisions").fetchone()[0]
    finally:
        catalog.close()
    assert count == 1
