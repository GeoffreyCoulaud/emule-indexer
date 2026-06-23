import stat
from pathlib import Path

import pytest

from emule_indexer.adapters.quarantine_fs import FilesystemQuarantine


def test_promote_moves_the_file_to_quarantine_by_hash(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    source = staging / "Keroro 062A.avi"
    source.write_bytes(b"\x00\x01\x02")  # le crawler ne lit JAMAIS ces octets
    adapter = FilesystemQuarantine(quarantine)

    adapter.promote(source, "a" * 32)

    moved = quarantine / ("a" * 32)
    assert not source.exists()  # rename atomique : la source a disparu
    assert moved.exists()
    assert moved.stat().st_size == 3


def test_promote_never_sets_executable_bits(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    source = staging / "x.bin"
    source.write_bytes(b"data")
    FilesystemQuarantine(quarantine).promote(source, "b" * 32)
    mode = (quarantine / ("b" * 32)).stat().st_mode
    assert not (mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def test_promote_missing_source_raises(tmp_path: Path) -> None:
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    adapter = FilesystemQuarantine(quarantine)
    with pytest.raises(FileNotFoundError):
        adapter.promote(tmp_path / "absent.part", "c" * 32)


def test_promote_is_idempotent_when_source_already_consumed(tmp_path: Path) -> None:
    # Régression logic-download#0 : os.replace CONSOMME la source. Si une étape POST-promote
    # (enqueue_verification / set_state) échoue et que la boucle retente au cycle suivant,
    # promote est rappelé avec la source DÉJÀ consommée alors que quarantine/<hash> est en
    # place. Ce re-promote doit être un NO-OP idempotent (le fichier EST promu), pas lever —
    # sinon le fichier reste bloqué en completed pour toujours, jamais vérifié.
    staging = tmp_path / "staging"
    staging.mkdir()
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    source = staging / "Keroro 062A.avi"
    source.write_bytes(b"\x00\x01\x02")
    adapter = FilesystemQuarantine(quarantine)
    adapter.promote(source, "a" * 32)  # 1re promotion : source consommée par le rename
    moved = quarantine / ("a" * 32)
    assert moved.exists() and not source.exists()

    adapter.promote(source, "a" * 32)  # retry : source absente, cible présente → no-op

    assert moved.exists()
    assert moved.read_bytes() == b"\x00\x01\x02"  # cible intacte, non corrompue
