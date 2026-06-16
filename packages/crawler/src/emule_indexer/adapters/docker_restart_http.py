"""Adapter ``HttpMuleRestarter`` : restart amuled via le docker-socket-proxy (port-sync §5.3).

``POST {proxy}/v1.43/containers/amuled/restart`` au proxy à surface minimale (wollomatic :
l'allowlist n'autorise QUE ce chemin+méthode ; le crawler ne voit JAMAIS le socket Docker). Docker
renvoie **204 No Content** sur un restart réussi → tout 2xx = succès ; ≠2xx / timeout / connect
error → ``RestarterError`` (la boucle l'absorbe en alerte + backoff). PAS de retry interne (le
cycle suivant ré-essaiera, sous rate-limit). ``aclose`` ferme le client httpx (composition à
l'arrêt).
"""

import logging

import httpx

from emule_indexer.ports.mule_restarter import RestarterError

_logger = logging.getLogger("emule_indexer.adapters.docker_restart_http")

# Chemin Docker Engine API du restart d'amuled : c'est EXACTEMENT ce que l'allowlist du proxy
# autorise (regex ``/v1\..{1,2}/containers/amuled/restart`` côté wollomatic). v1.43 = API stable.
_DEFAULT_RESTART_PATH = "/v1.43/containers/amuled/restart"


class HttpMuleRestarter:
    """Implémentation httpx du port ``MuleRestarter`` (satisfaction STRUCTURELLE)."""

    def __init__(
        self, client: httpx.AsyncClient, *, restart_path: str = _DEFAULT_RESTART_PATH
    ) -> None:
        self._client = client
        self._restart_path = restart_path

    async def restart(self) -> None:
        """``POST`` le restart au proxy ; 2xx → succès ; sinon ``RestarterError`` (absorbé)."""
        try:
            response = await self._client.post(self._restart_path)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RestarterError(
                f"proxy de restart a répondu {error.response.status_code}"
            ) from error
        except httpx.HTTPError as error:
            raise RestarterError(f"proxy de restart injoignable ({error})") from error
        _logger.info("restart d'amuled demandé (status %d)", response.status_code)

    async def aclose(self) -> None:
        """Ferme le client httpx (appelé par la composition à l'arrêt)."""
        await self._client.aclose()
