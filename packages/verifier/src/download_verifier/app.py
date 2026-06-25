"""App Starlette du verifier (spec verify §4 — DÉCISION DV1/DV2).

``POST /verify {hash, expected}`` → ``{verdict, real_meta, checks}`` : validation STRICTE et
BORNÉE (corps lu en bytes, taille plafonnée AVANT parse → 400 ; hash canonique exigé pour ne
jamais sortir du dossier de quarantaine — pas de traversal) ; délègue à ``check.verify_file``.
``GET /health`` → 200 (le crawler fail-fast au démarrage si ce health-check échoue, §7).

Stateless / no-DB / no-domain / no-Internet (spec §4) : ne lit que ``quarantine/<hash>`` en RO.
Le dossier de quarantaine vient de la config du service (``QUARANTINE_DIR`` env, défaut
``/quarantine``). ``build_app(quarantine_dir)`` est la fabrique testable ; ``app`` (module-level)
est l'instance que ``uvicorn`` charge par chemin d'import (``download_verifier.app:app``).
"""

import json
import logging
import os
import re
import time
from pathlib import Path

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from download_verifier.check import verify_file
from download_verifier.config import AnalysisConfig
from download_verifier.metrics import VerifierMetrics

_logger = logging.getLogger("download_verifier.app")

# Hash eD2k canonique (32 hex minuscules) : la SEULE forme acceptée → jamais de traversal hors
# du dossier de quarantaine (un "../" ou un "/" ne matche pas et donne 400).
_CANONICAL_HASH_RE = re.compile(r"[0-9a-f]{32}\Z")

# Corps borné : un /verify légitime est minuscule ({hash, expected}). 64 Kio est généreux et
# protège d'un corps illimité chargé en mémoire (parsing défensif côté service aussi, §8).
_MAX_BODY_BYTES = 65536


def _bad_request(metrics: VerifierMetrics, detail: str) -> JSONResponse:
    metrics.observe_response(400)
    return JSONResponse({"error": detail}, status_code=400)


async def verify_endpoint(request: Request) -> JSONResponse:
    """``POST /verify`` : valide (strict + borné), analyse (enfant confiné, DA6), rend le résultat.

    Le NO-OP n'existe plus : l'analyse spawne un enfant confiné (``check.verify_file`` → DA6).

    Instrumentation (observability#2/#3) : ``responses{status}`` est incrémenté pour CHAQUE
    sortie (200/400/500) — ``observe`` historique ne voyait que les 200. ``child_outcome``
    capture la CAUSE technique de l'issue du child (timeout, exit ≠ 0, overflow, JSON cassé,
    OK) — orthogonale au verdict métier.
    """
    metrics: VerifierMetrics = request.app.state.metrics
    try:
        raw = await request.body()
        if len(raw) > _MAX_BODY_BYTES:
            return _bad_request(metrics, "corps trop volumineux")
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError, RecursionError):
            # RecursionError : corps sous le cap d'octets mais trop profondément imbriqué
            # (RecursionError est un RuntimeError, pas un ValueError) → 400 propre, jamais 500.
            return _bad_request(metrics, "JSON invalide")
        if not isinstance(payload, dict):
            return _bad_request(metrics, "objet JSON attendu")
        ed2k_hash = payload.get("hash")
        if not isinstance(ed2k_hash, str) or _CANONICAL_HASH_RE.fullmatch(ed2k_hash) is None:
            return _bad_request(metrics, "hash canonique requis (32 hex minuscules)")
        expected = payload.get("expected", {})
        if not isinstance(expected, dict):
            return _bad_request(metrics, "expected doit être un objet")
        config: AnalysisConfig = request.app.state.config
        start = time.monotonic()
        # verify_file est SYNCHRONE et bloquant (spawn d'un enfant + communicate jusqu'au timeout) :
        # l'exécuter dans un thread libère l'event loop, qui continue de servir /health et
        # /metrics pendant l'analyse (sinon le conteneur flappe en unhealthy —
        # sandbox-confinement#0).
        verdict, real_meta, checks, outcome = await run_in_threadpool(
            verify_file, _quarantine_dir(request) / ed2k_hash, expected, cfg=config
        )
        metrics.observe(verdict, time.monotonic() - start)
        if outcome is not None:
            # ``outcome`` ne vit que si un child a tourné : verify_file court-circuite
            # (fichier absent, symlink, type non régulier → ``error``) rend None et on n'a
            # PAS d'issue technique à classer.
            metrics.observe_child_outcome(outcome)
        _logger.info("verify hash=%s → verdict=%s outcome=%s", ed2k_hash, verdict, outcome)
        metrics.observe_response(200)
        return JSONResponse({"verdict": verdict, "real_meta": real_meta, "checks": checks})
    except Exception:
        # Filet 500 (observability#3) : tout chemin imprévu (mkdtemp sur FS plein, etc.) est
        # compté avant que Starlette ne génère sa réponse 500 par défaut. On relève pour que
        # le middleware ASGI standard fasse son travail.
        metrics.observe_response(500)
        raise


async def health_endpoint(request: Request) -> JSONResponse:
    """``GET /health`` → 200 (vivacité du service ; gate full-mode du crawler, §7)."""
    return JSONResponse({"status": "ok"})


async def metrics_endpoint(request: Request) -> Response:
    """``GET /metrics`` : exposition Prometheus du registre dédié de l'app."""
    metrics: VerifierMetrics = request.app.state.metrics
    return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)


def _quarantine_dir(request: Request) -> Path:
    """Dossier de quarantaine injecté dans l'état de l'app (``build_app``)."""
    directory: Path = request.app.state.quarantine_dir
    return directory


def build_app(config: AnalysisConfig) -> Starlette:
    """Fabrique l'app Starlette à partir d'une config DÉJÀ résolue/validée (testable in-process).

    La config (rlimits, timeout, checks, quarantine_dir) est résolue UNE fois en amont et stockée
    dans ``state`` : ``verify_endpoint`` l'injecte à ``verify_file`` sans re-lire l'environnement
    par requête (cf. error-boundary#0). Le dossier de quarantaine en découle (``quarantine_dir``).
    """
    application = Starlette(
        routes=[
            Route("/verify", verify_endpoint, methods=["POST"]),
            Route("/health", health_endpoint, methods=["GET"]),
            Route("/metrics", metrics_endpoint, methods=["GET"]),
        ]
    )
    application.state.config = config
    application.state.quarantine_dir = Path(config.quarantine_dir)
    application.state.metrics = VerifierMetrics()
    return application


# Résolution/validation de la config AU BOOT : une env invalide (RLIMIT négatif, check inconnu,
# planchers violés) lève ici, à l'import du module → uvicorn ne démarre pas (fail-fast §8/E-D13),
# au lieu d'un 500 « transitoire » par requête menant au dead-letter.
app = build_app(AnalysisConfig.from_env(os.environ))
