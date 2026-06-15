"""Entrée du verifier : ``python -m download_verifier`` (spec verify §4 ; logging E-D2).

Bootstrap deux-temps : ``basicConfig(INFO)`` puis ``setLevel`` depuis le YAML d'observabilité
(``VERIFIER_CONFIG``) avant ``uvicorn.run``. Le dossier de quarantaine vient de ``QUARANTINE_DIR``
(lu par ``app.py`` à l'import)."""

import logging
import os
from collections.abc import Mapping
from pathlib import Path

import uvicorn

from download_verifier.obs_config import load_observability


def configure_logging(env: Mapping[str, str]) -> None:
    """Arme le logging (INFO).

    Si ``VERIFIER_CONFIG`` est présent, applique ensuite ``log_level`` du YAML.
    """
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger().setLevel(logging.INFO)
    config_path = env.get("VERIFIER_CONFIG")
    if config_path:
        log_level = load_observability(Path(config_path)).log_level
        logging.getLogger().setLevel(log_level)


def main() -> None:
    """Configure le logging puis sert l'app verifier (host/port depuis l'environnement)."""
    configure_logging(os.environ)
    uvicorn.run(
        "download_verifier.app:app",
        host=os.environ.get("VERIFIER_HOST", "127.0.0.1"),
        port=int(os.environ.get("VERIFIER_PORT", "8000")),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
