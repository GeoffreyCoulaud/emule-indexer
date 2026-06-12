"""Port ``CatalogRepository`` : la mémoire durable du catalogue (spec data-model §4).

Protocol SYNCHRONE (spec §3 : une écriture locale est sub-milliseconde ; si le plan C
veut s'isoler, il enveloppera dans ``asyncio.to_thread`` sans toucher cette couche).
Le port n'importe QUE le domaine. Les stubs tiennent sur UNE ligne (le ``def`` s'exécute
à la création de la classe : couvert). L'adapter stamppe ``observed_at``/``decided_at``/
``node_id`` — c'est pour ça que ``record_decision`` reçoit le hash À CÔTÉ de la décision
(``MatchDecision`` ne porte pas la clé contenu, par principe : domaine sans colonnes de
persistance).
"""

from typing import Protocol

from emule_indexer.domain.matching.engine import DecisionRecord, MatchDecision
from emule_indexer.domain.observation import FileObservation


class CatalogRepository(Protocol):
    """Contrat sync d'écriture du catalogue (append-only ; l'adapter signale, il ne décide pas).

    ``last_decision`` est une LECTURE (anti-redondance, spec orchestration §3) : le dernier
    verdict CONNU pour un hash, ou ``None`` si jamais décidé. Elle rend un
    :class:`DecisionRecord` (les 3 colonnes comparables ``target_id``/``rule_name``/``tier``)
    et NON un :class:`MatchDecision` : ``explanation`` n'est PAS persisté (spec data-model),
    le fabriquer vide serait un mensonge — la comparaison de verdict n'a besoin que de ces
    trois champs.
    """

    def record_observation(self, observation: FileObservation) -> None: ...

    def record_decision(self, ed2k_hash: str, decision: MatchDecision) -> None: ...

    def last_decision(self, ed2k_hash: str) -> DecisionRecord | None: ...
