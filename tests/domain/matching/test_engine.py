import dataclasses

import pytest

from emule_indexer.domain.matching.config import TIERS
from emule_indexer.domain.matching.engine import _TIER_RANK, Explanation, MatchDecision


def test_tier_rank_orders_download_above_notify_above_catalog() -> None:
    assert _TIER_RANK["download"] > _TIER_RANK["notify"]
    assert _TIER_RANK["notify"] > _TIER_RANK["catalog"]


def test_tier_rank_catalog_is_lowest() -> None:
    assert _TIER_RANK["catalog"] < _TIER_RANK["download"]
    assert _TIER_RANK["catalog"] < _TIER_RANK["notify"]


def test_tier_rank_covers_exactly_the_valid_tiers() -> None:
    # Cohérence : tout palier licite (TIERS) a un rang, et aucun rang orphelin.
    assert set(_TIER_RANK) == TIERS


def test_explanation_is_frozen_and_holds_fields() -> None:
    explanation = Explanation(
        target_id="S2E062A",
        rules_fired=("id_segment_exact", "keroro_large"),
        tokens_matched=("is_video", "keroro", "segment_id"),
        coverage_values=(("title_hit", 1.0),),
    )
    assert explanation.target_id == "S2E062A"
    assert explanation.rules_fired == ("id_segment_exact", "keroro_large")
    assert explanation.tokens_matched == ("is_video", "keroro", "segment_id")
    assert explanation.coverage_values == (("title_hit", 1.0),)
    with pytest.raises(dataclasses.FrozenInstanceError):
        explanation.target_id = "S2E062B"  # type: ignore[misc]


def test_match_decision_is_frozen_and_holds_persisted_columns_plus_explanation() -> None:
    explanation = Explanation(
        target_id="S2E062A",
        rules_fired=("id_segment_exact",),
        tokens_matched=("keroro",),
        coverage_values=(),
    )
    decision = MatchDecision(
        target_id="S2E062A",
        rule_name="id_segment_exact",
        tier="download",
        explanation=explanation,
    )
    # Les trois colonnes que match_decisions persistera (spec §11).
    assert decision.target_id == "S2E062A"
    assert decision.rule_name == "id_segment_exact"
    assert decision.tier == "download"
    assert decision.explanation is explanation
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.tier = "notify"  # type: ignore[misc]
