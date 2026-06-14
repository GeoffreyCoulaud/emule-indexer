import dataclasses

import pytest

from download_verifier.checks.base import (
    STATUS_RANK,
    CheckOutcome,
    worst_status,
)


def test_status_rank_orders_clean_below_suspicious_below_malicious() -> None:
    assert STATUS_RANK["clean"] < STATUS_RANK["suspicious"] < STATUS_RANK["malicious"]


def test_check_outcome_is_frozen() -> None:
    outcome = CheckOutcome(name="type_sniff", status="clean", meta={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.status = "malicious"  # type: ignore[misc]


def test_check_outcome_carries_name_status_meta() -> None:
    outcome = CheckOutcome(name="ffprobe", status="suspicious", meta={"container": "mkv"})
    assert outcome.name == "ffprobe"
    assert outcome.status == "suspicious"
    assert outcome.meta == {"container": "mkv"}


def test_worst_status_all_clean_is_clean() -> None:
    assert worst_status(["clean", "clean"]) == "clean"


def test_worst_status_picks_suspicious_over_clean() -> None:
    assert worst_status(["clean", "suspicious", "clean"]) == "suspicious"


def test_worst_status_picks_malicious_over_all() -> None:
    assert worst_status(["clean", "suspicious", "malicious"]) == "malicious"


def test_worst_status_empty_is_clean() -> None:
    assert worst_status([]) == "clean"
