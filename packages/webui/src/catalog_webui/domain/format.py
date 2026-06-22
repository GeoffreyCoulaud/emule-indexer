"""Formatage pur pour l'affichage (spec webui §4/§7). Aucun I/O."""


def ed2k_link(ed2k_hash: str, filename: str, size_bytes: int) -> str:
    """Reconstruit le lien eD2k canonique d'un fichier observé."""
    return f"ed2k://|file|{filename}|{size_bytes}|{ed2k_hash}|/"


def short_hash(ed2k_hash: str) -> str:
    """Hash tronqué pour l'affichage (8 premiers caractères + ellipse)."""
    if len(ed2k_hash) <= 8:
        return ed2k_hash
    return f"{ed2k_hash[:8]}…"
