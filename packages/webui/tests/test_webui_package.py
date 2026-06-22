import catalog_webui


def test_package_is_importable() -> None:
    assert catalog_webui.__name__ == "catalog_webui"
