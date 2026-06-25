"""Dérivation pure du statut de couverture d'une cible (spec webui §5). Aucun I/O.

L'ordre des paliers vient de ``catalog_matching.config.TIER_RANK`` (source de vérité partagée
avec l'engine de matching). Sans cette mutualisation, le webui réinventait sa propre table
divergente — un 4ᵉ palier ou un renommage aurait silencieusement faussé la coverage.
"""

from collections.abc import Sequence

from catalog_matching.config import TIER_RANK
from catalog_webui.domain.views import CoverageStatus


def coverage_for(target_id: str, decisions: Sequence[tuple[str, str]]) -> CoverageStatus:
    """``decisions`` = ``(ed2k_hash, tier)`` des derniers verdicts pour cette cible."""
    if not decisions:
        return CoverageStatus(status="none", best_tier=None, file_count=0)
    # TIER_RANK : entier croissant = palier plus fort (download > notify > catalog) ; un tier
    # inconnu retombe sur ``-1`` (sous le plus faible) — neutre vis-à-vis du choix.
    best = max(decisions, key=lambda d: TIER_RANK.get(d[1], -1))[1]
    status = "found" if best == "download" else "partial"
    return CoverageStatus(status=status, best_tier=best, file_count=len(decisions))
