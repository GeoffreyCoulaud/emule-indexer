"""Point d'entrée `python -m emule_indexer.compact` : CLI safe-by-default de la compaction.

`main(argv) -> int` : 0 = OK ; 2 = erreur d'usage/compaction (message clair sur stderr, jamais
de traceback nu) ; argparse rend lui-même 2 pour une erreur de parsing. Aucune variable
d'environnement (doctrine du repo). Safe-by-default (spec §6) : la sortie ne doit PAS exister
(pas de --force, pas d'append) ; source absente → erreur ; keep-recent-days >= 0.
"""

import argparse
import logging
import sys
from pathlib import Path

from emule_indexer.compact.compactor import compact_catalog
from emule_indexer.compact.errors import CompactError

_LOGGER = logging.getLogger("emule_indexer.compact")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="emule_indexer.compact",
        description=(
            "Compacte un catalog.db (rollup journalier des observations) vers une sortie neuve."
        ),
    )
    parser.add_argument("source", type=Path, help="catalog.db à compacter.")
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Fichier de sortie NEUF (refus s'il existe ; supprimez-le pour refaire).",
    )
    parser.add_argument(
        "--keep-recent-days",
        type=int,
        default=90,
        help="Jours récents gardés bruts (défaut 90 ; 0 = compacter tout l'historique).",
    )
    return parser.parse_args(argv)


def _validate(args: argparse.Namespace) -> None:
    """Règles safe-by-default, AVANT toute ouverture/création (CompactError, message clair)."""
    if not args.source.exists():
        raise CompactError(f"source introuvable : {args.source}")
    if args.output.exists():
        raise CompactError(f"la sortie existe déjà : {args.output} (supprimez-la pour refaire)")
    if args.keep_recent_days < 0:
        raise CompactError("--keep-recent-days doit être >= 0")


def main(argv: list[str] | None = None) -> int:
    """Entrée CLI. 0 = OK, 2 = erreur d'usage/compaction (message clair sur stderr)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        _validate(args)
        _LOGGER.info(
            "compact %s → %s (keep_recent_days=%d)", args.source, args.output, args.keep_recent_days
        )
        compact_catalog(args.source, args.output, keep_recent_days=args.keep_recent_days)
    except CompactError as error:
        print(f"Compaction impossible : {error}", file=sys.stderr, flush=True)
        return 2
    _LOGGER.info("compaction terminée : %s", args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
