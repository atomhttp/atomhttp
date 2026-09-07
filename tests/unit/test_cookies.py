import pytest

from atomhttp import AtomHTTP


class TestCookieJar:
    def test_cookies_persist_across_requests(self, base_url):
        with AtomHTTP(base_url=base_url, timeout=5) as client:
            client.get("/cookies/set", params={"session": "abc123"})
            response = client.get("/cookies")
            assert response.data["cookie"] == "session=abc123"

    def test_cookies_disabled(self, base_url):
        with AtomHTTP(base_url=base_url, timeout=5, cookies=False) as client:
            assert client.cookies is None
            client.get("/cookies/set", params={"session": "xyz"})
            response = client.get("/cookies")
            assert response.data["cookie"] is None

    def test_manual_cookie_injection(self, base_url):
        with AtomHTTP(base_url=base_url, timeout=5) as client:
            from urllib.parse import urlsplit

            host = urlsplit(base_url).netloc.split(":")[0]
            client.cookies.set("manual", "value1", domain=host)
            response = client.get("/cookies")
            assert "manual=value1" in response.data["cookie"]

    def test_separate_clients_have_separate_jars(self, base_url):
        client_a = AtomHTTP(base_url=base_url, timeout=5)
        client_b = AtomHTTP(base_url=base_url, timeout=5)
        client_a.get("/cookies/set", params={"session": "for-a-only"})
        response = client_b.get("/cookies")
        assert response.data["cookie"] is None


class TestXSRF:
    def test_xsrf_header_set_from_cookie(self, base_url):
        with AtomHTTP(base_url=base_url, timeout=5) as client:
            client.get("/cookies/set", params={"XSRF-TOKEN": "tok123"})
            response = client.get("/headers")
            # http.server's header dict normalizes casing unpredictably
            # across runs, so compare case-insensitively.
            lowered = {k.lower(): v for k, v in response.data["headers"].items()}
            assert lowered.get("x-xsrf-token") == "tok123"
