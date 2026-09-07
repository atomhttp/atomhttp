"""
Error Module
------------
All AtomHTTP exception classes live here (previously split across
``errors/__init__.py`` + ``errors/http_errors.py`` for no real reason).

Hierarchy
---------
AtomHTTPError                  Base class for everything AtomHTTP raises.
 +-- AtomHTTPRequestError      Bad/invalid request, or a non-2xx response
 |                             rejected by ``validateStatus``.
 +-- AtomHTTPNetworkError      DNS failure, connection refused, TLS errors,
 |                             or any other transport-level failure.
 +-- AtomHTTPTimeoutError      The request did not complete within the
                               configured timeout.
"""

from typing import Any, Optional


class AtomHTTPError(Exception):
    """Base exception for all AtomHTTP errors.

    Attributes:
        message: Human readable description of the error.
        config: The :class:`~atomhttp.config.RequestConfig` used for the
            request that failed.
        response: The :class:`~atomhttp.response.Response` object, if a
            response was actually received from the server.
        request: Alias for ``config``, kept for axios-style familiarity.
        code: Short machine readable error code, e.g. ``"ERR_NETWORK"``.
    """

    def __init__(
        self,
        message: str,
        config: Optional[Any] = None,
        response: Optional[Any] = None,
        request: Optional[Any] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.config = config
        self.response = response
        self.request = request if request is not None else config
        self.code = code

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} code={self.code!r} message={self.message!r}>"


class AtomHTTPRequestError(AtomHTTPError):
    """Raised for malformed requests or rejected (non-2xx) responses."""

    def __init__(
        self,
        message: str,
        request: Optional[Any] = None,
        config: Optional[Any] = None,
        response: Optional[Any] = None,
    ):
        super().__init__(message, config=config, response=response, request=request)
        self.code = f"ERR_BAD_{response.status}" if response is not None else "ERR_BAD_REQUEST"


class AtomHTTPNetworkError(AtomHTTPError):
    """Raised for connection-level failures (DNS, refused, TLS, reset, ...)."""

    def __init__(self, message: str, config: Optional[Any] = None):
        super().__init__(message, config=config)
        self.code = "ERR_NETWORK"


class AtomHTTPTimeoutError(AtomHTTPError):
    """Raised when a request exceeds its configured timeout."""

    def __init__(self, message: str, config: Optional[Any] = None, request: Optional[Any] = None):
        super().__init__(message, config=config, request=request)
        self.code = "ECONNABORTED"
