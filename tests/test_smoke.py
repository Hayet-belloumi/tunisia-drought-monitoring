import tdm


def test_package_importable() -> None:
    assert tdm.__version__ == "0.1.0"
