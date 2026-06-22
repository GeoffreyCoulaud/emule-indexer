"""Dérivation pure du statut de couverture d'une cible (spec webui §5). Aucun I/O."""

from collections.abc import Sequence

from catalog_webui.domain.views import CoverageStatus

# Du plus fort au plus faible (cf. config/crawler/matcher.yaml).
_TIER_RANK = {"download": 3, "notify": 2, "catalog": 1}


def coverage_for(target_id: str, decisions: Sequence[tuple[str, str]]) -> CoverageStatus:
    """``decisions`` = ``(ed2k_hash, tier)`` des derniers verdicts pour cette cible."""
    if not decisions:
        return CoverageStatus(status="none", best_tier=None, file_count=0)
    best = max(decisions, key=lambda d: _TIER_RANK.get(d[1], 0))[1]
    status = "found" if best == "download" else "partial"
    return CoverageStatus(status=status, best_tier=best, file_count=len(decisions))
