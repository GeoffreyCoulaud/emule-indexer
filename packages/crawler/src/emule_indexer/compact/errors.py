"""`CompactError` : erreur d'usage ou de compaction (message clair pour le CLI, jamais nu).

Outil opérateur standalone (spec compaction §6), indépendant du contrat d'erreur des
repositories — comme MergeError. `__main__` la rend sur stderr avec un code de sortie non nul.
"""


class CompactError(Exception):
    """Usage invalide ou compaction qui échoue (fail-fast, message clair pour l'opérateur)."""
