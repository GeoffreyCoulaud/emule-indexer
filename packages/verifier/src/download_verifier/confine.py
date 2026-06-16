"""Ring noyau de l'enfant d'analyse : filtre seccomp-bpf par-enfant (blocklist).

Le ``Confiner`` installe un filtre seccomp ``ALLOW`` par défaut qui DENY un petit ensemble de
syscalls réseau/dangereux (cf. spec ring noyau §4) — réduit la surface d'attaque noyau d'un 0-day
ffprobe/clamscan et coupe le mouvement latéral intra-conteneur. Le filtre est HÉRITÉ par le
petit-fils (fork/exec sous ``no_new_privs``). Le ``Confiner`` est INJECTABLE : l'impl PROD installe
le vrai filtre via ``pyseccomp`` (``# pragma: no cover`` — couvert par analysis_integration) ; les
tests injectent un no-op. AUCUNE capability requise : ``no_new_privs`` est déjà posé par le
conteneur (``no-new-privileges:true``, compose.yaml) — voir spec §3.

Fail-open ASSUMÉ (spec §10) : un échec d'installation du ring (``no_new_privs`` non posé hors
conteneur, ``libseccomp`` absent, noyau sans seccomp) log un warning et continue SANS filtre — il
ne doit JAMAIS transformer un média sain en ``suspicious`` (seccomp est une couche
defense-in-depth, pas la seule barrière).
"""

import contextlib
import errno
import logging
from typing import Protocol

_LOG = logging.getLogger(__name__)

# Syscalls deny en ERRNO(EPERM) : l'appelant gère l'échec (moins de faux positifs que KILL).
# ``ptrace`` est traité à part (KILL_PROCESS — signal d'attaque univoque, spec §4).
_DENY_EPERM = (
    "socket",
    "socketcall",
    "connect",
    "bind",
    "listen",
    "accept",
    "accept4",
    "process_vm_readv",
    "process_vm_writev",
    "bpf",
    "userfaultfd",
)


class Confiner(Protocol):
    """Installe le ring noyau sur le process courant. Injecté pour les tests."""

    def __call__(self) -> None: ...


class ProdConfiner:
    """``Confiner`` de PROD : vrai filtre seccomp (couvert par analysis_integration)."""

    def __call__(self) -> None:  # pragma: no cover
        try:
            import pyseccomp

            filt = pyseccomp.SyscallFilter(pyseccomp.ALLOW)  # blocklist : allow par défaut
            for name in _DENY_EPERM:
                # syscall absent de cette arch (ex. socketcall sur x86-64) → OSError ignorée.
                with contextlib.suppress(OSError):
                    filt.add_rule(pyseccomp.ERRNO(errno.EPERM), name)
            filt.add_rule(pyseccomp.KILL_PROCESS, "ptrace")
            filt.load()  # applique au thread courant (no_new_privs déjà posé → pas de privilège)
        except (OSError, ImportError) as exc:
            # fail-open contrôlé : jamais un faux suspicious — on continue sans filtre (les autres
            # rings tiennent : internal:true, RO, rlimits, cap_drop).
            _LOG.warning("seccomp filter not installed (fail-open): %s", exc)
            return


class NoopConfiner:
    """``Confiner`` no-op : ne pose AUCUN filtre. Défaut quand le ring est désactivé/indispo."""

    def __call__(self) -> None:
        return None
