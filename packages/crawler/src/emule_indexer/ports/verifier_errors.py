"""Contrat d'erreur du verifier (spec verify §5/§8 — DÉCISION DV6).

Couche PORTS : le CONTRAT d'erreur transitoire que la boucle de vérification attrape vit au
niveau du port, JAMAIS d'un adapter (règle de dépendance §4, motif ``MuleUnreachableError``).
L'adapter http (``HttpContentVerifier``) LÈVE ``VerifierUnavailableError`` quand le service est
injoignable (connexion refusée / timeout / 5xx) — une panne TRANSITOIRE : la boucle
``fail_verification`` (lease → retry), n'invente AUCUN verdict. Une réponse 200 simplement
malformée n'est PAS transitoire → l'adapter rend un ``VerificationResult(verdict="error")``.
"""


class VerifierUnavailableError(Exception):
    """Le service verifier est injoignable (transitoire) → retry par la boucle (spec §8)."""
