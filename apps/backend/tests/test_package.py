def test_backend_package_is_importable() -> None:
    import mori

    assert mori.__doc__ == "Mori backend package."
