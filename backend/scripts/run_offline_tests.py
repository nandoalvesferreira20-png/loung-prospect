"""Run pytest with all non-loopback socket connections/DNS disabled."""
import socket
import os
import sys
import pytest

original_resolve = socket.getaddrinfo
original_connect = socket.socket.connect
allowed = {"localhost", "127.0.0.1", "::1"}


def resolve(host, *args, **kwargs):
    if host not in allowed:
        raise AssertionError("External DNS is forbidden during validation")
    return original_resolve(host, *args, **kwargs)


def connect(connection, address):
    if isinstance(address, tuple) and address[0] not in allowed:
        raise AssertionError("External network is forbidden during validation")
    return original_connect(connection, address)


if __name__ == "__main__":
    os.environ["GOOGLE_PLACES_API_KEY"] = "offline-synthetic-key-not-real"
    os.environ["GROQ_API_KEY"] = "offline-synthetic-key-not-real"
    os.environ["GROQ_MODEL"] = "offline-test-model"
    socket.getaddrinfo = resolve
    socket.socket.connect = connect
    raise SystemExit(pytest.main(sys.argv[1:]))
