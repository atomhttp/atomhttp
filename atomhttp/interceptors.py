"""
Interceptor Manager Module
---------------------------
Request/response middleware, axios-style. Interceptors registered here run
for both the sync :class:`~atomhttp.client.AtomHTTP` client and the async
:class:`~atomhttp.client.AsyncAtomHTTP` client.

A request interceptor is ``fn(config: RequestConfig) -> RequestConfig``.
A response interceptor is ``fn(response: Response) -> Response``.
Either may be a regular function or an ``async def`` -- the async client
will ``await`` async interceptors; the sync client runs a small internal
event loop for the rare case where an async interceptor is registered on a
sync client.
"""

from typing import Callable, List


class InterceptorManager:
    """Registers and runs request/response interceptors in order."""

    def __init__(self) -> None:
        self.request_interceptors: List[Callable] = []
        self.response_interceptors: List[Callable] = []

    def use(self, interceptor: Callable, is_response: bool = False) -> int:
        """Register ``interceptor``. Returns an index usable with :meth:`eject`."""
        target = self.response_interceptors if is_response else self.request_interceptors
        target.append(interceptor)
        return len(target) - 1

    def eject(self, index: int, is_response: bool = False) -> None:
        """Remove a previously registered interceptor. No-op if out of range."""
        target = self.response_interceptors if is_response else self.request_interceptors
        if 0 <= index < len(target):
            target.pop(index)

    def clear(self) -> None:
        self.request_interceptors.clear()
        self.response_interceptors.clear()
