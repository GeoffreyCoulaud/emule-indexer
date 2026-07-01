"""Génération des mots-clés de recherche depuis la config (PUR, spec search-simplification).

Domaine PUR : aucune I/O. Les mots-clés sont fournis par la config (``crawler.yml``,
``search.keywords``) — par défaut ``keroro`` (filet large) + ``titar`` (sentinelle FR,
jackpot-proof). ``generate_keywords`` est déterministe : même liste → même tuple, ORDONNÉ
et DÉDUPLIQUÉ (premier vu gagne), pour que le shuffle seedé du cycle parte d'un ordre stable.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchKeyword:
    """Un mot-clé à rechercher + sa provenance. GELÉ et hashable → déduplication triviale."""

    text: str
    origin: str


def generate_keywords(keywords: Sequence[str]) -> tuple[SearchKeyword, ...]:
    """Liste ORDONNÉE et DÉDUPLIQUÉE des mots-clés (spec search-simplification).

    Ordre = ordre d'entrée ; déduplication par ``text`` (premier vu gagne) ; les chaînes
    vides sont ignorées. ``origin`` = le texte lui-même (provenance = mot-clé de config).
    """
    seen: set[str] = set()
    result: list[SearchKeyword] = []
    for text in keywords:
        if text and text not in seen:
            seen.add(text)
            result.append(SearchKeyword(text=text, origin=text))
    return tuple(result)
