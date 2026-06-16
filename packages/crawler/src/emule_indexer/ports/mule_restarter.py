"""Port ``MuleRestarter`` : redémarre le conteneur amuled (port-sync High-ID, design §4.1/§5).

Couche PORTS. amuled ne re-bind PAS son port d'écoute à chaud (socket créé une seule fois au
boot) : après un ``set_listen_port`` EC, il faut RESTARTER le conteneur pour qu'il re-bind le
nouveau port. Le restart passe par un docker-socket-proxy à surface minimale (le crawler ne voit
JAMAIS le socket Docker). ``RestarterError`` (le proxy refuse/échoue) est ABSORBÉE par la boucle
(jamais fatale → alerte edge-triggered + backoff). Stub sur UNE ligne (le ``def`` compte couvert).
"""

from typing import Protocol


class RestarterError(Exception):
    """Le restart du conteneur amuled a échoué (proxy injoignable / ≠2xx) → absorbé par la boucle.

    La boucle l'attrape sans importer cet adapter (règle de dépendance §4) : alerte + backoff.
    """


class MuleRestarter(Protocol):
    async def restart(self) -> None: ...
