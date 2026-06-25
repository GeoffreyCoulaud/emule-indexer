"""Fabrique de l'application Starlette (spec webui — Task 11).

``build_app`` câble les adaptateurs (SQLite, YAML, templates) et enregistre
toutes les routes. Les handlers sont des fermetures capturant les dépendances
— pas de ``app.state``.
"""

import contextlib
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.types import ASGIApp

from catalog_matching.ed2k_link import build_ed2k_link
from catalog_webui.adapters.catalog_read import PAGE_SIZE, CatalogReader
from catalog_webui.adapters.db import open_ro
from catalog_webui.adapters.local_read import LocalReader
from catalog_webui.adapters.matching_read import MatchingExplainer
from catalog_webui.adapters.targets_read import load_targets
from catalog_webui.domain.coverage import coverage_for
from catalog_webui.domain.format import short_hash
from catalog_webui.domain.views import (
    FileDetailDisplay,
    FileRow,
    FileRowDisplay,
    PageNav,
    SchedulerEntry,
    TargetCoverageRow,
)


def _to_display_rows(file_rows: Iterable[FileRow]) -> list[FileRowDisplay]:
    """Convertit les lignes catalogue en view-models ``FileRowDisplay``. Dédup partagée par
    ``handle_files`` et ``handle_target`` (code-smell#3 — sans ça, toute évolution de colonne
    devait être faite à deux endroits)."""
    return [
        FileRowDisplay(
            ed2k_hash=row.ed2k_hash,
            short_hash=short_hash(row.ed2k_hash),
            filename=row.filename,
            size_bytes=row.size_bytes,
            source_count=row.source_count,
            last_seen=row.last_seen,
            target_id_display=row.target_id if row.target_id is not None else "—",
            tier_display=row.tier if row.tier is not None else "—",
            verdict_display=row.last_verdict if row.last_verdict is not None else "—",
            ed2k_link=build_ed2k_link(row.filename, row.size_bytes, row.ed2k_hash),
        )
        for row in file_rows
    ]


