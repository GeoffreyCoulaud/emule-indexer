"""Matchers feuilles du moteur de matching (cf. spec §8.2)."""

import re2

from emule_indexer.domain.matching.models import FileCandidate
from emule_indexer.domain.normalization import fold, tokenize


class KeywordMatcher:
    """Vrai si la phrase (tokenisée) est une sous-suite CONTIGUË des tokens du nom."""

    def __init__(self, phrase: str) -> None:
        self._tokens = tokenize(phrase)

    def matches(self, candidate: FileCandidate) -> bool:
        needle = self._tokens
        haystack = tokenize(candidate.filename)
        if not needle:
            return True
        # Fenêtre glissante de largeur len(needle) : sous-suite CONTIGUË.
        last_start = len(haystack) - len(needle)
        return any(
            haystack[start : start + len(needle)] == needle for start in range(last_start + 1)
        )


class RegexMatcher:
    """Match RE2 sur ``fold(filename)``. Si ``"i"`` dans ``flags``, préfixe ``(?i)``.

    On préfixe explicitement ``(?i)`` au pattern plutôt que de s'appuyer sur des
    constantes de flag RE2 (portabilité de l'API ``re2``).

    ``flags`` est une chaîne courte façon ``re`` : ``"i"`` active l'insensibilité
    à la casse, ``""`` la laisse sensible. Valeurs attendues depuis la config
    YAML (Plan 2b) : ``"i"`` ou ``""``. La détection est ``"i" in flags`` — ne
    pas passer de noms verbeux (``"ignore_case"``…), qui activeraient ``(?i)``
    par accident. Un pattern invalide lève ``re2.error`` à la construction
    (validation de config déléguée au Plan 2b).
    """

    def __init__(self, pattern: str, flags: str = "i") -> None:
        if "i" in flags:
            pattern = "(?i)" + pattern
        self._re = re2.compile(pattern)

    def matches(self, candidate: FileCandidate) -> bool:
        return self._re.search(fold(candidate.filename)) is not None
