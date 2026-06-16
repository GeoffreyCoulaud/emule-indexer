"""Intégration get/set du port d'écoute contre un amuled RÉEL (port-sync High-ID, design §2/§4.2).

Run dédié : uv run pytest -m ec_integration --no-cov

Valide EMPIRIQUEMENT contre le vrai daemon les points figés par la lecture de la source amont :
  - **R3** : la RÉPONSE de ``GET_PREFERENCES`` porte-t-elle bien l'opcode ``EC_OP_SET_PREFERENCES``
    (0x40, PAS 0x3F) ? Si ``get_listen_port()`` rend une valeur, c'est confirmé (le client attend
    0x40 ; un mauvais ``expected`` lèverait ``EcProtocolError``). Sinon, ajuster l'``expected``.
  - **R4** : ``EC_DETAIL_CMD`` (implicite, on n'émet PAS de tag de détail) suffit-il à récupérer
    ``EC_TAG_CONN_TCP_PORT`` ? Si la lecture réussit, oui.
  - le ROUND-TRIP set→get : ``set_listen_port(N)`` puis ``get_listen_port()`` rend ``N`` (la pref
    est mise à jour EN MÉMOIRE ; le re-bind effectif exige un restart, non testé ici).

NOTE : le restart réel + le High-ID réel sont couverts par la suite e2e couche B (WT-e2e), hors
de ce fichier (pas de proxy Docker ici).
"""

from collections.abc import Iterator

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from emule_indexer.adapters.mule_ec.client import AmuleEcClient

pytestmark = pytest.mark.ec_integration

_EC_PASSWORD = "indexer-ec-test"
_IMAGE = "ngosang/amule:3.0.0-1"  # DÉCISION 10 : image Docker Hub ngosang/docker-amule


@pytest.fixture(scope="module")
def amuled() -> Iterator[tuple[str, int]]:
    ready = LogMessageWaitStrategy(r"listening on 0\.0\.0\.0:4712").with_startup_timeout(180)
    container = (
        DockerContainer(_IMAGE)
        .with_env("GUI_PWD", _EC_PASSWORD)
        .with_exposed_ports(4712)
        .waiting_for(ready)
    )
    try:
        container.start()
        yield container.get_container_host_ip(), int(container.get_exposed_port(4712))
    finally:
        container.stop()


@pytest.mark.asyncio
async def test_real_get_listen_port_reads_a_plausible_port(amuled: tuple[str, int]) -> None:
    # R3 + R4 : si get_listen_port rend une valeur, l'opcode de réponse (0x40) ET le detail level
    # (CMD implicite) sont CONFIRMÉS contre le vrai daemon. Le port par défaut de l'image est 4662.
    host, port = amuled
    client = AmuleEcClient(host, port, _EC_PASSWORD, timeout=30.0)
    await client.connect()
    try:
        listen_port = await client.get_listen_port()
        assert 0 < listen_port < 65536  # un port d'écoute plausible (défaut image : 4662)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_real_set_then_get_round_trips_the_port(amuled: tuple[str, int]) -> None:
    # set_listen_port(N) met à jour la pref EN MÉMOIRE ; un get ultérieur doit rendre N (preuve que
    # SET_PREFERENCES → Apply() a bien posé EC_TAG_CONN_TCP_PORT). Le re-bind effectif (socket)
    # exige un restart — NON testé ici (couvert par l'e2e couche B).
    host, port = amuled
    client = AmuleEcClient(host, port, _EC_PASSWORD, timeout=30.0)
    await client.connect()
    try:
        original = await client.get_listen_port()
        target = 51820 if original != 51820 else 51821
        await client.set_listen_port(target)
        assert await client.get_listen_port() == target
        # courtoisie : on restaure le port d'origine (la pref est persistée par amuled).
        await client.set_listen_port(original)
    finally:
        await client.close()
