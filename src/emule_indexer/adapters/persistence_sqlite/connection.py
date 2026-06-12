"""Connexion SQLite + runner de migrations (spec data-model §3/§4/§7).

Chaque connexion est ouverte en autocommit RÉEL (``autocommit=True``, Python ≥ 3.12) :
les transactions sont EXPLICITES (``BEGIN``/``COMMIT``/``ROLLBACK`` écrits par les
repositories), aucune isolation implicite. PRAGMA d'ouverture (spec §3) :
``journal_mode=WAL`` — EXIGÉ : ``:memory:`` ne le porte pas (il répond ``memory``)
et est donc refusé net ; les tests utilisent des fichiers réels (spec §8) —
``foreign_keys=ON``, et ``recursive_triggers=ON`` (sans quoi ``INSERT OR REPLACE``
traverse les triggers append-only, spec §3 amendement post-review).

Le runner lit les scripts ``NNNN_*.sql`` embarqués dans le paquet (``importlib.
resources``), les applique en ordre croissant CHACUN dans SA transaction (échec →
ROLLBACK best-effort, version inchangée — même esprit que le ``close()`` best-effort
du transport EC), et trace l'état dans ``PRAGMA user_version``. Une base PLUS RÉCENTE
que le code → refus net (``MigrationError``, fail-fast spec MVP §14). Les scripts ne
contiennent AUCUN ``BEGIN``/``COMMIT`` : c'est le runner qui enveloppe.

Ce module porte aussi l'horloge partagée des repositories (``Clock``/``utc_now``/
``utc_iso``) : ISO-8601 UTC en TEXT (spec §3), microsecondes FIXES pour que l'ordre
lexicographique SOIT l'ordre chronologique (le claim FIFO trie sur ``enqueued_at``).
"""

import sqlite3
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from emule_indexer.adapters.persistence_sqlite.errors import (
    MigrationError,
    PersistenceError,
    wrap_sqlite_errors,
)

type Clock = Callable[[], datetime]

_MIGRATIONS = resources.files("emule_indexer.adapters.persistence_sqlite") / "migrations"


def utc_now() -> datetime:
    """Horloge par défaut des repositories (spec §3 : injectable, ``datetime.now(UTC)``)."""
    return datetime.now(UTC)


def utc_iso(moment: datetime) -> str:
    """ISO-8601 UTC à largeur fixe (microsecondes TOUJOURS écrites), p.ex.
    ``2026-06-11T12:00:00.000000+00:00``. ``moment`` doit être AWARE (contrat de
    ``Clock``) ; un fuseau non-UTC est normalisé, jamais stocké tel quel."""
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def open_catalog(path: Path | str) -> sqlite3.Connection:
    """Ouvre/migre ``catalog.db`` (les triggers append-only font partie du schéma)."""
    return _open(path, _MIGRATIONS / "catalog")


def open_local(path: Path | str) -> sqlite3.Connection:
    """Ouvre/migre ``local.db``."""
    return _open(path, _MIGRATIONS / "local")


def _open(path: Path | str, scripts_dir: Traversable) -> sqlite3.Connection:
    with wrap_sqlite_errors():
        connection = sqlite3.connect(path, autocommit=True)
    try:
        with wrap_sqlite_errors():
            _configure(connection)
            _apply_migrations(connection, _load_scripts(scripts_dir))
    except PersistenceError:
        connection.close()
        raise
    return connection


def _configure(connection: sqlite3.Connection) -> None:
    journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if journal_mode != "wal":
        raise PersistenceError(
            f"journal_mode={journal_mode!r} : WAL exigé (spec §3) — base fichier uniquement"
        )
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA recursive_triggers=ON")


def _load_scripts(directory: Traversable) -> tuple[tuple[int, str], ...]:
    """Découverte des migrations : ``NNNN_*.sql`` triés par nom (ordre lexicographique).

    Un fichier non-``.sql`` est ignoré ; un ``.sql`` sans préfixe numérique est un BUG
    d'empaquetage → ``MigrationError`` (fail-fast, pas de migration silencieusement sautée).
    """
    scripts: list[tuple[int, str]] = []
    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".sql"):
            continue
        prefix = entry.name.partition("_")[0]
        if not prefix.isdigit():
            raise MigrationError(f"nom de script invalide (attendu NNNN_*.sql) : {entry.name}")
        scripts.append((int(prefix), entry.read_text(encoding="utf-8")))
    return tuple(scripts)


def _apply_migrations(connection: sqlite3.Connection, scripts: tuple[tuple[int, str], ...]) -> None:
    """Applique les scripts de version > ``user_version``, chacun dans SA transaction.

    ``PRAGMA user_version = N`` est posé DANS la transaction du script N (le pragma est
    transactionnel : un ROLLBACK le rend — vérifié empiriquement, SQLite 3.47.1). PRAGMA
    n'accepte pas de paramètre lié : ``version`` vient d'``int()``, l'interpolation est sûre.
    """
    current = int(connection.execute("PRAGMA user_version").fetchone()[0])
    latest = scripts[-1][0] if scripts else 0
    if current > latest:
        raise MigrationError(
            f"base en version {current}, code en version {latest} : "
            "base plus récente que le code, refus de démarrer (spec §3)"
        )
    for version, script in scripts:
        if version <= current:
            continue
        try:
            connection.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;")
        except sqlite3.Error as error:
            with suppress(sqlite3.Error):
                connection.execute("ROLLBACK")
            raise MigrationError(f"migration {version} échouée : {error}") from error
