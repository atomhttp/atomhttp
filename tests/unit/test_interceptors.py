import pytest
import pytest_asyncio

from atomhttp import AsyncAtomHTTP, AtomHTTP


class TestSyncInterceptors:
    def test_request_interceptor_mutates_config(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5)

        def add_header(config):
            config.headers["X-Injected"] = "yes"
            return config

        client.interceptors.request.use(add_header)
        response = client.get("/headers")
        assert response.data["headers"]["X-Injected"] == "yes"

    def test_response_interceptor_mutates_response(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5)

        def wrap(response):
            response.data = {"wrapped": response.data}
            return response

        client.interceptors.response.use(wrap)
        response = client.get("/get")
        assert "wrapped" in response.data

    def test_eject_removes_interceptor(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5)
        calls = []
        idx = client.interceptors.request.use(lambda c: (calls.append(1), c)[1])
        client.interceptors.request.eject(idx)
        client.get("/get")
        assert calls == []

    def test_multiple_interceptors_run_in_order(self, base_url):
        client = AtomHTTP(base_url=base_url, timeout=5)
        order = []
        client.interceptors.request.use(lambda c: (order.append("first"), c)[1])
        client.interceptors.request.use(lambda c: (order.append("second"), c)[1])
        client.get("/get")
        assert order == ["first", "second"]


class TestAsyncInterceptors:
    @pytest.mark.asyncio
    async def test_async_interceptor_is_awaited(self, base_url):
        async with AsyncAtomHTTP(base_url=base_url, timeout=5) as client:

            async def add_header(config):
                config.headers["X-Async"] = "yes"
                return config

            client.interceptors.request.use(add_header)
            response = await client.get("/headers")
            assert response.data["headers"]["X-Async"] == "yes"

    @pytest.mark.asyncio
    async def test_sync_interceptor_works_on_async_client(self, base_url):
        async with AsyncAtomHTTP(base_url=base_url, timeout=5) as client:
            client.interceptors.request.use(lambda c: c)
            response = await client.get("/get")
            assert response.status == 200
