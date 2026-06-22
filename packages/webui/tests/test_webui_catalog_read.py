"""Tests TDD pour CatalogReader — couverture, explorateur filtré, détail (spec W-D6 / §6)."""

import sqlite3
from pathlib import Path

import pytest

from catalog_webui.adapters.catalog_read import CatalogReader
from catalog_webui.adapters.db import open_ro

# ---------------------------------------------------------------------------
# Helpers de seed
# ---------------------------------------------------------------------------


def _seed(db: Path) -> None:
    """Peuple la base avec un fichier, une observation, une décision."""
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO files (ed2k_hash, size_bytes) VALUES (?, ?)",
            ("a" * 32, 100),
        )
        conn.execute(
            "INSERT INTO file_observations"
            " (ed2k_hash, filename, size_bytes, source_count,"
            " complete_source_count, raw_meta, keyword, observed_at, node_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "a" * 32,
                "keroro_062.avi",
                100,
                5,
                2,
                "[]",
                "keroro",
                "2026-06-22T10:00:00.000000+00:00",
                "n1",
            ),
        )
        conn.execute(
            "INSERT INTO match_decisions"
            " (ed2k_hash, target_id, rule_name, tier, decided_at, node_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                "a" * 32,
                "S2E062A",
                "id_segment_exact",
                "download",
                "2026-06-22T10:00:01.000000+00:00",
                "n1",
            ),
        )
        conn.commit()


