from pathlib import Path

from download_verifier.check import verify_file


def test_existing_file_is_unverified_noop(tmp_path: Path) -> None:
    target = tmp_path / ("a" * 32)
    target.write_bytes(b"\x00\x01\x02")  # le verifier ne lit JAMAIS ces octets
    verdict, real_meta, checks = verify_file(target, {"target_id": "S2E062A"})
    assert verdict == "unverified"
    assert real_meta == {}
    assert checks == []


def test_missing_file_is_error(tmp_path: Path) -> None:
    verdict, real_meta, checks = verify_file(tmp_path / "absent", {})
    assert verdict == "error"
    assert real_meta == {}
    assert checks == []


def test_directory_is_error_not_unverified(tmp_path: Path) -> None:
    # une quarantaine "fichier" qui est en fait un répertoire n'est pas un fichier vérifiable.
    directory = tmp_path / "dir"
    directory.mkdir()
    verdict, _real_meta, _checks = verify_file(directory, {})
    assert verdict == "error"


def test_expected_is_ignored_in_noop(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_bytes(b"data")
    # même verdict quel que soit expected (le NO-OP ne l'exploite pas).
    assert verify_file(target, {})[0] == "unverified"
    assert verify_file(target, {"anything": 1})[0] == "unverified"
