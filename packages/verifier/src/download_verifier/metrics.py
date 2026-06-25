"""Métriques techniques du verifier (E-D10). Pas d'événements/notifications (crawler-only) :

- ``emule_verifier_requests{verdict}`` : compteur historique des verdicts métier rendus par
  ``/verify`` (clean/suspicious/malicious/error).
- ``emule_verifier_child_outcome{outcome}`` (observability#2) : cause TECHNIQUE de l'issue du
  child (ok/timeout/nonzero_exit/egress_overflow/malformed) — orthogonale au verdict, permet
  en incident de masse d'identifier la cause derrière une montée de ``suspicious``.
- ``emule_verifier_responses{status}`` (observability#3) : compteur de réponses HTTP par code
  (200/400/500) — couvre les 400 (validation) et 500 (exceptions) qu'``observe`` ne voyait pas.
- ``emule_verifier_analysis_duration_seconds`` : histogramme de durée d'analyse.

Counter SANS ``_total`` (ajouté par prometheus_client à l'exposition).
"""

from prometheus_client import CollectorRegistry, Counter, Histogram


class VerifierMetrics:
    """Registre + compteurs verdict / child_outcome / responses + histogramme de durée."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self._requests = Counter(
            "emule_verifier_requests",
            "Requêtes /verify traitées",
            ["verdict"],
            registry=self.registry,
        )
        self._child_outcome = Counter(
            "emule_verifier_child_outcome",
            "Cause technique de l'issue du child d'analyse",
            ["outcome"],
            registry=self.registry,
        )
        self._responses = Counter(
            "emule_verifier_responses",
            "Réponses HTTP du verifier",
            ["status"],
            registry=self.registry,
        )
        self._duration = Histogram(
            "emule_verifier_analysis_duration_seconds",
            "Durée d'analyse d'un fichier (s)",
            registry=self.registry,
        )

    def observe(self, verdict: str, seconds: float) -> None:
        """Compte une requête (par verdict) et observe sa durée d'analyse."""
        self._requests.labels(verdict=verdict).inc()
        self._duration.observe(seconds)

    def observe_child_outcome(self, outcome: str) -> None:
        """Compte la cause TECHNIQUE de l'issue du child (observability#2)."""
        self._child_outcome.labels(outcome=outcome).inc()

    def observe_response(self, status: int) -> None:
        """Compte une réponse HTTP par code de statut (observability#3)."""
        self._responses.labels(status=str(status)).inc()
