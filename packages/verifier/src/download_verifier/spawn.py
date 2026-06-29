"""Spawn de l'enfant d'analyse (spec analysis §4 — DA5/DA8/DA9), côté PARENT.

``run_analysis`` re-exec un enfant Python jetable par fichier (PAS ``os.fork``) : argv minimal,
cwd ``tempfile.mkdtemp()`` jetable (supprimé en ``finally`` même en cas d'exception), env EXPLICITE
minimal (on n'hérite PAS de ``os.environ`` — secrets/VPN ; on ne passe que QUARANTINE_DIR + la
config des checks + un PATH minimal). Le ``ChildRunner`` est INJECTABLE : l'impl PROD fait le vrai
``subprocess.Popen`` (``close_fds=True``, ``preexec_fn=_confine`` = rlimits + setsid,
timeout-kill du
groupe via ``killpg``) — ces lignes système sont ``# pragma: no cover`` (couvertes par
analysis_integration). Le mapping de l'issue (stdout/timeout/exit) est délégué à ``egress.parse``
(défensif, DA6). Le parent ne lit JAMAIS d'octets du fichier (DA8).
"""

import contextlib
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from typing import Protocol

from download_verifier import egress
from download_verifier.config import AnalysisConfig

_CHILD_MODULE = "download_verifier.analysis_child"
_MINIMAL_PATH = "/usr/local/bin:/usr/bin:/bin"
# Délai borné du reap post-timeout (sandbox-confinement#2) : un descendant compromis qui
# s'échappe via ``setsid()`` peut garder stdout ouvert (l'EOF n'arrive pas) → ``communicate()``
# bloquerait indéfiniment, gelant le worker (cf. l'event loop). On borne la fenêtre de reap
# et on bascule sur un kill ciblé + wait borné si nécessaire. Un orphelin « godille » reste
# possible mais ne nous bloque plus (cgroups borne son impact).
_REAP_TIMEOUT_S = 2.0


class ChildRunner(Protocol):
    """Exécute l'enfant et rend ``(returncode, stdout, timed_out)``. Injecté pour les tests."""

    def __call__(
        self, argv: Sequence[str], *, cwd: str, env: Mapping[str, str], timeout: float
    ) -> tuple[int, bytes, bool]: ...


class ProdChildRunner:
    """``ChildRunner`` de PROD : vrai subprocess confiné (couvert par analysis_integration)."""

    def __init__(self, cfg: AnalysisConfig) -> None:
        self._cfg = cfg

    def __call__(  # pragma: no cover
        self, argv: Sequence[str], *, cwd: str, env: Mapping[str, str], timeout: float
    ) -> tuple[int, bytes, bool]:
        proc = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            preexec_fn=self._confine,
        )
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # tuer le GROUPE (enfant + petit-fils ffprobe) ; race : si l'enfant est déjà
            # mort, getpgid lève ProcessLookupError → absorbée.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            # Fermer le read-end PARENT du pipe stdout (sandbox-confinement#2) : un
            # descendant qui a échappé via setsid garde son write-end ouvert → l'EOF
            # n'arrive jamais → ``communicate()`` boucle. En coupant côté parent, on
            # se libère ; le descendant écrira dans un pipe cassé (SIGPIPE/EPIPE).
            if proc.stdout is not None:
                proc.stdout.close()
            try:
                proc.wait(timeout=_REAP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                # Dernier ressort : SIGKILL ciblé + wait borné. Si même cela échoue,
                # l'enfant reste zombie (extrêmement improbable après killpg+kill) — on
                # se libère quand même, cgroups borne l'orphelin éventuel.
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=_REAP_TIMEOUT_S)
            return 0, b"", True
        return proc.returncode, stdout, False

    def _confine(self) -> None:  # pragma: no cover
        os.setsid()  # groupe de process dédié → on tue l'enfant ET son petit-fils ffprobe
        cfg = self._cfg
        resource.setrlimit(resource.RLIMIT_CPU, (cfg.rlimit_cpu_s, cfg.rlimit_cpu_s))
        resource.setrlimit(resource.RLIMIT_AS, (cfg.rlimit_as_bytes, cfg.rlimit_as_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (cfg.rlimit_fsize_bytes, cfg.rlimit_fsize_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (cfg.rlimit_nproc, cfg.rlimit_nproc))
        resource.setrlimit(resource.RLIMIT_NOFILE, (cfg.rlimit_nofile, cfg.rlimit_nofile))
        # pas de core dump : un crash de l'enfant/ffprobe ne doit pas écrire d'octets du
        # fichier hostile dans le cwd (DA8).
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_analysis(
    ed2k_hash: str, cfg: AnalysisConfig, runner: ChildRunner
) -> tuple[str, dict[str, object], list[object], egress.ChildOutcome]:
    """Spawne l'enfant ; rend ``(verdict, real_meta, checks, outcome)`` (DA6 + observability#2).

    ``outcome`` est la CATÉGORIE TECHNIQUE de l'issue (``ok``/``timeout``/``nonzero_exit``/
    ``egress_overflow``/``malformed``), exposée en métrique côté ``app.py`` — orthogonale au
    verdict métier. Permet en incident de masse de voir la cause derrière une montée de
    ``suspicious`` (sans cela, les opérateurs n'ont qu'un agrégat aveugle).
    """
    argv = [sys.executable, "-m", _CHILD_MODULE, ed2k_hash]
    scratch = tempfile.mkdtemp(prefix="analysis-")
    try:
        returncode, stdout, timed_out = runner(
            argv, cwd=scratch, env=_minimal_env(cfg), timeout=cfg.timeout_s
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    verdict, real_meta, checks = egress.parse(stdout, returncode, timed_out, cfg)
    outcome = egress.classify_outcome(stdout, returncode, timed_out, cfg)
    return verdict, real_meta, checks, outcome


def _minimal_env(cfg: AnalysisConfig) -> dict[str, str]:
    """Env EXPLICITE minimal pour l'enfant (DA8) — ne fuit JAMAIS ``os.environ``."""
    return {
        "QUARANTINE_DIR": cfg.quarantine_dir,
        "ENABLED_CHECKS": ",".join(cfg.enabled_checks),
        "FFPROBE_PATH": cfg.ffprobe_path,
        "CLAMSCAN_PATH": cfg.clamscan_path,
        "CLAMAV_DB_DIR": cfg.clamav_db_dir,
        "HEADER_BYTES": str(cfg.header_bytes),
        "ANALYSIS_TIMEOUT_S": str(cfg.timeout_s),
        # l'enfant re-résout sa config depuis l'env : on lui transmet l'état du ring noyau.
        "SECCOMP_ENABLED": "1" if cfg.seccomp_enabled else "0",
        "PATH": _MINIMAL_PATH,
    }
