"""Tests de ``get_listen_port`` / ``set_listen_port`` (port-sync High-ID, design §2.3/§4.2).

Idiome du reste de la suite EC : faux transport scripté (court-circuite le réseau) pour les
assertions sur les paquets ÉMIS + un round-trip RÉEL via ``FakeEcServer`` (vrais streams asyncio
+ vrai codec) pour prouver la (dé)sérialisation des tags imbriqués parent/enfant.
"""

import pytest

from emule_indexer.adapters.mule_ec import codes
from emule_indexer.adapters.mule_ec.client import AmuleEcClient
from emule_indexer.adapters.mule_ec.codec import (
    EcPacket,
    EcTag,
    empty_tag,
    encode_packet,
    string_tag,
    uint_tag,
)
from emule_indexer.adapters.mule_ec.errors import EcConnectError, EcProtocolError
from tests.adapters.mule_ec.ec_fakes import FakeEcServer

_PASSWORD = "secret123"


def _auth_replies(salt: int) -> list[bytes]:
    return [
        encode_packet(EcPacket(codes.EC_OP_AUTH_SALT, (uint_tag(codes.EC_TAG_PASSWD_SALT, salt),))),
        encode_packet(
            EcPacket(codes.EC_OP_AUTH_OK, (string_tag(codes.EC_TAG_SERVER_VERSION, "3.0.0"),))
        ),
    ]


class _ScriptedTransport:
    """Faux transport : rend des réponses SCRIPTÉES, capture les paquets envoyés."""

    def __init__(self, replies: list[EcPacket]) -> None:
        self._replies = replies
        self.sent: list[EcPacket] = []
        self.closed = False

    async def send_packet(self, packet: EcPacket) -> None:
        self.sent.append(packet)

    async def receive_packet(self) -> EcPacket:
        return self._replies.pop(0)

    async def close(self) -> None:
        self.closed = True


def _connected_client(transport: _ScriptedTransport) -> AmuleEcClient:
    client = AmuleEcClient("h", 4712, "pwd")
    client._transport = transport  # type: ignore[assignment]  # injecté (déjà connecté)
    return client


def _prefs_reply(tcp_port: int) -> EcPacket:
    """La RÉPONSE de GET_PREFERENCES : opcode SET_PREFERENCES (0x40, PIÈGE R3) + parent
    CONNECTIONS portant l'enfant TCP_PORT (et un UDP_PORT, présent côté amont)."""
    return EcPacket(
        codes.EC_OP_SET_PREFERENCES,
        (
            empty_tag(
                codes.EC_TAG_PREFS_CONNECTIONS,
                (
                    uint_tag(codes.EC_TAG_CONN_TCP_PORT, tcp_port),
                    uint_tag(codes.EC_TAG_CONN_UDP_PORT, tcp_port + 1),
                ),
            ),
        ),
    )


# ---------------------------------------------------------------- get_listen_port


@pytest.mark.asyncio
async def test_get_listen_port_reads_tcp_port_child() -> None:
    # La réponse porte l'opcode SET_PREFERENCES (PIÈGE R3, NON GET_PREFERENCES) ; le client lit
    # l'enfant EC_TAG_CONN_TCP_PORT sous le parent EC_TAG_PREFS_CONNECTIONS.
    transport = _ScriptedTransport([_prefs_reply(4662)])
    client = _connected_client(transport)
    port = await client.get_listen_port()
    assert port == 4662
    # La requête émise : GET_PREFERENCES avec le sélecteur EC_PREFS_CONNECTIONS.
    sent = transport.sent[0]
    assert sent.opcode == codes.EC_OP_GET_PREFERENCES
    selector = sent.find(codes.EC_TAG_SELECT_PREFS)
    assert selector is not None
    assert selector.int_value() == codes.EC_PREFS_CONNECTIONS


@pytest.mark.asyncio
async def test_get_listen_port_raises_when_connections_parent_is_missing() -> None:
    # Réponse conforme à l'opcode (0x40) mais SANS le parent EC_TAG_PREFS_CONNECTIONS → réponse
    # non conforme → EcProtocolError (la boucle la capte comme « EC indisponible » → backoff).
    reply = EcPacket(codes.EC_OP_SET_PREFERENCES, ())
    client = _connected_client(_ScriptedTransport([reply]))
    with pytest.raises(EcProtocolError, match="CONNECTIONS"):
        await client.get_listen_port()


@pytest.mark.asyncio
async def test_get_listen_port_raises_when_tcp_port_child_is_missing() -> None:
    # Parent présent MAIS sans l'enfant EC_TAG_CONN_TCP_PORT → EcProtocolError (2e branche).
    reply = EcPacket(
        codes.EC_OP_SET_PREFERENCES,
        (empty_tag(codes.EC_TAG_PREFS_CONNECTIONS, ()),),
    )
    client = _connected_client(_ScriptedTransport([reply]))
    with pytest.raises(EcProtocolError, match="TCP_PORT"):
        await client.get_listen_port()


