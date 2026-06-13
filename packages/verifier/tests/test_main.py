import pytest
import uvicorn

import download_verifier.__main__ as entry


def test_main_invokes_uvicorn_with_app_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def _fake_run(target: object, **kwargs: object) -> None:
        calls.append((target, kwargs))

    monkeypatch.setattr(uvicorn, "run", _fake_run)
    monkeypatch.setenv("VERIFIER_HOST", "0.0.0.0")
    monkeypatch.setenv("VERIFIER_PORT", "9100")
    entry.main()
    assert calls == [("download_verifier.app:app", {"host": "0.0.0.0", "port": 9100})]
