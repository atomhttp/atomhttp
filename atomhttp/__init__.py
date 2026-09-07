"""
AtomHTTP
========
A synchronous-by-default HTTP client for Python, with fully optional async
support, built entirely on :mod:`urllib3` (no ``aiohttp``).

Quick start (no ``async`` required)::

    import atomhttp

    response = atomhttp.get("https://api.example.com/users/1")
    print(response.data)

Or with a configured client::

    from atomhttp import AtomHTTP

    client = AtomHTTP(base_url="https://api.example.com", timeout=10)
    response = client.post("/users", data={"name": "Ada"})

Async is available if you want it, using the exact same urllib3 transport::

    import asyncio
    from atomhttp import AsyncAtomHTTP

    async def main():
        async with AsyncAtomHTTP(base_url="https://api.example.com") as client:
            response = await client.get("/users/1")
            print(response.data)

    asyncio.run(main())
"""

from typing import Any

from .adapters import BaseAdapter, HTTPAdapter, MockAdapter
from .auth import BasicAuth, BearerAuth
from .client import AsyncAtomHTTP, AtomHTTP, Interceptors
from .config import RequestConfig
from .cookies import CookieJar
from .errors import (
    AtomHTTPError,
    AtomHTTPNetworkError,
    AtomHTTPRequestError,
    AtomHTTPTimeoutError,
)
from .form_data import FormData
from .interceptors import InterceptorManager
from .progress import ProgressTracker
from .response import Response
from .version import __version__

__all__ = [
    "__version__",
    # Clients
    "AtomHTTP",
    "AsyncAtomHTTP",
    "Interceptors",
    # Data structures
    "RequestConfig",
    "Response",
    "FormData",
    "CookieJar",
    "ProgressTracker",
    "InterceptorManager",
    # Auth helpers
    "BasicAuth",
    "BearerAuth",
    # Adapters
    "BaseAdapter",
    "HTTPAdapter",
    "MockAdapter",
    # Errors
    "AtomHTTPError",
    "AtomHTTPRequestError",
    "AtomHTTPNetworkError",
    "AtomHTTPTimeoutError",
    # Module-level convenience functions
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "request",
]

# A lazily-created, shared default client -- lets `atomhttp.get(...)` work
# immediately with zero setup, the same way `requests.get(...)` does.
_default_client: Any = None


def _client() -> AtomHTTP:
    global _default_client
    if _default_client is None:
        _default_client = AtomHTTP()
    return _default_client


def request(method: str, url: str, **kwargs: Any) -> Response:
    return _client().request(method, url, **kwargs)


def get(url: str, **kwargs: Any) -> Response:
    return _client().get(url, **kwargs)


def post(url: str, data: Any = None, **kwargs: Any) -> Response:
    return _client().post(url, data=data, **kwargs)


def put(url: str, data: Any = None, **kwargs: Any) -> Response:
    return _client().put(url, data=data, **kwargs)


def patch(url: str, data: Any = None, **kwargs: Any) -> Response:
    return _client().patch(url, data=data, **kwargs)


def delete(url: str, **kwargs: Any) -> Response:
    return _client().delete(url, **kwargs)


def head(url: str, **kwargs: Any) -> Response:
    return _client().head(url, **kwargs)


def options(url: str, **kwargs: Any) -> Response:
    return _client().options(url, **kwargs)
