"""Global pytest config.

H1 (hardness): network I/O is denied via `--disable-socket` in
[tool.pytest.ini_options].addopts in pyproject.toml. pytest-socket
natively respects per-test @pytest.mark.disable_socket /
@pytest.mark.enable_socket overrides.
"""