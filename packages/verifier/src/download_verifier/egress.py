"""Contrat d'égress de l'enfant (spec analysis §4/§6 — DA6) : parse DÉFENSIF côté parent.

``parse`` mappe l'issue de l'enfant en ``(verdict, real_meta, checks)`` de façon TOUJOURS
déterministe (jamais d'exception remontée — le service répond 200, §6). Un enfant qui timeout,
sort en erreur, dépasse le cap d'octets, ou rend un égress illisible/hors-schéma est un signal de
POISON → ``suspicious``. Schéma strict : objet ``{verdict ∈ {clean,suspicious,malicious}: str,
real_meta: obj, checks: list}``. Tout écart → ``suspicious``.
"""

import json

from download_verifier.checks.base import STATUS_RANK
from download_verifier.config import AnalysisConfig

_VALID_VERDICTS = frozenset(STATUS_RANK)


def _poison() -> tuple[str, dict[str, object], list[object]]:
    """Verdict de poison déterministe (valeurs NEUVES → pas de mutation partagée)."""
    return "suspicious", {}, []


def parse(
    stdout: bytes, returncode: int, timed_out: bool, cfg: AnalysisConfig
) -> tuple[str, dict[str, object], list[object]]:
    """Mappe l'égress enfant en ``(verdict, real_meta, checks)`` (jamais d'exception)."""
    if timed_out or returncode != 0 or len(stdout) > cfg.egress_cap_bytes:
        return _poison()
    try:
        payload = json.loads(stdout)
    # RecursionError = défense en profondeur (cf. app.py §8) ; pas de test dédié car json.loads
    # (impl C) ne récurse pas en CPython 3.12 — la branche except est couverte par les cas non-JSON.
    except (json.JSONDecodeError, ValueError, RecursionError):
        return _poison()
    if not isinstance(payload, dict):
        return _poison()
    verdict = payload.get("verdict")
    real_meta = payload.get("real_meta")
    checks = payload.get("checks")
    if not isinstance(verdict, str) or verdict not in _VALID_VERDICTS:
        return _poison()
    if not isinstance(real_meta, dict) or not isinstance(checks, list):
        return _poison()
    return verdict, real_meta, checks
