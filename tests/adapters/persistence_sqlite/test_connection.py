import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from emule_indexer.adapters.persistence_sqlite.connection import (
    _apply_migrations,
    _load_scripts,
    open_catalog,
    open_local,
    utc_iso,
    utc_now,
)
from emule_indexer.adapters.persistence_sqlite.errors import MigrationError, PersistenceError

_CATALOG_TABLES = {
    "files",
    "file_observations",
    "sources",
    "source_observations",
    "match_decisions",
    "file_verifications",
}
_LOCAL_TABLES = {"node_runtime", "verification_tasks", "downloads", "scheduler_state"}

# Canonical 32-char lowercase hex hash (satisfies the CHECK constraint).
_CANONICAL_HASH = "a" * 32


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def test_open_catalog_creates_the_six_tables_and_versions_the_schema(tmp_path: Path) -> None:
    connection = open_catalog(tmp_path / "catalog.db")
    try:
        assert _table_names(connection) == _CATALOG_TABLES
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        connection.close()


def test_open_local_creates_the_four_tables_and_the_partial_unique_index(tmp_path: Path) -> None:
    connection = open_local(tmp_path / "local.db")
    try:
        assert _table_names(connection) == _LOCAL_TABLES
        index_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'idx_verification_tasks_active_hash'"
        ).fetchone()[0]
        assert "WHERE status IN ('pending', 'in_progress')" in index_sql
    finally:
        connection.close()


def test_open_applies_wal_and_foreign_keys_and_recursive_triggers_pragmas(tmp_path: Path) -> None:
    connection = open_catalog(tmp_path / "catalog.db")
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
    finally:
        connection.close()


def test_open_local_applies_recursive_triggers_pragma(tmp_path: Path) -> None:
    connection = open_local(tmp_path / "local.db")
    try:
        assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
    finally:
        connection.close()


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    connection = open_catalog(tmp_path / "catalog.db")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                "INSERT INTO match_decisions"
                " (ed2k_hash, target_id, rule_name, tier, decided_at, node_id)"
                " VALUES ('absent', 't', 'r', 'catalog', 'now', 'n')"
            )
    finally:
        connection.close()


def test_reopen_is_idempotent_and_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "catalog.db"
    first = open_catalog(path)
    first.execute("INSERT INTO files (ed2k_hash, size_bytes) VALUES (?, 1)", (_CANONICAL_HASH,))
    first.close()
    second = open_catalog(path)  # version 1 déjà appliquée : AUCUN script ne rejoue
    try:
        assert second.execute("PRAGMA user_version").fetchone()[0] == 1
        assert second.execute("SELECT count(*) FROM files").fetchone()[0] == 1
    finally:
        second.close()


def test_in_memory_database_is_refused_because_wal_is_required() -> None:
    # :memory: répond journal_mode='memory' (vérifié empiriquement) -> refus net.
    with pytest.raises(PersistenceError, match="WAL"):
        open_catalog(":memory:")


def test_unopenable_path_raises_persistence_error(tmp_path: Path) -> None:
    with pytest.raises(PersistenceError):
        open_catalog(tmp_path)  # un répertoire n'est pas une base


def test_database_newer_than_the_code_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "catalog.db"
    open_catalog(path).close()
    raw = sqlite3.connect(path, autocommit=True)
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    with pytest.raises(MigrationError, match="99"):
        open_catalog(path)


def test_apply_migrations_with_no_scripts_is_a_noop(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "vide.db", autocommit=True)
    try:
        _apply_migrations(connection, ())
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        connection.close()


def test_failed_script_is_rolled_back_and_version_unchanged(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "echec.db", autocommit=True)
    bad_script = "CREATE TABLE disparait (x INTEGER);\nINSERT INTO inexistante VALUES (1);"
    try:
        with pytest.raises(MigrationError, match="migration 2"):
            _apply_migrations(
                connection, ((1, "CREATE TABLE survit (x INTEGER);"), (2, bad_script))
            )
        # La migration 1 a SA transaction (appliquée) ; la 2 est ENTIÈREMENT défaite.
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert _table_names(connection) == {"survit"}
    finally:
        connection.close()


def test_load_scripts_orders_by_name_and_skips_non_sql(tmp_path: Path) -> None:
    (tmp_path / "0002_second.sql").write_text("B", encoding="utf-8")
    (tmp_path / "0001_premier.sql").write_text("A", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignoré", encoding="utf-8")
    assert _load_scripts(tmp_path) == ((1, "A"), (2, "B"))


def test_load_scripts_rejects_a_non_numeric_prefix(tmp_path: Path) -> None:
    (tmp_path / "abcd_mauvais.sql").write_text("X", encoding="utf-8")
    with pytest.raises(MigrationError, match="abcd_mauvais.sql"):
        _load_scripts(tmp_path)


def test_utc_iso_is_fixed_width_and_normalizes_to_utc() -> None:
    # Largeur fixe (microsecondes TOUJOURS écrites) => ordre lexicographique == chronologique.
    paris = timezone(timedelta(hours=2))
    moment = datetime(2026, 6, 11, 14, 0, 0, tzinfo=paris)
    assert utc_iso(moment) == "2026-06-11T12:00:00.000000+00:00"


def test_utc_now_returns_an_aware_utc_datetime() -> None:
    now = utc_now()
    assert now.tzinfo == UTC


# --- MANDATED AMENDMENT: recursive_triggers guards append-only against INSERT OR REPLACE ---


def test_insert_or_replace_on_existing_hash_raises_integrity_error(tmp_path: Path) -> None:
    """INSERT OR REPLACE on an existing files row must raise (triggers guarded by
    recursive_triggers=ON, spec §3 amendment).  The trigger fires on the implicit DELETE
    that REPLACE performs internally, surfacing as sqlite3.IntegrityError."""
    connection = open_catalog(tmp_path / "catalog.db")
    try:
        connection.execute(
            "INSERT INTO files (ed2k_hash, size_bytes) VALUES (?, 1)", (_CANONICAL_HASH,)
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT OR REPLACE INTO files (ed2k_hash, size_bytes) VALUES (?, 2)",
                (_CANONICAL_HASH,),
            )
    finally:
        connection.close()
