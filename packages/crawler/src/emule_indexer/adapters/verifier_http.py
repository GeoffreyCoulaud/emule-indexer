"""Adapter ``HttpContentVerifier`` : RPC HTTP vers le service verifier (spec verify §5/§8).

httpx ``AsyncClient`` sur l'URL du verifier. ``verify`` ``POST /verify {hash, expected}`` ;
``health`` ``GET /health``. PARSING DÉFENSIF (DÉCISION DV6) — deux familles d'échec :
  - service INJOIGNABLE (connexion refusée / timeout / réseau / 5xx) → TRANSITOIRE :
    ``VerifierUnavailableError`` (la boucle ``fail_verification`` → retry via lease) ;
  - réponse 200 MALFORMÉE / hors-schéma / trop grosse → DÉTERMINISTE : on rend un
    ``VerificationResult(verdict="error")`` (enregistré + ``complete`` — pas de boucle infinie).
Le contrat d'erreur transitoire vit dans le PORT (``ports/verifier_errors``) — l'adapter en
hérite/le lève, l'application l'attrape sans importer cet adapter (règle de dépendance §4).

``aclose`` ferme le client httpx (appelé par la composition à l'arrêt). Le DTO crawler est
``ports.content_verifier.VerificationResult`` — défini indépendamment de la réponse du verifier
(frontière de paquet) ; ce module PROUVE le contrat de fil par son test contre la vraie app.
"""

import json
import logging
from collections.abc import Mapping

import httpx

from emule_indexer.ports.content_verifier import VerificationResult
from emule_indexer.ports.verifier_errors import VerifierUnavailableError

_logger = logging.getLogger("emule_indexer.adapters.verifier_http")

# Plafond de SANITÉ/schéma sur une réponse DÉJÀ reçue : un /verify NO-OP rend un corps minuscule,
# donc un corps hors-norme est forcément anormal → ``verdict="error"`` (parsing défensif, §8).
# Ce N'EST PAS une défense mémoire/DoS : ``_parse`` lit ``response.content``, qui matérialise tout
# le corps en mémoire AVANT le check de taille (httpx bufferise la réponse à la réception). Un vrai
# bound en flux (lecture cappée en streaming) relève du durcissement de déploiement (Plan F).
_DEFAULT_MAX_RESPONSE_BYTES = 65536

_ERROR_RESULT = VerificationResult(verdict="error", real_meta={}, checks=())


class HttpContentVerifier:
    """Implémentation httpx du port ``ContentVerifier`` (satisfaction STRUCTURELLE)."""

    def __init__(
        self, client: httpx.AsyncClient, *, max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES
    ) -> None:
        self._client = client
        self._max_response_bytes = max_response_bytes

    async def verify(self, ed2k_hash: str, expected: Mapping[str, object]) -> VerificationResult:
        """``POST /verify`` ; injoignable→``VerifierUnavailableError`` ; mauvaise réponse→error."""
        try:
            response = await self._client.post(
                "/verify", json={"hash": ed2k_hash, "expected": dict(expected)}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            # 4xx/5xx : un 5xx est transitoire ; un 4xx (notre payload rejeté) est un bug de
            # contrat — dans les deux cas on ne fabrique pas de verdict, on remonte transitoire
            # (le 4xx ne se résoudra pas au retry mais finira en dead_letter, visible, §8).
            raise VerifierUnavailableError(
                f"verifier a répondu {error.response.status_code}"
            ) from error
        except httpx.HTTPError as error:
            raise VerifierUnavailableError(f"verifier injoignable ({error})") from error
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> VerificationResult:
        """Parse défensif d'un 200 : malformé/hors-schéma/trop gros → verdict ``error``."""
        body = response.content
        if len(body) > self._max_response_bytes:
            _logger.warning("réponse verifier trop volumineuse (%d o) — verdict error", len(body))
            return _ERROR_RESULT
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            _logger.warning("réponse verifier non-JSON — verdict error")
            return _ERROR_RESULT
        if not isinstance(payload, dict):
            return _ERROR_RESULT
        verdict = payload.get("verdict")
        if not isinstance(verdict, str):
            return _ERROR_RESULT
        real_meta = payload.get("real_meta", {})
        checks = payload.get("checks", [])
        if not isinstance(real_meta, dict) or not isinstance(checks, list):
            return _ERROR_RESULT
        return VerificationResult(verdict=verdict, real_meta=real_meta, checks=tuple(checks))

    async def health(self) -> bool:
        """``GET /health`` ; ``True`` ssi 2xx, ``False`` sur tout échec (gate full-mode, §7)."""
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
        except httpx.HTTPError:
            return False
        return True

    async def aclose(self) -> None:
        """Ferme le client httpx (appelé par la composition à l'arrêt)."""
        await self._client.aclose()
