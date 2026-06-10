"""Moteur d'ÉVALUATION du matching (cf. spec §8.5, partie évaluation).

Domaine PUR. Prend une :class:`MatcherConfig` déjà validée (Plan 2b) et des
:class:`TargetSegment`, pré-résout les arbres de matchers par cible une fois à la
construction (via :class:`MatcherResolver`), puis rend une décision EN MÉMOIRE pour un
:class:`FileCandidate`. AUCUNE I/O, AUCUN logging, AUCUNE DB : l'« explicabilité loggée
en DEBUG » de §8.5 = le moteur RETOURNE un résultat explicable ; le logging est l'affaire
d'un adapter d'un plan ultérieur.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    """Pourquoi cette décision (cf. spec §8.5 : tokens/règles déclenchés + value coverage).

    Concerne la SEULE cible gagnante. ``rules_fired`` : noms des règles vraies pour cette
    cible, dans l'ordre de la config (la 1re est la gagnante). ``tokens_matched`` : noms
    des tokens nommés de la config qui matchent (triés). ``coverage_values`` : pour chaque
    token coverage, ``(nom, value(candidate))`` (triés). Tuples (et non dicts) pour rester
    GELÉ/hashable et déterministe.
    """

    target_id: str
    rules_fired: tuple[str, ...]
    tokens_matched: tuple[str, ...]
    coverage_values: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class MatchDecision:
    """Décision fichier (cf. spec §8.5). Porte les 3 colonnes de match_decisions (§11).

    ``target_id``/``rule_name``/``tier`` = exactement les colonnes que ``match_decisions``
    persistera (§11). ``decided_at``/``node_id``/``ed2k_hash`` ne sont PAS ici : ce sont
    des colonnes de persistance (horloge + identité + clé contenu) injectées par l'adapter
    DB d'un plan ultérieur. ``explanation`` embarque l'explicabilité (§8.5).
    """

    target_id: str
    rule_name: str
    tier: str
    explanation: Explanation


# Rang des paliers (cf. spec §8.5 : « palier le plus haut, download>notify>catalog »).
# Entier croissant = palier plus haut. `TIERS` (config) donne l'ensemble LICITE ; ce
# rang donne l'ORDRE de décision. Un test vérifie set(_TIER_RANK) == TIERS.
_TIER_RANK: dict[str, int] = {"catalog": 0, "notify": 1, "download": 2}