def _normalize(raw: str | None) -> str | None:
    """Normalise un param de query : whitespace strippé, vide ⇒ ``None``. Sans ça, un select
    HTML à option vide envoie ``?target=`` → ``""`` → ``dec.target_id = ''`` ne matche RIEN
    → 0 résultats sans message (webui-security#0/filtres)."""
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _page_nav(page: int, n_rows: int, base_path: str, query: dict[str, str]) -> PageNav:
    """Précalcule les liens prev/next pour une page (W-D8 : view-model, pas de logique
    template). On n'a pas le compte total → ``next`` est rendu quand la page est PLEINE
    (heuristique standard ; au pire un clic next renvoie une page vide)."""
    prev_url: str | None = None
    next_url: str | None = None
    if page > 1:
        prev = dict(query)
        prev["page"] = str(page - 1)
        prev_url = f"{base_path}?{urlencode(prev)}"
    if n_rows >= PAGE_SIZE:
        nxt = dict(query)
        nxt["page"] = str(page + 1)
        next_url = f"{base_path}?{urlencode(nxt)}"
    return PageNav(page=page, prev_url=prev_url, next_url=next_url)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """En-têtes de sécurité defense-en-profondeur (webui-security#3).

    L'autoescape Jinja2 neutralise déjà XSS et le bind 127.0.0.1 limite l'exposition par
    défaut. CSP ``default-src 'self'`` empêche un fragment injecté de charger un asset
    externe (filet sous l'autoescape). ``X-Content-Type-Options: nosniff`` empêche un
    navigateur de re-deviner le type MIME. ``Referrer-Policy: no-referrer`` évite de fuiter
    le hash eD2k à un éventuel asset tiers (paranoïa cohérente avec l'esprit du projet).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


def build_app(
    *,
    catalog_db: Path,
    local_db: Path,
    targets: Path,
    matcher: Path,
    templates_dir: Path,
    static_dir: Path,
) -> Starlette:
    """Construit et retourne l'application Starlette câblée."""

    templates = Jinja2Templates(directory=templates_dir)
    target_segments = load_targets(targets)
    explainer = MatchingExplainer(matcher_yaml=matcher, targets_yaml=targets)

    # Titre par target_id (accès rapide)
    _title_by_id = {seg.target_id: seg.title for seg in target_segments}

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def handle_health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def handle_dashboard(request: Request) -> Response:
        with contextlib.closing(open_ro(catalog_db)) as catalog_conn:
            catalog = CatalogReader(catalog_conn)
            coverage_data = catalog.target_coverage()
        with contextlib.closing(open_ro(local_db)) as local_conn:
            local = LocalReader(local_conn)
            node_state = local.node_state()

        rows = []
        for seg in target_segments:
            decisions = coverage_data.get(seg.target_id, [])
            cov = coverage_for(seg.target_id, decisions)
            rows.append(
                TargetCoverageRow(
                    target_id=seg.target_id,
                    title=seg.title,
                    status=cov.status,
                    best_tier_display=cov.best_tier if cov.best_tier is not None else "—",
                    file_count=cov.file_count,
                )
            )

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"rows": rows, "node_state": node_state},
        )

    async def handle_files(request: Request) -> Response:
        # Filtres : ``param.strip() or None`` (webui-security#0) — un select à option vide
        # envoyait ``?target=`` (chaîne vide) qui matchait 0 résultat sans message.
        target_param = _normalize(request.query_params.get("target"))
        tier_param = _normalize(request.query_params.get("tier"))
        verdict_param = _normalize(request.query_params.get("verdict"))
        query_param = _normalize(request.query_params.get("q"))
        page_raw = request.query_params.get("page", "1")
        try:
            page = int(page_raw)
        except ValueError:
            page = 1
        # ``max(1, ...)`` (webui-security#2) — sans ça ``?page=0`` produisait OFFSET=-50 que
        # SQLite traite comme 0 → page=0 et page=1 rendaient la même page silencieusement.
        page = max(1, page)

        with contextlib.closing(open_ro(catalog_db)) as catalog_conn:
            catalog = CatalogReader(catalog_conn)
            file_rows = catalog.list_files(
                target=target_param,
                tier=tier_param,
                verdict=verdict_param,
                query=query_param,
                page=page,
            )

        display_rows = _to_display_rows(file_rows)
        # Liens prev/next précalculés (webui-security#1 — sans cela, au-delà de 50 fichiers les
        # résultats étaient inaccessibles sauf à forger ``?page=N`` à la main).
        nav_query = {
            k: v
            for k, v in {
                "target": target_param,
                "tier": tier_param,
                "verdict": verdict_param,
                "q": query_param,
            }.items()
            if v is not None
        }
        nav = _page_nav(page, len(display_rows), "/files", nav_query)
        return templates.TemplateResponse(
            request,
            "files.html",
            {"rows": display_rows, "nav": nav},
        )

    async def handle_file_detail(request: Request) -> Response:
        ed2k_hash: str = request.path_params["ed2k_hash"]

        with contextlib.closing(open_ro(catalog_db)) as catalog_conn:
            catalog = CatalogReader(catalog_conn)
            detail = catalog.file_detail(ed2k_hash)

        if detail is None:
            return templates.TemplateResponse(request, "404.html", {}, status_code=404)

        # Précalcul du lien eD2k depuis la dernière observation
        last_obs = detail.observations[-1] if detail.observations else None
        if last_obs is not None:
            link = build_ed2k_link(last_obs.filename, last_obs.size_bytes, detail.ed2k_hash)
        else:
            link = ""

        # Explication depuis la config courante
        explanation_target_id: str | None = None
        explanation_rules_fired: tuple[str, ...] = ()
        explanation_tokens_matched: tuple[str, ...] = ()
        explanation_notes: tuple[str, ...] = ()

        if detail.decision is not None and last_obs is not None:
            explanation = explainer.explain(
                filename=last_obs.filename,
                size_bytes=last_obs.size_bytes,
                media_length_sec=last_obs.media_length_sec,
                bitrate_kbps=last_obs.bitrate_kbps,
                target_id=detail.decision.target_id,
            )
            if explanation is not None:
                explanation_target_id = explanation.target_id
                explanation_rules_fired = explanation.rules_fired
                explanation_tokens_matched = explanation.tokens_matched
                explanation_notes = ("Évalué contre la configuration actuelle",)

        decisions = (detail.decision,) if detail.decision is not None else ()

        display = FileDetailDisplay(
            ed2k_hash=detail.ed2k_hash,
            size_bytes=detail.size_bytes,
            aich_hash_display=detail.aich_hash if detail.aich_hash is not None else "—",
            observations=detail.observations,
            decisions=decisions,
            verifications=detail.verifications,
            ed2k_link=link,
            explanation_target_id=explanation_target_id,
            explanation_rules_fired=explanation_rules_fired,
            explanation_tokens_matched=explanation_tokens_matched,
            explanation_notes=explanation_notes,
        )

        return templates.TemplateResponse(
            request,
            "file_detail.html",
            {"file": display, "title_by_id": _title_by_id},
        )

    async def handle_target(request: Request) -> Response:
        target_id: str = request.path_params["target_id"]
        with contextlib.closing(open_ro(catalog_db)) as catalog_conn:
            catalog = CatalogReader(catalog_conn)
            file_rows = catalog.list_files(
                target=target_id,
                tier=None,
                verdict=None,
                query=None,
                page=1,
            )

        display_rows = _to_display_rows(file_rows)
        # Pas de pagination ici (vue cible : on en attend peu) — nav vide.
        nav = PageNav(page=1, prev_url=None, next_url=None)
        return templates.TemplateResponse(
            request,
            "files.html",
            {"rows": display_rows, "nav": nav},
        )

    async def handle_node(request: Request) -> Response:
        with contextlib.closing(open_ro(local_db)) as local_conn:
            local = LocalReader(local_conn)
            node_state = local.node_state()

        scheduler_entries = tuple(
            SchedulerEntry(key=k, value=v) for k, v in node_state.scheduler.items()
        )

        return templates.TemplateResponse(
            request,
            "node.html",
            {"node_state": node_state, "scheduler_entries": scheduler_entries},
        )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    return Starlette(
        routes=[
            Route("/health", handle_health),
            Route("/", handle_dashboard),
            Route("/files", handle_files),
            Route("/files/{ed2k_hash}", handle_file_detail),
            Route("/targets/{target_id}", handle_target),
            Route("/node", handle_node),
            Mount("/static", StaticFiles(directory=static_dir)),
        ],
        middleware=[Middleware(_SecurityHeadersMiddleware)],
    )
