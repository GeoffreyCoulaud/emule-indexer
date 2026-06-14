import pytest

from download_verifier.config import AnalysisConfig


def test_from_env_uses_defaults_when_empty() -> None:
    cfg = AnalysisConfig.from_env({})
    assert cfg.enabled_checks == ("type_sniff", "ffprobe")
    assert cfg.ffprobe_path == "ffprobe"
    assert cfg.timeout_s == 30.0
    assert cfg.rlimit_cpu_s == 20
    assert cfg.rlimit_as_bytes == 512 * 1024 * 1024
    assert cfg.rlimit_nproc == 64
    assert cfg.rlimit_nofile == 64
    assert cfg.rlimit_fsize_bytes == 16 * 1024 * 1024
    assert cfg.egress_cap_bytes == 65536
    assert cfg.header_bytes == 4096
    assert cfg.quarantine_dir == "/quarantine"


def test_from_env_overrides_each_field() -> None:
    cfg = AnalysisConfig.from_env(
        {
            "ENABLED_CHECKS": "type_sniff",
            "FFPROBE_PATH": "/usr/bin/ffprobe",
            "ANALYSIS_TIMEOUT_S": "12.5",
            "RLIMIT_CPU_S": "9",
            "RLIMIT_AS_BYTES": "1048576",
            "RLIMIT_NPROC": "7",
            "RLIMIT_NOFILE": "33",
            "RLIMIT_FSIZE_BYTES": "2048",
            "EGRESS_CAP_BYTES": "4096",
            "HEADER_BYTES": "512",
            "QUARANTINE_DIR": "/data/quarantine",
        }
    )
    assert cfg.enabled_checks == ("type_sniff",)
    assert cfg.ffprobe_path == "/usr/bin/ffprobe"
    assert cfg.timeout_s == 12.5
    assert cfg.rlimit_cpu_s == 9
    assert cfg.rlimit_as_bytes == 1048576
    assert cfg.rlimit_nproc == 7
    assert cfg.rlimit_nofile == 33
    assert cfg.rlimit_fsize_bytes == 2048
    assert cfg.egress_cap_bytes == 4096
    assert cfg.header_bytes == 512
    assert cfg.quarantine_dir == "/data/quarantine"


def test_enabled_checks_splits_and_strips() -> None:
    cfg = AnalysisConfig.from_env({"ENABLED_CHECKS": " type_sniff , ffprobe "})
    assert cfg.enabled_checks == ("type_sniff", "ffprobe")


def test_from_env_rejects_empty_enabled_checks() -> None:
    with pytest.raises(ValueError):
        AnalysisConfig.from_env({"ENABLED_CHECKS": "  ,  "})


def test_from_env_rejects_unparsable_int() -> None:
    with pytest.raises(ValueError):
        AnalysisConfig.from_env({"RLIMIT_CPU_S": "not-an-int"})


def test_from_env_rejects_unparsable_float() -> None:
    with pytest.raises(ValueError):
        AnalysisConfig.from_env({"ANALYSIS_TIMEOUT_S": "soon"})


def test_config_is_frozen() -> None:
    cfg = AnalysisConfig.from_env({})
    with pytest.raises(AttributeError):
        cfg.timeout_s = 1.0  # type: ignore[misc]
