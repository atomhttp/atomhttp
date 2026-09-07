"""
Client Module
--------------
:class:`AtomHTTP` is the primary, **synchronous** client -- no ``await``
required anywhere, every method returns a :class:`~atomhttp.response.Response`
directly. This is a deliberate change from v1, where the entire library was
unusable without ``async``/``await`` even for the simplest ``GET``.

:class:`AsyncAtomHTTP` is the fully optional async counterpart. It shares
100% of the request-building and transport logic with :class:`AtomHTTP` --
it simply runs the same blocking call in a worker thread
(``loop.run_in_executor``) so the event loop stays responsive. There is no
``aiohttp`` anywhere in this library; both clients are backed by the same
``urllib3``-based adapter (:class:`atomhttp.adapters.HTTPAdapter`), which
means connection pooling, retries, and cookies behave identically whether
or not you use ``async``.
"""

import asyncio
import concurrent.futures
import inspect
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from .adapters import HTTPAdapter
from .adapters.base import BaseAdapter
from .config import RequestConfig
from .cookies import CookieJar
from .defaults import Defaults
from .interceptors import InterceptorManager
from .response import Response

__all__ = ["AtomHTTP", "AsyncAtomHTTP", "Interceptors"]


class _InterceptorChannel:
    """Axios-style ``client.interceptors.request.use(fn)`` handle."""

    def __init__(self, manager: InterceptorManager, is_response: bool):
        self._manager = manager
        self._is_response = is_response

    def use(self, fn: Callable) -> int:
        return self._manager.use(fn, is_response=self._is_response)

    def eject(self, index: int) -> None:
        self._manager.eject(index, is_response=self._is_response)


class Interceptors:
    """Holds the ``request``/``response`` interceptor channels for a client."""

    def __init__(self) -> None:
        self.manager = InterceptorManager()
        self.request = _InterceptorChannel(self.manager, is_response=False)
        self.response = _InterceptorChannel(self.manager, is_response=True)


def _build_url(base_url: str, url: str, params: Optional[Dict[str, Any]]) -> str:
    """Join ``base_url`` + ``url`` and merge in query ``params``."""
    is_absolute = url.startswith(("http://", "https://"))
    full = url if is_absolute else f"{base_url.rstrip('/')}/{url.lstrip('/')}" if base_url else url

    if not params:
        return full

    parts = urlsplit(full)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            existing.extend((key, str(v)) for v in value)
        else:
            existing.append((key, str(value)))
    new_query = urlencode(existing)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


class _ClientCore:
    """Shared config-building logic used by both :class:`AtomHTTP` and :class:`AsyncAtomHTTP`."""

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[Dict[str, str]] = None,
        timeout: Union[int, float] = 30,
        adapter: Optional[BaseAdapter] = None,
        cookies: bool = True,
        **default_overrides: Any,
    ):
        self.defaults = Defaults()
        self.defaults.update(
            RequestConfig(baseURL=base_url, headers=headers or {}, timeout=timeout, **default_overrides)
        )
        self.interceptors = Interceptors()
        self._adapter: BaseAdapter = adapter or HTTPAdapter()
        self._cookie_jar: Optional[CookieJar] = CookieJar() if cookies else None

    @property
    def cookies(self) -> Optional[CookieJar]:
        """The client's persistent cookie jar (``None`` if cookies were disabled)."""
        return self._cookie_jar

    def _build_config(self, method: str, url: str, **overrides: Any) -> RequestConfig:
        base = self.defaults.to_dict()
        base["method"] = method.upper()

        params = overrides.pop("params", None)
        base_headers = dict(base.get("headers", {}))
        if "headers" in overrides and overrides["headers"]:
            base_headers.update(overrides.pop("headers"))
        base["headers"] = base_headers

        base.update(overrides)
        base["url"] = _build_url(base.get("baseURL", ""), url, params)
        base.pop("baseURL", None)

        config = RequestConfig(**{k: v for k, v in base.items() if k in RequestConfig.__dataclass_fields__})

        if config.transformRequest and config.data is not None:
            config.data = config.transformRequest(config.data)

        return config

    def _pick_adapter(self, config: RequestConfig) -> BaseAdapter:
        return config.adapter or self._adapter

    def close(self) -> None:
        self._adapter.close()


