"""Les événements sont des dataclasses gelées à champs métier — test de construction/gel."""

import dataclasses

import pytest

from emule_indexer.domain.observability.events import (
    ObservationRecorded,
    VerificationCompleted,
)


def test_observation_recorded_carries_network() -> None:
    event = ObservationRecorded(network="ed2k")
    assert event.network == "ed2k"


def test_event_is_frozen() -> None:
    event = VerificationCompleted(target_id="S2E062A", verdict="clean")
    # Passer l'attribut via une variable pour éviter ruff B010 tout en
    # déclenchant FrozenInstanceError au runtime (frozen=True).
    attr = "verdict"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(event, attr, "malicious")
