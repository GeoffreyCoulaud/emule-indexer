from emule_indexer.domain.matching.config import TIERS
from emule_indexer.domain.matching.engine import _TIER_RANK


def test_tier_rank_orders_download_above_notify_above_catalog() -> None:
    assert _TIER_RANK["download"] > _TIER_RANK["notify"]
    assert _TIER_RANK["notify"] > _TIER_RANK["catalog"]


def test_tier_rank_catalog_is_lowest() -> None:
    assert _TIER_RANK["catalog"] < _TIER_RANK["download"]
    assert _TIER_RANK["catalog"] < _TIER_RANK["notify"]


def test_tier_rank_covers_exactly_the_valid_tiers() -> None:
    # Cohérence : tout palier licite (TIERS) a un rang, et aucun rang orphelin.
    assert set(_TIER_RANK) == TIERS
