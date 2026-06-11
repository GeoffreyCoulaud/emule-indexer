"""Port ``MuleClient`` : ce que le crawler attend d'un client eMule (cf. spec EC-adapter §4).

Le port n'importe QUE le domaine. Les stubs du Protocol tiennent sur UNE ligne (le ``def``
s'exécute à la création de la classe : couvert). La convenance ``search_and_wait`` (poll +
timeout) vit dans l'outil probe, PAS ici : le polling appartient à l'appelant (spec §3).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from emule_indexer.domain.observation import FileObservation


class SearchChannel(StrEnum):
    """Canal de recherche (enum fermé, spec §4) : serveurs eD2k ou Kad."""

    GLOBAL = "global"
    KAD = "kad"


class KadStatus(StrEnum):
    """État Kad (enum fermé), décodé du bitfield CONNSTATE (réf. protocole §6)."""

    OFF = "off"
    RUNNING = "running"
    CONNECTED = "connected"
    FIREWALLED = "firewalled"


@dataclass(frozen=True)
class NetworkStatus:
    """Statut réseau (spec §4) — exactement ce que les métriques (§13 MVP) consommeront.

    ``ed2k_id`` est ``None`` quand le client n'est pas connecté à un serveur eD2k.
    ``ed2k_high`` : LowID si l'ID < 16777216 (HIGHEST_LOWID_ED2K_KAD, réf. §6).
    """

    ed2k_id: int | None
    ed2k_high: bool
    kad_status: KadStatus
    server_name: str | None = None
    server_addr: str | None = None


class MuleClient(Protocol):
    """Contrat async du client eMule. Actions UNITAIRES : aucun sleep/retry/boucle ici.

    ``fetch_results`` retourne le snapshot CUMULATIF accumulé par le daemon (réf. §5) ;
    ``search_progress`` retourne un pourcentage si EC l'expose, sinon ``None``.
    """

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def start_search(self, keyword: str, channel: SearchChannel) -> None: ...

    async def fetch_results(self) -> tuple[FileObservation, ...]: ...

    async def stop_search(self) -> None: ...

    async def search_progress(self) -> int | None: ...

    async def network_status(self) -> NetworkStatus: ...
