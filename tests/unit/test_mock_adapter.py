import pytest

from atomhttp import AtomHTTP, MockAdapter
from atomhttp.errors import AtomHTTPNetworkError, AtomHTTPRequestError


class TestMockAdapter:
    def test_basic_route(self):
        mock = MockAdapter()
        mock.on("GET", "/users/1", status=200, data={"id": 1})
        client = AtomHTTP(adapter=mock)
        response = client.get("/users/1")
        assert response.status == 200
        assert response.data == {"id": 1}

    def test_wildcard_pattern(self):
        mock = MockAdapter()
        mock.on("GET", "/users/*", status=200, data={"matched": True})
        client = AtomHTTP(adapter=mock)
        assert client.get("/users/42").data == {"matched": True}

    def test_regex_pattern(self):
        mock = MockAdapter()
        mock.on("GET", r"re:/items/\d+$", status=200, data={"ok": True})
        client = AtomHTTP(adapter=mock)
        assert client.get("/items/123").data == {"ok": True}

    def test_unmatched_route_raises_network_error(self):
        mock = MockAdapter()
        client = AtomHTTP(adapter=mock)
        with pytest.raises(AtomHTTPNetworkError):
            client.get("/nope")

    def test_dynamic_handler(self):
        mock = MockAdapter()

        def handler(config):
            return {"status": 201, "data": {"echo": config.data}}

        mock.on("POST", "/echo", handler=handler)
        client = AtomHTTP(adapter=mock)
        response = client.post("/echo", data={"x": 1})
        assert response.status == 201
        assert response.data == {"echo": {"x": 1}}

    def test_simulated_error(self):
        mock = MockAdapter()
        mock.on("GET", "/broken", error=AtomHTTPNetworkError("simulated failure"))
        client = AtomHTTP(adapter=mock)
        with pytest.raises(AtomHTTPNetworkError):
            client.get("/broken")

    def test_history_records_requests(self):
        mock = MockAdapter()
        mock.on("GET", "/a", status=200, data={})
        client = AtomHTTP(adapter=mock)
        client.get("/a")
        client.get("/a")
        assert len(mock.history) == 2

    def test_validate_status_with_mock(self):
        mock = MockAdapter()
        mock.on("GET", "/fail", status=500, data={})
        client = AtomHTTP(adapter=mock)
        with pytest.raises(AtomHTTPRequestError):
            client.get("/fail", validateStatus=lambda s: s < 400)

    def test_per_request_adapter_override(self, base_url):
        # A client configured with the real HTTP adapter can still use a
        # mock adapter for a single request via RequestConfig.adapter.
        mock = MockAdapter()
        mock.on("GET", "/override", status=200, data={"mocked": True})
        client = AtomHTTP(base_url=base_url, timeout=5)
        response = client.get("/override", adapter=mock)
        assert response.data == {"mocked": True}
