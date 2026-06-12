"""Hiérarchie d'erreurs de l'adapter persistence (spec data-model §7).

L'adapter SIGNALE, il ne décide pas (même philosophie que l'adapter EC) : toute
``sqlite3.Error`` inattendue sort enveloppée en ``PersistenceError``, jamais nue.
Un trigger append-only qui se déclenche est un BUG du code appelant, pas un cas
métier → la même ``PersistenceError``. ``wrap_sqlite_errors`` est l'enveloppe
UNIQUE partagée par la connexion et les deux repositories (cause chaînée gardée).
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


class PersistenceError(Exception):
    """Base de toutes les erreurs de l'adapter persistence."""


class MigrationError(PersistenceError):
    """Base plus récente que le code, ou script qui échoue (fail-fast, spec MVP §14)."""


@contextmanager
def wrap_sqlite_errors() -> Iterator[None]:
    """Enveloppe toute ``sqlite3.Error`` en ``PersistenceError`` (cause chaînée)."""
    try:
        yield
    except sqlite3.Error as error:
        raise PersistenceError(str(error)) from error
