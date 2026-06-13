"""Entrée dev du verifier : ``python -m download_verifier`` (spec verify §4).

Lance uvicorn sur l'app Starlette. L'IMAGE Docker + le compose + le réseau ``internal: true``
sont Plan F ; ici c'est l'entrée locale/dev (et le support de l'e2e si lancé en socket). Le
dossier de quarantaine vient de ``QUARANTINE_DIR`` (lu par ``app.py`` à l'import).
"""

import os

import uvicorn


def main() -> None:
    """Sert l'app verifier (host/port depuis l'environnement, défauts dev)."""
    uvicorn.run(
        "download_verifier.app:app",
        host=os.environ.get("VERIFIER_HOST", "127.0.0.1"),
        port=int(os.environ.get("VERIFIER_PORT", "8000")),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
