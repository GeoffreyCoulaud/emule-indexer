"""Entrée du webui : ``python -m catalog_webui`` (spec webui — Task 12).

Lit la configuration depuis l'environnement, résout les chemins templates/static
relatifs au paquet, construit l'application via ``build_app`` et lance uvicorn.

Variables d'environnement :
- ``CATALOG_DB``     : chemin vers catalog.db (requis)
- ``LOCAL_DB``       : chemin vers local.db (requis)
- ``TARGETS_CONFIG`` : chemin vers targets.yaml (requis)
- ``MATCHER_CONFIG`` : chemin vers matcher.yaml (requis)
- ``WEBUI_HOST``     : adresse d'écoute (défaut : 127.0.0.1)
- ``WEBUI_PORT``     : port d'écoute (défaut : 8080)
"""

import os
from collections.abc import Mapping
from pathlib import Path

import uvicorn

from catalog_webui.composition.app import build_app


def _require_env(env: Mapping[str, str], key: str) -> str:
    """Retourne ``env[key]`` ou lève ``RuntimeError`` avec le nom de la variable manquante."""
    value = env.get(key)
    if value is None:
        raise RuntimeError(f"{key} requis")
    return value


def main() -> None:
    """Configure et lance l'application webui (host/port/chemins depuis l'environnement)."""
    env = os.environ

    catalog_db = Path(_require_env(env, "CATALOG_DB"))
    local_db = Path(_require_env(env, "LOCAL_DB"))
    targets = Path(_require_env(env, "TARGETS_CONFIG"))
    matcher = Path(_require_env(env, "MATCHER_CONFIG"))

    host = env.get("WEBUI_HOST", "127.0.0.1")
    port = int(env.get("WEBUI_PORT", "8080"))

    templates_dir = Path(__file__).parent / "adapters" / "templates"
    static_dir = Path(__file__).parent / "adapters" / "static"

    app = build_app(
        catalog_db=catalog_db,
        local_db=local_db,
        targets=targets,
        matcher=matcher,
        templates_dir=templates_dir,
        static_dir=static_dir,
    )

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
