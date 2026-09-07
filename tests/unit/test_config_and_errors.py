import pytest

import atomhttp
from atomhttp import AtomHTTP, RequestConfig
from atomhttp.errors import AtomHTTPError, AtomHTTPNetworkError, AtomHTTPRequestError


class TestModuleLevelFunctions:
    def test_get_works_without_creating_a_client(self, base_url):
        response = atomhttp.get(f"{base_url}/get")
        assert response.status == 200

    def test_post_works_without_creating_a_client(self, base_url):
        response = atomhttp.post(f"{base_url}/anything", data={"a": 1})
        assert response.data["data"] == {"a": 1}


class TestDefaultsAndConfig:
    def test_client_default_headers_merge_with_per_request_headers(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5, headers={"X-Default": "1"})
        response = client.get("/headers", headers={"X-Extra": "2"})
        assert response.data["headers"]["X-Default"] == "1"
        assert response.data["headers"]["X-Extra"] == "2"

    def test_per_request_header_overrides_default(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5, headers={"X-Val": "default"})
        response = client.get("/headers", headers={"X-Val": "override"})
        assert response.data["headers"]["X-Val"] == "override"

    def test_base_url_joins_relative_paths(self, base_url):
        client = AtomHTTP(base_url=base_url + "/", timeout=5)
        response = client.get("get")
        assert response.status == 200

    def test_absolute_url_ignores_base_url(self, base_url):
        client = AtomHTTP(base_url="https://unused.invalid", timeout=5)
        response = client.get(f"{base_url}/get")
        assert response.status == 200

    def test_request_config_copy(self):
        config = RequestConfig(url="/a", method="GET")
        copy = config.copy(method="POST")
        assert config.method == "GET"
        assert copy.method == "POST"
        assert copy.url == "/a"

    def test_sync_client_can_be_converted_to_async_and_back(self, base_url):
        from atomhttp import AsyncAtomHTTP

        sync_client = AtomHTTP(base_url=base_url, timeout=5)
        async_client = sync_client.as_async()
        assert isinstance(async_client, AsyncAtomHTTP)
        assert async_client.cookies is sync_client.cookies

    def test_transform_request_hook(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5)
        response = client.post(
            "/anything",
            data={"a": 1},
            transformRequest=lambda data: {**data, "extra": True},
        )
        assert response.data["data"] == {"a": 1, "extra": True}

    def test_transform_response_hook(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5)
        response = client.get(
            "/get", transformResponse=lambda data: {"transformed": True, **data}
        )
        assert response.data["transformed"] is True


class TestErrors:
    def test_error_hierarchy(self):
        assert issubclass(AtomHTTPRequestError, AtomHTTPError)
        assert issubclass(AtomHTTPNetworkError, AtomHTTPError)

    def test_network_error_on_connection_refused(self):
        client = AtomHTTP(timeout=2)
        with pytest.raises(AtomHTTPNetworkError):
            client.get("http://127.0.0.1:1/unreachable")

    def test_network_error_on_bad_host(self):
        client = AtomHTTP(timeout=2)
        with pytest.raises(AtomHTTPNetworkError):
            client.get("http://this-host-should-not-exist.invalid/")
