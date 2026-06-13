"""Logique de vérification NO-OP (spec verify §4 — DÉCISION DV1).

Le verifier est trivial : il confirme l'EXISTENCE du fichier en quarantaine (``stat`` RO)
et rend ``unverified`` — il ne lit JAMAIS les octets, n'exécute rien dessus, et ignore
``expected``. Le VRAI travail d'analyse (confinement jetable + checks type_sniff/ffprobe/
clamav remplissant ``real_meta``) est D-analysis. La forme de résultat (verdict, real_meta,
checks) est définie ICI, indépendamment du DTO crawler (frontière de paquet, DÉCISION DV4) ;
le contrat de fil JSON les garde en phase (test de contrat + e2e).

Le verifier est stateless, no-DB, no-domain, no-Internet : il ne connaît que le dossier de
quarantaine (config du service) et le hash demandé.
"""

from collections.abc import Mapping
from pathlib import Path

# Verdict NO-OP : un fichier présent est "unverified" (existence prouvée, contenu non analysé) ;
# absent (ou non-fichier) est "error" (rien à vérifier — la boucle l'enregistre + complète).
_VERDICT_UNVERIFIED = "unverified"
_VERDICT_ERROR = "error"


def verify_file(
    quarantine_path: Path, expected: Mapping[str, object]
) -> tuple[str, dict[str, object], list[object]]:
    """Vérifie (NO-OP) un fichier en quarantaine. Rend ``(verdict, real_meta, checks)``.

    Ne lit JAMAIS les octets (``is_file`` ne touche que les métadonnées d'inode) et ignore
    ``expected`` (le NO-OP n'en fait rien ; D-analysis l'exploitera pour comparer aux attendus).
    Fichier régulier présent → ``("unverified", {}, [])`` ; absent ou non-fichier (répertoire,
    lien cassé…) → ``("error", {}, [])``.
    """
    if quarantine_path.is_file():
        return _VERDICT_UNVERIFIED, {}, []
    return _VERDICT_ERROR, {}, []
