"""
Request Configuration Module
-----------------------------
Defines :class:`RequestConfig`, the axios-inspired configuration object that
describes a single HTTP request.

Every field has a sane default, so ``RequestConfig()`` alone is a valid
(if useless) configuration. :class:`~atomhttp.client.AtomHTTP` merges a
per-request ``RequestConfig`` with the client's defaults before executing
the request.
"""

from dataclasses import dataclass, field, asdict
from datetime import timedelta
from typing import Any, Callable, Dict, Optional, Union


@dataclass
class RequestConfig:
    """Configuration for a single HTTP request.

    Attributes:
        url: Target URL, absolute or relative to ``baseURL``.
        method: HTTP method (``GET``, ``POST``, ``PUT``, ``PATCH``,
            ``DELETE``, ``HEAD``, ``OPTIONS``). Defaults to ``"GET"``.
        baseURL: Prefix prepended to relative ``url`` values.
        headers: Extra headers to send. Merged on top of client defaults.
        params: Query string parameters, merged into the final URL.
        data: Request body. ``dict``/``list`` -> JSON, :class:`FormData` ->
            ``multipart/form-data``, ``str``/``bytes`` sent as-is.
        timeout: Timeout in seconds (``int``/``float``) or a
            :class:`datetime.timedelta`. Defaults to 30 seconds.
        withCredentials: Whether cookies should be sent/stored for this
            request when using the client's cookie jar.
        auth: ``{"username": ..., "password": ...}`` for HTTP Basic Auth.
        proxy: ``{"host": "http://proxy:8080", "auth": {...}}``.
        maxRedirects: Maximum redirects to follow. ``0`` disables redirects.
        maxContentLength: Max allowed response body size in bytes, or ``-1``
            for unlimited.
        maxBodyLength: Max allowed request body size in bytes, or ``-1`` for
            unlimited.
        transformRequest: Optional ``fn(data) -> data`` applied before the
            built-in serialization logic.
        transformResponse: Optional ``fn(data) -> data`` applied to the
            parsed response body before it's returned to the caller.
        responseType: One of ``"json"``, ``"text"``, ``"blob"``,
            ``"arraybuffer"``, ``"stream"``.
        xsrfCookieName / xsrfHeaderName: If a cookie with this name exists
            in the client's cookie jar for the target host, its value is
            copied into the ``xsrfHeaderName`` request header automatically
            (standard XSRF-double-submit pattern).
        onUploadProgress / onDownloadProgress: ``fn(loaded, total)``
            callbacks for progress reporting.
        socketPath: Path to a Unix domain socket to connect through, instead
            of TCP (e.g. ``"/var/run/docker.sock"``).
        keepAlive: Whether to reuse pooled connections.
        decompress: Whether to transparently decode gzip/deflate responses.
        validateStatus: ``fn(status_code) -> bool``. Return ``False`` to
            raise :class:`~atomhttp.errors.AtomHTTPRequestError`. If left as
            ``None`` (the default) no status-based validation happens and
            every completed response is returned normally, matching v1
            behaviour.
        adapter: Custom adapter instance implementing ``.send(config)``.
        verify: Whether to verify TLS certificates.
        retryConfig: ``{"max_retries": int, "backoff_factor": float,
            "status_forcelist": [int, ...]}``. Applied via urllib3's retry
            machinery.
    """

    # Core request parameters
    url: str = ""
    method: str = "GET"
    baseURL: str = ""

    # Headers and parameters
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Any = None

    # Timing and connection settings
    timeout: Union[int, float, timedelta] = 30
    withCredentials: bool = False

    # Authentication and proxy
    auth: Optional[Dict[str, str]] = None
    proxy: Optional[Dict[str, Any]] = None

    # Request limits and redirects
    maxRedirects: int = 5
    maxContentLength: int = -1
    maxBodyLength: int = -1

    # Data transformation hooks
    transformRequest: Optional[Callable] = None
    transformResponse: Optional[Callable] = None

    # Response handling
    responseType: str = "json"

    # CSRF/XSRF protection
    xsrfCookieName: str = "XSRF-TOKEN"
    xsrfHeaderName: str = "X-XSRF-TOKEN"

    # Progress tracking
    onUploadProgress: Optional[Callable] = None
    onDownloadProgress: Optional[Callable] = None

    # Low-level connection options
    socketPath: Optional[str] = None
    keepAlive: bool = True
    decompress: bool = True

    # Status validation
    validateStatus: Optional[Callable] = None

    # Custom adapter override
    adapter: Optional[Any] = None

    # TLS verification
    verify: bool = True

    # Retry behaviour (actually wired up to the adapter, unlike v1)
    retryConfig: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a ``dict`` of all non-``None`` fields.

        ``timedelta`` timeouts are normalized to seconds so downstream code
        never has to special-case them.
        """
        data = asdict(self)
        if isinstance(self.timeout, timedelta):
            data["timeout"] = self.timeout.total_seconds()
        return {k: v for k, v in data.items() if v is not None}

    def copy(self, **overrides: Any) -> "RequestConfig":
        """Return a shallow copy of this config with ``overrides`` applied."""
        values = {f: getattr(self, f) for f in self.__dataclass_fields__}
        values.update(overrides)
        return RequestConfig(**values)
