"""Adapter ``GluetunPortReader`` : lit le port forwardé vivant de gluetun (port-sync, design §3.2).

``GET {base}/v1/portforward`` → ``{"port": N}`` (route confirmée via la doc gluetun upstream).
PARSING DÉFENSIF (DÉCISION 7) — TOUT échec → ``None`` (« pas prêt »), JAMAIS d'exception qui
remonte : le mode dégradé (Low-ID) est toléré (control-server injoignable, PF pas encore négocié,
corps malformé). Miroir EXACT du parsing défensif de ``HttpContentVerifier``.

Auth : sur le réseau interne ``ec``, l'auth du control-server gluetun est désactivée
(``HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE='{"auth":"none"}'``, DÉCISION D3) → aucun en-tête à
poser. Pour durcir un jour, c'est un en-tête (``X-API-Key``/``Authorization``) à ajouter ICI,
boucle inchangée. ``aclose`` ferme le client httpx (appelé par la composition à l'arrêt).
"""

import json
import logging

import httpx

_logger = logging.getLogger("emule_indexer.adapters.gluetun_port")


class GluetunPortReader:
    """Implémentation httpx du port ``PortForwardingReader`` (satisfaction STRUCTURELLE)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def forwarded_port(self) -> int | None:
        """``GET /v1/portforward`` ; ``int > 0`` si le PF est vivant, sinon ``None`` (défensif)."""
        try:
            response = await self._client.get("/v1/portforward")
            response.raise_for_status()
        except httpx.HTTPError as error:
            # control-server injoignable / timeout / 4xx / 5xx → « pas prêt » (Low-ID toléré).
            _logger.debug("gluetun control-server indisponible (%s) — port forwardé inconnu", error)
            return None
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> int | None:
        """Parse défensif d'un 200 : un ``port`` entier > 0, sinon ``None`` (jamais d'exception)."""
        try:
            payload = json.loads(response.content)
        except (json.JSONDecodeError, ValueError):
            _logger.debug("réponse /v1/portforward non-JSON — port forwardé inconnu")
            return None
        if not isinstance(payload, dict):
            return None
        port = payload.get("port")
        # bool est un sous-type d'int : exclu explicitement (True ne doit pas valoir un port).
        if not isinstance(port, int) or isinstance(port, bool) or port <= 0:
            return None
        return port

    async def aclose(self) -> None:
        """Ferme le client httpx (appelé par la composition à l'arrêt)."""
        await self._client.aclose()
