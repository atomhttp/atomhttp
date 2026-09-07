"""
Base Adapter Module
---------------------
Adapters are the transport layer: they take a fully-prepared
:class:`~atomhttp.config.RequestConfig` and produce a
:class:`~atomhttp.response.Response`. Everything in AtomHTTP is
synchronous at this layer -- ``send()`` is a plain (blocking) method, never
a coroutine. The async client gets its "async-ness" by running the same
synchronous adapter in a worker thread, not by giving adapters their own
async implementation. This is also why swapping in a custom adapter (e.g.
for testing, or a totally different transport) automatically works for
both the sync and async client.
"""

from typing import Optional

from ..config import RequestConfig
from ..cookies import CookieJar
from ..response import Response


class BaseAdapter:
    """Interface every transport adapter must implement."""

    def send(self, config: RequestConfig, cookie_jar: Optional[CookieJar] = None) -> Response:
        """Execute ``config`` and return a :class:`Response`. Blocking call."""
        raise NotImplementedError

    def close(self) -> None:
        """Release any pooled connections/resources. Safe to call repeatedly."""
        pass
