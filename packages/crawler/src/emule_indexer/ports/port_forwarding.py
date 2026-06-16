"""Port ``PortForwardingReader`` : le port forwardé VIVANT du VPN (port-sync, design §3.1).

Couche PORTS. Le crawler lit le port forwardé négocié par gluetun (NAT-PMP) pour aligner le
port d'écoute d'amuled dessus (High-ID). ``int > 0`` = port vivant ; ``None`` = « pas prêt »
(port 0 / JSON malformé / control-server injoignable) — parsing DÉFENSIF dans l'adapter, JAMAIS
d'exception : le mode dégradé (Low-ID) est toléré. Stub sur UNE ligne (le ``def`` compte couvert).
"""

from typing import Protocol


class PortForwardingReader(Protocol):
    async def forwarded_port(self) -> int | None: ...
