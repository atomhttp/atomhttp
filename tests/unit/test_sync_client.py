import pytest

from atomhttp import AtomHTTP
from atomhttp.errors import AtomHTTPRequestError, AtomHTTPTimeoutError


@pytest.fixture()
def client(base_url):
    with AtomHTTP(base_url=base_url, timeout=5) as c:
        yield c


class TestBasicRequests:
    def test_get_is_synchronous_and_returns_response_directly(self, client):
        response = client.get("/get", params={"q": "hello"})
        assert response.status == 200
        assert response.ok is True
        assert response.data["query"] == {"q": "hello"}

    def test_post_json_body(self, client):
        response = client.post("/anything", data={"name": "Ada", "age": 30})
        assert response.status == 200
        assert response.data["data"] == {"name": "Ada", "age": 30}
        assert response.data["headers"]["Content-Type"] == "application/json"

    def test_put_patch_delete(self, client):
        assert client.put("/anything", data={"a": 1}).data["method"] == "PUT"
        assert client.patch("/anything", data={"a": 1}).data["method"] == "PATCH"
        assert client.delete("/anything").data["method"] == "DELETE"

    def test_head_and_options(self, client):
        assert client.head("/anything").status == 200
        assert client.options("/anything").status == 200

    def test_string_body_sent_as_plain_text(self, client):
        response = client.post("/anything", data="hello world")
        assert response.data["data"] == "hello world"
        assert "text/plain" in response.data["headers"]["Content-Type"]

    def test_bytes_body(self, client):
        response = client.post("/anything", data=b"raw-bytes")
        assert response.data["body_length"] == len(b"raw-bytes")

    def test_custom_headers_are_sent(self, client):
        response = client.get("/headers", headers={"X-Custom": "value123"})
        assert response.data["headers"]["X-Custom"] == "value123"

    def test_query_params_list_values(self, client):
        response = client.get("/get", params={"tag": ["a", "b"]})
        assert response.data["query"]["tag"] == ["a", "b"]


class TestStatusHandling:
    def test_default_no_raise_on_error_status(self, client):
        # No validateStatus configured -> even a 500 comes back as a normal Response.
        response = client.get("/status/500")
        assert response.status == 500
        assert response.ok is False

    def test_raise_for_status_helper(self, client):
        response = client.get("/status/404")
        with pytest.raises(AtomHTTPRequestError) as exc_info:
            response.raise_for_status()
        assert exc_info.value.response.status == 404

    def test_validate_status_rejects(self, client):
        with pytest.raises(AtomHTTPRequestError) as exc_info:
            client.get("/status/500", validateStatus=lambda s: s < 400)
        assert exc_info.value.code == "ERR_BAD_500"

    def test_validate_status_accepts(self, client):
        response = client.get("/status/201", validateStatus=lambda s: s < 400)
        assert response.status == 201


class TestRedirects:
    def test_follows_redirects_by_default(self, client):
        response = client.get("/redirect/3")
        assert response.status == 200
        assert response.data == {"redirected": True}

    def test_max_redirects_zero_disables_following(self, client):
        response = client.get("/redirect/3", maxRedirects=0)
        assert response.status == 302
        assert response.headers.get("Location") == "/redirect/2"


class TestTimeouts:
    def test_timeout_raises_atomhttp_timeout_error(self, client):
        with pytest.raises(AtomHTTPTimeoutError):
            client.get("/delay/2", timeout=0.2)

    def test_request_completes_within_timeout(self, client):
        response = client.get("/delay/0.1", timeout=2)
        assert response.status == 200


class TestAuth:
    def test_basic_auth_success(self, client):
        response = client.get(
            "/basic-auth/alice/wonderland",
            auth={"username": "alice", "password": "wonderland"},
        )
        assert response.data["authenticated"] is True

    def test_basic_auth_failure(self, client):
        response = client.get(
            "/basic-auth/alice/wonderland",
            auth={"username": "alice", "password": "wrong"},
        )
        assert response.status == 401


class TestResponseTypes:
    def test_text_response_type(self, client):
        response = client.get("/get", responseType="text")
        assert isinstance(response.data, str)

    def test_arraybuffer_response_type(self, client):
        response = client.get("/get", responseType="arraybuffer")
        assert isinstance(response.data, bytes)

    def test_stream_response_type_returns_raw_response(self, client):
        response = client.get("/large", params={"size": 1000}, responseType="stream")
        raw = response.data.read()
        assert len(raw) == 1000
        response.data.release_conn()


class TestContentLimits:
    def test_max_content_length_enforced(self, client):
        with pytest.raises(AtomHTTPRequestError):
            client.get("/large", params={"size": 200_000}, maxContentLength=1000)

    def test_max_body_length_enforced(self, client):
        with pytest.raises(AtomHTTPRequestError):
            client.post("/anything", data=b"x" * 1000, maxBodyLength=100)


class TestCompression:
    def test_gzip_decoded_by_default(self, client):
        response = client.get("/gzip")
        assert response.data == {"gzipped": True}

    def test_decompress_false_returns_raw_bytes(self, client):
        response = client.get("/gzip", decompress=False, responseType="arraybuffer")
        assert response.data[:2] == b"\x1f\x8b"  # gzip magic number


class TestConcurrency:
    def test_all_runs_requests_concurrently(self, client, base_url):
        responses = client.all(
            [
                lambda: client.get("/delay/0.2"),
                lambda: client.get("/delay/0.2"),
                lambda: client.get("/delay/0.2"),
            ]
        )
        assert all(r.status == 200 for r in responses)

    def test_all_is_actually_faster_than_sequential(self, client):
        import time

        start = time.perf_counter()
        client.all([lambda: client.get("/delay/0.3") for _ in range(4)])
        elapsed = time.perf_counter() - start
        # 4 x 0.3s sequential would be >= 1.2s; concurrently it should be well under that.
        assert elapsed < 1.0


class TestProgress:
    def test_download_progress_reports_final_total(self, client):
        events = []
        client.get(
            "/large",
            params={"size": 300_000},
            onDownloadProgress=lambda loaded, total: events.append((loaded, total)),
        )
        assert events
        final_loaded, final_total = events[-1]
        assert final_loaded == final_total == 300_000

    def test_upload_progress_reports_final_total(self, client):
        events = []
        body = b"x" * 200_000
        client.post(
            "/anything",
            data=body,
            onUploadProgress=lambda loaded, total: events.append((loaded, total)),
        )
        assert events
        assert events[-1] == (len(body), len(body))