class AtomHTTP(_ClientCore):
    """Synchronous HTTP client. Every method returns a :class:`Response` directly.

    Example:
        >>> client = AtomHTTP(base_url="https://api.example.com")
        >>> response = client.get("/users/1")
        >>> response.data
        {'id': 1, 'name': 'Ada'}

    Use as a context manager to release pooled connections automatically::

        with AtomHTTP(base_url="https://api.example.com") as client:
            client.get("/health")
    """

    def request(self, method: str = "GET", url: str = "", **kwargs: Any) -> Response:
        """Perform a request. Runs request interceptors, sends it, runs response interceptors."""
        config = self._build_config(method, url, **kwargs)

        for interceptor in self.interceptors.manager.request_interceptors:
            config = self._run_maybe_async(interceptor, config) or config

        adapter = self._pick_adapter(config)
        response = adapter.send(config, self._cookie_jar)

        for interceptor in self.interceptors.manager.response_interceptors:
            response = self._run_maybe_async(interceptor, response) or response

        return response

    @staticmethod
    def _run_maybe_async(fn: Callable, value: Any) -> Any:
        if inspect.iscoroutinefunction(fn):
            return asyncio.run(fn(value))
        return fn(value)

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        return self.request("POST", url, data=data, **kwargs)

    def put(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        return self.request("PUT", url, data=data, **kwargs)

    def patch(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        return self.request("PATCH", url, data=data, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        return self.request("DELETE", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> Response:
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Response:
        return self.request("OPTIONS", url, **kwargs)

    def all(
        self, calls: List[Callable[[], Response]], max_workers: int = 10
    ) -> List[Response]:
        """Run several request thunks concurrently on a thread pool.

        Because the underlying urllib3 pools are thread-safe, this gives you
        real concurrency (and therefore real speedups for I/O-bound batches
        of requests) without needing ``async``/``await`` anywhere.

        Example:
            >>> client.all([
            ...     lambda: client.get("/a"),
            ...     lambda: client.get("/b"),
            ... ])
            [<Response [200 OK]>, <Response [200 OK]>]
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(call) for call in calls]
            return [f.result() for f in futures]

    def as_async(self) -> "AsyncAtomHTTP":
        """Return an :class:`AsyncAtomHTTP` sharing this client's config/adapter/cookies."""
        async_client = AsyncAtomHTTP.__new__(AsyncAtomHTTP)
        async_client.defaults = self.defaults
        async_client.interceptors = self.interceptors
        async_client._adapter = self._adapter
        async_client._cookie_jar = self._cookie_jar
        return async_client

    def __enter__(self) -> "AtomHTTP":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


class AsyncAtomHTTP(_ClientCore):
    """Fully optional async client with the exact same request surface as :class:`AtomHTTP`.

    No ``aiohttp`` involved -- every call is the same ``urllib3``-based
    synchronous adapter, dispatched to a worker thread so it doesn't block
    the event loop.

    Example:
        >>> async def main():
        ...     async with AsyncAtomHTTP(base_url="https://api.example.com") as client:
        ...         response = await client.get("/users/1")
        ...         print(response.data)
    """

    async def request(self, method: str = "GET", url: str = "", **kwargs: Any) -> Response:
        config = self._build_config(method, url, **kwargs)

        for interceptor in self.interceptors.manager.request_interceptors:
            config = await self._run_maybe_async(interceptor, config) or config

        adapter = self._pick_adapter(config)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, adapter.send, config, self._cookie_jar)

        for interceptor in self.interceptors.manager.response_interceptors:
            response = await self._run_maybe_async(interceptor, response) or response

        return response

    @staticmethod
    async def _run_maybe_async(fn: Callable, value: Any) -> Any:
        if inspect.iscoroutinefunction(fn):
            return await fn(value)
        return fn(value)

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        return await self.request("POST", url, data=data, **kwargs)

    async def put(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        return await self.request("PUT", url, data=data, **kwargs)

    async def patch(self, url: str, data: Any = None, **kwargs: Any) -> Response:
        return await self.request("PATCH", url, data=data, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Response:
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> Response:
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> Response:
        return await self.request("OPTIONS", url, **kwargs)

    async def all(self, coros: List[Any]) -> List[Response]:
        """``asyncio.gather`` shortcut for running several requests concurrently."""
        return await asyncio.gather(*coros)

    def as_sync(self) -> "AtomHTTP":
        """Return an :class:`AtomHTTP` sharing this client's config/adapter/cookies."""
        sync_client = AtomHTTP.__new__(AtomHTTP)
        sync_client.defaults = self.defaults
        sync_client.interceptors = self.interceptors
        sync_client._adapter = self._adapter
        sync_client._cookie_jar = self._cookie_jar
        return sync_client

    async def __aenter__(self) -> "AsyncAtomHTTP":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self.close()
