"""Lecture read-only du catalogue (spec webui W-D6 / §6).

``CatalogReader`` expose trois lectures :

- ``target_coverage()`` — par ``target_id``, liste ``(ed2k_hash, tier)`` de la DERNIÈRE
  décision de matching de chaque fichier (fenêtre ROW_NUMBER PARTITION BY ed2k_hash).
- ``list_files()`` — explorateur filtré paginé (fichiers ⨝ dernière observation ⨝
  dernière décision ⨝ dernier verdict, filtres optionnels + LIMIT/OFFSET).
- ``file_detail()`` — toutes les observations + dernière décision + tous les verdicts
  d'un hash donné ; ``None`` si le hash est inconnu.

Tout le SQL est en constantes module, paramétré (aucune interpolation de valeurs).
"""

import sqlite3

from catalog_webui.domain.views import (
    DecisionView,
    FileDetail,
    FileRow,
    ObservationRow,
    VerificationRow,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_PAGE_SIZE = 50

# Dernière décision par fichier via fenêtre ROW_NUMBER.
_SQL_COVERAGE = """\
SELECT
    md.ed2k_hash,
    md.target_id,
    md.tier
FROM match_decisions AS md
WHERE (
    SELECT COUNT(*)
    FROM match_decisions AS md2
    WHERE
        md2.ed2k_hash = md.ed2k_hash
        AND (
            md2.decided_at > md.decided_at
            OR (md2.decided_at = md.decided_at AND md2.id > md.id)
        )
) = 0
ORDER BY md.target_id, md.ed2k_hash
"""

# Explorateur : fichiers ⨝ dernière observation ⨝ dernière décision ⨝ dernier verdict.
# Les filtres optionnels sont ajoutés dynamiquement (voir list_files()).
_SQL_LIST_FILES_BASE = """\
SELECT
    f.ed2k_hash,
    f.size_bytes,
    obs.filename,
    obs.source_count,
    obs.observed_at AS last_seen,
    dec.target_id,
    dec.tier,
    ver.verdict AS last_verdict
FROM files AS f
LEFT JOIN file_observations AS obs
    ON obs.ed2k_hash = f.ed2k_hash
    AND (
        SELECT COUNT(*)
        FROM file_observations AS obs2
        WHERE
            obs2.ed2k_hash = obs.ed2k_hash
            AND (
                obs2.observed_at > obs.observed_at
                OR (obs2.observed_at = obs.observed_at AND obs2.id > obs.id)
            )
    ) = 0
LEFT JOIN match_decisions AS dec
    ON dec.ed2k_hash = f.ed2k_hash
    AND (
        SELECT COUNT(*)
        FROM match_decisions AS dec2
        WHERE
            dec2.ed2k_hash = dec.ed2k_hash
            AND (
                dec2.decided_at > dec.decided_at
                OR (dec2.decided_at = dec.decided_at AND dec2.id > dec.id)
            )
    ) = 0
LEFT JOIN file_verifications AS ver
    ON ver.ed2k_hash = f.ed2k_hash
    AND (
        SELECT COUNT(*)
        FROM file_verifications AS ver2
        WHERE
            ver2.ed2k_hash = ver.ed2k_hash
            AND (
                ver2.verified_at > ver.verified_at
                OR (ver2.verified_at = ver.verified_at AND ver2.id > ver.id)
            )
    ) = 0
"""

# Toutes les observations d'un fichier (timeline), ordre chronologique.
_SQL_OBSERVATIONS = """\
SELECT
    id,
    filename,
    size_bytes,
    source_count,
    complete_source_count,
    media_length_sec,
    bitrate_kbps,
    keyword,
    observed_at,
    node_id
FROM file_observations
WHERE ed2k_hash = ?
ORDER BY observed_at ASC, id ASC
"""

# Dernière décision d'un fichier.
_SQL_LAST_DECISION = """\
SELECT
    target_id,
    rule_name,
    tier,
    decided_at,
    node_id
FROM match_decisions
WHERE ed2k_hash = ?
ORDER BY decided_at DESC, id DESC
LIMIT 1
"""

# Tous les verdicts d'un fichier, ordre chronologique.
_SQL_VERIFICATIONS = """\
SELECT
    id,
    verdict,
    verified_at,
    node_id
FROM file_verifications
WHERE ed2k_hash = ?
ORDER BY verified_at ASC, id ASC
"""

# Lookup de base sur files (pour file_detail).
_SQL_FILE = """\
SELECT ed2k_hash, size_bytes, aich_hash
FROM files
WHERE ed2k_hash = ?
"""


# ---------------------------------------------------------------------------
# CatalogReader
# ---------------------------------------------------------------------------


class CatalogReader:
    """Accès read-only au catalogue via une connexion SQLite (open_ro)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Couverture
    # ------------------------------------------------------------------

    def target_coverage(self) -> dict[str, list[tuple[str, str]]]:
        """Retourne pour chaque ``target_id`` la liste ``(ed2k_hash, tier)``
        de la DERNIÈRE décision de matching de chaque fichier.
        """
        rows = self._conn.execute(_SQL_COVERAGE).fetchall()
        result: dict[str, list[tuple[str, str]]] = {}
        for row in rows:
            target_id: str = row["target_id"]
            entry = (row["ed2k_hash"], row["tier"])
            if target_id not in result:
                result[target_id] = []
            result[target_id].append(entry)
        return result

    # ------------------------------------------------------------------
    # Explorateur filtré paginé
    # ------------------------------------------------------------------

    def list_files(
        self,
        *,
        target: str | None,
        tier: str | None,
        verdict: str | None,
        query: str | None,
        page: int,
    ) -> list[FileRow]:
        """Retourne une page de ``FileRow`` (taille ``_PAGE_SIZE``) avec filtres optionnels.

        Filtres :
        - ``target`` : filtre sur ``dec.target_id`` (dernière décision).
        - ``tier``   : filtre sur ``dec.tier`` (dernière décision).
        - ``verdict``: filtre sur ``ver.verdict`` (dernier verdict).
        - ``query``  : sous-chaîne de ``obs.filename`` (LIKE ``%query%``).
        - ``page``   : numéro de page (1-based).
        """
        clauses: list[str] = []
        params: list[str | int] = []

        if target is not None:
            clauses.append("dec.target_id = ?")
            params.append(target)
        if tier is not None:
            clauses.append("dec.tier = ?")
            params.append(tier)
        if verdict is not None:
            clauses.append("ver.verdict = ?")
            params.append(verdict)
        if query is not None:
            clauses.append("obs.filename LIKE ?")
            params.append(f"%{query}%")

        sql = _SQL_LIST_FILES_BASE
        if clauses:
            sql += "WHERE " + " AND ".join(clauses) + "\n"
        sql += "ORDER BY obs.observed_at DESC, f.ed2k_hash\n"
        sql += "LIMIT ? OFFSET ?\n"
        params.append(_PAGE_SIZE)
        params.append((page - 1) * _PAGE_SIZE)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            FileRow(
                ed2k_hash=row["ed2k_hash"],
                size_bytes=row["size_bytes"],
                filename=row["filename"] or "",
                source_count=row["source_count"],
                last_seen=row["last_seen"] or "",
                target_id=row["target_id"],
                tier=row["tier"],
                last_verdict=row["last_verdict"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Détail
    # ------------------------------------------------------------------

    def file_detail(self, ed2k_hash: str) -> FileDetail | None:
        """Retourne le détail complet d'un fichier, ou ``None`` si inconnu."""
        file_row = self._conn.execute(_SQL_FILE, (ed2k_hash,)).fetchone()
        if file_row is None:
            return None

        obs_rows = self._conn.execute(_SQL_OBSERVATIONS, (ed2k_hash,)).fetchall()
        dec_row = self._conn.execute(_SQL_LAST_DECISION, (ed2k_hash,)).fetchone()
        ver_rows = self._conn.execute(_SQL_VERIFICATIONS, (ed2k_hash,)).fetchall()

        decision: DecisionView | None = None
        if dec_row is not None:
            decision = DecisionView(
                target_id=dec_row["target_id"],
                rule_name=dec_row["rule_name"],
                tier=dec_row["tier"],
                decided_at=dec_row["decided_at"],
                node_id=dec_row["node_id"],
            )

        return FileDetail(
            ed2k_hash=file_row["ed2k_hash"],
            size_bytes=file_row["size_bytes"],
            aich_hash=file_row["aich_hash"],
            observations=tuple(
                ObservationRow(
                    id=row["id"],
                    filename=row["filename"],
                    size_bytes=row["size_bytes"],
                    source_count=row["source_count"],
                    complete_source_count=row["complete_source_count"],
                    media_length_sec=row["media_length_sec"],
                    bitrate_kbps=row["bitrate_kbps"],
                    keyword=row["keyword"],
                    observed_at=row["observed_at"],
                    node_id=row["node_id"],
                )
                for row in obs_rows
            ),
            decision=decision,
            verifications=tuple(
                VerificationRow(
                    id=row["id"],
                    verdict=row["verdict"],
                    verified_at=row["verified_at"],
                    node_id=row["node_id"],
                )
                for row in ver_rows
            ),
        )
