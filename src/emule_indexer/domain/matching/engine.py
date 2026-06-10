"""Moteur d'ÉVALUATION du matching (cf. spec §8.5, partie évaluation).

Domaine PUR. Prend une :class:`MatcherConfig` déjà validée (Plan 2b) et des
:class:`TargetSegment`, pré-résout les arbres de matchers par cible une fois à la
construction (via :class:`MatcherResolver`), puis rend une décision EN MÉMOIRE pour un
:class:`FileCandidate`. AUCUNE I/O, AUCUN logging, AUCUNE DB : l'« explicabilité loggée
en DEBUG » de §8.5 = le moteur RETOURNE un résultat explicable ; le logging est l'affaire
d'un adapter d'un plan ultérieur.
"""

# Rang des paliers (cf. spec §8.5 : « palier le plus haut, download>notify>catalog »).
# Entier croissant = palier plus haut. `TIERS` (config) donne l'ensemble LICITE ; ce
# rang donne l'ORDRE de décision. Un test vérifie set(_TIER_RANK) == TIERS.
_TIER_RANK: dict[str, int] = {"catalog": 0, "notify": 1, "download": 2}
