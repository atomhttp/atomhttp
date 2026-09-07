"""
Mock Adapter Module
----------------------
A drop-in adapter for tests: register expected responses (or handler
functions) and no real network I/O ever happens. Works identically for
both :class:`~atomhttp.client.AtomHTTP` and
:class:`~atomhttp.client.AsyncAtomHTTP`, same as every other adapter.
"""

import fnmatch
import re
import time
from typing import Any, Callable, Dict, List, Optional, Union

from ..config import RequestConfig
from ..cookies import CookieJar
from ..errors import AtomHTTPNetworkError
from ..response import Response
from .base import BaseAdapter


class MockAdapter(BaseAdapter):
    """In-memory adapter for unit testing.

    Example:
        >>> mock = MockAdapter()
        >>> mock.on("GET", "/users/1", status=200, data={"id": 1, "name": "Ada"})
        >>> client = AtomHTTP(adapter=mock)
        >>> client.get("/users/1").data
        {'id': 1, 'name': 'Ada'}
    """

    def __init__(self) -> None:
        self._routes: List[Dict[str, Any]] = []
        self.history: List[RequestConfig] = []

    def on(
        self,
        method: str,
        url_pattern: str,
        status: int = 200,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
        handler: Optional[Callable[[RequestConfig], Union[Response, Dict[str, Any]]]] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Register a mock route.

        Args:
            method: HTTP method to match (case-insensitive), or ``"*"`` for any.
            url_pattern: ``fnmatch``-style glob (``*`` wildcards) or a string
                starting with ``re:`` for a full regex match against the URL.
            status: Status code to return.
            data: Response body to return.
            headers: Response headers to return.
            handler: Optional callable ``fn(config) -> Response | dict`` for
                dynamic responses. Overrides ``status``/``data``/``headers``.
            error: If set, raise this exception instead of returning a response.
        """
        self._routes.append(
            {
                "method": method.upper(),
                "pattern": url_pattern,
                "status": status,
                "data": data,
                "headers": headers or {},
                "handler": handler,
                "error": error,
            }
        )

    def reset(self) -> None:
        self._routes.clear()
        self.history.clear()

    @staticmethod
    def _matches(pattern: str, url: str) -> bool:
        if pattern.startswith("re:"):
            return re.search(pattern[3:], url) is not None
        return fnmatch.fnmatch(url, pattern) or pattern in url

    def send(self, config: RequestConfig, cookie_jar: Optional[CookieJar] = None) -> Response:
        self.history.append(config)
        start = time.perf_counter()

        for route in self._routes:
            method_ok = route["method"] in ("*", config.method.upper())
            if method_ok and self._matches(route["pattern"], config.url):
                if route["error"] is not None:
                    raise route["error"]

                if route["handler"] is not None:
                    result = route["handler"](config)
                    if isinstance(result, Response):
                        return result
                    result = result or {}
                    return Response(
                        data=result.get("data"),
                        status=result.get("status", 200),
                        status_text=result.get("status_text", "OK"),
                        headers=result.get("headers", {}),
                        config=config,
                        request=config,
                        elapsed=time.perf_counter() - start,
                        url=config.url,
                    )

                response = Response(
                    data=route["data"],
                    status=route["status"],
                    status_text="OK" if route["status"] < 400 else "Error",
                    headers=route["headers"],
                    config=config,
                    request=config,
                    elapsed=time.perf_counter() - start,
                    url=config.url,
                )
                if config.validateStatus and not config.validateStatus(response.status):
                    from ..errors import AtomHTTPRequestError

                    raise AtomHTTPRequestError(
                        f"Request failed with status code {response.status}",
                        request=config,
                        config=config,
                        response=response,
                    )
                return response

        raise AtomHTTPNetworkError(
            f"MockAdapter: no route registered for {config.method} {config.url}", config=config
        )
