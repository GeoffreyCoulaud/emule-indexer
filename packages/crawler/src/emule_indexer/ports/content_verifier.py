"""Port ``ContentVerifier`` : la vérification d'un fichier en quarantaine (spec verify §5).

Protocol ASYNC (l'adapter fait un RPC HTTP). ``verify`` rend un ``VerificationResult`` (DTO
frozen) ; ``health`` un booléen (vivacité, pour le gate full-mode au démarrage, §7). Le port
n'importe RIEN du verifier (frontière de paquet, DÉCISION DV4) : le DTO ``VerificationResult``
est défini ICI, indépendamment de la forme de résultat du service ; le contrat de fil JSON les
garde en phase (test de contrat + e2e). Le stub ``health`` tient sur UNE ligne ; ``verify``
est WRAPPÉ (signature > 100 cols sur une ligne → ruff E501) mais GARDE le ``: ...`` final sur
la ligne du ``->`` (idiome de couverture : le ``def`` s'exécute à la création de la classe).

``verify`` ne LÈVE pas pour une mauvaise réponse déterministe (→ ``VerificationResult(verdict=
"error")``, enregistré) ; il LÈVE ``VerifierUnavailableError`` (``ports/verifier_errors``)
seulement quand le service est injoignable (transitoire → retry), DÉCISION DV6.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VerificationResult:
    """Résultat d'une vérification (DTO de port, spec §5).

    ``verdict`` : chaîne (en NO-OP : ``unverified``/``error`` ; D-analysis ajoutera ``clean``/
    ``suspicious``/``malicious``). ``real_meta`` : métadonnées média extraites (vide en NO-OP).
    ``checks`` : trace des checks exécutés (vide en NO-OP). Gelé → comparaison par valeur en test.
    Ces trois champs sont EXACTEMENT les colonnes que ``file_verifications`` persiste (verdict/
    real_meta/checks) — ``verified_at``/``node_id`` sont stampés par l'adapter (pas le domaine).
    """

    verdict: str
    real_meta: Mapping[str, object]
    checks: tuple[object, ...]


class ContentVerifier(Protocol):
    """Contrat async de vérification (spec §5). ``verify`` RPC ; ``health`` vivacité (gate §7)."""

    async def verify(
        self, ed2k_hash: str, expected: Mapping[str, object]
    ) -> VerificationResult: ...

    async def health(self) -> bool: ...
