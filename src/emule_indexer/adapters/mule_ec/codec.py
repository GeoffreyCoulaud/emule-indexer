"""Codec EC PUR et SYNCHRONE : bytes ↔ arbre de tags (cf. docs/reference/ec-protocol.md §1-§3).

GÉNÉRIQUE : encode/décode N'IMPORTE QUEL paquet EC (format conteneur récursif). AUCUNE I/O.
Les noms de tags manipulés ici sont LOGIQUES ; le décalage wire ``(nom << 1) | enfants``
(réf. §2, piège 2) est enfermé dans l'encodage/décodage (Tasks 6-8).
"""

from dataclasses import dataclass
from typing import Final

from emule_indexer.adapters.mule_ec import codes
from emule_indexer.adapters.mule_ec.errors import EcProtocolError

# Largeur (octets) de chaque type entier — réf. §3. Ordre croissant : uint_tag prend le 1er
# qui suffit (« encodé au plus court », InitInt, ECTag.cpp:207-221).
INT_WIDTHS: Final[dict[int, int]] = {
    codes.EC_TAGTYPE_UINT8: 1,
    codes.EC_TAGTYPE_UINT16: 2,
    codes.EC_TAGTYPE_UINT32: 4,
    codes.EC_TAGTYPE_UINT64: 8,
}


@dataclass(frozen=True)
class EcTag:
    """Un tag EC : nom LOGIQUE (déjà ``>> 1``), type, valeur propre, sous-tags."""

    name: int
    tag_type: int
    value: bytes = b""
    children: tuple["EcTag", ...] = ()

    def find(self, name: int) -> "EcTag | None":
        """Premier enfant portant ce nom logique, ou ``None``."""
        for child in self.children:
            if child.name == name:
                return child
        return None

    def int_value(self) -> int:
        """Valeur entière à LARGEUR VARIABLE (réf. §9 piège 4 — équivalent ``GetInt()``)."""
        if self.tag_type not in INT_WIDTHS or len(self.value) != INT_WIDTHS[self.tag_type]:
            raise EcProtocolError(f"tag 0x{self.name:04X} : pas un entier EC valide")
        return int.from_bytes(self.value, "big")

    def string_value(self) -> str:
        """Valeur chaîne : UTF-8 + NUL final inclus dans TAGLEN (réf. §3, piège 10).

        Décodage ``errors="replace"`` : un nom de fichier hostile ne crashe jamais
        (les octets bruts restent disponibles dans ``value``).
        """
        if self.tag_type != codes.EC_TAGTYPE_STRING or not self.value.endswith(b"\x00"):
            raise EcProtocolError(f"tag 0x{self.name:04X} : pas une chaîne EC valide")
        return self.value[:-1].decode("utf-8", errors="replace")

    def ipv4_value(self) -> str:
        """Valeur IPV4 (réf. §3) : 4 octets d'IP + port uint16 big-endian → ``"a.b.c.d:port"``."""
        if self.tag_type != codes.EC_TAGTYPE_IPV4 or len(self.value) != 6:
            raise EcProtocolError(f"tag 0x{self.name:04X} : pas un IPv4 EC valide")
        ip = ".".join(str(byte) for byte in self.value[:4])
        port = int.from_bytes(self.value[4:6], "big")
        return f"{ip}:{port}"


@dataclass(frozen=True)
class EcPacket:
    """Un paquet EC : opcode + tags de premier niveau (le paquet est un pseudo-tag, réf. §2)."""

    opcode: int
    tags: tuple[EcTag, ...] = ()

    def find(self, name: int) -> EcTag | None:
        """Premier tag de premier niveau portant ce nom logique, ou ``None``."""
        for tag in self.tags:
            if tag.name == name:
                return tag
        return None


def uint_tag(name: int, value: int, children: tuple[EcTag, ...] = ()) -> EcTag:
    """Tag entier encodé AU PLUS COURT (réf. §3 : InitInt)."""
    if value < 0:
        raise EcProtocolError(f"entier EC négatif : {value}")
    for tag_type, width in INT_WIDTHS.items():
        if value < 1 << (8 * width):
            return EcTag(name, tag_type, value.to_bytes(width, "big"), children)
    raise EcProtocolError(f"entier trop grand pour EC : {value}")


def string_tag(name: int, text: str, children: tuple[EcTag, ...] = ()) -> EcTag:
    """Tag chaîne : UTF-8 + NUL final, INCLUS dans la longueur (réf. §3, piège 10)."""
    return EcTag(name, codes.EC_TAGTYPE_STRING, text.encode("utf-8") + b"\x00", children)


def hash16_tag(name: int, digest: bytes, children: tuple[EcTag, ...] = ()) -> EcTag:
    """Tag hash : exactement 16 octets bruts, MSB first (réf. §3)."""
    if len(digest) != 16:
        raise EcProtocolError(f"hash EC : 16 octets attendus, reçu {len(digest)}")
    return EcTag(name, codes.EC_TAGTYPE_HASH16, digest, children)


def empty_tag(name: int, children: tuple[EcTag, ...] = ()) -> EcTag:
    """Tag vide (CECEmptyTag, réf. §2) : type CUSTOM, TAGLEN 0 — forme des tags ``CAN_*``."""
    return EcTag(name, codes.EC_TAGTYPE_CUSTOM, b"", children)