def _seed_with_verdict(db: Path) -> None:
    """Ajoute un verdict de vérification au fichier seedé."""
    _seed(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO file_verifications"
            " (ed2k_hash, verdict, real_meta, checks, verified_at, node_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                "a" * 32,
                "ok",
                None,
                None,
                "2026-06-22T11:00:00.000000+00:00",
                "n1",
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Tests : couverture
# ---------------------------------------------------------------------------


def test_target_coverage_groups_by_target(catalog_db: Path) -> None:
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    coverage = reader.target_coverage()
    assert coverage["S2E062A"] == [("a" * 32, "download")]


def test_target_coverage_empty_db_returns_empty(catalog_db: Path) -> None:
    reader = CatalogReader(open_ro(catalog_db))
    coverage = reader.target_coverage()
    assert coverage == {}


def test_target_coverage_multiple_files_same_target(catalog_db: Path) -> None:
    """Deux fichiers matchant le même target_id → list de longueur 2."""
    with sqlite3.connect(catalog_db) as conn:
        for suffix in ("a", "b"):
            h = suffix * 32
            conn.execute(
                "INSERT INTO files (ed2k_hash, size_bytes) VALUES (?, ?)",
                (h, 100),
            )
            conn.execute(
                "INSERT INTO match_decisions"
                " (ed2k_hash, target_id, rule_name, tier, decided_at, node_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (h, "S2E062A", "rule", "download", "2026-06-22T10:00:00.000000+00:00", "n1"),
            )
        conn.commit()
    reader = CatalogReader(open_ro(catalog_db))
    coverage = reader.target_coverage()
    assert len(coverage["S2E062A"]) == 2


# ---------------------------------------------------------------------------
# Tests : explorateur — filtres présents / absents
# ---------------------------------------------------------------------------


def test_list_files_no_filter_returns_all(catalog_db: Path) -> None:
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    rows = reader.list_files(target=None, tier=None, verdict=None, query=None, page=1)
    assert len(rows) == 1
    assert rows[0].ed2k_hash == "a" * 32
    assert rows[0].filename == "keroro_062.avi"
    assert rows[0].source_count == 5


def test_list_files_filter_by_target(catalog_db: Path) -> None:
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    hit = reader.list_files(target="S2E062A", tier=None, verdict=None, query=None, page=1)
    miss = reader.list_files(target="S2E001A", tier=None, verdict=None, query=None, page=1)
    assert len(hit) == 1
    assert miss == []


def test_list_files_filter_by_tier(catalog_db: Path) -> None:
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    hit = reader.list_files(target=None, tier="download", verdict=None, query=None, page=1)
    miss = reader.list_files(target=None, tier="notify", verdict=None, query=None, page=1)
    assert len(hit) == 1
    assert miss == []


def test_list_files_filter_by_verdict(catalog_db: Path) -> None:
    _seed_with_verdict(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    hit = reader.list_files(target=None, tier=None, verdict="ok", query=None, page=1)
    miss = reader.list_files(target=None, tier=None, verdict="malicious", query=None, page=1)
    assert len(hit) == 1
    assert miss == []


def test_list_files_no_verdict_still_returns_file(catalog_db: Path) -> None:
    """Un fichier sans vérification apparaît quand verdict=None."""
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    rows = reader.list_files(target=None, tier=None, verdict=None, query=None, page=1)
    assert len(rows) == 1


def test_list_files_filter_by_query(catalog_db: Path) -> None:
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    hit = reader.list_files(target=None, tier=None, verdict=None, query="keroro", page=1)
    miss = reader.list_files(target=None, tier=None, verdict=None, query="unknown", page=1)
    assert len(hit) == 1
    assert miss == []


def test_list_files_page_two_is_empty(catalog_db: Path) -> None:
    """Page 2 est vide si moins de PAGE_SIZE résultats."""
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    rows = reader.list_files(target=None, tier=None, verdict=None, query=None, page=2)
    assert rows == []


# ---------------------------------------------------------------------------
# Tests : détail
# ---------------------------------------------------------------------------


def test_file_detail_carries_observations_and_decision(catalog_db: Path) -> None:
    _seed(catalog_db)
    detail = CatalogReader(open_ro(catalog_db)).file_detail("a" * 32)
    assert detail is not None
    assert detail.size_bytes == 100
    assert detail.decision is not None
    assert detail.decision.target_id == "S2E062A"
    assert len(detail.observations) == 1


def test_file_detail_unknown_hash_is_none(catalog_db: Path) -> None:
    _seed(catalog_db)
    assert CatalogReader(open_ro(catalog_db)).file_detail("f" * 32) is None


def test_file_detail_with_verifications(catalog_db: Path) -> None:
    _seed_with_verdict(catalog_db)
    detail = CatalogReader(open_ro(catalog_db)).file_detail("a" * 32)
    assert detail is not None
    assert len(detail.verifications) == 1
    assert detail.verifications[0].verdict == "ok"


def test_file_detail_no_decision(catalog_db: Path) -> None:
    """Détail fonctionne même sans décision (fichier non matché)."""
    with sqlite3.connect(catalog_db) as conn:
        conn.execute(
            "INSERT INTO files (ed2k_hash, size_bytes) VALUES (?, ?)",
            ("b" * 32, 200),
        )
        conn.execute(
            "INSERT INTO file_observations"
            " (ed2k_hash, filename, size_bytes, source_count,"
            " complete_source_count, raw_meta, keyword, observed_at, node_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "b" * 32,
                "unknown.avi",
                200,
                1,
                0,
                "[]",
                "unknown",
                "2026-06-22T09:00:00.000000+00:00",
                "n2",
            ),
        )
        conn.commit()
    detail = CatalogReader(open_ro(catalog_db)).file_detail("b" * 32)
    assert detail is not None
    assert detail.decision is None
    assert detail.size_bytes == 200


# ---------------------------------------------------------------------------
# Tests : list_files avec multiples filtres combinés
# ---------------------------------------------------------------------------


def test_list_files_combined_target_and_tier_filters(catalog_db: Path) -> None:
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    hit = reader.list_files(target="S2E062A", tier="download", verdict=None, query=None, page=1)
    miss = reader.list_files(target="S2E062A", tier="notify", verdict=None, query=None, page=1)
    assert len(hit) == 1
    assert miss == []


@pytest.mark.parametrize("page", [1, 2])
def test_list_files_pagination(catalog_db: Path, page: int) -> None:
    """Vérifie que la pagination ne crash pas (page 1 = résultats, page 2 = vide)."""
    _seed(catalog_db)
    reader = CatalogReader(open_ro(catalog_db))
    rows = reader.list_files(target=None, tier=None, verdict=None, query=None, page=page)
    if page == 1:
        assert len(rows) == 1
    else:
        assert rows == []
