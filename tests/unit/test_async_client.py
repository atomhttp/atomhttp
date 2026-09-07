import asyncio
import time

import pytest
import pytest_asyncio

from atomhttp import AsyncAtomHTTP
from atomhttp.errors import AtomHTTPTimeoutError

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture()
async def async_client(base_url):
    async with AsyncAtomHTTP(base_url=base_url, timeout=5) as c:
        yield c


class TestAsyncBasics:
    async def test_get(self, async_client):
        response = await async_client.get("/get", params={"q": "hi"})
        assert response.status == 200
        assert response.data["query"] == {"q": "hi"}

    async def test_post(self, async_client):
        response = await async_client.post("/anything", data={"a": 1})
        assert response.data["data"] == {"a": 1}

    async def test_timeout(self, async_client):
        with pytest.raises(AtomHTTPTimeoutError):
            await async_client.get("/delay/2", timeout=0.2)


class TestAsyncConcurrency:
    async def test_gather_runs_concurrently(self, async_client):
        start = time.perf_counter()
        results = await async_client.all(
            [async_client.get("/delay/0.3") for _ in range(4)]
        )
        elapsed = time.perf_counter() - start
        assert all(r.status == 200 for r in results)
        assert elapsed < 1.0

    async def test_event_loop_is_not_blocked_during_request(self, async_client):
        # A background counter task should keep incrementing while a slow
        # request is in flight -- proof the request truly runs off-thread
        # and doesn't block the event loop.
        counter = {"n": 0}
        stop = asyncio.Event()

        async def ticker():
            while not stop.is_set():
                counter["n"] += 1
                await asyncio.sleep(0.02)

        task = asyncio.create_task(ticker())
        await async_client.get("/delay/0.3")
        stop.set()
        await task
        assert counter["n"] > 5


class TestSyncAsyncBridge:
    async def test_as_sync_shares_cookie_jar(self, base_url):
        async_client = AsyncAtomHTTP(base_url=base_url, timeout=5)
        sync_client = async_client.as_sync()
        assert sync_client.cookies is async_client.cookies
        await async_client.request("GET", "/get")
