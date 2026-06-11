"""Hiérarchie d'erreurs de l'adapter EC (cf. spec EC-adapter §6).

L'adapter SIGNALE, il ne décide pas : pas de retry caché, pas de crash silencieux. Cette
hiérarchie permet à l'appelant (plan C) de distinguer « amuled est down » (EcConnectError)
de « ma config est fausse » (EcAuthError), une trame illisible (EcProtocolError) d'un échec
applicatif proprement signalé par le daemon (EcFailureError).
"""


class EcError(Exception):
    """Base de toutes les erreurs de l'adapter EC."""


class EcConnectError(EcError):
    """TCP refusé, connexion perdue, ou opération sans connexion établie."""


class EcAuthError(EcError):
    """Authentification refusée (mot de passe ou version de protocole)."""


class EcProtocolError(EcError):
    """Trame malformée ou réponse inattendue (l'entrée réseau est non fiable)."""


class EcTimeoutError(EcError):
    """Délai dépassé (lecture réseau ou établissement de connexion)."""


class EcFailureError(EcError):
    """Échec applicatif signalé par le daemon (EC_OP_FAILED) ; porte son message."""
