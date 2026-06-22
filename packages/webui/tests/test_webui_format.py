from catalog_webui.domain.format import ed2k_link, short_hash


def test_ed2k_link_is_canonical() -> None:
    link = ed2k_link("a" * 32, "Keroro 062.avi", 12345)
    assert link == f"ed2k://|file|Keroro 062.avi|12345|{'a' * 32}|/"


def test_short_hash_truncates_with_ellipsis() -> None:
    assert short_hash("a" * 32) == "aaaaaaaa…"


def test_short_hash_short_input_is_unchanged() -> None:
    assert short_hash("abc") == "abc"
