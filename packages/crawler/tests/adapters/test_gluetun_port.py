"""Tests de ``GluetunPortReader`` (port-sync, design §3.2). Parsing DÉFENSIF : tout échec → None.

Idiome ``test_verifier_http.py`` : httpx ``MockTransport`` fabrique chaque réponse ; on couvre
une branche par cas du tableau §3.2 (les deux côtés de chaque conditionnel).
"""

from collections.abc import Callable

import httpx
import pytest

from emule_indexer.adapters.gluetun_port import GluetunPortReader


def _reader_with_handler(
    handler: Callable[[httpx.Request], httpx.Response],
) -> GluetunPortReader:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://gluetun:8000")
    return GluetunPortReader(client)


@pytest.mark.asyncio
async def test_live_port_is_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/portforward"  # route confirmée via doc gluetun (R2)
        return httpx.Response(200, json={"port": 51820})

    reader = _reader_with_handler(handler)
    try:
        assert await reader.forwarded_port() == 51820
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_zero_port_is_none() -> None:
    # {"port": 0} = PF pas encore négocié (§3.4) → None (« pas prêt », pas une erreur).
    reader = _reader_with_handler(lambda r: httpx.Response(200, json={"port": 0}))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_negative_port_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(200, json={"port": -1}))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_non_integer_port_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(200, json={"port": "x"}))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_boolean_port_is_none() -> None:
    # bool est un sous-type d'int en Python : True ne doit PAS passer pour un port valide.
    reader = _reader_with_handler(lambda r: httpx.Response(200, json={"port": True}))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_missing_port_key_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(200, json={"other": 1}))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_non_dict_json_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(200, json=[1, 2, 3]))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_non_json_body_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(200, content=b"<html>nope</html>"))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_404_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(404))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_500_is_none() -> None:
    reader = _reader_with_handler(lambda r: httpx.Response(500, text="boom"))
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_connect_error_is_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    reader = _reader_with_handler(handler)
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_timeout_is_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow")

    reader = _reader_with_handler(handler)
    try:
        assert await reader.forwarded_port() is None
    finally:
        await reader.aclose()


@pytest.mark.asyncio
async def test_aclose_closes_client() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"port": 1}))
    client = httpx.AsyncClient(transport=transport, base_url="http://gluetun:8000")
    reader = GluetunPortReader(client)
    await reader.aclose()
    assert client.is_closed is True
