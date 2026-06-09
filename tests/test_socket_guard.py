"""H1 sanity: confirm pytest-socket is active.

If a future test runs in a mode where sockets are accidentally enabled, this
will fail loudly.
"""

import socket

import pytest


def test_socket_creation_is_blocked_by_default():
    with pytest.raises(RuntimeError):
        s = socket.socket()
        s.connect(("1.1.1.1", 80))