@pytest.mark.asyncio
async def test_get_listen_port_unexpected_opcode_raises_protocol_error() -> None:
    # Un opcode INATTENDU (ni 0x40) → EcProtocolError via _request (R3 : si l'observation réelle
    # diffère, c'est ICI que l'expected serait ajusté).
    reply = EcPacket(codes.EC_OP_NOOP, ())
    client = _connected_client(_ScriptedTransport([reply]))
    with pytest.raises(EcProtocolError, match="attendu"):
        await client.get_listen_port()


@pytest.mark.asyncio
async def test_get_listen_port_on_disconnected_client_raises_connect_error() -> None:
    client = AmuleEcClient("h", 4712, "pwd")  # jamais connecté
    with pytest.raises(EcConnectError):
        await client.get_listen_port()


@pytest.mark.asyncio
async def test_get_listen_port_survives_a_real_codec_round_trip() -> None:
    # Round-trip RÉEL (FakeEcServer + vrais streams + vrai codec) : prouve que le parent
    # EC_TAG_PREFS_CONNECTIONS et ses enfants survivent à encode → socket → decode → lecture.
    reply = encode_packet(_prefs_reply(51820))
    async with FakeEcServer(_auth_replies(1) + [reply]) as server:
        client = AmuleEcClient("127.0.0.1", server.port, _PASSWORD, timeout=2.0)
        await client.connect()
        port = await client.get_listen_port()
        await client.close()
    assert port == 51820
    request = server.received[2]  # [0]/[1] = handshake ; [2] = GET_PREFERENCES
    assert request.opcode == codes.EC_OP_GET_PREFERENCES


# ---------------------------------------------------------------- set_listen_port


@pytest.mark.asyncio
async def test_set_listen_port_emits_connections_parent_with_tcp_and_udp() -> None:
    transport = _ScriptedTransport([EcPacket(codes.EC_OP_NOOP)])
    client = _connected_client(transport)
    await client.set_listen_port(51820)
    sent = transport.sent[0]
    assert sent.opcode == codes.EC_OP_SET_PREFERENCES
    parent = sent.find(codes.EC_TAG_PREFS_CONNECTIONS)
    assert parent is not None
    tcp = parent.find(codes.EC_TAG_CONN_TCP_PORT)
    udp = parent.find(codes.EC_TAG_CONN_UDP_PORT)
    assert tcp is not None and tcp.int_value() == 51820
    assert udp is not None and udp.int_value() == 51820  # TCP=UDP=N (design §4.2)


@pytest.mark.asyncio
async def test_set_listen_port_accepts_noop_reply() -> None:
    transport = _ScriptedTransport([EcPacket(codes.EC_OP_NOOP)])
    client = _connected_client(transport)
    await client.set_listen_port(4662)  # réponse EC_OP_NOOP → pas d'exception


@pytest.mark.asyncio
async def test_set_listen_port_unexpected_reply_opcode_raises_protocol_error() -> None:
    reply = EcPacket(codes.EC_OP_MISC_DATA, ())  # ni NOOP
    client = _connected_client(_ScriptedTransport([reply]))
    with pytest.raises(EcProtocolError, match="attendu"):
        await client.set_listen_port(4662)


@pytest.mark.asyncio
async def test_set_listen_port_on_disconnected_client_raises_connect_error() -> None:
    client = AmuleEcClient("h", 4712, "pwd")  # jamais connecté
    with pytest.raises(EcConnectError):
        await client.set_listen_port(4662)


@pytest.mark.asyncio
async def test_set_listen_port_survives_a_real_codec_round_trip() -> None:
    # Round-trip RÉEL : le parent CONNECTIONS porteur de TCP+UDP est encodé, transmis, et le
    # serveur le reçoit et le décode (preuve que le décalage wire parent/enfants tient).
    reply = encode_packet(EcPacket(codes.EC_OP_NOOP))
    async with FakeEcServer(_auth_replies(1) + [reply]) as server:
        client = AmuleEcClient("127.0.0.1", server.port, _PASSWORD, timeout=2.0)
        await client.connect()
        await client.set_listen_port(51820)
        await client.close()
    request = server.received[2]
    assert request.opcode == codes.EC_OP_SET_PREFERENCES
    parent = request.find(codes.EC_TAG_PREFS_CONNECTIONS)
    assert parent is not None
    tcp = parent.find(codes.EC_TAG_CONN_TCP_PORT)
    assert tcp is not None and tcp.int_value() == 51820
    received_child = parent.find(codes.EC_TAG_CONN_UDP_PORT)
    assert isinstance(received_child, EcTag)  # l'enfant UDP est bien présent dans la trame reçue
