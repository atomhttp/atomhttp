import pytest

from ._server import TestServer


@pytest.fixture(scope="session")
def server():
    srv = TestServer().start()
    yield srv
    srv.stop()


@pytest.fixture()
def base_url(server):
    return server.url
