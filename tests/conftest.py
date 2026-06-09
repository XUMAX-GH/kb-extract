"""Global pytest config.

H1 (hardness): adapter tests must not make network calls. We deny sockets
globally; specific tests that need them (none expected in v1) must opt in
with @pytest.mark.enable_socket.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-mark every adapter test as socket-disabled."""
    for item in items:
        if "adapters" in str(item.fspath):
            item.add_marker(pytest.mark.disable_socket)


@pytest.fixture(autouse=True)
def _disable_socket_by_default(request):
    """Disable sockets by default; tests can override with enable_socket marker."""
    if request.node.get_closest_marker("enable_socket"):
        return
    pytest_socket = pytest.importorskip("pytest_socket")
    pytest_socket.disable_socket()
    yield
    pytest_socket.enable_socket()